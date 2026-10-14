local path = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not vim.uv.fs_stat(path) then
  local output = vim.fn.system({
    "git",
    "clone",
    "--filter=blob:none",
    "--branch=stable",
    "https://github.com/folke/lazy.nvim.git",
    path,
  })
  if vim.v.shell_error ~= 0 then
    error("Unable to install lazy.nvim: " .. output)
  end
end
vim.opt.rtp:prepend(path)
require("lazy").setup({ { import = "maya.plugins" } }, {
  lockfile = vim.fn.stdpath("config") .. "/lazy-lock.json",
  rocks = { enabled = false },
  change_detection = { notify = false },
  checker = { enabled = false },
  install = { colorscheme = { "catppuccin", "habamax" } },
  ui = { border = "rounded" },
})
