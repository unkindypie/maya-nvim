"""Exercise personal overrides through real Neovim startup, reusing installed plugins."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class UserConfigTest(unittest.TestCase):
    def test_simple_preferences(self):
        self.launch(
            "return {pokemon_sound_on_start=false,reopen_tabs=false}",
            """
assert(require("maya.user").get("pokemon_sound_on_start")==false)
assert(require("maya.user").get("reopen_tabs")==false)
""",
        )
        self.launch(
            "return {}",
            """
assert(require("maya.user").get("pokemon_sound_on_start")==true)
assert(require("maya.user").get("reopen_tabs")==true)
""",
        )

    def test_theme_selection_and_options(self):
        self.launch(
            "return {}",
            'assert(vim.g.colors_name=="catppuccin-frappe"); assert(require("lazy.core.config").plugins["tokyonight.nvim"]==nil); assert(require("lazy.core.config").plugins["kanagawa.nvim"]==nil)',
        )
        self.launch(
            'return {theme="catppuccin/nvim"}',
            'assert(vim.g.colors_name=="catppuccin-frappe")',
        )
        self.launch('return {theme="habamax"}', 'assert(vim.g.colors_name=="habamax")')
        self.assertTrue(
            self.launch(
                'return {theme={name="catppuccin-mocha",opts={transparent_background=false}}}',
                'assert(vim.g.colors_name=="catppuccin-mocha"); assert(vim.api.nvim_get_hl(0,{name="Normal",link=false}).bg ~= nil)',
            )
        )
        self.assertTrue(
            self.launch(
                'return {theme="folke/tokyonight.nvim"}',
                'assert(vim.g.colors_name:match("^tokyonight")); assert(require("lazy.core.config").plugins["tokyonight.nvim"])',
            )
        )
        self.assertTrue(
            self.launch(
                'return {theme={name="kanagawa-wave",plugin="rebelot/kanagawa.nvim",module="kanagawa",opts={transparent=true}}}',
                'assert(vim.g.colors_name=="kanagawa"); assert(vim.api.nvim_get_hl(0,{name="Normal",link=false}).bg == nil)',
            )
        )
        self.launch(
            "return {theme={opts={}}}",
            'assert(require("maya.user").get("theme")=="catppuccin/nvim")',
        )
        self.launch(
            'return {theme="missing-theme-for-test"}',
            'assert(vim.g.colors_name:match("^catppuccin"))',
        )

    def test_sound_volume(self):
        self.launch(
            "return {pokemon_sound_on_start_volume_percentage=25}",
            'assert(require("maya.user").get("pokemon_sound_on_start_volume_percentage")==25)',
        )
        self.launch(
            "return {}",
            'assert(require("maya.user").get("pokemon_sound_on_start_volume_percentage")==50)',
        )
        for value in ["-1", "101", "0/0", '"loud"']:
            self.launch(
                "return {pokemon_sound_on_start_volume_percentage=" + value + "}",
                'assert(require("maya.user").get("pokemon_sound_on_start_volume_percentage")==50)',
            )

    def launch(self, config, assertions, modules=None):
        with tempfile.TemporaryDirectory(prefix="maya personal config ") as temp:
            root = Path(temp)
            (root / "maya-nvim").symlink_to(ROOT)
            personal = root / "mvim"
            personal.mkdir()
            if config is not None:
                (personal / "init.lua").write_text(config)
            for name, content in (modules or {}).items():
                file = personal / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(content)
            env = dict(
                os.environ,
                NVIM_APPNAME="maya-nvim",
                XDG_CONFIG_HOME=temp,
                XDG_STATE_HOME=str(root / "state"),
                MAYA_NVIM_NO_INSTALL="1",
                MAYA_NVIM_NO_AI="1",
                MAYA_NVIM_NO_SESSION="1",
            )
            script = root / "check.lua"
            script.write_text(
                "local ok,err=pcall(function()\n" + assertions + "\nend)\n"
                'if not ok then io.stderr:write(tostring(err)); vim.cmd("cquit 1") end\n'
            )
            # --cmd is run before init; the assertion file runs afterwards.
            result = subprocess.run(
                ["nvim", "--headless", "+lua dofile(vim.env.MAYA_USER_CHECK)", "+qa!"],
                env=dict(env, MAYA_USER_CHECK=str(script)),
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return (personal / "lazy-lock.json").exists()

    def test_options_setup_plugins_modules_and_runtime(self):
        config = """return {
 options={number=false,scrolloff=3},
 plugins={
  {"folke/snacks.nvim",opts={dashboard={preset={header="Personal dashboard"}}}},
  {"akinsho/bufferline.nvim",enabled=false},
  {"catppuccin/nvim",name="catppuccin",opts={transparent_background=false}},
 },
 setup=function()
  vim.g.personal_value=require("mvim.sample")
  vim.keymap.set("n","<leader>w","<cmd>echo 'personal'<cr>",{desc="Personal save"})
 end,
}"""
        self.assertTrue(
            self.launch(
                config,
                """
assert(vim.o.number==false)
assert(vim.o.scrolloff==3)
assert(vim.g.personal_value==42)
assert(vim.fn.maparg(" w","n"):match("personal"))
assert(Snacks.config.dashboard.preset.header=="Personal dashboard")
assert(require("catppuccin").options.transparent_background==false)
assert(require("lazy.core.config").plugins["bufferline.nvim"]==nil)
assert(require("lazy.core.config").options.lockfile==require("maya.user").path.."/lazy-lock.json")
vim.cmd("enew")
vim.cmd("setfiletype lua")
assert(vim.b.personal_ftplugin==true)
""",
                {
                    "lua/mvim/sample.lua": "return 42",
                    "after/ftplugin/lua.lua": "vim.b.personal_ftplugin=true",
                },
            )
        )

    def test_imported_personal_plugin(self):
        self.assertTrue(
            self.launch(
                'return {plugins={{import="mvim.plugins"}}}',
                "assert(vim.g.personal_plugin_loaded==true)",
                {
                    "lua/mvim/plugins/local.lua": """return {
 dir=vim.env.XDG_CONFIG_HOME.."/mvim/local-plugin",
 name="personal-test-plugin",
 config=function() require("personal_test").setup() end,
}""",
                    "local-plugin/lua/personal_test/init.lua": "return {setup=function() vim.g.personal_plugin_loaded=true end}",
                },
            )
        )

    def test_no_overrides_keeps_managed_lock(self):
        self.assertFalse(
            self.launch(
                None,
                """
assert(vim.o.number==true)
assert(require("lazy.core.config").options.lockfile==vim.fn.stdpath("config").."/lazy-lock.json")
""",
            )
        )

    def test_invalid_file_preserves_defaults(self):
        self.launch("this is invalid Lua!", "assert(vim.o.number==true)")
        self.launch('return {options="invalid"}', "assert(vim.o.number==true)")

    def test_setup_failure_and_invalid_option_do_not_stop_startup(self):
        self.launch(
            'return {options={number=false,not_a_real_option=1},setup=function() error("test error") end}',
            'assert(vim.o.number==false); assert(vim.fn.maparg(" f","n")~="")',
        )


if __name__ == "__main__":
    unittest.main()
