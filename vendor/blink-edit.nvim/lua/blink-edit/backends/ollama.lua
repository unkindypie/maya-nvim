--- Ollama backend for blink-edit
--- Uses /api/generate endpoint

local M = {}

local transport = require("blink-edit.transport")
local config = require("blink-edit.config")
local log = require("blink-edit.log")

local warned_override_keys = {}

---@param user_options table
---@param overrides table
local function warn_overridden_options(user_options, overrides)
  for key, _ in pairs(overrides) do
    if user_options[key] ~= nil and not warned_override_keys[key] then
      warned_override_keys[key] = true
      log.debug(string.format("backends.ollama.options.%s is overridden by llm settings", key))
    end
  end
end

---@param opts { prompt: string, model: string, max_tokens: number, temperature: number, stop: string[] }
---@param callback fun(err: { type: string, message: string, code?: number }|nil, result: { text: string, usage: table|nil }|nil)
---@return number request_id
function M.complete(opts, callback)
  local cfg = config.get()
  local ollama_cfg = cfg.backends.ollama or {}
  local user_options = ollama_cfg.options or {}

  local overrides = {
    temperature = opts.temperature or cfg.llm.temperature,
    num_predict = opts.max_tokens or cfg.llm.max_tokens,
    stop = opts.stop or cfg.llm.stop_tokens,
  }

  warn_overridden_options(user_options, overrides)

  local options = vim.tbl_deep_extend("force", user_options, overrides)

  if ollama_cfg.num_ctx then
    options.num_ctx = ollama_cfg.num_ctx
  end
  if ollama_cfg.num_gpu then
    options.num_gpu = ollama_cfg.num_gpu
  end
  if ollama_cfg.num_thread then
    options.num_thread = ollama_cfg.num_thread
  end

  local request_body = {
    model = opts.model or cfg.llm.model,
    prompt = opts.prompt,
    stream = false,
    raw = true,
    options = options,
  }

  local url = cfg.llm.url
  local endpoint = "/api/generate"

  local request_id = transport.request({
    url = url .. endpoint,
    method = "POST",
    headers = {
      ["Content-Type"] = "application/json",
    },
    body = vim.json.encode(request_body),
    timeout = cfg.llm.timeout_ms,
  }, function(err, response)
    if err then
      callback(err, nil)
      return
    end

    local body = response.body
    if type(body) == "string" then
      local ok, decoded = pcall(vim.json.decode, body)
      if not ok then
        callback({ type = "parse", message = "Failed to parse JSON response" }, nil)
        return
      end
      body = decoded
    end

    if body.error then
      local error_msg = body.error.message or vim.inspect(body.error)
      callback({
        type = "server",
        message = "API error: " .. error_msg,
        code = response.status,
      }, nil)
      return
    end

    local text = body.response
    if not text then
      callback({ type = "parse", message = "No response in Ollama payload" }, nil)
      return
    end

    callback(nil, {
      text = text,
      usage = nil,
    })
  end)

  return request_id
end

---@param callback fun(available: boolean, message: string)
function M.health_check(callback)
  local cfg = config.get()
  local endpoint = cfg.backends.ollama.health_endpoint or "/api/tags"

  transport.request({
    url = cfg.llm.url .. endpoint,
    method = "GET",
    timeout = 2000,
  }, function(err, response)
    if err then
      callback(false, "Cannot reach server: " .. err.message)
      return
    end

    if response.status >= 200 and response.status < 300 then
      callback(true, "Server is healthy")
    else
      callback(false, "Server returned status " .. response.status)
    end
  end)
end

return M
