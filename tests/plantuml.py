"""On-demand tools, real LSP, unsaved local preview, includes, errors and export."""

import os
from pathlib import Path
import tempfile
from integration import start, stop, wait

os.environ["MAYA_NVIM_NO_INSTALL"] = "1"
with tempfile.TemporaryDirectory(prefix="maya-plantuml-") as temp:
    directory = Path(temp)
    (directory / "shared.iuml").write_text("class Included\n")
    source = "@startuml\n!include shared.iuml\nclass Original\nIncluded --> Original\n@enduml\n"
    path = directory / "example.puml"
    path.write_text(source)
    nvim = start()
    try:
        nvim.ui_attach(110, 35, rgb=True)
        assert nvim.exec_lua('return package.loaded["maya.plantuml"] == nil')
        assert not nvim.exec_lua(
            'return require("lazy.core.config").plugins["plantuml-syntax"]._.loaded ~= nil'
        )
        nvim.command("edit " + nvim.funcs.fnameescape(str(path)))
        assert nvim.current.buffer.options["filetype"] == "plantuml"
        assert nvim.exec_lua(
            'return vim.fn.hlexists("plantumlKeyword") == 1 or vim.b.current_syntax == "plantuml"'
        )
        wait(nvim, '#vim.lsp.get_clients({name="plantuml_lsp",bufnr=0})==1')
        nvim.exec_lua(
            "_G.preview_url=nil; vim.ui.open=function(url) _G.preview_url=url end"
        )
        wait(nvim, 'require("maya.plantuml").status() ~= nil')
        assert len(nvim.windows) == 2
        assert nvim.current.buffer.name == str(path)
        nvim.input(" ")
        wait(
            nvim,
            '(function() for _,w in ipairs(vim.api.nvim_list_wins()) do local lines=vim.api.nvim_buf_get_lines(vim.api.nvim_win_get_buf(w),0,-1,false); if table.concat(lines," "):find("Preview UML Diagram",1,true) then return true end end return false end)()',
        )
        rows = nvim.exec_lua(
            'local rows={} for _,w in ipairs(vim.api.nvim_list_wins()) do local lines=vim.api.nvim_buf_get_lines(vim.api.nvim_win_get_buf(w),0,-1,false); if table.concat(lines," "):find("Preview UML Diagram",1,true) then rows=lines end end return rows'
        )
        assert "Preview UML Diagram" in next(line for line in rows if line.strip())
        nvim.input("<CR>")
        assert nvim.exec_lua('return require("maya.plantuml").status()==nil')
        nvim.input(" <CR>")
        wait(nvim, 'require("maya.plantuml").status() ~= nil')
        preview = Path(
            nvim.exec_lua('return require("maya.plantuml").status().directory')
        )
        wait(nvim, 'require("maya.plantuml").status().pane.path ~= nil')
        frame = Path(
            nvim.exec_lua('return require("maya.plantuml").status().pane.path')
        )
        assert frame.read_bytes().startswith(b"\x89PNG")
        nvim.current.buffer[:] = source.replace("Original", "Unsaved").splitlines()
        nvim.command("doautocmd TextChanged")
        wait(nvim, 'require("maya.plantuml").status().pane.path ~= ' + repr(str(frame)))
        good_path = nvim.exec_lua('return require("maya.plantuml").status().pane.path')
        good = Path(good_path).read_bytes()
        nvim.current.buffer[:] = ["@startuml", "class { broken", "@enduml"]
        nvim.command("doautocmd TextChanged")
        wait(nvim, 'require("maya.plantuml").status().error ~= nil')
        assert (
            nvim.exec_lua('return require("maya.plantuml").status().pane.path')
            == good_path
        )
        assert Path(good_path).read_bytes() == good
        wait(nvim, "#vim.diagnostic.get(0)>0")
        nvim.current.buffer[:] = source.replace("Original", "Exported").splitlines()
        for ext in ("svg", "png"):
            exported = directory / ("export." + ext)
            nvim.command("PlantumlExport " + nvim.funcs.fnameescape(str(exported)))
            wait(nvim, "vim.fn.filereadable(" + repr(str(exported)) + ")==1")
            data = exported.read_bytes()
            nvim.command("PlantumlExport " + nvim.funcs.fnameescape(str(exported)))
            assert exported.read_bytes() == data, (
                "existing export overwritten without bang"
            )
            assert (b"<svg" in data) if ext == "svg" else data.startswith(b"\x89PNG")
        nvim.command("PlantumlStop")
        assert not preview.exists()
        assert nvim.exec_lua('return require("maya.plantuml").status()==nil')
        nvim.exec_lua("""local m=require("maya.plantuml")
local install=m.install
local callback
m.install=function(done) callback=done end
m.open()
m.stop()
callback()
assert(m.status()==nil, "late installation reopened a stopped preview")
m.install=install
""")
        assert nvim.current.buffer.options["modified"]
        assert path.read_text() == source
        nvim.command("enew!")
        nvim.command("setfiletype text")
        assert nvim.exec_lua('return vim.fn.maparg(" <CR>","n")==""')
        nvim.input(" ")
        wait(
            nvim,
            '(function() for _,w in ipairs(vim.api.nvim_list_wins()) do if vim.api.nvim_win_get_config(w).relative~="" then return true end end return false end)()',
        )
        assert not nvim.exec_lua(
            'local rows={} for _,w in ipairs(vim.api.nvim_list_wins()) do vim.list_extend(rows,vim.api.nvim_buf_get_lines(vim.api.nvim_win_get_buf(w),0,-1,false)) end return table.concat(rows," "):find("Preview UML Diagram",1,true)~=nil'
        )
        nvim.input("<Esc>")
        print(
            "PASS: lazy syntax/LSP, automatic split, local unsaved PNG/includes, last-good preview, diagnostics, PNG/SVG exports and cleanup"
        )
    finally:
        stop(nvim)
