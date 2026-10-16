--- Base provider interface for blink-edit
--- Providers handle prompt construction and response parsing
---
--- Each provider must implement:
--- - get_requirements(): Returns what context the provider needs
--- - build_prompt(context, limits): Builds the prompt from context data
--- - parse_response(response, snapshot_lines): Parses LLM response
--- - get_stop_tokens(): Returns stop tokens for the model

local M = {}
M.__index = M

local utils = require("blink-edit.utils")

-- =============================================================================
-- Data Structure Definitions (for documentation)
-- =============================================================================

---@class BlinkEditProvider
---@field name string
---@field config table
---@field global_config BlinkEditConfig|nil

---@class BlinkEditProviderRequirements
---@field needs_history boolean
---@field needs_diagnostics boolean
---@field needs_full_file boolean
---@field needs_lsp_definitions boolean
---@field needs_lsp_references boolean
---@field needs_selection boolean
---@field local_context_lines number|nil

-- =============================================================================
-- Constructor
-- =============================================================================

---@param opts? { name?: string, config?: table, global_config?: BlinkEditConfig }
---@return BlinkEditProvider
function M.new(opts)
  opts = opts or {}
  local self = setmetatable({}, M)
  self.name = opts.name or "base"
  self.config = opts.config or {}
  self.global_config = opts.global_config
  return self
end

-- =============================================================================
-- Interface Methods (providers should override these)
-- =============================================================================

--- Get provider requirements - what context does this provider need?
--- Providers should override this method.
---@return BlinkEditProviderRequirements
function M:get_requirements()
  return {
    needs_history = false,
    needs_diagnostics = false,
    needs_full_file = false,
    needs_lsp_definitions = false,
    needs_lsp_references = false,
    needs_selection = false,
    local_context_lines = nil,
  }
end

--- Build prompt from context data
--- Providers should override this method.
---@param _context BlinkEditContextData
---@param _limits BlinkEditContextLimits
---@return string|nil prompt
---@return table|nil metadata
---@return string|nil error
function M:build_prompt(_context, _limits)
  return nil, nil, "build_prompt not implemented"
end

--- Parse LLM response into lines
--- Providers can override this for custom parsing.
---@param response string
---@param _snapshot_lines string[]|nil
---@return string[]|nil lines
---@return string|nil error
function M:parse_response(response, _snapshot_lines)
  response = self:trim_response(response)
  return self:split_lines(response), nil
end

--- Get stop tokens for this provider
--- Providers should override this method.
---@return string[]
function M:get_stop_tokens()
  return {}
end

-- =============================================================================
-- Helper Methods (shared utilities for all providers)
-- =============================================================================

--- Trim trailing whitespace from response
---@param response string
---@return string
function M:trim_response(response)
  return response:gsub("%s+$", "")
end

--- Split response into lines
---@param response string
---@return string[]
function M:split_lines(response)
  local lines = {}
  for line in response:gmatch("([^\n]*)\n?") do
    table.insert(lines, line)
  end

  if #lines > 0 and lines[#lines] == "" then
    table.remove(lines)
  end

  return lines
end

--- Format lines array to string
---@param lines string[]
---@return string
function M:format_lines(lines)
  if not lines or #lines == 0 then
    return ""
  end
  return table.concat(lines, "\n")
end

--- Filter out empty history entries (both original and updated are empty)
---@param entries BlinkEditHistoryEntry[]
---@return BlinkEditHistoryEntry[]
function M:filter_empty_history(entries)
  if not entries then
    return {}
  end

  local filtered = {}
  for _, entry in ipairs(entries) do
    local original = entry.original or ""
    local updated = entry.updated or ""

    -- Skip if both are empty or only whitespace
    if original:match("%S") or updated:match("%S") then
      table.insert(filtered, entry)
    end
  end

  return filtered
end

--- Estimate token count from text
---@param text string
---@return number
function M:estimate_tokens(text)
  return utils.estimate_tokens(text)
end

--- Generate unified diff between old and new text using vim.diff
---@param old_text string
---@param new_text string
---@return string
function M:generate_unified_diff(old_text, new_text)
  if not old_text then
    old_text = ""
  end
  if not new_text then
    new_text = ""
  end

  -- Ensure texts end with newline for proper diff
  if old_text ~= "" and not old_text:match("\n$") then
    old_text = old_text .. "\n"
  end
  if new_text ~= "" and not new_text:match("\n$") then
    new_text = new_text .. "\n"
  end

  -- Handle edge cases
  if old_text == new_text then
    return ""
  end

  -- Use vim.diff to generate unified diff
  local ok, diff = pcall(vim.diff, old_text, new_text, {
    algorithm = "histogram",
    result_type = "unified",
    ctxlen = 3,
  })

  if not ok or not diff then
    -- Fallback: simple diff format
    return self:generate_simple_diff(old_text, new_text)
  end

  -- Remove the diff header (first two lines: --- a/... and +++ b/...)
  -- Keep just the hunks starting with @@
  local lines = {}
  local in_hunk = false
  for line in diff:gmatch("([^\n]*)\n?") do
    if line:match("^@@") then
      in_hunk = true
    end
    if in_hunk then
      table.insert(lines, line)
    end
  end

  return table.concat(lines, "\n")
end

--- Generate simple diff (fallback when vim.diff fails)
---@param old_text string
---@param new_text string
---@return string
function M:generate_simple_diff(old_text, new_text)
  local old_lines = vim.split(old_text, "\n", { plain = true, trimempty = false })
  local new_lines = vim.split(new_text, "\n", { plain = true, trimempty = false })

  -- Remove trailing empty line if text ended with newline
  if #old_lines > 0 and old_lines[#old_lines] == "" then
    table.remove(old_lines)
  end
  if #new_lines > 0 and new_lines[#new_lines] == "" then
    table.remove(new_lines)
  end

  local result = {}
  table.insert(result, string.format("@@ -1,%d +1,%d @@", #old_lines, #new_lines))

  for _, line in ipairs(old_lines) do
    table.insert(result, "-" .. line)
  end
  for _, line in ipairs(new_lines) do
    table.insert(result, "+" .. line)
  end

  return table.concat(result, "\n")
end

--- Build context block with file separator (for generic/sweep style)
---@param label string Label for the block (e.g., "test.py.diff")
---@param content string Content of the block
---@param separator string|nil Separator token (default: "<|file_sep|>")
---@return string
function M:build_context_block(label, content, separator)
  separator = separator or "<|file_sep|>"
  return string.format("%s%s\n%s", separator, label, content)
end

return M
