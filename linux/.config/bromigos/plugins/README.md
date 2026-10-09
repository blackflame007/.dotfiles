# The operator's bromigOS plugins

bromigOS's packaged live layer, widgets and VECTOR (`bromigos-live`, `bromigos-widgets`,
`bromigos-vector`) read personal extensions from here (`~/.config/bromigos/plugins/`, stowed from this folder);
the seam is documented in bromigOS's `docs/plugins.md`.

| Folder | What | Here |
|---|---|---|
| `live/` | modules that join the live layer's `live` package; a `<kind>_deck.py` with `DECK` opens as a deck | the ARBITER deck and its client (`arbiter_deck.py`, `arbiter.py`), the trade replay |
| `live/layers/` | shader layers (`<name>.frag` + `<name>.json`) | none yet (the old `~/.config/bromigos-live/layers/` is still read) |
| `live/decks/` | hot-loaded deck plugins (`<name>.py` with `DECK`) | none yet |
| `widgets/` | widget panels (`panels.Panel` subclasses) | GAME SERVERS (`game_servers.py`) |
| `vector/` | VECTOR's tools, memory stores, skills and whole systems of mine (`register(vector)`; the seam is bromigos-vector's `docs/plugins.md`). Protected: he can't write them, and his guard logs any change | ARBITER (`arbiter.py`): its read tool, the monolith's feed, the ARBITER and replay decks, the brief's paper results, his prompt's lines. Its real money is named in `../vector/vector.toml` `[real_money]`, where his limits read it; my tests are `../vector/tests/test-arbiter.py`, my evals `../vector/evals/` |

These read the homelab through the private overlay (`bromigos_private`) and stay off
without it. Netmap, Ops, Mind, LAB and his Gnosis memory came with bromigos-homelab
(bromigOS docs/homelab.md), configured by `../homelab.toml`; `homelab/` here would hold
homelab adapters of his own (none yet).
