"""Seamless video loops as GPU textures, for worlds (a layer's `video`, or any actor
sprite that names a video file).

One ffmpeg process per loop decodes it endlessly (`-stream_loop -1`) to raw NV12 on a
pipe (no colour conversion on the CPU); a reader thread keeps the newest frame; the
render thread uploads its two planes and converts them to premultiplied RGBA on the
GPU (shaders/world_yuv.frag) when the loop's clock says a new frame is due. Decoding is
hardware accelerated where ffmpeg can (`-hwaccel auto`: CUDA/NVDEC, VAAPI, Vulkan ...),
except VP9 with an alpha channel, which only the software decoder (libvpx) reads (that
one comes as RGBA). Measured (RTX 5070, a 1920x1080 30 fps high-motion test loop): about
9% of one core in ffmpeg as NV12, against 41% converted to RGBA by ffmpeg; 1280x720 at
24 fps or less keeps a backdrop within the live layer's budget.

Pausing is free: the reader takes a frame only after the previous one was used, so when
the layer stops rendering (locked, fullscreen, a deck on top) the pipe fills, ffmpeg
blocks and decodes nothing. A loop nobody draws for a while is never even started.

Alpha (world.toml `[loops."<path>"] alpha = ...`):
  "none"     opaque video (H.264 / HEVC / AV1 / VP9), hardware decoded
  "native"   VP9 or AV1 with alpha (default for .webm), software decoded
  "stacked"  the colour on top, its alpha (grey) below, in one frame twice as tall:
             any codec, hardware decoded; ffmpeg merges the halves
Also per loop: `fps` (default: the file's), `scale` (decode at this fraction of the
file's size, to keep big backdrops cheap).
"""
import json
import os
import subprocess
import threading
import time

import numpy as np
from OpenGL import GL

VIDEO_EXT = (".mp4", ".webm", ".mkv", ".mov", ".m4v")


def is_video(path):
    return path.lower().endswith(VIDEO_EXT)


def probe(path):
    """(width, height, fps) of the first video stream."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,avg_frame_rate,r_frame_rate", "-of", "json", path],
                         capture_output=True, text=True, timeout=10).stdout
    s = (json.loads(out or "{}").get("streams") or [{}])[0]
    num, _, den = (s.get("avg_frame_rate") or s.get("r_frame_rate") or "30/1").partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 30.0
    return int(s.get("width") or 0), int(s.get("height") or 0), fps or 30.0


class VideoLoop:
    def __init__(self, path, alpha=None, fps=None, scale=1.0, sync=False):
        self.path = path
        self.alpha = alpha or ("native" if path.lower().endswith(".webm") else "none")
        w, h, f = probe(path)
        if self.alpha == "stacked":
            h //= 2
        sc = max(0.05, min(1.0, float(scale)))
        self.w, self.h = max(2, int(w * sc) // 2 * 2), max(2, int(h * sc) // 2 * 2)
        self.src_h = h
        self.nv12 = self.alpha != "native"           # stacked and opaque loops come as NV12
        self.target = None
        self.planes = None
        self.fps = float(fps or f)
        self.aspect = self.w / self.h
        self.tex = None
        self.proc = None
        self.frame = None            # the newest decoded frame (bytes), not yet uploaded
        self.taken = threading.Event()
        self.taken.set()
        self.lock = threading.Lock()
        self.clock = 0.0             # the loop's own time: advances only while it is drawn
        self.shown = -1
        self.stop = threading.Event()
        self.last_use = 0.0
        self.sync = sync             # offscreen renders: wait for each frame instead of dropping it

    # ---- decoding
    def _cmd(self):
        cmd = ["ffmpeg", "-v", "error", "-nostdin"]
        if self.alpha == "native":
            if self.path.lower().endswith(".webm"):
                cmd += ["-c:v", "libvpx-vp9"]          # ffmpeg's own VP9 decoder drops the alpha
        else:
            cmd += ["-hwaccel", "auto"]
        cmd += ["-stream_loop", "-1", "-i", self.path]
        fh = self.h * 2 if self.alpha == "stacked" else self.h     # stacked: both halves
        if self.nv12:
            cmd += ["-vf", f"scale={self.w}:{fh}"] if (self.w, fh) != self._src_size() else []
            cmd += ["-r", f"{self.fps:.3f}", "-f", "rawvideo", "-pix_fmt", "nv12", "-"]
        else:
            cmd += ["-vf", f"scale={self.w}:{self.h},format=rgba"]
            cmd += ["-r", f"{self.fps:.3f}", "-f", "rawvideo", "-pix_fmt", "rgba", "-"]
        return cmd

    def _src_size(self):
        return (self.w, self.src_h * (2 if self.alpha == "stacked" else 1))

    def _frame_bytes(self):
        if self.nv12:
            fh = self.h * 2 if self.alpha == "stacked" else self.h
            return self.w * fh * 3 // 2
        return self.w * self.h * 4

    def _start(self):
        self.proc = subprocess.Popen(self._cmd(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     bufsize=0, start_new_session=True)
        self.ready = threading.Event()
        threading.Thread(target=self._read, args=(self.proc.stdout, self.stop, self.taken, self.ready),
                         daemon=True, name="videoloop").start()

    def _read(self, f, stop, taken, ready):
        n = self._frame_bytes()
        while not stop.is_set():
            taken.wait()                              # paused until the last frame is used
            if stop.is_set():
                break
            buf = bytearray(n)
            view = memoryview(buf)
            got = 0
            try:
                while got < n:
                    k = f.readinto(view[got:])
                    if not k:
                        return
                    got += k
            except (OSError, ValueError):
                return
            with self.lock:
                if stop.is_set():
                    return
                self.frame = buf
                taken.clear()
                ready.set()

    # ---- the render thread
    def advance(self, dt):
        """Advance the loop's clock by dt (the frame's time) and upload a new frame when one is
        due. Returns the texture (None until the first frame arrives)."""
        self.last_use = time.monotonic()
        if self.proc is None:
            self._start()
        self.clock += max(0.0, min(dt, 0.25))
        due = int(self.clock * self.fps)
        if due != self.shown:
            if self.sync:
                self.ready.wait(5.0)
            with self.lock:
                self.ready.clear()
                buf, self.frame = self.frame, None
            if buf is not None:
                self._upload(buf)
                self.shown = due
                self.taken.set()
        return self.tex

    def _upload(self, buf):
        if self.nv12:
            return self._upload_nv12(buf)
        if self.tex is None:
            self.tex = GL.glGenTextures(1)
            GL.glBindTexture(GL.GL_TEXTURE_2D, self.tex)
            GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
            GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA8, self.w, self.h, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, None)
            for p, v in ((GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR), (GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR),
                         (GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE), (GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)):
                GL.glTexParameteri(GL.GL_TEXTURE_2D, p, v)
        a = np.frombuffer(buf, np.uint8).reshape(self.h, self.w, 4)
        if self.alpha != "none":                      # premultiply, like every other world texture
            a = a.copy()
            a[..., :3] = (a[..., :3].astype(np.uint16) * a[..., 3:4] // 255).astype(np.uint8)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.tex)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
        GL.glTexSubImage2D(GL.GL_TEXTURE_2D, 0, 0, 0, self.w, self.h, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, a)

    def _upload_nv12(self, buf):
        """The frame's Y and UV planes into two textures, converted into the RGBA target."""
        from . import glkit
        fh = self.h * 2 if self.alpha == "stacked" else self.h
        if self.target is None:
            self.target = glkit.Target(self.w, self.h)
            self.tex = self.target.tex
            self.planes = GL.glGenTextures(2)
            for t, (fmt, w, h) in zip(self.planes, ((GL.GL_R8, self.w, fh), (GL.GL_RG8, self.w // 2, fh // 2))):
                GL.glBindTexture(GL.GL_TEXTURE_2D, t)
                GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, fmt, w, h, 0, GL.GL_RED if fmt == GL.GL_R8 else GL.GL_RG,
                                GL.GL_UNSIGNED_BYTE, None)
                for p, v in ((GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR), (GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR),
                             (GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE), (GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)):
                    GL.glTexParameteri(GL.GL_TEXTURE_2D, p, v)
            VideoLoop._prog = getattr(VideoLoop, "_prog", None) or glkit.program("fs.vert", "world_yuv.frag")
            VideoLoop._fs = getattr(VideoLoop, "_fs", None) or glkit.Fullscreen()
        a = np.frombuffer(buf, np.uint8)
        ysz = self.w * fh
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.planes[0])
        GL.glTexSubImage2D(GL.GL_TEXTURE_2D, 0, 0, 0, self.w, fh, GL.GL_RED, GL.GL_UNSIGNED_BYTE, a[:ysz])
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.planes[1])
        GL.glTexSubImage2D(GL.GL_TEXTURE_2D, 0, 0, 0, self.w // 2, fh // 2, GL.GL_RG, GL.GL_UNSIGNED_BYTE, a[ysz:])
        prev_fbo = GL.glGetIntegerv(GL.GL_DRAW_FRAMEBUFFER_BINDING)
        prev_vp = GL.glGetIntegerv(GL.GL_VIEWPORT)
        blend = GL.glIsEnabled(GL.GL_BLEND)
        GL.glDisable(GL.GL_BLEND)
        self.target.bind()
        p = VideoLoop._prog
        p.use()
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.planes[0])
        GL.glActiveTexture(GL.GL_TEXTURE1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.planes[1])
        p.i("u_y", 0)
        p.i("u_uv", 1)
        p.f("u_stacked", 1.0 if self.alpha == "stacked" else 0.0)
        p.f("u_bt709", 1.0 if self.h > 576 else 0.0)
        VideoLoop._fs.draw()
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, int(prev_fbo))
        GL.glViewport(*[int(x) for x in prev_vp])
        if blend:
            GL.glEnable(GL.GL_BLEND)

    def idle_check(self, now, after=20.0):
        """Stop the decoder of a loop that hasn't been drawn for a while (it restarts on use)."""
        if self.proc is not None and now - self.last_use > after:
            self.close(keep_texture=True)

    def close(self, keep_texture=False):
        self.stop.set()
        self.taken.set()
        if self.proc is not None:
            try:
                self.proc.kill()
                self.proc.wait(timeout=2)
            except Exception:
                pass
        self.proc = None
        self.stop = threading.Event()
        self.taken = threading.Event()
        self.taken.set()
        if not keep_texture and self.tex is not None:
            try:
                if self.target is not None:
                    self.target.free()
                    GL.glDeleteTextures(list(self.planes))
                else:
                    GL.glDeleteTextures([self.tex])
            except Exception:
                pass
            self.tex = self.target = self.planes = None
