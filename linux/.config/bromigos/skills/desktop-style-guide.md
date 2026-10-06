---
name: desktop-style-guide
description: The Bromigos desktop's visual and sound language — palette tokens and their roles, type, the HUD frame, motion, cues — and the operator's rules with the reasons behind them, with the holograms as exemplars of good.
when_to_use: Before designing or reviewing anything that appears on the operator's desktop (a hologram, a panel, a notification, a bar module, an animation, a sound), and whenever you are unsure whether something is on brand.
---

# The desktop's style

The desktop is the operator's control center, styled as the Wick: BLACKFLAME's
relay station in the Bromigos universe (lore: `bromigos-org/platform/agents/LORE.md`).
Retro sci-fi HUD in phosphor green on void black — 80s/90s/2000s film interfaces,
reinterpreted, never copied.

## The rules, and why

1. **Real data only.** Every number, light and motion means a real reading or a real
   event. Decoration is allowed only for atmosphere (stars, loops) and the emblem,
   and the config marks it as decoration. *Why:* the operator reads this desktop to
   run his lab and ARBITER; a fake number is a lie on his instruments.
2. **Missing data says so.** "NO LAB SNAPSHOT", "NO CI ON THIS COMMIT",
   "OPENING FILL OLDER THAN THE LAST 1,000". Never invent a plausible value.
3. **Nothing over windows.** No CRT overlay, scanlines, vignette or tint on apps;
   the background stays behind windows; summoned decks are the operator's choice.
   *Why:* "it'll be hard to see" — legibility of his actual work comes first.
4. **No callsign, no frequency, no dossier on screen.** Identity lives only in the
   emblem (the burn-in). The ring carries only the motto.
5. **Hover hints everywhere.** Everything hoverable says what it is, its live values,
   and what a click does.
6. **Original designs.** No film or franchise assets, names, logos, silhouettes or
   quotes. The starships are our own hull: arrowhead plates, a relay-mast spire,
   not a stepped bridge tower or a trench.
7. **Real money stays the operator's.** ARBITER visuals are paper; show
   "REAL MONEY: OFF · NOT ARMED" plainly. Nothing on the desktop trades or arms.
8. **Cheap.** Heavy reads only while visible; 30/20/0 fps; pause under fullscreen.
9. **Assets** (images, video, audio, 3D) come from the operator's `nolgia` CLI, or
   are procedural; keep spend modest and say what was spent.

## Palette tokens

Use only these (`live/glkit.py` `PAL`, CSS in `brand/palette.css`):

| Token | Hex | Role |
|-------|-----|------|
| void | `#000500` | backgrounds, plates (as black with alpha) |
| panel | `#001300` | panel fill |
| guard | `#003b00` | rules, grids, idle tracks |
| phosphor | `#39ff14` | the primary light: OK, healthy, active, a win |
| soft | `#9cff8a` | text and secondary lines; outbound packets |
| dim | `#159b09` | labels, captions, hints, idle things |
| amber | `#d4af37` | warning, waiting on the operator, unpushed, return packets, upload |
| danger | `#ff766f` | failure, down, a loss, gone |
| white | `#e8ffe0` | emphasis only: the selected thing, the cursor, VECTOR's own marks |
| static | `#7e927e` | no data |

Status order is always phosphor → amber → danger, grey for unknown.

## Type

Geist Mono, uppercase for HUD text, wide tracking on titles. Atlas sizes
(`glkit.Atlas`): `xs` 12, `s` 14, `m` 17, `l` 24, `xl` 40, `xxl` 64, `cap` 22.
Titles `l` with track 6; panel titles `m` track 3; values `s`–`l`; captions `xs`.
Check legibility downscaled to 1080p. Only ASCII plus `· → ← ↑ ↓ ° ± ×` and a few
symbols are in the atlas; anything else renders as `?` (use `deckkit.ascii_()`).

## The HUD frame

- `gadgets.frame()`: a dark plate, 1 px rules, targeting brackets at the corners,
  a wide-tracked title and a right-aligned subtitle stating the data's source.
- A deck: a title strip with provenance on the right ("TOPOLOGY + TRAFFIC FROM
  UNIFI (UNPOLLER) AND NODE-EXPORTER · LATENCY BY PING"), the stage panel, a side
  panel (legend, log, the selected thing's card), and a footer of keys and verbs.
- Panels assemble on open: rules draw in, brackets land, titles type on.
- Selected things get a spinning four-segment bracket ring; hovered things a readout
  box with brackets.

## Motion and sound

Calm and purposeful: slow spins, packets that mean traffic, flares that decay,
blinks under 1 Hz. Event animations are short and leave nothing. Sounds are quiet
(0.3), few, and respect mute: a terminal blip, a notification chirp, a critical
alert, the intercept's hiss / sweep / sign-off. VECTOR speaks in his own voices.

## What good looks like

- **Holo deck (SUPER+H):** arc rings that tick up to real CPU/GPU/RAM/VRAM, the lab
  as a constellation, a compact live-lit model with a hand-off to the gallery.
- **Network map (SUPER+SHIFT+N):** topology read from UniFi, packets that scale with
  each link's real rate, a ring per node for ping, and a trace that lights the slow
  hop with its milliseconds. Every element is data.
- **Swarm (SUPER+SHIFT+S):** status you can read from across the room — steady
  lights working, an amber beacon waiting on you, red trouble — on an original hull.
- **Mind (SUPER+I):** memories placed by meaning (embeddings), knowledge by
  provenance; a recall visibly reaches back to VECTOR.
- **Trade replay (SUPER+R):** cause → entry → price → exit → result, scrubbable,
  with the gaps in the data shown as gaps.
