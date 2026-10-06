# bromigos-holo

The desktop's Stark-lab hologram system: one renderer, two faces.

- **VECTOR** (SUPER+E shows or minimizes, hold SUPER+V talks, SUPER+SHIFT+V mutes): the SpacePort's ancient caretaker construct (canon: platform `agents/network/vector.yaml`), chipper, prim, precise and devoted to protocol. He never leaves his post at the arrivals pad: the Wick's console keeps a line open to him over the relays, and he answers from there ("ARRIVALS · LINE OPEN"). He calls the operator "host", never gives the host an arrival number, and never names BLACKFLAME. (He replaced PILOT on 2026-10-04; the old `pilot` verbs still work.) His hologram is a construct of relay light (dial bezel, six-blade iris, diamond core, two tuning-dial gimbals, three whip antennae, a spark) that listens (iris wide, whips up), consults (amber, darting), speaks (iris pulses with the voice), logs anomalies, and hums between arrivals (drifting notes, visual only). Whatever he looks up appears as a live model on his side table, with readouts.
- **Gallery** (SUPER+O): the five models from `../brand/3d/` on the projection table. Drag to rotate, scroll or Space to explode, click a part (or its readout) to isolate it, ←/→ or 1–5 to switch models, S to scan, R to reset, Esc to close. Every part shows a live reading; colours follow its status (phosphor ok, amber warn, red critical, grey no data).

## Living with VECTOR on screen

- **Click-through.** Only the chat entry and the buttons (MINIMIZE, ◉ CONVERSATION, ☰ HISTORY, ■ STOP while a command runs), and the history panel while it's open, take the mouse (a layer-shell input region); every other pixel of the hologram passes clicks to the window behind it, and the backdrop is nearly clear so you can see that window.
- **Keyboard on demand.** SUPER+E maps VECTOR with on-demand keyboard interactivity, so it gets the keyboard as it opens. Esc hands the keyboard back (VECTOR stays up), a click on any other window takes it back too, and a click on the entry gives it to VECTOR again. Shift+Esc minimizes.
- **Minimized, still working.** SUPER+E (or MINIMIZE, or Shift+Esc) only hides the window. A running turn finishes, its tools run, the reply is spoken if voice is on, and it waits in the transcript for the next open. A quiet notification (no live-layer chirp: `x-bromigos-sound:none`) shows the reply, and the bar's **VECTOR pip** (waybar `custom/vector`, the iris icon) shows idle, thinking, speaking, listening or trouble, plus the unread count; click it to show or minimize, right-click to mute. After two quiet minutes VECTOR minimizes itself unless you're typing. `bromigos-holo stop` waits for a running turn or queued speech (up to 90 s; `stop now` doesn't).
- **Never one model.** The brain tries `hive` (LiteLLM's default alias: Qwen3.8-Flash-Next with Nemotron-Lightning behind it), then `nemotron-lightning-30b` (DGX Spark) by name, then `qwen3.8-flash-next`. LiteLLM fails over on errors, but a wedged backend hangs, so each model gets 9 s to start answering; on a timeout, connection error, 5xx or 429 the same turn moves to the next model, the transcript shows an amber "rerouting to …" line, and the failed model is skipped for two minutes. Once an answer is streaming only a 45 s silence counts as failure. If every model fails VECTOR says so, in character, on screen and aloud. Thinking stays off on every route.

## Pieces

| File | What |
|------|------|
| `bin/bromigos-holo` | Launcher and control: `vector` (show/minimize), `vector-show`, `vector-hide`, `ask "…"`, `gallery [model]`, `ptt on/off`, `mute`, `voice …`, `conversation`, `shell off|on`, `history` (toggle; `history open N`, `history continue` for scripts), `status`, `stop [now]`, `restart`, `log`, `snap vector|gallery PATH` (save what a window renders) |
| `../../waybar/scripts/vector.py` | The bar's VECTOR pip, read from `$XDG_RUNTIME_DIR/bromigos-vector.json` (written by the daemon on every change, with SIGRTMIN+9 to waybar) |
| `holo/app.py` | The daemon (system python, GTK3 layer-shell, overlay layer). Windows exist only while summoned; hidden ones render and poll nothing |
| `holo/render.py`, `shaders.py`, `gl.py`, `text.py` | The shared renderer: projection table (emitter bed, rotating rings, light cone), part-indexed models (depth prepass, fresnel shell, topographic slices, scan band, fat AA edges with hidden-line ghosting), 2D overlay (leader lines, label boxes, Pango text), quarter-res bloom, one composite |
| `holo/stage.py` | A model on the table: materialise, explode/assemble, isolate, the scan sweep (it runs when fresh readings land), live part colours, callouts (side columns or a row), CPU picking |
| `holo/fmt.py` | Reader for `.holo.npz` (format in `../brand/3d/README.md`) |
| `holo/live.py`, `bind.py` | Live readings (this machine via psutil and NVML, the Lab, ARBITER read-only), polled only while wanted; part bindings |
| `holo/gallery.py` | The gallery scene |
| `holo/vector/` | `avatar.py` (the construct), `scene.py` (console layout and transcript), `persona.py` (system prompt), `brain.py` (LiteLLM streaming with tools and the model fallback chain), `text.py` (markdown out of display and speech), `tools.py` (allowlisted tools and the audit log), `voice.py` (push-to-talk and speech, desktop side) |
| `holo/voice_server.py`, `voice.json`, `voices/` | Speech in and out, in the venv `~/.local/share/bromigos/venv-tts` (Python 3.12, torch cu130): faster-whisper `large-v3-turbo` on the GPU, Qwen3-TTS speaking VECTOR's five voices from local references (`voices/make-refs.py`), Kokoro as the fallback, the dial scratch, lines cached in `~/.cache/bromigos/vector-tts` |
| `holo/vector/mood.py` | Mood from the facts (tool results that show trouble) |
| `tools/voice-demo.py` | Render a tagged reply to a wav exactly as the desktop would speak it |
| `holo/shimmer.py` | The projector shimmer DSP (band-limit, swept comb, quiet ring mod, tiny room), streamable, one knob per voice; and the dial scratch between voices |
| `holo/pilot/` | Compatibility alias for older callers (`holo.pilot.voice` is `holo.vector.voice`) |
| `holo/vector/history.py` | Conversation history from `vector-chat.log`: sessions, titles, search, the `conversation_history` tool |
| `tools/kb-sync.py` | Syncs the operator's docs into the Gnosis knowledge base (`kb-*` spaces); nightly via `bromigos-kb-sync.timer` |
| `tools/offscreen.py` | Headless renders (EGL) for screenshots and tuning (`HISTORY_OPEN=1` renders the console as it looks under the history panel) |

## Memory

VECTOR keeps a long-term memory in Gnosis, the homelab memory service (`holo/vector/memory.py`). His scope is tenant `bromigos`, space `vector`, agent `vector`, user `operator`, `private_user`.

- **Tokens.** Every call goes through the homelab's **gnosis-gate** (`helm/gnosis-gate`, at `https://gnosis.redacted/gate/`) with two narrow tokens. Gnosis itself has only one service token for everyone, and its operator tokens share that value, so the desktop never holds it.
  - `gnosis-vector-write-token`: add, search, list, context and delete in his own scope only.
  - `gnosis-vector-read-token`: read his scope, and search `arbiter-research` and `arbiter-signals`.
  - Both live in Vault `secret/<vault-path>` and as mode-600 files in `~/.local/share/bromigos/`.
- **Recall, before every turn.** Recall starts when the typed text is submitted or the transcript is final. Push-to-talk-down warms the mirror and the embedding path.
  - It is capped at 0.2 s. Gnosis's `/v1/memory/context` takes about 6 s with its LLM legs and about 0.35 s without, so the hot path races it against a local mirror of his Gnosis space, embedded with the same local qwen3-embedding model Gnosis uses and ranked by cosine. The mirror answers in about 0.05 s.
  - Up to five lines go into the prompt as "WHAT YOU REMEMBER". On a timeout the turn simply goes without; `recall_ms`, `recall_source` and `recalled` are in the reply stats.
- **Writing.** The `remember` tool writes one short sentence (host preferences, decisions, lab facts, recurring problems) asynchronously, with Gnosis fact extraction on (`messages` + `infer=true`). The note is in the mirror at once.
  - After ten quiet minutes, the conversation since the last summary goes to Gnosis the same way.
- **Forgetting.** `forget` ("forget that" means the last note) deletes in his own space only, then sweeps near-duplicates that extraction filed in other words, at once and again 12 s later.
- **Reading other memory.** `gnosis_search` reads `vector`, `arbiter-research` or `arbiter-signals`.
- **Audit.** Every recall, remember, forget, summary and search is in `~/.local/state/bromigos/vector-audit.log` with the text hashed and truncated, never whole.
- **On the avatar.** A ring of dots with "◈ RECALLED n", "◈ FILED" or "◈ FORGOTTEN" flickers by the construct, and he says it in character ("noted; filed under host preferences").

## The brain

`voice.json` `"brain"` picks the brain. `"pai"` is the default: `holo/vector/brain_pai.py` on Pydantic AI (`pydantic-ai-slim` 2.54.0 and `pydantic-ai-harness` 0.54.0, pinned, in `~/.local/share/bromigos/venv-brain`, a venv with system site packages so GTK still loads; `bin/bromigos-holo` runs the daemon there). `"classic"` is the hand-rolled `holo/vector/brain.py`. Both drive the same callbacks, so they can run side by side.

- **Events.** The agent's event stream drives the text deltas, tool rows, voice and mood markers, reroute lines, and the done or error line. Barge-in cancels the run.
- **Tools.** Exactly `tools.SPECS`, as in-process functions; there are no framework built-ins. Every call goes through `tools.call()`, which stays the single place where read-only access is enforced and audited.
- **Fallback.** Each lane is a `FallbackModel` over guarded models. A `Guard` (`WrapperModel`) gives its model 9 s to produce the first stream event and 45 s between events. A model that misses the first-byte rule fails while its stream is still opening, so `FallbackModel` moves on, the amber "rerouting to …" line appears, and the failed model is skipped for two minutes.
- **Lanes.** `voice.json` `"lanes"` sets `voice` and `deep`. When they differ, the voice lane gets one extra tool, `think_harder`, which hands the turn to the deep lane, and a pre-rendered in-character acknowledgement plays in the current voice meanwhile.
  - Measured on 2026-10-04 with VECTOR's full prompt and tools: hive gives the first token in 0.4–0.5 s, Nemotron-Lightning in 0.8–0.9 s. Nemotron also rarely tags voices.
  - So hive leads both lanes and the hand-off is off. Pydantic AI and the classic brain are within noise of each other on the same model.
- **MCP.** `holo/vector/mcp_server.py` publishes the read-only tools (15 of them, never desktop actions or memory writes) as an MCP server over stdio, or over HTTP on 127.0.0.1 with `--http PORT`, for background workers.

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

The infrastructure tools in `holo/vector/tools.py` stay **read-only**, and they remain the fast path for the lab, the cluster, ARBITER, GitHub, Gnosis and the docs:

- no shell inside them (fixed argv only);
- cluster reads through the `pilot-readonly` ServiceAccount (no secrets, configmaps or exec);
- Prometheus GETs, and `gh` read subcommands for bromigos-org;
- a fixed table of ARBITER console GETs (nothing that trades or arms);
- Gnosis through the gnosis-gate with narrow tokens;
- docs under the repo roots, with secret-looking paths refused.

Writes and actions outside the terminal: his own memory, FIELD NOTES, launching an allowlisted app or an http(s) URL, panels, the den wallpaper, the scanner and holograms. Every call goes to `~/.local/state/bromigos/vector-audit.log`, and the conversation to `vector-chat.log`; both stay local. Keys are read from mode-600 files in `~/.local/share/bromigos/` and never logged.

## Knowledge base

What the operator's software is and how it works lives in Gnosis, in five knowledge spaces (tenant `bromigos`, `user_id` = the space), written by `tools/kb-sync.py` and read by the `knowledge_search` tool.

| Space | Source | Chunks (2026-10-04) |
|-------|--------|------|
| `kb-bromigos` | `~/github.com/bromigos-org/*` (except homelab) and platform `agents/LORE.md` | 2,955 |
| `kb-nolgia` | `~/github.com/nolgiainc/*` (Nolgia, the operator's other company) | 5,755 |
| `kb-personal` | `~/github.com/blackflame007/*` | 513 |
| `kb-desktop` | `~/.dotfiles`: AGENTS.md, the holo/live/brand READMEs, the live keybind table, and the docstrings of the desktop's own Python (widgets, holo, waybar scripts; panels are headed by their on-screen title, e.g. "WORKBENCH panel") | 188 |
| `kb-homelab` | `~/github.com/bromigos-org/homelab` | 213 |

- **Sources.** Per repo, the `README*`, `AGENTS.md`, `CLAUDE.md` and `docs/**/*.md` that git tracks (so ignored files never go), minus vendored and generated directories and anything secret-looking, up to 300 KB a file. New clones are picked up on the next run.
- **Sync.** Chunks follow headings (about 1,500 characters), verbatim (`infer=false`), with metadata `{repo, path, heading, sha, url}`. A state file (`~/.local/state/bromigos/kb-sync.json`) maps each chunk key to its Gnosis id and content hash, so a run only adds changed chunks and deletes stale ones. A first full sync took 413 s (about 25 chunks/s); a run with no changes takes seconds. `bromigos-kb-sync.timer` runs it nightly at 03:30; `tools/kb-sync.py --space kb-desktop` syncs one space, `--dry-run` only counts. Log: `~/.local/state/bromigos/kb-sync.log`.
- **Tokens.** It writes through the gnosis-gate with `gnosis-kb-ingest-token` (write and delete in the `kb-*` spaces only). VECTOR's read token reads them.
- **Search.** `knowledge_search` queries every space in parallel (or one, with `space`), takes 20 candidates from each, and reranks them. Gnosis ranks by embeddings only, which misses exact names, so query words add a small bonus where they appear in a chunk's text, path or heading, weighted by how rare they are among the candidates. The same doc kept in two repos (gnosis is in both orgs) is folded into one hit. Each hit carries its local `file` for `docs_read`. About 0.15 s.
- **Gnosis setting this relies on.** The homelab Gnosis runs with `GNOSIS_SCOPED_DENSE_RETRIEVAL_ENABLED` (homelab `02004f4`). Without it, the vector search ranks the whole store and filters by space afterwards, so big spaces crowd small ones out: kb-desktop returned nothing, and searches took about 0.9 s.

## History

Every conversation is kept in `~/.local/state/bromigos/vector-chat.log` (JSONL, local, never rewritten). `holo/vector/history.py` reads it:

- **Sessions.** A new session starts after ten quiet minutes or when the brain is reset.
- **Titles.** Each finished session gets a short title and a one-line summary from `hive`, generated once and cached in `vector-sessions.json`; until then the first question is the title.
- **The panel.** ☰ HISTORY (or Ctrl+H while VECTOR has the keyboard) lists past conversations, newest first. Typing in the box searches them as you type, Enter searches, and Esc closes the panel. Click a conversation to read it (read only). **↻ CONTINUE** puts its recent turns (up to 24, about 16k characters) back into VECTOR's context, with the session's summary in front when older turns didn't fit, and carries on; ◀ BACK returns to the list. The live transcript is hidden while the panel covers it.
- **The tool.** `conversation_history(query, when)` lets VECTOR answer "what did we talk about yesterday?" or "when did we discuss gnosis?" (`when`: today, yesterday, last week, a weekday or a date). It reads the local log and takes about 5 ms.

## The web and herdr

`holo/vector/reach.py`.

- **`web_search`** queries the homelab's SearXNG (`https://search.redacted/search?format=json`, homelab CA) in about 1 s. It takes an optional category (`general`, `it`, `science`, `news`); when one comes back empty it tries the others before giving up, and it returns SearXNG's infobox when there is one. If SearXNG is down it fails cleanly with a one-line message.
- **`web_fetch`** returns a page's readable text, extracted with trafilatura and capped at 8,000 characters. Only http and https; LAN hosts are refused (checked after DNS too, including on redirects), except `*.redacted`.
- **herdr** (the operator's workspace manager for AI coding agents) through fixed argv:
  - `herdr_status`: agents with working, idle or blocked status, from `herdr api snapshot`;
  - `herdr_read`: recent output;
  - `herdr_send`: types to an agent (logged, with the text hashed);
  - `herdr_start`: e.g. Claude Code in a repo;
  - `herdr_wait`.
  - Agents are matched by id or by a hint such as the repo name.
- **The herdr watcher** polls `herdr agent list` every 5 s. An agent turning **blocked** ("the homelab session is waiting on you") or finishing after at least 20 s of work becomes a notice in the Lin Yao voice, with an unread pip if VECTOR is minimized. It's capped at 12 an hour, and identical notices for the same agent are dropped within 2 minutes.

## VECTOR's terminal (full access, not read-only)

`run_shell` (`holo/vector/shell.py`) runs bash on the workstation **as the operator's user, with no approval step**. VECTOR says in one line what he is about to run before anything that changes state, then summarises the result.

**Limits, enforced in code and covered by `tools/test-shell.py`** (45 refusal cases and 7 allowed actions; run it with the brain venv's python):

1. **No privilege escalation.** sudo, su, doas, pkexec, run0, systemd-run, machinectl and polkit helpers are refused anywhere in the command: in pipes, `$(…)`, backticks, `sh -c '…'`, `eval`, and the text of a script the command runs. The command is parsed with bashlex; if it can't be parsed, it's refused.
2. **No secrets.**
   - The shell's environment is scrubbed of tokens, keys, secrets, passwords, Vault, cloud, GitHub and the SSH agent.
   - Refused: `vault`, `pass`, `gpg`, `gcloud secrets`, `kubectl`/`helm` on secrets, and reading `/proc/*/environ`.
   - Refused paths: `~/.vault-token`, `~/.ssh` (except `.pub`, `known_hosts`, `config`), `~/.local/share/bromigos/`, gcloud, kube, aws, docker and gh credentials, `.env*`, gnupg, password stores, keyrings, browser profiles, solana wallets, and secret-looking files.
   - Output is redacted (private keys, GitHub, Vault and API tokens, JWTs, `key=value` secrets, Authorization headers) before it reaches the model, the transcript or the log.
3. **No real money.** Refused: Alpaca live (the paper API is fine), Kalshi, Polymarket and Coinbase order endpoints, ARBITER `/api/live` and arm routes, fund transfers (solana, spl-token, cast) and anything naming wallets or private keys.
4. **Operation.**
   - Each command runs in a new session (setsid). The timeout defaults to 60 s; he may ask for up to 600 s. The working directory defaults to `~`. Output is capped at 512 KB, and the model sees at most 6,000 characters (head and tail).
   - While a command runs, the panel shows the live command line with a ■ STOP button. STOP, a barge-in or interrupting the turn kills the whole process group.
   - Kill switch: `bromigos-holo shell off` (also the `shell_off` tool, which VECTOR can use but can never reverse). `bromigos-holo shell on` turns it back on, and `bromigos-holo shell stop` stops the running command.
5. **Audit.** Every command and every refusal goes to `~/.local/state/bromigos/vector-shell.log` (time, cwd, the redacted command, exit code, duration, output size, or the refusal reason). The transcript shows `$ git status · exit 0`.

## Voice

Push-to-talk only: `pw-record` runs while SUPER+V is held (cut at 30 s if a release is missed), with a red MIC LIVE readout. No hotword. VECTOR never hears itself on speakers: pressing SUPER+V is a barge-in (playback killed, speech queue cleared, the running turn interrupted); nothing is spoken while the mic is open; the first 350 ms after playback is dropped as speaker drain; VECTOR plays and records through a session-only PipeWire webrtc echo-cancel pair (`vector_aec_sink`, `vector_aec_source`, built on the current default speakers and mic, defaults untouched, suspended when idle; `"echo_cancel": false` in `voice.json` turns it off); and a transcript that repeats a verbatim stretch of what VECTOR said in the last 30 s is dropped. The greeting plays once per session on SUPER+E (again only after four quiet hours), never on push-to-talk or `ask`. Replies are spoken sentence by sentence as they stream, and each sentence streams too.

**Voices.** VECTOR has five voices and switches between them himself. Every voice runs locally on Qwen3-TTS 1.7B (Apache-2.0, `faster-qwen3-tts`, CUDA graphs), cloned from a reference clip:

| Role | Voice | When | Colour | Shimmer |
|------|-------|------|--------|---------|
| main | Governor Voss | everything else (the default) | phosphor #39ff14 | 0.25 |
| robot | Sigil | machine readouts: status figures, diagnostics, "running scan" | cyan #3fe0c5 | 0.6 |
| scientist | Professor Arc | technology: how something works, new tech, a discovery | amber #d4af37 | 0.15 |
| floor | Revolver Lynx | ARBITER and the Floor: trades, positions, P&L | gold #f0d36a | 0.2 |
| notify | Lin Yao | notifications and codec calls (chosen by the desktop) | soft #9cff8a | 0.2 |

- **References.** These are the operator's own Brodec cast voices on Fish: four were designed from text descriptions, and Lynx is a generic library narrator. Each is rendered once by `voices/make-refs.py` (about 300 characters each, a few cents) into `~/.local/share/bromigos/voices/` with its transcript. The clips are not committed, and there are no Fish calls at runtime. If a clip is missing, the role falls back to main, and main falls back to the designed `voices/vector-ref-A.wav`.
- **Fast switching.** At load, every role's voice prompt is computed once and cached, so switching costs nothing. Each voice starts in about 0.25 s. Kokoro (CPU, a stock voice per role) answers if the GPU voice isn't loaded or fails.
- **Configuration.** `voice.json` `voices` maps each role to `{name, ref, shimmer, colour, marker, use, kokoro}`. The `use` text is what the brain is told, so giving a role a new job (for example floor becoming lore and recaps) is one edit.
- **Automatic switching.** The brain wraps whole sentences in markers: `‹robot›…‹/robot›`, `‹sci›…‹/sci›`, `‹floor›…‹/floor›` (the prompt is built from `voice.json`). Markers are stripped from the display and from speech (`holo/vector/text.py`).
  - `VoiceSplitter` gives each sentence the voice that covers most of it, and never switches into another voice for a sentence of one or two words.
  - If a reply has no markers at all (the Nemotron fallback rarely tags), a light heuristic assigns sentences instead: market words go to floor, a sentence of figures to robot, and technology words to scientist, with hysteresis so the voice doesn't flap.
  - Broken or unknown markers fall back to main.
- **The scratch.** On every real voice change, a ~240 ms radio-dial scratch plays first: swept band-passed noise, a heterodyne whistle and crackle, made with local DSP. It runs through the incoming voice's shimmer, in the same stream as the sentence, so there is no gap or overlap. Mute silences it too.
- **Colour.** The hologram's tint crossfades to the voice's colour over ~300 ms, timed with the scratch, with a brief tremor of the iris.
- **Manual setting.** `bromigos-holo voice auto|main|robot|scientist|floor|notify|cycle` pins a voice; auto is the default. The choice persists in `~/.local/state/bromigos/vector-voice-mode`. VECTOR has a `set_voice` tool ("use the robot voice", "back to normal"), and right-clicking the bar pip cycles the voice (middle-click mutes). The pip's tooltip shows the current voice and mode.
- **Codec calls** from the live layer go through `holo.pilot.voice`, which speaks in the notify voice.

**Pacing and playback** (fixed 2026-10-04).

- **Root cause.** Every sentence used to get its own `pw-play`, and the next sentence was synthesised only after the previous one finished playing. The result was a 1.7–2.1 s pause after every full stop.
- **Now:**
  - One reply plays as one continuous output stream. A producer streams sentence after sentence from the server into a buffer; the next sentence is generating while the current one plays (at about twice realtime). A single `pw-play` is fed from that buffer after a 0.3 s prebuffer, paced to stay about 0.25 s ahead, so barge-in still stops within about 0.25 s.
  - The server shapes each sentence before it leaves:
    - `SilenceShaper` drops the model's lead-in silence, caps pauses inside a sentence at `pacing.max_pause_s` (0.08 s), and keeps `pacing.sentence_tail_s` (0.11 s) after the last word.
    - `TimeStretch` (streaming WSOLA) speeds speech up without changing pitch: `"speed"`, default 1.1, overridable per voice.
    - Then the shimmer.
- **Measured** on the same four-sentence reply, recorded at the sink:
  - The pause after a sentence went from 1.7–2.1 s to about 0.25 s.
  - Total silence went from 6.8 s to 0.9 s, and the longest pause from 2.0 s to 0.14 s, with no underruns.
  - Speaking pace is now about 290 wpm over the reply. Qwen's Voss clone is already brisk at 1.0, so lower `speed` if it feels rushed.

**Conversation mode** (SUPER+SHIFT+E, the ◉ CONVERSATION button on the panel, or `bromigos-holo conversation`).

- **How it works.** Hands-free and local. While it's on, VECTOR listens on the echo-cancelled mic. Silero VAD (2 MB ONNX on the CPU, `~/.local/share/bromigos/voice/silero_vad.onnx`) finds where you stop: `conversation.end_of_turn_ms`, 700 ms by default. The utterance goes to the same local speech-to-text, he replies, then he listens again.
- **Barge-in.** Talking over him stops him and cancels the turn. While he speaks, the bar for a barge-in is higher (probability 0.8, 0.4 s of speech), and the echo canceller keeps his own voice out: tested at a probability of about 0 for his voice alone and 1.0 for a voice over him.
- **Indicators.** A pulsing "● CONVERSATION · LISTENING" line, the mic-live state and a red CONVERSATION pip on the bar.
- **Auto-off.** It turns off after `auto_off_s` (120) without speech, with a soft blip.
- **Privacy and mute.** The mic process exists only while the mode is on. Muted, he still listens and replies in text.
- **Push-to-talk.** The mic opens in about 0.15 s. Releasing the key keeps listening 0.25 s (`release_tail_ms`) so the last word isn't clipped, and stops pw-record with SIGINT so it flushes. With echo cancellation, a barge-in drops only 0.12 s of speaker drain (was 0.35 s).
- **Checks.** The echo canceller passes near-end speech intact: identical large-v3-turbo transcripts before and after it, on four test phrases. The CUDA libraries for speech-to-text come from the venv (`nvidia/cublas`, `nvidia/cudnn`). `"mic_source"` in `voice.json` overrides the capture node.

**Mood.** A mood layer blends over the voice colour without hiding it:

| Mood | Look | Voice shimmer |
|------|------|---------------|
| calm | the voice's colour | +0 |
| excited | brighter, faster gimbals | +0 |
| concerned | desaturated toward amber | +0.05 |
| alarmed | flushed toward danger #ff766f with deep-rust edges, a harder and faster iris, a slow static crackle (steps at ~4 Hz, never a strobe), a flinch | +0.15 |

- **Sources.** The reply can set a mood with a marker (`‹mood:alarmed›`, stripped from display and speech). The facts can set it too: `holo/vector/mood.py` reads tool results for a node down, failed CI, degraded apps, a critical alert or drawdown near its limit, and pushes concerned or alarmed even if the reply forgets. The facts win over a cheerful marker.
- **Timing.** A mood eases in over ~400 ms and settles back to calm about 4 s after the reply ends, fading over ~15 s. The bar pip takes the mood colour.
- **Audio.** `~/Music/vector-voices/demo.wav` is a multi-voice reply plus an alarmed one, rendered by `tools/voice-demo.py`; `switch.mp4` is the colour switch, rendered by `tools/offscreen.py vector-switch`.

- **Speech to text** is faster-whisper `large-v3-turbo` on the GPU: about 0.13 s per push-to-talk clip, about 2.3 GiB. Set `"stt": {"model": "small.en"}` for 0.08 s and 0.8 GiB.
- **VRAM:** with both models loaded, the voice server holds about 7.7 GiB of the 12 GiB card. Models unload after 10 idle minutes, and the server exits after 30.
- **Other engines:** `breeze` (the homelab's Breeze TTS 2) is too slow to talk live. `fish` works only with a voice the operator owns. Set `BROMIGOS_HOLO_SINK` to send the voice to a specific output.

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

## Event feed

VECTOR tells the desktop what he is doing through an append-only feed, and the live layer's holograms (`bromigos-live`: Mind, Ops theater, Swarm, Network map, Trade replay) draw it.

- **File:** `$XDG_RUNTIME_DIR/bromigos-vector-events.jsonl` (tmpfs), one JSON object per line, rotated to `.1` at about 5 MB. Written by `holo/vector/events.py` (`emit(type, **fields)`); his state stays in `bromigos-vector.json` beside it.
- **Every line:** `{"v": 1, "t": "<ISO-8601 local, ms>", "ts": <epoch seconds>, "type": "...", ...}`. Readers ignore unknown types and fields. No line ever carries memory text, file contents or secret values.

| type | fields | drawn by |
|------|--------|----------|
| `memory.recall` | `space`, `ids[]` (Gnosis memory or kb chunk ids), `n`, `ms`, `source` (mirror, gnosis, none) | Mind: the recalled lights flare and pull toward VECTOR's core |
| `memory.file` | `space`, `category` | Mind: a new memory settles in from the dark |
| `memory.forget` | `space`, `n` | Mind: logged; the node burns out when its id is known |
| `tool.start` / `tool.end` | `id`, `name`, `args` (short summary) / `ok`, `ms`, `outcome` (one line) | Ops theater: a packet runs from VECTOR to the station the tool touches |
| `task.progress` | `task`, `title`, `step`, `note`, `state` (running, done, failed, stopped), `pct` | Ops theater: a progress arc around VECTOR |
| `git.push` | `repo`, `branch`, `sha`, `ok` | Ops theater: the push beam, then that commit's CI checks |
| `ci.result` | `repo`, `sha`, `workflow`, `status`, `conclusion`, `url` | Ops theater: the check lights |
| `argo.sync` | `app`, `action`, `sync`, `health`, `revision` | Ops theater: a pulse from Argo into the cluster |
| `k8s.action` | `action` (restart, scale, delete_pod, run_job), `namespace`, `kind`, `name`, `replicas`, `ok` | Ops theater: the pod flagged beside the rack |
| `vault.op` | `op`, `path`, `key` (never a value) | not drawn |

The reader is `bromigos-live/live/vfeed.py`: it tails the file only while a hologram is open (a stat every 0.25 s), keeps the last 400 events so a hologram opened a moment later still sees them, and maps these names onto what each deck handles (`normalise`). The decks also watch the same things for themselves (push reflogs, check runs, Argo and pod state from Prometheus), so they work when the feed is quiet.

### Driving the holograms

VECTOR (his shell, or a tool) drives them with `bromigos-live <deck> <verb> [args]`. A closed deck opens and then runs the verb; the result line is printed and shown on the deck.

| Deck (key) | Verbs |
|------|-------|
| `mind` (SUPER+I) | `focus <text>` (a memory or document), `space <kb-name>`, `clear` |
| `ops` (SUPER+SHIFT+O) | `focus <repo>` (that repo's latest push and checks), `clear` |
| `swarm` (SUPER+SHIFT+S) | `point <repo or agent>` (a beam from VECTOR), `focus <repo or agent>`, `clear` |
| `netmap` (SUPER+SHIFT+N) | `trace <host or ip>` (hop by hop, the slowest lit), `clear` |
| `replay` (SUPER+R) | `pick <latest, biggest, instrument, agent or fill id>`, `play [pick]`, `pause`, `seek <0..1>` |
| any | `open`, `close` |

How these are built, and how to build another, is in `../skills/hologram-build.md`.
