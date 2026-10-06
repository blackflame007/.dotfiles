"""ARBITER feed: read-only GETs against the console API (the console's LAN
URL comes from the private overlay, endpoints.arbiter, via config.py).

Never touches anything that trades or arms: the only verbs used are GET, and
the only paths are the read endpoints below. The live/* endpoints (arms,
readiness) need a session and are not used; "real money" is read from
/api/overview/now (agents.real_money) and /api/performance.

The heavy reads (roster, road, ~3 MB together) run only while the deck is open,
every few minutes; the light ones every 20-60 s.
"""
import json
import os
import ssl
import threading
import time
import urllib.parse
import urllib.request

READS = {  # name: (path, seconds between reads while open)
    "now": ("/api/overview/now", 30),
    "overview": ("/api/overview", 30),
    "perf": ("/api/performance?tf=24h", 60),
    "trades": ("/api/trades?limit=40", 20),
    "positions": ("/api/positions", 60),
    "impact": ("/api/events/impact/feed", 90),
    "roster": ("/api/roster", 180),
    "road": ("/api/agents/road", 180),
}


class Feed:
    def __init__(self, cfg):
        a = cfg.get("arbiter", {})
        self.base = (a.get("console") or "").rstrip("/")
        ca = os.path.expanduser(cfg.get("cluster", {}).get("ca_file", "") or "")
        self.ctx = ssl.create_default_context(cafile=ca) if ca and os.path.exists(ca) else ssl.create_default_context()
        self.lock = threading.Lock()
        self.d = {}
        self.err = {}
        self.at = {}
        self.bars = {}          # instrument id -> [(t, close)]
        self.bars_at = 0.0
        self.version = 0
        self.stop = threading.Event()
        self.thread = None

    def get(self, path, timeout=15):
        if not self.base:
            raise OSError("no ARBITER console configured (private overlay endpoints.arbiter)")
        req = urllib.request.Request(self.base + path, headers={"Accept": "application/json"}, method="GET")
        with urllib.request.urlopen(req, timeout=timeout, context=self.ctx) as r:
            return json.load(r)

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop.clear()
        self.thread = threading.Thread(target=self._loop, daemon=True, name="arbiter-feed")
        self.thread.start()

    def close(self):
        self.stop.set()

    def snapshot(self):
        with self.lock:
            return dict(self.d), dict(self.bars), dict(self.err), self.version

    def _fetch(self, name, path):
        try:
            v = self.get(path)
            with self.lock:
                self.d[name] = v
                self.err.pop(name, None)
                self.version += 1
        except Exception as e:  # keep the last good value; say what failed
            with self.lock:
                self.err[name] = str(e)[:80]
        self.at[name] = time.monotonic()

    def _loop(self):
        while not self.stop.is_set():
            now = time.monotonic()
            due = [(n, p) for n, (p, every) in READS.items() if now - self.at.get(n, -1e9) >= every]
            # light ones first so the deck fills fast; heavy ones on their own threads
            ths = [threading.Thread(target=self._fetch, args=(n, p), daemon=True) for n, p in due]
            for t in ths:
                t.start()
            for t in ths:
                t.join(30)
            if now - self.bars_at > 300:
                self.bars_at = now
                self._fetch_bars()
            self.stop.wait(2.0)

    def _fetch_bars(self):
        pos = (self.d.get("positions") or {}).get("positions") or []
        top = sorted(pos, key=lambda p: -abs(p.get("notional_usd") or 0))[:5]
        out = {}
        for p in top:
            iid = p.get("instrument_id")
            if not iid:
                continue
            rng = "30d" if (p.get("venue") == "equities") else "7d"
            try:
                v = self.get("/api/instrument?" + urllib.parse.urlencode({"id": iid, "range": rng}))
                out[iid] = [(b["t"], b["c"]) for b in v.get("bars") or [] if b.get("c") is not None]
            except Exception:
                continue
        with self.lock:
            self.bars = out
            self.version += 1
