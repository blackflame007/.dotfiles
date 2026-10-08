"""The burn-in, loaded from the theme's emblem kit (never redrawn here).

emblem-ring.svg   ring: lines, motto band, tuning gap -> rotated in the shader
emblem-flame.svg  halo + flame + mast                   -> holds still
emblem-small.svg  dial-scale ring for icon sizes (< 64 px text is unreadable)

The kit is the current theme's (~/.local/state/bromigos/theme/current/emblem/: a world's
post has its own mark, the Wick's is the burn-in), else the dotfiles' brand/.
"""
import os

import cairo
import gi

gi.require_version("Rsvg", "2.0")
from gi.repository import Rsvg  # noqa: E402

from . import glkit  # noqa: E402

BRAND = os.path.expanduser("~/.config/bromigos/brand")
if not os.path.isdir(BRAND):   # not stowed yet: read the kit straight from the dotfiles
    BRAND = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))),
                         "bromigos", "brand")


CURRENT = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"),
                       "bromigos", "theme", "current", "emblem")


def kit():
    """The emblem kit in force: the current theme's, else the brand kit."""
    return CURRENT if os.path.exists(os.path.join(CURRENT, "emblem-ring.svg")) else BRAND


def _surface(path, size):
    h = Rsvg.Handle.new_from_file(path)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    cr = cairo.Context(surf)
    vp = Rsvg.Rectangle()
    vp.x, vp.y, vp.width, vp.height = 0, 0, size, size
    h.render_document(cr, vp)
    return surf


def _png(path, size):
    src = cairo.ImageSurface.create_from_png(path)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    cr = cairo.Context(surf)
    cr.scale(size / src.get_width(), size / src.get_height())
    cr.set_source_surface(src, 0, 0)
    cr.paint()
    return surf


class Emblem:
    """GL textures for one context: ring (rotating), flame (still), small (icon)."""

    def __init__(self, size=1024, small=128, kit_dir=None):
        k = kit_dir or kit()
        ring = os.path.join(k, "emblem-ring.svg")
        flame = os.path.join(k, "emblem-flame.svg")
        sm = os.path.join(k, "emblem-small.svg")
        self.split = os.path.exists(ring) and os.path.exists(flame)
        if self.split:
            self.ring = glkit.texture_from_cairo(_surface(ring, size), mip=True)
            self.flame = glkit.texture_from_cairo(_surface(flame, size), mip=True)
        else:
            whole = os.path.join(k, "emblem-1024.png")
            self.ring = glkit.texture_from_cairo(_png(whole, size), mip=True)
            self.flame = None
        if os.path.exists(sm):
            self.small = glkit.texture_from_cairo(_surface(sm, small), mip=True)
        else:
            self.small = self.ring
