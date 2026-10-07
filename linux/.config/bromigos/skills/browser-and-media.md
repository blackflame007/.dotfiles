---
name: browser-and-media
description: How VECTOR opens web pages and videos in Sir's browser and controls what's playing — find the link, open it in a new tab, check it started, then play, pause, skip, seek and set the volume — and what he can't do in the browser.
when_to_use: Sir asks to play or put on a video, song, stream or YouTube, to open a website or link, to pause, resume, skip, rewind or turn something up or down, or asks what's playing.
triggers: '\b(youtube|video|music|song|playlist|stream|podcast|spotify|play|pause|resume|unpause|skip|rewind|fast.?forward|volume|turn (it )?(up|down)|what''?s playing|browser|tab|website|web ?page|open (a |the )?(link|site|url))\b'
---

# Browser and media

## Play a video

1. **Find a real link.** `web_search` with `site:youtube.com` and what they asked for
   ("lofi hip hop radio site:youtube.com"). Take a `youtube.com/watch?v=…` URL
   from the results. Never make up a video id.
2. **Open it:** `launch` with the URL. It opens in a **new tab** of Sir's browser
   (Chrome), in front. Don't launch the browser first, and never use the terminal
   (`xdg-open`) for this; `launch` is the way.
3. **Check it started:** a few seconds later, `media` status. The tab shows up as a
   `chromium.instance…` player with the video's title. If it's `Paused` (browsers
   sometimes block autoplay), `media` play.
4. Say in one line what's playing (the title from `media`, not your guess).

## Control what's playing

`media`: `play`, `pause`, `toggle`, `next`, `previous`, `stop`, `seek` (`+10`, `-30`
or an absolute second), `volume` (`0-100`, `+10`, `-10`). `status` lists every player
with its title, position and volume. With several players, pass `player` from status;
otherwise the most recent one is used.

- "Pause it" / "turn it down a bit": act straight away, then confirm in a few words.
- `volume` sets the player's own volume. The system volume is Sir's (his knob).

## What you can't do in the browser

You can open pages in new tabs and control media. You can't click inside a page, type
into it, read it, or switch or close individual tabs. To look at a page, use `web_fetch`
on its URL; to see the screen, `look` (only when asked). `window` can focus or close the
whole browser window (say so first). If they need more, say plainly what's missing.
