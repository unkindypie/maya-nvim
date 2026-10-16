-- Async LSP hints. Prompt hooks only read this bounded cache; they never wait.
local M = {}
local cache, pending, generation = {}, {}, 0
local timer
local function identity()
  local buf = vim.api.nvim_get_current_buf()
  local cursor = vim.api.nvim_win_get_cursor(0)
  return buf, vim.api.nvim_buf_get_changedtick(buf), cursor
end
function M.cancel()
  generation = generation + 1
  if timer and not timer:is_closing() then
    timer:stop()
    timer:close()
  end
  timer = nil
  for _, cancel in ipairs(pending) do
    pcall(cancel)
  end
  pending = {}
  cache = {}
end
local function key(buf, tick, cursor)
  return table.concat({ buf, tick, cursor[1], cursor[2] }, ":")
end
function M.get()
  local buf, tick, cursor = identity()
  local entry = cache[key(buf, tick, cursor)]
  return entry and vim.uv.now() - entry.time < 2000 and entry.text:sub(1, 1500) or ""
end
local function definition(location, append, valid)
  local uri = location.uri or location.targetUri
  local range = location.range or location.targetSelectionRange or location.targetRange
  if not uri or not uri:match("^file://") or not range then
    return
  end
  local path = vim.uri_to_fname(uri)
  local buf = vim.fn.bufnr(path)
  local first = math.max(0, range.start.line - 3)
  local function consume(lines)
    if valid() then
      append(path .. ":\n" .. table.concat(vim.list_slice(lines, first + 1, first + 20), "\n"))
    end
  end
  if buf >= 0 and vim.api.nvim_buf_is_loaded(buf) then
    local last = math.min(first + 20, vim.api.nvim_buf_line_count(buf))
    if first < last and valid() then
      append(
        path .. ":\n" .. table.concat(vim.api.nvim_buf_get_lines(buf, first, last, false), "\n")
      )
    end
  else
    vim.uv.fs_open(path, "r", 438, function(err, fd)
      if err or not fd then
        return
      end
      vim.uv.fs_fstat(fd, function(stat_err, stat)
        if stat_err or stat.size > 262144 then
          vim.uv.fs_close(fd)
          return
        end
        vim.uv.fs_read(fd, math.min(stat.size, 65536), 0, function(read_err, data)
          vim.uv.fs_close(fd)
          if not read_err then
            vim.schedule(function()
              consume(vim.split(data, "\n", { plain = true }))
            end)
          end
        end)
      end)
    end)
  end
end
function M.refresh()
  for _, cancel in ipairs(pending) do
    pcall(cancel)
  end
  pending = {}
  generation = generation + 1
  local request_generation = generation
  local buf, tick, cursor = identity()
  local k = key(buf, tick, cursor)
  local function valid()
    if request_generation ~= generation or not vim.api.nvim_buf_is_valid(buf) then
      return false
    end
    local b, t, c = identity()
    return b == buf and t == tick and vim.deep_equal(c, cursor)
  end
  local entry = { time = vim.uv.now(), text = "" }
  if vim.tbl_count(cache) >= 64 then
    cache = {}
  end
  cache[k] = entry
  local function append(text)
    entry.text = (entry.text .. "\n" .. text):sub(1, 1500)
  end
  -- Point hover/definitions at the receiver before '.', ':', or '->'.
  local before = vim.api.nvim_get_current_line():sub(1, cursor[2])
  local receiver = before:match("()([%w_]+)[%.:][%w_]*$") or before:match("()([%w_]+)%->[%w_]*$")
  for _, client in ipairs(vim.lsp.get_clients({ bufnr = buf })) do
    for _, method in ipairs({
      "textDocument/hover",
      "textDocument/signatureHelp",
      "textDocument/definition",
    }) do
      if client:supports_method(method, buf) then
        local params = vim.lsp.util.make_position_params(0, client.offset_encoding)
        if receiver and method ~= "textDocument/signatureHelp" then
          params.position.character = vim.str_utfindex(
            vim.api.nvim_get_current_line(),
            client.offset_encoding,
            receiver - 1,
            false
          )
        end
        local done = false
        local ok, id = client:request(method, params, function(err, result)
          done = true
          if err or not result or not valid() then
            return
          end
          if method == "textDocument/hover" then
            append(
              table.concat(vim.lsp.util.convert_input_to_markdown_lines(result.contents), "\n")
            )
          elseif method == "textDocument/signatureHelp" then
            for _, signature in ipairs(result.signatures or {}) do
              append(signature.label or "")
            end
          else
            local locations = vim.islist(result) and result or { result }
            for i = 1, math.min(2, #locations) do
              definition(locations[i], append, valid)
            end
          end
        end, buf)
        if ok then
          local cancel = function()
            if not done then
              done = true
              client:cancel_request(id)
            end
          end
          pending[#pending + 1] = cancel
          vim.defer_fn(cancel, 1000)
        end
      end
    end
  end
end
function M.setup(enabled)
  local group = vim.api.nvim_create_augroup("MayaAIContext", { clear = true })
  vim.api.nvim_create_autocmd({ "CursorMovedI", "TextChangedI", "InsertEnter" }, {
    group = group,
    callback = function()
      M.cancel()
      if not enabled() then
        return
      end
      timer = vim.defer_fn(function()
        timer = nil
        if enabled() then
          M.refresh()
        end
      end, 300)
    end,
  })
  vim.api.nvim_create_autocmd(
    { "BufLeave", "InsertLeave", "LspDetach" },
    { group = group, callback = M.cancel }
  )
end
return M
