"""Readings only the worlds need, polled only while a world is up:

  agents   herdr's agents (the Swarm deck's data: `herdr api snapshot`, ~8 ms), every
           2 s; every 8 s while the layer is paused. Each: key, status (working,
           needs_you, finished; error counts as needs_you with a danger signal), cwd.
  vector   VECTOR's state from $XDG_RUNTIME_DIR/bromigos-vector.json (written by his
           daemon on every change): off (no file / stale daemon), idle, thinking,
           speaking, listening, error. A stat every 0.5 s; read only when it changed.
"""
import json
import os
import threading
import time

from . import sources

RUNTIME = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
VECTOR_FILE = os.path.join(RUNTIME, "bromigos-vector.json")


def agent_status(a):
    """herdr's agent_status as a world state (same reading as the Swarm deck's status_of)."""
    s = (a.get("agent_status") or "").lower()
    if s in ("working", "busy", "running"):
        return "working", False
    if s in ("blocked", "waiting", "needs_input", "permission", "attention"):
        return "needs_you", False
    if s in ("error", "failed", "crashed", "exited"):
        return "needs_you", True
    return "finished", False


class Feed:
    def __init__(self, data):
        self.data = data            # live.data.Data: its .paused slows the polls
        self.agents = []
        self.agents_ok = False
        self.vector = "off"
        self.stop = threading.Event()
        self._vsig = None
        self.first_seen = {}        # agent key -> when first seen: a stable order (the first few are the foreground)

    def start(self):
        threading.Thread(target=self._herdr_loop, daemon=True, name="world-herdr").start()
        threading.Thread(target=self._vector_loop, daemon=True, name="world-vector").start()

    def halt(self):
        self.stop.set()

    def _herdr_loop(self):
        while not self.stop.is_set():
            try:
                raw = sources.herdr()
                out = []
                for a in raw:
                    st, err = agent_status(a)
                    key = a.get("terminal_id") or a.get("pane_id") or json.dumps(a.get("agent_session"))
                    out.append({"key": str(key), "status": st, "error": err, "cwd": a.get("cwd") or "",
                                "name": a.get("agent") or a.get("name") or ""})
                now = time.time()
                for a in out:
                    self.first_seen.setdefault(a["key"], now)
                live = {a["key"] for a in out}
                self.first_seen = {k: v for k, v in self.first_seen.items() if k in live}
                out.sort(key=lambda a: (self.first_seen[a["key"]], a["key"]))
                self.agents = out
                self.agents_ok = True
            except Exception:
                self.agents_ok = False
            self.stop.wait(8.0 if getattr(self.data, "paused", False) else 2.0)

    def _vector_loop(self):
        while not self.stop.is_set():
            try:
                st = os.stat(VECTOR_FILE)
                sig = (st.st_mtime_ns, st.st_size)
                if sig != self._vsig:
                    self._vsig = sig
                    with open(VECTOR_FILE) as f:
                        self.vector = str(json.load(f).get("state") or "idle")
            except (OSError, ValueError):
                self._vsig = None
                self.vector = "off"
            self.stop.wait(2.0 if getattr(self.data, "paused", False) else 0.5)
