"""VECTOR's console: the construct on its emitter, an exhibit table beside it (a live
model hologram of whatever it is talking about), and the conversation as holographic
text. Scene logic only; the window and the brain live elsewhere."""
import math
import time

import numpy as np

from .. import gl
from ..render import Holo, approach, col, ease, lin
from ..stage import Stage
from .avatar import Avatar
from .text import plain

STATE_WORD = {"idle": "AT HIS POST", "listening": "LISTENING", "thinking": "CONSULTING", "speaking": "SPEAKING",
              "error": "ANOMALY LOGGED", "sleep": "HUMMING"}


class Msg:
    __slots__ = ("role", "text", "shown", "t", "done")

    def __init__(self, role, text="", done=True):
        self.role, self.text, self.t, self.done = role, text, time.monotonic(), done
        self.shown = float(len(text)) if role != "vector" else 0.0


class VectorScene:
    def __init__(self, live, scale=1.0):
        self.live = live
        self.scale = scale
        self.avatar = Avatar()
        self.holo = None
        self.msgs = []
        self.stage = None          # current exhibit
        self.ex_parts = None
        self.ex_until = 0.0
        self.ex_amt = 0.0
        self.last_t = time.monotonic()
        self.fade = 0.0
        self.fade_to = 1.0
        self.subtitle = ""
        self.voice = "VOICE OFF"
        self.route = "qwen3.8-flash-next · homelab LiteLLM"
        self.audio_level = None    # set by the voice player while it speaks
        self.typing = False
        self.mic_live = False
        self.left_w = 540

    # ------------------------------------------------------------------ conversation
    def set_state(self, s):
        self.avatar.set_state(s)

    # ------------------------------------------------------------------ voice colour and mood
    def _voices(self):
        if getattr(self, "_vcfg", None) is None:
            import json
            import os
            try:
                with open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "voice.json")) as f:
                    self._vcfg = json.load(f).get("voices", {})
            except (OSError, ValueError):
                self._vcfg = {}
        return self._vcfg

    def set_voice(self, role, switch=True):
        """The voice now speaking: its colour crossfades in (with a tremor if it changed)."""
        col = self._voices().get(role, {}).get("colour", "#39ff14")
        changed = role != getattr(self, "voice_role", "main")
        self.voice_role = role
        self.avatar.set_voice_colour(col, switch and changed)

    def set_mood(self, mood):
        """calm | excited | concerned | alarmed, from the reply's marker or the facts."""
        self.mood_at = time.monotonic()
        order = {"calm": 0, "excited": 1, "concerned": 2, "alarmed": 3}
        cur = self.mood_name()
        # the facts win over a cheerful marker: never step down from alarmed/concerned mid-reply
        if mood in ("excited", "calm") and cur in ("concerned", "alarmed") and time.monotonic() - getattr(self, "fact_at", -99) < 20:
            return
        if mood in ("concerned", "alarmed") and order.get(mood, 0) < order.get(cur, 0):
            return
        if mood == "calm":
            self.avatar.calm_down()
        else:
            self.avatar.set_mood(mood)

    def set_mood_from_facts(self, mood):
        self.fact_at = time.monotonic()
        self.set_mood(mood)

    def mood_name(self):
        return self.avatar.mood_name()

    def memory_flash(self, what, n=1):
        """A brief glyph when VECTOR recalls (cyan-white), files (phosphor) or forgets (dim) something."""
        self.mem_flash = (what, n, time.monotonic())
        self.avatar.activity = 1.0
        self.avatar.glitch = max(self.avatar.glitch, 0.35)

    def add_user(self, text):
        self.msgs.append(Msg("you", text))
        self._trim()

    def add_tool(self, text):
        self.end_reply()                 # whatever it said before the lookup is finished
        self.msgs.append(Msg("tool", text))
        self.avatar.activity = 1.0
        self._trim()

    def begin_reply(self):
        self.msgs.append(Msg("vector", "", done=False))

    def feed(self, delta):
        if not self.msgs or self.msgs[-1].role != "vector" or self.msgs[-1].done:
            self.begin_reply()
        self.msgs[-1].text += delta

    def end_reply(self):
        for m in self.msgs:
            if m.role == "vector":
                m.done = True

    def reroute(self, model, why):
        """A model didn't answer in time; the same turn goes to the next one. Say so."""
        self.end_reply()
        self.msgs.append(Msg("route", f"rerouting to {model} ({why})"))
        self.avatar.glance(-0.5, -0.1, 0.8)
        self._trim()

    def catch_up(self):
        """Opening after a minimize: replies that arrived while hidden show whole."""
        for m in self.msgs:
            if m.role == "vector" and m.done:
                m.shown = float(len(m.text))

    def streaming(self):
        return any(m.role == "vector" and not m.done and m.text for m in self.msgs[-1:])

    def note(self, text):
        self.msgs.append(Msg("sys", text))
        self._trim()

    def _trim(self):
        self.msgs = self.msgs[-40:]

    def revealing(self):
        return any(m.role == "vector" and m.shown < len(m.text) for m in self.msgs)

    def exhibit(self, name, parts=None, hold=45.0):
        """Put a live model hologram on the side table, calling out `parts` (ids)."""
        if not self.stage or self.stage.name != name:
            if self.stage:
                self.stage.release()
            self.stage = Stage(name, self.live)
            self.stage.spin = 0.25
            self.stage.explode_to = 0.55
            self.ex_amt = 0.0
        ids = [p["id"] for p in self.stage.parts]
        self.ex_parts = [ids.index(p) for p in (parts or []) if p in ids][:3] or None
        self.stage.scan()
        self.ex_until = time.monotonic() + hold
        self.avatar.glance(0.75, -0.05, 1.4)

    def busy(self):
        a = self.avatar
        return (a.state in ("thinking", "speaking", "listening", "error") or self.revealing() or
                abs(self.fade - self.fade_to) > 0.01 or a.state_t < 1.5 or
                (self.stage is not None and abs(self.ex_amt - (1.0 if time.monotonic() < self.ex_until else 0.0)) > 0.01))

    # ------------------------------------------------------------------ animation
    def advance(self, dt):
        a = self.avatar
        # typewriter: VECTOR's words appear at a speaking pace; the iris pulses with them
        lvl = 0.0
        for m in self.msgs:
            if m.role == "vector" and m.shown < len(m.text):
                backlog = len(m.text) - m.shown
                m.shown = min(len(m.text), m.shown + dt * (62 + backlog * 1.5))
                ch = m.text[int(m.shown) - 1:int(m.shown)].lower() if m.shown >= 1 else ""
                lvl = 0.55 + 0.35 * math.sin(time.monotonic() * 17) * math.sin(time.monotonic() * 5.3) + (0.15 if ch in "aeiou" else 0)
                a.activity = 1.0
                break
        if self.audio_level is not None:
            lvl = self.audio_level
        a.level = approach(a.level, lvl, dt, 18.0)
        if a.state == "speaking" and not self.revealing() and self.audio_level is None and a.state_t > 0.5:
            a.set_state("idle")
        a.update(dt)
        self.fade = approach(self.fade, self.fade_to, dt, 6.0)
        on = self.stage is not None and time.monotonic() < self.ex_until
        self.ex_amt = approach(self.ex_amt, 1.0 if on else 0.0, dt, 3.5)
        # moods settle back to calm a few seconds after the reply ends (then fade over ~15 s)
        if a.state not in ("speaking", "thinking") and not self.revealing() and \
                time.monotonic() - getattr(self, "mood_at", 0) > 4 and any(a.mood_to.values()):
            a.calm_down()
        if self.stage:
            self.stage.update(dt)
            self.stage.fade = self.ex_amt
            if not on and self.ex_amt < 0.01:
                self.stage.release()
                self.stage = None

    # ------------------------------------------------------------------ render
    def render(self, fbo, w, h):
        if self.holo is None:
            self.holo = Holo(self.scale)
        t = time.monotonic()
        dt = min(0.1, t - self.last_t)
        self.last_t = t
        self.advance(dt)
        H = self.holo
        sc = self.scale
        H.begin(w, h, t)
        lw = self.left_w * sc
        ex = ease(self.ex_amt)
        # camera frames the construct alone, or the construct plus the exhibit table
        tgt = np.array([0.3 * ex, 0.42 - 0.06 * ex, 0], np.float32)
        d = 1.75 + 1.05 * ex
        pitch = 0.13
        eye = tgt + d * np.array([0, math.sin(pitch), math.cos(pitch)], np.float32)
        band = 150 * sc * ex if self.ex_parts else 0.0     # room for the exhibit's readouts
        H.camera(eye, tgt, 32.0, viewport=(0, 40 * sc * ex, lw, h - band - 40 * sc * ex))
        st = self.avatar.state
        table_col = {"thinking": "amber", "error": "danger"}.get(st) or tuple(self.avatar.colour()[0])
        base = gl.rot_y(-0.18 * ex)
        H.draw_table(base @ gl.rot_y(-t * 0.08), radius=0.3, cone_top=0.26, cone_h=0.55,
                     power=(0.75 + 0.35 * self.avatar.level) * self.fade, colour=table_col)
        self.avatar.draw(H, base, self.fade)
        if self.stage and self.ex_amt > 0.01:
            eb = gl.translate(0.66, 0, -0.1) @ gl.rot_y(-0.3)
            self.stage.draw(H, t, base=eb, size=0.5, table_power=0.8, gain=0.5, width=1.1)
            which = self.ex_parts if self.ex_parts is not None else []
            self.stage.draw_callouts(H, (14 * sc, h - 150 * sc, lw - 28 * sc, 122 * sc), which=which,
                                     size=int(12 * sc), max_lines=3, reveal=self.ex_amt, row=True)
        self._text(H, w, h, lw)
        # nearly clear behind the hologram (under the compositor's blur threshold) so the
        # window you click through to stays visible; the transcript gets its own backing
        H.end(fbo, bg=(0.0, 0.02, 0.0, 0.12), bloom=1.2, fade=self.fade)

    def _text(self, H, w, h, lw):
        sc = self.scale
        f = self.fade
        ph = col("phosphor", 1, f)
        H.brackets(8 * sc, 8 * sc, w - 16 * sc, h - 16 * sc, (ph[0], ph[1], ph[2], 0.75 * f), arm=18 * sc, width=1.5)
        x0 = lw + 14 * sc
        tw, th = H.label("VECTOR", 26 * sc, 22 * sc, ph, int(24 * sc), "bold", spacing=7)
        st = self.avatar.state
        sc_col = {"thinking": "amber", "error": "danger", "listening": "white", "sleep": "dim"}.get(st, "soft")
        word = STATE_WORD.get(st, st.upper()) + (f" · {self.subtitle}" if self.subtitle else "")
        H.label(word, 26 * sc + tw + 16 * sc, 22 * sc + th - 18 * sc, col(sc_col, 1, f), int(13 * sc), "bold", spacing=2.5)
        mf = getattr(self, "mem_flash", None)
        if mf and time.monotonic() - mf[2] < 1.8:
            # memory: a small ring of dots closing around the word, then fading
            age = time.monotonic() - mf[2]
            a = (1.0 if age < 1.2 else 1.0 - (age - 1.2) / 0.6) * f
            word = {"recall": f"◈ RECALLED {mf[1]}", "store": "◈ FILED", "forget": "◈ FORGOTTEN"}.get(mf[0], "◈ MEMORY")
            c = {"recall": "white", "store": "phosphor", "forget": "static"}.get(mf[0], "soft")
            cx, cy = lw * 0.5, h * 0.17
            for k in range(12):
                ang = k * math.pi / 6 + age * 2.0
                r = 46 * sc * (1.0 - 0.25 * min(1.0, age * 2))
                H.label("·", cx + r * math.cos(ang), cy + 0.45 * r * math.sin(ang), col(c, 1, a * (0.4 + 0.6 * (k % 3 == 0))), int(14 * sc), anchor="cm")
            H.label(word, cx, cy, col(c, 1, a), int(12 * sc), "bold", anchor="cm", spacing=2.5)
        # the line: VECTOR answers from his post at the SpacePort arrivals pad, over the relays
        pulse = 0.55 + 0.25 * math.sin(time.monotonic() * 1.3)
        H.label("ARRIVALS · LINE OPEN", 26 * sc, 22 * sc + th + 4 * sc, col("dim", 1.5, pulse * f), int(10 * sc), "bold", spacing=3)
        if st == "idle" and self.avatar.state_t > 6:
            # he hums between arrivals: a few drifting notes beside the construct (visual only)
            t = time.monotonic()
            for k in range(3):
                ph_ = ((t * 0.35 + k / 3) % 1.0)
                if ph_ < 0.75:
                    a = math.sin(ph_ / 0.75 * math.pi) * 0.55 * f
                    H.label("♪", lw * 0.62 + 24 * sc * k + 10 * sc * math.sin(t + k), h * 0.42 - ph_ * 90 * sc,
                            col("soft", 1, a), int((13 + 3 * k) * sc))
        H.label(self.route, w - 28 * sc, 26 * sc, col("static", 1, 0.9 * f), int(12 * sc), anchor="rt")
        if self.mic_live:   # the microphone is open only while SUPER+V is held, and it says so
            blink = 0.65 + 0.35 * math.sin(time.monotonic() * 6)
            H.label("● MIC LIVE · RELEASE SUPER+V TO SEND", w - 28 * sc, 44 * sc, col("danger", 1, blink * f), int(12 * sc), "bold", anchor="rt", spacing=1.5)
        else:
            H.label(self.voice, w - 28 * sc, 44 * sc, col("dim", 1.3, 0.9 * f), int(11 * sc), "bold", anchor="rt", spacing=1.5)
        # divider between the table and the transcript
        H.line2d(lw, 70 * sc, lw, h - 30 * sc, col("guard", 1.6, 0.9 * f), 1.0)
        # transcript, newest at the bottom, above the input line
        width = w - x0 - 32 * sc
        y = h - 78 * sc
        top = 72 * sc
        rows = []
        for m in reversed(self.msgs):
            if m.role == "vector":
                text = plain(m.text[:int(m.shown)], streaming=True).strip()
                if not text:
                    continue
                if m.shown < len(m.text) or not m.done:
                    text += "▌"
                c, size, weight, ind = col("phosphor", 1, f), 15, "normal", 0
            elif m.role == "you":
                text, c, size, weight, ind = "› " + m.text, col("white", 1, 0.95 * f), 14, "medium", 0
            elif m.role == "tool":
                text, c, size, weight, ind = "⟐ " + m.text, col("dim", 1.5, 0.95 * f), 12, "normal", 14
            elif m.role == "route":
                text, c, size, weight, ind = "↻ " + m.text, col("amber", 0.9, 0.95 * f), 12, "normal", 14
            else:
                text, c, size, weight, ind = m.text, col("amber", 1, f), 13, "normal", 0
            tw_, th_ = H.measure(text, int(size * sc), weight, width=(width - ind * sc) / sc)
            y -= th_ + (10 if m.role != "tool" else 4) * sc
            if y < top:
                break
            rows.append((text, x0 + ind * sc, y, c, int(size * sc), weight, (width - ind * sc) / sc))
        # a dark backing under the transcript and the entry, only as tall as the text
        y_top = min([r[2] for r in rows] + [h - 78 * sc]) - 12 * sc
        H.rect(x0 - 14 * sc, y_top, w - x0 - 4 * sc, h - y_top - 10 * sc, (0.0, 0.035, 0.0, 0.8 * f))
        H.rect(x0 - 14 * sc, 12 * sc, w - x0 - 4 * sc, 84 * sc, (0.0, 0.035, 0.0, 0.62 * f))   # header backing
        H.rect(12 * sc, 12 * sc, 330 * sc, 52 * sc, (0.0, 0.035, 0.0, 0.5 * f))
        for text, x, yy, c, size, weight, wd in rows:
            H.label(text, x, yy, c, size, weight, width=wd)
        hint = ("Enter sends · Esc hands the keyboard back · Shift+Esc minimizes" if self.typing else
                "click the box to type · clicks elsewhere go to your windows · SUPER+E minimizes")
        H.label(hint, w - 28 * sc, h - 14 * sc, col("static", 1, 0.8 * f), int(11 * sc), anchor="rb")

    def demo_transcript(self):
        """For offscreen screenshots only."""
        self.add_user("how's the lab doing?")
        self.add_tool("lab status · 6 of 6 nodes, 34 of 34 services")
        self.feed("Right, so, good news first, which is also the only news: all six nodes are up and every one of "
                  "the thirty-four services is answering. The beam's lit. Nine alerts firing, but they're the usual "
                  "chatter, I checked twice. Three times. It's fine.")
        self.end_reply()
        for m in self.msgs:
            m.shown = len(m.text)
