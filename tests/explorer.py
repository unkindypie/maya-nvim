"""Check real Explorer key presses, not just the mapping table."""

from pathlib import Path
import tempfile
import subprocess
import unittest
from integration import start, wait, stop


class ExplorerTest(unittest.TestCase):
    def test_tab_opens_and_s_toggles_multiselection(self):
        self.check_open_and_selection("\t")

    def test_enter_opens_and_s_toggles_multiselection(self):
        self.check_open_and_selection("\r")

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
 return found['.hidden'] and found['ignored.txt']
end)()""",
                )
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
