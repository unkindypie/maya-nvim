#!/usr/bin/env python3
"""Real language, debug, AI, and folder-session tests; requires pynvim."""
import json
import os
from pathlib import Path
import tempfile
import time
from integration import start, wait, stop
import pynvim


def cpp_project():
    path = Path('/home/may/Desktop/cpp/vita-sdl/src/main.cpp')
    original = path.read_bytes()
    nvim = start()
    try:
        nvim.exec_lua('''
_G.maya_cpp_published = false
local native=vim.lsp.handlers["textDocument/publishDiagnostics"]
vim.lsp.handlers["textDocument/publishDiagnostics"]=function(err,result,ctx,config)
 native(err,result,ctx,config)
 if vim.lsp.get_client_by_id(ctx.client_id).name=="clangd" then _G.maya_cpp_published=true end
end
''')
        nvim.command('edit ' + nvim.funcs.fnameescape(str(path)))
        wait(nvim, '_G.maya_cpp_published', 60)
        errors = nvim.exec_lua('return vim.diagnostic.get(0,{severity=vim.diagnostic.severity.ERROR})')
        assert not errors, errors
        baseline = nvim.current.buffer[:]
        nvim.current.buffer.append('int maya_editor_typecheck_error = "wrong";')
        errors = wait(nvim, '(function() local d=vim.diagnostic.get(0,{severity=vim.diagnostic.severity.ERROR}); return #d>0 and d end)()')
        assert any('int' in d['message'] for d in errors), errors
        nvim.current.buffer[:] = baseline
        wait(nvim, '#vim.diagnostic.get(0,{severity=vim.diagnostic.severity.ERROR})==0')
        assert path.read_bytes() == original
        print('PASS vita-sdl: clangd zero errors; injected unsaved C++ type error detected and cleared', flush=True)
    finally:
        stop(nvim)


def rust_first_use():
    with tempfile.TemporaryDirectory(prefix='maya-rust-') as temp:
        root = Path(temp)
        (root / 'Cargo.toml').write_text('[package]\nname="maya_editor_check"\nversion="0.1.0"\nedition="2021"\n')
        (root / 'src').mkdir()
        (root / 'src/main.rs').write_text('fn main() { let value: i32 = "bad"; println!("{}", value); }\n')
        nvim = start()
        try:
            nvim.command('edit ' + nvim.funcs.fnameescape(str(root / 'src/main.rs')))
            source = nvim.current.buffer.number
            wait(nvim, '(function() for _,c in ipairs(vim.lsp.get_clients({bufnr=0})) do if c.name=="rust_analyzer" then return true end end return false end)()', 180)
            wait(nvim, 'pcall(vim.treesitter.get_parser,0,"rust")', 180)
            errors = wait(nvim, '(function() local d=vim.diagnostic.get(0,{severity=vim.diagnostic.severity.ERROR}); return #d>0 and d end)()', 120)
            assert nvim.current.buffer.number == source
            print('PASS Rust: first-use installation, same-buffer parser/LSP activation, real type diagnostic', flush=True)
        finally:
            stop(nvim)


def debug_program(language, source):
    with tempfile.TemporaryDirectory(prefix='maya-dap-') as temp:
        path = Path(temp) / ('debug.py' if language == 'python' else 'debug.js')
        path.write_text(source)
        nvim = start()
        try:
            nvim.command('edit ' + nvim.funcs.fnameescape(str(path)))
            nvim.current.window.cursor = (2, 0)
            nvim.exec_lua('require("dap").toggle_breakpoint()')
            config = {'type': 'python' if language == 'python' else 'pwa-node', 'request': 'launch', 'name': 'Maya test', 'program': str(path), 'cwd': temp}
            if language == 'python':
                config.update(pythonPath='/usr/bin/python3', console='internalConsole')
            else:
                config.update(sourceMaps=True, skipFiles=['<node_internals>/**'])
            nvim.exec_lua('require("dap").run(...)', config)
            wait(nvim, '(function() local s=require("dap").session(); return s and s.current_frame and s.current_frame.line==2 end)()', 45)
            nvim.exec_lua('require("dap").step_over()')
            wait(nvim, '(function() local s=require("dap").session(); return s and s.current_frame and s.current_frame.line==3 end)()')
            nvim.exec_lua('require("dap").continue()')
            wait(nvim, 'require("dap").session()==nil')
            print('PASS ' + language + ' debugging: breakpoint, step, continue, termination', flush=True)
        finally:
            stop(nvim)


def ai_suggestions():
    nvim = start()
    try:
        nvim.command('enew')
        nvim.current.buffer[:] = ['def add(a: int, b: int) -> int:', '    ', '', 'print(add(2, 3))']
        nvim.command('setfiletype python')
        nvim.current.window.cursor = (2, 4)
        nvim.exec_lua('require("maya.ai").select("ollama",false)')
        nvim.input('A')
        wait(nvim, 'vim.fn.mode()=="i"')
        nvim.exec_lua('require("minuet.virtualtext").action.next()')
        wait(nvim, 'require("minuet.virtualtext").action.is_visible()', 30)
        nvim.input('\t')
        wait(nvim, r'table.concat(vim.api.nvim_buf_get_lines(0,0,-1,false),"\n"):match("return") ~= nil')
        nvim.input('\x1b')
        nvim.exec_lua('require("maya.ai").select("copilot",false)')
        assert nvim.exec_lua('return require("maya.ai").provider') == 'copilot'
        nvim.exec_lua('require("maya.ai").select("off",false)')
        assert not nvim.exec_lua('return require("maya.ai").accept()')
        print('PASS AI: real Ollama inline completion accepted via Tab; GitHub/off provider switching', flush=True)
    finally:
        stop(nvim)


def folder_sessions():
    # Exercise actual VimEnter/VimLeave sessions in separate processes and cwd.
    old = os.environ.pop('MAYA_NVIM_NO_SESSION', None)
    try:
        with tempfile.TemporaryDirectory(prefix='maya-session-') as temp:
            root = Path(temp)
            first, second = root / 'a.txt', root / 'b.txt'
            first.write_text('a\nb\nc\n'); second.write_text('x\ny\nz\n')
            def launch(directory, args=()):
                argv = ['nvim', '--embed', '--headless', '--cmd', 'cd ' + str(directory), *map(str,args)]
                return pynvim.attach('child', argv=argv)
            nvim = launch(root)
            nvim.command('edit ' + str(first)); nvim.current.window.cursor = (2, 0)
            nvim.command('vsplit ' + str(second)); nvim.current.window.cursor = (3, 0)
            stop(nvim)
            nvim = launch(root)
            try:
                wait(nvim, '#vim.fn.getbufinfo({buflisted=1}) >= 2')
                names = {Path(b.name).name for b in nvim.buffers if b.options['buflisted']}
                assert {'a.txt','b.txt'} <= names, names
                windows = [w for w in nvim.windows if not nvim.api.win_get_config(w.handle)['relative']]
                assert len(windows)==2
                assert {w.cursor[0] for w in windows} == {2,3}
            finally:
                stop(nvim)
            nvim = launch(root, [first])
            try:
                assert Path(nvim.current.buffer.name)==first
                assert len([w for w in nvim.windows if not nvim.api.win_get_config(w.handle)['relative']])==1
                # Keep the previous session intact for this explicit-file test.
                nvim.exec_lua('require("persistence").stop()')
            finally:
                stop(nvim)
            other = root / 'other'; other.mkdir()
            nvim = launch(other)
            try:
                assert not any(b.name in (str(first),str(second)) for b in nvim.buffers)
            finally:
                stop(nvim)
            print('PASS sessions: same-folder buffers/splits/cursors restore; other folder and explicit file stay separate', flush=True)
    finally:
        if old is not None:
            os.environ['MAYA_NVIM_NO_SESSION'] = old


if __name__ == '__main__':
    cpp_project()
    rust_first_use()
    debug_program('python', 'a = 1\nb = a + 2\nprint(b)\n')
    debug_program('javascript', 'const a = 1;\nconst b = a + 2;\nconsole.log(b);\n')
    ai_suggestions()
    folder_sessions()
