# The live wallpaper, element by element

Every element of the live background and its event animations in one place: what it
looks like, what it means, where its data comes from, the code and config behind it,
what it costs, and how to change it. The rule of the house holds for all of them:
**anything that moves is a real reading or a real event**, except what is marked
*decoration* (the emblem, the atmosphere and the seamless loops), which runs at a
fixed calm pace tied to nothing.

Coordinates are pixels in the 2560×1440 den plate (origin top-left). The code scales
them to the monitor (`sx = w / 2560`, `sy = h / 1440`).

Paths are relative to `linux/.config/bromigos-live/` (installed as
`~/.config/bromigos-live/`). `config.toml` reloads on save; code changes need
`bromigos-live restart`.

## At a glance

| Element | Where | Shows | Data, rate | Config key |
|---------|-------|-------|------------|------------|
| [Oscilloscope](#oscilloscope) | den scope, right of the desk | this machine's network throughput, last 48 s | psutil, 1 s | `background.den` |
| [Relay map](#relay-map) | den's big monitor | the lab's nodes and links, their health and load | Lab API, 25 s | `background.den` |
| [Emblem monitor](#emblem-monitor) | den monitor left of the desk | the burn-in turning (decoration) | none | `background.den` |
| [Meters](#meters) | two analog meters on the desk | left: CPU load; right: GPU load | psutil 1 s; nvidia-smi 1.5 s | `background.den` |
| [Glyph rain and bursts](#glyph-rain-and-bursts) | deep space, top of the screen | rain: CPU load; bursts: notifications, lab alerts, ARBITER fills | psutil 1 s; events | `[rain]` |
| [Floor pulses](#floor-pulses) | the den's floor grid | download (toward you) and upload (away) | psutil, 1 s | `[floor]` |
| [Ships and debris](#ships-and-debris) | the open sky and the den's window (behind the station's art), at many headings and three depths | network throughput as traffic density | psutil, 1 s | `space.traffic` |
| [Stars](#stars) | deep space | decoration | none | `space.stars` |
| [Relay beam](#relay-beam) | from the station, up and left | lab all green; pulse speed = ingress requests/s | Lab API, 25 s | `space.relay_beam` |
| [Health tint](#health-tint) | space and rain | amber: running hot or lab link stale; red: a node or service down | Lab API, sensors | `space.health_tint` |
| [X-ray sweep](#x-ray-sweep) | a beam across the screen, schematic over the den | this machine's parts with live readings | snapshot at each pass | `[sweep]` |
| [Workspace wipe](#workspace-wipe) | a line down the screen | a workspace change | Hyprland event | `events.workspace_wipe` |
| [Intercept](#intercept) | full screen, once | login or unlock | session events | `events.intercept_on_*` |
| [Transmission](#transmission) | around the notification | a critical notification | D-Bus notifications | `events.critical_flash` |
| [Codec calls](#codec-calls) | corner panel, bottom right | notable real events, spoken | events | `[codec]` |
| [Screensaver: planet and station](#screensaver-planet-and-station) | full screen after 8 min idle | local hour; lab services; clock | Lab API, clock | `[screensaver]`, `space.planet`, `space.station` |
| [Loops: steam, streaks, rows](#loops-steam-streaks-rows) | mug, left edge, floor | decoration | none | `[loops]` |
| [Plugin shader layers](#plugin-shader-layers) | anywhere, behind windows | whatever the layer says (real readings only) | `u_load`, `u_net`, `u_health` | `layers/<name>.json` |
| [Sound cues](#sound-cues) | (audio) | terminal opened, notification, critical, intercept | events | `[sounds]` |

| [Worlds](#worlds) | the whole background, when the theme has one (Mire, Tidewell) | everything below, as a scene | see the world's table | `[world]`, the theme's `live/world.toml` |

The summoned decks (holo deck, ARBITER, timeline, Drift map, Mind, Ops, Swarm, Network,
Replay) and the radial menu are overlays you open, not part of the wallpaper; they
are in `../README.md` ("Decks") and the `hologram-build` skill.

## How the background is drawn

One GTK window on the layer-shell BACKGROUND layer (behind every window), one GL
context. Each frame `live/scene.py` `Background.render()`:

1. reads the latest snapshot from `live/data.py` (`Data.snapshot()`; the pollers run
   on their own threads, so a frame never waits on I/O);
2. draws the emissive gadgets (the relay map) into an offscreen target and blooms it;
3. runs one full-screen shader, `shaders/bg.frag`, which includes `rain.glsl`
   (palette, hashes, glyphs, rain), `space.glsl` (stars, ships, beam, tint, planet)
   and `denloop.glsl` (loops), with every reading passed as a uniform;
4. draws the opt-in plugin layers (`live/plugins.py`) on top.

Frame rate: 30 fps with the desktop visible, 20 under tiled windows, 0 when locked,
under a true fullscreen window or under a full-screen deck (`App.refresh_state()` in
`live/app.py`). Data polling slows (about 3–4×) while paused. Measured: the daemon
7–9% of one core, the GPU under 1%.

When the background is not there, `bromigos-live status` says why:

| Status | Meaning | What happens |
|--------|---------|--------------|
| `background off (toggled off: …)` | the operator turned it off (SUPER+SHIFT+B, `bromigos-live toggle`) | stays off; never healed back on, kept across config reloads |
| `background off (config: …)` | `background.enabled = false` in `config.toml` | stays off until the config says otherwise |
| `surface=FAILED`, `FAULT: background failed to start (…)` | creating the window failed (no display, no monitor, a GL error) | `App.heal()` retries after 30 s, 60 s, 2 min, then every 5 min; toggling it on retries at once |
| `surface=MISSING` | the window existed but the compositor dropped it (monitor off, output removed) | healed on hotplug, unlock, display-on and every 30 s |
| `waiting for the output` | the monitor is gone | the window is recreated when it returns |

At start, `live/app.py` `wait_for_display()` waits up to 60 s for a Wayland socket GTK can
open with a monitor; without one it exits with code 3 and the supervisor
(`bin/bromigos-live`) starts it again, or stops when no Wayland session is left.

Where each layer may draw:
- *Deep space* is the wallpaper's dark sky: `u_space_rect` (x 0–2400, y 34 to the
  floor horizon) and only on dark pixels (the shader's `lum_mask`, wallpaper
  luminance under about 0.1), so nothing paints over the art.
- *Den screens* are the rectangles in `DEN` (`live/scene.py`), fitted by hand to the
  approved den images.
- *The floor* is below `floor.horizon_y`, left of `floor.max_x`.

## Elements

### Oscilloscope

- **Looks like:** a green trace on the den's small scope, a carrier wave whose
  amplitude swells and falls, over a faint grid. Rect `DEN["wave"]` = (1475, 762,
  124, 110).
- **Shows:** this machine's network throughput (download + upload) over the last
  48 seconds, newest on the right; amplitude = log10(1 + bytes/s) / 7. The carrier's
  wiggle itself is decoration; its envelope is the data.
- **Data:** `psutil.net_io_counters` in `Data._local_loop`, every 1 s (`rx_hist`,
  `tx_hist`, 48 samples; loopback, docker, bridges and VPN interfaces skipped).
- **Code:** `Background.render()` builds `self.wave`; `bg.frag` `den()` first block;
  uniforms `u_wave_rect`, `u_wave[48]`.
- **Config:** `background.den` (all four den screens together).
- **Craft overhead** (`kind = "flyby"`, `live/actors.py`): now and then one of the world's
  `[[actors.craft]]` crosses the sky at a random distance (nearer: bigger, faster, less
  haze), behind the layers in front of its `depth`. Time runs toward the next pass at
  `1 + gain x` the signal's level (network: busier, sooner), `every = [min, max]` seconds
  apart, `max` at once; `sky = [top, bottom]` keeps the whole craft inside a band (Tidewell:
  above the trawlers' masts). Each craft has nav lamps (`blink = "strobe"` or a beacon's
  period), a moonlight rim on its top edges (`rim`), the night air's haze (`haze`), exhaust
  `trails` laid where it flew that drift and fade, and with `clouds` the sky layer's lit
  clouds (`cloud_luma`; the moon's disc stays clear) hide it and its lamps. The mirror
  water reflects it like everything behind the water. Off with the `ships` switch
  (`bromigos anim off ships`, `space.traffic`) and under `general.reduced_motion`. A pass
  costs about 0.2 ms of CPU a frame. Test: `w event flyby` or `w event flyby:<craft id>`.
- **Cost:** measured with the real art at 2560x1440, rendering in real time at 30 fps (RTX
  5070, Ryzen 7 3700X): Mire (five agents, Hollis's loop, the head and hand loops, fireflies)
  8.8% of one core for the whole process, Tidewell 7.0%; a steady frame about 1 ms of CPU,
  GPU 0.3-2 ms. Seamless loops are decoded once and played from the GPU: each runs an
  ffmpeg process (4-6% of a core) only for its first pass, and one-shot clips stream while
  they play. Paused, nothing decodes. The den: 0.56 ms a frame.
- **Try it without switching themes:** `tools/offscreen.py world out.mp4 20` with
  `OFF_WORLD=<theme dir>` and `OFF_SCRIPT` steps `w set <signal> <value>`, `w event
  <name>`; on the desktop, with a world up: `bromigos-live world state|event critical|
  set cpu 0.95|clear|rollcall`.
- **Config:** `[world]`: `enabled`, `dir`, `idle_after = 90`, `ambient_sounds`.

### Mire

| Thing | Shows | Signal |
|---|---|---|
| Sleeper heads (three, in the foreground water) | the first three herdr agents (oldest first): an agent starts, bubbles rise, a swell, the head breaks the surface and its eyes boot with a flicker, then a slow working pulse spilling light on the water and pads; needs you: it rises a little, turns to you, the eyes double-flash amber (red on an error); finished: it submerges, rings spread, the last bubbles rise | `agents` |
| Sleepers wading (moss-covered exo-frames) | further agents: wading among the wrecks, eye-lamps lit (working); stop, turn to you, the eye flashes amber (needs you); settle into the water (finished); sink away (closed) | `agents` |
| Hollis (the keeper) | fishing while you work, nodding in his rocking chair when idle, slumped with the lantern dimmed when locked | `user` |
| His line | taut on every ARBITER paper fill; a fish comes up for a win, a boot for a loss, a twitch for an opening fill | fills |
| Herons | a heron rises off the shore for a notification; a critical one flies at the screen, red-eyed | `notify`, `critical` |
| Fireflies (`live/fireflies.py`) | this machine's network throughput: live particles on a slow curl flow, each blinking on its own rhythm, near ones reflected directly below; a handful when idle, hundreds in a big download (smoothed over 3 s), a few more in deep night; they scatter from a Sleeper rising or going under | `net` |
| Mist, rain, thunder | CPU: mist thickens, then drizzle, a downpour on the water, lightning near 100% | `cpu` |
| Two eyes, a long shape | lab trouble: eyes by the shack's stilts at health 1, a long shape too at 2 | `health` |
| The crashed gunship, the wreckage, the boat | the scene (art only) | — |
| The mast's light | the lab all green | `lab_green` |
| The drone by the lantern | VECTOR: hovering (idle), circling amber (thinking), pulsing (speaking), facing you (listening), flickering red (error), gone (off) | `vector` |
| Frogs (on pads and on the heads) | your activity: croaking (puffed throat, a croak cue) and hopping pad to pad while you work, still when idle or locked | `user` |
| Crickets (sound) | your activity: often while you work, rarer when idle, none when locked | `user` |
| Moon, light | the real moon; dusk, night and dawn by the clock | clock |
| Stars | faint, twinkling through the canopy gaps, fading into the mist at the horizon; brightest in deep night, gone by day | clock |

### Tidewell

The sea at night seen from just under the surface: the waterline a fifth of the way
down, a strip of sky with Greywater Light small on its rock in the upper right, and the
water column below as the stage.

| Thing | Shows | Signal |
|---|---|---|
| The Choir (glowing swimmers) | herdr agents: gliding through the deep with a cyan glow; rise, face you and breach with light and spray (needs you); dive leaving a trail (finished) | `agents` |
| Maren (the keeper) | a tiny figure in the lamp room: moving about while you work, sitting by the glass when idle, asleep with the room dark when locked | `user` |
| Greywater Light's beam | sweeps the surface strip; its colour is lab health (white, amber, red), its turn the ingress rate | `health`, `ingress` |
| Storm | rain and lightning on the surface strip when something in the lab is down; the flashes flicker down the light shafts | `storm` |
| Light shafts, caustics | the moon's or the day's light under the surface, moved by the swell | clock, `cpu` |
| Hulls at the surface | trawlers coming in (download, left to right), haulers going out (upload), seen from below with their running lights | `net_rx`, `net_tx` |
| Jellyfish blooms | notifications, rising through the water column; red when critical | `notify`, `critical` |
| Silver fish in the moored trawler's net | ARBITER fills: green flashes for a win, red for a loss, silver for an opening | fills |
| A school of fish, seabirds | your activity: schooling and wheeling while you work, still when idle, gone when locked | `user` |
| The swell | CPU | `cpu` |
| The tide | the moon, computed locally | clock |
| The lamp-drone under the surface | VECTOR | `vector` |

## The den plate and its variants

The fitted elements (the four den screens, the floor pulses, the loops) only line up
with one family of images, so they switch on only for approved ones:

- Every approved den image is composited onto the same **v1 plate**
  (`background.den_plate`), so all variants share its geometry.
- `[background.den_plates]` maps each approved image's **sha1** to a variant name
  (`den`, `empty`, `masked`, `v1`). `Background._load_under()` hashes the current
  wallpaper; a match turns on the fitted overlays and the clean plate, anything else
  is drawn as is with only the generic layers (rain, space, sweep, wipe), and the log
  says "not an approved den variant".
- The current choice is local state (`~/.local/state/bromigos/wallpaper/den.jpg`,
  switched by `bromigos-wallpaper`), never a tracked file; the committed canonical link
  is the fallback.
- **Adding a variant:** composite it on the v1 plate at the same size and position,
  render it offscreen and check every fitted rect still sits on its screen, then add
  its sha1 under `[background.den_plates]` and, if its mug should steam, its name to
  `loops.steam`. Never edit or re-save the wallpaper file to make something fit.
- **Fitting coordinates:** everything fitted is in plate pixels: the `DEN` rects
  (`live/scene.py`), the floor fit (`[floor]`), and `live/plate.py` (`STEAM_BOX`,
  `HORIZON`, `FLOOR_X1`, `ROWS`). Find a rect by opening the plate at 100% in an image
  viewer and reading the corners; then render (`tools/offscreen.py bg out.png 2`) and
  look at the crop at full size. The plate is 16:9; other resolutions scale.

## Adding a new element

1. **Decide what it means.** Name the real reading or event it shows, or mark it as
   decoration and keep it calm. If it needs a reading the snapshot doesn't have, add it
   to `live/data.py` in the loop with the right rate (`_local_loop` 1 s, `_slow_loop`
   5 s, `_gpu_loop` 1.5 s, `_cluster_loop` 25 s) and read it with `d.get(key)`;
   polling never happens in the frame.
2. **Pick the route.** A self-contained effect over the whole background with only
   load, network and health: a plugin layer (`layers/`, no core edit; the
   `live-shader-layer` skill). Anything fitted to the den, using other data, or
   interacting with the existing layers: core (`scene.py` + `bg.frag`).
3. **Fit it.** For a den screen, add its rect to `DEN` in plate coordinates (see
   above) and pass it scaled with `self._px(DEN["name"])`. For sky elements stay
   inside `u_space_rect` and multiply by `sky` (dark pixels only). Never cover the
   figure or the desk art.
4. **Uniforms.** Declare `uniform vec4 u_<name>;` in `bg.frag` (pack related values
   into one vec4), set it in `Background.render()` with `f.f("u_<name>", ...)`, write
   the drawing as a function (`vec3 my_thing(vec2 px)`), and call it in `main()` or,
   for a den screen, in `den()` with the `glass()` helper.
5. **Pause rules come free.** The background stops at 0 fps when locked, under
   fullscreen or under a deck; don't add timers of your own. Smooth readings toward
   their target per frame (like `meter_v`) so they don't jump at 1 Hz.
6. **Config key.** Add a toggle (and any tuning) to `config.toml` under the right
   section with a comment saying whether it is data or decoration, and read it with
   `cfg.get(...)` and a default, so an old config still works.
7. **Test.** `tools/offscreen.py bg out.png 2 5` renders real frames headless; check it
   at full size and at 1280×720; for loops, check the seam. Watch the frame cost with
   `bromigos-live status` after `bromigos-live restart`.
8. **Document it.** Add a row to the table at the top and a section here, in the same
   fields. If it adds a key, also update the comment block at the top of
   `config.toml` (data vs decoration).

## Worked examples

### Change what an element shows: the left meter shows RAM

The left meter reads `cpu`; memory is already in the snapshot as `mem` (percent, from
`psutil.virtual_memory`, every 1 s). In `live/scene.py`, `Background.render()`:

```python
for i, k in enumerate(("cpu", "gpu")):          # before
for i, k in enumerate(("mem", "gpu")):          # after: left = RAM, right = GPU
```

Nothing else changes: the needle maps 0–100 to the scale, eases the same way, and the
shader doesn't know what it shows. Then update this file's "Meters" row and section
("left = memory in use"), render (`tools/offscreen.py bg /tmp/m.png 3`) and look at
the meter crop, `bromigos-live restart`. VECTOR does this through his build loop
(`update-visualization` skill): `build_begin`, render before, change, render after,
`build_apply` with "Updated: the den's left meter shows memory instead of CPU".

### Add a new element: a disk-activity lamp on the den

A small lamp that glows with disk writes. Disk throughput is in the snapshot already
(`disks`: per-disk read and write bytes/s, every 1 s).

1. Fit: pick an unused lit spot on the desk art and add `"lamp": (x, y, w, h)` to `DEN`
   (plate pixels).
2. Data to uniform, in `Background.render()`:
   ```python
   w = sum(v["w"] for v in (d.get("disks") or {}).values())
   self.lamp_v += (min(math.log10(1 + w) / 8.0, 1.0) - self.lamp_v) * a   # eased; init 0.0 in __init__
   f.f("u_lamp", *self._px(DEN["lamp"]))
   f.f("u_lamp_v", self.lamp_v)
   ```
3. Shader, in `bg.frag`: `uniform vec4 u_lamp; uniform float u_lamp_v;` and in `den()`:
   ```glsl
   m = glass(px, u_lamp, uv, g);
   if (m > 0.0) c = mix(c, g + AMBER * u_lamp_v * exp(-dot(uv - 0.5, uv - 0.5) * 8.0), m);
   ```
4. Config: it rides on `background.den`; give it its own toggle if it should be
   switchable.
5. Test offscreen, check the frame cost, add its row and section here.
