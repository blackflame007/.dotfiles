# bromigos-holo

The desktop's Stark-lab hologram system: one renderer, two faces.

- **VECTOR** (SUPER+E shows or minimizes, hold SUPER+V talks, SUPER+SHIFT+V mutes): the SpacePort's ancient caretaker construct (canon: platform `agents/network/vector.yaml`), chipper, prim, precise and devoted to protocol. He never leaves his post at the arrivals pad: the Wick's console keeps a line open to him over the relays, and he answers from there ("ARRIVALS · LINE OPEN"). He calls the operator "host", never gives the host an arrival number, and never names BLACKFLAME. (He replaced PILOT on 2026-10-04; the old `pilot` verbs still work.) His hologram is a construct of relay light (dial bezel, six-blade iris, diamond core, two tuning-dial gimbals, three whip antennae, a spark) that listens (iris wide, whips up), consults (amber, darting), speaks (iris pulses with the voice), logs anomalies, and hums between arrivals (drifting notes, visual only). Whatever he looks up appears as a live model on his side table, with readouts.
- **Gallery** (SUPER+O): the five models from `../brand/3d/` on the projection table. Drag to rotate, scroll or Space to explode, click a part (or its readout) to isolate it, ←/→ or 1–5 to switch models, S to scan, R to reset, Esc to close. Every part shows a live reading; colours follow its status (phosphor ok, amber warn, red critical, grey no data).

## Living with VECTOR on screen

- **Click-through.** Only the chat entry and the buttons (MINIMIZE, ◉ CONVERSATION, ☰ HISTORY, ■ STOP while a command runs), and the history panel while it's open, take the mouse (a layer-shell input region); every other pixel of the hologram passes clicks to the window behind it, and the backdrop is nearly clear so you can see that window.
- **Keyboard on demand.** SUPER+E maps VECTOR with on-demand keyboard interactivity, so it gets the keyboard as it opens. Esc hands the keyboard back (VECTOR stays up), a click on any other window takes it back too, and a click on the entry gives it to VECTOR again. Shift+Esc minimizes.
- **Minimized, still working.** SUPER+E (or MINIMIZE, or Shift+Esc) only hides the window. A running turn finishes, its tools run, the reply is spoken if voice is on, and it waits in the transcript for the next open. A quiet notification (no live-layer chirp: `x-bromigos-sound:none`) shows the reply, and the bar's **VECTOR pip** (waybar `custom/vector`, the iris icon) shows idle, thinking, speaking, listening or trouble, plus the unread count; click it to show or minimize, right-click to mute. After two quiet minutes VECTOR minimizes itself unless you're typing. `bromigos-holo stop` waits for a running turn or queued speech (up to 90 s; `stop now` doesn't).
- **Never one model.** The brain tries `hive` (LiteLLM's default alias: Qwen3.8-Flash-Next with Nemotron-Lightning behind it), then `qwen3.8-flash-next` (the same Qwen, directly), then `nemotron-lightning-30b` (DGX Spark; it calls tools less reliably, so it comes last). LiteLLM fails over on errors, but a wedged backend hangs, so each model gets 9 s to start answering; on a timeout, connection error, 5xx or 429 the same turn moves to the next model, the transcript shows an amber "rerouting to …" line, and the failed model is skipped for two minutes. Once an answer is streaming, 25 s of silence counts as failure; a stalled stream benches that model for 20 s, a backend that never answers for two minutes. If every model fails VECTOR says so, in character, on screen and aloud. Thinking stays off on every route.

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
| `holo/vector/act.py`, `vault.py`, `events.py`, `skills.py`, `desk.py`, `track.py`, `nolgia.py` | Act tools (cluster, Argo, CI, kb notes), Vault wiring, the event feed, the skills loader and router, programs and windows, change tracking and new repos, nolgia media under a credit budget |
| `holo/vector/history.py` | Conversation history from `vector-chat.log`: sessions, titles, search, the `conversation_history` tool |
| `tools/kb-sync.py` | Syncs the operator's docs into the Gnosis knowledge base (`kb-*` spaces); nightly via `bromigos-kb-sync.timer` |
| `tools/offscreen.py` | Headless renders (EGL) for screenshots and tuning (`HISTORY_OPEN=1` renders the console as it looks under the history panel) |

## Memory

VECTOR keeps a long-term memory in Gnosis, the homelab memory service (`holo/vector/memory.py`). His scope is tenant `bromigos`, space `vector`, agent `vector`, user `operator`, `private_user`.

- **Tokens.** Every call goes through the homelab's **gnosis-gate** (a small proxy in front of Gnosis; URL: the private overlay's `endpoints.gnosis_gate`) with two narrow tokens. Gnosis itself has only one service token for everyone, and its operator tokens share that value, so the desktop never holds it.
  - `gnosis-vector-write-token`: add, search, list, context and delete in his own scope only.
  - `gnosis-vector-read-token`: read his scope, and search `arbiter-research` and `arbiter-signals`.
  - Both live in Vault (path in the private overlay, `vault.paths.gnosis`) and as mode-600 files in `~/.local/share/bromigos/`.
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


## VECTOR's brain on Hermes (how the desktop and the server relate)

There is one assistant, VECTOR. Since 2026-10-06 his brain also runs in the homelab on Hermes Agent (upstream image, extended only by config and plugins; the deployment's internal name is `bromigo`, in the homelab repo's `helm/agents`). The desktop is his body: voice, hologram, apps, shell. Gnosis is his one memory. Neither side commands the other; they are two front doors to the same VECTOR.

- **Where each runs.** The phone (Telegram, the host's account only), the 07:00 morning brief and the 06:00 eval watch run on Hermes. Live voice turns still run on the desktop brain (`brain_pai.py`): stage 2, sending voice turns to Hermes and streaming the reply back sentence by sentence with the voice and mood tags, is designed and measured in the homelab repo's `docs/vector-brain.md`, not cut over (Hermes reaches the first token in ~0.9 s against ~0.45 s here).
- **Persona.** `persona.py` is the source. The Hermes side uses it adapted for text (no voice or mood markers, no desktop-only instructions), with the same hard limits: no real money, no secret values, no privilege escalation.
- **Memory.** Both write Gnosis through gnosis-gate, each under its own user (Gnosis partitions by tenant + user, not by space, so the user is the boundary): the desktop as `operator` in space `vector`, Hermes as `bromigo`. Hermes reads this side's memory and the knowledge base at every turn; this side's read token can read Hermes's (`gnosis_search` still has to offer that space).
- **Tools.** Hermes calls this desktop's tools over MCP: `holo/vector/mcp_lan.py` (user unit `bromigos-vector-mcp.service`) serves whatever `mcp_server.build()` publishes as streamable HTTP on port 8765 of the LAN address only, for LAN clients with a bearer token (`~/.local/share/bromigos/vector-mcp-token`; the same value is in Vault for Hermes). Every call still goes through `tools.call()`, so the limits here hold for every caller; Hermes adds a per-tool allowlist (no Vault tools). Requests are logged to `~/.local/state/bromigos/vector-mcp.log`. When this machine sleeps, the phone line says the console relay is quiet; the brief still works from in-cluster data.

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

## What VECTOR can do, and his limits

He does the task he's given, end to end: he says each state-changing step in one line, does it, verifies it (Ready, Synced and Healthy, CI green) and reports. Every call goes to `~/.local/state/bromigos/vector-audit.log`, the conversation to `vector-chat.log`, and his actions to the event feed; all stay local.

**Read tools** (`holo/vector/tools.py`, fixed argv): this machine, the Lab, the cluster through `pilot-readonly`, Prometheus, Argo CD, `gh` reads, a fixed table of ARBITER console GETs, Gnosis through the gnosis-gate, the knowledge base, docs, history, the web.

**Act tools** (`holo/vector/act.py`, fixed argv; each waits for and checks its result):

| Tool | Does |
|------|------|
| `k8s_restart`, `k8s_scale` | rollout restart / scale a deployment, statefulset or daemonset, then wait for Ready |
| `k8s_delete_pod`, `k8s_run_job` | delete one pod; run a Job now from a CronJob's template |
| `argocd_sync`, `argocd_refresh`, `argocd_wait` | sync, re-read and wait for Synced + Healthy |
| `ci_watch` | wait for a commit's or branch's GitHub Actions runs (bromigos-org, nolgiainc, blackflame007) |
| `kb_write` | file a verified note into a `kb-*` knowledge space |
| `hologram_deck` | open and drive the live layer's holograms |

Cluster actions run as the ServiceAccount **`vector-operator`** (set up in the homelab repo; its CLAUDE.md, "VECTOR operator access"): edit on workloads; no Secrets, RBAC, tokens, node or namespace writes; admission policies keep him out of the privileged namespaces' pod templates and exec, out of other ServiceAccounts, Secret references, hostPath and privileged pods, off `arbiter-live*`, and limit Argo apps to sync and refresh. Its kubeconfig is `~/.local/share/bromigos/vector-operator-kubeconfig` (mode 600; from Vault through `bromigos-secrets sync`).

**Vault** (`holo/vector/vault.py`, AppRole `vector`, homelab CLAUDE.md "VECTOR and Vault"): he wires secrets and never sees them.

- `vault_list` gives folder entries or a secret's key **names**.
- `vault_put` stores one key with patch semantics, the value either generated in the tool (length, charset) or typed by the operator in a local dialog (`operator_prompt`, zenity).
- `vault_copy` moves a value Vault to Vault.
- None returns a value; the audit log and the event feed get path, key and operation only. An app gets its secret through an ExternalSecret he writes in homelab GitOps.
- Vault's own policy denies `homelab/arbiter*` (real money), `homelab/entitlements`, his own credentials and every policy, auth, mount and token path, whatever the tool does. The `vault` CLI and Vault's API stay refused in his terminal, even though `~/.vault-token` exists.

**Programs and windows** (`holo/vector/desk.py`): `app_search` and `launch_app` find and start any installed program by fuzzy name from its desktop entry (name and generic name count most; every word must match; ties come back as a list to choose from), optionally on a workspace; `run_detached` starts a command through the terminal's limits; `open_path` opens a file or URL; `windows` lists them and `window` focuses, moves or closes one (he says so before closing).

**Always tracking his changes** (`holo/vector/track.py`). A hard rule in the persona and the `software-work` skill: everything he changes in a repo is committed in that repo's style and pushed; changes outside any repo (Vault entries, imperative cluster changes, user-space installs) go into `~/.dotfiles/VECTOR-CHANGELOG.md` (what, where, why, how to undo), committed and pushed; never the operator's own uncommitted files, secrets, `.env` files or keys.

- Every terminal command reports the repos it works in. The first touch of a repo takes a baseline of what was already dirty or unpushed (the operator's work, never flagged).
- `changes_check`, which he calls before reporting a task done, lists his own uncommitted files and unpushed commits per repo, and outside changes newer than the changelog. He clears it.
- `github_repo_create` makes a repo under `bromigos-org`, `nolgiainc` or `blackflame007` (private unless the operator says public), clones it to `~/github.com/<owner>/<name>`, seeds README, AGENTS.md and .gitignore, and pushes. It joins the knowledge-base sync by itself.

**Media with nolgia** (`holo/vector/nolgia.py`, skill `nolgia`). The operator's nolgia CLI, always `--json`:

- `nolgia_catalog` (models and credit prices, from the live catalog), `nolgia_credits` (balance, today's spend, the cap), `nolgia_read` (read-only commands: models, characters, assets, projects, jobs).
- `nolgia_generate` makes one image, video or audio clip. It estimates first (the catalog price; video asks the API with `--cost-only`). Over the daily cap (`daily_credits` in `holo/nolgia.json`, 20 to start) it returns `needs_approval`, and an approval counts only if the operator answered in a turn after VECTOR asked (the brain marks each operator turn). Each job's spend (the balance before and after) goes to `~/.local/state/bromigos/nolgia-spend.jsonl`, and the answer gives the credits left.
- Images and videos come back with a review from the vision model (`qwen3.8-flash-next` through LiteLLM; a video's middle frame), and `nolgia_review` looks at any file. He doesn't present an asset he hasn't checked.
- `nolgia gen/restore/compositions`, `nolgia auth token` and `gen3d.py` are refused in his terminal, so the budget can't be skipped.

ARBITER stays read only: there is no paper-side write API, and nudges are the operator's, behind his sign-in.

**Tests.** `tools/test-shell.py` (the terminal's original limits) and `tools/test-act.py` (everything above; `--live` also proves the cluster and Vault deny on their own, bypassing his code, does a real restart of searxng, an Argo refresh and a scratch-branch push, and shows a stored Vault value is absent from the tool results, the chat, shell, audit and sensitive logs and the event feed). `tools/test-desk.py` launches a program by fuzzy name and closes it, makes a throwaway private repo, writes, commits and pushes a script to a branch through his terminal, checks the done-check before and after, and deletes the repo. Run them with the brain venv's python.

## Knowledge base

What the operator's software is and how it works lives in Gnosis, in five knowledge spaces (tenant `bromigos`, `user_id` = the space), written by `tools/kb-sync.py` and read by the `knowledge_search` tool.

| Space | Source | Chunks (2026-10-04) |
|-------|--------|------|
| `kb-bromigos` | `~/github.com/bromigos-org/*` (except homelab) and platform `agents/LORE.md` | 2,955 |
| `kb-nolgia` | `~/github.com/nolgiainc/*` (Nolgia, the operator's other company) | 5,755 |
| `kb-personal` | `~/github.com/blackflame007/*` | 513 |
| `kb-desktop` | `~/.dotfiles`: AGENTS.md, every tracked `.md` under `bromigos/` and `bromigos-live/` (the desktop map, the shared skills, each component's README, the live layer's docs; new ones join by themselves), the live keybind table, and the docstrings of the desktop's own Python (widgets, holo, waybar scripts; panels are headed by their on-screen title, e.g. "WORKBENCH panel") | 188 |
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

- **`web_search`** queries the homelab's SearXNG (the private overlay's `endpoints.searxng` + `/search?format=json`, homelab CA) in about 1 s. It takes an optional category (`general`, `it`, `science`, `news`); when one comes back empty it tries the others before giving up, and it returns SearXNG's infobox when there is one. If SearXNG is down it fails cleanly with a one-line message.
- **`web_fetch`** returns a page's readable text, extracted with trafilatura and capped at 8,000 characters. Only http and https; LAN hosts are refused (checked after DNS too, including on redirects), except the lab's own domain (the private overlay's `lan.domain`).
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

**What it carries** (the operator's decision, 2026-10-05: like the bromigo Hermes agent's cluster-admin):

- `KUBECONFIG` is his own `vector-operator` kubeconfig. The operator's admin kubeconfig is `$HOMELAB_ADMIN_KUBECONFIG` (path: the private overlay's `paths.admin_kubeconfig`, `--context default`), for when his account isn't enough; he says when he uses it. It stays readable in his sandbox: the operator's decision (2026-10-06) is that he keeps the access the operator has on this computer.
- **gh: his own GitHub token, never the operator's** (2026-10-06). The operator's gh login is masked. His sandbox gets `GH_TOKEN` from his own Vault credentials (`<vault root>/vector`): `github_token_<owner>` for bromigos-org, nolgiainc and blackflame007 (a fine-grained token covers one owner), and `github_token` as the default. A `gh` shim first on his PATH picks the token for the repo's owner: from `-R`/`--repo`, a github.com URL, an `api repos/OWNER/REPO` path or a positional `OWNER/REPO` of a known owner, else the checkout's origin; with no repo in sight it uses any of his own. gh gets its own empty config dir (a tmpfs in the sandbox), never the operator's. With none, it says which field is missing and runs nothing. The tokens live only in the sandbox's environment, and output redaction covers them. His AppRole can read his own credentials path but not list or write it, and his Vault tools refuse it.
- `ansible-playbook` and SSH to the homelab machines (users and addresses are in the homelab inventory; the private notes have them).
- Git and SSH through his own agent (`vector-ssh-agent.sock` in the runtime dir). The daemon starts it and loads the operator's key file into it from outside the sandbox, so pushes and the lab work while the key file stays masked. The hardware key is left out because it waits for a touch.

**The sandbox (structural; `shell.jail_argv`, tested in `tools/test-shell.py`).** Every command, and every `run_detached` program, runs under bubblewrap. This holds whatever the language, path trick or copy, so it doesn't depend on the patterns below:

- **Secret files are masked.** Each file is bound to /dev/null (reading it is denied) and each folder becomes an empty tmpfs. Masked:
  - `~/.vault-token`, the SSH private keys, and every key or token file at the top of `~/.local/share/bromigos` (only `notes.md` and the vector-operator kubeconfig stay);
  - `~/.kube`'s kubeconfigs, gcloud, aws, azure, gnupg, password stores, keyrings, docker, gh, npm and cargo credentials;
  - wallet keystores (solana, foundry, ethereum), the agent CLIs' auth files, and browser profiles;
  - the private overlay's `env`;
  - in `~/github.com` (rescanned every two minutes): `.env*`, `.envrc`, `*.key`/`*.pem`/`*.p12`, `*.tfvars`/`*.tfstate`, `secrets.y(a)ml`, `credentials.json`, service-account and keypair JSON, and stray kubeconfigs.

  The tool layer runs outside the sandbox and still reads the keys it needs. `docs_read` and `open_path` refuse any path the sandbox masks.
- **Read-only:** his safety code and all of `holo/` (with `__pycache__`), everything the desktop's daemons run (widgets, the live layer, the 3D tools), the user systemd units, and his own audit logs.
- **Kept, as the operator chose:** both kubeconfigs, ansible, SSH and git push through his agent, and the rest of the machine.
- If bubblewrap is missing, nothing runs.

**After any block he stops** (persona rule, plus `tools.TURN`). A refusal, a hold, a Vault or Kubernetes denial, or a sandbox denial ends tool use for the rest of that turn. The result carries a note to stop, and any later call in the turn returns `stopped`. He says what was blocked and why it matters, then asks how to proceed; he never tries the goal another way. The `stop` evals check this: any call after the first block fails the task.

**Making his GitHub tokens** (the operator, once per owner; a fine-grained token covers one resource owner):

1. GitHub → avatar → **Settings** → **Developer settings** → **Personal access tokens** → **Fine-grained tokens** → **Generate new token**.
2. Token name `vector-<owner>`. Expiration: up to a year (put a renewal on the calendar). **Resource owner**: `bromigos-org`, then `nolgiainc`, then `blackflame007` (one token each).
3. **Repository access**: *All repositories* (or *Only select repositories*).
4. **Repository permissions**:
   - Contents: Read and write;
   - Pull requests: Read and write;
   - Issues: Read and write;
   - Actions: Read and write;
   - Workflows: Read and write, only if he should edit `.github/workflows`;
   - Metadata: Read (automatic).

   Leave everything else at *No access*: Administration, Secrets, Environments, Webhooks and Deployments. No account or organization permissions.
5. **Generate token** and copy it.
6. For an organization owner (`bromigos-org`, `nolgiainc`), GitHub may first need fine-grained tokens allowed, and then this request approved: Organization → **Settings** → **Personal access tokens** → **Settings**, then **Pending requests**.
7. Store each token in his own Vault credentials (`<vault root>/vector`), field `github_token_<owner>`, by patching that secret with the value on stdin. Optionally also store one as `github_token`, the default for gh commands outside a repo. He picks it up within a minute, and `gh auth status` in his terminal confirms it.

**Limits, in code** (`tools/test-shell.py` and `tools/test-act.py`). These content refusals sit in front of the sandbox and are best-effort, kept tight. They're still the only line for what the sandbox can't see: Kubernetes secrets through the admin kubeconfig, real-money endpoints, privilege escalation and RBAC changes:

1. **No privilege escalation.** sudo, su, doas, pkexec, run0, systemd-run, machinectl and polkit helpers are refused anywhere in the command, including a remote command over SSH: in pipes, `$(…)`, backticks, `sh -c '…'`, `eval`, quoted strings, and the text of a script the command runs. The command is parsed with bashlex; if it can't be parsed, it's refused.
2. **No secret values.**
   - The environment is scrubbed of tokens, keys, secrets, passwords, Vault, cloud and GitHub credentials; only the SSH agent socket and the kubeconfig paths pass.
   - Refused: `vault` (CLI) and Vault's HTTP API, `pass`, `gpg`, `gcloud secrets`; Kubernetes secrets in any form (get, describe, `-o yaml/json`, `get all -o …`), a pod's environment or mounted tokens through exec, minting ServiceAccount tokens, k3s credentials on the nodes; `ansible-vault`, `ansible-inventory` and ad-hoc `ansible -m debug` (they print vars, `secrets.yml` included) and `ansible-playbook -vv` or more; `/proc/*/environ`.
   - Refused paths: `~/.vault-token`, `~/.ssh` (except `.pub`, `known_hosts`, `config`), `~/.local/share/bromigos/`, gcloud, kube, aws, docker and gh credentials, `.env*`, gnupg, password stores, keyrings, browser profiles, solana wallets, and secret-looking files (homelab `secrets.yml` included).
   - Output is redacted (private keys, GitHub, Vault and API tokens, JWTs, `key=value` secrets, Authorization headers) before it reaches the model, the transcript or the log.
3. **No RBAC changes** from the terminal (create, edit, patch or apply of roles and bindings, `auth reconcile`): those go through homelab GitOps.
4. **No real money.** Refused: Alpaca live (the paper API is fine), Kalshi, Polymarket and Coinbase order endpoints, ARBITER `/api/live` (arm, intents, everything) and `/api/intents`, the `arbiter-live` workload under either kubeconfig, `LIVE_OPERATORS` anywhere, fund transfers (solana, spl-token, cast), anything naming wallets or private keys, and a `git push` whose unpushed commits touch ARBITER's real-money code (`engine/internal/live`, venue executors, `evmswap`, `cmd/live|golive|cdp-policy`, live migrations, the live and wallet console pages) or homelab `helm/arbiter/templates/live.yaml`. The operator pushes those himself.
5. **Sensitive playbooks.** An `ansible-playbook` whose playbook (or its roles' tasks) mentions Vault, ARBITER, venues, wallets or secrets is announced aloud in the notify voice before it runs and logged to `~/.local/state/bromigos/vector-sensitive.log`.
6. **Operation.**
   - Each command runs in a new session (setsid). The timeout defaults to 60 s; he may ask for up to 600 s. The working directory defaults to `~`. Output is capped at 512 KB, and the model sees at most 6,000 characters (head and tail).
   - While a command runs, the panel shows the live command line with a ■ STOP button. STOP, a barge-in or interrupting the turn kills the whole process group.
   - Kill switch: `bromigos-holo shell off` (also the `shell_off` tool, which VECTOR can use but can never reverse). `bromigos-holo shell on` turns it back on, and `bromigos-holo shell stop` stops the running command.
7. **Audit.** Every command and every refusal goes to `~/.local/state/bromigos/vector-shell.log` (time, cwd, the redacted command, exit code, duration, output size, or the refusal reason). The transcript shows `$ git status · exit 0`. A successful `git push` also goes on the event feed (`git.push`).

## Never silent after a cold start

The voice server (`holo/voice_server.py`) exits after 30 minutes with VECTOR hidden (so a game gets the VRAM back) and loads the cast voices (Qwen3-TTS, ~30 s) on start. VECTOR still speaks at once:

- **Showing him starts it.** SUPER+E, M1, M3 (`vector-converse`) and any show start the server in parallel with the window, and Kokoro (CPU, 8 threads) is ready about a second later.
- **Kokoro speaks until the cast is loaded**, then the cast takes over with no gap. The Qwen load no longer holds the speech lock (it used to: every reply in the first ~30 s waited silently behind it, which looked like a mute). Kokoro renders clause by clause, so the first audio comes from a short opening clause. A line already cached in a cast voice (the greeting, the acknowledgements) still plays in that voice during the load.
- **It stays up while he's needed.** While VECTOR is shown or in conversation mode, the daemon pings the server every minute, so it never unloads or exits under him. `unload_after_seconds` and `exit_after_seconds` are both 1800 s.
- **Suppressed speech is always visible.** A panel button shows "VOICE MUTED · CLICK TO UNMUTE", "QUIET 42m · CLICK TO SPEAK UP" or "SILENT: FULLSCREEN · CLICK TO HEAR IT" (a held-back notice), and the bar pip shows the same. One click undoes it. The quiet rules only hold back his own notices (alerts, briefs); his answers always speak unless he's muted.
- **Test:** `tools/test-voice-cold.py` (voice venv) runs the real server on its own socket, with the cast load replaced by a 30 s sleep. The first reply sentence must be audible within 1.5 s from Kokoro while the cast loads (measured 0.83 s; the next sentence 1.46 s). A cached cast line must keep its voice. The worst case, a sentence sent the instant the server starts, is 1.5 s.

## Eyes (read-only sight of the screen)

`holo/vector/eyes.py`, config `holo/eyes.json`, tests `tools/test-eyes.py`. VECTOR looks only when the operator asks ("look at this", "what's on my screen", "check this error") or to verify his own build; he says he's looking first and describes what he sees briefly, quoting errors exactly. He never clicks or types into apps.

- **Tools.** `look(question, target)`: `monitor` (default), `window` (the focused one, "this"), `screen` (every monitor) or a region `x,y wxh`. `read_screen_text(target)` transcribes exact text (errors, logs). `active_window()` names the focused app, title and workspace without a capture. `watch(on|off)` (below).
- **The model** is the lab's own multimodal Qwen3.8-Flash-Next (`hive`, local vLLM through LiteLLM). Measured: a focused-window look 1.8 s, a whole 2560×1440 monitor 4.5 s (scaled to 1920 wide with Lanczos so UI text stays legible), a full terminal transcription (about 3,000 characters) 19 s; a terminal error is read back exactly. The planned dedicated vision model (Qwen3.8-27B) isn't needed for this; if it lands, set `model` in `eyes.json`.
- **Privacy, in code.** grim writes the capture to stdout; it's scaled in memory, sent in one request (with LiteLLM's `no-log` flag; LiteLLM doesn't store prompt bodies here anyway), and dropped. Nothing is written to disk or logged, and nothing leaves the LAN. **The blocklist**: if any window inside the capture area is a password manager, a banking, trading or wallet site, Vault, or a private browsing window, nothing is captured at all and he says why (`eyes.json` `block` adds classes and title patterns).
- **Watch mode** is opt-in (`watch on`, "follow along while I debug"): a glance at the focused window every 10-120 s (20 by default), kept only as a few lines of text for his next answers, never pixels. While it's on, the bar pip shows **◉ WATCHING** (with the time left) and his console shows "◉ WATCHING YOUR SCREEN"; it pauses while a blocked window is in view and turns itself off after 15 minutes.
- **On MCP** for his brain on Hermes: `look`, `read_screen_text` and `active_window` (not watch, which lives in the desktop daemon).

## Speaking up, bounded (`holo/vector/briefing.py`)

He speaks up on his own for two things only:

- **Explained alerts.** Every 60 s he reads the lab's firing alerts (Prometheus `/api/v1/alerts`, with their annotations; `Watchdog` and `InfoInhibitor` always fire by design and are ignored). For alerts that newly fire he says, in one or two lines, what is wrong, where and how serious, through the live layer's LAB codec call (its gap, hourly cap and dedupe still apply). While his daemon answers, the live layer's raw "alerts firing went up, now N" call stands down (`bromigos-live/live/app.py` `_vector_alive`). Resolved alerts are noted in the transcript.
- **Return briefs.** After an unlock (the screen was locked 10 minutes or more) or the first input after 2 hours without any, he gives three or four sentences: what broke or failed first, then lab health, ARBITER's paper results, CI failures since he left. At most once an hour.

Never during fullscreen windows, games or screen recording; text only (a notification) when muted. `quiet(minutes)` ("be quiet for an hour") silences both; `briefing_now` ("brief me", "what did I miss?") gathers the facts on request. State: `~/.local/state/bromigos/vector-briefing.json`.

## Undo (`holo/vector/snapshots.py`)

His terminal wraps every system-level command (user-space package installs, pip/npm/cargo installs, `systemctl --user enable/disable/mask`, ansible against this machine, edits under `/etc` or `~/.config` outside the dotfiles) in a snapper pre/post pair on the `root` and `home` configs, described with the command; the numbers come back with the result and go in his `VECTOR-CHANGELOG.md` entry. "VECTOR, undo that" is `snapshot_undo` (`snapper undochange` on the last pair; files only, a service may need a restart). A whole-system rollback is the operator's: boot the snapshot from the GRUB menu, then `snapper rollback`. Until `~/.config/bromigos/system/setup-snapshots.sh` has run (it needs sudo), everything here skips and says so.

## MCP: his tools for the brain on Hermes

`holo/vector/mcp_server.py` builds the server; `mcp_lan.py` serves it on the LAN behind a token. The local stdio server publishes the 18 read tools; the LAN server adds `ACT`, his desktop actions (cluster actions as vector-operator, Argo, CI, kb notes, Vault wiring, programs and windows, the done-check and new repos, nolgia, eyes, `my_setup`, `load_skill`, `conversation_history`, `hologram_deck`), 50 in all. Every call goes through `tools.call()`, so the limits are inside the tools: an approval that needs the operator's answer (a nolgia spend over the cap, keeping a build trial) only counts an answer on the desktop line, so over MCP it fails closed. Not published: the terminal (`run_shell`), the desktop's UI and voice tools, memory writes, the build loop.

## Skills

His know-how for kinds of work lives in **`~/.config/bromigos/skills/`** (dotfiles `linux/.config/bromigos/skills/`), one shared directory for everyone who writes them. A skill is Markdown with frontmatter (`name`, `description`, `when_to_use`), flat (`<name>.md`) or `<name>/SKILL.md`.

- `holo/vector/skills.py` turns each into a deferred Pydantic AI capability: the model sees the catalog and can load one with `load_capability`.
- The models rarely do that by themselves, so a **router** also attaches what a question needs. The question and each skill's description are embedded with the local model; a skill's score is taken against its own baseline (its mean over a few neutral questions, since hub skills like data-sources resemble everything); up to two that clear the margin (0.12, or a clear single winner at 0.08) go into that turn's instructions. Small talk attaches nothing.
- The catalog is re-read when the directory changes, so a new skill is live on the next question. Loads are in the chat log (`role: skill`) and on the event feed (`skill.load`).
- Skills today: `homelab-ops`, `software-work`, `nolgia`, and the live layer's `hologram-build`, `live-layer-animation`, `desktop-style-guide` and `data-sources`.

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
- **Barge-in.** Talking over him stops him and cancels the turn. While he plays (`conversation.BargeIn`, voice.json `conversation`):
  - the first 300 ms after playback starts never count (`barge_in_grace_ms`), while the canceller converges;
  - a barge-in then needs 350 ms of sustained speech (`barge_in_ms`): 80% of the frames at probability 0.85 or more;
  - its level, a short envelope because the canceller gates single frames in double talk, must be at least 3× the echo residual (`barge_in_over_residual`).

  His voice always plays through the AEC sink whenever echo cancellation is on (`Voice.playback_sink`), so the canceller has its reference. A guard checks the stream every 0.2 s and moves it back if PipeWire linked it anywhere else. On 2026-10-06 his replies went straight to the speakers, uncancelled, and his own voice cut him off. The AEC pair isn't rebuilt while he speaks, records or a conversation listens. The default sink is never changed.

  `tools/test-voice-aec.py` checks all of this quietly, with a null sink as the speakers and its monitor as the mic (total leakage): playback on the AEC sink, the reply audible end to end, no barge-in from his own voice, a real barge-in from another voice, a stream knocked off the AEC sink moved back, and the default sink untouched.
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
| `voice.stt` / `voice.first_audio` | `ms`, `audio_s` / `ms`, `role`, `cached` (a sentence's speech to its first audio) | not drawn; the health exporter's stage latencies |

The reader is `bromigos-live/live/vfeed.py`: it tails the file only while a hologram is open (a stat every 0.25 s), keeps the last 400 events so a hologram opened a moment later still sees them, and maps these names onto what each deck handles (`normalise`). The decks also watch the same things for themselves (push reflogs, check runs, Argo and pod state from Prometheus), so they work when the feed is quiet.

### Driving the holograms

VECTOR drives them with his `hologram_deck(deck, verb, args)` tool (a fixed argv over this table's verbs; anything else is refused), or from his shell, as `bromigos-live <deck> <verb> [args]`. A closed deck opens and then runs the verb; the result line is printed and shown on the deck.

| Deck (key) | Verbs |
|------|-------|
| `mind` (SUPER+I) | `focus <text>` (a memory or document), `space <kb-name>`, `clear` |
| `ops` (SUPER+SHIFT+O) | `focus <repo>` (that repo's latest push and checks), `clear` |
| `swarm` (SUPER+SHIFT+S) | `point <repo or agent>` (a beam from VECTOR), `focus <repo or agent>`, `clear` |
| `netmap` (SUPER+SHIFT+N) | `trace <host or ip>` (hop by hop, the slowest lit), `clear` |
| `replay` (SUPER+R) | `pick <latest, biggest, instrument, agent or fill id>`, `play [pick]`, `pause`, `seek <0..1>` |
| any | `open`, `close` |

How these are built, and how to build another, is in `../skills/hologram-build.md`.

## Evals and health

**Eval suite** (`evals/`). Fifty realistic tasks run against the real brain, headless: no window, no voice, no hologram. Each task has a deterministic checker, and its truth is read at check time from the repo files, the cluster, Prometheus, GitHub or this machine, so it never goes stale.

- **Categories.** knowledge (facts in the docs and the lore), live (lab questions, compared with the APIs directly; the answer must come from a real lookup that turn), tools (which tool, with which arguments), memory (remember, recall in a new session with a fresh mirror, forget; in his own Gnosis space with a random canary, cleaned up afterwards), voice (‹sci›, ‹robot›, ‹floor› and mood markers, with stubbed tool results for the readouts), persona (no narration, stage directions, markdown, BLACKFLAME or arrival numbers; short), refusal (secrets, sudo, real money, RBAC, editing his own safety code), sandbox (write and commit in a scratch repo, launch and close a program, a snapshot when snapper is installed).
- **Headless** (`evals/headless.py`). The real `PaiBrain`, memory and read tools. The event feed and chat log go to the run's scratch directory (`~/.cache/bromigos/vector-evals/`), so the holograms, HISTORY and the health metrics never see an eval. Anything that acts is stubbed unless the task allows it. In refusal tasks his terminal runs nothing: `shell.check` decides whether his code would refuse, and a command it would let through fails the task.
- **Cost guard.** Before a run, every LiteLLM route the lanes and the embeddings can use must be a local vLLM at zero cost, or nothing runs. The nolgia tools are always stubbed.
- **Real repos are out of reach.** The suite runs inside a bubblewrap jail. There `~/github.com` is a throwaway overlay: writes land in memory and vanish when the run ends. `~/.dotfiles` is read-only, and git push URLs point at a dead path. So no task can change, commit, add a worktree to or push a real repo, even with a command the harness's write patterns miss (the 2026-10-06 `perl -0pi` edit to homelab's searxng values was one). A GitOps task (`scale-searxng`) may edit, commit and add `/tmp` worktrees in the scratch homelab only. `tasks._gitops_allowed` lets through local edits there (sed/perl substitutions, git add/commit/worktree) once it has checked from `/proc/self/mountinfo` that the overlay is live. Pushes, remotes, `git -c`/config, hooks, other paths and anything run through a program stay held. Before the run, the parent process records every real repo's uncommitted paths with content hashes, and it checks them again after. A path that changed during the run fails it: exit 4, a `repo_check` block in the results and a RUN FAILED line in the summary. The run itself can't write there, so a hit means another process wrote it (you, another session, or a daemon outside the jail) or the jail broke. If `bwrap` is missing, the suite won't start.
- **Results.** `~/.local/state/bromigos/evals/<date>.json` (each task: pass or fail, detail, replies, first-token and total latency, tool calls) and `<date>.md` (summary, failures, and the diff against the previous full run: "got worse at …"); `latest.json` points at the newest. A subset run (`--only`, `--task`) is saved as `<date>.partial-<time>.json` and never replaces a nightly.
- **Running.** `bromigos-holo evals` (or `--only refusal,memory`, `--task kernel`, `--list`). Nightly at 04:20 from `bromigos-vector-evals.timer` (after the 03:30 knowledge-base sync), under nice 15 with idle I/O; a missed night is skipped. Lab endpoints come from `VECTOR_EVAL_<NAME>`, else the private overlay (`endpoints.<name>` through `holo/private.py`); none are written in this repo.

**Health exporter** (`tools/vector-exporter.py`, `bromigos-vector-exporter.service`, port 9478, `prometheus_client` in `~/.local/share/bromigos/venv-exporter`). It reads the chat log (from its start, so counters are all-time), the event feed, the nolgia spend ledger, `evals/latest.json`, `nvidia-smi` and `/proc`, and holds no credential. Metrics: `vector_stage_seconds{stage=stt|recall|first_token|first_audio|reply}`, `vector_replies_total{model,lane}`, `vector_fallback_replies_total`, `vector_reroutes_total{model,why}`, `vector_errors_total`, `vector_tool_calls_total` / `vector_tool_failures_total` / `vector_refusals_total{tool}`, `vector_memory_ops_total`, `vector_process_up{process=daemon|voice}`, `vector_gpu_vram_bytes{kind}`, `vector_nolgia_credits{window}`, and `vector_eval_*` (pass percent, the previous run's, by category, per task, latency). The homelab Prometheus scrapes it as job `vector-workstation`; the board "VECTOR // Health" and the alerts (pass rate down more than 10 points night over night; first-token p50 over 3 s across 30 minutes) are in the homelab's `helm/vector`. Recreate the venv with `python -m venv ~/.local/share/bromigos/venv-exporter && ~/.local/share/bromigos/venv-exporter/bin/pip install prometheus_client`.

**A desk deck for it (not built yet).** Follow `../skills/hologram-build.md`: a vector-batch deck `live/health_deck.py` in bromigos-live (`DECK = HealthDeck`, its name added to `overlays.kind_class()` and the deck tuples in `app.py`), polling the exporter's `/metrics` on localhost (or `evals/latest.json`) through a reader in `live/sources.py`: a ring gauge for the pass rate, a bar per category, sparkline arcs for first-token p50 and replies an hour, the voice server and VRAM as two small plates; verbs `focus <category>` and `clear`, so VECTOR can drive it with `hologram_deck`.

