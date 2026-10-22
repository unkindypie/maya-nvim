-- Read-only, request-scoped editor context. No buffer contents are written to disk.
local M = {}
local last
local function path(buf)
  if
    not vim.api.nvim_buf_is_loaded(buf)
    or vim.bo[buf].buftype ~= ""
    or not vim.bo[buf].buflisted
  then
    return
  end
  local name = vim.api.nvim_buf_get_name(buf)
  if name ~= "" and not name:match("^%w+://") then
    return vim.uv.fs_realpath(name) or vim.fs.normalize(name)
  end
end
local function inside(file, root)
  return file == root or file:sub(1, #root + 1) == root .. "/"
end
local function position(buf, row, byte)
  local line = vim.api.nvim_buf_get_lines(buf, row, row + 1, false)[1] or ""
  return { line = row, character = vim.str_utfindex(line, "utf-16", math.min(byte, #line), false) }
end

function M.capture()
  local buf = vim.api.nvim_get_current_buf()
  if not path(buf) then
    return
  end
  local cursor = vim.api.nvim_win_get_cursor(0)
  local point = position(buf, cursor[1] - 1, cursor[2])
  last = {
    buf = buf,
    selection = { start = point, ["end"] = point },
    selections = {},
    text = "",
    tick = vim.api.nvim_buf_get_changedtick(buf),
  }
  local mode = vim.fn.mode()
  if mode ~= "v" and mode ~= "V" and mode ~= "\22" then
    return
  end
  local anchor, finish = vim.fn.getpos("v"), vim.fn.getpos(".")
  if math.abs(anchor[2] - finish[2]) >= 1000 then
    last.text = "[Selection omitted: more than 1,000 lines selected.]"
    return
  end
  local opts = { type = mode, exclusive = vim.o.selection == "exclusive" }
  local spans = vim.fn.getregionpos(anchor, finish, opts)
  local lines = vim.fn.getregion(anchor, finish, opts)
  local text = table.concat(lines, "\n")
  if vim.fn.strchars(text) > 40000 then
    text = vim.fn.strcharpart(text, 0, 40000) .. "\n[Selection truncated to 40,000 characters.]"
  end
  last.text = text
  for _, span in ipairs(spans) do
    local a, b = span[1], span[2]
    local row = a[2] - 1
    local source = vim.api.nvim_buf_get_lines(buf, row, row + 1, false)[1] or ""
    local byte = math.min(math.max(b[3] - 1, 0), #source)
    local next_byte = byte + #vim.fn.strcharpart(source:sub(byte + 1), 0, 1)
    last.selections[#last.selections + 1] =
      { start = position(buf, row, math.max(a[3] - 1, 0)), ["end"] = position(buf, row, next_byte) }
  end
  if #last.selections > 0 then
    if mode == "V" then
      last.selection = {
        start = { line = spans[1][1][2] - 1, character = 0 },
        ["end"] = { line = spans[#spans][2][2], character = 0 },
      }
      last.selections = {}
    elseif mode ~= "\22" then
      last.selection =
        { start = last.selections[1].start, ["end"] = last.selections[#last.selections]["end"] }
      last.selections = {}
    else
      last.selection = last.selections[1]
    end
  end
end

function M.snapshot(root)
  if type(root) ~= "string" or root:sub(1, 1) ~= "/" then
    return
  end
  root = (vim.uv.fs_realpath(root) or vim.fs.normalize(root)):gsub("/+$", "")
  if root == "" then
    return
  end
  M.capture()
  local tabs = {}
  for _, buf in ipairs(vim.api.nvim_list_bufs()) do
    local file = path(buf)
    if file and inside(file, root) and #tabs < 100 then
      tabs[#tabs + 1] = { label = vim.fs.basename(file), path = file:sub(#root + 2), fsPath = file }
    end
  end
  if #tabs == 0 then
    return
  end
  local active = vim.NIL
  if last and vim.api.nvim_buf_is_valid(last.buf) then
    local file = path(last.buf)
    if file and inside(file, root) then
      local valid = last.tick == vim.api.nvim_buf_get_changedtick(last.buf)
      active = {
        label = vim.fs.basename(file),
        path = file:sub(#root + 2),
        fsPath = file,
        selection = valid and last.selection
          or { start = { line = 0, character = 0 }, ["end"] = { line = 0, character = 0 } },
        selections = valid and last.selections or {},
        activeSelectionContent = valid and last.text or "",
      }
    end
  end
  return { activeFile = active, openTabs = tabs }
end

return M
