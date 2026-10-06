-- Keybinds (required by hyprland.lua). The BROMIGOS LIVE binds are in live.lua.
--
-- Add a bind with the helpers in keys.lua, inside the right fenced block:
--   K.exec("SUPER + Q", "~/.config/bromigos/bin/some-tool")             -- run a command
--   K.dsp("ALT + P", "hl.dsp.window.pin()")                              -- a dispatcher
--   K.exec("SUPER + V", "... ptt off", { release = true })               -- on key-up
-- Keys are "MODS + KEY" ("SUPER + SHIFT + K"), a keysym, or code:N (evdev code + 8).
-- Then add an EXEC row in ~/.config/bromigos/widgets/keybinds.py if it's an exec bind
-- SHORTCUTS should name, and run `bromigos-docs keys`. Check free keys: hyprctl binds -j.

local K = require("bromigos.keys")

local mainMod = "ALT"

-- binds
-- Reload Plugin Manager
-- K.dsp("SUPER + SHIFT + R", ...) hyprload reload / install / update (unused)

K.dsp(mainMod .. " + mouse:272", "hl.dsp.window.drag()", { mouse = true })
K.dsp(mainMod .. " + mouse:273", "hl.dsp.window.resize()", { mouse = true })

K.exec(mainMod .. " + b", "pkill -SIGUSR1 waybar")
K.dsp(mainMod .. " + SHIFT + C", "hl.dsp.window.close()")
K.dsp(mainMod .. " + F", 'hl.dsp.window.fullscreen({ mode = "maximized" })')
K.dsp(mainMod .. " + SHIFT + F", 'hl.dsp.window.fullscreen({ mode = "fullscreen" })')
K.exec(mainMod .. " + SHIFT + RETURN", "kitty")
K.dsp(mainMod .. " + C", "hl.dsp.window.close()")
K.dsp(mainMod .. " + SHIFT + Q", "hl.dsp.exit()")
K.exec(mainMod .. " + E", "pcmanfm")
K.exec(mainMod .. " + W", "librewolf")
K.exec(mainMod .. " + SHIFT + W", "google-chrome-stable")
K.exec(mainMod .. " + SHIFT + D", "discord")
K.dsp(mainMod .. " + SHIFT + V", "hl.dsp.window.float()")
K.exec(mainMod .. " + p", "rofi -show drun")
K.exec(mainMod .. " + m", "spotify-launcher")
K.exec(mainMod .. " + SHIFT + o", "obs")
K.exec(mainMod .. " + g", "steam")
-- K.exec(mainMod .. " + P", ...) pseudo (unused)
K.exec(mainMod .. " + R", "/home/blackflame/Repos/reStream/reStream.sh")
K.exec(mainMod .. " + ESCAPE", "sudo systemctl suspend")
-- BROMIGOS THEME: screenshots go through bromigos-shot (save, clipboard, cue, notification; click it to annotate in swappy).
-- (previous: grim -g "$(slurp)" - | swappy -f -)
K.exec(mainMod .. " + Y", "~/.config/bromigos/bin/bromigos-shot region")
K.exec(mainMod .. " + SHIFT + Y", "~/.config/bromigos/bin/bromigos-shot screen")
K.exec("XF86AudioMute", "pactl set-sink-mute @DEFAULT_SINK@ toggle")
K.exec("XF86AudioLowerVolume", "pactl set-sink-volume @DEFAULT_SINK@ -5%")
K.exec("XF86AudioRaiseVolume", "pactl set-sink-volume @DEFAULT_SINK@ +5%")
-- Not from the Razer: its side button 3 (F20) can arrive as XF86AudioMicMute under the
-- default layout, which muted the mic every time recording was started from it.
K.exec("XF86AudioMicMute", "pactl set-source-mute @DEFAULT_SOURCE@ toggle",
       { device = { inclusive = false, list = { "razer-blackwidow" } } })
K.exec("XF86MonBrightnessUp", "brightnessctl -q set +5%")   -- increase screen brightness
K.exec("XF86MonBrightnessDown", "brightnessctl -q set 5%-") -- decrease screen brightness
K.exec("XF86AudioPlay", "playerctl play-pause")             -- Toggle Media
K.exec("XF86AudioPrev", "playerctl previous")               -- previous track
K.exec("XF86AudioNext", "playerctl next")                   -- next track
-- BROMIGOS THEME: recording toggles (press again or click the notification to stop).
-- (previous: wf-recorder -g "$(slurp)")
K.exec(mainMod .. " + SHIFT + R", "~/.config/bromigos/bin/bromigos-rec region")

-- ---- BROMIGOS THEME: keybinds ----------------------------------------------------
-- Power menu (lock / suspend / logout / reboot / shutdown); previously wlogout.
K.exec(mainMod .. " + SHIFT + E", "~/.config/rofi/scripts/power-menu")
-- Lock now (SUPER is otherwise unused here).
K.exec("SUPER + L", "loginctl lock-session")
-- FIELD NOTES: focus the pad for typing (Esc hands focus back) / quick note from anywhere.
K.exec(mainMod .. " + N", "~/.config/bromigos/widgets/bromigos-widgets notes")
K.exec(mainMod .. " + SHIFT + N", "~/.config/rofi/scripts/quick-note")
-- Desktop panels: toggle all / one at a time.
K.exec("SUPER + W", "~/.config/bromigos/widgets/bromigos-widgets toggle all")
K.exec("SUPER + S", "~/.config/bromigos/widgets/bromigos-widgets toggle system")
K.exec("SUPER + N", "~/.config/bromigos/widgets/bromigos-widgets toggle network")
K.exec("SUPER + D", "~/.config/bromigos/widgets/bromigos-widgets toggle storage")
K.exec("SUPER + C", "~/.config/bromigos/widgets/bromigos-widgets toggle lab")
K.exec("SUPER + B", "~/.config/bromigos/widgets/bromigos-widgets toggle workbench")
K.exec("SUPER + F", "~/.config/bromigos/widgets/bromigos-widgets toggle notes")
-- Shortcuts: the keybind panel / a searchable cheat sheet that runs the chosen bind.
K.exec("SUPER + K", "~/.config/bromigos/widgets/bromigos-widgets toggle shortcuts")
K.exec("SUPER + SHIFT + K", "~/.config/bromigos/widgets/keybinds.py rofi")
-- Launcher: window switcher.
K.exec(mainMod .. " + TAB", "rofi -show window")
-- bromigos-holo: VECTOR, on a line from his post at the SpacePort (typed; Esc hands the keyboard back) / the hologram gallery.
K.exec("SUPER + E", "~/.config/bromigos/holo/bin/bromigos-holo vector")
-- VECTOR conversation mode: hands-free, listens until you stop talking, replies, listens again.
K.exec("SUPER + SHIFT + E", "~/.config/bromigos/holo/bin/bromigos-holo conversation")
K.exec("SUPER + O", "~/.config/bromigos/holo/bin/bromigos-holo gallery")
-- VECTOR push-to-talk: the mic is open only while SUPER+V is held / mute VECTOR's voice.
K.exec("SUPER + V", "~/.config/bromigos/holo/bin/bromigos-holo ptt on")
K.exec("SUPER + V", "~/.config/bromigos/holo/bin/bromigos-holo ptt off", { release = true })
K.exec("SUPER + SHIFT + V", "~/.config/bromigos/holo/bin/bromigos-holo mute")
-- The Razer gets its own keymap so F13-F22 stay F13-F22: its hl.device() entries are in
-- hyprland.lua (see razer-blackwidow.xkb).
-- Razer BlackWidow V4 Pro macro keys, bound by keycode (code:N = evdev code + 8) so no keymap
-- can rename them: M1-M5 = F13-F17 (191-195), side buttons F18-F20 (196-198), dial press F24 (202). With openrazer in driver mode (openrazer-daemon,
-- user in the `openrazer` group) M1-M5 send F13-F17, the three side buttons F18-F20
-- and a press of the command dial F24; nothing else uses those keys.
-- M1: show/hide VECTOR; M2 (hold): push to talk; M3: VECTOR conversation on/off; M4: holo deck;
-- M5: screenshot a region. Side buttons: 1 ARBITER deck, 2 timeline, 3 start/stop recording.
-- (Shift+M5 can't work: Shift and the M-keys arrive on different Razer input devices,
-- so a bind never sees Shift held with an M-key.)
-- They listen to the Razer only: in Hyprland 0.56 a Lua code:N bind also fires for any key
-- that has no keysym (a JIS or stray consumer key), so the device list keeps other
-- keyboards' odd keys from setting off every macro bind at once. Only the Razer sends
-- 191-202, so nothing else changes.
local razer = { device = { list = { "razer-blackwidow" } } }       -- the tag set in hyprland.lua
local razer_release = { release = true, device = razer.device }
K.exec("code:191", "~/.config/bromigos/holo/bin/bromigos-holo vector", razer)
K.exec("code:192", "~/.config/bromigos/holo/bin/bromigos-holo ptt on", razer)
K.exec("code:192", "~/.config/bromigos/holo/bin/bromigos-holo ptt off", razer_release)
K.exec("code:193", "~/.config/bromigos/bin/vector-converse", razer)
K.exec("code:194", "~/.config/bromigos-live/bin/bromigos-live holodeck", razer)
K.exec("code:195", "~/.config/bromigos/bin/bromigos-shot region", razer)
K.exec("code:196", "~/.config/bromigos-live/bin/bromigos-live arbiter", razer)
K.exec("code:197", "~/.config/bromigos-live/bin/bromigos-live timeline", razer)
K.exec("code:198", "~/.config/bromigos/bin/bromigos-rec region", razer)
K.exec("code:202", "~/.config/bromigos/holo/bin/bromigos-holo mute", razer)
-- ---- END BROMIGOS THEME: keybinds ------------------------------------------------
-- K.exec(mainMod .. " + SHIFT + L", "swaylock")

K.dsp(mainMod .. " + RETURN", 'hl.dsp.layout("swapwithmaster")')
K.dsp(mainMod .. " + j", 'hl.dsp.layout("cyclenext")')
K.dsp(mainMod .. " + k", 'hl.dsp.layout("cycleprev")')

K.dsp(mainMod .. " + h", 'hl.dsp.focus({ direction = "left" })')
K.dsp(mainMod .. " + l", 'hl.dsp.focus({ direction = "right" })')
-- K.dsp(mainMod .. " + k", 'hl.dsp.focus({ direction = "up" })')
-- K.dsp(mainMod .. " + j", 'hl.dsp.focus({ direction = "down" })')

K.dsp(mainMod .. " + left", "hl.dsp.window.resize({ x = -40, y = 0, relative = true })")
K.dsp(mainMod .. " + right", "hl.dsp.window.resize({ x = 40, y = 0, relative = true })")

K.dsp(mainMod .. " + SHIFT + h", 'hl.dsp.window.move({ direction = "left" })')
K.dsp(mainMod .. " + SHIFT + l", 'hl.dsp.window.move({ direction = "right" })')
K.dsp(mainMod .. " + SHIFT + k", 'hl.dsp.window.move({ direction = "up" })')
K.dsp(mainMod .. " + SHIFT + j", 'hl.dsp.window.move({ direction = "down" })')

-- The scratchpad: the default special workspace ("special:special").
K.dsp(mainMod .. " + SHIFT + S", 'hl.dsp.window.move({ workspace = "special" })')
K.dsp(mainMod .. " + s", "hl.dsp.workspace.toggle_special()")

-- Workspaces 1-6 live on DP-1 and 7-10 on DP-2 (workspace rules in hyprland.lua).
-- Each key focuses the monitor, then the workspace (two binds on one key run in order).
for ws = 1, 10 do
    local key = tostring(ws % 10)
    local monitor = ws <= 6 and "DP-1" or "DP-2"
    K.dsp(mainMod .. " + " .. key, ('hl.dsp.focus({ monitor = "%s" })'):format(monitor))
    K.dsp(mainMod .. " + " .. key, ("hl.dsp.focus({ workspace = %d })"):format(ws))
end

-- Send the active window to a workspace without following it.
for ws = 1, 10 do
    K.dsp(mainMod .. " + SHIFT + " .. tostring(ws % 10),
        ("hl.dsp.window.move({ workspace = %d, follow = false })"):format(ws))
end
