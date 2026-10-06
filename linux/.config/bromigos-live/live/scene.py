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
        self.variant = None
        self.segs = []
        self.steam_on = False
        self.face = (0.62, 0.8, 0.55)
        self.checked_at = 0.0
        self._load_under()
        self.schem_tex = None
        self.schem_next = time.monotonic() + 6.0
        self.sweep_t0 = None
        self.scan_req = False
        self.scan_pin = False
        self.scan_held = False
        self.pin_amt = 0.0
        self.hold_amt = 0.0
        self.schem_at = 0.0
        self.beam_speed = 600.0
        self.bursts = [(0.0, 0.0, 0.0, 0.0)] * 6
        self.burst_i = 0
        self.wipe_t0 = -10.0
        self.static_burst = 0.0
        self.meter_v = [0.0, 0.0]
        self.wave = np.zeros(48, dtype=np.float32)
        self.last_build = 0.0
        self.t0 = time.monotonic()
        from .plugins import Layers
        self.layers = Layers()          # opt-in shader layers (layers/*.frag), GPU-budgeted

    def _path(self):
        bg = self.cfg["background"]
        for key in ("underlay", "underlay_fallback"):
            p = os.path.expanduser(bg.get(key, "") or "")
            if p and os.path.exists(p):
                return p
        return None

    def _sig(self):
        path = self._path()
        try:
            real = os.path.realpath(path)
            st = os.stat(real)
            return (path, real, st.st_mtime_ns, st.st_size)
        except (OSError, TypeError):
            return None

    def _load_under(self):
        """(Re)load the den by path (bromigos-wallpaper switches it). An image on
        the committed allowlist (background.den_plates, sha1 -> variant) is a den
        variant on the shared v1 plate: it gets the fitted overlays and the clean
        plate (baked steam/streaks/rows removed, redrawn live as loops). Any other
        image is drawn as is, with only the generic layers."""
        import hashlib
        from . import plate
        bg = self.cfg["background"]
        lp = self.cfg.get("loops", {})
        sig = self._sig()
        self.under_sig = sig
        if self.under is not None:
            GL.glDeleteTextures([self.under])
            self.under = None
        self.fitted = False
        self.variant = None
        self.segs = []
        if not sig:
            return
        path = sig[1]
        with open(path, "rb") as fh:
            self.variant = (bg.get("den_plates") or {}).get(hashlib.sha1(fh.read()).hexdigest())
        self.fitted = self.variant is not None
        steam = self.fitted and self.variant in (lp.get("steam") or [])
        if self.fitted and (steam or lp.get("streaks", True) or lp.get("rows", True)):
            v1 = os.path.expanduser(bg.get("den_plate", "") or "")
            img, self.segs, info = plate.clean_plate(path, v1, steam=steam, streaks=bool(lp.get("streaks", True)),
                                                    rows=bool(lp.get("rows", True)))
            if (self.w, self.h) != (plate.PLATE_W, plate.PLATE_H):
                import cairo  # noqa: F401  (scale through GdkPixbuf)
                import gi
                gi.require_version("GdkPixbuf", "2.0")
                from gi.repository import GdkPixbuf, GLib
                pb = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(img.tobytes()), GdkPixbuf.Colorspace.RGB,
                                                     False, 8, plate.PLATE_W, plate.PLATE_H, plate.PLATE_W * 3)
                pb = pb.scale_simple(self.w, self.h, GdkPixbuf.InterpType.BILINEAR)
                st = pb.get_rowstride()
                raw = np.frombuffer(pb.get_pixels(), dtype=np.uint8).reshape(self.h, st)[:, :self.w * 3]
                raw = np.ascontiguousarray(raw).reshape(self.h, self.w, 3)
            else:
                raw = img
        else:
            raw, _pb = load_image(path, self.w, self.h)
            if not self.fitted:
                print("bromigos-live: wallpaper is not an approved den variant; den overlays off", flush=True)
        self.steam_on = steam
        self.under = glkit.texture_rgba(raw, self.w, self.h, GL.GL_RGB)
        print(f"bromigos-live: plate {os.path.basename(path)} variant={self.variant} steam={steam} "
              f"streaks={len(self.segs)}", flush=True)
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

    def loop_uniforms(self, f):
        """Decorative loops. Phases come from wall-clock seconds in double precision
        (time.monotonic), each wrapped by its own period, so every loop closes exactly."""
        from . import plate
        lp = self.cfg.get("loops", {})
        sx, sy = self.w / 2560.0, self.h / 1440.0
        on = self.under is not None and self.fitted      # independent of the den-screens toggle
        T_s = float(lp.get("streak_period", 10))
        T_r = float(lp.get("row_period", 12))
        T_st = float(lp.get("steam_period", 7))
        now = self.loop_clock()
        f.f("u_loop", (now % T_s) / T_s, (now % T_r) / T_r, (now % T_st) / T_st, T_s)
        sk = np.zeros((16, 4), dtype=np.float32)
        sk2 = np.zeros((16, 4), dtype=np.float32)
        if on and lp.get("streaks", True):
            for i, sg in enumerate(self.segs[:16]):
                sk[i] = (sg["x0"] * sx, sg["y"] * sy, sg["x1"] * sx, sg["thick"] * sy)
                sk2[i] = (sg["amp"], 0.137 * (i + 1) + 0.71, 1.0 if sg["x0"] == 0 else 0.0, 1.0)
        f.fv("u_sk", sk, 4)
        f.fv("u_sk2", sk2, 4)
        f.fv("u_rows", np.array(plate.ROWS, dtype=np.float32) * sy, 1)
        f.f("u_rowfx", 1.0 if (on and lp.get("rows", True)) else 0.0, plate.FLOOR_X1 * sx, 926.0 * sy,
            float(lp.get("row_amp", 1.0)))
        f.f("u_steam", 1347.0 * sx, 1204.0 * sy, 47.0 * sx, 1.0 if (on and self.steam_on) else 0.0)
        f.f("u_steam2", 175.0 * sy, float(lp.get("steam_intensity", 0.55)), T_st, 100.0 * sy)

    def loop_clock(self):
        return time.monotonic()

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
        # sweep scheduling: periodic, on demand (scan), held, pinned
        sw = cfg["sweep"]
        sweep_x, sweep_on = 0.0, 0.0
        dur = float(sw.get("duration", 5.5))
        glow_hold, glow_fade = 0.0, 0.6
        if sw.get("enabled", True) or self.scan_req or self.scan_held:
            due = self.sweep_t0 is None or t - self.sweep_t0 > float(sw.get("interval", sw.get("period", 60)))
            if self.scan_req or (due and sw.get("enabled", True)):
                self.scan_req = False
                self.sweep_t0 = t
                self._draw_schematic(d)
            if self.sweep_t0 is not None:
                st = t - self.sweep_t0
                if st < dur + 2.0:
                    sweep_on = 1.0
                    sweep_x = -200 + (self.w + 400) * (st / dur)
        if self.scan_held and mono - getattr(self, "hold_t", mono) > 15.0:
            self.scan_held = False                     # a lost key release never sticks
        # pinned / held: keep the readings live (redraw every 2 s), ease in and out
        live = self.scan_pin or self.scan_held
        if live and mono - self.schem_at > 2.0:
            self._draw_schematic(d)
        dt = max(0.0, min(t - getattr(self, "_ease_t", t), 1.0))
        self._ease_t = t
        k_in = 1.0 - math.exp(-dt / 0.18)
        k_out = 1.0 - math.exp(-dt / 0.2)                   # released/unpinned: the original quick fade
        self.pin_amt += ((1.0 if self.scan_pin else 0.0) - self.pin_amt) * (k_in if self.scan_pin else k_out)
        self.hold_amt += ((1.0 if self.scan_held else 0.0) - self.hold_amt) * (k_in if self.scan_held else k_out)
        self.beam_speed = (self.w + 400) / dur
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
        f.f("u_scan", glow_hold, glow_fade, self.hold_amt, self.pin_amt)
        f.f("u_scan2", self.beam_speed, 0.0, 0.0, 0.0)
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
        sp = cfg.get("space", {})
        hl = gadgets.health(d) if sp.get("health_tint", True) else 0
        green = gadgets.all_green(d) and sp.get("relay_beam", True)
        rps = ((d.get("cluster") or {}).get("traefik") or {}).get("rpsNow") or 0.0
        f.f("u_space", 1.0 if sp.get("stars", True) else 0.0,
            gadgets.traffic_level(d) if sp.get("traffic", True) else -1.0, 1.0 if green else 0.0, float(hl))
        f.f("u_space_rect", 0.0, 34.0 * sy, 2400.0 * sx, (fl["horizon_y"] - 34.0) * sy)
        f.f("u_planet", 0.0, 0.0, 1.0, 0.0)
        f.f("u_sun", 0.0, 0.0, 0.0, 0.0)
        bx0, by0 = 2000.0 * sx, 370.0 * sy
        f.f("u_beam", bx0, by0, -2.5, 0.12 + min(rps, 6.0) / 12.0)
        self.loop_uniforms(f)
        self.stage.fs.draw()
        self.layers.draw(fbo, self.w, self.h, t, d)

    # ---- scanner control (bromigos-live scan / scan-pin / scan-hold on|off)
    def scan(self):
        self.scan_req = True

    def scan_pin_toggle(self):
        self.scan_pin = not self.scan_pin
        if self.scan_pin:
            self.schem_at = 0.0
        return self.scan_pin

    def scan_hold(self, on):
        if on and not self.scan_held:
            self.scan_req = True
        self.scan_held = on
        self.hold_t = time.monotonic()

    def _draw_schematic(self, d):
        self.schem_at = time.monotonic()
        surf = schematic.draw(d, self.st)
        if self.schem_tex is None:
            self.schem_tex = glkit.texture_from_cairo(surf)
        else:
            glkit.update_texture_from_cairo(self.schem_tex, surf)
