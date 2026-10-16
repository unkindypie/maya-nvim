"""Exercise local engine coordination and prompts without network/model downloads."""

import tempfile
from integration import start, stop, wait

with tempfile.TemporaryDirectory(prefix="maya-ai-local-") as temp:
    nvim = start()
    try:
        nvim.ui_attach(110, 35, rgb=True)
        nvim.command("enew")
        nvim.exec_lua(
            """
local state = ...
local original = vim.fn.stdpath
vim.fn.stdpath = function(key) return key == "state" and state or original(key) end
_G.save = function(value) vim.fn.writefile({vim.json.encode(value)}, state .. "/ai.json") end
local ai = require("maya.ai")
_G.requests = {}
package.loaded["blink-edit.backends"] = {
 complete = function(opts, callback) requests[#requests+1] = {opts=opts, callback=callback}; return #requests end,
}
package.loaded["copilot"] = { setup=function() end }
vim.api.nvim_create_user_command("Copilot", function() end, {nargs="*",force=true})
_G.enabled = true
save({provider="ollama",local_mode="single",next_edit_model="test-sweep",model="old-custom",endpoint="http://localhost:12345"})
ai.select("ollama",false)
assert(ai.local_mode=="single" and ai.model=="old-custom")
assert(not ai.initialized.ollama, "single must not load Minuet")
assert(require("blink-edit.config").get().llm.model=="test-sweep")
assert(vim.fn.maparg("<C-j>","i",false,true).desc~="Accept first line of blink-edit prediction")
vim.api.nvim_buf_set_lines(0,0,-1,false,{"local value = 1", "print(value)"})
vim.api.nvim_win_set_cursor(0,{1,0})
""",
            temp,
        )
        nvim.exec_lua(
            """
require("maya.ai_next_edit").trigger()
assert(#requests==1)
requests[1].callback(nil,{text="local value = 2\\nprint(value)"})
""",
            temp,
        )
        wait(nvim, 'require("maya.ai_next_edit").visible()', timeout=2)
        nvim.exec_lua('require("maya.ai").accept()')
        assert nvim.current.buffer[0] == "local value = 2", (
            nvim.current.buffer[:],
            nvim.command_output("messages"),
            nvim.exec_lua(
                'return require("blink-edit.core.state").get_prediction(vim.api.nvim_get_current_buf())'
            ),
        )
        nvim.command("undo")
        assert nvim.current.buffer[0] == "local value = 1", nvim.current.buffer[:]
        nvim.exec_lua("""
local ai=require("maya.ai")
for i=1,10 do
 ai.select("ollama",false)
 require("maya.ai_next_edit").trigger()
 local late=requests[#requests].callback
 ai.select(i%2==0 and "copilot" or "off",false)
 late(nil,{text="local value = 999\\nprint(value)"})
end
""")
        assert not nvim.exec_lua('return require("maya.ai_next_edit").visible()')
        assert nvim.current.buffer[0] == "local value = 1"
        nvim.exec_lua("""
save({provider="ollama",local_mode="dual",model="qwen2.5-coder:1.5b-base-q8_0",next_edit_model="test-sweep"})
require("maya.ai").select("ollama",false)
local options=require("minuet").config.provider_options.openai_fim_compatible
assert(options.end_point:find("/api/generate",1,true))
local request=options.transform[1]({body={prompt="test"}})
assert(request.body.raw and request.body.options.num_ctx==4096)
local prompts=require("maya.ai_prompts")
assert(prompts.prompt("qwen","BEFORE","AFTER","type: int","test.py","python"):find("<|fim_suffix|>AFTER<|fim_middle|>",1,true))
local mellum=prompts.prompt("mellum","BEFORE","AFTER","type: int","test.py","python")
assert(mellum:find("<filename>test.py\\n<fim_suffix>AFTER<fim_prefix>BEFORE<fim_middle>",1,true))
assert(not mellum:find("<|fim",1,true))
""")
        nvim.input("i")
        wait(nvim, 'vim.fn.mode()=="i"')
        before = nvim.exec_lua("return #requests")
        nvim.exec_lua('require("maya.ai_next_edit").trigger()')
        assert nvim.exec_lua("return #requests") == before, (
            "Sweep ran in dual Insert mode"
        )
        nvim.exec_lua("""
_G.inline_callbacks={}
package.loaded["minuet.backends.openai_fim_compatible"]={
 complete=function(_,callback) inline_callbacks[#inline_callbacks+1]=callback end,
}
local ai=require("maya.ai")
for i=1,10 do
 ai.select("ollama",false)
 require("minuet.virtualtext").action.next()
 local late=inline_callbacks[#inline_callbacks]
 assert(late,"no Minuet request")
 ai.select(i%2==0 and "copilot" or "off",false)
 late({"must not appear"})
 assert(not require("minuet.virtualtext").action.is_visible())
end
ai.select("ollama",false)
""")
        nvim.input("z")
        before_accept = nvim.current.buffer[:]
        nvim.exec_lua("""
require("blink.cmp").hide()
require("minuet.virtualtext").action.next()
inline_callbacks[#inline_callbacks]({"AI"})
assert(require("minuet.virtualtext").action.is_visible())
require("maya.ai").accept()
""")
        wait(nvim, 'vim.api.nvim_get_current_line():find("AI",1,true)~=nil')
        nvim.input("<Esc>")
        wait(nvim, 'vim.fn.mode()=="n"')
        nvim.command("undo")
        assert nvim.current.buffer[:] == before_accept, (
            "AI undo removed preceding typed text"
        )
        wait(nvim, f"#requests > {before}", timeout=5)
        print(
            "PASS single/dual coordination, undo, rapid provider switching, native transport and FIM formats"
        )
    finally:
        stop(nvim)
