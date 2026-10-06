"""VECTOR's event feed, consumed by the holograms.

VECTOR (holo/vector, Pydantic AI brain) appends one JSON object per line to
$XDG_RUNTIME_DIR/bromigos-vector-events.jsonl; the schema is documented in
bromigos/holo/README.md ("VECTOR's event feed"). His state is in
$XDG_RUNTIME_DIR/bromigos-vector.json.

This reader tails the file only while a hologram is open (a stat every 0.25 s,
a read only when it grew), keeps the last 400 events so a hologram opened a
moment after an event still sees it, and hands each consumer the events it has
not seen yet: feed.poll(cursor) -> (events, cursor).
"""
import json
import os
import threading
import time

RUN = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
PATH = os.environ.get("BROMIGOS_VECTOR_EVENTS") or os.path.join(RUN, "bromigos-vector-events.jsonl")
STATE = os.path.join(RUN, "bromigos-vector.json")
KEEP = 400


class Feed:
    _inst = None

    @classmethod
    def get(cls):
        if cls._inst is None:
            cls._inst = Feed()
        return cls._inst

    def __init__(self):
        self.lock = threading.Lock()
        self.events = []          # (seq, event dict)
        self.seq = 0
        self.users = 0
        self.thread = None
        self.pos = 0
        self.ino = None
        self._seed()

    def _seed(self):
        """The last 10 minutes of the file, so a fresh hologram has context."""
        try:
            with open(PATH, "rb") as f:
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(0, size - 256 * 1024))
                lines = f.read().decode(errors="replace").splitlines()
            if size > 256 * 1024:
                lines = lines[1:]                 # the first line is probably cut
            cut = time.time() - 600
            for line in lines[-KEEP:]:
                e = self._parse(line)
                if e and e.get("t", 0) >= cut:
                    self._push(e)
            st = os.stat(PATH)
            self.pos, self.ino = st.st_size, st.st_ino
        except OSError:
            pass

    @staticmethod
    def _parse(line):
        try:
            e = json.loads(line)
            return e if isinstance(e, dict) and e.get("type") else None
        except ValueError:
            return None

    def _push(self, e):
        with self.lock:
            self.seq += 1
            self.events.append((self.seq, e))
            del self.events[:-KEEP]

    def acquire(self):
        self.users += 1
        if not (self.thread and self.thread.is_alive()):
            self.thread = threading.Thread(target=self._loop, daemon=True, name="vector-feed")
            self.thread.start()

    def release(self):
        self.users = max(0, self.users - 1)

    def _loop(self):
        while self.users > 0:
            try:
                st = os.stat(PATH)
                if st.st_ino != self.ino or st.st_size < self.pos:     # rotated or truncated
                    self.ino, self.pos = st.st_ino, 0
                if st.st_size > self.pos:
                    with open(PATH, "rb") as f:
                        f.seek(self.pos)
                        chunk = f.read()
                    nl = chunk.rfind(b"\n")
                    if nl >= 0:
                        self.pos += nl + 1
                        for line in chunk[:nl].decode(errors="replace").splitlines():
                            e = self._parse(line)
                            if e:
                                e.setdefault("t", time.time())
                                self._push(e)
            except OSError:
                pass
            time.sleep(0.25)

    def poll(self, cursor=0, types=None):
        with self.lock:
            out = [e for s, e in self.events if s > cursor and (types is None or e.get("type") in types)]
            return out, self.seq

    def recent(self, types=None, seconds=600):
        cut = time.time() - seconds
        with self.lock:
            return [e for _, e in self.events if e.get("t", 0) >= cut and (types is None or e.get("type") in types)]

    def inject(self, e):
        """Events the desktop itself observes (a push seen in git, a pod restart seen in
        Prometheus) join the same stream, marked source=desktop."""
        e = dict(e, source=e.get("source", "desktop"))
        e.setdefault("t", time.time())
        self._push(e)


def vector_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}
