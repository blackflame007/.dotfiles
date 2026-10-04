"""Plain text for the hologram and the voice: models sometimes answer in markdown
(Nemotron likes bold and bullets); PILOT's words are shown as holographic text and
read aloud, so the markup goes."""
import re

_BOLD = re.compile(r"(\*\*|__)(.+?)\1", re.S)
_EM = re.compile(r"(?<![\w*])([*_])(?!\s)(.+?)(?<!\s)\1(?![\w*])", re.S)
_CODE = re.compile(r"`{1,3}([^`]*)`{1,3}")
_HEAD = re.compile(r"^\s{0,3}#{1,6}\s*", re.M)
_BULLET = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+", re.M)
_LINK = re.compile(r"\[([^\]]+)\]\((?:[^)]+)\)")
# Roleplay stage directions ("*PILOT blinks, then smiles.*", "*waves*"): PILOT is told
# never to use asterisks, so a single-asterisk span is an action, not emphasis. Drop it.
_ACTION = re.compile(r"(?<![\w*])\*(?!\s|\*)[^*\n]+?(?<!\s)\*(?![\w*])")


def plain(text, bullets="· "):
    t = _LINK.sub(r"\1", text)
    t = _CODE.sub(r"\1", t)
    t = _BOLD.sub(r"\2", t)
    t = _ACTION.sub("", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
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
