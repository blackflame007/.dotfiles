"""Hyprland IPC without spawning hyprctl: request socket for state queries,
event socket (socket2) on a thread for workspace/fullscreen/window events."""
import json
import os
import socket
import threading
import time


def _sig():
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    base = os.path.join(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"), "hypr")
    if sig and os.path.exists(os.path.join(base, sig, ".socket.sock")):
        return base, sig
    try:
        dirs = sorted((os.path.join(base, d) for d in os.listdir(base)), key=os.path.getmtime, reverse=True)
        for d in dirs:
            if os.path.exists(os.path.join(d, ".socket.sock")):
                return base, os.path.basename(d)
    except OSError:
        pass
    return base, sig or ""


def request(cmd, as_json=True):
    base, sig = _sig()
    path = os.path.join(base, sig, ".socket.sock")
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect(path)
            s.sendall((("j/" if as_json else "") + cmd).encode())
            chunks = []
            while True:
                b = s.recv(65536)
                if not b:
                    break
                chunks.append(b)
        out = b"".join(chunks).decode(errors="replace")
        return json.loads(out) if as_json else out
    except (OSError, ValueError):
        return None


def monitor_state(name):
    """(active workspace has windows, a client there is in TRUE fullscreen, monitor).
    Maximize (fullscreen mode 1) does not count: the layer still shows in the gaps."""
    mons = request("monitors") or []
    mon = next((m for m in mons if m.get("name") == name), None)
    if not mon:
        return False, False, None
    ids = {(mon.get("activeWorkspace") or {}).get("id")}
    special = (mon.get("specialWorkspace") or {}).get("id") or 0
    if special:
        ids.add(special)
    windows = full = False
    for c in request("clients") or []:
        if (c.get("workspace") or {}).get("id") in ids and c.get("mapped", True) and not c.get("hidden"):
            windows = True
            if c.get("fullscreen") == 2:
                full = True
    return windows, full, mon


def layers_on(name):
    data = request("layers") or {}
    return (data.get(name) or {}).get("levels", {})


class Events(threading.Thread):
    def __init__(self, cb):
        super().__init__(daemon=True, name="hypr-events")
        self.cb = cb

    def run(self):
        while True:
            base, sig = _sig()
            path = os.path.join(base, sig, ".socket2.sock")
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                    s.connect(path)
                    buf = b""
                    while True:
                        b = s.recv(4096)
                        if not b:
                            break
                        buf += b
                        while b"\n" in buf:
                            line, buf = buf.split(b"\n", 1)
                            ev, _, arg = line.decode(errors="replace").partition(">>")
                            self.cb(ev, arg)
            except OSError:
                pass
            time.sleep(2)
