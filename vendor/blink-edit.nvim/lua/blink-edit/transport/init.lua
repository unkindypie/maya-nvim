--- Transport router
--- Selects the appropriate transport based on URL and configuration

local M = {}

local tcp = require("blink-edit.transport.tcp")
local curl = require("blink-edit.transport.curl")

--- Check if daemon is available
---@return boolean
local function daemon_available()
  -- TODO: Implement daemon detection in Phase 5
  return false
end

--- Determine which transport to use based on URL and config
---@param url string
---@return "tcp"|"curl"|"daemon"
local function select_transport(url)
  local config = require("blink-edit.config").get()

  -- Check for daemon mode (Phase 5)
  if config.use_daemon then
    if daemon_available() then
      return "daemon"
    elseif not config.fallback_to_direct then
      -- Daemon required but not available, and no fallback
      return "daemon" -- Will error
    end
    -- Fallback to direct connection
  end

  -- Check URL protocol
  if url:match("^https://") then
    return "curl" -- HTTPS requires curl for TLS
  else
    return "tcp" -- HTTP can use fast TCP path
  end
end

--- Get the transport module for a given type
---@param transport_type "tcp"|"curl"|"daemon"
---@return table
local function get_transport_module(transport_type)
  if transport_type == "tcp" then
    return tcp
  elseif transport_type == "curl" then
    return curl
  elseif transport_type == "daemon" then
    -- TODO: Implement daemon transport in Phase 5
    error("Daemon transport not yet implemented")
  else
    error("Unknown transport type: " .. tostring(transport_type))
  end
end

--- Make an HTTP request using the appropriate transport
---@param opts { url: string, method?: string, headers?: table<string, string>, body?: string, timeout?: number }
---@param callback fun(err: { type: string, message: string }|nil, response: { status: number, headers: table, body: string }|nil)
---@return number request_id for cancellation
function M.request(opts, callback)
  local transport_type = select_transport(opts.url)
  local transport = get_transport_module(transport_type)

  -- Add default timeout from config if not specified
  if not opts.timeout then
    local config = require("blink-edit.config").get()
    opts.timeout = config.llm.timeout_ms
  end

  return transport.request(opts, callback)
end

--- Cancel an active request by ID (TCP only)
---@param request_id number
---@return boolean cancelled
function M.cancel(request_id)
  return tcp.cancel(request_id)
end

--- Close all pooled connections
function M.close_all()
  tcp.close_all()
end

return M
