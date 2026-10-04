# bromigos-holo

The desktop's Stark-lab hologram system: one renderer, two faces.

- **PILOT** (SUPER+E shows or minimizes, hold SUPER+V talks, SUPER+SHIFT+V mutes): the Wick's console tech, a quick, slightly nervous, eager relay intelligence that has minded the station alone a bit too long. Original character, desktop flavour of the Bromigos lore; it never speaks as BLACKFLAME. Its hologram is a construct of relay light (dial bezel, six-blade iris, diamond core, two tuning-dial gimbals, three whip antennae, a pilot-light spark) that listens (iris wide, whips up), thinks (amber, darting), speaks (iris pulses with the voice) and flinches at errors. Whatever it looks up appears as a live model on its side table, with readouts.
- **Gallery** (SUPER+O): the five models from `../brand/3d/` on the projection table. Drag to rotate, scroll or Space to explode, click a part (or its readout) to isolate it, ←/→ or 1–5 to switch models, S to scan, R to reset, Esc to close. Every part shows a live reading; colours follow its status (phosphor ok, amber warn, red critical, grey no data).

## Living with PILOT on screen

- **Click-through.** Only the chat entry and the MINIMIZE button take the mouse (a layer-shell input region); every other pixel of the hologram passes clicks to the window behind it, and the backdrop is nearly clear so you can see that window.
- **Keyboard on demand.** SUPER+E maps PILOT with on-demand keyboard interactivity, so it gets the keyboard as it opens. Esc hands the keyboard back (PILOT stays up), a click on any other window takes it back too, and a click on the entry gives it to PILOT again. Shift+Esc minimizes.
- **Minimized, still working.** SUPER+E (or MINIMIZE, or Shift+Esc) only hides the window. A running turn finishes, its tools run, the reply is spoken if voice is on, and it waits in the transcript for the next open. A quiet notification (no live-layer chirp: `x-bromigos-sound:none`) shows the reply, and the bar's **PILOT pip** (waybar `custom/pilot`, the iris icon) shows idle, thinking, speaking, listening or trouble, plus the unread count; click it to show or minimize, right-click to mute. After two quiet minutes PILOT minimizes itself unless you're typing. `bromigos-holo stop` waits for a running turn or queued speech (up to 90 s; `stop now` doesn't).
- **Never one model.** The brain tries `hive` (LiteLLM's default alias: Qwen3.8-Flash-Next with Nemotron-Lightning behind it), then `nemotron-lightning-30b` (DGX Spark) by name, then `qwen3.8-flash-next`. LiteLLM fails over on errors, but a wedged backend hangs, so each model gets 9 s to start answering; on a timeout, connection error, 5xx or 429 the same turn moves to the next model, the transcript shows an amber "rerouting to …" line, and the failed model is skipped for two minutes. Once an answer is streaming only a 45 s silence counts as failure. If every model fails PILOT says so, in character, on screen and aloud. Thinking stays off on every route.

## Pieces

| File | What |
|------|------|
| `bin/bromigos-holo` | Launcher and control: `pilot` (show/minimize), `pilot-show`, `pilot-hide`, `ask "…"`, `gallery [model]`, `ptt on/off`, `mute`, `status`, `stop [now]`, `restart`, `log`, `snap pilot|gallery PATH` (save what a window renders) |
| `../../waybar/scripts/pilot.py` | The bar's PILOT pip, read from `$XDG_RUNTIME_DIR/bromigos-pilot.json` (written by the daemon on every change, with SIGRTMIN+9 to waybar) |
| `holo/app.py` | The daemon (system python, GTK3 layer-shell, overlay layer). Windows exist only while summoned; hidden ones render and poll nothing |
| `holo/render.py`, `shaders.py`, `gl.py`, `text.py` | The shared renderer: projection table (emitter bed, rotating rings, light cone), part-indexed models (depth prepass, fresnel shell, topographic slices, scan band, fat AA edges with hidden-line ghosting), 2D overlay (leader lines, label boxes, Pango text), quarter-res bloom, one composite |
| `holo/stage.py` | A model on the table: materialise, explode/assemble, isolate, the scan sweep (it runs when fresh readings land), live part colours, callouts (side columns or a row), CPU picking |
| `holo/fmt.py` | Reader for `.holo.npz` (format in `../brand/3d/README.md`) |
| `holo/live.py`, `bind.py` | Live readings (this machine via psutil and NVML, the Lab, ARBITER read-only), polled only while wanted; part bindings |
| `holo/gallery.py` | The gallery scene |
| `holo/pilot/` | `avatar.py` (the construct), `scene.py` (console layout and transcript), `persona.py` (system prompt), `brain.py` (LiteLLM streaming with tools and the model fallback chain), `text.py` (markdown out of display and speech), `tools.py` (allowlisted tools and the audit log), `voice.py` (push-to-talk and speech, desktop side) |
| `holo/voice_server.py`, `voice.json` | Speech in and out, in the venv `~/.local/share/bromigos/venv`: faster-whisper `small.en` on the GPU, Kokoro on the CPU, lines cached in `~/.cache/bromigos/pilot-tts` |
| `tools/offscreen.py` | Headless renders (EGL) for screenshots and tuning |

## Reusing the renderer

```python
from holo.render import Holo
from holo.stage import Stage
from holo.live import Live
holo, stage = Holo(), Stage("wick", Live())       # inside a current GL 3.3 context
holo.begin(w, h, t); holo.camera(eye, target, 30)  # per frame
stage.update(dt); stage.draw(holo, t)              # table + model; stage.explode_to = 1.0 to explode
stage.draw_callouts(holo, (x, y, w, h))            # leader lines + readouts
holo.end(target_fbo, bg=(0, 0.02, 0, 0.9))       # bloom, composite, overlay
```

## PILOT's limits

All enforced in `holo/pilot/tools.py`, not by the prompt: no shell (fixed argv only), cluster reads through the `pilot-readonly` ServiceAccount (no secrets, configmaps or exec), Prometheus GETs, `gh` read subcommands for bromigos-org, a fixed table of ARBITER console GETs (nothing that trades or arms), Gnosis search only, docs under the repo roots with secret-looking paths refused. Writes: append to FIELD NOTES; actions: launch an allowlisted app or an http(s) URL, toggle a panel, switch the den wallpaper, run the scanner, show holograms. Every call goes to `~/.local/state/bromigos/pilot-audit.log`; the conversation to `pilot-chat.log`; both stay local. Keys are read from mode-600 files in `~/.local/share/bromigos/` and never logged.

## Voice

Push-to-talk only: `pw-record` runs while SUPER+V is held (cut at 30 s if a release is missed), with a red MIC LIVE readout. No hotword. Replies are spoken sentence by sentence as they stream. The default voice is Kokoro's `bm_fable` and `bm_lewis` styles blended 55/45 at 1.15x speed: an original synthetic voice, nobody cloned. `voice.json` can switch to `breeze` (the homelab TTS, voice designed from a text instruction; slow) or `fish` (Fish Audio, only with a `reference_id` you own, such as a model made from the operator's own recording; key in `~/.local/share/bromigos/fish-audio-key`). Set `BROMIGOS_HOLO_SINK` to send the voice to a specific output.
