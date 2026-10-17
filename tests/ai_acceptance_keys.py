"""Accept Sweep through actual Tab mappings, retaining undo and stale-edit guards."""

import json
from pathlib import Path
import tempfile
from integration import start, stop, wait

with tempfile.TemporaryDirectory(prefix="maya-ai-acceptance-") as temp:
    Path(temp, "ai.json").write_text(
        json.dumps(
            {
                "provider": "ollama",
                "local_mode": "single",
                "next_edit_model": "test-sweep",
            }
        )
    )
    nvim = start()
    try:
        nvim.ui_attach(110, 35, rgb=True)
        nvim.command("enew")
        nvim.exec_lua(
            """local temp=...; local original=vim.fn.stdpath
vim.fn.stdpath=function(k) return k=="state" and temp or original(k) end
_G.responses={}
package.loaded["blink-edit.backends"]={complete=function(_,cb)
 responses[#responses+1]=cb; return #responses
end}
require("maya.user").config.ai_next_edit_debounce_ms=60000
vim.api.nvim_buf_set_lines(0,0,-1,false,{"local value = "})
require("maya.ai").select("ollama",false)
""",
            temp,
        )
        nvim.input("A1")
        wait(
            nvim,
            'vim.fn.mode()=="i" and vim.api.nvim_get_current_line()=="local value = 1"',
        )

        def predict(value):
            nvim.exec_lua(
                """require("blink.cmp").hide()
require("maya.ai_next_edit").trigger()
responses[#responses](nil,{text="local value = "..tostring(...)})""",
                value,
            )
            wait(nvim, 'require("maya.ai_next_edit").visible()')

        predict(2)
        nvim.input("\t")
        wait(nvim, 'vim.api.nvim_get_current_line()=="local value = 2"', timeout=3)
        assert "E565" not in nvim.command_output("messages")
        nvim.input("z")
        wait(nvim, 'vim.api.nvim_get_current_line():find("z",1,true)~=nil')
        nvim.input("<Esc>")
        wait(nvim, 'vim.fn.mode()=="n"')
        nvim.command("undo")
        assert nvim.current.buffer[:] == ["local value = 2"], (
            "later typing merged with acceptance"
        )
        nvim.command("undo")
        assert nvim.current.buffer[:] == ["local value = 1"], (
            "acceptance undo removed user typing"
        )

        predict(3)
        nvim.input("\t")
        wait(nvim, 'vim.api.nvim_get_current_line()=="local value = 3"', timeout=3)
        nvim.command("undo")
        assert nvim.current.buffer[:] == ["local value = 1"]

        predict(4)
        nvim.exec_lua("""assert(require("maya.ai").accept())
vim.api.nvim_buf_set_lines(0,0,-1,false,{"local value = 99"})""")
        assert nvim.current.buffer[:] == ["local value = 99"], (
            "queued acceptance overwrote intervening edit"
        )
        nvim.exec_lua('require("maya.ai").cancel()')
        predict(5)
        nvim.exec_lua("""assert(require("maya.ai").accept())
require("maya.ai").select("off",false)""")
        assert nvim.current.buffer[:] == ["local value = 99"], (
            "queued acceptance survived AI-off"
        )
        assert "E565" not in nvim.command_output("messages")
        nvim.exec_lua("""local state = require("blink-edit.core.state")
local render = require("blink-edit.core.render")
local buf = vim.api.nvim_create_buf(false, true)
state.set_prediction(buf, { text = "stale preview" })
vim.api.nvim_buf_delete(buf, { force = true })
assert(not vim.api.nvim_buf_is_valid(buf))
local cleared = false
render.set_visibility_listeners({on_clear = function(b)
  if b == buf then cleared = true end
end})
require("blink-edit").cancel()
assert(cleared, "wiped buffer cleanup skipped visibility notification")
assert(not state.has_prediction(buf), "wiped buffer retained prediction")
render.clear(buf) -- repeated cancellation must also be safe
render.set_visibility_listeners(nil)
""")
        print(
            "PASS Insert/Normal Tab acceptance, undo preserves typing, and queued acceptance invalidation"
        )
    finally:
        stop(nvim)
