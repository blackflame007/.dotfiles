---
name: make-hologram-model
description: How to make a new 3D hologram model for the desktop's gallery (SUPER+O) and holo deck — procedural from primitives first (dish, cylinder, lattice mast, torus …, no credits), or generated on the homelab (image-to-3D, no credits) when it must be organic — with parts, live readings, hover hints and explode directions, baked to .holo.npz and checked with an offscreen render.
when_to_use: "Making a new hologram, 3D model, wireframe model or 3D object for the gallery or holo deck (a satellite dish, a ship, a station, a machine)."
---

# Making a hologram model

The gallery and the holo deck show every `.holo.npz` in the hologram collections: mine
(`linux/.config/bromigos/vector/holo/`, stowed at `~/.config/bromigos/vector/holo/`: the
ARBITER monolith and anything new), bromigos-homelab's (`/usr/share/bromigos/homelab/holo/`:
the rack) and VECTOR's (`/usr/share/bromigos/vector/holo/`: workstation, wick, emblem). The
format and the tools: `/usr/share/bromigos/vector/holo/README.md` and `/usr/lib/bromigos/vector/tools/holo/`.
New models go in mine. A new model is a manifest entry plus a bake; no code changes, and it appears without a restart. Decks and
renderers themselves: `hologram-build.md`.

## From the line (talking to Sir)

You don't build models yourself; the builder does, through the build loop.
- **A real-world object** (a mug, a helmet, a plant, a creature): call `make_hologram`
  with a short `name` and the `subject` (or Sir's `image`). It makes the concept, cutout
  and mesh on the homelab for no credits and returns `build_goal`; call `build_start` with
  that goal and tell Sir it's under way. Never run commands in your terminal for this.
- **A machine or structure from simple shapes** (a dish, a mast, a station): call
  `build_start` with the goal; the builder makes it procedurally (below).

The rest of this skill is the builder's how-to.

## Procedural first (no credits, exact)

Write a spec JSON in the build worktree, then:

```bash
~/.local/share/bromigos/venv/bin/python /usr/lib/bromigos/vector/tools/holo/make-holo.py \
    --root linux/.config/bromigos/vector/holo add satdish /tmp/satdish.json
# -> {"ok", "counts", "parts": [[id, tris, edges]], "preview": "previews/satdish-parts.png", "warnings"}
```

The spec (shapes in `/usr/lib/bromigos/vector/tools/holo/prims.py`; units free, normalised after: base on y = 0,
tallest extent 1, y up, front +z; angles in degrees):

```json
{"title": "SAT DISH", "subtitle": "uplink",
 "parts": [
  {"id": "dish", "label": "DISH", "bind": "ws.net",
   "hint": "The reflector: this machine's network traffic in and out",
   "explode": [0, 0.6, 0.8], "distance": 0.3},
  {"id": "feed", "label": "FEED", "bind": "wick.solar", "hint": "…", "explode": [0, 1, 1], "distance": 0.35},
  {"id": "mount", "label": "MOUNT", "bind": "", "hint": "The pedestal (structure only)",
   "explode": [0, -1, 0], "distance": 0.2, "rest": true}],
 "shapes": [
  {"type": "dish", "part": "dish", "r": 1.0, "depth": 0.32, "at": [0, 1.5, 0], "rotate": [-30, 0, 0]},
  {"type": "tube", "part": "feed", "a": [0, 1.62, 0.2], "b": [0, 2.15, 0.85], "r": 0.025},
  {"type": "sphere", "part": "feed", "r": 0.07, "at": [0, 2.15, 0.85]},
  {"type": "cylinder", "part": "mount", "r": 0.1, "h": 1.3, "at": [0, 0.75, 0]},
  {"type": "frustum", "part": "mount", "r0": 0.55, "r1": 0.3, "h": 0.15}]}
```

Shapes: `box` (size), `cylinder` (r, h, axis), `cone`, `frustum` (r0, r1, h), `sphere`,
`torus` (R, r, axis), `dish` (r, depth, thickness: a paraboloid bowl opening up +y),
`lathe` (profile [[r, y], …] revolved), `tube` (a, b, r: a strut between points),
`lattice` (a, b, w, r, bays: a truss mast). Each takes `part`, `at`, `rotate`
(applied rotate-then-move, about the shape's own origin), `segments`. A rotated shape's
attached parts need their own coordinates computed (rotate the offset yourself).

## Parts are the point

- 3-8 parts, each a meaningful piece. Every part has a `label`, a `hint` (hover text:
  what it is and what its reading means) and a `bind`: a live reading from
  `holo/holo/bind.py` KEYS, or "" for pure structure:
  - this machine: `ws.cpu ws.ram ws.gpu ws.disks ws.fans ws.net ws.power ws.host`;
  - the lab: `rack.nodes rack.switch rack.storage rack.gpu rack.power rack.frame
    wick.racks wick.solar wick.hull wick.wan wick.lan wick.beam wick.vault emb.gap
    emb.ring emb.flame emb.mast` (WAN rates, LAN clients and ISP latency, the relay beam,
    the NAS pool);
  - ARBITER (read only): `arb.referee arb.research arb.positions arb.forward arb.agents
    arb.portfolio`.
  Bind what fits the part (a dish to the WAN, a solar panel to the solar array). The full list is `bind.KEYS`, read from the handlers in `bind.py`.
  make-holo refuses unknown binds and missing hints.
- `explode`: the direction a part leaves when the model is exploded (away from the
  centre), `distance` 0.2-0.45. One part may be `"rest": true`.

## Generated on the homelab (organic shapes; no credits)

1. From the line: `make_hologram name subject` (or Sir's image) makes the concept,
   the cutout and the mesh on the homelab and returns `build_goal`; start the build with
   it. In a build: `homelab_make` (image.generate for the concept: one whole object,
   three-quarter view, plain white background, no text; then image.cutout; then
   model3d.generate with an `out` ending `.glb`), all into the worktree.
2. If the homelab refuses (down, or no model), stop and tell Sir. Never use nolgia for a
   hologram unless Sir asks for nolgia by name.
3. Parts as bbox-fraction boxes (`[x0, x1, y0, y1, z0, z1]`, see `manifest.json`), then
   `make-holo.py --root linux/.config/bromigos/vector/holo glb NAME model.glb parts.json`.

## Check it

`build_validate` renders it offscreen in the gallery with real readings and has the
vision model look. Also read `previews/<name>-parts.png`: each part should be a distinct,
sensible region and the wireframe should read as the object. Budgets: under 30k edges,
under 1 MB. Commit the spec's result (manifest.json, holo/NAME.holo.npz,
previews/NAME-parts.png) through the build loop.
