-- Async LSP hints. Prompt hooks only read this bounded cache; they never wait.
local M = {}
local cache, pending, generation = {}, {}, 0
local snippets = {}
local function identity()
  local buf = vim.api.nvim_get_current_buf()
  local cursor = vim.api.nvim_win_get_cursor(0)
  return buf, vim.api.nvim_buf_get_changedtick(buf), cursor
end
function M.cancel()
  generation = generation + 1
  for _, cancel in ipairs(pending) do
    pcall(cancel)
  end
  pending = {}
  cache = {}
end
local function key(buf, tick, cursor)
  return table.concat({ buf, tick, cursor[1], cursor[2] }, ":")
end
---@param opts? {include_source?: boolean}
function M.get(opts)
  local buf, tick, cursor = identity()
  local entry = cache[key(buf, tick, cursor)]
  if not entry then
    return ""
  end
  local matches = {}
  for _, item in ipairs(snippets) do
    local target = vim.fn.bufnr(item.path)
    if not item.buf and target >= 0 and vim.api.nvim_buf_is_loaded(target) then
      item.valid = false
    end
    if
      item.owner == buf
      and item.scope == entry.scope
      and math.abs(item.row - cursor[1]) < 12
      and item.valid
      and (
        not item.buf
        or (
          vim.api.nvim_buf_is_valid(item.buf)
          and vim.api.nvim_buf_get_changedtick(item.buf) == item.tick
        )
      )
    then
      matches[#matches + 1] = item
    end
  end
  table.sort(matches, function(a, b)
    return a.priority > b.priority
  end)
  local parts, used = {}, 0
  for _, item in ipairs(matches) do
    local text = item.text:sub(1, 5000 - used)
    parts[#parts + 1] = text
    used = used + #text + 1
    if used >= 5000 then
      break
    end
  end
  if not opts or opts.include_source ~= false then
    parts[#parts + 1] = (entry.source or ""):sub(1, 1000)
  end
  parts[#parts + 1] = entry.text
  return table.concat(parts, "\n"):gsub("^\n+", ""):sub(1, 6000)
end
local function definition(location, valid, owner, row, scope, priority, follow)
  local uri = location.uri or location.targetUri
  local range = location.range or location.targetSelectionRange or location.targetRange
  if not uri or not uri:match("^file://") or not range then
    return
  end
  local path = vim.uri_to_fname(uri)
  local buf = vim.fn.bufnr(path)
  local first = math.max(0, range.start.line - 8)
  local function retain(text, target, tick, stat)
    if not valid() then
      return
    end
    for i = #snippets, 1, -1 do
      if snippets[i].path == path and snippets[i].owner == owner and snippets[i].first == first then
        priority = math.max(priority, snippets[i].priority)
        table.remove(snippets, i)
      end
    end
    if #snippets >= 32 then
      table.remove(snippets, 1)
    end
    snippets[#snippets + 1] = {
      owner = owner,
      row = row,
      path = path,
      first = first,
      text = text,
      buf = target,
      tick = tick,
      stat = stat,
      valid = true,
      priority = priority,
      scope = scope,
    }
  end
  local function consume(lines, offset, target, tick, stat, document)
    if not valid() then
      return
    end
    local start, last = 1, #lines
    local selected = range.start.line - offset + 1
    -- Retain the entire Lua annotation block, excluding unrelated declarations.
    if
      path:match("%.lua$")
      and lines[selected]
      and lines[selected]:match("^%s*%-%-%-@class%s+")
    then
      start, last = selected, selected
      while start > 1 and lines[start - 1]:match("^%s*%-%-%-") do
        start = start - 1
      end
      while last < #lines and lines[last + 1]:match("^%s*%-%-%-") do
        last = last + 1
      end
    end
    local selected_lines = vim.list_slice(lines, start, last)
    first = offset + start - 1
    retain(path .. ":\n" .. table.concat(selected_lines, "\n"), target, tick, stat)
    local ft = ({ lua = "lua", ts = "typescript", tsx = "typescriptreact", py = "python" })[path:match(
      "%.([^.]+)$"
    )]
    if follow and ft then
      follow(uri, selected_lines, offset + start - 1, target, tick, ft, document)
    end
  end
  if buf >= 0 and vim.api.nvim_buf_is_loaded(buf) then
    local last = math.min(first + 65, vim.api.nvim_buf_line_count(buf))
    if first < last then
      consume(
        vim.api.nvim_buf_get_lines(buf, first, last, false),
        first,
        buf,
        vim.api.nvim_buf_get_changedtick(buf)
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
        vim.uv.fs_read(fd, stat.size, 0, function(read_err, data)
          vim.uv.fs_close(fd)
          if not read_err then
            vim.schedule(function()
              local document = vim.split(data, "\n", { plain = true })
              consume(
                vim.list_slice(document, first + 1, first + 65),
                first,
                nil,
                nil,
                stat,
                document
              )
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
  for _, item in ipairs(snippets) do
    if not item.buf then
      item.valid = false
      vim.uv.fs_stat(item.path, function(err, stat)
        vim.schedule(function()
          item.valid = not err
            and stat
            and item.stat
            and stat.size == item.stat.size
            and vim.deep_equal(stat.mtime, item.stat.mtime)
        end)
      end)
    end
  end
  local k = key(buf, tick, cursor)
  local function valid()
    if request_generation ~= generation or not vim.api.nvim_buf_is_valid(buf) then
      return false
    end
    local b, t, c = identity()
    return b == buf and t == tick and vim.deep_equal(c, cursor)
  end
  local positions, source = require("maya.ai_context_positions").get(buf, cursor)
  local names = {}
  for _, position in ipairs(positions) do
    if position.annotation then
      local text = vim.api.nvim_buf_get_lines(buf, position[1], position[1] + 1, false)[1] or ""
      names[#names + 1] = position.symbol or text:sub(position[2] + 1):match("^[%w_%.]+") or ""
    end
  end
  local entry = {
    scope = vim.bo[buf].filetype .. ":" .. table.concat(names, ","),
    time = vim.uv.now(),
    text = "",
    source = "Enclosing source (expected type unresolved unless supplied by LSP):\n" .. source,
  }
  if vim.tbl_count(cache) >= 64 then
    cache = {}
  end
  cache[k] = entry
  local function append(text)
    entry.text = (entry.text .. "\n" .. text):sub(1, 3000)
  end
  local followed, opened, extra_requests = {}, {}, 0
  local request
  request = function(client, method, uri, position, line, priority, depth, source_valid)
    if not client:supports_method(method, buf) then
      return
    end
    local params = {
      textDocument = { uri = uri },
      position = {
        line = position[1],
        character = vim.str_utfindex(
          line,
          client.offset_encoding,
          math.min(position[2], #line),
          false
        ),
      },
    }
    local done = false
    local ok, id = client:request(method, params, function(err, result)
      local expired = done == "expired"
      done = true
      if expired or err or not result or not valid() or (source_valid and not source_valid()) then
        return
      end
      if method == "textDocument/hover" then
        append(table.concat(vim.lsp.util.convert_input_to_markdown_lines(result.contents), "\n"))
      elseif method == "textDocument/signatureHelp" then
        for _, signature in ipairs(result.signatures or {}) do
          append(signature.label or "")
          if signature.documentation then
            append(
              table.concat(
                vim.lsp.util.convert_input_to_markdown_lines(signature.documentation),
                "\n"
              )
            )
          end
        end
      else
        local locations = vim.islist(result) and result or { result }
        for i = 1, math.min(2, #locations) do
          definition(
            locations[i],
            function()
              return valid() and (not source_valid or source_valid())
            end,
            buf,
            cursor[1],
            entry.scope,
            priority,
            depth < 2
                and function(target_uri, lines, first, target, target_tick, ft, document)
                  local anchors =
                    require("maya.ai_context_positions").annotations(lines, first, true, ft)
                  if #anchors == 0 then
                    return
                  end
                  -- Some servers need didOpen before requests against a definition's document.
                  -- Use the async source read and leave user buffers untouched.
                  if not target or not vim.lsp.buf_is_attached(target, client.id) then
                    local key = client.id .. ":" .. target_uri
                    if not opened[key] then
                      local text = document
                      if
                        target
                        and vim.api.nvim_buf_get_offset(
                            target,
                            vim.api.nvim_buf_line_count(target)
                          )
                          <= 262144
                      then
                        text = vim.api.nvim_buf_get_lines(target, 0, -1, false)
                      end
                      if not text then
                        return
                      end
                      local ok = client:notify("textDocument/didOpen", {
                        textDocument = {
                          uri = target_uri,
                          languageId = ft,
                          version = 0,
                          text = table.concat(text, "\n"),
                        },
                      })
                      if not ok then
                        return
                      end
                      opened[key] = true
                      pending[#pending + 1] = function()
                        if not opened[key] then
                          return
                        end
                        opened[key] = nil
                        local existing = vim.fn.bufnr(vim.uri_to_fname(target_uri))
                        if existing < 0 or not vim.lsp.buf_is_attached(existing, client.id) then
                          client:notify(
                            "textDocument/didClose",
                            { textDocument = { uri = target_uri } }
                          )
                        end
                      end
                    end
                  end
                  local function unchanged()
                    return not target
                      or (
                        vim.api.nvim_buf_is_valid(target)
                        and vim.api.nvim_buf_get_changedtick(target) == target_tick
                      )
                  end
                  for _, anchor in ipairs(anchors) do
                    local key = table.concat({ client.id, target_uri, anchor[1], anchor[2] }, ":")
                    if not followed[key] and extra_requests < 12 then
                      followed[key] = true
                      extra_requests = extra_requests + 1
                      request(
                        client,
                        client:supports_method("textDocument/definition", buf)
                            and "textDocument/definition"
                          or "textDocument/typeDefinition",
                        target_uri,
                        anchor,
                        lines[anchor[1] - first + 1],
                        math.max(1, priority - 1),
                        depth + 1,
                        unchanged
                      )
                    end
                  end
                end
              or nil
          )
        end
      end
    end, buf)
    if ok then
      local cancel = function()
        if not done then
          done = "expired"
          client:cancel_request(id)
        end
      end
      pending[#pending + 1] = cancel
      vim.defer_fn(cancel, 1000)
    end
  end
  for _, client in ipairs(vim.lsp.get_clients({ bufnr = buf })) do
    for _, position in ipairs(positions) do
      local line = vim.api.nvim_buf_get_lines(buf, position[1], position[1] + 1, false)[1] or ""
      for _, method in ipairs({
        "textDocument/hover",
        "textDocument/signatureHelp",
        "textDocument/typeDefinition",
        "textDocument/definition",
      }) do
        request(
          client,
          method,
          vim.uri_from_bufnr(buf),
          position,
          line,
          position.annotation and 3 or 1,
          0
        )
      end
    end
  end
end
function M.setup(_) end
return M
