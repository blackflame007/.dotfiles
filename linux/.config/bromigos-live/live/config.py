"""config.toml loader. Missing keys fall back to DEFAULTS so an old or partial
config never crashes the layer.

The operator's internal URLs aren't in config.toml (the repo is public): empty
cluster.url / arbiter.console / codec.tts_url and radial items with `endpoint = "<name>"`
are filled from the private overlay (~/.config/bromigos/lib/bromigos_private.py,
key endpoints.<name>). On a fresh clone they stay empty and those feeds stay off."""
import copy
import os
import sys
import tomllib

sys.path.insert(0, os.path.expanduser("~/.config/bromigos/lib"))
import bromigos_private as PRIV  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
PATH = os.environ.get("BROMIGOS_LIVE_CONFIG") or os.path.join(os.path.expanduser("~/.config/bromigos-live"), "config.toml")
if not os.path.exists(PATH):
    PATH = os.path.join(HERE, "config.toml")

DEFAULTS = {
    "general": {"monitor": "DP-1", "fps": 30, "fps_covered": 20, "reduced_motion": False},
    "background": {"enabled": True, "underlay": "", "underlay_fallback": "", "underlay_brightness": 1.0,
                   "glow": 0.85, "den": True, "den_plate": "", "den_plates": {}},
    "loops": {"streaks": True, "streak_period": 10, "rows": True, "row_period": 12, "row_amp": 1.0,
              "steam": ["den", "empty", "masked", "v1"], "steam_period": 7, "steam_intensity": 0.55},
    "rain": {"enabled": True, "region": [0, 30, 2390, 600], "brightness": 0.55, "bursts": True},
    "floor": {"enabled": True, "horizon_y": 926, "vanish_x": 690, "lane_slope": 0.98, "lane_offset": 0.71,
              "max_x": 1000, "draw_grid": False},
    "sweep": {"enabled": True, "interval": 60, "duration": 5.5},
    "holodeck": {"enabled": True},
    "space": {"stars": True, "traffic": True, "relay_beam": True, "health_tint": True, "planet": True,
              "station": True},
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


def _private(cfg):
    """Fill the internal URLs from the private overlay (see the module docstring)."""
    cl = cfg["cluster"]
    if not cl.get("url"):
        cl["url"] = PRIV.url("lab", "/api/status")
    ar = cfg["arbiter"]
    if not ar.get("console"):
        ar["console"] = PRIV.url("arbiter")
    if (ar.get("url") or "").startswith("/"):          # a path on the console
        ar["url"] = ar["console"] + ar["url"] if ar["console"] else ""
    co = cfg.setdefault("codec", {})
    if not co.get("tts_url"):
        co["tts_url"] = PRIV.url("tts")
    items = []
    for it in cfg.get("radial", {}).get("items") or []:
        if it.get("endpoint"):
            it = dict(it, url=PRIV.url(it["endpoint"]))
            if not it["url"]:
                continue                                  # not configured on this machine
        items.append(it)
    cfg.setdefault("radial", {})["items"] = items
    return cfg


def load():
    try:
        with open(PATH, "rb") as f:
            return _private(_merge(DEFAULTS, tomllib.load(f)))
    except (OSError, tomllib.TOMLDecodeError) as e:
        print("bromigos-live: config error, using defaults:", e, flush=True)
        return _private(copy.deepcopy(DEFAULTS))
