# Bromigos / BLACKFLAME brand kit

The house palette is in `palette.json`, `palette.css` and `kitty-colors.conf`. The canon emblem (the burn-in) sources are `emblem*.svg`, rebuilt with `bromigos-emblem build`. The canon Bromigos logo is `bromigos-logo.png`, the hooded operator with shades and headphones. Everything below is new and builds on those files; nothing here replaces them.

`contact-sheet.jpg` shows every asset on one page.

**How the assets were made**

- **AI images:** the [nolgia](https://nolgia.ai) CLI.
- **The operator's likeness:** the nolgia character **BLACKFLAME (operator likeness)**, id `06c2b001-0154-4a87-a5f4-5e8bf81844e5`. It was built from a head-and-shoulders crop of the operator's photo. The source photo is not in this repo.
- **Vectors:** `potrace`, filled with the exact palette hex.
- **Lockups, overlay and sting:** built locally from the canon SVGs and Geist Mono, with text converted to paths.

**Canon rules these assets keep (agents/LORE.md, "BLACKFLAME"):**

- The burn-in ring never names BLACKFLAME and never shows the frequency.
- In BLACKFLAME footage, the emblem covers his face.
- The BLACKFLAME wordmark is for video titles only. It never goes on the desktop or inside the ring.
- Nothing here borrows from other franchises.

## portraits/

All portraits use the nolgia character, so the likeness stays consistent.

| File | Use | How |
| --- | --- | --- |
| `blackflame-hero-2048.jpg`, `-512.jpg` | Profile picture: hood up, shades, headphones, phosphor rim light on void | gpt-image-2.5-flare + character. Prompt: "Stylized cinematic hero portrait of the man from the reference photo, a covert radio operator. Chest-up, slight three-quarter angle, solid broad-shouldered build. A worn dark hoodie with the hood UP, dark rectangular wraparound sunglasses, large over-ear studio headphones worn over the hood. His short, full dark beard and jawline clearly visible. Lit only by a phosphor-green rim light from behind … pure near-black void … Monochrome phosphor green (#39ff14) and black … retro sci-fi codec-operator mood … Slightly lower camera angle, a faint glow of a monitor reflected in the sunglasses." |
| `blackflame-hero-16x9-2560x1440.jpg`, `-512.jpg` | Video-intro still. He sits on the right third; the left two thirds are left free for titles | gpt-image-2.5-flare, using the hero as input + the character. Prompt: "Recompose this exact portrait … as a 16:9 widescreen video intro still … right third of the frame … confident closed-mouth half smile. The left two thirds are a deep near-black void with very faint phosphor-green radio static … left empty for titles." |
| `blackflame-hero-cutout-2048.png`, `-512.png` | Transparent cutout of the hero for thumbnails and compositing | nolgia `remove-background` |
| **`blackflame-burn-in-2048.jpg`**, `-512.jpg` | **The signature piece.** The network's answer to "who is BLACKFLAME": the burn-in sits over his face, glitching | Built locally: the canon `emblem-2048.png` over the hero, on a void disc. Adds the ring glow, a 16% burn-in ghost offset, scanline tears with green colour bleed, and phosphor scan lines. Built to the "Footage" rule in the lore. |
| `blackflame-burn-in-16x9-2560x1440.jpg`, `-512.jpg` | The same piece in 16:9, for video | The same composite over the 16:9 hero |
| `blackflame-cel-2048.jpg`, `-512.jpg` | Graphic-novel, cel-shaded version for merch and thumbnails | gpt-image-2.5-flare, using the hero as input + the character. Prompt: "Turn this portrait … into a graphic-novel cel-shaded illustration: bold clean black ink outlines, two or three flat tones of phosphor green (#39ff14, #159b09, #003b00) and solid black shadows …" |
| `blackflame-cel-cutout-2048.png`, `-512.png` | Transparent cel cutout for stickers and merch | nolgia `remove-background` |
| `blackflame-lineart.svg`, `-2048.png`, `-512.png` | Minimal line art for stickers, merch and engraving. Recolour it via the `fill` in the SVG | gpt-image-2.5-flare, then potrace. Prompt: "… minimal single-weight line art for a sticker: clean continuous white lines on a pure black background, no shading … the hood, rectangular sunglasses, large over-ear headphones, the outline of his short full beard and smile, shoulders." |
| `blackflame-sticker.svg`, `-2048.png`, `-512.png` | A die-cut style sticker with a thick outline | gpt-image-2.5-flare, then potrace. Prompt: "… minimal flat sticker icon: solid white shapes on a pure black background with a thick uniform outline, very simplified like a vector emblem …" |

## logos/

All logos are transparent and in exact palette hex. Each comes as an SVG (true vectors, text as outlines) plus 2048 and 512 PNGs. Marks sit on square canvases; wordmarks and lockups are 2048 wide.

**The Bromigos variants** were traced from the canon `bromigos-logo.png`, so the identity is unchanged. The canon logo itself stays as it is.

| File | Use | How |
| --- | --- | --- |
| `bromigos-lockup-horizontal.*` | Site headers, video end cards, letterhead | Canon glyph + "BROMIGOS" in Geist Mono 700 + a "THE NETWORK" subline. Phosphor, with a phosphor-dim subline. |
| `bromigos-lockup-horizontal-amber.*` | Monochrome amber (#d4af37): print, merch, anywhere green would clash | Same build, all amber |
| `bromigos-lockup-stacked.*`, `-stacked-amber.*` | Square spots: avatars with a name, merch fronts | Glyph above the wordmark |
| `bromigos-glyph.*`, `bromigos-glyph-amber.*` | The glyph alone, as a clean vector | potrace of the canon logo |
| `bromigos-favicon.svg`, `.ico`, `-16/32/48/180/512/2048.png` | Favicon-scale glyph: a void tile with a phosphor-dim border. The glyph is slightly emboldened so it survives 16–32 px | Local SVG. `-180` is the Apple touch icon. |
| `arbiter-mark.*` | **ARBITER**, the market's referee (the Floor): an A whose crossbar is a level balance beam, with candlesticks rising inside it | recraft-v4.1, then potrace. Prompt: "Logo for ARBITER, the market's referee. A bold geometric letter A whose crossbar is a level balance beam, with three ascending candlestick bars rising inside the A. The word ARBITER below in a wide, bold monospace typeface. Flat vector logo mark, single colour …" |
| `arbiter-glyph.*` | The ARBITER A alone, for the app icon or favicon | The same source, cropped above the text |
| `echocraft-wick-mark.*` | **EchoCraft Lab / the Wick**: a server rack drawn as a candle, with one lit wick. The lit rack room. | recraft-v4.1, then potrace. Prompt: "Logo for ECHOCRAFT LAB, nicknamed the Wick: a tall server rack drawn as a candle, with a single small lit wick flame on top, and three horizontal rack units with indicator dots …" |
| `echocraft-wick-glyph.*` | The rack-candle alone | The same source, cropped |
| `echocraft-relay-badge.*` | Alternative: a relay mast over rack units, in a badge. The relay station. | recraft-v4.1, then potrace. Prompt: "… a radio relay mast rising from a stack of server rack units, with two concentric signal arcs … inside a rounded square badge …" |
| `blackflame-wordmark.*` | **BLACKFLAME wordmark, for video titles only.** Not for the desktop, and never inside the ring. | recraft-v4.1, then potrace. Prompt: "Wordmark only: the single word BLACKFLAME … A bold, wide, custom retro sci-fi display typeface with squared corners, like an 80s computer terminal title card, with thin horizontal scanline cuts through the lower half of the letters." |
| `blackflame-wordmark-dial.*` | Alternative: a thin extended wordmark with a tuning-dial underline | recraft-v4.1, then potrace. Prompt: "… A wide extended monospace typeface with generous tracking … a thin underline beneath the word with small tick marks like a tuning dial." |

## video/

| File | Use | How |
| --- | --- | --- |
| `burn-in-intercept-sting-1080p.mp4` (9.1 s, 3.5 MB, H.264 + AAC) | Stream and video intro or transition: the burn-in takes the feed | Rendered locally from `emblem-ring.svg` and `emblem-flame.svg`, following the canonical intercept sequence. The intercepted feed is the operator den wallpaper. Sound comes from the live layer's `hiss`, `sweep`, `blip` and `signoff` wavs. See the timings below. |
| `burn-in-intercept-sting-poster.jpg` | Poster frame for the sting | — |

The sting's timings:

1. **Hold**, 0.25 s.
2. **Tear**, 0.4 s, with the colour bleeding to green.
3. **Ring sweep**, 0.5 s. A needle crosses the dial; the ticks and text land first, then the lines.
4. **Flame**, 0.4 s. It burns in from base to tip.
5. **Turn.** The ring turns counter-clockwise at 1 revolution per 24 s, and `TRANSMISSION INTERCEPTED` types in.
6. **Sign-off.** `STILL LIT.` types in, the emblem cuts to black in one frame, and a 15% ghost fades over 3 s.

## overlays/

| File | Use | How |
| --- | --- | --- |
| `stream-overlay.svg`, `-1080p.png`, `-1440p.png`, `-512.png` | OBS stream frame with a transparent centre. It has: <br>• a Bromigos ident, top left; <br>• an ON AIR panel with a tuning dial and CH 142.59, top right; <br>• a "NOW TRANSMITTING" lower third, where the title goes in an OBS text source; <br>• a codec cam window, bottom right; <br>• a STILL LIT. tag. | Local SVG |
| `youtube-banner-2560x1440.jpg`, `-512.jpg` | YouTube channel banner. The lockup and the tagline "SIGNALS · RELAYS · MACHINES THAT THINK" sit inside the 1546x423 safe area for all devices. | Background from gpt-image-2.5-flare; lockup composited locally. Prompt: "Ultra-wide panoramic channel banner background art, no text. Deep space … wrecked, patched orbital relay stations and dead radio masts strung across the far left and far right edges … The central horizontal band is calm, dark and nearly empty … A single hand-rebuilt relay mast on a derelict station at the far right glows faintly, with a small black flame shape scorched into its housing." |

## wallpaper/ (and `~/.config/wallpaper/`)

The live files sit in `wallpaper/.config/wallpaper/`. The files in `brand/wallpaper/` are symlinks to them. Switch between them with:

```
bromigos-wallpaper              # show the current one and the choices
bromigos-wallpaper den|empty|masked|v1
```

The command lives at `~/.config/bromigos/bin/bromigos-wallpaper`, symlinked into `~/.local/bin`. Each switch does four things:

1. Repoints the canonical symlinks: `bromigos-den-2560x1440.jpg` (swaybg and the live layer's base plate) and `bromigos-lock-2560x1440.jpg` (hyprlock).
2. Updates `den_fit_sha1` in the live layer config.
3. Restarts swaybg.
4. Runs `bromigos-live ctl reload`.

Every variant is composited onto the v1 plate, with only the figure and desk region replaced. The CRT, meter and floor-grid rects that the live layer draws into are pixel-identical across variants, so the den overlays stay fitted.

| File | Scene | How |
| --- | --- | --- |
| `bromigos-den-operator-2560x1440.jpg` | The Wick, with the operator at the desk in three-quarter rear view. Short hair and beard in profile, hood down, the shades and headphones. The left third is untouched. | gpt-image-2.5-flare, using the v1 den as input + the character. Only the figure region was composited back. Prompt: "Edit this wallpaper. Keep the entire composition … Replace ONLY the hooded figure on the right with the man from the reference photo … three-quarter rear view with his face in profile … Short dark brown hair, faded short on the sides, and a short full dark beard clearly visible … hood pushed DOWN … No long hair." |
| `bromigos-den-empty-2560x1440.jpg` | The same den with nobody in it. The chair is empty and turned, as if he just stepped away. The headphones and folded shades sit by the keyboard, and the mug is still steaming. | gpt-image-2.5-flare, using the v1 den as input. The figure and desk region were composited back. Prompt: "… Remove the person completely … The operator's worn chair … is now EMPTY and turned slightly away … A pair of large over-ear studio headphones … rests on the desk beside the keyboard, with dark sunglasses folded next to them, and the metal mug … has a thin wisp of steam rising." |
| `bromigos-den-masked-2560x1440.jpg` | The operator den, with the burn-in over his face (the in-canon footage rule) | Local burn-in composite |
| `bromigos-den-2560x1440-v1.jpg` | The original plate | — |
| `bromigos-lock-{operator,empty,masked}-2560x1440.jpg`, `bromigos-lock-2560x1440-v1.jpg` | The hyprlock background for each variant | The den variant with a Gaussian blur of 3.5 and a gain of about 0.24. This transform was fitted to reproduce the original lock image. |

## Credits

The nolgia generation for this kit cost **158 credits** at list price. That covers:

- 9 recraft-v4.1 logo options (4 each, 36 credits);
- 15 gpt-image-2.5-flare images (8 each, 120 credits): 6 portraits, 5 wallpapers, 2 banners and 2 line-art passes;
- 2 remove-background runs (1 each).

The emblem-over-face composites, the vectors, the lockups, the overlay and the sting were built locally and cost nothing.
