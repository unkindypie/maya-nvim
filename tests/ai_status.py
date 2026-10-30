"""Preference migration, reload, status, and local/cloud/off handover."""

import tempfile
from integration import start, stop

with tempfile.TemporaryDirectory(prefix="maya-ai-status-") as temp:
    nvim = start()
    try:
        nvim.exec_lua(
            """
local state=...
local original=vim.fn.stdpath
vim.fn.stdpath=function(key) return key=="state" and state or original(key) end
local file=state.."/ai.json"
vim.fn.writefile({vim.json.encode({provider="off",model="qwen",local_mode="dual",next_edit_model="custom-sweep",endpoint="http://127.0.0.1:9"})},file)
local ai=require("maya.ai")
ai.select("ollama")
local saved=vim.json.decode(table.concat(vim.fn.readfile(file),"\\n"))
assert(saved.schema==2 and saved.local_mode==nil and saved.model=="custom-sweep")
assert(saved.legacy.model=="qwen" and saved.endpoint=="http://127.0.0.1:9")
assert(require("cursortab.config").get().provider.model=="custom-sweep")
ai.action("dismiss")
assert(require("maya.ai_next_edit").status():find("dismissed"))
ai.select("ollama",false)
assert(not require("maya.ai_next_edit").status():find("dismissed"))
_G.notice=""
vim.notify=function(text) _G.notice=text end
ai.notify_status()
assert(notice:find("Cursortab") and notice:find("custom%-sweep") and notice:find("Ctrl%-%]"))
package.loaded.copilot={setup=function() end}
vim.api.nvim_create_user_command("Copilot",function() end,{nargs="*",force=true})
ai.select("copilot",false)
assert(not require("cursortab.daemon").is_enabled())
ai.select("off",false)
assert(ai.status()=="" and not ai.accept())
require("cursortab.daemon").stop_daemon()
""",
            temp,
        )
        print(
            "PASS: saved preferences migrate, model reloads, status, Copilot/off cancel local AI"
        )
    finally:
        stop(nvim)
