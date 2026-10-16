"""Opt-in real Ollama editor smoke; reads test preferences, never changes saved choices."""

import json
import os
from pathlib import Path
import tempfile
from integration import start, stop, wait

if os.environ.get("MAYA_NVIM_TEST_OLLAMA") != "1":
    raise SystemExit("Set MAYA_NVIM_TEST_OLLAMA=1 to run real model requests")

with tempfile.TemporaryDirectory(prefix="maya-ai-inference-") as temp:
    config = {
        "provider": "ollama",
        "local_mode": "dual",
        "model": "qwen2.5-coder:1.5b-base-q8_0",
        "next_edit_model": "hf.co/sweepai/sweep-next-edit-1.5B:Q8_0",
        "endpoint": "http://127.0.0.1:11434",
    }
    Path(temp, "ai.json").write_text(json.dumps(config))
    nvim = start()
    try:
        nvim.ui_attach(110, 35, rgb=True)
        nvim.command("enew")
        nvim.exec_lua(
            """
local state=...
local original=vim.fn.stdpath
vim.fn.stdpath=function(key) return key=="state" and state or original(key) end
vim.api.nvim_buf_set_lines(0,0,-1,false,{"def add(a: int, b: int) -> int:","    "})
vim.bo.filetype="python"
require("maya.ai").select("ollama",false)
""",
            temp,
        )
        nvim.current.window.cursor = (2, 3)
        nvim.input("A")
        wait(nvim, 'vim.fn.mode()=="i"')
        nvim.exec_lua(
            'require("blink.cmp").hide(); require("minuet.virtualtext").action.next()'
        )
        wait(nvim, 'require("minuet.virtualtext").action.is_visible()', timeout=20)
        nvim.exec_lua('require("maya.ai").accept()')
        wait(
            nvim,
            'vim.api.nvim_get_current_line():find("return",1,true)~=nil',
            timeout=5,
        )
        print(
            "PASS real Minuet Qwen FIM prediction and acceptance:",
            nvim.current.buffer[1],
            flush=True,
        )
        nvim.input("<Esc>")
        wait(nvim, 'vim.fn.mode()=="n"')
        nvim.exec_lua("""
require("maya.ai").cancel()
vim.api.nvim_buf_set_lines(0,0,-1,false,{"def greet(person):","    return person.upper()"})
vim.api.nvim_win_set_cursor(0,{1,0})
""")
        nvim.input("i")
        wait(nvim, 'vim.fn.mode()=="i"')
        nvim.exec_lua(
            'vim.api.nvim_buf_set_lines(0,1,2,false,{"    return person.uper()"})'
        )
        nvim.input("<Esc>")
        wait(nvim, 'vim.fn.mode()=="n"')
        nvim.exec_lua('require("maya.ai_next_edit").trigger()')
        wait(nvim, 'require("maya.ai_next_edit").visible()', timeout=20)
        nvim.exec_lua('require("maya.ai").accept()')
        wait(
            nvim,
            'vim.api.nvim_buf_get_lines(0,1,2,false)[1]:find("person.upper()",1,true)~=nil',
            timeout=5,
        )
        print(
            "PASS real Sweep next-edit replacement:", nvim.current.buffer[1], flush=True
        )
        nvim.command("undo")
        assert nvim.current.buffer[0] == "def greet(person):", nvim.current.buffer[:]
        assert nvim.current.buffer[1] == "    return person.uper()", (
            nvim.current.buffer[:]
        )
        print("PASS real accepted edit undo preserves preceding user edit", flush=True)
        config["local_mode"] = "single"
        Path(temp, "ai.json").write_text(json.dumps(config))
        nvim.exec_lua(
            'require("maya.ai").select("ollama",false); vim.api.nvim_buf_set_lines(0,0,-1,false,{"def add(a, b):","    return "}); vim.api.nvim_win_set_cursor(0,{2,10})'
        )
        nvim.input("A")
        wait(nvim, 'vim.fn.mode()=="i"')
        nvim.exec_lua(
            'require("blink.cmp").hide(); require("maya.ai_next_edit").trigger()'
        )
        wait(nvim, 'require("maya.ai_next_edit").visible()', timeout=20)
        nvim.exec_lua('require("maya.ai").accept()')
        wait(nvim, "#vim.api.nvim_get_current_line()>11", timeout=5)
        print(
            "PASS real single-model Sweep insertion:",
            nvim.current.buffer[1],
            flush=True,
        )
    finally:
        stop(nvim)
