"""Worlds: a theme's whole live scene, drawn instead of the Wick's den.

When the current theme (bromigOS `bromigos theme set <name>`, rendered into
~/.local/state/bromigos/theme/current/) has `live/world.toml`, the background is that
world: layered art with parallax, a water plane, effects and actors, every one bound to
a real signal. Without it (the Wick) the den (live/scene.py) is drawn exactly as before.

The format is documented in bromigOS docs/theming.md ("live/: worlds") and in
docs/ELEMENTS.md ("Worlds"); in short, paths relative to the theme directory:

  [camera] [clock] [water]       how the layers sway, the light by the hour, the water
  [[layers]]                     art files back to front: depth, parallax, sky/water/fog
  [[effects]]                    reusable effect blocks, each bound to a signal
  [[actors]]                     creatures and craft (live/actors.py), bound to signals
  [sounds] [rollcall]            ambient cues by the user's activity; the login roll call

Signals (World.signals): cpu, gpu, mem, net, net_rx, net_tx, health (0/1/2), lab_green,
storm, ingress, user (working/dozing/asleep), activity, vector, agents, hour, daylight,
moon_phase, tide. Events: notify, critical, fill, fill_win, fill_loss, fill_open,
lab_alert, login (the roll call).

Frame: every layer and actor group shallower than the water is drawn into the back
target; the water/effects pass (shaders/world.frag) composes the frame from it (the
mirror reflects it); deeper layers and actors are drawn over that. Pause rules are the
den's (App.refresh_state): the world simply isn't rendered while paused.
"""
import math
import os
import random
import time
import tomllib

import numpy as np
from OpenGL import GL

from . import actors as A
from . import gadgets, glkit, skyclock
from .activity import get as activity

PLATE_W, PLATE_H = 2560.0, 1440.0
STATE = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
CURRENT = os.path.join(STATE, "bromigos", "theme", "current")


def log(*a):
    print("bromigos-live: world:", *a, flush=True)


# ------------------------------------------------------------------ finding the world
def world_file(cfg):
    """The world.toml in force, or None (the den). $BROMIGOS_WORLD (a theme directory or a
    world.toml) wins, then [world] dir, then the current theme."""
    w = cfg.get("world", {})
    if not w.get("enabled", True):
        return None
    for base in (os.environ.get("BROMIGOS_WORLD"), w.get("dir") or None, CURRENT):
        if not base:
            continue
        base = os.path.expanduser(base)
        p = base if base.endswith(".toml") else os.path.join(base, "live", "world.toml")
        if os.path.isfile(p):
            return p
    return None


def signature(cfg):
    """Changes when the world to draw changes (a theme switch, an edited world.toml)."""
    p = world_file(cfg)
    if not p:
        return None
    try:
        real = os.path.realpath(p)
        st = os.stat(real)
        return (real, st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def make_scene(cfg, data, w, h):
    """The background renderer: the theme's world, or the Wick's den. A world that fails
    to load falls back to the den (and says why in the log)."""
    p = world_file(cfg)
    if p:
        try:
            return World(cfg, data, w, h, p)
        except Exception as e:
            import traceback
            traceback.print_exc()
            log(f"{p} failed to load ({type(e).__name__}: {e}); drawing the den")
    from .scene import Background
    return Background(cfg, data, w, h)


# ------------------------------------------------------------------ images
def load_rgba(path):
    """(premultiplied RGBA uint8 array h x w x 4, w, h)."""
    from PIL import Image
    im = Image.open(path).convert("RGBA")
    a = np.asarray(im, dtype=np.uint8).copy()
    al = a[..., 3:4].astype(np.uint16)
    a[..., :3] = (a[..., :3].astype(np.uint16) * al // 255).astype(np.uint8)
    return a, im.width, im.height


def sprite_frames(root, rel):
    """A sprite's frame files: <rel>.webp (or .png), or <rel>/NN.webp in order."""
    base = os.path.join(root, rel)
    for ext in (".webp", ".png"):
        if os.path.isfile(base + ext):
            return [base + ext]
    if os.path.isfile(base):
        return [base]
    if os.path.isdir(base):
        fs = sorted(f for f in os.listdir(base) if f.lower().endswith((".webp", ".png")))
        return [os.path.join(base, f) for f in fs]
    return []


def build_atlas(root, rels, width=4096, pad=3):
    """Pack every sprite's frames into one premultiplied atlas. Returns (pixels, w, h,
    {rel: actors.Sprite}). A missing sprite becomes a grey block and is logged."""
    imgs = {}
    for rel in rels:
        files = sprite_frames(root, rel)
        if not files:
            log(f"sprite {rel} not found; a placeholder block stands in")
            blk = np.zeros((64, 48, 4), np.uint8)
            blk[...] = (60, 60, 60, 255)
            imgs[rel] = [blk]
            continue
        imgs[rel] = [load_rgba(f)[0] for f in files]
    x = y = row = 0
    place = {}
    for rel, frames in imgs.items():
        for i, im in enumerate(frames):
            h, w = im.shape[:2]
            if x + w + pad > width:
                x, y, row = 0, y + row + pad, 0
            place[(rel, i)] = (x, y, w, h)
            x += w + pad
            row = max(row, h)
    H = max(64, y + row + pad)
    atlas = np.zeros((H, width, 4), np.uint8)
    out = {}
    for rel, frames in imgs.items():
        fl = []
        for i, im in enumerate(frames):
            px, py, w, h = place[(rel, i)]
            atlas[py:py + h, px:px + w] = im
            fl.append(((px + 0.5) / width, (py + 0.5) / H, (px + w - 0.5) / width, (py + h - 0.5) / H, w / h))
        out[rel] = A.Sprite(fl)
    return atlas, width, H, out


# ------------------------------------------------------------------ the world
class Layer:
    def __init__(self, t, root):
        self.t = t
        self.id = t.get("id") or os.path.splitext(os.path.basename(t["file"]))[0]
        self.depth = float(t.get("depth", 0))
        self.parallax = float(t.get("parallax", 0.0))
        self.sky = bool(t.get("sky", False))
        self.water = bool(t.get("water", False))
        fog = t.get("fog", False)                 # true, or how much of the fog reaches it (0..1)
        self.fog = float(fog) if not isinstance(fog, bool) else (1.0 if fog else 0.0)
        px, w, h = load_rgba(os.path.join(root, t["file"]))
        self.tex = glkit.texture_rgba(np.ascontiguousarray(px), w, h, GL.GL_RGBA)


class Effects:
    """The world's [[effects]], by type (one block of each type per world)."""

    def __init__(self, world, items):
        self.world = world
        self.by = {}
        for e in items:
            self.by[e["type"]] = e
        self.strike_at = None
        self.strike = None          # (t0, x, seed)
        self.line_taut_until = -1.0
        self.line_jerk = 0.0
        self.beam_phase = 0.0
        self.mist_phase = 0.0
        self.swell_phase = 0.0

    def has(self, kind):
        return kind in self.by

    def defines(self):
        d = []
        for k, flag in (("rain", "FX_RAIN"), ("mist", "FX_MIST"), ("fireflies", "FX_FIREFLIES"),
                        ("line", "FX_LINE"), ("beam", "FX_BEAM"), ("spray", "FX_SPRAY"), ("rays", "FX_RAYS")):
            if k in self.by:
                d.append(flag)
        return d


class World:
    is_world = True

    def __init__(self, cfg, data, w, h, path):
        self.cfg, self.data = cfg, data
        self.w, self.h = w, h
        self.path = path
        self.root = os.path.dirname(os.path.dirname(os.path.abspath(path)))   # <theme>/live/world.toml
        with open(path, "rb") as f:
            self.spec = tomllib.load(f)
        sp = self.spec
        self.name = sp.get("name", os.path.basename(self.root))
        self.sx, self.sy = w / PLATE_W, h / PLATE_H
        t0 = time.monotonic()
        self.layers = sorted((Layer(L, self.root) for L in sp.get("layers", [])), key=lambda L: L.depth)
        self.water_layer = next((L for L in self.layers if L.water), None)
        self.water = sp.get("water", {})
        self.water_depth = self.water_layer.depth if self.water_layer else 1e9
        self.split = self.water.get("mode", "mirror") == "split"
        self.surface_y = float(self.water.get("line", 900))
        self.fx = Effects(self, sp.get("effects", []))
        # actors and their sprites
        rels = []
        for a in sp.get("actors", []):
            rels.append(a["sprite"])
            for v in a.get("on", []):
                if v.get("sprite"):
                    rels.append(v["sprite"])
            for st in (a.get("states") or {}).values():
                if isinstance(st, dict) and st.get("sprite"):
                    rels.append(st["sprite"])
        rels = list(dict.fromkeys(rels))
        atlas, aw, ah, sprites = build_atlas(self.root, rels)
        self.atlas = glkit.texture_rgba(np.ascontiguousarray(atlas), aw, ah, GL.GL_RGBA)
        self.defs = [A.Def(a, sprites, self) for a in sp.get("actors", [])]
        self.actors = A.Actors(self.defs)
        self.keeper = next((d for d in self.defs if d.kind == "keeper"), None)
        # GL
        defs = self.fx.defines() + (["WATER_SPLIT"] if self.split else [])
        src = glkit.read_shader("world.frag").replace(
            "#version 330 core", "#version 330 core\n" + "".join(f"#define {x}\n" for x in defs), 1)
        self.p_world = glkit.Program(glkit.read_shader("fs.vert"), src)
        self.p_layer = glkit.program("fs.vert", "world_layer.frag")
        self.p_world.cache, self.p_layer.cache = {}, {}
        self.sprites_gl = []
        self.glows_gl = []
        self.fs = glkit.Fullscreen()
        self.back = glkit.Target(w, h)
        self.t0 = time.monotonic()
        self.t_last = None
        self.cam = [0.0, 0.0]
        self.sig = {}
        self.smooth = {}
        self.forced = {}
        self.spray = [(0.0, 0.0, -10.0, 0.0)] * 6
        self.spray_i = 0
        self.line_hook = None
        self.queue = []             # (t, event) staggered fills
        self.sound_next = {}
        from .worldfeed import Feed
        self.feed = Feed(data)
        self.feed.start()
        act = activity()
        act.idle_after = float(cfg.get("world", {}).get("idle_after", 90))
        act.start(cfg["general"].get("monitor", "DP-1"))
        log(f"{self.name}: {len(self.layers)} layers, {len(self.defs)} actors, effects "
            f"{sorted(self.fx.by)} ({(time.monotonic() - t0) * 1000:.0f} ms) from {self.root}")

    # ---- the den's hooks, for App (the world has no scanner or rain bursts)
    def now(self):
        return time.monotonic() - self.t0

    def loop_clock(self):
        return time.monotonic()

    def burst(self, kind=0, x=None, strength=1.0):
        self.event({0: "notify", 1: "fill", 2: "critical"}.get(int(kind), "notify"))

    def wipe(self):
        pass

    def scan(self):
        pass

    def scan_pin_toggle(self):
        return False

    def scan_hold(self, on):
        pass

    def close(self):
        self.feed.halt()
        activity().halt()

    # ---- events
    def event(self, name, **info):
        t = self.now()
        if name == "fill":
            results = info.get("results") or ["open"]
            for i, r in enumerate(results[:3]):
                self.queue.append((t + i * 2.8, "fill_" + str(r)))
            return
        if name == "login":
            self.actors.event("rollcall", t)
            rc = self.spec.get("rollcall", {})
            if rc.get("sound"):
                self._play(rc["sound"])
            return
        self._fire(name, t)

    def _fire(self, name, t):
        if name.startswith("fill_"):
            self.fx.line_taut_until = t + 2.6
            self.fx.line_jerk = t
            if name == "fill_open":
                end = self.line_end()
                self._spray(end[0], end[1], t, 0.25)
        self.actors.event(name, t + (1.1 if name in ("fill_win", "fill_loss") else 0.0))

    def _spray(self, x, y, t, s):
        self.spray[self.spray_i % 6] = (x * self.sx, y * self.sy, t, s)
        self.spray_i += 1

    # ---- the control socket: bromigos-live ctl world …
    def command(self, verb, args):
        if verb in ("", "state"):
            return self.describe()
        if verb == "event":
            name, *rest = (args or "notify").split()
            if name == "fill":
                self.event("fill", results=rest or ["win"])
            else:
                self.event(name)
            return f"event {name}"
        if verb == "set":                          # set <signal> <value>: hold a signal (testing)
            k, _, v = args.partition(" ")
            if k == "agents":                      # agents a:working,b:needs_you,c:finished[,d:error]
                out = []
                for item in filter(None, v.replace(" ", ",").split(",")):
                    key, _, st = item.partition(":")
                    out.append({"key": key, "status": "needs_you" if st == "error" else (st or "working"),
                                "error": st == "error", "cwd": "", "name": key})
                self.forced["agents"] = out
                return f"agents = {len(out)}"
            try:
                self.forced[k] = float(v)
            except ValueError:
                self.forced[k] = v
            return f"{k} = {self.forced[k]}"
        if verb == "clear":
            self.forced.clear()
            return "signals live"
        if verb == "rollcall":
            self.event("login")
            return "roll call"
        return "world verbs: state, event <name> [win|loss|open], set <signal> <value>, clear, rollcall"

    def describe(self):
        s = self.sig
        n = {}
        for inst in self.actors.insts.values():
            n[inst.d.id] = n.get(inst.d.id, 0) + 1
        return (f"world {self.name} ({self.root})\n"
                f"user={s.get('user')} vector={s.get('vector')} health={s.get('health')} cpu={s.get('cpu', 0):.2f} "
                f"net={s.get('net', 0):.2f} hour={s.get('hour', 0):.2f} moon={s.get('moon_phase', 0):.2f} "
                f"tide={s.get('tide', 0):+.2f}\n"
                f"agents={len(s.get('agents') or [])} actors: " + ", ".join(f"{k}×{v}" for k, v in sorted(n.items()))
                + (f"\nforced: {self.forced}" if self.forced else ""))

    # ---- signals
    def _ease(self, key, v, dt, tau):
        cur = self.smooth.get(key, v)
        cur = cur + (v - cur) * (1.0 - math.exp(-dt / tau)) if tau > 0 else v
        self.smooth[key] = cur
        return cur

    def signals(self, d, dt):
        f = self.forced
        act = activity()
        lv = lambda v: max(0.0, min(1.0, math.log10(1.0 + v) / 7.3))  # noqa: E731
        hour = float(f.get("hour", skyclock.local_hour()))
        ph = float(f.get("moon_phase", skyclock.phase()))
        health = int(f.get("health", gadgets.health(d)))
        s = {
            "cpu": self._ease("cpu", float(f.get("cpu", (d.get("cpu") or 0.0) / 100.0)), dt, 3.0),
            "gpu": (d.get("gpu") or 0.0) / 100.0,
            "mem": (d.get("mem") or 0.0) / 100.0,
            "net": self._ease("net", float(f.get("net", gadgets.traffic_level(d))), dt, 4.0),
            "net_rx": self._ease("rx", float(f.get("net_rx", lv(d.get("rx") or 0.0))), dt, 4.0),
            "net_tx": self._ease("tx", float(f.get("net_tx", lv(d.get("tx") or 0.0))), dt, 4.0),
            "health": health,
            "lab_green": bool(f.get("lab_green", gadgets.all_green(d))) if "lab_green" not in f else bool(float(f["lab_green"])),
            "storm": 1.0 if health >= 2 else 0.0,
            "ingress": float(f.get("ingress", ((d.get("cluster") or {}).get("traefik") or {}).get("rpsNow") or 0.0)),
            "user": str(f.get("user", act.state())),
            "vector": str(f.get("vector", self.feed.vector)),
            "hour": hour,
            "moon_phase": ph,
            "tide": skyclock.tide(hour, ph),
        }
        s["activity"] = {"working": 1.0, "dozing": 0.4, "asleep": 0.0}.get(s["user"], 1.0)
        if "agents" in f:
            s["agents"] = f["agents"]
        else:
            s["agents"] = self.feed.agents
        return s

    # ---- geometry helpers (plate px)
    def line_tip(self):
        """The keeper's rod tip (its `rod` anchor for the frame showing), plate px."""
        inst = self.actors.insts.get((self.keeper.id, "keeper")) if self.keeper else None
        pl = getattr(inst, "placed", None) if inst else None
        anc = (self.keeper.anchors.get("rod") if self.keeper else None)
        if not pl or not anc:
            e = self.fx.by.get("line", {})
            return tuple(e.get("tip", (1400, 760)))
        x, base, w, h, rot, fi = pl
        u, v = anc[fi % len(anc)]
        if w < 0:
            u = 1.0 - u
        lx, ly = (u - 0.5) * abs(w), -(1.0 - v) * h
        ca, sa = math.cos(rot), math.sin(rot)
        return (x + lx * ca - ly * sa, base + lx * sa + ly * ca)

    def line_end(self):
        e = self.fx.by.get("line", {})
        return tuple(e.get("float", (1200, 960)))

    # ---- frame
    def render(self, fbo, fps):
        t = self.now()
        dt = 0.0 if self.t_last is None else max(0.0, min(t - self.t_last, 0.1))
        self.t_last = t
        d = self.data.snapshot()
        sig = self.signals(d, dt if dt > 0 else 1.0)
        self.sig = sig
        while self.queue and self.queue[0][0] <= t:
            _, name = self.queue.pop(0)
            self._fire(name, t)
        # the water line follows the tide
        wl = float(self.water.get("line", 900))
        if self.water.get("tide") == "moon":
            wl -= sig["tide"] * float(self.water.get("tide_range", 12))
        self.surface_y = wl
        self.line_hook = None
        sprites, glows, wakes = self.actors.update(t, dt, sig)
        for (x, y, t0, s) in self.actors.spray:
            self._spray(x, y, t0, s)
        self._sounds(t, sig)
        # camera: the pointer, eased; settles home when the user is idle
        cam = self.spec.get("camera", {})
        cx, cy = activity().cursor() if cam.get("parallax", "cursor") == "cursor" and not self.forced.get("still") else (0.0, 0.0)
        if "cam_x" in self.forced:
            cx, cy = float(self.forced["cam_x"]), float(self.forced.get("cam_y", 0.0))
        k = 1.0 - math.exp(-dt / 1.4) if dt > 0 else 1.0
        self.cam[0] += (cx - self.cam[0]) * k
        self.cam[1] += (cy - self.cam[1]) * k
        sway = cam.get("sway", (20, 8))
        self.sway = (float(sway[0]), float(sway[1]))
        # light: the hour's grade, the lightning
        cl = self.spec.get("clock", {})
        g = skyclock.grade(sig["hour"], {
            "night": cl.get("night", (0.6, 0.7, 0.85)), "day": cl.get("day", (1, 1, 1)),
            "dawn_tint": cl.get("dawn_tint", (1.0, 0.8, 0.8)), "dusk_tint": cl.get("dusk_tint", (1.0, 0.75, 0.6)),
            "dawn": cl.get("dawn", (5.5, 7.5)), "dusk": cl.get("dusk", (18.0, 20.5))})
        if sig.get("storm") and self.split:
            g = (g[0] * 0.7, g[1] * 0.72, g[2] * 0.8, g[3])
        self.grade = g
        day = skyclock.daylight(sig["hour"], tuple(cl.get("dawn", (5.5, 7.5))), tuple(cl.get("dusk", (18.0, 20.5))))
        lift = cl.get("day_lift", (0.0, 0.0, 0.0))
        self.lift = tuple(float(x) * day * (0.5 if sig.get("storm") else 1.0) for x in lift)
        flash = self._lightning(t, sig)
        self.flash = flash
        # ---- the back: everything shallower than the water
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE_MINUS_SRC_ALPHA)
        self.back.bind()
        GL.glClearColor(0, 0, 0, 1)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        items = self._draw_list(sprites, glows)
        back = [it for it in items if it[0] < self.water_depth]
        front = [it for it in items if it[0] > self.water_depth]
        self._draw_items(back, t, sig)
        # ---- the water and effects pass, into the frame
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, fbo)
        GL.glViewport(0, 0, self.w, self.h)
        GL.glDisable(GL.GL_BLEND)
        self._world_pass(t, sig, wakes)
        # ---- in front of the water
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE_MINUS_SRC_ALPHA)
        self._draw_items(front, t, sig)
        GL.glDisable(GL.GL_BLEND)

    def _draw_list(self, sprites, glows):
        by = {}
        for L in self.layers:
            if not L.water:
                by.setdefault(L.depth, [[], [], []])[0].append(L)
        for dep, s in sprites:
            by.setdefault(dep, [[], [], []])[1].append(s)
        for dep, g in glows:
            by.setdefault(dep, [[], [], []])[2].append(g)
        for e in (self.fx.by.get("beacon"),):
            if e:
                gl = self._beacon(e)
                if gl:
                    by.setdefault(float(e.get("depth", 20.5)), [[], [], []])[2].append(gl)
        return sorted(((k,) + tuple(v) for k, v in by.items()), key=lambda it: it[0])

    def _par(self, depth, par=None):
        """Parallax offset in screen px for a depth (interpolated between the layers)."""
        if par is None:
            ls = [L for L in self.layers]
            par = 0.0
            for i, L in enumerate(ls):
                if L.depth <= depth:
                    par = L.parallax
                    nxt = ls[i + 1] if i + 1 < len(ls) else None
                    if nxt and nxt.depth > depth:
                        f = (depth - L.depth) / (nxt.depth - L.depth)
                        par = L.parallax + (nxt.parallax - L.parallax) * f
        return (-self.cam[0] * self.sway[0] * par * self.sx, -self.cam[1] * self.sway[1] * par * self.sy)

    def _layer_view(self, L):
        ox, oy = self._par(L.depth, L.parallax)
        margin = 1.0 + 2.0 * max(self.sway[0] * self.sx / self.w, self.sway[1] * self.sy / self.h) * max(L.parallax, 0.0)
        return (-ox / self.w, -oy / self.h, margin)

    def _common(self, p):
        p.f("u_res", float(self.w), float(self.h))
        p.f("u_grade", *self.grade)
        p.f("u_flash", float(self.flash))
        p.f("u_lift", *self.lift)

    def _fog(self, p, amount=None):
        wt = self.water
        p.f("u_fog", self.surface_y * self.sy, float(wt.get("fog_distance", 260)) * self.sy, 1.0 if self.split else 0.0,
            float(wt.get("fog_actors", 0.6)) if amount is None else amount)
        p.f("u_fogcol", *[float(x) for x in wt.get("fog", (0.01, 0.04, 0.07))])

    def _draw_items(self, items, t, sig):
        gi = si = 0
        for depth, layers, sprs, glows in items:
            for L in layers:
                self._draw_layer(L, t, sig)
            if sprs:
                self._draw_sprites(si, sprs, depth, t)
                si += 1
            if glows:
                GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE)
                self._draw_glows(gi, glows, depth)
                GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE_MINUS_SRC_ALPHA)
                gi += 1

    def _draw_layer(self, L, t, sig):
        p = self.p_layer
        p.use()
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, L.tex)
        p.i("u_tex", 0)
        self._common(p)
        vx, vy, z = self._layer_view(L)
        p.f("u_view", vx, vy, z, 0.0)
        if L.sky:
            p.f("u_sky", 1.0, self.surface_y * self.sy, 0.55, 0.0)
            tw = self.spec.get("clock", {}).get("twilight", (1.0, 0.55, 0.35))
            p.f("u_twi", *[float(x) for x in tw])
            m = self.fx.by.get("moon")
            if m:
                ph = sig["moon_phase"]
                mx, my = skyclock.moon_place(sig["hour"], ph)
                if "moon_x" in self.forced:
                    mx, my = float(self.forced["moon_x"]), float(self.forced.get("moon_y", 0.8))
                win = m.get("window", (200, 60, 2300, 600))
                x = win[0] + (win[2] - win[0]) * mx
                y = win[3] - (win[3] - win[1]) * max(my, -0.3)
                r = float(m.get("radius", 36))
                bright = max(0.0, min(1.0, (my + 0.15) / 0.3)) * (1.0 - 0.7 * skyclock.daylight(sig["hour"]))
                if sig.get("storm") and m.get("storm_hides", True):
                    bright *= 0.15
                p.f("u_moon", x * self.sx, y * self.sy, r * self.sy, ph)
                p.f("u_moon2", bright, 0.0, 0.0, 0.0)
            else:
                p.f("u_moon", 0.0, 0.0, 0.0, 0.0)
            st = self.fx.strike
            if st and t - st[0] < 0.28:
                p.f("u_bolt", st[1] * self.sx, st[3] * self.sy, 1.0 - (t - st[0]) / 0.28, st[2])
            else:
                p.f("u_bolt", 0.0, 0.0, 0.0, 0.0)
        else:
            p.f("u_sky", 0.0, 0.0, 0.0, 0.0)
            p.f("u_moon", 0.0, 0.0, 0.0, 0.0)
            p.f("u_bolt", 0.0, 0.0, 0.0, 0.0)
        if L.fog:
            self._fog(p, L.fog)
        else:
            p.f("u_fog", 0.0, 1.0, 0.0, 0.0)
        self.fs.draw()

    def _inst_buf(self, pool, i, vs, fs, n):
        while len(pool) <= i:
            pool.append(glkit.Instanced(vs, fs, n))
            pool[-1].prog.cache = {}
        return pool[i]

    def _draw_sprites(self, i, sprs, depth, t):
        rows = []
        sx, sy = self.sx, self.sy
        for s in sprs:
            ox, oy = self._par(depth, s.get("par"))
            x, y = s["x"] * sx + ox, s["y"] * sy + oy
            w, h = s["w"] * sx, s["h"] * sy
            cut = s["cut"] * sy + oy if s["cut"] >= 0 else -1.0
            tint = s.get("tint")
            tr = (tint[0], tint[1], tint[2], tint[3] if len(tint) > 3 else 0.5) if tint else (0.0, 0.0, 0.0, 0.0)
            base = [x, y, w, h, *s["uv"], s["rot"], s["alpha"], cut, 0.0, *tr, s["reflect"],
                    1.0 if s["fog"] else 0.0, s["bright"], 0.0]
            if s["reflect"] > 0 and cut > 0:
                r = list(base)
                r[11] = 1.0
                rows.append(r)
            rows.append(base)
        buf = self._inst_buf(self.sprites_gl, i, "world_sprite.vert", "world_sprite.frag", 5)
        buf.upload(np.array(rows, np.float32))
        p = buf.prog
        p.use()
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.atlas)
        p.i("u_atlas", 0)
        self._common(p)
        p.f("u_time", t)
        p.f("u_water", *[float(x) for x in self.water.get("tint", (0.03, 0.06, 0.07))])
        self._fog(p)
        buf.draw()

    def _draw_glows(self, i, glows, depth):
        rows = []
        sx, sy = self.sx, self.sy
        ox, oy = self._par(depth)
        for (x, y, rx, ry, r, g, b, inten, fog) in glows:
            rows.append([x * sx + ox, y * sy + oy, rx * sy, ry * sy, r, g, b, inten, fog, 0, 0, 0])
        buf = self._inst_buf(self.glows_gl, i, "world_glow.vert", "world_glow.frag", 3)
        buf.upload(np.array(rows, np.float32))
        p = buf.prog
        p.use()
        p.f("u_res", float(self.w), float(self.h))
        self._fog(p)
        buf.draw()

    # ---- effects
    def _lightning(self, t, sig):
        e = self.fx.by.get("lightning")
        if not e:
            return 0.0
        v = float(sig.get(e.get("signal", "cpu"), 0.0) or 0.0)
        on = v >= float(e.get("above", 0.88))
        fx = self.fx
        if on:
            if fx.strike_at is None:
                fx.strike_at = t + 1.0 + random.random() * 2.0
            if t >= fx.strike_at:
                zone = e.get("zone", (200, 2300))
                fx.strike = (t, zone[0] + (zone[1] - zone[0]) * random.random(), random.random() * 100.0,
                             float(e.get("ground", self.surface_y)))
                ev = e.get("every", (5, 14))
                fx.strike_at = t + ev[0] + (ev[1] - ev[0]) * random.random()
        else:
            fx.strike_at = None
        st = fx.strike
        if not st:
            return 0.0
        a = t - st[0]
        if a > 0.6:
            return 0.0
        return float(e.get("flash", 0.9)) * (math.exp(-a / 0.06) + 0.6 * math.exp(-((a - 0.18) ** 2) / 0.002))

    def _beacon(self, e):
        on = bool(self.sig.get(e.get("signal", "lab_green")))
        if not on:
            return None
        t = self.now()
        per = float(e.get("period", 2.4))
        u = (t % per) / per
        k = math.exp(-((u - 0.1) ** 2) / 0.004) + 0.15
        c = e.get("color", (1.0, 0.3, 0.25))
        r = float(e.get("radius", 7))
        at = e.get("at", (1800, 300))
        return (at[0], at[1], r, r, c[0], c[1], c[2], k)  + (0.0,)

    def _world_pass(self, t, sig, wakes):
        p = self.p_world
        p.use()
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.back.tex)
        p.i("u_back", 0)
        GL.glActiveTexture(GL.GL_TEXTURE1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.water_layer.tex if self.water_layer else self.back.tex)
        p.i("u_water", 1)
        GL.glActiveTexture(GL.GL_TEXTURE0)
        sx, sy = self.sx, self.sy
        self._common(p)
        p.f("u_time", t)
        p.f("u_scale", sy)
        if self.water_layer:
            vx, vy, z = self._layer_view(self.water_layer)
            p.f("u_wview", vx, vy, z, 0.0)
        wt = self.water
        fx = self.fx
        cpu = sig["cpu"]
        dt = max(0.0, min(t - getattr(self, "_fx_t", t), 0.1))
        self._fx_t = t
        # rain and mist (the den's CPU rain, as weather)
        rain = 0.0
        e = fx.by.get("rain")
        if e:
            v = float(sig.get(e.get("signal", "cpu"), 0.0) or 0.0)
            rain = max(0.0, min(1.0, (v - float(e.get("from", 0.3))) / max(float(e.get("full", 0.85)) - float(e.get("from", 0.3)), 1e-3)))
        p.f("u_rain", rain, 0.0, 0.0, 0.0)
        base_ripple = float(wt.get("ripple", 0.6)) * (0.35 + 0.65 * min(1.0, cpu * 2.5))
        p.f("u_line", self.surface_y * sy, 0.0, float(wt.get("reflect", 0.7)), base_ripple)
        e = fx.by.get("mist")
        if e:
            v = float(sig.get(e.get("signal", "cpu"), 0.0) or 0.0)
            band = e.get("band", (700, 1100))
            strength = float(e.get("base", 0.25)) + float(e.get("gain", 0.6)) * min(1.0, v / max(float(e.get("full", 0.35)), 1e-3))
            strength *= 1.0 - 0.4 * rain
            fx.mist_phase = (fx.mist_phase + dt * (0.015 + 0.06 * v)) % 1000.0
            p.f("u_mist", strength, band[0] * sy, band[1] * sy, fx.mist_phase)
            p.f("u_mistcol", *[float(x) for x in e.get("color", (0.55, 0.62, 0.62))])
        e = fx.by.get("fireflies")
        if e:
            v = float(sig.get(e.get("signal", "net"), 0.0) or 0.0)
            z = e.get("zone", (0, 600, 2560, 1100))
            dens = float(e.get("base", 0.04)) + float(e.get("gain", 0.5)) * v
            p.f("u_ff", dens, float(e.get("brightness", 1.0)) * (0.6 + 0.6 * v), float(e.get("cell", 70)) * sy, 0.0)
            p.f("u_ffzone", z[0] * sx, z[1] * sy, z[2] * sx, z[3] * sy)
            p.f("u_ffcol", *[float(x) for x in e.get("color", (0.85, 1.0, 0.45))])
        e = fx.by.get("line")
        if e:
            tip = self.line_tip()
            end = self.line_hook or self.line_end()
            taut = t < fx.line_taut_until or self.line_hook is not None
            sag = 0.0 if taut else float(e.get("sag", 26.0))
            if taut and self.line_hook is None:
                a = t - fx.line_jerk
                end = (end[0] + math.sin(a * 21.0) * 2.0 * math.exp(-a), end[1] + 7.0 * math.exp(-a * 0.8))
            ox, oy = self._par(float(e.get("depth", 31)))
            p.f("u_fline", tip[0] * sx + ox, tip[1] * sy + oy, end[0] * sx + ox, end[1] * sy + oy)
            p.f("u_fline2", sag * sy, 1.0, 0.0, 0.0)
            p.f("u_flinecol", *[float(x) for x in e.get("color", (0.8, 0.82, 0.78))])
        e = fx.by.get("beam")
        if e:
            rate = float(e.get("rate", 0.35)) + float(e.get("rate_gain", 0.12)) * min(float(sig.get(e.get("rate_signal", "ingress"), 0.0) or 0.0), 6.0)
            fx.beam_phase = (fx.beam_phase + dt * rate) % (2 * math.pi)
            cols = e.get("colors", [(1.0, 0.95, 0.8), (1.0, 0.72, 0.25), (1.0, 0.3, 0.25)])
            lvl = int(sig.get(e.get("signal", "health"), 0) or 0)
            c = cols[max(0, min(lvl, len(cols) - 1))]
            at = e.get("at", (1880, 225))
            ox, oy = self._par(float(e.get("depth", 20)))
            p.f("u_beam", at[0] * sx + ox, at[1] * sy + oy, fx.beam_phase, 1.0)
            p.f("u_beam2", float(e.get("reach", 2400)) * sx, 0.0, 0.0, 0.0)
            p.f("u_beamcol", *[float(x) for x in c])
        e = fx.by.get("swell")
        if e:
            v = float(sig.get(e.get("signal", "cpu"), 0.0) or 0.0)
            amp = float(e.get("min", 3)) + (float(e.get("max", 26)) - float(e.get("min", 3))) * v
            amp = self._ease("swell_amp", amp, dt if dt > 0 else 1.0, 2.5)
            fx.swell_phase = (fx.swell_phase + dt * (0.5 + 1.2 * v)) % (2 * math.pi * 1000)
            p.f("u_swell", amp * sy, float(e.get("wavelength", 420)) * sx, fx.swell_phase, min(1.0, amp / 18.0))
            p.f("u_caus", float(e.get("caustics", 0.6)) * (0.4 + 0.6 * v), 0.0, 0.0, 0.0)
        else:
            p.f("u_swell", 0.0, 400.0, 0.0, 0.0)
            p.f("u_caus", 0.3, 0.0, 0.0, 0.0)
        e = fx.by.get("rays")
        if e:
            day = skyclock.daylight(sig["hour"])
            mx, my = skyclock.moon_place(sig["hour"], sig["moon_phase"])
            moon = skyclock.illumination(sig["moon_phase"]) * max(0.0, min(1.0, (my + 0.1) / 0.3))
            light = max(day, moon * 0.8) * (0.4 if sig.get("storm") else 1.0)
            p.f("u_rays", float(e.get("gain", 0.25)) * (float(e.get("base", 0.15)) + (1.0 - float(e.get("base", 0.15))) * light),
                float(e.get("slant", 0.18)), float(e.get("reach", 520)) * sy, 0.0)
            p.f("u_rayscol", *[float(x) for x in e.get("color", (0.45, 0.75, 0.85))])
        wk = np.zeros((12, 4), np.float32)
        ox, oy = self._par(self.water_depth)
        for i, (x, y, s) in enumerate(wakes[:12]):
            wk[i] = (x * sx + ox, y * sy + oy, s, 0.0)
        p.fv("u_wake", wk, 4)
        p.fv("u_spray", np.array(self.spray, np.float32), 4)
        self.fs.draw()

    # ---- ambient sound: the creatures follow the user
    def _sounds(self, t, sig):
        snd = self.spec.get("sounds", {})
        amb = snd.get("ambient") or []
        if not amb or not self.cfg.get("world", {}).get("ambient_sounds", True):
            return
        if getattr(self, "offscreen", False):
            return
        mult = {"working": 1.0, "dozing": 3.0}.get(sig["user"])
        for i, a in enumerate(amb):
            nxt = self.sound_next.get(i)
            ev = a.get("every", (10, 30))
            if mult is None:
                self.sound_next[i] = None
                continue
            if nxt is None:
                self.sound_next[i] = t + (ev[0] + (ev[1] - ev[0]) * random.random()) * mult
                continue
            if t >= nxt:
                self._play(a["file"], float(a.get("gain", 0.5)))
                self.sound_next[i] = t + (ev[0] + (ev[1] - ev[0]) * random.random()) * mult

    def _play(self, rel, gain=0.6):
        app = getattr(self, "app", None)
        snd = getattr(app, "sound", None) if app else None
        path = os.path.join(self.root, rel)
        if snd and os.path.isfile(path):
            snd.play_file(path, gain=gain)
