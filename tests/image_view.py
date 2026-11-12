"""Readable viewport, hovered mouse zoom, dragging, toolbar and live-frame camera retention."""

import os
from pathlib import Path
import struct
import subprocess
import tempfile
from integration import start, stop, wait

os.environ["MAYA_NVIM_NO_INSTALL"] = "1"
with tempfile.TemporaryDirectory(prefix="maya-image-view-") as temp:
    path = Path(temp) / "large.png"
    subprocess.run(
        ["magick", "-size", "3670x1840", "gradient:white-blue", str(path)], check=True
    )
    nvim = start()
    try:
        nvim.ui_attach(120, 40, rgb=True)
        assert nvim.exec_lua('return package.loaded["maya.image_view"]==nil')
        nvim.command("enew")
        nvim.current.buffer[:] = ["alpha", "beta", "gamma"]
        nvim.exec_lua(
            '_G.pane=require("maya.media").pane(vim.api.nvim_get_current_buf()); pane:update(...)',
            str(path),
        )
        wait(nvim, "pane.view_path ~= nil")
        initial = nvim.exec_lua(
            "return {pane.view.zoom,pane.view.viewport,pane.view_path}"
        )
        assert initial[0] == 1.25
        assert initial[1]["crop_width"] < 3670 / 3
        data = Path(initial[2]).read_bytes()
        assert struct.unpack(">II", data[16:24]) == (
            initial[1]["width"],
            initial[1]["height"],
        )
        assert nvim.exec_lua("return vim.api.nvim_get_current_win() ~= pane.win")
        row, col = nvim.exec_lua("return vim.api.nvim_win_get_position(pane.win)")
        nvim.api.input_mouse("wheel", "up", "", 0, row + 5, col + 8)
        wait(nvim, "pane.view.zoom > 1.25")
        assert nvim.exec_lua("return vim.api.nvim_get_current_win() ~= pane.win"), (
            "wheel stole source focus"
        )
        before = nvim.exec_lua("return {pane.view.x,pane.view.y}")
        nvim.api.input_mouse("left", "press", "", 0, row + 9, col + 15)
        nvim.api.input_mouse("left", "drag", "", 0, row + 5, col + 8)
        nvim.api.input_mouse("left", "release", "", 0, row + 5, col + 8)
        wait(
            nvim,
            "pane.view.x > " + str(before[0]) + " or pane.view.y > " + str(before[1]),
        )
        assert nvim.exec_lua("return vim.api.nvim_get_current_win()==pane.win")
        # Click Fit in the real window bar, then restore readable size from keyboard.
        fit_col = nvim.exec_lua(
            'local text=vim.api.nvim_eval_statusline(vim.wo[pane.win].winbar,{winid=pane.win,use_winbar=true}).str; return vim.fn.strdisplaywidth(text:sub(1,text:find("Fit",1,true)-1))'
        )
        nvim.api.input_mouse("left", "press", "", 0, row, col + fit_col)
        nvim.api.input_mouse("left", "release", "", 0, row, col + fit_col)
        wait(nvim, "pane.view.fit == true", 3)
        wait(
            nvim,
            "pane.view.viewport.crop_width == 3670 and pane.view.viewport.crop_height == 1840",
        )
        nvim.input("0")
        wait(nvim, "pane.view.zoom==1 and not pane.view.fit")
        nvim.input("+")
        wait(nvim, "pane.view.zoom>1")
        nvim.input("l")
        wait(nvim, "pane.view.job==nil")
        camera = nvim.exec_lua("return {pane.view.zoom,pane.view.x,pane.view.y}")
        nvim.exec_lua("pane:update(...)", str(path))
        assert (
            nvim.exec_lua("return {pane.view.zoom,pane.view.x,pane.view.y}") == camera
        )
        nvim.exec_lua("pane:close()")
        assert not Path(initial[2]).parent.exists()
        assert path.exists()
        row, col = nvim.exec_lua("return vim.api.nvim_win_get_position(0)")
        nvim.api.input_mouse("left", "press", "", 0, row + 1, col + 1)
        nvim.api.input_mouse("left", "release", "", 0, row + 1, col + 1)
        wait(nvim, "vim.api.nvim_win_get_cursor(0)[1] == 2")
        assert nvim.current.buffer[:] == ["alpha", "beta", "gamma"]
        print(
            "PASS: readable crop, wheel zoom without focus theft, mouse drag, clickable Fit, keyboard controls, camera retention and cleanup"
        )
    finally:
        stop(nvim)
