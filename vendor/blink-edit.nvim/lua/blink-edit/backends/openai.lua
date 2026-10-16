--- OpenAI-compatible backend for blink-edit
--- Supports llama.cpp, vLLM, LocalAI, and any OpenAI-compatible server

local M = {}

local transport = require("blink-edit.transport")
local config = require("blink-edit.config")

---@class OpenAICompletionRequest
---@field prompt string
---@field model string
---@field max_tokens number
---@field temperature number
---@field stop string[]

---@class OpenAICompletionResult
---@field text string Generated completion text
---@field usage { prompt_tokens: number, completion_tokens: number, total_tokens: number }|nil

--- Send a completion request to the OpenAI-compatible API
---@param opts OpenAICompletionRequest
---@param callback fun(err: { type: string, message: string, code?: number }|nil, result: OpenAICompletionResult|nil)
---@return number request_id for cancellation
function M.complete(opts, callback)
  local cfg = config.get()

  local request_body = {
    model = opts.model or cfg.llm.model,
    prompt = opts.prompt,
    max_tokens = opts.max_tokens or cfg.llm.max_tokens,
    temperature = opts.temperature or cfg.llm.temperature,
    stop = opts.stop or cfg.llm.stop_tokens,
  }

  local url = cfg.llm.url
  local endpoint = "/v1/completions"

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

    -- Parse response
    local body = response.body
    if type(body) == "string" then
      local ok, decoded = pcall(vim.json.decode, body)
      if not ok then
        callback({ type = "parse", message = "Failed to parse JSON response" }, nil)
        return
      end
      body = decoded
    end

    -- Check for API errors
    if body.error then
      local error_msg = body.error.message or vim.inspect(body.error)
      callback({
        type = "server",
        message = "API error: " .. error_msg,
        code = response.status,
      }, nil)
      return
    end

    -- Extract completion text
    if not body.choices or #body.choices == 0 then
      callback({ type = "parse", message = "No choices in response" }, nil)
      return
    end

    local text = body.choices[1].text
    if not text then
      callback({ type = "parse", message = "No text in response choice" }, nil)
      return
    end

    callback(nil, {
      text = text,
      usage = body.usage,
    })
  end)

  return request_id
end

--- Check if the backend is available (health check)
---@param callback fun(available: boolean, message: string)
function M.health_check(callback)
  local cfg = config.get()
  local endpoint = cfg.backends.openai.health_endpoint or "/health"

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
