--- Generic provider for blink-edit
--- Template-based prompt building for custom models
---
--- Supports all context types with configurable template.
---
--- Template variables:
--- - {{filepath}} - Relative file path
--- - {{filetype}} - Vim filetype
--- - {{baseline}} - Baseline window content
--- - {{current}} - Current window content
--- - {{history}} - Edit history (format configurable)
--- - {{diagnostics}} - LSP diagnostics
--- - {{context}} - Combined full-file + LSP + selection context
--- - {{selection}} - Visual selection content
---
--- Configuration options:
--- - prompt_template: Custom template string
--- - history_format: "sweep" or "unified_diff"
--- - use_history: boolean (default: true)
--- - use_diagnostics: boolean (default: false)
--- - use_same_file: boolean (default: false)
--- - use_lsp: boolean (default: false)
--- - use_selection: boolean (default: false)

local BaseProvider = require("blink-edit.providers.base")

local M = setmetatable({}, { __index = BaseProvider })
M.__index = M

-- =============================================================================
-- Constants
-- =============================================================================

local DEFAULT_TEMPLATE = [[
You are a coding assistant. Apply the next edit.

File: {{filepath}}
Language: {{filetype}}

{{history}}{{context}}Original:
{{baseline}}

Current:
{{current}}

Updated:
]]

-- =============================================================================
-- Constructor
-- =============================================================================

---@param opts? { name?: string, config?: table, global_config?: BlinkEditConfig }
---@return BlinkEditProvider
function M.new(opts)
  opts = opts or {}
  opts.name = "generic"

  local self = BaseProvider.new(opts)
  setmetatable(self, M)

  local cfg = opts.config or {}
  self.prompt_template = cfg.prompt_template
  self.history_format = cfg.history_format or "sweep"

  return self
end

-- =============================================================================
-- Interface Implementation
-- =============================================================================

--- Get provider requirements (configurable via provider config)
---@return BlinkEditProviderRequirements
function M:get_requirements()
  local cfg = self.config or {}

  return {
    needs_history = cfg.use_history ~= false, -- Default: true
    needs_diagnostics = cfg.use_diagnostics == true, -- Default: false
    needs_full_file = cfg.use_same_file == true, -- Default: false
    needs_lsp_definitions = cfg.use_lsp == true, -- Default: false
    needs_lsp_references = cfg.use_lsp == true, -- Default: false
    needs_selection = cfg.use_selection == true, -- Default: false
    local_context_lines = nil,
  }
end

--- Build prompt from context data
---@param context BlinkEditContextData
---@param _limits BlinkEditContextLimits
---@return string|nil prompt
---@return table|nil metadata
---@return string|nil error
function M:build_prompt(context, _limits)
  -- Build history section
  local history_section = self:build_history_section(context.history)

  -- Build diagnostics section
  local diagnostics_section = self:build_diagnostics_section(context.diagnostics, context.filepath)

  -- Build combined context section (full-file + LSP + selection)
  local context_section = self:build_context_section(context)

  -- Build selection section (standalone)
  local selection_section = self:build_selection_section(context.selection)

  -- Template variables
  local vars = {
    filepath = context.filepath,
    filetype = context.filetype,
    baseline = self:format_lines(context.baseline_window.lines),
    current = self:format_lines(context.current_window.lines),
    history = history_section,
    diagnostics = diagnostics_section,
    context = context_section,
    selection = selection_section,
  }

  -- Apply template
  local template = self.prompt_template or DEFAULT_TEMPLATE
  local prompt = self:apply_template(template, vars)

  -- If context exists but template doesn't have {{context}}, prepend it
  local has_context_placeholder = template:find("{{context}}") ~= nil
  if context_section ~= "" and not has_context_placeholder then
    prompt = context_section .. prompt
  end

  local metadata = {
    window_start = context.current_window.start_line,
    window_end = context.current_window.end_line,
    filepath = context.filepath,
  }

  return prompt, metadata, nil
end

--- Get stop tokens (configurable via provider config)
---@return string[]
function M:get_stop_tokens()
  local cfg = self.config or {}
  if cfg.stop_tokens then
    return cfg.stop_tokens
  end
  return { "</s>", "<|endoftext|>", "<|end|>" }
end

-- =============================================================================
-- Private Methods: Section Building
-- =============================================================================

--- Build history section
---@param history BlinkEditHistoryEntry[]
---@return string
function M:build_history_section(history)
  local filtered = self:filter_empty_history(history)
  if #filtered == 0 then
    return ""
  end

  local parts = {}

  if self.history_format == "unified_diff" then
    -- Unified diff format (like Zeta)
    for _, entry in ipairs(filtered) do
      local diff = self:generate_unified_diff(entry.original or "", entry.updated or "")
      if diff ~= "" then
        table.insert(parts, string.format('Edit in "%s":\n```diff\n%s\n```', entry.filepath or "[scratch]", diff))
      end
    end
  else
    -- Sweep format (default)
    for _, entry in ipairs(filtered) do
      table.insert(
        parts,
        string.format(
          "Diff %s:\nOriginal:\n%s\nUpdated:\n%s",
          entry.filepath or "[scratch]",
          entry.original or "",
          entry.updated or ""
        )
      )
    end
  end

  if #parts == 0 then
    return ""
  end

  return "Recent edits:\n" .. table.concat(parts, "\n\n") .. "\n\n"
end

--- Build diagnostics section
---@param diagnostics BlinkEditDiagnostic[]
---@param filepath string
---@return string
function M:build_diagnostics_section(diagnostics, filepath)
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

  return string.format('Diagnostics in "%s":\n%s\n\n', filepath, table.concat(lines, "\n"))
end

--- Build combined context section (full-file + LSP + selection)
---@param context BlinkEditContextData
---@return string
function M:build_context_section(context)
  local parts = {}

  -- Same-file context (above/below window)
  local same_file_ctx = self:build_same_file_context(context)
  if same_file_ctx ~= "" then
    table.insert(parts, same_file_ctx)
  end

  -- LSP definitions
  for _, loc in ipairs(context.lsp_definitions or {}) do
    table.insert(parts, string.format("Definition in %s:\n%s", loc.filepath, self:format_lines(loc.lines)))
  end

  -- LSP references
  for _, loc in ipairs(context.lsp_references or {}) do
    table.insert(parts, string.format("Reference in %s:\n%s", loc.filepath, self:format_lines(loc.lines)))
  end

  -- Selection (if not using standalone {{selection}})
  if context.selection and #(context.selection.lines or {}) > 0 then
    table.insert(
      parts,
      string.format(
        "Selected text in %s:\n%s",
        context.selection.filepath or context.filepath,
        self:format_lines(context.selection.lines)
      )
    )
  end

  if #parts == 0 then
    return ""
  end

  return table.concat(parts, "\n\n") .. "\n\n"
end

--- Build same-file context (above/below window)
---@param context BlinkEditContextData
---@return string
function M:build_same_file_context(context)
  local cfg = self.config or {}
  if not cfg.use_same_file then
    return ""
  end

  local full_lines = context.full_file_lines
  local window_start = context.current_window.start_line
  local window_end = context.current_window.end_line
  local max_lines = cfg.same_file_max_lines or 50

  local parts = {}

  -- Above window
  if window_start > 1 then
    local above_start = math.max(1, window_start - max_lines)
    local above_lines = {}
    for i = above_start, window_start - 1 do
      table.insert(above_lines, full_lines[i] or "")
    end
    if #above_lines > 0 then
      table.insert(
        parts,
        string.format("Context above (lines %d-%d):\n%s", above_start, window_start - 1, self:format_lines(above_lines))
      )
    end
  end

  -- Below window
  if window_end < #full_lines then
    local below_end = math.min(#full_lines, window_end + max_lines)
    local below_lines = {}
    for i = window_end + 1, below_end do
      table.insert(below_lines, full_lines[i] or "")
    end
    if #below_lines > 0 then
      table.insert(
        parts,
        string.format("Context below (lines %d-%d):\n%s", window_end + 1, below_end, self:format_lines(below_lines))
      )
    end
  end

  return table.concat(parts, "\n\n")
end

--- Build selection section (standalone)
---@param selection BlinkEditSelection|nil
---@return string
function M:build_selection_section(selection)
  if not selection or not selection.lines or #selection.lines == 0 then
    return ""
  end

  return string.format(
    "Selected text in %s (lines %d-%d):\n%s\n\n",
    selection.filepath or "[scratch]",
    selection.start_line,
    selection.end_line,
    self:format_lines(selection.lines)
  )
end

--- Apply template with variable substitution
---@param template string
---@param vars table
---@return string
function M:apply_template(template, vars)
  return template:gsub("{{(%w+)}}", function(key)
    return vars[key] or ""
  end)
end

return M
