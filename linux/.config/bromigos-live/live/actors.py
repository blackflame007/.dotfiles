"""The worlds' actors: creatures and craft bound to real signals (live/world.py draws them).

An actor definition is one `[[actors]]` table in a world's `live/world.toml`; its `kind`
says where its instances come from and which states they have:

  agents   one instance per herdr agent (the Swarm deck's data). States: working,
           needs_you, finished; `gone` when the agent closes (then it leaves).
  keeper   the world's keeper, one instance mirroring the user: working (active),
           dozing (idle), asleep (session locked). Its `lamp` dims with it.
  signal   one instance whose state is a signal's value (lab health 0/1/2, VECTOR's
           state ...). A state with `hidden = true` hides it.
  crowd    a fixed flock at `spots`, following the user's activity like the keeper
           (working, dozing, asleep).
  traffic  craft crossing on lanes; whether a crossing carries one is decided once, as it
           starts off-screen, from its signal (the Wick's ship rule: nothing pops).
  event    spawned by events (notify, critical, fill_win, fill_loss, ...): `[[actors.on]]`
           variants, each with its own motion, sprite, depth and lifetime.

Every state names a `motion` (below) and how its lights burn. The "needs you" gesture is
shared by every kind: `turn = true` stops the actor, turns it to face the viewer (the
`front` frame when the strip has one, else a squash-turn) and `signal = true` blinks its
lights in the signal colour at 0.55 Hz, after one bright flash.

Motions: still, hold, bob, rock, wander, settle, hover, circle, drift, pace, croak,
breach, dive, rise, approach, reel, drift_up, dart, cross. Positions are plate pixels
(2560x1440); `update()` returns sprite and glow instances in plate pixels, the renderer
scales them.
"""
import math
import random

TAU = 2 * math.pi


def _rng(*key):
    return random.Random(hash(key) & 0xFFFFFFFF)


def _ease(cur, target, dt, tau):
    if tau <= 0:
        return target
    return cur + (target - cur) * (1.0 - math.exp(-dt / tau))


def _smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


class Sprite:
    """A sprite's frames in the atlas: list of (u0, v0, u1, v1, aspect w/h)."""

    def __init__(self, frames, video=None):
        self.frames = frames
        self.video = video          # a VideoLoop: the frame is its texture (uv 0..1)

    def frame(self, i):
        return self.frames[int(i) % len(self.frames)]


class Def:
    def __init__(self, t, sprites, world):
        self.t = t
        self.id = t["id"]
        self.kind = t.get("kind", "signal")
        self.sprite = sprites[t["sprite"]]
        self.sprites = sprites
        self.height = float(t.get("height", 100))
        self.depth = float(t.get("depth", 25))
        self.parallax = t.get("parallax")
        self.wade = float(t.get("wade", 0.0))
        self.reflect = float(t.get("reflect", 0.0))
        self.fog = bool(t.get("fog", False))
        self.at = tuple(t.get("at", (1280, 900)))
        self.zones = [tuple(z) for z in t.get("zones", [])] or ([tuple(t["zone"])] if "zone" in t else [])
        self.frames = {k: list(v) for k, v in (t.get("frames") or {}).items()}
        self.lights = t.get("lights") or []
        self.anchors = t.get("anchors") or {}
        self.states = t.get("states") or {}
        self.lamp = t.get("lamp")
        self.signal = t.get("signal")
        self.max = int(t.get("max", 12))
        self.signal_color = tuple(t.get("signal_color", (1.0, 0.68, 0.22)))
        self.error_color = tuple(t.get("error_color", (1.0, 0.4, 0.35)))
        self.on = t.get("on") or []
        self.spots = [tuple(s) for s in t.get("spots", [])]
        self.world = world

    def state_cfg(self, state):
        return self.states.get(state) or {}

    def frame_list(self, name, default=None):
        f = self.frames.get(name)
        if f:
            return f
        return default if default is not None else [0]


class Inst:
    def __init__(self, d, key, t):
        self.d = d
        self.key = key
        self.born = t
        self.state = None
        self.state_t = t
        self.x, self.y = d.at
        self.face = 1.0
        self.turn = 0.0
        self.light = 0.0
        self.lamp = 1.0
        self.sink = 1.0 if d.kind == "agents" else 0.0
        self.alpha = 0.0
        self.dist = 0.0
        self.target = None
        self.pause_until = 0.0
        self.scale = 1.0
        self.error = False
        self.dead = False
        self.flare = 0.0           # roll call: a brief light flare
        self.flare_t = -1.0
        self.v = None               # event / traffic: the variant table and path
        self.path = None
        self.life = 0.0
        self.extra = {}
        self.dx = self.dy = self.rot = 0.0
        self.frame = None
        self.turn_target = 0.0
        self.spot = d.at
        self.zone = None
        self.placed = None
        self.slot = None
        self.slot_cfg = {}
        self.clip = None
        self.clip_hold = False
        r = _rng(d.id, key)
        self.r = r
        self.seed = r.random()


# --------------------------------------------------------------------------- the system
class Actors:
    def __init__(self, defs):
        self.defs = defs
        self.insts = {}            # (def id, key) -> Inst
        self.events = []           # (variant, def, t) waiting to spawn
        self.spray = []            # (x, y, t0, strength) new this frame
        self.n_event = 0
        self.lanes = {}
        self.sounds = []           # cues the actors asked for this frame (relative paths)

    # ---- events
    def event(self, name, t, **info):
        for d in self.defs:
            if d.kind != "event":
                continue
            for v in d.on:
                if v.get("event") == name:
                    for k in range(int(v.get("count", 1))):
                        self.n_event += 1
                        inst = Inst(d, f"ev{self.n_event}", t + k * float(v.get("stagger", 0.35)))
                        inst.v = v
                        self.insts[(d.id, inst.key)] = inst
        if name == "rollcall":
            i = 0
            for inst in sorted(self.insts.values(), key=lambda s: (s.d.depth, s.x)):
                if inst.d.kind in ("agents", "keeper", "signal"):
                    inst.flare_t = t + 0.6 + 0.45 * i
                    i += 1

    # ---- per frame
    def update(self, t, dt, sig):
        """Advance every actor. sig: the world's signals (see world.Signals). Returns
        (sprites, glows, wakes): sprites = [(depth, dict)], glows = [(depth, (x, y, rx, ry, r, g, b, i, fog))],
        wakes = [(x, y, strength)]."""
        self.spray = []
        self.sounds = []
        self.rings, self.bubbles, self.disturb = [], [], []
        sprites, glows, wakes = [], [], []
        for d in self.defs:
            getattr(self, "_sync_" + d.kind, lambda *a: None)(d, t, sig)
        for key in list(self.insts):
            inst = self.insts[key]
            if t < inst.born:
                continue
            self._step(inst, t, dt, sig)
            if inst.dead:
                del self.insts[key]
                continue
            self._emit(inst, t, sig, sprites, glows, wakes)
        lamp_glows = []
        for d in self.defs:
            if d.kind == "keeper" and d.lamp:
                inst = self.insts.get((d.id, "keeper"))
                lv = inst.lamp if inst else 1.0
                lp = d.lamp
                flick = 1.0 + 0.04 * math.sin(t * 7.3) * math.sin(t * 2.9)
                fl = (1.0 + 1.5 * inst.flare) if inst else 1.0
                c = lp.get("color", (1.0, 0.7, 0.35))
                r = float(lp.get("radius", 90))
                lamp_glows.append((float(lp.get("depth", d.depth)),
                                   (lp["at"][0], lp["at"][1], r, r, c[0], c[1], c[2], lv * flick * fl, 0.0)))
        return sprites, glows + lamp_glows, wakes

    # ---- populations
    def _sync_agents(self, d, t, sig):
        agents = sig.get("agents") or []
        take = d.t.get("take", (0, d.max))
        live = {}
        for a in agents[int(take[0]):int(take[1])][:d.max]:
            live[a["key"]] = a
        slots = d.t.get("slots")
        used = {getattr(o, "slot", None) for (did, _), o in self.insts.items() if did == d.id and o.state != "gone"}
        for k, a in live.items():
            inst = self.insts.get((d.id, k))
            if inst is None and slots:                 # a fixed place (a foreground head), the first free one
                free = [i for i in range(len(slots)) if i not in used]
                if not free:
                    continue
                inst = Inst(d, k, t)
                inst.slot = free[0]
                used.add(free[0])
                sl = slots[free[0]]
                inst.x, inst.y = sl["at"]
                inst.face = float(sl.get("face", 1.0))
                inst.slot_cfg = sl
                self.insts[(d.id, k)] = inst
            if inst is None:
                inst = Inst(d, k, t)
                zones = d.zones or [(d.at[0] - 200, d.at[1], d.at[0] + 200, d.at[1] + 30)]
                others = [(o.x, o.y) for (did, _), o in self.insts.items() if did == d.id and o.state != "gone"]
                best = None
                for _ in range(10):                 # the spot farthest from the others
                    z = zones[inst.r.randrange(len(zones))]
                    p = (z[0] + (z[2] - z[0]) * inst.r.random(), z[1] + (z[3] - z[1]) * inst.r.random())
                    gap = min((abs(p[0] - ox) + 2 * abs(p[1] - oy) for ox, oy in others), default=1e9)
                    if best is None or gap > best[0]:
                        best = (gap, z, p)
                _, z, (inst.x, inst.y) = best
                inst.zone = z
                inst.face = 1.0 if inst.r.random() < 0.5 else -1.0
                self.insts[(d.id, k)] = inst
            inst.error = bool(a.get("error"))
            self._set_state(inst, a["status"], t)
        for (did, k), inst in self.insts.items():
            if did == d.id and k not in live:
                self._set_state(inst, "gone", t)

    def _sync_keeper(self, d, t, sig):
        inst = self.insts.get((d.id, "keeper"))
        if inst is None:
            inst = Inst(d, "keeper", t)
            inst.sink = 0.0
            inst.alpha = 1.0
            inst.lamp = 0.15
            self.insts[(d.id, "keeper")] = inst
        self._set_state(inst, sig.get("user", "working"), t)

    def _sync_signal(self, d, t, sig):
        inst = self.insts.get((d.id, "one"))
        if inst is None:
            inst = Inst(d, "one", t)
            inst.sink = 0.0
            self.insts[(d.id, "one")] = inst
        v = sig.get(d.signal)
        key = str(int(v)) if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v)
        if isinstance(v, bool):
            key = "1" if v else "0"
        self._set_state(inst, key, t)

    def _sync_crowd(self, d, t, sig):
        for i, spot in enumerate(d.spots):
            inst = self.insts.get((d.id, i))
            if inst is None:
                inst = Inst(d, i, t)
                inst.sink = 0.0
                inst.x, inst.y = spot
                inst.spot = spot
                inst.face = 1.0 if inst.r.random() < 0.5 else -1.0
                self.insts[(d.id, i)] = inst
            self._set_state(inst, sig.get("user", "working"), t)

    def _sync_traffic(self, d, t, sig):
        lv = float(sig.get(d.signal, 0.0) or 0.0)
        n = int(d.t.get("lanes", 3))
        for k in range(n):
            inst = self.insts.get((d.id, k))
            if inst is None or inst.path is None or t - inst.path[0] >= inst.path[1]:
                cyc = 0 if inst is None else inst.extra.get("cyc", 0) + 1
                first = inst is None
                inst = Inst(d, k, t)
                inst.sink = 0.0
                inst.extra["cyc"] = cyc
                r = _rng(d.id, k, cyc)
                band = d.t.get("band", (d.at[1], d.at[1]))
                inst.y = band[0] + (band[1] - band[0]) * r.random()
                sp = d.t.get("speed", (20, 40))
                v = sp[0] + (sp[1] - sp[0]) * r.random()
                direction = float(d.t.get("dir", 1)) or (1.0 if r.random() < 0.5 else -1.0)
                x0, x1 = d.t.get("span", (-300, 2860))
                length = x1 - x0
                dur = length / v
                t0 = t - (dur * r.random() if first else 0.0)
                inst.path = (t0, dur, x0, x1, direction)
                inst.face = direction
                inst.busy = r.random() < float(d.t.get("base", 0.1)) + float(d.t.get("gain", 0.9)) * lv
                inst.state = "crossing"
                self.insts[(d.id, k)] = inst

    # ---- state machine
    def _set_state(self, inst, state, t):
        if state == inst.state:
            return
        prev = inst.state
        inst.state = state
        inst.state_t = t
        cfg = inst.d.state_cfg(state)
        if not cfg.get("turn"):
            inst.turn_target = 0.0
        else:
            inst.turn_target = 1.0
        sc = inst.slot_cfg or {}
        clip = ((sc.get("states") or {}).get(state, {}).get("clip")) or cfg.get("clip")
        inst.clip = None
        if clip and inst.d.sprites.get(clip) and inst.d.sprites[clip].video:
            inst.clip = inst.d.sprites[clip]        # a one-shot clip: plays once, then holds or chains
            inst.clip.video.restart()
            inst.clip_hold = bool(((sc.get("states") or {}).get(state, {}).get("hold")) or cfg.get("hold"))
        if inst.d.kind == "agents":
            under = prev is None or prev in ("finished", "gone")
            if state in ("working", "needs_you") and under:
                # an agent starts (or works again): bubbles, a swell, then it breaks the surface
                inst.sink = max(inst.sink, 1.0) if prev is None else inst.sink
                inst.rise_t = t
                inst.extra.pop("booted", None)
                self.bubbles.append((inst.x, inst.y, t, 1.0))
                self.bubbles.append((inst.x + 20, inst.y + 4, t + 0.7, 0.8))
            elif state in ("finished", "gone") and prev in ("working", "needs_you"):
                # it submerges: rings spread, the last bubbles rise, the fireflies scatter
                inst.rise_t = None
                inst.sub_t = t
                self.rings.append((inst.x, inst.y, t, 1.0))
                self.disturb.append((inst.x, inst.y - inst.d.height * 0.4, t))
        if state == "gone":
            inst.gone_t = t

    # ---- motions
    def _step(self, inst, t, dt, sig):
        d = inst.d
        if inst.v is not None:
            return self._step_event(inst, t, dt, sig)
        if d.kind == "traffic":
            t0, dur, x0, x1, direction = inst.path
            f = (t - t0) / dur
            inst.x = x0 + (x1 - x0) * f if direction > 0 else x1 - (x1 - x0) * f
            inst.alpha = 1.0 if inst.busy else 0.0
            inst.light = 1.0
            inst.frame = int((t * float(d.t.get("fps", 0))) % max(len(d.sprite.frames), 1))
            return
        cfg = d.state_cfg(inst.state)
        req = d.t.get("requires")
        hidden = bool(cfg.get("hidden")) or bool(req and not sig.get(req))
        inst.alpha = _ease(inst.alpha, 0.0 if hidden else 1.0, dt, 0.8)
        inst.turn = _ease(inst.turn, getattr(inst, "turn_target", 0.0), dt, 0.35)
        target_light = float(cfg.get("light", 1.0))
        inst.light = _ease(inst.light, target_light, dt, 0.6)
        inst.lamp = _ease(inst.lamp, float(cfg.get("lamp", 1.0)), dt, 1.4)
        if inst.flare_t > 0:
            a = t - inst.flare_t
            inst.flare = math.exp(-((a - 0.3) ** 2) / 0.06) if -0.5 < a < 1.6 else 0.0
            if a > 1.6:
                inst.flare_t = -1.0
        m = cfg.get("motion", "hold")
        rise_t = getattr(inst, "rise_t", None)
        if d.kind == "agents" and rise_t is not None:
            a = t - rise_t
            hold = float(d.t.get("rise_hold", 1.2))          # bubbles first, still under
            dur = float(d.t.get("rise_seconds", 2.6))
            if a < hold:
                inst.sink = max(inst.sink, 1.0)
            elif a < hold + dur:
                if not inst.extra.get("swell"):
                    inst.extra["swell"] = True
                    self.rings.append((inst.x, inst.y, t, 0.9))       # the swell, as it breaks the surface
                    self.disturb.append((inst.x, inst.y - d.height * 0.3, t))
                f = _smooth((a - hold) / dur)
                inst.sink = 1.0 + (float(cfg.get("sink", 0.0)) - 1.0) * f
            else:
                inst.rise_t = None
                inst.extra.pop("swell", None)
            # the eyes boot with a flicker as they clear the water
            eye_v = float(d.t.get("eye_v", 0.3))                    # how far down the sprite the eyes sit
            wade = float(d.wade)
            clear = inst.sink + wade < (1.0 - eye_v)
            if clear and "booted" not in inst.extra:
                inst.extra["booted"] = t
        sub_t = getattr(inst, "sub_t", None)
        if sub_t is not None:
            for k, at in enumerate((2.6, 3.4)):                   # the last bubbles
                if t - sub_t >= at and not inst.extra.get(f"lastbub{k}"):
                    inst.extra[f"lastbub{k}"] = True
                    self.bubbles.append((inst.x + 14 * k, inst.y, t, 0.7))
            if t - sub_t > 4.0:
                inst.sub_t = None
                inst.extra.pop("lastbub0", None)
                inst.extra.pop("lastbub1", None)
        if "at" in cfg and d.kind in ("keeper", "signal"):     # a state can have its own place
            inst.x, inst.y = cfg["at"]
        elif "at" not in cfg and d.kind in ("keeper", "signal") and m != "pace":
            inst.x, inst.y = d.at
        inst.dx = inst.dy = inst.rot = 0.0
        inst.frame = None
        sink_target = float(cfg.get("sink", 0.0))
        if getattr(inst, "rise_t", None) is not None:
            pass                                    # the rise sets the sink itself
        elif m == "settle":
            inst.sink = _ease(inst.sink, sink_target, dt, 1.2)
        else:
            inst.sink = _ease(inst.sink, sink_target, dt, 1.5)
        if inst.state == "gone":
            fade = float(cfg.get("fade", 5.0))
            if t - getattr(inst, "gone_t", t) > fade:
                inst.dead = True
            inst.alpha = max(0.0, 1.0 - (t - inst.gone_t) / fade)
        amp, rate = float(cfg.get("amp", 2.0)), float(cfg.get("rate", 0.3))
        ph = inst.seed * TAU
        if m == "wander" and inst.turn < 0.05:
            z = getattr(inst, "zone", None) or (inst.x - 100, inst.y, inst.x + 100, inst.y)
            if inst.target is None or (abs(inst.target - inst.x) < 2 and t > inst.pause_until):
                inst.target = z[0] + (z[2] - z[0]) * inst.r.random()
            if abs(inst.target - inst.x) >= 2:
                sp = float(cfg.get("speed", 8.0)) * dt
                step = max(-sp, min(sp, inst.target - inst.x))
                inst.x += step
                inst.dist += abs(step)
                inst.face = 1.0 if step > 0 else -1.0
                if abs(inst.target - inst.x) < 2:
                    inst.pause_until = t + 2 + 5 * inst.r.random()
            inst.dy = math.sin(t * 1.3 + ph) * float(cfg.get("bob", 1.5))
        elif m in ("bob", "hold"):
            inst.dy = math.sin(t * TAU * rate + ph) * (amp if m == "bob" else amp * 0.4)
        elif m == "rock":
            inst.rot = math.sin(t * TAU * rate + ph) * math.radians(amp)
        elif m == "hover":
            inst.dx = math.sin(t * 0.7 + ph) * amp
            inst.dy = math.sin(t * 1.1 + ph) * amp * 0.8
        elif m == "circle":
            inst.dx = math.cos(t * TAU * rate + ph) * amp
            inst.dy = math.sin(t * TAU * rate + ph) * amp * 0.35
            inst.face = -1.0 if math.sin(t * TAU * rate + ph) > 0 else 1.0
        elif m == "drift":
            inst.dx = math.sin(t * TAU * rate + ph) * amp
            inst.dy = math.sin(t * TAU * rate * 1.7 + ph) * amp * 0.1
            inst.face = 1.0 if math.cos(t * TAU * rate + ph) > 0 else -1.0
        elif m == "pace":
            path = cfg.get("path") or d.t.get("path") or (inst.x - 40, inst.x + 40)
            sp = float(cfg.get("speed", 6.0))
            span = abs(path[1] - path[0]) or 1.0
            per = 2 * span / sp + 2 * float(cfg.get("pause", 3.0))
            u = ((t + inst.seed * per) % per) / per
            pause = float(cfg.get("pause", 3.0)) / per
            if u < 0.5 - pause:
                f, inst.face = u / (0.5 - pause), 1.0
            elif u < 0.5:
                f = 1.0
            elif u < 1.0 - pause:
                f, inst.face = 1.0 - (u - 0.5) / (0.5 - pause), -1.0
            else:
                f = 0.0
            inst.x = path[0] + (path[1] - path[0]) * f
            inst.dist = inst.x
        elif m == "croak":
            puff = max(0.0, math.sin(t * TAU * rate + ph)) ** 8
            if puff > 0.5 and not inst.extra.get("puffing"):
                self.sounds.append(cfg.get("sound") or d.t.get("sound"))     # one croak, one cue
            inst.extra["puffing"] = puff > 0.5
            inst.extra["throat"] = puff
            every = float(cfg.get("hop_every", 0))
            if every and d.spots:                      # hop to another pad now and then
                k = int((t + inst.seed * every) // every)
                if k != inst.extra.get("hop_k"):
                    if inst.extra.get("hop_k") is not None:
                        free = [sp for sp in d.spots if sp != inst.spot]
                        inst.extra["hop"] = (inst.spot, free[inst.r.randrange(len(free))] if free else inst.spot, t)
                    inst.extra["hop_k"] = k
        elif m == "breach":
            self._breach(inst, t, cfg)
        elif m == "dive":
            a = t - inst.state_t
            inst.dy = min(a, 12.0) * float(cfg.get("speed", 30.0))
            inst.extra["shrink"] = math.exp(-a / 10.0)
        if d.kind == "crowd" and m == "circle":
            around = d.t.get("around", inst.spot)
            rad = float(cfg.get("radius", 120))
            spread = float(d.t.get("spread", 1.0))      # 1 = round the whole circle; small = one school
            a = t * TAU * rate * (1.0 + (0.4 * inst.seed - 0.2) * spread) + ph * spread
            inst.x = around[0] + math.cos(a) * rad * (0.7 + 0.5 * inst.seed)
            inst.y = around[1] + math.sin(a) * rad * 0.25 + (inst.seed - 0.5) * 60
            inst.dx = inst.dy = 0.0
            inst.face = -1.0 if math.sin(a) > 0 else 1.0
        elif d.kind == "crowd":
            hop = inst.extra.get("hop")
            if hop and t - hop[2] < 0.7:
                f = (t - hop[2]) / 0.7
                (x0, y0), (x1, y1) = hop[0], hop[1]
                inst.x, inst.y = x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
                inst.dy = -math.sin(f * math.pi) * float(cfg.get("hop_height", 60))
                inst.face = 1.0 if x1 >= x0 else -1.0
            else:
                if hop:
                    inst.spot = hop[1]
                    inst.extra["hop"] = None
                inst.x, inst.y = inst.spot

    def _breach(self, inst, t, cfg):
        """Needs you, for swimmers: rise to the surface, then leap clear every `every` s."""
        world = inst.d.world
        surf = world.surface_y if world else 640.0
        a = t - inst.state_t
        rise = _smooth(a / 4.0)
        y_hold = surf + inst.d.height * 0.35
        inst.dy = (y_hold - inst.y) * rise
        every = float(cfg.get("every", 7.0))
        hop = float(cfg.get("leap", 1.6))
        if a > 4.0:
            u = (a - 4.0) % every
            if u < hop:
                f = u / hop
                inst.dy += -math.sin(f * math.pi) * inst.d.height * float(cfg.get("leap_height", 1.3))
                inst.rot = (0.5 - f) * 0.7 * inst.face
                k = int((a - 4.0) // every)
                for edge, ff in (("up", 0.08), ("down", 0.86)):
                    tag = (k, edge)
                    if f > ff and tag not in inst.extra.setdefault("sprayed", set()):
                        inst.extra["sprayed"].add(tag)
                        self.spray.append((inst.x, surf, t, 1.0))

    def _step_event(self, inst, t, dt, sig):
        v, d = inst.v, inst.d
        dur = float(v.get("seconds", 6.0))
        a = t - inst.born
        f = a / dur
        if f >= 1.0:
            inst.dead = True
            return
        inst.alpha = min(1.0, a / 0.35) * min(1.0, (dur - a) / 0.8)
        inst.light = 1.0
        inst.dx = inst.dy = inst.rot = 0.0
        r = inst.r
        m = v.get("motion", "rise")
        if inst.path is None:
            zones = v.get("from") or d.t.get("from") or [[d.at[0], d.at[1], d.at[0], d.at[1]]]
            z = zones[r.randrange(len(zones))]
            p0 = (z[0] + (z[2] - z[0]) * r.random(), z[1] + (z[3] - z[1]) * r.random())
            to = v.get("to") or d.t.get("to") or [[p0[0] + 400, p0[1] - 600]]
            if to and not isinstance(to[0], (list, tuple)):
                to = [to]
            p1 = tuple(to[r.randrange(len(to))])
            if m == "drift_up":                      # a bloom rises from the deep toward the surface
                p1 = (p0[0] + (r.random() - 0.5) * 160, float(v.get("rise_to", 700)) + r.random() * 60)
            if m == "reel":
                w = d.world
                p0 = w.line_end() if w else p0
                p1 = w.line_tip() if w else p1
                self.spray.append((p0[0], p0[1], t, 0.5))
            inst.path = (p0, p1)
            inst.face = 1.0 if p1[0] >= p0[0] else -1.0
        (x0, y0), (x1, y1) = inst.path
        if m == "rise":
            e = f * f * (3 - 2 * f) * 0.4 + f * 0.6
            inst.x = x0 + (x1 - x0) * e
            inst.y = y0 + (y1 - y0) * e - math.sin(f * math.pi) * 60
            inst.scale = 1.0 - 0.45 * f
            inst.frame = int(a * float(v.get("fps", 3.0)))
        elif m == "approach":
            e = f ** 1.8
            inst.x = x0 + (x1 - x0) * e
            inst.y = y0 + (y1 - y0) * e
            inst.scale = 0.35 + (float(v.get("grow", 5.0)) - 0.35) * e
            inst.extra["flap"] = math.sin(a * TAU * float(v.get("fps", 2.4))) * 0.08
            inst.frame = None
        elif m == "reel":
            w = d.world
            if w:
                (x1, y1) = w.line_tip()
            hold = 0.75
            e = _smooth(min(f / hold, 1.0))
            inst.x = x0 + (x1 - x0) * e
            inst.y = y0 + (y1 - y0) * e - math.sin(e * math.pi) * 90
            inst.rot = math.sin(a * TAU * float(v.get("wriggle", 5.0))) * 0.35 * (1.0 - 0.6 * e)
            inst.frame = 0
            if w:
                w.line_hook = (inst.x, inst.y - d.height * 0.5)
        elif m == "drift_up":
            e = f
            inst.x = x0 + math.sin(a * 0.6 + inst.seed * TAU) * 18 + (x1 - x0) * e
            inst.y = y0 + (y1 - y0) * e
            inst.frame = int(a * float(v.get("fps", 0.9)))
            inst.scale = 0.8 + 0.4 * inst.seed
        elif m == "dart":
            e = 1.0 - (1.0 - f) ** 3
            inst.x = x0 + (x1 - x0) * e
            inst.y = y0 + (y1 - y0) * e + math.sin(a * 9) * 3
            inst.extra["glint"] = math.exp(-((a - 0.4) ** 2) / 0.05) + 0.5 * math.exp(-((a - 1.3) ** 2) / 0.04)
            inst.frame = 0

    # ---- output
    @staticmethod
    def _blink(inst, t, cfg):
        """The lights' level for the state: a double flash then a calm 0.55 Hz blink for "needs
        you" (`signal`), a pulse, a flicker; for a rising agent, dark until its eyes clear the
        water, then a boot flicker."""
        blink = 1.0
        if inst.d.kind == "agents" and getattr(inst, "rise_t", None) is not None or "booted" in inst.extra:
            b = inst.extra.get("booted")
            if b is None:
                return 0.0                              # still under: the eyes are dark
            a = t - b
            if a < 0.9:                                 # the boot: an uneven flicker, settling
                on = (math.sin(a * 61.0) * math.sin(a * 23.0 + 1.3)) > (-0.3 + a * 0.5)
                return (1.3 if on else 0.15) * min(1.0, 0.3 + a)
            if a > 6.0:
                inst.extra.pop("booted", None)
        if cfg.get("signal"):
            a = t - inst.state_t
            if a > 1.2:
                blink = 0.55 + 0.45 * math.sin(TAU * 0.55 * (a - 1.2) - math.pi / 2)
            else:                                       # the double flash
                blink = 1.7 * (math.exp(-((a - 0.2) ** 2) / 0.005) + math.exp(-((a - 0.6) ** 2) / 0.005)) + 0.35
        if cfg.get("pulse"):
            blink *= 0.7 + 0.3 * math.sin(t * TAU * float(cfg["pulse"]))
        if cfg.get("flicker"):
            blink *= 0.5 + 0.5 * (math.sin(t * 23.0) * math.sin(t * 7.1) > -0.2)
        return blink

    def _emit(self, inst, t, sig, sprites, glows, wakes):
        d = inst.d
        v = inst.v or {}
        if inst.alpha <= 0.003:
            return
        cfg = d.state_cfg(inst.state) if inst.v is None else v
        sc = inst.slot_cfg
        st_sprite = (sc.get("states") or {}).get(inst.state, {}).get("sprite") if sc else None
        sprite = d.sprites.get(v.get("sprite")) if v.get("sprite") else None
        clip = getattr(inst, "clip", None)
        if clip is not None and clip.video.finished() and not getattr(inst, "clip_hold", False):
            inst.clip = clip = None                 # the clip is over: chain into the state's loop or sprite
        sprite = sprite or clip or (d.sprites.get(st_sprite) if st_sprite else None) \
            or (d.sprites.get(cfg.get("sprite")) if cfg.get("sprite") else None) \
            or (d.sprites.get(sc.get("sprite")) if sc.get("sprite") else None) or d.sprite
        h = float(cfg.get("height", d.height)) * inst.scale * inst.extra.get("shrink", 1.0)
        depth = float(v.get("depth", cfg.get("depth", d.depth)))
        # frame: the turn gesture, the state's strip, or the walk cycle
        front = d.frames.get("front")
        if inst.turn > 0.5 and front:
            fi = front[0]
            sx = (inst.turn - 0.5) * 2.0
        else:
            sx = inst.face * (1.0 - 2.0 * min(inst.turn, 0.5)) if inst.turn > 0.02 else inst.face
            if inst.frame is not None:
                fl = d.frame_list(v.get("frames_key", "fly") if inst.v is not None else inst.state, d.frame_list("walk"))
                fi = fl[inst.frame % len(fl)] if inst.v is not None or d.kind == "traffic" else inst.frame
            elif inst.state in d.frames:
                fl = d.frames[inst.state]
                fps = float(cfg.get("fps", 0.5))
                fi = fl[int(t * fps + inst.seed * 7) % len(fl)]
            elif "walk" in d.frames and cfg.get("motion") == "wander":
                fl = d.frames["walk"]
                stride = max(d.height * 0.12, 4.0)
                fi = fl[int(inst.dist / stride) % len(fl)]
            elif "frame" in cfg:
                fi = int(cfg["frame"])
            else:
                fi = 0
            if inst.v is not None and v.get("motion") == "approach" and front:
                fi, sx = front[0], 1.0
        if inst.v is not None and "frame" in v:
            fi = int(v["frame"])
        u0, v0, u1, v1, asp = sprite.frame(fi)
        w = h * asp
        patch = sc.get("patch") or d.t.get("patch")
        if isinstance(patch, str):                  # a clip's name: its rect from live/clips/manifest.toml
            m = (d.world.manifest.get(patch) or d.world.manifest.get("clips", {}).get(patch) or {}) if d.world else {}
            patch = m.get("rect") if isinstance(m, dict) else m
        if patch:                                   # a patch of the scene, placed by its rect (one-shot clips)
            px0, py0, pw, ph = (float(v_) for v_ in patch)
            inst.x, inst.y, w, h, sx = px0 + pw / 2, py0 + ph, pw, ph, 1.0
            inst.dx = inst.dy = inst.sink = 0.0
        sy = 1.0 + inst.extra.get("flap", 0.0) + 0.12 * inst.extra.get("throat", 0.0)
        wade = float(cfg.get("wade", d.wade)) if (d.wade or "wade" in cfg) and not patch else 0.0
        x = inst.x + inst.dx
        cut = inst.y + inst.dy * 0.0 if wade > 0 else -1.0
        base = inst.y + inst.dy + (wade + inst.sink) * h
        if wade <= 0:
            base = inst.y + inst.dy + inst.sink * h
        tint = cfg.get("tint") or v.get("tint")
        bright = float(cfg.get("bright", v.get("bright", 1.0)))
        par = d.parallax
        spr = {"x": x, "y": base, "w": w * sx, "h": h * sy, "uv": (u0, v0, u1, v1), "rot": inst.rot, "video": sprite.video,
               "alpha": inst.alpha, "cut": cut, "tint": tint, "bright": bright, "fog": d.fog,
               "reflect": d.reflect if wade > 0 else 0.0, "par": par,
               "add": (v.get("blend") or cfg.get("blend") or d.t.get("blend")) == "add"}   # glow creatures on black
        sprites.append((depth, spr))
        inst.placed = (x, base, w * sx, h * sy, inst.rot, fi)
        # an emissive mask (eye-lamps painted as light): drawn additively in the light's colour
        em = sc.get("emissive") or d.t.get("emissive")
        if em and d.sprites.get(em):
            es = d.sprites[em]
            col = (d.error_color if inst.error else d.signal_color) if cfg.get("signal") else \
                tuple(cfg.get("color") or d.t.get("light_color", (0.35, 0.95, 1.0)))
            lit_e = inst.light * inst.alpha * self._blink(inst, t, cfg) * (1.0 + 1.8 * inst.flare)
            if lit_e > 0.01:
                e_uv = es.frame(fi)
                sprites.append((depth + 0.005, dict(spr, uv=e_uv[:4], video=es.video, tint=(col[0], col[1], col[2], 1.0),
                                                     bright=lit_e * float(d.t.get("emissive_gain", 1.4)), add=True, emissive=True,
                                                     reflect=0.0)))
        # a diver leaves a fading trail of light above it
        if cfg.get("motion") == "dive" and inst.v is None:
            a = t - inst.state_t
            c = tuple(cfg.get("trail", (0.3, 0.9, 1.0)))
            for k in range(1, 9):
                ty = base - h * 0.5 - k * 34.0 * min(a, 12.0) / 12.0 * 3.0
                inten = 0.5 * math.exp(-k / 3.0) * math.exp(-a / 9.0) * inst.alpha
                if inten > 0.01:
                    glows.append((depth + 0.01, (x + math.sin(k * 1.7 + a) * 6, ty, 5.0, 5.0, c[0], c[1], c[2], inten,
                                                 1.0 if d.fog else 0.0)))
        # wakes: wading things that move ruffle the water
        if wade > 0 and inst.alpha > 0.2:
            moving = 1.0 if (cfg.get("motion") == "wander" and inst.target is not None
                             and abs(inst.target - inst.x) >= 2) else 0.25
            wakes.append((x, inst.y, moving * inst.alpha * (1.0 - min(inst.sink, 1.0) * 0.6)))
        # lights
        col_sig = None
        if cfg.get("signal"):
            col_sig = d.error_color if inst.error else d.signal_color
        blink = self._blink(inst, t, cfg)
        lit = inst.light * inst.alpha * blink * (1.0 + 1.8 * inst.flare) + inst.extra.get("glint", 0.0)
        lights = cfg.get("lights") or v.get("lights") or ([v["light"]] if v.get("light") else None) \
            or sc.get("lights") or d.lights
        if lit > 0.01 and lights:
            ca, sa = math.cos(inst.rot), math.sin(inst.rot)
            for L in lights:
                if inst.turn > 0.5 and front:
                    if "front_at" not in L and any("front_at" in M for M in lights):
                        continue                    # a side light the front view doesn't show
                    lu, lv = L.get("front_at", L["at"])
                    lu = 0.5 + (lu - 0.5) * abs(sx)
                else:
                    lu, lv = L["at"]
                    if sx < 0:
                        lu = 1.0 - lu
                    lu = 0.5 + (lu - 0.5) * abs(sx) if abs(sx) < 1 else lu
                lx = (lu - 0.5) * abs(w)
                ly = -(1.0 - lv) * h * sy
                gx = x + lx * ca - ly * sa
                gy = base + lx * sa + ly * ca
                if wade > 0 and gy > cut + 1:
                    continue
                c = col_sig or tuple(cfg.get("color") or L.get("color", (1, 1, 1)))
                rad = float(L.get("radius", 6)) * (h / max(d.height, 1)) ** 0.5
                if col_sig:
                    rad *= float(d.t.get("signal_radius", 1.8))
                glows.append((depth + 0.01, (gx, gy, rad, rad, c[0], c[1], c[2], lit * float(L.get("gain", 1.0)),
                                             1.0 if d.fog else 0.0)))
                spill = float(L.get("spill", d.t.get("spill", 0.0)))
                if spill > 0:                       # light spilling on the water and the pads around it
                    glows.append((depth + 0.01, (gx, gy + rad * 3, rad * 9, rad * 4, c[0], c[1], c[2], lit * spill, 0.0)))
                if wade > 0 and d.reflect > 0:      # the lamp's streak in the water
                    glows.append((depth + 0.01, (gx, 2 * cut - gy, rad * 1.3, rad * 3.2, c[0], c[1], c[2],
                                                 lit * d.reflect * 0.45, 0.0)))
