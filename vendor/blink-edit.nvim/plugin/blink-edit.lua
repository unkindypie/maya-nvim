-- Auto-register commands without requiring setup()

if vim.g.loaded_blink_edit then
  return
end
vim.g.loaded_blink_edit = true

local log = require("blink-edit.log")

-- Minimum Neovim version check
if vim.fn.has("nvim-0.9") ~= 1 then
  log.error("Requires Neovim 0.9+")
  return
end

vim.api.nvim_create_user_command("BlinkEditStatus", function()
  local ok, blink = pcall(require, "blink-edit")
  if ok and blink._is_initialized and blink._is_initialized() then
    require("blink-edit.ui").status()
  else
    log.warn("Run setup() first, then use :BlinkEditStatus")
  end
end, { desc = "Show blink-edit status and health" })

vim.api.nvim_create_user_command("BlinkEditEnable", function()
  vim.g.blink_edit_enabled = true
  log.info("Enabled")
end, { desc = "Enable blink-edit predictions" })

vim.api.nvim_create_user_command("BlinkEditDisable", function()
  vim.g.blink_edit_enabled = false
  log.info("Disabled")
end, { desc = "Disable blink-edit predictions" })

vim.api.nvim_create_user_command("BlinkEditToggle", function()
  vim.g.blink_edit_enabled = not (vim.g.blink_edit_enabled == true)
  local status = vim.g.blink_edit_enabled and "Enabled" or "Disabled"
  log.info(status)
end, { desc = "Toggle blink-edit predictions" })
