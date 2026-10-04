"""Plain text for the hologram and the voice: models sometimes answer in markdown
(Nemotron likes bold and bullets); VECTOR's words are shown as holographic text and
read aloud, so the markup goes."""
import re

_BOLD = re.compile(r"(\*\*|__)(.+?)\1", re.S)
_EM = re.compile(r"(?<![\w*])([*_])(?!\s)(.+?)(?<!\s)\1(?![\w*])", re.S)
_CODE = re.compile(r"`{1,3}([^`]*)`{1,3}")
_HEAD = re.compile(r"^\s{0,3}#{1,6}\s*", re.M)
_BULLET = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+", re.M)
_LINK = re.compile(r"\[([^\]]+)\]\((?:[^)]+)\)")
# Roleplay the fallback model adds despite the persona:
#  * stage directions: "*VECTOR blinks, then smiles.*", "*waves*", "*a bit of static*"
#  * speaker labels: "**vector**: Oh!", "VECTOR: Right."
# A single-asterisk span of two or more words, or one action verb, is a direction and
# goes; a single other word ("*me*") is emphasis and keeps the word.
_STAR = re.compile(r"(?<![\w*])\*(?!\s|\*)([^*\n]+?)(?<!\s)\*(?![\w*])")
_SPEAKER = re.compile(r"^\s*(?:\*\*|__)?\s*vector\s*(?:\*\*|__)?\s*:\s*(?:\*\*|__)?\s*", re.I | re.M)
_VERBS = re.compile(r"^(?:blinks?|nods?|waves?|smiles?|grins?|laughs?|chuckles?|giggles?|sighs?|shrugs?|"
                    r"winks?|beams?|gestures?|pauses?|coughs?|gulps?|fidgets?|flickers?|crackles?|hums?|"
                    r"beeps?|whirs?|buzz(?:es)?|static|silence|ahem|ahem\.?)$", re.I)


def _star(m):
    inner = m.group(1).strip()
    if " " in inner or _VERBS.match(inner):
        return ""
    return inner


def plain(text, bullets="· "):
    t = _SPEAKER.sub("", text)
    t = _LINK.sub(r"\1", t)
    t = _CODE.sub(r"\1", t)
    t = _BOLD.sub(r"\2", t)
    t = _STAR.sub(_star, t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\s+([,.!?…])", r"\1", t)        # "words *waves* ." -> "words."
    t = re.sub(r"(?m)^\W*$\n?", "", t) if t.strip() else t
    t = re.sub(r"^[ \t]+|[ \t]+$", "", t, flags=re.M)
    t = _EM.sub(r"\2", t)
    t = _HEAD.sub("", t)
    t = _BULLET.sub(bullets, t)
    t = t.replace("**", "")
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def spoken(text):
    """For the voice: no markup, no bullet glyphs, newlines become pauses."""
    t = plain(text, bullets="")
    t = re.sub(r"([.!?:;,…])\s*\n+\s*", r"\1 ", t)       # a line that already ends in punctuation
    return re.sub(r"\s*\n+\s*", ". ", t).strip()
