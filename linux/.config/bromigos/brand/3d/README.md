# Bromigos 3D models (holograms)

Five models for the desktop's holograms. Four were generated with nolgia (concept image, then image-to-3D); the burn-in is extruded from the canon vectors, because a generator would garble the motto and the tuning gap, and a ring that misspells the motto is a counterfeit flame. The runtime never reads the GLBs: it reads the compact `holo/*.holo.npz` files baked from them.

| Model | Source | Parts (live reading) |
|-------|--------|----------------------|
| `workstation` | `workstation.glb`, concept `concepts/workstation.jpg` | CPU (load, temp, clock), MEMORY, GPU (util, VRAM, temp, watts), DRIVES (fullest mounts, I/O), EXHAUST (fans), INTAKE (network), PSU (GPU board power, uptime), CHASSIS (host, kernel, load). This machine: Ryzen 7 3700X, X570, RTX 5070, three SSDs |
| `wick` | `wick-station.glb`, concept `concepts/wick-station.jpg` | MAST (the relay beam: lit while every Lab service answers), DISH (WAN), ANTENNAE (LAN clients, ISP latency), SOLAR / SOLAR ARRAY (the house array), RACK ROOM (nodes, pods, alerts), DOCK (NAS pool), HULL (hypervisor) |
| `rack` | `server-rack.glb`, concept `concepts/server-rack.jpg` | SWITCH, NODES, GPU SERVER, STORAGE, POWER, FRAME (Argo CD, alerts): EchoCraft Lab |
| `monolith` | `arbiter-monolith.glb`, concept `concepts/arbiter-monolith.jpg` | REFEREE (cohort, real money: read only), RESEARCH, POSITIONS, FORWARD TESTS, AGENTS, PORTFOLIO (equity, drawdown, cash): ARBITER, read-only GETs |
| `emblem` | `../emblem-ring.svg`, `../emblem-flame.svg` via `tools/emblem.py` | RING (motto), TUNING GAP (services answering), FLAME (beam lit), FIRST RELAY (the mast cut-out: nodes ready) |

`previews/*-parts.png` show each model's part split (front, side, three-quarter). `previews/holo-*.jpg` are renders from the hologram renderer.

## How they were made

1. **Concepts**: nolgia `gpt-image-2.5-flare`, 1:1, 8 credits each. Every prompt ends with the same isolation block: *"Isolated 3D product render on a plain pure white background, whole object fully in frame with margin, three-quarter view from slightly above, soft even studio lighting, no cast shadow, no text, no logos, no people, crisp hard-surface modelling with clear separable parts."* Subjects:
   - workstation: *"A stylized mid-tower desktop workstation PC with the side panel removed so the internals are visible: a tall tower air cooler on the CPU, four RAM sticks, a long triple-fan graphics card, a PSU shroud along the bottom, three large front intake fans behind a mesh front, a small drive cage, a rear exhaust fan. Chunky industrial retro sci-fi design with panel lines and vents, matte graphite and gunmetal."*
   - wick-station: *"A small decommissioned space relay station floating in space, as a free-standing model: a squat cylindrical hub module with a ring of small lit windows around a rack room, a tall lattice antenna mast rising from the top with three crossbars, a parabolic dish on a short arm, several whip antennae, two short folded solar panel wings, docking ring underneath, weathered patched hull plating, worn lived-in space-opera hardware."*
   - server-rack: *"A 42U server rack cabinet with its front door removed: a patch panel and a network switch at the top, three 1U servers, a 4U GPU server with large front fans, a storage server with rows of drive bays, a UPS at the bottom, cable management arms, perforated side panels, sturdy caster base. Clean hard-surface model, dark charcoal steel."*
   - arbiter-monolith: *"A tall obsidian monolith sculpture for a market exchange floor: a slim rectangular obelisk built from stacked segmented slabs separated by thin recessed glowing bands, a narrow vertical slot running up the front, small angular fins at the shoulders, standing on a stepped hexagonal plinth. Brutalist sci-fi, polished black stone and dark metal."*
2. **Image to 3D**: `tools/gen3d.py concept.png out.glb` posts to nolgia `POST /v1/generate/3d` (the CLI has no 3d verb yet) with `hunyuan3d-v3`, untextured (13 credits; a hologram needs only geometry). Each job, asset id and cost is appended to `generations.jsonl`.
3. **Masters**: the raw outputs (500k faces, 9 MB each) are kept off-repo in `~/.local/share/bromigos/3d-raw/` and can be re-downloaded by asset id; the committed GLBs are 100k-face quadric-decimated masters (about 1.8 MB each).
4. **Bake**: `~/.local/share/bromigos/venv/bin/python tools/bake.py --preview` reads `manifest.json` and writes `holo/<name>.holo.npz` plus `previews/<name>-parts.png`.

Credits spent: 32 (four concepts) + 52 (four untextured 3D generations) = **84**.

The build venv is `~/.local/share/bromigos/venv` (trimesh, fast-simplification, shapely, svgpathtools, pillow, numpy). Recreate it with `uv venv ~/.local/share/bromigos/venv --python /usr/bin/python3 && VIRTUAL_ENV=~/.local/share/bromigos/venv uv pip install trimesh numpy scipy fast-simplification shapely svgpathtools manifold3d mapbox-earcut networkx pillow`.

## Parts

Generated meshes come out as one fused shell, so parts are regions. In `manifest.json` each part lists boxes `[x0, x1, y0, y1, z0, z1]` in fractions of the normalised bounding box (y up, front +z). A face goes to the first part whose box holds its centroid, else to the part marked `"rest": true`. `explode` is the direction a part leaves in and `distance` how far; `bind` names its live reading (VECTOR's `holo/bind.py` (bromigos-vector)); `hint` is the hover text. Edit the boxes, rebake, and check `previews/<name>-parts.png`.

## The `.holo` format (`bromigos-holo/1`)

A NumPy `.npz` archive; `numpy.load` is all a reader needs.

| Array | Type | Meaning |
|-------|------|---------|
| `meta` | uint8 | UTF-8 JSON header, below |
| `pos` | float32 [V,3] | vertices; y up, front +z, base on y = 0, tallest extent 1 |
| `nrm` | float16 [V,3] | vertex normals |
| `part` | uint8 [V] | part index per vertex. Vertices are split per part, so moving a part never tears its neighbours |
| `tri` | uint32 [T,3] | surface triangles (faint shell, depth for hidden lines, picking) |
| `edge` | uint32 [E,2] | feature edges: creases sharper than `edge_deg`, part borders, open boundaries. This is the wireframe |

`meta`: `format, name, title, subtitle, source, source_sha1, up, front, height, radius, counts{verts,tris,edges}, edge_deg, baked, parts[]`; each part is `{id, label, bind, hint, centroid[3], extent[3], explode[3], anchor[3], tris, edges}`. `explode` is the part's full offset at 100% exploded; `anchor` is where a callout's leader line attaches (add the same offset). Sizes: 140 to 600 KB per model; 10k to 22k vertices, 19k to 44k triangles, 7k to 23k edges.

```python
import json, numpy as np
d = np.load("wick.holo.npz")
meta = json.loads(bytes(d["meta"]))
pos, part, edge = d["pos"], d["part"], d["edge"]
offset = np.array([p["explode"] for p in meta["parts"]], np.float32)[part] * amount  # explode
lines = (pos + offset)[edge]                                                          # [E, 2, 3] segments
```

The renderer that draws these (VECTOR's `holo/render.py`, `stage.py`: bromigos-vector, `/usr/lib/bromigos/vector`) is documented there; the model gallery is SUPER+O.
