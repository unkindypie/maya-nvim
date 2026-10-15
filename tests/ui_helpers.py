#!/usr/bin/env python3
"""Comments, inline blame, and safe desktop launcher arguments."""

import os
from pathlib import Path
import tempfile
import time
from integration import start, wait, stop, ROOT


def main():
    nvim = start()
    nvim.ui_attach(110, 35, rgb=True)
    try:
        nvim.exec_lua('require("lazy").load({plugins={"lualine.nvim"}})')
        nvim.command("redrawstatus")
        time.sleep(2.2)  # Lualine reports configuration notices after two seconds.
        assert nvim.funcs.exists(":LualineNotices") == 0, (
            "Unexpected lualine configuration warning"
        )
        print("PASS lualine startup without configuration notices", flush=True)
        with tempfile.TemporaryDirectory(prefix="maya-statusline-") as temp:
            root = Path(temp)
            markdown = root / "preview.md"
            markdown.write_text("# Preview\n")
            shell = root / "check.sh"
            shell.write_text("#!/bin/sh\necho hello\n")
            nvim.command("edit " + str(markdown))
            wait(
                nvim,
                'require("maya.statusline").tools():find("Fmt: prettier", 1, true) ~= nil',
            )
            nvim.exec_lua("vim.b.maya_noformat = true")
            assert "Fmt:" not in nvim.exec_lua(
                'return require("maya.statusline").tools()'
            )
            nvim.command("edit " + str(shell))
            wait(
                nvim,
                'require("maya.statusline").tools():find("Lint: shellcheck", 1, true) ~= nil',
            )
            wait(nvim, "#vim.lsp.get_clients({bufnr=0}) > 0")
            status = nvim.exec_lua('return require("maya.statusline").tools()')
            assert "LSP: bashls" in status, status
            assert "Fmt: shfmt" in status and "prettier" not in status, status
            original_window = nvim.current.window.handle
            nvim.input(" li")
            wait(nvim, 'vim.api.nvim_win_get_config(0).relative == "editor"')
            panel = "\n".join(nvim.current.buffer[:])
            assert "Attached language servers" in panel and "bashls" in panel, panel
            assert "Lint: shellcheck" in panel and "Command:" in panel, panel
            nvim.input("q")
            wait(nvim, f"vim.api.nvim_get_current_win() == {original_window}")
            python = root / "check.py"
            python.write_text("value = 1\n")
            nvim.command("edit " + str(python))
            wait(
                nvim,
                'require("maya.statusline").tools():find("Fmt: ruff", 1, true) ~= nil',
            )
            status = nvim.exec_lua('return require("maya.statusline").tools()')
            assert status.split("Fmt: ")[1] == "ruff", status
            nvim.command("enew")
            assert nvim.exec_lua('return require("maya.statusline").tools()') == ""
            print(
                "PASS buffer-local LSP, linter, formatter status and disabled formatting",
                flush=True,
            )

        nvim.command("enew")
        nvim.current.buffer[:] = ["local value = 1"]
        nvim.command("setfiletype lua")
        nvim.input(" /")
        wait(nvim, 'vim.api.nvim_get_current_line():match("^%-%-") ~= nil')
        nvim.input(" /")
        wait(nvim, 'vim.api.nvim_get_current_line() == "local value = 1"')
        nvim.exec_lua("""
local bank=require("maya.pokemon")
local header=Snacks.config.dashboard.preset.header
local found=false
for _,sound in ipairs(bank) do if header:find(sound,1,true) then found=true end end
assert(found, "dashboard sound must come from the local bank")
""")
        nvim.command("edit! " + str(ROOT / "README.md"))
        nvim.current.window.cursor = (2, 0)
        nvim.input("k")
        text = wait(
            nvim,
            """(function()
 for ns,id in pairs(vim.api.nvim_get_namespaces()) do
  if ns:match("blame") then
   for _,mark in ipairs(vim.api.nvim_buf_get_extmarks(0,id,0,-1,{details=true})) do
    local text=vim.inspect(mark[4].virt_text)
    if text:match("Maya") and text:match("2026") then
     assert(mark[4].virt_text_pos == "right_align", "blame should align with the window's right edge")
     return text
    end
   end
  end
 end
 return false
end)()""",
            15,
        )
        assert "build isolated" in text.lower(), text
        print(
            "PASS native comment mapping and inline blame author/date/commit summary",
            flush=True,
        )
    finally:
        stop(nvim)
    with tempfile.TemporaryDirectory(prefix="maya-close-others-") as temp:
        root = Path(temp)
        first, second = root / "keep.txt", root / "other.txt"
        first.write_text("keep on disk\n")
        second.write_text("other on disk\n")
        nvim = start()
        try:
            nvim.command("edit " + str(first))
            keep = nvim.current.buffer.number
            nvim.current.buffer[:] = ["keep unsaved changes"]
            nvim.command("tabedit " + str(second))
            other = nvim.current.buffer.number
            nvim.current.buffer[:] = ["other unsaved changes"]
            nvim.command("tabprevious")
            nvim.exec_lua("""
local native=vim.fn.confirm
vim.fn.confirm=function() return 3 end
require("maya.util").close_others()
vim.fn.confirm=native
""")
            assert len(nvim.tabpages) == 2
            assert nvim.buffers[other].options["modified"]
            nvim.exec_lua("""
local native=vim.fn.confirm
vim.fn.confirm=function() return 2 end
require("maya.util").close_others()
vim.fn.confirm=native
""")
            assert len(nvim.tabpages) == 1
            assert (
                len(
                    [
                        w
                        for w in nvim.windows
                        if not nvim.api.win_get_config(w.handle)["relative"]
                    ]
                )
                == 1
            )
            assert nvim.current.buffer.number == keep
            assert nvim.current.buffer[:] == ["keep unsaved changes"]
            assert [b.number for b in nvim.buffers if b.options["buflisted"]] == [keep]
            assert second.read_text() == "other on disk\n"
            print(
                "PASS Close all others: current unsaved buffer kept; cancel protects dirty buffer/tabs; explicit discard closes others",
                flush=True,
            )
        finally:
            stop(nvim)
    with tempfile.TemporaryDirectory(prefix="maya open directory ") as temp:
        root = Path(temp)
        capture = root / "args.txt"
        thunar = root / "thunar"
        # Record each argument on its own line; the directory with spaces must remain one argument.
        thunar.write_text(
            '#!/usr/bin/env bash\nprintf "%s\\n" "$@" > '
            + "'"
            + str(capture)
            + "'"
            + "\n"
        )
        thunar.chmod(0o755)
        old_path = os.environ["PATH"]
        os.environ["PATH"] = str(root) + os.pathsep + old_path
        nvim = start()
        try:
            file = root / "some file.txt"
            file.write_text("Maya\n")
            nvim.command("edit " + nvim.funcs.fnameescape(str(file)))
            nvim.exec_lua('require("maya.util").open_directory()')
            wait(
                nvim, "vim.fn.filereadable(...) == 1".replace("...", repr(str(capture)))
            )
            assert capture.read_text().splitlines() == [str(root)]
            print(
                "PASS desktop explorer launch with a directory containing spaces",
                flush=True,
            )
        finally:
            stop(nvim)
            os.environ["PATH"] = old_path


if __name__ == "__main__":
    main()
