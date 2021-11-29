# .dotfiles

Stow is being used to manage dotfiles. There are many submodules being used in this repo so after cloning install the submodules.
```bash
git submodule update --init --recursive
```
To modify for your own need create a folder tree for config files with the base folder being treated as if it were the HOME directory

Install Example
```bash
stow zsh
```

Uninstall Example
```bash
stow -D zsh
```
