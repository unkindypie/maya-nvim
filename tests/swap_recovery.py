"""Recover a real crashed Neovim swap without touching existing project files."""

import os
from pathlib import Path
import signal
import tempfile
import unittest
from integration import start, stop, wait


class SwapRecoveryTest(unittest.TestCase):
    def test_native_recovery_readonly_and_skip(self):
        for option in (0, 1, 2):
            with (
                self.subTest(option=option),
                tempfile.TemporaryDirectory(prefix="maya-swap-") as temp,
            ):
                file = Path(temp) / "file.txt"
                file.write_text("on disk\n")
                writer = start()
                swap = None
                try:
                    writer.command("edit " + str(file))
                    writer.current.buffer[:] = ["unsaved recovered text"]
                    writer.command("preserve")
                    swap = Path(writer.eval("swapname(bufnr())"))
                    os.kill(writer.funcs.getpid(), signal.SIGKILL)
                finally:
                    try:
                        stop(writer)
                    except Exception:
                        pass
                nvim = start()
                try:
                    nvim.ui_attach(110, 35, rgb=True)
                    nvim.exec_lua("""vim.ui.select=function(items,opts,callback)
 recovery={items=items,opts=opts,callback=callback}
end""")
                    nvim.command("edit " + str(file))
                    wait(nvim, "recovery ~= nil")
                    self.assertTrue(swap.exists())
                    self.assertNotEqual(nvim.current.buffer.name, str(file))
                    nvim.exec_lua("recovery.callback(recovery.items[...])", option + 1)
                    if option == 0:
                        self.assertEqual(
                            list(nvim.current.buffer[:]), ["unsaved recovered text"]
                        )
                        self.assertTrue(nvim.current.buffer.options["modified"])
                    elif option == 1:
                        self.assertEqual(list(nvim.current.buffer[:]), ["on disk"])
                        self.assertTrue(nvim.current.buffer.options["readonly"])
                    else:
                        self.assertNotEqual(nvim.current.buffer.name, str(file))
                    self.assertEqual(file.read_text(), "on disk\n")
                    self.assertTrue(swap.exists())
                finally:
                    stop(nvim)
                    if swap:
                        swap.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
