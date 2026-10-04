"""Hologram models from the brand kit (bromigos-holo/1, *.holo.npz — see
~/.config/bromigos/holo/holo/fmt.py): feature edges drawn as 1 px lines,
each part lit by a live reading and exploding along its own offset like a
suit diagnostic. Readings are real: this machine for the workstation, the lab
(EchoCraft /api/status) for the rack and the Wick, ARBITER for the monolith;
the emblem is identity, not data, and says so."""
import json
import math
import os

import numpy as np

from .gadgets import fmt_bytes, fmt_rate, pct, temp
from .glkit import col

DIR = os.path.expanduser("~/.config/bromigos/brand/3d/holo")
ORDER = ["workstation", "rack", "wick", "monolith", "emblem"]


class Model:
    def __init__(self, path):
        with np.load(path) as d:
            self.meta = json.loads(bytes(d["meta"]).decode())
            self.pos = d["pos"].astype(np.float32)
            self.part = d["part"].astype(np.int32)
            self.edge = d["edge"].astype(np.int64)
        self.name = self.meta.get("name") or os.path.basename(path).split(".")[0]
        self.parts = self.meta.get("parts") or []
        h = float(self.meta.get("height") or self.pos[:, 1].max() or 1.0)
        self.center = np.array([0.0, h / 2.0, 0.0], dtype=np.float32)
        self.scale = 1.0 / max(h, float(self.meta.get("radius") or 0.5) * 1.6)

    def p(self, v):
        return tuple(float(x) for x in (np.asarray(v, dtype=np.float32) - self.center) * self.scale)

    def offset(self, i, amount):
        e = np.asarray(self.parts[i].get("explode") or [0, 0, 0], dtype=np.float32)
        return e * amount * self.scale

    def line_array(self, space, t0=0.0, alpha=0.9):
        """Every feature edge as a line instance tagged with its part, built in
        one numpy pass (the explode is a per-part shader offset, so this is
        uploaded once per model). Layout matches glkit.Batch.line."""
        P = (self.pos - self.center) * self.scale
        a, c = self.edge[:, 0], self.edge[:, 1]
        n = len(a)
        out = np.zeros((n, 20), dtype=np.float32)
        out[:, 0:3] = P[a]
        out[:, 3] = space
        out[:, 4:7] = P[c]
        out[:, 7] = 1.0
        out[:, 8:12] = col("phosphor", alpha)
        out[:, 12] = self.part[a]
        # assembly: edges draw in sorted bottom-up, part by part
        order = np.argsort(P[a][:, 1] + self.part[a] * 0.02)
        rv = np.empty(n, dtype=np.float32)
        rv[order] = t0 + 0.15 + 1.1 * np.arange(n) / max(n, 1)
        out[:, 13] = rv if t0 else 0.0
        out[:, 15] = 1.0
        out[:, 16] = space
        out[:, 17] = 1.0
        return out


def available():
    out = []
    for n in ORDER:
        f = os.path.join(DIR, f"{n}.holo.npz")
        if os.path.exists(f):
            out.append(n)
    return out


def load(name):
    return Model(os.path.join(DIR, f"{name}.holo.npz"))


# ---------------------------------------------------------------- readings
def _lin(v, a, b):
    return 0.0 if v is None else max(0.0, min(1.0, (v - a) / (b - a)))


def readings(bind, d, st, arb=None):
    """(lines, intensity 0..1, heat 0..1) for a part's bind name."""
    cl = d.get("cluster") or {}
    c = cl.get("cluster") or {}
    if bind == "ws.cpu":
        return ([f"LOAD {pct(d.get('cpu'))} · {temp(d.get('cpu_temp'))}",
                 f"{st['cpu_model'].upper()[:34]}", f"{st['cores_phys']}C / {st['threads']}T"],
                0.5 + 0.5 * _lin(d.get("cpu"), 0, 100), _lin(d.get("cpu_temp"), 60, 90))
    if bind == "ws.ram":
        return ([f"{fmt_bytes(d.get('mem_used'))} / {fmt_bytes(d.get('mem_total'))} ({pct(d.get('mem'))})",
                 f"SWAP {pct(d.get('swap'))}"], 0.5 + 0.5 * _lin(d.get("mem"), 0, 100), _lin(d.get("mem"), 85, 98))
    if bind == "ws.gpu":
        vt = d.get("vram_total")
        return ([f"LOAD {pct(d.get('gpu'))} · {temp(d.get('gpu_temp'))} · {(d.get('gpu_power') or 0):.0f} W",
                 f"VRAM {(d.get('vram_used') or 0) / 1024:.1f} / {(vt or 0) / 1024:.0f} GB",
                 st["gpu_name"].upper()[:34]], 0.5 + 0.5 * _lin(d.get("gpu"), 0, 100), _lin(d.get("gpu_temp"), 60, 88))
    if bind == "ws.disks":
        ms = sorted(d.get("mounts") or [], key=lambda m: -m["pct"])[:3]
        io = sum((x.get("r", 0) + x.get("w", 0)) for x in (d.get("disks") or {}).values())
        nv = d.get("nvme_temps") or {}
        hot = max(nv.values()) if nv else None
        return ([f"{m['mount']} {m['pct']:.0f}% FULL" for m in ms] + [f"I/O {fmt_rate(io)} · NVME {temp(hot)}"],
                0.5 + 0.5 * min(math.log10(1 + io) / 8, 1), _lin(hot, 55, 75))
    if bind == "ws.fans":
        return ([f"GPU FAN {pct(d.get('gpu_fan'))}", f"BOARD {temp(d.get('board_temp'))}",
                 "CASE FANS: NO TELEMETRY"], 0.45 + 0.55 * _lin(d.get("gpu_fan"), 0, 100), _lin(d.get("board_temp"), 50, 75))
    if bind == "ws.net":
        rx, tx = d.get("rx") or 0, d.get("tx") or 0
        return ([f"IN {fmt_rate(rx)}", f"OUT {fmt_rate(tx)}"], 0.45 + 0.55 * min(math.log10(1 + rx + tx) / 7.5, 1), 0.0)
    if bind == "ws.power":
        return ([f"GPU DRAW {(d.get('gpu_power') or 0):.0f} W", "PSU: NO TELEMETRY"],
                0.4 + 0.6 * _lin(d.get("gpu_power"), 0, 250), 0.0)
    if bind == "ws.host":
        return ([f"{st['sys'].upper()} {st['kernel']}", "ECHOBASE"], 0.55, 0.0)
    # ---- the lab
    nodes = cl.get("nodes") or []
    svc = cl.get("services") or {}
    up = sum(1 for v in svc.values() if (v or {}).get("status") == "up")
    green = bool(svc) and up == len(svc)
    if not cl and (bind.startswith(("rack.", "wick.")) or bind in ("emb.flame", "emb.mast")):
        return (["NO LAB SNAPSHOT"], 0.3, 0.5)
    if bind in ("rack.nodes", "wick.racks"):
        worst = max([max(n.get("cpuPct") or 0, n.get("memPct") or 0) for n in nodes] or [0])
        return ([f"NODES {c.get('nodesReady', '?')}/{c.get('nodesTotal', '?')} READY · PODS {c.get('podsRunning') or 0:.0f}"]
                + [f"{n['name'].upper()[:16]} CPU {pct(n.get('cpuPct'))} MEM {pct(n.get('memPct'))}" for n in nodes[:4]],
                0.5 + 0.5 * _lin(c.get("cpuNow"), 0, 100),
                (0.5 if c.get("nodesReady") is None or c.get("nodesTotal") is None      # unknown: amber
                 else _lin(worst, 85, 98) if c.get("nodesReady") == c.get("nodesTotal") else 1.0))
    if bind in ("rack.gpu",):
        g = cl.get("gpu") or {}
        return ([f"LAB GPU {pct(g.get('utilNow'))} · {temp(g.get('tempC'))} · {(g.get('powerW') or 0):.0f} W",
                 f"VRAM {fmt_bytes(g.get('vramUsed'))} / {fmt_bytes(g.get('vramTotal'))}"],
                0.5 + 0.5 * _lin(g.get("utilNow"), 0, 100), _lin(g.get("tempC"), 70, 88))
    if bind in ("rack.storage", "wick.vault"):
        nas = cl.get("nas") or {}
        pool = nas.get("pool") or {}
        used, total = pool.get("used"), pool.get("total")
        p = (used / total * 100) if used and total else None
        return ([f"NAS {fmt_bytes(used)} / {fmt_bytes(total)} ({pct(p)})" if total else "NAS: NO READING"],
                0.55, _lin(p, 80, 95))
    if bind in ("rack.switch", "wick.lan"):
        net = cl.get("network") or {}
        return ([f"CLIENTS {net.get('clients') or 0:.0f} · ISP {net.get('ispLatencyMs') or 0:.0f} MS",
                 f"POE {net.get('poeWatts') or 0:.0f} W"], 0.6, 0.0)
    if bind in ("wick.wan",):
        net = cl.get("network") or {}
        return ([f"WAN ↓ {fmt_bytes((net.get('wanDownBps') or 0) / 8, 'B/S')} ↑ {fmt_bytes((net.get('wanUpBps') or 0) / 8, 'B/S')}"],
                0.45 + 0.55 * min(math.log10(1 + (net.get("wanDownBps") or 0)) / 9, 1), 0.0)
    if bind in ("rack.power", "wick.solar", "wick.solar2"):
        so = cl.get("solar") or {}
        prod = so.get("productionW")
        return ([f"SOLAR {prod:.0f} W" if isinstance(prod, (int, float)) else "SOLAR: NO READING",
                 f"PROXMOX CPU {pct((cl.get('proxmox') or {}).get('cpuPct'))}"], 0.5, 0.0)
    if bind in ("wick.beam", "emb.flame"):
        return ([f"SERVICES {up}/{len(svc)} UP", "RELAY BEAM " + ("UP" if green else "DOWN")],
                1.0 if green else 0.5, 0.0 if green else 1.0)
    if bind in ("wick.hull", "rack.frame"):
        return ([f"ALERTS FIRING {c.get('alertsFiring') or 0:.0f}", f"ARGO {(cl.get('argocd') or {}).get('healthy', '?')}"
                 f"/{(cl.get('argocd') or {}).get('total', '?')}"], 0.55, _lin(c.get("alertsFiring"), 5, 20))
    if bind == "emb.mast":
        return ([f"NODES {c.get('nodesReady', '?')}/{c.get('nodesTotal', '?')} READY"], 0.7, 0.0)
    if bind.startswith("emb."):
        return (["IDENTITY · NOT DATA"], 0.6, 0.0)
    # ---- ARBITER (the monolith)
    if bind.startswith("arb."):
        if not arb:
            return (["CONTACTING THE FLOOR…"], 0.35, 0.0)
        now = arb.get("now") or {}
        ov = arb.get("overview") or {}
        ag = now.get("agents") or {}
        if bind == "arb.portfolio":
            ex = ov.get("exposure") or {}
            dd = (ov.get("risk") or {}).get("drawdown")
            return ([f"PAPER EQUITY ${ex.get('equity') or 0:,.0f}", f"DRAWDOWN {(dd or 0) * 100:.1f}%",
                     "REAL MONEY: OFF · NOT ARMED"], 0.7, _lin(dd, 0.03, 0.05))
        if bind == "arb.agents":
            return ([f"{ag.get('all', '?')} AGENTS · {ag.get('rule', '?')} RULE · {ag.get('learning', '?')} LEARNING",
                     f"{ag.get('holding', '?')} HOLDING"], 0.65, 0.0)
        if bind == "arb.forward":
            return ([f"{len(now.get('forward') or [])} FORWARD TESTS"], 0.55, 0.0)
        if bind == "arb.positions":
            return ([f"{ag.get('positions', '?')} AGENT POSITIONS"], 0.6, 0.0)
        if bind == "arb.research":
            k = (now.get("research") or {}).get("kiln") or {}
            return ([f"KILN {k.get('tested', '?')} TESTED · {k.get('promoted', '?')} PROMOTED"], 0.55, 0.0)
        if bind == "arb.referee":
            co = now.get("cohort") or {}
            return ([f"LINEUP DAY {co.get('days', '?')} OF {co.get('min_days', '?')}", f"FUNDED {ag.get('funded', '?')}"],
                     0.75, 0.0)
    return (["NO BINDING"], 0.4, 0.0)
