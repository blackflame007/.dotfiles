"""The burn-in: the operator's emblem, drawn to the canonical spec in
platform/agents/LORE.md ("The burn-in (the emblem)").

Geometry in a 1000-unit viewBox (D = 1000):
  outer line   at D        (r 495, 10 thick = 0.01 D)
  inner line   at 0.80 D   (r 400, 10 thick)
  text band    between them: the motto once, clockwise, filling 300 degrees
  tuning gap   the other 60 degrees: 11 ticks, the centre one twice as tall,
               at 12 o'clock at rest
  dark halo    phosphor glow off the inner line, fading TOWARD the flame
  flame        true black with a phosphor-dim hairline, 0.50 D tall, base a
               little below centre, a relay mast cut through it
Below 64 px the text band becomes a dial scale all round ("small" variant).

Parts are exported separately (ring / flame) so anything that animates the
ring (the live layer, the lock screen) can turn it while the flame holds still.
Canon motion: counter-clockwise, one turn per ~24 s.
"""
import json
import math
import os
import re
import xml.sax.saxutils as sx

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # ~/.config/bromigos
BRAND = os.path.join(ROOT, "brand")
IDENTITY = os.path.join(ROOT, "identity.json")

VOID = "#000500"
PHOSPHOR = "#39ff14"
PHOSPHOR_DIM = "#159b09"
BLACK = "#000000"

C = 500.0
R_OUT, R_IN, LINE = 495.0, 400.0, 10.0
R_BAND = (R_OUT + R_IN) / 2                         # 447.5
GAP_DEG = 60.0
FLAME_H, FLAME_TOP = 500.0, 272.0                   # spans 272..772: base a little below centre


def identity():
    try:
        with open(IDENTITY) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


# ------------------------------------------------------------------ flame
def _flame_src():
    with open(os.path.join(BRAND, "flame.svg")) as f:
        s = f.read()
    vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', s).group(1).split()]
    gt = re.search(r'<g transform="([^"]+)"', s).group(1)
    paths = re.findall(r'<path d="([^"]+)"', s)
    return vb, gt, paths


def _flame_transform():
    vb, gt, _ = _flame_src()
    k = FLAME_H / vb[3]
    x = C - vb[2] * k / 2 - vb[0] * k
    y = FLAME_TOP - vb[1] * k
    return f"translate({x:.3f},{y:.3f}) scale({k:.6f}) {gt}", k


def _mast_shapes():
    """Relay mast in emblem units: base to 60% of the flame, 3 bars narrowing upward."""
    base = FLAME_TOP + FLAME_H
    top = base - 0.60 * FLAME_H
    shapes = [(C - 9, top, 18, base - top + 6)]
    for frac, w in ((0.20, 118), (0.36, 86), (0.50, 56)):
        y = base - frac * FLAME_H
        shapes.append((C - w / 2, y - 7, w, 14))
    return shapes


def flame_svg(hairline=3.0):
    """The flame with the mast cut through it (needs the <defs> from flame_defs())."""
    t, k = _flame_transform()
    sw = hairline / (k * 0.1)                       # potrace paths carry scale(0.1,-0.1)
    _, _, paths = _flame_src()
    d = " ".join(paths)
    mast = "".join(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}"/>'
                   for x, y, w, h in _mast_shapes())
    return (f'<g mask="url(#bi-mast)"><path transform="{t}" d="{d}" fill="{BLACK}" '
            f'stroke="{PHOSPHOR_DIM}" stroke-width="{sw:.1f}"/></g>'
            f'<g clip-path="url(#bi-flameclip)" fill="none" stroke="{PHOSPHOR_DIM}" '
            f'stroke-width="{min(hairline * 2, 6):.1f}">{mast}</g>')


def flame_defs():
    t, _ = _flame_transform()
    _, _, paths = _flame_src()
    d = " ".join(paths)
    mast = "".join(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="black"/>'
                   for x, y, w, h in _mast_shapes())
    return (f'<mask id="bi-mast" maskUnits="userSpaceOnUse" x="0" y="0" width="1000" height="1000">'
            f'<rect x="0" y="0" width="1000" height="1000" fill="white"/>{mast}</mask>'
            f'<clipPath id="bi-flameclip"><path transform="{t}" d="{d}"/></clipPath>')


# ------------------------------------------------------------------ ring
def _tick(a_deg, r1, r2, w):
    a = math.radians(a_deg)
    return (f'<line x1="{C + r1 * math.sin(a):.2f}" y1="{C - r1 * math.cos(a):.2f}" '
            f'x2="{C + r2 * math.sin(a):.2f}" y2="{C - r2 * math.cos(a):.2f}" stroke-width="{w}"/>')


def _gap_ticks():
    out = []
    for i in range(11):
        a = -GAP_DEG / 2 + GAP_DEG * (i + 0.5) / 11
        if i == 5:
            out.append(_tick(a, R_BAND - 36, R_BAND + 36, 7))       # centre: twice as tall
        else:
            out.append(_tick(a, R_BAND - 18, R_BAND + 18, 6))
    return f'<g stroke="{PHOSPHOR}" stroke-linecap="butt">' + "".join(out) + "</g>"


def _text_band(text, font):
    chars = list(text.strip())
    n = max(1, len(chars))
    span = 360.0 - GAP_DEG
    out = []
    for i, ch in enumerate(chars):
        if ch == " ":
            continue
        a = GAP_DEG / 2 + span * (i + 0.5) / n
        out.append(f'<text x="{C}" y="{C - R_BAND + 17.5:.1f}" transform="rotate({a:.3f} {C} {C})" '
                   f'text-anchor="middle">{sx.escape(ch)}</text>')
    return (f'<g fill="{PHOSPHOR}" font-family="{font}" font-weight="700" font-size="50">'
            + "".join(out) + "</g>")


def ring_svg(angle=0.0, ident=None):
    """Both lines + text band + tuning gap. angle in degrees (negative = counter-clockwise)."""
    ident = ident or identity()
    lines = (f'<circle cx="{C}" cy="{C}" r="{R_OUT}" fill="none" stroke="{PHOSPHOR}" stroke-width="{LINE}"/>'
             f'<circle cx="{C}" cy="{C}" r="{R_IN}" fill="none" stroke="{PHOSPHOR}" stroke-width="{LINE}"/>')
    band = _text_band(ident.get("ring_text", ""), ident.get("ring_font", "Geist Mono")) + _gap_ticks()
    return f'<g transform="rotate({angle:.3f} {C} {C})">{lines}{band}</g>'


def dial_svg(angle=0.0):
    """Small-size ring (< 64 px): no text, the dial scale all round, heavier strokes."""
    out = [f'<circle cx="{C}" cy="{C}" r="{R_OUT - 15}" fill="none" stroke="{PHOSPHOR}" stroke-width="40"/>',
           f'<circle cx="{C}" cy="{C}" r="{R_IN - 10}" fill="none" stroke="{PHOSPHOR}" stroke-width="34"/>']
    ticks = []
    for i in range(24):
        if i == 0:
            ticks.append(_tick(0, R_IN - 50, R_OUT, 34))       # centre tick, twice as tall
        else:
            ticks.append(_tick(i * 15, R_IN + 16, R_OUT - 38, 20))
    return (f'<g transform="rotate({angle:.3f} {C} {C})">' + "".join(out)
            + f'<g stroke="{PHOSPHOR}">' + "".join(ticks) + "</g></g>")


def halo_svg(strength=0.34, reach=0.52):
    """The dark halo: glow off the inner line that drains toward the flame.
    reach = radius fraction where the glow has fully drained (smaller = closer to the flame)."""
    return (f'<radialGradient id="bi-halo" cx="{C}" cy="{C}" r="{R_IN}" gradientUnits="userSpaceOnUse">'
            f'<stop offset="0" stop-color="{PHOSPHOR}" stop-opacity="0"/>'
            f'<stop offset="{reach}" stop-color="{PHOSPHOR}" stop-opacity="0"/>'
            f'<stop offset="0.85" stop-color="{PHOSPHOR}" stop-opacity="{strength * 0.35:.3f}"/>'
            f'<stop offset="1" stop-color="{PHOSPHOR}" stop-opacity="{strength:.3f}"/></radialGradient>',
            f'<circle cx="{C}" cy="{C}" r="{R_IN}" fill="url(#bi-halo)"/>')


# ------------------------------------------------------------------ documents
def svg(parts=("halo", "ring", "flame"), angle=0.0, background=None, glow=False, size=1000, small=False):
    """A complete SVG document. parts: any of halo, ring, flame. small=True: dial ring, heavier lines."""
    defs = flame_defs()
    body = ""
    if "halo" in parts:
        hd, hb = halo_svg(0.85, 0.18) if small else halo_svg(0.34)
        defs += hd
        body += hb
    ring = (dial_svg(angle) if small else ring_svg(angle)) if "ring" in parts else ""
    if glow and ring:
        defs += ('<filter id="bi-glow" x="-10%" y="-10%" width="120%" height="120%">'
                 '<feGaussianBlur stdDeviation="10"/></filter>')
        body += f'<g filter="url(#bi-glow)" opacity="0.7">{ring}</g>'
    body += ring
    if "flame" in parts:
        body += flame_svg(14.0 if small else 3.0)
    bg = f'<rect x="-60" y="-60" width="1120" height="1120" fill="{background}"/>' if background else ""
    pad = 40 if glow else 0
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
            f'viewBox="{-pad} {-pad} {1000 + 2 * pad} {1000 + 2 * pad}"><defs>{defs}</defs>{bg}{body}</svg>')


def _rsvg(svg_text, size):
    import gi
    gi.require_version("Rsvg", "2.0")
    from gi.repository import Rsvg
    import cairo
    h = Rsvg.Handle.new_from_data(svg_text.encode())
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    cr = cairo.Context(surf)
    vp = Rsvg.Rectangle()
    vp.x, vp.y, vp.width, vp.height = 0, 0, size, size
    h.render_document(cr, vp)
    return surf


def render_png(svg_text, path, size):
    surf = _rsvg(svg_text, size)
    surf.write_to_png(path)
    return surf


def surface(svg_text, size):
    return _rsvg(svg_text, size)
