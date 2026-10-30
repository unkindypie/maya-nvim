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
-- Exercise the real shared adapter, but never launch an authenticated cloud client.
local enabled={}
vim.lsp.enable=function(name,value) assert(name=="copilot"); enabled[#enabled+1]=value~=false end
local executable=vim.fn.executable
vim.fn.executable=function(name) return name=="copilot-language-server" and 0 or executable(name) end
vim.env.MAYA_NVIM_NO_INSTALL=nil
local installed
require("maya.languages").install_package=function(name,done)
 assert(name=="copilot-language-server"); installed=done
end
ai.select("copilot",false)
assert(require("cursortab.config").get().provider.type=="copilot")
assert(require("cursortab.config").get().enabled_predicate())
assert(not package.loaded.copilot and not require("lazy.core.config").plugins["copilot.lua"])
assert(type(vim.lsp.config.copilot.on_attach)=="function")
ai.notify_status()
assert(notice:find("GitHub Copilot") and notice:find("LspCopilotSignIn"))
ai.select("off",false)
installed() -- A late install must not re-enable cloud access after AI-off.
assert(enabled[#enabled]==false and #enabled==1)
assert(ai.status()=="" and not ai.accept() and not require("cursortab.daemon").is_enabled())
ai.select("copilot",false)
installed()
assert(enabled[#enabled]==true)
ai.select("ollama",false)
assert(enabled[#enabled]==false)
assert(require("cursortab.config").get().provider.type=="sweep")
assert(require("cursortab.config").get().provider.model=="custom-sweep")
ai.select("off",false)
require("cursortab.daemon").stop_daemon()
""",
            temp,
        )
        print(
            "PASS: saved preferences migrate, model reloads, status, Copilot/off cancel local AI"
        )
    finally:
        stop(nvim)
