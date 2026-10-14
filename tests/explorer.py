"""Check real Explorer key presses, not just the mapping table."""
from pathlib import Path
import tempfile
import unittest
from integration import start, wait, stop


class ExplorerTest(unittest.TestCase):
    def test_tab_opens_and_enter_toggles_multiselection(self):
        with tempfile.TemporaryDirectory(prefix='maya-explorer-') as temp:
            root = Path(temp)
            (root / 'folder').mkdir()
            (root / 'folder/child.txt').write_text('child\n')
            file = root / 'file.txt'
            file.write_text('Maya\n')
            nvim = start()
            nvim.ui_attach(110,35,rgb=True)
            try:
                nvim.exec_lua('_G.explorer=Snacks.explorer({cwd=...})',temp)
                wait(nvim,'explorer and #explorer.list.items>=3')
                nvim.exec_lua('''for i,item in ipairs(explorer.list.items) do
 if item.dir and item.file:match("/folder$") then explorer.list:move(i,true,true); break end
end''')
                nvim.input('\t')
                wait(nvim,'''(function() for _,item in ipairs(explorer.list.items) do
 if item.file:match("/child.txt$") then return true end end return false end)()''')
                self.assertFalse(nvim.exec_lua('return explorer.closed'))
                nvim.exec_lua('''for i,item in ipairs(explorer.list.items) do
 if item.dir and item.file:match("/folder$") then explorer.list:move(i,true,true); break end
end''')
                nvim.input('\t')
                wait(nvim,'''(function() for _,item in ipairs(explorer.list.items) do
 if item.file:match("/child.txt$") then return false end end return true end)()''')
                self.assertFalse(nvim.exec_lua('return explorer.closed'))
                nvim.exec_lua('''for i,item in ipairs(explorer.list.items) do
 if item.file:match("/file.txt$") then explorer.list:move(i,true,true); break end
end''')
                nvim.input('\r')
                wait(nvim,'#explorer:selected() == 1')
                self.assertFalse(nvim.exec_lua('return explorer.closed'))
                nvim.exec_lua('''for i,item in ipairs(explorer.list.items) do
 if item.dir and item.file:match("/folder$") then explorer.list:move(i,true,true); break end
end''')
                nvim.input('\r')
                wait(nvim,'#explorer:selected() == 2')
                self.assertFalse(nvim.exec_lua('return explorer.closed'))
                nvim.exec_lua('''for i,item in ipairs(explorer.list.items) do
 if item.dir and item.file:match("/folder$") then explorer.list:move(i,true,true); break end
end''')
                nvim.input('\r')
                wait(nvim,'#explorer:selected() == 1')
                self.assertTrue(nvim.exec_lua('return explorer:selected()[1].file:match("/file.txt$") ~= nil'))
                nvim.exec_lua('''for i,item in ipairs(explorer.list.items) do
 if item.file:match("/file.txt$") then explorer.list:move(i,true,true); break end
end''')
                nvim.input('\t')
                wait(nvim,'explorer.closed')
                self.assertEqual(nvim.current.buffer.name, str(file))
            finally:
                stop(nvim)


if __name__ == '__main__':
    unittest.main()
