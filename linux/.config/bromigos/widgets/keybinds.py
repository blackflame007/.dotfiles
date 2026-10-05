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
# Display order. The Bromigos pieces come first, grouped by what they're for; the
# stock window-manager binds follow. Within a section, rows follow the order of the
# EXEC / DISPATCH tables below (not the order in hyprland.conf).
SECTIONS = ["VECTOR", "HOLOGRAMS", "PANELS + NOTES", "LIVE LAYER",
            "LAUNCH", "CAPTURE", "WINDOWS", "WORKSPACES", "MEDIA", "SYSTEM"]
BROMIGOS = SECTIONS[:4]
# Sections whose rows can be clicked to run (the panel) — hold-to-use binds never are.
RUNNABLE = BROMIGOS + ["LAUNCH", "CAPTURE"]

KEYNAMES = {
    "RETURN": "ENTER", "ESCAPE": "ESC", "LEFT": "←", "RIGHT": "→", "UP": "↑", "DOWN": "↓",
    "SLASH": "/", "SPACE": "SPACE", "TAB": "TAB",
    "MOUSE:272": "LMB DRAG", "MOUSE:273": "RMB DRAG",
    "XF86AUDIOMUTE": "MUTE", "XF86AUDIOLOWERVOLUME": "VOL−", "XF86AUDIORAISEVOLUME": "VOL+",
    "XF86AUDIOMICMUTE": "MIC", "XF86MONBRIGHTNESSUP": "BRI+", "XF86MONBRIGHTNESSDOWN": "BRI−",
    "XF86AUDIOPLAY": "PLAY", "XF86AUDIOPREV": "PREV", "XF86AUDIONEXT": "NEXT",
    # Razer BlackWidow V4 Pro macro keys (openrazer driver mode)
    "F13": "M1", "F14": "M2", "F15": "M3", "F16": "M4", "F17": "M5",
    "F18": "SIDE 1", "F19": "SIDE 2", "F20": "SIDE 3", "F24": "DIAL PRESS",
    "CODE:191": "M1", "CODE:192": "M2", "CODE:193": "M3", "CODE:194": "M4", "CODE:195": "M5",
    "CODE:196": "SIDE 1", "CODE:197": "SIDE 2", "CODE:198": "SIDE 3", "CODE:202": "DIAL PRESS",
}

# (regex on the exec command, description, section). First match wins; the list
# order is also the row order inside each section.
EXEC = [
    # VECTOR: the caretaker on the line, and his voice
    (r"bromigos-holo\b.*\b(vector|pilot)\b", "VECTOR: show / minimize", "VECTOR"),
    (r"bromigos-holo\b.*\bconversation\b", "VECTOR: conversation mode on/off (hands-free)", "VECTOR"),
    (r"bromigos-holo\b.*\bptt\b", "VECTOR: hold to talk", "VECTOR"),
    (r"bromigos-holo\b.*\bmute\b", "VECTOR: voice on/off", "VECTOR"),
    # HOLOGRAMS: the full-screen decks and 3D views
    (r"bromigos-live\b.*holodeck", "Holo deck (this machine)", "HOLOGRAMS"),
    (r"bromigos-holo\b.*\bgallery\b", "3D model gallery", "HOLOGRAMS"),
    (r"bromigos-live\b.*arbiter", "ARBITER deck (the Floor)", "HOLOGRAMS"),
    (r"bromigos-live\b.*timeline", "Timeline (scrub the last 72 h)", "HOLOGRAMS"),
    (r"bromigos-live\b.*driftmap", "Drift map (lore star chart)", "HOLOGRAMS"),
    (r"bromigos-live\b.*radial", "Radial quick-launch", "HOLOGRAMS"),
    # PANELS + NOTES: the desktop widgets
    (r"bromigos-widgets toggle all", "All desktop panels", "PANELS + NOTES"),
    (r"bromigos-widgets toggle shortcuts", "This shortcuts panel", "PANELS + NOTES"),
    (r"keybinds\.py rofi", "Search shortcuts (Enter runs)", "PANELS + NOTES"),
    (r"bromigos-widgets toggle (\w+)", lambda m: f"{m.group(1).capitalize()} panel", "PANELS + NOTES"),
    (r"bromigos-widgets notes", "Type in field notes", "PANELS + NOTES"),
    (r"quick-note", "Quick note from anywhere", "PANELS + NOTES"),
    # LIVE LAYER: the animated background
    (r"bromigos-live\b.*scan-pin", "Scanner: pin hardware schematic", "LIVE LAYER"),
    (r"bromigos-live\b.*scan-hold", "Scanner: hold to scan", "LIVE LAYER"),
    (r"bromigos-live\b.*codec-quiet", "Codec calls: voice on/off", "LIVE LAYER"),
    (r"bromigos-live\b.*mute", "Live layer sounds on/off", "LIVE LAYER"),
    (r"bromigos-live\b.*toggle", "Live background on/off", "LIVE LAYER"),
    (r"bromigos-live\b.*wallpaper", "Wallpaper", "LIVE LAYER"),
    # LAUNCH
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
    # CAPTURE
    (r"bromigos-shot\b.*region|^grim\b", "Screenshot a region", "CAPTURE"),
    (r"bromigos-shot\b.*screen", "Screenshot the screen", "CAPTURE"),
    (r"bromigos-rec\b|wf-recorder", "Record a region (again to stop)", "CAPTURE"),
    # MEDIA
    (r"set-sink-mute", "Mute", "MEDIA"),
    (r"set-sink-volume\S* \S+ -", "Volume down", "MEDIA"),
    (r"set-sink-volume\S* \S+ \+", "Volume up", "MEDIA"),
    (r"set-source-mute", "Mic mute", "MEDIA"),
    (r"brightnessctl.*\+", "Brightness up", "MEDIA"),
    (r"brightnessctl.*-", "Brightness down", "MEDIA"),
    (r"playerctl play-pause", "Play / pause", "MEDIA"),
    (r"playerctl previous", "Previous track", "MEDIA"),
    (r"playerctl next", "Next track", "MEDIA"),
    # SYSTEM
    (r"lock-session|hyprlock", "Lock", "SYSTEM"),
    (r"power-menu", "Power menu", "SYSTEM"),
    (r"systemctl suspend", "Suspend", "SYSTEM"),
    (r"SIGUSR1 waybar", "Show / hide bar", "SYSTEM"),
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
# Inputs handled outside Hyprland's bind table (so `hyprctl binds` can't list them):
# (section, keys, description, rank). The dial is read by bromigos-knob.
EXTRA = [("VECTOR", ["DIAL TURN"], "VECTOR: cycle voices (auto, Voss, Sigil, Arc, Lynx, Lin Yao)", 2.5)]
_DRANK = {k: len(EXEC) + i for i, k in enumerate(DISPATCH)}


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
        if b.get("release"):                   # the key-up half of a hold bind
            continue
        key = b["key"] or (f"code:{b['keycode']}" if b.get("keycode") else "")   # keycode binds (code:N)
        binds.append((mods, key, b["dispatcher"], b.get("arg", "")))
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
        if m.group(1).startswith("bindr"):      # the key-up half of a hold bind
            continue
        disp, arg = (parts[2], parts[3]) if m.group(1) != "bindm" else ("mouse", parts[2])
        binds.append((mods, parts[1], disp, arg))
    return binds


# ------------------------------------------------------------------ describe
def keyname(k):
    u = k.upper()
    return KEYNAMES.get(u, u)


def describe(disp, arg):
    """(description, section, rank) — rank orders rows inside a section."""
    if disp == "exec":
        for i, (pat, desc, sec) in enumerate(EXEC):
            m = re.search(pat, arg)
            if m:
                return (desc(m) if callable(desc) else desc), sec, i
        return (os.path.basename(arg.split()[0]) if arg else "Run"), "LAUNCH", 999
    if (disp, arg) in DISPATCH:
        return DISPATCH[(disp, arg)] + (_DRANK[(disp, arg)],)
    n = len(EXEC) + len(DISPATCH)
    if disp == "movefocus":
        return f"Focus {DIRS.get(arg, arg)}", "WINDOWS", n
    if disp == "movewindow":
        return f"Move window {DIRS.get(arg, arg)}", "WINDOWS", n + 1
    if disp == "resizeactive":
        return ("Narrower" if arg.strip().startswith("-") else "Wider"), "WINDOWS", n + 2
    if disp.startswith("workspace") or disp.startswith("movetoworkspace") or disp == "focusmonitor":
        return f"{disp} {arg}".strip(), "WORKSPACES", n + 3
    return f"{disp} {arg}".strip(), "SYSTEM", n + 4


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
        desc, sec, rank = describe(disp, arg)
        hold = "hold" in desc                   # press-and-hold binds can't be run from a click
        out.append((sec, mods + [keyname(key)], desc, None if disp == "mouse" or hold else (disp, arg), rank))
    for group, desc in ((ws_go, "Go to workspace"), (ws_move, "Move window to workspace")):
        if group:
            keys = [k for _, k in group]
            rng = f"{keys[0]}–{keys[-1]}" if len(keys) > 1 else keys[0]
            out.append(("WORKSPACES", group[0][0] + [rng], desc, None, 10_000))
    for sec, keys, desc, rank in EXTRA:
        if os.path.exists(os.path.expanduser("~/.config/systemd/user/bromigos-knob.service")):
            out.append((sec, keys, desc, None, rank))
    out.sort(key=lambda s: (SECTIONS.index(s[0]) if s[0] in SECTIONS else 99, s[4]))   # stable: ties keep conf order
    merged, seen = [], {}
    for sec, keys, desc, action, _ in out:     # two binds, one job (ALT+C and ALT+SHIFT+C both close)
        if (sec, desc) in seen:
            i = seen[(sec, desc)]
            s0, k0, d0, a0 = merged[i]
            # keycaps show the keyboard chord; the Razer macro key goes in "(also …)"
            if _macro(k0) and not _macro(keys):
                k0, keys = keys, k0
            elif _macro(k0) == _macro(keys) and len(keys) < len(k0):
                k0, keys = keys, k0
            merged[i] = (s0, k0, f"{d0} (also {'+'.join(keys)})", a0)
            continue
        seen[(sec, desc)] = len(merged)
        merged.append((sec, keys, desc, action))
    return merged


def _macro(keys):
    return any(k.startswith(("M", "SIDE", "DIAL")) and k in KEYNAMES.values() for k in keys)


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
