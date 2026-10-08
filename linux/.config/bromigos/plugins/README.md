# The operator's bromigOS plugins

bromigOS's packaged live layer and widgets (`bromigos-live`, `bromigos-widgets`) read
personal extensions from here (`~/.config/bromigos/plugins/`, stowed from this folder);
the seam is documented in bromigOS's `docs/plugins.md`.

| Folder | What | Here |
|---|---|---|
| `live/` | modules that join the live layer's `live` package; a `<kind>_deck.py` with `DECK` opens as a deck | the ARBITER deck and its client (`arbiter_deck.py`, `arbiter.py`), the trade replay, Netmap, Ops, Mind |
| `live/layers/` | shader layers (`<name>.frag` + `<name>.json`) | none yet (the old `~/.config/bromigos-live/layers/` is still read) |
| `live/decks/` | hot-loaded deck plugins (`<name>.py` with `DECK`) | none yet |
| `widgets/` | widget panels (`panels.Panel` subclasses) | GAME SERVERS (`game_servers.py`) |

These read the homelab through the private overlay (`bromigos_private`) and stay off
without it.
