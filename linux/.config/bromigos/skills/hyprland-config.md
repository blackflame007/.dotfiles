---
name: hyprland-config
description: "How Sir's Hyprland is configured — the Lua config (hypr/hyprland.lua and hypr/bromigos/*.lua), adding or changing a keybind, window rule, layer rule, workspace rule, device or autostart program, checking it, and running dispatchers from scripts (`hyprctl dispatch 'hl.dsp…'`) — and the rollback to the old hyprland.conf."
when_to_use: "Adding, changing or finding a keybind, a window/layer/workspace rule, a monitor, a device (keyboard) setting, an environment variable or a login program; any script or tool that calls `hyprctl dispatch`; when a bind or rule doesn't work or Hyprland shows a config error."
---

# The Hyprland config (Lua)

Hyprland 0.56 runs a **Lua** config. The old `hyprland.conf` format (`bind=`, `windowrule =`,
`exec-once=`, `hyprctl dispatch workspace 3`) is deprecated and is removed in 0.57; the file
stays in the repo only as the rollback. Never add anything to it.

| File (in `~/.dotfiles/linux/.config/hypr/`, stowed to `~/.config/hypr/`) | Holds |
|------|-------|
| `hyprland.lua` | monitors, autostart, env, look (gaps, borders, shadow, blur, animations), input, layer rules, window rules, Razer device keymap, workspace→monitor rules; requires the two below |
| `bromigos/binds.lua` | every keybind except the live layer's (stock ones, the `BROMIGOS THEME: keybinds` block, the Razer macro keys) |
| `bromigos/live.lua` | the `BROMIGOS LIVE` block: bromigos-live's autostart, its layer rule and its binds |
| `bromigos/keys.lua` | the bind helpers `K.exec` / `K.dsp` (keep every bind's action as text for SHORTCUTS) |

Hyprland loads `~/.config/hypr/hyprland.lua` when it exists, else `hyprland.conf`. Saving any
of these files reloads Hyprland by itself. API reference: `/usr/share/hypr/stubs/hl.meta.lua`
(every `hl.*` function and option) and https://wiki.hypr.land/Configuring/.
Keep edits inside the fenced `BROMIGOS THEME` / `BROMIGOS LIVE` blocks they belong to, with a
comment line saying what the thing is.

## Add a keybind

1. Find a free key: `hyprctl binds -j` (or the SHORTCUTS panel, SUPER+K).
2. In `bromigos/binds.lua` (or `live.lua` for a live-layer deck), with the helpers:
   ```lua
   K.exec("SUPER + Q", "~/.config/bromigos/bin/some-tool --flag")         -- a command (sh -c; ~ and $HOME expand)
   K.dsp("ALT + P", "hl.dsp.window.pin()")                                 -- a dispatcher, written as Lua source
   K.exec("SUPER + Z", "… scan-hold off", { release = true })              -- on key-up (hold binds: a press + a release)
   ```
   Keys are `"MODS + KEY"` with mods SUPER, ALT (the config's `mainMod`), CTRL, SHIFT; the key
   is a keysym (`E`, `RETURN`, `XF86AudioMute`, `mouse:272`) or `code:N` (evdev code + 8).
   Flags (third argument): `release`, `repeating`, `locked`, `mouse`, `device`, … (see `HL.BindOptions`).
   Use the helpers, not a bare `hl.bind`: they put the action in the bind's description, which is
   how SHORTCUTS, the rofi cheat sheet and `bromigos-docs keys` name and run it.
3. An exec bind SHORTCUTS should name: an `EXEC` row (regex, description, section) in
   bromigOS bromigOS `widgets/keybinds.py`. A new kind of dispatcher bind: a `DISPATCH` row there.
4. `~/.config/bromigos/bin/bromigos-docs keys` regenerates the key table in `AGENTS.md`
   (`--check` says if it's stale).

The Razer macro keys are `code:191`… binds limited to the keyboard with
`{ device = { list = { "razer-blackwidow" } } }` (the tag its `hl.device()` entries set in
`hyprland.lua`): in 0.56 a Lua `code:N` bind also fires for keys with no keysym, so an
unlimited one could go off from a stray key on another keyboard.

## Add a rule, device, env or login program (in `hyprland.lua`)

```lua
hl.window_rule({ match = { class = "^(pavucontrol)$" }, float = true, size = "800 600", center = true })
hl.layer_rule({ match = { namespace = "my-overlay" }, blur = true, ignore_alpha = 0.2 })
hl.workspace_rule({ workspace = "5", monitor = "DP-1" })
hl.device({ name = "some-keyboard", kb_options = "caps:escape" })    -- names: hyprctl devices
hl.env("SOME_VAR", "value")
hl.on("hyprland.start", function() hl.exec_cmd("some-daemon") end)  -- runs once at login, not on reload
hl.config({ general = { gaps_in = 4 } })                              -- any option: see the stubs
```
Window rules match regexes on `class` / `title` (`hyprctl clients` shows them); they are
anonymous and apply top to bottom. Effects that take a size or position are strings (`"25% 40%"`).

## Check it

- Before saving a bigger change: `Hyprland --verify-config -c ~/.config/hypr/hyprland.lua`
  (prints `config ok` or each error with its file and line).
- After saving: `hyprctl configerrors` (empty = fine). A mistake in one bind doesn't stop the
  binds after it; a Lua syntax error stops the reload and Hyprland keeps the last good config.
- `hyprctl binds -j | grep -c __lua` (bind count), the SHORTCUTS panel, `bromigos-docs keys --check`.
- Look around live: `hyprctl repl 'return hl.get_active_window().class'`.

## Dispatchers from scripts and tools

`hyprctl dispatch` takes **Lua** now; the old form is an error:

| Old (`.conf` era) | Now |
|-----|-----|
| `hyprctl dispatch exec kitty` | `hyprctl dispatch 'hl.dsp.exec_cmd("kitty")'` |
| `hyprctl dispatch exec [workspace 3 silent] kitty` | `hyprctl dispatch 'hl.dsp.exec_cmd("kitty", { workspace = "3 silent" })'` |
| `hyprctl dispatch workspace 3` | `hyprctl dispatch 'hl.dsp.focus({ workspace = 3 })'` |
| `hyprctl dispatch focuswindow address:0x…` | `hyprctl dispatch 'hl.dsp.focus({ window = "address:0x…" })'` |
| `hyprctl dispatch closewindow address:0x…` | `hyprctl dispatch 'hl.dsp.window.close({ window = "address:0x…" })'` |
| `hyprctl dispatch movetoworkspacesilent 3,address:0x…` | `hyprctl dispatch 'hl.dsp.window.move({ window = "address:0x…", workspace = 3, follow = false })'` |
| `hyprctl dispatch killactive` / `togglefloating` | `'hl.dsp.window.close()'` / `'hl.dsp.window.float()'` |
| `hyprctl dispatch fullscreen 1` | `'hl.dsp.window.fullscreen({ mode = "maximized" })'` |
| `hyprctl dispatch dpms off` | `'hl.dsp.dpms({ action = "off" })'` |
| `hyprctl dispatch exit` | `'hl.dsp.exit()'` |
| `hyprctl keyword general:gaps_in 8` | `hyprctl eval 'hl.config({ general = { gaps_in = 8 } })'` (until the next reload) |

`hyprctl dispatch` answers `ok` on success. Put any outside text (a command, a title) into
the Lua string safely: escape it (Python: `keybinds._lua_str()`), never paste it raw. Scripts
that must also work on the rollback use `~/.config/bromigos/bin/bromigos-dispatch '<Lua>' <old
form…>` (shell), `hypr.dispatch()` (live layer) or `desk._dispatch()` (VECTOR's desk tools).
`hyprctl` queries (`clients -j`, `activewindow -j`, `monitors -j`, `layers -j`) and the event
socket (`workspacev2>>`, `openwindow>>`, …) are unchanged.

## Rollback

`~/.config/bromigos/bin/bromigos-hyprconfig status | lua | conf`. `conf` unlinks
`hyprland.lua` so the next login loads `hyprland.conf`; it never switches a running Hyprland
back (that crashes 0.56.2) — log out and in. `lua` links the Lua config back, checks it and
switches the running Hyprland. The rollback is the operator's call; tell him rather than
running it.

Lines in `hypr/` that change how VECTOR's own daemon starts (bromigos-holo) are refused by
his guard; those stay Sir's.
