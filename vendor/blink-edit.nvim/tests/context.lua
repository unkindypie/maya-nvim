local manager = require("blink-edit.core.context_manager")
local calls, callbacks = 0, {}
vim.lsp.buf_request_sync = function()
  error("must never block on LSP")
end
local client = { id = 1, offset_encoding = "utf-16" }
function client:supports_method()
  return true
end
function client:request(method, params, callback)
  calls = calls + 1
  callbacks[calls] = callback
  return true, calls
end
function client:cancel_request() end
local original_clients = vim.lsp.get_clients
vim.lsp.get_clients = function()
  return { client }
end
vim.api.nvim_buf_set_lines(0, 0, -1, false, { "reference" })
vim.api.nvim_buf_set_name(0, "/tmp/blink-reference-test.lua")
local function collect()
  return manager.collect_lsp_locations(1, "textDocument/references", 1000, 2, 0, 0, "other.lua", 1, 1)
end
assert(#collect() == 0 and calls == 1)
callbacks[1](nil, { { uri = vim.uri_from_bufnr(1), range = { start = { line = 0 }, ["end"] = { line = 0 } } } })
local cached = collect()
assert(#cached == 1 and calls == 1 and cached[1].lines[1] == "reference")
manager.cancel(1)
callbacks[1](nil, { { uri = vim.uri_from_bufnr(1), range = { start = { line = 0 }, ["end"] = { line = 0 } } } })
assert(#collect() == 0 and calls == 2)
manager.cancel(1)
vim.lsp.get_clients = original_clients
print("PASS nonblocking reference cache and late LSP cancellation")
