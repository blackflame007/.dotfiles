"""PILOT's voice, desktop side (system python, inside the holo daemon).

Push-to-talk: SUPER+V down starts `pw-record` (16 kHz mono, raw to a pipe) and PILOT
shows LISTENING with a live MIC indicator; key up stops it at once. Nothing records
unless the key is held, and a recording is cut at `max_record_seconds` in case a
release is missed. Audio goes to the venv voice server for speech-to-text; the text
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
VENV = os.path.expanduser("~/.local/share/bromigos/venv")
RUNTIME = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
SOCK = os.path.join(RUNTIME, "bromigos-holo-voice.sock")
STATE = os.path.expanduser("~/.local/state/bromigos")
MUTED = os.path.join(STATE, "pilot-voice-muted")
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
    def ptt_down(self):
        if self.rec:
            return
        self.stop()                                   # talking over PILOT interrupts it
        self.app.show_pilot(focus=False)
        sc = self.app.pscene
        sc.set_state("listening")
        sc.mic_live = True
        self.rec_buf = bytearray()
        self.rec_t0 = time.monotonic()
        self.rec = subprocess.Popen(["pw-record", "--raw", "--rate", "16000", "--channels", "1", "--format", "s16", "-"],
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
        fd, path = tempfile.mkstemp(prefix="pilot-ptt-", suffix=".pcm", dir=RUNTIME)
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
            GLib.idle_add(self.app.ask, text)
        except Exception as e:
            GLib.idle_add(self.app._pilot_error, f"voice: {e}")
        finally:
            os.unlink(path)

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
            self._enqueue(m.group(1))
            self.pending = self.pending[m.end():]

    def flush(self):
        if self.pending.strip() and not self.muted:
            self._enqueue(self.pending)
        self.pending = ""

    def say(self, text):
        """A whole line (the greeting, a fixed phrase)."""
        if not self.muted:
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
        nxt = None                     # synthesise the next sentence while this one plays
        try:
            while True:
                with self.qlock:
                    if not self.queue:
                        break
                    gen, s = self.queue.pop(0)
                if gen != self.gen:
                    continue
                t0 = time.monotonic()
                out = nxt.result() if nxt and nxt.text == s else self._req({"op": "tts", "text": s}, 90)
                self.last_stats["tts_ms"] = int((time.monotonic() - t0) * 1000)
                with self.qlock:
                    peek = self.queue[0][1] if self.queue else None
                nxt = _Prefetch(self, peek) if peek else None
                if gen != self.gen or self.muted:
                    continue
                self._play(out["wav"], gen)
        except Exception as e:
            GLib.idle_add(self.app.pscene.note, f"(voice trouble: {str(e)[:80]})")
        finally:
            with self.qlock:
                self.speaking = False
            GLib.idle_add(self._done_speaking)

    def _play(self, path, gen):
        with wave.open(path) as w:
            sr = w.getframerate()
            a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0
        hop = sr // 30
        env = np.array([np.sqrt(np.mean(a[i:i + hop] ** 2)) for i in range(0, len(a), hop)] or [0.0])
        env = np.clip((20 * np.log10(np.maximum(env, 1e-5)) + 50) / 38, 0, 1)
        sc = self.app.pscene
        GLib.idle_add(sc.set_state, "speaking")
        sink = self.cfg.get("sink")
        self.player = subprocess.Popen(["pw-play"] + (["--target", sink] if sink else []) + [path], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
        t0 = time.monotonic()
        while self.player.poll() is None:
            if gen != self.gen:
                self.player.terminate()
                break
            k = int((time.monotonic() - t0) * 30)
            sc.audio_level = float(env[min(k, len(env) - 1)])
            time.sleep(1 / 30)
        sc.audio_level = None

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
            self.player.terminate()

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


class _Prefetch:
    def __init__(self, voice, text):
        self.text = text
        self.out = None
        self.err = None
        self.t = threading.Thread(target=self._run, args=(voice,), daemon=True)
        self.t.start()

    def _run(self, voice):
        try:
            self.out = voice._req({"op": "tts", "text": self.text}, 90)
        except Exception as e:
            self.err = e

    def result(self):
        self.t.join(90)
        if self.err:
            raise self.err
        return self.out
