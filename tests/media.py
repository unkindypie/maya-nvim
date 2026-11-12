"""Automatic raster-only display and editable SVG split previews, without source writes."""

import os
import subprocess
import tempfile
from pathlib import Path
from integration import start, stop, wait

os.environ["MAYA_NVIM_NO_INSTALL"] = "1"
with tempfile.TemporaryDirectory(prefix="maya-media-") as temp:
    root = Path(temp)
    raster = root / "picture.png"
    subprocess.run(["magick", "-size", "80x60", "xc:red", str(raster)], check=True)
    original = raster.read_bytes()
    svg = root / "drawing.svg"
    source = '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="60"><rect width="80" height="60" fill="red"/></svg>\n'
    svg.write_text(source)
    nvim = start()
    try:
        nvim.ui_attach(110, 35, rgb=True)
        assert nvim.exec_lua(
            'return package.loaded["maya.media"]==nil and package.loaded["snacks.image"]==nil'
        )
        # Test the first raster open as well as later opens handled by Snacks itself.
        nvim.command("edit " + nvim.funcs.fnameescape(str(raster)))
        wait(nvim, "not vim.bo.modifiable")
        nvim.command("write!")
        assert raster.read_bytes() == original
        nvim.command("edit " + nvim.funcs.fnameescape(str(svg)))
        buf = nvim.current.buffer.number
        wait(nvim, 'require("maya.media").status(' + str(buf) + ") ~= nil")
        assert nvim.current.buffer.number == buf
        assert nvim.current.buffer.options["filetype"] == "svg"
        assert nvim.current.buffer.options["modifiable"]
        assert (
            nvim.exec_lua(
                'local count=0 for _,w in ipairs(vim.api.nvim_list_wins()) do if vim.api.nvim_win_get_config(w).relative=="" then count=count+1 end end return count'
            )
            == 2
        )
        state = 'require("maya.media").status(' + str(buf) + ")"
        wait(nvim, state + ".pane.path ~= nil")
        first = Path(nvim.exec_lua("return " + state + ".pane.path"))
        assert first.read_bytes().startswith(b"\x89PNG")
        nvim.current.buffer[:] = source.replace(
            'fill="red"', 'fill="blue"'
        ).splitlines()
        nvim.command("doautocmd TextChanged")
        wait(nvim, state + ".pane.path ~= " + repr(str(first)))
        last = Path(nvim.exec_lua("return " + state + ".pane.path"))
        assert first.read_bytes() != last.read_bytes()
        nvim.current.buffer[:] = ["<svg broken"]
        nvim.command("doautocmd TextChanged")
        wait(nvim, state + ".version >= 3 and " + state + ".job == nil")
        assert nvim.exec_lua("return " + state + ".pane.path") == str(last)
        nvim.command("enew!")
        wait(nvim, 'require("maya.media").status(' + str(buf) + ") == nil")
        assert not first.parent.exists()
        assert (
            nvim.exec_lua(
                'local count=0 for _,w in ipairs(vim.api.nvim_list_wins()) do if vim.api.nvim_win_get_config(w).relative=="" then count=count+1 end end return count'
            )
            == 1
        )
        nvim.command("edit " + nvim.funcs.fnameescape(str(raster)))
        wait(nvim, "not vim.bo.modifiable")
        assert (
            nvim.exec_lua(
                'local count=0 for _,w in ipairs(vim.api.nvim_list_wins()) do if vim.api.nvim_win_get_config(w).relative=="" then count=count+1 end end return count'
            )
            == 1
        )
        # A headless terminal gets Snacks' informative fallback instead of raw binary.
        assert not nvim.current.buffer.options["modifiable"]
        nvim.command("write!")
        assert raster.read_bytes() == original
        nvim.command("buffer " + str(buf))
        wait(nvim, 'require("maya.media").status(' + str(buf) + ") ~= nil")
        assert nvim.current.buffer.number == buf
        nvim.exec_lua('require("maya.media").status(...).pane:close()', buf)
        wait(nvim, 'require("maya.media").status(' + str(buf) + ") == nil")
        assert nvim.current.buffer.number == buf
        assert svg.read_text() == source
        assert nvim.exec_lua("return vim.bo.modified"), "unsaved SVG edits were lost"
        print(
            "PASS: media stays lazy; automatic editable SVG split, unsaved refresh/errors, cleanup and display-only raster preservation"
        )
    finally:
        stop(nvim)
