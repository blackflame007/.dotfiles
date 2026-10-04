"""The live background: the theme's wallpaper as the base plate, with the den's
own screens made live (scope = network, monitor = the burn-in, meters = CPU and
GPU, main CRT = the homelab relay map), Drift-script rain in the deep-space
window, floor-grid throughput pulses, and the X-ray scanner pass."""
import math
import os
import time

import numpy as np
from OpenGL import GL

from . import gadgets, glkit, schematic
from .emblem import Emblem
from .stage import Stage

TAU = 2 * math.pi

DEN = {   # screen rects in the 2560x1440 den wallpaper (fitted by hand)
    "wave": (1475, 762, 124, 110),
    "emblem": (1090, 920, 158, 143),
    "big": (1188, 678, 200, 175),
    "meter0": (1545, 932, 66, 32),
    "meter1": (1555, 1050, 61, 32),
    "schem": (1000, 560, 860, 660),
}


def load_image(path, w, h):
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, w, h, False)
    if pb.get_has_alpha():
        pb = pb.composite_color_simple(w, h, GdkPixbuf.InterpType.BILINEAR, 255, 1, 0, 0)
    stride = pb.get_rowstride()
    raw = np.frombuffer(pb.get_pixels(), dtype=np.uint8).reshape(h, stride)[:, :w * 3]
    return np.ascontiguousarray(raw).reshape(h, w, 3), pb


class Background:
    def __init__(self, cfg, data, w, h):
        self.cfg = cfg
        self.data = data
        self.st = data.static
        self.w, self.h = w, h
        self.stage = Stage(w, h, "bg.frag")
        self.emblem = Emblem(512, 128)
        self.under = None
        self.under_sig = None
        self.fitted = False
        self.face = (0.62, 0.8, 0.55)
        self.checked_at = 0.0
        self._load_under()
        self.schem_tex = None
        self.schem_next = time.monotonic() + 6.0
        self.sweep_t0 = None
        self.bursts = [(0.0, 0.0, 0.0, 0.0)] * 6
        self.burst_i = 0
        self.wipe_t0 = -10.0
        self.static_burst = 0.0
        self.meter_v = [0.0, 0.0]
        self.wave = np.zeros(48, dtype=np.float32)
        self.last_build = 0.0
        self.t0 = time.monotonic()

    def _sig(self):
        path = os.path.expanduser(self.cfg["background"].get("underlay", "") or "")
        try:
            st = os.stat(path)
            return (path, st.st_mtime_ns, st.st_size)
        except OSError:
            return None

    def _load_under(self):
        """(Re)load the wallpaper by path. The den overlays (screens, meters, floor
        lanes) are fitted to one specific image: they only switch on when the file's
        sha1 matches background.den_fit_sha1, so a regenerated wallpaper never gets
        misplaced overlays (re-fit DEN rects and update the sha1 to re-enable)."""
        import hashlib
        bg = self.cfg["background"]
        sig = self._sig()
        self.under_sig = sig
        if self.under is not None:
            GL.glDeleteTextures([self.under])
            self.under = None
        self.fitted = False
        if sig:
            path = sig[0]
            with open(path, "rb") as fh:
                self.fitted = hashlib.sha1(fh.read()).hexdigest() == bg.get("den_fit_sha1", "")
            raw, pb = load_image(path, self.w, self.h)
            self.under = glkit.texture_rgba(raw, self.w, self.h, GL.GL_RGB)
            if not self.fitted:
                print("bromigos-live: wallpaper differs from the fitted den; den overlays off", flush=True)
            # the meter faces' own colour, so the live faces match the art
            m = DEN["meter0"]
            sx, sy = self.w / 2560.0, self.h / 1440.0
            x0, y0 = int(m[0] * sx), int(m[1] * sy)
            patch = raw[y0 + 4:y0 + int(m[3] * sy) - 4, x0 + 4:x0 + int(m[2] * sx) - 4]
            if patch.size:
                rgb = patch.reshape(-1, 3).astype(np.float32) / 255.0
                lum = rgb @ np.array([0.3, 0.59, 0.11], dtype=np.float32)
                top = rgb[lum >= np.percentile(lum, 70)]
                self.face = tuple(float(x) for x in top.mean(axis=0))

    # ------------------------------------------------------------------ events
    def burst(self, kind=0, x=None, strength=1.0):
        if not self.cfg["rain"].get("bursts", True):
            return
        r = self.cfg["rain"]["region"]
        if x is None:
            x = r[0] + r[2] * (0.25 + 0.5 * ((time.monotonic() * 7.31) % 1.0))
        self.bursts[self.burst_i % 6] = (float(x), self.now(), float(strength), float(kind))
        self.burst_i += 1

    def wipe(self):
        self.wipe_t0 = self.now()

    def now(self):
        return time.monotonic() - self.t0

    # ------------------------------------------------------------------ build
    def rebuild(self, d):
        b = glkit.Batch(self.stage.atlas)
        if self.den_on():
            x, y, w, h = self._px(DEN["big"])
            gadgets.constellation(b, d, x + w / 2, y + h / 2, min(w, h) * 0.36, space=1, labels=False, mini=True)
        self.stage.painter.upload(b)

    def den_on(self):
        return bool(self.cfg["background"].get("den", True)) and self.under is not None and self.fitted

    def _px(self, r):
        sx, sy = self.w / 2560.0, self.h / 1440.0
        return (r[0] * sx, r[1] * sy, r[2] * sx, r[3] * sy)

    # ------------------------------------------------------------------ frame
    def render(self, fbo, fps):
        t = self.now()
        d = self.data.snapshot()
        mono = time.monotonic()
        if mono - self.checked_at > 5.0:            # wallpaper replaced in place?
            self.checked_at = mono
            if self._sig() != self.under_sig:
                self._load_under()
                self.last_build = 0.0
        if mono - self.last_build > 2.0:
            self.rebuild(d)
            self.last_build = mono
        cfg = self.cfg
        # smoothed meters + scope envelope
        a = min(1.0, 4.0 / max(fps, 1))
        for i, k in enumerate(("cpu", "gpu")):
            self.meter_v[i] += ((d.get(k) or 0.0) / 100.0 - self.meter_v[i]) * a
        hist = np.array(d.get("rx_hist") or [0] * 48, dtype=np.float32) + np.array(d.get("tx_hist") or [0] * 48, dtype=np.float32)
        self.wave = np.clip(np.log10(1.0 + hist) / 7.0, 0.0, 1.0).astype(np.float32)
        # rain follows CPU load
        cpu = (d.get("cpu") or 0.0) / 100.0
        rc = cfg["rain"]
        density = 0.22 + 0.55 * min(cpu * 1.6, 1.0)
        speed = 0.55 + 1.6 * cpu
        # network pulses
        rx, tx = d.get("rx") or 0.0, d.get("tx") or 0.0
        lv = lambda v: max(0.0, min(1.0, math.log10(1 + v) / 7.5))  # noqa: E731
        # sweep scheduling
        sw = cfg["sweep"]
        sweep_x, sweep_on = 0.0, 0.0
        if sw.get("enabled", True):
            if self.sweep_t0 is None or t - self.sweep_t0 > float(sw.get("period", 24)):
                self.sweep_t0 = t
                self._draw_schematic(d)
            st = t - self.sweep_t0
            dur = float(sw.get("duration", 5.5))
            if st < dur + 2.0:
                sweep_on = 1.0
                sweep_x = -200 + (self.w + 400) * (st / dur)
        # the space constellation on the big CRT
        p = self.stage.painter
        bx, by, bw, bh = self._px(DEN["big"])
        p.rot[1] = glkit.rot_matrix(t * 0.25, 0.35)
        p.ctr[1] = (bx + bw / 2, by + bh / 2, min(bw, bh) * 0.36, 3.0)
        # ---- passes
        self.stage.begin_emit()
        p.draw((float(self.w), float(self.h)), t)
        bloom = self.stage.bloom(1.0)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, fbo)
        GL.glViewport(0, 0, self.w, self.h)
        GL.glDisable(GL.GL_BLEND)
        f = self.stage.final
        f.use()
        units = [("u_under", self.under or self.stage.emit.tex), ("u_emit", self.stage.emit.tex),
                 ("u_bloom", bloom), ("u_schem", self.schem_tex or self.stage.emit.tex),
                 ("u_ring", self.emblem.ring), ("u_flame", self.emblem.flame or self.emblem.ring)]
        for i, (name, tex) in enumerate(units):
            GL.glActiveTexture(GL.GL_TEXTURE0 + i)
            GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
            f.i(name, i)
        GL.glActiveTexture(GL.GL_TEXTURE0)
        sx, sy = self.w / 2560.0, self.h / 1440.0
        f.f("u_res", float(self.w), float(self.h))
        f.f("u_time", t)
        f.f("u_has_under", 1.0 if self.under else 0.0)
        f.f("u_under_bright", float(cfg["background"].get("underlay_brightness", 1.0)))
        f.f("u_glow", float(cfg["background"].get("glow", 0.85)))
        r = rc["region"]
        f.f("u_rain_rect", r[0] * sx, r[1] * sy, r[2] * sx, r[3] * sy)
        f.f("u_rain", density, speed, float(rc.get("brightness", 0.55)), 1.0 if rc.get("enabled", True) else 0.0)
        f.fv("u_burst", np.array(self.bursts, dtype=np.float32), 4)
        fl = cfg["floor"]
        f.f("u_floor", fl["horizon_y"] * sy, fl["vanish_x"] * sx, float(fl.get("lane_slope", 0.98)),
            float(fl.get("lane_offset", 0.71)))
        f.f("u_floor2", fl.get("max_x", 1000) * sx, 1.0 if fl.get("draw_grid") or not self.under else 0.0,
            1.0 if (fl.get("enabled", True) and (self.fitted or not self.under)) else 0.0, 0.0)
        f.f("u_net", lv(rx), lv(tx), 0.10 + 0.35 * lv(rx), 0.10 + 0.35 * lv(tx))
        f.f("u_sweep", sweep_x, sweep_on, 1.0, 1.0 if self.schem_tex else 0.0)
        f.f("u_schem_rect", *self._px(DEN["schem"]))
        wp = (t - self.wipe_t0) / 0.45
        f.f("u_wipe", wp if (0 <= wp <= 1 and cfg["events"].get("workspace_wipe", True)) else -1.0)
        f.f("u_dark", 0.0)
        # den screens
        burst = 1.0 if (t % 17.0) < 0.18 else 0.0
        f.f("u_den", 1.0 if self.den_on() else 0.0, -t * TAU / 24.0, burst, 0.0)
        f.f("u_wave_rect", *self._px(DEN["wave"]))
        f.fv("u_wave", self.wave, 1)
        f.f("u_emb_rect", *self._px(DEN["emblem"]))
        f.f("u_big_rect", *self._px(DEN["big"]))
        f.f("u_meter0", *self._px(DEN["meter0"]))
        f.f("u_meter1", *self._px(DEN["meter1"]))
        f.f("u_meter_v", *self.meter_v)
        f.f("u_meter_face", *self.face)
        self.stage.fs.draw()

    def _draw_schematic(self, d):
        surf = schematic.draw(d, self.st)
        if self.schem_tex is None:
            self.schem_tex = glkit.texture_from_cairo(surf)
        else:
            glkit.update_texture_from_cairo(self.schem_tex, surf)
