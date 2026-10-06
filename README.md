# .dotfiles

The operator's dotfiles for Arch Linux (Hyprland) and macOS, managed with GNU Stow and a
few git submodules. On Linux they carry the **Bromigos desktop**: a themed Hyprland
control center with HUD widgets, an animated data-driven live layer, holograms, and
VECTOR, the desktop AI.

- **Status:** active, used daily on one Arch workstation (`master`).
- **Docs:** `AGENTS.md` (layout, conventions, the desktop map and the generated key
  table), `linux/.config/bromigos/README.md` (how the desktop works), and a README per
  desktop component.
- **Bromigos systems map:** the network-wide map of services and repos is
  `docs/SYSTEMS.md` in the private `bromigos-org/platform` repo.

## Installing

You need `git` and GNU `stow`. Clone with SSH (the submodules need it):

```bash
git clone git@github.com:blackflame007/.dotfiles.git ~/.dotfiles
cd ~/.dotfiles
git submodule update --init --recursive
```

Then link what you want, or run `./install` (it detects the OS, installs the basics — stow, git, zsh, neovim — and stows every directory):

```bash
stow common linux zsh   # shared, Linux and shell configs
stow zsh                # just the shell
```

Each top-level directory mirrors `$HOME` (for example `linux/.config/hypr/` becomes
`~/.config/hypr/`). Remove links with `stow -D <dir>`, or everything with `./uninstall`.

The Bromigos desktop also needs secrets and Python environments that are not in git;
`linux/.config/bromigos/README.md` ("Where state lives") lists each one and how to get it.

## Packages

The Arch package list is `linux/.pacman.list`.

```bash
pacman -Qqe > linux/.pacman.list                                          # export
pacman -S --needed $(comm -12 <(pacman -Slq | sort) <(sort linux/.pacman.list))  # install (repo packages only)
```
