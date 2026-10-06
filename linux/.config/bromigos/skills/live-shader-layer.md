---
name: live-shader-layer
description: How to add a background shader layer or a deck plugin to the live layer (bromigos-live) without touching its core — the layer contract (uniforms with real readings), opt-in JSON, GPU budget, the headless compile-and-render test, and the deck plugin hook.
when_to_use: "Adding a new animation, shader effect or ambient visual to the desktop background, or a new summoned deck as a plugin."
---

# Live-layer plugins

How the live layer animates in general (loops, decks, pause rules, frame budgets) is in
`live-layer-animation.md`; read it first. This is the plugin route, which needs no core
edits.

## A shader layer

Two files in `linux/.config/bromigos-live/layers/`:

`<name>.frag` (GLSL 330 core), drawn over the finished background, behind every window:

```glsl
#version 330 core
in vec2 v_uv; out vec4 frag;          // v_uv 0..1, origin bottom-left
uniform vec2 u_res; uniform float u_time; uniform float u_opacity;
uniform vec4 u_load;    // cpu, gpu, memory, vram (0..1, real readings)
uniform vec4 u_net;     // rx, tx (log-scaled 0..1), recent peaks
uniform float u_health; // 0 all green, 1 hot or stale, 2 something down
uniform vec4 u_rect;    // the JSON rect (pixels) or the whole screen
void main() {
    // a phosphor horizon line whose height follows real CPU load
    float y = 0.1 + 0.3 * u_load.x;
    float a = exp(-abs(v_uv.y - y) * u_res.y * 0.6) * u_opacity;
    frag = vec4(vec3(0.22, 1.0, 0.08) * a, a);
}
```

`<name>.json`: `{"enabled": true, "opacity": 0.5, "blend": "add", "budget_ms": 1.0,
"title": "...", "hint": "what it shows"}`. Layers are **opt-in**: without `"enabled":
true` nothing draws. `blend` "add" (default; light only) or "alpha" (premultiplied).

Rules: motion must mean something (a reading drives it) or be the slow fixed ambience the
rules allow; never a CRT or scanline effect over windows (layers are behind them anyway,
keep them subtle); palette colours only (phosphor 0.22,1.0,0.08; soft 0.61,1.0,0.54;
amber 0.83,0.69,0.22; danger 1.0,0.46,0.44); stay out of the den's fitted screens.

Budget: each layer's GPU time is measured every frame; over `budget_ms` on average (2 s),
or a compile error, and it switches itself off (health:
`$XDG_RUNTIME_DIR/bromigos-live-plugins.json`, log: `live-plugins.log`). Test headless:

```bash
cd linux/.config/bromigos-live && python3 -m live.plugins test-layer layers/<name>.frag /tmp/l.png
# -> {"gpu_ms", "within_budget", "lit_fraction", ...}; a GLSL error prints its line
```

`build_validate` runs exactly this and looks at the PNG.

## A deck plugin

`linux/.config/bromigos-live/plugins/<name>.py` defining `DECK = <class>` built on
`live/deckkit.py` (the same base as Mind, Ops, Swarm; `hologram-build.md` shows how).
Opened with `bromigos-live plugin <name> [verb args]`. A deck that raises stops drawing
and closes; the live layer carries on.
