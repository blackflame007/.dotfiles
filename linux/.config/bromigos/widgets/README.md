# bromigos-widgets (the operator's layout)

The desktop widgets — SYSTEM, NETWORK, STORAGE, LAB, WORKBENCH, FIELD NOTES, SHORTCUTS
— are bromigOS's now: the `bromigos-widgets` package, from `bromigos-org/bromigOS`
`widgets/` (README there and in `/usr/share/doc/bromigos-widgets/`). Code changes go in
that repo; new keybind `EXEC` rows go in its `widgets/keybinds.py`.

Here:
- `layout.json` — the operator's panels and positions (with LAB and the LAN ping hosts
  from the private overlay); it replaces the packaged default whole.
- `bromigos-widgets` — hands every call to `/usr/bin/bromigos-widgets`.

GAME SERVERS is a plugin in `../plugins/widgets/` (bromigOS `docs/plugins.md`); the old
`plugins/` folder here is still read, for panels VECTOR's build loop writes.
