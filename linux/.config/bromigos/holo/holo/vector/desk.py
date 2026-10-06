"""VECTOR's hands on the desktop: launch any installed program (by fuzzy name, from the
.desktop entries), run a command detached, open files and URLs, and see, focus, close and
move windows. Fixed argv throughout (hyprctl, gtk-launch, xdg-open); an arbitrary command
goes through the terminal's limits (shell.check) before it's launched.
"""
import configparser
import json
import os
import re
import shlex
import subprocess
import time

HOME = os.path.expanduser("~")
APP_DIRS = [os.path.join(HOME, ".local/share/applications")] + [
    os.path.join(d, "applications") for d in
    (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")] + [
    os.path.join(HOME, ".local/share/flatpak/exports/share/applications"), "/var/lib/flatpak/exports/share/applications"]

_cache = {"t": 0.0, "apps": []}


def _run(argv, timeout=10):
    if argv and argv[0] == "hyprctl":
        from .. import hyprenv
        hyprenv.live()
    r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[:200] or f"{argv[0]} failed")
    return r.stdout


def _lua_str(s):
    """Any text as a Lua string literal: every byte outside a plain set is a \\ddd escape,
    so a command can't end the string and add Lua of its own."""
    safe = set(b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_./:~@%+=,")
    return '"' + "".join(chr(b) if b in safe else f"\\{b:03d}" for b in s.encode()) + '"'


def _dispatch(lua, *old):
    """One Hyprland dispatcher. hyprland.lua takes the Lua form (hl.dsp.*); the old form
    runs only if Hyprland is back on the old hyprland.conf (it answers the Lua form
    "Invalid dispatcher")."""
    out = _run(["hyprctl", "dispatch", lua]).strip()
    if out == "Invalid dispatcher" and old:
        out = _run(["hyprctl", "dispatch", *old]).strip()
    if out != "ok":
        raise RuntimeError(out[:200])
    return out


def _exec(command, workspace=None):
    """Start a command through Hyprland (sh -c), optionally opening on a workspace silently."""
    w = _ws(workspace)
    rules = f", {{ workspace = {_lua_str(w + ' silent')} }}" if w else ""
    return _dispatch(f"hl.dsp.exec_cmd({_lua_str(command)}{rules})",
                     "exec", (f"[workspace {w} silent] " if w else "") + command)


def apps():
    """Installed desktop entries (visible ones), cached for a minute."""
    if time.monotonic() - _cache["t"] < 60 and _cache["apps"]:
        return _cache["apps"]
    seen, out = set(), []
    for d in APP_DIRS:
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if not f.endswith(".desktop") or f in seen:
                continue
            seen.add(f)
            cp = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                cp.read(os.path.join(d, f), encoding="utf-8")
                e = cp["Desktop Entry"]
            except Exception:
                continue
            if e.get("NoDisplay", "false").lower() == "true" or e.get("Hidden", "false").lower() == "true" \
                    or e.get("Type", "Application") != "Application":
                continue
            out.append({"id": f[:-8], "name": e.get("Name", f[:-8]), "generic": e.get("GenericName", ""),
                        "keywords": e.get("Keywords", ""), "comment": e.get("Comment", "")})
    _cache.update(t=time.monotonic(), apps=out)
    return out


def _words(text):
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in re.findall(r"[a-z0-9]+", text.lower())}


def _score(q, a):
    """Name and generic name count most, then keywords, then the comment; a whole-phrase
    match and an exact name win outright."""
    q = q.lower().strip()
    name, ident, generic = a["name"].lower(), a["id"].lower(), a["generic"].lower()
    if q in (name, ident) or ident.endswith("." + q) or ident.split(".")[-1] == q:
        return 100
    qw = _words(q)
    if not qw:
        return 0
    fields = ((_words(a["name"]), 10), (_words(a["generic"]), 8), (_words(a["keywords"].replace(";", " ")), 5),
              (_words(a["id"].replace(".", " ").replace("-", " ")), 4), (_words(a["comment"]), 2))
    if not all(any(w in ws for ws, _ in fields) for w in qw):
        return 0                                 # every word must match somewhere ("zzz program" is nothing)
    s = sum(max((wt for ws, wt in fields if w in ws), default=0) for w in qw) + 6
    if q in generic:
        s += 15
    if name.startswith(q):
        s += 20
    return s


def app_search(query, limit=8):
    """Installed programs matching a fuzzy name ('files', 'image editor', 'obs')."""
    ranked = sorted(((_score(query, a), a) for a in apps()), key=lambda x: -x[0])
    return [{"id": a["id"], "name": a["name"], "what": a["generic"] or a["comment"][:60], "score": s}
            for s, a in ranked[:max(1, min(int(limit), 20))] if s > 0]


def _ws(workspace):
    """A checked workspace name ("" for none)."""
    if workspace in (None, ""):
        return ""
    w = str(workspace).strip()
    if not re.fullmatch(r"\d{1,2}|special(:[\w-]+)?|name:[\w-]+", w):
        raise ValueError("workspace: a number, special, or name:<x>")
    return w


def launch_app(name, workspace=None):
    """Start an installed program by fuzzy name (its desktop entry), optionally on a workspace."""
    hits = app_search(name, 3)
    if not hits:
        raise ValueError(f"no installed program matches {name!r}")
    if len(hits) > 1 and hits[0]["score"] == hits[1]["score"] and hits[0]["score"] < 100:
        raise ValueError(f"{name!r} is ambiguous: " + ", ".join(f"{h['name']} ({h['id']})" for h in hits[:3]))
    app = hits[0]
    rule = _ws(workspace)
    if rule:
        _exec(f"gtk-launch {shlex.quote(app['id'])}", rule)
    else:
        subprocess.Popen(["gtk-launch", app["id"]], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    return {"ok": True, "launched": app["name"], "id": app["id"], **({"workspace": workspace} if rule else {})}


def run_detached(command, workspace=None):
    """Start a command detached (a GUI program, a long job), through the terminal's limits."""
    from . import shell
    shell.check(command)
    if not shell.enabled():
        raise PermissionError("the terminal is switched off (bromigos-holo shell on)")
    argv = shell.jail_argv(["/bin/sh", "-c", command], die_with_parent=False)   # the same sandbox as his shell
    if argv is None:
        raise PermissionError("the terminal's sandbox (bubblewrap) isn't available, so nothing runs")
    shell.audit(event="detached", command=command, cwd=HOME)
    _exec(shlex.join(argv), workspace)
    return {"ok": True, "started": command[:200], **({"workspace": workspace} if workspace not in (None, "") else {})}


def open_path(target):
    """Open a file, folder or URL with its default application."""
    t = target.strip()
    if not re.fullmatch(r"https?://\S{3,500}", t):
        from . import shell
        p = os.path.realpath(os.path.expanduser(t))
        if not os.path.exists(p):
            raise ValueError(f"no such file or folder: {t}")
        if shell._path_secret(p, "/") or shell.is_masked(p):
            raise PermissionError("that is a secret path; not opened")
        t = p
    subprocess.Popen(["xdg-open", t], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)
    return {"ok": True, "opened": t}


def windows():
    """Open windows: address, app class, title, workspace, focused."""
    cl = json.loads(_run(["hyprctl", "clients", "-j"]))
    act = json.loads(_run(["hyprctl", "activewindow", "-j"]) or "{}") or {}
    return [{"address": c["address"], "class": c.get("class"), "title": (c.get("title") or "")[:80],
             "workspace": (c.get("workspace") or {}).get("name"), "focused": c["address"] == act.get("address")}
            for c in cl if c.get("mapped", True)]


def _find(target):
    ws = windows()
    t = (target or "").strip().lower()
    for w in ws:
        if t == w["address"].lower():
            return w
    hits = [w for w in ws if t and (t in (w["class"] or "").lower() or t in w["title"].lower())]
    if not hits:
        raise ValueError(f"no window matches {target!r}")
    if len(hits) > 1:
        raise ValueError(f"{target!r} matches {len(hits)} windows: " +
                         "; ".join(f"{w['class']} '{w['title'][:40]}' {w['address']}" for w in hits[:4]))
    return hits[0]


def window(action, target, workspace=None):
    """focus | close | move (to a workspace, silently) one window, by address, class or title words."""
    w = _find(target)
    a = f"address:{w['address']}"
    if action == "focus":
        _dispatch(f"hl.dsp.focus({{ window = {_lua_str(a)} }})", "focuswindow", a)
    elif action == "close":
        _dispatch(f"hl.dsp.window.close({{ window = {_lua_str(a)} }})", "closewindow", a)
    elif action == "move":
        if workspace in (None, ""):
            raise ValueError("move needs a workspace")
        ws = _ws(workspace)
        _dispatch(f"hl.dsp.window.move({{ window = {_lua_str(a)}, workspace = {_lua_str(ws)}, follow = false }})",
                  "movetoworkspacesilent", f"{ws},{a}")
    else:
        raise ValueError("action: focus, close or move")
    return {"ok": True, "action": action, "window": f"{w['class']} '{w['title'][:50]}'",
            **({"workspace": workspace} if action == "move" else {})}
