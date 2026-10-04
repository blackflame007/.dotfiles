#!/usr/bin/env python3
"""Waybar GPU readout via NVML (no nvidia-smi fork). Prints one JSON line every 2 s."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.expanduser("~/.config/bromigos/widgets"))
from sources import GPU, human  # noqa: E402

g = GPU()
if not g.ok:
    print(json.dumps({"text": "", "class": "hidden"}), flush=True)
    sys.exit(0)
while True:
    r = g.read()
    cls = "critical" if r["util"] >= 90 or r["temp"] >= 85 else "warning" if r["util"] >= 70 or r["temp"] >= 75 else ""
    print(json.dumps({
        "text": f"{r['util']:>2d}% <span color='#7e927e'>{r['temp']}°</span>",
        "tooltip": (f"{g.name}\nload {r['util']}%  ·  {r['temp']} °C  ·  {r['watts']:.0f} W\n"
                    f"VRAM {human(r['vram_used'])} / {human(r['vram_total'])}\n"
                    "amber: load 70% or 75 °C · red: 90% or 85 °C"),
        "class": cls, "percentage": r["util"]}), flush=True)
    time.sleep(2)
