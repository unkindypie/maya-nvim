local M = {}
function M.root()
  return vim.fs.root(
    0,
    { ".git", "pyproject.toml", "Cargo.toml", "CMakeLists.txt", "package.json" }
  ) or vim.uv.cwd()
end
function M.pick(name, opts)
  return function()
    Snacks.picker[name](opts or {})
  end
end
function M.open_directory()
  local file = vim.api.nvim_buf_get_name(0)
  local dir = file ~= "" and vim.fs.dirname(file) or vim.uv.cwd()
  for _, app in ipairs({ "thunar", "xdg-open", "gio", "open" }) do
    if vim.fn.executable(app) == 1 then
      local args = app == "gio" and { app, "open", dir } or { app, dir }
      vim.system(args, { detach = true }, function(result)
        if result.code ~= 0 then
          vim.schedule(function()
            vim.notify(result.stderr, vim.log.levels.ERROR)
          end)
        end
      end)
      return
    end
  end
  vim.notify("Install a desktop file manager or xdg-open", vim.log.levels.WARN)
end
function M.config_file(name)
  vim.cmd.edit(vim.fn.fnameescape(vim.fn.stdpath("config") .. "/" .. name))
end
function M.close_others()
  local current = vim.api.nvim_get_current_buf()
  -- Snacks uses native Save/Discard/Cancel confirmation for modified buffers.
  Snacks.bufdelete.other()
  for _, buf in ipairs(vim.api.nvim_list_bufs()) do
    if buf ~= current and vim.bo[buf].buflisted then
      return
    end
  end
  -- A cancelled close leaves remaining buffers and their tabs/windows intact.
  vim.cmd("tabonly")
  vim.cmd("only")
end
return M
