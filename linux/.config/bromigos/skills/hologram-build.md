---
name: hologram-build
description: How the desktop's holograms are built end to end — file map, the two renderers, getting real data in, the event feed, testing headless, frame budgets, and control verbs — with the starship as a worked example.
when_to_use: Building a new hologram or deck, changing one of the existing ones (Mind, Ops theater, Swarm, Network map, Trade replay, holo deck, ARBITER deck, Drift map, timeline), adding a verb VECTOR can drive, or turning a 3D model into a live-lit hologram.
---

# Building a hologram

A hologram here is a summoned deck: a full-screen layer-shell overlay drawn in
phosphor vector lines, showing one real thing, driven by real data, that the
operator (or you, VECTOR) can open, turn, hover, click and command. This is the
process the five holograms of October 2026 were built with. Follow it in order.

## 1. Know where things live

| What | Where |
|------|-------|
| The live layer daemon (decks, background, sounds) | `~/.config/bromigos-live/` (dotfiles `linux/.config/bromigos-live/`) |
| Deck base for 3D holograms | `live/deckkit.py` (`Deck3D`: drag, drift, picking, hover readout, Tab cycle, verbs, pollers) |
| The overlay renderer every deck inherits | `live/overlays.py` (`Base`: one emissive pass, bloom, composite; `make()` opens the window) |
| Vector primitives | `live/glkit.py` (`Batch`: `line`, `arc`, `text`, `plate`, `brackets`, `rect`; `Painter`; `rot_matrix`, `project`) |
| Panels and gauges | `live/gadgets.py` (`frame`, `rings`, `constellation`, …) |
| Shaders | `shaders/*.vert|frag|glsl` (`#include name` pulls `name.glsl`) |
| Shared data readers | `live/sources.py` (Prometheus, repos + git, push reflogs, gh, herdr, ping) |
| VECTOR's event feed reader | `live/vfeed.py` |
| The shared 3D renderer (models with parts) | `/usr/lib/bromigos/vector/holo/` (bromigos-vector; source: bromigos-org/vector) (`render.Holo`, `stage.Stage`, `bind.reading`, `fmt` for `.holo.npz`) |
| Models | `~/.config/bromigos/brand/3d/holo/*.holo.npz`, plus `/usr/lib/bromigos/live/models/starship.holo.npz` |
| Headless renders | `/usr/lib/bromigos/live/tools/offscreen.py` |
| The one config | `bromigos-live/config.toml` (reloads on save) |
| Keys | a personal deck's: Sir's `~/.config/hypr/hyprland.lua`, after the defaults; bromigOS's decks: `/usr/share/bromigos/default/hypr/bromigos/live.lua` (read-only; source bromigOS `desktop/hypr/`) (skill `hyprland-config`) + bromigOS `widgets/keybinds.py` `EXEC` rows for SHORTCUTS |

The decks are registered by name in `overlays.kind_class()`: a module
`live/<name>_deck.py` that ends with `DECK = YourDeck` is found automatically for
`mind`, `ops`, `swarm`, `netmap` and `replay`; add a new name to that tuple and to
the deck tuples in `app.py` (`overlay()`, `refresh_state()`, `command("deck")`).

## 2. Pick the renderer

**Vector batch (most decks).** Everything is instanced quads: lines, arcs/discs,
glow dots and glyphs. You build a `Batch` in `build()` a few times a second;
motion (spin, packets, reveals, depth fade) runs in the shaders, so a frame is a
handful of draw calls. Points can live in a 3D "space": space 2 is the deck's
turnable scene.

```python
b.line(p0, p1, col("soft", 0.8), space=2, dash=6)                    # a lane
b.arc(c, 0, 6 * s, 0, TAU, col("white"), kind=2, space=2)            # a glow dot
b.arc(a, 0, 2.6 * s, 0, TAU, col("soft"), kind=2, space=2,
      end=b_, speed=0.5, phase=k / n)                                 # a packet running a -> b
b.arc(c, 14 * s, 15.4 * s, 0, TAU, col("dim"), segs=10, gap=0.35, spin=0.2, space=2)  # a spinning ring
b.text("ARGO CD", *c[:2], col("soft"), font="s", track=2, space=2, z=c[2], dx=-30, dy=-34)
```

**Shared holo renderer (solid models with parts).** For a real 3D object with
named parts, lit by live readings: `holo.render.Holo` + `holo.stage.Stage`. The
holo deck's compact model and the Ops theater's rack use it through
`live/holoview.CompactHolo`, which renders into its own target and is blended
over the deck in `post_composite()`:

```python
self.hv = holoview.CompactHolo(["rack"], scale=s)
def animate(self, t, d):              # before our passes
    self.hv.render(rw, rh, t)
def post_composite(self, u):          # after the composite, premultiplied alpha
    self.hv.composite((self.w, self.h), rect, u.get("fade", 1.0))
```

**Instanced custom geometry.** When many copies of one model must move every
frame (the swarm's ships), upload the model once and draw it instanced with
per-instance uniforms — see section 8.

## 3. Get real data in, cheaply

The rule: every value drawn is a real reading or a real event. Atmosphere and
the emblem are the only exceptions, and a missing reading says so
("NO LAB SNAPSHOT", "NO BARS YET · TO THE FILL PRICE") instead of inventing one.

Heavy reads only while the deck is open. `Deck3D.poll_every(fn, seconds, name)`
starts a thread that dies with the deck:

```python
self.poll_every(self._poll_herdr, 2, "herdr")     # ~8 ms a call
self.poll_every(self._poll_git, 60, "git")        # 50 repos ~2.9 s, off the render thread
self.poll_every(self._poll_ci, 180, "ci")         # gh, top repos only, cached 10 min on disk
```

Budgets that worked: anything under 50 ms every 2–5 s; seconds-long scans every
60 s; network APIs with quotas (gh) every few minutes and cached. Never block
`build()` or `frame()` on I/O; pollers write fields and set `self.built_at = None`
to request a rebuild.

Check `data-sources.md` for every source, its access path and its latency.

## 4. Listen to VECTOR

`live/vfeed.py` tails `$XDG_RUNTIME_DIR/bromigos-vector-events.jsonl` (schema in
`~/.config/bromigos/holo/README.md`, "Event feed"). In a deck, override
`on_event(e, t)`; `Deck3D.frame()` calls it for each new event about ten times a
second. `normalise()` maps the emitter's dotted names (`memory.recall`,
`tool.start`, `git.push`, …) to `recall`, `tool_start`, `git_push`, …

```python
def on_event(self, e, t):
    if e.get("type") == "recall":
        for mid in e.get("ids") or []:
            if mid in self.mem_ix:
                self.flare["mem:" + mid] = (t, "white")    # decays over 6 s in build()
        self.built_at = None
```

Decks should also observe the world themselves (the Ops theater reads push
reflogs and Prometheus), so they are alive when the feed is quiet.

## 5. Expose verbs

`bromigos-live <deck> <verb> [args]` reaches `command(verb, args)` on the open
deck, or opens it and queues the verb. Return one short line: it is printed for
the caller and shown on the deck as a toast. Keep verbs few and nouns natural:

```python
def command(self, verb, args):
    if verb == "trace":
        ...
        return f"tracing workstation → {name} ({len(path) - 1} hops)"
    return "netmap verbs: trace <host>, clear"
```

Document new verbs in the README's "Driving the holograms" table.

## 6. Build the look

Read `desktop-style-guide.md`. In short: a `frame_panel()` for the stage and one
for the side panel, a header with the data's provenance on the right, hover
readouts on everything (`hover_tip(b, label, lines, "CLICK TO …")`: what it is,
its live values, what a click does), palette tokens only, reveals on open
(`reveal=T + k`, `type_rate`) so panels assemble.

### Maps: zoom and level of detail

Any deck that is a map (a starfield, a constellation, a network, a system of
bodies) zooms. Mind, Swarm, Network and the Drift map all do it the same way, with
`live/zoomcam.py`; build new maps the same way.

- **Turn it on.** On a `Deck3D`, set `zoom = (min, max)` on the class (Mind
  `(0.7, 16)`, Swarm `(0.7, 9)`, Network `(0.7, 5)`). You get: scroll zooms toward
  the point under the cursor (eased, frame-rate independent, fine steps from touchpad
  deltas), left-drag pans while zoomed in and turns at 1×, Shift+drag or the right
  button turns, `+`/`-` zoom, double-click on empty space or `0` resets, a zoom
  readout in the panel's corner, and the 3D space clipped to the panel below its
  title. A deck that is not a `Deck3D` (the Drift map) holds a `ZoomCam` itself and
  forwards `scroll`, `dclick`, `+`/`-`/`0` and the pan drag to it, as `drift_map.py`
  does.
- **Detail grows with zoom, not with size.** Markers are drawn in pixels (`arc`
  radii times `s`), so zooming spreads points apart instead of inflating them. Read
  `self.cam.z` in `build()` and use `lod(z, z0, z1)` (0 below z0, 1 above z1) to fade a
  class of detail in. Clusters expand instead of spiderfying: Mind keeps each repo's
  documents close around their hub when zoomed out and opens them out as you zoom in
  (`_spread()`, `_doc_positions()`, computed for every document at once with numpy).
  Things drawn in model units that should stay readable rather than huge (Swarm's
  ships) scale by `z ** -0.45`.
- **Labels by room.** Never draw every label. Hand candidates to
  `labels = self.cam.labels(self.stage.atlas, self.stage.painter, self.s, cap=…)`
  with a priority, then `labels.place(b)` once: the highest priorities that land
  inside the panel without overlapping are drawn, up to the cap. `force=True` for the
  few that must always show (space names, the hovered or selected thing). Zoomed
  out only the important names fit; zooming in makes room for the rest. Cull first:
  project the points with numpy and only offer labels for what is on screen
  (Mind offers at most 240 document names).
- **Rebuilds follow the camera.** `Deck3D.render` rebuilds while the view moves, at
  most 12 times a second, and once when it settles; keep `build()` cheap (Mind: 5–7
  ms at any zoom, the others 1–2 ms).
- **VECTOR's verbs move the camera.** `self.fly_to(pick_id, zoom)` eases to centre a
  picked thing and follows it while it moves (Swarm passes a function of the ship's
  live position: `self.cam.fly_to(lambda: self._pos_of(tgt), 4.5)`);
  `self.cam.fit(points, rot, persp, zmax=…)` frames a set (Network frames a traced
  path); `clear` calls `self.cam.reset()`. A click by the operator does not move the
  camera.
- **Hover keeps working.** Picking projects with the live camera, so hover readouts
  work at every zoom; keep `pick_pts` in sync with what you draw (expanded positions,
  not the layout's).

## 7. Test headless, then on screen

Render without touching the desktop (NVIDIA EGL device):

```bash
cd ~/.config/bromigos-live
OFF_WARM=1 tools/offscreen.py mind "/tmp/x/mind_%.png" 1.0 2.0 4.0      # frames at those times
OFF_SCRIPT="1.0 cmd trace k8s-gpu-worker" tools/offscreen.py netmap /tmp/x/net_%.png 1 3 6 9
OFF_SCRIPT='1.0 event {"type":"recall","ids":["..."]}' tools/offscreen.py mind /tmp/x/m_%.png 1.5
BROMIGOS_VECTOR_EVENTS=/tmp/x/test.jsonl ...      # keep test events out of VECTOR's real feed
tools/offscreen.py ops /tmp/x/ops.mp4 12 30        # a clip
# maps: zoom, pan, reset and hover (2560x1440 coordinates; DY > 0 zooms out)
OFF_SCRIPT="2 wheel 1344 659 -5; 4 wheel 1344 659 -6; 6 drag 1100 680 900 600; 7 hover 890 706; 8 dclick 300 300" \
  tools/offscreen.py mind /tmp/x/z_%.png 1 2 3 4 5 6 7 8 9
```

For a map, render at least 1×, about 2.5× and the maximum, and a verb that flies
the camera; check that labels appear with zoom, never pile up, and stay inside the
panel. Ask for times one second apart when the deck moves things (ships), so the
animation runs between frames.

A deck with `ready()` is waited for (real data first). Look at every render
(downscale to 1280×720 to check legibility at 1080p): overlaps, clipped labels,
things outside the panel, unreadable text.

**Frame budget.** Measure with `glFinish()` around `render()` over 120 frames.
The five holograms: median 0.6–1.7 ms, p95 under 7 ms, against 33 ms at 30 fps.
Rebuilds (Python building the batch) are the spikes; rebuild at 0.1–0.5 s unless
something is animating geometry.

**Loops and seams.** For anything that loops, render frames just before, at and
just after the period boundary and compare the frame-to-frame difference at the
wrap with the mid-loop difference. They must match (the den loops measured
0.0059 vs 0.0064 for the streaks).

**On screen.** Overlays take the keyboard. Warn the operator before opening one
on his monitor during work; prefer offscreen renders.

## 8. Worked example: the starships

The Swarm's ships went from nothing to a live, status-lit fleet like this.

**Model.** `tools/make-starship.py` builds the hull procedurally (original design:
a long arrowhead in stacked plates, a swept relay-mast spire with the burn-in's
narrowing crossbars, an octagonal engine bank, running lights) and writes the
shared format, so any renderer can read it:

```python
PARTS = [("hull", ...), ("spire", ...), ("engines", ...), ("lights", ...), ("beacon", ...)]
np.savez_compressed(path, meta=json_bytes, pos=pos, nrm=nrm, part=part_u8, tri=tri, edge=edge)
```

Parts exist so status can light each one separately. A purchased or generated mesh
goes through the brand kit's bake tools (`brand/3d/tools/bake.py`) to the same
format.

**Instancing.** `live/starship.py` uploads the edges once as a static VBO of quads
(6 vertices per edge: both endpoints, a corner, the part id) and the triangles for
the faint shell, then draws every ship with one `glDrawArraysInstanced` per pass.
Per-ship state is uniform arrays indexed by `gl_InstanceID` (`shaders/ship.glsl`):

```glsl
uniform vec4 u_sp[32];   // position, scale
uniform vec4 u_so[32];   // yaw, pitch, roll, alpha
uniform vec4 u_sl[32];   // light levels: hull, spire, engines, running lights
uniform vec4 u_sc[32];   // status colour (lights + beacon), beacon level
```

**Status lights.** Python decides levels per ship per frame (`_ship_draw_list`):
working = everything lit and steady; idle = dimmed, engines at idle; blocked = an
amber beacon at a calm 0.55 Hz and the ship turns to face the viewer; error = a red
flicker, then it limps away; gone = lights fade, then it jumps. Blinks are slow
sines, never strobes.

**Arrival.** A new agent's ship starts far behind its station, runs a 0.6 s streak
(a bright line plus a wide faint one), flashes as it arrives, then decelerates into
station keeping. The live layer's `sweep` cue plays through `app.sound`, which
respects mute.

**Hover and click.** Ship positions go into `pick_pts`; hover shows agent, repo,
status and the last line of its output (read on hover only); a click opens a card
whose buttons hand the job to VECTOR (`bromigos-holo ask "…"`).

## 9. Wire it in and ship it

1. Key: a `K.exec("SUPER + …", live .. " <deck>")` line in `~/.config/hypr/hyprland.lua`, after
   the defaults (a personal plugin deck; a bromigOS deck's goes in bromigOS `desktop/hypr/bromigos/live.lua`).
   Check free keys first (`hyprctl binds -j`; skill `hyprland-config`, including its
   auto-reload rule), plus an `EXEC` row in bromigOS `widgets/keybinds.py`.
2. Docs: the key table in `~/.dotfiles/AGENTS.md` (`bromigos-docs keys`), verbs in `holo/README.md`.
3. Restart: `bromigos-live restart`.
4. Commit in reviewable steps with the house style (`Added:` / `Updated:`), and push.
