"""Restore actual folder sessions and capture the startup notification."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SessionPreferencesTest(unittest.TestCase):
    def test_restoration_notification_and_disabled_preference(self):
        with tempfile.TemporaryDirectory(prefix='maya-session-preferences-') as temp:
            root = Path(temp)
            config = root / 'config'
            config.mkdir()
            (config / 'maya-nvim').symlink_to(ROOT)
            (config / 'mvim').mkdir()
            personal = config / 'mvim/init.lua'
            personal.write_text('return {pokemon_sound_on_start=false,reopen_tabs=true}')
            first, second = root / 'a.txt', root / 'b.txt'
            first.write_text('first\n')
            second.write_text('second\n')
            env = dict(os.environ, NVIM_APPNAME='maya-nvim', XDG_CONFIG_HOME=str(config),
                       XDG_STATE_HOME=str(root / 'state'), MAYA_NVIM_NO_INSTALL='1',
                       MAYA_NVIM_NO_AI='1', MAYA_NVIM_NO_SOUND='1')
            env.pop('MAYA_NVIM_NO_SESSION', None)

            def launch(args):
                result = subprocess.run(['nvim', '--headless', *args], cwd=root,
                                        env=env, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            launch(['+edit ' + str(first), '+tabedit ' + str(second), '+qa'])
            capture = '''lua vim.api.nvim_create_autocmd("User", {
pattern="PersistenceLoadPost", callback=function()
vim.notify=function(message, level, opts) vim.g.greeting=message; vim.g.greeting_title=opts.title end
end})'''
            script = root / 'check.lua'
            script.write_text('''
local ok, err = pcall(function()
 assert(vim.wait(3000, function() return vim.g.greeting ~= nil end))
 assert(#vim.api.nvim_list_tabpages() == 2)
 assert(vim.g.greeting == require("maya.pokemon_startup").quote)
 assert(Snacks.config.dashboard.preset.header:find(vim.g.greeting, 1, true))
 assert(vim.g.greeting_title == "Pokémon")
 require("persistence").stop()
end)
if not ok then io.stderr:write(tostring(err)); vim.cmd("cquit 1") end
''')
            launch(['--cmd', capture, '--cmd',
                    'lua vim.api.nvim_create_autocmd("VimEnter", {once=true, callback=function() '
                    'vim.defer_fn(function() local ok,err=pcall(dofile,' + repr(str(script)) + '); '
                    'if not ok then io.stderr:write(tostring(err)); vim.cmd("cquit 1") end; '
                    'vim.cmd("qa!") end,100) end})'])
            personal.write_text('return {pokemon_sound_on_start=false,reopen_tabs=false}')
            script.write_text('''
vim.wait(200)
assert(#vim.api.nvim_list_tabpages() == 1)
assert(vim.g.greeting == nil)
assert(vim.api.nvim_buf_get_name(0) == "")
require("persistence").stop()
''')
            launch(['--cmd', capture, '--cmd',
                    'lua vim.api.nvim_create_autocmd("VimEnter", {once=true, callback=function() '
                    'vim.defer_fn(function() local ok,err=pcall(dofile,' + repr(str(script)) + '); '
                    'if not ok then io.stderr:write(tostring(err)); vim.cmd("cquit 1") end; '
                    'vim.cmd("qa!") end,100) end})'])
