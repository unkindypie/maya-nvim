-- Syntax locates anchors only; semantic types come from LSP responses.
local M = {}
local adapters = {
  lua = {
    variable_declaration = true,
    assignment_statement = true,
    function_call = true,
    arguments = true,
  },
  typescript = {
    lexical_declaration = true,
    variable_declarator = true,
    call_expression = true,
    arguments = true,
  },
  typescriptreact = {
    lexical_declaration = true,
    variable_declarator = true,
    call_expression = true,
    arguments = true,
  },
  python = { assignment = true, call = true, argument_list = true, function_definition = true },
}
local primitive = {
  any = true,
  boolean = true,
  number = true,
  integer = true,
  string = true,
  table = true,
  ["function"] = true,
  ["nil"] = true,
  unknown = true,
  thread = true,
  userdata = true,
  fun = true,
  self = true,
  str = true,
  int = true,
  float = true,
  bool = true,
  bytes = true,
  object = true,
  list = true,
  dict = true,
  set = true,
  tuple = true,
  None = true,
  ["true"] = true,
  ["false"] = true,
}

-- Locate named types in annotations, without interpreting their semantics.
function M.annotations(lines, first, fields, ft)
  ft = ft or "lua"
  local positions = {}
  for i, line in ipairs(lines) do
    local column, expression
    if ft == "lua" then
      column, expression = line:match("^%s*%-%-%-@type%s+()([^#]+)")
      if fields and not expression then
        column, expression = line:match("^%s*%-%-%-@field%s+[%w_%.%?]+%s+()(%S+)")
        if not expression then
          column, expression = line:match("^%s*%-%-%-@alias%s+[%w_%.]+%s+()(%S+)")
        end
      end
    end
    if ft == "python" and (fields or line:find("=", 1, true)) then
      column, expression = line:match("^%s*[%w_]+%s*:%s*()([^=#]+)")
    elseif
      (ft == "typescript" or ft == "typescriptreact") and (fields or line:find("=", 1, true))
    then
      column, expression = line:match("^%s*[%w_$]+%??%s*:%s*()([^=;]+)")
      if not expression then
        column, expression = line:match("^%s*[%w_%s]+%s+[%w_$]+%s*:%s*()([^=;]+)")
      end
    end
    if expression then
      for offset, name in expression:gmatch("()([%a_][%w_%.]*)") do
        if not primitive[name] and #positions < 8 then
          positions[#positions + 1] = {
            first + i - 1,
            column + offset + (name:match(".*()%.") or 0) - 2,
            annotation = true,
            symbol = name,
          }
        end
      end
    end
  end
  return positions
end

local function encloses(lines, start, ft)
  local depth, quote, escaped = 0, nil, false
  for row = start, #lines do
    local code, line, col = {}, lines[row], 1
    while col <= #line do
      local char = line:sub(col, col)
      if quote then
        if escaped then
          escaped = false
        elseif char == "\\" then
          escaped = true
        elseif char == quote then
          quote = nil
        end
      elseif char == '"' or char == "'" or char == "`" then
        quote = char
      elseif
        (ft == "lua" and line:sub(col, col + 1) == "--")
        or (ft == "python" and char == "#")
        or (ft ~= "lua" and ft ~= "python" and line:sub(col, col + 1) == "//")
      then
        break
      else
        code[#code + 1] = char
        if char == "{" or char == "[" or char == "(" then
          depth = depth + 1
        elseif char == "}" or char == "]" or char == ")" then
          depth = depth - 1
        end
      end
      col = col + 1
    end
    local text = table.concat(code)
    if row < #lines and depth <= 0 and text:match("%S") and not text:match("=%s*$") then
      return false
    end
  end
  return true
end

function M.get(buf, cursor)
  local row, col = cursor[1] - 1, cursor[2]
  local line = vim.api.nvim_buf_get_lines(buf, row, row + 1, false)[1] or ""
  local before = line:sub(1, col)
  local receiver = before:match("()([%w_]+)[%.:][%w_]*$") or before:match("()([%w_]+)%->[%w_]*$")
  local positions = { { row, receiver and receiver - 1 or col } }
  local seen = { [row .. ":" .. positions[1][2]] = true }
  local function add(position)
    local key = position[1] .. ":" .. position[2]
    if not seen[key] and #positions < 8 then
      seen[key] = true
      positions[#positions + 1] = position
    end
  end
  if receiver then
    add({ row, col })
  end
  local first, last = math.max(0, row - 5), row + 3
  local ft = vim.bo[buf].filetype
  local adapter = adapters[ft]
  if adapter then
    local ok, node =
      pcall(vim.treesitter.get_node, { bufnr = buf, pos = { row, math.max(0, col - 1) } })
    if ok then
      while node and #positions < 8 do
        if adapter[node:type()] then
          local r, c, e = node:range()
          first, last = math.max(0, r - 5, row - 40), math.min(e + 1, row + 12)
          local name = node:field("name")[1] or node:field("left")[1] or node:field("function")[1]
          if name then
            r, c = name:range()
          end
          add({ r, c })
          local annotation = node:field("type")[1]
          if annotation then
            -- TypeScript's type_annotation includes ':', followed by the type.
            if annotation:type() == "type_annotation" then
              annotation = annotation:named_child(0) or annotation
            end
            local ar, ac = annotation:range()
            add({ ar, ac, annotation = true })
          end
        end
        node = node:parent()
      end
    end
  end
  if adapter then
    -- Incomplete values may parse as ERROR, with no declaration ancestor.
    local start = math.max(0, row - 80)
    local lines = vim.api.nvim_buf_get_lines(buf, start, row + 1, false)
    for i = #lines, 1, -1 do
      local anchors = M.annotations({ lines[i] }, start + i - 1, false, ft)
      if #anchors > 0 and encloses(lines, ft == "lua" and i + 1 or i, ft) then
        for _, position in ipairs(anchors) do
          add(position)
        end
        first = math.min(first, start + i - 1)
        break
      end
    end
  end
  -- Resolve explicit annotations before less specific cursor/call anchors.
  for i, position in ipairs(positions) do
    position.order = i
  end
  table.sort(positions, function(a, b)
    if not not a.annotation == not not b.annotation then
      return a.order < b.order
    end
    return a.annotation == true
  end)
  return positions,
    table.concat(
      vim.api.nvim_buf_get_lines(
        buf,
        first,
        math.min(last, vim.api.nvim_buf_line_count(buf)),
        false
      ),
      "\n"
    )
end
return M
