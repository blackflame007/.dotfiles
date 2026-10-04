#!/usr/bin/env python3
"""The live keybind list, grouped and described, for the SHORTCUTS panel and rofi.

Source: Hyprland's own bind table (`hyprctl binds -j`), which already resolves
$mainMod and includes every sourced file. If Hyprland can't be asked, the conf
files are parsed instead (hyprland.conf and anything it `source`s).

  keybinds.py            print the grouped list
  keybinds.py rofi       searchable cheat sheet; Enter runs the selected bind
"""
import glob
import json
import os
import re
import subprocess
import sys

MOD = "ALT"                     # $mainMod in hyprland.conf
SECTIONS = ["LAUNCH", "WINDOWS", "WORKSPACES", "BROMIGOS", "MEDIA", "SYSTEM"]

KEYNAMES = {
    "RETURN": "ENTER", "ESCAPE": "ESC", "LEFT": "←", "RIGHT": "→", "UP": "↑", "DOWN": "↓",
    "SLASH": "/", "SPACE": "SPACE", "TAB": "TAB",
    "MOUSE:272": "LMB DRAG", "MOUSE:273": "RMB DRAG",
    "XF86AUDIOMUTE": "MUTE", "XF86AUDIOLOWERVOLUME": "VOL−", "XF86AUDIORAISEVOLUME": "VOL+",
    "XF86AUDIOMICMUTE": "MIC", "XF86MONBRIGHTNESSUP": "BRI+", "XF86MONBRIGHTNESSDOWN": "BRI−",
    "XF86AUDIOPLAY": "PLAY", "XF86AUDIOPREV": "PREV", "XF86AUDIONEXT": "NEXT",
}

# (regex on the exec command, description, section). First match wins.
EXEC = [
    (r"bromigos-live\b.*scan-pin", "Scanner: pin hardware schematic", "BROMIGOS"),
    (r"bromigos-live\b.*scan-hold", "Scanner: hold to scan", "BROMIGOS"),
    (r"bromigos-live\b.*holodeck", "Holo deck", "BROMIGOS"),
    (r"bromigos-live\b.*arbiter", "ARBITER deck (the Floor)", "BROMIGOS"),
    (r"bromigos-live\b.*radial", "Radial menu", "BROMIGOS"),
    (r"bromigos-live\b.*toggle", "Live background on/off", "BROMIGOS"),
    (r"bromigos-live\b.*mute", "Live layer sound on/off", "BROMIGOS"),
    (r"bromigos-live\b.*wallpaper", "Wallpaper", "BROMIGOS"),
    (r"bromigos-widgets toggle all", "All desktop panels", "BROMIGOS"),
    (r"bromigos-widgets toggle (\w+)", lambda m: f"{m.group(1).capitalize()} panel", "BROMIGOS"),
    (r"bromigos-widgets notes", "Type in field notes", "BROMIGOS"),
    (r"keybinds\.py rofi", "Search shortcuts", "BROMIGOS"),
    (r"quick-note", "Quick note", "BROMIGOS"),
    (r"power-menu", "Power menu", "BROMIGOS"),
    (r"lock-session|hyprlock", "Lock", "BROMIGOS"),
    (r"rofi -show drun", "Launcher", "LAUNCH"),
    (r"rofi -show window", "Window switcher", "LAUNCH"),
    (r"rofi -show run", "Run a command", "LAUNCH"),
    (r"^kitty\b|^alacritty\b", "Terminal", "LAUNCH"),
    (r"pcmanfm|dolphin|thunar|nautilus", "Files", "LAUNCH"),
    (r"librewolf", "LibreWolf", "LAUNCH"),
    (r"google-chrome", "Chrome", "LAUNCH"),
    (r"discord", "Discord", "LAUNCH"),
    (r"spotify", "Spotify", "LAUNCH"),
    (r"^obs\b", "OBS", "LAUNCH"),
    (r"^steam\b", "Steam", "LAUNCH"),
    (r"reStream", "reMarkable mirror", "LAUNCH"),
    (r"set-sink-mute", "Mute", "MEDIA"),
    (r"set-sink-volume\S* \S+ -", "Volume down", "MEDIA"),
    (r"set-sink-volume\S* \S+ \+", "Volume up", "MEDIA"),
    (r"set-source-mute", "Mic mute", "MEDIA"),
    (r"brightnessctl.*\+", "Brightness up", "MEDIA"),
    (r"brightnessctl.*-", "Brightness down", "MEDIA"),
    (r"playerctl play-pause", "Play / pause", "MEDIA"),
    (r"playerctl previous", "Previous track", "MEDIA"),
    (r"playerctl next", "Next track", "MEDIA"),
    (r"SIGUSR1 waybar", "Show / hide bar", "SYSTEM"),
    (r"systemctl suspend", "Suspend", "SYSTEM"),
    (r"^grim\b", "Screenshot a region", "SYSTEM"),
    (r"wf-recorder", "Record a region", "SYSTEM"),
]

DISPATCH = {
    ("killactive", ""): ("Close window", "WINDOWS"),
    ("fullscreen", "1"): ("Maximize", "WINDOWS"),
    ("fullscreen", "0"): ("Fullscreen", "WINDOWS"),
    ("togglefloating", ""): ("Float / tile window", "WINDOWS"),
    ("layoutmsg", "swapwithmaster"): ("Swap with master", "WINDOWS"),
    ("layoutmsg", "cyclenext"): ("Next window", "WINDOWS"),
    ("layoutmsg", "cycleprev"): ("Previous window", "WINDOWS"),
    ("mouse", "movewindow"): ("Move window", "WINDOWS"),
    ("mouse", "resizewindow"): ("Resize window", "WINDOWS"),
    ("togglespecialworkspace", ""): ("Scratchpad", "WORKSPACES"),
    ("movetoworkspace", "special"): ("Send window to scratchpad", "WORKSPACES"),
    ("exit", ""): ("Quit Hyprland", "SYSTEM"),
}
DIRS = {"l": "left", "r": "right", "u": "up", "d": "down"}


# ------------------------------------------------------------------ sources
def _hypr_binds():
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not sig:
        try:
            d = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "hypr")
            sig = sorted(os.listdir(d), key=lambda n: os.path.getmtime(os.path.join(d, n)))[-1]
        except (OSError, IndexError):
            return None
    try:
        out = subprocess.run(["/usr/bin/hyprctl", "-i", "0", "binds", "-j"], capture_output=True, text=True,
                             timeout=2, env={**os.environ, "HYPRLAND_INSTANCE_SIGNATURE": sig}).stdout
        raw = json.loads(out)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    binds = []
    for b in raw:
        mm = b.get("modmask", 0)
        mods = [n for bit, n in ((64, "SUPER"), (8, MOD), (4, "CTRL"), (1, "SHIFT")) if mm & bit]
        binds.append((mods, b["key"], b["dispatcher"], b.get("arg", "")))
    return binds


def _conf_binds(path=os.path.expanduser("~/.config/hypr/hyprland.conf"), seen=None):
    seen = seen or set()
    path = os.path.realpath(path)
    if path in seen or not os.path.exists(path):
        return []
    seen.add(path)
    variables, binds = {}, []
    for line in open(path):
        line = line.split("#", 1)[0].strip() if not line.lstrip().startswith("bind") else line.strip()
        m = re.match(r"^\$(\w+)\s*=\s*(.+)$", line)
        if m:
            variables[m.group(1)] = m.group(2).strip()
            continue
        m = re.match(r"^source\s*=\s*(.+)$", line)
        if m:
            for p in glob.glob(os.path.expanduser(m.group(1).strip())):
                binds += _conf_binds(p, seen)
            continue
        m = re.match(r"^(bind[a-z]*)\s*=\s*(.*)$", line)
        if not m:
            continue
        body = re.sub(r"\s+#.*$", "", m.group(2))
        parts = [p.strip() for p in body.split(",", 3)]
        while len(parts) < 4:
            parts.append("")
        mods_s = parts[0]
        for k, v in variables.items():
            mods_s = mods_s.replace("$" + k, "MAINMOD" if k == "mainMod" else v)
        mods = [MOD if t.upper() == "MAINMOD" else t.upper() for t in mods_s.split()]
        disp, arg = (parts[2], parts[3]) if m.group(1) != "bindm" else ("mouse", parts[2])
        binds.append((mods, parts[1], disp, arg))
    return binds


# ------------------------------------------------------------------ describe
def keyname(k):
    u = k.upper()
    return KEYNAMES.get(u, u)


def describe(disp, arg):
    if disp == "exec":
        for pat, desc, sec in EXEC:
            m = re.search(pat, arg)
            if m:
                return (desc(m) if callable(desc) else desc), sec
        return os.path.basename(arg.split()[0]) if arg else "Run", "LAUNCH"
    if (disp, arg) in DISPATCH:
        return DISPATCH[(disp, arg)]
    if disp == "movefocus":
        return f"Focus {DIRS.get(arg, arg)}", "WINDOWS"
    if disp == "movewindow":
        return f"Move window {DIRS.get(arg, arg)}", "WINDOWS"
    if disp == "resizeactive":
        return ("Narrower" if arg.strip().startswith("-") else "Wider"), "WINDOWS"
    if disp.startswith("workspace") or disp.startswith("movetoworkspace") or disp == "focusmonitor":
        return f"{disp} {arg}".strip(), "WORKSPACES"
    return f"{disp} {arg}".strip(), "SYSTEM"


def shortcuts():
    """[(section, keys list, description, (dispatcher, arg) or None)] in display order."""
    binds = _hypr_binds() or _conf_binds()
    by_combo, order = {}, []
    for mods, key, disp, arg in binds:
        combo = (tuple(mods), key.upper())
        if disp == "focusmonitor" and combo in by_combo:
            continue
        if combo not in by_combo:
            order.append(combo)
        if disp == "focusmonitor":               # paired with a workspace bind on the same key
            by_combo.setdefault(combo, (mods, key, disp, arg))
        else:
            by_combo[combo] = (mods, key, disp, arg)
    out, ws_go, ws_move = [], [], []
    for combo in order:
        mods, key, disp, arg = by_combo[combo]
        if key.isdigit() and disp == "workspace":
            ws_go.append((mods, key))
            continue
        if key.isdigit() and disp in ("movetoworkspace", "movetoworkspacesilent"):
            ws_move.append((mods, key))
            continue
        if disp == "focusmonitor":
            continue
        desc, sec = describe(disp, arg)
        out.append((sec, mods + [keyname(key)], desc, (disp, arg) if disp != "mouse" else None))
    for group, desc in ((ws_go, "Go to workspace"), (ws_move, "Move window to workspace")):
        if group:
            keys = [k for _, k in group]
            rng = f"{keys[0]}–{keys[-1]}" if len(keys) > 1 else keys[0]
            out.append(("WORKSPACES", group[0][0] + [rng], desc, None))
    out.sort(key=lambda s: SECTIONS.index(s[0]) if s[0] in SECTIONS else 99)
    return out


def config_mtime():
    paths = glob.glob(os.path.expanduser("~/.config/hypr/*.conf"))
    return max((os.path.getmtime(p) for p in paths), default=0)


# ------------------------------------------------------------------ CLI
def _rofi():
    items = shortcuts()
    lines = [f"{'  '.join(k):<22} {d:<30} {s}" for s, k, d, _ in items]
    theme = ('window { width: 760px; } listview { lines: 14; } '
             'element-text { font: "Geist Mono Medium 12"; }')
    r = subprocess.run(["rofi", "-dmenu", "-i", "-no-custom", "-format", "i", "-p", "",
                        "-mesg", f"{len(items)} SHORTCUTS · ENTER RUNS THE SELECTED ONE",
                        "-theme-str", theme], input="\n".join(lines), capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        return
    _, _, _, action = items[int(r.stdout.strip())]
    if action:
        subprocess.Popen(["/usr/bin/hyprctl", "dispatch", action[0], action[1]],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "rofi":
        _rofi()
    else:
        sec = None
        for s, k, d, _ in shortcuts():
            if s != sec:
                print(f"\n{s}")
                sec = s
            print(f"  {' + '.join(k):<24} {d}")
