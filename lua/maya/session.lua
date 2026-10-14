-- Native mksession files, managed by persistence.nvim and scoped to cwd.
local M = {}
function M.setup()
  vim.opt.sessionoptions =
    { "buffers", "curdir", "tabpages", "winsize", "folds", "help", "skiprtp" }
  require("persistence").setup({ branch = false, need = 1 })
  if vim.env.MAYA_NVIM_NO_SESSION == "1" then
    require("persistence").stop()
  end
  local stdin = false
  vim.api.nvim_create_autocmd("StdinReadPre", {
    once = true,
    callback = function()
      stdin = true
    end,
  })
  vim.api.nvim_create_autocmd("VimEnter", {
    once = true,
    callback = function()
      if vim.fn.argc() == 0 and not stdin and vim.env.MAYA_NVIM_NO_SESSION ~= "1" then
        vim.schedule(function()
          require("persistence").load()
        end)
      end
    end,
  })
  vim.api.nvim_create_user_command("MayaSessionSave", function()
    require("persistence").save()
  end, {})
  vim.api.nvim_create_user_command("MayaSessionLoad", function()
    require("persistence").load()
  end, {})
end
return M
