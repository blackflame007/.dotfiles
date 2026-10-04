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
| Palette, emblem, logos, portraits, icons | `linux/.config/bromigos/brand/` | `emblem.svg` is the single source; `icons/` (16 px HUD set, `build-icons.py`); palette as CSS, JSON and kitty |
| Identity text | `linux/.config/bromigos/identity.json` | Ring motto, caption, sign-off. Rebuild with `bromigos-emblem build` |
| Desktop widgets | `linux/.config/bromigos/widgets/` | One GTK3 layer-shell app (SYSTEM, NETWORK, STORAGE, LAB, SWITCHBOARD, FIELD NOTES, SHORTCUTS); layout in `layout.json` |
| Live layer | `linux/.config/bromigos-live/` | GPU shader background, holo deck, radial menu, intercept, screensaver, sounds; toggles in `config.toml` (reloads on save) |
| Bar, launcher, notifications | `linux/.config/waybar/`, `rofi/`, `dunst/` | Themed; rofi power menu and quick note |
| Lock and idle | `linux/.config/hypr/hyprlock.conf`, `hypridle.conf` | Lock at 10 min, display off at 15, never suspends; screensaver at 8 min |
| Wallpapers | `wallpaper/.config/wallpaper/bromigos-*` | `bromigos-wallpaper den|empty|v1` switches the den and lock images (canonical names are symlinks) |

Rules the operator set:

- Every element shows real data or does something. No decorative status text.
- No CRT overlay (scanlines, vignette) over the screen or app windows. The live layer stays strictly behind windows.
- No callsign, frequency or dossier on the desktop. Identity lives only in the emblem.
- Original IP only. Personal art in the operator's likeness is fine for his own desktop; the lore canon keeps BLACKFLAME's face unseen.
- Custom image, video and audio assets are made with the operator's `nolgia` CLI.
- The LAB panel reads EchoCraft Lab's `/api/status` with a read-only token (`~/.local/share/bromigos/lab-token`, from Vault `secret/<vault-path>`).

Key binds (ALT is `$mainMod`):

| Key | Action |
|-----|--------|
| SUPER W | All panels |
| SUPER S / N / D / C / B / F | One panel each |
| SUPER H | Holo deck |
| SUPER A | Radial launcher |
| SUPER SHIFT B | Live layer on or off |
| SUPER SHIFT M | Mute |
| SUPER L | Lock |
| ALT SHIFT E | Power menu |
| ALT N | Focus notes |
| ALT SHIFT N | Quick note |

The SHORTCUTS panel lists every bind live from `hyprland.conf`.

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
