---
name: make-widget
description: How to build a new desktop widget panel for the Bromigos desktop as a plugin — the Panel API, the draw.py helpers (frame, labels, segment numerals, ring gauges, fuel cells), real data sources, hover regions, placement, budgets, offscreen rendering, and a worked example.
when_to_use: "Making a new desktop widget, panel, gauge, meter or readout on the desktop (the GTK widgets on DP-1, beside SYSTEM, NETWORK, LAB …)."
---

# Making a widget panel

The widgets are one GTK3 process (`linux/.config/bromigos/widgets/bromigos-widgets`), one
layer-shell surface per panel, below windows. A new panel is a **plugin**: one file,
`linux/.config/bromigos/widgets/plugins/<name>.py`. No core file changes. It is picked up
within 2 s, hot-reloaded on every save, isolated (an exception shows as a PLUGIN ERROR
frame and is logged; five in a minute, or slow draws, switch it off), and placed in free
space clear of the other panels and VECTOR's console. See `plugins.py` for the contract.

## The contract

```python
import draw as D          # the house drawing vocabulary (cairo + pango)
import panels as P        # Panel base class
import sources as S       # real readings: S.System(), S.GPU(), S.Net(), S.storage(), S.Lab(...)

LAYOUT = {"width": 300, "height": 210}       # optional: size (and x, y to pin a spot)

class GpuGauge(P.Panel):
    name, title = "gpu_gauge", "GPU"          # title: short, uppercase, shown in the frame
    interval = 1.0                            # seconds between tick() calls

    def __init__(self, cfg=None):
        super().__init__(cfg)
        self.gpu = S.GPU()                    # NVML; .ok False when there is no NVIDIA GPU
        self.r = None

    def tick(self):                           # sample here (cheap; runs even while covered)
        self.r = self.gpu.read()              # {"util", "vram_used", "vram_total", "temp", "watts"} or None

    def draw(self, cr, w, h):                 # draw here; never sample here
        top = D.frame(cr, w, h, self.title, self.gpu.name or "NO GPU")   # returns the content top (44)
        if not self.r:
            D.label(cr, 16, top, "NO READING (NVML UNAVAILABLE)", "static")
            self.region(0, 0, w, h, "No NVIDIA reading: NVML did not answer.")
            return
        t = self.r["temp"]
        D.ring(cr, 70, top + 70, 48, t / 100, width=7, color=D.level(t, 75, 85))
        D.seg7(cr, 42, top + 56, 28, f"{t:2d}", D.level(t, 75, 85))
        self.region(14, top + 14, 112, 112, f"GPU core temperature: {t} °C (amber 75, red 85)")
```

`PANEL = GpuGauge` at the end is allowed (otherwise the first Panel subclass is used).

## draw.py, the only way to draw

| Helper | Draws |
|--------|-------|
| `D.frame(cr, w, h, title, right=None, right_color="static")` | the panel: translucent plate, 1 px rule, targeting brackets, header rule; returns the content top |
| `D.label(cr, x, y, s, color="dim", size=11, align="left")` | small uppercase wide-tracked label |
| `D.text(cr, x, y, s, size=11, color="soft", weight="medium", align="left", glow=False, width=None, wrap=False)` | any text; returns (w, h) |
| `D.seg7(cr, x, y, h, "042", color)` | seven-segment numerals (digits, `-`, `.`, `%`) with ghost segments |
| `D.ring(cr, cx, cy, r, frac, width=6, color="phosphor", dashed=False)` | arc gauge from 12 o'clock, with 24 ticks |
| `D.cells(cr, x, y, w, h, frac, n=24, warn=0.75, crit=0.9)` | segmented fuel-cell bar, cells coloured by threshold |
| `D.bar(cr, x, y, w, h, frac, color)` | a plain bar |
| `D.dot(cr, x, y, r, color, glow=True)`, `D.rule(cr, x1, y, x2)`, `D.brackets(...)` | details |
| `D.level(v, warn, crit)` | "phosphor", "amber" or "danger" for a reading (None -> "static") |
| `D.src(cr, name, alpha)` | set a palette colour for raw cairo drawing |

Colours are **palette tokens only**: `void panel guard phosphor soft dim amber danger rust
static` (`D.PAL`). No hex literals, no other colours.

## Data

Real readings only; when one is missing, say so on the panel. Sources (`sources.py`):

- `S.System()` → `.sample()` then `.total` (CPU %), `.per` (per thread), `.mem`
  (psutil), `.g` (GPU dict), `.temps` (`{"CPU": °C, "NVME": …}`), `.load`, `.cores`.
- `S.GPU()` → `.read()`; `.name`; for anything else NVML has, call it directly:
  `g.lib.nvmlDeviceGetFanSpeed(g.h, ctypes.byref(c_uint))` (fan %, 0-100; this RTX 5070
  has 2 fans: `nvmlDeviceGetNumFans`, `nvmlDeviceGetFanSpeed_v2(g.h, i, byref)`),
  `nvmlDeviceGetClockInfo(g.h, 0, byref)` (graphics MHz). Check the return code (0 = ok).
- `S.Net()` → `.sample()`: rates and history; `S.storage()`: mounts; `S.Lab(every,
  on_update)`: the homelab's `/api/status` (thread).
- More (the lab, ARBITER, Prometheus, git, herdr): `data-sources.md`.

## Rules (checked by the build loop)

- Every element shows real data or does something; no decorative labels.
- **Every** element gets a hover region: `self.region(x, y, w, h, "what it is, what it
  shows (thresholds)", action=None)`; with `action` (a callable) a click does something,
  and the tip says what. The build loop fails a panel with no regions.
- Draw in under 40 ms (aim for 5): sample in `tick()`, never in `draw()`; no network or
  disk I/O in `draw()`. Slow I/O goes in a thread (see `WorkbenchPanel`).
- Size: width 300-470 (the core column is 470); keep text off the brackets (16 px in).
- Original design in the house language (see `desktop-style-guide.md`); no CRT effects.

## Build and check

Inside a build (the build loop does this for you in `build_validate`):

```bash
python3 linux/.config/bromigos/widgets/bromigos-widgets render \
    linux/.config/bromigos/widgets/plugins/gpu_gauge.py /tmp/gauge.png --ticks 3
# -> {"size", "draw_ms", "regions", "regions_without_hint"} and the PNG
```

Look at the PNG (the vision review) before calling it done: text clipped by the frame,
overlapping labels, an empty panel, or a ring with no reading are failures.

Worked examples in the core panels: `panels.py` `SystemPanel` (segment numerals, heat
grid, waterfall, fuel cells), `StoragePanel` (bars), `LabPanel` (rings, status dots,
threaded data), `WorkbenchPanel` (rows with click actions).
