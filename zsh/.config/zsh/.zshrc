#!/bin/sh
export ZDOTDIR=$HOME/.config/zsh
source "$ZDOTDIR/.zshenv"

# Terminal settings
stty stop undef 2>/dev/null

HISTFILE=~/.zsh_history
SAVEHIST=1000000
HISTSIZE=1000000
setopt incappendhistory

# some useful options (man zshoptions)
setopt autocd extendedglob nomatch menucomplete
setopt interactive_comments
zle_highlight=('paste:none')

# beeping is annoying
unsetopt BEEP


# completions
zstyle ':completion:*' menu select
zmodload zsh/complist
_comp_options+=(globdots)		# Include hidden files.

autoload -U up-line-or-beginning-search
autoload -U down-line-or-beginning-search
zle -N up-line-or-beginning-search
zle -N down-line-or-beginning-search

# Colors
autoload -Uz colors && colors

# Useful Functions
source "$ZDOTDIR/zsh-functions"

# Normal files to source
zsh_add_file "zsh-exports"
zsh_add_file "zsh-vim-mode"
zsh_add_file "zsh-aliases"
zsh_add_file "zsh-mehshell"

# Plugins
zsh_add_plugin "zsh-users/zsh-autosuggestions"
zsh_add_plugin "zsh-users/zsh-syntax-highlighting"
zsh_add_plugin "hlissner/zsh-autopair"

# Completions — cache compinit dump, rebuild only once per day
autoload -Uz compinit
if [[ -f "$ZDOTDIR/.zcompdump" && $(date +'%j') == $(date -r "$ZDOTDIR/.zcompdump" +'%j' 2>/dev/null) ]]; then
    compinit -C
else
    compinit
fi


# Optional tools & runtimes (inits)
zsh_add_file "zsh-fzf"
zsh_add_file "zsh-optional"
zsh_add_file "zsh-conda"
zsh_add_file "zsh-pnpm"
zsh_add_file "zsh-bun"
zsh_add_file "zsh-docker"
