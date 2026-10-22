-- Native Codex /ide IPC v0. Private upstream protocol; see docs/CODEX.md.
local M = {}
local uv = vim.uv
local context = require("maya.codex_context")
local running, listener, upstream, retry, owned, socket_path
local peers, pending = {}, {}
local serial = 0
local function id()
  serial = serial + 1
  return "mvim-" .. vim.fn.getpid() .. "-" .. serial
end
local function close(peer)
  if peer and not peer.pipe:is_closing() then
    peer.pipe:close()
  end
  if peer then
    peers[peer] = nil
  end
end
local function send(peer, value)
  if not peer or peer.pipe:is_closing() then
    return
  end
  local data = vim.json.encode(value)
  local size = #data
  local header = string.char(
    size % 256,
    math.floor(size / 256) % 256,
    math.floor(size / 65536) % 256,
    math.floor(size / 16777216) % 256
  )
  peer.pipe:write(header .. data)
end
local function response(peer, request, result, err)
  send(peer, {
    type = "response",
    requestId = request.requestId,
    method = request.method,
    resultType = err and "error" or "success",
    error = err,
    result = not err and { ideContext = result } or nil,
  })
end
local function dispatch(peer, message)
  if message.type == "client-discovery-request" then
    local request = type(message.request) == "table" and message.request or {}
    local params = type(request.params) == "table" and request.params or {}
    send(peer, {
      type = "client-discovery-response",
      requestId = message.requestId,
      response = {
        canHandle = request.method == "ide-context"
          and context.snapshot(params.workspaceRoot) ~= nil,
      },
    })
    return
  end
  if message.type == "response" and pending[message.requestId] then
    local task = pending[message.requestId]
    if task.target == peer then
      pending[message.requestId] = nil
      message.requestId = task.request.requestId
      send(task.peer, message)
    end
    return
  end
  if message.type == "client-discovery-response" and pending[message.requestId] then
    local task = pending[message.requestId]
    if task.candidates and task.candidates[peer] and (message.response or {}).canHandle then
      task.target = peer
      task.candidates = nil
      local forwarded = vim.deepcopy(task.request)
      forwarded.requestId = message.requestId
      send(peer, forwarded)
    end
    return
  end
  if message.type ~= "request" or type(message.requestId) ~= "string" then
    return
  end
  if message.method == "initialize" then
    peer.registered = true
    send(peer, {
      type = "response",
      requestId = message.requestId,
      resultType = "success",
      result = { clientId = id() },
    })
    return
  end
  if message.method ~= "ide-context" then
    return response(peer, message, nil, "no-handler-for-request")
  end
  M.requests = (M.requests or 0) + 1
  if message.version and message.version ~= 0 then
    return response(peer, message, nil, "request-version-mismatch")
  end
  local params = type(message.params) == "table" and message.params or {}
  local snapshot = context.snapshot(params.workspaceRoot)
  if snapshot then
    return response(peer, message, snapshot)
  end
  if peer == upstream then
    return response(peer, message, nil, "no-client-found")
  end
  local request_id = id()
  local task = { peer = peer, request = message, candidates = {} }
  pending[request_id] = task
  for candidate in pairs(peers) do
    if candidate ~= peer and candidate.registered then
      task.candidates[candidate] = true
      send(
        candidate,
        { type = "client-discovery-request", requestId = request_id, request = message }
      )
    end
  end
  if not next(task.candidates) then
    pending[request_id] = nil
    return response(peer, message, nil, "no-client-found")
  end
  vim.defer_fn(function()
    if pending[request_id] == task then
      pending[request_id] = nil
      response(peer, message, nil, "request-timeout")
    end
  end, 2000)
end
local function read(peer, disconnected)
  local buffer = ""
  local function drop()
    close(peer)
    if disconnected then
      vim.schedule(disconnected)
    end
  end
  peer.pipe:read_start(function(err, data)
    if err or not data then
      drop()
      return
    end
    buffer = buffer .. data
    if #buffer > 1048576 then
      drop()
      return
    end
    while #buffer >= 4 do
      local a, b, c, d = buffer:byte(1, 4)
      local size = a + b * 256 + c * 65536 + d * 16777216
      if size > 1048576 then
        drop()
        return
      end
      if #buffer < size + 4 then
        break
      end
      local ok, message = pcall(vim.json.decode, buffer:sub(5, size + 4))
      buffer = buffer:sub(size + 5)
      if not ok or type(message) ~= "table" then
        drop()
        return
      end
      vim.schedule(function()
        if running and not peer.pipe:is_closing() then
          dispatch(peer, message)
        end
      end)
    end
  end)
end
local acquire
local function reconnect()
  upstream = nil
  if not running then
    return
  end
  retry = vim.defer_fn(function()
    retry = nil
    acquire()
  end, 1000)
end
acquire = function()
  if not running then
    return
  end
  local server = uv.new_pipe(false)
  local ok, err = server:bind(socket_path)
  if ok then
    listener = server
    owned = uv.fs_lstat(socket_path)
    uv.fs_chmod(socket_path, 384)
    local listening, listen_err = server:listen(32, function(accept_err)
      if accept_err then
        return
      end
      local peer = { pipe = uv.new_pipe(false) }
      server:accept(peer.pipe)
      peers[peer] = true
      read(peer)
    end)
    if listening then
      M.error = nil
    else
      M.error = tostring(listen_err)
    end
    return
  end
  server:close()
  local peer = { pipe = uv.new_pipe(false) }
  local candidate_stat = uv.fs_lstat(socket_path)
  upstream = peer
  peer.pipe:connect(socket_path, function(connect_err)
    vim.schedule(function()
      if not running or upstream ~= peer then
        close(peer)
        return
      end
      if connect_err then
        close(peer)
        local stat = uv.fs_lstat(socket_path)
        -- Only remove an owned stale socket after an explicit refused connection.
        if
          tostring(connect_err):find("ECONNREFUSED", 1, true)
          and stat
          and stat.type == "socket"
          and stat.uid == uv.getuid()
          and candidate_stat
          and candidate_stat.ino == stat.ino
          and candidate_stat.dev == stat.dev
        then
          uv.fs_unlink(socket_path)
        end
        M.error = tostring(connect_err or err)
        reconnect()
        return
      end
      M.error = nil
      peer.connected = true
      read(peer, function()
        if upstream == peer then
          reconnect()
        end
      end)
      send(peer, {
        type = "request",
        requestId = id(),
        method = "initialize",
        params = { clientType = "neovim" },
      })
    end)
  end)
end

function M.stop()
  running = false
  if retry and not retry:is_closing() then
    retry:stop()
    retry:close()
  end
  retry = nil
  close(upstream)
  upstream = nil
  for peer in pairs(peers) do
    close(peer)
  end
  if listener and not listener:is_closing() then
    listener:close()
  end
  listener = nil
  local stat = socket_path and uv.fs_lstat(socket_path)
  if owned and stat and owned.ino == stat.ino and owned.dev == stat.dev then
    uv.fs_unlink(socket_path)
  end
  owned = nil
  pending = {}
end
function M.start(opts)
  if running then
    return true
  end
  if not uv.getuid then
    return false, "Codex IDE context currently requires Unix"
  end
  opts = opts or {}
  local home = vim.env.CODEX_HOME or (vim.fn.expand("~") .. "/.codex")
  socket_path = opts.socket_path or (home .. "/ipc/ipc.sock")
  local parent = vim.fs.dirname(socket_path)
  vim.fn.mkdir(parent, "p", 448)
  local stat = uv.fs_stat(parent)
  if not stat or stat.uid ~= uv.getuid() or bit.band(stat.mode, 18) ~= 0 then
    return false,
      "Codex IPC directory must be owned by you and not group/world writable: " .. parent
  end
  local existing = uv.fs_lstat(socket_path)
  if existing and (existing.type ~= "socket" or existing.uid ~= uv.getuid()) then
    M.error = "Refusing an existing non-socket or foreign-owned endpoint"
    return false, M.error
  end
  running = true
  M.requests = 0
  context.capture()
  acquire()
  return true
end
function M.status()
  return {
    running = running == true,
    role = listener and "router"
      or (upstream and (upstream.connected and "client" or "connecting") or "disconnected"),
    socket = socket_path,
    error = M.error,
  }
end
function M.notify_status()
  local status = M.status()
  vim.notify(
    table.concat({
      "Codex IDE context: " .. (status.running and status.role or "stopped"),
      "Socket: " .. (status.socket or "not started"),
      "Context requests received: " .. (M.requests or 0),
      status.error and ("Connection: " .. status.error)
        or "Read-only: open files and current selection; no file writes.",
      "In Codex CLI: /ide to attach context.",
      ":MayaCodexStart / :MayaCodexStop",
    }, "\n"),
    vim.log.levels.INFO,
    { title = "Codex IDE context", timeout = 10000 }
  )
end
function M.setup()
  local group = vim.api.nvim_create_augroup("MayaCodex", { clear = true })
  vim.api.nvim_create_autocmd(
    { "BufLeave", "CursorMoved", "CursorMovedI", "ModeChanged", "TextChanged", "TextChangedI" },
    {
      group = group,
      callback = function()
        if running then
          context.capture()
        end
      end,
    }
  )
  vim.api.nvim_create_autocmd("VimLeavePre", { group = group, callback = M.stop })
  vim.api.nvim_create_user_command("MayaCodexStart", function()
    local ok, err = M.start()
    if not ok then
      vim.notify(err, vim.log.levels.ERROR)
    else
      M.notify_status()
    end
  end, {})
  vim.api.nvim_create_user_command("MayaCodexStop", function()
    M.stop()
    M.notify_status()
  end, {})
  vim.api.nvim_create_user_command("MayaCodexStatus", M.notify_status, {})
  if require("maya.user").get("codex_ide_context") and vim.env.MAYA_NVIM_NO_AI ~= "1" then
    local ok, err = M.start()
    if not ok then
      vim.notify(err, vim.log.levels.WARN)
    end
  end
end
return M
