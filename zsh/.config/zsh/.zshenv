#PATH
typeset -U PATH path
path=("$HOME/.local/bin" "$HOME/.config/scripts/" "$HOME/.local/share/applications" "$path[@]")
export PATH
