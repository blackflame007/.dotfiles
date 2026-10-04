# bromigos-holo

The desktop's Stark-lab hologram system: one renderer, two faces.

- **VECTOR** (SUPER+E shows or minimizes, hold SUPER+V talks, SUPER+SHIFT+V mutes): the SpacePort's ancient caretaker construct (canon: platform `agents/network/vector.yaml`), chipper, prim, precise and devoted to protocol. He never leaves his post at the arrivals pad: the Wick's console keeps a line open to him over the relays, and he answers from there ("ARRIVALS · LINE OPEN"). He calls the operator "host", never gives the host an arrival number, and never names BLACKFLAME. (He replaced PILOT on 2026-10-04; the old `pilot` verbs still work.) His hologram is a construct of relay light (dial bezel, six-blade iris, diamond core, two tuning-dial gimbals, three whip antennae, a spark) that listens (iris wide, whips up), consults (amber, darting), speaks (iris pulses with the voice), logs anomalies, and hums between arrivals (drifting notes, visual only). Whatever he looks up appears as a live model on his side table, with readouts.
- **Gallery** (SUPER+O): the five models from `../brand/3d/` on the projection table. Drag to rotate, scroll or Space to explode, click a part (or its readout) to isolate it, ←/→ or 1–5 to switch models, S to scan, R to reset, Esc to close. Every part shows a live reading; colours follow its status (phosphor ok, amber warn, red critical, grey no data).

## Living with VECTOR on screen

- **Click-through.** Only the chat entry and the MINIMIZE button take the mouse (a layer-shell input region); every other pixel of the hologram passes clicks to the window behind it, and the backdrop is nearly clear so you can see that window.
- **Keyboard on demand.** SUPER+E maps VECTOR with on-demand keyboard interactivity, so it gets the keyboard as it opens. Esc hands the keyboard back (VECTOR stays up), a click on any other window takes it back too, and a click on the entry gives it to VECTOR again. Shift+Esc minimizes.
- **Minimized, still working.** SUPER+E (or MINIMIZE, or Shift+Esc) only hides the window. A running turn finishes, its tools run, the reply is spoken if voice is on, and it waits in the transcript for the next open. A quiet notification (no live-layer chirp: `x-bromigos-sound:none`) shows the reply, and the bar's **VECTOR pip** (waybar `custom/vector`, the iris icon) shows idle, thinking, speaking, listening or trouble, plus the unread count; click it to show or minimize, right-click to mute. After two quiet minutes VECTOR minimizes itself unless you're typing. `bromigos-holo stop` waits for a running turn or queued speech (up to 90 s; `stop now` doesn't).
- **Never one model.** The brain tries `hive` (LiteLLM's default alias: Qwen3.8-Flash-Next with Nemotron-Lightning behind it), then `nemotron-lightning-30b` (DGX Spark) by name, then `qwen3.8-flash-next`. LiteLLM fails over on errors, but a wedged backend hangs, so each model gets 9 s to start answering; on a timeout, connection error, 5xx or 429 the same turn moves to the next model, the transcript shows an amber "rerouting to …" line, and the failed model is skipped for two minutes. Once an answer is streaming only a 45 s silence counts as failure. If every model fails VECTOR says so, in character, on screen and aloud. Thinking stays off on every route.

## Pieces

| File | What |
|------|------|
| `bin/bromigos-holo` | Launcher and control: `vector` (show/minimize), `vector-show`, `vector-hide`, `ask "…"`, `gallery [model]`, `ptt on/off`, `mute`, `status`, `stop [now]`, `restart`, `log`, `snap vector|gallery PATH` (save what a window renders) |
| `../../waybar/scripts/vector.py` | The bar's VECTOR pip, read from `$XDG_RUNTIME_DIR/bromigos-vector.json` (written by the daemon on every change, with SIGRTMIN+9 to waybar) |
| `holo/app.py` | The daemon (system python, GTK3 layer-shell, overlay layer). Windows exist only while summoned; hidden ones render and poll nothing |
| `holo/render.py`, `shaders.py`, `gl.py`, `text.py` | The shared renderer: projection table (emitter bed, rotating rings, light cone), part-indexed models (depth prepass, fresnel shell, topographic slices, scan band, fat AA edges with hidden-line ghosting), 2D overlay (leader lines, label boxes, Pango text), quarter-res bloom, one composite |
| `holo/stage.py` | A model on the table: materialise, explode/assemble, isolate, the scan sweep (it runs when fresh readings land), live part colours, callouts (side columns or a row), CPU picking |
| `holo/fmt.py` | Reader for `.holo.npz` (format in `../brand/3d/README.md`) |
| `holo/live.py`, `bind.py` | Live readings (this machine via psutil and NVML, the Lab, ARBITER read-only), polled only while wanted; part bindings |
| `holo/gallery.py` | The gallery scene |
| `holo/vector/` | `avatar.py` (the construct), `scene.py` (console layout and transcript), `persona.py` (system prompt), `brain.py` (LiteLLM streaming with tools and the model fallback chain), `text.py` (markdown out of display and speech), `tools.py` (allowlisted tools and the audit log), `voice.py` (push-to-talk and speech, desktop side) |
| `holo/voice_server.py`, `voice.json`, `voices/` | Speech in and out, in the venv `~/.local/share/bromigos/venv-tts` (Python 3.12, torch cu130): faster-whisper `large-v3-turbo` on the GPU, Qwen3-TTS speaking VECTOR's designed voice, Kokoro as the fallback, lines cached in `~/.cache/bromigos/vector-tts` |
| `holo/shimmer.py` | The projector shimmer DSP (band-limit, swept comb, quiet ring mod, tiny room), streamable, one knob |
| `holo/pilot/` | Compatibility alias for older callers (`holo.pilot.voice` is `holo.vector.voice`) |
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

## VECTOR's limits

All enforced in `holo/vector/tools.py`, not by the prompt: no shell (fixed argv only), cluster reads through the `pilot-readonly` ServiceAccount (no secrets, configmaps or exec), Prometheus GETs, `gh` read subcommands for bromigos-org, a fixed table of ARBITER console GETs (nothing that trades or arms), Gnosis search only, docs under the repo roots with secret-looking paths refused. Writes: append to FIELD NOTES; actions: launch an allowlisted app or an http(s) URL, toggle a panel, switch the den wallpaper, run the scanner, show holograms. Every call goes to `~/.local/state/bromigos/vector-audit.log`; the conversation to `vector-chat.log`; both stay local. Keys are read from mode-600 files in `~/.local/share/bromigos/` and never logged.

## Voice

Push-to-talk only: `pw-record` runs while SUPER+V is held (cut at 30 s if a release is missed), with a red MIC LIVE readout. No hotword. VECTOR never hears itself on speakers: pressing SUPER+V is a barge-in (playback killed, speech queue cleared, the running turn interrupted); nothing is spoken while the mic is open; the first 350 ms after playback is dropped as speaker drain; VECTOR plays and records through a session-only PipeWire webrtc echo-cancel pair (`vector_aec_sink`, `vector_aec_source`, built on the current default speakers and mic, defaults untouched, suspended when idle; `"echo_cancel": false` in `voice.json` turns it off); and a transcript that repeats a verbatim stretch of what VECTOR said in the last 30 s is dropped. The greeting plays once per session on SUPER+E (again only after four quiet hours), never on push-to-talk or `ask`. Replies are spoken sentence by sentence as they stream, and each sentence streams too.

**The voice (chosen 2026-10-04 after a survey and local benchmark; see below).** Everything is local and every voice is original:

- **Qwen3-TTS 1.7B** (Apache-2.0, via `faster-qwen3-tts`, CUDA graphs) speaks every line from one reference, `voices/vector-ref-A.wav`. That reference was designed from a text description with the VoiceDesign model ("an older English gentleman ... bright, prim and precise ... sing-song"), so the voice is nobody's. `voices/README.md` lists the three designed references and their descriptions. On the RTX 5070: about 0.2 s to first audio, 2.1 to 2.3x realtime, about 4.7 GiB VRAM while loaded. The voice loads when the window opens (about 30 s cold); until it is ready, and if it ever fails, **Kokoro** answers (stock `bm_george` 70% + `bm_fable` 30%, CPU, about 0.8 s for a first sentence).
- **The projector shimmer** (`holo/shimmer.py`) runs on every engine, set by one knob: `"shimmer"` in `voice.json`, from 0 (dry) to 1 (very machine); the default is 0.35.
- **Speech to text** is faster-whisper `large-v3-turbo` on the GPU: about 0.13 s per push-to-talk clip, about 2.3 GiB. Set `"stt": {"model": "small.en"}` for 0.08 s and 0.8 GiB.
- **VRAM:** with both models loaded the voice server holds about 8.2 GiB of the 12 GiB card. Models unload after 10 idle minutes, and the server exits after 30. To make it lighter, use `"stt": {"model": "small.en"}` (saves about 1.5 GiB) or `"qwen": {"model": "Qwen/Qwen3-TTS-12Hz-0.6B-Base"}` (saves about 2 GiB, slightly plainer). Rendered lines are cached by text hash, so repeats start in about 10 ms.
- **Other engines:** `breeze` is the homelab's Breeze TTS 2, top of the open-weights arena, but 2.4x slower than realtime on the shared 5090 in eager mode, so it can't talk live. `fish` works only with a `reference_id` the operator owns, made from his own recording; its key is in `~/.local/share/bromigos/fish-audio-key`. VECTOR's production Fish model is a clone of a game character's voice and is not used anywhere here.
- Set `BROMIGOS_HOLO_SINK` to send the voice to a specific output.

**Benchmark (2026-10-04, RTX 5070, typical first sentence):**

| TTS | First audio | Speed | VRAM | Licence |
|-----|-------------|-------|------|---------|
| Qwen3-TTS 1.7B Base + designed voice, streaming | 0.20 s | 2.1–2.3x realtime | 4.7 GiB | Apache-2.0 |
| Qwen3-TTS 0.6B Base, same | 0.18 s | 2.6x | 2.8 GiB | Apache-2.0 |
| Qwen3-TTS 1.7B, reference `qwen-tts` (no CUDA graphs) | 4.0 s | 0.7x | 4.1 GiB | Apache-2.0 |
| Kokoro-82M (old default), CPU | 0.75–0.85 s | 2.8x | 0 | Apache-2.0 |
| Breeze TTS 2, homelab 5090 (eager) | 1.4–2.1 s | 0.4x | (5090) | research / non-commercial |

| STT (10 push-to-talk clips) | WER | Latency per clip | VRAM |
|-----|-----|------------------|------|
| faster-whisper large-v3-turbo (now) | 2.4% | 0.13 s | 2.3 GiB |
| faster-whisper small.en (before) | 2.4% | 0.08 s | 0.8 GiB |
| distil-large-v3.5 | 3.7% | 0.15 s | 2.3 GiB |
| Parakeet TDT 0.6B v3 (ONNX, CPU) | 3.7% | 0.36 s | 0 |

The clips are clean synthetic speech, so small.en ties turbo here. On the public Open ASR Leaderboard turbo is clearly more accurate on real-world audio, and that is why it is the default.
