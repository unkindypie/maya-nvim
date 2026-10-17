"""Headless HTML preview checks with a fake graphical browser launcher."""

import os
import tempfile
import time
import unittest
from pathlib import Path

import pynvim
from integration import ROOT, start, stop

os.environ["MAYA_NVIM_NO_INSTALL"] = "1"
os.environ["MAYA_NVIM_NO_AI"] = "1"
os.environ["MAYA_NVIM_NO_SESSION"] = "1"
os.environ["MAYA_NVIM_NO_SOUND"] = "1"


class HtmlPreviewTest(unittest.TestCase):
    def setUp(self):
        self.nvim = None
        self.temp = tempfile.TemporaryDirectory(prefix="maya-html-preview-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / "xdg"
        self.config.mkdir()
        (self.config / "maya-nvim").symlink_to(ROOT)
        self.browser_log = self.root / "browser.log"
        self.browser_fail = self.root / "browser-fail"
        fakebin = self.root / "bin"
        fakebin.mkdir()
        self.write_executable(
            fakebin / "xdg-settings",
            """#!/usr/bin/env bash
if [ "$1" = "get" ] && [ "$2" = "default-web-browser" ]; then
  echo test.Browser.desktop
  exit 0
fi
exit 1
""",
        )
        self.write_executable(
            fakebin / "gtk-launch",
            """#!/usr/bin/env bash
if [ -e "$MAYA_TEST_BROWSER_FAIL" ]; then
  echo "simulated browser failure" >&2
  exit 1
fi
printf '%s\\n' "$@" >> "$MAYA_TEST_BROWSER_LOG"
exit 0
""",
        )
        self.saved_env = {
            key: os.environ.get(key)
            for key in (
                "XDG_CONFIG_HOME",
                "XDG_STATE_HOME",
                "XDG_CACHE_HOME",
                "PATH",
                "MAYA_TEST_BROWSER_LOG",
                "MAYA_TEST_BROWSER_FAIL",
            )
        }
        self.addCleanup(self.restore_env)
        os.environ["XDG_CONFIG_HOME"] = str(self.config)
        os.environ["XDG_STATE_HOME"] = str(self.root / "state")
        os.environ["XDG_CACHE_HOME"] = str(self.root / "cache")
        os.environ["PATH"] = str(fakebin) + os.pathsep + os.environ.get("PATH", "")
        os.environ["MAYA_TEST_BROWSER_LOG"] = str(self.browser_log)
        os.environ["MAYA_TEST_BROWSER_FAIL"] = str(self.browser_fail)
        self.nvim = start()
        self.addCleanup(stop, self.nvim)
        self.nvim.exec_lua(
            """
_G.__maya_notifications = {}
vim.notify = function(message, level)
  table.insert(_G.__maya_notifications, { message = tostring(message), level = level })
end
"""
        )

    def restore_env(self):
        for key, value in self.saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    @staticmethod
    def write_executable(path, content):
        path.write_text(content)
        path.chmod(0o755)

    def open_file(self, path, cwd):
        self.nvim.command("cd " + self.nvim.funcs.fnameescape(str(cwd)))
        self.nvim.command("edit " + self.nvim.funcs.fnameescape(str(path)))

    def clear_browser_log(self):
        self.browser_log.unlink(missing_ok=True)

    def wait_for_browser_log(self, timeout=10):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.browser_log.exists():
                lines = self.browser_log.read_text().splitlines()
                if len(lines) >= 2:
                    return lines
            time.sleep(0.05)
        self.fail("Browser launcher was not called\n" + self.messages())

    def wait_for_notification(self, text, timeout=10):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            notifications = self.nvim.exec_lua("return _G.__maya_notifications")
            for item in notifications:
                if text in item["message"]:
                    return item
            time.sleep(0.05)
        self.fail(f"Missing notification containing {text!r}\n{self.messages()}")

    def messages(self):
        try:
            return self.nvim.command_output("messages")
        except (EOFError, OSError, pynvim.Error):
            return ""

    def assert_registered(self):
        self.assertEqual(self.nvim.funcs.exists(":MayaHtmlPreview"), 2)
        self.assertEqual(self.nvim.funcs.exists(":MayaHtmlPreviewIndex"), 2)
        self.assertEqual(
            self.nvim.exec_lua('return vim.fn.maparg(" hp", "n", false, true).desc'),
            "Preview current HTML in browser",
        )
        self.assertEqual(
            self.nvim.exec_lua('return vim.fn.maparg(" hi", "n", false, true).desc'),
            "Preview index.html in browser",
        )
        self.assertTrue(self.nvim.funcs.maparg(" h", "n"))

    def test_current_html_with_spaces_and_shell_metacharacters(self):
        project = self.root / "project"
        project.mkdir()
        name = "página with spaces & 'quotes' $(touch SHOULD_NOT_EXIST).html"
        file = project / name
        file.write_text("<title>Current HTML</title>\n")
        self.open_file(file, project)
        self.assert_registered()
        self.clear_browser_log()
        self.nvim.command("MayaHtmlPreview")
        lines = self.wait_for_browser_log()
        self.assertEqual(lines[0], "test.Browser")
        expected = self.nvim.exec_lua("return vim.uri_from_fname(...)", str(file))
        self.assertEqual(lines[1], expected)
        self.assertFalse((project / "SHOULD_NOT_EXIST").exists())
        self.assertFalse((Path.cwd() / "SHOULD_NOT_EXIST").exists())

    def test_index_fallback_uses_project_root(self):
        project = self.root / "project"
        project.mkdir()
        (project / ".git").mkdir()
        index = project / "index.html"
        index.write_text("<title>Project index</title>\n")
        sub = project / "sub"
        sub.mkdir()
        notes = sub / "notes.txt"
        notes.write_text("not html\n")
        self.open_file(notes, sub)
        self.clear_browser_log()
        self.nvim.command("MayaHtmlPreview")
        lines = self.wait_for_browser_log()
        expected = self.nvim.exec_lua("return vim.uri_from_fname(...)", str(index))
        self.assertEqual(lines[1], expected)
        self.wait_for_notification("previewing")

    def test_index_command(self):
        project = self.root / "project"
        project.mkdir()
        index = project / "index.html"
        index.write_text("<title>Project index</title>\n")
        notes = project / "notes.txt"
        notes.write_text("not html\n")
        self.open_file(notes, project)
        self.clear_browser_log()
        self.nvim.command("MayaHtmlPreview index")
        lines = self.wait_for_browser_log()
        expected = self.nvim.exec_lua("return vim.uri_from_fname(...)", str(index))
        self.assertEqual(lines[1], expected)

    def test_modified_html_warns_and_previews_saved_file(self):
        project = self.root / "project"
        project.mkdir()
        file = project / "index.html"
        file.write_text("<title>On disk</title>\n")
        self.open_file(file, project)
        self.nvim.current.buffer[:] = ["<title>Unsaved</title>"]
        self.clear_browser_log()
        self.nvim.command("MayaHtmlPreview")
        lines = self.wait_for_browser_log()
        expected = self.nvim.exec_lua("return vim.uri_from_fname(...)", str(file))
        self.assertEqual(lines[1], expected)
        self.wait_for_notification("unsaved changes are not included")

    def test_missing_index_and_unsupported_buffer(self):
        project = self.root / "project"
        project.mkdir()
        notes = project / "notes.txt"
        notes.write_text("not html\n")
        self.open_file(notes, project)
        self.clear_browser_log()
        self.nvim.command("MayaHtmlPreview")
        item = self.wait_for_notification("No index.html")
        self.assertEqual(item["level"], 4)
        self.assertFalse(self.browser_log.exists())

    def test_missing_html_file_reports_error(self):
        project = self.root / "project"
        project.mkdir()
        file = project / "deleted.html"
        file.write_text("<title>Deleted</title>\n")
        self.open_file(file, project)
        file.unlink()
        self.clear_browser_log()
        self.nvim.command("MayaHtmlPreview")
        item = self.wait_for_notification("Save the current buffer")
        self.assertEqual(item["level"], 4)
        self.assertFalse(self.browser_log.exists())

    def test_browser_failure_reports_error(self):
        project = self.root / "project"
        project.mkdir()
        file = project / "index.html"
        file.write_text("<title>Browser failure</title>\n")
        self.open_file(file, project)
        self.browser_fail.touch()
        self.clear_browser_log()
        self.nvim.command("MayaHtmlPreview")
        item = self.wait_for_notification("Browser could not be launched")
        self.assertEqual(item["level"], 4)
        self.assertIn("simulated browser failure", item["message"])


if __name__ == "__main__":
    unittest.main()
