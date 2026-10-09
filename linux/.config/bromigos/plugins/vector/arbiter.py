"""ARBITER for VECTOR: my trading system's read views, its hologram readings, its decks, its
place in his briefs and his prompt. bromigos-vector is generic; this is mine (its seam:
bromigos-vector docs/plugins.md).

  * the `arbiter` tool: a fixed table of console GET paths (paper trading; never trades,
    arms or touches live/*), with the monolith as its hologram and a mood from the risk;
  * the `arbiter` feed: the monolith's parts (arb.*) lit by the console's readings;
  * the ARBITER and replay decks (my live-layer plugins, ../live/) for hologram_deck;
  * the switchboard's `arbiter` link, the brief's paper results and its CI repos;
  * his prompt's lines on ARBITER, and the floor voice's word for it.

Real money is not here: ARBITER's live workload, routes, console and code are named in
../../vector/vector.toml [real_money], where VECTOR's limits read them. The console's
address comes from the private overlay (endpoints.arbiter); without it this plugin adds
nothing. It never writes: every request is a GET.
"""
import json
import os
import ssl
import urllib.parse
import urllib.request

try:
    import bromigos_private as PRIV
except ImportError:          # no bromigos-core here
    PRIV = None

CA = os.path.expanduser("~/.config/homelab/homelab-ca.crt")
VIEWS = {  # name -> (path, what it is)
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
KEYS = ["arb.referee", "arb.research", "arb.positions", "arb.forward", "arb.agents", "arb.portfolio"]


def console():
    return (PRIV.url("arbiter") if PRIV else "") or ""


def get_json(url, timeout=12):
    if not url or url.startswith("/"):
        raise OSError("that service isn't configured on this machine (private overlay endpoints)")
    ctx = ssl.create_default_context(cafile=CA) if os.path.exists(CA) else ssl.create_default_context()
    req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return json.load(r)


# ------------------------------------------------------------------ the tool
def arbiter(view, key=None):
    base = console()
    if view == "cause_detail":
        if not key or len(key) > 200:
            raise ValueError("cause_detail needs a key from the causes view")
        return get_json(base + "/api/causes/detail?" + urllib.parse.urlencode({"key": key}), timeout=25)
    if view not in VIEWS:
        raise ValueError(f"view must be one of {sorted(VIEWS)} or cause_detail")
    d = get_json(base + VIEWS[view][0], timeout=25)
    if view == "now":
        r = d.get("research") or {}
        r["findings"] = [{k: f.get(k) for k in ("title", "verdict", "summary", "kind") if k in f}
                         for f in (r.get("findings") or [])[:8]]
    if view == "positions":
        d.pop("forward_exposure", None)
    return d


def mood(d):
    """A drawdown near its cuts is concerning; past its floor, alarming."""
    if not isinstance(d, dict):
        return None
    risk = d.get("risk") or {}
    dd, cuts, floor = risk.get("drawdown"), risk.get("cuts_at"), risk.get("floor_at")
    if dd is not None and floor and dd >= floor:
        return "alarmed"
    if dd is not None and cuts and dd >= 0.8 * cuts:
        return "concerned"
    return None


# ------------------------------------------------------------------ the monolith's readings
def read():
    out = {}
    for k, p in (("now", "/api/overview/now"), ("overview", "/api/overview"), ("positions", "/api/positions")):
        try:
            out[k] = get_json(console() + p, timeout=20)
        except Exception as e:
            out[k + "_err"] = str(e)[:80]
    if not any(k in out for k in ("now", "overview", "positions")):
        raise RuntimeError(out.get("now_err", "unreachable"))
    return out


def _money(v):
    return f"${v:,.0f}" if abs(v) >= 100 else f"${v:,.2f}"


def _lvl(v, warn, crit):
    if v is None:
        return "off"
    return "crit" if v >= crit else "warn" if v >= warn else "ok"


def reading(key, A):
    now, ov, pos = A.get("now") or {}, A.get("overview") or {}, A.get("positions") or {}
    ag, co, rs = now.get("agents") or {}, now.get("cohort") or {}, now.get("research") or {}
    risk, ex = ov.get("risk") or {}, ov.get("exposure") or {}
    if key == "arb.referee":
        return ("ok", 0.7, [f"cohort {co.get('state', '?')}  day {co.get('days', 0)} of {co.get('min_days', 0)}",
                            f"allocator {(ex.get('why_cash') or {}).get('allocator', '?')}",
                            f"real money {'NONE' if not ag.get('real_money') else ag.get('real_money')}  (paper)"])
    if key == "arb.research":
        cnt = rs.get("counts") or {}
        k = rs.get("kiln") or {}
        return ("ok", 0.6, [f"{len(rs.get('findings') or [])} findings this week",
                            f"{cnt.get('supported', 0)} supported, {cnt.get('rejected', 0)} rejected",
                            f"Kiln tested {k.get('tested', 0):,}"])
    if key == "arb.positions":
        ps = pos.get("positions") or []
        upnl = sum(p.get("unrealized_usd") or 0 for p in ps)
        return (("ok" if upnl >= 0 else "warn"), min(len(ps) / 12, 1) + 0.2,
                [f"{len(ps)} open  invested {_money(pos.get('invested_usd') or 0)}",
                 f"unrealized {'+' if upnl >= 0 else ''}{_money(upnl)}"] +
                [f"{p.get('instrument')} {p.get('side')} {_money(p.get('notional_usd') or 0)}" for p in
                 sorted(ps, key=lambda p: -abs(p.get("notional_usd") or 0))[:2]])
    if key == "arb.forward":
        ft = pos.get("forward_tests") or {}
        return "ok", 0.6, [f"{ft.get('books', 0)} books forward-testing", f"{ft.get('open_positions', 0):,} open positions"]
    if key == "arb.agents":
        return ("ok", 0.6, [f"{ag.get('all', 0)} agents  {ag.get('rule', 0)} rule, {ag.get('learning', 0)} learning",
                            f"{ag.get('eligible', 0)} eligible  {ag.get('funded', 0)} funded"])
    if key == "arb.portfolio":
        dd = risk.get("drawdown") or 0
        return (_lvl(dd, risk.get("cuts_at", 0.05) * 0.8, risk.get("floor_at", 0.15)), 0.7,
                [f"equity {_money(ex.get('equity') or pos.get('portfolio_equity') or 0)}",
                 f"drawdown {dd * 100:.1f}%  (cuts at {risk.get('cuts_at', 0) * 100:.0f}%)",
                 f"cash {(ex.get('cash_pct') or 0) * 100:.0f}%"])
    return None


# ------------------------------------------------------------------ his prompt
PERSONA = [
    "Any fact about ARBITER comes from the arbiter tool, called in THIS turn.",
    "ARBITER is read only for you: there is no paper-side write path, and nudges (encourage, avoid, exits, "
    "trades) are [[ref's]], behind [[his]] sign-in.",
    "ARBITER is paper trading on the Floor. It reads the tape like everyone else. Never claim it, or you, can hear "
    "the future.",
    "In the station's story, the Floor is ARBITER, and the replay deck plays back one of its paper trades.",
]


def register(vector):
    if not hasattr(vector, "feed"):          # a bromigos-vector from before plugins could bring a system
        return
    url = console()
    if not url:
        return
    vector.tool("arbiter", "ARBITER market floor, read-only console views (paper trading; never trades or arms). "
                "view: " + ", ".join(sorted(VIEWS)) + ", cause_detail (needs key from causes).",
                {"type": "object", "properties": {"view": {"type": "string"}, "key": {"type": "string"}},
                 "required": ["view"]},
                arbiter, level="read", exhibit=("monolith", ["plinth", "slab3", "crown"]), mood=mood, mcp=True)
    vector.feed("arbiter", read, prefix="arb.", reading=reading, label="ARBITER (read only)", every=30.0, keys=KEYS)
    vector.deck("arbiter", about="open/close only: ARBITER's paper portfolio")
    vector.deck("replay", verbs=("pick", "play", "pause", "seek"),
                about="pick <latest, biggest, instrument, agent or fill id>, play, pause, seek <0..1>: an ARBITER "
                      "paper trade")
    vector.switchboard("arbiter", url)
    vector.briefing("arbiter_paper", lambda: arbiter("performance"), about="ARBITER's paper results",
                    repos=["bromigos-org/homelab", "bromigos-org/arbiter", "bromigos-org/platform"])
    for line in PERSONA:
        vector.persona(line)
    vector.words("floor", ["arbiter"])
