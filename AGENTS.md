# PROJECT KNOWLEDGE BASE

**Generated:** 2026-03-13
**Commit:** 1b7acc3
**Branch:** master

## OVERVIEW

GNU Stow-managed dotfiles for Arch Linux and macOS. Zsh (custom plugin loader, no framework), Neovim (lazy.nvim, 100+ plugins), tmux (tpm), Hyprland/Yabai window managers. 5 git submodules for nvim config, zsh plugins, and private configs.

## STRUCTURE

```
.dotfiles/
├── common/          # Cross-platform configs (stowed everywhere)
│   ├── .tmux.conf   #   tmux + tpm plugins (resurrect, continuum, yank)
│   └── .config/     #   alacritty, kitty, cava, lf, ranger, mpd, opencode
├── linux/           # Arch Linux-specific (stowed on Linux only)
│   ├── .config/     #   hyprland, waybar, polybar, dunst, rofi, picom, scripts
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
- **Font**: MesloLGM Nerd Font, 16pt (consistent across kitty + alacritty)
- **Color theme**: Nord-inspired palette (terminals), tokyonight-night (neovim)
- **Commit style**: `Added:`, `Updated:`, `Removed:` prefix

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

The Hyprland desktop is themed as the operator's control center in the Bromigos style: phosphor green on void, retro sci-fi HUD. The look comes from bromigos.org, BRODEC and the ARBITER console; the identity comes from the lore (the BLACKFLAME entry and "the burn-in" emblem in `bromigos-org/platform/agents/LORE.md`).

| Piece | Where | Notes |
|-------|-------|-------|
| Palette, emblem, logos, portraits, icons | `linux/.config/bromigos/brand/` | `emblem.svg` is the single source; `icons/` (16 px HUD set, `build-icons.py`); palette as CSS, JSON and kitty; `README.md` lists every portrait, logo, video and overlay asset with its prompt and model, `contact-sheet.jpg` shows them all |
| Identity text | `linux/.config/bromigos/identity.json` | Ring motto, caption, sign-off. Rebuild with `bromigos-emblem build` |
| Desktop widgets | `linux/.config/bromigos/widgets/` | One GTK3 layer-shell app (SYSTEM, NETWORK, STORAGE, LAB, WORKBENCH, FIELD NOTES, SHORTCUTS); layout in `layout.json` |
| Live layer | `linux/.config/bromigos-live/` | GPU shader background behind every window: the den with its screens made live, glyph rain (CPU), floor pulses (network), the Drift space layer, the hardware scanner (every 60 s; pin/hold/on demand), and seamless decorative loops over a clean plate (mug steam, left glitch streaks, floor-row scroll). Summoned decks: local holo deck, ARBITER deck (the Floor, read-only GETs), Drift map (lore star chart; relays = live lab services), radial launcher. Events: intercept on login/unlock, critical-notification transmission, codec calls (notable ARBITER fills, lab alerts, long jobs via `bromigos-live job -- cmd`, critical notifications, `bromigos-live codec "text"`: a corner panel with the voice's real waveform, spoken in VECTOR's voice (Breeze TTS as the fallback); rate-limited, quiet mode), idle screensaver, sounds. `config.toml` holds every toggle (reloads on save) and marks which layers are data and which decoration. `tools/offscreen.py` renders any of it headless (NVIDIA EGL) to PNG/MP4 |
| Bar, launcher, notifications | `linux/.config/waybar/`, `rofi/`, `dunst/` | Themed; rofi power menu and quick note |
| Lock and idle | `linux/.config/hypr/hyprlock.conf`, `hypridle.conf` | Lock at 10 min, display off at 15, never suspends; screensaver at 8 min |
| Wallpapers | `wallpaper/.config/wallpaper/bromigos-*` | `bromigos-wallpaper den|empty|masked|v1` switches the den and lock images. The choice is local state (`~/.local/state/bromigos/wallpaper/{den,lock}.jpg`, `variant`), never a tracked file; swaybg (`bromigos-wallpaper apply` at login), hyprlock and the live layer read it. The committed canonical symlinks stay on the default. All variants share the v1 plate; the live layer approves them by a sha1 allowlist in its `config.toml` |
| Browser start page | `linux/.config/bromigos/startpage/` | Search, SWITCHBOARD links with up/down, Lab status, latest FIELD NOTES, clock. `snapshot.py` writes `data.js` (gitignored) every minute from `bromigos-startpage.timer` (`linux/.config/systemd/user/`); the page never sees the Lab token |
| GTK, icons, cursor | `linux/.config/bromigos/gtk/` builds `linux/.local/share/themes/Bromigos`, `icons/Bromigos`, `icons/Bromigos-cursor` | GTK3/GTK4 theme generated from the toolkit's own dark theme with the palette mapped in (edit `overrides.css`, rerun `build-gtk-theme.py`); folder icons recoloured from Breeze Dark; cursors drawn in `build-icons-cursor.py` (Xcursor written directly, no xcursorgen). Applied with gsettings; libadwaita colours come from `libadwaita.css`, imported by `~/.config/gtk-4.0/gtk.css` |
| Qt / KDE apps (Dolphin) | `linux/.local/share/color-schemes/Bromigos.colors` | KDE colour scheme in the palette; applied with `plasma-apply-colorscheme Bromigos` (writes `~/.config/kdeglobals`, which is not tracked) plus `kwriteconfig6 --file kdeglobals --group Icons --key Theme Bromigos`. Qt apps read it through `env=QT_QPA_PLATFORMTHEME,kde` in hyprland.conf. Dolphin is the file manager (ALT+E, WORKBENCH) |
| Shell | `zsh/.config/zsh/zsh-bromigos`, `linux/.config/bromigos/shell/` | mehshell prompt recoloured to the palette (precmd hook, 24-bit terminals only); `bromigos` prints the emblem in braille with live host, kernel, uptime, load, memory and disk (about 3 ms). Shown on login shells; `BROMIGOS_BANNER=always` for every shell, `off` to hide |
| Screenshots, recording | `linux/.config/bromigos/bin/bromigos-shot`, `bromigos-rec` | Save, copy, a quiet cue from the live layer's sounds (honours its mute), and a themed notification (dunst rules `capture.*`). Click a shot's notification to annotate it in swappy |
| Holograms and VECTOR | `linux/.config/bromigos/holo/` (`bin/bromigos-holo`) | One daemon (`python -m holo.app`, started on first key) with one shared renderer (`holo/render.py`: projection table, part-indexed wireframes, scan sweep, bloom). **VECTOR** (SUPER+E) is the canon SpacePort caretaker (platform `agents/network/vector.yaml`), answering the Wick's console over the relays from his post at the arrivals pad (he replaced PILOT on 2026-10-04; `pilot` verbs and `holo.pilot.voice` still work as aliases): a construct of relay light on its emitter, typed chat on the homelab LiteLLM, read-only tools (`holo/vector/tools.py`), long-term memory in Gnosis (`holo/vector/memory.py`: recall before every turn in about 0.05 s, capped at 0.2 s, from a local mirror of his Gnosis space; `remember` and `forget` tools; an end-of-conversation summary with fact extraction) ( the brain is Pydantic AI, `holo/vector/brain_pai.py` in `~/.local/share/bromigos/venv-brain`, with the classic one selectable in `holo/voice.json`; the read tools are also an MCP server, `holo/vector/mcp_server.py`) and a live model on his side table for whatever he's discussing. It never blocks the desktop (click-through except the entry and MINIMIZE, keyboard on demand), keeps working minimized with the waybar `custom/vector` pip for state and unread replies, and never depends on one model (`hive`, then Nemotron-Lightning, then Qwen, 9 s to first byte each). Voice is push-to-talk with barge-in and echo cancellation; no hotword. Everything is local: faster-whisper large-v3-turbo, and Qwen3-TTS 1.7B speaking five voices from local references of the operator's Brodec cast (Voss main, Sigil readouts, Arc technology, Lynx the Floor, Lin Yao notices; `holo/voices/make-refs.py` renders them once from Fish, never at runtime). VECTOR switches on whole sentences, by his own markers or a fallback heuristic, with a dial-scratch cue and a colour crossfade. A mood layer (calm, excited, concerned, alarmed), driven by the reply and by the facts in tool results, tints the hologram over the voice colour. `bromigos-holo voice …`, the `set_voice` tool and right-clicking the pip pin a voice. Kokoro is the fallback, and each voice has its own projector shimmer (`holo/voice.json`). It is served by `holo/voice_server.py` in `~/.local/share/bromigos/venv-tts`, spawned on demand and exiting when idle. Voice candidates for comparison are in `~/Music/pilot-voice-candidates/`. **Gallery** (SUPER+O): the 3D models as holograms with suit-diagnostic explode, callouts on live data, click-to-isolate. `bromigos-holo status` reports fps and frame time; logs in `~/.local/state/bromigos/` (`holo.log`, `vector-chat.log`, `vector-audit.log`, all local only) |
| 3D models | `linux/.config/bromigos/brand/3d/` | Workstation, the Wick, the rack, the ARBITER monolith (nolgia concept + hunyuan3d-v3) and the burn-in (extruded from the canon SVGs). `README.md` has prompts, credits, the part manifest and the `.holo` format; `tools/bake.py` rebakes from `manifest.json` in the venv `~/.local/share/bromigos/venv` |

Rules the operator set:

- Every element shows real data or does something. No decorative status text.
- No CRT overlay (scanlines, vignette) over the screen or app windows. The live layer stays strictly behind windows.
- No callsign, frequency or dossier on the desktop. Identity lives only in the emblem.
- Original IP only. Personal art in the operator's likeness is fine for his own desktop; the lore canon keeps BLACKFLAME's face unseen.
- Custom image, video and audio assets are made with the operator's `nolgia` CLI.
- The LAB panel reads EchoCraft Lab's `/api/status` with a read-only token (`~/.local/share/bromigos/lab-token`, from Vault `secret/<vault-path>`).
- VECTOR sees, he doesn't touch. His tools are allowlisted in code: this machine; the Lab; the cluster through the `pilot-readonly` ServiceAccount (`~/.local/share/bromigos/pilot-kubeconfig`, Vault `secret/<vault-path>`; get/list/watch only, no secrets, configmaps or exec); Prometheus queries; Argo CD; `gh` read commands for bromigos-org; fixed ARBITER console GETs (never trading or arming); Gnosis through the homelab `gnosis-gate` with two narrow tokens (read his space and the ARBITER research/signal spaces; write and delete only in his own space, `vector`), never Gnosis's service token; the docs and lore. His only writes are his own long-term memory (remember and forget, in his Gnosis space), appending to FIELD NOTES, launching apps or links, panels, wallpaper, the scanner and holograms. No shell, no deletes, no installs. He never names BLACKFLAME, never gives the host an arrival number, and never claims to have left his post. No cloned voices: never a real person's, a game's or a film's (VECTOR's production Fish model is one, so it isn't used). Keys stay in mode-600 files under `~/.local/share/bromigos/` (`litellm-key`, `gnosis-vector-read-token`, `gnosis-vector-write-token`), never in the repo or logs.

Key binds (ALT is `$mainMod`):

| Key | Action |
|-----|--------|
| SUPER W | All panels |
| SUPER S / N / D / C / B / F | One panel each |
| SUPER H | Holo deck: arc rings, cluster constellation and a compact view of the current 3D model (drawn by the shared bromigos-holo renderer from `bromigos/brand/3d/holo/*.holo.npz`; `[` `]` change model, hover a part for its live reading, click it or press O to open that model in the gallery); N opens FIELD NOTES inside it; Tab cycles local → ARBITER → timeline |
| SUPER G | ARBITER deck: the Floor as a hologram (road to live, paper core, tape, lineup, ribbons; click a star for its card) |
| SUPER M | Drift map: the lore as a star chart; the lab's live services are the lit relays |
| SUPER T | Timeline: minute history (72 h, `~/.local/state/bromigos-live/history.npz` + `events.jsonl`) as a 3D ribbon to scrub; lab lanes backfilled from EchoCraft |
| SUPER X | Scanner: pin the hardware schematic |
| SUPER Z (hold) | Scanner: hold to scan |
| SUPER A | Radial launcher |
| SUPER E | VECTOR: show (takes the keyboard) or minimize; he keeps working minimized. Enter sends, Esc hands the keyboard back, Shift+Esc minimizes; clicks outside the entry pass through to your windows |
| SUPER O | Hologram gallery, the full model viewer (drag rotate, scroll or Space explode, click a part to isolate, ←/→ or 1–5 model, S scan, Esc) |
| SUPER SHIFT E | VECTOR conversation mode: hands-free; he listens, answers when you pause, listens again; talk over him to interrupt; off after two quiet minutes (the mic is closed whenever it's off) |
| SUPER V (hold) | Talk to VECTOR (barge-in: stops him mid-sentence): the mic is open only while held; release to send |
| SUPER SHIFT V | Mute or unmute VECTOR's voice |
| SUPER SHIFT B | Live layer on or off |
| SUPER SHIFT M | Mute |
| SUPER SHIFT C | Codec calls: voice on/off (quiet mode). Calls speak in VECTOR's voice (`bromigos/holo/voice.json`); the lab's Breeze TTS only if VECTOR's speech server is down |
| SUPER L | Lock |
| ALT SHIFT E | Power menu |
| ALT N | Focus notes |
| ALT SHIFT N | Quick note |
| ALT Y / ALT SHIFT Y | Screenshot region / focused screen |
| ALT SHIFT R | Record a region; press again to stop |

The SHORTCUTS panel lists every bind live from `hyprland.conf`.

### Start page in the browsers

The page is `file:///home/blackflame/.config/bromigos/startpage/index.html`. It needs `systemctl --user enable --now bromigos-startpage.timer` (already on). The default search engine follows the browser (DuckDuckGo in LibreWolf, Google in Chrome); the menu beside the box changes it and is remembered.

- **LibreWolf:** `librewolf-user.js` is linked as `user.js` into the profile, so Home and new windows open the page. Firefox-based browsers cannot set the new-tab page from prefs. For new tabs too: `about:debugging` → This LibreWolf → Load Temporary Add-on → pick `startpage/manifest.json` (lasts until restart), or install any "new tab override" add-on and point it at the URL above.
- **Chrome:** new tab: `chrome://extensions` → turn on Developer mode → Load unpacked → choose `~/.config/bromigos/startpage`; keep the change when Chrome asks. Home and startup: Settings → Appearance → Show home button → enter the URL above; Settings → On startup → Open a specific page → add the URL.

Theme edits in `hyprland.conf` sit in fenced `BROMIGOS THEME` and `BROMIGOS LIVE` blocks. `bromigos-live status` reports whether it is running, idle or paused, with fps; its log is at `~/.local/state/bromigos-live/live.log`.

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
- `private/` submodule contains notes and sensitive settings — never commit secrets to main repo
- Neovim requires >= 0.11.1, Node.js, Python 3, Rust, Nerd Font
