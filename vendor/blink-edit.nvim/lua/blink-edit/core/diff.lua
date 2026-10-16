--- Diff computation for blink-edit
--- Uses vim.diff() to compute line-level diffs with character-level analysis for modifications

local M = {}

local utils = require("blink-edit.utils")

-- =============================================================================
-- Type Definitions (for documentation)
-- =============================================================================

---@class LineChange
---@field type "append_chars"|"modification"|"replace_line"
---@field col number Column position for ghost text (0-indexed)
---@field text string The text to display

---@class LineChangeEntry
---@field index number Relative index within hunk (1-indexed)
---@field change LineChange

---@class DiffHunk
---@field type "insertion"|"deletion"|"modification"|"replacement"
---@field start_old number Line number in old text (1-indexed)
---@field start_new number Line number in new text (1-indexed)
---@field count_old number Number of old lines affected
---@field count_new number Number of new lines affected
---@field old_lines string[]|nil Lines from snapshot (for deletion/modification)
---@field new_lines string[]|nil Lines from predicted (for insertion/modification)
---@field line_changes LineChangeEntry[]|nil For same-count modifications: per-line analysis

---@class DiffResult
---@field hunks DiffHunk[]
---@field has_changes boolean

-- =============================================================================
-- Helper Functions
-- =============================================================================

--- Extract a range of lines from an array
---@param lines string[]
---@param start number Start index (1-indexed)
---@param count number Number of lines to extract
---@return string[]
local function extract_lines(lines, start, count)
  local result = {}
  for i = 1, count do
    result[i] = lines[start + i - 1] or ""
  end
  return result
end

--- Find the length of the common prefix between two strings
---@param s1 string
---@param s2 string
---@return number
local function common_prefix_length(s1, s2)
  local len = 0
  for i = 1, math.min(#s1, #s2) do
    if s1:sub(i, i) == s2:sub(i, i) then
      len = i
    else
      break
    end
  end
  return len
end

-- =============================================================================
-- Line Change Analysis
-- =============================================================================

--- Analyze what changed between two lines (character-level)
--- Returns information about where to place ghost text
---@param old_line string
---@param new_line string
---@return LineChange
function M.analyze_line_change(old_line, new_line)
  -- Pattern 1: Append at end (new starts with old)
  if #new_line > #old_line and new_line:sub(1, #old_line) == old_line then
    return {
      type = "append_chars",
      col = #old_line,
      text = new_line:sub(#old_line + 1),
    }
  end

  -- Pattern 2: Find common prefix
  local prefix_len = common_prefix_length(old_line, new_line)

  -- If we have a reasonable prefix, show from divergence point
  if prefix_len > 0 then
    return {
      type = "modification",
      col = prefix_len,
      text = new_line:sub(prefix_len + 1),
    }
  end

  -- Pattern 3: No good prefix, replace entire line
  return {
    type = "replace_line",
    col = 0,
    text = new_line,
  }
end

-- =============================================================================
-- Hunk Processing
-- =============================================================================

--- Process a raw vim.diff() hunk into our DiffHunk structure
---@param raw number[] { start_old, count_old, start_new, count_new }
---@param snapshot string[]
---@param predicted string[]
---@return DiffHunk
local function process_raw_hunk(raw, snapshot, predicted)
  local start_old, count_old, start_new, count_new = raw[1], raw[2], raw[3], raw[4]

  -- Extract affected lines
  local old_lines = extract_lines(snapshot, start_old, count_old)
  local new_lines = extract_lines(predicted, start_new, count_new)

  ---@type DiffHunk
  local hunk = {
    start_old = start_old,
    start_new = start_new,
    count_old = count_old,
    count_new = count_new,
    old_lines = old_lines,
    new_lines = new_lines,
    type = "modification", -- Default, will be overwritten
    line_changes = nil,
  }

  -- Classify hunk type
  if count_old == 0 and count_new > 0 then
    -- INSERTION: lines added, nothing deleted
    hunk.type = "insertion"
  elseif count_old > 0 and count_new == 0 then
    -- DELETION: lines deleted, nothing added
    hunk.type = "deletion"
  elseif count_old == count_new then
    -- MODIFICATION: same number of lines, can do 1-to-1 comparison
    hunk.type = "modification"
    hunk.line_changes = {}

    for i = 1, count_old do
      if old_lines[i] ~= new_lines[i] then
        local change = M.analyze_line_change(old_lines[i], new_lines[i])
        table.insert(hunk.line_changes, {
          index = i,
          change = change,
        })
      end
    end
  else
    -- REPLACEMENT: different counts, can't do 1-to-1 mapping
    hunk.type = "replacement"
  end

  return hunk
end

-- =============================================================================
-- Main API
-- =============================================================================

--- Compute diff between snapshot and predicted lines
---@param snapshot string[]
---@param predicted string[]
---@return DiffResult
function M.compute(snapshot, predicted)
  -- Handle nil inputs
  if not snapshot then
    snapshot = {}
  end
  if not predicted then
    predicted = {}
  end

  -- Check if identical
  if utils.lines_equal(snapshot, predicted) then
    return { hunks = {}, has_changes = false }
  end

  -- Handle edge case: empty snapshot (all insertions)
  if #snapshot == 0 and #predicted > 0 then
    return {
      hunks = {
        {
          type = "insertion",
          start_old = 0,
          start_new = 1,
          count_old = 0,
          count_new = #predicted,
          old_lines = {},
          new_lines = predicted,
          line_changes = nil,
        },
      },
      has_changes = true,
    }
  end

  -- Handle edge case: empty predicted (all deletions)
  if #snapshot > 0 and #predicted == 0 then
    return {
      hunks = {
        {
          type = "deletion",
          start_old = 1,
          start_new = 0,
          count_old = #snapshot,
          count_new = 0,
          old_lines = snapshot,
          new_lines = {},
          line_changes = nil,
        },
      },
      has_changes = true,
    }
  end

  -- Convert to text for vim.diff()
  local old_text = table.concat(snapshot, "\n")
  local new_text = table.concat(predicted, "\n")

  -- Get raw hunks from vim.diff()
  local raw_hunks = vim.diff(old_text, new_text, {
    result_type = "indices",
    algorithm = "histogram",
  })

  -- Handle case where vim.diff returns nil or empty
  if not raw_hunks or #raw_hunks == 0 then
    -- Texts differ but vim.diff found no hunks - edge case
    -- This shouldn't happen, but handle it gracefully
    return { hunks = {}, has_changes = false }
  end

  -- Process each hunk
  local hunks = {}
  for _, raw in ipairs(raw_hunks) do
    local hunk = process_raw_hunk(raw, snapshot, predicted)
    table.insert(hunks, hunk)
  end

  return { hunks = hunks, has_changes = #hunks > 0 }
end

-- =============================================================================
-- Utility Functions (for debugging/testing)
-- =============================================================================

--- Get a summary of a diff result
---@param diff_result DiffResult
---@return { insertions: number, deletions: number, modifications: number, replacements: number }
function M.summarize(diff_result)
  local summary = {
    insertions = 0,
    deletions = 0,
    modifications = 0,
    replacements = 0,
  }

  for _, hunk in ipairs(diff_result.hunks) do
    if hunk.type == "insertion" then
      summary.insertions = summary.insertions + 1
    elseif hunk.type == "deletion" then
      summary.deletions = summary.deletions + 1
    elseif hunk.type == "modification" then
      summary.modifications = summary.modifications + 1
    elseif hunk.type == "replacement" then
      summary.replacements = summary.replacements + 1
    end
  end

  return summary
end

return M
