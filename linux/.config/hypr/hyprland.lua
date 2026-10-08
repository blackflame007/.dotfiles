-- Hyprland config (Lua, Hyprland >= 0.55). Hyprland loads ~/.config/hypr/hyprland.lua when it
-- exists and only falls back to hyprland.conf (the old format, kept for rollback) when it
-- doesn't. Switch and roll back with ~/.config/bromigos/bin/bromigos-hyprconfig.
--
-- Layout: this file (monitors, autostart, env, look, input, rules, devices, workspaces),
-- bromigos/binds.lua (keybinds), bromigos/live.lua (the BROMIGOS LIVE block),
-- bromigos/keys.lua (bind helpers). Saving any of them reloads Hyprland; errors show in
-- `hyprctl configerrors`. Check a file first: Hyprland --verify-config -c <hyprland.lua>.
-- API: /usr/share/hypr/stubs/hl.meta.lua and https://wiki.hypr.land/Configuring/

-- hl.monitor({ output = "", mode = "1920x1080@60", position = "0x0", scale = 1 })
-- bitdepth must match physical monitor for screen sharing (check monitor OSD/specs; use 8 or 10)
hl.monitor({ output = "DP-1", mode = "2560x1440@59.95", position = "3440x0", scale = 1, bitdepth = 10 })
hl.monitor({ output = "DP-2", mode = "3440x1440@59.97", position = "0x0", scale = 1, bitdepth = 10 })
-- hl.monitor({ output = "HDMI-A-1", mode = "1920x1080@60", position = "0x0", scale = 1 })

-- Autostart: runs once at login (not on reload). bromigos-live starts from bromigos/live.lua.
hl.on("hyprland.start", function()
    -- this session's display for systemd/D-Bus, and VECTOR's daemon moved off any old session
    hl.exec_cmd("~/.config/bromigos/bin/bromigos-session-env adopt")
    hl.exec_cmd("waybar")
    -- ---- BROMIGOS THEME: session start (wallpaper, widgets, idle) -------------------
    -- Static den wallpaper: the base under any live background layer.
    -- (previous: bleach_urahara.jpg on DP-1, monkey-d-luffy...jpg on DP-2)
    -- swaybg on the chosen den variant (choice is local state: ~/.local/state/bromigos/wallpaper)
    hl.exec_cmd("~/.config/bromigos/bin/bromigos-wallpaper apply")
    hl.exec_cmd("~/.config/bromigos/widgets/bromigos-widgets")
    hl.exec_cmd("hypridle")
    hl.exec_cmd("/usr/bin/hyprctl setcursor Bromigos-cursor 24")
    -- ---- END BROMIGOS THEME: session start --------------------------------------------
    hl.exec_cmd("dunst")
    hl.exec_cmd("$HOME/.local/share/hyprload/hyprload.sh")
end)

-- ---- BROMIGOS THEME: session environment ------------------------------------------
-- Cursor theme (~/.config/bromigos/gtk/build-icons-cursor.py); GTK/icon themes are set with gsettings.
hl.env("XCURSOR_THEME", "Bromigos-cursor")
hl.env("XCURSOR_SIZE", "24")
-- Stop Wine from re-registering itself as the handler for images and documents
-- (winemenubuilder made PNG/JPEG open in Wine); imv is the image viewer.
hl.env("WINEDLLOVERRIDES", "winemenubuilder.exe=d")
-- Qt/KDE apps (Dolphin, file dialogs, OBS) read the Bromigos colour scheme
-- (~/.local/share/color-schemes/Bromigos.colors via kdeglobals) through KDE's platform theme.
hl.env("QT_QPA_PLATFORMTHEME", "kde")
-- ---- END BROMIGOS THEME: session environment --------------------------------------
-- gsettings set org.gnome.desktop.interface gtk-theme "Arc-Dark"
-- gsettings set org.gnome.desktop.wm.preferences theme "Arc-dark"
-- gsettings set org.gnome.desktop.interface icon-theme "Arc-X-D"

-- Colours: the active bromigOS theme (borders, shadows), rendered by `bromigos theme set`
-- into ~/.local/state/bromigos/theme/current/hyprland.lua, which returns a table. Read
-- with dofile, so `hyprctl reload` (which `theme set` runs) always picks up a new theme.
-- Missing (no theme set yet): Hyprland's default colours.
local theme = {}
do
    local state = os.getenv("XDG_STATE_HOME")
    if state == nil or state == "" then state = os.getenv("HOME") .. "/.local/state" end
    local ok, t = pcall(dofile, state .. "/bromigos/theme/current/hyprland.lua")
    if ok and type(t) == "table" then theme = t end
end

hl.config({
    input = {
        kb_options   = "caps:escape",
        repeat_rate  = 50,
        repeat_delay = 240,
        sensitivity  = 1.0, -- for mouse cursor

        touchpad = {
            disable_while_typing    = true,
            natural_scroll          = true,
            clickfinger_behavior    = true,
            middle_button_emulation = false,
            tap_to_click            = false,
        },
    },

    general = {
        layout = "master",

        -- ---- BROMIGOS THEME: borders and gaps (previous: gaps 5/20, 0xff5e81ac / 0x66333333)
        gaps_in     = 4,
        gaps_out    = 12,
        border_size = 2,
        col = {
            active_border   = theme.active_border,
            inactive_border = theme.inactive_border,
        },
        -- ---- END BROMIGOS THEME
    },

    decoration = {
        -- ---- BROMIGOS THEME: square corners, dark green shadow (previous: rounding 10)
        rounding = 0,
        shadow = {
            enabled        = true,
            range          = 16,
            render_power   = 3,
            color          = theme.shadow,
            color_inactive = theme.shadow_inactive,
        },
        -- ---- END BROMIGOS THEME
        blur = {
            enabled = true,
            size    = 3,
            passes  = 1,
        },
    },

    animations = {
        enabled = true,
    },

    dwindle = {
        force_split = 2,
        -- preserve_split = true,
    },

    master = {
        new_on_top = true,
    },

    misc = {
        disable_hyprland_logo    = true,
        disable_splash_rendering = true,
        mouse_move_enables_dpms  = true,
        -- a crashed lock screen can be replaced by a fresh hyprlock (you still type your
        -- password) instead of only being cleared from a tty
        allow_session_lock_restore = true,
    },
})

-- ---- BROMIGOS THEME: crisp, quick (previous: windows 7, fade 10, workspaces 6, default curve)
hl.curve("crisp", { type = "bezier", points = { { 0.2, 0.9 }, { 0.1, 1 } } })
hl.curve("snap", { type = "bezier", points = { { 0.4, 0 }, { 0.2, 1 } } })
hl.animation({ leaf = "windows", enabled = true, speed = 3, bezier = "crisp", style = "popin 92%" })
hl.animation({ leaf = "windowsOut", enabled = true, speed = 2, bezier = "snap", style = "popin 92%" })
hl.animation({ leaf = "border", enabled = true, speed = 4, bezier = "snap" })
hl.animation({ leaf = "fade", enabled = true, speed = 3, bezier = "snap" })
hl.animation({ leaf = "layers", enabled = true, speed = 2, bezier = "snap", style = "fade" })
hl.animation({ leaf = "workspaces", enabled = true, speed = 3, bezier = "crisp", style = "slide" })
-- ---- END BROMIGOS THEME

-- ---- BROMIGOS THEME: layer rules ------------------------------------------------
-- Blur behind the translucent bar, launcher, notifications and desktop panels;
-- ignore_alpha keeps blur off their fully transparent pixels.
-- bromigos-holo: VECTOR's console and the hologram gallery (summoned, overlay layer).
for _, namespace in ipairs({ "waybar", "rofi", "notifications", "bromigos-widgets",
                             "bromigos-vector", "bromigos-holo-gallery" }) do
    hl.layer_rule({ match = { namespace = namespace }, blur = true, ignore_alpha = 0.2 })
end
-- ---- END BROMIGOS THEME: layer rules --------------------------------------------

-- Window rules (anonymous, applied top to bottom). Add one with
--   hl.window_rule({ match = { class = "regex", title = "regex" }, float = true, ... })
-- Find a window's class and title with: hyprctl clients
-- hl.window_rule({ match = { class = "abc" }, move = "69 420" })
-- hl.window_rule({ match = { class = "abc" }, size = "420 69" })
hl.window_rule({ match = { class = "kitty" }, tile = true })
hl.window_rule({ match = { class = "reStream" }, tile = true })
hl.window_rule({ match = { class = "ffplay" }, tile = true })
-- Android emulator: tiling stretches its frame while the phone stays
-- phone-shaped, leaving a white slab. Float it at phone aspect instead.
hl.window_rule({ match = { class = "Emulator" }, float = true })
hl.window_rule({ match = { class = "Emulator", title = "Android Emulator.*" }, size = "545 1224" })
hl.window_rule({ match = { class = "Emulator", title = "Android Emulator.*" }, move = "1975 86" })
-- hl.window_rule({ match = { class = "kitty" }, opacity = "0.80" })
-- hl.window_rule({ match = { class = "kitty", title = ".*(nvim).*" }, opacity = "0.80" })

hl.window_rule({ match = { class = "librewolf" }, tile = true })
hl.window_rule({ match = { class = "discord" }, tile = true })
hl.window_rule({ match = { class = "spotify" }, tile = true })
hl.window_rule({ match = { class = "discord" }, workspace = "8" })
hl.window_rule({ match = { class = "Google-chrome" }, workspace = "2" })
hl.window_rule({ match = { class = "Spotify" }, workspace = "3" })
hl.window_rule({ match = { class = "Steam" }, workspace = "4" })
hl.window_rule({ match = { class = "com.obsproject.Studio" }, workspace = "9" })
hl.window_rule({ match = { class = "alacritty" }, opacity = "0.80" })
-- Apps (Chrome especially) ask to open maximized; ignore it so new windows tile.
hl.window_rule({ match = { class = ".*" }, suppress_event = "maximize" })
hl.window_rule({ match = { class = "Rofi" }, float = true })
hl.window_rule({ match = { class = "Rofi" }, move = "25% 40%" })
hl.window_rule({ match = { class = "Rofi" }, size = "50% 20%" })
hl.window_rule({ match = { class = "Rofi" }, opacity = "0.80" })
hl.window_rule({ match = { class = "Rofi" }, center = true })

-- The Razer gets its own keymap so F13-F22 stay F13-F22 (see razer-blackwidow.xkb).
-- The tag lets its macro-key binds (bromigos/binds.lua) listen to this keyboard only.
-- Device names: hyprctl devices.
for _, name in ipairs({ "razer-razer-blackwidow-v4-pro", "razer-razer-blackwidow-v4-pro-1",
                        "razer-razer-blackwidow-v4-pro-3", "razer-razer-blackwidow-v4-pro-5" }) do
    hl.device({ name = name, kb_file = "~/.config/hypr/razer-blackwidow.xkb", tags = "razer-blackwidow" })
end

-- Workspaces 1-6 on DP-1, 7-10 on DP-2.
for ws = 1, 10 do
    hl.workspace_rule({ workspace = tostring(ws), monitor = ws <= 6 and "DP-1" or "DP-2" })
end

require("bromigos.binds")
require("bromigos.live")
