"""VECTOR's ears and voice: a small server in the voice venv (faster-whisper, Qwen3-TTS via
faster-qwen3-tts, kokoro-onnx), spawned on demand by the desktop daemon and talked to
over a unix socket, one JSON request per connection:

    {"op": "warm"}                      load speech-to-text now (on push-to-talk press)
    {"op": "warm_tts"}                  load the voice now (when VECTOR's window opens)
    {"op": "stt", "pcm": path}          16 kHz mono s16 raw -> {"text", "ms"}
    {"op": "tts", "text": "...", "role": r}        -> {"wav": path, "ms", "cached", "engine"}
    {"op": "tts_stream", "text": "...", "role": r, "shimmer_add": x, "cue": bool}
                                        -> one JSON header line {"sr", "engine", "cached"}, then raw
                                           mono s16le PCM until the socket closes; with cue, the
                                           dial-scratch transition comes first in the same stream
    roles (voice.json "voices"): main, robot, scientist, floor, notify
    {"op": "ping"}

Voice (voice.json "engine"):
  qwen     Qwen3-TTS 1.7B (Apache-2.0) speaking in VECTOR's own designed voice: the voice
           was designed once from a text description with the VoiceDesign model (no one's
           recording), saved as voices/vector-ref.wav, and every line is spoken by the Base
           model from that reference. Streams: ~0.2 s to first audio, ~2.3x realtime on
           the RTX 5070, ~4.7 GiB VRAM while loaded.
  kokoro   Kokoro-82M on the CPU, a blend of stock British male voices; the fallback.
  breeze   the homelab's Breeze TTS 2 (voice designed by instruction); too slow to talk live.
  fish     Fish Audio, only with a reference_id the operator owns (his own recording).
Every engine goes through the projector shimmer (holo/shimmer.py, voice.json "shimmer").
If the main engine fails or is still loading, the `fallback` engine answers.

Every finished line is cached as a wav by a hash of the engine settings and the text, so
repeats cost nothing. Models are unloaded after `unload_after_seconds` idle; the process
exits after `exit_after_seconds` idle. Nothing here listens to the microphone.

Run: ~/.local/share/bromigos/venv-tts/bin/python -m holo.voice_server
"""
import hashlib
import io
import json
import os
import socket
import ssl
import threading
import time
import urllib.request
import uuid
import wave

import numpy as np

from .shimmer import SilenceShaper, Shimmer, TimeStretch, dial_scratch

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = os.path.join(HERE, "voice.json")
RUNTIME = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
SOCK = os.path.join(RUNTIME, "bromigos-holo-voice.sock")
CACHE = os.path.expanduser("~/.cache/bromigos/vector-tts")
VOICE_DIR = os.path.expanduser("~/.local/share/bromigos/voice")
CA = os.path.expanduser("~/.config/homelab/homelab-ca.crt")
FISH_KEY = os.path.expanduser("~/.local/share/bromigos/fish-audio-key")


def log(*a):
    print(time.strftime("%H:%M:%S"), "holo-voice:", *a, flush=True)


def _wav_bytes(a, sr):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(sr))
        w.writeframes(_s16(a))
    return buf.getvalue()


def _s16(a):
    return (np.clip(np.asarray(a, np.float32), -1, 1) * 32767).astype(np.int16).tobytes()


class Server:
    def __init__(self):
        with open(CONF) as f:
            self.cfg = json.load(f)
        self.whisper = None
        self.kokoro = None
        self.kstyle = None
        self.qwen = None
        self.qwen_loading = threading.Event()
        self.last = time.monotonic()
        self.stt_lock = threading.Lock()
        self.tts_lock = threading.Lock()
        os.makedirs(CACHE, exist_ok=True)

    # ------------------------------------------------------------------ STT
    def warm(self):
        with self.stt_lock:
            if self.whisper is None:
                from faster_whisper import WhisperModel
                c = self.cfg["stt"]
                t0 = time.monotonic()
                try:
                    self.whisper = WhisperModel(c["model"], device=c.get("device", "cuda"), compute_type=c.get("compute_type", "float16"))
                except Exception as e:
                    log("whisper on GPU failed, using CPU:", e)
                    self.whisper = WhisperModel(c["model"], device="cpu", compute_type="int8")
                # the first pass loads the VAD and the CUDA kernels: do it now, not on the first sentence
                list(self.whisper.transcribe(np.zeros(16000, np.float32), beam_size=1, language="en", vad_filter=True)[0])
                log(f"whisper {c['model']} loaded in {time.monotonic() - t0:.2f}s")
        return {"ok": True}

    def stt(self, pcm):
        self.warm()
        a = np.fromfile(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        t0 = time.monotonic()
        with self.stt_lock:
            segs, _ = self.whisper.transcribe(a, beam_size=1, language="en", vad_filter=True,
                                              initial_prompt=self.cfg["stt"].get("prompt", ""))
            text = " ".join(s.text for s in segs).strip()
        return {"text": text, "ms": int((time.monotonic() - t0) * 1000), "seconds": round(len(a) / 16000, 2)}

    # ------------------------------------------------------------------ roles
    def role(self, name):
        v = self.cfg.get("voices", {})
        return v.get(name) or v.get("main") or {}

    def ref(self, name):
        """(reference wav, its transcript) for a role; the designed voice if the reference is missing."""
        r = self.role(name)
        p = os.path.expanduser(r.get("ref") or "")
        if p and os.path.exists(p) and os.path.exists(p[:-4] + ".txt"):
            with open(p[:-4] + ".txt") as f:
                return p, f.read().strip()
        if name != "main":
            return self.ref("main")
        d = self.cfg.get("designed_fallback", {})
        return os.path.join(HERE, d.get("ref", "voices/vector-ref-A.wav")), d.get("text", "")

    # ------------------------------------------------------------------ TTS engines (each yields float chunks)
    def _load_qwen(self):
        if self.qwen is not None:
            return self.qwen
        if self.qwen_loading.is_set():
            return None
        self.qwen_loading.set()
        try:
            from faster_qwen3_tts import FasterQwen3TTS
            c = self.cfg["qwen"]
            t0 = time.monotonic()
            m = FasterQwen3TTS.from_pretrained(c["model"])
            m.warmup(prefill_len=100)
            # every role's voice prompt (speaker embedding + reference codes) is computed here
            # once and cached inside the model, so switching voices mid-reply costs nothing
            for name in self.cfg.get("voices", {"main": {}}):
                ref, text = self.ref(name)
                list(m.generate_voice_clone_streaming(text="One moment.", language="English", ref_audio=ref,
                                                      ref_text=text, chunk_size=c.get("chunk_size", 4)))
            self.qwen = m
            log(f"qwen voice {c['model']} ready in {time.monotonic() - t0:.1f}s")
            return m
        finally:
            self.qwen_loading.clear()

    def warm_tts(self):
        if self.cfg["engine"] == "qwen" and self.qwen is None and not self.qwen_loading.is_set():
            threading.Thread(target=self._safe_load, daemon=True).start()
        return {"ok": True, "ready": self.cfg["engine"] != "qwen" or self.qwen is not None}

    def _safe_load(self):
        try:
            with self.tts_lock:
                self._load_qwen()
        except Exception as e:
            log("qwen voice failed to load:", e)

    def _gen_qwen(self, text, role):
        m = self.qwen
        if m is None:
            raise RuntimeError("qwen voice not loaded yet")
        c = self.cfg["qwen"]
        ref, ref_text = self.ref(role)
        for chunk, sr, _ in m.generate_voice_clone_streaming(
                text=text, language="English", ref_audio=ref, ref_text=ref_text,
                chunk_size=c.get("chunk_size", 4), temperature=c.get("temperature", 0.7)):
            yield np.asarray(chunk, np.float32).squeeze(), sr

    def _gen_kokoro(self, text, role):
        c = self.role(role).get("kokoro") or self.role("main").get("kokoro") or {"blend": {"bm_george": 1.0}}
        if self.kokoro is None:
            import onnxruntime as ort
            from kokoro_onnx import Kokoro
            sess = ort.InferenceSession(os.path.join(VOICE_DIR, "kokoro-v1.0.onnx"), providers=["CPUExecutionProvider"])
            self.kokoro = Kokoro.from_session(sess, os.path.join(VOICE_DIR, "voices-v1.0.bin"))
            self.kstyle = {}
        key = json.dumps(c["blend"], sort_keys=True)
        if key not in self.kstyle:
            self.kstyle[key] = sum(w * self.kokoro.get_voice_style(v) for v, w in c["blend"].items())
        a, sr = self.kokoro.create(text, voice=self.kstyle[key], speed=c.get("speed", 1.05), lang=c.get("lang", "en-gb"))
        yield np.asarray(a, np.float32), sr

    def _gen_breeze(self, text, role):
        c = self.cfg["breeze"]
        b = uuid.uuid4().hex
        parts = [f"--{b}\r\nContent-Disposition: form-data; name=\"{n}\"\r\n\r\n{v}\r\n"
                 for n, v in (("text", text), ("instruction", c["instruction"]), ("seed", str(c.get("seed", 7))),
                              ("cfg_scale", str(c.get("cfg_scale", 4))))]
        body = ("".join(parts) + f"--{b}--\r\n").encode()
        ctx = ssl.create_default_context(cafile=CA) if os.path.exists(CA) else ssl.create_default_context()
        req = urllib.request.Request(c["url"], data=body, method="POST", headers={"Content-Type": f"multipart/form-data; boundary={b}"})
        with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
            while True:
                pcm = r.read1(9600)
                if not pcm:
                    break
                yield np.frombuffer(pcm[: len(pcm) // 2 * 2], np.int16).astype(np.float32) / 32768.0, 24000

    def _gen_fish(self, text, role):
        c = self.cfg["fish"]
        if not c.get("reference_id"):
            raise RuntimeError("fish engine needs a reference_id of a voice model the operator owns")
        with open(FISH_KEY) as f:
            key = f.read().strip()
        body = {"reference_id": c["reference_id"], "text": text, "format": "wav", "normalize": True}
        req = urllib.request.Request("https://api.fish.audio/v1/tts", data=json.dumps(body).encode(), method="POST",
                                     headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        with wave.open(io.BytesIO(data)) as w:
            sr = w.getframerate()
            yield np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0, sr

    # ------------------------------------------------------------------ TTS front
    def _key(self, engine, text, role="main", shimmer=0.0):
        r = self.role(role)
        conf = [engine, self.cfg.get(engine), role, r.get("ref"), r.get("kokoro") if engine == "kokoro" else None,
                round(shimmer, 3), round(self.speed_for(role), 3), self.cfg.get("pacing")]
        return hashlib.sha1(json.dumps([conf, text], sort_keys=True).encode()).hexdigest()[:24]

    def _engines(self):
        main, fb = self.cfg["engine"], self.cfg.get("fallback", "kokoro")
        if main == "qwen" and self.qwen is None:
            self.warm_tts()
            # give a load in progress a moment (the window usually warmed it already)
            t0 = time.monotonic()
            while self.qwen is None and self.qwen_loading.is_set() and time.monotonic() - t0 < self.cfg["qwen"].get("wait_for_load_s", 4):
                time.sleep(0.05)
        out = [main] if (main != "qwen" or self.qwen is not None) else []
        return out + ([fb] if fb and fb != main else [])

    def speed_for(self, role):
        """voice.json "speed" (default 1.12), a role may override; WSOLA keeps the pitch."""
        return max(0.7, min(1.6, float(self.role(role).get("speed", self.cfg.get("speed", 1.12)))))

    def shimmer_for(self, role, add=0.0):
        return max(0.0, min(1.0, float(self.role(role).get("shimmer", 0.3)) + float(add or 0)))

    def cue(self, role, sr, add=0.0):
        """The dial scratch into `role`, through that role's shimmer; cached."""
        key = (role, sr, round(add, 3))
        if not hasattr(self, "_cues"):
            self._cues = {}
        if key not in self._cues:
            variant = sorted(self.cfg.get("voices", {"main": 0})).index(role) if role in self.cfg.get("voices", {}) else 0
            a = dial_scratch(sr, variant, self.cfg.get("cue", {}).get("seconds", 0.24))
            self._cues[key] = Shimmer(sr, self.shimmer_for(role, add)).process(a)
        return self._cues[key]

    def speak(self, text, role="main", add=0.0, cue=False):
        """Yields (header, chunks...): header {"sr", "engine", "cached"} then float32 chunks."""
        text = text.strip()
        shim = self.shimmer_for(role, add)
        for engine in self._engines():
            path = os.path.join(CACHE, self._key(engine, text, role, shim) + ".wav")
            if os.path.exists(path):
                with wave.open(path) as w:
                    sr = w.getframerate()
                    a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0
                yield {"sr": sr, "engine": engine, "cached": True}
                if cue:
                    yield self.cue(role, sr, add)
                for i in range(0, len(a), sr // 5):
                    yield a[i:i + sr // 5]
                return
            try:
                gen = getattr(self, "_gen_" + engine)(text, role)
                first = next(gen)
            except Exception as e:
                log(f"tts engine {engine} failed: {e}")
                continue
            chunk, sr = first
            dsp = Shimmer(sr, shim)
            ts = TimeStretch(sr, self.speed_for(role))
            pc = self.cfg.get("pacing", {})
            sh = SilenceShaper(sr, pc.get("max_pause_s", 0.12), pc.get("sentence_tail_s", 0.09))
            yield {"sr": sr, "engine": engine, "cached": False}
            if cue:
                yield self.cue(role, sr, add)
            done = []
            y = dsp.process(ts.process(sh.process(chunk)))
            done.append(y)
            yield y
            for chunk, _ in gen:
                y = dsp.process(ts.process(sh.process(chunk)))
                if len(y):
                    done.append(y)
                    yield y
            y = dsp.process(ts.process(sh.process(np.zeros(0, np.float32), final=True), final=True))
            if len(y):
                done.append(y)
                yield y
            tmp = path + ".part"
            with open(tmp, "wb") as f:
                f.write(_wav_bytes(np.concatenate(done), sr))
            os.replace(tmp, path)
            return
        raise RuntimeError("no TTS engine answered")

    def tts(self, text, role="main"):
        t0 = time.monotonic()
        with self.tts_lock:
            it = self.speak(text, role)
            head = next(it)
            a = np.concatenate([c for c in it] or [np.zeros(1, np.float32)])
        path = os.path.join(CACHE, self._key(head["engine"], text.strip(), role, self.shimmer_for(role)) + ".wav")
        return {"wav": path, "ms": int((time.monotonic() - t0) * 1000), "cached": head["cached"], "engine": head["engine"]}

    # ------------------------------------------------------------------ loop
    def handle(self, req, conn):
        op = req.get("op")
        self.last = time.monotonic()
        if op == "ping":
            return {"ok": True, "whisper": self.whisper is not None, "qwen": self.qwen is not None,
                    "engine": self.cfg["engine"]}
        if op == "warm":
            return self.warm()
        if op == "warm_tts":
            return self.warm_tts()
        if op == "stt":
            return self.stt(req["pcm"])
        if op == "tts":
            return self.tts(req["text"], req.get("role", "main"))
        if op == "cue":
            return {"seconds": self.cfg.get("cue", {}).get("seconds", 0.24)}
        if op == "tts_stream":
            with self.tts_lock:
                it = self.speak(req["text"], req.get("role", "main"), req.get("shimmer_add", 0.0), bool(req.get("cue")))
                head = next(it)
                conn.sendall((json.dumps(head) + "\n").encode())
                for chunk in it:
                    try:
                        conn.sendall(_s16(chunk))
                    except (BrokenPipeError, ConnectionResetError):
                        # barge-in: the client hung up; finish quietly so the cache is still written
                        for _ in it:
                            pass
                        break
            return None
        return {"error": "unknown op"}

    def janitor(self):
        while True:
            time.sleep(20)
            idle = time.monotonic() - self.last
            if idle > self.cfg.get("unload_after_seconds", 1800):
                if self.whisper is not None:
                    with self.stt_lock:
                        self.whisper = None
                    log("whisper unloaded (idle)")
                if self.qwen is not None:
                    with self.tts_lock:
                        self.qwen = None
                        import gc
                        gc.collect()
                        try:
                            import torch
                            torch.cuda.empty_cache()
                        except Exception:
                            pass
                    log("qwen voice unloaded (idle)")
            if idle > self.cfg.get("exit_after_seconds", 3600):
                log("exiting (idle)")
                os._exit(0)

    def serve(self):
        # One server per session: two clients spawning at once each loaded every model and
        # the second ran the 12 GB card out of memory (CUBLAS_STATUS_ALLOC_FAILED).
        import fcntl
        self._lock = open(SOCK + ".lock", "w")
        try:
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            log("another voice server holds the lock; exiting")
            os._exit(0)
        try:
            os.unlink(SOCK)
        except FileNotFoundError:
            pass
        srv = socket.socket(socket.AF_UNIX)
        srv.bind(SOCK)
        os.chmod(SOCK, 0o600)
        srv.listen(8)
        threading.Thread(target=self.janitor, daemon=True).start()
        log("ready", SOCK, "engine", self.cfg["engine"])
        if self.cfg.get("preload_tts", True):
            self.warm_tts()
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
                out = self.handle(json.loads(buf.decode()), c)
            except Exception as e:
                out = {"error": f"{type(e).__name__}: {str(e)[:200]}"}
            if out is not None:
                c.sendall((json.dumps(out) + "\n").encode())
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            c.close()


if __name__ == "__main__":
    Server().serve()
