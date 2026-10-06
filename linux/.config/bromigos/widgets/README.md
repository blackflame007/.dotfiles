# bromigos-widgets — the desktop panels

Seven HUD panels pinned to the desktop, showing this machine and the homelab at a
glance: SYSTEM, NETWORK, STORAGE, LAB, WORKBENCH, FIELD NOTES and SHORTCUTS. They sit
on the BOTTOM layer-shell layer of the monitor in `layout.json`: above the live
background, below every window.

**Status:** active. One GTK3 process (system Python, GtkLayerShell, Cairo/Pango,
psutil), started by Hyprland at login (the `hyprland.start` autostart in `hypr/hyprland.lua`).

## Use

```bash
bromigos-widgets toggle all|system|network|storage|lab|workbench|shortcuts|notes
bromigos-widgets notes        # focus FIELD NOTES for typing (Esc hands focus back)
bromigos-widgets reload       # re-read layout.json
bromigos-widgets stats        # draw counts and coverage, to the app's stderr
```

Keys: SUPER+W all panels, SUPER+S/N/D/C/B/F one each, SUPER+K shortcuts, ALT+N type
in notes (the full table is generated into `AGENTS.md`).

## Files

| File | What |
|------|------|
| `bromigos-widgets` | The app: one layer-shell window per panel, the 100 ms heartbeat, the control socket `$XDG_RUNTIME_DIR/bromigos-widgets.sock` (datagram), hotplug recovery |
| `layout.json` | Panel positions and sizes on the monitor, `visible`, and the latency radar's hosts |
| `panels.py` | The panels; each draws real readings only, with a tooltip on every region |
| `sources.py` | Readers: psutil, NVML, temperatures, wifi signal, ping, storage, the Lab API |
| `draw.py` | Cairo/Pango primitives in the house style (frames, brackets, gauges, bars) |
| `keybinds.py` | Reads the binds for SHORTCUTS and the rofi cheat sheet (`keybinds.py rofi`, Enter runs it): live from Hyprland (the list `hypr/bromigos/keys.lua` keeps, via `hyprctl repl`), else from the Lua config files through `keybinds-dump.lua` (or the old `hyprland.conf` on the rollback); its `EXEC` table names every exec bind. `bromigos-docs keys` uses it to generate the table in `AGENTS.md` |

## Panels

| Panel | Reads | Every |
|-------|-------|-------|
| SYSTEM | CPU per core, memory, GPU (NVML), temperatures, uptime | 2 s |
| NETWORK | Throughput, wifi signal, a latency radar to the hosts in `layout.json` | 1 s |
| STORAGE | Mounts and usage | 30 s |
| LAB | EchoCraft Lab `/api/status` (bearer token in `~/.local/share/bromigos/lab-token`) | 20 s |
| WORKBENCH | Recent git repos by local activity and zoxide's most-used folders; rows open nvim, a terminal or a file manager | 60 s |
| FIELD NOTES | `~/.local/share/bromigos/notes.md`, autosaved | on edit |
| SHORTCUTS | Every bind, from `keybinds.py` | 5 s |

Redraws pause while windows cover the desktop on that monitor; sampling continues
cheaply so graphs have history when you come back.

## Notes

- The WORKBENCH rows open folders in Dolphin (`WorkbenchPanel.FILES`), while ALT+E and
  the operator's choice is PCManFM.
- The start page reads its link list from a `SwitchboardPanel` class that no longer
  exists here, so its switchboard is currently empty (see `../README.md`, "Known issues").
