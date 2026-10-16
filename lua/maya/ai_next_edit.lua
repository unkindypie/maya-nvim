local M = { initialized = false }
M.default_model = "hf.co/sweepai/sweep-next-edit-1.5B:Q8_0"
function M.cancel()
  if M.initialized then
    require("blink-edit").cancel()
  end
end
function M.setup(ai)
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
    debounce_ms = 400,
    cancel_in_flight = true,
    enabled_predicate = function()
      local mode = vim.api.nvim_get_mode().mode
      local cmp = package.loaded["blink.cmp"]
      return ai.provider == "ollama"
        and ai.local_mode ~= "completion-only"
        and ai.eligible()
        and (ai.local_mode == "single" or mode == "n")
        and not (cmp and cmp.is_visible())
    end,
    trigger_modes = ai.local_mode == "single" and { "i", "n" } or { "n" },
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
    ui = { suppress_lsp_floats = false, progress = false },
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
  if M.visible() then
    require("blink-edit").accept()
    return true
  end
  return false
end
function M.trigger()
  if M.initialized then
    require("blink-edit").trigger({ force = true })
  end
end
return M
