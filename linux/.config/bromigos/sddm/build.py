#!/usr/bin/env python3
"""Build the Bromigos SDDM theme into a directory, from the dotfiles alone.

  build.py OUT [--test-shots DIR] [--variant empty|masked] [--home DIR]

Copies the QML theme (bromigos/), Geist Mono and its licence, renders the burn-in's
two parts with the brand kit's own emblem code (assets/ring.png: the motto ring with
its glow, which the theme turns; assets/flame.png: the halo and the flame, which hold
still), and picks the den for the background by the lock screen's rules:

  * the lock-screen variant of the den the operator chose (bromigos-wallpaper keeps the
    choice in ~/.local/state/bromigos/wallpaper/variant);
  * only the "empty" or "masked" variants: the login screen is seen by anyone at the
    desk, so a variant with the operator in it falls back to "empty".

Run as the operator, or by install.sh under sudo (then the choice is read from
$SUDO_USER's home). Needs python3-gobject with Rsvg (the brand kit's renderer).
Nothing here reaches the network.
"""
import argparse
import os
import pwd
import re
import shutil
import sys

HERE = os.path.dirname(os.path.realpath(__file__))              # .../linux/.config/bromigos/sddm
BROMIGOS = os.path.dirname(HERE)                                 # .../linux/.config/bromigos
REPO = os.path.realpath(os.path.join(BROMIGOS, "..", "..", ".."))
THEME_SRC = os.path.join(HERE, "bromigos")
FONTS = os.path.join(REPO, "fonts", ".local", "share", "fonts", "GeistMono")
WALLPAPERS = os.path.join(REPO, "wallpaper", ".config", "wallpaper")
SAFE_VARIANTS = ("empty", "masked")

sys.path.insert(0, os.path.join(BROMIGOS, "lib"))
import bromigos_emblem as E  # noqa: E402


def operator_home():
    user = os.environ.get("SUDO_USER")
    if user and user != "root":
        return pwd.getpwnam(user).pw_dir
    return os.path.expanduser("~")


def chosen_variant(home):
    try:
        with open(os.path.join(home, ".local", "state", "bromigos", "wallpaper", "variant")) as f:
            v = f.read().strip()
    except OSError:
        v = ""
    return v if v in SAFE_VARIANTS else "empty"


def render_emblem(out, size=1024):
    ring = E.svg(parts=("ring",), glow=True, size=size)
    flame = E.svg(parts=("halo", "flame"), size=size)
    # the ring's glow pads its viewBox by 40 units; give the flame the same frame so they align
    flame = flame.replace('viewBox="0 0 1000 1000"', 'viewBox="-40 -40 1080 1080"', 1)
    E.render_png(ring, os.path.join(out, "ring.png"), size)
    E.render_png(flame, os.path.join(out, "flame.png"), size)


def set_conf(path, values):
    with open(path) as f:
        text = f.read()
    for k, v in values.items():
        text, n = re.subn(rf"(?m)^{re.escape(k)}=.*$", f"{k}={v}", text)
        if not n:
            text += f"{k}={v}\n"
    with open(path, "w") as f:
        f.write(text)


def build(out, test_shots="", variant=None, home=None):
    if os.path.exists(out):
        shutil.rmtree(out)
    shutil.copytree(THEME_SRC, out, ignore=shutil.ignore_patterns("*.qmlc", "__pycache__"))
    os.makedirs(os.path.join(out, "fonts"), exist_ok=True)
    for name in os.listdir(FONTS):
        if name.endswith(".ttf") or name == "OFL.txt":
            shutil.copy2(os.path.join(FONTS, name), os.path.join(out, "fonts", name))
    assets = os.path.join(out, "assets")
    os.makedirs(assets, exist_ok=True)
    render_emblem(assets)
    v = variant if variant in SAFE_VARIANTS else chosen_variant(home or operator_home())
    shutil.copy2(os.path.join(WALLPAPERS, f"bromigos-lock-{v}-2560x1440.jpg"), os.path.join(assets, "background.jpg"))
    ident = E.identity()
    set_conf(os.path.join(out, "theme.conf"), {
        "caption": ident.get("caption", "TRANSMISSION INTERCEPTED"),
        "signoff": ident.get("signoff", "STILL LIT."),
        "ringSeconds": str(ident.get("ring_seconds_per_turn", 24)),
        "testShots": test_shots,
    })
    for root, dirs, files in os.walk(out):                     # readable by the sddm user
        os.chmod(root, 0o755)
        for f in files:
            os.chmod(os.path.join(root, f), 0o644)
    return v


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("out")
    ap.add_argument("--test-shots", default="")
    ap.add_argument("--variant", choices=SAFE_VARIANTS)
    ap.add_argument("--home", help="the operator's home (where the wallpaper choice is kept)")
    a = ap.parse_args()
    v = build(os.path.abspath(a.out), a.test_shots, a.variant, a.home)
    print(f"built {a.out} (den variant: {v})")


if __name__ == "__main__":
    main()
