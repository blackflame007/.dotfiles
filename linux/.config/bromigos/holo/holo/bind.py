"""Part bindings: what each model part shows. `reading(bind, live)` returns
(level, value, lines): level in ok|warn|crit|off drives the part's colour, value in
0..1 drives its brightness, lines are the callout text (first line is the headline).

SOURCES maps a model to the live sources it needs, so the gallery only polls what is
on the table."""
import time

SOURCES = {"workstation": ("local",), "wick": ("lab",), "rack": ("lab",), "emblem": ("lab",),
           "monolith": ("arbiter",), "vector": ()}


PREFIX_SOURCE = {"ws.": "local", "wick.": "lab", "rack.": "lab", "emb.": "lab", "arb.": "arbiter"}
def _all_keys():
    """Every reading a part can bind to, read from this file's own handlers (so the list can't
    drift from what reading() answers): local (ws.*), lab (wick.*, rack.*, emb.*), arbiter (arb.*)."""
    import os
    import re as _re
    src = open(os.path.abspath(__file__)).read()
    found = set()
    for m in _re.finditer(r'key\s*(?:==|in)\s*(\([^)]*\)|"[a-z]+\.[a-z_]+")', src):
        found.update(_re.findall(r'"([a-z]+\.[a-z_]+)"', m.group(1)))
    out = {"local": [], "lab": [], "arbiter": []}
    for k in sorted(found):
        out[PREFIX_SOURCE.get(k.split(".")[0] + ".", "lab")].append(k)
    return out


KEYS = _all_keys()


def sources(name, parts=None):
    """The live sources a model needs: the table above for the built-in models, else
    inferred from its parts' bind prefixes (so a new model needs no code change)."""
    if name in SOURCES:
        return SOURCES[name]
    if parts is None:
        try:
            from . import fmt
            parts = fmt.load(name).parts
        except Exception:
            parts = []
    out = []
    for p in parts:
        b = p.get("bind") or ""
        for pre, src in PREFIX_SOURCE.items():
            if b.startswith(pre) and src not in out:
                out.append(src)
    return tuple(out)


def gib(b):
    return f"{b / 2**30:.1f}"


def rate(bps):
    for unit, d in (("GB/s", 1e9), ("MB/s", 1e6), ("KB/s", 1e3)):
        if bps >= d:
            return f"{bps / d:.1f} {unit}"
    return f"{bps:.0f} B/s"


def bits(bps):
    for unit, d in (("Gb/s", 1e9), ("Mb/s", 1e6), ("kb/s", 1e3)):
        if bps * 8 >= d:
            return f"{bps * 8 / d:.1f} {unit}"
    return f"{bps * 8:.0f} b/s"


def lvl(v, warn, crit):
    if v is None:
        return "off"
    return "crit" if v >= crit else "warn" if v >= warn else "ok"


def dur(s):
    d, h, m = int(s // 86400), int(s % 86400 // 3600), int(s % 3600 // 60)
    return f"{d}d {h}h" if d else f"{h}h {m}m"


def money(v):
    return f"${v:,.0f}" if abs(v) >= 100 else f"${v:,.2f}"


def _ws(key, L):
    if key == "ws.cpu":
        t = L.get("cpu_temp")
        return (max(lvl(L["cpu"], 75, 92), lvl(t, 80, 90), key=["off", "ok", "warn", "crit"].index),
                L["cpu"] / 100, [f"{L['cpu']:.0f}%  peak core {L['cpu_max']:.0f}%",
                                 (f"{t:.0f}°C  " if t else "") + (f"{L['freq'] / 1000:.2f} GHz" if L.get("freq") else ""),
                                 f"{L['cores']} threads  load {L['load'][0]:.2f}"])
    if key == "ws.ram":
        return (lvl(L["mem_pct"], 80, 93), L["mem_pct"] / 100,
                [f"{gib(L['mem_used'])} / {gib(L['mem_total'])} GiB  {L['mem_pct']:.0f}%",
                 f"swap {gib(L['swap_used'])} GiB"])
    if key == "ws.gpu":
        g = L.get("gpu")
        if not g:
            return "off", 0, ["no NVML"]
        vp = 100 * g["vram_used"] / max(g["vram_total"], 1)
        return (max(lvl(g["util"], 85, 98), lvl(g["temp"], 78, 86), key=["off", "ok", "warn", "crit"].index),
                g["util"] / 100, [f"{g['name']}  {g['util']}%",
                                  f"VRAM {gib(g['vram_used'])} / {gib(g['vram_total'])} GiB",
                                  f"{g['temp']}°C  {g['watts']:.0f} W" + (f"  fan {g['fan']}%" if g.get("fan") is not None else "")])
    if key == "ws.disks":
        ds = L["disks"][:3]
        if not ds:
            return "off", 0, ["no disks"]
        top = ds[0]
        return (lvl(top["pct"], 85, 95), top["pct"] / 100,
                [f"{d['mount']}  {d['pct']:.0f}%  of {d['total'] / 1e12:.1f} TB" if d["total"] > 1e12 else
                 f"{d['mount']}  {d['pct']:.0f}%  of {d['total'] / 1e9:.0f} GB" for d in ds]
                + [f"read {rate(L['disk_rd'])}  write {rate(L['disk_wr'])}"])
    if key == "ws.fans":
        fs = sorted(L["fans"], key=lambda f: -f[1])[:3]
        if not fs:
            return "off", 0.2, ["no fan sensors"]
        return "ok", min(fs[0][1] / 2000, 1), [f"{n.lower()}  {rpm:.0f} rpm" for n, rpm in fs]
    if key == "ws.net":
        tot = L["net_rx"] + L["net_tx"]
        return "ok", min(tot / 12.5e6, 1), [f"down {bits(L['net_rx'])}", f"up {bits(L['net_tx'])}"]
    if key == "ws.power":
        g = L.get("gpu") or {}
        return "ok", min((g.get("watts") or 0) / 250, 1), [f"GPU board {g.get('watts', 0):.0f} W",
                                                            f"up {dur(L['uptime'])}"]
    if key == "ws.host":
        return "ok", 0.4, [f"{L['host']}", f"kernel {L['kernel']}",
                           "load " + " ".join(f"{x:.2f}" for x in L["load"])]


def _lab(key, D):
    c, net, svc = D.get("cluster") or {}, D.get("network") or {}, D.get("services") or {}
    down = [k for k, v in svc.items() if v.get("status") != "up"]
    nodes_ok = c.get("nodesReady") == c.get("nodesTotal") and c.get("nodesTotal")
    beam = (not down) and nodes_ok
    g = D.get("gpu") or {}
    nas = D.get("nas") or {}
    pool = nas.get("pool") or {}
    if key in ("wick.beam", "emb.flame"):
        return ("ok" if beam else "crit", 1.0 if beam else 0.3,
                ["BEAM LIT" if beam else "BEAM DARK",
                 f"{len(svc) - len(down)} / {len(svc)} services answering"] + ([f"down: {', '.join(down[:4])}"] if down else []))
    if key == "emb.gap":
        return ("ok" if not down else "warn", (len(svc) - len(down)) / max(len(svc), 1),
                [f"{len(svc) - len(down)} of {len(svc)} channels answering"])
    if key in ("wick.racks", "emb.mast", "rack.nodes"):
        nodes = sorted(D.get("nodes") or [], key=lambda n: -(n.get("cpuPct") or 0))
        lines = [f"{c.get('nodesReady', 0):.0f} / {c.get('nodesTotal', 0):.0f} nodes ready",
                 f"{c.get('podsRunning', 0):.0f} pods running" + (f", {c.get('podsNotRunning', 0):.0f} not" if c.get("podsNotRunning") else "")]
        if key == "rack.nodes" and nodes:
            lines += [f"{n['name']}  cpu {n.get('cpuPct', 0):.0f}%  mem {n.get('memPct', 0):.0f}%" for n in nodes[:2]]
        if key == "wick.racks":
            lines.append(f"{c.get('alertsFiring', 0):.0f} alerts firing")
        return ("ok" if nodes_ok else "crit", (c.get("cpuNow") or 0) / 100 + 0.4, lines)
    if key == "emb.ring":
        return "ok", 0.6, ["NO ONE OWNS THE DARK", "turns once every 24 s"]
    if key in ("wick.wan",):
        return ("ok", min((net.get("wanDownBps", 0) + net.get("wanUpBps", 0)) / 50e6, 1),
                [f"WAN down {bits(net.get('wanDownBps', 0))}", f"WAN up {bits(net.get('wanUpBps', 0))}"])
    if key in ("wick.lan", "rack.switch"):
        lines = [f"{net.get('clients', 0):.0f} clients" + (f", {net.get('guests', 0):.0f} guests" if net.get("guests") else ""),
                 f"ISP latency {net.get('ispLatencyMs', 0):.0f} ms"]
        if key == "rack.switch":
            tr = D.get("traefik") or {}
            lines.append(f"ingress {tr.get('rpsNow', 0):.2f} req/s")
        return lvl(net.get("ispLatencyMs"), 40, 120), 0.6, lines
    if key in ("wick.solar", "wick.solar2"):
        s = D.get("solar") or {}
        if key == "wick.solar":
            return ("ok", min(s.get("productionW", 0) / 6000, 1) + 0.15,
                    [f"producing {s.get('productionW', 0) / 1000:.2f} kW", f"today {s.get('energyTodayWh', 0) / 1000:.1f} kWh"])
        return "ok", 0.4, [f"lifetime {s.get('lifetimeWh', 0) / 1e6:.1f} MWh", f"status {s.get('status', '?')}"]
    if key in ("wick.vault",):
        pct = 100 * pool.get("used", 0) / max(pool.get("total", 1), 1)
        disks = nas.get("disks") or []
        bad = [d for d in disks if d.get("health") != "good"]
        return (lvl(pct, 85, 95) if not bad else "crit", pct / 100,
                [f"NAS pool {pct:.0f}%  of {pool.get('total', 0) / 1e12:.0f} TB",
                 f"{len(disks)} disks, {len(bad)} unhealthy"])
    if key == "rack.storage":
        pct = 100 * pool.get("used", 0) / max(pool.get("total", 1), 1)
        nd = sorted(D.get("nodeDisks") or [], key=lambda d: -d.get("pct", 0))
        lines = [f"NAS pool {pct:.0f}%  ({pool.get('raidMembers', 0)} drives)"]
        if nd:
            lines.append(f"{nd[0]['node']}  disk {nd[0]['pct']:.0f}%")
        return max(lvl(pct, 85, 95), lvl(nd[0]["pct"] if nd else None, 85, 95), key=["off", "ok", "warn", "crit"].index), pct / 100, lines
    if key == "wick.hull":
        p = D.get("proxmox") or {}
        return (lvl(p.get("memPct"), 92, 97), (p.get("cpuPct") or 0) / 100 + 0.3,
                [f"hypervisor cpu {p.get('cpuPct', 0):.0f}%  mem {p.get('memPct', 0):.0f}%",
                 f"{sum(1 for v in p.get('vms', []) if v.get('status') == 'running')} VMs running"])
    if key == "rack.gpu":
        vp = 100 * g.get("vramUsed", 0) / max(g.get("vramTotal", 1), 1)
        ai = D.get("ai") or {}
        return (lvl(g.get("tempC"), 80, 88), (g.get("utilNow") or 0) / 100 + 0.3,
                [f"{g.get('count', 0)} GPUs  util {g.get('utilNow', 0):.0f}%",
                 f"VRAM {vp:.0f}%  {g.get('tempC', 0):.0f}°C  {g.get('powerW', 0):.0f} W",
                 f"models {sum(1 for m in ai.get('models', []) if m.get('up'))} up  {ai.get('rpmNow', 0):.1f} req/min"])
    if key == "rack.power":
        return "ok", 0.5, [f"PoE {net.get('poeWatts', 0):.0f} W", f"GPUs {g.get('powerW', 0):.0f} W"]
    if key == "rack.frame":
        a = D.get("argocd") or {}
        al = c.get("alertsFiring", 0)
        return (("warn" if al else "ok") if a.get("healthy") == a.get("total") else "warn", 0.4,
                [f"Argo CD {a.get('healthy', 0)} / {a.get('total', 0)} healthy", f"{al:.0f} alerts firing"])


def _arb(key, A):
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
                [f"{len(ps)} open  invested {money(pos.get('invested_usd') or 0)}",
                 f"unrealized {'+' if upnl >= 0 else ''}{money(upnl)}"] +
                [f"{p.get('instrument')} {p.get('side')} {money(p.get('notional_usd') or 0)}" for p in
                 sorted(ps, key=lambda p: -abs(p.get("notional_usd") or 0))[:2]])
    if key == "arb.forward":
        ft = pos.get("forward_tests") or {}
        return "ok", 0.6, [f"{ft.get('books', 0)} books forward-testing", f"{ft.get('open_positions', 0):,} open positions"]
    if key == "arb.agents":
        return ("ok", 0.6, [f"{ag.get('all', 0)} agents  {ag.get('rule', 0)} rule, {ag.get('learning', 0)} learning",
                            f"{ag.get('eligible', 0)} eligible  {ag.get('funded', 0)} funded"])
    if key == "arb.portfolio":
        dd = risk.get("drawdown") or 0
        return (lvl(dd, risk.get("cuts_at", 0.05) * 0.8, risk.get("floor_at", 0.15)), 0.7,
                [f"equity {money(ex.get('equity') or pos.get('portfolio_equity') or 0)}",
                 f"drawdown {dd * 100:.1f}%  (cuts at {risk.get('cuts_at', 0) * 100:.0f}%)",
                 f"cash {(ex.get('cash_pct') or 0) * 100:.0f}%"])


def reading(key, live):
    """-> (level, value 0..1, [lines], age_seconds or None)"""
    try:
        if key.startswith("ws."):
            d, err, at = live.get("local")
            if d is None:
                return "off", 0.2, ["reading…" if not err else f"no data: {err}"], None
            r = _ws(key, d)
        elif key.startswith(("wick.", "rack.", "emb.")):
            d, err, at = live.get("lab")
            if d is None:
                return "off", 0.2, ["reading…" if not err else f"Lab unreachable: {err[:40]}"], None
            r = _lab(key, d)
        elif key.startswith("arb."):
            d, err, at = live.get("arbiter")
            if d is None:
                return "off", 0.2, ["reading…" if not err else f"ARBITER unreachable: {err[:40]}"], None
            r = _arb(key, d)
        else:
            return "off", 0.2, [""], None
    except Exception as e:  # a reading that cannot be computed says so
        return "off", 0.2, [f"? {type(e).__name__}: {str(e)[:40]}"], None
    if r is None:
        return "off", 0.2, ["—"], None
    level, v, lines = r
    return level, max(0.0, min(1.0, v)), [x for x in lines if x], time.time() - at if at else None
