#!/usr/bin/env python3
"""Real Neovim integration checks. Requires pynvim; does not alter existing project files."""

import os
from pathlib import Path
import tempfile
import time
import pynvim

os.environ["NVIM_APPNAME"] = "maya-nvim"
os.environ["MAYA_NVIM_NO_AI"] = "1"
os.environ["MAYA_NVIM_NO_SESSION"] = "1"
ROOT = Path(__file__).resolve().parents[1]


def start():
    return pynvim.attach("child", argv=["nvim", "--embed", "--headless"])


def wait(nvim, expression, timeout=45):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = nvim.exec_lua("return " + expression)
        if value:
            return value
        time.sleep(0.1)
    raise AssertionError(
        "Timed out: " + expression + "\n" + nvim.command_output("messages")
    )


def stop(nvim):
    try:
        nvim.command("qa!")
    except (EOFError, OSError):
        pass


def python_project():
    directory = Path("/home/may/Desktop/python/playground")
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", prefix="maya_editor_validation_", dir=directory
    ) as file:
        file.write(
            'import sys\nimport os\n\nvalue: int = "bad"\n\ndef add(a:int,b:int)->int:\n return a+b\n'
        )
        file.flush()
        nvim = start()
        try:
            nvim.command("edit " + nvim.funcs.fnameescape(file.name))
            wait(nvim, "#vim.lsp.get_clients({bufnr=0}) >= 2")
            diagnostics = wait(
                nvim,
                '(function() local d=vim.diagnostic.get(0); for _,item in ipairs(d) do if item.message:find("int",1,true) then return d end end end)()',
            )
            assert any("int" in d["message"] for d in diagnostics), diagnostics
            wait(
                nvim,
                '(function() for _,d in ipairs(vim.diagnostic.get(0)) do if tostring(d.code)=="F401" then return true end end return false end)()',
            )
            nvim.exec_lua('require("conform").format({timeout_ms=5000})')
            lines = nvim.current.buffer[:]
            assert lines.index("import os") < lines.index("import sys"), lines
            assert "def add(a: int, b: int) -> int:" in lines, lines
            assert "    return a + b" in lines, lines
            # Real LSP completion and definition requests, not just client attachment.
            result = nvim.exec_lua("""
local results = vim.lsp.buf_request_sync(0, "textDocument/completion", {
 textDocument={uri=vim.uri_from_bufnr(0)}, position={line=6,character=10}, context={triggerKind=1}
}, 10000)
return results
""")
            assert result, "No completion response"
            nvim.current.buffer[:] = [
                "value: int = 2",
                "",
                "def add(a: int, b: int) -> int:",
                "    return a + b",
                "",
                "result = add(value, 3)",
            ]
            nvim.command("write")
            wait(
                nvim,
                "#vim.diagnostic.get(0, {severity=vim.diagnostic.severity.ERROR}) == 0",
            )
            result = nvim.exec_lua("""return vim.lsp.buf_request_sync(0,"textDocument/definition",{
textDocument={uri=vim.uri_from_bufnr(0)},position={line=(function() for i,line in ipairs(vim.api.nvim_buf_get_lines(0,0,-1,false)) do if line:match("^result =") then return i-1 end end end)(),character=10}},10000)""")
            values = result.values() if isinstance(result, dict) else result
            assert any(x and x.get("result") for x in values), result
            print(
                "PASS Python project: Ruff diagnostics, formatting/imports, ty type error, completion and definition",
                flush=True,
            )
        finally:
            stop(nvim)


def reload_and_diff():
    with tempfile.TemporaryDirectory() as temp:
        file = Path(temp) / "external.txt"
        file.write_text("original\n")
        nvim = start()
        try:
            nvim.command("edit " + nvim.funcs.fnameescape(str(file)))
            source = nvim.current.buffer.number
            file.write_text("external replacement longer\n")
            wait(
                nvim,
                'vim.api.nvim_get_current_line() == "external replacement longer"',
                5,
            )
            assert nvim.current.buffer.number == source
            nvim.input("i")
            wait(nvim, 'vim.fn.mode()=="i"')
            replacement = Path(temp) / "replacement"
            replacement.write_text("atomic external replacement while inserting\n")
            replacement.replace(file)
            wait(
                nvim,
                'vim.api.nvim_get_current_line() == "atomic external replacement while inserting"',
                5,
            )
            assert nvim.current.buffer.number == source
            nvim.input("\x1b")
            nvim.current.buffer[:] = ["Maya unsaved edit"]
            # Native FileChangedShell is intercepted in this test only, to emulate keeping edits.
            nvim.exec_lua(
                'vim.api.nvim_create_autocmd("FileChangedShell", {callback=function() vim.v.fcs_choice="" end})'
            )
            file.write_text("Codex changed the file again\n")
            time.sleep(1.5)
            assert nvim.current.buffer[:] == ["Maya unsaved edit"]
            assert nvim.current.buffer.options["modified"]
            nvim.command("MayaDiffDisk")
            normal_windows = [
                w
                for w in nvim.windows
                if not nvim.api.win_get_config(w.handle)["relative"]
            ]
            assert len(normal_windows) == 2
            assert nvim.current.buffer[:] == ["Codex changed the file again"]
            assert all(w.options["diff"] for w in normal_windows)
            assert file.read_text() == "Codex changed the file again\n"
            print(
                "PASS external changes: same-buffer timer reload; unsaved edit preserved; native diff snapshot",
                flush=True,
            )
        finally:
            stop(nvim)


def mappings_and_plugins():
    nvim = start()
    try:
        nvim.exec_lua('vim.api.nvim_exec_autocmds("User", {pattern="VeryLazy"})')
        for key in [" f", " e", " w", "bd", " od", " ao", " ac", " gB", " dU"]:
            if key == "bd":
                key = " bd"
            assert nvim.funcs.maparg(key, "n"), key
        nvim.exec_lua("""
require("blink.cmp"); require("conform"); require("gitsigns"); require("dap"); require("dapui")
local spec = require("maya.plugins.completion")[1].opts.keymap["<Tab>"]
local ai = require("maya.ai")
local old=ai.accept
ai.accept=function() return true end
assert(spec[1] == "accept")
assert(spec[2]() == true)
ai.accept=function() return false end
assert(spec[2]() == false)
ai.accept=old
for _, ft in ipairs({"hyprlang","conf","config"}) do
 vim.bo.filetype=ft
 assert(vim.bo.indentexpr=="")
 assert(vim.b.snacks_indent==false)
end
""")
        print(
            "PASS mappings, plugin load, AI-first Tab dispatch, safe config indentation",
            flush=True,
        )
    finally:
        stop(nvim)


if __name__ == "__main__":
    mappings_and_plugins()
    reload_and_diff()
    python_project()
