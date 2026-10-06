"""bromigos-holo daemon: one GTK process hosting VECTOR's console and the hologram gallery,
both on the shared renderer. Controlled over a unix socket by bin/bromigos-holo.

Windows are layer-shell surfaces on the overlay layer, shown only when summoned.
Hidden windows render nothing; the idle daemon is a sleeping GTK main loop.

VECTOR never blocks the desktop: its window takes input only on the chat entry and its
minimize button (an input region; clicks anywhere else go to the window behind it),
and it holds keyboard focus on demand (when SUPER+E opens it or the entry is clicked;
Esc or a click elsewhere hands it back). Minimized, VECTOR keeps working: a running
turn finishes, the reply is spoken (voice on) and queued for the next open, and the
bar module (waybar custom/vector, fed by $XDG_RUNTIME_DIR/bromigos-vector.json) shows its
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
VECTOR_STATE = os.path.join(RUNTIME, "bromigos-vector.json")
WAYBAR_SIGNAL = 9           # waybar custom/vector "signal": 9 -> refresh on SIGRTMIN+9
MONITOR = os.environ.get("BROMIGOS_HOLO_MONITOR", "DP-1")
CSS = b"""
#vector-entry {
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
#vector-entry:focus { border-color: #39ff14; }
#vector-entry selection { background-color: #159b09; color: #000500; }
#vector-min {
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
#vector-min:hover { color: #000500; background-color: #39ff14; border-color: #39ff14; }
#vector-history {
  background-color: rgba(0, 12, 0, 0.92);
  border: 1px solid rgba(21, 155, 9, 0.9);
  font-family: "Geist Mono";
}
#vector-history list, #vector-history row { background-color: transparent; }
#vector-history row { padding: 6px 10px; border-bottom: 1px solid rgba(21, 155, 9, 0.25); }
#vector-history row:hover { background-color: rgba(57, 255, 20, 0.12); }
#vector-history .hist-title { color: #9cff8a; font-weight: 700; font-size: 13px; }
#vector-history .hist-meta { color: #7e927e; font-size: 11px; }
#vector-history .hist-head { color: #39ff14; font-weight: 700; font-size: 12px; letter-spacing: 2px; padding: 8px 10px; }
#vector-history textview, #vector-history textview text { background-color: transparent; color: #c4f5bb; font-size: 13px; }
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
        self.vector = None
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

    # ------------------------------------------------------------------ VECTOR
    def ensure_vector(self):
        if self.vector:
            return
        from .vector.brain import Brain
        try:
            with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "voice.json")) as f:
                which = json.load(f).get("brain", "classic")
        except (OSError, ValueError):
            which = "classic"
        if which == "pai":
            try:
                from .vector.brain_pai import PaiBrain as Brain   # noqa: F811
            except ImportError as e:          # not in venv-brain: run the classic brain
                log("pydantic-ai brain unavailable, using classic:", e)
        from .vector.scene import VectorScene
        self.pscene = VectorScene(self.live)
        self.entry = Gtk.Entry(name="vector-entry")
        self.entry.set_placeholder_text("ask VECTOR…")
        self.entry.set_halign(Gtk.Align.END)
        self.entry.set_valign(Gtk.Align.END)
        self.entry.set_margin_end(30)
        self.entry.set_margin_bottom(34)
        self.entry.set_size_request(1180 - self.pscene.left_w - 14 - 30, -1)
        self.entry.connect("activate", self._on_entry)
        self.entry.connect("changed", lambda e: self.histpanel.get_visible() and GLib.timeout_add(250, self._history_typed, e.get_text()))
        self.entry.set_tooltip_text("Type to VECTOR; Enter sends. Esc hands the keyboard back; click here to type again.")
        self.minbtn = Gtk.Button(label="— MINIMIZE", name="vector-min")
        self.minbtn.set_halign(Gtk.Align.END)
        self.minbtn.set_valign(Gtk.Align.START)
        self.minbtn.set_margin_end(30)
        self.minbtn.set_margin_top(64)
        self.minbtn.set_can_focus(False)
        self.minbtn.set_tooltip_text("Minimize VECTOR. It keeps working: replies are spoken and wait here for you. "
                                     "SUPER+E brings it back; the bar's VECTOR pip shows what it is doing.")
        self.minbtn.connect("clicked", lambda b: self.hide_vector())
        self.convbtn = Gtk.Button(label="◉ CONVERSATION", name="vector-min")
        self.convbtn.set_halign(Gtk.Align.END)
        self.convbtn.set_valign(Gtk.Align.START)
        self.convbtn.set_margin_end(140)
        self.convbtn.set_margin_top(64)
        self.convbtn.set_can_focus(False)
        self.convbtn.set_tooltip_text("Conversation mode (SUPER+SHIFT+E): hands-free. VECTOR listens on the echo-cancelled mic, "
                                      "answers when you pause, and listens again; talk over him to interrupt. "
                                      "Off after two quiet minutes. The mic is closed whenever this is off.")
        self.convbtn.connect("clicked", lambda b: self.toggle_conversation())
        self.histbtn = Gtk.Button(label="☰ HISTORY", name="vector-min")
        self.histbtn.set_halign(Gtk.Align.END)
        self.histbtn.set_valign(Gtk.Align.START)
        self.histbtn.set_margin_end(300)
        self.histbtn.set_margin_top(64)
        self.histbtn.set_can_focus(False)
        self.histbtn.set_tooltip_text("Past conversations with VECTOR, newest first (Ctrl+H). Type in the box below to search "
                                      "every message; click one to read it; CONTINUE picks it up again.")
        self.histbtn.connect("clicked", lambda b: self.toggle_history())
        self.histpanel = self._build_history()
        self.stopbtn = Gtk.Button(label="■ STOP", name="vector-min")
        self.stopbtn.set_halign(Gtk.Align.END)
        self.stopbtn.set_valign(Gtk.Align.END)
        self.stopbtn.set_margin_end(30)
        self.stopbtn.set_margin_bottom(96)
        self.stopbtn.set_can_focus(False)
        self.stopbtn.set_no_show_all(True)
        self.stopbtn.set_tooltip_text("Stop the command VECTOR is running in the terminal (kills its whole process group).")
        self.stopbtn.connect("clicked", lambda b: self._stop_clicked())
        from .vector.shell import RUNNER
        RUNNER.on_change = lambda cur: GLib.idle_add(self._shell_changed, cur)
        RUNNER.on_notice = lambda text: GLib.idle_add(self._herdr_notice, text)   # spoken in the notify voice
        self.vector = HoloWindow("bromigos-vector", self.pscene, (1180, 640), "br", {"r": 24, "b": 24},
                                keyboard_exclusive=False, overlay_children=[self.histpanel, self.entry, self.minbtn, self.convbtn, self.histbtn, self.stopbtn],
                                input_widgets=[self.entry, self.minbtn, self.convbtn, self.histbtn, self.stopbtn, self.histpanel])
        self.vector.win.connect("key-press-event", self._vector_key)
        self.vector.win.connect("notify::has-toplevel-focus", self._vector_focus)
        self.brain = Brain(self._BrainCB(self), ui=self._ui_from_brain, live=self.live)
        try:
            from .vector.memory import Memory
            self.memory = Memory()
            self.brain.memory = self.memory
        except Exception as e:
            log("memory unavailable:", e)
            self.memory = None
        self.summarized_at = 0               # history length at the last end-of-conversation summary
        try:                                 # herdr agents waiting on the host / finishing -> a spoken notice
            from .vector.guard import Sentinel
            self.sentinel = Sentinel(lambda paths: GLib.idle_add(
                self._herdr_notice, "My safety code changed on disk, so I've switched my terminal off until I'm restarted."))
            GLib.timeout_add_seconds(6, self._announce_trial)
            from .vector.reach import HerdrWatcher
            self.herdr = HerdrWatcher(lambda msg, a: GLib.idle_add(self._herdr_notice, msg))
        except Exception as e:
            log("herdr watcher unavailable:", e)
        self.ensure_voice()

    class _BrainCB:
        def __init__(self, app):
            self.app = app

        def state(self, s):
            GLib.idle_add(self.app._vector_state, s)

        def delta(self, text):
            GLib.idle_add(self.app._vector_delta, text)

        def tool(self, name, args, label, ex):
            GLib.idle_add(self.app._vector_tool, name, label, ex)

        def ack(self, text):
            GLib.idle_add(self.app._vector_ack, text)

        def memory(self, what, n=1):
            GLib.idle_add(self.app.pscene.memory_flash, what, n)

        def mood(self, mood):
            GLib.idle_add(self.app.pscene.set_mood_from_facts, mood)

        def done(self, text, stats):
            GLib.idle_add(self.app._vector_done, text, stats)

        def error(self, msg):
            GLib.idle_add(self.app._vector_error, msg)

        def reroute(self, model, why):
            GLib.idle_add(self.app._vector_reroute, model, why)

    def _vector_state(self, s):
        self.pscene.set_state(s)
        self.pscene.subtitle = ""

    def _vector_delta(self, text):
        self.pscene.feed(text)
        if self.voice:
            self.voice.feed(text)
        self.last_activity = time.monotonic()

    def _vector_tool(self, name, label, ex):
        self.pscene.add_tool(label)
        self.pscene.subtitle = label.split(" · ")[0].upper()
        if ex:
            self.pscene.exhibit(*ex)

    def _vector_done(self, text, stats):
        self.pscene.end_reply()
        self.pscene.route = f"{stats.get('model', self.brain.model)} · homelab LiteLLM"
        self.last_activity = time.monotonic()
        if self.voice:
            self.voice.flush()
        log("reply", json.dumps(stats))
        if not self._vector_shown():
            self.unread += 1
            self._notify("VECTOR", text)

    def _vector_error(self, msg):
        self.pscene.end_reply()
        self.pscene.set_state("error")
        line = "Oh no. Sorry, sorry: " + msg
        self.pscene.note(line)
        if self.voice:
            self.voice.say("Oh no. Sorry. Every model I can reach has gone quiet." if "went quiet" in msg
                           else "Oh no. That didn't work, sorry.")
        if not self._vector_shown():
            self.unread += 1
            self._notify("VECTOR: trouble", line)
        GLib.timeout_add(2500, lambda: (self.pscene.avatar.state == "error" and self.pscene.set_state("idle"), False)[1])

    # ------------------------------------------------------------------ builds (background, trial mode)
    def _build_tool(self, name, args):
        from .vector import build
        if name == "build_start":
            cur = getattr(self, "build_task", None)
            if cur and cur.thread.is_alive():
                return {"refused": f"a build is already running ({cur.note}); one at a time"}
            st = build.state()
            if st.get("phase") == "trial":
                return {"refused": f"the {st.get('title')} trial is still up; keep or revert it first"}
            from .vector.buildtask import BuildTask
            goal = (args.get("goal") or "").strip()
            if len(goal) < 8:
                raise ValueError("goal: what to build, in a sentence")
            self.build_task = BuildTask(goal, lambda note, pct: GLib.idle_add(self._build_progress, note, pct),
                                        lambda ok, summary, secs: GLib.idle_add(self._build_done, ok, summary, secs))
            GLib.idle_add(self._build_progress, "starting", 0)
            return {"ok": True, "started": goal, "note": "it runs in the background; you'll hear when the trial is up"}
        if name == "build_status":
            t = getattr(self, "build_task", None)
            turn = build.LAST_USER["t"]
            self._status_calls = (self._status_calls + 1) if getattr(self, "_status_turn", None) == turn else 1
            self._status_turn = turn
            if self._status_calls > 1 and t and t.thread.is_alive():
                return {"note": "Still building in the background. Don't check again: end your turn now and talk with "
                                "the host about anything else; you'll announce the trial when it's up."}
            return {**build.status(), **({"builder": {"note": t.note, "pct": t.pct, "seconds": round(time.time() - t.started),
                                                     "running": t.thread.is_alive()}} if t else {})}
        if name == "build_stop":
            t = getattr(self, "build_task", None)
            out = t.stop() if t and t.thread.is_alive() else build.stop("stopped by the host")
            GLib.idle_add(self._build_progress, None, None)
            return out
        if name == "build_keep":
            return build.keep()
        if name == "build_revert":
            return build.revert("the host said revert")
        raise ValueError(f"unknown build tool {name}")

    def _build_progress(self, note, pct):
        """The BUILDING readout (with STOP), and a spoken milestone now and then."""
        t = getattr(self, "build_task", None)
        self.pscene.build_line = None if note is None else (note, pct, t.started if t else time.time())
        building = note is not None
        self.stopbtn.set_visible(building or bool(getattr(self.pscene, "shell_cmd", None)))
        self.stopbtn.set_tooltip_text("Stop the build VECTOR is running in the background (its worktree is removed; "
                                      "a trial is rolled back)." if building else
                                      "Stop the command VECTOR is running in the terminal (kills its whole process group).")
        if self.vector:
            self.vector.update_input_region()
        now = time.monotonic()
        if note and note != "starting" and now - getattr(self, "build_said", 0) > 45:
            self.build_said = now
            self._herdr_notice(f"Build: {note}.")
        self._publish_state()
        return False

    def _build_done(self, ok, summary, secs):
        self.pscene.build_line = None
        self.stopbtn.set_visible(bool(getattr(self.pscene, "shell_cmd", None)))
        from .vector import build
        st = build.state()
        if ok and st.get("phase") == "trial":
            self._herdr_notice(f"{st.get('say') or 'The build is up.'} Keep it? Ten minutes to decide.")
        else:
            self._herdr_notice(f"The build didn't make it: {summary[:160]}")
        self.pscene.note(f"Build {'up for trial' if ok else 'ended'} after {secs // 60} min {secs % 60} s: {summary[:300]}")
        if self.vector:
            self.vector.update_input_region()
        return False

    def _announce_trial(self):
        """After a restart (a build that changed VECTOR himself), say the trial is up."""
        from .vector import build
        st = build.state()
        if st.get("phase") == "trial" and time.time() < st.get("deadline", 0):
            self._herdr_notice(f"{st.get('say') or 'The build is up.'} Keep it?")
        return False

    def _herdr_notice(self, msg):
        self.pscene.note(msg)
        if self.voice and not self.voice.muted and not self.voice.rec:
            self.voice.say(msg, role="notify")
        if not self._vector_shown():
            self.unread += 1
            self._notify("VECTOR · herdr", msg)
        return False

    # ------------------------------------------------------------------ history
    def _build_history(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, name="vector-history")
        box.set_halign(Gtk.Align.END)
        box.set_valign(Gtk.Align.START)
        box.set_margin_end(30)
        box.set_margin_top(100)
        box.set_size_request(1180 - 540 - 14 - 30, 440)
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.hist_head = Gtk.Label(label="PAST CONVERSATIONS", xalign=0)
        self.hist_head.get_style_context().add_class("hist-head")
        bar.pack_start(self.hist_head, True, True, 0)
        self.hist_back = Gtk.Button(label="◀ BACK", name="vector-min")
        self.hist_back.set_tooltip_text("Back to the list of conversations.")
        self.hist_back.connect("clicked", lambda b: self._history_list())
        self.hist_cont = Gtk.Button(label="↻ CONTINUE", name="vector-min")
        self.hist_cont.set_tooltip_text("Load this conversation's recent turns back into VECTOR's context and carry on.")
        self.hist_cont.connect("clicked", lambda b: self._history_continue())
        for b in (self.hist_back, self.hist_cont):
            b.set_can_focus(False)
            b.set_no_show_all(True)
            bar.pack_end(b, False, False, 4)
        box.pack_start(bar, False, False, 0)
        self.hist_scroll = Gtk.ScrolledWindow()
        self.hist_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.hist_list = Gtk.ListBox()
        self.hist_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.hist_list.connect("row-activated", lambda lb, row: self._history_open(row.session_id))
        self.hist_text = Gtk.TextView()
        self.hist_text.set_editable(False)
        self.hist_text.set_cursor_visible(False)
        self.hist_text.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.hist_text.set_left_margin(10)
        self.hist_text.set_right_margin(10)
        self.hist_scroll.add(self.hist_list)
        box.pack_start(self.hist_scroll, True, True, 0)
        box.set_no_show_all(True)
        self.hist_open_id = None
        return box

    def toggle_history(self):
        if self.histpanel.get_visible():
            self.histpanel.hide()
            self.entry.set_placeholder_text("ask VECTOR…")
        else:
            from .vector import history
            history.title_missing()
            self.histpanel.show()              # (no_show_all: show the parts by hand; BACK/CONTINUE stay hidden)
            for w in (self.hist_head.get_parent(), self.hist_head, self.hist_scroll, self.hist_list):
                w.show()
            self._history_list()
            self.entry.set_placeholder_text("search past conversations…")
        self.pscene.history_open = self.histpanel.get_visible()
        if self.vector:
            self.vector.update_input_region()
            GLib.timeout_add(50, lambda: (self.vector.update_input_region(), False)[1])
        return "history " + ("open" if self.histpanel.get_visible() else "closed")

    def _history_list(self, query=None):
        from .vector import history
        self.hist_open_id = None
        self.hist_back.hide()
        self.hist_cont.hide()
        if self.hist_scroll.get_child() is not self.hist_list:
            self.hist_scroll.remove(self.hist_scroll.get_child())
            self.hist_scroll.add(self.hist_list)
        for row in self.hist_list.get_children():
            self.hist_list.remove(row)
        q = (query if query is not None else self.entry.get_text()).strip()
        if q:
            hits = history.search(q, 60)
            seen, items = set(), []
            for s, m in hits:
                if s["id"] not in seen:
                    seen.add(s["id"])
                    items.append((s, f"{m['role']}: {m['text'][:110]}"))
            self.hist_head.set_text(f"MATCHING “{q[:24]}” · {len(items)}")
        else:
            items = [(s, s.get("summary") or "") for s in history.sessions()[:200]]
            self.hist_head.set_text(f"PAST CONVERSATIONS · {len(items)}")
        for s, sub in items:
            row = Gtk.ListBoxRow()
            row.session_id = s["id"]
            v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            t = Gtk.Label(label=s["title"], xalign=0)
            t.set_ellipsize(3)
            t.get_style_context().add_class("hist-title")
            meta = Gtk.Label(label=f"{s['start'].strftime('%a %d %b %Y · %H:%M')} · {s['count']} messages"
                             + (f" · {sub[:90]}" if sub else ""), xalign=0)
            meta.set_ellipsize(3)
            meta.get_style_context().add_class("hist-meta")
            v.pack_start(t, False, False, 0)
            v.pack_start(meta, False, False, 0)
            row.add(v)
            row.set_tooltip_text("Open this conversation (read only); CONTINUE inside picks it up again.")
            self.hist_list.add(row)
        self.hist_list.show_all()

    def _history_typed(self, text):
        if self.histpanel.get_visible() and self.entry.get_text() == text and self.hist_open_id is None:
            self._history_list(text)
        return False

    def _history_open(self, sid):
        from .vector import history
        s = next((x for x in history.sessions() if x["id"] == sid), None)
        if not s:
            return
        self.hist_open_id = sid
        self.hist_head.set_text(f"{s['start'].strftime('%a %d %b · %H:%M')} · {s['title'][:40]}")
        buf = self.hist_text.get_buffer()
        lines = []
        for m in s["messages"]:
            who = {"you": "› YOU", "vector": "VECTOR", "tool": "  ⟐"}.get(m["role"], m["role"])
            lines.append(f"{m['t'].strftime('%H:%M')}  {who}  {m['text']}")
        buf.set_text("\n\n".join(lines))
        self.hist_scroll.remove(self.hist_scroll.get_child())
        self.hist_scroll.add(self.hist_text)
        self.hist_text.show()
        self.hist_back.show()
        self.hist_cont.show()

    def _history_continue(self):
        from .vector import history
        s = next((x for x in history.sessions() if x["id"] == self.hist_open_id), None)
        if not s or not self.brain:
            return
        turns, pending = [], None
        for m in s["messages"]:
            if m["role"] == "you":
                pending = m["text"]
            elif m["role"] == "vector" and pending is not None:
                turns.append((pending, m["text"]))
                pending = None
        keep, size = [], 0
        for u, v in reversed(turns):             # the most recent turns, up to ~16k characters
            size += len(u) + len(v)
            if keep and (len(keep) >= 24 or size > 16000):
                break
            keep.insert(0, (u, v))
        if len(keep) < len(turns) and s.get("summary"):   # what came before, in one line
            keep.insert(0, ("(Earlier in this conversation, before the turns below.)", "Earlier we covered: " + s["summary"]))
        self.brain.load_turns(keep)
        self.pscene.note(f"Continuing “{s['title'][:50]}” ({min(len(keep), len(turns))} of {len(turns)} turns back in context).")
        self.toggle_history()

    def _shell_changed(self, cur):
        """A terminal command started (cur) or ended (None): live line + STOP button."""
        self.pscene.shell_cmd = (cur["command"], cur["t0"]) if cur else None
        self.stopbtn.set_visible(bool(cur))
        if self.vector:
            self.vector.update_input_region()
        self._publish_state()
        return False

    def _stop_clicked(self):
        t = getattr(self, "build_task", None)
        if t and t.thread.is_alive():
            threading.Thread(target=lambda: self._build_tool("build_stop", {}), daemon=True).start()
            self._herdr_notice("Stopping the build.")
            return "stopping the build"
        return self.shell_stop()

    def shell_stop(self):
        from .vector.shell import RUNNER
        return "stopped" if RUNNER.kill("stopped by the host") else "nothing running"

    def toggle_conversation(self):
        v = self.ensure_voice()
        if not v:
            return "voice unavailable"
        if getattr(v, "conv", None) is None:
            from .vector.conversation import Conversation
            v.conv = Conversation(v)
        on = v.conv.toggle()
        self.convbtn.set_label("◉ END CONVERSATION" if on else "◉ CONVERSATION")
        self.last_activity = time.monotonic()
        return "conversation on" if on else "conversation off"

    def conversation_on(self):
        return bool(self.voice and getattr(self.voice, "conv", None) and self.voice.conv.on)

    def _vector_ack(self, text):
        """The voice lane handed the turn to the deep lane: say a short in-character line meanwhile."""
        self.pscene.add_tool("handing to the deep lane")
        if self.voice:
            self.voice.say(text, role=self.voice.voice_now)

    def _vector_reroute(self, model, why):
        self.pscene.reroute(model, why)
        self.pscene.route = f"{model} · homelab LiteLLM (rerouted)"

    def _vector_shown(self):
        return bool(self.vector and self.vector.visible and self.pscene.fade_to > 0)

    def _notify(self, title, body):
        """A quiet notification while VECTOR is minimized (no live-layer chirp; voice speaks it)."""
        from .vector.text import plain
        body = plain(body)
        body = body if len(body) <= 220 else body[:217] + "…"
        try:
            import subprocess
            subprocess.Popen(["notify-send", "-a", "VECTOR", "-u", "low", "-t", "9000",
                              "-h", "string:x-bromigos-sound:none", "-h", "string:x-dunst-stack-tag:vector",
                              title, body + "\nSUPER+E to open"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass

    def _ui_from_brain(self, name, args):
        """UI-only tools, called from the brain thread."""
        if name.startswith("build_"):
            return self._build_tool(name, args or {})
        if name in ("remember", "forget"):
            if not self.memory:
                raise RuntimeError("long-term memory unavailable")
            if name == "remember":
                out = self.memory.remember((args or {}).get("text", ""), (args or {}).get("category") or "note")
                GLib.idle_add(self.pscene.memory_flash, "store", 1)
            else:
                out = self.memory.forget((args or {}).get("what", ""))
                if out.get("ok"):
                    GLib.idle_add(self.pscene.memory_flash, "forget", 1)
            return out
        from . import fmt
        model = (args or {}).get("model") or "workstation"
        if model not in fmt.available():
            raise ValueError(f"model must be one of {fmt.available()}")
        if name == "set_voice":
            mode = (args or {}).get("mode", "auto")
            box = {}
            ev = threading.Event()

            def run():
                try:
                    box["m"] = self.set_voice_mode(mode)
                except Exception as e:
                    box["e"] = e
                ev.set()
                return False
            GLib.idle_add(run)
            ev.wait(5)
            if "e" in box:
                raise box["e"]
            return {"ok": True, "voice_mode": box.get("m")}
        if name == "show_hologram":
            GLib.idle_add(lambda: (self.pscene.exhibit(model, args.get("parts")), False)[1])
            return {"ok": True, "showing": model}
        GLib.idle_add(lambda: (self.show_gallery(model), False)[1])
        return {"ok": True, "gallery": model}

    def _on_entry(self, entry):
        if self.histpanel.get_visible():          # in history, the box searches
            self._history_list()
            return
        text = entry.get_text().strip()
        if not text:
            return
        entry.set_text("")
        self.ask(text)

    def ask(self, text):
        self.ensure_vector()
        self.last_word = time.monotonic()
        if not self.vector.visible:
            self.show_vector(focus=False, greet=False)
        self.pscene.add_user(text)
        self.last_activity = time.monotonic()
        self.brain.ask(text)

    def _vector_key(self, w, ev):
        name = Gdk.keyval_name(ev.keyval)
        self.last_activity = time.monotonic()
        if name in ("h", "H") and ev.state & Gdk.ModifierType.CONTROL_MASK:
            self.toggle_history()
            return True
        if name == "Escape" and self.histpanel.get_visible():
            self.toggle_history()
            return True
        if name == "Escape":
            if ev.state & Gdk.ModifierType.SHIFT_MASK:
                self.hide_vector()               # Shift+Esc minimizes
            else:
                self.release_keyboard()         # Esc hands the keyboard back; VECTOR stays up
            return True
        if not self.entry.has_focus():
            self.entry.grab_focus_without_selecting()
        return False

    def _vector_focus(self, win, *a):
        self.focused = win.props.has_toplevel_focus
        self.pscene.typing = self.focused

    def release_keyboard(self):
        """Give keyboard focus back to the window behind; clicking the entry takes it again."""
        if not self.vector:
            return
        self.vector.keyboard("none")
        GLib.timeout_add(120, lambda: (self.vector.visible and self.vector.keyboard("on_demand"), False)[1])

    def focus_vector(self):
        """SUPER+E: the window was just mapped on-demand, so the compositor gave it the
        keyboard; put the caret in the entry. A click on any other window takes it back."""
        self.entry.grab_focus()

    GREET_AFTER_IDLE = 4 * 3600      # greet again only after this long without a word

    def show_vector(self, focus=True, greet=True):
        """greet: the hello is for SUPER+E only, once per session (or after a long quiet
        spell); never when VECTOR is opened by push-to-talk or an ask, so it can't talk
        over the operator or into the mic."""
        self.ensure_vector()
        quiet_for = time.monotonic() - getattr(self, "last_word", -1e9)
        first = greet and (not getattr(self, "greeted", False) or quiet_for > self.GREET_AFTER_IDLE)
        self.pscene.fade_to = 1.0
        was_hidden = not self.vector.visible
        self.vector.show(focus=focus)
        if was_hidden:
            self.pscene.catch_up()              # replies that came in while minimized: show them whole
        self.unread = 0
        self.hidden_since = None
        if self.voice and not self.voice.muted:
            self.voice.warm_tts()               # load the voice while the host types
        if focus:
            self.focus_vector()
        if first:
            from .vector.persona import GREETING
            self.greeted = True
            self.last_word = time.monotonic()
            self.pscene.set_state("speaking")
            self.pscene.feed(GREETING)
            self.pscene.end_reply()
            if self.voice:
                self.voice.say(GREETING)
        else:
            self.pscene.set_state("listening" if focus else self.pscene.avatar.state)
            GLib.timeout_add(900, lambda: (self.pscene.avatar.state == "listening" and self.pscene.set_state("idle"), False)[1])
        self.last_activity = time.monotonic()

    def summarize_conversation(self):
        """Hand the conversation since the last summary to Gnosis (infer=true), in the background."""
        if not (self.memory and self.brain) or self.brain.busy:
            return
        turns = self.brain.history[self.summarized_at:]
        if sum(1 for m in turns if m.get("role") == "user") < 2:
            return
        self.summarized_at = len(self.brain.history)
        threading.Thread(target=self.memory.summarize, args=(turns,), daemon=True, name="memory-summary").start()

    def hide_vector(self):
        """Minimize: the window goes, VECTOR keeps working (turn, tools, voice)."""
        if self.vector and self.vector.visible:
            self.pscene.fade_to = 0.0
            self.hidden_since = time.monotonic()
            GLib.timeout_add(260, lambda: (self.vector.hide() if self.pscene.fade_to == 0 else None, False)[1])

    def toggle_vector(self):
        if self._vector_shown():
            self.hide_vector()
        else:
            self.show_vector()

    def _voice_label(self):
        if not self.voice:
            return "TYPED · VOICE NOT SET UP"
        if self.voice.muted:
            return "VOICE MUTED · SUPER+SHIFT+V"
        mode = "VOICES AUTO" if self.voice.mode == "auto" else f"VOICE PINNED: {self.voice.mode.upper()}"
        return f"{mode} · HOLD SUPER+V TO TALK"

    def set_voice_mode(self, mode):
        v = self.ensure_voice()
        if not v:
            raise RuntimeError("voice unavailable")
        m = v.set_mode(mode)
        self.pscene.voice = self._voice_label()
        if m != "auto":
            self.pscene.set_voice(m, True)          # show the pinned voice's colour right away
        return m

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
        self.ensure_vector()
        if self.voice is None:
            try:
                from .vector.voice import Voice
                self.voice = Voice(self)
            except Exception as e:
                log("voice unavailable:", e)
                self.voice = None
        self.pscene.voice = self._voice_label()
        return self.voice

    # ------------------------------------------------------------------ housekeeping
    def _idle_check(self):
        # VECTOR steps back after a quiet two minutes once it has finished talking (unless you're typing)
        if self._vector_shown() and not self.busy() and not self.pscene.revealing() and not self.focused \
                and not self.conversation_on():
            if time.monotonic() - self.last_activity > 120:
                self.hide_vector()
        if self.vector and time.monotonic() - self.last_activity > 600:
            self.summarize_conversation()            # a quiet ten minutes ends a conversation
        return True

    def busy(self):
        """A turn is running or speech is queued/playing: never exit or drop it."""
        return bool((self.brain and self.brain.busy) or (self.voice and self.voice.active()))

    def vector_state(self):
        if not self.vector:
            return "off"
        if self.voice and self.voice.rec:
            return "listening"
        if self.conversation_on() and not (self.brain and self.brain.busy) and not self.voice.speaking:
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
        st = {"state": self.vector_state(), "unread": self.unread, "shown": self._vector_shown(),
              "model": self.brain.model if self.brain else None,
              "muted": bool(self.voice and self.voice.muted),
              "voice_mode": self.voice.mode if self.voice else "auto",
              "conversation": self.conversation_on(),
              "voice": getattr(self.pscene, "voice_role", "main") if self.vector else "main",
              "mood": self.pscene.mood_name() if self.vector else "calm"}
        sig = json.dumps(st, sort_keys=True)
        if sig != self._state_sig:
            self._state_sig = sig
            tmp = VECTOR_STATE + ".part"
            with open(tmp, "w") as f:
                f.write(sig)
            os.replace(tmp, VECTOR_STATE)
            try:
                import subprocess
                subprocess.Popen(["pkill", f"-RTMIN+{WAYBAR_SIGNAL}", "-x", "waybar"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                pass
        return True

    def status(self):
        out = {"pid": os.getpid()}
        for k, w in (("vector", self.vector), ("gallery", self.gallery)):
            if w:
                out[k] = {"visible": w.visible, "fps": w.fps, "frames": w.frames, "frame_ms": round(w.frame_ms, 2)}
        if self.vector:
            out["vector"].update(state=self.vector_state(), unread=self.unread, focused=self.focused,
                                model=self.brain.model, input_rects=list(self.vector.input_rects),
                                entry_text=self.entry.get_text())
        if self.voice:
            out["voice"] = self.voice.status()
        return json.dumps(out)

    def command(self, cmd):
        parts = cmd.strip().split(" ", 1)
        verb, arg = parts[0], (parts[1] if len(parts) > 1 else "")
        if verb == "vector":
            self.toggle_vector()
        elif verb == "vector-show":
            self.show_vector()
        elif verb == "vector-hide":
            self.hide_vector()
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
                if self.vector:
                    self.pscene.voice = self._voice_label()
                return "muted" if v.muted else "unmuted"
            return "voice unavailable"
        elif verb == "snap":
            name, _, path = arg.partition(" ")
            w = {"vector": self.vector, "gallery": self.gallery}.get(name)
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
        elif verb == "say":                # the build watcher (another process) speaks through here
            self._herdr_notice(arg[:300])
            return "ok"
        elif verb == "history":
            if arg.startswith("open "):        # open the Nth conversation (1 = newest); for scripts and tests
                from .vector import history
                ss = history.sessions()
                n = int(arg.split()[1]) - 1
                if not self.histpanel.get_visible():
                    self.toggle_history()
                self._history_open(ss[n]["id"])
                return "opened " + ss[n]["title"][:40]
            if arg == "continue":              # carry on with the open conversation (scripts and tests)
                if not self.hist_open_id:
                    return "no conversation open"
                self._history_continue()
                return "continuing"
            return self.toggle_history()
        elif verb == "shell":
            from .vector.shell import RUNNER, enabled, set_enabled
            if arg in ("off", "on"):
                if arg == "off":
                    RUNNER.kill("terminal switched off")
                return "terminal " + ("on" if set_enabled(arg == "on") else "off")
            if arg == "stop":
                return self.shell_stop()
            return "terminal " + ("on" if enabled() else "off")
        elif verb == "conversation":
            return self.toggle_conversation()
        elif verb == "voice":
            try:
                return "voice " + self.set_voice_mode(arg.strip() or "cycle")
            except Exception as e:
                return f"error: {e}"
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


def migrate_from_pilot():
    """VECTOR was PILOT: carry its logs, mute choice and line cache over, once."""
    import shutil
    st = os.path.expanduser("~/.local/state/bromigos")
    for old, new in (("pilot-chat.log", "vector-chat.log"), ("pilot-audit.log", "vector-audit.log"),
                     ("pilot-voice-muted", "vector-voice-muted")):
        o, n = os.path.join(st, old), os.path.join(st, new)
        if os.path.exists(o):
            if os.path.exists(n) and old.endswith(".log"):
                with open(o) as fo, open(n) as fn:
                    merged = fo.read() + fn.read()
                with open(n, "w") as f:
                    f.write(merged)
                os.unlink(o)
            elif not os.path.exists(n):
                shutil.move(o, n)
            else:
                os.unlink(o)
    oc, nc = os.path.expanduser("~/.cache/bromigos/pilot-tts"), os.path.expanduser("~/.cache/bromigos/vector-tts")
    if os.path.isdir(oc):          # PILOT's voice lines: a different voice, no use to VECTOR
        shutil.rmtree(oc, ignore_errors=True)


def main():
    migrate_from_pilot()
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, lambda *a: Gtk.main_quit())
    app = App()
    log("ready on", SOCK)
    Gtk.main()
    if app.voice:
        app.voice.stop()                     # no orphaned player keeps talking after the daemon
        if getattr(app.voice, "conv", None):
            app.voice.conv.stop()
        app.voice.drop_aec()
    for p in (SOCK, VECTOR_STATE):
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
