# bromigos-live — the live layer

The animated, data-driven layer of the Bromigos desktop: a GPU background behind every
window, the summoned decks and holograms, short event animations, codec calls, the idle
screensaver and the desktop's sound cues. Every moving thing is a real reading or a real
event, except the atmosphere and the emblem (`config.toml` marks which is which).

**Status:** active. One GTK3 process (`python -m live.app`, system Python with
GtkLayerShell, PyOpenGL, numpy, psutil), supervised by `bin/bromigos-live`, started from
Hyprland (`bromigos-live start --login` in the `hyprland.start` autostart of `hypr/bromigos/live.lua`). Part of the desktop described in
`../bromigos/README.md`.

**Every element of the live wallpaper** (what it looks like, what it means, its data,
code, config key and how to change it, plus how to add one) is catalogued in
[docs/ELEMENTS.md](docs/ELEMENTS.md).

## Use

```bash
bromigos-live status            # mode, target vs measured fps, surface mapped/missing, layers on the monitor
bromigos-live restart           # after editing code; config.toml reloads by itself on save
bromigos-live mind focus kb-sync  # open a hologram and drive it (see "Decks")
bromigos-live codec "Deck here. Test." DECK
bromigos-live job -- make build # a long command calls in when it ends
```

The full verb list is the header of `bin/bromigos-live`. Keys are in `AGENTS.md`
(generated) and on the SHORTCUTS panel.

## Layout

| Path | What |
|------|------|
| `bin/bromigos-live` | CLI and supervisor (restarts on crash, gives up after 4 crashes in 2 min) |
| `config.toml` | Every toggle, reloaded on save; documents which layers are data and which decoration |
| `live/app.py` | The daemon: windows, Hyprland and notification events, pause rules, self-healing on monitor hotplug, the control socket |
| `live/scene.py`, `shaders/bg.frag`, `space.glsl`, `rain.glsl`, `denloop.glsl` | The background: the den wallpaper made live, glyph rain, floor pulses, the Drift space layer, the hardware scanner, seamless decorative loops |
| `live/plate.py` | The clean plate: baked steam and streaks removed in memory so loops can redraw them (the wallpaper file is never changed) |
| `live/overlays.py` | The overlay renderer and the built-in overlays: intercept, transmission, holo deck, screensaver, radial menu; `make()` opens any of them |
| `live/deckkit.py` | The base for 3D decks: drag, drift, picking, hover readouts, the Tab cycle, verbs, pollers that live only while a deck is open |
| `live/zoomcam.py` | Zoom and pan for the maps (toward the cursor, eased, fly-to and fit for VECTOR's verbs), the zoom readout, and label placement by room |
| `live/*_deck.py`, `arbiter_deck.py`, `drift_map.py`, `timeline.py` | The decks (below) |
| `live/glkit.py`, `stage.py`, `gadgets.py` | Vector primitives (lines, arcs, glyphs), render targets and bloom, HUD panels and gauges |
| `live/holoview.py` | A compact model from the shared `bromigos/holo` renderer, embedded in a deck |
| `live/starship.py`, `models/starship.holo.npz`, `tools/make-starship.py`, `shaders/ship*` | The Swarm's ship: a procedural model, drawn instanced |
| `live/data.py`, `sources.py`, `arbiter.py`, `history.py` | Data: local machine (psutil, nvidia-smi), the Lab API, Prometheus, git, gh, herdr, ping, ARBITER (GET only), the 72 h minute history |
| `live/vfeed.py` | Reader for VECTOR's event feed |
| `live/codec.py`, `codec_panel.py` | Codec calls (rate-limited voiced transmissions) |
| `live/watch.py`, `hypr.py` | Notification (D-Bus monitor) and lock watching; Hyprland IPC |
| `live/sound.py`, `sounds/` | Cues through PipeWire, one mute file, an optional sink |
| `tools/offscreen.py` | Renders the background or any deck headless (NVIDIA EGL) to PNG or MP4, with scripted verbs and test events |

## Decks

One deck is up at a time: opening another (by key, the radial menu, a verb or VECTOR) closes the one showing (`App.is_deck`, deck plugins included). Decks sit on the top layer (still over every window); the overlay layer above them is for VECTOR's console, notifications and the radial menu.

| Deck | Key | Shows | Verbs |
|------|-----|-------|-------|
| holodeck | SUPER+H | This machine's arc rings, the lab constellation, a compact 3D model; FIELD NOTES (N) | — |
| arbiter | SUPER+G | ARBITER's paper portfolio: the road to live, the tape with causes, the lineup | — |
| timeline | SUPER+T | The last 72 h as a ribbon to scrub | — |
| driftmap | SUPER+M | The lore catalog as a star chart; the lab's services as relays | — |
| mind | SUPER+I | VECTOR's memory and the knowledge base as a constellation | `focus <text>`, `space <kb>`, `clear` |
| ops | SUPER+SHIFT+O | Pushes → CI → Argo → pods, VECTOR's tasks and tool calls | `focus <repo>`, `clear` |
| swarm | SUPER+SHIFT+S | Repos as a star system, herdr agents as starships | `point`, `focus <repo or agent>`, `clear` |
| netmap | SUPER+SHIFT+N | The LAN from UniFi, link traffic, ping latency | `trace <host>`, `clear` |
| replay | SUPER+R | An ARBITER paper round trip as a price ribbon with its causes | `pick …`, `play`, `pause`, `seek` |

Tab cycles holodeck → arbiter → timeline → mind → ops → swarm → netmap → replay.

The maps (Mind, Swarm, Netmap, Drift map) zoom (`live/zoomcam.py`): scroll toward the
cursor, drag pans while zoomed in (Shift+drag or the right button turns), `+`/`-`,
double-click empty space or `0` resets. Detail grows with zoom: Mind's clusters open
into their documents, Swarm's ships get names, the Drift map's minor entries get
labels, and labels only appear where there is room. VECTOR's `focus`, `point`,
`space` and `trace` verbs fly the camera to their target.

## State

- `~/.local/state/bromigos-live/`: `live.log`, `history.npz` + `events.jsonl` (72 h),
  `swarm-seen.json`, the `muted` and `codec-quiet` flags.
- `~/.cache/bromigos-live/`: the clean plate, the kb chart, CI results, the Drift map
  layout, TTS lines; all rebuilt on demand.
- `$XDG_RUNTIME_DIR/bromigos-live.sock`, `bromigos-live.pid`.
- Reads: `~/.local/share/bromigos/lab-token`, `gnosis-vector-read-token` (Mind's
  fallback), the wallpaper choice in `~/.local/state/bromigos/wallpaper/`.

## Performance and rules

30 fps with the desktop visible, 20 under tiled windows, 0 when locked, under a true
fullscreen window or under a full-screen deck. Measured: the daemon about 7–9% of one
core, the GPU under 1%; a deck frame 0.6–1.7 ms median. Heavy reads only while the deck
that needs them is open. Nothing ever draws over application windows.

How to build or change any of it: `../bromigos/skills/hologram-build.md`,
`live-layer-animation.md`, `desktop-style-guide.md`, `data-sources.md`.
