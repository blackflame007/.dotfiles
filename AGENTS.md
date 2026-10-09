# PROJECT KNOWLEDGE BASE

The operator's dotfiles (public repo `blackflame007/.dotfiles`, branch `master`). Start with
`README.md` for installing; this file is for agents and contributors. The Linux side is the
**Bromigos desktop**: its map is below, its architecture is `linux/.config/bromigos/README.md`.


**What lives where.** The desktop is bromigOS (pacman packages from `bromigos-org/bromigOS`
and `bromigos-org/vector`); this repo holds only what's mine: thin configs over bromigOS's
defaults, my settings, the encrypted private overlay, my plugins (ARBITER and the rest),
my Razer bits, my backup config, my likeness and personal brand, my own hologram models
(the ARBITER monolith) and my copies of his skills. Engine changes belong in bromigOS, not here. The full list:
`linux/.config/bromigos/README.md`, "What lives where".

## OVERVIEW

GNU Stow-managed dotfiles for Arch Linux and macOS. Zsh (custom plugin loader, no framework), Neovim (lazy.nvim, 100+ plugins), tmux (tpm), Hyprland/Yabai window managers. 5 git submodules for nvim config, zsh plugins, and private configs.

## STRUCTURE

```
.dotfiles/
├── common/          # Cross-platform configs (stowed everywhere)
│   ├── .tmux.conf   #   tmux + tpm plugins (resurrect, continuum, yank)
│   └── .config/     #   alacritty, kitty, cava, lf, ranger, mpd, opencode
├── linux/           # Arch Linux-specific (stowed on Linux only)
│   ├── .config/     #   hypr, waybar, dunst, rofi, bromigos (desktop), bromigos-live (live layer),
│   │                #   systemd user units, polybar/picom (X11 leftovers), scripts, swappy
│   ├── .local/share/ #  generated GTK theme, icons, cursor, KDE colour scheme, .desktop files
│   ├── .xinitrc     #   X11 init
│   └── .pacman.list #   Package list for reproducible installs
├── osx/             # macOS-specific (stowed on Mac only)
│   └── .config/     #   yabai, skhd, sketchybar (with C helper)
├── zsh/             # Shell config (see zsh/.config/zsh/AGENTS.md)
│   ├── .zshrc       #   Bootstrap → sets ZDOTDIR → sources .config/zsh/.zshrc
│   └── .config/zsh/ #   Modular config (18 files), plugins, mehshell prompt
├── nvim/            # Neovim config (submodule, see nvim/.config/nvim/AGENTS.md)
├── fonts/           # Nerd Font files
├── wallpaper/       # Desktop wallpapers
├── private/         # Sensitive configs (submodule, SSH-only access)
├── install          # Bootstrap script (OS detect → pkg manager → stow)
└── uninstall        # Remove stowed symlinks
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add new tool config | `common/.config/{tool}/` | Cross-platform tools go here |
| Add Linux-only config | `linux/.config/{tool}/` | Arch-specific (hyprland, waybar, etc.) |
| Add macOS-only config | `osx/.config/{tool}/` | Mac-specific (yabai, skhd, etc.) |
| Modify shell | `zsh/.config/zsh/` | See `zsh/.config/zsh/AGENTS.md` |
| Modify editor | `nvim/.config/nvim/` | See `nvim/.config/nvim/AGENTS.md` |
| Modify tmux | `common/.tmux.conf` | TPM plugins at bottom |
| Add shell alias | `zsh/.config/zsh/zsh-aliases` | Functions: `gac`, `gacp`, `kport` |
| Add env variable | `zsh/.config/zsh/zsh-exports` | PATH, runtimes (nvm, pyenv, go, rust) |
| Add custom script | `linux/.config/scripts/` | Executable utilities, symlinked to ~/.config/scripts |
| Install on new machine | `./install` | Detects OS, installs deps, runs stow |
| Selectively install | `stow {dir}` | e.g. `stow zsh` for just shell config |
| Reproduce packages | `linux/.pacman.list` | `pacman -S --needed $(comm -12 ...)` |

## HOW STOW WORKS HERE

Each top-level directory mirrors `$HOME`. Running `stow common` creates symlinks:
- `common/.tmux.conf` → `~/.tmux.conf`
- `common/.config/alacritty/` → `~/.config/alacritty/`

`.stow-local-ignore` excludes: `.git`, `README.*`, `LICENSE.*`, editor backups.

`install` script runs `stow */` to link everything. `uninstall` runs `stow -D` per folder.

## CONVENTIONS

- **Directory naming** matches stow target path (e.g., `common/.config/kitty/` → `~/.config/kitty/`)
- **Platform separation**: shared → `common/`, linux-only → `linux/`, mac-only → `osx/`
- **Submodules** for independently-versioned configs (nvim, zsh plugins, private)
- **No framework** for zsh — custom `zsh_add_plugin()` / `zsh_add_file()` loader functions
- **Font**: MesloLGM Nerd Font, 16pt in the terminals (kitty + alacritty); Geist Mono for the desktop HUD
- **Color theme**: the Bromigos palette (bromigOS's `brand/palette.*`, the Wick's); on Linux the apps read bromigOS's active theme (`bromigos theme`, `~/.local/state/bromigos/theme/current/`), kitty on macOS `bromigos-macos.conf`; tokyonight-night (neovim)
- **Commit style**: `Added:`, `Updated:`, `Removed:`, `Fixed:` prefix
- **Public repo**: no private infrastructure details and no secrets in plaintext; see "Private values" below

## PRIVATE VALUES (this repo is public)

The rule, for every helper and for VECTOR: nothing that maps the operator's lab goes into a tracked file in plaintext. That means LAN addresses, internal hostnames (`*.<lab domain>`), Vault paths, device, node and host names, cluster layout, personal identifiers beyond the GitHub handle, and anything token-shaped. Code, generic defaults, the brand and docs that say *how* things work are fine.

- **Where private values live:** `linux/.config/bromigos/private.sops.yaml`, committed **encrypted** with sops + age (recipient pinned in `.sops.yaml`). Keys stay readable and values are `ENC[...]`. At login `bromigos-private.service` decrypts it to `~/.config/bromigos/private/` (gitignored, 0600): `config.json` (all of it), `env` (its `env:` section, sourced by `zsh-exports`) and `NOTES.md` (the private runbook: addresses, hosts, which Vault path holds what). `bromigos-private.path` re-decrypts after a `git pull` changes the file. The age private key is `~/.config/sops/age/keys.txt` (0600, never committed). A backup is in Vault; the private notes say where and how to restore it.
- **Add or change a value:** `bromigos-private edit` (this is `sops edit` on the file, then decrypt), then commit the encrypted file. Sections: `endpoints.*` (base URLs: `lab`, `arbiter`, `prometheus`, `grafana`, `argocd`, `litellm`, `gnosis_gate`, `searxng`, `tts`, `vault`, `pelican`), `games.minecraft_ping` (the Minecraft proxy's public `host:port`, for GAME SERVERS' player names), `lan.*` (`domain`, `ping` list for the radar, `ssh_host`), `netmap.*` (gateway/switch/AP models and IPs, `roles`, `aliases`, `show_prefixes`, `show_hosts`), `vault.root`, `vault.paths.*`, `paths.*` (`admin_kubeconfig`, `homelab_repo`), `env.*`, `secrets` (the manifest below), `guard.patterns`, `docs.*`. `operator.*` (`name`, `full_name`, `aliases`, `address`, `pronouns`) says who the operator is and what VECTOR calls him: `bromigos-private decrypt` seeds the user profile `~/.config/bromigos/profile.toml` (gitignored; `bromigos profile`) from it when there is no profile, and never overwrites one, so the public code holds no names.
- **Read them in code** through `bromigos_private` (bromigOS, `/usr/lib/bromigos/lib/bromigos_private.py`; `bromigos private decrypt|edit|status` and `bromigos secrets sync|status` manage the overlay and the Vault files): `P.url("lab", "/api/status")`, `P.get("lan.ping", [])`, `P.vault("lab_api")`, `P.path("admin_kubeconfig")`. The holo package has `holo/private.py` (`PRIV`, plus `fill()` for `{{endpoints.lab}}` placeholders in prompts), and bromigos-live has `live/config.py` (`PRIV`; radial items take `endpoint = "<name>"`). Every caller passes a neutral default (empty), so a fresh clone without the key runs and just shows "not configured".
- **Docs and skills** name the key instead of the value, e.g. "the Lab URL is `endpoints.lab`". Skills can write `{{endpoints.lab}}`; VECTOR's skill loader fills it in, and other readers find the value in `~/.config/bromigos/private/config.json`.
- **Real secrets never go in the repo, not even encrypted.** Tokens, keys and kubeconfigs stay in Vault. `bromigos-secrets sync` copies each one to a 0600 file in `~/.local/share/bromigos/`, using the `secrets:` manifest (file → Vault path#key) that sits inside the encrypted file. It logs in with `$VAULT_TOKEN`, then the operator's `~/.vault-token`, then VECTOR's AppRole. It never prints a value and never blanks a file it can't read. `bromigos-secrets.service` runs it at login, and `bromigos-secrets status` lists the files.
- **The guard:** `.githooks/pre-commit` (turn it on with `.githooks/install`, which sets `core.hooksPath`; `./install` does this) runs `lib/privacy_guard.py check-staged` on every commit. It blocks private IPv4 addresses, internal DNS names, MAC addresses, token shapes (plus gitleaks when installed) and the lab's own names from `guard.patterns`. It also checks that every `*.sops.*` file carries sops metadata and only `ENC[...]` values. `.github/workflows/privacy.yml` runs the same check over the whole tree, plus gitleaks over the pushed commits, with the lab patterns from the `PRIVACY_PATTERNS` repo secret. VECTOR's build guard and shell push check use the same patterns. A reviewed false positive can end its line with `privacy: allow`. Never use `--no-verify` to get real details in.
- **Commit hygiene with several helpers in one checkout:** `git pull --rebase` first, stage only your own paths (`git commit -- <paths>`), and never commit whatever happens to be in the index.

## ANTI-PATTERNS

- **DO NOT** `source ~/.zshrc` to reload — use `exec zsh` or `exit` (shell state issues)
- **DO NOT** put cross-platform configs in `linux/` or `osx/` — use `common/`
- **DO NOT** modify nvim submodule from this repo — push changes in the nvim repo first, then `git submodule update`
- **DO NOT** clone via HTTPS — submodules require SSH (`git@github.com:...`)

## SUBMODULES

| Submodule | Path | Purpose |
|-----------|------|---------|
| nvim config | `nvim/` | Full neovim setup (separate repo) |
| zsh-autosuggestions | `zsh/.config/zsh/plugins/zsh-autosuggestions` | History suggestions |
| zsh-syntax-highlighting | `zsh/.config/zsh/plugins/zsh-syntax-highlighting` | Real-time highlighting |
| zsh-autopair | `zsh/.config/zsh/plugins/zsh-autopair` | Bracket auto-pairing |
| private | `private/` | Sensitive configs (SSH-only) |

Update all: `git submodule update --remote --recursive`

## BROMIGOS DESKTOP (Linux, since 2026-10-04)

The Hyprland desktop is the operator's control center, styled as the Wick (BLACKFLAME's relay station in the Bromigos lore, `bromigos-org/platform/agents/LORE.md`): phosphor green on void, a retro sci-fi HUD in which every light and number is real. **The desktop is bromigOS** (packages from `bromigos-org/bromigOS` and `bromigos-org/vector`); how bromigOS works is its own documentation: `README.md`, the index `docs/README.md`, the manual (`manual/`, with the generated `commands.md` and `keys.md`), and the vector repo's `README.md`. What's here is only mine on top of it. **My setup (how the pieces talk, where state lives and how to regenerate it): `linux/.config/bromigos/README.md`.** Each piece has its own README for detail.

### Map

| Piece | Where (under `linux/.config/`) | Docs |
|-------|-------|------|
| My brand kit: portraits, wordmarks, overlays, my lab's and ARBITER's marks, (bromigOS's own brand, palette and emblem kits are in bromigOS) | `bromigos/brand/` | `bromigos/brand/README.md` |
| My hologram models: the ARBITER monolith (VECTOR's ship in bromigos-vector, the rack in bromigos-homelab) | `bromigos/vector/holo/` | `bromigos/vector/holo/README.md` |
| Theme: Hyprland, bar, launcher, notifications, lock/idle, GTK/Qt themes, cursor | `hypr/`, `waybar/`, `rofi/`, `dunst/`, `bromigos/gtk/`, `../.local/share/` | `bromigos/README.md` "Theme" |
| Hyprland config (Lua: binds, rules, devices, autostart; switch/rollback, dispatch helper) | `hypr/hyprland.lua`, `hypr/bromigos/*.lua`, `bromigos/bin/bromigos-{hyprconfig,dispatch}` | `bromigos/skills/hyprland-config.md` |
| Widgets: SYSTEM, NETWORK, STORAGE, LAB, WORKBENCH, FIELD NOTES, SHORTCUTS (package `bromigos-widgets`, code in bromigOS `widgets/`); GAME SERVERS (plugin) | `bromigos/widgets/` (layout.json, launcher), `bromigos/plugins/widgets/` | `bromigos/widgets/README.md`, bromigOS `widgets/README.md`, `docs/plugins.md` |
| Live layer: background, decks (holo deck, ARBITER, Drift map, timeline), VECTOR's holograms (Mind, Ops, Swarm, Network, Replay), intercept, transmissions, codec calls, screensaver, sounds (package `bromigos-live`, code in bromigOS `live/`; Netmap, Ops and Mind come with `bromigos-homelab`; the ARBITER deck and replay are my plugins) | `bromigos-live/` (config.toml, launcher), `bromigos/plugins/live/` | `bromigos-live/README.md`; bromigOS `live/README.md`, `live/docs/ELEMENTS.md`, `docs/plugins.md` |
| VECTOR (the desktop AI) and the holo daemon (shared 3D renderer, gallery) (package `bromigos-vector`, code in `bromigos-org/vector`; Gnosis memory comes with `bromigos-homelab`) | `bromigos/vector/` (voice.json, eyes.json, kb-sync.py, make-refs.py), `bromigos/plugins/vector/`, `bromigos/holo/bin/` (launcher hand-over) | vector repo `README.md`, `docs/plugins.md`; "VECTOR" below |
| Skills (VECTOR's know-how, also the best guide for humans) | `bromigos/skills/` | the files themselves |
| Start page (browser home, with its own switchboard) | `bromigos/startpage/` | `bromigos/README.md` "Start page" |
| Login screen (SDDM theme, matches the lock screen) | `bromigos/sddm/` (theme in `bromigos/`, `build.py`, `install.sh` run with sudo) | `bromigos/sddm/bromigos/README.md` |
| Razer keyboard and mouse (macro keys, dial, lighting) | `hypr/razer-blackwidow.xkb`, `bromigos/bin/bromigos-{knob,rgb}` | `bromigos/README.md` "Razer" |
| Services and timers | `systemd/user/bromigos-*` | `bromigos/README.md` "Services" |
| Wallpaper switcher, capture, shell banner (bromigOS, package bromigos-desktop; my den variants in `wallpaper/.config/wallpaper/`) | `/usr/bin/bromigos-{wallpaper,shot,rec,banner}` | script headers, `zsh/.config/zsh/AGENTS.md` |
| Doc tooling | `bromigos/bin/bromigos-docs` | its header |

### How they talk (summary)

- Keys run each piece's CLI (`bromigos-widgets`, `bromigos-live`, `bromigos-holo`), which reaches its daemon over a unix socket in `$XDG_RUNTIME_DIR`.
- VECTOR writes his actions to `$XDG_RUNTIME_DIR/bromigos-vector-events.jsonl` (schema: the vector repo's `README.md`, "Event feed") and his state to `bromigos-vector.json`; the holograms draw the feed, the bar pip and the Razer lighting read the state. He drives the holograms with `bromigos-live <deck> <verb>`.
- One voice: codec calls speak through VECTOR's voice server. One sound mute (SUPER+SHIFT+M) for the desktop's cues, VECTOR's own on SUPER+SHIFT+V.
- Homelab data (Lab API, Prometheus, ARBITER GETs, Gnosis via the gate, LiteLLM): `bromigos/skills/data-sources.md`.
- State outside git (tokens, venvs, voices, notes, logs, caches, the wallpaper choice): the table in `bromigos/README.md`.

### Rules the operator set

- Every element shows real data or does something. No decorative status text; decoration (atmosphere, the emblem) is marked as such.
- No CRT overlay (scanlines, vignette) over the screen or app windows. The live layer stays strictly behind windows.
- No callsign, frequency or dossier on the desktop. Identity lives only in the emblem.
- Original IP only. Personal art in the operator's likeness is fine for his own desktop; the lore canon keeps BLACKFLAME's face unseen.
- Custom image, video and audio assets are made with the operator's `nolgia` CLI (or procedurally).
- Hover hints on everything hoverable. Heavy reads only while visible.
- Real money stays the operator's: nothing on the desktop trades or arms; ARBITER is shown as paper.
- The LAB panel reads the lab's `/api/status` with a read-only token (`~/.local/share/bromigos/lab-token`, from Vault via `bromigos-secrets sync`); its URL is the private overlay's `endpoints.lab`.

### Key binds

<!-- keybinds:start -->
Generated by `bromigos-docs keys` from `linux/.config/hypr/hyprland.lua` and the `bromigos/*.lua` it requires (ALT is `mainMod`; the SHORTCUTS panel shows the same list live). Do not edit by hand.

**VECTOR**

| Keys | Action |
|------|--------|
| SUPER + E | VECTOR: show / minimize (also M1) |
| SUPER + SHIFT + E | VECTOR: conversation mode on/off (hands-free) (also M3) |
| SUPER + V | VECTOR: hold to talk (also M2) |
| DIAL TURN | VECTOR: cycle voices (auto, Voss, Sigil, Arc, Lynx, Lin Yao) |
| SUPER + SHIFT + V | VECTOR: voice on/off (also DIAL PRESS) |

**HOLOGRAMS**

| Keys | Action |
|------|--------|
| SUPER + H | Holo deck (this machine) (also M4) |
| SUPER + O | 3D model gallery |
| SUPER + G | ARBITER deck (the Floor) (also SIDE 1) |
| SUPER + T | Timeline (scrub the last 72 h) (also SIDE 2) |
| SUPER + M | Drift map (lore star chart) |
| SUPER + I | Mind: VECTOR's memory and knowledge |
| SUPER + SHIFT + O | Ops theater: pushes, CI, Argo, pods |
| SUPER + SHIFT + S | Swarm: repos and agent starships |
| SUPER + SHIFT + N | Network map: the LAN, traffic, latency |
| SUPER + R | Trade replay: an ARBITER paper trade |
| SUPER + A | Radial quick-launch |

**PANELS + NOTES**

| Keys | Action |
|------|--------|
| SUPER + W | All desktop panels |
| SUPER + K | This shortcuts panel |
| SUPER + SHIFT + K | Search shortcuts (Enter runs) |
| SUPER + S | System panel |
| SUPER + N | Network panel |
| SUPER + D | Storage panel |
| SUPER + C | Lab panel |
| SUPER + B | Workbench panel |
| SUPER + F | Notes panel |
| ALT + N | Type in field notes |
| ALT + SHIFT + N | Quick note from anywhere |

**LIVE LAYER**

| Keys | Action |
|------|--------|
| SUPER + X | Scanner: pin hardware schematic |
| SUPER + Z | Scanner: hold to scan |
| SUPER + SHIFT + C | Codec calls: voice on/off |
| SUPER + SHIFT + M | Live layer sounds on/off |
| SUPER + SHIFT + B | Live background on/off |

**LAUNCH**

| Keys | Action |
|------|--------|
| ALT + P | Launcher |
| ALT + TAB | Window switcher |
| ALT + SHIFT + ENTER | Terminal |
| ALT + E | Files |
| ALT + W | LibreWolf |
| ALT + SHIFT + W | Chrome |
| ALT + SHIFT + D | Discord |
| ALT + M | Spotify |
| ALT + SHIFT + O | OBS |
| ALT + G | Steam |
| ALT + R | reMarkable mirror |

**CAPTURE**

| Keys | Action |
|------|--------|
| ALT + Y | Screenshot a region (also M5) |
| ALT + SHIFT + Y | Screenshot the screen |
| ALT + SHIFT + R | Record a region (again to stop) (also SIDE 3) |

**WINDOWS**

| Keys | Action |
|------|--------|
| ALT + C | Close window (also ALT+SHIFT+C) |
| ALT + F | Maximize |
| ALT + SHIFT + F | Fullscreen |
| ALT + SHIFT + V | Float / tile window |
| ALT + ENTER | Swap with master |
| ALT + J | Next window |
| ALT + K | Previous window |
| ALT + LMB DRAG | Move window |
| ALT + RMB DRAG | Resize window |
| ALT + H | Focus left |
| ALT + L | Focus right |
| ALT + SHIFT + H | Move window left |
| ALT + SHIFT + L | Move window right |
| ALT + SHIFT + K | Move window up |
| ALT + SHIFT + J | Move window down |
| ALT + ← | Narrower |
| ALT + → | Wider |

**WORKSPACES**

| Keys | Action |
|------|--------|
| ALT + S | Scratchpad |
| ALT + SHIFT + S | Send window to scratchpad |
| ALT + 1–0 | Go to workspace |
| ALT + SHIFT + 1–0 | Move window to workspace |

**MEDIA**

| Keys | Action |
|------|--------|
| MUTE | Mute |
| VOL− | Volume down |
| VOL+ | Volume up |
| MIC | Mic mute |
| BRI+ | Brightness up |
| BRI− | Brightness down |
| PLAY | Play / pause |
| PREV | Previous track |
| NEXT | Next track |

**SYSTEM**

| Keys | Action |
|------|--------|
| SUPER + L | Lock |
| ALT + SHIFT + E | Power menu |
| ALT + ESC | Suspend |
| ALT + B | Show / hide bar |
| ALT + SHIFT + Q | Quit Hyprland |
<!-- keybinds:end -->

### Adding a piece

1. A directory in the right stow tree with a README (what, why, how to run, where its state lives).
2. Follow `bromigos/skills/desktop-style-guide.md`; for anything animated or 3D, `hologram-build.md`.
3. Binds go in the Lua config with `K.exec`/`K.dsp`: mine in `hypr/hyprland.lua` (the Razer's in `hypr/bromigos/razer.lua`), bromigOS's in its `desktop/hypr/bromigos/binds.lua` or `live.lua` (package bromigos-desktop), an `EXEC` row in bromigOS's `widgets/keybinds.py`, then run `bromigos-docs keys`. My rules, env and autostart are in `hypr/hyprland.lua` after bromigOS's defaults (`/usr/share/bromigos/default/hypr/`); how-to in `bromigos/skills/hyprland-config.md`. `hyprctl dispatch` takes Lua (`'hl.dsp.focus({ workspace = 3 })'`); `hypr/hyprland.conf` is only the rollback (`bromigos-hyprconfig conf`).
4. Secrets: a mode-600 file in `~/.local/share/bromigos/` from Vault; record its path in the state table.
5. A row in the map above and in `bromigos/README.md`; commit (`Added:`), push.

### VECTOR

<!-- Owned by the VECTOR builder: the summary of VECTOR's capabilities and limits. Detail lives in the vector repo's README.md (bromigos-org/vector, installed as bromigos-vector in /usr/lib/bromigos/vector; paths below like holo/... are in that tree). -->

One daemon (`python -m holo.app`, started on first key) with one shared renderer (`holo/render.py`: projection table, part-indexed wireframes, scan sweep, bloom). **VECTOR** (SUPER+E) is the canon SpacePort caretaker (platform `agents/network/vector.yaml`), answering the Wick's console over the relays from his post at the arrivals pad (he replaced PILOT on 2026-10-04; `pilot` verbs and `holo.pilot.voice` still work as aliases): a construct of relay light on its emitter, typed chat on the homelab LiteLLM, read-only tools (`holo/vector/tools.py`), long-term memory in Gnosis (`holo/vector/memory.py`: recall before every turn in about 0.05 s, capped at 0.2 s, from a local mirror of his Gnosis space; `remember` and `forget` tools; an end-of-conversation summary with fact extraction), a knowledge base of the operator's docs in Gnosis (`kb-bromigos`, `kb-nolgia`, `kb-personal`, `kb-desktop`, `kb-homelab`, about 9,600 chunks, synced nightly by `bromigos/vector/kb-sync.py` and `bromigos-kb-sync.timer`, read by `knowledge_search` in about 0.15 s), conversation history (☰ HISTORY or Ctrl+H: past sessions with titles, search, read, CONTINUE; and the `conversation_history` tool, from the local `vector-chat.log`) ( the brain is Pydantic AI, `holo/vector/brain_pai.py` in `~/.local/share/bromigos/venv-brain`, with the classic one selectable in his `voice.json` (`~/.config/bromigos/vector/`); the read tools are also an MCP server, `holo/vector/mcp_server.py`) and a live model on his side table for whatever he's discussing. It never blocks the desktop (click-through except the entry and MINIMIZE, keyboard on demand), keeps working minimized with the waybar `custom/vector` pip for state and unread replies, and never depends on one model (`hive`, then Nemotron-Lightning, then Qwen, 9 s to first byte each). Voice is push-to-talk with barge-in and echo cancellation; no hotword. Everything is local: faster-whisper large-v3-turbo, and Qwen3-TTS 1.7B speaking five voices from local references of the operator's Brodec cast (Voss main, Sigil readouts, Arc technology, Lynx the Floor, Lin Yao notices; `bromigos/vector/make-refs.py` renders them once from Fish, never at runtime). VECTOR switches on whole sentences, by his own markers or a fallback heuristic, with a dial-scratch cue and a colour crossfade. A mood layer (calm, excited, concerned, alarmed), driven by the reply and by the facts in tool results, tints the hologram over the voice colour. `bromigos-holo voice …`, the `set_voice` tool and right-clicking the pip pin a voice. Kokoro is the fallback, and each voice has its own projector shimmer (his `voice.json`). It is served by `holo/voice_server.py` in `~/.local/share/bromigos/venv-tts`, spawned on demand and exiting when idle. Voice candidates for comparison are in `~/Music/pilot-voice-candidates/`. **Gallery** (SUPER+O): the 3D models as holograms with suit-diagnostic explode, callouts on live data, click-to-isolate. `bromigos-holo status` reports fps and frame time; logs in `~/.local/state/bromigos/` (`holo.log`, `vector-chat.log`, `vector-audit.log`, all local only)

VECTOR does the tasks he's given, end to end, and verifies them (2026-10-05): he narrates each state change in one line, checks the result (Ready, Synced and Healthy, CI green) and reports. Read tools: this machine, the Lab, the cluster (`pilot-readonly`), Prometheus, Argo CD, `gh`, fixed ARBITER console GETs, Gnosis through the `gnosis-gate`, the knowledge base, docs, history, the web. Act tools (`holo/vector/act.py`): restart, scale, delete a pod, run a Job from a CronJob, Argo sync/refresh/wait, CI watch, kb notes, the holograms; cluster actions run as ServiceAccount `vector-operator` (homelab `helm/vector`: edit on workloads, no Secrets/RBAC/tokens, admission policies keep it out of privileged namespaces' templates and off `arbiter-live*`). Vault (`holo/vector/vault.py`, AppRole `vector`): list key names, store a generated or operator-typed value (a local dialog), copy Vault to Vault; never a value back; Vault itself denies `homelab/arbiter*`, `entitlements`, his own credentials and admin paths. His terminal, `run_shell`, has **full access as the operator's user and no approval step**, with his own kubeconfig, the operator's admin kubeconfig (`$HOMELAB_ADMIN_KUBECONFIG`), ansible, SSH to the homelab and git pushes. Its content refusals are in code (`holo/vector/shell.py`, tested by `tools/test-shell.py` and `tools/test-act.py`): no sudo or privilege escalation, even nested or over SSH; no secret values (scrubbed environment, Kubernetes secrets in any form, pod environments, token minting, the vault CLI and API, ansible-vault/inventory/debug, secret paths; redacted output); no RBAC changes outside GitOps; no real money (ARBITER live/intents routes, arbiter-live, LIVE_OPERATORS, venue orders, transfers, wallet keys, pushes of ARBITER's real-money code). Sensitive playbooks are announced aloud and logged; every command and refusal goes to `~/.local/state/bromigos/vector-shell.log`. He launches any installed program by name and manages windows, writes software in the repos himself, creates repos (`bromigos-org`, `nolgiainc`, `blackflame007`; private by default), and always tracks his changes: commit and push in each repo's style, outside changes recorded in `VECTOR-CHANGELOG.md` (this repo's root), and a done-check (`changes_check`) before he reports a task done. He can look at the screen (`holo/vector/eyes.py`), read only and only when asked or to check his own build, through the lab's own multimodal model, with captures kept in memory and a blocklist (password managers, banking, trading or wallet sites, Vault, private browsing) that stops a capture outright; watch mode is opt-in, shows ◉ WATCHING on the bar and ends after 15 minutes. He has his own browser (`holo/vector/browser.py`): a separate Chrome with its own profile (`~/.local/share/bromigos/vector-browser`, window class `vector-browser`, never the operator's Chrome) that he drives through Playwright over a pipe, visible on the desktop, for research and multi-step web tasks; in code it refuses banking, brokerage, crypto, wallet, prediction-market, password-manager, Vault and money-console sites and LAN hosts, never types into login, password or payment fields, never clicks buy, pay, subscribe or checkout, and has downloads and uploads off (`tools/test-browser.py`). His desktop actions are also published over MCP to his brain on Hermes (`mcp_server.py` ACT, served by `mcp_lan.py`). He speaks up on his own only for explained lab alerts (through the live layer's codec channel, which then stands down its raw count call) and a short brief when the operator returns, never during fullscreen, games or recording, and not at all while told to be quiet (`holo/vector/briefing.py`). System-level commands from his terminal get a snapper pre/post pair, and "undo that" reverts it (`holo/vector/snapshots.py`). He makes images, video and audio with the operator's nolgia CLI under a daily credit cap (`nolgia.json` in the package; over it he asks first), reviews every asset with the vision model before presenting it, and logs each job's spend. ARBITER stays read only for him: nudges are the operator's. Skills (know-how loaded on demand, routed by meaning) live in the shared `linux/.config/bromigos/skills/`. His actions go on the event feed (`$XDG_RUNTIME_DIR/bromigos-vector-events.jsonl`, schema in holo/README.md) for the holograms. He addresses the user as their profile says (`~/.config/bromigos/profile.toml`, read with `bromigos profile --json`; the persona is rebuilt when it changes, and his `set_profile` tool edits it when told "call me …"), names their aliases only when asked, never calls them host or operator to their face, never gives them an arrival number, and never claims to have left his post. No cloned voices: never a real person's, a game's or a film's (VECTOR's production Fish model is one, so it isn't used). Keys stay in mode-600 files under `~/.local/share/bromigos/` (`litellm-key`, `gnosis-vector-{read,write}-token`, `gnosis-kb-ingest-token`, `vector-operator-kubeconfig`, `vault-vector-{role,secret}-id`), never in the repo or logs.

## COMMANDS

```bash
# Bootstrap new machine
./install

# Stow specific config
stow zsh                    # Just shell
stow common linux           # Shared + Linux

# Unstow
stow -D zsh

# Update submodules
git submodule update --init --recursive

# Reproduce Arch packages
pacman -S --needed $(comm -12 <(pacman -Slq | sort) <(sort linux/.pacman.list))

# Export current packages
pacman -Qqe > linux/.pacman.list
```

## NOTES

- Tmux history: 20,000 lines, sessions auto-saved/restored via continuum
- Zsh history: 1,000,000 lines at `~/.zsh_history`
- `.mypy_cache/` exists at root — likely from a Python script, gitignored
- `private/` submodule (`blackflame007/private`) holds older notes; the desktop's private values are the encrypted overlay (see "Private values")
- Neovim requires >= 0.11.1, Node.js, Python 3, Rust, Nerd Font
