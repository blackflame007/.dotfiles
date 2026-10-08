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
- **Cost:** negligible (a few ops per pixel inside the rect only).
- **Change it:** the envelope scale is the `/ 7.0` in `render()`; the trace shape is
  `carrier` in `den()`.

### Relay map

- **Looks like:** a small turning constellation on the den's big monitor: the lab's
  nodes as dots with ring markers, links between them with packets running along.
  Rect `DEN["big"]` = (1188, 678, 200, 175).
- **Shows:** the lab cluster's nodes, coloured by health (phosphor ready, amber
  degraded, red down, grey no telemetry), packets per link scaled by the far node's
  CPU, the uplink by WAN throughput and the AI link by model requests per minute.
- **Data:** the Lab API status (`Data._cluster_loop`, every `cluster.poll_seconds`
  = 25 s, never under 20; the endpoint comes from the private overlay).
- **Code:** `gadgets.constellation(..., mini=True, labels=False)` called from
  `Background.rebuild()` (geometry rebuilt every 2 s); painter space 1, turning at
  0.25 rad/s (`p.rot[1]`, `p.ctr[1]` in `render()`); the fresh glass behind it is in
  `bg.frag` `den()`.
- **Config:** `background.den`; `[cluster]` for the source.
- **Cost:** about a hundred instanced primitives; rebuilt 0.5 times a second.
- **Change it:** `gadgets.constellation` is shared with the holo deck and the
  screensaver; `NODES`, `LINKS` and `WAN` at the top of `gadgets.py` place them.

### Emblem monitor

- **Looks like:** the burn-in (ring and flame) on the den monitor left of the desk,
  the ring turning against the clock, faint phosphor noise, a short static burst
  every 17 s. Rect `DEN["emblem"]` = (1090, 920, 158, 143).
- **Shows:** decoration (the emblem is the one element allowed to move for its own
  sake).
- **Code:** `bg.frag` `den()` second block; textures `u_ring`, `u_flame` from
  `live/emblem.py` (`Emblem`, rendered from the canonical SVG); uniform `u_den`
  (on, angle = −t·2π/24, so one turn per 24 s, static burst).
- **Config:** `background.den`.
- **Change it:** the turn rate is the `24.0` in `u_den`; never redraw the emblem by
  hand, it comes from `bromigos/lib/bromigos_emblem.py`.

### Meters

- **Looks like:** two analog panel meters on the desk; the face colour is sampled
  from the art so the live faces match it; scale arc, ticks, a red zone, a needle.
  `DEN["meter0"]` = (1545, 932, 66, 32) on the left, `DEN["meter1"]` = (1555, 1050,
  61, 32) on the right.
- **Shows:** left = CPU load (all cores), right = GPU utilisation, 0–100% across
  ±0.6 rad.
- **Data:** CPU from `psutil.cpu_percent` every 1 s (`Data._local_loop`, key `cpu`);
  GPU from `nvidia-smi -lms 1500` (`Data._gpu_loop`, key `gpu`). The needles ease
  toward the value (`meter_v`, about a quarter-second response).
- **Code:** `Background.render()`: `for i, k in enumerate(("cpu", "gpu"))`; `bg.frag`
  `den()` meter loop; uniforms `u_meter0`, `u_meter1`, `u_meter_v`, `u_meter_face`.
- **Config:** `background.den`.
- **Change it:** see the worked example at the end (the left meter showing RAM).

### Glyph rain and bursts

- **Looks like:** columns of the Drift script (an original 24-glyph set built from
  relay-mast strokes) falling through the dark sky; bright heads, fading tails,
  glyphs that mutate. A burst is a ripple running out sideways from one column,
  brightening and recolouring the rain for about 2.6 s.
- **Shows:** density and speed follow CPU load (density 0.22 + 0.55·min(1.6·cpu, 1),
  speed 0.55 + 1.6·cpu). Bursts: a notification (soft green), a critical
  notification or a lab alert (red), an ARBITER paper fill (amber).
- **Data:** CPU as above; bursts from `App.on_notify` (D-Bus notifications) and
  `App.on_data_event` (`cluster_alert` from the Lab API poll, `arbiter_fill` from the
  ARBITER console poll every `arbiter.poll_seconds` = 30 s, GET only).
- **Code:** `rain()` in `shaders/rain.glsl` (shared with the overlays);
  `Background.burst(kind, x, strength)` fills six ring-buffer slots (`u_burst[6]`:
  x, t0, strength, colour kind); uniforms `u_rain_rect`, `u_rain`.
- **Config:** `[rain]`: `enabled`, `region` (x, y, w, h; default 0, 30, 2390, 600),
  `brightness`, `bursts`.
- **Cost:** two glyph tests per 15×24 cell, only inside the region and on dark pixels.
- **Change it:** a new burst source is one `self.bg.renderer.burst(kind)` call where
  the event lands in `app.py`; a new colour kind goes in `burst_col()`.

### Floor pulses

- **Looks like:** light pulses running along the den floor's converging lanes:
  phosphor toward you, amber away toward the horizon, each with a soft tail.
- **Shows:** this machine's network throughput: download (toward you) and upload
  (away). The share of lanes carrying a pulse and their speed follow
  log10(1 + bytes/s) / 7.5.
- **Data:** `rx`, `tx` from psutil every 1 s.
- **Code:** `floor_pulses()` in `bg.frag`; uniforms `u_floor` (horizon y, vanishing
  x, lane slope, lane offset), `u_floor2` (max x, draw own grid, on), `u_net`.
- **Config:** `[floor]`: `enabled`, and the fit `horizon_y = 926`, `vanish_x = 690`,
  `lane_slope = 0.98`, `lane_offset = 0.71`, `max_x = 1000`; `draw_grid` draws a grid
  when there is no wallpaper grid to ride on.
- **Cost:** a short loop over two directions per floor pixel.
- **Change it:** the fit values must match the art's own lanes; change them only with
  an offscreen render to compare (`tools/offscreen.py bg out.png`).

### Ships and debris

- **Looks like:** small wireframe haulers (container ribs or fins) crossing the open sky
  on straight paths at many headings: horizontal, gentle diagonals (10–35°) and a few
  steep ones (50–70°), either way. Three depth tiers: far ships small (0.5×), slow
  (7–13 px/s) and dim; mid (0.8×, 14–26 px/s); near larger (1.15×), faster (24–38 px/s)
  and bright. Near ships hide far ones where their hulls overlap. Rarely a far ship
  approaches or recedes, its size changing along the path. Amber engines and a trail
  behind, along the heading; a red nav blink. Tumbling debris flecks.
- **Where:** in both of the den's skies: the open sky left of its wall, and the space
  seen through its window on the right. Paths are planned across the whole sky rect
  (x 0–2400, y 34 to the floor horizon, as before 2026-10-06) and aimed alternately
  through each region (`shipmask.FOCUS`), so a ship can slip behind the wall and come back
  into view in the window. Two masks decide where a ship shows, multiplied together:
  - `live/shipmask.py`, fitted to the v1 plate like the den screens: the open sky (left of
    x 995, fading out over the 40 px above the horizon) and the window's glass (inside its
    frame, above the desk, with the monitors and cabinet in front of its lower-left corner
    cut out). Ships never show over the den's screens, frame or interior. Sampled as
    `u_shipmask` in `traffic()`.
  - the dark-pixel test every sky layer uses (`sky` in `bg.frag`: wallpaper luminance under
    about 0.1, nothing under a gadget plate), so the station, the wrecks and anything else
    bright in the art hide the ships passing behind them.
  On any other wallpaper only the second applies, over the whole sky rect.
- **Shows:** network throughput as traffic. Whether a crossing carries a ship is decided
  once, when it starts off-screen: busy if a stable random draw < 0.12 + 0.88·level,
  where level = log10(1 + rx + tx) / 7.3 (`gadgets.traffic_level`). The whole path
  (heading, depth, speed) is fixed then and the ship runs edge to edge whatever the level
  does, so it never appears or vanishes mid-screen; the number of busy lanes follows the
  level with a lag of at most one crossing. Debris density follows a ~25 s average of the
  level, and flecks fade in and out around the threshold instead of blinking.
- **Data:** psutil, 1 s.
- **Code:** `live/traffic.py`: ten lanes (`TIERS`: three far, five mid, two near);
  `Traffic.uniforms(level, rect)` plans each crossing (`heading()`, `path()`: through a
  point in the region, from one edge to another plus the ship's reach), works out every
  position in double precision, and returns them sorted far to near. `traffic()`,
  `ship_dist()` and `ship_cover()` in `shaders/space.glsl` draw them from `u_ship[10]`
  (x, y px, heading, scale), `u_ship2[10]` (brightness, occupied, hull kind) and
  `u_ship_rect`, with `u_shipmask` from `live/shipmask.py`; `u_space.y` is the smoothed level (−1 = off). The background
  (`Background.render()`) and the screensaver each own a `Traffic`.
- **Config:** `space.traffic`.
- **Cost:** measured with all ten lanes busy: 1.03 ms against 0.95 ms with traffic off
  (median background frame, RTX 5070); each pixel skips a ship outside its 150 px reach.
- **Change it:** tiers, speeds and brightness in `TIER`; the heading mix in `heading()`;
  the busy rule in `_new()`; the hull in `ship_dist()` and its silhouette in
  `ship_cover()`. Never decide occupancy in the shader from the live level: that made
  ships pop (fixed 2026-10-06). These are not the Swarm deck's starships
  (`live/starship.py`).

### Stars

- **Looks like:** three parallax layers of twinkling stars drifting slowly.
- **Shows:** decoration.
- **Code:** `stars()` in `space.glsl`; uniform `u_space.x`.
- **Config:** `space.stars`.

### Relay beam

- **Looks like:** a thin beam rising from a point in the right of the sky
  (origin (2000, 370), pointing up and to the left), with three pulses running out
  along it and fading with distance.
- **Shows:** **the lab is all green**: the Lab API link is up, every node is Ready
  and every service is up (`gadgets.all_green`). The beam is simply absent otherwise:
  a stale Lab API link, a node not Ready or a service down turns it off; this machine
  running hot does not (that only tints the sky amber).
  Its pulse speed is 0.12 + min(ingress requests/s, 6) / 12, so a busier ingress
  pulses faster.
- **Data:** the Lab API status, every 25 s (`cluster.nodesReady`, `nodesTotal`,
  `services[*].status`, `traefik.rpsNow`).
- **Code:** `relay_beam()` in `space.glsl`; uniforms `u_space.z` (on), `u_beam`
  (x0, y0, angle, pulse speed), set in `Background.render()`. The screensaver draws
  the same beam from its station; the Drift map has its own beam with the same
  meaning.
- **Config:** `space.relay_beam`.
- **Change it:** origin and angle in `render()` (`bx0, by0`, `-2.5` rad).

### Health tint

- **Looks like:** the whole sky layer (stars, ships, beam) and the rain shift toward
  amber or red. The den screens and floor stay their colour.
- **Shows:** 0 nominal; 1 amber: CPU ≥ 90 °C, GPU ≥ 87 °C, or the Lab API link stale;
  2 red: a lab node not Ready or a lab service down (`gadgets.health`).
- **Data:** sensors (psutil, every 5 s), nvidia-smi, the Lab API.
- **Code:** `health_tint()` in `space.glsl`; uniform `u_space.w`.
- **Config:** `space.health_tint`.

### X-ray sweep

- **Looks like:** a phosphor beam crossing the screen left to right in about 5.5 s;
  behind it, for about half a second, an X-ray schematic of this machine shows over
  the den (rect `DEN["schem"]` = (1000, 560, 860, 660)), darkening the art under its
  lines. SUPER+X pins it, holding SUPER+Z keeps it up while held.
- **Shows:** this machine's real parts (CPU, GPU, memory, drives, board) labelled with
  their readings at the moment of the pass. The beam itself is decoration.
- **Data:** the snapshot, redrawn with Cairo just before each pass (`live/schematic.py`
  `draw()`), every 2 s while pinned or held.
- **Code:** sweep scheduling in `Background.render()`; `_draw_schematic()`; the reveal
  in `bg.frag` `main()`; uniforms `u_sweep`, `u_scan`, `u_scan2`, `u_schem_rect`,
  texture `u_schem`. On demand: `bromigos-live scan`, `scan-pin`, `scan-hold on|off`.
- **Config:** `[sweep]`: `enabled`, `interval = 60` (s between passes), `duration =
  5.5`.
- **Cost:** a texture upload per pass (860×660); otherwise a few ops per pixel.

### Workspace wipe

- **Looks like:** one soft line sweeping down the screen in 0.45 s with a faint glow
  behind it.
- **Shows:** a workspace change (Hyprland `workspacev2` event, `App.on_hypr`).
- **Code:** `Background.wipe()`; `bg.frag` `main()`; uniform `u_wipe`.
- **Config:** `events.workspace_wipe`.

### Intercept

- **Looks like:** a full-screen overlay: the frozen screen holds, tears, the burn-in's
  ring draws, the flame lights, it turns, "TRANSMISSION INTERCEPTED" and the sign-off
  type on, then a ghost fades. About 4 s plus a 3 s ghost; the ghost phase never takes
  input.
- **Shows:** a login (`bromigos-live start --login` from Hyprland's login autostart) or an
  unlock (the daemon's lock watcher, `live/watch.py`).
- **Code:** `Intercept` in `live/overlays.py` (timings `HOLD`, `TEAR`, `RING`, `FLAME`;
  `CAPTION`, `SIGN`); cues `hiss` and `signoff`.
- **Config:** `events.intercept_on_login`, `events.intercept_on_unlock`.
- **Rules:** the canonical burn-in sequence; reduced motion
  (`general.reduced_motion`) swaps the tear and turn for crossfades.

### Transmission

- **Looks like:** targeting brackets snapping around the notification popup, a
  150 ms interference band, a red edge pulse, a ghost when it is dismissed.
- **Shows:** a critical notification (urgency 2 on D-Bus), never while locked.
- **Code:** `Transmission` in `live/overlays.py`; `notification_rect()` finds the popup;
  triggered from `App.on_notify`.
- **Config:** `events.critical_flash`; the cue is `sounds.critical`.

### Codec calls

- **Looks like:** a compact card in the bottom-right corner: channel glyph, a tuning
  dial with the channel readout (CH 01 THE FLOOR, CH 02 THE LAB, CH 03 THE DECK, CH 04
  PRIORITY), the voice's real amplitude as a waveform, the message typing in step with
  the voice.
- **Shows:** notable real events, spoken in VECTOR's voice: notable ARBITER paper fills
  (|realized| ≥ `fill_min_realized` or notional ≥ `fill_min_notional`), lab alerts
  (while VECTOR's own daemon is down; when it is up he briefs them himself), long jobs
  (`bromigos-live job -- cmd`), critical notifications, or `bromigos-live codec "text"
  CHANNEL`.
- **Code:** `live/codec.py` (`Desk` queues, rate limits, voices; `Call`),
  `live/codec_panel.py` (`CodecPanel`).
- **Config:** `[codec]`: `enabled`, `voice` (`"pilot"` is the alias for VECTOR's voice
  server; `"breeze"` skips it for the fallback TTS), `min_gap = 120`,
  `max_per_hour = 8`, `dedupe = 1800`, `on_critical`, `on_lab_alert`, `on_fill`,
  `job_min_seconds`. SUPER+SHIFT+M mutes everything, SUPER+SHIFT+C makes calls silent.
- **Rules:** one call at a time, never while locked or under a fullscreen window, no
  identity frequencies on the readout.

### Screensaver: planet and station

- **Looks like:** after 8 minutes idle (hypridle, `hypr/hypridle.conf`, before the
  10-minute lock): a wireframe gas giant rising from the bottom right, the Drift relay
  station top left with its spokes, the lab constellation, this machine's arc rings,
  the burn-in turning, rain over the whole screen, the time and date in the middle.
  Any key, click or real mouse movement ends it.
- **Shows:** the planet's terminator is the local hour (noon faces you, midnight away;
  `gadgets.local_sun_angle`); the station's spokes are the lab's services, lit = up;
  the rings are this machine's load; the relay beam runs from the station when the lab
  is all green; a "DEGRADED" or "RUNNING HOT" line when health is 2 or 1.
- **Code:** `Screensaver` in `live/overlays.py` (`build()`, `frame()`);
  `gadgets.drift_station`, `gadgets.rings`, `gadgets.constellation`; `planet()` in
  `space.glsl` (uniforms `u_planet`, `u_sun`).
- **Config:** `[screensaver] enabled`, `space.planet`, `space.station`.

### Loops: steam, streaks, rows

- **Looks like:** steam curling up from the mug; glitch streaks on the left edge
  drifting, stretching and fading; the floor grid's rows scrolling toward you.
- **Shows:** decoration. Constant pace, tied to no metric.
- **Code:** `shaders/denloop.glsl` (`den_steam`, `den_streaks`, `den_rows`,
  `den_loops`); phases from `Background.loop_uniforms()` (`u_loop`: each phase
  computed in double precision on the CPU and wrapped by its own period, so every loop
  closes exactly); the baked versions are removed in memory by `live/plate.py`
  (`clean_plate()`), never in the wallpaper file.
- **Config:** `[loops]`: `streaks`, `streak_period = 10`, `rows`, `row_period = 12`,
  `row_amp`, `steam` (the variants whose mug steams), `steam_period = 7`,
  `steam_intensity`.
- **Rules:** see `live-layer-animation.md` ("Seamless loops"); check for seams by
  rendering frames across the wrap.

### Plugin shader layers

- **Looks like:** whatever a layer draws, over the finished background, behind every
  window.
- **Shows:** must be a real reading (the contract gives `u_load` = CPU, GPU, memory,
  VRAM; `u_net`; `u_health`) or the slow ambience the rules allow.
- **Code:** `layers/<name>.frag` + `layers/<name>.json`, loaded by `live/plugins.py`
  (`Layers`); opt-in (`"enabled": true`); each layer's GPU time is measured and it
  switches itself off over `budget_ms` or on a compile error.
- **How:** the `live-shader-layer` skill.

### Sound cues

`live/sound.py` plays `sounds/*.wav` through PipeWire at `sounds.volume` (0.3): a blip
when a terminal opens (`terminal_classes`), a chirp on a notification (not for
`quiet_apps` or a `capture.` category), an alert on a critical one, the hiss and
sign-off in the intercept, a sweep when a Swarm ship warps in. One mute file
(SUPER+SHIFT+M); `sounds.sink` or `BROMIGOS_LIVE_SINK` sends them to another sink (test
with a null sink, never the speakers).

## Worlds

When the current theme (bromigOS: `bromigos theme set mire`) has `live/world.toml`, the
background is that **world** instead of the den: layered art with parallax, a water
plane, effects and actors, every moving thing bound to a real signal. The Wick has no
world, so the den above is drawn exactly as before; `bromigos theme set wick` goes back.
The format (layers, effects, actors, their states, the signals) is documented once, in
bromigOS `docs/theming.md` ("Worlds"); this section is how the live layer runs it.

- **Where it comes from:** `live/world.py` `world_file()`: `$BROMIGOS_WORLD`, then
  `[world] dir`, then `~/.local/state/bromigos/theme/current/live/world.toml` (copied
  there by `bromigos theme set`, which then sends `theme` to the socket).
  `App.check_world()` also compares its signature every 3 s and rebuilds the background
  (a world that fails to load falls back to the den and logs why).
- **Frame** (`World.render()`): the hour's grade and lightning; every layer and actor
  shallower than the water into a back target; `shaders/world.frag` composes the frame
  from it (the water: a mirror reflecting the back target with ripples, rain rings and
  wakes, or a split view with a moving surface, the deep's fog and caustics; then mist,
  fireflies and their reflections, the fishing line, the lighthouse beam, spray, rain);
  then the deeper layers and actors over it. Layers: `world_layer.frag` (the sky layer
  also carries the real moon, the twilight glow, the bolt). Actors: instanced sprites
  from one atlas (`world_sprite.*`) and additive lights (`world_glow.*`).
- **Actors** (`live/actors.py`): `keeper`, `agents`, `signal`, `crowd`, `traffic`,
  `event`; motions and the "needs you" turn-and-signal gesture are shared by all.
  Positions are planned on the CPU in plate pixels (like the ships: nothing pops).
- **Data:** the den's snapshot (CPU, network, lab health, ARBITER fills with their
  realized P&L, notifications); `live/worldfeed.py` while a world is up: herdr's agents
  (2 s, 8 s paused) and VECTOR's state file (a stat every 0.5 s);
  `live/activity.py`: the user working / dozing / asleep (hypridle's listener at 90 s
  in `hypr/hypridle.conf` → `ctl activity idle|active`; until hypridle reads it, the
  pointer (Hyprland IPC, 2 Hz) and focus/workspace events; the lock watch);
  `live/skyclock.py`: the hour's light, the moon's phase and place, the tide, all local.
- **Camera:** the layers sway with the pointer while the user works (parallax), and
  settle home when idle.
- **Video loops** (`live/videoloop.py`, `shaders/world_yuv.frag`): a layer's `video` or
  any actor sprite naming a video file plays it as a GPU texture: one ffmpeg per loop
  (`-hwaccel auto`, `-stream_loop -1`) writing NV12 to a pipe, a reader thread, the
  planes uploaded and converted to premultiplied RGBA on the GPU. Videos advance at the
  start of a frame, only while drawn; a paused layer stops consuming frames so ffmpeg
  blocks (measured: 0.01 s CPU in 3 s paused); a loop unused for 20 s is stopped.
  Offscreen renders wait for every frame (`BROMIGOS_WORLD_SYNC`). Alpha: `stacked`
  (colour over grey alpha, hardware decoded), `native` (VP9 alpha, libvpx), `none`.
- **No data, no inhabitant:** an effect or actor with `requires = "lab"` (or any signal)
  isn't drawn while that source is unavailable: Mire's mast light and Tidewell's beam
  without the Lab API.
- **Sound:** the world's `[sounds] ambient` cues (Mire's frogs and crickets) through
  `live/sound.py`: often while the user works, a third as often when idle, none when
  locked; mute and `sounds.volume` apply; `[world] ambient_sounds = false` stops them.
- **Roll call:** at login (after the intercept) the world's lights wake one by one
  (`[rollcall]`; its `sound` is reserved).
- **Pause rules:** the den's: 30 fps visible, 20 under windows, 0 locked, under a
  true fullscreen window or a full-screen deck. A world catches up when it resumes:
  after an unlock the keeper wakes over a few seconds, the lantern brightening.
- **Cost:** a frame's own CPU, best of 15 batches of 40 frames at 2560×1440 (RTX 5070,
  Ryzen 7 3700X): Mire 0.59 ms, Tidewell 0.74 ms, the den 0.56 ms; at 30 fps that is
  about 2% of one core either way. Mire at full tilt (420 fireflies in a big download,
  five agents) 1.1 ms, about 3.3%. GPU 0.2–0.4 ms a frame (the den 0.44). The world's own
  pollers add about 0.4% (herdr every 2 s). So a world costs what the den does in the
  daemon (7–9% of one core with GTK and the data threads). Whole-process headless runs
  (`tools/offscreen.py bench 40 world`) vary 3–8% with the machine's other load.
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
