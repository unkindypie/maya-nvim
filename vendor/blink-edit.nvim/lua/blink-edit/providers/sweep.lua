--- Sweep provider for blink-edit
--- Builds Sweep-style prompts with context support and token budget management
---
--- Prompt format:
--- <|file_sep|>{other_file}              -- Other-file context (LSP refs + selection)
--- {merged_snippets}
---
--- <|file_sep|>{filepath}                -- Same-file context (full-file + LSP refs above range)
--- {merged_snippets}
---
--- <|file_sep|>{filepath}.diff           -- History
--- original:
--- {original_text}
--- updated:
--- {updated_text}
---
--- <|file_sep|>original/{filepath}       -- Baseline window
--- {baseline_window_lines}
---
--- <|file_sep|>current/{filepath}        -- Current window
--- {current_window_lines}
---
--- <|file_sep|>updated/{filepath}        -- Model generates from here

local BaseProvider = require("blink-edit.providers.base")
local config = require("blink-edit.config")
local utils = require("blink-edit.utils")

local M = setmetatable({}, { __index = BaseProvider })
M.__index = M

-- =============================================================================
-- Constants
-- =============================================================================

-- Priority levels for context blocks (higher = more important, kept first)
local PRIORITY = {
  SAME_FILE = 100, -- Most important: same-file context
  OTHER_FILE = 10, -- Other file refs (lower priority, dropped first)
}

-- =============================================================================
-- Local Helper Functions
-- =============================================================================

--- Collect all snippets from context sources, grouped by filepath
--- Sources: LSP references, selection
---@param context BlinkEditContextData
---@return table<string, table[]> snippets grouped by filepath
local function collect_all_snippets(context)
  local snippets = {}

  -- Add LSP references
  for _, ref in ipairs(context.lsp_references or {}) do
    if ref.filepath and ref.lines and #ref.lines > 0 then
      if not snippets[ref.filepath] then
        snippets[ref.filepath] = {}
      end
      table.insert(snippets[ref.filepath], {
        start_line = ref.start_line,
        end_line = ref.end_line,
        lines = ref.lines,
      })
    end
  end

  -- Add selection
  local sel = context.selection
  if sel and sel.filepath and sel.lines and #sel.lines > 0 then
    if not snippets[sel.filepath] then
      snippets[sel.filepath] = {}
    end
    table.insert(snippets[sel.filepath], {
      start_line = sel.start_line,
      end_line = sel.end_line,
      lines = sel.lines,
    })
  end

  return snippets
end

-- =============================================================================
-- Constructor
-- =============================================================================

---@param opts? { name?: string, config?: table, global_config?: BlinkEditConfig }
---@return BlinkEditProvider
function M.new(opts)
  opts = opts or {}
  opts.name = "sweep"

  local self = BaseProvider.new(opts)
  setmetatable(self, M)

  local cfg = opts.config or {}
  self.window_size = cfg.window_size or 21
  self.strict_line_count = cfg.strict_line_count ~= false

  return self
end

-- =============================================================================
-- Interface Implementation
-- =============================================================================

--- Get provider requirements
--- Returns requirements based on user config (all enabled by default)
---@return BlinkEditProviderRequirements
function M:get_requirements()
  local cfg = config.get()
  return {
    needs_history = true,
    needs_diagnostics = false,
    needs_full_file = cfg.context.same_file.enabled,
    needs_lsp_definitions = false,
    needs_lsp_references = cfg.context.lsp.enabled,
    needs_selection = cfg.context.selection.enabled,
    local_context_lines = nil,
  }
end

--- Build prompt from context data
---@param context BlinkEditContextData
---@param limits BlinkEditContextLimits
---@return string|nil prompt
---@return table|nil metadata
---@return string|nil error
function M:build_prompt(context, limits)
  local parts = {}

  -- 1. Add context section (other files first, then same file)
  --    Respects max_context_tokens budget
  local context_section = self:build_context_section(context, limits.max_context_tokens)
  if context_section ~= "" then
    table.insert(parts, context_section)
  end

  -- 2. Add diff history section (already trimmed by context_manager)
  local diff_section = self:build_diff_section(context.history)
  if diff_section ~= "" then
    table.insert(parts, diff_section)
  end

  -- 3. Add original section (baseline window)
  table.insert(
    parts,
    string.format("<|file_sep|>original/%s\n%s", context.filepath, self:format_lines(context.baseline_window.lines))
  )

  -- 4. Add current section (current window)
  table.insert(
    parts,
    string.format("<|file_sep|>current/%s\n%s", context.filepath, self:format_lines(context.current_window.lines))
  )

  -- 5. Add updated marker (model generates from here)
  table.insert(parts, string.format("<|file_sep|>updated/%s", context.filepath))

  local prompt = table.concat(parts, "\n")

  local metadata = {
    window_start = context.current_window.start_line,
    window_end = context.current_window.end_line,
    filepath = context.filepath,
  }

  return prompt, metadata, nil
end

--- Parse LLM response
---@param response string
---@param _snapshot_lines string[]|nil
---@return string[]|nil lines
---@return string|nil error
function M:parse_response(response, _snapshot_lines)
  -- Split response into lines
  local lines = vim.split(response, "\n", { plain = true, trimempty = false })

  -- Trim trailing whitespace per line (preserve indentation)
  for i = 1, #lines do
    lines[i] = lines[i]:gsub("[ \t\r]+$", "")
  end

  -- Trust the model - return whatever it gives us
  return lines, nil
end

--- Get stop tokens
---@return string[]
function M:get_stop_tokens()
  return { "<|file_sep|>", "</s>", "<|endoftext|>" }
end

-- =============================================================================
-- Context Building Methods
-- =============================================================================

---@class ContextBlock
---@field filepath string
---@field content string
---@field tokens number
---@field priority number

--- Build context section with token budget management
--- Prioritizes blocks and pops off lowest priority blocks if over budget
--- Order: other files first, then same file
---@param context BlinkEditContextData
---@param max_tokens number Token budget for context
---@return string
function M:build_context_section(context, max_tokens)
  local all_snippets = collect_all_snippets(context)

  -- Collect all context blocks (ONE per file)
  ---@type ContextBlock[]
  local blocks = {}

  -- 1. Collect OTHER file blocks (lower priority - dropped first if over budget)
  for filepath, snippets in pairs(all_snippets) do
    if filepath ~= context.filepath then
      local merged = utils.merge_snippets(snippets)
      if merged ~= "" then
        local content = string.format("<|file_sep|>%s\n%s", filepath, merged)
        table.insert(blocks, {
          filepath = filepath,
          content = content,
          tokens = utils.estimate_tokens(content),
          priority = PRIORITY.OTHER_FILE,
        })
      end
    end
  end

  -- 2. Build SAME file block (higher priority - kept if possible)
  local same_file_block = self:build_same_file_block(context, all_snippets[context.filepath] or {})
  if same_file_block then
    table.insert(blocks, same_file_block)
  end

  -- 3. Sort by priority (highest first) for budget trimming
  table.sort(blocks, function(a, b)
    return a.priority > b.priority
  end)

  -- 4. Add blocks until we hit the token budget
  local result = {}
  local total_tokens = 0

  for _, block in ipairs(blocks) do
    if max_tokens > 0 and total_tokens + block.tokens > max_tokens then
      -- Would exceed budget, skip this block (and all remaining lower priority)
      break
    end
    table.insert(result, block)
    total_tokens = total_tokens + block.tokens
  end

  -- 5. Re-sort for prompt order: other files first, then same file
  table.sort(result, function(a, b)
    return a.priority < b.priority
  end)

  -- 6. Build final content
  local parts = {}
  for _, block in ipairs(result) do
    table.insert(parts, block.content)
  end

  return table.concat(parts, "\n")
end

--- Build same-file context block (ONE block combining all same-file context)
--- Merges: full-file context (100 lines above) + LSP refs/selection above that range
---@param context BlinkEditContextData
---@param same_file_snippets table[] Snippets from same file (LSP refs, selection)
---@return ContextBlock|nil
function M:build_same_file_block(context, same_file_snippets)
  local cfg = config.get()
  local max_lines_before = cfg.context.same_file.max_lines_before
  local window_start = context.current_window.start_line

  -- Calculate same-file context range
  local context_start = math.max(1, window_start - max_lines_before)
  local context_end = window_start - 1

  -- Collect all snippets to merge into one block
  local snippets_to_merge = {}

  -- 1. Add LSP refs/selection that are ABOVE the context range (rare case)
  for _, snippet in ipairs(same_file_snippets) do
    if snippet.end_line < context_start then
      -- This snippet is entirely above our context range - include it
      table.insert(snippets_to_merge, snippet)
    end
    -- All other cases: skip (within range, overlapping, or below window)
  end

  -- 2. Add same-file context (lines above window) if enabled
  if cfg.context.same_file.enabled and context_end >= context_start and context.full_file_lines then
    local context_lines = {}
    for i = context_start, context_end do
      table.insert(context_lines, context.full_file_lines[i] or "")
    end
    if #context_lines > 0 then
      table.insert(snippets_to_merge, {
        start_line = context_start,
        end_line = context_end,
        lines = context_lines,
      })
    end
  end

  -- 3. If nothing to include, return nil
  if #snippets_to_merge == 0 then
    return nil
  end

  -- 4. Merge all snippets into one block
  local merged = utils.merge_snippets(snippets_to_merge)
  if merged == "" then
    return nil
  end

  local content = string.format("<|file_sep|>%s\n%s", context.filepath, merged)
  return {
    filepath = context.filepath,
    content = content,
    tokens = utils.estimate_tokens(content),
    priority = PRIORITY.SAME_FILE,
  }
end

-- =============================================================================
-- History Building Methods
-- =============================================================================

--- Build diff section from history entries
--- Note: History is already trimmed by context_manager based on max_history_tokens
---@param history BlinkEditHistoryEntry[]
---@return string
function M:build_diff_section(history)
  -- Filter out empty entries
  local filtered = self:filter_empty_history(history)
  if #filtered == 0 then
    return ""
  end

  local parts = {}
  for _, entry in ipairs(filtered) do
    local diff_block = string.format(
      "<|file_sep|>%s.diff\noriginal:\n%s\nupdated:\n%s",
      entry.filepath or "[scratch]",
      entry.original or "",
      entry.updated or ""
    )
    table.insert(parts, diff_block)
  end

  return table.concat(parts, "\n")
end

return M
