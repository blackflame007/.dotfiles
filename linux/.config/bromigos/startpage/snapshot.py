#!/usr/bin/env python3
"""Writes data.js next to the start page: a small snapshot of the Lab status,
the SWITCHBOARD links with up/down, and the latest FIELD NOTES lines.

A browser page cannot read local files or send the Lab's bearer token across
origins (the Lab sends no CORS headers), so this runs from a user systemd timer
(bromigos-startpage.timer, every minute) and the page loads the result as a
plain <script>. The token never leaves this machine and never reaches the page.

The switchboard entries are read from the widgets' own SwitchboardPanel
(widgets/panels.py, FIXED and FROM_LAB) so both stay in step.
"""
import ast
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.realpath(__file__))
PANELS = os.path.join(HERE, "..", "widgets", "panels.py")
OUT = os.path.join(HERE, "data.js")
LAB_URL = "https://lab.redacted/api/status"
TOKEN_FILE = os.path.expanduser("~/.local/share/bromigos/lab-token")
NOTES = os.path.expanduser("~/.local/share/bromigos/notes.md")
CTX = ssl.create_default_context()


def switchboard_config():
    """FIXED and FROM_LAB from the widgets' SwitchboardPanel, read without importing GTK."""
    with open(PANELS) as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "SwitchboardPanel":
            vals = {}
            for st in node.body:
                if isinstance(st, ast.Assign) and isinstance(st.targets[0], ast.Name):
                    if st.targets[0].id in ("FIXED", "FROM_LAB"):
                        vals[st.targets[0].id] = ast.literal_eval(st.value)
            return vals.get("FIXED", []), vals.get("FROM_LAB", [])
    return [], []


def token():
    t = os.environ.get("BROMIGOS_LAB_TOKEN")
    if t:
        return t
    try:
        with open(TOKEN_FILE) as f:
            return f.read().strip()
    except OSError:
        return None


def lab_status():
    tok = token()
    if not tok:
        return None, "no-token"
    try:
        req = urllib.request.Request(LAB_URL, headers={"Authorization": f"Bearer {tok}"})
        with urllib.request.urlopen(req, timeout=8, context=CTX) as r:
            data = json.load(r)
        age = time.time() - float(data.get("generatedAt") or 0)
        return data, ("stale" if age > 120 else "ok")
    except urllib.error.HTTPError as e:
        return None, ("unauthorized" if e.code in (401, 403) else f"HTTP {e.code}")
    except (OSError, ValueError):
        return None, "down"


def http_alive(url, timeout=4):
    """Any answer below 500 counts as up (the same rule the Lab and the widgets use)."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"),
                                    timeout=timeout, context=CTX) as r:
            return r.status < 500
    except urllib.error.HTTPError as e:
        return e.code < 500
    except OSError:
        return False


def lab_summary(d):
    """Only the numbers the page shows (no addresses, names or series)."""
    if not d:
        return None
    c, a, s = d.get("cluster") or {}, d.get("argocd") or {}, d.get("services") or {}
    g, ai, n = d.get("gpu") or {}, d.get("ai") or {}, d.get("network") or {}
    down = sorted(k for k, v in s.items() if v.get("status") != "up")
    return {
        "generatedAt": d.get("generatedAt"),
        "nodesReady": c.get("nodesReady"), "nodesTotal": c.get("nodesTotal"),
        "podsRunning": c.get("podsRunning"), "podsNotRunning": c.get("podsNotRunning"),
        "alertsFiring": c.get("alertsFiring"), "cpuNow": c.get("cpuNow"),
        "argoHealthy": a.get("healthy"), "argoTotal": a.get("total"),
        "servicesUp": len(s) - len(down), "servicesTotal": len(s), "servicesDown": down,
        "gpuUtil": g.get("utilNow"), "gpuCount": g.get("count"),
        "aiRpm": ai.get("rpmNow"),
        "wanDownBps": n.get("wanDownBps"), "wanUpBps": n.get("wanUpBps"),
    }


def switchboard(d):
    fixed, from_lab = switchboard_config()
    out = [{"id": sid, "name": name, "role": role, "url": url, "up": http_alive(url)}
           for sid, name, role, url in fixed]
    groups = (d or {}).get("config", {}).get("groups", [])
    status = (d or {}).get("services", {})
    for sid, label in from_lab:
        for g in groups:
            for s in g.get("services", []):
                if s.get("id") == sid and s.get("lan"):
                    st = status.get(sid, {}).get("status")
                    out.append({"id": sid, "name": label, "role": s.get("role", ""),
                                "url": s["lan"], "up": None if st is None else st == "up"})
    return out


def notes(limit=8):
    try:
        with open(NOTES) as f:
            lines = [ln.rstrip() for ln in f if ln.strip()]
        return {"lines": lines[-limit:], "count": len(lines), "mtime": os.path.getmtime(NOTES)}
    except OSError:
        return {"lines": [], "count": 0, "mtime": None}


def main():
    d, state = lab_status()
    snap = {
        "at": time.time(),
        "lab": {"state": state, "summary": lab_summary(d)},
        "switchboard": switchboard(d),
        "notes": notes(),
    }
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        f.write("window.BROMIGOS_SNAPSHOT = " + json.dumps(snap, separators=(",", ":")) + ";\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
