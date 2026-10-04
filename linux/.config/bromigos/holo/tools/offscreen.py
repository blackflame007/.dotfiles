#!/usr/bin/env python3
"""Render the hologram scenes headless (EGL, NVIDIA device) to PNG with real readings,
without touching the desktop. For screenshots and tuning.

  offscreen.py gallery OUT.png [model] [explode 0..1] [iso part id] [t seconds]
  offscreen.py pilot OUT.png [state] [exhibit] [t seconds]
"""
import ctypes
import os
import sys
import time

os.environ["PYOPENGL_PLATFORM"] = "egl"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

import numpy as np  # noqa: E402
from OpenGL import EGL, GL  # noqa: E402

W, H = int(os.environ.get("OFF_W", 1760)), int(os.environ.get("OFF_H", 1040))


def egl():
    attrs = [EGL.EGL_CONTEXT_MAJOR_VERSION, 3, EGL.EGL_CONTEXT_MINOR_VERSION, 3,
             EGL.EGL_CONTEXT_OPENGL_PROFILE_MASK, EGL.EGL_CONTEXT_OPENGL_CORE_PROFILE_BIT, EGL.EGL_NONE]
    from OpenGL.EGL.EXT.device_base import eglQueryDevicesEXT
    from OpenGL.EGL.EXT.platform_base import eglGetPlatformDisplayEXT
    from OpenGL.EGL.EXT.platform_device import EGL_PLATFORM_DEVICE_EXT
    devs = (EGL.EGLDeviceEXT * 8)()
    n = EGL.EGLint()
    eglQueryDevicesEXT(8, devs, ctypes.byref(n))
    dpy = None
    for i in range(n.value):
        d = eglGetPlatformDisplayEXT(EGL_PLATFORM_DEVICE_EXT, devs[i], None)
        if EGL.eglInitialize(d, None, None) and b"NVIDIA" in (EGL.eglQueryString(d, EGL.EGL_VENDOR) or b""):
            dpy = d
            break
    EGL.eglBindAPI(EGL.EGL_OPENGL_API)
    cfg = EGL.EGLConfig()
    EGL.eglChooseConfig(dpy, [EGL.EGL_SURFACE_TYPE, EGL.EGL_PBUFFER_BIT, EGL.EGL_RENDERABLE_TYPE, EGL.EGL_OPENGL_BIT,
                              EGL.EGL_NONE], ctypes.byref(cfg), 1, ctypes.byref(n))
    ctx = EGL.eglCreateContext(dpy, cfg, EGL.EGL_NO_CONTEXT, attrs)
    EGL.eglMakeCurrent(dpy, EGL.EGL_NO_SURFACE, EGL.EGL_NO_SURFACE, ctx)


def target():
    fbo = GL.glGenFramebuffers(1)
    GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, fbo)
    rb = GL.glGenRenderbuffers(1)
    GL.glBindRenderbuffer(GL.GL_RENDERBUFFER, rb)
    GL.glRenderbufferStorage(GL.GL_RENDERBUFFER, GL.GL_RGBA8, W, H)
    GL.glFramebufferRenderbuffer(GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0, GL.GL_RENDERBUFFER, rb)
    return fbo


def save(fbo, out):
    from PIL import Image
    GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, fbo)
    px = GL.glReadPixels(0, 0, W, H, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
    a = np.frombuffer(px, np.uint8).reshape(H, W, 4)[::-1]
    # show it over the den wallpaper, as it would sit on the desktop
    bgp = os.path.expanduser("~/.config/wallpaper/bromigos-den-2560x1440.jpg")
    rgb = a[..., :3].astype(np.float32)
    al = a[..., 3:4].astype(np.float32) / 255
    if os.path.exists(bgp):
        bg = np.asarray(Image.open(bgp).convert("RGB").resize((W, H)), np.float32)
        rgb = rgb + bg * (1 - al)            # premultiplied over
    Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).save(out)
    print(out)


def main():
    kind, out = sys.argv[1], sys.argv[2]
    args = sys.argv[3:]
    egl()
    from holo.live import Live
    live = Live()
    fbo = target()
    if kind == "gallery":
        from holo.gallery import Gallery
        g = Gallery(live)
        model = args[0] if args else "workstation"
        g.show(model)
        s = g.stage
        s.poll()
        time.sleep(float(os.environ.get("OFF_WARM", 4)))
        s.explode_to = s.explode = float(args[1]) if len(args) > 1 else 0.0
        if len(args) > 2 and args[2] != "-":
            s.iso = [p["id"] for p in s.parts].index(args[2])
            s.iso_amt[s.iso] = 1.0
        tt = float(args[3]) if len(args) > 3 else 3.0
        now = time.monotonic()
        s.born = now - tt
        s.scan_t0 = now - float(os.environ.get("OFF_SCAN", 1.2))
        s.read_at = 0
        s.fade = 1.0
        g.last_t = now
        g.render(fbo, W, H)       # first frame lays out callouts
        s.read_at = 0
        g.render(fbo, W, H)
        save(fbo, out)
    elif kind == "pilot":
        from holo.pilot.scene import PilotScene
        p = PilotScene(live)
        state = args[0] if args else "idle"
        p.set_state(state)
        if len(args) > 1 and args[1] != "-":
            p.exhibit(args[1], os.environ.get('OFF_PARTS', '').split(',') if os.environ.get('OFF_PARTS') else None)
        time.sleep(float(os.environ.get("OFF_WARM", 4)))
        tt = float(args[2]) if len(args) > 2 else 3.0
        p.demo_transcript()
        p.fade = 1.0
        for k in range(int(tt * 30)):
            p.advance(1 / 30)
            if p.stage:
                p.stage.read_at = 0
        p.set_state(state)
        p.fade = 1.0
        if p.stage:
            p.ex_amt = 1.0
        p.render(fbo, W, H)
        p.render(fbo, W, H)
        save(fbo, out)


if __name__ == "__main__":
    main()
