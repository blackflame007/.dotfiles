# .dotfiles

Stow is being used to manage dotfiles. There are many submodules being used in this repo so after cloning install the submodules.

## Installing

You will need `git` and GNU `stow`

Clone into your `$HOME` directory or `~` using SSH

```bash
git clone git@github.com:blackflame007/.dotfiles.git ~
```
git submodules will not update unless you cloned this repo with  SSH

```bash
git submodule update --init --recursive
```

Run `stow` to symlink everything or just select what you want

```bash
stow */ # Everything (the '/' ignores the README)
```

```bash
stow zsh # Just my zsh config
```

## Uninstall Example
```bash
stow -D zsh
```
## Programs

An updated list of all the programs I use can be found in the `programs` directory

To create the package list

```bash
pacman -Qqe > ~/.dotfiles/programs/.pacman.list
```

To install packages from list make sure to filter out packages from the AUR 

```bash
pacman -S --needed $(comm -12 <(pacman -Slq | sort) <(sort pkglist.txt))
```
