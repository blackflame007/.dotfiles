"""SUPER+R — ARBITER trade replay: one paper round trip as a 3D price ribbon you scrub.

From ARBITER's read API (GET only): the last 1,000 fills (/api/trades?book=all), every
closed round trip with a realised result (crypto and funds; prediction markets have no
price bars), and that instrument's bars around it (/api/instrument, the finest range
that covers the trade). Entry: the opening fill when it is in the window, else the
close's held time on the bars (marked as such). Each marker carries its causes as
ARBITER recorded them. Paper only: nothing here trades.

Play flies the camera along the ribbon while the cursor runs from before the entry to
after the exit, captioning each fill as it passes; VECTOR narrates over it.
Verbs: pick <latest|biggest|instrument text|fill id>, play, pause, seek <0..1>.
Keys: Space play/pause, ←/→ scrub, ↑/↓ choose a trade, Enter play it.
"""
import json
import math
import time
import urllib.parse
from datetime import datetime, timezone

import numpy as np

from .arbiter import Feed as ArbiterFeed
from .deckkit import TAU, Deck3D, ascii_, frame_panel, wrap
from .glkit import col

RANGES = [("24h", 86400), ("7d", 7 * 86400), ("30d", 30 * 86400), ("90d", 90 * 86400)]
X0, X1 = -1.25, 1.25


def ts(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")[:26] + "+00:00" if "." in iso
                                      else iso.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return None


def money(v):
    return "--" if v is None else (f"+${v:,.2f}" if v >= 0 else f"-${-v:,.2f}")


def cause_text(f):
    cs = f.get("causes") or []
    if cs:
        return "; ".join(ascii_(c.get("summary") or c.get("kind"), 90) for c in cs[:2])
    return ascii_(f.get("reason"), 120)


class ReplayDeck(Deck3D):
    name = "replay"
    title = "REPLAY // ONE PAPER TRADE, FROM CAUSE TO RESULT"
    hint = "VECTOR: bromigos-live replay pick <instrument> · replay play"

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.pitch, self.yaw, self.persp, self.spin = 0.42, -0.28, 4.0, 0.0
        s = self.s
        self.L["center"] = (890 * s, 690 * s, 470 * s)
        self.api = ArbiterFeed(self.cfg)          # the same read-only client as the ARBITER deck
        self.trades = []          # round trips
        self.ti = 0
        self.bars = None          # (t array, close array, interval)
        self.cur = 0.0            # cursor 0..1 across the window
        self.playing = False
        self.play_t = None
        self.err = None
        self.loading = False
        self.poll_every(self._load_trades, 120, "trades")

    def ready(self):
        return self.bars is not None or self.err is not None

    # ------------------------------------------------------------------ data
    def _load_trades(self):
        fills = self.api.get("/api/trades?limit=1000&book=all", timeout=30).get("trades") or []
        out = []
        for f in fills:
            if f.get("effect") not in ("close", "flip") or not f.get("realized_usd") or f.get("venue") == "kalshi":
                continue
            exit_t = ts(f["at"])
            held = f.get("held_for_s")
            opens = [o for o in fills if o["book"] == f["book"] and o["instrument_id"] == f["instrument_id"]
                     and o.get("effect") in ("open", "flip") and ts(o["at"]) < exit_t]
            op = min(opens, key=lambda o: abs(exit_t - (held or 0) - ts(o["at"]))) if opens else None
            entry_t = ts(op["at"]) if op else (exit_t - held if held else None)
            if entry_t is None:
                continue
            name = ((f.get("by") or [{}])[0].get("name") or f["book"])
            out.append({"id": f["id"], "inst": f["instrument_id"], "label": f["instrument"], "book": f["book"],
                        "agent": name, "entry_t": entry_t, "exit_t": exit_t, "entry": op, "exit": f,
                        "entry_px": op.get("price") if op else None, "exit_px": f.get("price"),
                        "realized": f.get("realized_usd"), "side": "LONG" if f.get("action") == "sell" else "SHORT"})
        out.sort(key=lambda r: -r["exit_t"])
        first = not self.trades
        self.trades = out[:60]
        if first and self.trades:
            self._pick(0)

    def _pick(self, i):
        self.ti = max(0, min(i, len(self.trades) - 1))
        self.bars, self.err, self.cur, self.playing = None, None, 0.0, False
        self.loading = True
        tr = self.trades[self.ti]
        span = tr["exit_t"] - tr["entry_t"]
        w0, w1 = tr["entry_t"] - max(span * 0.3, 1800), tr["exit_t"] + max(span * 0.2, 1200)
        age = time.time() - w0
        rng = next((r for r, sec in RANGES if age < sec * 0.98), "90d")
        try:
            d = self.api.get("/api/instrument?" + urllib.parse.urlencode({"id": tr["inst"], "range": rng}), timeout=30)
            bars = [(ts(b["t"]), b["c"]) for b in d.get("bars") or [] if b.get("c") is not None]
            bars = [b for b in bars if b[0] is not None and w0 <= b[0] <= w1]
            if len(bars) < 4:
                raise RuntimeError(f"only {len(bars)} bars for the window")
            # bars can lag the tape: carry the line to the exit with the fill's own price
            if bars[-1][0] < tr["exit_t"]:
                bars.append((tr["exit_t"], tr["exit_px"]))
                tr["bars_end"] = bars[-2][0]
            t_, c_ = np.array([b[0] for b in bars]), np.array([b[1] for b in bars], np.float64)
            self.bars = (t_, c_, d.get("interval"))
            self.window = (w0, w1)
            if tr["entry_px"] is None:
                tr["entry_px"] = float(np.interp(tr["entry_t"], t_, c_))
                tr["entry_from_bars"] = True
        except Exception as e:
            self.err = str(e)[:120]
        self.loading = False
        self.built_at = None

    # ------------------------------------------------------------------ verbs
    def command(self, verb, args):
        if verb == "pick":
            q = args.lower().strip()
            if not self.trades:
                return "no trades loaded yet"
            if q in ("", "latest"):
                i = 0
            elif q == "biggest":
                i = max(range(len(self.trades)), key=lambda k: abs(self.trades[k]["realized"] or 0))
            else:
                i = next((k for k, tr in enumerate(self.trades) if q == tr["id"].lower() or q in tr["label"].lower()
                          or q in tr["agent"].lower()), None)
                if i is None:
                    return f"no recent round trip matches '{args}'"
            import threading
            threading.Thread(target=self._pick, args=(i,), daemon=True).start()
            tr = self.trades[i]
            return f"picked {tr['label']} by {tr['agent']}: {money(tr['realized'])}"
        if verb == "play":
            if args:
                self.command("pick", args)
            self.playing, self.play_t = True, None
            return "playing"
        if verb == "pause":
            self.playing = False
            return "paused"
        if verb == "seek":
            try:
                self.cur = max(0.0, min(1.0, float(args)))
            except ValueError:
                return "seek takes 0..1"
            return f"at {self.cur:.2f}"
        return "replay verbs: pick <latest|biggest|text|id>, play, pause, seek <0..1>"

    # ------------------------------------------------------------------ geometry
    def _xy(self, t_, px):
        w0, w1 = self.window
        tt, cc = self.bars[0], self.bars[1]
        lo, hi = cc.min(), cc.max()
        tr = self.trades[self.ti]
        for p in (tr["entry_px"], tr["exit_px"]):
            if p:
                lo, hi = min(lo, p), max(hi, p)
        pad = (hi - lo) * 0.08 or 1.0
        x = X0 + (X1 - X0) * (t_ - w0) / (w1 - w0)
        y = -0.32 + 0.64 * (px - lo + pad) / (hi - lo + 2 * pad)
        return x, y

    def animate(self, t, d):
        if self.playing and self.bars is not None:
            if self.play_t is None:
                self.play_t = (t, self.cur if self.cur < 0.98 else 0.0)
            t0, c0 = self.play_t
            self.cur = min(1.0, c0 + (t - t0) / 14.0)
            if self.cur >= 1.0:
                self.playing = False
            self.built_at = None
            # fly along: turn and pull in toward the cursor
            self.yaw += ((-0.35 + 0.7 * self.cur) - self.yaw) * 0.04
            self.pitch += (0.32 - self.pitch) * 0.04

    def frame(self, t, d):
        u = super().frame(t, d)
        p = self.stage.painter
        cx, cy, R = self.L["center"]
        if self.bars is not None and (self.playing or self.cur > 0):
            zoom = 1.0 + 0.35 * math.sin(min(self.cur, 1.0) * math.pi) * (1.0 if self.playing else 0.6)
            from . import glkit
            xw, yw = self._xy(self.window[0] + (self.window[1] - self.window[0]) * self.cur,
                              float(np.interp(self.window[0] + (self.window[1] - self.window[0]) * self.cur,
                                              self.bars[0], self.bars[1])))
            sx, sy, _ = glkit.project([(xw, yw, 0.0)], p.rot[2], (cx, cy, R * zoom, self.persp))[0]
            x0, y0, w0, h0 = self.L["panel"]
            nx = max(x0 + w0 * 0.42, min(x0 + w0 * 0.58, cx - (sx - cx) * 0.5))
            p.ctr[2] = (nx, cy - (sy - cy) * 0.4, R * zoom, self.persp)
        return u

    # ------------------------------------------------------------------ build
    def rebuild_due(self, t):
        return self.built_at is None or t - self.built_at >= (0.05 if self.playing else 0.5)

    def build(self, b, d, t):
        s = self.s
        T = 0.05
        self.header(b, "ARBITER READ API: FILLS, CAUSES, PRICE BARS · PAPER ONLY")
        x, y, w, h = self.L["panel"]
        tr = self.trades[self.ti] if self.trades else None
        sub = (f"{tr['label']} · {tr['agent']} · {money(tr['realized'])}".upper() if tr else "LOADING THE TAPE…")
        frame_panel(b, x, y, w, h, "THE RIBBON", T + 0.05, sub=ascii_(sub, 70))
        self.pick_pts, self.pick_ids = np.zeros((0, 3), np.float32), []
        if self.err:
            b.text(f"NO BARS FOR THIS TRADE: {self.err}".upper(), x + w / 2, y + h / 2, col("amber"), font="s",
                   track=1.5, align="c")
        if tr and self.bars is not None:
            self._ribbon(b, t, tr, T)
        elif tr and self.loading:
            b.text("FETCHING BARS…", x + w / 2, y + h / 2, col("dim"), font="s", track=3, align="c")
        self._side(b, t, T)

    def _ribbon(self, b, t, tr, T):
        s = self.s
        tt, cc, iv = self.bars
        pts = [self._xy(a, c) for a, c in zip(tt, cc)]
        win = (tr["realized"] or 0) >= 0
        pc = "phosphor" if win else "danger"
        ex_x, ex_y = self._xy(tr["exit_t"], tr["exit_px"])
        en_x, en_y = self._xy(tr["entry_t"], tr["entry_px"])
        cur_t = self.window[0] + (self.window[1] - self.window[0]) * self.cur
        # grid floor and time ticks
        for k in range(9):
            gx = X0 + (X1 - X0) * k / 8
            b.line((gx, -0.36, -0.12), (gx, -0.36, 0.12), col("guard"), space=2)
            ta = self.window[0] + (self.window[1] - self.window[0]) * k / 8
            b.text(time.strftime("%m-%d %H:%M", time.localtime(ta)), gx, -0.36, col("dim"), font="xs", track=0.6,
                   space=2, z=0.12, dx=-36, dy=22)
        b.line((X0, -0.36, -0.12), (X1, -0.36, -0.12), col("guard"), space=2)
        # the ribbon: two rails and struts, the held span lit in the trade's colour
        for i in range(len(pts) - 1):
            (x0, y0), (x1, y1) = pts[i], pts[i + 1]
            held = tr["entry_t"] <= tt[i] <= tr["exit_t"]
            past = tt[i] <= cur_t or self.cur <= 0
            c = col(pc if held else "soft", (0.95 if held else 0.55) * (1.0 if past else 0.25))
            gap = tr.get("bars_end") is not None and tt[i] >= tr["bars_end"]
            for z in (-0.035, 0.035):
                b.line((x0, y0, z), (x1, y1, z), c, width=1.4 if held else 1.0, space=2, dash=6 if gap else 0)
            if gap:
                b.text("NO BARS YET · TO THE FILL PRICE", (x0 + x1) / 2, (y0 + y1) / 2, col("dim"), font="xs",
                       track=1, space=2, z=0.04, dx=-60, dy=-10)
            if i % 2 == 0:
                b.line((x0, y0, -0.035), (x0, y0, 0.035), col(pc if held else "dim", 0.5 if past else 0.15), space=2)
            if held and past:
                b.line((x0, y0, 0.0), (x0, -0.36, 0.0), col(pc, 0.10), space=2)
        # entry and exit pylons with their causes
        for (mx, my, label, f, when, px) in ((en_x, en_y, "ENTRY", tr["entry"], tr["entry_t"], tr["entry_px"]),
                                             (ex_x, ex_y, "EXIT", tr["exit"], tr["exit_t"], tr["exit_px"])):
            lit = cur_t >= when or self.cur <= 0
            c = col("white" if label == "ENTRY" else pc, 1.0 if lit else 0.3)
            b.line((mx, -0.36, 0), (mx, my + 0.18, 0), c, width=1.6, space=2)
            b.arc((mx, my, 0), 0, 6 * s, 0, TAU, c, kind=2, space=2)
            b.arc((mx, my, 0), 12 * s, 13.4 * s, 0, TAU, c, segs=8, gap=0.4, spin=0.5, space=2)
            head = f"{label} {time.strftime('%m-%d %H:%M', time.localtime(when))} @ {px:,.6g}"
            if label == "ENTRY" and tr.get("entry_from_bars"):
                head += " (FROM HELD TIME)"
            b.text(head.upper(), mx, my + 0.18, c, font="s", track=1.2, space=2, z=0, dx=8, dy=-6)
            why = cause_text(f) if f else "OPENING FILL OLDER THAN THE LAST 1,000"
            for k, ln in enumerate(wrap(why.upper(), 46)[:3]):
                b.text(ln, mx, my + 0.18, col("soft", 0.9 if lit else 0.3), font="xs", track=0.5, space=2, z=0, dx=8,
                       dy=14 + k * 16)
        # the cursor
        cx_, cy_ = self._xy(cur_t, float(np.interp(cur_t, tt, cc)))
        if self.cur > 0:
            b.line((cx_, -0.36, 0), (cx_, 0.42, 0), col("white", 0.7), space=2)
            b.arc((cx_, cy_, 0), 0, 5 * s, 0, TAU, col("white"), kind=2, space=2)
            b.text(f"{time.strftime('%a %H:%M', time.localtime(cur_t))} · {float(np.interp(cur_t, tt, cc)):,.6g}".upper(),
                   cx_, 0.42, col("white"), font="xs", track=1, space=2, z=0, dx=8, dy=-6)
        # caption: what happens at the cursor
        cap = None
        if self.playing or self.cur > 0:
            if abs(cur_t - tr["entry_t"]) < (self.window[1] - self.window[0]) * 0.06:
                cap = "ENTRY · " + (cause_text(tr["entry"]) if tr["entry"] else "the opening fill")
            elif abs(cur_t - tr["exit_t"]) < (self.window[1] - self.window[0]) * 0.06:
                cap = f"EXIT · {money(tr['realized'])} · " + cause_text(tr["exit"])
        if cap:
            x, y, w, h = self.L["panel"]
            lines = wrap(ascii_(cap).upper(), 90)[:2]
            b.plate(x + 40 * s, y + h - 110 * s, w - 80 * s, 80 * s, 0.9)
            for k, ln in enumerate(lines):
                b.text(ln, x + w / 2, y + h - 74 * s + k * 26 * s, col("white" if k == 0 else "soft"), font="m",
                       track=1, align="c")

    def _side(self, b, t, T):
        s = self.s
        x, y, w, h = self.L["side"]
        frame_panel(b, x, y, w, h, "ROUND TRIPS", T + 0.1, sub="↑↓ CHOOSE · ENTER PLAY · CLICK")
        yy = y + 70 * s
        self.rows = []
        first = max(0, self.ti - 14)
        for i, tr in enumerate(self.trades[first:first + 24]):
            k = first + i
            on = k == self.ti
            if on:
                b.plate(x + 10 * s, yy - 18 * s, w - 20 * s, 38 * s, 0.9)
                b.rect(x + 10 * s, yy - 18 * s, w - 20 * s, 38 * s, col("soft"))
            c = "phosphor" if (tr["realized"] or 0) >= 0 else "danger"
            b.text(f"{time.strftime('%H:%M', time.localtime(tr['exit_t']))} {ascii_(tr['label'], 22)}".upper(),
                   x + 20 * s, yy, col("white" if on else "soft"), font="xs", track=0.8)
            b.text(money(tr["realized"]), x + w - 20 * s, yy, col(c), font="xs", track=0.8, align="r")
            b.text(ascii_(tr["agent"], 50).upper(), x + 20 * s, yy + 15 * s, col("dim"), font="xs", track=0.4)
            self.rows.append((x + 10 * s, yy - 18 * s, w - 20 * s, 38 * s, k))
            yy += 40 * s

    def side_click(self, x, y):
        for rx, ry, rw, rh, k in getattr(self, "rows", []):
            if rx <= x <= rx + rw and ry <= y <= ry + rh:
                import threading
                threading.Thread(target=self._pick, args=(k,), daemon=True).start()
                return True
        return False

    def extra_key(self, name):
        if name == "space":
            self.playing = not self.playing
            self.play_t = None
        elif name in ("Up", "Down") and self.trades:
            import threading
            threading.Thread(target=self._pick, args=(self.ti + (-1 if name == "Up" else 1),), daemon=True).start()
        elif name in ("Return", "KP_Enter"):
            self.playing, self.play_t = True, None
        elif name in ("comma", "period"):
            self.cur = max(0.0, min(1.0, self.cur + (-0.02 if name == "comma" else 0.02)))
        self.built_at = None
        return True

    def key(self, name):
        if name in ("Left", "Right") and self.bars is not None:   # scrub instead of turning
            self.playing = False
            self.cur = max(0.0, min(1.0, self.cur + (-0.02 if name == "Left" else 0.02)))
            self.built_at = None
            return True
        return super().key(name)


DECK = ReplayDeck
