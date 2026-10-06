---
name: live-layer-animation
description: "How the live layer animates — the background shader layers, overlays and decks, seamless loops (loop phase and crossfade), pause/fullscreen rules, frame-rate budgets and self-healing surfaces — as actually implemented in bromigos-live."
when_to_use: "Adding or changing anything that moves on the desktop: a background layer, a loop, an event animation (intercept, transmission, codec call), a deck's motion, or when something stops animating, stutters, costs too much, or shows a seam."
---

# Animating the live layer

## The pieces

- **Background** (`live/scene.py` + `shaders/bg.frag`): one GLArea on the layer-shell
  BACKGROUND layer of DP-1, behind every window. It draws the den wallpaper as a
  base plate, then the layers: glyph rain (CPU), floor pulses (network), the den's
  screens made live, the Drift space layer (`space.glsl`), the hardware scanner
  pass, the decorative loops (`denloop.glsl`), and the emissive gadgets with bloom.
- **Overlays** (`live/overlays.py`): short-lived OVERLAY-layer windows — intercept,
  transmission, codec panel, screensaver — and the summoned decks (holo deck,
  ARBITER, Drift map, timeline, Mind, Ops, Swarm, Network, Replay).
- **One config**: `config.toml`, reloaded on save. It marks which layers are data
  and which are decoration.
- **The catalog**: `linux/.config/bromigos-live/docs/ELEMENTS.md` lists every element
  of the wallpaper (oscilloscope, relay map, emblem monitor, meters, rain and bursts,
  floor pulses, ships, stars, relay beam, health tint, X-ray sweep, wipe, intercept,
  transmission, codec calls, screensaver, loops, plugin layers, sounds) with what it
  means, its data source and rate, its code and uniforms, its config key and how to
  change it, plus the den plate fitting rules and how to add a new element. Read the
  element's section before you touch it, and update the section when you change it.

Nothing ever draws over application windows: no CRT pass, no scanlines, no tint.
Overlays are either summoned by the operator or brief event animations that leave
nothing behind.

## Frame rates and pauses

`App.refresh_state()` decides the background's mode from Hyprland state:

| Mode | When | fps |
|------|------|-----|
| running | the desktop is visible | 30 (`general.fps`) |
| idle | windows are tiled over it (only gaps show) | 20 (`general.fps_covered`) |
| paused | session locked, a true fullscreen window (mode 2, not maximize), or a full-screen deck on top | 0 |

Overlays render at 30 fps while open and stop when closed. Background data
polling slows down while paused. Measured cost on this machine (RTX 5070,
Ryzen 7 3700X): the daemon about 7–9% of one core, GPU under 1%; a 3D deck's frame
0.6–1.7 ms median.

Rules that came from real bugs:
- Pause only on true fullscreen (`client.fullscreen == 2`). Maximize also sets the
  workspace's `hasfullscreen`, and pausing on it froze the background for the
  operator.
- `bromigos-live status` must be honest: target vs measured fps, surface mapped or
  MISSING. A measured rate far under target is a fault, not "idle".
- Surfaces die when the monitor powers off (the output is removed). The daemon heals
  on monitor added/removed, unlock, DPMS-on and every 30 s: it checks
  `hyprctl layers` for its namespace on the monitor and recreates the window and GL
  context if it is missing, retrying at 1.5/4/9/20 s while the output flaps.

## Seamless loops

Decorative motion loops; it is tied to no metric and runs at a calm, constant pace.
Two techniques, both from `shaders/denloop.glsl`.

**1. Phase from double-precision time, wrapped per loop.** The CPU computes each
loop's phase in [0, 1) from `time.monotonic()` in Python floats and sends only the
phase; the shader never sees large time values, so there is no precision drift and
no visible reset:

```python
T_s, T_r, T_st = 10.0, 12.0, 7.0                 # streaks, floor rows, steam
now = time.monotonic()
f.f("u_loop", (now % T_s) / T_s, (now % T_r) / T_r, (now % T_st) / T_st, T_s)
```

Everything driven by the phase must be periodic in it: `sin(TAU * phase * n)` with
integer `n`, a scroll by exactly one grid cell per loop (the floor rows), a shimmer
frame index `floor(phase * frames)` with integral `frames` per loop.

**2. Crossfade two realisations one period apart** for things that evolve freely,
like noise-driven steam. At phase `w`, blend the field at time `w*T` with the field
at `w*T - T`, so the end of the loop equals the start, and renormalise the variance
so the blend does not dip in the middle:

```glsl
float A = plume(q, ph * T);
float B = plume(q, ph * T - T);
float w = ph;
float m = 0.12;                                     // the field's mean
float f = m + ((A - m) * (1.0 - w) + (B - m) * w) / sqrt((1.0 - w) * (1.0 - w) + w * w);
```

**Removing what is baked in.** When the wallpaper already shows the thing you
animate (the mug's steam, the left streaks, the floor rows), build a clean plate in
memory (`live/plate.py`: mask from the difference against the v1 plate, clone-fill
along rows) and draw the loop over it. Never edit the wallpaper file.

**Checking for seams.** Render frames at the wrap and in the middle and compare the
mean frame-to-frame difference in the loop's region. Equal numbers mean no seam
(steam 0.22 at the wrap vs 0.25 mid-loop; rows 0.115 vs 0.124):

```bash
OFF_LOOP0=1000000 tools/offscreen.py bg "/tmp/seam/f_%.png" 5.97 6.0 6.03 2.5 2.53
```

## Event animations

Short, skippable, and they leave nothing behind:
- **Intercept** (login/unlock): the burn-in's canonical sequence — hold, tear, ring,
  flame, turn, sign-off, a fading ghost. Total about 4 s plus a 3 s ghost.
- **Transmission** (critical notification): targeting brackets around the
  notification, a 150 ms interference band, a red edge pulse, the ghost on dismissal.
- **Codec call** (notable real events): a corner panel with the voice's real
  amplitude envelope and the message brightening as it is spoken, in VECTOR's voice.
- **Workspace wipe**: one quick scanline wipe on workspace change.
- **Deck assembly**: panels draw their rules in, brackets land, titles type on
  (`reveal=T + k`, `type_rate`), counters tick up from zero.

Reduced motion (`general.reduced_motion`) drops tears and rotation for crossfades.

## Motion vocabulary

- Spin: rings at 0.05–0.6 rad/s, counter-rotating neighbours.
- Packets: glow dots running a link, count and speed scaled by the real rate
  (log scale), forward phosphor, return amber.
- Flares: a lit node decays over ~6 s; recalled nodes are pulled toward the
  centre by up to 45% along a sine ease.
- Blinks: slow sines (0.5–0.6 Hz) for "needs you"; never strobe.
- Arrivals: a streak, a flash, then deceleration. Departures: lights out, then away.

## Sounds

`live/sound.py` plays the cues in `sounds/` through PipeWire at `sounds.volume`
(0.3), honours the mute state file (`SUPER+SHIFT+M`), and accepts a sink override
(`sounds.sink` or `BROMIGOS_LIVE_SINK`) — test with a null sink, never the speakers.
