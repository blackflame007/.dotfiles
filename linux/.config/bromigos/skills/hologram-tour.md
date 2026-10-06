---
name: hologram-tour
description: How VECTOR gives the host a guided tour of the desktop's holograms on his own — the route, what each deck shows and what to point out, which voice carries which part, pacing, and how to end or stop.
when_to_use: The host asks for a tour, a walkthrough or a demo of the holograms, the decks, the desktop or "what you can show me", or to be shown around, without naming one deck.
triggers: '\b(tour|walk ?through|walk me through|show me around|guided|demo|show me (all|everything|what you (can|got)))\b.*\b(holo\w*|decks?|desktop|ui|setup|screens?|panels?)\b|\b(holo\w*|decks?)\b.*\b(tour|walk ?through|all of them|one by one)\b|^\s*(give me )?a tour\b'
---

# Giving the hologram tour

You run it yourself, start to finish, in **one turn**: don't ask which deck first, don't
read docs or open a terminal to prepare. This skill and your tools are all you need.

## How a stop works

For each stop, in order:

1. `hologram_deck(deck, "open")`. It waits until you've finished speaking what you said
   before it, then opens the deck. The last deck closes by itself (one is up at a time).
2. Say **2–4 sentences** about it: what it is, one thing to look at, the key that opens
   it. Include **one real reading** when you have it (from `lab_status`, `system_stats`,
   `herdr_status`, `arbiter`). Never invent a number, a host, a repo or a trade.
3. Optionally drive it once with a verb on a **real** target you just read (a repo you
   saw in `ops`, a host from `lab_status`): `swarm point <repo>`, `netmap trace <host>`,
   `replay pick latest` then `play`, `mind space <kb>`. Skip it rather than guess.
4. Move on: the next `open` waits for you to finish.

Fetch the two or three readings you'll quote **before** the first stop (`lab_status`,
`system_stats`, `herdr_status`), in one go, so the tour doesn't stall mid-way.

## Voices (markers nobody sees)

- Untagged: your own voice, the guide. Openings and the wrap-up.
- `‹robot›…‹/robot›`: readouts said as a system. The holodeck's numbers, the netmap's
  latency, how many pods are up.
- `‹sci›…‹/sci›`: how something works. How the swarm turns agents into starships, how the
  mind deck clusters memories, how the timeline records 72 hours.
- `‹floor›…‹/floor›`: the ARBITER deck and the trade replay (paper money; say so).

Switch at least three times across the tour, whole sentences only, a sentence or two
each. One opening `‹mood:excited›` fits; this is the fun part of the job.

## The route

| # | deck | what it is | point out | key |
|---|------|-----------|-----------|-----|
| 1 | `holodeck` | This machine as arc rings, the lab as a constellation, a compact 3D model | the rings are live CPU, GPU, RAM and VRAM with a ring of per-core load; drag the model to spin it, click a part for its readings; N opens FIELD NOTES | SUPER+H |
| 2 | `netmap` | The LAN from UniFi: devices, link traffic, ping latency | scroll zooms toward the cursor; drag pans | SUPER+SHIFT+N |
| 3 | `ops` | Pushes → CI → Argo → pods, plus your own tasks and tool calls | a recent push travelling the chain | SUPER+SHIFT+O |
| 4 | `swarm` | Repos as a star system, herdr agents as starships | ships are agents at work; zoom in and they get names | SUPER+SHIFT+S |
| 5 | `mind` | Your memory and the knowledge base as a constellation | clusters open into documents as you zoom | SUPER+I |
| 6 | `timeline` | The last 72 hours as a ribbon to scrub | move the mouse (or ←/→) to scrub; 1/2/3 switch 6 h / 24 h / 72 h | SUPER+T |
| 7 | `driftmap` | The lore catalog as a star chart; the lab's services as relays | the Bromigos universe, mapped | SUPER+M |
| 8 | `arbiter` | ARBITER's paper portfolio: the road to live, the tape with causes, the lineup | it's paper money, learning | SUPER+G |
| 9 | `replay` | One paper round trip as a price ribbon with its causes | `pick latest`, then `play` | SUPER+R |

Then `hologram_deck(<last>, "close")` and a one-line wrap-up: Tab cycles the decks, Esc
closes one, and they can ask for any by name.

A short tour (the host says "quick" or "the highlights"): holodeck, netmap, swarm, arbiter.

## Rules

- One turn, no questions in between. If a deck fails to open, say so in a sentence and
  go to the next stop.
- The host talks over you or says stop: stop the tour, close the open deck, one line.
- Keep each stop short; nine stops at 2–4 sentences is a three-minute tour.
- These decks only show; nothing on the tour changes anything. ARBITER stays read only.
