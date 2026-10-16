--- Backend router for blink-edit

local M = {}

local config = require("blink-edit.config")

local backend_cache = {}

---@param name string
---@return table
local function load_backend(name)
  if backend_cache[name] then
    return backend_cache[name]
  end

  local ok, backend = pcall(require, "blink-edit.backends." .. name)
  if not ok or not backend then
    error("[blink-edit] Unknown backend: " .. tostring(name))
  end

  backend_cache[name] = backend
  return backend
end

---@return table
function M.get()
  local cfg = config.get()
  local name = cfg.llm.backend or "openai"
  return load_backend(name)
end

---@param opts table
---@param callback fun(err: { type: string, message: string, code?: number }|nil, result: table|nil)
---@return number request_id
function M.complete(opts, callback)
  return M.get().complete(opts, callback)
end

---@param callback fun(available: boolean, message: string)
function M.health_check(callback)
  return M.get().health_check(callback)
end

return M
