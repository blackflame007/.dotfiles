"""Real data for VECTOR's holograms, each read only while a deck that needs it is open.

  prom(q)            Prometheus instant query (LAN, no auth) ~20-60 ms
  repos()            every git repo under ~/github.com/{bromigos-org,nolgiainc,blackflame007} + ~/.dotfiles
  git_state(r)       branch, dirty files, ahead/behind, commits in 14 days (4 git calls, ~15 ms)
  pushes(rs, since)  pushes seen in the remote-tracking reflogs ("update by push"): stats only
  gh_json(args)      gh CLI, the operator's login (~0.4-1 s a call; keep to a few per poll)
  herdr()            herdr api snapshot: every agent pane with status and cwd (~30 ms)
  ping(host)         one ICMP echo, ms or None (1 s timeout)
"""
import json
import os
import re
import ssl
import shutil
import subprocess
import time
import urllib.parse
import urllib.request

HOME = os.path.expanduser("~")
CA = os.path.join(HOME, ".config/homelab/homelab-ca.crt")
from .config import PRIV  # noqa: E402
PROM = PRIV.url("prometheus")                      # private: endpoints.prometheus
ORGS = ("bromigos-org", "nolgiainc", "blackflame007")
_ctx = None


def ctx():
    global _ctx
    if _ctx is None:
        _ctx = ssl.create_default_context(cafile=CA) if os.path.exists(CA) else ssl.create_default_context()
    return _ctx


def prom(q, timeout=8):
    if not PROM:
        raise OSError("no Prometheus configured (private overlay endpoints.prometheus)")
    url = PROM + "/api/v1/query?" + urllib.parse.urlencode({"query": q})
    with urllib.request.urlopen(url, timeout=timeout, context=ctx()) as r:
        return json.load(r)["data"]["result"]


def prom_range(q, minutes, step=60):
    if not PROM:
        raise OSError("no Prometheus configured (private overlay endpoints.prometheus)")
    now = int(time.time())
    url = PROM + "/api/v1/query_range?" + urllib.parse.urlencode(
        {"query": q, "start": now - minutes * 60, "end": now, "step": step})
    with urllib.request.urlopen(url, timeout=10, context=ctx()) as r:
        return json.load(r)["data"]["result"]


# The daemon starts from Hyprland's exec-once, whose PATH lacks the user's bin dirs
# (herdr lives in ~/.local/bin), so bare command names are resolved against them too.
_USER_BINS = [os.path.expanduser(p) for p in ("~/.local/bin", "~/.cargo/bin")]


def _resolve(cmd):
    if os.sep in cmd:
        return cmd
    path = os.pathsep.join([os.environ.get("PATH", "")] + _USER_BINS)
    return shutil.which(cmd, path=path) or cmd


def run(args, timeout=15, cwd=None):
    args = [_resolve(args[0])] + list(args[1:])
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    return r.stdout if r.returncode == 0 else ""


_repos = {"at": 0, "list": []}


def repos():
    if time.time() - _repos["at"] < 300:
        return _repos["list"]
    out = []
    for org in ORGS:
        base = os.path.join(HOME, "github.com", org)
        try:
            names = sorted(os.listdir(base))
        except OSError:
            continue
        for n in names:
            p = os.path.join(base, n)
            if os.path.isdir(os.path.join(p, ".git")):
                out.append({"name": n, "org": org, "path": p})
    dot = os.path.join(HOME, ".dotfiles")
    if os.path.isdir(os.path.join(dot, ".git")):
        out.append({"name": "dotfiles", "org": "blackflame007", "path": dot})
    for r in out:
        url = run(["git", "-C", r["path"], "config", "--get", "remote.origin.url"], 5).strip()
        m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(\.git)?/?$", url)
        r["slug"] = f"{m.group(1)}/{m.group(2)}" if m else None
    _repos.update(at=time.time(), list=out)
    return out


def git_state(r):
    p = r["path"]
    st = run(["git", "-C", p, "status", "--porcelain=v1", "-b"], 8).splitlines()
    head = st[0] if st else ""
    dirty = len(st) - 1 if st else 0
    ahead = int(m.group(1)) if (m := re.search(r"ahead (\d+)", head)) else 0
    behind = int(m.group(1)) if (m := re.search(r"behind (\d+)", head)) else 0
    branch = head[3:].split("...")[0] if head.startswith("## ") else "?"
    n14 = run(["git", "-C", p, "rev-list", "--count", "--since=14.days", "HEAD"], 8).strip()
    last = run(["git", "-C", p, "log", "-1", "--format=%ct %s"], 5).strip()
    t, _, subj = last.partition(" ")
    return {"branch": branch, "dirty": dirty, "ahead": ahead, "behind": behind,
            "commits14": int(n14 or 0), "last_t": int(t or 0), "last_subject": subj}


def pushes(rs, since):
    """[(time, repo, branch, sha)] from 'update by push' lines in the remote-tracking reflogs."""
    out = []
    for r in rs:
        d = os.path.join(r["path"], ".git", "logs", "refs", "remotes", "origin")
        try:
            files = [os.path.join(d, f) for f in os.listdir(d)]
        except OSError:
            continue
        for f in files:
            try:
                if os.path.getmtime(f) < since or not os.path.isfile(f):
                    continue
                with open(f, errors="replace") as fh:
                    lines = fh.readlines()[-5:]
            except OSError:
                continue
            for ln in lines:
                if "update by push" not in ln:
                    continue
                parts = ln.split()
                m = re.search(r"> (\d+) [+-]\d{4}\t", ln)
                if m and int(m.group(1)) >= since:
                    out.append((int(m.group(1)), r, os.path.basename(f), parts[1]))
    return sorted(out, key=lambda x: x[0])


def gh_json(args, timeout=20):
    out = run(["gh"] + args, timeout)
    return json.loads(out) if out.strip() else None


def check_runs(slug, sha):
    """CI for one commit: every check run, in start order."""
    d = gh_json(["api", f"repos/{slug}/commits/{sha}/check-runs", "--jq",
                 "[.check_runs[] | {name, status, conclusion, started_at, completed_at}]"])
    return sorted(d or [], key=lambda c: c.get("started_at") or "")


def latest_ci(slug):
    d = gh_json(["run", "list", "-R", slug, "-L", "1", "--json", "status,conclusion,workflowName,createdAt,headSha"])
    return (d or [None])[0]


def herdr():
    out = run(["herdr", "api", "snapshot"], 5)
    if not out:
        return []
    snap = (json.loads(out).get("result") or {}).get("snapshot") or {}
    panes = {p.get("pane_id"): p for p in snap.get("panes") or []}
    agents = []
    for a in snap.get("agents") or []:
        a = dict(a)
        a["pane"] = panes.get(a.get("pane_id"), {})
        agents.append(a)
    return agents


def ping(host, timeout=1):
    out = run(["ping", "-n", "-c", "1", "-W", str(timeout), host], timeout + 1)
    m = re.search(r"time=([\d.]+) ms", out)
    return float(m.group(1)) if m else None
