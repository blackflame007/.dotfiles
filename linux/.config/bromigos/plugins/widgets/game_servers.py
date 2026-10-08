"""GAME SERVERS: the Pelican game servers on the homelab (the Minecraft network and
Satisfactory) — state, players online/max, CPU and memory, a network total, and the names
of the Minecraft players when the proxy shares them.

Data:
  * Prometheus (endpoints.prometheus, homelab CA), one instant query every 15 s for the
    pelican-exporter series (homelab helm/pelican-exporter, which refreshes every 30 s):
    pelican_server_{state,players_online,players_max,cpu_percent,memory_bytes,uptime_seconds}
    labelled server_uuid / server_name / game, plus pelican_exporter_up.
  * Player names: a Minecraft server-list ping to the proxy's public address
    (games.minecraft_ping, "host:port") every 60 s. Its players.sample lists who is on, when
    the proxy is set to share it; placeholder entries (zero UUIDs, non-username text) are
    dropped. Satisfactory's API gives a count only, so it shows no names.
  * Clicks open the server in the Pelican panel (endpoints.pelican) when that is set.
"""
import json
import os
import re
import socket
import ssl
import struct
import threading
import time
import urllib.parse
import urllib.request
import weakref

import draw as D
import panels as P
import sources as S

LAYOUT = {"width": 470, "height": 372}

CA = os.path.expanduser("~/.config/homelab/homelab-ca.crt")
QUERY = ('{__name__=~"pelican_server_(state|players_online|players_max|cpu_percent|memory_bytes|uptime_seconds)'
         '|pelican_exporter_up"}')
PROM_EVERY, PING_EVERY = 15, 60
# Exporter encoding: 1 running, 2 starting, 3 stopping, 0 offline, -1 unreachable.
STATES = {1: ("RUNNING", "phosphor"), 2: ("STARTING", "amber"), 3: ("STOPPING", "amber"),
          0: ("OFFLINE", "danger"), -1: ("UNREACHABLE", "danger")}
PROXY = re.compile(r"velocity|proxy|bungee|waterfall", re.I)
USERNAME = re.compile(r"^[.*]?\w{1,16}$")           # Java names; Floodgate prefixes Bedrock ones
GAMES = {"minecraft": "MINECRAFT NETWORK", "satisfactory": "SATISFACTORY"}


def _ctx():
    return ssl.create_default_context(cafile=CA) if os.path.exists(CA) else ssl.create_default_context()


def _varint(n):
    out = b""
    while True:
        b, n = n & 0x7F, n >> 7
        out += bytes([b | 0x80]) if n else bytes([b])
        if not n:
            return out


def slp(addr, timeout=5):
    """Minecraft server-list ping to "host:port" -> the status JSON's players dict."""
    host, _, port = addr.rpartition(":")
    host, port = host or addr, int(port or 25565)
    with socket.create_connection((host, port), timeout) as s:
        s.settimeout(timeout)
        hs = b"\x00" + _varint(770) + _varint(len(host)) + host.encode() + struct.pack(">H", port) + _varint(1)
        s.sendall(_varint(len(hs)) + hs + _varint(1) + b"\x00")
        f = s.makefile("rb")

        def rv():
            n = i = 0
            while True:
                b = f.read(1)
                if not b:
                    raise OSError("connection closed mid-reply")
                n |= (b[0] & 0x7F) << (7 * i)
                i += 1
                if not b[0] & 0x80:
                    return n
        rv()                                          # packet length
        rv()                                          # packet id
        blob = f.read(rv())
    return json.loads(blob.decode("utf-8")).get("players") or {}


class GameServersPanel(P.Panel):
    name, title = "game_servers", "GAME SERVERS"
    interval = 1.0                       # redraw cadence for the freshness clock; data in a thread
    ROW = 40

    def __init__(self, cfg=None):
        super().__init__(cfg)
        self.servers = []                # [{uuid, name, game, state, on, max, cpu, mem, up}]
        self.exporter_up = None
        self.state, self.error, self.fetched = "waiting", "", 0
        self.names, self.ping_state, self.ping_online, self.pinged, self.ping_err = None, "waiting", None, 0, ""
        self.pulse_at = 0
        threading.Thread(target=GameServersPanel._loop, args=(weakref.ref(self),), daemon=True).start()

    @property
    def animating(self):
        return time.time() - self.pulse_at < 1.6

    @animating.setter
    def animating(self, _v):
        pass

    # ------------------------------------------------------------ data (thread)
    @staticmethod
    def _loop(ref):
        """Holds the panel only weakly, so a hot reload's old instance lets its thread end."""
        next_ping = 0
        while True:
            p = ref()
            if p is None:
                return
            p._poll()
            if time.time() >= next_ping:
                p._ping()
                next_ping = time.time() + PING_EVERY
            del p
            time.sleep(PROM_EVERY)

    def _poll(self):
        base = S.PRIV.url("prometheus")
        if not base:
            self.state, self.error = "unset", "no Prometheus configured (private overlay: endpoints.prometheus)"
            return
        try:
            url = base.rstrip("/") + "/api/v1/query?" + urllib.parse.urlencode({"query": QUERY})
            with urllib.request.urlopen(url, timeout=6, context=_ctx()) as r:
                rows = json.load(r)["data"]["result"]
        except (OSError, ValueError, KeyError) as e:
            self.state, self.error = "down", str(e)[:100]
            return
        by, up = {}, None
        for row in rows:
            m, v = row["metric"], float(row["value"][1])
            if m["__name__"] == "pelican_exporter_up":
                up = v
                continue
            uid = m.get("server_uuid")
            if not uid:
                continue
            s = by.setdefault(uid, {"uuid": uid, "name": m.get("server_name") or uid[:8],
                                    "game": m.get("game") or "other"})
            s[m["__name__"].replace("pelican_server_", "")] = v
        servers = list(by.values())
        servers.sort(key=lambda s: (list(GAMES).index(s["game"]) if s["game"] in GAMES else len(GAMES),
                                    s["game"], not PROXY.search(s["name"]), s["name"].lower()))
        self.servers, self.exporter_up = servers, up
        self.state = "ok" if up == 1 else ("stale" if servers else "empty")
        self.error = "" if up == 1 else ("the exporter could not reach the Pelican API" if up == 0
                                         else "no pelican-exporter series in Prometheus")
        self.fetched = self.pulse_at = time.time()

    def _ping(self):
        addr = S.PRIV.get("games.minecraft_ping", "")
        if not addr:
            self.ping_state, self.names = "unset", None
            return
        try:
            pl = slp(addr)
        except (OSError, ValueError) as e:
            self.ping_state, self.names, self.ping_err = "down", None, str(e)[:80]
            return
        zero = "00000000-0000-0000-0000-000000000000"
        self.names = [p["name"] for p in pl.get("sample") or []
                      if isinstance(p, dict) and p.get("id") != zero and USERNAME.match(str(p.get("name", "")))]
        self.ping_online = pl.get("online")
        self.ping_state, self.pinged = "ok", time.time()

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _url(uuid=None):
        return S.PRIV.url("pelican", f"/server/{uuid[:8]}" if uuid else "") or None

    def _act(self, uuid=None):
        u = self._url(uuid)
        return (lambda: P.open_url(u)) if u else None

    @staticmethod
    def _players_src(s):
        if s["game"] == "minecraft":
            return ("a server-list ping to the proxy, which answers for the whole network" if PROXY.search(s["name"])
                    else "a server-list ping to this backend (players here also count at the proxy)")
        if s["game"] == "satisfactory":
            return "the dedicated server's HTTPS API (QueryServerState)"
        return "no player probe for this game"

    def totals(self):
        """Network players: Minecraft counted once (at the proxy, or the busiest server when
        there is none), plus every other game's servers."""
        mc = [s for s in self.servers if s["game"] == "minecraft" and "players_online" in s]
        prox = [s for s in mc if PROXY.search(s["name"])]
        n = sum(int(s["players_online"]) for s in prox) if prox else max((int(s["players_online"]) for s in mc),
                                                                          default=0)
        n += sum(int(s["players_online"]) for s in self.servers
                 if s["game"] != "minecraft" and "players_online" in s)
        counted = bool(mc) or any("players_online" in s for s in self.servers)
        return (n if counted else None), (prox[0]["name"] if prox else None)

    # ------------------------------------------------------------ draw
    def draw(self, cr, w, h):
        age = time.time() - self.fetched if self.fetched else None
        right, rcol = {"ok": (f"SYNC {int(age or 0)}s AGO", "static"),
                       "stale": ("EXPORTER DOWN", "amber"),
                       "empty": ("NO EXPORTER DATA", "amber"),
                       "down": ("PROMETHEUS UNREACHABLE", "danger"),
                       "unset": ("NO PROMETHEUS SET", "danger"),
                       "waiting": ("CONNECTING", "static")}[self.state]
        top = D.frame(cr, w, h, self.title, right, rcol)
        if self.state == "ok":
            pulse = max(0.0, 1 - (time.time() - self.pulse_at) / 1.6)
            tw = D.layout(cr, right.upper(), 11, "semibold", 0.18).get_pixel_size()[0]
            D.dot(cr, w - 16 - tw - 10, 18, 2.5 + 2 * pulse, "phosphor", glow=True)
        self.region(0, 0, w, 34, "Game servers on the homelab's Pelican panel, from Prometheus (pelican-exporter, "
                    f"which asks the Pelican API every 30 s; this panel reads it every {PROM_EVERY} s). "
                    f"State: {self.state}{' - ' + self.error if self.error else ''}."
                    + (" Click to open the Pelican panel." if self._url() else
                       " Set endpoints.pelican in the private overlay to open the panel on click."),
                    self._act())
        x0, x1 = 16, w - 16
        if not self.servers:
            D.text(cr, x0, top + 10, self.error or "waiting for the first reading", 12,
                   "amber" if self.state != "waiting" else "static", width=x1 - x0, wrap=True)
            self.region(x0, top, x1 - x0, 40, "No game server readings yet: " + (self.error or "first poll pending."))
            return
        y = top
        # --- summary strip (as LAB's): network players, servers running, the exporter
        total, proxy = self.totals()
        running = sum(1 for s in self.servers if s.get("state") == 1)
        sats = [s for s in self.servers if s["game"] != "minecraft"]
        items = [
            ("PLAYERS", "--" if total is None else str(total),
             "static" if total is None else "phosphor" if total else "soft",
             "Players online across the network right now: Minecraft counted once "
             + (f"at the proxy ({proxy}), since every player passes through it" if proxy else
                "(the busiest server; no proxy found)")
             + (", plus " + ", ".join(s["name"] for s in sats) if sats else "")
             + ". From pelican-exporter via Prometheus."),
            ("RUNNING", f"{running}/{len(self.servers)}", "phosphor" if running == len(self.servers) else "amber",
             "Game servers Pelican reports as running / all servers on the panel (amber when any is not running)."),
            ("PANEL API", {1: "OK", 0: "DOWN"}.get(self.exporter_up, "--"),
             {1: "phosphor", 0: "danger"}.get(self.exporter_up, "static"),
             "Whether pelican-exporter's last pass reached the Pelican panel API (pelican_exporter_up). "
             "When DOWN, the rows show the last readings Prometheus still holds."),
        ]
        cw = (x1 - x0) / len(items)
        for i, (k, v, col, tip) in enumerate(items):
            ix = x0 + i * cw
            D.label(cr, ix, y, k, "dim")
            D.text(cr, ix, y + 14, v, 20, col, "bold", glow=col == "phosphor")
            self.region(ix, y, cw - 6, 40, tip, self._act())
        y += 50
        D.rule(cr, x0, y, x1)
        y += 10
        # --- one group per game
        for game in dict.fromkeys(s["game"] for s in self.servers):
            rows = [s for s in self.servers if s["game"] == game]
            head = GAMES.get(game, game.upper())
            D.label(cr, x0, y, head, "phosphor", size=10)
            hw = D.layout(cr, head.upper(), 10, "semibold", 0.18).get_pixel_size()[0]
            D.label(cr, x1, y, "ONLINE / MAX", "static", size=10, align="right")
            D.rule(cr, x0 + hw + 10, y + 7, x1 - 110, "dim", 0.35)
            self.region(x0, y, x1 - x0, 16, f"{head.title()}: {len(rows)} server(s) on Pelican. The number at the "
                        "right of each row is players online / player slots.")
            y += 20
            for s in rows:
                self._row(cr, x0, x1, y, s)
                y += self.ROW
            y = self._names(cr, x0, x1, y, game, rows)
            y += 8

    def _row(self, cr, x0, x1, y, s):
        st_txt, st_col = STATES.get(int(s["state"]), ("UNKNOWN", "static")) if "state" in s else ("NO STATE", "static")
        act = self._act(s["uuid"])
        click = " Click to open it in the Pelican panel." if act else ""
        on, mx = s.get("players_online"), s.get("players_max")
        cpu, mem, up = s.get("cpu_percent"), s.get("memory_bytes"), s.get("uptime_seconds")
        role = "PROXY" if s["game"] == "minecraft" and PROXY.search(s["name"]) else None
        # whole row first; the parts below override it with their own hints
        self.region(x0, y, x1 - x0, self.ROW - 4,
                    f"{s['name']} ({s['game']}, Pelican server {s['uuid'][:8]}): {st_txt.lower()}"
                    + (f", up {S.duration(up)}" if up else "")
                    + (f". Players {int(on)}/{int(mx or 0)} from {self._players_src(s)}" if on is not None
                       else ". No player count (the probe got no answer)")
                    + (f". CPU {cpu:.1f}%, memory {S.human(mem)}" if cpu is not None else "")
                    + ". Read from Prometheus (pelican-exporter, every 30 s)." + click, act)
        # state light + name
        D.dot(cr, x0 + 4, y + 9, 3.5, st_col, glow=st_col == "phosphor")
        self.region(x0 - 2, y, 14, 18, f"{s['name']} state from Pelican: {st_txt.lower()} "
                    "(green running, amber starting/stopping, red offline or unreachable)." + click, act)
        D.text(cr, x0 + 14, y + 1, s["name"].upper(), 12, "soft", "semibold", spacing=0.04, width=200)
        sub = " · ".join(b.upper() for b in (role, st_txt, f"UP {S.duration(up)}" if up and int(s.get("state", 0)) == 1
                                     else None) if b)
        D.text(cr, x0 + 14, y + 19, sub, 10, st_col if st_col != "phosphor" else "static", "semibold",
               spacing=0.08, width=196)
        # CPU and memory, small
        cx = x0 + 222
        D.label(cr, cx, y + 2, "CPU", "dim", size=10)
        D.text(cr, cx, y + 18, "--" if cpu is None else (f"{cpu:.1f}%" if cpu < 10 else f"{cpu:.0f}%"), 11, "soft")
        self.region(cx - 2, y, 58, self.ROW - 4, f"{s['name']} CPU: "
                    + ("no reading" if cpu is None else f"{cpu:.1f}%")
                    + " (Wings' cpu_absolute: 100% = one full core), from pelican-exporter." + click, act)
        mx_ = cx + 62
        D.label(cr, mx_, y + 2, "MEM", "dim", size=10)
        D.text(cr, mx_, y + 18, "--" if mem is None else S.human(mem), 11, "soft")
        self.region(mx_ - 2, y, 80, self.ROW - 4, f"{s['name']} memory in use: "
                    + ("no reading" if mem is None else S.human(mem)) + " (Wings), from pelican-exporter." + click, act)
        # players online / max, the headline
        if on is None:
            D.text(cr, x1, y + 4, "--", 20, "static", "bold", align="right")
            pw = 40
            tip = f"{s['name']}: no player count. " + (
                "The exporter's probe got no answer this pass." if s["game"] in ("minecraft", "satisfactory")
                else "The exporter has no player probe for this game.")
        else:
            mw, _ = D.text(cr, x1, y + 11, f"/{int(mx or 0)}", 12, "dim", "semibold", align="right")
            ow, _ = D.text(cr, x1 - mw - 2, y + 2, str(int(on)), 20, "phosphor" if on else "soft", "bold",
                           align="right", glow=bool(on))
            pw = mw + ow + 6
            tip = (f"{s['name']}: {int(on)} player(s) online of {int(mx or 0)} slots, from {self._players_src(s)}; "
                   "read by pelican-exporter every 30 s.")
        self.region(x1 - max(pw, 60), y, max(pw, 60), self.ROW - 4, tip + click, act)
        D.rule(cr, x0 + 14, y + self.ROW - 5, x1, "guard", 0.6)

    def _names(self, cr, x0, x1, y, game, rows):
        """Who is on: names from the proxy's list-ping sample (Minecraft only); never guessed."""
        if game == "minecraft":
            n = next((int(s["players_online"]) for s in rows if PROXY.search(s["name"]) and "players_online" in s),
                     None)
            D.label(cr, x0 + 14, y + 1, "ON NOW", "dim", size=10)
            if self.ping_state == "unset":
                txt, col = "NAMES OFF · SET games.minecraft_ping", "static"
                tip = ("Player names come from a server-list ping to the proxy's public address; set "
                       "games.minecraft_ping (host:port) in the private overlay to turn them on.")
            elif self.ping_state == "down":
                txt, col = "LIST PING FAILED · COUNT ONLY", "amber"
                tip = f"The server-list ping to the proxy failed ({self.ping_err}); counts above still hold."
            elif self.ping_state == "waiting":
                txt, col = "PINGING THE PROXY", "static"
                tip = "Waiting for the first server-list ping to the proxy."
            elif self.names:
                more = max(0, int(self.ping_online or 0) - len(self.names))
                txt, col = ", ".join(self.names) + (f" +{more} MORE" if more else ""), "soft"
                tip = (f"Minecraft players on the network now ({len(self.names)} named"
                       + (f", {more} more the proxy did not list" if more else "")
                       + f"), from the proxy's server-list ping sample, {int(time.time() - self.pinged)} s ago "
                       f"(every {PING_EVERY} s).")
            elif (self.ping_online or 0) > 0:
                txt, col = f"{int(self.ping_online)} ONLINE · THE PROXY SHARES NO NAMES", "static"
                tip = ("The proxy's server-list ping reports players but lists no names (Velocity's "
                       "sample-players-in-ping is off), so only the count is shown.")
            else:
                txt, col = "NO ONE ONLINE", "static"
                tip = (f"The proxy's server-list ping ({int(time.time() - self.pinged)} s ago, every {PING_EVERY} s) "
                       "reports no players" + (f"; the exporter's count is {n}" if n else "") + ".")
            D.text(cr, x0 + 76, y, txt if col == "soft" else txt.upper(), 11, col,
                   "medium" if col == "soft" else "semibold", width=x1 - x0 - 76)
            self.region(x0, y - 2, x1 - x0, 18, tip)
            return y + 20
        D.label(cr, x0 + 14, y + 1, "ON NOW", "dim", size=10)
        D.label(cr, x0 + 76, y + 1, "COUNT ONLY · NO NAMES FROM THIS GAME", "static", size=10)
        self.region(x0, y - 2, x1 - x0, 18, f"{GAMES.get(game, game).title()} reports how many players are on, "
                    "not who: its API and the exporter carry a count only, so no names are shown.")
        return y + 20


PANEL = GameServersPanel
