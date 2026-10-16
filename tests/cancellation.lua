local edit = require("blink-edit")
local callbacks, canceled = {}, {}
local backend = require("blink-edit.backends")
backend.complete = function(_, callback)
  callbacks[#callbacks + 1] = callback
  return #callbacks
end
require("blink-edit.transport").cancel = function(id)
  canceled[id] = true
end
local enabled = true
local config = {
  llm = { backend = "ollama", provider = "sweep", model = "test" },
  enabled_predicate = function()
    return enabled
  end,
  normal_mode = { enabled = true, debounce_ms = 60000 },
  context = { lsp = { enabled = false } },
  keymaps = {
    insert = { accept = false, accept_line = false, clear = false, reject = false },
    normal = { accept = false, accept_line = false },
  },
  ui = { suppress_lsp_floats = false, progress = false },
}
edit.setup(config)
vim.api.nvim_buf_set_lines(0, 0, -1, false, { "local value = 1", "print(value)" })
local function request()
  edit.trigger({ force = true })
  return callbacks[#callbacks]
end
local late = request()
assert(late, "no request")
edit.cancel()
late(nil, { text = "local value = 2\nprint(value)" })
vim.wait(20)
assert(canceled[1] and not edit.has_prediction(), "late response survived cancellation")
local old = request()
edit.cancel()
local newer = request()
old(nil, { text = "local value = 3\nprint(value)" })
vim.wait(20)
assert(require("blink-edit.core.state").is_in_flight(1), "old callback cleared newer flight")
newer(nil, { text = "local value = 2\nprint(value)" })
vim.wait(20)
assert(edit.has_prediction(), "valid prediction missing")
enabled = false
edit.accept()
assert(vim.api.nvim_get_current_line() == "local value = 1", "disabled prediction applied")
enabled = true
for _, mutate in ipairs({
  function()
    vim.api.nvim_buf_set_lines(0, 0, -1, false, { "user edit", "print(value)" })
  end,
  function()
    vim.api.nvim_win_set_cursor(0, { 2, 0 })
  end,
  function()
    require("blink-edit.config").get().llm.model = "other"
  end,
}) do
  edit.cancel()
  vim.api.nvim_win_set_cursor(0, { 1, 0 })
  require("blink-edit.config").get().llm.model = "test"
  local callback = request()
  mutate()
  callback(nil, { text = "local value = 2\nprint(value)" })
  vim.wait(20)
  assert(not edit.has_prediction(), "stale response displayed")
end
edit.reset()
print("PASS blink-edit cancellation, stale callbacks, predicates, changedtick, cursor and model")
