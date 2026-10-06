---
name: workstation-ops
description: How VECTOR diagnoses and fixes problems on the host's own workstation (Arch, Hyprland, PipeWire, the Razer keyboard and mouse, systemd user services, Docker, snapshots, the NAS backup) — the method, the tools, and every fault already met here with its real cause and fix.
when_to_use: The host says something on this machine stopped working or behaves oddly — no sound, mic dead or muted, a key or button doing the wrong thing, the wallpaper animation frozen or gone, panels missing, a hologram empty or closing, VECTOR silent, a service failing, the disk filling, a backup failing, sudo misbehaving — or asks you to manage or tune the system.
triggers: '(stopped|stops|isn''?t|is not|not|doesn''?t|does not|won''?t|can''?t|cannot)\s+(work|working|moving|playing|loading|showing|responding|turn on|start|hear|record)|does nothing|no (sound|audio|mic|picture|signal)|\b(mic|microphone|sound|audio|speakers?|headphones?|keyboard|mouse|key|button|razer|M[1-5]|wallpaper|animation|panel|widget|bar|waybar|display|monitor|screen|disk|drive|service)\b.*\b(broken|dead|frozen|stuck|muted|silent|missing|gone|full|failing|failed|crash\w*|wrong|weird|off|lagging|slow)\b|\b(wrong|broken)\b.*\b(computer|machine|system|desktop|workstation)\b|\b(failing|failed|crash\w*|errors?)\b.*\b(machine|computer|system|services?|desktop)\b|disk (is |getting )?full|out of (space|memory)'
---

# Fixing the workstation

Same rules as every task: say in one line what you're about to change, change it,
**prove it worked**, report in a sentence. Look before you touch: most faults here
were one setting, found in seconds by reading state, not by guessing.

## Method

1. **Reproduce or read the state first.** `wpctl status`, `systemctl --user status <unit>`,
   `journalctl --user -u <unit> -n 50`, the app's own log in `~/.local/state/bromigos*/`,
   `hyprctl configerrors`. Read the exact error line before forming a theory.
2. **Find what changed.** `git -C ~/.dotfiles log --oneline -10`, recent restarts in the
   logs, a key or button the host just pressed. A fault that started "just now" usually
   follows something that happened just now.
3. **Fix the cause, not the symptom**, then make it not recur (a config line, a guard),
   commit it to the dotfiles (public repo: no addresses or secrets, the pre-commit guard
   checks), and note anything out of git in `~/.dotfiles/VECTOR-CHANGELOG.md`.
4. **Snapshot first** for anything system-level (packages, /etc, system services):
   your terminal wraps those in a snapper pre/post pair; "undo that" reverts it.
5. **Needs sudo?** You can't type the host's passphrase or touch his YubiKey. Write the
   exact command and ask him to run it **in a terminal** (kitty, Alt+Shift+Enter): sudo
   can't prompt through Claude Code's `!` prefix. If sudo hangs before prompting, his
   YubiKey isn't answering (pam_u2f waits, then falls back to the password): unplug and
   replug it.

## Tools

| Area | Look | Fix |
|---|---|---|
| Audio (PipeWire) | `wpctl status` (MUTED marks, `*` = default), `pactl get-default-source`/`-sink`, `pactl list short modules` | `wpctl set-mute @DEFAULT_SOURCE@ 0`, `wpctl set-default <id>`, `wpctl set-volume` |
| Input / keys | `hyprctl binds -j`, `hyprctl devices -j`, `bromigos-hyprconfig status`, `journalctl --user -u openrazer-daemon` | edit `~/.config/hypr/bromigos/binds.lua` (see the hyprland-config skill), `hyprctl reload` |
| Hyprland | `hyprctl configerrors`, `Hyprland --verify-config -c ~/.config/hypr/hyprland.lua` | fix the Lua, reload; never `reload full-reset` casually |
| User services | `systemctl --user list-units --failed`, `status`, `journalctl --user -u` | `systemctl --user restart <unit>` |
| Desktop pieces | `bromigos-live status` (surface mapped? measured fps), `bromigos-holo status`, `bromigos-widgets` | `bromigos-live restart`, `bromigos-holo restart`, `bromigos-widgets reload` |
| GPU | `nvidia-smi` (who holds VRAM), `nvidia-smi --query-compute-apps=pid,used_memory --format=csv` | stop the duplicate or idle holder |
| Disk | `df -h /`, `docker system df`, `du -xh --max-depth=2 / \| sort -rh \| head` | `docker builder prune -af`, `docker image prune -af --filter until=720h`; ask before deleting named volumes |
| Snapshots / backup | `snapper -c root list`, `systemctl status btrbk.service`, `journalctl -u btrbk.service` | see the snapshots section of `~/.config/bromigos/README.md` |

## Faults already met here (cause → fix)

| Symptom | Real cause | Fix |
|---|---|---|
| Mic dead after pressing Razer side button 3 | F20 arrives as `XF86AudioMicMute` under the default layout and toggled the Yeti's mute | unmute (`wpctl set-mute @DEFAULT_SOURCE@ 0`); the mic-mute bind now excludes the Razer |
| No sound at all | the default **sink** muted at the OS level | `wpctl set-mute @DEFAULT_AUDIO_SINK@ 0` |
| VECTOR silent when opened | voice server cold start: the cast load blocked speech (fixed: Kokoro answers during the load) | if it recurs, `bromigos-holo status`, voice log `~/.local/state/bromigos/holo-voice.log` |
| VECTOR silent: "muted" | his own mute file `~/.local/state/bromigos/vector-voice-muted` | `bromigos-holo mute` toggles; the panel shows the reason |
| VECTOR errors `CUBLAS_STATUS_ALLOC_FAILED` | two voice servers loaded at once filled the 12 GB GPU | `nvidia-smi`, kill the duplicate; the server now holds a lock |
| Shift + a Razer M-key acts like the plain M-key | Shift and the M-keys come from different Razer input devices; binds never see both | use the side buttons, not modifiers, for extra actions |
| M-keys do nothing | openrazer daemon not running (user must be in `openrazer`, then reboot) or the keys were bound by name | `systemctl --user status openrazer-daemon`; binds use `code:N` |
| Wallpaper animation stopped | the monitor turned off and the layer surface was destroyed | self-heals now; `bromigos-live status` shows `surface=MISSING`; `bromigos-live restart` |
| A hologram deck closes after a second | a crash on the first frame (e.g. float32 epoch time under NumPy 2) | read `~/.local/state/bromigos-live/live.log` for the traceback |
| Swarm shows no ships | the daemon's PATH lacked `~/.local/bin` (herdr) | commands resolve user bin dirs now; check the log for `No such file` |
| Panels gone | toggled off | Super+W toggles all |
| Files open in Wine | Wine's menubuilder registered itself for images | `xdg-mime default imv.desktop image/png` (and friends); WINEDLLOVERRIDES set in Hyprland |
| A command works in a terminal but not from a keybind or service | different PATH/env (Hyprland exec, systemd user units) | use absolute paths or resolve `~/.local/bin`, `~/.cargo/bin` |
| btrbk "Failed to fetch subvolume detail" | `/mnt/btrfs-top` automount not started | `systemctl start 'mnt-btrfs\x2dtop.automount'` (root) |
| Razer volume roller does nothing | it reports as vertical scroll on the keyboard's mouse interface, which `bromigos-knob` grabs for the dial; the grab swallowed it | the knob service now turns roller scrolls into `wpctl set-volume` (2% a click); if a new control on that interface goes dead, look there first |
| `sudo` hangs, no FIDO prompt | YubiKey not answering | replug it |

## Don't

- Don't guess and change several things at once; one change, then check.
- Don't delete user data (Docker named volumes, files outside caches) without asking.
- Don't restart the host's session, SDDM, or Hyprland with `full-reset` while he's working.
- Don't edit your own safety files; if a fix needs that, tell the host.
