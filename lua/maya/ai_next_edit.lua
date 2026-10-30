-- Cursortab owns requests, debounce, streaming, previews and acceptance.
local M = { initialized = false, state = { state = "Idle", pending = false } }
local generation = 0
local dismissed
function M.cancel()
  generation = generation + 1
  if M.initialized then
    require("cursortab.daemon").set_enabled(false)
    require("cursortab.events").clear_all_completions()
  end
  M.state = { state = "Idle", pending = false }
end
function M.dismiss()
  dismissed = { vim.api.nvim_get_current_buf(), vim.api.nvim_buf_get_changedtick(0) }
  M.cancel()
end
local function eligible(ai)
  local cmp = package.loaded["blink.cmp"]
  return ai.provider ~= "off"
    and ai.eligible()
    and not (cmp and cmp.get_selected_item())
    and not vim.deep_equal(
      dismissed,
      { vim.api.nvim_get_current_buf(), vim.api.nvim_buf_get_changedtick(0) }
    )
end
function M.setup(ai)
  if M.initialized then
    require("cursortab.daemon").stop_daemon()
  end
  dismissed = nil
  local user = require("maya.user")
  require("cursortab").setup({
    enabled = true,
    contribute_data = false,
    -- Each editor owns its daemon; disabling one editor cannot affect another.
    state_dir = vim.fn.stdpath("state") .. "/cursortab/" .. vim.fn.getpid(),
    debug = { immediate_shutdown = true },
    keymaps = { accept = false, partial_accept = false, trigger = false },
    enabled_predicate = function()
      return eligible(ai)
    end,
    source_context = function()
      return require("maya.ai_context").get({ focused = true })
    end,
    behavior = {
      text_change_debounce = user.get("ai_completion_debounce_ms"),
      idle_completion_delay = user.get("ai_next_edit_debounce_ms"),
    },
    provider = ai.provider == "copilot" and { type = "copilot", completion_timeout = 10000 } or {
      type = ai.engine,
      url = ai.endpoint,
      model = ai.model,
      context_size = ai.context_size,
      max_tokens = 512,
      temperature = 0,
      completion_timeout = 10000,
      privacy_mode = true,
    },
  })
  M.initialized = true
  require("maya.ai_context").refresh()
end
function M.visible()
  return M.initialized
    and (
      require("cursortab.ui").has_completion() or require("cursortab.ui").has_cursor_prediction()
    )
end
function M.pending()
  return M.state.pending
end
function M.status()
  if M.visible() then
    return "suggestion ready"
  end
  if M.pending() then
    return "waiting for model response"
  end
  return dismissed and "dismissed; waiting for the next edit"
    or "ready; edit to request a suggestion"
end
function M.accept(partial)
  if not M.visible() or (partial and not require("cursortab.ui").has_completion()) then
    return false
  end
  local expected, buf, tick =
    generation, vim.api.nvim_get_current_buf(), vim.api.nvim_buf_get_changedtick(0)
  local cursor, mode = vim.api.nvim_win_get_cursor(0), vim.api.nvim_get_mode().mode
  vim.schedule(function()
    if
      expected == generation
      and buf == vim.api.nvim_get_current_buf()
      and tick == vim.api.nvim_buf_get_changedtick(0)
      and M.visible()
      and vim.deep_equal(cursor, vim.api.nvim_win_get_cursor(0))
      and mode == vim.api.nvim_get_mode().mode
    then
      if partial then
        require("cursortab").partial_accept()
      else
        require("cursortab").accept()
      end
    end
  end)
  return true
end
function M.trigger()
  local ai = require("maya.ai")
  if not M.initialized or ai.provider == "off" or M.visible() or M.pending() then
    return
  end
  dismissed = nil
  if eligible(ai) then
    require("cursortab.daemon").set_enabled(true)
    require("cursortab.daemon").send_event("trigger_completion")
  end
end
function M.watch(ai)
  local group = vim.api.nvim_create_augroup("MayaAIContext", { clear = true })
  vim.api.nvim_create_autocmd({
    "TextChanged",
    "TextChangedI",
    "TextChangedP",
    "CursorMoved",
    "CursorMovedI",
    "InsertEnter",
    "BufEnter",
    "LspAttach",
  }, {
    group = group,
    callback = function()
      if not M.initialized then
        return
      end
      if eligible(ai) then
        dismissed = nil
        require("cursortab.daemon").set_enabled(true)
        require("maya.ai_context").refresh()
      else
        M.cancel()
      end
    end,
  })
  vim.api.nvim_create_autocmd({ "BufLeave", "LspDetach" }, {
    group = group,
    callback = function()
      ai.cancel()
    end,
  })
  vim.api.nvim_create_autocmd("User", {
    group = group,
    pattern = "CursortabStateChanged",
    callback = function(e)
      M.state = e.data
    end,
  })
end
return M
