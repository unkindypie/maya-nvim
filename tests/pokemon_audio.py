"""Exercise async cry retrieval and caching without using real speakers."""

from pathlib import Path
import tempfile
import unittest
from integration import start, wait, stop


class PokemonAudioTest(unittest.TestCase):
    def test_dashboard_plays_the_displayed_pokemon(self):
        nvim = start()
        try:
            nvim.exec_lua("""package.loaded["maya.pokemon_audio"] = {
 play=function(quote) played_quote=quote end
}""")
            nvim.ui_attach(110, 35, rgb=True)
            nvim.exec_lua("Snacks.dashboard()")
            wait(nvim, "played_quote ~= nil")
            self.assertTrue(
                nvim.exec_lua(
                    "return Snacks.config.dashboard.preset.header:find(played_quote, 1, true) ~= nil"
                )
            )
        finally:
            stop(nvim)

    def test_async_matching_cache_and_failure(self):
        with tempfile.TemporaryDirectory(prefix="maya-cries-") as temp:
            nvim = start()
            try:
                nvim.exec_lua(
                    """
local cache = ...
local original_stdpath = vim.fn.stdpath
vim.fn.stdpath = function(key) return key == "cache" and cache or original_stdpath(key) end
vim.api.nvim_list_uis = function() return {{}} end
vim.fn.executable = function(command) return (command == "mpv" or command == "curl") and 1 or 0 end
calls = {}
vim.system = function(args, opts, callback)
  calls[#calls + 1] = args
  vim.defer_fn(function()
    if args[1] == "mpv" then callback({code=0}); return end
    local output
    for i,arg in ipairs(args) do if arg == "--output" then output=args[i+1] end end
    if output then vim.fn.writefile({"fake cry"}, output) end
    callback({code=0, stdout=output and "" or vim.json.encode({cries={latest="https://raw.githubusercontent.com/PokeAPI/cries/main/cries/pokemon/latest/25.ogg"}})})
  end, 50)
  return {kill=function() end}
end
local audio=require("maya.pokemon_audio")
audio.play("Pika-pika! Chu! - Pikachu (c)")
assert(#calls == 1, "must return before async download finishes")
assert(calls[1][#calls[1]] == "https://pokeapi.co/api/v2/pokemon/pikachu/")
audio.play("Eevee! Vee! - Eevee (c)")
assert(#calls == 1, "only one sound per launch")
""",
                    temp,
                )
                wait(nvim, "#calls == 3")
                self.assertEqual(nvim.exec_lua("return calls[3][1]"), "mpv")
                self.assertTrue(
                    nvim.exec_lua('return vim.tbl_contains(calls[3], "--volume=50")')
                )
                self.assertEqual(
                    nvim.exec_lua("return calls[3][#calls[3]]"),
                    str(Path(temp) / "pokemon-cries/pikachu.ogg"),
                )
                nvim.exec_lua("""
package.loaded["maya.pokemon_audio"] = nil
calls = {}
require("maya.pokemon_audio").play("Pika-pika! Chu! - Pikachu (c)")
assert(#calls == 1 and calls[1][1] == "mpv", "cache must bypass API")
""")
                nvim.exec_lua("""
require("maya.user").config.pokemon_sound_on_start_volume_percentage = 25
for executable, argument in pairs({mpv="--volume=25", ffplay="25", ["pw-play"]="--volume=0.25", paplay="--volume=16384"}) do
  package.loaded["maya.pokemon_audio"] = nil
  calls = {}
  vim.fn.executable = function(command) return command == executable and 1 or 0 end
  require("maya.pokemon_audio").play("Pika-pika! Chu! - Pikachu (c)")
  assert(#calls == 1 and calls[1][1] == executable)
  assert(vim.tbl_contains(calls[1], argument), vim.inspect(calls))
end
package.loaded["maya.pokemon_audio"] = nil
calls = {}
require("maya.user").config.pokemon_sound_on_start_volume_percentage = 0
require("maya.pokemon_audio").play("Pika-pika! Chu! - Pikachu (c)")
assert(#calls == 0, "zero volume must skip playback")
require("maya.user").config.pokemon_sound_on_start_volume_percentage = 50
vim.fn.executable = function(command) return (command == "mpv" or command == "curl") and 1 or 0 end
""")
                nvim.exec_lua("""
package.loaded["maya.pokemon_audio"] = nil
calls = {}
vim.system = function(args, opts, callback)
 calls[#calls+1] = args
 vim.schedule(function() callback({code=22, stdout=""}) end)
 return {kill=function() end}
end
require("maya.pokemon_audio").play("Eevee! Vee! - Eevee (c)")
""")
                wait(nvim, "#calls == 1")
                nvim.exec_lua("""
package.loaded["maya.pokemon_audio"] = nil
vim.g.maya_pokemon_sound = false
calls = {}
require("maya.pokemon_audio").play("Eevee! Vee! - Eevee (c)")
assert(#calls == 0)
""")
            finally:
                stop(nvim)


if __name__ == "__main__":
    unittest.main()
