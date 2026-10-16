--- curl transport for HTTPS connections
--- Uses vim.fn.jobstart to spawn curl process
--- Fallback for when TCP can't be used (TLS/SSL)

local M = {}

local log = require("blink-edit.log")

--- Make an HTTP request using curl
---@param opts { url: string, method?: string, headers?: table<string, string>, body?: string, timeout?: number }
---@param callback fun(err: { type: string, message: string }|nil, response: { status: number, headers: table, body: string }|nil)
function M.request(opts, callback)
  local url = opts.url
  local method = opts.method or "POST"
  local timeout = opts.timeout or 5000
  local body = opts.body or ""

  -- Build curl arguments
  local args = {
    "curl",
    "-s", -- Silent mode
    "-S", -- Show errors
    "-X",
    method, -- HTTP method
    "--max-time",
    tostring(timeout / 1000), -- Timeout in seconds
    "-w",
    "\n%{http_code}", -- Append status code
    "-D",
    "-", -- Dump headers to stdout
  }

  -- Add custom headers
  if opts.headers then
    for key, value in pairs(opts.headers) do
      table.insert(args, "-H")
      table.insert(args, string.format("%s: %s", key, value))
    end
  end

  -- Add body
  if body and #body > 0 then
    table.insert(args, "-d")
    table.insert(args, body)
  end

  -- Add URL
  table.insert(args, url)

  -- Collect output
  local stdout_data = {}
  local stderr_data = {}

  local job_id = vim.fn.jobstart(args, {
    stdout_buffered = true,
    stderr_buffered = true,

    on_stdout = function(_, data)
      if data then
        for _, line in ipairs(data) do
          if line and line ~= "" then
            table.insert(stdout_data, line)
          end
        end
      end
    end,

    on_stderr = function(_, data)
      if data then
        for _, line in ipairs(data) do
          if line and line ~= "" then
            table.insert(stderr_data, line)
          end
        end
      end
    end,

    on_exit = function(_, exit_code)
      vim.schedule(function()
        -- Check for errors
        if exit_code ~= 0 then
          local error_msg = table.concat(stderr_data, "\n")
          if error_msg == "" then
            if exit_code == 7 then
              error_msg = "Connection refused"
            elseif exit_code == 28 then
              error_msg = "Request timed out"
            elseif exit_code == 6 then
              error_msg = "Could not resolve host"
            else
              error_msg = "curl exited with code " .. exit_code
            end
          end

          log.error(error_msg)
          callback({
            type = exit_code == 28 and "timeout" or "curl_error",
            message = error_msg,
          }, nil)
          return
        end

        -- Parse response
        local raw_output = table.concat(stdout_data, "\n")

        -- The last line should be the HTTP status code (from -w flag)
        local status_code = nil
        local output_lines = vim.split(raw_output, "\n")

        -- Find the status code (last non-empty line that's just a number)
        for i = #output_lines, 1, -1 do
          local line = output_lines[i]
          if line:match("^%d+$") then
            status_code = tonumber(line)
            table.remove(output_lines, i)
            break
          end
        end

        -- Find headers and body split
        local headers = {}
        local body_start = 1
        local in_headers = true

        for i, line in ipairs(output_lines) do
          if in_headers then
            if line == "" or line:match("^%s*$") then
              -- Empty line marks end of headers
              body_start = i + 1
              in_headers = false
            else
              -- Parse header
              local key, value = line:match("^([^:]+):%s*(.+)$")
              if key then
                headers[key:lower()] = value
              end
            end
          end
        end

        -- Extract body
        local body_lines = {}
        for i = body_start, #output_lines do
          table.insert(body_lines, output_lines[i])
        end
        local response_body = table.concat(body_lines, "\n")

        -- Parse JSON if applicable
        local json_body = nil
        if headers["content-type"] and headers["content-type"]:find("application/json") then
          local ok, decoded = pcall(vim.json.decode, response_body)
          if ok then
            json_body = decoded
          end
        end

        callback(nil, {
          status = status_code or 0,
          headers = headers,
          body = json_body or response_body,
        })
      end)
    end,
  })

  if job_id <= 0 then
    vim.schedule(function()
      log.error("Failed to start curl process")
      callback({
        type = "spawn_error",
        message = "Failed to start curl process",
      }, nil)
    end)
  end

  -- Return job_id so caller can cancel if needed
  return job_id
end

--- Cancel a running curl request
---@param job_id number
function M.cancel(job_id)
  if job_id and job_id > 0 then
    pcall(vim.fn.jobstop, job_id)
  end
end

return M
