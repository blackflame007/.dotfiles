-- ---- BROMIGOS LIVE: animated live layer (~/.config/bromigos-live) ----------------
-- Background shader layer + event overlays + holo gadgets. Toggles: bromigos-live/config.toml.
-- Required last by hyprland.lua, so these binds come after the stock ones (as before).

local K = require("bromigos.keys")

local live = "~/.config/bromigos-live/bin/bromigos-live"

hl.on("hyprland.start", function()
    hl.exec_cmd(live .. " start --login")
end)
hl.layer_rule({ match = { namespace = "^(bromigos-live.*)$" }, no_anim = true })
-- Holo deck: arc rings, cluster constellation, machine hologram (Esc closes).
K.exec("SUPER + H", live .. " holodeck")
-- ARBITER deck: the Floor as a hologram (read-only; Tab switches to the local deck).
K.exec("SUPER + G", live .. " arbiter")
-- Drift map: the lore catalog as a star chart; the lab's live services are its lit relays.
K.exec("SUPER + M", live .. " driftmap")
-- Timeline: the local history (minute samples, 72 h) as a 3D ribbon to scrub.
K.exec("SUPER + T", live .. " timeline")
-- VECTOR's holograms (Tab cycles through every deck; VECTOR drives them with bromigos-live <deck> <verb>).
K.exec("SUPER + I", live .. " mind")
K.exec("SUPER + SHIFT + O", live .. " ops")
K.exec("SUPER + SHIFT + S", live .. " swarm")
K.exec("SUPER + SHIFT + N", live .. " netmap")
K.exec("SUPER + R", live .. " replay")
-- Radial quick-launch (rofi stays the full launcher on ALT+P).
K.exec("SUPER + A", live .. " radial")
-- Live background on/off, sounds mute/unmute.
K.exec("SUPER + SHIFT + B", live .. " toggle")
K.exec("SUPER + SHIFT + M", live .. " mute")
-- Codec calls without voice (quiet mode toggle).
K.exec("SUPER + SHIFT + C", live .. " codec-quiet")
-- Scanner: pin the hardware schematic (toggle) / hold to scan (release hides it).
K.exec("SUPER + X", live .. " scan-pin")
K.exec("SUPER + Z", live .. " scan-hold on")
K.exec("SUPER + Z", live .. " scan-hold off", { release = true })
-- ---- END BROMIGOS LIVE ------------------------------------------------------------
