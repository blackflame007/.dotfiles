"""SUPER+G — the ARBITER holo deck: the Floor as a hologram, from real reads.

  * the paper portfolio core: equity, P&L since the start, drawdown vs its cut;
  * every agent (rule + learning) as a star on the road to live: concentric
    rings are the road's gates, outermost "proven on history" in to "in the paper
    portfolio", then the live road's gates inside the core, ending at the REAL
    MONEY ring — empty, amber, OFF. An agent sits in the band of the next gate
    it has not passed; funded books orbit the core sized by weight;
  * colour = the agent's own P&L (phosphor up, red down), size = |P&L|/weight;
  * trades: light pulses from the agent that made them into the core, fading
    with age; the tape shows each fill with its cause;
  * the referee's lineup cohort, the event-impact feed, price ribbons of the
    largest holdings;
  * drag to spin, hover a star for its name, click for its card.

Paper only. Real money is shown as what it is: off, not armed, 0 agents.
"""
import hashlib
import math
import time
from datetime import datetime, timezone

import numpy as np

from . import gadgets, glkit
from .arbiter import Feed
from .glkit import col, level
from .overlays import Base, ease

TAU = 2 * math.pi
PORT_ROAD = ["history", "warmup", "record90", "evidence", "portfolio_level", "review", "funded"]
LIVE_ROAD = ["week", "record", "calm", "live_level", "live"]
R_PORT = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4]
R_LIVE = [0.32, 0.27, 0.22, 0.17, 0.12]
R_REAL = 0.07


def _ascii(s, n=None):
    s = "".join(ch if 32 <= ord(ch) < 127 or ch in "·°→←↑↓±×" else "" for ch in (s or ""))
    s = " ".join(s.split())
    return s[:n] if n else s


def _wrap(s, n):
    out, line = [], ""
    for w in s.split():
        if len(line) + len(w) + 1 > n:
            out.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    if line:
        out.append(line)
    return out


def _ago(iso):
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00")[:26] + "+00:00" if "." in iso else iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - t).total_seconds()


def _hash01(s, k=0):
    h = hashlib.blake2b(f"{s}:{k}".encode(), digest_size=4).digest()
    return int.from_bytes(h, "little") / 2 ** 32


def money(v, sign=True):
    if v is None:
        return "--"
    s = "+" if (sign and v > 0) else ("-" if v < 0 else "")
    a = abs(v)
    return f"{s}${a:,.0f}" if a >= 100 else f"{s}${a:,.2f}"


class ArbiterDeck(Base):
    name = "arbiter"
    rebuild_every = 1.0

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        s = self.h / 1440.0
        self.s = s
        self.feed = Feed(self.cfg)
        self.feed.start()
        self.L = {
            "gal_panel": (80 * s, 170 * s, 1420 * s, 960 * s),
            "gal": (790 * s, 690 * s, 560 * s),
            "lineup": (1540 * s, 170 * s, 940 * s, 300 * s),
            "tape": (1540 * s, 490 * s, 940 * s, 390 * s),
            "impact": (1540 * s, 900 * s, 940 * s, 230 * s),
            "ribbons": (80 * s, 1160 * s, 2400 * s, 200 * s),
        }
        self.yaw, self.pitch = 0.4, 0.62
        self.drag = None
        self.last_input = -10.0
        self.selected = None
        self.sel_t = 0.0
        self.hover = None
        self.ver = -1
        self.stars = []          # (id, model xyz)
        self.star_ids = []
        self.star_pts = np.zeros((0, 3), dtype=np.float32)
        self.d = {}
        self.bars = {}
        self.err = {}
        self.seen_trades = None
        self.new_fill_t = -10.0

    def close(self):
        self.feed.close()
        super().close()

    # ------------------------------------------------------------------ data
    def _model(self):
        roster = {a["id"]: a for a in (self.d.get("roster") or {}).get("agents") or []}
        road = {a["id"]: a for a in (self.d.get("road") or {}).get("agents") or []}
        stars = []
        for aid, r in road.items():
            ro = roster.get(aid, {})
            nxt = (r.get("next") or {}).get("key")
            if r.get("status") == "in_portfolio":
                rad = 0.40 - 0.035
                band = 0.018
            elif nxt in PORT_ROAD:
                i = PORT_ROAD.index(nxt)
                rad = (R_PORT[i - 1] if i else 1.08) - 0.05     # just outside the gate it faces
                band = 0.035
            elif nxt in LIVE_ROAD:
                i = LIVE_ROAD.index(nxt)
                rad = (R_LIVE[i - 1] if i else 0.40) - 0.025
                band = 0.012
            else:
                rad, band = 1.1, 0.05
            ang = _hash01(aid) * TAU
            rr = rad + (_hash01(aid, 1) - 0.5) * 2 * band
            y = (_hash01(aid, 2) - 0.5) * (0.07 if r.get("kind") == "learning" else 0.04) + \
                (0.012 if r.get("kind") == "rule" else -0.012)
            stars.append({"id": aid, "p": (math.cos(ang) * rr, y, math.sin(ang) * rr), "road": r, "ro": ro})
        return stars

    def _star_style(self, st):
        r, ro = st["road"], st["ro"]
        pnl = ro.get("pnl")
        cap = ro.get("capital") or 10000
        if r.get("status") == "in_portfolio":
            return col("white", 1.0), 3.2 + 9.0 * (r.get("weight") or 0)
        if pnl is None:
            return col("static", 0.55), 1.3
        ret = pnl / cap
        k = min(abs(ret) / 0.02, 1.0)
        if ret > 0.0005:
            c = col("phosphor", 0.45 + 0.55 * k)
        elif ret < -0.0005:
            c = col("danger", 0.45 + 0.55 * k)
        else:
            c = col("dim", 0.6)
        return c, 1.2 + 2.2 * k

    # ------------------------------------------------------------------ build
    def build(self, b, d, t):
        self.d, self.bars, self.err, ver = self.feed.snapshot()
        s = self.s
        T = 0.05
        if ver != self.ver:
            self.stars = self._model()
            self.star_ids = [x["id"] for x in self.stars]
            self.star_pts = np.array([x["p"] for x in self.stars], dtype=np.float32).reshape(-1, 3)
            self.ver = ver
            self._note_new_fills()
        now = self.d.get("now") or {}
        ag = now.get("agents") or {}
        # ---- title + the real-money chip, plainly
        b.text("ARBITER // THE FLOOR", 80 * s, 110 * s, col("soft"), font="l", track=6, reveal=T, type_rate=0.02)
        b.text("PAPER PORTFOLIO · A FORWARD TEST, NO REAL MONEY", 560 * s, 108 * s, col("dim"), font="s", track=2.5,
               reveal=T + 0.2, type_rate=0.01)
        real = ag.get("real_money")
        chip = f"REAL MONEY: OFF · NOT ARMED · {real if real is not None else '?'} AGENTS"
        cw = len(chip) * 13 * s + 40 * s
        cx0 = self.w - 80 * s - cw
        b.plate(cx0, 82 * s, cw, 38 * s, 0.95)
        b.rect(cx0, 82 * s, cw, 38 * s, col("amber", 0.95), width=1.5, reveal=T + 0.1)
        b.text(chip, cx0 + cw / 2, 108 * s, col("amber"), font="m", track=1.5, align="c", reveal=T + 0.2,
               type_rate=0.008)
        b.line((80 * s, 132 * s), (self.w - 80 * s, 132 * s), col("guard"), reveal=T)
        if not self.d:
            msg = "CONTACTING THE FLOOR…" if not self.err else "FLOOR UNREACHABLE: " + _ascii(next(iter(self.err.values())), 60)
            b.text(msg.upper(), self.w / 2, self.h / 2, col("amber"), font="m", track=3, align="c")
            return
        self._galaxy(b, t, T)
        self._core(b, T)
        self._lineup(b, T)
        self._tape(b, T)
        self._impact(b, T)
        self._ribbons(b, T)
        self._card(b, T)
        stale = [k for k in self.err]
        foot = "DRAG TO SPIN · HOVER A STAR · CLICK FOR ITS CARD · TAB: TIMELINE · ESC CLOSES"
        if stale:
            foot = "STALE: " + ", ".join(stale).upper() + " · " + foot
        b.text(foot, self.w / 2, self.h - 22 * s, col("amber" if stale else "dim", 0.85), font="xs", track=2.5,
               align="c", reveal=T + 1.2)

    def _galaxy(self, b, t, T):
        s = self.s
        x, y, w, h = self.L["gal_panel"]
        cnt = {}
        for st in self.stars:
            k = (st["road"].get("next") or {}).get("key")
            if st["road"].get("status") == "in_portfolio":
                k = "funded_in"
            cnt[k] = cnt.get(k, 0) + 1
        gadgets.frame(b, x, y, w, h, "THE ROAD TO LIVE", T + 0.05,
                      sub=f"{len(self.stars)} AGENTS · RINGS ARE THE GATES · CENTRE IS REAL MONEY")
        # rings
        def ring(r, c, dash=0.0, n=120, rv=0.0):
            pts = [(math.cos(i / n * TAU) * r, 0.0, math.sin(i / n * TAU) * r) for i in range(n + 1)]
            for i in range(n):
                b.line(pts[i], pts[i + 1], c, space=2, dash=dash, reveal=rv)
        steps = {st["key"]: st["label"] for st in (self.d.get("road") or {}).get("steps") or []}
        for i, (k, r) in enumerate(zip(PORT_ROAD, R_PORT)):
            ring(r, col("dim" if k != "funded" else "soft", 0.75 if k != "funded" else 0.95), rv=T + 0.2 + i * 0.05)
            lab = _ascii(steps.get(k, k)).upper()
            n = cnt.get(PORT_ROAD[i + 1], 0) if i + 1 < len(PORT_ROAD) else cnt.get("week", 0) + cnt.get("funded_in", 0)
            b.text(f"{lab}", -r * 0.7071, 0.0, col("dim", 0.9), font="xs", track=1.2, space=2, z=r * 0.7071,
                   dx=6, dy=-4, reveal=T + 0.6 + i * 0.05)
        for i, (k, r) in enumerate(zip(LIVE_ROAD, R_LIVE)):
            ring(r, col("amber", 0.55), dash=5.0, n=72, rv=T + 0.5 + i * 0.05)
        ring(R_REAL, col("amber", 0.95), dash=3.0, n=48, rv=T + 0.8)
        b.text("REAL MONEY · OFF", R_REAL, 0.0, col("amber"), font="xs", track=1.5, space=2, z=0.0, dx=8, dy=-6,
               reveal=T + 0.9)
        # stars
        for st in self.stars:
            c, size = self._star_style(st)
            sel = st["id"] == self.selected
            b.arc(st["p"], 0, size * s * (1.6 if sel else 1.0), 0, TAU, c, kind=2, space=2, reveal=T + 0.4)
            if st["road"].get("status") == "in_portfolio":
                b.arc(st["p"], size * s + 5, size * s + 6.5, 0, TAU, col("soft", 0.9), segs=8, gap=0.4, spin=0.8,
                      space=2, reveal=T + 0.6)
                b.text(_ascii(st["road"].get("name"), 30).upper(), *st["p"][:2], col("white"), font="s", track=1.5,
                       space=2, z=st["p"][2], dx=14, dy=-4, reveal=T + 0.9)
                b.text(f"FUNDED {st['road'].get('weight', 0) * 100:.0f}% · {money(st['ro'].get('pnl'))}",
                       *st["p"][:2], col("soft"), font="xs", track=1, space=2, z=st["p"][2], dx=14, dy=14,
                       reveal=T + 1.0)
            if sel:
                b.arc(st["p"], 10 * s, 11.5 * s, 0, TAU, col("white"), segs=4, gap=0.5, spin=1.5, space=2)
        # trade pulses: from the agent into the core, fading with age (last 6 h)
        idx = {x["id"]: x for x in self.stars}
        for tr in ((self.d.get("trades") or {}).get("trades") or [])[:40]:
            age = _ago(tr.get("at", "")) or 1e9
            if age > 6 * 3600:
                continue
            fresh = max(0.25, 1.0 - age / (6 * 3600))
            win = (tr.get("realized_usd") or 0) >= 0
            for by in tr.get("by") or []:
                src = idx.get(by.get("sleeve")) or idx.get(by.get("id"))
                p0 = src["p"] if src else (0.42 * math.cos(_hash01(by.get("sleeve")) * TAU), 0.0,
                                           0.42 * math.sin(_hash01(by.get("sleeve")) * TAU))
                b.line(p0, (0, 0, 0), col("soft", 0.18 * fresh), space=2, dash=4)
                b.arc(p0, 0, 2.6 * s, 0, TAU, col("soft" if win else "amber", fresh), kind=2, space=2,
                      end=(0.0, 0.0, 0.0), speed=0.35, phase=_hash01(tr.get("id")), reveal=T + 1.0)
        if self.hover and self.hover != self.selected and self.hover in idx:
            st = idx[self.hover]
            pn = st["ro"].get("pnl")
            b.text(f"{_ascii(st['road'].get('name'), 40).upper()} · {money(pn)} · CLICK FOR CARD", *st["p"][:2],
                   col("white"), font="xs", track=1.2, space=2, z=st["p"][2], dx=12, dy=-10)

    def _core(self, b, T):
        s = self.s
        ov = self.d.get("overview") or {}
        perf = self.d.get("perf") or {}
        ex = ov.get("exposure") or {}
        risk = ov.get("risk") or {}
        cx, cy, R = self.L["gal"]
        eq = ex.get("equity")
        cap = perf.get("capital")
        # the core itself: a small bright glyph so the live-road rings stay visible
        b.arc((0, 0, 0), 0, 9 * s, 0, TAU, col("white", 0.95), kind=2, space=2, reveal=T + 0.3)
        b.arc((0, 0, 0), 14 * s, 15.5 * s, 0, TAU, col("soft", 0.9), segs=6, gap=0.35, spin=0.4, space=2,
              reveal=T + 0.35)
        # readout panel, top right of the galaxy, with a leader to the core
        x, y, w, h = self.L["gal_panel"]
        px, py, pw, ph = x + w - 360 * s, y + 58 * s, 336 * s, 150 * s
        b.plate(px, py, pw, ph, 0.92)
        b.brackets(px, py, pw, ph, col("soft"), l=10, reveal=T + 0.3)
        b.line((px, py + ph), (cx + 18 * s, cy - 14 * s), col("soft", 0.5), dash=6, reveal=T + 0.5)
        b.text("THE PAPER CORE", px + 16 * s, py + 26 * s, col("dim"), font="xs", track=2.5, reveal=T + 0.35)
        b.text(money(eq, sign=False) if eq is not None else "--", px + 16 * s, py + 66 * s, col("white"), font="xl",
               track=0.5, reveal=T + 0.4)
        pnl = (eq - cap) if (eq is not None and cap) else None
        if pnl is not None:
            b.text(f"{money(pnl)} ON {money(cap, sign=False)} SINCE {_ascii(perf.get('since', ''), 14).upper()}",
                   px + 16 * s, py + 92 * s, col("phosphor" if pnl >= 0 else "danger"), font="xs", track=1,
                   reveal=T + 0.5)
        dd = risk.get("drawdown")
        cut = risk.get("cuts_at") or 0.05
        if dd is not None:
            b.text(f"DRAWDOWN {dd * 100:.1f}% · CUTS AT {cut * 100:.0f}%", px + 16 * s, py + 114 * s,
                   col(level(dd, cut * 0.8, cut)), font="xs", track=1, reveal=T + 0.55)
            bw = pw - 32 * s
            b.line((px + 16 * s, py + 130 * s), (px + 16 * s + bw, py + 130 * s), col("guard"), width=4)
            b.line((px + 16 * s, py + 130 * s), (px + 16 * s + bw * min(dd / cut, 1.0), py + 130 * s),
                   col(level(dd, cut * 0.8, cut)), width=4, reveal=T + 0.7)
        if ex.get("cash_pct") is not None:
            b.text(f"CASH {ex['cash_pct'] * 100:.0f}% · LONG {money(ex.get('long_usd'), sign=False)}",
                   px + pw - 16 * s, py + 26 * s, col("soft", 0.9), font="xs", track=1, align="r", reveal=T + 0.45)
        wc = (ex.get("why_cash") or {}).get("line")
        if wc:
            for i, ln in enumerate(_wrap(_ascii(wc).upper(), 70)[:2]):
                b.text(ln, x + 24 * s, y + 64 * s + i * 20 * s, col("soft", 0.85), font="xs", track=1,
                       reveal=T + 0.9, type_rate=0.004)

    def _lineup(self, b, T):
        s = self.s
        x, y, w, h = self.L["lineup"]
        c = (self.d.get("now") or {}).get("cohort") or {}
        gadgets.frame(b, x, y, w, h, "THE REFEREE'S LINEUP", T + 0.15,
                      sub=f"DAY {c.get('days', '?')} OF {c.get('min_days', '?')} · {_ascii(c.get('state', '')).upper()}")
        rows = list(c.get("agents") or [])
        for ref in ("equal", "growth"):
            if c.get(ref):
                rows.append(dict(c[ref], rank="REF"))
        b.text("RANK  ALLOCATOR                              P&L       INVESTED   LOG-GROWTH (90% CI)", x + 20 * s,
               y + 64 * s, col("dim"), font="xs", track=1, reveal=T + 0.3)
        for i, a in enumerate(rows[:9]):
            yy = y + 88 * s + i * 23 * s
            pn = a.get("pnl")
            ci = a.get("log_growth_ci") or [None, None]
            cis = f"{a.get('log_growth', 0):+.2f} [{ci[0]:+.2f}, {ci[1]:+.2f}]" if ci[0] is not None else "--"
            line = f"{str(a.get('rank', '')):<5} {_ascii(a.get('name'), 36):<38} {money(pn):>9}   {a.get('invested', 0) * 100:>5.0f}%    {cis}"
            b.text(line.upper(), x + 20 * s, yy, col("soft" if (pn or 0) >= 0 else "danger", 0.95), font="xs",
                   track=0.6, reveal=T + 0.35 + i * 0.04, type_rate=0.002)

    def _tape(self, b, T):
        s = self.s
        x, y, w, h = self.L["tape"]
        trades = (self.d.get("trades") or {}).get("trades") or []
        total = (self.d.get("trades") or {}).get("total")
        gadgets.frame(b, x, y, w, h, "THE TAPE · FILLS AND THEIR CAUSES", T + 0.25,
                      sub=f"{total} PAPER FILLS" if total is not None else "")
        for i, tr in enumerate(trades[:8]):
            yy = y + 66 * s + i * 40 * s
            age = _ago(tr.get("at", ""))
            ago = (f"{age / 60:.0f}M" if age < 3600 else f"{age / 3600:.0f}H" if age < 86400 else f"{age / 86400:.0f}D") if age else "?"
            r = tr.get("realized_usd")
            act = f"{tr.get('action', '').upper()} {tr.get('effect', '').upper()}"
            head = f"{ago:>4} AGO  {act:<11} {_ascii(tr.get('instrument'), 30):<30} {money(tr.get('notional_usd'), sign=False):>8}"
            fresh = age is not None and age < 900
            b.text(head.upper(), x + 20 * s, yy, col("white" if fresh else "soft"), font="xs", track=0.6,
                   reveal=T + 0.4 + i * 0.05, type_rate=0.002)
            if r is not None:
                b.text(f"REALIZED {money(r)}", x + w - 20 * s, yy, col("phosphor" if r >= 0 else "danger"), font="xs",
                       track=0.6, align="r", reveal=T + 0.45 + i * 0.05)
            cause = (tr.get("causes") or [{}])[0]
            who = ", ".join(_ascii(bb.get("name"), 26) for bb in (tr.get("by") or [])[:2])
            why = _ascii(cause.get("summary") or tr.get("reason") or "", 70)
            b.text(f"   {who} · {why}".upper()[:96], x + 20 * s, yy + 17 * s, col("dim", 0.95), font="xs", track=0.4,
                   reveal=T + 0.5 + i * 0.05, type_rate=0.002)

    def _impact(self, b, T):
        s = self.s
        x, y, w, h = self.L["impact"]
        f = self.d.get("impact") or {}
        items = f.get("items") or []
        gadgets.frame(b, x, y, w, h, "EVENT IMPACT · LAST 72 H", T + 0.35, sub=f"{len(items)} OPEN READS")
        for i, it in enumerate(items[:6]):
            yy = y + 66 * s + i * 26 * s
            title = _ascii(it.get("title"), 40) or "(non-latin title)"
            med = it.get("median_24h")
            pu = it.get("p_up_24h")
            line = f"{_ascii(it.get('coin'), 8).upper():<8} {_ascii(it.get('type'), 26).upper():<26} {title.upper():<40}"
            b.text(line, x + 20 * s, yy, col("soft"), font="xs", track=0.5, reveal=T + 0.5 + i * 0.05, type_rate=0.002)
            if med is not None:
                b.text(f"24H MEDIAN {med * 100:+.1f}% · P(UP) {pu * 100:.0f}%", x + w - 20 * s, yy,
                       col("phosphor" if med >= 0 else "danger"), font="xs", track=0.5, align="r",
                       reveal=T + 0.55 + i * 0.05)

    def _ribbons(self, b, T):
        s = self.s
        x, y, w, h = self.L["ribbons"]
        pos = sorted((self.d.get("positions") or {}).get("positions") or [], key=lambda p: -abs(p.get("notional_usd") or 0))[:5]
        gadgets.frame(b, x, y, w, h, "PRICE RIBBONS · LARGEST PAPER HOLDINGS", T + 0.45,
                      sub="7 DAYS (CRYPTO) · 30 SESSIONS (FUNDS)")
        if not pos:
            b.text("NO OPEN POSITIONS", x + w / 2, y + h / 2 + 10 * s, col("dim"), font="s", track=3, align="c")
            return
        cw = (w - 40 * s) / len(pos)
        for i, p in enumerate(pos):
            cx0 = x + 20 * s + i * cw
            bx0, by0, bw, bh = cx0 + 10 * s, y + 72 * s, cw - 30 * s, h - 96 * s
            series = self.bars.get(p.get("instrument_id")) or []
            u = p.get("unrealized_usd") or 0
            b.text(_ascii(p.get("instrument"), 22).upper(), bx0, y + 62 * s, col("soft"), font="s", track=1.5,
                   reveal=T + 0.6 + i * 0.05)
            b.text(f"{p.get('side', '').upper()} {money(p.get('notional_usd'), sign=False)} · {money(u)}",
                   bx0 + bw, y + 62 * s, col("phosphor" if u >= 0 else "danger"), font="xs", track=1, align="r",
                   reveal=T + 0.65 + i * 0.05)
            if len(series) < 2:
                b.text("NO BARS", bx0 + bw / 2, by0 + bh / 2, col("dim"), font="xs", track=2, align="c")
                continue
            v = np.array([c for _, c in series], dtype=np.float64)
            lo, hi = v.min(), v.max()
            rngv = (hi - lo) or 1.0
            n = len(v)
            pts = [(bx0 + bw * k / (n - 1), by0 + bh - bh * (v[k] - lo) / rngv) for k in range(n)]
            up = v[-1] >= v[0]
            cc = col("phosphor" if up else "danger", 0.95)
            for k in range(n - 1):
                rv = T + 0.7 + i * 0.05 + k * 0.004
                b.line(pts[k], pts[k + 1], cc, width=1.4, reveal=rv)
                b.line(pts[k], (pts[k][0], by0 + bh), col("phosphor" if up else "danger", 0.07), width=bw / n + 0.5,
                       reveal=rv)
            b.arc(pts[-1], 0, 3.2 * s, 0, TAU, col("white"), kind=2, reveal=T + 1.1)
            chg = (v[-1] / v[0] - 1) * 100 if v[0] else 0.0
            ly = pts[-1][1] - 10 * s if pts[-1][1] > by0 + 24 * s else pts[-1][1] + 20 * s
            b.plate(pts[-1][0] - 120 * s, ly - 14 * s, 112 * s, 18 * s, 0.7)
            b.text(f"{v[-1]:,.4g} · {chg:+.1f}%", pts[-1][0] - 10 * s, ly, col("white"), font="xs",
                   track=0.5, align="r", reveal=T + 1.15)

    def _card(self, b, T):
        if not self.selected:
            return
        st = next((x for x in self.stars if x["id"] == self.selected), None)
        if not st:
            return
        s = self.s
        r, ro = st["road"], st["ro"]
        x, y, w, h = self.L["gal_panel"]
        px, py, pw, ph = x + w - 624 * s, y + h - 290 * s, 600 * s, 270 * s
        rv = self.sel_t
        b.plate(px, py, pw, ph, 0.95)
        b.brackets(px, py, pw, ph, col("soft"), l=12, reveal=rv)
        b.text(_ascii(r.get("name"), 46).upper(), px + 16 * s, py + 28 * s, col("white"), font="m", track=1.2,
               reveal=rv, type_rate=0.008)
        meta = f"{_ascii(r.get('kind')).upper()} · {_ascii(r.get('class')).upper()} · {_ascii(r.get('status')).upper().replace('_', ' ')}"
        b.text(meta, px + 16 * s, py + 50 * s, col("dim"), font="xs", track=1.5, reveal=rv + 0.05)
        pn, ci = ro.get("pnl"), ro.get("pnl_ci") or [None, None]
        rec = f"RECORD  {money(pn)} ON {money(ro.get('capital'), sign=False)}"
        if ci[0] is not None:
            rec += f"   90% INTERVAL {money(ci[0])} TO {money(ci[1])}"
        b.text(rec, px + 16 * s, py + 80 * s, col("phosphor" if (pn or 0) >= 0 else "danger"), font="s", track=0.8,
               reveal=rv + 0.1, type_rate=0.004)
        b.text(f"ROAD    {r.get('passed', 0)} OF {r.get('of', 0)} GATES · WEIGHT {r.get('weight', 0) * 100:.0f}%",
               px + 16 * s, py + 104 * s, col("soft"), font="s", track=0.8, reveal=rv + 0.15)
        nxt = r.get("next") or {}
        lines = _wrap(_ascii(f"NEXT: {nxt.get('label', '')} — {nxt.get('line', '')}").upper(), 70)[:3]
        lines += _wrap(_ascii(ro.get("doing", "")).upper(), 70)[:1]
        # cause summary: this agent's latest fills on the tape
        mine = [tr for tr in ((self.d.get("trades") or {}).get("trades") or [])
                if any(bb.get("sleeve") == r.get("id") or bb.get("id") == r.get("id") for bb in tr.get("by") or [])]
        if mine:
            c0 = (mine[0].get("causes") or [{}])[0]
            lines += _wrap(_ascii(f"LAST FILL: {mine[0].get('action', '')} {mine[0].get('instrument', '')} · "
                                  f"{c0.get('summary') or mine[0].get('reason', '')}").upper(), 70)[:2]
        for i, ln in enumerate(lines[:6]):
            b.text(ln, px + 16 * s, py + 132 * s + i * 21 * s, col("dim" if i else "amber", 1.0), font="xs", track=0.6,
                   reveal=rv + 0.2 + i * 0.03, type_rate=0.002)
        # its equity sparkline
        sp = ro.get("sparkline") or []
        if len(sp) > 2:
            v = np.array([q[1] for q in sp], dtype=np.float64)
            lo, hi = v.min(), v.max()
            rg = (hi - lo) or 1.0
            sx0, sy0, sw, sh = px + pw - 196 * s, py + 14 * s, 180 * s, 46 * s
            pts = [(sx0 + sw * k / (len(v) - 1), sy0 + sh - sh * (v[k] - lo) / rg) for k in range(len(v))]
            for k in range(len(v) - 1):
                b.line(pts[k], pts[k + 1], col("soft", 0.9), reveal=rv + 0.2)

    def _note_new_fills(self):
        trades = (self.d.get("trades") or {}).get("trades") or []
        ids = {t.get("id") for t in trades}
        if self.seen_trades is not None and ids - self.seen_trades:
            self.new_fill_t = self.now()
        self.seen_trades = ids

    # ------------------------------------------------------------------ frame
    def frame(self, t, d):
        p = self.stage.painter
        if self.drag is None and t - self.last_input > 4.0:
            self.yaw += 0.0025
        gx, gy, gR = self.L["gal"]
        p.rot[2] = glkit.rot_matrix(self.yaw, self.pitch)
        p.ctr[2] = (gx, gy, gR, 3.4)
        fade = min(t / 0.25, 1.0)
        if self.closing_at is not None:
            fade = max(0.0, 1.0 - (t - self.closing_at) / 0.25)
        u = {"backdrop": 0.84, "glow": 0.95, "fade": fade}
        if t - self.new_fill_t < 1.2:      # a new paper fill: the core flares
            u["edge"] = (0.35 * (1.0 - (t - self.new_fill_t) / 1.2), 0.0, 0.0, 0.0)
        if self.closing_at is not None and t - self.closing_at > 0.26:
            u["finished"] = True
        return u

    # ------------------------------------------------------------------ input
    def _pick(self, x, y):
        if not len(self.star_pts):
            return None
        p = self.stage.painter
        pr = glkit.project(self.star_pts, p.rot[2], p.ctr[2])
        dd = np.hypot(pr[:, 0] - x, pr[:, 1] - y)
        i = int(np.argmin(dd))
        return self.star_ids[i] if dd[i] < 9 * self.s + 3 else None

    def _in_gal(self, x, y):
        x0, y0, w, h = self.L["gal_panel"]
        return x0 <= x <= x0 + w and y0 <= y <= y0 + h

    def click(self, x, y, button):
        self.last_input = self.now()
        if self._in_gal(x, y):
            self.drag = (x, y, self.yaw, self.pitch, False)
            return True
        inside = any(px <= x <= px + w and py <= y <= py + h for (px, py, w, h) in
                     (self.L["lineup"], self.L["tape"], self.L["impact"], self.L["ribbons"]))
        if not inside:
            self.close()
        return True

    def motion(self, x, y, buttons):
        self.last_input = self.now()
        if self.drag:
            x0, y0, yaw, pitch, moved = self.drag
            moved = moved or abs(x - x0) + abs(y - y0) > 4
            self.yaw = yaw + (x - x0) * 0.008
            self.pitch = max(0.12, min(1.45, pitch + (y - y0) * 0.006))
            self.drag = (x0, y0, yaw, pitch, moved)
            return
        h = self._pick(x, y) if self._in_gal(x, y) else None
        if h != self.hover:
            self.hover = h
            self.built_at = None

    def release(self, x, y):
        if self.drag and not self.drag[4]:
            n = self._pick(x, y)
            self.selected = None if n == self.selected else n
            self.sel_t = self.now() + 0.01
            self.built_at = None
        self.drag = None

    def key(self, name):
        if name in ("Escape", "q"):
            self.close()
        elif name == "Tab" and self.app:
            self.close()
            from gi.repository import GLib
            from .deckkit import next_deck
            GLib.timeout_add(300, lambda: (self.app.overlay(next_deck(self.name)), False)[1])
        elif name in ("Left", "h"):
            self.yaw -= 0.2
        elif name in ("Right", "l"):
            self.yaw += 0.2
        self.last_input = self.now()
        return True
