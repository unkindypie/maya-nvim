--- Logging utilities for blink-edit
--- Centralizes debug/info/warn/error notifications with debounce

local M = {}

local uv = vim.uv or vim.loop

-- Debounce state for error notifications
local last_error_time = 0
local ERROR_DEBOUNCE_MS = 5000

local function notify(msg, level)
  vim.schedule(function()
    vim.notify("[blink-edit] " .. msg, level)
  end)
end

---@param msg string
---@param level? number
function M.debug(msg, level)
  if vim.g.blink_edit_debug then
    notify(msg, level or vim.log.levels.DEBUG)
    vim.schedule(function()
      pcall(vim.api.nvim_echo, { { "[blink-edit] " .. msg } }, true, {})
    end)
  end
end

---@param msg string
---@param level? number
function M.debug2(msg, level)
  if vim.g.blink_edit_debug and vim.g.blink_edit_debug >= 2 then
    M.debug(msg, level)
  end
end

---@param msg string
function M.info(msg)
  notify(msg, vim.log.levels.INFO)
end

---@param msg string
function M.warn(msg)
  notify(msg, vim.log.levels.WARN)
end

---@param msg string
---@param debounce? boolean
function M.error(msg, debounce)
  if debounce == nil then
    debounce = true
  end

  local now = uv.now()
  if debounce and (now - last_error_time) < ERROR_DEBOUNCE_MS then
    return
  end
  last_error_time = now

  notify(msg, vim.log.levels.ERROR)
end

return M
