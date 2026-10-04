"""PILOT's tools. Read-only by construction, a few safe desktop actions, nothing else.

Hard limits (enforced here, not by the prompt):
  * no shell: every subprocess is a fixed argv from an allowlist, never a shell string;
  * the cluster through the `pilot-readonly` ServiceAccount kubeconfig only (get/list/
    watch, no secrets/configmaps/exec); verbs used: get, logs, top;
  * Prometheus: GET /api/v1/query and query_range only;
  * GitHub: `gh` read subcommands only, repos under bromigos-org;
  * ARBITER: a fixed table of console GET paths (no trading, no arming, no live/*);
  * Gnosis: POST /v1/memories/search only, two spaces;
  * files: read under the docs roots only (markdown/json/yaml/txt), never secret-looking
    names; the one write is appending to FIELD NOTES;
  * actions: launch an allowlisted app or an http(s) URL, toggle a widget panel, switch
    the den wallpaper, run a scanner pass, show a hologram.
Every call is appended to ~/.local/state/bromigos/pilot-audit.log (tool, args, ok, ms).
"""
import calendar
import datetime as dt
import fnmatch
import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request

from ..live import get_json, ssl_ctx

HOME = os.path.expanduser("~")
STATE = os.path.join(HOME, ".local/state/bromigos")
AUDIT = os.path.join(STATE, "pilot-audit.log")
KUBECONFIG = os.path.join(HOME, ".local/share/bromigos/pilot-kubeconfig")
GNOSIS_TOKEN = os.path.join(HOME, ".local/share/bromigos/gnosis-read-token")
NOTES = os.path.join(HOME, ".local/share/bromigos/notes.md")
PROM = "https://prometheus.redacted"
GNOSIS = "https://gnosis.redacted"
ARBITER = "https://arbiter.redacted"
LAB = "https://lab.redacted/api/status"
WIDGETS = os.path.join(HOME, ".config/bromigos/widgets/bromigos-widgets")
WALLPAPER = os.path.join(HOME, ".config/bromigos/bin/bromigos-wallpaper")
LIVE = os.path.join(HOME, ".config/bromigos-live/bin/bromigos-live")
ORG = "bromigos-org"
DOC_ROOTS = [os.path.join(HOME, "github.com/bromigos-org"), os.path.join(HOME, ".dotfiles")]
DOC_EXT = (".md", ".json", ".yaml", ".yml", ".txt", ".toml")
SECRETISH = re.compile(r"(secret|token|credential|password|passwd|\.env|private|\.key$|\.pem$|kubeconfig|vault|zsh-secrets)", re.I)
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", "target", "private"}

APPS = {  # name -> argv (the desktop's own launch commands, from the Hyprland binds)
    "terminal": ["kitty"], "kitty": ["kitty"], "browser": ["librewolf"], "librewolf": ["librewolf"],
    "chrome": ["google-chrome-stable"], "files": ["pcmanfm"], "discord": ["discord"],
    "spotify": ["spotify-launcher"], "obs": ["obs"], "steam": ["steam"],
}
ARBITER_VIEWS = {  # name -> (path, what it is)
    "now": ("/api/overview/now", "agents, cohort, research at a glance"),
    "overview": ("/api/overview", "risk, exposure, costs, benchmark, regime"),
    "performance": ("/api/performance?tf=24h", "paper P&L horizons"),
    "positions": ("/api/positions", "open paper positions and forward tests"),
    "trades": ("/api/trades?limit=15", "recent paper fills"),
    "lineup": ("/api/lineup", "the main portfolio's lineup"),
    "referee": ("/api/agents/referee", "the referee's view"),
    "agent_events": ("/api/agents/events", "recent agent events"),
    "road": ("/api/road/track", "the road to real money: stages and gates"),
    "realmoney": ("/api/realmoney", "real-money candidates and gate (read only)"),
    "research_activity": ("/api/research/activity", "research schedule and jobs"),
    "research_smarter": ("/api/research/smarter", "research funnel and readiness"),
    "research_library": ("/api/research/library", "studies, candidates, verdicts"),
    "hypotheses": ("/api/hypotheses", "hypothesis families and counts"),
    "predictions": ("/api/predictions", "prediction-market quotes"),
    "predictions_games": ("/api/predictions/games", "games, settled calls, accuracy"),
    "risk_limits": ("/api/portfolio/limits", "risk limits and what binds"),
    "underwater": ("/api/portfolio/underwater", "drawdown curve and throttle"),
    "causes": ("/api/causes", "what moved the book and why"),
    "health": ("/api/health", "console components"),
}
K8S_KINDS = {"pods", "deployments", "statefulsets", "daemonsets", "jobs", "cronjobs", "nodes", "services",
             "ingresses", "ingressroutes", "applications", "namespaces", "replicasets", "events"}
GH_ACTIONS = {
    "repos": lambda repo, n: ["repo", "list", ORG, "--limit", str(n), "--json", "name,description,pushedAt,isArchived"],
    "commits": lambda repo, n: ["api", f"repos/{repo}/commits?per_page={n}", "--jq",
                                ".[] | {sha: .sha[0:8], date: .commit.author.date, author: .commit.author.name, msg: (.commit.message | split(\"\\n\")[0])}"],
    "runs": lambda repo, n: ["run", "list", "-R", repo, "--limit", str(n), "--json", "workflowName,status,conclusion,headBranch,createdAt,displayTitle"],
    "prs": lambda repo, n: ["pr", "list", "-R", repo, "--limit", str(n), "--state", "all", "--json", "number,title,state,author,updatedAt"],
    "issues": lambda repo, n: ["issue", "list", "-R", repo, "--limit", str(n), "--json", "number,title,state,updatedAt"],
}

# the hologram that fits each tool, and the parts worth calling out
EXHIBIT = {
    "system_stats": ("workstation", ["cpu", "gpu", "ram"]),
    "lab_status": ("rack", ["nodes", "gpu", "storage"]),
    "k8s_get": ("rack", ["nodes"]), "k8s_logs": ("rack", ["nodes"]), "k8s_events": ("rack", ["frame"]),
    "argocd_apps": ("rack", ["frame"]), "prometheus_query": ("rack", ["nodes", "gpu"]),
    "arbiter": ("monolith", ["plinth", "slab3", "crown"]), "gnosis_search": ("monolith", ["slab4"]),
    "scan": ("workstation", ["cpu", "gpu"]),
}


def _audit(name, args, ok, ms, size=0, err=None):
    os.makedirs(STATE, exist_ok=True)
    rec = {"t": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "tool": name, "args": args, "ok": ok, "ms": ms, "bytes": size}
    if err:
        rec["err"] = str(err)[:200]
    with open(AUDIT, "a") as f:
        f.write(json.dumps(rec) + "\n")


def _run(argv, timeout=20, env=None):
    r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=env, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[:300])
    return r.stdout


def _short(obj, limit=7000):
    s = obj if isinstance(obj, str) else json.dumps(obj, default=str, separators=(",", ":"))
    return s if len(s) <= limit else s[:limit] + f"…[truncated {len(s) - limit} chars]"


def _detach(argv):
    subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


# ================================================================== tools
def system_stats(live=None):
    from ..live import Local
    src = live.sources["local"] if live else Local()
    d = src.data if (live and src.data) else src.read()
    if not (live and src.data):
        time.sleep(0.4)
        d = src.read()
    g = d.get("gpu") or {}
    return {"host": d["host"], "kernel": d["kernel"], "uptime_h": round(d["uptime"] / 3600, 1),
            "cpu_pct": round(d["cpu"], 1), "cpu_peak_core_pct": round(d["cpu_max"], 1), "cpu_temp_c": d["cpu_temp"],
            "load": d["load"], "mem_used_gib": round(d["mem_used"] / 2**30, 1), "mem_total_gib": round(d["mem_total"] / 2**30, 1),
            "swap_used_gib": round(d["swap_used"] / 2**30, 1),
            "gpu": {k: g.get(k) for k in ("name", "util", "temp", "watts")} | {"vram_used_gib": round(g.get("vram_used", 0) / 2**30, 1), "vram_total_gib": round(g.get("vram_total", 0) / 2**30, 1)} if g else None,
            "disks": [{"mount": x["mount"], "pct": x["pct"], "total_gb": round(x["total"] / 1e9)} for x in d["disks"][:5]],
            "net_down_mbps": round(d["net_rx"] * 8 / 1e6, 2), "net_up_mbps": round(d["net_tx"] * 8 / 1e6, 2),
            "fans_rpm": d["fans"][:4]}


def lab_status(section="overview"):
    with open(os.path.join(HOME, ".local/share/bromigos/lab-token")) as f:
        D = get_json(LAB, {"Authorization": "Bearer " + f.read().strip()})
    svc = D.get("services") or {}
    down = {k: v for k, v in svc.items() if v.get("status") != "up"}
    c = D.get("cluster") or {}
    if section == "overview":
        return {"nodes_ready": c.get("nodesReady"), "nodes_total": c.get("nodesTotal"), "pods_running": c.get("podsRunning"),
                "pods_not_running": c.get("podsNotRunning"), "alerts_firing": c.get("alertsFiring"), "cluster_cpu_pct": c.get("cpuNow"),
                "services_up": len(svc) - len(down), "services_total": len(svc), "services_down": list(down),
                "argocd": D.get("argocd"), "gpu": {k: (D.get("gpu") or {}).get(k) for k in ("count", "utilNow", "tempC", "powerW")},
                "ai_models_up": [m.get("name") for m in (D.get("ai") or {}).get("models", []) if m.get("up")],
                "players_now": (D.get("games") or {}).get("playersNow"),
                "wan_down_mbps": round((D.get("network") or {}).get("wanDownBps", 0) * 8 / 1e6, 1),
                "solar_w": (D.get("solar") or {}).get("productionW")}
    pick = {"nodes": ["nodes", "nodeDisks", "proxmox"], "services": ["services"], "gpu": ["gpu", "ai"],
            "storage": ["nas", "nodeDisks"], "network": ["network", "traefik"], "games": ["games"], "solar": ["solar"]}.get(section)
    if not pick:
        raise ValueError("section must be overview|nodes|services|gpu|storage|network|games|solar")
    out = {k: D.get(k) for k in pick}
    for v in out.values():   # drop long time series; the model wants the now
        if isinstance(v, dict):
            for k in list(v):
                if k.endswith("Series"):
                    v.pop(k)
    return out


def _kubectl(args):
    if not os.path.exists(KUBECONFIG):
        raise RuntimeError("no pilot-readonly kubeconfig")
    return _run(["kubectl", "--kubeconfig", KUBECONFIG, "--request-timeout=15s"] + args, timeout=25)


def k8s_get(kind, namespace=None, name=None, selector=None):
    kind = kind.lower().rstrip()
    if kind in ("pod", "deployment", "node", "service", "job", "application", "ingress"):
        kind += "s"
    if kind not in K8S_KINDS:
        raise ValueError(f"kind must be one of {sorted(K8S_KINDS)}")
    if kind == "applications" and not namespace:
        namespace = "argocd"
    args = ["get", kind]
    if name:
        if not re.fullmatch(r"[a-z0-9.\-]{1,253}", name):
            raise ValueError("bad name")
        args.append(name)
    args += ["-n", namespace] if namespace else (["-A"] if kind not in ("nodes", "namespaces") else [])
    if selector:
        if not re.fullmatch(r"[\w./\-=,!]{1,200}", selector):
            raise ValueError("bad selector")
        args += ["-l", selector]
    if namespace and not re.fullmatch(r"[a-z0-9\-]{1,63}", namespace):
        raise ValueError("bad namespace")
    args += ["-o", "wide"] if kind in ("pods", "nodes") else []
    out = _kubectl(args)
    lines = out.strip().splitlines()
    return {"rows": len(lines) - 1, "table": "\n".join(lines[:80]) + ("\n…" if len(lines) > 80 else "")}


def k8s_logs(namespace, pod, container=None, tail=80, grep=None):
    for v in (namespace, pod) + ((container,) if container else ()):
        if not re.fullmatch(r"[a-z0-9.\-]{1,253}", v or ""):
            raise ValueError("bad name")
    args = ["logs", "-n", namespace, pod, f"--tail={min(int(tail), 300)}"]
    if container:
        args += ["-c", container]
    out = _kubectl(args)
    lines = out.splitlines()
    if grep:
        lines = [l for l in lines if grep.lower() in l.lower()]
    return "\n".join(l[:300] for l in lines[-120:])


def k8s_events(namespace=None, warnings_only=True):
    args = ["get", "events", "--sort-by=.lastTimestamp"]
    args += ["-n", namespace] if namespace else ["-A"]
    if warnings_only:
        args += ["--field-selector", "type=Warning"]
    lines = _kubectl(args).strip().splitlines()
    return "\n".join(lines if len(lines) <= 41 else lines[:1] + lines[-40:])


def argocd_apps(problems_only=False):
    d = json.loads(_kubectl(["get", "applications", "-n", "argocd", "-o", "json"]))
    apps = [{"name": a["metadata"]["name"], "sync": a.get("status", {}).get("sync", {}).get("status"),
             "health": a.get("status", {}).get("health", {}).get("status"),
             "revision": (a.get("status", {}).get("sync", {}).get("revision") or "")[:8]} for a in d.get("items", [])]
    bad = [a for a in apps if a["sync"] != "Synced" or a["health"] != "Healthy"]
    return {"total": len(apps), "healthy_synced": len(apps) - len(bad), "problems": bad,
            **({} if problems_only else {"apps": [a["name"] for a in apps]})}


def prometheus_query(promql, range_minutes=None, step_seconds=60):
    if len(promql) > 600:
        raise ValueError("query too long")
    if range_minutes:
        end = time.time()
        q = urllib.parse.urlencode({"query": promql, "start": end - 60 * min(int(range_minutes), 1440), "end": end,
                                    "step": max(int(step_seconds), 15)})
        d = get_json(f"{PROM}/api/v1/query_range?{q}")
        res = d.get("data", {}).get("result", [])
        return [{"metric": r.get("metric"), "points": len(r.get("values", [])),
                 "first": r.get("values", [[None, None]])[0][1], "last": r.get("values", [[None, None]])[-1][1],
                 "min": min((float(v[1]) for v in r.get("values", [])), default=None),
                 "max": max((float(v[1]) for v in r.get("values", [])), default=None)} for r in res[:25]]
    d = get_json(f"{PROM}/api/v1/query?" + urllib.parse.urlencode({"query": promql}))
    res = d.get("data", {}).get("result", [])
    return {"count": len(res), "result": [{"metric": r.get("metric"), "value": (r.get("value") or [None, None])[1]} for r in res[:40]]}


def github(action, repo=None, limit=10):
    if action not in GH_ACTIONS:
        raise ValueError(f"action must be one of {sorted(GH_ACTIONS)}")
    if action != "repos":
        repo = repo if (repo or "").startswith(ORG + "/") else f"{ORG}/{repo}"
        if not re.fullmatch(ORG + r"/[\w.\-]{1,100}", repo or ""):
            raise ValueError("repo must be under bromigos-org")
    out = _run(["gh"] + GH_ACTIONS[action](repo, max(1, min(int(limit), 30))), timeout=25)
    try:
        return json.loads(out)
    except ValueError:
        return out


def arbiter(view, key=None):
    if view == "cause_detail":
        if not key or len(key) > 200:
            raise ValueError("cause_detail needs a key from the causes view")
        return get_json(ARBITER + "/api/causes/detail?" + urllib.parse.urlencode({"key": key}), timeout=25)
    if view not in ARBITER_VIEWS:
        raise ValueError(f"view must be one of {sorted(ARBITER_VIEWS)} or cause_detail")
    d = get_json(ARBITER + ARBITER_VIEWS[view][0], timeout=25)
    if view == "now":
        r = d.get("research") or {}
        r["findings"] = [{k: f.get(k) for k in ("title", "verdict", "summary", "kind") if k in f} for f in (r.get("findings") or [])[:8]]
    if view == "positions":
        d.pop("forward_exposure", None)
    return d


def gnosis_search(space, query, limit=5):
    users = {"arbiter-research": ("arbiter-research", "arbiter-research"), "arbiter-signals": ("arbiter-signals", "arbiter-news")}
    if space not in users:
        raise ValueError("space must be arbiter-research or arbiter-signals")
    with open(GNOSIS_TOKEN) as f:
        tok = f.read().strip()
    user, agent = users[space]
    body = {"scope": {"tenant_id": "bromigos", "space_id": space, "agent_id": agent, "session_id": agent,
                      "user_id": user, "visibility": "agent_shared"},
            "query": query[:400], "limit": max(1, min(int(limit), 8)), "use_llm": False}
    req = urllib.request.Request(GNOSIS + "/v1/memories/search", data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20, context=ssl_ctx()) as r:
        d = json.load(r)
    return [{"content": x.get("content", "")[:600], "score": round(x.get("score", 0), 3),
             "date": (x.get("metadata") or {}).get("date") or x.get("created_at"), "kind": (x.get("metadata") or {}).get("kind")}
            for x in d.get("results", [])]


def _doc_ok(path):
    rp = os.path.realpath(path)
    if not any(rp.startswith(os.path.realpath(r) + os.sep) for r in DOC_ROOTS):
        return False
    if SECRETISH.search(rp) or not rp.endswith(DOC_EXT):
        return False
    return not any(part in SKIP_DIRS for part in rp.split(os.sep))


def docs_search(query, repo=None, limit=12):
    q = query.lower().strip()
    if len(q) < 3:
        raise ValueError("query too short")
    roots = DOC_ROOTS if not repo else [os.path.join(DOC_ROOTS[0], repo) if repo != "dotfiles" else DOC_ROOTS[1]]
    hits, scanned = [], 0
    t0 = time.monotonic()
    for root in roots:
        for d, dirs, files in os.walk(root):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith(".")]
            for fn in files:
                p = os.path.join(d, fn)
                if not fn.endswith((".md",)) or not _doc_ok(p):
                    continue
                scanned += 1
                try:
                    with open(p, errors="replace") as f:
                        for n, line in enumerate(f, 1):
                            if q in line.lower():
                                hits.append({"path": p.replace(HOME, "~"), "line": n, "text": line.strip()[:200]})
                                if len(hits) >= limit:
                                    return {"hits": hits, "scanned": scanned}
                except OSError:
                    continue
            if time.monotonic() - t0 > 6:
                return {"hits": hits, "scanned": scanned, "note": "stopped after 6 s"}
    return {"hits": hits, "scanned": scanned}


def docs_read(path, start_line=1, lines=120):
    p = os.path.expanduser(path)
    if not _doc_ok(p):
        raise ValueError("not a readable doc (docs roots only; md/json/yaml/txt/toml; nothing secret-looking)")
    with open(p, errors="replace") as f:
        all_ = f.readlines()
    s = max(1, int(start_line))
    chunk = all_[s - 1:s - 1 + min(int(lines), 250)]
    return {"path": path, "total_lines": len(all_), "from": s, "text": "".join(chunk)}


def notes_read(last_lines=60):
    if not os.path.exists(NOTES):
        return ""
    with open(NOTES) as f:
        ls = f.readlines()
    return "".join(ls[-min(int(last_lines), 200):])


def notes_append(text):
    text = text.strip()
    if not text or len(text) > 2000:
        raise ValueError("note must be 1-2000 chars")
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(NOTES, "a") as f:
        f.write(f"\n- {stamp}  {text}\n")
    return {"ok": True, "appended": len(text)}


def _switchboard():
    out = {"arbiter": "https://arbiter.redacted", "lab": "https://lab.redacted",
           "prometheus": PROM, "grafana": "https://grafana.redacted"}
    try:
        with open(os.path.join(HOME, ".local/share/bromigos/lab-token")) as f:
            D = get_json(LAB, {"Authorization": "Bearer " + f.read().strip()}, timeout=6)
        for g in (D.get("config") or {}).get("groups", []):
            for s in g.get("services", []):
                if s.get("lan") and s.get("id"):
                    out[s["id"].lower()] = s["lan"]
    except Exception:
        pass
    return out


def launch(target):
    t = target.strip()
    if re.fullmatch(r"https?://[^\s\"'<>]{3,500}", t):
        _detach(["xdg-open", t])
        return {"opened": t}
    key = t.lower().replace(" ", "")
    if key in APPS:
        _detach(APPS[key])
        return {"launched": key}
    sb = _switchboard()
    if key in sb:
        _detach(["xdg-open", sb[key]])
        return {"opened": key, "url": sb[key]}
    raise ValueError(f"unknown target. Apps: {sorted(APPS)}; switchboard: {sorted(sb)}; or an http(s) URL")


def panel(name, action="toggle"):
    names = {"all", "system", "network", "storage", "lab", "switchboard", "notes", "shortcuts"}
    if name not in names or action not in ("toggle", "show", "hide"):
        raise ValueError(f"panel must be one of {sorted(names)}; action toggle|show|hide")
    _run([WIDGETS, action, name], timeout=8)
    return {"ok": True, "panel": name, "action": action}


def wallpaper(variant):
    if variant not in ("den", "empty", "masked", "v1"):
        raise ValueError("variant must be den|empty|masked|v1")
    _run([WALLPAPER, variant], timeout=20)
    return {"ok": True, "wallpaper": variant}


def scan():
    _run([LIVE, "scan"], timeout=8)
    return {"ok": True, "note": "scanner pass running on the desktop"}


def time_now():
    now = dt.datetime.now().astimezone()
    return {"local": now.strftime("%A %d %B %Y, %H:%M:%S %Z"), "iso": now.isoformat(timespec="seconds"),
            "utc": dt.datetime.now(dt.timezone.utc).strftime("%H:%M UTC")}


def calendar_month(offset_months=0):
    now = dt.date.today()
    m = now.month - 1 + int(offset_months)
    y, m = now.year + m // 12, m % 12 + 1
    return {"month": calendar.TextCalendar(calendar.MONDAY).formatmonth(y, m), "today": now.isoformat()}


# ================================================================== registry
def _p(props, req=()):
    return {"type": "object", "properties": props, "required": list(req)}


S = {"type": "string"}
I = {"type": "integer"}
B = {"type": "boolean"}
SPECS = {
    "system_stats": ("This workstation now: CPU, temps, memory, GPU, disks, network, fans.", _p({})),
    "lab_status": ("EchoCraft Lab (the homelab) summary. section: overview (default), nodes, services, gpu, storage, network, games, solar.",
                   _p({"section": S})),
    "k8s_get": ("Read-only kubectl get on the homelab cluster. kind: pods, deployments, statefulsets, daemonsets, jobs, cronjobs, nodes, services, ingresses, ingressroutes, applications, namespaces, replicasets, events. Optional namespace, name, selector.",
                _p({"kind": S, "namespace": S, "name": S, "selector": S}, ["kind"])),
    "k8s_logs": ("Tail a pod's logs (read only). tail up to 300 lines; optional grep substring.",
                 _p({"namespace": S, "pod": S, "container": S, "tail": I, "grep": S}, ["namespace", "pod"])),
    "k8s_events": ("Recent cluster events, warnings only by default.", _p({"namespace": S, "warnings_only": B})),
    "argocd_apps": ("Argo CD applications: sync and health.", _p({"problems_only": B})),
    "prometheus_query": ("PromQL against the homelab Prometheus (read only). Instant by default; range_minutes for a summary over time.",
                         _p({"promql": S, "range_minutes": I, "step_seconds": I}, ["promql"])),
    "github": ("Read-only GitHub for bromigos-org via gh. action: repos, commits, runs, prs, issues. repo: name under bromigos-org.",
               _p({"action": S, "repo": S, "limit": I}, ["action"])),
    "arbiter": ("ARBITER market floor, read-only console views (paper trading; never trades or arms). view: " +
                ", ".join(sorted(ARBITER_VIEWS)) + ", cause_detail (needs key from causes).",
                _p({"view": S, "key": S}, ["view"])),
    "gnosis_search": ("Search ARBITER's research memory. space: arbiter-research or arbiter-signals.",
                      _p({"space": S, "query": S, "limit": I}, ["space", "query"])),
    "docs_search": ("Search the lore, AGENTS.md/CLAUDE.md and repo docs (markdown) for a phrase. repo: optional bromigos-org repo name or 'dotfiles'.",
                    _p({"query": S, "repo": S}, ["query"])),
    "docs_read": ("Read part of a doc found by docs_search (path as returned).", _p({"path": S, "start_line": I, "lines": I}, ["path"])),
    "notes_read": ("Read the end of FIELD NOTES, the operator's notepad.", _p({"last_lines": I})),
    "notes_append": ("Append a line to FIELD NOTES (only when the operator asks to note something).", _p({"text": S}, ["text"])),
    "launch": ("Open an app (terminal, browser, chrome, files, discord, spotify, obs, steam), a switchboard entry (arbiter, lab, grafana, argocd, …) or an http(s) URL.",
               _p({"target": S}, ["target"])),
    "panel": ("Toggle a desktop widget panel: all, system, network, storage, lab, switchboard, notes, shortcuts.",
              _p({"name": S, "action": S}, ["name"])),
    "wallpaper": ("Switch the den wallpaper: den, empty, masked, v1.", _p({"variant": S}, ["variant"])),
    "scan": ("Run the desktop scanner pass (the hardware schematic sweep).", _p({})),
    "show_hologram": ("Put a model hologram on your side table: workstation, wick, rack, monolith, emblem; optional part ids to call out.",
                      _p({"model": S, "parts": {"type": "array", "items": S}}, ["model"])),
    "open_gallery": ("Open the full hologram gallery on a model.", _p({"model": S})),
    "time_now": ("The local date and time.", _p({})),
    "calendar_month": ("A month calendar; offset_months 0 = this month.", _p({"offset_months": I})),
}
FUNCS = {n: globals()[n] for n in SPECS if n in globals()}


def schemas():
    return [{"type": "function", "function": {"name": n, "description": d, "parameters": p}} for n, (d, p) in SPECS.items()]


def call(name, args, ui=None, live=None):
    """Run a tool; returns (result_text, exhibit or None). ui handles the UI-only tools."""
    t0 = time.monotonic()
    args = args or {}
    try:
        if name in ("show_hologram", "open_gallery"):
            if ui is None:
                raise RuntimeError("no display")
            res = ui(name, args)
        elif name == "system_stats":
            res = system_stats(live)
        elif name in FUNCS:
            res = FUNCS[name](**args)
        else:
            raise ValueError(f"unknown tool {name}")
        text = _short(res)
        _audit(name, args, True, int((time.monotonic() - t0) * 1000), len(text))
        ex = EXHIBIT.get(name)
        return text, ex
    except Exception as e:
        _audit(name, args, False, int((time.monotonic() - t0) * 1000), err=e)
        return json.dumps({"error": f"{type(e).__name__}: {str(e)[:300]}"}), None
