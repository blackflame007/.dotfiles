-- The Razer BlackWidow V4 Pro (required by hyprland.lua, after bromigOS's defaults).
--
-- It gets its own keymap so F13-F22 stay F13-F22 (see ../razer-blackwidow.xkb); the tag
-- lets its macro-key binds listen to this keyboard only. Device names: hyprctl devices.
for _, name in ipairs({ "razer-razer-blackwidow-v4-pro", "razer-razer-blackwidow-v4-pro-1",
                        "razer-razer-blackwidow-v4-pro-3", "razer-razer-blackwidow-v4-pro-5" }) do
    hl.device({ name = name, kb_file = "~/.config/hypr/razer-blackwidow.xkb", tags = "razer-blackwidow" })
end

local K = require("bromigos.keys")

-- Mic mute, but not from the Razer: its side button 3 (F20) can arrive as XF86AudioMicMute
-- under the default layout, which muted the mic every time recording was started from it.
-- (bromigOS's own mic-mute bind is skipped: bromigos.unbind in hyprland.lua.)
K.exec("XF86AudioMicMute", "pactl set-source-mute @DEFAULT_SOURCE@ toggle",
       { device = { inclusive = false, list = { "razer-blackwidow" } } })

-- Macro keys, bound by keycode (code:N = evdev code + 8) so no keymap can rename them:
-- M1-M5 = F13-F17 (191-195), side buttons F18-F20 (196-198), dial press F24 (202). With
-- openrazer in driver mode (openrazer-daemon, user in the `openrazer` group) M1-M5 send
-- F13-F17, the three side buttons F18-F20 and a press of the command dial F24; nothing
-- else uses those keys.
-- M1: show/hide VECTOR; M2 (hold): push to talk; M3: VECTOR conversation on/off; M4: holo deck;
-- M5: screenshot a region. Side buttons: 1 ARBITER deck, 2 timeline, 3 start/stop recording.
-- (Shift+M5 can't work: Shift and the M-keys arrive on different Razer input devices,
-- so a bind never sees Shift held with an M-key.)
-- They listen to the Razer only: in Hyprland 0.56 a Lua code:N bind also fires for any key
-- that has no keysym (a JIS or stray consumer key), so the device list keeps other
-- keyboards' odd keys from setting off every macro bind at once. Only the Razer sends
-- 191-202, so nothing else changes.
local razer = { device = { list = { "razer-blackwidow" } } }       -- the tag set above
local razer_release = { release = true, device = razer.device }
local holo = "~/.config/bromigos/holo/bin/bromigos-holo"
for _, p in ipairs({ "/usr/bin/bromigos-holo", "/usr/lib/bromigos/vector/bin/bromigos-holo" }) do
    local f = io.open(p, "r")
    if f then
        f:close()
        holo = p
        break
    end
end
K.exec("code:191", holo .. " vector", razer)
K.exec("code:192", holo .. " ptt on", razer)
K.exec("code:192", holo .. " ptt off", razer_release)
K.exec("code:193", "~/.config/bromigos/bin/vector-converse", razer)
K.exec("code:194", "bromigos-live holodeck", razer)
K.exec("code:195", "bromigos-shot region", razer)
K.exec("code:196", "bromigos-live arbiter", razer)
K.exec("code:197", "bromigos-live timeline", razer)
K.exec("code:198", "bromigos-rec region", razer)
K.exec("code:202", holo .. " mute", razer)
