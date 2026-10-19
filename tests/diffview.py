"""Real Git tree, branch/remote comparisons and preservation of unsaved buffers."""

import os
import subprocess
import tempfile
from pathlib import Path

import pynvim
from integration import ROOT, start, stop, wait

with tempfile.TemporaryDirectory(prefix="maya-diffview-") as temp:
    repo = Path(temp)

    def git(*args):
        return subprocess.check_output(["git", "-C", temp, *args], text=True).strip()

    git("init", "-b", "main")
    git("config", "user.name", "Diffview Test")
    git("config", "user.email", "diffview@example.invalid")
    (repo / "src").mkdir()
    file = repo / "src/example.txt"
    file.write_text("original value\n")
    git("add", ".")
    git("commit", "-m", "base")
    git("update-ref", "refs/remotes/origin/main", "HEAD")
    git("checkout", "-b", "feature")
    file.write_text("branch value\n")
    git("commit", "-am", "feature")
    file.write_text("working value\n")
    (repo / "src/new.txt").write_text("untracked value\n")
    source = os.environ.get("MAYA_DIFFVIEW_COMPAT_SOURCE")
    if source:
        nvim = pynvim.attach(
            "child", argv=[str(ROOT / "bin/mvim"), "--clean", "--embed", "--headless"]
        )
        nvim.exec_lua(
            'vim.opt.rtp:append(...); vim.cmd("runtime plugin/diffview.lua"); require("diffview").setup({file_panel={listing_style="tree"}})',
            source,
        )
    else:
        nvim = start()
    try:
        nvim.ui_attach(140, 45, rgb=True)
        nvim.command("cd " + nvim.funcs.fnameescape(temp))
        nvim.command("edit " + nvim.funcs.fnameescape(str(file)))
        original = nvim.current.buffer
        original.append("unsaved text")
        original_lines = original[:]
        version = nvim.exec_lua("return vim.version()")
        assert version["major"] == 0 and version["minor"] >= 12, version

        def open_diff(rev, expected):
            nvim.command("DiffviewOpen" + (" " + rev if rev else ""))
            wait(
                nvim,
                """(function()
for _, win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
 local b=vim.api.nvim_win_get_buf(win)
 if vim.bo[b].filetype=="DiffviewFiles" and table.concat(vim.api.nvim_buf_get_lines(b,0,-1,false),"\\n"):find("example.txt",1,true) then return true end
end end)()""",
            )
            wait(
                nvim,
                """(function() for _,w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
local b=vim.api.nvim_win_get_buf(w)
if vim.wo[w].diff and table.concat(vim.api.nvim_buf_get_lines(b,0,-1,false),"\\n"):find(...,1,true) then return true end
end end)()""".replace("...", '"' + expected + '"'),
            )
            assert (
                nvim.exec_lua(
                    'return require("diffview.config").get_config().file_panel.listing_style'
                )
                == "tree"
            )
            nvim.command("DiffviewClose")
            assert original[:] == original_lines and original.options["modified"]

        open_diff("", "branch value")
        open_diff("main", "original value")
        open_diff("origin/main...HEAD", "original value")
        open_diff("main..feature", "branch value")
        if not source:
            # Exercise both new entry points and cancel/empty prompt behavior.
            for revision in (None, ""):
                tabs = len(nvim.tabpages)
                nvim.exec_lua(
                    """local revision = ...; if revision == vim.NIL then revision = nil end
local input = vim.ui.input
vim.ui.input = function(_, callback) callback(revision) end
vim.fn.maparg(" gV", "n", false, true).callback()
vim.ui.input = input""",
                    revision,
                )
                assert len(nvim.tabpages) == tabs
            nvim.exec_lua("""local input = vim.ui.input
vim.ui.input = function(_, callback) callback("origin/main...HEAD") end
vim.fn.maparg(" gV", "n", false, true).callback()
vim.ui.input = input""")
            wait(nvim, 'vim.bo.filetype == "DiffviewFiles" or vim.wo.diff')
            nvim.input(" gq")
            wait(nvim, "#vim.api.nvim_list_tabpages() == 1")
            nvim.input(" gv")
            wait(nvim, "#vim.api.nvim_list_tabpages() == 2")
            nvim.input(" gq")
            wait(nvim, "#vim.api.nvim_list_tabpages() == 1")
            assert original[:] == original_lines and original.options["modified"]
        messages = nvim.command_output("messages")
        assert (
            "Error executing" not in messages and "Invalid window id" not in messages
        ), messages
        print(
            f"PASS Neovim {version['major']}.{version['minor']}.{version['patch']}: changed-file tree, working/branch/remote/range diffs, unsaved edits retained"
        )
    finally:
        stop(nvim)
