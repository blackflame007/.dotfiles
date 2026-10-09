# bromigos-live (the operator's settings)

The live layer itself — the background, the worlds' engine, the decks, the intercept,
codec calls, the screensaver, sounds — is bromigOS's now: the `bromigos-live` package,
from `bromigos-org/bromigOS` `live/` (its README and `docs/ELEMENTS.md` are there and
in `/usr/share/doc/bromigos-live/`). Engine changes go in that repo.

Here:
- `config.toml` — the operator's own switchboard, merged key by key over the packaged
  default (`/usr/share/bromigos/live/config.toml`), so it holds only what's mine.
  Animation switches are in `~/.config/bromigos/live/overrides.toml` (`bromigos anim …`).
- `bin/bromigos-live` — hands every call to `/usr/bin/bromigos-live`.
- `layers/` (if any) — shader layers, still read; new ones go in
  `~/.config/bromigos/plugins/live/layers/`.

Personal decks (the ARBITER deck, trade replay, Netmap, Ops, Mind) are plugins in
`../bromigos/plugins/live/` (bromigOS `docs/plugins.md`).
