"""The desktop panels. Each one draws real readings only; every hoverable region
carries a tooltip saying what it is, and clickable ones say what a click does."""
import math
import subprocess
import time

import cairo

import draw as D
import sources as S


def open_url(url):
    subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


def copy_text(s):
    subprocess.Popen(["wl-copy", s], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class Panel:
    name = "panel"
    title = "PANEL"
    width = 470
    height = 200
    interval = 2.0                      # seconds between samples

    def __init__(self, cfg=None):
        self.cfg = cfg or {}
        self.regions = []               # (x, y, w, h, tooltip, action-or-None)
        self.animating = False          # True while a short animation wants ~15 fps

    def region(self, x, y, w, h, tip, action=None):
        self.regions.append((x, y, w, h, tip, action))

    def hit(self, x, y):
        for r in reversed(self.regions):
            if r[0] <= x <= r[0] + r[2] and r[1] <= y <= r[1] + r[3]:
                return r
        return None

    def tick(self):
        """Sample data. Called every `interval` seconds even while covered (cheap)."""

    def render(self, cr, w, h):
        self.regions = []
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        self.draw(cr, w, h)

    def draw(self, cr, w, h):
        raise NotImplementedError


# =================================================================== SYSTEM
class SystemPanel(Panel):
    name, title = "system", "SYSTEM"
    height = 452
    interval = 2.0

    def __init__(self, cfg=None):
        super().__init__(cfg)
        self.sys = S.System(history=200)   # 200 x 2 s = 6:40 of waterfall

    def tick(self):
        self.sys.sample()

    def draw(self, cr, w, h):
        s = self.sys
        top = D.frame(cr, w, h, self.title, f"{s.host} · {s.os} {s.kernel.split('-')[0]}")
        self.region(0, 0, w, 34, f"This machine: host {s.host}, {s.os}, kernel {s.kernel}")
        x0, x1 = 16, w - 16

        # --- CPU: segment readout + per-core heat grid
        D.label(cr, x0, top, "CPU", "dim")
        col = D.level(s.total, 70, 90)
        D.seg7(cr, x0, top + 18, 40, f"{s.total:3.0f}", col)
        D.text(cr, x0 + 104, top + 40, "%", 16, col, "bold")
        ctemp = s.temps.get("CPU")
        if ctemp is not None:
            D.label(cr, x0, top + 66, f"TEMP {ctemp:.0f}°C", D.level(ctemp, 80, 90))
        self.region(x0, top, 130, 84, f"CPU load across all {s.cores} threads (2 s average)"
                    + (f"; package temperature {ctemp:.0f} °C (amber 80, red 90)" if ctemp else ""))
        gx, gy = x0 + 146, top + 2
        cols = 8
        rows = math.ceil(s.cores / cols)
        cw, chh, gap = (x1 - gx - (cols - 1) * 4) / cols, 32, 4
        D.label(cr, x1, top, f"{s.cores} THREADS", "dim", align="right")
        gy += 16
        cell_h = (68 - (rows - 1) * gap) / rows if rows else chh
        for i, v in enumerate(s.per):
            r, c = divmod(i, cols)
            cx, cy = gx + c * (cw + 4), gy + r * (cell_h + gap)
            heat = v / 100
            colr = "danger" if v >= 95 else "amber" if v >= 80 else "phosphor"
            D.src(cr, "guard", 0.9)
            cr.rectangle(cx, cy, cw, cell_h)
            cr.fill()
            D.src(cr, colr, 0.15 + 0.85 * heat)
            cr.rectangle(cx, cy + cell_h * (1 - heat), cw, cell_h * heat)
            cr.fill()
            D.text(cr, cx + cw / 2, cy + cell_h / 2 - 7, f"{v:.0f}", 10,
                   "void" if heat > 0.55 else "soft", "semibold", align="center")
            self.region(cx, cy, cw, cell_h, f"CPU thread {i}: {v:.0f}% busy")

        # --- waterfall: per-thread load over time, newest at the right
        wy = top + 98
        D.label(cr, x0, wy, "LOAD WATERFALL", "dim")
        span = len(s.history) * self.interval
        D.label(cr, x1, wy, f"LAST {S.duration(span)}", "static", align="right")
        wy += 18
        wh = 128
        self._waterfall(cr, x0, wy, x1 - x0, wh)
        self.region(x0, wy, x1 - x0, wh, "Load waterfall: one row per CPU thread, one column per 2 s sample, "
                    "brighter = busier; newest at the right")

        # --- memory and GPU fuel cells
        y = wy + wh + 16
        m = s.mem
        self._cellrow(cr, x0, x1, y, "RAM", m.used / m.total,
                      f"{S.human(m.used)} / {S.human(m.total)}",
                      f"Memory in use (excludes cache): {S.human(m.used)} of {S.human(m.total)}; "
                      f"{S.human(m.available)} available. Amber past 75%, red past 90%.")
        y += 38
        g = s.g
        if g:
            self._cellrow(cr, x0, x1, y, "VRAM", g["vram_used"] / g["vram_total"],
                          f"{S.human(g['vram_used'])} / {S.human(g['vram_total'])}",
                          f"{s.gpu.name} video memory: {S.human(g['vram_used'])} of {S.human(g['vram_total'])}")
            y += 38
            gc = D.level(g["util"], 70, 90)
            D.label(cr, x0, y, "GPU", "dim")
            D.text(cr, x0 + 56, y - 3, f"{g['util']:3d}%", 15, gc, "bold", glow=g["util"] > 0)
            D.label(cr, x0 + 130, y, s.gpu.name, "static")
            D.label(cr, x1, y, f"{g['temp']}°C · {g['watts']:.0f} W", D.level(g["temp"], 75, 85), align="right")
            self.region(x0, y - 4, x1 - x0, 22, f"{s.gpu.name}: {g['util']}% busy, {g['temp']} °C, "
                        f"drawing {g['watts']:.0f} W (NVML)")
            y += 30

        # --- footer: load, uptime, session
        D.rule(cr, x0, y - 6, x1)
        la = s.load
        D.label(cr, x0, y + 2, f"LOAD {la[0]:.2f} {la[1]:.2f} {la[2]:.2f}",
                D.level(la[0] / s.cores, 0.7, 1.0))
        self.region(x0, y, 200, 18, "Load average over 1, 5 and 15 minutes "
                    f"(amber past {s.cores * 0.7:.0f}, i.e. 70% of {s.cores} threads)")
        up = time.time() - s.boot
        ses = time.time() - s.session_start
        D.label(cr, x1, y + 2, f"UP {S.duration(up)} · SESSION {S.duration(ses)}", "soft", align="right")
        self.region(x1 - 220, y, 220, 18, f"Uptime since boot {S.duration(up)}; this Hyprland session "
                    f"has run {S.duration(ses)}")
        nv = s.temps.get("NVME")
        if nv is not None:
            pass

    def _cellrow(self, cr, x0, x1, y, name, frac, right, tip):
        D.label(cr, x0, y, name, "dim")
        D.label(cr, x1, y, right, "soft", align="right")
        D.label(cr, x0 + 56, y, f"{frac * 100:.0f}%", D.level(frac, 0.75, 0.9))
        D.cells(cr, x0, y + 17, x1 - x0, 9, frac, n=40)
        self.region(x0, y, x1 - x0, 28, tip)

    def _waterfall(self, cr, x, y, w, h):
        hist = list(self.sys.history)
        n = len(hist)
        cores = self.sys.cores
        D.src(cr, "void", 0.9)
        cr.rectangle(x, y, w, h)
        cr.fill()
        if not n:
            return
        cols = 200
        colw = w / cols
        rowh = h / cores
        start = cols - n
        for i, sample in enumerate(hist):
            cx = x + (start + i) * colw
            for c, v in enumerate(sample):
                if v < 4:
                    continue
                colr = "danger" if v >= 95 else "amber" if v >= 80 else "phosphor"
                D.src(cr, colr, min(1.0, 0.12 + v / 100 * 0.95))
                cr.rectangle(cx, y + c * rowh, colw + 0.4, rowh - 0.6)
        cr.fill()
        cr.set_line_width(1)
        D.src(cr, "dim", 0.45)
        cr.rectangle(x + 0.5, y + 0.5, w - 1, h - 1)
        cr.stroke()


# =================================================================== NETWORK
class NetworkPanel(Panel):
    name, title = "network", "NETWORK"
    height = 262
    interval = 1.0

    def __init__(self, cfg=None):
        super().__init__(cfg)
        self.net = S.Net(history=120)
        targets = [(t["label"], t.get("host")) for t in self.cfg.get("ping", [])] or [("GATEWAY", None)]
        self.ping = S.Pinger(targets, every=6)
        self.ping.start()
        self.sweep = 0.0

    def tick(self):
        self.net.sample()
        self.sweep = (self.sweep + 30) % 360

    def draw(self, cr, w, h):
        n = self.net
        wifi = f" · {n.signal:.0f} dBm" if n.signal is not None else ""
        top = D.frame(cr, w, h, self.title, f"{n.iface or 'NO LINK'}{wifi}",
                      "static" if n.iface else "amber")
        self.region(0, 0, w, 34, (f"Default route via {n.iface}" + (f", Wi-Fi signal {n.signal:.0f} dBm" if wifi else "")
                                  + (f"; address {n.addr} (click to copy)" if n.addr else ""))
                    if n.iface else "No default route: disconnected",
                    (lambda: copy_text(n.addr)) if n.addr else None)
        x0, x1 = 16, w - 16
        scope_w = x1 - x0 - 150
        # --- readouts
        D.label(cr, x0, top, "RX", "dim")
        D.text(cr, x0 + 30, top - 3, S.rate(n.rx), 14, "phosphor", "bold", glow=n.rx > 1024)
        D.label(cr, x0 + scope_w / 2 + 10, top, "TX", "dim")
        D.text(cr, x0 + scope_w / 2 + 40, top - 3, S.rate(n.tx), 14, "soft", "bold", glow=n.tx > 1024)
        self.region(x0, top - 4, scope_w, 22, f"Live throughput on {n.iface}: receive {S.rate(n.rx)}, "
                    f"transmit {S.rate(n.tx)} (1 s)")
        # --- oscilloscope
        sy, sh = top + 26, h - top - 26 - 16
        self._scope(cr, x0, sy, scope_w, sh)
        peak_rx, peak_tx = max(n.rx_hist), max(n.tx_hist)
        self.region(x0, sy, scope_w, sh, f"Last 2 minutes, log scale. RX peak {S.rate(peak_rx)}, "
                    f"TX peak {S.rate(peak_tx)}")
        # --- latency radar
        rx = x1 - 62
        self._radar(cr, rx, top + 58, 54)

    def _scope(self, cr, x, y, w, h):
        D.src(cr, "void", 0.9)
        cr.rectangle(x, y, w, h)
        cr.fill()
        # graticule: 10 x 4 vector grid
        cr.set_line_width(1)
        D.src(cr, "guard", 1)
        for i in range(1, 10):
            gx = round(x + w * i / 10) + 0.5
            cr.move_to(gx, y)
            cr.line_to(gx, y + h)
        for j in range(1, 4):
            gy = round(y + h * j / 4) + 0.5
            cr.move_to(x, gy)
            cr.line_to(x + w, gy)
        cr.stroke()
        D.src(cr, "dim", 0.45)
        cr.rectangle(x + 0.5, y + 0.5, w - 1, h - 1)
        cr.stroke()
        top = max(max(self.net.rx_hist), max(self.net.tx_hist), 64 * 1024)
        lt = math.log10(top + 1)

        def ypos(v):
            return y + h - 3 - (h - 6) * (math.log10(v + 1) / lt)

        for hist, color, base_a in ((self.net.tx_hist, "soft", 0.55), (self.net.rx_hist, "phosphor", 1.0)):
            vals = list(hist)
            nseg = len(vals) - 1
            # afterglow: older segments fade, the head is brightest
            cr.set_line_width(1.6)
            for i in range(nseg):
                a = base_a * (0.12 + 0.88 * (i / nseg) ** 1.6)
                D.src(cr, color, a)
                cr.move_to(x + w * i / nseg, ypos(vals[i]))
                cr.line_to(x + w * (i + 1) / nseg, ypos(vals[i + 1]))
                cr.stroke()
            D.dot(cr, x + w - 1, ypos(vals[-1]), 2.4, color)
        D.label(cr, x + 4, y + 3, S.rate(top).replace(" ", ""), "static", size=9)

    def _radar(self, cr, cx, cy, r):
        cr.new_path()
        D.src(cr, "void", 0.9)
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.fill()
        cr.set_line_width(1)
        for rr, a in ((r, 0.7), (r * 0.66, 0.45), (r * 0.33, 0.45)):
            D.src(cr, "dim", a)
            cr.arc(cx, cy, rr, 0, 2 * math.pi)
            cr.stroke()
        D.src(cr, "guard", 1)
        cr.move_to(cx - r, cy)
        cr.line_to(cx + r, cy)
        cr.move_to(cx, cy - r)
        cr.line_to(cx, cy + r)
        cr.stroke()
        # sweep with a trailing wedge
        a0 = math.radians(self.sweep - 90)
        for k in range(10):
            D.src(cr, "phosphor", 0.10 * (1 - k / 10))
            cr.move_to(cx, cy)
            cr.arc(cx, cy, r, a0 - math.radians(3 * (k + 1)), a0 - math.radians(3 * k))
            cr.close_path()
            cr.fill()
        D.src(cr, "phosphor", 0.9)
        cr.move_to(cx, cy)
        cr.line_to(cx + r * math.cos(a0), cy + r * math.sin(a0))
        cr.stroke()
        # blips: bearing fixed per host, distance = log latency (1 ms centre .. 300 ms rim)
        targets = self.ping.targets
        legend_y = cy + r + 8
        for i, (label, _) in enumerate(targets):
            rtt = self.ping.rtt.get(label)
            bearing = 360 * i / len(targets) + 45
            ba = math.radians(bearing - 90)
            diff = (self.sweep - bearing) % 360
            fresh = 1.0 - min(diff, 360 - 0) / 360        # brightest just after the sweep passes
            if rtt is None:
                rr, col = r - 4, "danger"
            else:
                rr = 6 + (r - 10) * min(1.0, math.log10(max(rtt, 1)) / math.log10(300))
                col = D.level(rtt, 50, 150)
            D.dot(cr, cx + rr * math.cos(ba), cy + rr * math.sin(ba), 2.6, col, glow=fresh > 0.7)
            self.region(cx + rr * math.cos(ba) - 8, cy + rr * math.sin(ba) - 8, 16, 16,
                        f"{label}: " + (f"{rtt:.1f} ms round trip" if rtt is not None else "no reply"))
        # legend under the radar
        for i, (label, _) in enumerate(targets):
            rtt = self.ping.rtt.get(label)
            col = "danger" if rtt is None else D.level(rtt, 50, 150)
            lx = cx - r - 8
            ly = legend_y + i * 16
            D.label(cr, lx, ly, label, "dim", size=10)
            D.label(cr, cx + r + 6, ly, "--" if rtt is None else f"{rtt:.0f} MS", col, size=10, align="right")
            self.region(lx, ly, 2 * r + 14, 15, f"{label} latency (ICMP ping every 6 s): "
                        + (f"{rtt:.1f} ms" if rtt is not None else "no reply")
                        + ". The radar plots it by distance: centre 1 ms, rim 300 ms.")


# =================================================================== STORAGE
class StoragePanel(Panel):
    name, title = "storage", "STORAGE"
    height = 214
    interval = 30.0

    def __init__(self, cfg=None):
        super().__init__(cfg)
        self.mounts = S.storage()

    def tick(self):
        self.mounts = S.storage()

    def draw(self, cr, w, h):
        total = sum(m["size"] for m in self.mounts if m["mounted"])
        used = sum(m["used"] for m in self.mounts if m["mounted"])
        top = D.frame(cr, w, h, self.title, f"{S.human(used)} / {S.human(total)} USED")
        self.region(0, 0, w, 34, f"All mounted filesystems together: {S.human(used)} used of {S.human(total)}")
        shown = self.mounts[:4]
        slot = (w - 32) / max(1, len(shown))
        for i, m in enumerate(shown):
            cx = 16 + slot * i + slot / 2
            cy = top + 50
            if m["mounted"]:
                frac = m["pct"] / 100
                col = D.level(frac, 0.8, 0.92)
                D.ring(cr, cx, cy, 38, frac, 7, col)
                D.text(cr, cx, cy - 10, f"{m['pct']:.0f}%", 16, col, "bold", align="center", glow=True)
                name = m["mount"]
                D.label(cr, cx, cy + 50, name if len(name) < 12 else "…" + name[-10:], "phosphor", align="center")
                D.label(cr, cx, cy + 66, S.human(m['used'], digits=0).replace(" ", "") + "/"
                        + S.human(m['size'], digits=0).replace(" ", ""), "soft", size=10, align="center")
                D.label(cr, cx, cy + 81, f"{S.human(m['free'], digits=0).replace(' ', '')} FREE", "static",
                        size=10, align="center")
                tip = (f"{m['mount']} on {m['device']} ({m['fstype']}): {S.human(m['used'])} used of "
                       f"{S.human(m['size'])}, {S.human(m['free'])} free. Click to open in the file manager.")
                act = (lambda p=m["mount"]: subprocess.Popen(["xdg-open", p], start_new_session=True))
            else:
                D.ring(cr, cx, cy, 38, None, 7, "static", dashed=True)
                D.label(cr, cx, cy - 7, "OFF", "static", align="center")
                D.label(cr, cx, cy + 50, m.get("label") or m["device"], "static", align="center")
                D.label(cr, cx, cy + 66, f"{S.human(m['size'], digits=1)} {m['fstype'].upper()}", "static",
                        size=9, align="center")
                D.label(cr, cx, cy + 80, "NOT MOUNTED", "amber", size=9, align="center")
                tip = (f"{m['device']} ({m['fstype']}, {S.human(m['size'])}"
                       + (f", label {m['label']}" if m.get("label") else "") + ") is not mounted")
                act = None
            self.region(cx - slot / 2, top, slot, h - top - 6, tip, act)


# =================================================================== LAB (control center)
class LabPanel(Panel):
    name, title = "lab", "LAB · ECHOCRAFT"
    height = 640
    interval = 1.0                       # redraw cadence for the freshness clock; data every 20 s

    def __init__(self, cfg=None, wake=None):
        super().__init__(cfg)
        self.lab = S.Lab(every=20, on_update=self._new)
        self.pulse_at = 0
        self._wake = wake
        self.lab.start()

    def _new(self):
        self.pulse_at = time.time()
        if self._wake:
            self._wake(self)

    @property
    def animating(self):
        return time.time() - self.pulse_at < 1.6

    @animating.setter
    def animating(self, _v):
        pass

    def draw(self, cr, w, h):
        L, d = self.lab, self.lab.data
        age = time.time() - L.fetched if L.fetched else None
        state_txt = {"ok": f"SYNC {int(age)}s AGO" if age is not None else "SYNC",
                     "stale": "SNAPSHOT STALE", "no-token": "NO TOKEN",
                     "unauthorized": "TOKEN REFUSED", "down": "LAB UNREACHABLE"}[L.state]
        state_col = {"ok": "static", "stale": "amber"}.get(L.state, "danger")
        top = D.frame(cr, w, h, self.title, state_txt, state_col)
        if L.state == "ok":
            pulse = max(0.0, 1 - (time.time() - self.pulse_at) / 1.6)
            tw = D.layout(cr, state_txt.upper(), 11, "semibold", 0.18).get_pixel_size()[0]
            D.dot(cr, w - 16 - tw - 10, 18, 2.5 + 2 * pulse, "phosphor", glow=True)
        self.region(0, 0, w, 34, f"EchoCraft Lab snapshot (lab.redacted/api/status, every 20 s). "
                    f"State: {L.state}{' - ' + L.error if L.error else ''}. Click to open the Lab.",
                    lambda: open_url("https://lab.redacted"))
        x0, x1 = 16, w - 16
        if not d:
            D.text(cr, x0, top + 10, L.error or "waiting for the first snapshot", 12, "amber", width=x1 - x0)
            return
        c = d.get("cluster", {})
        y = top
        # --- summary strip
        alerts = int(c.get("alertsFiring") or 0)
        argo = d.get("argocd") or {}
        items = [
            ("NODES", f"{c.get('nodesReady', 0)}/{c.get('nodesTotal', 0)}",
             "phosphor" if c.get("nodesReady") == c.get("nodesTotal") else "amber",
             "Kubernetes nodes Ready / total"),
            ("PODS", f"{int(c.get('podsRunning') or 0)}", "danger" if c.get("podsNotRunning") else "phosphor",
             f"Pods running; {int(c.get('podsNotRunning') or 0)} not running"),
            ("ARGO", f"{argo.get('healthy', 0)}/{argo.get('total', 0)}",
             "phosphor" if argo.get("healthy") == argo.get("total") else "amber",
             "ArgoCD applications healthy / total. Click to open ArgoCD."),
            ("ALERTS", f"{alerts}", "amber" if alerts else "phosphor",
             "Prometheus alerts firing. Click to open Alertmanager."),
        ]
        acts = [None, None, lambda: open_url(self._svc_url(d, "argocd")),
                lambda: open_url(self._svc_url(d, "alertmanager"))]
        cw = (x1 - x0) / len(items)
        for i, (k, v, col, tip) in enumerate(items):
            ix = x0 + i * cw
            D.label(cr, ix, y, k, "dim")
            D.text(cr, ix, y + 14, v, 20, col, "bold", glow=True)
            self.region(ix, y, cw - 6, 40, tip, acts[i])
        y += 50
        D.rule(cr, x0, y, x1)
        y += 10
        # --- node map: a bus with the nodes hanging off it
        y = self._nodes(cr, d, x0, x1, y)
        D.rule(cr, x0, y, x1)
        y += 10
        # --- services matrix
        y = self._services(cr, d, x0, x1, y)
        D.rule(cr, x0, y, x1)
        y += 10
        # --- storage pools
        self._pools(cr, d, x0, x1, y)

    def _svc_url(self, d, sid):
        for g in d.get("config", {}).get("groups", []):
            for s in g.get("services", []):
                if s.get("id") == sid:
                    return s.get("lan") or s.get("wan") or "https://lab.redacted"
        return "https://lab.redacted"

    def _nodes(self, cr, d, x0, x1, y):
        nodes = d.get("nodes") or []
        D.label(cr, x0, y, "NODE MAP", "dim")
        cl = d.get("cluster", {})
        D.label(cr, x1, y, f"CLUSTER CPU {cl.get('cpuNow', 0):.0f}%", "static", align="right")
        y += 20
        n = max(1, len(nodes))
        bw = (x1 - x0 - (n - 1) * 8) / n
        bus_y = y + 4
        D.src(cr, "dim", 0.6)
        cr.set_line_width(1)
        cr.move_to(x0, bus_y + 0.5)
        cr.line_to(x1, bus_y + 0.5)
        cr.stroke()
        pulse = max(0.0, 1 - (time.time() - self.pulse_at) / 1.6)
        for i, nd in enumerate(nodes):
            bx = x0 + i * (bw + 8)
            cx = bx + bw / 2
            cpu, mem = nd.get("cpuPct", 0) / 100, nd.get("memPct", 0) / 100
            worst = max(D.level(cpu, 0.85, 0.95), D.level(mem, 0.9, 0.97),
                        key=["phosphor", "amber", "danger", "static"].index)
            D.src(cr, "dim", 0.6)
            cr.move_to(cx + 0.5, bus_y)
            cr.line_to(cx + 0.5, bus_y + 10)
            cr.stroke()
            by = bus_y + 10
            D.src(cr, "void", 0.7)
            cr.rectangle(bx, by, bw, 76)
            cr.fill()
            D.brackets(cr, bx, by, bw, 76, 6, worst, 1.2, 0.9)
            D.dot(cr, bx + 9, by + 11, 2.5 + 1.5 * pulse, worst, glow=True)
            D.text(cr, bx + 18, by + 4, nd.get("name", "?").replace("k8s-", "").upper(), 10, "soft", "semibold", spacing=0.08, width=bw - 22)
            D.label(cr, bx + 6, by + 25, "CPU", "dim", size=10)
            D.bar(cr, bx + 40, by + 30, bw - 46, 5, cpu, D.level(cpu, 0.85, 0.95))
            D.label(cr, bx + 6, by + 41, "MEM", "dim", size=10)
            D.bar(cr, bx + 40, by + 46, bw - 46, 5, mem, D.level(mem, 0.9, 0.97))
            D.label(cr, bx + 6, by + 57, f"L{nd.get('load1', 0):.1f} · {nd.get('cores', '?')}C", "static", size=10)
            self.region(bx, by, bw, 76, f"Node {nd.get('name')}: CPU {nd.get('cpuPct', 0):.0f}%, memory "
                        f"{nd.get('memPct', 0):.0f}%, load {nd.get('load1', 0):.2f} on {nd.get('cores')} cores. "
                        "Amber: memory past 90% or CPU past 85%.")
        return bus_y + 10 + 76 + 12

    def _services(self, cr, d, x0, x1, y):
        groups = d.get("config", {}).get("groups", [])
        status = d.get("services", {})
        total = sum(len(g.get("services", [])) for g in groups)
        up = sum(1 for g in groups for s in g.get("services", []) if status.get(s["id"], {}).get("status") == "up")
        D.label(cr, x0, y, "SERVICES", "dim")
        D.label(cr, x1, y, f"{up}/{total} UP", "phosphor" if up == total else "amber", align="right")
        y += 20
        cols = 4
        cw = (x1 - x0 - (cols - 1) * 4) / cols
        ch = 21
        for g in groups:
            D.label(cr, x0, y, g.get("name", ""), "static", size=10)
            y += 16
            for i, s in enumerate(g.get("services", [])):
                r, c = divmod(i, cols)
                cx, cy = x0 + c * (cw + 4), y + r * (ch + 3)
                st = status.get(s["id"], {})
                state = st.get("status")
                col = {"up": "phosphor", "down": "danger"}.get(state, "amber")
                D.src(cr, col, 0.10 if state == "up" else 0.22)
                cr.rectangle(cx, cy, cw, ch)
                cr.fill()
                D.src(cr, col, 0.55 if state == "up" else 1)
                cr.set_line_width(1)
                cr.rectangle(cx + 0.5, cy + 0.5, cw - 1, ch - 1)
                cr.stroke()
                D.src(cr, col)
                cr.rectangle(cx + 5, cy + ch / 2 - 2, 4, 4)
                cr.fill()
                D.text(cr, cx + 14, cy + 3, s.get("name", s["id"]).upper(), 10,
                       "soft" if state == "up" else col, "semibold", spacing=0.06, width=cw - 18)
                url = s.get("lan") or s.get("wan")
                ms = st.get("ms")
                tip = (f"{s.get('name')} ({s.get('role', '')}): {state or 'unknown'}"
                       + (f", answered in {ms:.0f} ms" if isinstance(ms, (int, float)) else "")
                       + (f". Click to open {url}" if url else (f". Address {s.get('address')}" if s.get("address") else "")))
                act = (lambda u=url: open_url(u)) if url else \
                    ((lambda a=s.get("address"): copy_text(a)) if s.get("address") else None)
                self.region(cx, cy, cw, ch, tip, act)
            rows = math.ceil(len(g.get("services", [])) / cols)
            y += rows * (ch + 3) + 4
        return y + 4

    def _pools(self, cr, d, x0, x1, y):
        D.label(cr, x0, y, "STORAGE POOLS", "dim")
        y += 20
        nas = d.get("nas") or {}
        pool = nas.get("pool") or {}
        if pool.get("total"):
            frac = pool["used"] / pool["total"]
            D.label(cr, x0, y, "NAS", "phosphor")
            D.label(cr, x0 + 44, y, f"{S.human(pool['used'], digits=1)} / {S.human(pool['total'], digits=1)}", "soft")
            disks = nas.get("disks") or []
            # disk bays as 8 small cells at the right
            bx = x1 - len(disks) * 16
            for i, dk in enumerate(disks):
                bad = dk.get("health") != "good" or dk.get("state") != "normal"
                col = "danger" if bad else D.level(dk.get("tempC") or 0, 45, 55)
                D.src(cr, col, 0.9)
                cr.rectangle(bx + i * 16, y + 1, 12, 12)
                cr.fill()
                self.region(bx + i * 16, y, 14, 14, f"NAS bay {dk.get('slot')}: {dk.get('model', '')} "
                            f"{S.human(dk.get('size'))}, {dk.get('health')}, {dk.get('tempC')} °C, "
                            f"{dk.get('hours', 0)} power-on hours")
            D.cells(cr, x0, y + 18, x1 - x0, 7, frac, n=48, warn=0.8, crit=0.9)
            dev = nas.get("device") or {}
            self.region(x0, y, bx - x0 - 6, 28, f"{dev.get('name', 'NAS')}: RAID pool ({pool.get('raidMembers')} disks, "
                        f"{pool.get('health')}) {S.human(pool['used'])} used of {S.human(pool['total'])}")
            y += 34
        shares = {s["name"]: s for s in nas.get("shares") or []}
        rf = shares.get("k8s_rustfs")
        if rf:
            D.label(cr, x0, y, "RUSTFS", "phosphor")
            D.label(cr, x0 + 70, y, f"{S.human(rf['usage'], digits=1)} on the NAS share k8s_rustfs", "soft")
            st = (d.get("services") or {}).get("rustfs", {}).get("status")
            D.dot(cr, x1 - 4, y + 7, 3, "phosphor" if st == "up" else "danger")
            self.region(x0, y, x1 - x0, 16, f"RustFS object store: {S.human(rf['usage'])} used (share "
                        f"k8s_rustfs, no quota); console {st or 'unknown'}. Click to open.",
                        lambda: open_url(self._svc_url(d, "rustfs")))
            y += 22
        for nd in d.get("nodeDisks") or []:
            frac = nd["pct"] / 100
            D.label(cr, x0, y, nd["node"].replace("k8s-", ""), "static", size=9)
            D.bar(cr, x0 + 110, y + 4, x1 - x0 - 210, 5, frac, D.level(frac, 0.8, 0.9))
            D.label(cr, x1, y, f"{S.human(nd['used'], digits=0)}/{S.human(nd['capacity'], digits=0)}",
                    "soft", size=9, align="right")
            self.region(x0, y, x1 - x0, 15, f"Local disk on node {nd['node']}: {nd['pct']:.0f}% used")
            y += 16


# =================================================================== SWITCHBOARD
class SwitchboardPanel(Panel):
    name, title = "switchboard", "SWITCHBOARD"
    height = 158
    interval = 60.0

    # Hosts come from the homelab repo: ARBITER's console from helm/arbiter values
    # (console.lanHostname), the Lab from helm/homepage ingress.lanHostname; every
    # other entry is read live from the Lab snapshot's own config (helm/homepage groups).
    FIXED = [("arbiter", "ARBITER", "The Floor: ARBITER console", "https://arbiter.redacted"),
             ("lab", "LAB", "EchoCraft Lab homepage", "https://lab.redacted")]
    FROM_LAB = [("argocd", "ARGO CD"), ("grafana", "GRAFANA"), ("litellm", "LITELLM"),
                ("openwebui", "OPEN WEBUI"), ("comfyui", "COMFYUI"), ("proxmox", "PROXMOX"),
                ("vault", "VAULT"), ("rustfs", "RUSTFS")]

    def __init__(self, cfg=None, lab=None):
        super().__init__(cfg)
        self.lab = lab
        self.alive = {}
        import threading
        threading.Thread(target=self._probe_loop, daemon=True).start()

    def _probe_loop(self):
        while True:
            for sid, _, _, url in self.FIXED:
                self.alive[sid] = S.http_alive(url)
            time.sleep(60)

    def entries(self):
        d = self.lab.lab.data if self.lab else None
        out = [(sid, name, role, url, self.alive.get(sid)) for sid, name, role, url in self.FIXED]
        groups = (d or {}).get("config", {}).get("groups", [])
        status = (d or {}).get("services", {})
        for sid, label in self.FROM_LAB:
            for g in groups:
                for s in g.get("services", []):
                    if s["id"] == sid and s.get("lan"):
                        st = status.get(sid, {}).get("status")
                        out.append((sid, label, s.get("role", ""), s["lan"],
                                    None if st is None else st == "up"))
        return out

    def draw(self, cr, w, h):
        top = D.frame(cr, w, h, self.title, "CLICK TO OPEN")
        self.region(0, 0, w, 34, "Launch shortcuts to the homelab and ARBITER (opens in the browser). "
                    "Dot: green answering, red not, grey unknown.")
        x0, x1 = 16, w - 16
        cols = 4
        cw = (x1 - x0 - (cols - 1) * 6) / cols
        ch = 30
        for i, (sid, name, role, url, ok) in enumerate(self.entries()):
            r, c = divmod(i, cols)
            bx, by = x0 + c * (cw + 6), top + r * (ch + 6)
            col = "static" if ok is None else ("phosphor" if ok else "danger")
            D.src(cr, "void", 0.6)
            cr.rectangle(bx, by, cw, ch)
            cr.fill()
            cr.set_line_width(1)
            D.src(cr, "dim", 0.7)
            cr.rectangle(bx + 0.5, by + 0.5, cw - 1, ch - 1)
            cr.stroke()
            D.brackets(cr, bx, by, cw, ch, 5, "phosphor", 1.2, 0.8)
            D.dot(cr, bx + 10, by + ch / 2, 2.5, col, glow=bool(ok))
            D.label(cr, bx + 20, by + 9, name, "soft", size=10)
            self.region(bx, by, cw, ch, f"{name}: {role}. Opens {url}"
                        + ("" if ok is None else (" (answering)" if ok else " (not answering)")),
                        lambda u=url: open_url(u))


# =================================================================== SHORTCUTS
class ShortcutsPanel(Panel):
    """Live Hyprland keybinds as keycaps, Bromigos sections first. Scroll to move; click a
    Bromigos, launch or capture line to run it (window, workspace, system and hold-to-use
    binds stay keyboard-only)."""
    name, title = "shortcuts", "SHORTCUTS"
    height = 384
    interval = 5.0
    ROW, HEAD = 24, 26
    RUNNABLE = None                         # keybinds.RUNNABLE, set in __init__

    def __init__(self, cfg=None):
        super().__init__(cfg)
        import keybinds
        self.kb = keybinds
        self.RUNNABLE = tuple(keybinds.RUNNABLE)
        self.items, self.mtime, self.offset = [], -1, 0
        self.tick()

    def tick(self):
        m = self.kb.config_mtime()
        if m != self.mtime:
            self.mtime = m
            self.items = self.kb.shortcuts()

    def content_height(self):
        secs = len({s for s, *_ in self.items})
        return secs * self.HEAD + len(self.items) * self.ROW

    def scroll(self, dy):
        view = self.height - 44 - 10
        self.offset = max(0, min(max(0, self.content_height() - view), self.offset + dy * self.ROW * 3))

    def keycap(self, cr, x, y, label):
        lay = D.layout(cr, label, 11, "semibold", 0.04)
        w = lay.get_pixel_size()[0] + 12
        D.src(cr, "guard", 0.9)
        cr.rectangle(x, y, w, 18)
        cr.fill()
        cr.set_line_width(1)
        D.src(cr, "dim", 0.9)
        cr.rectangle(x + 0.5, y + 0.5, w - 1, 17)
        cr.stroke()
        D.src(cr, "phosphor", 0.55)
        cr.move_to(x + 1, y + 17.5)
        cr.line_to(x + w - 1, y + 17.5)
        cr.stroke()
        D.text(cr, x + 6, y + 1, label, 11, "soft", "semibold", spacing=0.04)
        return w

    def draw(self, cr, w, h):
        top = D.frame(cr, w, h, self.title, f"{len(self.items)} BINDS · SUPER+SHIFT+K SEARCH")
        self.region(0, 0, w, 34, "Every Hyprland keybind, read live from Hyprland (it refreshes when "
                    "a hypr .conf changes). Bromigos keys first. Scroll to move; click a Bromigos, launch or capture line to run it. "
                    "SUPER+SHIFT+K opens a searchable version.")
        x0, x1 = 16, w - 16
        view_top, view_bot = top, h - 10
        cr.save()
        cr.rectangle(0, view_top, w, view_bot - view_top)
        cr.clip()
        y = view_top - self.offset
        sec = None
        for s, keys, desc, action in self.items:
            if s != sec:
                sec = s
                if view_top - self.HEAD <= y <= view_bot:
                    lw = D.layout(cr, s.upper(), 10, "semibold", 0.18).get_pixel_size()[0]
                    D.label(cr, x0, y + 6, s, "phosphor", size=10)
                    D.rule(cr, x0 + lw + 10, y + 13, x1, "dim", 0.35)
                y += self.HEAD
            if view_top - self.ROW <= y <= view_bot:
                kx = x0
                for i, k in enumerate(keys):
                    if i:
                        D.text(cr, kx + 2, y + 2, "+", 10, "static", "regular")
                        kx += 12
                    kx += self.keycap(cr, kx, y + 1, k)
                D.text(cr, max(kx + 12, x0 + 200), y + 2, desc, 12, "soft", "regular",
                       width=x1 - max(kx + 12, x0 + 200))
                runnable = action and s in self.RUNNABLE
                if runnable and view_top <= y and y + self.ROW <= view_bot:
                    import subprocess as _sp
                    self.region(x0, y, x1 - x0, self.ROW - 2, f"{' + '.join(keys)}: {desc}. Click to run it now.",
                                lambda a=action: _sp.Popen(["/usr/bin/hyprctl", "dispatch", a[0], a[1]],
                                                           stdout=_sp.DEVNULL, stderr=_sp.DEVNULL))
            y += self.ROW
        cr.restore()
        # scroll position rail
        total = self.content_height()
        view = view_bot - view_top
        if total > view:
            th = max(24, view * view / total)
            ty = view_top + (view - th) * self.offset / (total - view)
            D.src(cr, "guard", 1)
            cr.rectangle(w - 6, view_top, 2, view)
            cr.fill()
            D.src(cr, "phosphor", 0.8)
            cr.rectangle(w - 6, ty, 2, th)
            cr.fill()
