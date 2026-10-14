local bank = require("maya.pokemon")
local M = { quote = bank[(vim.uv.hrtime() % #bank) + 1] }
local notified = false

function M.greet(notification)
  if notification and not notified then
    notified = true
    vim.notify(M.quote, vim.log.levels.INFO, { title = "Pokémon" })
  end
  require("maya.pokemon_audio").play(M.quote)
end

return M
