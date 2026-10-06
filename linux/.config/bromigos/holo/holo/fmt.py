"""Reader for the compact hologram format, `bromigos-holo/1` (`*.holo.npz`).

A .holo.npz is a NumPy zip archive (numpy alone reads it) with:

    meta  uint8   UTF-8 JSON header (see below)
    pos   f32[V,3] vertex positions; y up, front +z, base on y = 0, tallest extent 1
    nrm   f16[V,3] vertex normals
    part  u8[V]    part index of each vertex (vertices are split per part, so a part
                   moves as a unit with no tearing at its borders)
    tri   u32[T,3] surface triangles (for the faint fill, depth and picking)
    edge  u32[E,2] feature edges (sharp creases, part borders, open boundaries):
                   the wireframe a hologram draws

meta = {format, name, title, subtitle, source, source_sha1, up, front, height, radius,
        counts, edge_deg, baked,
        parts: [{id, label, bind, hint, centroid[3], extent[3], explode[3], anchor[3],
                 tris, edges}]}

`explode` is the full offset of a part when the model is fully exploded; `anchor` is
the point a callout's leader line attaches to (move it with the part); `bind` names
the live reading the part shows (see holo/bind.py).
"""
import json
import os

import numpy as np

MODEL_DIRS = [os.path.expanduser("~/.config/bromigos/brand/3d/holo")]
if os.environ.get("BROMIGOS_HOLO_MODELS"):          # a build worktree's models first (offscreen checks)
    MODEL_DIRS.insert(0, os.environ["BROMIGOS_HOLO_MODELS"])
ORDER = ["workstation", "wick", "rack", "monolith", "emblem"]


class HoloModel:
    def __init__(self, path):
        with np.load(path) as d:
            self.meta = json.loads(bytes(d["meta"]).decode())
            self.pos = d["pos"].astype(np.float32)
            self.nrm = d["nrm"].astype(np.float32)
            self.part = d["part"].astype(np.uint8)
            self.tri = d["tri"].astype(np.uint32)
            self.edge = d["edge"].astype(np.uint32)
        self.path = path
        self.name = self.meta["name"]
        self.parts = self.meta["parts"]

    def __repr__(self):
        return f"<HoloModel {self.name} {self.meta['counts']}>"


def path_of(name):
    for d in MODEL_DIRS:
        p = os.path.join(d, name + ".holo.npz")
        if os.path.exists(p):
            return p
    raise FileNotFoundError(name)


def available():
    seen = []
    for d in MODEL_DIRS:
        if os.path.isdir(d):
            seen += [f[:-9] for f in sorted(os.listdir(d)) if f.endswith(".holo.npz")]
    return sorted(set(seen), key=lambda n: (ORDER.index(n) if n in ORDER else 99, n))


_cache = {}


def load(name):
    """Cached, but re-read when the file changes (a rebake shows at once)."""
    p = path_of(name)
    m = os.path.getmtime(p)
    if name not in _cache or _cache[name][0] != m:
        _cache[name] = (m, HoloModel(p))
    return _cache[name][1]
