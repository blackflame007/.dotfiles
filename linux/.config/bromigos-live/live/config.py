"""config.toml loader. Missing keys fall back to DEFAULTS so an old or partial
config never crashes the layer."""
import copy
import os
import tomllib

HERE = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
PATH = os.path.join(os.path.expanduser("~/.config/bromigos-live"), "config.toml")
if not os.path.exists(PATH):
    PATH = os.path.join(HERE, "config.toml")

DEFAULTS = {
    "general": {"monitor": "DP-1", "fps": 30, "fps_covered": 10, "reduced_motion": False},
    "background": {"enabled": True, "underlay": "", "underlay_brightness": 1.0, "glow": 0.85, "den": True},
    "rain": {"enabled": True, "region": [0, 30, 2390, 600], "brightness": 0.55, "bursts": True},
    "floor": {"enabled": True, "horizon_y": 926, "vanish_x": 690, "lane_slope": 0.98, "lane_offset": 0.71,
              "max_x": 1000, "draw_grid": False},
    "sweep": {"enabled": True, "period": 24, "duration": 5.5},
    "holodeck": {"enabled": True},
    "cluster": {"url": "", "token_file": "", "ca_file": "", "poll_seconds": 25},
    "arbiter": {"url": "", "poll_seconds": 30},
    "events": {"intercept_on_login": True, "intercept_on_unlock": True, "critical_flash": True,
               "workspace_wipe": True},
    "screensaver": {"enabled": True},
    "sounds": {"enabled": True, "volume": 0.3, "terminal_classes": ["kitty", "Alacritty"]},
    "radial": {"items": []},
}


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load():
    try:
        with open(PATH, "rb") as f:
            return _merge(DEFAULTS, tomllib.load(f))
    except (OSError, tomllib.TOMLDecodeError) as e:
        print("bromigos-live: config error, using defaults:", e, flush=True)
        return copy.deepcopy(DEFAULTS)
