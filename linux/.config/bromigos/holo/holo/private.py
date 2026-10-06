"""The operator's private values for the holo package (VECTOR, the gallery): see
~/.config/bromigos/lib/bromigos_private.py. Empty on a fresh clone."""
import os
import sys

_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
import bromigos_private as PRIV  # noqa: E402,F401

_PLACEHOLDER = None


def fill(text):
    """{{endpoints.lab}}-style placeholders -> the private overlay's values. Prompts and
    skills are public files; the operator's addresses and Vault paths reach VECTOR only
    through here. A key the overlay lacks stays visible as <endpoints.lab>."""
    import re
    global _PLACEHOLDER
    if _PLACEHOLDER is None:
        _PLACEHOLDER = re.compile(r"\{\{([a-z_]+(?:\.[a-z_]+)+)\}\}")

    def one(m):
        v = PRIV.get(m.group(1))
        return str(v) if isinstance(v, (str, int, float)) and v != "" else f"<{m.group(1)}>"
    return _PLACEHOLDER.sub(one, text)
