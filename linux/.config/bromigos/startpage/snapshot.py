#!/usr/bin/env python3
"""Writes data.js next to the start page: a small snapshot of the Lab status,
the SWITCHBOARD links with up/down, and the latest FIELD NOTES lines.

A browser page cannot read local files or send the Lab's bearer token across
origins (the Lab sends no CORS headers), so this runs from a user systemd timer
(bromigos-startpage.timer, every minute) and the page loads the result as a
plain <script>. The token never leaves this machine and never reaches the page.

The switchboard entries are the start page's own list (FIXED_LINKS, FROM_LAB)
(widgets/panels.py, FIXED and FROM_LAB) so both stay in step.
"""
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
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
import bromigos_private as PRIV  # noqa: E402  the operator's private values (empty on a fresh clone)

LAB_URL = PRIV.url("lab", "/api/status")           # private: endpoints.lab
TOKEN_FILE = os.path.expanduser("~/.local/share/bromigos/lab-token")
NOTES = os.path.expanduser("~/.local/share/bromigos/notes.md")
CTX = ssl.create_default_context()


# The page's links. SWITCHBOARD was a widget panel until 2026-10-05 (replaced by
# WORKBENCH); the start page keeps its own list. Fixed links come from the private
# overlay's endpoints (empty on a fresh clone); the rest are read live from the Lab
# snapshot's own service groups by id.
FIXED_LINKS = [("arbiter", "ARBITER", "The Floor: ARBITER console"),
               ("lab", "LAB", "EchoCraft Lab homepage")]
FROM_LAB = [("argocd", "ARGO CD"), ("grafana", "GRAFANA"), ("litellm", "LITELLM"),
            ("openwebui", "OPEN WEBUI"), ("comfyui", "COMFYUI"), ("proxmox", "PROXMOX"),
            ("vault", "VAULT"), ("rustfs", "RUSTFS")]


def switchboard_config():
    """(fixed, from_lab): fixed = [(id, name, role, url)] with URLs from the private overlay."""
    fixed = [(sid, name, role, PRIV.url(sid, "")) for sid, name, role in FIXED_LINKS]
    return [f for f in fixed if f[3]], FROM_LAB


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
    if not LAB_URL:
        return None, "unconfigured"
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
        "lab": {"state": state, "summary": lab_summary(d), "url": PRIV.url("lab"),
                "token_vault": PRIV.vault("lab_api")},
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
