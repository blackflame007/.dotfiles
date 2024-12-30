export ZDOTDIR=$HOME/.config/zsh
source "$HOME/.config/zsh/.zshrc"

[[ -s "/home/blackflame/.gvm/scripts/gvm" ]] && source "/home/blackflame/.gvm/scripts/gvm"

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion
