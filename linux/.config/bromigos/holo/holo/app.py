"""bromigos-holo daemon: one GTK process hosting PILOT's console and the hologram gallery,
both on the shared renderer. Controlled over a unix socket by bin/bromigos-holo.

Windows are layer-shell surfaces on the overlay layer, shown only when summoned.
Hidden windows render nothing; the idle daemon is a sleeping GTK main loop.

PILOT never blocks the desktop: its window takes input only on the chat entry and its
minimize button (an input region; clicks anywhere else go to the window behind it),
and it holds keyboard focus on demand (when SUPER+E opens it or the entry is clicked;
Esc or a click elsewhere hands it back). Minimized, PILOT keeps working: a running
turn finishes, the reply is spoken (voice on) and queued for the next open, and the
bar module (waybar custom/pilot, fed by $XDG_RUNTIME_DIR/bromigos-pilot.json) shows its
state and unread count."""
import json
import os
import signal
import socket
import sys
import threading
import time

os.environ.setdefault("PYOPENGL_PLATFORM", "egl")

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gdk, GLib, Gtk, GtkLayerShell  # noqa: E402
from OpenGL import GL  # noqa: E402

from .live import Live  # noqa: E402

RUNTIME = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
SOCK = os.path.join(RUNTIME, "bromigos-holo.sock")
PILOT_STATE = os.path.join(RUNTIME, "bromigos-pilot.json")
WAYBAR_SIGNAL = 9           # waybar custom/pilot "signal": 9 -> refresh on SIGRTMIN+9
MONITOR = os.environ.get("BROMIGOS_HOLO_MONITOR", "DP-1")
CSS = b"""
#pilot-entry {
  background-color: rgba(0, 19, 0, 0.82);
  color: #c4f5bb;
  caret-color: #39ff14;
  border: 1px solid rgba(21, 155, 9, 0.9);
  border-radius: 0;
  box-shadow: none;
  font-family: "Geist Mono";
  font-size: 14px;
  padding: 8px 12px;
}
#pilot-entry:focus { border-color: #39ff14; }
#pilot-entry selection { background-color: #159b09; color: #000500; }
#pilot-min {
  background-image: none;
  background-color: rgba(0, 19, 0, 0.82);
  color: #9cff8a;
  border: 1px solid rgba(21, 155, 9, 0.9);
  border-radius: 0;
  box-shadow: none;
  font-family: "Geist Mono";
  font-size: 12px;
  font-weight: 700;
  padding: 2px 10px;
  min-height: 0;
}
#pilot-min:hover { color: #000500; background-color: #39ff14; border-color: #39ff14; }
"""


def log(*a):
    print(time.strftime("%H:%M:%S"), "bromigos-holo:", *a, flush=True)


def monitor_for(name):
    display = Gdk.Display.get_default()
    mons = [display.get_monitor(i) for i in range(display.get_n_monitors())]
    for m in mons:
        if (m.get_model() or "") == name or getattr(m, "get_connector", lambda: None)() == name:
            return m
    return mons[0] if mons else None


class HoloWindow:
    """A layer-shell window with one GL area; renders only while shown."""
    ALL = []                              # every window, for hotplug recovery

    def __init__(self, ns, scene, size, anchors, margins, keyboard_exclusive=True, overlay_children=(),
                 input_widgets=None):
        self.scene = scene
        self.input_widgets = input_widgets      # None: the whole window takes input
        self.anchors = anchors
        self.win = Gtk.Window()
        GtkLayerShell.init_for_window(self.win)
        GtkLayerShell.set_layer(self.win, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_namespace(self.win, ns)
        mon = monitor_for(MONITOR)
        if mon:
            GtkLayerShell.set_monitor(self.win, mon)
        for ch, edge in (("t", GtkLayerShell.Edge.TOP), ("b", GtkLayerShell.Edge.BOTTOM),
                         ("l", GtkLayerShell.Edge.LEFT), ("r", GtkLayerShell.Edge.RIGHT)):
            GtkLayerShell.set_anchor(self.win, edge, ch in anchors)
            GtkLayerShell.set_margin(self.win, edge, margins.get(ch, 0))
        GtkLayerShell.set_exclusive_zone(self.win, -1)
        self.kb_exclusive = keyboard_exclusive
        vis = self.win.get_screen().get_rgba_visual()
        if vis:
            self.win.set_visual(vis)
        self.win.set_app_paintable(True)
        self.win.set_default_size(*size)
        self.win.set_size_request(*size)
        self.area = Gtk.GLArea()
        self.area.set_required_version(3, 3)
        self.area.set_has_alpha(True)
        self.area.set_auto_render(False)
        self.area.connect("render", self._render)
        self.area.connect("unrealize", self._unrealize)
        self.area.add_events(Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.BUTTON_PRESS_MASK |
                             Gdk.EventMask.BUTTON_RELEASE_MASK | Gdk.EventMask.SCROLL_MASK |
                             Gdk.EventMask.SMOOTH_SCROLL_MASK)
        self.ov = Gtk.Overlay()
        self.ov.add(self.area)
        for child in overlay_children:
            self.ov.add_overlay(child)
        self.win.add(self.ov)
        if input_widgets is not None:
            self.win.connect("size-allocate", lambda *a: GLib.idle_add(self.update_input_region))
            self.win.connect("map", lambda *a: GLib.idle_add(self.update_input_region))
        self.visible = False
        self.timer = None
        self.fps = 0
        self.failed = False
        self.frames = 0
        self.frame_ms = 0.0
        self.lost = False                 # was shown when its output went away
        self.win.connect("delete-event", self._surface_closed)
        HoloWindow.ALL.append(self)

    def update_input_region(self):
        """Only the listed widgets take pointer input; everything else passes through."""
        gw = self.win.get_window()
        if gw is None or self.input_widgets is None:
            return False
        import cairo
        rects = []
        for w in self.input_widgets:
            if not w.get_visible() or not w.get_realized():
                continue
            a = w.get_allocation()
            xy = w.translate_coordinates(self.win, 0, 0)
            if xy:
                rects.append(cairo.RectangleInt(int(xy[0]) - 2, int(xy[1]) - 2, a.width + 4, a.height + 4))
        gw.input_shape_combine_region(cairo.Region(rects), 0, 0)
        self.input_rects = [(r.x, r.y, r.width, r.height) for r in rects]
        return False

    input_rects = ()

    def keyboard(self, mode):
        GtkLayerShell.set_keyboard_mode(self.win, {
            "exclusive": GtkLayerShell.KeyboardMode.EXCLUSIVE, "on_demand": GtkLayerShell.KeyboardMode.ON_DEMAND,
            "none": GtkLayerShell.KeyboardMode.NONE}[mode])

    def _surface_closed(self, *_):
        """Output removed (monitor powered off): gtk-layer-shell turns the compositor's
        'closed' into a window close. Keep the window; map it again when the output is back."""
        self.lost = self.lost or self.visible
        self.hide()
        log("surface closed (output gone?)", "will reopen" if self.lost else "")
        return True

    @classmethod
    def output_lost(cls):
        """An output went away: its layer surfaces are gone even if GTK still thinks the
        window is shown (gtk-layer-shell 0.10 does not always close it)."""
        for w in cls.ALL:
            if w.visible:
                w.lost = True

    @classmethod
    def reattach(cls):
        for w in cls.ALL:
            if w.lost:
                w.lost = False
                w.hide()                          # drop the dead surface, map a fresh one
                w.show(focus=False)
                log("surface reopened after the output came back")
        return False

    def show(self, focus=True):
        """Map the window. An on-demand layer takes the keyboard when it maps (Hyprland),
        so focus=False maps it with no keyboard and allows on-demand just after."""
        if not self.visible:
            mon = monitor_for(MONITOR)            # the output may be a new object after a hotplug
            if mon:
                GtkLayerShell.set_monitor(self.win, mon)
            self.keyboard("exclusive" if self.kb_exclusive else ("on_demand" if focus else "none"))
            self.win.show_all()
            self.visible = True
            if not focus and not self.kb_exclusive:
                GLib.timeout_add(150, lambda: (self.visible and self.keyboard("on_demand"), False)[1])
        self.set_fps(60)

    def hide(self):
        self.set_fps(0)
        self.keyboard("none")
        self.win.hide()
        self.visible = False

    def set_fps(self, fps):
        if fps == self.fps and (self.timer or not fps):
            return
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = None
        self.fps = fps
        if fps:
            self.timer = GLib.timeout_add(max(8, int(1000 / fps)), self._tick)

    def _tick(self):
        self.area.queue_render()
        want = 60 if self.scene.busy() else 30
        if want != self.fps:
            self.set_fps(want)
            return False
        return True

    def _unrealize(self, area):
        self.scene.holo = None
        if hasattr(self.scene, "stages"):
            for s in self.scene.stages.values():
                s.gpu = None
        if hasattr(self.scene, "avatar"):
            self.scene.avatar.gpu = None
        if getattr(self.scene, "stage", None) is not None and not hasattr(self.scene, "stages"):
            self.scene.stage.gpu = None

    def _render(self, area, ctx):
        if self.failed:
            GL.glClearColor(0, 0, 0, 0)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT)
            return True
        sf = area.get_scale_factor()
        w, h = area.get_allocated_width() * sf, area.get_allocated_height() * sf
        if w < 16 or h < 16:
            return True
        fbo = int(GL.glGetIntegerv(GL.GL_DRAW_FRAMEBUFFER_BINDING))
        t0 = time.perf_counter()
        try:
            self.scene.render(fbo, w, h)
        except Exception:
            import traceback
            traceback.print_exc()
            self.failed = True
        self.frames += 1
        self.frame_ms = 0.9 * self.frame_ms + 0.1 * (time.perf_counter() - t0) * 1000
        if self.snap_path:
            self._snap(fbo, w, h)
        return True

    snap_path = None

    def _snap(self, fbo, w, h):
        """Save what this window just rendered (its own framebuffer), over the den wallpaper."""
        import numpy as np
        from PIL import Image
        path, self.snap_path = self.snap_path, None
        GL.glBindFramebuffer(GL.GL_READ_FRAMEBUFFER, fbo)
        px = GL.glReadPixels(0, 0, w, h, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
        a = np.frombuffer(px, np.uint8).reshape(h, w, 4)[::-1].astype(np.float32)
        bgp = os.path.expanduser("~/.config/wallpaper/bromigos-den-2560x1440.jpg")
        bg = np.asarray(Image.open(bgp).convert("RGB"), np.float32) if os.path.exists(bgp) else np.zeros((1440, 2560, 3), np.float32)
        H_, W_ = bg.shape[:2]
        x, y = self.snap_at(W_, H_, w, h)
        reg = bg[y:y + h, x:x + w]
        reg[:] = a[:reg.shape[0], :reg.shape[1], :3] + reg * (1 - a[:reg.shape[0], :reg.shape[1], 3:4] / 255)
        Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8)).save(path)
        log("snap", path)

    def snap_at(self, W, H, w, h):
        return (W - w - 24, H - h - 24) if self.anchors == "br" else ((W - w) // 2, (H - h) // 2)


class App:
    def __init__(self):
        prov = Gtk.CssProvider()
        prov.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        self.live = Live()
        disp = Gdk.Display.get_default()           # hotplug: reopen windows that were shown
        disp.connect("monitor-removed", lambda *_: HoloWindow.output_lost())
        disp.connect("monitor-added", lambda *_: [GLib.timeout_add(d, HoloWindow.reattach) for d in (1500, 4000)])
        self.pilot = None
        self.gallery = None
        self.brain = None
        self.voice = None
        self.last_activity = time.monotonic()
        self.unread = 0
        self.hidden_since = None
        self.focused = False
        self._state_sig = None
        self._serve()
        GLib.timeout_add_seconds(5, self._idle_check)
        GLib.timeout_add(400, self._publish_state)

    # ------------------------------------------------------------------ PILOT
    def ensure_pilot(self):
        if self.pilot:
            return
        from .pilot.brain import Brain
        from .pilot.scene import PilotScene
        self.pscene = PilotScene(self.live)
        self.entry = Gtk.Entry(name="pilot-entry")
        self.entry.set_placeholder_text("ask PILOT…")
        self.entry.set_halign(Gtk.Align.END)
        self.entry.set_valign(Gtk.Align.END)
        self.entry.set_margin_end(30)
        self.entry.set_margin_bottom(34)
        self.entry.set_size_request(1180 - self.pscene.left_w - 14 - 30, -1)
        self.entry.connect("activate", self._on_entry)
        self.entry.set_tooltip_text("Type to PILOT; Enter sends. Esc hands the keyboard back; click here to type again.")
        self.minbtn = Gtk.Button(label="— MINIMIZE", name="pilot-min")
        self.minbtn.set_halign(Gtk.Align.END)
        self.minbtn.set_valign(Gtk.Align.START)
        self.minbtn.set_margin_end(30)
        self.minbtn.set_margin_top(64)
        self.minbtn.set_can_focus(False)
        self.minbtn.set_tooltip_text("Minimize PILOT. It keeps working: replies are spoken and wait here for you. "
                                     "SUPER+E brings it back; the bar's PILOT pip shows what it is doing.")
        self.minbtn.connect("clicked", lambda b: self.hide_pilot())
        self.pilot = HoloWindow("bromigos-pilot", self.pscene, (1180, 640), "br", {"r": 24, "b": 24},
                                keyboard_exclusive=False, overlay_children=[self.entry, self.minbtn],
                                input_widgets=[self.entry, self.minbtn])
        self.pilot.win.connect("key-press-event", self._pilot_key)
        self.pilot.win.connect("notify::has-toplevel-focus", self._pilot_focus)
        self.brain = Brain(self._BrainCB(self), ui=self._ui_from_brain, live=self.live)
        self.ensure_voice()

    class _BrainCB:
        def __init__(self, app):
            self.app = app

        def state(self, s):
            GLib.idle_add(self.app._pilot_state, s)

        def delta(self, text):
            GLib.idle_add(self.app._pilot_delta, text)

        def tool(self, name, args, label, ex):
            GLib.idle_add(self.app._pilot_tool, name, label, ex)

        def done(self, text, stats):
            GLib.idle_add(self.app._pilot_done, text, stats)

        def error(self, msg):
            GLib.idle_add(self.app._pilot_error, msg)

        def reroute(self, model, why):
            GLib.idle_add(self.app._pilot_reroute, model, why)

    def _pilot_state(self, s):
        self.pscene.set_state(s)
        self.pscene.subtitle = ""

    def _pilot_delta(self, text):
        self.pscene.feed(text)
        if self.voice:
            self.voice.feed(text)
        self.last_activity = time.monotonic()

    def _pilot_tool(self, name, label, ex):
        self.pscene.add_tool(label)
        self.pscene.subtitle = label.split(" · ")[0].upper()
        if ex:
            self.pscene.exhibit(*ex)

    def _pilot_done(self, text, stats):
        self.pscene.end_reply()
        self.pscene.route = f"{stats.get('model', self.brain.model)} · homelab LiteLLM"
        self.last_activity = time.monotonic()
        if self.voice:
            self.voice.flush()
        log("reply", json.dumps(stats))
        if not self._pilot_shown():
            self.unread += 1
            self._notify("PILOT", text)

    def _pilot_error(self, msg):
        self.pscene.end_reply()
        self.pscene.set_state("error")
        line = "Oh no. Sorry, sorry: " + msg
        self.pscene.note(line)
        if self.voice:
            self.voice.say("Oh no. Sorry. Every model I can reach has gone quiet." if "went quiet" in msg
                           else "Oh no. That didn't work, sorry.")
        if not self._pilot_shown():
            self.unread += 1
            self._notify("PILOT: trouble", line)
        GLib.timeout_add(2500, lambda: (self.pscene.avatar.state == "error" and self.pscene.set_state("idle"), False)[1])

    def _pilot_reroute(self, model, why):
        self.pscene.reroute(model, why)
        self.pscene.route = f"{model} · homelab LiteLLM (rerouted)"

    def _pilot_shown(self):
        return bool(self.pilot and self.pilot.visible and self.pscene.fade_to > 0)

    def _notify(self, title, body):
        """A quiet notification while PILOT is minimized (no live-layer chirp; voice speaks it)."""
        from .pilot.text import plain
        body = plain(body)
        body = body if len(body) <= 220 else body[:217] + "…"
        try:
            import subprocess
            subprocess.Popen(["notify-send", "-a", "PILOT", "-u", "low", "-t", "9000",
                              "-h", "string:x-bromigos-sound:none", "-h", "string:x-dunst-stack-tag:pilot",
                              title, body + "\nSUPER+E to open"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass

    def _ui_from_brain(self, name, args):
        """UI-only tools, called from the brain thread."""
        from . import fmt
        model = (args or {}).get("model") or "workstation"
        if model not in fmt.available():
            raise ValueError(f"model must be one of {fmt.available()}")
        if name == "show_hologram":
            GLib.idle_add(lambda: (self.pscene.exhibit(model, args.get("parts")), False)[1])
            return {"ok": True, "showing": model}
        GLib.idle_add(lambda: (self.show_gallery(model), False)[1])
        return {"ok": True, "gallery": model}

    def _on_entry(self, entry):
        text = entry.get_text().strip()
        if not text:
            return
        entry.set_text("")
        self.ask(text)

    def ask(self, text):
        self.ensure_pilot()
        if not self.pilot.visible:
            self.show_pilot(focus=False)
        self.pscene.add_user(text)
        self.last_activity = time.monotonic()
        self.brain.ask(text)

    def _pilot_key(self, w, ev):
        name = Gdk.keyval_name(ev.keyval)
        self.last_activity = time.monotonic()
        if name == "Escape":
            if ev.state & Gdk.ModifierType.SHIFT_MASK:
                self.hide_pilot()               # Shift+Esc minimizes
            else:
                self.release_keyboard()         # Esc hands the keyboard back; PILOT stays up
            return True
        if not self.entry.has_focus():
            self.entry.grab_focus_without_selecting()
        return False

    def _pilot_focus(self, win, *a):
        self.focused = win.props.has_toplevel_focus
        self.pscene.typing = self.focused

    def release_keyboard(self):
        """Give keyboard focus back to the window behind; clicking the entry takes it again."""
        if not self.pilot:
            return
        self.pilot.keyboard("none")
        GLib.timeout_add(120, lambda: (self.pilot.visible and self.pilot.keyboard("on_demand"), False)[1])

    def focus_pilot(self):
        """SUPER+E: the window was just mapped on-demand, so the compositor gave it the
        keyboard; put the caret in the entry. A click on any other window takes it back."""
        self.entry.grab_focus()

    def show_pilot(self, focus=True):
        self.ensure_pilot()
        first = not self.pscene.msgs
        self.pscene.fade_to = 1.0
        was_hidden = not self.pilot.visible
        self.pilot.show(focus=focus)
        if was_hidden:
            self.pscene.catch_up()              # replies that came in while minimized: show them whole
        self.unread = 0
        self.hidden_since = None
        if focus:
            self.focus_pilot()
        if first:
            from .pilot.persona import GREETING
            self.pscene.set_state("speaking")
            self.pscene.feed(GREETING)
            self.pscene.end_reply()
            if self.voice:
                self.voice.say(GREETING)
        else:
            self.pscene.set_state("listening" if focus else self.pscene.avatar.state)
            GLib.timeout_add(900, lambda: (self.pscene.avatar.state == "listening" and self.pscene.set_state("idle"), False)[1])
        self.last_activity = time.monotonic()

    def hide_pilot(self):
        """Minimize: the window goes, PILOT keeps working (turn, tools, voice)."""
        if self.pilot and self.pilot.visible:
            self.pscene.fade_to = 0.0
            self.hidden_since = time.monotonic()
            GLib.timeout_add(260, lambda: (self.pilot.hide() if self.pscene.fade_to == 0 else None, False)[1])

    def toggle_pilot(self):
        if self._pilot_shown():
            self.hide_pilot()
        else:
            self.show_pilot()

    def _voice_label(self):
        if not self.voice:
            return "TYPED · VOICE NOT SET UP"
        return "VOICE MUTED · SUPER+SHIFT+V" if self.voice.muted else "HOLD SUPER+V TO TALK · SUPER+SHIFT+V MUTES"

    # ------------------------------------------------------------------ gallery
    def ensure_gallery(self):
        if self.gallery:
            return
        from .gallery import Gallery
        self.gscene = Gallery(self.live)
        self.gallery = HoloWindow("bromigos-holo-gallery", self.gscene, (1760, 1040), "", {})
        a = self.gallery.area
        a.connect("motion-notify-event", lambda w, e: self.gscene.on_motion(e.x, e.y))
        a.connect("button-press-event", lambda w, e: self.gscene.on_press(e.x, e.y, e.button))
        a.connect("button-release-event", lambda w, e: self.gscene.on_release(e.x, e.y, e.button))
        a.connect("scroll-event", self._gallery_scroll)
        self.gallery.win.connect("key-press-event", self._gallery_key)

    def _gallery_scroll(self, w, e):
        ok, dx, dy = e.get_scroll_deltas()
        if not ok:
            dy = {Gdk.ScrollDirection.UP: -1, Gdk.ScrollDirection.DOWN: 1}.get(e.direction, 0)
        self.gscene.on_scroll(dy)
        return True

    def _gallery_key(self, w, ev):
        name = Gdk.keyval_name(ev.keyval)
        if name == "Escape":
            self.gallery.hide()
            return True
        return self.gscene.on_key(name)

    def show_gallery(self, model=None):
        self.ensure_gallery()
        self.gscene.show(model) if model else self.gscene.show(self.gscene.names[self.gscene.idx])
        self.gallery.show()

    def toggle_gallery(self, model=None):
        if self.gallery and self.gallery.visible and not model:
            self.gallery.hide()
        else:
            self.show_gallery(model)

    # ------------------------------------------------------------------ voice (phase 3)
    def ensure_voice(self):
        self.ensure_pilot()
        if self.voice is None:
            try:
                from .pilot.voice import Voice
                self.voice = Voice(self)
            except Exception as e:
                log("voice unavailable:", e)
                self.voice = None
        self.pscene.voice = self._voice_label()
        return self.voice

    # ------------------------------------------------------------------ housekeeping
    def _idle_check(self):
        # PILOT steps back after a quiet two minutes once it has finished talking (unless you're typing)
        if self._pilot_shown() and not self.busy() and not self.pscene.revealing() and not self.focused:
            if time.monotonic() - self.last_activity > 120:
                self.hide_pilot()
        return True

    def busy(self):
        """A turn is running or speech is queued/playing: never exit or drop it."""
        return bool((self.brain and self.brain.busy) or (self.voice and self.voice.active()))

    def pilot_state(self):
        if not self.pilot:
            return "off"
        if self.voice and self.voice.rec:
            return "listening"
        if self.pscene.avatar.state == "error":
            return "error"
        if self.voice and self.voice.speaking:
            return "speaking"
        if self.brain and self.brain.busy:
            return "speaking" if self.pscene.streaming() else "thinking"
        return "idle"

    def _publish_state(self):
        """The bar module's feed: state, unread count, whether it is minimized."""
        st = {"state": self.pilot_state(), "unread": self.unread, "shown": self._pilot_shown(),
              "model": self.brain.model if self.brain else None,
              "muted": bool(self.voice and self.voice.muted)}
        sig = json.dumps(st, sort_keys=True)
        if sig != self._state_sig:
            self._state_sig = sig
            tmp = PILOT_STATE + ".part"
            with open(tmp, "w") as f:
                f.write(sig)
            os.replace(tmp, PILOT_STATE)
            try:
                import subprocess
                subprocess.Popen(["pkill", f"-RTMIN+{WAYBAR_SIGNAL}", "-x", "waybar"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                pass
        return True

    def status(self):
        out = {"pid": os.getpid()}
        for k, w in (("pilot", self.pilot), ("gallery", self.gallery)):
            if w:
                out[k] = {"visible": w.visible, "fps": w.fps, "frames": w.frames, "frame_ms": round(w.frame_ms, 2)}
        if self.pilot:
            out["pilot"].update(state=self.pilot_state(), unread=self.unread, focused=self.focused,
                                model=self.brain.model, input_rects=list(self.pilot.input_rects),
                                entry_text=self.entry.get_text())
        if self.voice:
            out["voice"] = self.voice.status()
        return json.dumps(out)

    def command(self, cmd):
        parts = cmd.strip().split(" ", 1)
        verb, arg = parts[0], (parts[1] if len(parts) > 1 else "")
        if verb == "pilot":
            self.toggle_pilot()
        elif verb == "pilot-show":
            self.show_pilot()
        elif verb == "pilot-hide":
            self.hide_pilot()
        elif verb == "ask":
            self.ask(arg)
        elif verb == "gallery":
            self.toggle_gallery(arg or None)
        elif verb == "gallery-hide":
            if self.gallery:
                self.gallery.hide()
        elif verb == "ptt":
            v = self.ensure_voice()
            if not v:
                return "voice unavailable"
            (v.ptt_down if arg != "off" else v.ptt_up)()
        elif verb == "mute":
            v = self.ensure_voice()
            if v:
                v.toggle_mute()
                if self.pilot:
                    self.pscene.voice = self._voice_label()
                return "muted" if v.muted else "unmuted"
            return "voice unavailable"
        elif verb == "snap":
            name, _, path = arg.partition(" ")
            w = {"pilot": self.pilot, "gallery": self.gallery}.get(name)
            if not w or not w.visible:
                return "not visible"
            w.snap_path = os.path.expanduser(path)
            w.area.queue_render()
        elif verb == "gallery-do":
            self.ensure_gallery()
            for k in arg.split():
                self.gscene.on_key(k)
        elif verb == "status":
            return self.status()
        elif verb == "stop":
            # a running turn or queued speech finishes first (up to 90 s) unless "stop now"
            if arg != "now" and self.busy():
                t0 = time.monotonic()

                def wait():
                    if self.busy() and time.monotonic() - t0 < 90:
                        return True
                    Gtk.main_quit()
                    return False
                GLib.timeout_add(500, wait)
                return "stopping after the current turn"
            GLib.idle_add(Gtk.main_quit)
        elif verb == "release":
            self.release_keyboard()
        else:
            return "unknown command"
        return "ok"

    def _serve(self):
        try:
            os.unlink(SOCK)
        except FileNotFoundError:
            pass
        srv = socket.socket(socket.AF_UNIX)
        srv.bind(SOCK)
        os.chmod(SOCK, 0o600)
        srv.listen(4)

        def loop():
            while True:
                c, _ = srv.accept()
                try:
                    cmd = c.recv(4096).decode()
                    box = {}
                    ev = threading.Event()

                    def run():
                        try:
                            box["r"] = self.command(cmd)
                        except Exception as e:
                            box["r"] = f"error: {e}"
                        ev.set()
                        return False
                    GLib.idle_add(run)
                    ev.wait(5)
                    c.sendall((box.get("r") or "timeout").encode())
                finally:
                    c.close()
        threading.Thread(target=loop, daemon=True, name="holo-sock").start()


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, lambda *a: Gtk.main_quit())
    App()
    log("ready on", SOCK)
    Gtk.main()
    for p in (SOCK, PILOT_STATE):
        try:
            os.unlink(p)
        except OSError:
            pass
    subprocess_quiet(["pkill", f"-RTMIN+{WAYBAR_SIGNAL}", "-x", "waybar"])


def subprocess_quiet(argv):
    import subprocess
    try:
        subprocess.run(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        pass


if __name__ == "__main__":
    main()
