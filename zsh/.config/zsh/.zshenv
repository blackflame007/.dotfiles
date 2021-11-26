#PATH
typeset -U PATH path
path=("$HOME/.local/bin" "$HOME/.config/scripts/" "$path[@]")
export PATH
