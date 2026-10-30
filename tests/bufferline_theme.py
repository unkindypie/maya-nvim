"""Buffer tabs follow live light/dark changes, including transparent themes."""

from integration import start, stop

nvim = start()
try:
    nvim.ui_attach(120, 30, rgb=True)
    nvim.exec_lua("""
require("lazy").load({plugins={"bufferline.nvim"}})
local user=require("maya.user")
user.config.theme_background="auto"
for _, name in ipairs({"first.lua", "second.py", "third.md"}) do
 local buf=vim.api.nvim_create_buf(true,false)
 vim.api.nvim_buf_set_name(buf,"/tmp/maya-bufferline-test/"..name)
 vim.api.nvim_set_current_buf(buf)
end
_G.palettes={}
local installed=vim.fn.getcompletion("", "color")
for _, scheme in ipairs({vim.tbl_contains(installed,"melange") and "melange" or "default", "catppuccin"}) do
for _, transparent in ipairs({false,true}) do
 user.config.transparent_background=transparent
 if scheme=="catppuccin" then require("catppuccin").setup({transparent_background=transparent}) end
 for _, mode in ipairs({"dark","light","dark"}) do
  vim.o.background=mode
  vim.cmd.colorscheme(scheme=="catppuccin" and (mode=="light" and "catppuccin-latte" or "catppuccin-frappe") or scheme)
  vim.cmd.redrawtabline()
  local function hl(name) return vim.api.nvim_get_hl(0,{name=name,link=false}) end
  assert(hl("SnacksPickerPathHidden").fg==hl("Directory").fg)
  assert(hl("SnacksPickerPathIgnored").fg==hl("Normal").fg)
  assert(hl("SnacksPickerPathIgnored").italic)
  local selected=hl("BufferLineBufferSelected")
  local inactive=hl("BufferLineBackground")
  local separator=hl("BufferLineSeparator")
  assert(selected.bg==hl("MayaBufferlineSelected").bg)
  assert(selected.fg==hl("Normal").fg and selected.bold)
  assert(selected.bg~=inactive.bg)
  assert(hl("BufferLineErrorSelected").bg==selected.bg)
  assert(separator.fg~=separator.bg)
  assert((hl("Normal").bg==nil)==transparent)
  local rendered=vim.api.nvim_eval_statusline(vim.o.tabline,{use_tabline=true,maxwidth=120}).str
  assert(rendered:find("│",1,true),rendered)
  palettes[mode]=selected.bg
 end
end
assert(palettes.light~=palettes.dark)
end
""")
    print(
        "PASS: light/dark tab colors, separators, selected contrast, transparency and live switching"
    )
finally:
    stop(nvim)
