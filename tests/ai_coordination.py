"""Deterministic scheduling, preview ownership, dismissal and late response checks."""

import json
import tempfile
import time
from pathlib import Path

from integration import start, stop, wait


def has_model_label(nvim, model, width=110):
    return nvim.exec_lua(
        """local model,width=...; vim.cmd.redraw()
for row=1,35 do
 local text=""; for col=1,width do text=text..vim.fn.screenstring(row,col) end
 if text:sub(-#model)==model then return true end
end
return false""",
        model,
        width,
    )


with tempfile.TemporaryDirectory(prefix="maya-coordination-") as temp:
    Path(temp, "ai.json").write_text(
        json.dumps(
            {
                "provider": "ollama",
                "local_mode": "dual",
                "model": "qwen2.5-coder:1.5b-base-q8_0",
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
_G.q={}; _G.s={}
package.loaded["minuet.backends.openai_fim_compatible"]={complete=function(_,cb) q[#q+1]=cb end}
package.loaded["blink-edit.backends"]={complete=function(_,cb) s[#s+1]=cb; return #s end}
vim.api.nvim_buf_set_lines(0,0,-1,false,{"local x = 1"})
require("maya.ai").select("ollama",false)
""",
            temp,
        )
        nvim.input("A ")
        wait(nvim, "#q==1")
        time.sleep(1.4)
        assert nvim.exec_lua("return #s") == 0, "Sweep competed with pending Qwen"
        nvim.exec_lua('q[1]({"+ 2"})')
        wait(nvim, 'require("minuet.virtualtext").action.is_visible()')
        qwen_model = "qwen2.5-coder:1.5b-base-q8_0"
        sweep_model = "hf.co/sweepai/sweep-next-edit-1.5B:Q8_0"
        assert has_model_label(nvim, qwen_model)
        nvim.ui_try_resize(80, 35)
        assert has_model_label(nvim, qwen_model, 80)
        nvim.ui_try_resize(110, 35)
        assert has_model_label(nvim, qwen_model)
        assert qwen_model not in "\n".join(nvim.current.buffer[:])
        time.sleep(1.4)
        assert nvim.exec_lua("return #s==0 and #q==1")
        nvim.exec_lua('require("maya.ai").accept()')
        wait(nvim, "#s==1")
        assert not has_model_label(nvim, qwen_model)
        assert nvim.exec_lua("return #q") == 1, "acceptance restarted Qwen"
        nvim.exec_lua('s[1](nil,{text="local x = 3"})')
        wait(nvim, 'require("maya.ai_next_edit").visible()')
        assert has_model_label(nvim, sweep_model)
        nvim.ui_try_resize(80, 35)
        assert has_model_label(nvim, sweep_model, 80)
        nvim.ui_try_resize(110, 35)
        assert sweep_model not in "\n".join(nvim.current.buffer[:])
        time.sleep(1.4)
        assert nvim.exec_lua(
            'return #q==1 and #s==1 and require("maya.ai_next_edit").visible()'
        )
        nvim.exec_lua('require("blink-edit").reject()')
        assert not has_model_label(nvim, sweep_model)
        nvim.input("<Left>")
        time.sleep(0.9)
        assert nvim.exec_lua("return #q==1 and #s==1"), "navigation lifted dismissal"
        nvim.input("z")
        wait(nvim, "#q==2")
        nvim.input("y")
        wait(nvim, "#q==3")
        nvim.exec_lua(
            'q[2]({"STALE"}); assert(not require("minuet.virtualtext").action.is_visible()); q[3]({})'
        )
        wait(nvim, "#s==2")
        nvim.exec_lua(
            'require("maya.ai").select("off",false); s[2](nil,{text="STALE"})'
        )
        time.sleep(0.1)
        assert not nvim.exec_lua('return require("maya.ai_next_edit").visible()')
        nvim.input("<Esc>")
        wait(nvim, 'vim.fn.mode()=="n"')
        nvim.exec_lua(
            'require("maya.ai").select("ollama",false); require("maya.ai_next_edit").trigger()'
        )
        nvim.input("v")
        wait(nvim, 'vim.fn.mode()=="v"')
        nvim.exec_lua('s[#s](nil,{text="STALE_VISUAL"})')
        time.sleep(0.1)
        assert not nvim.exec_lua('return require("maya.ai_next_edit").visible()')
        nvim.input("<Esc>")
        wait(nvim, 'vim.fn.mode()=="n"')
        nvim.input("A")
        wait(nvim, 'vim.fn.mode()=="i"')
        nvim.exec_lua('require("maya.ai").action("dismiss")')
        before_reload = nvim.exec_lua("return #q")
        time.sleep(0.3)
        assert nvim.exec_lua("return #q") == before_reload
        assert "dismissed" in nvim.exec_lua(
            'return require("maya.ai_coordinator").status()'
        )
        nvim.exec_lua('require("maya.ai").select("ollama",false)')
        wait(nvim, f"#q=={before_reload + 1}")
        assert (
            nvim.exec_lua('return require("maya.ai_coordinator").status()')
            == "waiting for model response"
        )
        nvim.exec_lua('require("maya.ai").select("off",false)')
        print(
            "PASS pending serialization, preview ownership, dismissal/re-enable, resumed typing, stale callbacks and model labels"
        )
    finally:
        stop(nvim)
