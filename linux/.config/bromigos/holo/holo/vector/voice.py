"""VECTOR's voice, desktop side (system python, inside the holo daemon).

Push-to-talk: SUPER+V down starts `pw-record` (16 kHz mono, raw to a pipe) and VECTOR
shows LISTENING with a live MIC indicator; key up stops it at once. Nothing records
unless the key is held, and a recording is cut at `max_record_seconds` in case a
release is missed.

VECTOR never hears itself (the operator has speakers, not headphones):
  * barge-in: SUPER+V down kills playback, clears the speech queue and interrupts the
    running turn, like talking over someone;
  * nothing is spoken while the mic is open, and the first `drain_ms` of a recording that
    starts right after playback is dropped (audio still draining from the speakers);
  * echo cancellation (voice.json "echo_cancel"): a session-only PipeWire webrtc AEC pair,
    vector_aec_sink -> the default speakers and the default mic -> vector_aec_source. VECTOR
    plays into the sink and records from the source, so its own voice is the reference
    that gets subtracted. Defaults are untouched; the nodes sit suspended (no CPU) when
    unused, and they are rebuilt if the default devices change;
  * a transcript that matches what VECTOR said in the last 30 s is dropped. Audio goes to the venv voice server for speech-to-text; the text
is asked like typed text. Replies are spoken sentence by sentence as they stream in
(TTS cached on disk); SUPER+SHIFT+V mutes the voice (persisted). There is no hotword.
"""
import json
import os
import re
import site
import socket
import subprocess
import tempfile
import threading
import time
import wave

import numpy as np
from gi.repository import GLib

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONF = os.path.join(HERE, "voice.json")
VENV = os.path.expanduser("~/.local/share/bromigos/venv-tts")   # py3.12 + torch: Qwen3-TTS, whisper, kokoro
RUNTIME = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
SOCK = os.path.join(RUNTIME, "bromigos-holo-voice.sock")
STATE = os.path.expanduser("~/.local/state/bromigos")
MUTED = os.path.join(STATE, "vector-voice-muted")
LOG = os.path.join(STATE, "holo-voice.log")
SENT_END = re.compile(r"(.+?[.!?…]+)(\s+|$)", re.S)


def _venv_env():
    env = dict(os.environ)
    sp = next(iter(__import__("glob").glob(os.path.join(VENV, "lib/python3*/site-packages"))), "")
    libs = [os.path.join(sp, "nvidia", d, "lib") for d in ("cublas", "cudnn", "cuda_runtime", "cuda_nvrtc")]
    env["LD_LIBRARY_PATH"] = ":".join([p for p in libs if os.path.isdir(p)] + [env.get("LD_LIBRARY_PATH", "")])
    env["HF_HUB_DISABLE_TELEMETRY"] = "1"
    return env


class Voice:
    def __init__(self, app):
        self.app = app
        with open(CONF) as f:
            self.cfg = json.load(f)
        self.cfg["sink"] = os.environ.get("BROMIGOS_HOLO_SINK") or self.cfg.get("sink")   # e.g. a headset node
        self.muted = os.path.exists(MUTED)
        self.rec = None
        self.rec_buf = bytearray()
        self.rec_t0 = 0.0
        self.player = None
        self.queue = []            # sentences waiting to be spoken
        self.pending = ""          # streamed text not yet a full sentence
        self.speaking = False
        self.qlock = threading.Lock()
        self.gen = 0               # bumps on stop(): stale audio is dropped
        self.last_stats = {}
        self.server_proc = None
        self.play_end = 0.0        # when playback last stopped (monotonic)
        self.skip_until = 0.0      # mic audio before this is speaker drain, dropped
        self.said = []             # (monotonic, sentence) VECTOR spoke recently
        self.aec = None            # (module id, sink master, source master)

    # ------------------------------------------------------------------ server
    def _req(self, obj, timeout=30.0):
        for attempt in range(2):
            try:
                s = socket.socket(socket.AF_UNIX)
                s.settimeout(timeout)
                s.connect(SOCK)
                s.sendall((json.dumps(obj) + "\n").encode())
                buf = b""
                while not buf.endswith(b"\n"):
                    chunk = s.recv(65536)
                    if not chunk:
                        break
                    buf += chunk
                s.close()
                out = json.loads(buf.decode() or "{}")
                if out.get("error"):
                    raise RuntimeError(out["error"])
                return out
            except (FileNotFoundError, ConnectionRefusedError):
                if attempt:
                    raise
                self._spawn()

    def _spawn(self):
        os.makedirs(STATE, exist_ok=True)
        if not (self.server_proc and self.server_proc.poll() is None):
            self.server_proc = subprocess.Popen([os.path.join(VENV, "bin/python"), "-m", "holo.voice_server"], cwd=HERE,
                                                env=_venv_env(), stdin=subprocess.DEVNULL, stdout=open(LOG, "a"),
                                                stderr=subprocess.STDOUT, start_new_session=True)
        for _ in range(100):
            if os.path.exists(SOCK):
                try:
                    s = socket.socket(socket.AF_UNIX)
                    s.connect(SOCK)
                    s.close()
                    return
                except OSError:
                    pass
            time.sleep(0.1)

    # ------------------------------------------------------------------ listening
    # ------------------------------------------------------------------ echo cancellation
    def _pactl(self, *args):
        return subprocess.run(["pactl", *args], capture_output=True, text=True, timeout=5).stdout.strip()

    def ensure_aec(self):
        """The AEC pair on the current default devices; None when off or unavailable."""
        if not self.cfg.get("echo_cancel", True) or self.cfg.get("sink"):
            return None
        try:
            sink, src = self._pactl("get-default-sink"), self._pactl("get-default-source")
            if not sink or not src or sink.startswith("vector_aec") or src.startswith("vector_aec"):
                return None
            mods = self._pactl("list", "short", "modules")
            if self.aec and self.aec[1:] == (sink, src) and f"{self.aec[0]}\t" in mods + "\t":
                return self.aec
            for line in mods.splitlines():          # ours from an earlier run, or on old devices
                if "vector_aec_source" in line:
                    self._pactl("unload-module", line.split()[0])
            mid = self._pactl("load-module", "module-echo-cancel", "aec_method=webrtc",
                              f"source_master={src}", f"sink_master={sink}",
                              "source_name=vector_aec_source", "sink_name=vector_aec_sink",
                              "rate=16000", "channels=1")
            self.aec = (mid, sink, src) if mid.isdigit() else None
        except (OSError, subprocess.TimeoutExpired):
            self.aec = None
        return self.aec

    def drop_aec(self):
        if self.aec:
            try:
                self._pactl("unload-module", self.aec[0])
            except (OSError, subprocess.TimeoutExpired):
                pass
            self.aec = None

    # ------------------------------------------------------------------ listening
    def ptt_down(self):
        if self.rec:
            return
        was_speaking = self.speaking or (self.player and self.player.poll() is None)
        self.stop()                                   # barge-in: talking over VECTOR stops it
        if self.app.brain:
            self.app.brain.interrupt()                # ... and the turn it was answering
        self.app.pscene.end_reply()
        # speaker drain: drop the first part of the recording if VECTOR was just talking
        drain = self.cfg.get("drain_ms", 350) / 1000
        self.skip_until = time.monotonic() + drain if (was_speaking or time.monotonic() - self.play_end < drain) else 0.0
        self.app.show_vector(focus=False, greet=False)
        sc = self.app.pscene
        sc.set_state("listening")
        sc.mic_live = True
        self.rec_buf = bytearray()
        self.rec_t0 = time.monotonic()
        aec = self.ensure_aec()
        self.rec = subprocess.Popen(["pw-record", "--raw", "--rate", "16000", "--channels", "1", "--format", "s16"]
                                    + (["--target", "vector_aec_source"] if aec else []) + ["-"],
                                    stdout=subprocess.PIPE, stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        threading.Thread(target=self._read_mic, args=(self.rec,), daemon=True).start()
        threading.Thread(target=lambda: self._safe(lambda: self._req({"op": "warm"}, 60)), daemon=True).start()
        GLib.timeout_add(int(self.cfg.get("max_record_seconds", 30) * 1000), self._watchdog, self.rec)

    def _watchdog(self, proc):
        if self.rec is proc:
            self.ptt_up()
        return False

    def _read_mic(self, proc):
        sc = self.app.pscene
        while True:
            chunk = proc.stdout.read(800)           # 25 ms
            if not chunk:
                break
            if time.monotonic() < self.skip_until:
                continue                            # VECTOR's voice still leaving the speakers
            self.rec_buf += chunk
            a = np.frombuffer(chunk[: len(chunk) // 2 * 2], np.int16).astype(np.float32) / 32768.0
            rms = float(np.sqrt(np.mean(a * a))) if len(a) else 0.0
            db = 20 * np.log10(max(rms, 1e-5))
            sc.avatar.level = max(0.0, min(1.0, (db + 55) / 40))

    def ptt_up(self):
        proc, self.rec = self.rec, None
        if not proc:
            return
        proc.terminate()
        try:
            proc.wait(1.0)
        except subprocess.TimeoutExpired:
            proc.kill()
        sc = self.app.pscene
        sc.mic_live = False
        secs = time.monotonic() - self.rec_t0
        data = bytes(self.rec_buf)
        self.rec_buf = bytearray()
        if secs < 0.35 or len(data) < 16000 * 2 * 0.3:
            sc.set_state("idle")
            return
        sc.set_state("thinking")
        sc.subtitle = "HEARING YOU"
        threading.Thread(target=self._transcribe, args=(data,), daemon=True).start()

    def _transcribe(self, data):
        fd, path = tempfile.mkstemp(prefix="vector-ptt-", suffix=".pcm", dir=RUNTIME)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            t0 = time.monotonic()
            out = self._req({"op": "stt", "pcm": path}, 60)
            self.last_stats = {"stt_ms": out.get("ms"), "stt_roundtrip_ms": int((time.monotonic() - t0) * 1000),
                               "audio_s": out.get("seconds")}
            text = (out.get("text") or "").strip()
            if len(re.sub(r"\W", "", text)) < 2:
                GLib.idle_add(self._heard_nothing)
                return
            if self._echo_of_self(text):
                self.last_stats["echo_rejected"] = text[:80]
                GLib.idle_add(self._heard_echo)
                return
            GLib.idle_add(self.app.ask, text)
        except Exception as e:
            GLib.idle_add(self.app._vector_error, f"voice: {e}")
        finally:
            os.unlink(path)

    def _echo_of_self(self, text):
        """True when the transcript is VECTOR's own recent speech coming back through the mic."""
        now = time.monotonic()
        recent = " ".join(s for t, s in self.said if now - t < 30)
        if not recent:
            return False
        words = lambda x: re.findall(r"[a-z0-9']+", x.lower())
        heard, spoke = words(text), words(recent)
        if len(heard) < 2:
            return False
        sset = set(spoke)
        contained = sum(w in sset for w in heard) / len(heard)
        import difflib
        run = difflib.SequenceMatcher(None, heard, spoke, autojunk=False).find_longest_match(0, len(heard), 0, len(spoke)).size
        # a verbatim stretch of its own words; loose word overlap is not enough, because the
        # operator often asks about exactly what VECTOR just said
        return run >= 4 or (run >= 3 and run >= 0.75 * len(heard)) or (contained == 1.0 and len(heard) >= 7)

    def _heard_echo(self):
        self.app.pscene.note("That was me talking, I think. Sorry! Hold SUPER+V and go ahead.")
        self.app.pscene.set_state("idle")

    def _heard_nothing(self):
        self.app.pscene.note("Sorry, I didn't catch that. Hold SUPER+V while you talk.")
        self.app.pscene.set_state("idle")

    # ------------------------------------------------------------------ speaking
    def feed(self, delta):
        """Streamed reply text: speak each sentence as soon as it is complete."""
        if self.muted:
            return
        self.pending += delta
        while True:
            m = SENT_END.match(self.pending)
            if not m or (m.end(1) == len(self.pending) and not m.group(2)):
                break
            end = m.end()
            # a "*stage direction*" can span sentence ends; wait for its closing
            # asterisk so spoken() drops it whole (up to a sane length)
            while self.pending[:end].count("*") % 2 and len(self.pending) < 600:
                nxt = SENT_END.match(self.pending, end)
                if not nxt or (nxt.end(1) == len(self.pending) and not nxt.group(2)):
                    end = None
                    break
                end = nxt.end()
            if end is None:
                break
            self._enqueue(self.pending[:end])
            self.pending = self.pending[end:]

    def flush(self):
        if self.pending.strip() and not self.muted:
            self._enqueue(self.pending)
        self.pending = ""

    def say(self, text):
        """A whole line (the greeting, a fixed phrase). Never while the mic is open."""
        if not self.muted and not self.rec:
            for m in SENT_END.finditer(text.strip() + " "):
                self._enqueue(m.group(1))

    def _enqueue(self, sentence):
        from .text import spoken
        s = re.sub(r"\s+", " ", spoken(sentence)).strip()
        if not re.search(r"\w", s):
            return
        with self.qlock:
            self.queue.append((self.gen, s))
            if not self.speaking:
                self.speaking = True
                threading.Thread(target=self._speak_loop, daemon=True).start()

    def _speak_loop(self):
        try:
            while True:
                with self.qlock:
                    if not self.queue:
                        break
                    gen, sentence = self.queue.pop(0)
                if gen != self.gen or self.muted:
                    continue
                self._stream(sentence, gen)
        except Exception as e:
            GLib.idle_add(self.app.pscene.note, f"(voice trouble: {str(e)[:80]})")
        finally:
            with self.qlock:
                self.speaking = False
            GLib.idle_add(self._done_speaking)

    def _open_stream(self, sentence):
        for attempt in range(2):
            try:
                s = socket.socket(socket.AF_UNIX)
                s.settimeout(30)
                s.connect(SOCK)
                break
            except (FileNotFoundError, ConnectionRefusedError):
                if attempt:
                    raise
                self._spawn()
        s.sendall((json.dumps({"op": "tts_stream", "text": sentence}) + "\n").encode())
        f = s.makefile("rb")
        head = json.loads(f.readline().decode() or "{}")
        if head.get("error") or not head.get("sr"):
            s.close()
            raise RuntimeError(head.get("error", "no audio"))
        return s, f, head

    def _stream(self, sentence, gen):
        """Speak one sentence as it is generated: socket -> buffer -> pw-play (raw PCM on stdin).
        The level that drives the iris comes from the audio actually being fed to the player."""
        if self.rec:
            return                                   # never speak into an open mic
        t0 = time.monotonic()
        s, f, head = self._open_stream(sentence)
        sr = int(head["sr"])
        self.last_stats.update(tts_engine=head.get("engine"), tts_cached=head.get("cached"))
        sink = self.cfg.get("sink") or ("vector_aec_sink" if self.ensure_aec() else None)
        now = time.monotonic()
        self.said = [(t, x) for t, x in self.said if now - t < 30] + [(now, sentence)]
        sc = self.app.pscene
        GLib.idle_add(sc.set_state, "speaking")
        self.player = subprocess.Popen(["pw-play"] + (["--target", sink] if sink else []) +
                                       ["--raw", "--rate", str(sr), "--channels", "1", "--format", "s16", "-"],
                                       stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            import fcntl
            fcntl.fcntl(self.player.stdin.fileno(), 1031, 8192)     # F_SETPIPE_SZ: ~0.17 s ahead, so the iris keeps time
        except OSError:
            pass
        chunks, done = [], threading.Event()

        def reader():                                # drain the socket at generation speed
            try:
                while True:
                    b = f.read1(8192) if hasattr(f, "read1") else f.read(8192)
                    if not b:
                        break
                    chunks.append(b)
            except OSError:
                pass
            done.set()
        threading.Thread(target=reader, daemon=True).start()
        first, pend = True, b""
        try:
            while not (done.is_set() and not chunks and not pend):
                if gen != self.gen:
                    break
                if not chunks and not pend:
                    time.sleep(0.01)
                    continue
                pend += b"".join(chunks[:]); del chunks[:len(chunks)]
                piece, pend = pend[:2400], pend[2400:]          # 50 ms at 24 kHz
                if len(piece) % 2:
                    pend, piece = piece[-1:] + pend, piece[:-1]
                if first:
                    self.last_stats["tts_first_audio_ms"] = int((time.monotonic() - t0) * 1000)
                    first = False
                a = np.frombuffer(piece, np.int16).astype(np.float32) / 32768.0
                rms = float(np.sqrt(np.mean(a * a))) if len(a) else 0.0
                sc.audio_level = float(np.clip((20 * np.log10(max(rms, 1e-5)) + 50) / 38, 0, 1))
                try:
                    self.player.stdin.write(piece)
                except (BrokenPipeError, ValueError):
                    break
            if gen == self.gen:
                try:
                    self.player.stdin.close()
                except OSError:
                    pass
                while self.player.poll() is None and gen == self.gen:
                    time.sleep(0.02)
            if self.player.poll() is None:
                self.player.kill()
        finally:
            s.close()
            sc.audio_level = None
            self.play_end = time.monotonic()

    def warm_tts(self):
        """Load the voice in the background (when the window opens), so the first reply is quick."""
        threading.Thread(target=lambda: self._safe(lambda: self._req({"op": "warm_tts"}, 10)), daemon=True).start()

    def _done_speaking(self):
        sc = self.app.pscene
        sc.audio_level = None
        if sc.avatar.state == "speaking" and not sc.revealing():
            sc.set_state("idle")
        self.app.last_activity = time.monotonic()

    def stop(self):
        self.gen += 1
        with self.qlock:
            self.queue.clear()
        self.pending = ""
        if self.player and self.player.poll() is None:
            self.player.kill()                       # SIGKILL: no fade-out tail into the mic
            try:
                self.player.wait(0.5)
            except subprocess.TimeoutExpired:
                pass
            self.play_end = time.monotonic()

    # ------------------------------------------------------------------ misc
    def toggle_mute(self):
        self.muted = not self.muted
        os.makedirs(STATE, exist_ok=True)
        if self.muted:
            open(MUTED, "w").close()
            self.stop()
        elif os.path.exists(MUTED):
            os.unlink(MUTED)

    def active(self):
        return bool(self.rec) or self.speaking

    def status(self):
        return {"muted": self.muted, "recording": bool(self.rec), "speaking": self.speaking,
                "engine": self.cfg.get("engine"), **self.last_stats}

    @staticmethod
    def _safe(fn):
        try:
            fn()
        except Exception:
            pass
