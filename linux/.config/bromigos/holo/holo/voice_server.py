"""PILOT's ears and voice: a small server in the bromigos venv (faster-whisper, kokoro-onnx),
spawned on demand by the desktop daemon and talked to over a unix socket, one JSON
request per connection:

    {"op": "warm"}                      load speech-to-text now (on push-to-talk press)
    {"op": "stt", "pcm": path}          16 kHz mono s16 raw -> {"text", "ms"}
    {"op": "tts", "text": "..."}        -> {"wav": path, "ms", "cached"}
    {"op": "ping"}

Whisper sits on the GPU (small.en, fp16, about 0.12 s per utterance) and is unloaded
after `unload_after_seconds` idle; the process exits after `exit_after_seconds` idle.
TTS runs on the CPU (about 3x realtime) and every rendered line is cached by hash.
Nothing here listens to the microphone; the client records only while the key is held.

Run: ~/.local/share/bromigos/venv/bin/python -m holo.voice_server
"""
import hashlib
import json
import os
import socket
import ssl
import threading
import time
import urllib.request
import uuid

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = os.path.join(HERE, "voice.json")
RUNTIME = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
SOCK = os.path.join(RUNTIME, "bromigos-holo-voice.sock")
CACHE = os.path.expanduser("~/.cache/bromigos/pilot-tts")
VOICE_DIR = os.path.expanduser("~/.local/share/bromigos/voice")
CA = os.path.expanduser("~/.config/homelab/homelab-ca.crt")
FISH_KEY = os.path.expanduser("~/.local/share/bromigos/fish-audio-key")


def log(*a):
    print(time.strftime("%H:%M:%S"), "holo-voice:", *a, flush=True)


class Server:
    def __init__(self):
        with open(CONF) as f:
            self.cfg = json.load(f)
        self.whisper = None
        self.kokoro = None
        self.style = None
        self.last = time.monotonic()
        self.lock = threading.Lock()
        os.makedirs(CACHE, exist_ok=True)

    # ------------------------------------------------------------------ STT
    def warm(self):
        if self.whisper is None:
            from faster_whisper import WhisperModel
            c = self.cfg["stt"]
            t0 = time.monotonic()
            try:
                self.whisper = WhisperModel(c["model"], device=c.get("device", "cuda"), compute_type=c.get("compute_type", "float16"))
            except Exception as e:
                log("whisper on GPU failed, using CPU:", e)
                self.whisper = WhisperModel(c["model"], device="cpu", compute_type="int8")
            # first pass loads the VAD and the CUDA kernels; do it now, not on the operator's first sentence
            list(self.whisper.transcribe(np.zeros(16000, np.float32), beam_size=1, language="en", vad_filter=True)[0])
            log(f"whisper loaded in {time.monotonic() - t0:.2f}s")
        return {"ok": True}

    def stt(self, pcm):
        self.warm()
        a = np.fromfile(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        t0 = time.monotonic()
        segs, _ = self.whisper.transcribe(a, beam_size=1, language="en", vad_filter=True,
                                          initial_prompt="PILOT, the Wick, ARBITER, the rack room, Argo CD, Prometheus, EchoCraft Lab.")
        text = " ".join(s.text for s in segs).strip()
        return {"text": text, "ms": int((time.monotonic() - t0) * 1000), "seconds": round(len(a) / 16000, 2)}

    # ------------------------------------------------------------------ TTS
    def _key(self, text):
        e = self.cfg["engine"]
        return hashlib.sha1(json.dumps([e, self.cfg.get(e), text], sort_keys=True).encode()).hexdigest()[:24]

    def tts(self, text):
        text = text.strip()
        path = os.path.join(CACHE, self._key(text) + ".wav")
        if os.path.exists(path):
            return {"wav": path, "ms": 0, "cached": True}
        t0 = time.monotonic()
        engine = self.cfg["engine"]
        audio, sr = getattr(self, "_tts_" + engine)(text)
        self._write_wav(path, audio, sr)
        return {"wav": path, "ms": int((time.monotonic() - t0) * 1000), "cached": False}

    def _tts_kokoro(self, text):
        if self.kokoro is None:
            import onnxruntime as ort
            from kokoro_onnx import Kokoro
            sess = ort.InferenceSession(os.path.join(VOICE_DIR, "kokoro-v1.0.onnx"), providers=["CPUExecutionProvider"])
            self.kokoro = Kokoro.from_session(sess, os.path.join(VOICE_DIR, "voices-v1.0.bin"))
            c = self.cfg["kokoro"]
            self.style = sum(w * self.kokoro.get_voice_style(v) for v, w in c["blend"].items())
        c = self.cfg["kokoro"]
        a, sr = self.kokoro.create(text, voice=self.style, speed=c.get("speed", 1.1), lang=c.get("lang", "en-gb"))
        return a, sr

    def _tts_breeze(self, text):
        c = self.cfg["breeze"]
        b = uuid.uuid4().hex
        parts = [f"--{b}\r\nContent-Disposition: form-data; name=\"{n}\"\r\n\r\n{v}\r\n"
                 for n, v in (("text", text), ("instruction", c["instruction"]), ("seed", str(c.get("seed", 7))))]
        body = ("".join(parts) + f"--{b}--\r\n").encode()
        ctx = ssl.create_default_context(cafile=CA) if os.path.exists(CA) else ssl.create_default_context()
        req = urllib.request.Request(c["url"], data=body, method="POST", headers={"Content-Type": f"multipart/form-data; boundary={b}"})
        with urllib.request.urlopen(req, timeout=90, context=ctx) as r:
            pcm = r.read()
        return np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0, 24000

    def _tts_fish(self, text):
        c = self.cfg["fish"]
        if not c.get("reference_id"):
            raise RuntimeError("fish engine needs a reference_id (a voice model you own)")
        with open(FISH_KEY) as f:
            key = f.read().strip()
        body = {"reference_id": c["reference_id"], "text": text, "format": "wav", "normalize": True}
        req = urllib.request.Request("https://api.fish.audio/v1/tts", data=json.dumps(body).encode(), method="POST",
                                     headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        import io
        import wave
        with wave.open(io.BytesIO(data)) as w:
            sr = w.getframerate()
            a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0
        return a, sr

    @staticmethod
    def _write_wav(path, a, sr):
        import wave
        a = np.clip(np.asarray(a, np.float32), -1, 1)
        tmp = path + ".part"
        with wave.open(tmp, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(int(sr))
            w.writeframes((a * 32767).astype(np.int16).tobytes())
        os.replace(tmp, path)

    # ------------------------------------------------------------------ loop
    def handle(self, req):
        op = req.get("op")
        with self.lock:
            self.last = time.monotonic()
            if op == "ping":
                return {"ok": True, "whisper": self.whisper is not None, "tts": self.kokoro is not None}
            if op == "warm":
                return self.warm()
            if op == "stt":
                return self.stt(req["pcm"])
            if op == "tts":
                return self.tts(req["text"])
        return {"error": "unknown op"}

    def janitor(self):
        while True:
            time.sleep(20)
            idle = time.monotonic() - self.last
            if self.whisper is not None and idle > self.cfg.get("unload_after_seconds", 600):
                with self.lock:
                    self.whisper = None
                log("whisper unloaded (idle)")
            if idle > self.cfg.get("exit_after_seconds", 1800):
                log("exiting (idle)")
                os._exit(0)

    def serve(self):
        try:
            os.unlink(SOCK)
        except FileNotFoundError:
            pass
        srv = socket.socket(socket.AF_UNIX)
        srv.bind(SOCK)
        os.chmod(SOCK, 0o600)
        srv.listen(8)
        threading.Thread(target=self.janitor, daemon=True).start()
        log("ready", SOCK)
        while True:
            c, _ = srv.accept()
            threading.Thread(target=self._client, args=(c,), daemon=True).start()

    def _client(self, c):
        try:
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = c.recv(65536)
                if not chunk:
                    break
                buf += chunk
            if not buf.strip():
                return                       # a liveness probe
            try:
                out = self.handle(json.loads(buf.decode()))
            except Exception as e:
                out = {"error": f"{type(e).__name__}: {str(e)[:200]}"}
            c.sendall((json.dumps(out) + "\n").encode())
        finally:
            c.close()


if __name__ == "__main__":
    Server().serve()
