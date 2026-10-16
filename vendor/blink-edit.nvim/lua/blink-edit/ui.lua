--- UI components for blink-edit (Folke-style)
--- Provides status popup and in-flight progress indicator

local M = {}

local config = require("blink-edit.config")
local state = require("blink-edit.core.state")
local backend = require("blink-edit.backends")

-- =============================================================================
-- Constants
-- =============================================================================

local LOGO = {
  [[██████╗ ██╗     ██╗███╗   ██╗██╗  ██╗    ███████╗██████╗ ██╗████████╗]],
  [[██╔══██╗██║     ██║████╗  ██║██║ ██╔╝    ██╔════╝██╔══██╗██║╚══██╔══╝]],
  [[██████╔╝██║     ██║██╔██╗ ██║█████╔╝     █████╗  ██║  ██║██║   ██║   ]],
  [[██╔══██╗██║     ██║██║╚██╗██║██╔═██╗     ██╔══╝  ██║  ██║██║   ██║   ]],
  [[██████╔╝███████╗██║██║ ╚████║██║  ██╗    ███████╗██████╔╝██║   ██║   ]],
  [[╚═════╝ ╚══════╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝    ╚══════╝╚═════╝ ╚═╝   ╚═╝   ]],
}

-- Note: Use display width, not byte length, for Unicode logo
local LOGO_WIDTH = 69 -- vim.fn.strdisplaywidth(LOGO[1])
local POPUP_WIDTH = LOGO_WIDTH + 8 -- padding (77)
local CONTENT_PADDING = 4 -- left padding to center content (POPUP_WIDTH - LOGO_WIDTH) / 2

-- =============================================================================
-- Float Class (à la lazy.nvim)
-- =============================================================================

---@class BlinkEditFloat
---@field buf number|nil
---@field win number|nil
---@field opts table
local Float = {}
Float.__index = Float

---@param opts? table
---@return BlinkEditFloat
function Float.new(opts)
  local self = setmetatable({}, Float)
  self.opts = vim.tbl_deep_extend("force", {
    width = 40,
    height = 12,
    border = "rounded",
    title = nil,
    title_pos = "center",
    relative = "editor",
    style = "minimal",
    focusable = true,
    zindex = 50,
    row = nil, -- nil = centered
    col = nil, -- nil = centered
  }, opts or {})
  return self
end

function Float:layout()
  local width = self.opts.width
  local height = self.opts.height

  -- Clamp to editor size
  width = math.min(width, vim.o.columns - 4)
  height = math.min(height, vim.o.lines - 4)

  -- Calculate position (centered by default)
  local row = self.opts.row or math.floor((vim.o.lines - height) / 2)
  local col = self.opts.col or math.floor((vim.o.columns - width) / 2)

  return {
    width = width,
    height = height,
    row = row,
    col = col,
  }
end

function Float:mount()
  if self:is_valid() then
    return
  end

  -- Create buffer
  self.buf = vim.api.nvim_create_buf(false, true)
  vim.bo[self.buf].buftype = "nofile"
  vim.bo[self.buf].bufhidden = "wipe"
  vim.bo[self.buf].swapfile = false

  -- Calculate layout
  local layout = self:layout()

  -- Window options
  local win_opts = {
    relative = self.opts.relative,
    width = layout.width,
    height = layout.height,
    row = layout.row,
    col = layout.col,
    style = self.opts.style,
    border = self.opts.border,
    zindex = self.opts.zindex,
    focusable = self.opts.focusable,
  }

  if self.opts.title then
    win_opts.title = " " .. self.opts.title .. " "
    win_opts.title_pos = self.opts.title_pos
  end

  -- Create window
  self.win = vim.api.nvim_open_win(self.buf, self.opts.focusable, win_opts)

  -- Window options
  vim.wo[self.win].conceallevel = 3
  vim.wo[self.win].foldenable = false
  vim.wo[self.win].spell = false
  vim.wo[self.win].wrap = false
  vim.wo[self.win].cursorline = false
  vim.wo[self.win].number = false
  vim.wo[self.win].relativenumber = false
  vim.wo[self.win].signcolumn = "no"
  vim.wo[self.win].winhighlight = "Normal:BlinkEditNormal,FloatBorder:BlinkEditBorder,FloatTitle:BlinkEditTitle"

  -- Setup close handlers
  self:on("WinClosed", function()
    self:close()
  end, { pattern = tostring(self.win) })

  if self.opts.focusable then
    self:on("BufLeave", function()
      vim.schedule(function()
        self:close()
      end)
    end)
  end
end

---@param events string|string[]
---@param fn function
---@param opts? table
function Float:on(events, fn, opts)
  opts = opts or {}
  opts.callback = fn
  if not opts.pattern then
    opts.buffer = self.buf
  end
  vim.api.nvim_create_autocmd(events, opts)
end

---@param key string
---@param fn function
---@param desc? string
function Float:on_key(key, fn, desc)
  vim.keymap.set("n", key, function()
    fn(self)
  end, { buffer = self.buf, nowait = true, desc = desc })
end

function Float:is_valid()
  return self.win and vim.api.nvim_win_is_valid(self.win)
end

function Float:close()
  if self.win and vim.api.nvim_win_is_valid(self.win) then
    vim.api.nvim_win_close(self.win, true)
  end
  self.win = nil
  self.buf = nil
end

---@param lines string[]
function Float:set_lines(lines)
  if not self.buf or not vim.api.nvim_buf_is_valid(self.buf) then
    return
  end
  vim.bo[self.buf].modifiable = true
  vim.api.nvim_buf_set_lines(self.buf, 0, -1, false, lines)
  vim.bo[self.buf].modifiable = false
end

---@param line_num number 0-indexed
---@param text string
function Float:set_line(line_num, text)
  if not self.buf or not vim.api.nvim_buf_is_valid(self.buf) then
    return
  end
  vim.bo[self.buf].modifiable = true
  vim.api.nvim_buf_set_lines(self.buf, line_num, line_num + 1, false, { text })
  vim.bo[self.buf].modifiable = false
end

-- =============================================================================
-- Highlights
-- =============================================================================

local function setup_highlights()
  local links = {
    BlinkEditNormal = "NormalFloat",
    BlinkEditBorder = "FloatBorder",
    BlinkEditTitle = "FloatTitle",
    BlinkEditLogo = "Special",
    BlinkEditLabel = "Comment",
    BlinkEditValue = "Normal",
    BlinkEditOk = "DiagnosticOk",
    BlinkEditWarn = "DiagnosticWarn",
    BlinkEditError = "DiagnosticError",
    BlinkEditProgress = "Comment",
  }

  for name, link in pairs(links) do
    vim.api.nvim_set_hl(0, name, { link = link, default = true })
  end
end

-- =============================================================================
-- LSP Float Suppression
-- =============================================================================

--- Close active LSP-related floating windows
function M.close_lsp_floats()
  local cfg = config.get()
  if not cfg.ui or cfg.ui.suppress_lsp_floats ~= true then
    return
  end

  for _, win in ipairs(vim.api.nvim_list_wins()) do
    if vim.api.nvim_win_is_valid(win) then
      local win_cfg = vim.api.nvim_win_get_config(win)
      if win_cfg and win_cfg.relative ~= "" then
        local is_lsp = false
        local ok_preview, preview = pcall(vim.api.nvim_win_get_var, win, "lsp_floating_preview")
        if ok_preview and preview then
          is_lsp = true
        end
        local ok_diag = pcall(vim.api.nvim_win_get_var, win, "diagnostic")
        if ok_diag then
          is_lsp = true
        end
        if is_lsp then
          pcall(vim.api.nvim_win_close, win, true)
        end
      end
    end
  end
end

-- =============================================================================
-- Helper Functions
-- =============================================================================

---@param text string
---@return string
local function pad_content(text)
  -- All content gets consistent left padding to align with logo
  return string.rep(" ", CONTENT_PADDING) .. text
end

-- Center text in a given width (utility, currently unused but kept for future use)
---@param text string
---@param width number
---@return string
local function center(text, width)
  local text_width = vim.fn.strdisplaywidth(text)
  local padding = math.floor((width - text_width) / 2)
  if padding < 0 then
    padding = 0
  end
  return string.rep(" ", padding) .. text
end
local _ = center -- silence unused warning

---@param label string
---@param value string
---@param label_width number
---@return string
local function format_row(label, value, label_width)
  local padding = label_width - #label
  return label .. string.rep(" ", padding) .. value
end

---@param text string
---@param content_width number
---@return string
local function center_in_content(text, content_width)
  -- Center text within the content area, then add left padding
  local text_width = vim.fn.strdisplaywidth(text)
  local inner_padding = math.floor((content_width - text_width) / 2)
  if inner_padding < 0 then
    inner_padding = 0
  end
  return string.rep(" ", CONTENT_PADDING + inner_padding) .. text
end

-- =============================================================================
-- Health Check
-- =============================================================================

---@param callback fun(status: string, message: string)
local function check_health(callback)
  local timeout_timer = nil
  local completed = false

  -- Set 2 second timeout
  timeout_timer = vim.defer_fn(function()
    if not completed then
      completed = true
      callback("timeout", "request timed out")
    end
  end, 2000)

  -- Run health check
  backend.health_check(function(available, message)
    if completed then
      return
    end
    completed = true

    if timeout_timer then
      timeout_timer:stop()
    end

    if available then
      callback("healthy", message or "connected")
    else
      callback("error", message or "connection failed")
    end
  end)
end

-- =============================================================================
-- Status Popup
-- =============================================================================

---@type BlinkEditFloat|nil
local status_float = nil

---@type number|nil  -- Line index for server status (0-indexed)
local server_status_line = nil

local function refresh_health()
  if not status_float or not status_float:is_valid() then
    return
  end

  -- Update to "checking..."
  local checking_row = pad_content(format_row("Server", "checking...", 14))
  status_float:set_line(server_status_line, checking_row)

  -- Apply highlight
  local ns = vim.api.nvim_create_namespace("blink_edit_status")
  vim.api.nvim_buf_clear_namespace(status_float.buf, ns, server_status_line, server_status_line + 1)

  local line_content = checking_row
  local label_start = line_content:find("Server") - 1
  local label_end = label_start + 6
  vim.api.nvim_buf_add_highlight(status_float.buf, ns, "BlinkEditLabel", server_status_line, label_start, label_end)

  local value_start = line_content:find("checking") - 1
  vim.api.nvim_buf_add_highlight(status_float.buf, ns, "BlinkEditWarn", server_status_line, value_start, -1)

  -- Run async health check
  check_health(function(status, message)
    vim.schedule(function()
      if not status_float or not status_float:is_valid() then
        return
      end

      local display_value = status == "healthy" and "healthy" or (status .. ": " .. message)
      local row = pad_content(format_row("Server", display_value, 14))
      status_float:set_line(server_status_line, row)

      -- Apply highlight
      local hl = status == "healthy" and "BlinkEditOk" or "BlinkEditError"
      vim.api.nvim_buf_clear_namespace(status_float.buf, ns, server_status_line, server_status_line + 1)

      local content = row
      local l_start = content:find("Server") - 1
      local l_end = l_start + 6
      vim.api.nvim_buf_add_highlight(status_float.buf, ns, "BlinkEditLabel", server_status_line, l_start, l_end)

      local v_start = content:find(status == "healthy" and "healthy" or status) - 1
      vim.api.nvim_buf_add_highlight(status_float.buf, ns, hl, server_status_line, v_start, -1)
    end)
  end)
end

--- Show status popup
function M.status()
  setup_highlights()

  -- Close existing
  if status_float and status_float:is_valid() then
    status_float:close()
    status_float = nil
    return
  end

  local cfg = config.get()
  local bufnr = vim.api.nvim_get_current_buf()

  -- Build content
  local lines = {}

  -- Empty line for top padding
  table.insert(lines, "")

  -- Logo (left-padded to align with content)
  for _, logo_line in ipairs(LOGO) do
    table.insert(lines, pad_content(logo_line))
  end

  -- Empty line after logo
  table.insert(lines, "")

  -- Status data
  local data = {
    { "Provider", cfg.llm.provider },
    { "Backend", cfg.llm.backend },
    { "Model", cfg.llm.model },
    { "URL", cfg.llm.url:gsub("^https?://", "") },
    { "", "" }, -- separator
    { "Server", "checking..." },
    { "In-flight", state.is_in_flight(bufnr) and "yes" or "no" },
    { "Prediction", state.has_prediction(bufnr) and "visible" or "none" },
    { "History", tostring(state.get_history_count(bufnr)) .. " entries" },
  }

  -- Track server status line
  local server_line_offset = #lines

  for i, row in ipairs(data) do
    if row[1] == "" then
      table.insert(lines, "")
    else
      table.insert(lines, pad_content(format_row(row[1], row[2], 14)))
      if row[1] == "Server" then
        server_status_line = #lines - 1 -- 0-indexed
      end
    end
  end

  -- Empty line before footer
  table.insert(lines, "")

  -- Footer (centered within content area)
  table.insert(lines, center_in_content("r refresh · q close", LOGO_WIDTH))

  -- Create float
  status_float = Float.new({
    width = POPUP_WIDTH,
    height = #lines,
  })
  status_float:mount()
  status_float:set_lines(lines)

  -- Apply highlights
  local ns = vim.api.nvim_create_namespace("blink_edit_status")

  -- Logo highlights
  for i = 1, #LOGO do
    vim.api.nvim_buf_add_highlight(status_float.buf, ns, "BlinkEditLogo", i, 0, -1)
  end

  -- Data row highlights
  local data_start_line = #LOGO + 2 -- 1 top padding + logo lines + 1 empty
  for i, row in ipairs(data) do
    if row[1] ~= "" then
      local line_idx = data_start_line + i - 1
      local line_content = lines[line_idx + 1]

      -- Find label position
      local label_start = line_content:find(row[1])
      if label_start then
        label_start = label_start - 1 -- 0-indexed
        local label_end = label_start + #row[1]
        vim.api.nvim_buf_add_highlight(status_float.buf, ns, "BlinkEditLabel", line_idx, label_start, label_end)
      end

      -- Find value position and apply color
      local value_hl = "BlinkEditValue"
      if row[1] == "Server" then
        value_hl = "BlinkEditWarn" -- Will be updated by health check
      elseif row[1] == "In-flight" then
        value_hl = row[2] == "yes" and "BlinkEditWarn" or "BlinkEditOk"
      elseif row[1] == "Prediction" then
        value_hl = row[2] == "visible" and "BlinkEditOk" or "BlinkEditLabel"
      end

      local value_start = line_content:find(row[2], 1, true)
      if value_start then
        value_start = value_start - 1
        vim.api.nvim_buf_add_highlight(status_float.buf, ns, value_hl, line_idx, value_start, -1)
      end
    end
  end

  -- Footer highlight
  local footer_line = #lines - 1
  vim.api.nvim_buf_add_highlight(status_float.buf, ns, "BlinkEditLabel", footer_line, 0, -1)

  -- Keymaps
  status_float:on_key("q", function(f)
    f:close()
  end, "Close")
  status_float:on_key("<Esc>", function(f)
    f:close()
  end, "Close")
  status_float:on_key("<CR>", function(f)
    f:close()
  end, "Close")
  status_float:on_key("r", function(_)
    refresh_health()
  end, "Refresh health")

  -- Start health check
  refresh_health()
end

-- =============================================================================
-- Progress Indicator
-- =============================================================================

---@type BlinkEditFloat|nil
local progress_float = nil

--- Show progress indicator (call when request starts)
function M.show_progress()
  local cfg = config.get()
  if cfg.ui and cfg.ui.progress == false then
    return
  end

  setup_highlights()

  -- Already showing
  if progress_float and progress_float:is_valid() then
    return
  end

  local text = "thinking..."

  progress_float = Float.new({
    width = #text + 2,
    height = 1,
    border = "rounded",
    relative = "editor",
    row = vim.o.lines - 4,
    col = vim.o.columns - #text - 6,
    focusable = false,
    zindex = 40,
  })
  progress_float:mount()
  progress_float:set_lines({ " " .. text })

  -- Apply highlight
  local ns = vim.api.nvim_create_namespace("blink_edit_progress")
  vim.api.nvim_buf_add_highlight(progress_float.buf, ns, "BlinkEditProgress", 0, 0, -1)
end

--- Hide progress indicator (call when request completes)
function M.hide_progress()
  if progress_float then
    progress_float:close()
    progress_float = nil
  end
end

--- Check if progress is visible
---@return boolean
function M.is_progress_visible()
  return progress_float ~= nil and progress_float:is_valid()
end

return M
