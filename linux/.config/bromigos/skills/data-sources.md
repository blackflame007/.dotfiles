---
name: data-sources
description: Every real data source the desktop and its holograms read — the Lab API, Prometheus (incl. UniFi and Argo metrics), kubectl, gh, ARBITER's console API, Gnosis through the gate, herdr, git, local sensors, VECTOR's feed — with how to reach each (token file paths, never values), what it costs, and how often it is safe to poll.
when_to_use: Choosing where a reading should come from, wiring a new hologram or panel to data, or debugging a value that looks stale or wrong.
---

# Data sources

All measured from this workstation (echobase, on the LAN) on 2026-10-05.
Secrets are files or Vault paths here — never print, log or embed their values.
The homelab CA is `~/.config/homelab/homelab-ca.crt`; use it for every `*.redacted` TLS call.

| Source | Reach | Cost | Poll at most |
|--------|-------|------|--------------|
| Local machine | psutil, `/sys`, one long-lived `nvidia-smi -lms 1500` | ~0 | 1 s (already done by `live/data.py`) |
| EchoCraft Lab API | `GET https://lab.redacted/api/status`, `Authorization: Bearer <~/.local/share/bromigos/lab-token>` (Vault `secret/<vault-path>` read_token) | 22 ms, 47 KB | 20–30 s (it refreshes every 20 s) |
| Prometheus | `https://prometheus.redacted/api/v1/query` (LAN, no auth) | ~20 ms per instant query | 5–10 s per deck |
| Argo CD | Prometheus `argocd_app_info{sync_status,health_status}`; or kubectl (below) | 20 ms / 220 ms | 10 s |
| Kubernetes | `kubectl --kubeconfig ~/.local/share/bromigos/pilot-kubeconfig` (the `pilot-readonly` ServiceAccount: no secrets, no exec) | ~220 ms | 30 s; prefer Prometheus (`kube_pod_info`, `kube_node_info`, `kube_pod_created`) |
| UniFi | Prometheus `unpoller_*`: `unpoller_client_uptime_seconds` (who is attached where: `sw_name`, `sw_port`, `ap_name`, `mac`, `ip`), `unpoller_device_port_{receive,transmit}_rate_bytes`, `unpoller_device_wan_rate_bytes`, `unpoller_device_rate_bytes`, `unpoller_device_port_poe_watts`, `unpoller_device_info` | 20 ms | 5 s |
| Node traffic | Prometheus `rate(node_network_{receive,transmit}_bytes_total{device!~"lo|veth.*|cali.*|flannel.*|cni.*|docker.*|br.*"}[1m])` | 20 ms | 5 s |
| GitHub | the `gh` CLI with the operator's login (`~/.config/gh/hosts.yml`): `gh run list -R o/r -L 1 --json status,conclusion,workflowName,headSha`, `gh api repos/o/r/commits/<sha>/check-runs` | 0.35–0.55 s a call, rate-limited | a few calls a minute; cache to disk (the Swarm caches 10 min) |
| Git (local) | `git status --porcelain=v1 -b`, `rev-list --count --since=14.days`, `log -1` | ~60 ms a repo; 50 repos 2.9 s | 60 s, off the render thread |
| Pushes | the remote-tracking reflogs `.git/logs/refs/remotes/origin/*`: lines ending `update by push` (stat first, read only changed files) | ~0 | 5 s |
| ARBITER console | `https://arbiter.redacted/api/...` GET only, no auth on the LAN | `overview/now` 32 ms; `trades?limit=1000&book=all` 134 ms, 1.4 MB; `roster` 1.7 s, 2.3 MB; `instrument?id=…&range=24h|7d|30d|90d` (bars) | light reads 20–60 s, heavy (roster, agents/road) 3 min and only while visible |
| Gnosis (memory + knowledge) | through the gnosis-gate `https://gnosis.redacted/gate`, `Bearer <~/.local/share/bromigos/gnosis-vector-read-token>` (VECTOR's read token: his own space + kb-* + arbiter research/signals); write and kb-ingest tokens sit beside it for their owners only | search ~0.15–0.35 s; `POST /v1/memories/list` 0.2 s per 200, **capped at 2,000 per space** | on demand |
| Knowledge chart | kb-sync's own chunker and state: `~/.config/bromigos/holo/tools/kb-sync.py` `sources()` + `chunks()`, ids from `~/.local/state/bromigos/kb-sync.json` (all ~9.6k chunks with exact Gnosis ids, no network) | ~2 s | once a day (kb-sync runs nightly at 03:30) |
| VECTOR's memory mirror | `~/.cache/bromigos/vector-memory.json` (his notes with 1024-d embeddings) | ~0 | on mtime change |
| herdr | `herdr api snapshot` (agents: status, cwd, pane id, title); `herdr pane read <pane> --source recent --lines N` | 8 ms; read ~30 ms | snapshot 2 s; read on hover only |
| Latency | `ping -n -c 1 -W 1 <ip>` | 1–10 ms on the LAN | 4 s, in parallel |
| VECTOR's state and feed | `$XDG_RUNTIME_DIR/bromigos-vector.json`; `$XDG_RUNTIME_DIR/bromigos-vector-events.jsonl` (schema: `holo/README.md`, "Event feed") | ~0 | stat 0.25 s while visible |
| The desktop's own history | `~/.local/state/bromigos-live/history.npz` (minute rows, 72 h) + `events.jsonl` | ~0 | — |
| Models | LiteLLM `https://litellm.redacted` with `~/.local/share/bromigos/litellm-key` (local vLLM first); embeddings `local-qwen3-embedding-0.6b` | varies | — |
| Speech | VECTOR's voice server (unix socket `$XDG_RUNTIME_DIR/bromigos-holo-voice.sock`, `{"op":"tts","text":…}`); the lab's Breeze TTS `https://tts.redacted/v1/audio/speech` as the fallback | 0.8 s+ | per call, cached by text |

## Addresses on the LAN

This repo is public, so addresses are not written here. Read them live: every lab host's
IP and where it is attached from UniFi (`unpoller_client_uptime_seconds`), the nodes from
`kube_node_info{internal_ip}`, the gateway from `ip route`. The Network map
(`bromigos-live netmap`) shows them all.

## Code you can reuse

`bromigos-live/live/sources.py`:

```python
from live import sources
sources.prom('argocd_app_info')                    # -> [{"metric": {...}, "value": [ts, "1"]}]
rs = sources.repos()                               # every repo, with its GitHub slug
sources.git_state(rs[0])                           # branch, dirty, ahead, behind, commits14, last commit
sources.pushes(rs, since=time.time() - 1800)       # [(t, repo, branch, sha)]
sources.check_runs("bromigos-org/homelab", sha)    # CI checks for a commit
sources.herdr()                                    # agents with status and cwd
sources.ping("10.0.0.x")                        # ms or None
```

`bromigos-live/live/arbiter.py` `Feed(cfg).get(path)` is the read-only ARBITER
client (it only ever sends GET).

## Things that bit us

- Gnosis's list endpoint stops at 2,000 items per space: chart kb spaces from
  kb-sync, not from listing.
- The Lab API's WAN route excludes `/api` on purpose; use the LAN hostname.
- ARBITER's `live/*` endpoints need a signed-in session and are about real money:
  never call them from the desktop.
- Instrument bars can lag the fills tape by hours; show the gap.
- Prediction-market (Kalshi) instruments have no price bars.
- The Lab snapshot's solar block also names a street address: keep only the numbers.
