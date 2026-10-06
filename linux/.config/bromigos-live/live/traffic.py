"""The sky's traffic (space.glsl traffic()), decided on the CPU so ships never pop.

Seven lanes cross the deep-space region. Each lane has a fixed speed and phase; a
"crossing" runs from fully off one edge to fully off the other. Whether a lane carries a
ship is decided once, when its crossing starts, from the traffic level at that moment
(this machine's network throughput), and held for the whole crossing. So a ship always
enters and leaves off-screen; the level still sets how many lanes are busy, with a lag of
at most one crossing.

The debris density follows a slow average of the level (about 25 s), and the shader fades
flecks in and out around that threshold, so nothing blinks either.

Positions are computed here in double precision (time.monotonic()), which also keeps the
motion smooth after days of uptime. Per frame: `uniforms(level, rect_w)` returns the
u_lane array (7 x vec4: x px along the lane, occupied 0/1, -, -) and the smoothed level.
"""
import hashlib
import math
import time

import numpy as np

LANES = 7
PAD = 100.0           # px beyond each edge: a hull is 44 px long, its trail ~60 px more
EMA_SECONDS = 25.0


def _unit(*key):
    """A stable pseudo-random number in [0, 1) for a key (same on every run)."""
    h = hashlib.blake2b(repr(key).encode(), digest_size=8).digest()
    return int.from_bytes(h, "little") / 2.0 ** 64


class Traffic:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.speed = [14.0 + 30.0 * _unit("speed", k) for k in range(LANES)]     # px/s: slow haulers
        self.phase = [_unit("phase", k) for k in range(LANES)]
        self.cycle = [None] * LANES
        self.busy = [0.0] * LANES
        self.smooth = None
        self.t_last = None

    def busy_threshold(self, level):
        return 0.12 + 0.88 * level

    def uniforms(self, level, rect_w):
        """level: 0..1 (or < 0 = traffic off). Returns (u_lane (7,4) float32, smoothed level)."""
        now = self.clock()
        dt = 0.0 if self.t_last is None else max(0.0, min(now - self.t_last, 5.0))
        self.t_last = now
        lane = np.zeros((LANES, 4), np.float32)
        if level < 0:
            self.smooth = None
            return lane, -1.0
        self.smooth = level if self.smooth is None else self.smooth + (level - self.smooth) * (1 - math.exp(-dt / EMA_SECONDS))
        span = rect_w + 2 * PAD
        for k in range(LANES):
            pos = now * self.speed[k] + self.phase[k] * span
            cyc = int(pos // span)
            if cyc != self.cycle[k]:              # a new crossing starts (off-screen): decide it now
                self.cycle[k] = cyc
                self.busy[k] = 1.0 if _unit("busy", k, cyc) < self.busy_threshold(level) else 0.0
            lane[k] = (pos - cyc * span - PAD, self.busy[k], 0.0, 0.0)
        return lane, float(self.smooth)
