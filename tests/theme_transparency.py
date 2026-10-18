"""Theme-independent transparency preserves foregrounds and survives theme changes."""

from integration import start, stop

nvim = start()
try:
    nvim.exec_lua("""local user = require("maya.user")
local theme = require("maya.theme")
user.config.transparent_background = false
vim.api.nvim_set_hl(0, "Normal", { fg=0x123456, bg=0xabcdef, bold=true, ctermbg=4 })
theme.apply_transparency()
assert(vim.api.nvim_get_hl(0, {name="Normal"}).bg == 0xabcdef)
user.config.transparent_background = true
theme.apply_transparency()
local hl = vim.api.nvim_get_hl(0, {name="Normal"})
assert(hl.bg == nil and hl.ctermbg == nil and hl.fg == 0x123456 and hl.bold)
for _, scheme in ipairs({"habamax", "desert"}) do
  vim.cmd.colorscheme(scheme)
  for _, name in ipairs({"Normal", "NormalNC", "NormalFloat", "FloatBorder", "SignColumn", "FoldColumn", "EndOfBuffer"}) do
    assert(vim.api.nvim_get_hl(0, {name=name, link=false}).bg == nil, scheme .. ": " .. name)
  end
end
user.config.transparent_background = false
vim.cmd.colorscheme("habamax")
assert(vim.api.nvim_get_hl(0, {name="Normal", link=false}).bg ~= nil)
""")
    print(
        "PASS optional transparency preserves colors/styles and survives colorscheme changes"
    )
finally:
    stop(nvim)
