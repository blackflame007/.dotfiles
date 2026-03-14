# ZSH CONFIGURATION

## OVERVIEW

Modular zsh config (18 files) with custom plugin loader — no oh-my-zsh/prezto/zinit. mehshell prompt engine (Go binary). Three plugins as git submodules.

## STRUCTURE

```
.config/zsh/
├── .zshrc              # Main config — sources all modules in order
├── .zshenv             # Early environment (ZDOTDIR)
├── .zprofile           # Login shell init (startx, DOTFILES var)
├── .zcompdump          # Completion cache (generated)
├── zsh-functions       # CORE: zsh_add_file(), zsh_add_plugin(), zsh_add_completion()
├── zsh-exports         # PATH, runtime managers (nvm, pyenv, gvm, cargo, go, bun)
├── zsh-aliases         # Aliases + functions (gac, gacp, kport)
├── zsh-vim-mode        # Vi keybindings, cursor shape per mode
├── zsh-mehshell        # mehshell prompt engine (eval "$(mehshell init zsh)")
├── zsh-fzf             # FZF key bindings + fuzzy completion (conditional)
├── zsh-optional        # Conditional: .zshenv re-source, system nvm
├── zsh-conda           # Conda init (if /opt/miniconda3 exists)
├── zsh-pnpm            # pnpm PATH setup
├── zsh-bun             # Bun completions
├── zsh-docker          # Docker CLI completions
├── completion/         # Custom completion scripts
└── plugins/            # Git submodule plugins
    ├── zsh-autosuggestions/
    ├── zsh-syntax-highlighting/
    └── zsh-autopair/
```

## LOAD ORDER (CRITICAL)

```
.zshrc sources in this exact sequence:
1. zsh-functions       # Loader functions (MUST be first)
2. zsh-exports         # Environment variables, PATH
3. zsh-vim-mode        # Vi keybindings
4. zsh-aliases         # Aliases and shell functions
5. zsh-mehshell        # mehshell prompt engine
6. zsh-autosuggestions # Plugin (via zsh_add_plugin)
7. zsh-syntax-highlighting # Plugin (via zsh_add_plugin)
8. zsh-autopair        # Plugin (via zsh_add_plugin)
9. compinit            # Completion initialization
10. zsh-fzf            # FZF integration (conditional)
11. zsh-optional       # Optional re-sources
12. zsh-conda          # Conda (conditional)
13. zsh-pnpm           # pnpm (conditional)
14. zsh-bun            # Bun (conditional)
15. zsh-docker         # Docker (conditional)
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Add alias or shell function | `zsh-aliases` | OS-aware (`$OSTYPE` case), functions at bottom |
| Add env variable or PATH | `zsh-exports` | Use `path+=("...")` for PATH entries |
| Add new plugin | `.zshrc` | `zsh_add_plugin "user/repo"` — auto-clones to plugins/ |
| Add optional runtime init | New `zsh-{tool}` file | Source via `zsh_add_file "zsh-{tool}"` in `.zshrc` |
| Change prompt | mehshell config | Recompile mehshell or configure via environment |
| Modify vi keybindings | `zsh-vim-mode` | Cursor shapes: block=normal, beam=insert |
| Add completion script | `completion/` | Add to fpath via `zsh_add_completion` |
| Debug sourcing | Check `zsh_add_file` | Silently skips missing files (`[ -f ] && source`) |

## CONVENTIONS

### Plugin Loader Pattern
```bash
# Source a config file from $ZDOTDIR
zsh_add_file "zsh-{name}"       # Sources $ZDOTDIR/zsh-{name} if exists

# Install + source a plugin from GitHub
zsh_add_plugin "user/repo"      # Clones to plugins/{repo}/, sources {repo}.plugin.zsh
```

Plugins are git submodules in `plugins/`. The loader auto-clones missing plugins.

### File Naming
- Config modules: `zsh-{purpose}` (no extension)
- Optional/runtime modules: `zsh-{tool}` (sourced conditionally at end of .zshrc)

### History
- 1,000,000 lines at `~/.zsh_history`
- Options: `incappendhistory` (write immediately, not on exit)

### Shell Options
- `autocd` — cd by typing directory name
- `extendedglob` — advanced glob patterns
- `menucomplete` — cycle through completions
- `interactive_comments` — allow `#` comments in interactive shell
- No beep (`unsetopt BEEP`)

## ANTI-PATTERNS

- **DO NOT** `source ~/.zshrc` to reload — use `exec zsh` or `exit` (shell state issues)

## NOTES

- `zsh-functions` must be sourced first — all other modules depend on `zsh_add_file()`
- `zsh-exports` runs `eval` for pyenv, luarocks — adds startup latency
- Completions include hidden files via `_comp_options+=(globdots)`
- `Ctrl+S` freeze is disabled (`stty stop undef`)
- Paste highlighting disabled (`zle_highlight=('paste:none')`)
