"""Check real LuaLS completion for the personal config schema."""

from pathlib import Path
import tempfile
import time
from integration import start, stop, wait


def labels(nvim):
    return nvim.exec_lua("""
local results=vim.lsp.buf_request_sync(0,"textDocument/completion",{
 textDocument={uri=vim.uri_from_bufnr(0)},position={line=2,character=2}},3000)
local labels={}
for _,response in pairs(results or {}) do
 local r=response.result or {}
 for _,item in ipairs(r.items or r) do labels[#labels+1]=item.label:gsub("%?$", "") end
end
return labels
""")


with tempfile.TemporaryDirectory(prefix="maya-config-completion-") as temp:
    file = Path(temp) / "init.lua"
    file.write_text("---@type MayaConfig\nreturn {\n  \n}\n")
    nvim = start()
    try:
        nvim.command("edit " + str(file))
        wait(nvim, "#vim.lsp.get_clients({bufnr=0}) > 0")
        expected = {
            "theme",
            "options",
            "plugins",
            "setup",
            "reopen_tabs",
            "ai_completion_debounce_ms",
            "ai_next_edit_debounce_ms",
            "pokemon_sound_on_start",
            "pokemon_sound_on_start_volume_percentage",
        }
        for attempt in range(30):
            found = set(labels(nvim))
            if expected <= found:
                break
            time.sleep(0.2)
        assert expected <= found, found
        nvim.current.buffer[:] = ["---@type MayaConfig", "return {theme={", "  ", "}}"]
        for attempt in range(30):
            found = set(labels(nvim))
            if {"plugin", "name", "module", "opts"} <= found:
                break
            time.sleep(0.2)
        assert {"plugin", "name", "module", "opts"} <= found, found
        print("PASS LuaLS completion for all personal settings and nested theme fields")
    finally:
        stop(nvim)
