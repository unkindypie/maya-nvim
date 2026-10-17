local M = { initialized = false }
local generation = 0
M.default_model = "hf.co/sweepai/sweep-next-edit-1.5B:Q8_0"
function M.cancel()
  generation = generation + 1
  if M.initialized then
    require("blink-edit").cancel()
  end
end
function M.setup(ai)
  generation = generation + 1
  local edit = require("blink-edit")
  if M.initialized then
    edit.reset()
  end
  edit.setup({
    llm = {
      backend = "ollama",
      provider = "sweep",
      url = ai.endpoint,
      model = ai.next_edit_model,
      max_tokens = 512,
      timeout_ms = 10000,
    },
    backends = { ollama = { num_ctx = 4096 } },
    mode = "next-edit",
    external_scheduler = true,
    prediction_filter = require("maya.ai_edit_filter").accept,
    on_dismiss = function()
      require("maya.ai_coordinator").dismiss()
    end,
    source_context = function()
      return require("maya.ai_context").get()
    end,
    debounce_ms = 650,
    cancel_in_flight = true,
    enabled_predicate = function()
      local mode = vim.api.nvim_get_mode().mode
      local cmp = package.loaded["blink.cmp"]
      return ai.provider == "ollama"
        and ai.local_mode ~= "completion-only"
        and ai.eligible()
        and (mode == "i" or mode == "n")
        and not (cmp and cmp.get_selected_item())
    end,
    trigger_modes = { "i", "n" },
    context = {
      max_tokens = 512,
      history = { enabled = true, max_items = 3, max_tokens = 512 },
      lsp = {
        enabled = true,
        max_references = 2,
        timeout_ms = 1000,
        lines_before = 3,
        lines_after = 16,
      },
      same_file = { enabled = true, max_lines_before = 20, max_lines_after = 20 },
    },
    keymaps = {
      insert = { accept = false, accept_line = false, clear = false, reject = false },
      normal = { accept = false, accept_line = false },
    },
    normal_mode = { enabled = true, debounce_ms = 800 },
    ui = { suppress_lsp_floats = false, progress = false, show_model = true },
    highlight = {
      addition = { link = "DiffAdd" },
      deletion = { link = "DiffDelete" },
      preview = { link = "Comment" },
      jump = { link = "DiagnosticHint" },
    },
    prefetch = { enabled = false },
    use_daemon = false,
    daemon_auto_start = false,
  })
  M.initialized = true
  -- setup initializes the plugin; provider predicates control activation quietly.
  vim.g.blink_edit_enabled = true
end
function M.visible()
  return M.initialized and require("blink-edit").has_prediction()
end
function M.accept()
  if not M.visible() then
    return false
  end
  local expected = generation
  local buf = vim.api.nvim_get_current_buf()
  local tick = vim.api.nvim_buf_get_changedtick(buf)
  local cursor = vim.api.nvim_win_get_cursor(0)
  local mode = vim.api.nvim_get_mode().mode
  local function valid()
    return expected == generation
      and vim.api.nvim_buf_is_valid(buf)
      and vim.api.nvim_get_current_buf() == buf
      and vim.api.nvim_buf_get_changedtick(buf) == tick
      and vim.deep_equal(vim.api.nvim_win_get_cursor(0), cursor)
      and vim.api.nvim_get_mode().mode == mode
      and M.visible()
  end
  -- Completion expression mappings run under textlock.
  vim.schedule(function()
    if not valid() then
      return
    end
    -- Close the typing undo block without changing either option value.
    vim.cmd("let &g:undolevels = &g:undolevels")
    if not valid() then
      return
    end
    require("blink-edit").accept()
    if vim.api.nvim_buf_get_changedtick(buf) ~= tick then
      vim.cmd("let &g:undolevels = &g:undolevels")
      require("maya.ai_coordinator").accepted()
    end
  end)
  return true
end
function M.pending()
  return M.initialized and require("blink-edit").is_pending and require("blink-edit").is_pending()
end
function M.trigger()
  require("maya.ai_coordinator").trigger()
end
function M.request()
  generation = generation + 1
  if M.initialized then
    require("blink-edit").trigger({ force = true })
  end
end
return M
