-- Hyprland (Lua, Hyprland >= 0.55): bromigOS's defaults (package bromigos-desktop), then mine.
-- The defaults and every setting are described in /usr/share/bromigos/default/hypr/hyprland.lua.
-- Saving reloads Hyprland; errors show in `hyprctl configerrors`. Check first:
-- Hyprland --verify-config -c ~/.config/hypr/hyprland.lua (and for several files at once,
-- `hyprctl keyword misc:disable_autoreload true` before, one `hyprctl reload` after).

bromigos = {
    mod = "ALT",
    -- bitdepth must match the physical monitor for screen sharing (monitor OSD/specs: 8 or 10)
    monitors = {
        { output = "DP-1", mode = "2560x1440@59.95", position = "3440x0", scale = 1, bitdepth = 10 },
        { output = "DP-2", mode = "3440x1440@59.97", position = "0x0", scale = 1, bitdepth = 10 },
    },
    -- workspaces 1-6 on DP-1 and 7-10 on DP-2; their keys focus that monitor first
    workspaces = {
        { first = 1, last = 6, monitor = "DP-1" },
        { first = 7, last = 10, monitor = "DP-2" },
    },
    config = { input = { kb_options = "caps:escape" } },
    -- mine below: the Razer's side button 3 can arrive as XF86AudioMicMute
    unbind = { "XF86AudioMicMute" },
    autostart = { "$HOME/.local/share/hyprload/hyprload.sh" },
}
dofile("/usr/share/bromigos/default/hypr/hyprland.lua")

local K = require("bromigos.keys")
local live = "bromigos-live"

-- Stop Wine from re-registering itself as the handler for images and documents
-- (winemenubuilder made PNG/JPEG open in Wine); imv is the image viewer.
hl.env("WINEDLLOVERRIDES", "winemenubuilder.exe=d")

-- My apps: their windows and workspaces.
hl.window_rule({ match = { class = "reStream" }, tile = true })
hl.window_rule({ match = { class = "ffplay" }, tile = true })
-- Android emulator: tiling stretches its frame while the phone stays
-- phone-shaped, leaving a white slab. Float it at phone aspect instead.
hl.window_rule({ match = { class = "Emulator" }, float = true })
hl.window_rule({ match = { class = "Emulator", title = "Android Emulator.*" }, size = "545 1224" })
hl.window_rule({ match = { class = "Emulator", title = "Android Emulator.*" }, move = "1975 86" })
hl.window_rule({ match = { class = "librewolf" }, tile = true })
hl.window_rule({ match = { class = "discord" }, tile = true })
hl.window_rule({ match = { class = "spotify" }, tile = true })
hl.window_rule({ match = { class = "discord" }, workspace = "8" })
hl.window_rule({ match = { class = "Google-chrome" }, workspace = "2" })
hl.window_rule({ match = { class = "Spotify" }, workspace = "3" })
hl.window_rule({ match = { class = "Steam" }, workspace = "4" })
hl.window_rule({ match = { class = "com.obsproject.Studio" }, workspace = "9" })
hl.window_rule({ match = { class = "alacritty" }, opacity = "0.80" })

K.exec("ALT + W", "librewolf")
K.exec("ALT + SHIFT + W", "google-chrome-stable")
K.exec("ALT + SHIFT + D", "discord")
K.exec("ALT + m", "spotify-launcher")
K.exec("ALT + SHIFT + o", "obs")
K.exec("ALT + g", "steam")
K.exec("ALT + R", "/home/blackflame/Repos/reStream/reStream.sh")

-- The LAB panel (a homelab panel) and my decks (personal plugins, ~/.config/bromigos/plugins/live).
K.exec("SUPER + C", "bromigos-widgets toggle lab")
-- ARBITER deck: the Floor as a hologram (read-only; Tab switches to the local deck).
K.exec("SUPER + G", live .. " arbiter")
K.exec("SUPER + I", live .. " mind")
K.exec("SUPER + SHIFT + O", live .. " ops")
K.exec("SUPER + SHIFT + N", live .. " netmap")
K.exec("SUPER + R", live .. " replay")

-- The Razer BlackWidow V4 Pro: its keymap, mic-mute fix and macro keys.
require("bromigos.razer")
