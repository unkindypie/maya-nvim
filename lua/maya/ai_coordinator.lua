-- One scheduler owns local generation; a visible preview has no expiry.
local M = {}
local timer, ai, identity, suppressed, completed, accepted
local generation = 0
local function snapshot()
  return {
    vim.api.nvim_get_current_buf(),
    vim.api.nvim_buf_get_changedtick(0),
    vim.api.nvim_win_get_cursor(0),
    vim.api.nvim_get_mode().mode,
  }
end
local function engines()
  local qwen = ai.initialized.ollama and require("minuet.virtualtext").action
  local sweep = require("maya.ai_next_edit")
  return qwen, sweep
end
function M.cancel()
  generation = generation + 1
  if timer and not timer:is_closing() then
    timer:stop()
    timer:close()
  end
  timer = nil
  identity = nil
end
function M.dismiss()
  M.cancel()
  suppressed = snapshot()
end
local function schedule(delay, callback)
  if timer and not timer:is_closing() then
    timer:stop()
    timer:close()
  end
  local expected = generation
  local scheduled
  scheduled = vim.defer_fn(function()
    if generation ~= expected or timer ~= scheduled then
      return
    end
    timer = nil
    callback()
  end, delay)
  timer = scheduled
end
local function eligible()
  local mode = vim.api.nvim_get_mode().mode
  local cmp = package.loaded["blink.cmp"]
  return ai.provider == "ollama"
    and ai.eligible()
    and (mode == "i" or mode == "n")
    and not (cmp and cmp.get_selected_item())
end
local function poll()
  if not identity or not vim.deep_equal(identity, snapshot()) or not eligible() or suppressed then
    return
  end
  local qwen, sweep = engines()
  if (qwen and qwen.is_visible()) or sweep.visible() then
    return
  end
  if (qwen and qwen.is_pending and qwen.is_pending()) or sweep.pending() then
    schedule(25, poll)
    return
  end
  if completed then
    return
  end
  completed = true
  if ai.local_mode ~= "completion-only" then
    sweep.request()
  end
end
function M.activity(edit)
  if not ai then
    return
  end
  local next_identity = snapshot()
  if identity and vim.deep_equal(identity, next_identity) then
    return
  end
  local old = identity
  local changed = edit or (old and (old[1] ~= next_identity[1] or old[2] ~= next_identity[2]))
  local after_accept = accepted
  accepted = false
  ai.cancel()
  identity = next_identity
  completed = false
  if
    changed
    and (not suppressed or suppressed[1] ~= next_identity[1] or suppressed[2] ~= next_identity[2])
  then
    suppressed = false
  end
  if suppressed or not eligible() then
    return
  end
  require("maya.ai_context").refresh()
  local user = require("maya.user")
  local sweep_delay = user.get("ai_next_edit_debounce_ms")
  local started = vim.uv.now()
  if not after_accept and next_identity[4] == "i" and ai.local_mode ~= "single" then
    schedule(user.get("ai_completion_debounce_ms"), function()
      if not identity or not vim.deep_equal(identity, snapshot()) or not eligible() then
        return
      end
      local qwen = engines()
      if qwen and qwen.trigger then
        qwen.trigger()
      end
      schedule(math.max(0, sweep_delay - (vim.uv.now() - started)), poll)
    end)
  else
    schedule(sweep_delay, poll)
  end
end
function M.accepted()
  accepted = true
  M.cancel()
  vim.schedule(function()
    M.activity(true)
  end)
end
function M.inline_action(name)
  local qwen, sweep = engines()
  if sweep.visible() or (qwen.is_pending and qwen.is_pending()) then
    return
  end
  M.cancel()
  sweep.cancel()
  identity = snapshot()
  completed = false
  qwen[name]()
  schedule(require("maya.user").get("ai_next_edit_debounce_ms"), poll)
end
function M.trigger()
  local qwen, sweep = engines()
  if (qwen and qwen.is_visible()) or sweep.visible() then
    return
  end
  M.cancel()
  if qwen then
    qwen.cancel()
  end
  sweep.cancel()
  suppressed = false
  identity = snapshot()
  completed = true
  if eligible() then
    require("maya.ai_next_edit").request()
  end
end
function M.setup(provider)
  ai = provider
  local group = vim.api.nvim_create_augroup("MayaAIScheduler", { clear = true })
  vim.api.nvim_create_autocmd({ "TextChangedI", "TextChangedP", "TextChanged" }, {
    group = group,
    callback = function()
      M.activity(true)
    end,
  })
  vim.api.nvim_create_autocmd(
    { "CursorMovedI", "CursorMoved", "InsertEnter", "InsertLeave", "ModeChanged", "BufEnter" },
    {
      group = group,
      callback = function()
        M.activity(false)
      end,
    }
  )
  vim.api.nvim_create_autocmd({ "BufLeave", "LspDetach" }, {
    group = group,
    callback = function()
      ai.cancel()
    end,
  })
end
return M
