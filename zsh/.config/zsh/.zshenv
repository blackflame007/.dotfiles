#PATH
typeset -U PATH path
path=("$HOME/.local/bin" "$HOME/.config/scripts/" "$HOME/.local/share/applications" "$HOME/.foundry/bin" "$path[@]")
export PATH
