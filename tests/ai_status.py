"""AI reselection reloads models quietly; status explains providers and controls."""

import tempfile

from integration import start, stop

with tempfile.TemporaryDirectory(prefix="maya-ai-status-") as temp:
    nvim = start()
    try:
        nvim.exec_lua(
            r"""
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
assert(status.message:find("Automatic local AI: enabled",1,true))
ai.action("dismiss")
ai.notify_status()
assert(notices[#notices].message:find("dismissed; waiting for the next edit",1,true))
ai.select("ollama",false)
assert(not require("maya.ai_coordinator").status():find("dismissed",1,true), "explicit enable retained dismissal")
vim.bo.readonly=true
ai.notify_status()
assert(notices[#notices].message:find("read-only buffer",1,true))
assert(notices[#notices].message:find("unavailable in this buffer",1,true))
vim.bo.readonly=false
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
-- Invoke the registered menu mapping with an isolated state file.
local saved={provider="off",local_mode="dual",model="qwen2.5-coder:1.5b-base",
 next_edit_model="test-sweep",endpoint="http://localhost:12345",personal_flag=true}
vim.fn.writefile({vim.json.encode(saved)},file)
local function read() return vim.json.decode(table.concat(vim.fn.readfile(file),"\n")) end
local original_select=vim.ui.select
local choice="single"
vim.ui.select=function(items,opts,callback)
 assert(opts.prompt=="Local AI mode (selecting enables Ollama)" and #items==3)
 local selected,marked=nil,0
 for _,item in ipairs(items) do
  local label=opts.format_item(item)
  if label:find("(saved)",1,true) then
   marked=marked+1; assert(item.value==(read().local_mode or "completion-only"))
  end
  if item.value==choice then selected=item end
 end
 assert(marked==1)
 callback(selected)
end
local mapping=vim.fn.maparg(" am","n",false,true)
assert(mapping.desc=="Local AI mode (enables Ollama)")
assert(vim.fn.maparg(" ao","n",false,true).desc=="Enable/reload local AI (Ollama)")
assert(vim.fn.maparg(" ax","n",false,true).desc=="Disable all AI")
mapping.callback()
assert(ai.provider=="ollama" and ai.local_mode=="single")
local value=read()
assert(value.local_mode=="single" and value.provider=="ollama")
assert(value.model==saved.model and value.next_edit_model==saved.next_edit_model)
assert(value.endpoint==saved.endpoint and value.personal_flag==true)
assert(notices[#notices].message:find("single",1,true))
ai.select("off")
local before=table.concat(vim.fn.readfile(file),"\n")
choice="cancel"; mapping.callback()
assert(ai.provider=="off" and before==table.concat(vim.fn.readfile(file),"\n"))
choice="dual"; mapping.callback()
assert(ai.provider=="ollama" and ai.local_mode=="dual" and read().local_mode=="dual")
choice="completion-only"; mapping.callback()
assert(ai.local_mode=="completion-only")
value=read(); value.model="custom-model"; vim.fn.writefile({vim.json.encode(value)},file)
ai.select("ollama")
before=table.concat(vim.fn.readfile(file),"\n")
choice="dual"; mapping.callback()
assert(ai.local_mode=="completion-only" and before==table.concat(vim.fn.readfile(file),"\n"))
assert(notices[#notices].message:find("fim_format",1,true))
vim.fn.writefile({vim.json.encode({provider="off"})},file)
mapping.callback()
assert(ai.local_mode=="dual" and ai.model=="qwen2.5-coder:3b-base")
vim.ui.select=original_select
ai.select("off",false)

""",
            temp,
        )
        print(
            "PASS quiet AI reselection, saved-model reload, Copilot switching, local-mode menu persistence/cancellation, and 10-second status"
        )
    finally:
        stop(nvim)
