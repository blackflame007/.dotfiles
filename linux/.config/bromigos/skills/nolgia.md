---
name: nolgia
description: How VECTOR makes images, video, audio and 3D with the host's own nolgia CLI — the tools, models and their credit prices, the daily budget, recipes (concept image, edit, video, sound effect, voice line, 3D concept), characters including the operator's likeness and its rules, reviewing every asset before presenting it, and where assets go (brand kit or a repo, committed).
when_to_use: "Making or editing an image, video clip, sound effect, music or voice line, a concept for a 3D model, a portrait or any brand asset; choosing a nolgia model; anything about nolgia credits."
---

# Making media with nolgia

nolgia (`~/.cargo/bin/nolgia`) is the host's own product (Nolgia, his company). Speak of
it plainly, as a product. The installed CLI is the authority: `nolgia_read "models get
<id>"` before relying on a model's options.

## The tools

| Tool | Use |
|------|-----|
| `nolgia_catalog modality` | models for image, video, audio or 3d, cheapest first, with credits |
| `nolgia_credits` | balance, today's spend, the daily cap |
| `nolgia_read "<cmd>"` | read-only CLI: `models get <id>`, `characters list`, `characters get <id>`, `assets list`, `assets get <id>`, `projects list`, `status <job>`, `wait <job>` |
| `nolgia_generate kind prompt …` | one image, video or audio clip, under the budget, with a vision review of images and video |
| `nolgia_review path question` | look at any image or video frame |

Generation from your raw terminal is refused, so the budget can't be skipped.

## Credits (always)

1. Pick the cheapest model that does the job (`nolgia_catalog`). Say the estimate before
   you generate: "about 2 credits".
2. The daily cap is `daily_credits` in `holo/nolgia.json` (20 to start). Over the cap,
   `nolgia_generate` returns `needs_approval`: ask the host with the number, and only
   after he says yes call again with `approved: true` (it is refused unless he answered
   after you asked).
3. Every job is logged to `~/.local/state/bromigos/nolgia-spend.jsonl`. In your answer,
   say what it cost and the credits left.

Reference prices (check the catalog, they change): images: ideogram-v4 1, flux-2-klein /
flux-schnell / flux-2-pro 2, flux-pro 4, gpt-image-2.5-flare 8 (best for portraits and
edits with references), quality tiers 2k/4k cost much more. Video: kling-v2-5-turbo 12 a
clip, veo-3.1-lite 14. Audio: elevenlabs-sound-effects-v2 4, stable-audio-3-medium 3,
TTS per character (inworld-tts 1 credit per 1,800 characters). 3D: trellis 2,
hunyuan3d-v3 21 (prefer procedural geometry; see `hologram-build.md`).

## Recipes

- **Concept image:** `nolgia_generate image "<subject>, <style>, <composition>"
  model=flux-2-klein aspect_ratio=16:9`. For a 3D concept, end the prompt with the
  isolation block from `brand/3d/README.md`: *"Isolated 3D product render on a plain pure
  white background, whole object fully in frame with margin, three-quarter view from
  slightly above, soft even studio lighting, no cast shadow, no text, no logos, no people,
  crisp hard-surface modelling with clear separable parts."*
- **Edit an image:** `input=<file or asset id>` on a model that takes references
  (`refs` > 0 in the catalog), e.g. gpt-image-2.5-flare; say what to change and what to
  keep.
- **Video:** `nolgia_generate video "<shot>" model=kling-v2-5-turbo duration_seconds=5`
  (it asks the API for the exact price first).
- **Sound effect:** `nolgia_generate audio "<sound>, short, clean" model=elevenlabs-sound-effects-v2`.
- **Voice line:** a TTS model and `voice=<id>` (`nolgia_read "models get <model>"` lists
  voices). Never clone a real person's, a game's or a film's voice.

## Characters

`nolgia_read "characters list"`. `character_id=<id>` keeps a likeness consistent.

- **BLACKFLAME (operator likeness)**, `06c2b001-0154-4a87-a5f4-5e8bf81844e5`: the host's
  own likeness, for his personal art only. It is out of canon: in the lore BLACKFLAME's
  face is never seen (the emblem covers it in footage), so likeness art never goes on the
  desktop as lore. Never show his employer's logo, badge or name. The existing portraits
  and their prompts are in `brand/README.md` (portraits/): hood up, dark wraparound
  shades, over-ear headphones, phosphor-green rim light on a void.

## Style (the house look)

- Palette from `brand/palette.json`: phosphor `#39ff14`, soft `#9cff8a`, dim `#159b09`,
  guard `#003b00`, void `#000500`, amber `#d4af37`, danger `#ff766f`. Retro sci-fi HUD,
  phosphor green on near-black. See `desktop-style-guide.md`.
- Original designs only: no franchise characters, ships, logos or lettering copied.
- No text in generated images unless needed (models garble it); add type locally.

## Review before presenting (always)

`nolgia_generate` returns a `review` from the vision model for images and videos. Read
it. If it says the subject is wrong, text is garbled, or a logo appeared, regenerate or
fix it (counting the cost) before you show it. Never present an asset you haven't looked
at. For audio, say what you asked for and that you haven't listened to it.

## Where assets go (and they're tracked)

- Brand assets: `~/.config/bromigos/brand/<area>/` (the dotfiles). Add a row to the
  brand README (file, use, model, prompt) and commit in the dotfiles style
  (`Added: …`), then push.
- For a repo: its own assets folder, committed and pushed there.
- One-offs the host asked for: `~/Pictures`, `~/Music`, `~/Videos` (not tracked; say
  where it is).
- Scratch: the default `~/.local/share/bromigos/nolgia/<date>/`.
- `changes_check` before you report done.
