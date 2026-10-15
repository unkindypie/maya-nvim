local U = require("maya.util")
local function map(mode, key, action, desc)
  vim.keymap.set(mode, key, action, { silent = true, desc = desc })
end
local function leader(key, action, desc, mode)
  map(mode or "n", "<leader>" .. key, action, desc)
end
local function cmd(value)
  return "<cmd>" .. value .. "<cr>"
end
local function pick(name, opts)
  return U.pick(name, opts)
end
for key, dir in pairs({ h = "h", j = "j", k = "k", l = "l" }) do
  map("n", "<C-" .. key .. ">", "<C-w>" .. dir, "Window " .. dir)
  map("t", "<C-" .. key .. ">", "<C-\\><C-n><C-w>" .. dir, "Window " .. dir)
end
for key, value in pairs({
  ["<C-Up>"] = "resize -2",
  ["<C-Down>"] = "resize +2",
  ["<C-Left>"] = "vertical resize -2",
  ["<C-Right>"] = "vertical resize +2",
  H = "BufferLineCyclePrev",
  L = "BufferLineCycleNext",
  ["]q"] = "cnext",
  ["[q"] = "cprev",
}) do
  map("n", key, cmd(value), value)
end
map("n", "<C-q>", function()
  if vim.fn.getqflist({ winid = 0 }).winid > 0 then
    vim.cmd.cclose()
  else
    vim.cmd.copen()
  end
end, "Toggle quickfix")
map("n", "<A-j>", ":m .+1<CR>==", "Move line down")
map("n", "<A-k>", ":m .-2<CR>==", "Move line up")
map("i", "<A-j>", "<Esc>:m .+1<CR>==gi", "Move line down")
map("i", "<A-k>", "<Esc>:m .-2<CR>==gi", "Move line up")
map("x", "<A-j>", ":m '>+1<CR>gv=gv", "Move selection down")
map("x", "<A-k>", ":m '<-2<CR>gv=gv", "Move selection up")
map("x", "<", "<gv", "Indent left")
map("x", ">", ">gv", "Indent right")
for key, dir in pairs({ Up = "k", Down = "j", Left = "h", Right = "l" }) do
  map("i", "<A-" .. key .. ">", "<Esc><C-w>" .. dir, "Window " .. dir)
end
map({ "n", "t" }, "<C-\\>", function()
  Snacks.terminal.toggle(nil, { win = { position = "float" } })
end, "Terminal")
leader(";", function()
  Snacks.dashboard()
end, "Dashboard")
leader("w", cmd("write"), "Save")
leader("q", cmd("confirm quit"), "Quit")
vim.keymap.set("n", "<leader>/", "gcc", { remap = true, desc = "Comment line" })
vim.keymap.set("x", "<leader>/", "gc", { remap = true, desc = "Comment selection" })
leader("c", function()
  Snacks.bufdelete()
end, "Close buffer")
leader("f", function()
  Snacks.picker.files({ cwd = U.root() })
end, "Find project file")
leader("h", cmd("nohlsearch"), "Clear search highlight")
leader("e", function()
  Snacks.explorer({ cwd = U.root() })
end, "Explorer")
for key, command in pairs({
  j = "BufferLinePick",
  b = "BufferLineCyclePrev",
  n = "BufferLineCycleNext",
  e = "BufferLinePickClose",
  h = "BufferLineCloseLeft",
  l = "BufferLineCloseRight",
  D = "BufferLineSortByDirectory",
  L = "BufferLineSortByExtension",
}) do
  leader("b" .. key, cmd(command), (command:gsub("BufferLine", "")))
end
leader("bf", pick("buffers"), "Find buffer")
leader("bW", cmd("noautocmd write"), "Save without formatting")
leader("bd", require("maya.reload").diff_disk, "Diff unsaved buffer against disk")
for key, command in pairs({
  i = "install",
  s = "sync",
  S = "show",
  c = "clean",
  u = "update",
  p = "profile",
  l = "log",
  d = "debug",
}) do
  leader("p" .. key, cmd("Lazy " .. command), command)
end
local git = {
  j = { "nav_hunk", "next" },
  k = { "nav_hunk", "prev" },
  l = { "blame_line" },
  p = { "preview_hunk" },
  r = { "reset_hunk" },
  R = { "reset_buffer" },
  s = { "stage_hunk" },
  u = { "undo_stage_hunk" },
  d = { "diffthis", "HEAD" },
  B = { "toggle_current_line_blame" },
}
for key, item in pairs(git) do
  leader("g" .. key, function()
    require("gitsigns")[item[1]](item[2])
  end, (item[1]:gsub("_", " ")))
end
leader("gL", function()
  require("gitsigns").blame_line({ full = true })
end, "Full blame")
leader("gg", function()
  Snacks.lazygit()
end, "Lazygit")
for key, name in pairs({ o = "git_status", b = "git_branches", c = "git_log", C = "git_log_file" }) do
  leader("g" .. key, pick(name), (name:gsub("_", " ")))
end
for _, action in ipairs({ { "r", "reset_hunk" }, { "s", "stage_hunk" } }) do
  leader("g" .. action[1], function()
    require("gitsigns")[action[2]]({ vim.fn.line("."), vim.fn.line("v") })
  end, action[2], "x")
end
local lsp = {
  a = { vim.lsp.buf.code_action, "Code action" },
  f = {
    function()
      require("conform").format({ timeout_ms = 1500, lsp_format = "never" })
    end,
    "Format",
  },
  r = { vim.lsp.buf.rename, "Rename" },
  l = { vim.lsp.codelens.run, "CodeLens" },
  q = { vim.diagnostic.setloclist, "Diagnostics location list" },
  j = {
    function()
      vim.diagnostic.jump({ count = 1, float = true })
    end,
    "Next diagnostic",
  },
  k = {
    function()
      vim.diagnostic.jump({ count = -1, float = true })
    end,
    "Previous diagnostic",
  },
}
for key, item in pairs(lsp) do
  leader("l" .. key, item[1], item[2])
end
leader("la", vim.lsp.buf.code_action, "Code action", "x")
leader("ld", pick("diagnostics_buffer"), "Buffer diagnostics")
leader("lw", pick("diagnostics"), "Workspace diagnostics")
leader("li", function()
  require("maya.lsp_info").open()
end, "LSP info")
leader("lI", cmd("Mason"), "Mason")
leader("ls", pick("lsp_symbols"), "Document symbols")
leader("lS", pick("lsp_workspace_symbols"), "Workspace symbols")
leader("le", pick("qflist"), "Quickfix")
for key, name in pairs({
  b = "git_branches",
  c = "colorschemes",
  f = "files",
  h = "help",
  H = "highlights",
  M = "man",
  r = "recent",
  R = "registers",
  t = "grep",
  k = "keymaps",
  C = "commands",
  l = "resume",
  p = "colorschemes",
  P = "projects",
}) do
  leader("s" .. key, pick(name), (name:gsub("_", " ")))
end
leader("Md", function()
  U.config_file("README.md")
end, "Documentation")
leader("Mf", function()
  Snacks.picker.files({ cwd = vim.fn.stdpath("config") })
end, "Find config files")
leader("Mg", function()
  Snacks.picker.grep({ cwd = vim.fn.stdpath("config") })
end, "Search configuration")
leader("Mk", pick("keymaps"), "Keymaps")
leader("Mi", cmd("checkhealth"), "Health")
leader("MI", function()
  U.config_file("docs/CHANGELOG.md")
end, "Changelog")
leader("Mr", function()
  vim.notify("Restart mvim to reload all configuration safely.")
end, "Reload instructions")
leader("Mu", function()
  require("maya.update").run()
end, "Update maya-nvim")
leader("Mll", function()
  vim.cmd.edit(vim.fn.fnameescape(vim.lsp.log.get_filename()))
end, "LSP log")
leader("Mln", function()
  vim.cmd.edit(vim.fn.fnameescape(vim.fn.stdpath("log") .. "/log"))
end, "Neovim log")
leader("Mld", cmd("MasonLog"), "Tool installation log")
leader("Ti", cmd("checkhealth nvim-treesitter"), "Treesitter health")
leader("Tl", cmd("MayaTools"), "Install/retry current language tools")
leader("od", U.open_directory, "Open directory in desktop explorer")
leader("om", cmd("RenderMarkdown toggle"), "Toggle Markdown preview")
for key, provider in pairs({ o = "ollama", c = "copilot", x = "off" }) do
  leader("a" .. key, function()
    require("maya.ai").select(provider)
  end, "AI: " .. provider)
end
leader("as", function()
  require("maya.ai").notify_status()
end, "AI status")
local dap = {
  t = "toggle_breakpoint",
  b = "step_back",
  c = "continue",
  C = "run_to_cursor",
  d = "disconnect",
  g = "session",
  i = "step_into",
  o = "step_over",
  u = "step_out",
  p = "pause",
  s = "continue",
  q = "close",
}
for key, action in pairs(dap) do
  leader("d" .. key, function()
    require("dap")[action]()
  end, (action:gsub("_", " ")))
end
leader("dr", function()
  require("dap").repl.toggle()
end, "Debug REPL")
leader("dU", function()
  require("dap")
  require("dapui").toggle({ reset = true })
end, "Debug UI")
require("maya.ai").setup()

leader("bs", cmd("MayaSessionSave"), "Save folder session")
leader("br", cmd("MayaSessionLoad"), "Restore folder session")

leader("bo", U.close_others, "Close all others (buffers/tabs)")

leader("Mc", function()
  vim.cmd.edit(vim.fn.fnameescape(require("maya.user").path .. "/init.lua"))
end, "Edit personal configuration")

vim.api.nvim_create_autocmd("FileType", {
  pattern = "qf",
  group = vim.api.nvim_create_augroup("MayaQuickfixKeys", { clear = true }),
  callback = function(ev)
    vim.keymap.set(
      "n",
      "q",
      "<cmd>close<cr>",
      { buffer = ev.buf, silent = true, desc = "Close results" }
    )
  end,
})
