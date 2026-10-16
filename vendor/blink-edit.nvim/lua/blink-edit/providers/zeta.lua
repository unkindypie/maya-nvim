--- Zeta provider for blink-edit
--- Builds instruction-style prompts for zed-industries/zeta model
---
--- Prompt format:
--- ### Goal:
--- You are an advanced **Next-Edit Prediction Engine**...
---
--- ### Edit History:
--- User edited "file.py":
--- ```diff
--- @@ -1,1 +1,2 @@
--- -old
--- +new
--- ```
---
--- ### Context:                          (OTHER-file refs only)
--- References from "utils.py":
--- ```python
--- def helper():
---     ...
--- ```
---
--- ### LSP Diagnostics:
--- Diagnostics in "file.py":
--- ```diagnostics
--- line 10: [error] Undefined variable 'x' (source: pyright)
--- ```
---
--- ### Code Window:                      (includes same-file context)
--- ```filepath
--- <|start_of_file|>
--- [same-file context above - max_lines_before]
--- <|editable_region_start|>
--- [content]<|user_cursor_is_here|>[content]
--- <|editable_region_end|>
--- [same-file context below - max_lines_after]
--- ```
---
--- ### Response:

local BaseProvider = require("blink-edit.providers.base")
local config = require("blink-edit.config")
local utils = require("blink-edit.utils")

local M = setmetatable({}, { __index = BaseProvider })
M.__index = M

-- =============================================================================
-- Constants
-- =============================================================================

local GOAL_TEXT =
  [[You are an advanced **Next-Edit Prediction Engine**. Your task is not simply to complete code, but to predict the immediate next logical state of the code window.

**Your Inputs:**
You will receive a `Code Window` (with cursor position marked by `<|user_cursor_is_here|>`), `Context`, `Edit History`, and `LSP Diagnostics`.]]

-- Priority levels for context blocks (higher = more important, kept first)
local PRIORITY = {
  OTHER_FILE = 10, -- Other file refs
}

-- =============================================================================
-- Local Helper Functions
-- =============================================================================

--- Get language identifier from filetype
---@param filetype string
---@return string
local function get_language_id(filetype)
  local lang_map = {
    python = "python",
    lua = "lua",
    javascript = "javascript",
    typescript = "typescript",
    typescriptreact = "tsx",
    javascriptreact = "jsx",
    go = "go",
    rust = "rust",
    c = "c",
    cpp = "cpp",
    java = "java",
    ruby = "ruby",
    php = "php",
    sh = "bash",
    bash = "bash",
    zsh = "zsh",
    vim = "vim",
    html = "html",
    css = "css",
    json = "json",
    yaml = "yaml",
    toml = "toml",
    markdown = "markdown",
  }
  return lang_map[filetype] or filetype or ""
end

--- Collect snippets from OTHER files only (not same file)
---@param context BlinkEditContextData
---@return table<string, table[]>
local function collect_other_file_snippets(context)
  local snippets = {}

  -- Add LSP references from OTHER files
  for _, ref in ipairs(context.lsp_references or {}) do
    if ref.filepath and ref.filepath ~= context.filepath and ref.lines and #ref.lines > 0 then
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

  -- Add selection from OTHER files
  local sel = context.selection
  if sel and sel.filepath and sel.filepath ~= context.filepath and sel.lines and #sel.lines > 0 then
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
  opts.name = "zeta"

  local self = BaseProvider.new(opts)
  setmetatable(self, M)

  return self
end

-- =============================================================================
-- Interface Implementation
-- =============================================================================

--- Get provider requirements
--- Zeta needs history, diagnostics, and context (LSP refs, selection, full-file)
---@return BlinkEditProviderRequirements
function M:get_requirements()
  local cfg = self.global_config or config.get()

  return {
    needs_history = true,
    needs_diagnostics = true,
    needs_full_file = cfg.context.same_file.enabled,
    needs_lsp_definitions = false,
    needs_lsp_references = cfg.context.lsp.enabled,
    needs_selection = cfg.context.selection.enabled,
    local_context_lines = nil, -- Not used - we use same_file.max_lines_before/after
  }
end

--- Build prompt from context data
---@param context BlinkEditContextData
---@param limits BlinkEditContextLimits
---@return string|nil prompt
---@return table|nil metadata
---@return string|nil error
function M:build_prompt(context, limits)
  local cfg = self.global_config or config.get()

  -- Validate mode
  if cfg.mode == "completion" then
    return nil, nil, "zeta provider only supports next-edit mode"
  end

  local zeta_cfg = cfg.providers and cfg.providers.zeta or {}
  local use_goal = zeta_cfg.use_instruction_prompt ~= false

  local parts = {}

  -- 1. Goal section
  if use_goal then
    table.insert(parts, "### Goal:")
    table.insert(parts, GOAL_TEXT)
  end

  -- 2. Edit History section (if any)
  local edit_history = self:format_edit_history(context.history)
  if edit_history ~= "" then
    table.insert(parts, "### Edit History:")
    table.insert(parts, edit_history)
  end

  -- 3. Context section (OTHER-file refs only, if any)
  local context_section = self:build_context_section(context, limits.max_context_tokens)
  if context_section ~= "" then
    table.insert(parts, "### Context:")
    table.insert(parts, context_section)
  end

  -- 4. LSP Diagnostics section (if any)
  local diagnostics = self:format_diagnostics(context.diagnostics, context.filepath)
  if diagnostics ~= "" then
    table.insert(parts, "### LSP Diagnostics:")
    table.insert(parts, diagnostics)
  end

  -- 5. Code Window section (includes same-file context)
  table.insert(parts, "### Code Window:")
  table.insert(parts, self:build_code_window(context))

  -- 6. Response marker
  table.insert(parts, "### Response:")

  local prompt = table.concat(parts, "\n\n")

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
  response = self:trim_response(response)

  -- Strip code fences if present in response
  response = response:gsub("^```[^\n]*\n", "")
  response = response:gsub("\n```%s*$", "")

  -- Extract content from editable region
  local content, has_markers = self:extract_editable_region(response)

  if not has_markers and _snapshot_lines and #_snapshot_lines > 0 then
    -- Markerless fallback: treat as completion
    -- The model returned raw text without markers
    -- Just use the content as-is
  end

  return self:split_lines(content), nil
end

--- Get stop tokens
---@return string[]
function M:get_stop_tokens()
  return {
    "\n<|editable_region_end|>",
    "</s>",
    "<|endoftext|>",
  }
end

-- =============================================================================
-- Context Building Methods (OTHER-file refs only)
-- =============================================================================

---@class ZetaContextBlock
---@field filepath string
---@field content string
---@field tokens number
---@field priority number

--- Build context section with OTHER-file refs only
--- Same-file context is now in Code Window
---@param context BlinkEditContextData
---@param max_tokens number
---@return string
function M:build_context_section(context, max_tokens)
  local other_file_snippets = collect_other_file_snippets(context)

  -- Collect context blocks (one per other file)
  ---@type ZetaContextBlock[]
  local blocks = {}

  for filepath, snippets in pairs(other_file_snippets) do
    local merged = utils.merge_snippets(snippets)
    if merged ~= "" then
      local lang = get_language_id(self:get_filetype_for_path(filepath))
      local content = string.format('References from "%s":\n```%s\n%s\n```', filepath, lang, merged)
      table.insert(blocks, {
        filepath = filepath,
        content = content,
        tokens = utils.estimate_tokens(content),
        priority = PRIORITY.OTHER_FILE,
      })
    end
  end

  -- If no blocks, return empty
  if #blocks == 0 then
    return ""
  end

  -- Apply token budget
  local result = {}
  local total_tokens = 0

  for _, block in ipairs(blocks) do
    if max_tokens > 0 and total_tokens + block.tokens > max_tokens then
      break
    end
    table.insert(result, block)
    total_tokens = total_tokens + block.tokens
  end

  -- Build final content
  local parts = {}
  for _, block in ipairs(result) do
    table.insert(parts, block.content)
  end

  return table.concat(parts, "\n\n")
end

--- Get filetype for a filepath (best effort)
---@param filepath string
---@return string
function M:get_filetype_for_path(filepath)
  local ext = filepath:match("%.([^%.]+)$")
  if not ext then
    return ""
  end

  local ext_map = {
    py = "python",
    lua = "lua",
    js = "javascript",
    ts = "typescript",
    tsx = "typescriptreact",
    jsx = "javascriptreact",
    go = "go",
    rs = "rust",
    c = "c",
    cpp = "cpp",
    h = "c",
    hpp = "cpp",
    java = "java",
    rb = "ruby",
    php = "php",
    sh = "bash",
    html = "html",
    css = "css",
    json = "json",
    yaml = "yaml",
    yml = "yaml",
    toml = "toml",
    md = "markdown",
  }

  return ext_map[ext] or ext
end

-- =============================================================================
-- History Building Methods
-- =============================================================================

--- Format history entries as Edit History section with unified diff
---@param history BlinkEditHistoryEntry[]
---@return string
function M:format_edit_history(history)
  local filtered = self:filter_empty_history(history)
  if #filtered == 0 then
    return ""
  end

  local parts = {}
  for _, entry in ipairs(filtered) do
    local diff = self:generate_unified_diff(entry.original or "", entry.updated or "")

    if diff ~= "" then
      local edit_block = string.format('User edited "%s":\n```diff\n%s\n```', entry.filepath or "[scratch]", diff)
      table.insert(parts, edit_block)
    end
  end

  return table.concat(parts, "\n\n")
end

-- =============================================================================
-- Diagnostics Formatting
-- =============================================================================

--- Format diagnostics section
---@param diagnostics BlinkEditDiagnostic[]
---@param filepath string
---@return string
function M:format_diagnostics(diagnostics, filepath)
  if not diagnostics or #diagnostics == 0 then
    return ""
  end

  local lines = {}
  for _, diag in ipairs(diagnostics) do
    local line = string.format("line %d: [%s] %s", diag.line, diag.severity or "info", diag.message or "")
    if diag.source then
      line = line .. string.format(" (source: %s)", diag.source)
    end
    table.insert(lines, line)
  end

  return string.format('Diagnostics in "%s":\n```diagnostics\n%s\n```', filepath, table.concat(lines, "\n"))
end

-- =============================================================================
-- Code Window Building (includes same-file context)
-- =============================================================================

--- Build code window with same-file context and special tokens
--- Uses same_file.max_lines_before/after for context outside editable region
---@param context BlinkEditContextData
---@return string
function M:build_code_window(context)
  local cfg = self.global_config or config.get()
  local max_lines_before = cfg.context.same_file.max_lines_before
  local max_lines_after = cfg.context.same_file.max_lines_after

  local full_lines = context.full_file_lines
  local total_lines = #full_lines
  local window_start = context.current_window.start_line
  local window_end = context.current_window.end_line

  -- Calculate same-file context bounds (outside editable region)
  local context_pre_start = math.max(1, window_start - max_lines_before)
  local context_pre_end = window_start - 1

  local context_post_start = window_end + 1
  local context_post_end = math.min(total_lines, window_end + max_lines_after)

  -- Gather same-file context lines before editable region
  local context_pre_lines = {}
  if context_pre_end >= context_pre_start then
    for i = context_pre_start, context_pre_end do
      table.insert(context_pre_lines, full_lines[i] or "")
    end
  end

  -- Gather same-file context lines after editable region
  local context_post_lines = {}
  if context_post_end >= context_post_start then
    for i = context_post_start, context_post_end do
      table.insert(context_post_lines, full_lines[i] or "")
    end
  end

  -- Build editable region with cursor marker
  local region_parts = self:build_editable_region(context)

  -- Assemble code window
  local window_parts = {}

  -- Code fence with filepath
  table.insert(window_parts, "```" .. context.filepath)

  -- Emit <|start_of_file|> only if code window starts at line 1
  local window_first_line = (#context_pre_lines > 0) and context_pre_start or window_start
  if window_first_line == 1 then
    table.insert(window_parts, "<|start_of_file|>")
  end

  -- Same-file context before editable region
  if #context_pre_lines > 0 then
    table.insert(window_parts, self:format_lines(context_pre_lines))
  end

  -- Editable region
  table.insert(window_parts, "<|editable_region_start|>")
  table.insert(window_parts, self:format_lines(region_parts))
  table.insert(window_parts, "<|editable_region_end|>")

  -- Same-file context after editable region
  if #context_post_lines > 0 then
    table.insert(window_parts, self:format_lines(context_post_lines))
  end

  -- Close code fence
  table.insert(window_parts, "```")

  return table.concat(window_parts, "\n")
end

--- Build editable region content with cursor marker
---@param context BlinkEditContextData
---@return string[]
function M:build_editable_region(context)
  local window_lines = context.current_window.lines
  local window_start = context.current_window.start_line
  local cursor_line = context.cursor.line
  local cursor_col = context.cursor.col

  local cursor_offset = cursor_line - window_start + 1

  -- Clamp cursor offset to valid range
  if cursor_offset < 1 then
    cursor_offset = 1
  elseif cursor_offset > #window_lines and #window_lines > 0 then
    cursor_offset = #window_lines
  end

  local region_parts = {}

  if #window_lines == 0 then
    -- Empty buffer
    table.insert(region_parts, "<|user_cursor_is_here|>")
  else
    -- Lines before cursor line
    for i = 1, cursor_offset - 1 do
      table.insert(region_parts, window_lines[i])
    end

    -- Cursor line with marker
    local current_line = window_lines[cursor_offset] or ""
    local before_cursor = current_line:sub(1, cursor_col)
    local after_cursor = current_line:sub(cursor_col + 1)
    table.insert(region_parts, before_cursor .. "<|user_cursor_is_here|>" .. after_cursor)

    -- Lines after cursor line
    for i = cursor_offset + 1, #window_lines do
      table.insert(region_parts, window_lines[i])
    end
  end

  return region_parts
end

-- =============================================================================
-- Response Parsing
-- =============================================================================

--- Clean up any marker remnants from content
--- Handles both proper markers and malformed ones (with newlines, missing |>, etc.)
---@param content string
---@return string cleaned
local function cleanup_markers(content)
  -- Remove cursor marker (proper and malformed)
  content = content:gsub("<|%s*user_cursor_is_here%s*|?>", "")

  -- Remove editable_region_start marker (proper and malformed)
  -- Handles: <|editable_region_start|>, <|editable_region_start, <|\neditable_region_start|>, etc.
  content = content:gsub("<|%s*\n?%s*editable_region_start%s*|?>\n?", "")

  -- Remove editable_region_end marker (proper and malformed)
  content = content:gsub("\n?<|%s*\n?%s*editable_region_end%s*|?>", "")

  -- Remove start_of_file marker
  content = content:gsub("<|%s*start_of_file%s*|?>\n?", "")

  -- Remove any remaining orphaned <| or |> that might be marker remnants
  content = content:gsub("^<|%s*\n", "")
  content = content:gsub("\n%s*|>$", "")

  -- Handle orphaned marker names on their own line (when <| was on previous line and got stripped)
  -- These patterns catch marker names at the START of content
  content = content:gsub("^%s*editable_region_start%s*|?>\n?", "")
  content = content:gsub("^%s*editable_region_end%s*|?>\n?", "")
  content = content:gsub("^%s*start_of_file%s*|?>\n?", "")
  content = content:gsub("^%s*user_cursor_is_here%s*|?>\n?", "")

  -- Also handle orphaned marker names without |> (just the name and newline)
  content = content:gsub("^%s*editable_region_start%s*\n", "")
  content = content:gsub("^%s*editable_region_end%s*\n?", "")
  content = content:gsub("^%s*start_of_file%s*\n", "")

  return content
end

--- Extract content from editable region in response
---@param response string
---@return string content
---@return boolean has_markers
function M:extract_editable_region(response)
  -- Remove cursor marker from response (proper form)
  local content = response:gsub("<|user_cursor_is_here|>", "")

  local start_marker = "<|editable_region_start|>"
  local end_marker = "<|editable_region_end|>"

  -- Try exact marker matching first
  local start_idx = content:find(start_marker, 1, true)
  if start_idx then
    -- Found proper markers - extract region between them
    content = content:sub(start_idx + #start_marker)
    content = content:gsub("^\n", "")

    local end_idx = content:find("\n" .. end_marker, 1, true)
    if not end_idx then
      end_idx = content:find(end_marker, 1, true)
    end

    if end_idx then
      content = content:sub(1, end_idx - 1)
    end

    -- Clean up any remaining marker remnants
    content = cleanup_markers(content)
    return content, true
  end

  -- Try flexible pattern matching for malformed markers
  -- Pattern matches: <| followed by optional whitespace/newline, then editable_region_start
  local start_pattern = "<|%s*\n?%s*editable_region_start"
  local start_pos = content:find(start_pattern)
  if start_pos then
    -- Find where the marker ends (look for |> or newline after marker name)
    local after_start = content:sub(start_pos)
    local marker_end = after_start:find("|?>%s*\n") or after_start:find("\n")
    if marker_end then
      content = content:sub(start_pos + marker_end)
    end

    -- Find end marker (flexible pattern)
    local end_pattern = "<|%s*\n?%s*editable_region_end"
    local end_pos = content:find(end_pattern)
    if end_pos then
      content = content:sub(1, end_pos - 1)
    end

    -- Clean up any remaining marker remnants
    content = cleanup_markers(content)
    return content, true
  end

  -- No markers found - markerless response, still clean up just in case
  content = cleanup_markers(content)
  return content, false
end

return M
