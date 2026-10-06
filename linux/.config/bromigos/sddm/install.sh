#!/usr/bin/env bash
# Install the Bromigos SDDM theme. Run by the operator with sudo:
#
#   sudo ~/.config/bromigos/sddm/install.sh
#
# Idempotent: every run rebuilds the theme from the dotfiles and puts the same files in
# the same places. It does not restart SDDM (that would end the session); the theme
# shows at the next boot or logout.
#
#   /usr/share/sddm/themes/bromigos      the theme (QML, Geist Mono, the rendered burn-in,
#                                        the lock-screen den: "empty" or "masked" only)
#   /usr/share/icons/Bromigos-cursor     the greeter's cursor (the desktop's own)
#   /etc/sddm.conf.d/20-bromigos.conf    [Theme] Current=bromigos, CursorTheme=Bromigos-cursor
#   /etc/sddm.conf                       its own Current= and CursorTheme= lines commented
#                                        out (that file outranks sddm.conf.d); the original
#                                        is kept once as /etc/sddm.conf.pre-bromigos
#
# sugar-candy stays installed. Back to it in one line:
#   sudo sed -i 's/^Current=bromigos$/Current=sugar-candy/' /etc/sddm.conf.d/20-bromigos.conf
set -euo pipefail

# BROMIGOS_SDDM_ROOT=/some/dir runs the whole install into a fake root (tests, no sudo)
ROOT="${BROMIGOS_SDDM_ROOT:-}"
if [[ $EUID -ne 0 && -z "$ROOT" ]]; then
    echo "run with sudo: sudo $0" >&2
    exit 1
fi

HERE="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
REPO="$(cd "$HERE/../../../.." && pwd)"
USER_NAME="${SUDO_USER:-}"
THEMES="$ROOT/usr/share/sddm/themes"
DEST="$THEMES/bromigos"
CURSOR_SRC="$REPO/linux/.local/share/icons/Bromigos-cursor"
CURSOR_DEST="$ROOT/usr/share/icons/Bromigos-cursor"
CONF_D="$ROOT/etc/sddm.conf.d"
CONF="$ROOT/etc/sddm.conf"
OWNER=root:root
[[ -n "$ROOT" ]] && OWNER="$(id -u):$(id -g)"
mkdir -p "$THEMES" "$(dirname "$CURSOR_DEST")"

# 1. build as the operator (reads the wallpaper choice from his home), in a temp dir
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
chmod 755 "$work"
if [[ $EUID -eq 0 && -n "$USER_NAME" && "$USER_NAME" != root ]]; then
    chown "$USER_NAME" "$work"
    home="$(getent passwd "$USER_NAME" | cut -d: -f6)"
    sudo -u "$USER_NAME" python3 "$HERE/build.py" "$work/bromigos" --home "$home"
else
    python3 "$HERE/build.py" "$work/bromigos"
fi

# 2. the theme, swapped in whole
rm -rf "$DEST.new"
cp -r "$work/bromigos" "$DEST.new"
chown -R "$OWNER" "$DEST.new"
rm -rf "$DEST"
mv "$DEST.new" "$DEST"
echo "theme:  $DEST"

# 3. the cursor, where the sddm user can read it
if [[ -d "$CURSOR_SRC" ]]; then
    rm -rf "$CURSOR_DEST"
    cp -rL "$CURSOR_SRC" "$CURSOR_DEST"
    chown -R "$OWNER" "$CURSOR_DEST"
    chmod -R a+rX "$CURSOR_DEST"
    echo "cursor: $CURSOR_DEST"
fi

# 4. select it
mkdir -p "$CONF_D"
cat > "$CONF_D/20-bromigos.conf" <<'EOF'
# Written by ~/.config/bromigos/sddm/install.sh. Back to the previous theme:
#   sudo sed -i 's/^Current=bromigos$/Current=sugar-candy/' /etc/sddm.conf.d/20-bromigos.conf
[Theme]
Current=bromigos
CursorTheme=Bromigos-cursor
EOF
echo "config: $CONF_D/20-bromigos.conf"

# 5. /etc/sddm.conf is read last and wins: stop it naming a theme or cursor of its own
if [[ -f "$CONF" ]] && grep -Eq '^(Current|CursorTheme)=' "$CONF"; then
    [[ -f "$CONF.pre-bromigos" ]] || cp -p "$CONF" "$CONF.pre-bromigos"
    sed -i -E 's/^(Current|CursorTheme)=/# (set in sddm.conf.d\/20-bromigos.conf) &/' "$CONF"
    echo "config: $CONF (Current= and CursorTheme= commented; original in $CONF.pre-bromigos)"
fi

echo
echo "Installed. It shows at the next boot or logout; SDDM was not restarted."
echo "Preview without logging out:  sddm-greeter-qt6 --test-mode --theme $DEST"
echo "Back to sugar-candy:          sudo sed -i 's/^Current=bromigos\$/Current=sugar-candy/' $CONF_D/20-bromigos.conf"
