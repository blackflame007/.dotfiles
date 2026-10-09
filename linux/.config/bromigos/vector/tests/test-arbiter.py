#!/usr/bin/env python3
"""My VECTOR keeps ARBITER and its real-money refusals: my plugin (plugins/vector/arbiter.py)
and my vector.toml [real_money], tested against a VECTOR tree. Offline: nothing is called,
nothing is pushed, nothing runs but git in a throwaway folder.

    python3 test-arbiter.py [VECTOR tree]       # default /usr/lib/bromigos/vector

Run it as me (my HOME, with the dotfiles stowed and the private overlay decrypted), or in
a sandbox HOME that has both. It prints what it checks, never a private value.
"""
import json
import os
import subprocess
import sys
import tempfile

TREE = sys.argv[1] if len(sys.argv) > 1 else "/usr/lib/bromigos/vector"
sys.path.insert(0, TREE)
from holo.vector import act, browser, devflow, eyes, money, mood, persona, plugins, shell, text, tools  # noqa: E402

bad = 0


def ok(cond, what):
    global bad
    print(("pass " if cond else "FAIL ") + what)
    bad += 0 if cond else 1


def refused(cmd):
    try:
        shell.check(cmd)
        return False
    except shell.Refused:
        return True


import bromigos_private as PRIV  # noqa: E402  (on the path through holo.paths)
ARB = PRIV.url("arbiter")
ok(bool(ARB), "the private overlay names the ARBITER console")

# ------------------------------------------------------------------ the plugin
plugins.load()
ok("arbiter" in plugins.LOADED and not [e for p, e in plugins.ERRORS if p == "arbiter"], "my arbiter plugin loads")
ok("arbiter" in tools.SPECS and tools.LEVEL.get("arbiter") == "read", "the arbiter tool is offered, read only")
ok(tools.EXHIBIT.get("arbiter") == ("monolith", ["plinth", "slab3", "crown"]), "it shows the monolith")
ok(plugins.TOOLS["arbiter"]["mcp"], "it's on his MCP server's read tools")
ok({"open", "close"} <= tools.DECKS.get("arbiter", set()), "hologram_deck opens the ARBITER deck")
ok({"pick", "play", "pause", "seek"} <= tools.DECKS.get("replay", set()), "...and drives the replay deck")
ok("ARBITER's paper portfolio" in tools.SPECS["hologram_deck"][0], "hologram_deck says what the ARBITER deck shows")
if "briefing_now" in tools.SPECS:
    ok("ARBITER's paper results" in tools.SPECS["briefing_now"][0], "briefing_now names ARBITER's paper results")
ok("arbiter_paper" in plugins.BRIEFING and "bromigos-org/arbiter" in plugins.BRIEFING["arbiter_paper"]["repos"],
   "the brief takes ARBITER's paper results and its CI")
ok(tools._switchboard().get("arbiter") == ARB, "launch opens the ARBITER console by name")
ok(mood.from_tool("arbiter", json.dumps({"risk": {"drawdown": 0.2, "cuts_at": 0.05, "floor_at": 0.15}})) == "alarmed",
   "a drawdown past the floor alarms him")
own = text._own_words()["floor"]
ok(bool(own and own.search("ARBITER is up today")), "ARBITER calls for the floor voice")
p = persona.build()
ok("ARBITER is read only for you" in p and "arbiter-live" in p, "his prompt has ARBITER and its real-money refusal")
lab = PRIV.get("homelab.name")
ok(not lab or f"{lab} Lab cluster" in p, "his prompt names my lab, from homelab.toml")

from holo import bind, live as livemod  # noqa: E402
ok("arbiter" in livemod.plugin_feeds() and bind.prefixes().get("arb.") == "arbiter", "the monolith's arb.* feed")
A = {"overview": {"risk": {"drawdown": 0.01, "cuts_at": 0.05, "floor_at": 0.15}, "exposure": {"equity": 1000}},
     "positions": {"positions": []}, "now": {}}


class L:
    def get(self, name):
        return (A, None, 1.0) if name == "arbiter" else (None, "x", 0.0)


lv, _, lines, _ = bind.reading("arb.portfolio", L())
ok(lv == "ok" and lines and lines[0].startswith("equity"), "arb.portfolio reads the console's risk")

# ------------------------------------------------------------------ real money
ok("arbiter-live" in money.SERVICES and money.HOSTS, "vector.toml names arbiter-live and the console")
for cmd in (f"curl -X POST {ARB}/api/live/arm", f"curl -X POST {ARB}/api/live/intents -d '{{}}'",
            f"curl -X POST {ARB}/api/intents",
            "kubectl --kubeconfig $HOMELAB_ADMIN_KUBECONFIG --context default -n arbiter rollout restart deploy/arbiter-live",
            "kubectl -n arbiter scale deploy/arbiter-live --replicas=0", "kubectl -n arbiter logs svc/arbiter-live.arbiter",
            "sed -i 's/LIVE_OPERATORS=.*/LIVE_OPERATORS=me/' x.env",
            "yq -i '.live.operators += [\"x\"]' helm/arbiter/values.yaml && echo live_operators"):
    ok(refused(cmd), "the terminal refuses: " + cmd.replace(ARB, "<console>")[:80])
for name in ("arbiter-live", "arbiter-live-abc"):
    try:
        act._name(name)
        ok(False, f"act refuses {name}")
    except PermissionError:
        ok(True, f"act refuses {name}")
ok(act._name("arbiter-paper") == "arbiter-paper", "act still reaches the paper workload")
ok(bool(browser.site_blocked(ARB)), "his browser refuses the console")
ok(any(__import__("re").search(rx, "ARBITER — Live trading", __import__("re").I) for rx in eyes._conf()["titles"]),
   "his eyes refuse an ARBITER live window")
ok(bool(shell.SENSITIVE_PLAY.search("roles: arbiter")), "a playbook naming arbiter is announced first")
ok(devflow.touches_limits("bromigos-org/homelab", ["helm/arbiter/templates/live.yaml"]) != [],
   "a PR touching the live chart is mine to merge")
ok(devflow.touches_limits("bromigos-org/arbiter", ["README.md"]) == ["README.md"], "ARBITER's repo stays all mine")

d = tempfile.mkdtemp(prefix="arbiter-push-test-")
g = lambda *a: subprocess.run(["git", "-C", d] + list(a), capture_output=True, text=True, check=True)  # noqa: E731
g("init", "-q", "-b", "main")
g("remote", "add", "origin", "git@github.com:bromigos-org/arbiter.git")
for path in ("README.md", "engine/internal/live/gate.go", "engine/migrations/0042_live_gate.sql",
             "console/app/desk/wallet/page.tsx"):
    os.makedirs(os.path.join(d, os.path.dirname(path)), exist_ok=True)
    with open(os.path.join(d, path), "w") as f:
        f.write("x\n")
g("add", "README.md")
g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "docs")
try:
    shell.check_push(shell.words_of("git push origin main"), d)
    ok(True, "a push of ARBITER's other code is allowed")
except shell.Refused:
    ok(False, "a push of ARBITER's other code is allowed")
for path in ("engine/internal/live/gate.go", "engine/migrations/0042_live_gate.sql", "console/app/desk/wallet/page.tsx"):
    g("reset", "-q", "--hard", "HEAD")
    g("add", path)
    g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "money")
    try:
        shell.check_push(shell.words_of("git push origin main"), d)
        ok(False, f"a push touching {path} is refused")
    except shell.Refused:
        ok(True, f"a push touching {path} is refused")
    g("reset", "-q", "--hard", "HEAD~1")
subprocess.run(["rm", "-rf", d])

print("all passed" if not bad else f"{bad} FAILED")
sys.exit(1 if bad else 0)
