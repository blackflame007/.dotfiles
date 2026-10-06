-- Bind helpers for the Bromigos Hyprland config (required by binds.lua and live.lua).
--
--   K.exec("ALT + E", "pcmanfm")                      run a shell command (sh -c: ~ and $HOME expand)
--   K.dsp("ALT + C", "hl.dsp.window.close()")         a dispatcher, written as Lua source
--   K.exec("SUPER + V", "... ptt off", { release = true })   opts are hl.bind's flags
--
-- Each bind's action is also kept as text: in its `description` (so `hyprctl binds` says
-- what it does) and in the list K.dump() prints. That list is how the SHORTCUTS panel, the
-- rofi cheat sheet and `bromigos-docs keys` (widgets/keybinds.py) name and run every bind,
-- live with `hyprctl repl 'return package.loaded["bromigos.keys"].dump()'`, or from the
-- files with widgets/keybinds-dump.lua. `hyprctl binds -j` can't do it alone: a Lua bind's
-- dispatcher/arg there are "__lua" and a registry number, and a code:N bind shows an
-- empty key and keycode 0. A plain hl.bind() still works, but SHORTCUTS won't list it.

local M = { binds = {} }

local function with_description(opts, text)
    local o = {}
    for k, v in pairs(opts or {}) do
        o[k] = v
    end
    o.description = text
    return o
end

local function register(keys, kind, payload, source, dispatcher, opts)
    opts = opts or {}
    table.insert(M.binds, { keys = keys, kind = kind, payload = payload,
                            release = opts.release and true or false, mouse = opts.mouse and true or false })
    return hl.bind(keys, dispatcher, with_description(opts, source))
end

-- Build the dispatcher from its source. A mistake never stops the binds after it:
-- hl.bind reports it (hyprctl configerrors) and the log names the bind.
local function compile(keys, source)
    local chunk, err = load("return " .. source, "=bind " .. keys, "t")
    local ok, dispatcher = false, nil
    if chunk then
        ok, dispatcher = pcall(chunk)
        err = dispatcher
    end
    if not ok or dispatcher == nil then
        print(("bromigos bind %s -> %s: %s"):format(keys, source, tostring(err)))
        return nil
    end
    return dispatcher
end

--- Bind keys to a dispatcher written as Lua source, e.g. K.dsp("ALT + C", "hl.dsp.window.close()").
function M.dsp(keys, source, opts)
    return register(keys, "lua", source, source, compile(keys, source), opts)
end

--- Bind keys to a shell command.
function M.exec(keys, cmd, opts)
    local source = ("hl.dsp.exec_cmd(%q)"):format(cmd)
    return register(keys, "exec", cmd, source, compile(keys, source), opts)
end

--- Every bind made through these helpers, in order, one per line:
--- release<TAB>mouse<TAB>keys<TAB>kind<TAB>payload  (kind: exec = a shell command,
--- lua = dispatcher source; \ tab and newline in the payload are escaped as \\ \t \n).
function M.dump()
    local out = {}
    for _, b in ipairs(M.binds) do
        local payload = b.payload:gsub("\\", "\\\\"):gsub("\t", "\\t"):gsub("\n", "\\n")
        out[#out + 1] = table.concat({ b.release and "1" or "0", b.mouse and "1" or "0", b.keys, b.kind, payload }, "\t")
    end
    return table.concat(out, "\n")
end

return M
