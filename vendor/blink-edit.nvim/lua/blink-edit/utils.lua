--- Shared utility functions for blink-edit
--- Centralizes common functions used across multiple modules

local M = {}

-- =============================================================================
-- Constants
-- =============================================================================

--- Characters per token estimate (rough: 1 token ~ 4 characters)
M.CHARS_PER_TOKEN = 4

-- =============================================================================
-- Line Operations
-- =============================================================================

--- Check if two line arrays are equal
---@param a string[]
---@param b string[]
---@return boolean
function M.lines_equal(a, b)
  if #a ~= #b then
    return false
  end
  for i = 1, #a do
    if a[i] ~= b[i] then
      return false
    end
  end
  return true
end

-- =============================================================================
-- Token Estimation
-- =============================================================================

--- Estimate token count from text
---@param text string
---@return number
function M.estimate_tokens(text)
  if not text or text == "" then
    return 0
  end
  return math.ceil(#text / M.CHARS_PER_TOKEN)
end

--- Estimate token count from lines array
---@param lines string[]
---@return number
function M.estimate_tokens_lines(lines)
  if not lines or #lines == 0 then
    return 0
  end
  local total_chars = 0
  for _, line in ipairs(lines) do
    total_chars = total_chars + #line + 1 -- +1 for newline
  end
  return math.ceil(total_chars / M.CHARS_PER_TOKEN)
end

-- =============================================================================
-- Path Operations
-- =============================================================================

--- Normalize filepath to relative path from cwd
---@param filepath string
---@return string
function M.normalize_filepath(filepath)
  if not filepath or filepath == "" then
    return "[scratch]"
  end
  local cwd = vim.fn.getcwd()
  if filepath:sub(1, #cwd) == cwd then
    return filepath:sub(#cwd + 2)
  end
  return filepath
end

-- =============================================================================
-- Snippet Operations
-- =============================================================================

--- Merge snippets into a single string (sorted by start_line)
--- Used by sweep.lua and zeta.lua for context building
---@param snippets table[] Array of {start_line, end_line, lines}
---@return string
function M.merge_snippets(snippets)
  if not snippets or #snippets == 0 then
    return ""
  end

  -- Sort by start_line
  table.sort(snippets, function(a, b)
    return a.start_line < b.start_line
  end)

  local parts = {}
  for _, snippet in ipairs(snippets) do
    if snippet.lines and #snippet.lines > 0 then
      table.insert(parts, table.concat(snippet.lines, "\n"))
    end
  end

  if #parts == 0 then
    return ""
  end

  -- Join with blank line between non-contiguous snippets
  return table.concat(parts, "\n\n")
end

return M
