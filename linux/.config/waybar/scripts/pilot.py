#!/usr/bin/env python3
"""Waybar PILOT pip: what PILOT is doing and how many replies wait unread. Fed by the
bromigos-holo daemon ($XDG_RUNTIME_DIR/bromigos-pilot.json), refreshed on SIGRTMIN+9.
Empty (hidden) when the daemon isn't running."""
import json
import os

path = os.path.join(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"), "bromigos-pilot.json")
try:
    with open(path) as f:
        st = json.load(f)
except (OSError, ValueError):
    print(json.dumps({"text": "", "class": "off"}))
    raise SystemExit
state, unread = st.get("state", "idle"), int(st.get("unread") or 0)
word = {"idle": "PILOT", "thinking": "THINKING", "speaking": "SPEAKING", "listening": "LISTENING",
        "error": "TROUBLE"}.get(state, "PILOT")
text = word + (f" <span color='#d4af37'>{unread}</span>" if unread else "")
tip = {
    "idle": "PILOT is standing by",
    "thinking": "PILOT is working on your question",
    "speaking": "PILOT is answering",
    "listening": "PILOT is listening (mic open while SUPER+V is held)",
    "error": "PILOT hit trouble: open it to see what",
}.get(state, "PILOT")
if unread:
    tip += f"\n{unread} repl{'y' if unread == 1 else 'ies'} waiting"
tip += f"\nmodel: {st.get('model') or '—'}" + ("\nvoice muted" if st.get("muted") else "")
tip += "\nclick: show or minimize PILOT (SUPER+E)"
cls = [state] + (["unread"] if unread else []) + ([] if st.get("shown") else ["minimized"])
print(json.dumps({"text": text, "tooltip": tip, "class": cls}))
