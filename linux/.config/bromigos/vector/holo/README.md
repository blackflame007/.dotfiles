# My hologram models

My own hologram collection: VECTOR's gallery (SUPER+O) and holo deck read it first, then
bromigos-homelab's (`/usr/share/bromigos/homelab/holo/`: the rack) and VECTOR's own
(`/usr/share/bromigos/vector/holo/`: workstation, wick, emblem). Stowed at
`~/.config/bromigos/vector/holo/`.

| Model | Source | Parts (live reading) |
|-------|--------|----------------------|
| `monolith` | `src/arbiter-monolith.glb`, concept `concepts/arbiter-monolith.jpg` | REFEREE (cohort, real money: read only), RESEARCH, POSITIONS, FORWARD TESTS, AGENTS, PORTFOLIO (equity, drawdown, cash): ARBITER, read-only GETs |

`concepts/contact.jpg` is the contact sheet of the four original concepts (2026-10-04).

The format, how the models were made and the build venv: `/usr/share/bromigos/vector/holo/README.md`.
New models land here: VECTOR's `make-hologram-model` skill, or by hand with
`~/.local/share/bromigos/venv/bin/python /usr/lib/bromigos/vector/tools/holo/make-holo.py --root ~/.config/bromigos/vector/holo add NAME spec.json`.
Rebake: `.../tools/holo/bake.py --root ~/.config/bromigos/vector/holo --preview monolith`.
