"""Check actual Markdown rendering and keyboard toggles without editing the file."""

import os
from pathlib import Path
import tempfile
import time
import unittest
from integration import start, wait, stop

os.environ["MAYA_NVIM_NO_INSTALL"] = "1"
os.environ["MAYA_NVIM_NO_SOUND"] = "1"


class MarkdownPreviewTest(unittest.TestCase):
    def test_render_and_toggle_preserve_source(self):
        source = '# Preview\n\n| Tool | State |\n| --- | --- |\n| mvim | Ready |\n\n- [x] Markdown\n\n```lua\nprint("hello")\n```\n\nCursor here.\n'
        with tempfile.TemporaryDirectory(prefix="maya-markdown-") as temp:
            file = Path(temp) / "preview.md"
            file.write_text(source)
            nvim = start()
            try:
                nvim.ui_attach(120, 40, rgb=True)
                self.assertTrue(
                    nvim.exec_lua('return package.loaded["render-markdown"] == nil')
                )
                nvim.command("edit " + str(file))
                nvim.current.window.cursor = (13, 0)
                wait(nvim, 'package.loaded["render-markdown"] ~= nil')
                marks = """#vim.api.nvim_buf_get_extmarks(0,
 vim.api.nvim_get_namespaces()["render-markdown.nvim"], 0, -1, {})"""
                wait(nvim, marks + " > 0")
                self.assertEqual(
                    nvim.exec_lua('return vim.fn.maparg(" om", "n", false, true).desc'),
                    "Toggle Markdown preview",
                )
                time.sleep(0.3)  # Let the initial asynchronous render settle.
                nvim.exec_lua("""
local ns = vim.api.nvim_get_namespaces()["render-markdown.nvim"]
local labels = 0
for _, mark in ipairs(vim.api.nvim_buf_get_extmarks(0, ns, {8,0}, {8,-1}, {details=true})) do
  for _, chunk in ipairs(mark[4].virt_text or {}) do
    if chunk[1]:find("lua", 1, true) then labels = labels + 1 end
    local groups = type(chunk[2]) == "table" and chunk[2] or {chunk[2]}
    for _, group in ipairs(groups) do
      local hl = vim.api.nvim_get_hl(0, {name=group, link=false})
      assert(hl.bg == nil and not hl.reverse, "Code fence has an opaque background: " .. group)
    end
    assert(not chunk[1]:find("█", 1, true), "Code fence must not draw a solid border")
  end
end
assert(labels > 0, "Language label should remain visible")
""")
                nvim.input("i")
                wait(nvim, "vim.wo.conceallevel == 0")
                wait(nvim, marks + " == 0")
                nvim.input("\x1b")
                wait(nvim, marks + " > 0")
                nvim.input(" om")
                wait(nvim, 'require("render-markdown").get() == false')
                wait(nvim, marks + " == 0")
                nvim.input(" om")
                wait(nvim, 'require("render-markdown").get() == true')
                wait(nvim, marks + " > 0")
                nvim.command("RenderMarkdown toggle")
                wait(nvim, marks + " == 0")
                self.assertEqual(
                    list(nvim.current.buffer[:]), source.rstrip("\n").split("\n")
                )
                self.assertFalse(nvim.current.buffer.options["modified"])
                self.assertEqual(file.read_text(), source)
            finally:
                stop(nvim)


if __name__ == "__main__":
    unittest.main()
