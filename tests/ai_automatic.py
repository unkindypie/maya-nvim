"""Automatic local suggestions survive an unselected completion menu and rapid typing."""

import os
import tempfile
import time
from integration import start, stop, wait

with tempfile.TemporaryDirectory(prefix="maya-auto-ai-") as state:
    os.environ.pop("MAYA_NVIM_NO_AI", None)
    nvim = start()
    try:
        nvim.ui_attach(110, 35, rgb=True)
        nvim.command("enew")
        nvim.exec_lua(
            """
local state=...
local original=vim.fn.stdpath
vim.fn.stdpath=function(key) return key=="state" and state or original(key) end
vim.fn.writefile({vim.json.encode({provider="ollama",local_mode="dual",model="qwen2.5-coder:1.5b-base-q8_0"})},state.."/ai.json")
_G.request_count=0
package.loaded["minuet.backends.openai_fim_compatible"]={complete=function(_,callback)
 request_count=request_count+1
 vim.defer_fn(function() callback({"urn 42"}) end,30)
end}
package.loaded["blink-edit.backends"]={complete=function() return 1 end}
vim.api.nvim_buf_set_lines(0,0,-1,false,{"def add(a, b):","    "})
vim.bo.filetype="python"
vim.api.nvim_win_set_cursor(0,{2,3})
""",
            state,
        )
        nvim.input("A")
        wait(nvim, 'require("maya.ai").provider=="ollama"')
        wait(
            nvim,
            'request_count>=1 and require("minuet.virtualtext").action.is_visible()',
            timeout=5,
        )
        count = nvim.exec_lua("return request_count")
        time.sleep(2)
        assert nvim.exec_lua("return request_count") == count
        assert nvim.exec_lua('return require("minuet.virtualtext").action.is_visible()')
        nvim.input("ret")
        wait(nvim, 'require("blink.cmp").is_visible()', timeout=5)
        wait(
            nvim,
            'request_count>=2 and require("minuet.virtualtext").action.is_visible()',
            timeout=5,
        )
        assert nvim.exec_lua('return require("blink.cmp").get_selected_item()==nil')
        nvim.input("<C-j>")
        wait(nvim, 'require("blink.cmp").get_selected_item()~=nil')
        assert not nvim.exec_lua(
            'return require("minuet.virtualtext").action.is_visible()'
        )
        nvim.exec_lua("""
_G.ai_accept_calls=0
require("maya.ai").accept=function() ai_accept_calls=ai_accept_calls+1; return false end
""")
        nvim.input("\t")
        wait(nvim, 'not require("blink.cmp").is_visible()')
        assert nvim.exec_lua("return ai_accept_calls") == 0
        print(
            "PASS automatic activation, idle completion beside unselected menu, and selection priority"
        )
    finally:
        stop(nvim)
