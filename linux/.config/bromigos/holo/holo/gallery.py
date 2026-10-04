"""The model gallery: one model at a time on the projection table, suit-diagnostic
callouts, flip between models. Pure scene logic; the window lives in app.py."""
import math
import time

import numpy as np

from . import bind, fmt
from .render import Holo, col
from .stage import Stage

HINTS = "DRAG rotate   SCROLL explode   CLICK isolate a part   ←/→ model   SPACE explode   S scan   R reset   ESC close"
SOURCE_NAME = {"local": "THIS MACHINE", "lab": "ECHOCRAFT LAB", "arbiter": "ARBITER (read only)"}


class Gallery:
    def __init__(self, live, scale=1.0):
        self.live = live
        self.scale = scale
        self.names = fmt.available()
        self.idx = 0
        self.stages = {}
        self.holo = None
        self.mouse = (0, 0)
        self.drag = None
        self.last_t = time.monotonic()
        self.hover_hint = ""
        self.size = (1, 1)
        self.dirty_pick = False

    @property
    def stage(self):
        n = self.names[self.idx]
        if n not in self.stages:
            self.stages[n] = Stage(n, self.live)
        return self.stages[n]

    def show(self, name=None, step=0):
        if name in self.names:
            self.idx = self.names.index(name)
        else:
            self.idx = (self.idx + step) % len(self.names)
        s = self.stage
        s.born = time.monotonic()
        s.scan()
        s.iso = None

    def busy(self):
        """True while something is moving enough to want the higher frame rate."""
        s = self.stage
        return (self.drag is not None or abs(s.explode - s.explode_to) > 0.01 or
                time.monotonic() - s.born < 2.0 or time.monotonic() - s.scan_t0 < s.scan_dur + 0.3)

    # ------------------------------------------------------------------ render
    def render(self, fbo, w, h):
        if self.holo is None:
            self.holo = Holo(self.scale)
        self.size = (w, h)
        t = time.monotonic()
        dt = min(0.1, t - self.last_t)
        self.last_t = t
        s = self.stage
        s.update(dt)
        H = self.holo
        H.begin(w, h, t)
        sc = self.scale
        top, bot = 96 * sc, 74 * sc
        vh = h - top - bot
        d = 3.5
        tgt = np.array([0, 0.5, 0], np.float32)
        eye = tgt + d * np.array([0, math.sin(s.pitch), math.cos(s.pitch)], np.float32)
        H.camera(eye, tgt, 30.0, viewport=(0, top, w, vh))
        s.draw(H, t, size=0.95)
        if self.dirty_pick and s.anchor_px is not None:
            s.hover = s.pick(H, *self.mouse) if self.drag is None else s.hover
            self.dirty_pick = False
        s.draw_callouts(H, (24 * sc, top, w - 48 * sc, vh), size=int(14 * sc), edges=True)
        self._hud(H, w, h, s, t)
        H.end(fbo, bg=(0.0, 0.02, 0.0, 0.9), bloom=1.15)

    def _hud(self, H, w, h, s, t):
        sc = self.scale
        ph = col("phosphor")
        H.brackets(10 * sc, 10 * sc, w - 20 * sc, h - 20 * sc, (ph[0], ph[1], ph[2], 0.7), arm=22 * sc, width=1.5)
        # title block: what is on the table and where its readings come from
        x, y = 36 * sc, 26 * sc
        tw, th = H.label(s.meta["title"], x, y, ph, int(30 * sc), "bold", spacing=6)
        H.label(s.meta.get("subtitle", "").upper(), x + tw + 18 * sc, y + th - 22 * sc, col("soft", 1, 0.8), int(14 * sc), spacing=3)
        srcs = bind.SOURCES.get(s.name, ())
        info = []
        for src in srcs:
            d, err, at = self.live.get(src)
            if err and d is None:
                info.append(f"{SOURCE_NAME[src]}  unreachable")
            elif at:
                info.append(f"{SOURCE_NAME[src]}  read {max(0, time.time() - at):.0f} s ago")
            else:
                info.append(f"{SOURCE_NAME[src]}  reading…")
        if s.name == "emblem":
            info.append("extruded from the canon vectors")
        H.label("   ".join(info), w - 36 * sc, y + 8 * sc, col("static", 1, 0.95), int(13 * sc), anchor="rt")
        st = "EXPLODED" if s.explode_to > 0.5 else "ASSEMBLED"
        if s.iso is not None:
            st = "ISOLATED: " + s.parts[s.iso]["label"]
        H.label(st, w - 36 * sc, y + 30 * sc, col("amber" if s.iso is not None else "dim", 1.3, 1), int(13 * sc), "bold", anchor="rt", spacing=2)
        # model strip: every model, the current one lit; click a name to switch
        fy = h - 52 * sc
        xs = 36 * sc
        self.strip = []
        for i, n in enumerate(self.names):
            m = fmt.load(n)
            lab = m.meta["title"]
            c = col("phosphor") if i == self.idx else col("dim", 1.2, 0.9)
            lw, lh = H.label(lab, xs, fy, c, int(13 * sc), "bold" if i == self.idx else "normal", spacing=2)
            if i == self.idx:
                H.line2d(xs, fy + lh + 3, xs + lw, fy + lh + 3, ph, 1.6)
            self.strip.append((n, xs, fy, lw, lh))
            xs += lw + 30 * sc
        hint = self.hover_hint or HINTS
        H.label(hint, w - 36 * sc, fy, col("static", 1, 0.9), int(12 * sc), anchor="rt")

    # ------------------------------------------------------------------ input
    def on_motion(self, x, y):
        if self.drag is not None:
            dx, dy = x - self.drag[0], y - self.drag[1]
            s = self.stage
            s.yaw += dx * 0.008
            s.pitch = min(0.9, max(-0.25, s.pitch + dy * 0.004))
            self.drag = (x, y)
        self.mouse = (x, y)
        self.dirty_pick = True
        s = self.stage
        self.hover_hint = s.parts[s.hover]["hint"] if s.hover is not None else ""

    def on_press(self, x, y, button):
        self.drag = (x, y)
        self.press_at = (x, y, time.monotonic())
        self.stage.dragging = True

    def on_release(self, x, y, button):
        s = self.stage
        s.dragging = False
        px, py, pt = getattr(self, "press_at", (x, y, 0))
        self.drag = None
        if abs(x - px) + abs(y - py) < 6 and time.monotonic() - pt < 0.6:
            for n, sx, sy, lw, lh in getattr(self, "strip", []):
                if sx <= x <= sx + lw and sy <= y <= sy + lh:
                    self.show(n)
                    return
            i = s.pick(self.holo, x, y) if self.holo else None
            s.isolate(i)
            if i is not None and s.explode_to < 0.5:
                s.scan()

    def on_scroll(self, dy):
        self.stage.toggle_explode(-0.25 * dy)

    def on_key(self, name):
        s = self.stage
        if name in ("Right", "l", "Tab"):
            self.show(step=1)
        elif name in ("Left", "h", "ISO_Left_Tab"):
            self.show(step=-1)
        elif name in ("space", "e"):
            s.toggle_explode()
        elif name == "s":
            s.scan()
        elif name == "r":
            s.yaw, s.pitch, s.iso, s.explode_to = -0.55, 0.16, None, 0.0
        elif name in [str(i + 1) for i in range(len(self.names))]:
            self.show(self.names[int(name) - 1])
        elif name in ("Up", "Down"):
            s.toggle_explode(0.25 if name == "Up" else -0.25)
        else:
            return False
        return True
