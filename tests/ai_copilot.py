"""Real Cursortab daemon/native Copilot bridge with an in-process LSP transport."""

import os
from pathlib import Path
import tempfile
from integration import start, stop, wait

os.environ["MAYA_NVIM_NO_INSTALL"] = "1"
with tempfile.TemporaryDirectory(prefix="maya-native-copilot-") as temp:
    source = Path(temp, "example.py")
    source.write_text("def add(a, b):\n    return a - b\n")
    nvim = start()
    try:
        nvim.ui_attach(110, 35, rgb=True)
        nvim.command("edit " + nvim.funcs.fnameescape(str(source)))
        nvim.exec_lua(
            """
local state=...
local original=vim.fn.stdpath
vim.fn.stdpath=function(k) return k=="state" and state or original(k) end
local executable=vim.fn.executable
vim.fn.executable=function(name) return name=="copilot-language-server" and 1 or executable(name) end
_G.requests=0
vim.lsp.config("copilot", {
 root_dir=function(_,cb) cb(state) end,
 cmd=function(dispatchers)
  local closing=false
  local id=0
  return {
   request=function(method,params,callback)
    id=id+1
    local result={}
    if method=="initialize" then
     result={capabilities={textDocumentSync=1}}
    elseif method=="textDocument/copilotInlineEdit" then
     requests=requests+1
     result={edits={{text="    return a + b",range={start={line=1,character=0},["end"]={line=1,character=16}}}}}
    end
    vim.schedule(function() callback(nil,result) end)
    return true,id
   end,
   notify=function(method)
    if method=="exit" then closing=true; dispatchers.on_exit(0,0) end
    return true
   end,
   is_closing=function() return closing end,
   terminate=function() closing=true; dispatchers.on_exit(0,0) end,
  }
 end,
})
require("blink.cmp").setup({sources={default={}}})
require("maya.ai").select("copilot",false)
""",
            temp,
        )
        wait(nvim, '#vim.lsp.get_clients({name="copilot",bufnr=0}) == 1')
        # A modification exercises native scheduling, LSP bridge and daemon rendering.
        nvim.current.window.cursor = (2, 0)
        nvim.input("A ")
        wait(nvim, 'require("maya.ai_next_edit").visible()')
        assert nvim.exec_lua("return requests > 0")
        nvim.input("<S-Tab>")
        wait(nvim, 'vim.api.nvim_get_current_line():find("a + b",1,true) ~= nil')
        nvim.input("<Esc>")
        nvim.exec_lua('require("maya.ai").select("off",false)')
        wait(nvim, '#vim.lsp.get_clients({name="copilot"}) == 0')
        assert not nvim.exec_lua('return require("maya.ai_next_edit").visible()')
        assert not nvim.exec_lua('return require("cursortab.daemon").is_enabled()')
        nvim.exec_lua('require("cursortab.daemon").stop_daemon()')
        assert source.read_text() == "def add(a, b):\n    return a - b\n"
        print(
            "PASS: native Copilot LSP bridge, Cursortab preview/partial acceptance and AI-off shutdown"
        )
    finally:
        stop(nvim)
