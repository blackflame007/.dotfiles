"""VECTOR's tools: fast read tools, act tools for the homelab, Vault wiring, desktop actions.
His full terminal is separate (run_shell, holo/vector/shell.py, with its own limits).

Hard limits (enforced here, not by the prompt):
  * every subprocess here is a fixed argv from an allowlist, never a shell string;
  * reads: the cluster through the `pilot-readonly` ServiceAccount kubeconfig (get/list/
    watch, no secrets/configmaps/exec); verbs used: get, logs, top;
  * acts (act.py): restart, scale, delete a pod, run a Job from a CronJob, Argo sync/
    refresh/wait, as `vector-operator` (RBAC + admission policies in the lab's vector chart),
    never arbiter-live*; CI watch through gh; notes into the kb-* knowledge spaces;
  * Vault (vault.py): AppRole `vector`; list names, put a generated or operator-typed
    value, copy Vault to Vault; never returns or logs a value;
  * Prometheus: GET /api/v1/query and query_range only;
  * GitHub: `gh` read subcommands only, repos under bromigos-org;
  * ARBITER: a fixed table of console GET paths (no trading, no arming, no live/*);
  * Gnosis: POST /v1/memories/search only, two spaces;
  * files: read under the docs roots only (markdown/json/yaml/txt), never secret-looking
    names; the one write is appending to FIELD NOTES;
  * actions: launch an allowlisted app or an http(s) URL, toggle a widget panel, switch
    the den wallpaper, run a scanner pass, show a hologram.
Every call is appended to ~/.local/state/bromigos/vector-audit.log (tool, args, ok, ms).
"""
import calendar
import datetime as dt
import fnmatch
import json
import math
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request

from ..live import get_json, ssl_ctx
from ..private import PRIV

HOME = os.path.expanduser("~")
STATE = os.path.join(HOME, ".local/state/bromigos")
AUDIT = os.path.join(STATE, "vector-audit.log")
KUBECONFIG = os.path.join(HOME, ".local/share/bromigos/pilot-kubeconfig")
GNOSIS_TOKEN = os.path.join(HOME, ".local/share/bromigos/gnosis-vector-read-token")   # gate token: read only
NOTES = os.path.join(HOME, ".local/share/bromigos/notes.md")
# Internal URLs and Vault paths come from the private overlay (AGENTS.md, Private values).
PROM = PRIV.url("prometheus")
GNOSIS = PRIV.url("gnosis_gate")                   # gnosis-gate: narrow tokens, never the service token
ARBITER = PRIV.url("arbiter")
LAB = PRIV.url("lab", "/api/status")
VAULT_ROOT = PRIV.vault_root() or "<vault root>"   # the KV prefix his Vault tools may touch
LAB_DOMAIN = PRIV.lan_domain() or "<lab domain>"
WIDGETS = os.path.join(HOME, ".config/bromigos/widgets/bromigos-widgets")
WALLPAPER = os.path.join(HOME, ".config/bromigos/bin/bromigos-wallpaper")
LIVE = os.path.join(HOME, ".config/bromigos-live/bin/bromigos-live")
ORG = "bromigos-org"
DOC_ROOTS = [os.path.join(HOME, "github.com/bromigos-org"), os.path.join(HOME, "github.com/nolgiainc"),
             os.path.join(HOME, "github.com/blackflame007"), os.path.join(HOME, ".dotfiles")]
DOC_EXT = (".md", ".json", ".yaml", ".yml", ".txt", ".toml")
SECRETISH = re.compile(r"(secret|token|credential|password|passwd|\.env|private|\.key$|\.pem$|kubeconfig|vault|zsh-secrets)", re.I)
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", "target", "private"}

APPS = {  # name -> argv (the desktop's own launch commands, from the Hyprland binds)
    "terminal": ["kitty"], "kitty": ["kitty"], "browser": ["librewolf"], "librewolf": ["librewolf"],
    "chrome": ["google-chrome-stable"], "files": ["pcmanfm"], "pcmanfm": ["pcmanfm"], "dolphin": ["dolphin"],
    "discord": ["discord"],
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
    "k8s_restart": ("rack", ["nodes"]), "k8s_scale": ("rack", ["nodes"]), "k8s_delete_pod": ("rack", ["nodes"]),
    "k8s_run_job": ("rack", ["nodes"]), "argocd_sync": ("rack", ["frame"]), "argocd_refresh": ("rack", ["frame"]),
    "argocd_wait": ("rack", ["frame"]),
}


LAST_USER_TEXT = {"text": ""}          # the host's latest words (set by the brain each turn)
PRIVATE_ARGS = {"remember": ("text",), "forget": ("what",), "gnosis_search": ("query",), "herdr_send": ("text",)}


def _audit(name, args, ok, ms, size=0, err=None):
    os.makedirs(STATE, exist_ok=True)
    if name in PRIVATE_ARGS:      # memory text is hashed and truncated, never logged whole
        import hashlib
        args = dict(args)
        for k in PRIVATE_ARGS[name]:
            if isinstance(args.get(k), str):
                t = args[k]
                args[k] = {"sha1": hashlib.sha1(t.encode()).hexdigest()[:12], "head": t[:40], "chars": len(t)}
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
    users = {"arbiter-research": ("arbiter-research", "arbiter-research"), "arbiter-signals": ("arbiter-signals", "arbiter-news"),
             "vector": ("operator", "vector")}
    if space not in users:
        raise ValueError("space must be vector (your own memory), arbiter-research or arbiter-signals")
    with open(GNOSIS_TOKEN) as f:
        tok = f.read().strip()
    user, agent = users[space]
    body = {"scope": {"tenant_id": "bromigos", "space_id": space, "agent_id": agent, "session_id": agent,
                      "user_id": user, "visibility": "private_user" if space == "vector" else "agent_shared"},
            "query": query[:400], "limit": max(1, min(int(limit), 8)), "use_llm": False}
    req = urllib.request.Request(GNOSIS + "/v1/memories/search", data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20, context=ssl_ctx()) as r:
        d = json.load(r)
    return [{"content": x.get("content", "")[:600], "score": round(x.get("score", 0), 3),
             "date": (x.get("metadata") or {}).get("date") or x.get("created_at"), "kind": (x.get("metadata") or {}).get("kind")}
            for x in d.get("results", [])]


KB_SPACES = {"bromigos": "kb-bromigos", "nolgia": "kb-nolgia", "personal": "kb-personal", "desktop": "kb-desktop",
             "homelab": "kb-homelab"}


_STOP = set("a an and are as at be by can do does for from has have how i in is it its me my of on or our so that the "
             "their them there this to us was we what whats when where which who why will with you your about".split())


def _terms(q):
    return [w for w in re.findall(r"[a-z0-9][a-z0-9_.-]*[a-z0-9]|[a-z0-9]", q.lower().replace("'s", "")) if w not in _STOP and len(w) > 1]


def _kb_file(space, repo, path):
    """Where a knowledge-base chunk's doc lives on this machine, if it does."""
    if not repo or not path:
        return None
    home = os.path.expanduser("~")
    if space == "kb-desktop":
        roots = [os.path.join(home, ".dotfiles")]
    else:
        org = {"kb-bromigos": "bromigos-org", "kb-nolgia": "nolgiainc", "kb-personal": "blackflame007",
               "kb-homelab": "bromigos-org"}.get(space)
        roots = [os.path.join(home, "github.com", org, repo)] if org else []
    for r in roots:
        f = os.path.join(r, path)
        if os.path.isfile(f):
            return f
    return None


def knowledge_search(query, space=None, limit=6):
    """The knowledge base in Gnosis (READMEs, AGENTS.md, CLAUDE.md and docs of the operator's
    repos, the canon lore and the desktop record), read through the gnosis-gate.

    Gnosis ranks by embeddings only (its hybrid BM25 leg is off server-wide), which misses
    exact names like WORKBENCH or LIVE.md, so a wider pool per space is re-ranked here with a
    small lexical bonus (query words in the path, heading and text), and copies of the same
    doc (a repo kept in two orgs) are folded together."""
    import concurrent.futures as cf
    spaces = list(KB_SPACES.values())
    if space:
        sp = KB_SPACES.get(space.replace("kb-", ""), space)
        if sp not in spaces:
            raise ValueError(f"space must be one of {sorted(KB_SPACES)}")
        spaces = [sp]
    with open(GNOSIS_TOKEN) as f:
        tok = f.read().strip()
    n = max(1, min(int(limit), 10))
    terms = _terms(query)

    def one(sp):
        body = {"scope": {"tenant_id": "bromigos", "space_id": sp, "agent_id": "vector", "session_id": "vector",
                          "user_id": sp, "visibility": "agent_shared"}, "query": query[:400], "limit": 20, "use_llm": False}
        req = urllib.request.Request(GNOSIS + "/v1/memories/search", data=json.dumps(body).encode(), method="POST",
                                     headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10, context=ssl_ctx()) as r:
            return sp, json.load(r).get("results", [])

    WORD = re.compile(r"[a-z0-9][a-z0-9_.-]*[a-z0-9]|[a-z0-9]")
    pool = []
    with cf.ThreadPoolExecutor(len(spaces)) as ex:
        for sp, res in ex.map(one, spaces):
            for x in res:
                m = x.get("metadata") or {}
                text = x.get("content") or ""
                where = f"{m.get('repo') or ''}/{m.get('path') or ''} {m.get('heading') or ''}".lower()
                pool.append((sp, x, m, text, where, set(WORD.findall(text.lower()))))
    # words rare in the pool (WORKBENCH, LIVE.md) say more than common ones (panel, work)
    idf = {t: math.log((len(pool) + 1) / (1 + sum(1 for p in pool if t in p[5] or t in p[4]))) + 0.1 for t in terms}
    total = sum(idf.values()) or 1.0
    hits, seen = [], {}
    for sp, x, m, text, where, words in pool:
        bonus = (0.14 * sum(idf[t] for t in terms if t in words) + 0.08 * sum(idf[t] for t in terms if t in where)) / total
        score = (x.get("score") or 0) + bonus
        key = (m.get("path"), m.get("heading"), text[:200])
        h = {"space": sp, "score": round(score, 3), "repo": m.get("repo"), "path": m.get("path"),
             "heading": m.get("heading"), "url": m.get("url"), "text": text[:900], "id": x.get("memory_id")}
        f = _kb_file(sp, m.get("repo"), m.get("path"))
        if f:
            h["file"] = f                 # the local copy: docs_read takes this, not the url
        if key in seen:                   # the same doc in two repos: keep one, note the other
            keep = seen[key]
            keep.setdefault("also_in", []).append(f"{sp}:{m.get('repo')}")
            keep["score"] = max(keep["score"], h["score"])
            continue
        seen[key] = h
        hits.append(h)
    hits.sort(key=lambda h: -h["score"])
    from . import events
    for sp in sorted({h["space"] for h in hits[:n]}):
        ids = [h["id"] for h in hits[:n] if h["space"] == sp and h.get("id")]
        events.emit("memory.recall", space=sp, ids=ids, n=len(ids), ms=None, source="gnosis")
    return {"query": query, "hits": hits[:n]}


def conversation_history(query="", when="", limit=8):
    from . import history
    return history.tool(query, when, limit)


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


def run_shell(command, cwd="~", timeout_s=60):
    """Full terminal as the operator's user; the limits live in shell.py (no sudo, no secrets,
    no real money), every command is logged to vector-shell.log."""
    from .shell import RUNNER
    return RUNNER.run(command, cwd, timeout_s)


def shell_off():
    t = LAST_USER_TEXT["text"].lower()
    if not (re.search(r"\b(terminal|shell|command line|commands)\b", t) and
            re.search(r"\b(off|stop|disable|don'?t|do not|no more|kill)\b", t)):
        raise PermissionError("only when the host asks you to stop using the terminal (he hasn't); "
                              "a refused command is not a reason to switch it off")
    from .shell import RUNNER, set_enabled
    RUNNER.kill("terminal switched off")
    set_enabled(False)
    return {"ok": True, "terminal": "off", "note": "only the host can switch it back on (bromigos-holo shell on)"}


from .reach import (herdr_read, herdr_send, herdr_start, herdr_status, herdr_wait,  # noqa: E402
                    web_fetch, web_search)
from .act import (argocd_refresh, argocd_sync, argocd_wait, ci_watch, k8s_delete_pod,  # noqa: E402
                  k8s_restart, k8s_run_job, k8s_scale, kb_write)
from .vault import vault_copy, vault_list, vault_put  # noqa: E402
from .desk import app_search, launch_app, open_path, run_detached, window, windows  # noqa: E402
from .track import changes_check, github_repo_create  # noqa: E402
from .skills import load_skill  # noqa: E402
from .eyes import active_window, look, read_screen_text, watch  # noqa: E402
from .snapshots import snapshot_create, snapshot_list, snapshot_undo  # noqa: E402
from .briefing import briefing_now, quiet  # noqa: E402
from .nolgia import nolgia_catalog, nolgia_credits, nolgia_generate, nolgia_read, nolgia_review  # noqa: E402


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
    out = {k: PRIV.url(k) for k in ("arbiter", "lab", "prometheus", "grafana") if PRIV.url(k)}
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
    from .desk import launch_app
    return launch_app(t)                      # any installed program, by fuzzy name


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


DECKS = {  # bromigos-live's holograms (README "Driving the holograms") -> their verbs
    "mind": {"open", "close", "focus", "space", "clear"},
    "ops": {"open", "close", "focus", "clear"},
    "swarm": {"open", "close", "point", "focus", "clear"},
    "netmap": {"open", "close", "trace", "clear"},
    "replay": {"open", "close", "pick", "play", "pause", "seek"},
}


def hologram_deck(deck, verb="open", args=""):
    """Open or drive one of the live layer's holograms (fixed argv, allowlisted verbs)."""
    if deck not in DECKS:
        raise ValueError(f"deck must be one of {sorted(DECKS)}")
    if verb not in DECKS[deck]:
        raise ValueError(f"{deck} verbs: {sorted(DECKS[deck])}")
    a = (args or "").strip()
    if len(a) > 160 or not re.fullmatch(r"[\w .:/@#,+=-]*", a):
        raise ValueError("args: up to 160 plain characters")
    out = _run([LIVE, deck, verb] + a.split(), timeout=10).strip()
    return {"ok": True, "deck": deck, "verb": verb, "result": out[:300]}


def my_setup():
    """VECTOR's own configuration, read live from his code and config files (never remembered)."""
    import json as _j
    holo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        vj = _j.load(open(os.path.join(holo, "voice.json")))
    except (OSError, ValueError):
        vj = {}
    from . import brain_pai, build, history, skills
    try:
        cap = _j.load(open(os.path.join(holo, "nolgia.json"))).get("daily_credits")
    except (OSError, ValueError):
        cap = None
    voices = {r: {"speaker": v.get("name"), "marker": v.get("marker"), "use": v.get("use")} for r, v in (vj.get("voices") or {}).items()}
    lanes = brain_pai.lanes()
    return {
        "brain": {"framework": "Pydantic AI", "voice_lane": lanes[0], "deep_lane": lanes[1],
                  "first_byte_timeout_s": brain_pai.FIRST_BYTE, "stream_silence_timeout_s": brain_pai.IDLE_GAP,
                  "failed_model_cooldown_s": brain_pai.COOLDOWN, "thinking": "off on every route"},
        "speech_to_text": (vj.get("stt") or {}).get("model"), "stt_device": (vj.get("stt") or {}).get("device"),
        "text_to_speech": {"engine": vj.get("engine"), "fallback": vj.get("fallback"), "speed": vj.get("speed")},
        "voices": voices, "conversation_mode": vj.get("conversation"),
        "memory": "Gnosis (homelab), own space, through the gnosis-gate; recall capped at 0.2 s from a local mirror",
        "knowledge_spaces": sorted(KB_SPACES.values()), "knowledge_sync": "nightly at 03:30 (bromigos-kb-sync.timer)",
        "history": f"chat log kept locally; a new session after {history.GAP // 60} quiet minutes",
        "nolgia_daily_credit_cap": cap, "build_trial_seconds": build.TRIAL_S,
        "skills": [x["name"] for x in skills.load()],
        "tools": len(SPECS),
    }


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
    "gnosis_search": ("Search memory: vector (your own long-term memory), arbiter-research or arbiter-signals (ARBITER's research and event memory, read only).",
                      _p({"space": S, "query": S, "limit": I}, ["space", "query"])),
    "knowledge_search": ("Search the knowledge base: what the host's software is and how it works. Spaces: bromigos "
                         "(the Bromigos org's repos and the canon lore), nolgia (Nolgia, the host's other company), personal "
                         "(his own repos), desktop (everything built on this desktop, keybinds), homelab. Omit space to search "
                         "all. For exact detail, docs_read a hit's file (its local path; never the url); desktop hits from .py "
                         "files are code docstrings, so read those with run_shell.", _p({"query": S, "space": S, "limit": I}, ["query"])),
    "conversation_history": ("Your past conversations with the host (from the local log). query: words to find "
                             "(e.g. 'gnosis'); when: today, yesterday, last week, a weekday or YYYY-MM-DD. Returns "
                             "session titles, summaries or matching snippets.", _p({"query": S, "when": S, "limit": I})),
    "docs_search": ("Search the lore, AGENTS.md/CLAUDE.md and repo docs (markdown) for a phrase. repo: optional bromigos-org repo name or 'dotfiles'.",
                    _p({"query": S, "repo": S}, ["query"])),
    "docs_read": ("Read part of a doc found by docs_search (path as returned).", _p({"path": S, "start_line": I, "lines": I}, ["path"])),
    "run_shell": ("Run a bash command on the host's workstation as the host's user (full access, no approval; everything is "
                  "logged). For anything the read tools don't cover: git, files, builds, systemctl --user, scripts. Say in one "
                  "short line what you are about to run before anything that changes state. Never sudo; no secrets; no real "
                  "money (those are refused). cwd defaults to ~; timeout_s up to 600.",
                  _p({"command": S, "cwd": S, "timeout_s": I}, ["command"])),
    "shell_off": ("Switch your terminal off (kill switch) when the host asks you to stop using it. You cannot switch it back on.",
                  _p({})),
    "web_search": ("Search the web (the homelab's SearXNG) for current information. Returns title, url and snippet. "
                   "Say where facts came from. category: general (default), it, science or news.", _p({"query": S, "n": I, "category": S}, ["query"])),
    "web_fetch": (f"Fetch a web page's readable text (http/https; no LAN hosts except *.{LAB_DOMAIN}).", _p({"url": S}, ["url"])),
    "herdr_status": ("The host's herdr workspaces: AI coding agents (e.g. Claude Code sessions) with their status: "
                     "working, idle, or blocked (waiting on the host).", _p({})),
    "herdr_read": ("Recent output of a herdr agent (target: its id, or a hint like the repo name).",
                   _p({"agent": S, "lines": I}, ["agent"])),
    "herdr_send": ("Send text to a herdr agent, as if typed (no Enter is added unless the text ends with a newline). "
                   "Say what you are sending first.", _p({"agent": S, "text": S}, ["agent", "text"])),
    "herdr_start": ("Start a new agent in herdr, e.g. a Claude Code session in a repo: name, cwd, argv (default [\"claude\"]).",
                    _p({"name": S, "cwd": S, "argv": {"type": "array", "items": S}}, ["name"])),
    "herdr_wait": ("Wait until a herdr agent reaches a status (idle, working, blocked), up to timeout_s.",
                   _p({"agent": S, "status": S, "timeout_s": I}, ["agent"])),
    "notes_read": ("Read the end of FIELD NOTES, the operator's notepad.", _p({"last_lines": I})),
    "notes_append": ("Append a line to FIELD NOTES (only when the operator asks to note something).", _p({"text": S}, ["text"])),
    "launch": ("Open an app (terminal, browser, chrome, files, discord, spotify, obs, steam, or any installed program by name), a switchboard entry (arbiter, lab, grafana, argocd, …) or an http(s) URL.",
               _p({"target": S}, ["target"])),
    "panel": ("Toggle a desktop widget panel: all, system, network, storage, lab, switchboard, notes, shortcuts.",
              _p({"name": S, "action": S}, ["name"])),
    "wallpaper": ("Switch the den wallpaper: den, empty, masked, v1.", _p({"variant": S}, ["variant"])),
    "scan": ("Run the desktop scanner pass (the hardware schematic sweep).", _p({})),
    "remember": ("Write something durable to your long-term memory (Gnosis): a host preference, a decision, a fact about "
                 "the lab worth keeping, or a recurring problem. One short self-contained sentence. category: host preferences, "
                 "decisions, lab facts or recurring problems.", _p({"text": S, "category": S}, ["text"])),
    "forget": ("Remove something from your own long-term memory when the host asks you to forget it. what: a description "
               "of it, or 'that' for the last thing you filed.", _p({"what": S})),
    "set_voice": ("Pin your voice on the line: auto (you pick per sentence, the default), or one of main, robot, scientist, "
                  "floor, notify. ALWAYS call this when the host asks to switch or change your voice ('switch to your robot "
                  "voice', 'back to normal' = auto); a marker in your reply does not switch it.",
                  _p({"mode": S}, ["mode"])),
    "show_hologram": ("Put a model hologram on your side table: workstation, wick, rack, monolith, emblem; optional part ids to call out.",
                      _p({"model": S, "parts": {"type": "array", "items": S}}, ["model"])),
    "open_gallery": ("Open the full hologram gallery on a model.", _p({"model": S})),
    "k8s_restart": ("Rollout-restart a deployment, statefulset or daemonset and wait until it's Ready again (as vector-operator). "
                    "namespace: the workload's real Kubernetes namespace, usually named after the app (searxng lives in "
                    "namespace searxng); 'the homelab' or 'the lab' is the cluster, never a namespace. If unsure, look it "
                    "up with k8s_get first. Say what you're restarting first.", _p({"namespace": S, "name": S, "kind": S, "wait": B}, ["namespace", "name"])),
    "k8s_scale": ("Scale a deployment or statefulset to replicas (0-20) and wait for it. namespace: the real one, usually "
                  "the app's own name (never 'homelab'); k8s_get first if unsure. Say it first.",
                  _p({"namespace": S, "name": S, "replicas": I, "kind": S}, ["namespace", "name", "replicas"])),
    "k8s_delete_pod": ("Delete one pod (e.g. a stuck one; its controller replaces it). Say it first.",
                       _p({"namespace": S, "pod": S}, ["namespace", "pod"])),
    "k8s_run_job": ("Run a Job now from a CronJob's template (namespace, cronjob); wait=true waits up to 9 minutes.",
                    _p({"namespace": S, "cronjob": S, "wait": B}, ["namespace", "cronjob"])),
    "argocd_sync": ("Sync an Argo CD app now and wait until Synced and Healthy (after a push to homelab master, Argo "
                    "applies it by itself; sync only to hurry it).", _p({"app": S, "wait": B}, ["app"])),
    "argocd_refresh": ("Make Argo CD re-read an app's source (hard=true also re-renders).", _p({"app": S, "hard": B}, ["app"])),
    "argocd_wait": ("Wait until an Argo CD app is Synced and Healthy (up to timeout_s, default 300).",
                    _p({"app": S, "timeout_s": I}, ["app"])),
    "ci_watch": ("Wait for GitHub Actions on a commit (sha) or a branch's latest run, in a repo under bromigos-org, "
                 "nolgiainc or blackflame007 (owner/name, or a bromigos-org name). Returns each run's conclusion.",
                 _p({"repo": S, "sha": S, "branch": S, "timeout_s": I}, ["repo"])),
    "kb_write": ("Add a verified note to the knowledge base (space: bromigos, nolgia, personal, desktop, homelab) "
                 "so it can be found later: how something works, where something lives. Never secrets.",
                 _p({"space": S, "title": S, "text": S}, ["space", "title", "text"])),
    "vault_list": ("Homelab Vault: a folder's entries or a secret's key NAMES (never values). "
                   f"path under {VAULT_ROOT}.",
                   _p({"path": S})),
    "vault_put": ("Store one key in the homelab Vault (patch: other keys untouched). value_from: generate (random; "
                  "length, charset alnum|hex|urlsafe|strong) or operator_prompt (a dialog pops up for the host to "
                  "type or paste it; say so first). You never see the value.",
                  _p({"path": S, "key": S, "value_from": S, "length": I, "charset": S}, ["path", "key", "value_from"])),
    "vault_copy": (f"Copy one Vault key to another path, Vault to Vault: src and dst as {VAULT_ROOT}/<path>#<key>.",
                   _p({"src": S, "dst": S}, ["src", "dst"])),
    "hologram_deck": ("Open or drive a live-layer hologram for the host. deck and verbs: mind (focus <memory or doc>, "
                      "space <kb-name>, clear: your memory and knowledge as a constellation); ops (focus <repo>, clear: your "
                      "and the host's actions on the lab, pushes, CI, Argo, pods); swarm (point <repo or agent>, focus, clear: "
                      "repos and herdr agents); netmap (trace <host or ip>, clear: the LAN and latency); replay (pick <latest, "
                      "biggest, instrument, agent or fill id>, play, pause, seek <0..1>: an ARBITER paper trade). open/close "
                      "for any. Use it when showing beats telling, or when the host asks to see something.",
                      _p({"deck": S, "verb": S, "args": S}, ["deck"])),
    "app_search": ("Find installed programs by fuzzy name or purpose ('image editor', 'files', 'obs').", _p({"query": S}, ["query"])),
    "launch_app": ("Start any installed program by fuzzy name (its desktop entry); workspace optional (opens there silently).",
                   _p({"name": S, "workspace": S}, ["name"])),
    "run_detached": ("Start a command detached from you (a GUI program or a long job), optionally on a workspace. Same "
                     "limits as your terminal.", _p({"command": S, "workspace": S}, ["command"])),
    "open_path": ("Open a file, folder or URL with its default application.", _p({"target": S}, ["target"])),
    "windows": ("The open windows: address, app, title, workspace, which is focused.", _p({})),
    "window": ("Act on one window (by address, app class or title words): focus, close (say so first), or move to a "
               "workspace.", _p({"action": S, "target": S, "workspace": S}, ["action", "target"])),
    "changes_check": ("Before you say a task is done: lists every repo you touched with changes you left uncommitted or "
                      "unpushed, and changes outside repos not yet recorded in VECTOR-CHANGELOG.md. Clear it first.", _p({})),
    "github_repo_create": ("Create a new GitHub repo: owner bromigos-org (Bromigos), nolgiainc (Nolgia, the company) or "
                           "blackflame007 (personal); ask when unclear. Private unless the host said public. Cloned to "
                           "~/github.com/<owner>/<name>, seeded with README, AGENTS.md and .gitignore, pushed.",
                           _p({"owner": S, "name": S, "description": S, "public": B}, ["owner", "name", "description"])),
    "nolgia_catalog": ("The host's nolgia models for a modality (image, video, audio, 3d) with credit prices, cheapest first.",
                       _p({"modality": S, "limit": I})),
    "nolgia_credits": ("nolgia credits: the balance, what you've spent today, and the daily cap.", _p({})),
    "nolgia_read": ("Read-only nolgia CLI: 'models get <id>', 'characters list', 'characters get <id>', 'assets list', "
                    "'assets get <id>', 'projects list', 'status <job>', 'wait <job>', 'skills list'.", _p({"command": S}, ["command"])),
    "nolgia_generate": ("Generate one image, video or audio clip with nolgia. Say the estimated cost first (nolgia_catalog); "
                        "over the daily cap it returns needs_approval: ask the host, and only after he says yes call again "
                        "with approved=true. Images and videos come back with a vision review: check it before presenting. "
                        "out: where the file goes (brand kit, a repo, ~/Pictures); omit for a scratch folder. Report credits left.",
                        _p({"kind": S, "prompt": S, "model": S, "out": S, "input": S, "aspect_ratio": S, "quality": S,
                            "character_id": S, "voice": S, "duration_seconds": I, "project_id": S, "approved": B},
                           ["kind", "prompt"])),
    "nolgia_review": ("Look at an image (or a video's middle frame) with the vision model and answer a question about it.",
                      _p({"path": S, "question": S}, ["path"])),
    "build_start": ("Build something new on the desktop, or change a visualization, in the background: a widget panel, a "
                    "live-layer shader or deck, a hologram model, a change to an existing view. Your builder works in a "
                    "git worktree, validates with offscreen renders and a vision look, then puts it up in trial mode; you "
                    "stay on the line. goal: what to build, with the details the host gave (data, look, placement). Say "
                    "one line that it's started.", _p({"goal": S}, ["goal"])),
    "build_status": ("Where the background build is: phase, files, progress, seconds left in a trial.", _p({})),
    "build_keep": ("The host said keep the trial: commit it in the dotfiles style, merge, push. Only after the host "
                   "answered; never on your own.", _p({})),
    "build_revert": ("The host said revert (or doesn't want it): roll the trial back to exactly what was there.", _p({})),
    "build_stop": ("Stop the background build now (its worktree is removed; a trial is rolled back).", _p({})),
    "load_skill": ("Load one of your skills by name (the catalog is in your instructions) when a task needs its know-how.",
                   _p({"name": S}, ["name"])),
    "my_setup": ("Your own configuration, read live: your models and lanes, the first-byte and silence timeouts, "
                 "speech-to-text and voice engines, your voices, memory, knowledge spaces and sync time, the nolgia "
                 "credit cap, the build trial length, your skills. Call it for any question about how you work.", _p({})),
    "look": ("Look at the host's screen and answer a question about it (read only: you never click or type into "
             "apps). Only when the host asks ('look at this', 'what's on my screen', 'check this error') or to check "
             "your own build; never on your own. target: monitor (default), window (the focused one: 'this'), screen "
             "(every monitor) or a region 'x,y wxh'. Say 'let me take a look' first.",
             _p({"question": S, "target": S}, ["question"])),
    "read_screen_text": ("Transcribe the exact text on screen (an error, a log, a dialog) when the wording matters; "
                         "target as for look (default: the focused window). Slower than look.", _p({"target": S})),
    "active_window": ("What the host is looking at: the focused window's app, title and workspace ('this' in his "
                      "question). No screenshot.", _p({})),
    "watch": ("Watch mode, only when the host turns it on: glance at the focused window every every_s seconds "
              "(10-120) and keep a few lines of notes to follow along (e.g. while debugging); an indicator shows the "
              "whole time and it turns itself off after 15 minutes. mode: on, off or status.",
              _p({"mode": S, "every_s": I}, ["mode"])),
    "snapshot_create": ("Take a snapper snapshot of the system (root and home) before something the host wants to be "
                        "able to undo; description says what. Your terminal already wraps system-level commands in a "
                        "pre/post pair by itself.", _p({"description": S}, ["description"])),
    "snapshot_list": ("Recent snapper snapshots and your own pre/post pairs.", _p({"limit": I})),
    "snapshot_undo": ("Undo your last system-level change (snapper undochange on its pre/post pair), or a given pair "
                      "'home:12..13'. For 'VECTOR, undo that'. A whole-system rollback is the host's (the GRUB "
                      "snapshot menu): explain it, don't do it.", _p({"pair": S})),
    "briefing_now": ("The facts for a brief right now (\"brief me\", \"what did I miss?\"): lab health, Argo problems, "
                     "firing alerts, ARBITER's paper results, CI failures in the last hours. Lead with what's broken.", _p({})),
    "quiet": ("Be quiet: no explained-alert calls and no return briefs for this many minutes (\"be quiet for an hour\" = "
              "60; 0 to speak up again). Answers to the host still work.", _p({"minutes": I}, ["minutes"])),
    "time_now": ("The local date and time.", _p({})),
    "calendar_month": ("A month calendar; offset_months 0 = this month.", _p({"offset_months": I})),
}
FUNCS = {n: globals()[n] for n in SPECS if n in globals()}


def schemas():
    return [{"type": "function", "function": {"name": n, "description": d, "parameters": p}} for n, (d, p) in SPECS.items()]


def _outcome(res):
    """One short line for the event feed (never the whole result)."""
    if isinstance(res, dict):
        for k in ("refused", "error", "ready", "rollout", "all_green", "sync", "exit", "ok"):
            if k in res:
                return f"{k}={str(res[k])[:80]}"
        return f"{len(res)} fields"
    if isinstance(res, list):
        return f"{len(res)} items"
    return f"{len(str(res))} chars"


def call(name, args, ui=None, live=None):
    """Run a tool; returns (result_text, exhibit or None). ui handles the UI-only tools."""
    t0 = time.monotonic()
    args = args or {}
    from . import events
    eid = events.next_id()
    events.emit("tool.start", id=eid, name=name, args="(private)" if name in PRIVATE_ARGS else events.summary(args))
    try:
        if name in ("show_hologram", "open_gallery", "set_voice", "remember", "forget") or name.startswith("build_"):
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
        ms = int((time.monotonic() - t0) * 1000)
        _audit(name, args, True, ms, len(text))
        events.emit("tool.end", id=eid, name=name, ok=True, ms=ms, outcome=_outcome(res))
        if name.startswith("vault_"):
            events.emit("vault.op", op=name[6:], path=args.get("path") or args.get("dst"), key=args.get("key"))
        from .track import note_outside
        note_outside(name, args)
        ex = EXHIBIT.get(name)
        return text, ex
    except Exception as e:
        ms = int((time.monotonic() - t0) * 1000)
        _audit(name, args, False, ms, err=e)
        events.emit("tool.end", id=eid, name=name, ok=False, ms=ms, outcome=f"{type(e).__name__}: {str(e)[:100]}")
        return json.dumps({"error": f"{type(e).__name__}: {str(e)[:300]}"}), None
