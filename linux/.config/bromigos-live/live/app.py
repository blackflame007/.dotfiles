"""bromigos-live daemon: one GTK process hosting the background layer, the
event overlays (intercept, transmission, screensaver), the holo deck and the
radial menu. Controlled over a unix socket by bin/bromigos-live."""
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
from gi.repository import Gdk, Gio, GLib, Gtk, GtkLayerShell  # noqa: E402

from OpenGL import GL  # noqa: E402

from . import config, hypr  # noqa: E402
from .data import Data  # noqa: E402
from .sound import Sound, toggle_mute  # noqa: E402
from .watch import LockWatch, Notifications  # noqa: E402

RUNTIME = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
SOCK = os.path.join(RUNTIME, "bromigos-live.sock")


def log(*a):
    print("bromigos-live:", *a, flush=True)


def find_monitor(name):
    display = Gdk.Display.get_default()
    mons = [display.get_monitor(i) for i in range(display.get_n_monitors())]
    info = next((m for m in (hypr.request("monitors") or []) if m.get("name") == name), None)
    if info:
        for m in mons:
            g = m.get_geometry()
            if g.x == info["x"] and g.y == info["y"]:
                return m, (info["width"], info["height"])
    m = mons[0] if mons else None
    g = m.get_geometry() if m else None
    return m, ((g.width, g.height) if g else (2560, 1440))


def layer_window(monitor, layer, namespace, anchors="tblr", keyboard=None, exclusive=-1):
    win = Gtk.Window()
    GtkLayerShell.init_for_window(win)
    GtkLayerShell.set_layer(win, layer)
    GtkLayerShell.set_namespace(win, namespace)
    if monitor:
        GtkLayerShell.set_monitor(win, monitor)
    for ch, edge in (("t", GtkLayerShell.Edge.TOP), ("b", GtkLayerShell.Edge.BOTTOM),
                     ("l", GtkLayerShell.Edge.LEFT), ("r", GtkLayerShell.Edge.RIGHT)):
        GtkLayerShell.set_anchor(win, edge, ch in anchors)
    GtkLayerShell.set_exclusive_zone(win, exclusive)
    GtkLayerShell.set_keyboard_mode(win, keyboard or GtkLayerShell.KeyboardMode.NONE)
    vis = win.get_screen().get_rgba_visual()
    if vis:
        win.set_visual(vis)
    win.set_app_paintable(True)
    return win


class GLWindow:
    """A layer-shell window with one GLArea driven by a timer at a set fps."""

    def __init__(self, app, layer, namespace, make_renderer, keyboard=None, alpha=False, input_ok=True):
        self.app = app
        self.mon, self.size = find_monitor(app.cfg["general"]["monitor"])
        self.win = layer_window(self.mon, layer, namespace, keyboard=keyboard)
        self.area = Gtk.GLArea()
        self.area.set_required_version(3, 3)
        self.area.set_has_alpha(alpha)
        self.area.set_auto_render(False)
        self.make_renderer = make_renderer
        self.renderer = None
        self.fps = 0
        self.timer = None
        self.failed = False
        self.frames = 0
        self.ticks = 0
        self.last_frame = 0.0
        self.area.connect("realize", self._realize)
        self.area.connect("unrealize", self._unrealize)
        self.area.connect("render", self._render)
        self.win.add(self.area)
        if not input_ok:
            self.win.connect("realize", lambda w: w.get_window().input_shape_combine_region(
                __import__("cairo").Region(), 0, 0))
        self.win.show_all()

    def _realize(self, area):
        area.make_current()
        if area.get_error():
            log("GL context error:", area.get_error())
            self.failed = True

    def _unrealize(self, area):
        self.renderer = None
        self.rsize = None

    rsize = None

    def _render(self, area, ctx):
        if self.failed:
            GL.glClearColor(0, 0, 0, 0)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT)
            return True
        sf = area.get_scale_factor()
        size = (area.get_allocated_width() * sf, area.get_allocated_height() * sf)
        if size[0] < 16 or size[1] < 16:
            return True
        if self.renderer is None or size != self.rsize:
            try:
                self.renderer = self.make_renderer(*size)
                self.rsize = size
            except Exception as e:
                import traceback
                traceback.print_exc()
                log("renderer init failed:", e)
                self.failed = True
                return True
        fbo = GL.glGetIntegerv(GL.GL_DRAW_FRAMEBUFFER_BINDING)
        self.frames += 1
        self.last_frame = time.monotonic()
        try:
            self.renderer.render(int(fbo), self.fps or 1)
        except Exception:
            import traceback
            traceback.print_exc()
            self.failed = True
            self.set_fps(0)
        return True

    def set_fps(self, fps):
        fps = 0 if self.failed else fps
        if fps == self.fps and (self.timer or not fps):
            return
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = None
        self.fps = fps
        if fps > 0:
            self.timer = GLib.timeout_add(max(int(1000 / fps), 8), self._tick, priority=GLib.PRIORITY_DEFAULT)
            self.area.queue_render()

    def _tick(self):
        self.ticks += 1
        self.area.queue_render()
        return True

    def destroy(self):
        self.set_fps(0)
        self.win.destroy()


class App:
    def __init__(self, login=False):
        self.cfg = config.load()
        self.sound = Sound(self.cfg)
        self.data = Data(self.cfg, self.on_data_event)
        self.bg = None
        self.bg_enabled = bool(self.cfg["background"].get("enabled", True))
        self.locked = False
        self.covered = False
        self.fullscreen = False
        self.overlays = {}
        self.cfg_mtime = self._mtime()
        self.data.start()
        if self.bg_enabled:
            self.show_background()
        hypr.Events(lambda ev, arg: GLib.idle_add(self.on_hypr, ev, arg)).start()
        self.notif = Notifications(self.on_notify)
        self.notif.start()
        LockWatch(self.on_lock).start()
        self._serve()
        GLib.timeout_add_seconds(3, self._watch_config)
        GLib.idle_add(self.refresh_state)
        if login and self.cfg["events"].get("intercept_on_login", True):
            GLib.timeout_add(1200, lambda: (self.overlay("intercept"), False)[1])

    # ------------------------------------------------------------------ layers
    def show_background(self):
        if self.bg:
            return
        from .scene import Background

        def make(w, h):
            return Background(self.cfg, self.data, w, h)
        self.bg = GLWindow(self, GtkLayerShell.Layer.BACKGROUND, "bromigos-live", make, input_ok=False)
        self.refresh_state()

    def hide_background(self):
        if self.bg:
            self.bg.destroy()
            self.bg = None

    def toggle_background(self):
        self.bg_enabled = not self.bg_enabled
        (self.show_background if self.bg_enabled else self.hide_background)()

    def overlay(self, kind, **kw):
        from . import overlays
        cur = self.overlays.get(kind)
        if cur and kind in ("holodeck", "radial", "screensaver"):
            cur.close()
            return
        if cur:
            cur.close()
        try:
            self.overlays[kind] = overlays.make(self, kind, **kw)
        except Exception:
            import traceback
            traceback.print_exc()
        self.refresh_state()

    def overlay_closed(self, kind, obj):
        if self.overlays.get(kind) is obj:
            del self.overlays[kind]
        self.refresh_state()

    # ------------------------------------------------------------------ state
    mode = "starting"

    def refresh_state(self):
        windows, full, _mon = hypr.monitor_state(self.cfg["general"]["monitor"])
        self.covered, self.fullscreen = windows, full
        g = self.cfg["general"]
        own_full = [k for k in ("screensaver", "holodeck") if k in self.overlays]
        if self.locked:
            mode, why = "paused", "session locked"
        elif full:
            mode, why = "paused", "fullscreen window"
        elif own_full:
            mode, why = "paused", f"{own_full[0]} on top"
        elif windows:
            mode, why = "idle", "windows tiled over it"
        else:
            mode, why = "running", "desktop visible"
        fps = 0 if mode == "paused" else int(g.get("fps_covered", 20) if mode == "idle" else g.get("fps", 30))
        self.data.paused = mode == "paused" and not own_full
        if self.bg:
            self.bg.set_fps(fps)
        if (mode, why) != getattr(self, "_last_mode", None):
            log(f"{mode} ({why}) fps={fps if self.bg else 0}")
            self._last_mode = (mode, why)
        self.mode = mode
        return False

    def describe(self):
        bg = self.bg
        if not self.bg_enabled or not bg:
            mode = "off"
        else:
            mode = self.mode
        out = [f"background {mode} fps={bg.fps if bg else 0}"]
        if bg:
            now = time.monotonic()
            f0, t0 = getattr(self, "_probe", (bg.frames, now - 1))
            rate = (bg.frames - f0) / max(now - t0, 1e-3)
            self._probe = (bg.frames, now)
            out.append(f"frames={bg.frames} ticks={bg.ticks} measured={rate:.1f}/s since last status "
                       f"last_frame={now - bg.last_frame:.1f}s ago failed={bg.failed}")
        out.append(f"windows={self.covered} fullscreen={self.fullscreen} locked={self.locked} "
                   f"overlays={sorted(self.overlays)}")
        return "\n".join(out)

    def on_hypr(self, ev, arg):
        if ev in ("workspacev2", "fullscreen", "openwindow", "closewindow", "movewindowv2",
                  "focusedmon", "activespecial", "changefloatingmode", "monitoradded", "monitorremoved"):
            self.refresh_state()
        if ev == "workspacev2" and self.bg:
            self.bg.renderer and self.bg.renderer.wipe()
        if ev == "openwindow":
            parts = arg.split(",", 3)
            if len(parts) >= 3 and parts[2] in self.cfg["sounds"].get("terminal_classes", []):
                self.sound.play("terminal")
        return False

    def on_lock(self, locked):
        was = self.locked
        self.locked = locked
        if locked:
            for k in ("screensaver", "holodeck", "radial"):
                if k in self.overlays:
                    self.overlays[k].close()
        elif was and self.cfg["events"].get("intercept_on_unlock", True):
            GLib.timeout_add(150, lambda: (self.overlay("intercept"), False)[1])
        self.refresh_state()
        return False

    def on_notify(self, what, a, b, c):
        if what == "notify":
            app_name, summary, urgency = a, b, c
            if app_name == "bromigos-live":
                return False
            if self.bg and self.bg.renderer:
                self.bg.renderer.burst(2 if urgency >= 2 else 0)
            if urgency >= 2 and self.cfg["events"].get("critical_flash", True) and not self.locked:
                self.sound.play("critical")
                self.overlay("transmission", summary=summary)
            else:
                self.sound.play("notify")
        elif what == "closed":
            ov = self.overlays.get("transmission")
            if ov:
                ov.dismissed()
        return False

    def on_data_event(self, kind, **info):
        def go():
            if self.bg and self.bg.renderer:
                self.bg.renderer.burst(1 if kind == "arbiter_fill" else 2)
            return False
        GLib.idle_add(go)

    # ------------------------------------------------------------------ control
    def _serve(self):
        try:
            os.unlink(SOCK)
        except OSError:
            pass
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(SOCK)
        srv.listen(4)

        def loop():
            while True:
                conn, _ = srv.accept()
                with conn:
                    try:
                        cmd = conn.recv(256).decode().strip()
                        done = threading.Event()
                        out = {}

                        def run():
                            out["r"] = self.command(cmd)
                            done.set()
                            return False
                        GLib.idle_add(run)
                        done.wait(3)
                        conn.sendall((out.get("r") or "ok").encode())
                    except OSError:
                        pass
        threading.Thread(target=loop, daemon=True, name="ctl").start()

    def command(self, cmd):
        c, _, arg = cmd.partition(" ")
        if c == "ping":
            return "pong"
        if c == "state":
            return self.describe()
        if c == "toggle":
            self.toggle_background()
            return "background " + ("on" if self.bg_enabled else "off")
        if c == "mute":
            return "muted" if toggle_mute() else "unmuted"
        if c in ("intercept", "holodeck", "radial", "screensaver"):
            if c == "screensaver" and not self.cfg["screensaver"].get("enabled", True):
                return "screensaver disabled"
            self.overlay(c)
            return c
        if c == "screensaver-off":
            if "screensaver" in self.overlays:
                self.overlays["screensaver"].close()
            return "ok"
        if c == "transmission":
            self.overlay("transmission", summary=arg or "TEST TRANSMISSION")
            return "ok"
        if c == "burst":
            if self.bg and self.bg.renderer:
                self.bg.renderer.burst(int(arg or 0))
            return "ok"
        if c == "reload":
            self.reload()
            return "reloaded"
        if c == "quit":
            Gtk.main_quit()
            return "bye"
        return "unknown command"

    def _mtime(self):
        try:
            return os.path.getmtime(config.PATH)
        except OSError:
            return 0

    def _watch_config(self):
        m = self._mtime()
        if m != self.cfg_mtime:
            self.cfg_mtime = m
            self.reload()
        return True

    def reload(self):
        new = config.load()
        self.cfg.clear()
        self.cfg.update(new)
        if self.bg:
            self.hide_background()
        self.bg_enabled = bool(self.cfg["background"].get("enabled", True))
        if self.bg_enabled:
            self.show_background()


def main():
    login = "--login" in sys.argv
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, lambda *a: GLib.idle_add(Gtk.main_quit))
    App(login=login)
    Gtk.main()
    try:
        os.unlink(SOCK)
    except OSError:
        pass


if __name__ == "__main__":
    main()
