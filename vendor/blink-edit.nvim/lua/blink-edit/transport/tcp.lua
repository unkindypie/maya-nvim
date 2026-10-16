--- TCP transport with keep-alive connection pooling
--- Uses vim.uv for raw socket connections (fast path for http://)

local M = {}

local uv = vim.uv or vim.loop
local log = require("blink-edit.log")

---@class ConnectionEntry
---@field socket userdata
---@field state "idle"|"busy"|"closed"
---@field last_used number
---@field host string
---@field port number

---@class ConnectionPool
---@field connections table<string, ConnectionEntry>
---@field idle_timeout number
local pool = {
  connections = {},
  idle_timeout = 30000, -- 30 seconds
}

---@class ActiveRequest
---@field socket userdata
---@field host string
---@field port number
---@field timer userdata|nil
---@field cancelled boolean

---@type table<number, ActiveRequest>
local active_requests = {}

---@type number
local request_id_counter = 0

--- Parse URL into components
---@param url string
---@return { protocol: string, host: string, port: number, path: string }|nil
local function parse_url(url)
  local protocol, rest = url:match("^(https?)://(.+)$")
  if not protocol then
    return nil
  end

  local host_port, path = rest:match("^([^/]+)(/.*)$")
  if not host_port then
    host_port = rest
    path = "/"
  end

  local host, port = host_port:match("^([^:]+):(%d+)$")
  if not host then
    host = host_port
    port = protocol == "https" and 443 or 80
  else
    port = tonumber(port)
  end

  return {
    protocol = protocol,
    host = host,
    port = port,
    path = path,
  }
end

--- Get pool key for a host:port combination
---@param host string
---@param port number
---@return string
local function get_pool_key(host, port)
  return string.format("%s:%d", host, port)
end

--- Create a new TCP connection
---@param host string
---@param port number
---@param callback fun(err: string|nil, socket: userdata|nil)
local function create_connection(host, port, callback)
  local socket = uv.new_tcp()
  if not socket then
    callback("Failed to create TCP socket", nil)
    return
  end

  -- Resolve hostname and connect
  uv.getaddrinfo(host, nil, { family = "inet" }, function(err, res)
    if err then
      socket:close()
      vim.schedule(function()
        callback("DNS resolution failed: " .. err, nil)
      end)
      return
    end

    if not res or #res == 0 then
      socket:close()
      vim.schedule(function()
        callback("DNS resolution failed: no results", nil)
      end)
      return
    end

    local addr = res[1].addr

    socket:connect(addr, port, function(connect_err)
      if connect_err then
        socket:close()
        vim.schedule(function()
          callback("Connection failed: " .. connect_err, nil)
        end)
        return
      end

      vim.schedule(function()
        callback(nil, socket)
      end)
    end)
  end)
end

--- Get an idle connection from the pool or create a new one
---@param host string
---@param port number
---@param force_new boolean Force create a new connection (skip pool)
---@param callback fun(err: string|nil, socket: userdata|nil, is_reused: boolean)
local function get_connection(host, port, force_new, callback)
  local key = get_pool_key(host, port)
  local entry = pool.connections[key]

  -- Check if we have an idle connection (unless force_new)
  if not force_new and entry and entry.state == "idle" then
    local now = uv.now()
    -- Check if connection is still fresh
    if now - entry.last_used < pool.idle_timeout then
      entry.state = "busy"
      callback(nil, entry.socket, true)
      return
    else
      -- Connection is stale, close it
      if not entry.socket:is_closing() then
        entry.socket:close()
      end
      pool.connections[key] = nil
    end
  end

  -- Close existing connection if forcing new
  if force_new and entry then
    if entry.socket and not entry.socket:is_closing() then
      entry.socket:close()
    end
    pool.connections[key] = nil
  end

  -- Create new connection
  create_connection(host, port, function(err, socket)
    if err then
      callback(err, nil, false)
      return
    end

    -- Store in pool
    pool.connections[key] = {
      socket = socket,
      state = "busy",
      last_used = uv.now(),
      host = host,
      port = port,
    }

    callback(nil, socket, false)
  end)
end

--- Return a connection to the pool (mark as idle)
---@param host string
---@param port number
local function return_connection(host, port)
  local key = get_pool_key(host, port)
  local entry = pool.connections[key]
  if entry and entry.state == "busy" then
    entry.state = "idle"
    entry.last_used = uv.now()
  end
end

--- Close and remove a connection from the pool
---@param host string
---@param port number
local function close_connection(host, port)
  local key = get_pool_key(host, port)
  local entry = pool.connections[key]
  if entry then
    if entry.socket and not entry.socket:is_closing() then
      entry.socket:close()
    end
    pool.connections[key] = nil
  end
end

--- Build HTTP/1.1 request string
---@param opts { method: string, path: string, host: string, headers: table<string, string>, body: string }
---@return string
local function build_http_request(opts)
  local method = opts.method or "GET"
  local path = opts.path or "/"
  local host = opts.host
  local body = opts.body or ""

  local headers = {
    string.format("%s %s HTTP/1.1", method, path),
    string.format("Host: %s", host),
    "Connection: keep-alive",
  }

  -- Add custom headers
  if opts.headers then
    for key, value in pairs(opts.headers) do
      table.insert(headers, string.format("%s: %s", key, value))
    end
  end

  -- Add content-length for body
  if #body > 0 then
    table.insert(headers, string.format("Content-Length: %d", #body))
  end

  -- End headers and add body
  table.insert(headers, "")
  table.insert(headers, body)

  return table.concat(headers, "\r\n")
end

--- Parse HTTP response
---@param data string
---@return { status: number, headers: table<string, string>, body: string, complete: boolean, headers_end: number|nil }
local function parse_http_response(data)
  local result = {
    status = 0,
    headers = {},
    body = "",
    complete = false,
    headers_end = nil,
  }

  -- Find end of headers
  local headers_end = data:find("\r\n\r\n")
  if not headers_end then
    return result
  end

  result.headers_end = headers_end + 4

  -- Parse status line
  local status_line = data:match("^HTTP/1%.%d (%d+)")
  if status_line then
    result.status = tonumber(status_line)
  end

  -- Parse headers
  local header_section = data:sub(1, headers_end - 1)
  for line in header_section:gmatch("[^\r\n]+") do
    local key, value = line:match("^([^:]+):%s*(.+)$")
    if key then
      result.headers[key:lower()] = value
    end
  end

  -- Extract body
  local body_start = headers_end + 4
  local body = data:sub(body_start)

  -- Check content-length
  local content_length = result.headers["content-length"]
  if content_length then
    content_length = tonumber(content_length)
    if #body >= content_length then
      result.body = body:sub(1, content_length)
      result.complete = true
    else
      result.body = body
    end
  else
    -- Check for chunked encoding
    local transfer_encoding = result.headers["transfer-encoding"]
    if transfer_encoding and transfer_encoding:lower():find("chunked") then
      -- Parse chunked encoding
      local decoded_body = ""
      local chunk_data = body
      local all_chunks_received = false

      while true do
        -- Find chunk size line
        local chunk_size_end = chunk_data:find("\r\n")
        if not chunk_size_end then
          break
        end

        local chunk_size_hex = chunk_data:sub(1, chunk_size_end - 1)
        local chunk_size = tonumber(chunk_size_hex, 16)

        if not chunk_size then
          break
        end

        if chunk_size == 0 then
          all_chunks_received = true
          break
        end

        local chunk_start = chunk_size_end + 2
        local chunk_end = chunk_start + chunk_size - 1

        if chunk_end > #chunk_data then
          -- Not all chunk data received yet
          break
        end

        decoded_body = decoded_body .. chunk_data:sub(chunk_start, chunk_end)

        -- Move past chunk and trailing \r\n
        chunk_data = chunk_data:sub(chunk_end + 3)
      end

      result.body = decoded_body
      result.complete = all_chunks_received
    else
      -- No content-length or chunked encoding, assume complete
      result.body = body
      result.complete = true
    end
  end

  return result
end

--- Internal function to perform the actual HTTP request
---@param opts { url: string, method?: string, headers?: table<string, string>, body?: string, timeout?: number, request_id?: number }
---@param url_parts { protocol: string, host: string, port: number, path: string }
---@param force_new_connection boolean
---@param callback fun(err: { type: string, message: string }|nil, response: { status: number, headers: table, body: string }|nil, should_retry: boolean)
---@return number request_id
local function do_request(opts, url_parts, force_new_connection, callback)
  local timeout = opts.timeout or 5000
  local timeout_timer = nil
  local request_completed = false

  -- Generate request ID
  request_id_counter = request_id_counter + 1
  local request_id = opts.request_id or request_id_counter

  -- Get or create connection
  get_connection(url_parts.host, url_parts.port, force_new_connection, function(conn_err, socket, is_reused)
    if conn_err then
      active_requests[request_id] = nil
      vim.schedule(function()
        callback({ type = "connection_error", message = conn_err }, nil, false)
      end)
      return
    end

    -- Track this active request
    active_requests[request_id] = {
      socket = socket,
      host = url_parts.host,
      port = url_parts.port,
      timer = nil,
      cancelled = false,
    }

    -- Set up timeout
    timeout_timer = uv.new_timer()
    active_requests[request_id].timer = timeout_timer
    timeout_timer:start(timeout, 0, function()
      if not request_completed then
        request_completed = true
        timeout_timer:stop()
        timeout_timer:close()
        active_requests[request_id] = nil
        close_connection(url_parts.host, url_parts.port)
        vim.schedule(function()
          callback({ type = "timeout", message = "Request timed out after " .. timeout .. "ms" }, nil, false)
        end)
      end
    end)

    -- Build and send request
    local http_request = build_http_request({
      method = opts.method or "POST",
      path = url_parts.path,
      host = url_parts.host,
      headers = opts.headers,
      body = opts.body or "",
    })

    socket:write(http_request, function(write_err)
      if write_err then
        if not request_completed then
          request_completed = true
          if timeout_timer then
            timeout_timer:stop()
            timeout_timer:close()
          end
          active_requests[request_id] = nil
          close_connection(url_parts.host, url_parts.port)
          vim.schedule(function()
            -- If this was a reused connection, we should retry with a new one
            local should_retry = is_reused
            callback({ type = "write_error", message = write_err }, nil, should_retry)
          end)
        end
        return
      end
    end)

    -- Read response
    local response_data = ""
    local received_any_data = false

    socket:read_start(function(read_err, chunk)
      if request_completed then
        return
      end

      -- Check if cancelled
      local active = active_requests[request_id]
      if active and active.cancelled then
        request_completed = true
        if timeout_timer then
          timeout_timer:stop()
          timeout_timer:close()
        end
        socket:read_stop()
        active_requests[request_id] = nil
        close_connection(url_parts.host, url_parts.port)
        vim.schedule(function()
          callback({ type = "cancelled", message = "Request cancelled" }, nil, false)
        end)
        return
      end

      if read_err then
        request_completed = true
        if timeout_timer then
          timeout_timer:stop()
          timeout_timer:close()
        end
        socket:read_stop()
        active_requests[request_id] = nil
        close_connection(url_parts.host, url_parts.port)
        vim.schedule(function()
          -- If this was a reused connection and we got an error, retry
          local should_retry = is_reused and not received_any_data
          callback({ type = "read_error", message = read_err }, nil, should_retry)
        end)
        return
      end

      if chunk then
        received_any_data = true
        response_data = response_data .. chunk

        -- Try to parse response
        local parsed = parse_http_response(response_data)
        if parsed.complete then
          request_completed = true
          if timeout_timer then
            timeout_timer:stop()
            timeout_timer:close()
          end
          socket:read_stop()
          active_requests[request_id] = nil

          -- Return connection to pool for reuse
          return_connection(url_parts.host, url_parts.port)

          -- Parse JSON body if applicable
          local body = parsed.body
          local json_body = nil

          if parsed.headers["content-type"] and parsed.headers["content-type"]:find("application/json") then
            local ok, decoded = pcall(vim.json.decode, body)
            if ok then
              json_body = decoded
            end
          end

          vim.schedule(function()
            callback(nil, {
              status = parsed.status,
              headers = parsed.headers,
              body = json_body or body,
            }, false)
          end)
        end
      else
        -- EOF - connection closed by server
        if not request_completed then
          request_completed = true
          if timeout_timer then
            timeout_timer:stop()
            timeout_timer:close()
          end
          socket:read_stop()
          active_requests[request_id] = nil
          close_connection(url_parts.host, url_parts.port)

          -- If we got EOF without receiving any data on a reused connection,
          -- the server likely closed the connection. Retry with a new one.
          if is_reused and not received_any_data then
            vim.schedule(function()
              callback({ type = "connection_closed", message = "Connection closed by server" }, nil, true)
            end)
            return
          end

          -- Try to parse what we have
          local parsed = parse_http_response(response_data)
          if parsed.status > 0 then
            vim.schedule(function()
              callback(nil, {
                status = parsed.status,
                headers = parsed.headers,
                body = parsed.body,
              }, false)
            end)
          else
            vim.schedule(function()
              callback({ type = "connection_closed", message = "Connection closed unexpectedly" }, nil, false)
            end)
          end
        end
      end
    end)
  end)

  return request_id
end

--- Make an HTTP request over TCP (with automatic retry for dead pooled connections)
---@param opts { url: string, method?: string, headers?: table<string, string>, body?: string, timeout?: number }
---@param callback fun(err: { type: string, message: string }|nil, response: { status: number, headers: table, body: string }|nil)
---@return number request_id for cancellation
function M.request(opts, callback)
  local url_parts = parse_url(opts.url)
  if not url_parts then
    vim.schedule(function()
      callback({ type = "invalid_url", message = "Invalid URL: " .. opts.url }, nil)
    end)
    return 0
  end

  if url_parts.protocol == "https" then
    vim.schedule(function()
      callback({ type = "https_not_supported", message = "HTTPS not supported by TCP transport, use curl" }, nil)
    end)
    return 0
  end

  -- Generate request ID upfront so we can return it
  request_id_counter = request_id_counter + 1
  local request_id = request_id_counter

  -- First attempt - may use pooled connection
  do_request(
    vim.tbl_extend("force", opts, { request_id = request_id }),
    url_parts,
    false,
    function(err, response, should_retry)
      if err and should_retry then
        -- Retry with a fresh connection
        if vim.g.blink_edit_debug then
          log.debug("Retrying with fresh connection: " .. err.message)
        end
        do_request(
          vim.tbl_extend("force", opts, { request_id = request_id }),
          url_parts,
          true,
          function(retry_err, retry_response, _)
            if retry_err and retry_err.type ~= "cancelled" then
              log.error(retry_err.message)
            end
            callback(retry_err, retry_response)
          end
        )
      else
        if err and err.type ~= "cancelled" then
          log.error(err.message)
        end
        callback(err, response)
      end
    end
  )

  return request_id
end

--- Cancel an active request by ID
---@param request_id number
---@return boolean cancelled True if request was found and cancelled
function M.cancel(request_id)
  local active = active_requests[request_id]
  if not active then
    return false
  end

  -- Mark as cancelled
  active.cancelled = true

  -- Stop the timeout timer
  if active.timer and not active.timer:is_closing() then
    active.timer:stop()
    active.timer:close()
  end

  -- Close the socket immediately to stop receiving data
  if active.socket and not active.socket:is_closing() then
    active.socket:read_stop()
    active.socket:close()
  end

  -- Remove from pool
  close_connection(active.host, active.port)

  -- Clean up tracking
  active_requests[request_id] = nil

  if vim.g.blink_edit_debug then
    log.debug(string.format("Cancelled request %d", request_id))
  end

  return true
end

--- Check if a request is active
---@param request_id number
---@return boolean
function M.is_active(request_id)
  return active_requests[request_id] ~= nil
end

--- Close all connections in the pool
function M.close_all()
  for key, entry in pairs(pool.connections) do
    if entry.socket and not entry.socket:is_closing() then
      entry.socket:close()
    end
  end
  pool.connections = {}
end

--- Get pool statistics (for debugging)
---@return { total: number, idle: number, busy: number }
function M.get_pool_stats()
  local stats = { total = 0, idle = 0, busy = 0 }
  for _, entry in pairs(pool.connections) do
    stats.total = stats.total + 1
    if entry.state == "idle" then
      stats.idle = stats.idle + 1
    elseif entry.state == "busy" then
      stats.busy = stats.busy + 1
    end
  end
  return stats
end

return M
