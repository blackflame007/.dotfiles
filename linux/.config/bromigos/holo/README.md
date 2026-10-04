# bromigos-holo

The desktop's Stark-lab hologram system: one renderer, two faces.

- **PILOT** (SUPER+E types, hold SUPER+V talks, SUPER+SHIFT+V mutes): the Wick's console tech, a quick, slightly nervous, eager relay intelligence that has minded the station alone a bit too long. Original character, desktop flavour of the Bromigos lore; it never speaks as BLACKFLAME. Its hologram is a construct of relay light (dial bezel, six-blade iris, diamond core, two tuning-dial gimbals, three whip antennae, a pilot-light spark) that listens (iris wide, whips up), thinks (amber, darting), speaks (iris pulses with the voice) and flinches at errors. Whatever it looks up appears as a live model on its side table, with readouts.
- **Gallery** (SUPER+O): the five models from `../brand/3d/` on the projection table. Drag to rotate, scroll or Space to explode, click a part (or its readout) to isolate it, ←/→ or 1–5 to switch models, S to scan, R to reset, Esc to close. Every part shows a live reading; colours follow its status (phosphor ok, amber warn, red critical, grey no data).

## Pieces

| File | What |
|------|------|
| `bin/bromigos-holo` | Launcher and control: `pilot`, `ask "…"`, `gallery [model]`, `ptt on/off`, `mute`, `status`, `stop`, `restart`, `log`, `snap pilot|gallery PATH` (save what a window renders) |
| `holo/app.py` | The daemon (system python, GTK3 layer-shell, overlay layer). Windows exist only while summoned; hidden ones render and poll nothing |
| `holo/render.py`, `shaders.py`, `gl.py`, `text.py` | The shared renderer: projection table (emitter bed, rotating rings, light cone), part-indexed models (depth prepass, fresnel shell, topographic slices, scan band, fat AA edges with hidden-line ghosting), 2D overlay (leader lines, label boxes, Pango text), quarter-res bloom, one composite |
| `holo/stage.py` | A model on the table: materialise, explode/assemble, isolate, the scan sweep (it runs when fresh readings land), live part colours, callouts (side columns or a row), CPU picking |
| `holo/fmt.py` | Reader for `.holo.npz` (format in `../brand/3d/README.md`) |
| `holo/live.py`, `bind.py` | Live readings (this machine via psutil and NVML, the Lab, ARBITER read-only), polled only while wanted; part bindings |
| `holo/gallery.py` | The gallery scene |
| `holo/pilot/` | `avatar.py` (the construct), `scene.py` (console layout and transcript), `persona.py` (system prompt), `brain.py` (LiteLLM streaming with tools), `tools.py` (allowlisted tools and the audit log), `voice.py` (push-to-talk and speech, desktop side) |
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
