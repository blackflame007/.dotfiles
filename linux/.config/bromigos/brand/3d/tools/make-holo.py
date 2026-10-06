#!/usr/bin/env python3
"""Add a hologram model and bake it, in one step (run with the build venv):

    ~/.local/share/bromigos/venv/bin/python tools/make-holo.py add NAME spec.json
        spec: {"title", "subtitle", "builder": "prims", "parts": [...], "shapes": [...]}
        (procedural: no credits; see prims.py for the shapes)
    ~/.local/share/bromigos/venv/bin/python tools/make-holo.py glb NAME model.glb parts.json
        a generated mesh (nolgia image-to-3D): parts are bbox-fraction boxes, as in
        manifest.json; the GLB is copied next to the others

Every part needs an id, a LABEL, a "hint" (the hover text: what it is and what it shows)
and a "bind": one of the live readings in ~/.config/bromigos/holo/holo/bind.py KEYS, or
"" for a part that only shapes the model. Parts get "explode": [x, y, z] (direction) and
"distance". The model lands in manifest.json and holo/NAME.holo.npz, with
previews/NAME-parts.png; the gallery (SUPER+O) and the holo deck pick it up by
themselves. Prints a JSON summary (counts, size, parts, preview path, warnings).
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
BIND_KEYS = None


def bind_keys():
    """The reading keys the holo renderer knows (holo/holo/bind.py KEYS), read without importing it."""
    import ast
    p = os.path.join(os.path.dirname(os.path.dirname(ROOT)), "holo", "holo", "bind.py")
    if not os.path.exists(p):
        p = os.path.expanduser("~/.config/bromigos/holo/holo/bind.py")
    tree = ast.parse(open(p).read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "KEYS":
            return {k for v in ast.literal_eval(node.value).values() for k in v}
    return set()


def check(name, spec):
    errs, warns = [], []
    if not name.replace("-", "").replace("_", "").isalnum() or len(name) > 40:
        errs.append("name: letters, digits, - and _ (up to 40)")
    for k in ("title", "parts"):
        if not spec.get(k):
            errs.append(f"spec needs {k}")
    keys = bind_keys()
    ids = set()
    for p in spec.get("parts", []):
        pid = p.get("id")
        if not pid or pid in ids:
            errs.append(f"part id missing or repeated: {pid!r}")
        ids.add(pid)
        if not p.get("label"):
            errs.append(f"part {pid}: needs a label")
        if not (p.get("hint") or "").strip():
            errs.append(f"part {pid}: needs a hint (hover text: what it is, what it shows)")
        b = p.get("bind", "")
        if b and b not in keys:
            errs.append(f"part {pid}: bind {b!r} is not a known reading ({sorted(keys)})")
        if not b:
            warns.append(f"part {pid}: no live reading (shape only)")
        p.setdefault("explode", [0, 1, 0])
        p.setdefault("distance", 0.3)
    if len(spec.get("parts", [])) > 16:
        errs.append("16 parts at most (part ids are one byte, callouts get crowded)")
    if spec.get("builder") == "prims":
        for s in spec.get("shapes", []):
            if s.get("part") not in ids:
                errs.append(f"shape {s.get('type')} names unknown part {s.get('part')!r}")
        if not spec.get("shapes"):
            errs.append("a prims model needs shapes")
    return errs, warns


def main():
    if len(sys.argv) < 4 or sys.argv[1] not in ("add", "glb"):
        sys.exit(__doc__)
    import numpy as np  # noqa: F401
    import bake
    mode, name = sys.argv[1], sys.argv[2]
    if mode == "add":
        spec = json.load(open(sys.argv[3]))
        spec["builder"] = spec.get("builder") or "prims"
        spec.setdefault("edge_deg", 1)          # clean primitives: every ring and meridian is wireframe; flat diagonals are not
        spec.setdefault("max_edges", 12000)
    else:
        glb, parts = sys.argv[3], json.load(open(sys.argv[4]))
        spec = parts if isinstance(parts, dict) else {"parts": parts}
        spec.setdefault("title", name.upper())
        dest = os.path.join(ROOT, f"{name}.glb")
        if os.path.realpath(glb) != os.path.realpath(dest):
            shutil.copy(glb, dest)
        spec["source"] = f"{name}.glb"
        spec.setdefault("faces", 40000)
        spec.setdefault("max_edges", 16000)
    errs, warns = check(name, spec)
    if errs:
        print(json.dumps({"ok": False, "errors": errs}))
        sys.exit(1)
    spec.setdefault("subtitle", "")
    man_path = os.path.join(ROOT, "manifest.json")
    man = json.load(open(man_path))
    man["models"][name] = spec
    try:
        bake.bake(name, spec, True)
    except Exception as e:
        print(json.dumps({"ok": False, "errors": [f"bake failed: {type(e).__name__}: {e}"]}))
        sys.exit(1)
    with open(man_path, "w") as f:
        json.dump(man, f, indent=1)
        f.write("\n")
    import numpy
    d = numpy.load(os.path.join(ROOT, "holo", f"{name}.holo.npz"))
    meta = json.loads(bytes(d["meta"]).decode())
    empty = [p["id"] for p in meta["parts"] if not p.get("tris")]
    if empty:
        warns.append(f"parts with no geometry: {empty}")
    print(json.dumps({"ok": True, "model": name, "file": f"holo/{name}.holo.npz",
                      "kb": os.path.getsize(os.path.join(ROOT, "holo", f"{name}.holo.npz")) // 1024,
                      "counts": meta["counts"], "parts": [(p["id"], p["tris"], p["edges"]) for p in meta["parts"]],
                      "preview": f"previews/{name}-parts.png", "warnings": warns}))


if __name__ == "__main__":
    main()
