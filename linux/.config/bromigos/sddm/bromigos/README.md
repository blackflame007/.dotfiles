# bromigos — the SDDM login theme

The login screen at boot, matching the hyprlock lock screen: the dimmed den behind the
burn-in, "TRANSMISSION INTERCEPTED", a big clock and a terminal-style sign-in, phosphor on
void, Geist Mono. Added to what the lock screen has: the account, the session chooser and
the power actions.

**Status:** active. SDDM 0.21 on Wayland, Qt 6 greeter (`QtVersion=6`). Source here,
built and installed by `../install.sh` (the operator runs it with sudo). sugar-candy stays
installed as the fallback.

```bash
sudo ~/.config/bromigos/sddm/install.sh                       # build + install (idempotent)
sddm-greeter-qt6 --test-mode --theme /usr/share/sddm/themes/bromigos   # preview, windowed
sudo sed -i 's/^Current=bromigos$/Current=sugar-candy/' /etc/sddm.conf.d/20-bromigos.conf   # revert
```

It never restarts SDDM; the theme shows at the next boot or logout.

## Rules

- **No live data, no network.** The greeter runs as the `sddm` user before anyone signs
  in: no lab, no ARBITER, no VECTOR. Nothing on screen pretends to be a reading; the
  only moving things are the emblem and the stars (decoration) and the clock.
- **Public screen.** Anyone at the desk sees it: no callsign, frequency or dossier, and the
  account name is never shown (the remembered account appears as "ACCOUNT ON RECORD").
  The den is the lock-screen variant of the operator's choice, but only `empty` or
  `masked`; a variant with the operator in it falls back to `empty`.
- **Cheap motion.** One `RotationAnimator` (render thread) and a few dozen opacity
  animations; no shaders, no CRT, no scanlines.

## Elements

| Element | Looks like | Shows | Code | Config (`theme.conf`) |
|---------|-----------|-------|------|------------------------|
| Den | the lock-screen den, dimmed, cropped to fill | decoration | `Main.qml` first `Image` | `background` (written by `build.py`) |
| Stars | ~80 faint dots twinkling slowly in the dark sky, top left | decoration | `components/Starfield.qml` | `stars` (0 = off) |
| Burn-in | the motto ring turning counter-clockwise (one turn per 24 s), the flame and halo still | decoration (the canon emblem) | `Main.qml` `emblem`: `ring` image with `RotationAnimator`, `flame` image | `ring`, `flame`, `ringSeconds` |
| Caption | "TRANSMISSION INTERCEPTED" | brand line | `Main.qml` `caption` | `caption` |
| Clock and date | 138 px HH:MM, the date in spaced capitals | the time | `Main.qml` `clock`, `date`, a 1 s `Timer` | — |
| Account | "ACCOUNT ON RECORD" (name hidden) or a `USER` line | who signs in | `components/Field.qml` (`cover`) | — |
| Passphrase | a `>` prompt, dots, a blinking block cursor | — | `Field.qml` (`secret`) | — |
| Status line | `> VERIFYING` amber, `> REJECTED · n` red, `CAPS LOCK IS ON` amber, SDDM's own messages | the sign-in state | `Main.qml` `statusLine` | — |
| Failure | outline fades red, three damped swings (430 ms), field clears, red text for 2.5 s | a wrong passphrase | `Main.qml` `failAnim`, `rejected()` | — |
| Session | `SESSION HYPRLAND ▴`, opens a list upward | what starts after sign-in | `components/SessionButton.qml`, `SessionMenu.qml` | `defaultSession` |
| Power | `SUSPEND`, `REBOOT`, `SHUT DOWN`; reboot and shut down need a second press within 4 s (amber "AGAIN TO …") | power actions SDDM allows | `components/PowerButton.qml`, `Main.qml` `power()` | — |
| Hint line | one line above the sign-off | what the hovered or focused control does | `Main.qml` `hintLine`, each control's `about` | — |
| Sign-off | "STILL LIT." in dim green at the bottom | brand line | `Main.qml` last `Text` | `signoff` |

Positions are in units of one pixel at 2560×1440 (`root.s` scales them), so the layout
holds at 1080p.

## Keyboard

Focus starts on the passphrase when an account is remembered (else on the user line).
Enter signs in; Esc clears the passphrase; Tab and Shift+Tab move through user,
passphrase, session, suspend, reboot, shut down. On "ACCOUNT ON RECORD", Space (or a
click) switches to typing another account. In the session list: Up/Down, Enter chooses,
Esc closes.

## Files

| File | What |
|------|------|
| `Main.qml` | The screen: palette, layout, state, SDDM calls (`sddm.login`, `suspend`, `reboot`, `powerOff`) |
| `components/*.qml` | `Field`, `SessionButton`, `SessionMenu`, `PowerButton`, `Starfield`; `TestDriver` (test only) |
| `metadata.desktop`, `theme.conf` | SDDM's theme metadata (Qt 6) and the theme's settings |
| `../build.py` | Builds the installable theme: copies this, Geist Mono and its licence, renders `assets/ring.png` and `assets/flame.png` with the brand kit's emblem code, picks the den, fills `theme.conf` from `identity.json` |
| `../install.sh` | Builds as the operator, installs to `/usr/share/sddm/themes/bromigos`, copies the cursor to `/usr/share/icons/Bromigos-cursor`, writes `/etc/sddm.conf.d/20-bromigos.conf`, comments out `Current=` and `CursorTheme=` in `/etc/sddm.conf` (it outranks `sddm.conf.d`; the original is kept as `/etc/sddm.conf.pre-bromigos`) |

## Changing it

1. Edit here, then build and test without root:
   ```bash
   cd ~/.config/bromigos/sddm
   python3 build.py /tmp/sddm-test --test-shots /tmp/sddm-shots
   echo '{"screens":[{"name":"DP-1","x":0,"y":0,"width":2560,"height":1440,"logicalDpi":96,"logicalBaseDpi":96,"dpr":1}]}' > /tmp/screen.json
   QT_FORCE_STDERR_LOGGING=1 QT_QPA_PLATFORM="offscreen:configfile=/tmp/screen.json" \
     timeout 30 sddm-greeter-qt6 --test-mode --theme /tmp/sddm-test
   ```
   `TestDriver.qml` steps through idle, typing, wrong password, caps lock, the session
   list and an armed shut-down, saving `/tmp/sddm-shots/<w>x<h>-<state>.png`. Repeat with
   1920×1080 in the screen file. The greeter must print no QML warnings. (In test mode
   SDDM never signs anyone in; the driver simulates the failure.)
2. Commit, then the operator runs `sudo ~/.config/bromigos/sddm/install.sh`. Installing
   needs root: VECTOR prepares and tests the change, the operator installs it.

The lock screen it matches is `hypr/hyprlock.conf`; change both together when the look
changes.
