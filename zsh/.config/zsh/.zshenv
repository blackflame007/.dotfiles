# Arch claude-code package sets NPM_CONFIG_PREFIX=/nonexistent via Bun runtime, breaks nvm
unset NPM_CONFIG_PREFIX

#PATH
typeset -U PATH path
path=("$HOME/.local/bin" "$HOME/.config/scripts/" "$HOME/.local/share/applications" "$HOME/.foundry/bin" "$path[@]")
export PATH
