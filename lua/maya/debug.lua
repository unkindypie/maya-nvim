local M = {}
function M.setup()
  local dap, ui = require("dap"), require("dapui")
  ui.setup({})
  dap.listeners.after.event_initialized.maya = function()
    ui.open()
  end
  dap.listeners.before.event_terminated.maya = function()
    ui.close()
  end
  dap.listeners.before.event_exited.maya = function()
    ui.close()
  end
  local python = vim.fn.stdpath("data") .. "/mason/packages/debugpy/venv/bin/python"
  require("dap-python").setup(python)
  dap.adapters["pwa-node"] = {
    type = "server",
    host = "127.0.0.1",
    port = "${port}",
    executable = { command = "js-debug-adapter", args = { "${port}", "127.0.0.1" } },
  }
  for _, ft in ipairs({ "javascript", "javascriptreact", "typescript", "typescriptreact" }) do
    dap.configurations[ft] = {
      {
        type = "pwa-node",
        request = "launch",
        name = "Launch current file",
        program = "${file}",
        cwd = "${workspaceFolder}",
        sourceMaps = true,
        resolveSourceMapLocations = { "${workspaceFolder}/**", "!**/node_modules/**" },
        skipFiles = { "<node_internals>/**" },
      },
      {
        type = "pwa-node",
        request = "attach",
        name = "Attach to Node",
        processId = require("dap.utils").pick_process,
        cwd = "${workspaceFolder}",
        sourceMaps = true,
      },
    }
  end
end
return M
