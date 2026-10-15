"""AI reselection reloads models quietly; status explains providers and controls."""

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
vim.fn.mkdir(state,"p")
local file=state.."/ai.json"
vim.fn.writefile({vim.json.encode({provider="ollama",model="qwen2.5-coder:1.5b-base"})},file)
_G.notices={}
vim.notify=function(message,level,opts) notices[#notices+1]={message=message,opts=opts} end
local ai=require("maya.ai")
ai.select("ollama")
assert(#notices==1)
notices={}
ai.select("ollama")
assert(#notices==1 and notices[1].message:find("1.5b-base",1,true))
vim.fn.writefile({vim.json.encode({provider="ollama",model="qwen2.5-coder:3b-base"})},file)
notices={}
ai.select("ollama")
assert(#notices==1)
assert(require("minuet").config.provider_options.openai_fim_compatible.model=="qwen2.5-coder:3b-base")
ai.notify_status()
local status=notices[#notices]
assert(status.opts.timeout==10000)
assert(status.message:find("3b-base",1,true) and status.message:find("Server:",1,true))
assert(status.message:find("Ctrl-]",1,true))
package.loaded.copilot={setup=function() end}
vim.api.nvim_create_user_command("Copilot",function() end,{nargs="*",force=true})
ai.select("copilot",false)
assert(ai.provider=="copilot")
assert(vim.b.minuet_virtual_text_auto_trigger==false)
ai.notify_status()
assert(notices[#notices].message:find("Copilot auth",1,true))
ai.select("off",false)
ai.notify_status()
assert(notices[#notices].message:find("Normal editor completion",1,true))
""",
            temp,
        )
        print(
            "PASS quiet AI reselection, saved-model reload, Copilot switching, and 10-second status"
        )
    finally:
        stop(nvim)
