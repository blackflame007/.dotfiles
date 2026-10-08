#!/usr/bin/env python3
"""Render VECTOR's four reference voices ONCE through Fish Audio, then everything is local.

    voices/make-refs.py            render any missing reference (never re-renders an existing one)
    voices/make-refs.py --force    render all four again

The voices are the operator's own Fish models from the Brodec cast: four "designed v1" voices
made from text descriptions, and revolver_lynx, a private copy of a generic unnamed library
narrator. Nobody's voice is cloned; ids in platform agents/wolfpack/<name>.yaml.
Output: ~/.local/share/bromigos/voices/<role>-<name>.wav (24 kHz mono) plus a .txt with the
exact transcript, which Qwen3-TTS needs to speak in that voice locally. Not committed.
Key: ~/.local/share/bromigos/fish-audio-key (from Vault through `bromigos-secrets sync`).
Cost: about 300 characters each, a few cents in total. References run 15-21 s: long
enough to carry the voice, short enough that every spoken line still starts in ~0.2 s.
"""
import json
import os
import subprocess
import sys
import urllib.request
import wave

OUT = os.path.expanduser("~/.local/share/bromigos/voices")
KEYFILE = os.path.expanduser("~/.local/share/bromigos/fish-audio-key")
VOICES = {  # role: (character, fish model id, text in that role's register, ~30 s)
    "main": ("governor_voss", "652612244816424bb0a8cf65132eea33",
             "Good evening, host. Everything at the arrivals pad is running exactly as it should, and I am delighted "
             "to hear from you. The line is open, the relays are quiet, and the kettle, so to speak, is on. Do tell me "
             "what you need; I have all the time in the world, and protocol, as ever, is wise. Shall we begin?"),
    "robot": ("sigil", "eb7e306c63ae4adeb30c40f19f25273d",
              "Status report. Six of six nodes ready. Thirty-four of thirty-four services answering. Cluster load, "
              "eleven percent. GPU temperature, forty-four degrees. Drawdown, four point five percent against a five "
              "percent limit. Running scan. Scan complete. No anomalies logged. All systems nominal. End of report."),
    "scientist": ("professor_arc", "a2945e9a5cff4f77a6860adf93c5caa3",
                  "Oh, now this is the good part! You see, the speech model doesn't just read the words, it predicts the "
                  "sound twelve times a second and hands each guess to the next one, like a relay! And the clever bit, "
                  "the really clever bit, is that it starts talking before it has even finished thinking. Isn't that "
                  "wonderful? Isn't that just marvellous?"),
    "notify": ("lin_yao", "abf16d90c4f54769ad55e49ba12a1303",
               "Incoming transmission. A paper fill on the Floor: buy, thirty-five shares, at the open. Logged. Notice: "
               "the lab reports one alert firing on the rack, nothing urgent. Logged. A message for the host is "
               "waiting on the console. A long job has finished, and it finished cleanly. That is all for now. Logged."),
    "floor": ("revolver_lynx", "acdea3740c984899be481001f0ac6521",
              "Right, here's the Floor tonight. The paper book's up a touch, eighty-nine percent sitting in cash, and "
              "the lineup took two small fills before the close: a long in the commodities fund and a trim on tech. "
              "Drawdown's four and a half percent, under the five percent line. No real money anywhere near it. "
              "That's the tape, and the tape doesn't lie."),
}


def key():
    if os.path.exists(KEYFILE):
        return open(KEYFILE).read().strip()
    sys.exit(f"no Fish Audio key at {KEYFILE}; run `bromigos-secrets sync` (it comes from Vault)")


def render(ref, text, k):
    body = {"reference_id": ref, "text": text, "format": "wav", "sample_rate": 24000, "normalize": True}
    req = urllib.request.Request("https://api.fish.audio/v1/tts", data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": "Bearer " + k, "Content-Type": "application/json",
                                          "model": "s1"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def main():
    force = "--force" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    k = None
    for role, (name, ref, text) in VOICES.items():
        wav = os.path.join(OUT, f"{role}-{name}.wav")
        if os.path.exists(wav) and not force:
            print("have", wav)
            continue
        k = k or key()
        data = render(ref, text, k)
        # Fish streams the wav with a placeholder length; rewrite a clean header
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "-", "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", wav],
                       input=data, check=True)
        with wave.open(wav) as w:
            secs = w.getnframes() / w.getframerate()
        with open(wav[:-4] + ".txt", "w") as f:
            f.write(text + "\n")
        print(f"wrote {wav} ({secs:.1f} s, {len(text)} chars)")


if __name__ == "__main__":
    main()
