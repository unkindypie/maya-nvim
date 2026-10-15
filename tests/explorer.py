"""Check real Explorer key presses, not just the mapping table."""

from pathlib import Path
import tempfile
import time
import subprocess
import unittest
from integration import start, wait, stop


class ExplorerTest(unittest.TestCase):
    def test_tab_opens_and_s_toggles_multiselection(self):
        self.check_open_and_selection("\t")

    def test_enter_opens_and_s_toggles_multiselection(self):
        self.check_open_and_selection("\r")

    def test_tab_and_enter_open_from_search_input(self):
        for key in ("\t", "\r"):
            with (
                self.subTest(key=key),
                tempfile.TemporaryDirectory(prefix="maya-explorer-input-") as temp,
            ):
                file = Path(temp) / "file.txt"
                file.write_text("Maya\n")
                nvim = start()
                try:
                    nvim.ui_attach(110, 35, rgb=True)
                    nvim.exec_lua("_G.explorer=Snacks.explorer({cwd=...})", temp)
                    wait(nvim, "explorer and #explorer.list.items == 2")
                    time.sleep(0.3)
                    nvim.exec_lua("""for i, item in ipairs(explorer.list.items) do
 if item.file:match("/file.txt$") then explorer.list:move(i,true,true); break end
end""")
                    nvim.input("i")
                    wait(
                        nvim, "vim.api.nvim_get_current_win() == explorer.input.win.win"
                    )
                    nvim.input(key)
                    wait(nvim, "explorer.closed")
                    self.assertEqual(nvim.current.buffer.name, str(file))
                finally:
                    stop(nvim)

    def test_curated_help_and_new_file_aliases(self):
        with tempfile.TemporaryDirectory(prefix="maya-explorer-help-") as temp:
            nvim = start()
            try:
                nvim.ui_attach(110, 35, rgb=True)
                nvim.exec_lua("_G.explorer=Snacks.explorer({cwd=...})", temp)
                wait(nvim, "explorer and #explorer.list.items == 1")
                time.sleep(0.3)
                nvim.input("?")
                wait(nvim, 'vim.api.nvim_win_get_config(0).relative == "editor"')
                text = "\n".join(nvim.current.buffer[:])
                self.assertIn("Enter or Tab", text)
                self.assertIn("a or n", text)
                self.assertNotIn("autopairs", text)
                self.assertNotIn("<CR>", text)
                self.assertLess(text.index("Open file"), text.index("Navigation"))
                nvim.input("q")
                wait(nvim, "vim.api.nvim_get_current_win() == explorer.list.win.win")
                for key in ("a", "n"):
                    nvim.exec_lua("""explorer.list:move(1,true,true)
Snacks.input=function(opts,callback) _G.add_file=callback end
_G.add_file=nil""")
                    nvim.input(key)
                    wait(nvim, "add_file ~= nil")
                    nvim.exec_lua("add_file(...)", key + ".txt")
                    self.assertTrue((Path(temp) / (key + ".txt")).is_file())
            finally:
                stop(nvim)

    def test_search_excludes_hidden_and_ignored_but_tree_shows_them(self):
        with tempfile.TemporaryDirectory(prefix="maya-explorer-search-") as temp:
            root = Path(temp)
            subprocess.run(["git", "init", "-q", temp], check=True)
            (root / ".gitignore").write_text("match_ignored.txt\nignored_dir/\n")
            for name in ["match_visible.txt", ".match_hidden.txt", "match_ignored.txt"]:
                (root / name).write_text("test\n")
            for directory in [".hidden_dir", "ignored_dir"]:
                (root / directory).mkdir()
                (root / directory / "match_nested.txt").write_text("test\n")
            nvim = start()
            try:
                nvim.ui_attach(110, 35, rgb=True)
                nvim.exec_lua("_G.explorer=Snacks.explorer({cwd=...})", temp)
                visible = """(function()
 local found={}
 for _,item in ipairs(explorer.list.items) do found[vim.fn.fnamemodify(item.file,':t')]=true end
 return found['.match_hidden.txt'] and found['match_ignored.txt'] and found['match_visible.txt']
end)()"""
                wait(nvim, visible)
                time.sleep(0.3)
                nvim.input("imatch")
                wait(nvim, "explorer.input.filter.meta.searching == true")
                wait(
                    nvim,
                    """(function()
 local found=false
 for _,item in ipairs(explorer.list.items) do
  if item.file:match('/match_visible.txt$') then found=true end
  if item.file:match('hidden') or item.file:match('ignored') or item.file:match('nested') then return false end
 end
 return found
end)()""",
                )
                nvim.input("<BS>" * 5)
                wait(nvim, visible)
            finally:
                stop(nvim)

    def check_open_and_selection(self, open_key):
        with tempfile.TemporaryDirectory(prefix="maya-explorer-") as temp:
            root = Path(temp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".hidden").write_text("hidden\n")
            (root / ".gitignore").write_text("ignored.txt\n")
            (root / "ignored.txt").write_text("ignored\n")
            (root / "folder").mkdir()
            (root / "folder/child.txt").write_text("child\n")
            file = root / "file.txt"
            file.write_text("Maya\n")
            nvim = start()
            nvim.ui_attach(110, 35, rgb=True)
            try:
                nvim.exec_lua("_G.explorer=Snacks.explorer({cwd=...})", temp)
                wait(nvim, "explorer and #explorer.list.items>=3")
                wait(
                    nvim,
                    """(function()
 local found = {}
 for _, item in ipairs(explorer.list.items) do found[vim.fn.fnamemodify(item.file, ':t')] = true end
 return found['.hidden'] and found['ignored.txt'] and found['folder'] and found['file.txt']
end)()""",
                )
                time.sleep(
                    0.3
                )  # Let the initial asynchronous Git status refresh settle.
                nvim.exec_lua("""for i,item in ipairs(explorer.list.items) do
 if item.dir and item.file:match("/folder$") then explorer.list:move(i,true,true); break end
end""")
                nvim.input(open_key)
                wait(
                    nvim,
                    """(function() for _,item in ipairs(explorer.list.items) do
 if item.file:match("/child.txt$") then return true end end return false end)()""",
                )
                self.assertFalse(nvim.exec_lua("return explorer.closed"))
                nvim.exec_lua("""for i,item in ipairs(explorer.list.items) do
 if item.dir and item.file:match("/folder$") then explorer.list:move(i,true,true); break end
end""")
                nvim.input(open_key)
                wait(
                    nvim,
                    """(function() for _,item in ipairs(explorer.list.items) do
 if item.file:match("/child.txt$") then return false end end return true end)()""",
                )
                self.assertFalse(nvim.exec_lua("return explorer.closed"))
                nvim.exec_lua("""for i,item in ipairs(explorer.list.items) do
 if item.file:match("/file.txt$") then explorer.list:move(i,true,true); break end
end""")
                nvim.input("s")
                wait(nvim, "#explorer:selected() == 1")
                self.assertFalse(nvim.exec_lua("return explorer.closed"))
                nvim.exec_lua("""for i,item in ipairs(explorer.list.items) do
 if item.dir and item.file:match("/folder$") then explorer.list:move(i,true,true); break end
end""")
                nvim.input("s")
                wait(nvim, "#explorer:selected() == 2")
                self.assertFalse(nvim.exec_lua("return explorer.closed"))
                nvim.exec_lua("""for i,item in ipairs(explorer.list.items) do
 if item.dir and item.file:match("/folder$") then explorer.list:move(i,true,true); break end
end""")
                nvim.input("s")
                wait(nvim, "#explorer:selected() == 1")
                self.assertTrue(
                    nvim.exec_lua(
                        'return explorer:selected()[1].file:match("/file.txt$") ~= nil'
                    )
                )
                nvim.exec_lua("""for i,item in ipairs(explorer.list.items) do
 if item.file:match("/file.txt$") then explorer.list:move(i,true,true); break end
end""")
                nvim.input(open_key)
                wait(nvim, "explorer.closed")
                self.assertEqual(nvim.current.buffer.name, str(file))
            finally:
                stop(nvim)


if __name__ == "__main__":
    unittest.main()
