"""Real Cursortab daemon/HTTP/keys/provider handover, without model downloads."""

import json
import os
from pathlib import Path
import tempfile
import time

import pynvim
from ai_candidate_support import Capture
from integration import wait, stop, ROOT

os.environ.update(
    NVIM_APPNAME="maya-nvim",
    MAYA_NVIM_NO_AI="1",
    MAYA_NVIM_NO_INSTALL="1",
    MAYA_NVIM_NO_SESSION="1",
)


def run():
    expected = "def add(a, b):\n    return a + b"
    delay = [0]

    def reply(row):
        time.sleep(delay[0])
        prefix = (
            row["body"]["prompt"]
            .rsplit("<|file_sep|>updated/", 1)[-1]
            .partition("\n")[2]
        )
        assert expected.startswith(prefix), prefix
        return {"choices": [{"text": expected[len(prefix) :], "finish_reason": "stop"}]}

    capture = Capture(reply=reply)
    try:
        with tempfile.TemporaryDirectory(prefix="maya-cursortab-runtime-") as temp:
            source = Path(temp, "example.py")
            source.write_text("def add(a, b):\n    return a")
            Path(temp, "ai.json").write_text(
                json.dumps(
                    {
                        "schema": 2,
                        "provider": "off",
                        "model": "test-sweep",
                        "engine": "sweep",
                        "endpoint": capture.url,
                    }
                )
            )
            nvim = pynvim.attach(
                "child", argv=[str(ROOT / "bin/mvim"), "--embed", "--headless"]
            )
            try:
                nvim.ui_attach(110, 35, rgb=True)
                nvim.command("edit " + nvim.funcs.fnameescape(str(source)))
                nvim.exec_lua(
                    """local state=...; local original=vim.fn.stdpath
vim.fn.stdpath=function(k) return k=="state" and state or original(k) end
require("maya.user").config.ai_completion_debounce_ms=80
require("maya.user").config.ai_next_edit_debounce_ms=150
require("blink.cmp").setup({sources={default={}}})
require("maya.ai").select("ollama",false)
""",
                    temp,
                )
                nvim.current.window.cursor = (2, 0)
                nvim.input("A +")
                wait(nvim, 'require("maya.ai_next_edit").visible()')
                assert capture.rows, "first automatic edit did not trigger"
                assert (
                    nvim.exec_lua(
                        'return require("cursortab.config").get().behavior.prefetch'
                    )
                    is True
                )
                count = len(capture.rows)
                time.sleep(0.6)
                assert nvim.exec_lua('return require("maya.ai_next_edit").visible()'), (
                    "prefetch replaced the visible preview"
                )
                count = len(capture.rows)
                nvim.input("<C-]>")
                time.sleep(0.2)
                assert not nvim.exec_lua(
                    'return require("maya.ai_next_edit").visible()'
                )
                nvim.input("<Left><Right>")
                time.sleep(0.3)
                assert len(capture.rows) == count, (
                    "dismissal did not survive cursor movement"
                )
                nvim.input(" ")
                deadline = time.monotonic() + 4
                while len(capture.rows) == count and time.monotonic() < deadline:
                    time.sleep(0.02)
                assert len(capture.rows) > count, "next edit did not resume requests"
                wait(nvim, 'not require("maya.ai_next_edit").pending()')
                # Native rejection caching may withhold the same proposal; an explicit request bypasses it.
                nvim.exec_lua('require("maya.ai_next_edit").trigger()')
                wait(nvim, 'require("maya.ai_next_edit").visible()')
                before = nvim.current.buffer[:]
                nvim.input("<Tab>")
                time.sleep(0.4)
                assert "\n".join(nvim.current.buffer[:]) == expected, (
                    nvim.current.buffer[:]
                )
                nvim.input("<Esc>u")
                time.sleep(0.2)
                assert nvim.current.buffer[:] == before, (
                    "undo swallowed typing",
                    nvim.current.buffer[:],
                    before,
                )
                nvim.exec_lua(
                    'require("maya.ai_next_edit").cancel(); require("maya.ai_next_edit").trigger()'
                )
                wait(nvim, 'require("maya.ai_next_edit").visible()')
                nvim.input("<Tab>")
                time.sleep(0.3)
                assert "\n".join(nvim.current.buffer[:]) == expected, (
                    "Normal Tab did not accept"
                )
                nvim.input("u")
                time.sleep(0.2)
                assert nvim.current.buffer[:] == before, (
                    "Normal acceptance undo lost typing"
                )
                nvim.exec_lua('require("maya.ai").select("off",false)')
                assert not nvim.exec_lua(
                    'return require("maya.ai_next_edit").visible()'
                )
                count = len(capture.rows)
                nvim.input("A ")
                time.sleep(0.4)
                assert len(capture.rows) == count, "off still made requests"
                # Cancel a delayed response without losing unsaved edits.
                nvim.input("<Esc>")
                nvim.current.buffer[:] = ["def add(a, b):", "    return a +"]
                delay[0] = 0.6
                nvim.exec_lua(
                    'require("maya.ai").select("ollama",false); require("maya.ai_next_edit").trigger()'
                )
                deadline = time.monotonic() + 4
                while len(capture.rows) == count and time.monotonic() < deadline:
                    time.sleep(0.02)
                assert len(capture.rows) > count
                nvim.exec_lua('require("maya.ai").select("off",false)')
                nvim.current.buffer[0] = "# unsaved edit survives"
                time.sleep(0.9)
                assert nvim.current.buffer[0] == "# unsaved edit survives"
                assert not nvim.exec_lua(
                    'return require("maya.ai_next_edit").visible()'
                )
                assert source.read_text() == "def add(a, b):\n    return a"
                assert not nvim.exec_lua(
                    'return package.loaded["minuet"] ~= nil or package.loaded["blink-edit"] ~= nil'
                )
                print(
                    "PASS: automatic first edit, preview ownership, Tab, undo, AI-off, late response and unsaved edits"
                )
            finally:
                nvim.exec_lua(
                    'if package.loaded["cursortab.daemon"] then require("cursortab.daemon").stop_daemon() end'
                )
                stop(nvim)
    finally:
        capture.close()


def normal_append_check():
    from ai_candidate_support import start as candidate_start, close

    source = "local function add(a, b)\n  return a + b\nend"
    expected = source + "\n\nreturn add"

    def reply(row):
        prefix = (
            row["body"]["prompt"]
            .rsplit("<|file_sep|>updated/", 1)[-1]
            .partition("\n")[2]
        )
        assert expected.startswith(prefix), prefix
        return {"choices": [{"text": expected[len(prefix) :], "finish_reason": "stop"}]}

    capture = Capture(reply=reply)
    try:
        with tempfile.TemporaryDirectory(prefix="maya-normal-append-") as temp:
            path = Path(temp, "fixture.lua")
            path.write_text(source[:-1])
            nvim = candidate_start(
                "cursortab",
                ROOT / "vendor/cursortab.nvim",
                capture.url,
                temp,
                path,
                "lua",
            )
            try:
                nvim.exec_lua(
                    """local state,endpoint=...
local original=vim.fn.stdpath
vim.fn.stdpath=function(k) return k=="state" and state or original(k) end
vim.fn.writefile({vim.json.encode({schema=2,model="test-sweep",engine="sweep",endpoint=endpoint})},state.."/ai.json")
require("maya.ai").select("ollama",false)
local cfg=require("cursortab.config").get()
assert(cfg.behavior.prefetch and not cfg.behavior.normal_edit_only)
assert(cfg.behavior.cursor_prediction.enabled and cfg.behavior.cursor_prediction.auto_advance)
assert(cfg.behavior.text_change_debounce==50 and cfg.behavior.idle_completion_delay==50)
""",
                    temp,
                    capture.url,
                )
                nvim.current.window.cursor = (3, 0)
                nvim.input("Ad<Esc>")
                wait(nvim, 'vim.fn.mode()=="n"')
                wait(nvim, 'require("maya.ai_next_edit").visible()')
                # Tab may first navigate to the insertion before accepting it.
                for _ in range(3):
                    nvim.input("<Tab>")
                    time.sleep(0.3)
                    if "\n".join(nvim.current.buffer[:]) == expected:
                        break
                assert "\n".join(nvim.current.buffer[:]) == expected
                print(
                    "PASS: default behavior enables Normal additions and Tab navigation/acceptance"
                )
            finally:
                close(nvim, "cursortab")
    finally:
        capture.close()


if __name__ == "__main__":
    run()
    normal_append_check()
