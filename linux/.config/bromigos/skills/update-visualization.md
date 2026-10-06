---
name: update-visualization
description: How to change one of the desktop's existing visualizations (a widget panel, VECTOR's console or hologram, the gallery, a live-layer deck or the background) safely through the build loop — find the code, change the least, keep its data honest, check before and after renders.
when_to_use: "The host asks to change, fix, restyle or extend an existing panel, gauge, hologram, deck, the background or VECTOR's own console."
---

# Changing an existing visualization

## Find it

| What the host sees | Where it lives (dotfiles root) | Render offscreen |
|--------------------|-------------------------------|------------------|
| SYSTEM, NETWORK, STORAGE, LAB, WORKBENCH, SHORTCUTS panels | `linux/.config/bromigos/widgets/panels.py` (+ `draw.py`, `sources.py`) | `widgets/bromigos-widgets render <name> out.png` |
| A widget plugin | `widgets/plugins/<name>.py` | same, with the file path |
| VECTOR's console and construct | `holo/holo/vector/scene.py`, `avatar.py` | `holo/tools/offscreen.py vector out.png` |
| The gallery (SUPER+O), models | `holo/holo/gallery.py`, `stage.py`, `render.py`; models `brand/3d/` | `holo/tools/offscreen.py gallery out.png <model>` |
| Background, decks (SUPER+H, Mind, Ops, …) | `linux/.config/bromigos-live/live/` | `bromigos-live/tools/offscreen.py <kind> out.png` |
| A background shader layer | `bromigos-live/layers/` | `python3 -m live.plugins test-layer` |
| An element of the live wallpaper (meters, scope, relay beam, rain, …) | `bromigos-live/docs/ELEMENTS.md` names its code, uniforms and config key | `bromigos-live/tools/offscreen.py bg out.png 3` |

Ask `knowledge_search` (space desktop) when unsure; the desktop map is
`linux/.config/bromigos/README.md`.

## Change it

1. `build_begin`, then render it **before** you change anything, and look (so you can
   compare).
2. Read the code around what you change; reuse its helpers and patterns.
3. Change the least that does the job. Keep every reading real; keep or add the hover
   regions; palette tokens only.
4. `build_validate` (it renders the changed widget, layer or model and looks); for a core
   file it doesn't render, run the offscreen renderer yourself with `build_run` and
   `look` at the PNG. Compare with the before render.
5. `build_apply` with a clear message ("Updated: the NETWORK panel's latency radar shows
   jitter").

Core files are restarted for the trial (widgets reload, the live layer restarts, a change
to VECTOR's own console restarts him: say so in `say`). The trial watcher rolls back if a
host crashes, errors repeat, or nobody keeps it in 10 minutes.

## Worked example: the den's left meter shows RAM instead of CPU

1. Look it up: `docs_read linux/.config/bromigos-live/docs/ELEMENTS.md` ("Meters"):
   the left meter is `meter0`, fed by `cpu` in `Background.render()` (`live/scene.py`);
   memory is already in the snapshot as `mem` (percent, psutil, every 1 s).
2. `build_begin`; render before: `tools/offscreen.py bg /tmp/before.png 3`, `look` at the
   desk crop.
3. The change is one word in `live/scene.py`:
   `for i, k in enumerate(("cpu", "gpu"))` becomes `for i, k in enumerate(("mem", "gpu"))`.
   The needle, easing and shader stay as they are.
4. Update the "Meters" row and section of `docs/ELEMENTS.md` (left = memory in use).
5. Render after, compare, `build_apply` "Updated: the den's left meter shows memory
   instead of CPU". The trial restarts the live layer.

The answer to "what does X on my wallpaper mean?" is the element's "Shows" line in
`docs/ELEMENTS.md`, said plainly with its current state if you can read it (for the
relay beam: whether the lab is all green right now).

You can't change VECTOR's safety code (the terminal's limits, tools, the brain's wiring,
the build loop, the plugin isolation); the build loop refuses it.
