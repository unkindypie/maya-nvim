local M = {}
-- Build opaque tab surfaces before transparency removes Normal's background.
local function bufferline_palette()
  local normal = vim.api.nvim_get_hl(0, { name = "Normal", link = false })
  local light = vim.o.background == "light"
  local bg = normal.bg or (light and 0xf2efda or 0x292522)
  local fg = normal.fg or (light and 0x343e34 or 0xece1d7)
  local function blend(a, b, weight)
    local result = 0
    for _, shift in ipairs({ 16, 8, 0 }) do
      local ac = math.floor(a / 2 ^ shift) % 256
      local bc = math.floor(b / 2 ^ shift) % 256
      result = result + math.floor(ac * (1 - weight) + bc * weight + 0.5) * 2 ^ shift
    end
    return result
  end
  local accent = vim.api.nvim_get_hl(0, { name = "Function", link = false }).fg or fg
  for name, value in pairs({
    Fill = { fg = fg, bg = bg },
    Inactive = { fg = blend(fg, bg, 0.25), bg = blend(bg, fg, 0.03) },
    Visible = { fg = fg, bg = blend(bg, fg, 0.07) },
    Selected = { fg = fg, bg = blend(bg, fg, 0.14), bold = true },
    Separator = { fg = blend(bg, fg, 0.45), bg = bg },
    Accent = { fg = accent, bg = bg },
  }) do
    vim.api.nvim_set_hl(0, "MayaBufferline" .. name, value)
  end
end

function M.bufferline_highlights()
  local function color(group, attr)
    return { highlight = "MayaBufferline" .. group, attribute = attr }
  end
  local highlights = { fill = { bg = color("Fill", "bg") } }
  for suffix, group in pairs({ [""] = "Inactive", _visible = "Visible", _selected = "Selected" }) do
    for _, name in ipairs({ "buffer", "close_button", "tab" }) do
      local key = name == "buffer" and suffix == "" and "background" or name .. suffix
      -- bufferline has tab/tab_selected, but no tab_visible.
      if key ~= "tab_visible" then
        highlights[key] = { fg = color(group, "fg"), bg = color(group, "bg"), italic = false }
      end
    end
    -- Preserve diagnostic/modified colors, while keeping each tab one continuous surface.
    for _, name in ipairs({
      "modified",
      "duplicate",
      "diagnostic",
      "error",
      "warning",
      "info",
      "hint",
      "pick",
    }) do
      highlights[name .. suffix] = { bg = color(group, "bg") }
    end
    highlights["separator" .. suffix] = { fg = color("Separator", "fg"), bg = color(group, "bg") }
  end
  highlights.buffer_selected.bold = true
  highlights.indicator_selected = { fg = color("Accent", "fg"), bg = color("Selected", "bg") }
  return highlights
end

function M.apply_transparency()
  if not require("maya.user").get("transparent_background") then
    return
  end
  for _, name in ipairs({
    "Normal",
    "NormalNC",
    "NormalFloat",
    "FloatBorder",
    "SignColumn",
    "FoldColumn",
    "EndOfBuffer",
  }) do
    local hl = vim.api.nvim_get_hl(0, { name = name, link = false })
    hl.bg = nil
    hl.ctermbg = nil
    vim.api.nvim_set_hl(0, name, hl)
  end
end
function M.resolve(value)
  local theme = type(value) == "string" and { name = value } or vim.deepcopy(value)
  if type(theme) ~= "table" then
    return nil, "theme must be a repository, colorscheme name, or table"
  end
  for key, kind in pairs({ name = "string", plugin = "string", module = "string", opts = "table" }) do
    if theme[key] ~= nil and type(theme[key]) ~= kind then
      return nil, "theme." .. key .. " must be a " .. kind
    end
  end
  if theme.name and theme.name:find("/", 1, true) then
    theme.plugin = theme.plugin or theme.name
    theme.name = nil
  end
  if theme.plugin then
    if not theme.plugin:match("^[%w_.-]+/[%w_.-]+$") then
      return nil, "theme.plugin must use owner/repository format"
    end
    if theme.plugin == "catppuccin/nvim" then
      theme.name = theme.name or "catppuccin-frappe"
      theme.module = theme.module or "catppuccin"
    else
      if not theme.name then
        theme.name = theme.plugin:match("/([^/]+)$"):gsub("%.nvim$", ""):gsub("^nvim%-", "")
        theme.inferred_alias = theme.name:match("^(.+)%-nvim$")
      end
    end
  elseif theme.name and theme.name:match("^catppuccin") then
    theme.plugin = "catppuccin/nvim"
    theme.module = "catppuccin"
  end
  if not theme.name or theme.name == "" then
    return nil, "theme needs a repository or colorscheme name"
  end
  if theme.plugin and theme.opts and not theme.module then
    return nil, "theme.module is required when supplying opts for a custom plugin"
  end
  return theme
end

local function selected()
  return assert(M.resolve(require("maya.user").get("theme")))
end

local function apply(name, inferred_alias)
  M.apply_background()
  local ok, err = pcall(vim.cmd.colorscheme, name)
  if not ok and inferred_alias and tostring(err):find("E185:", 1, true) then
    ok, err = pcall(vim.cmd.colorscheme, inferred_alias)
  end
  if not ok then
    vim.cmd.colorscheme("catppuccin")
    vim.schedule(function()
      vim.notify("mvim theme: " .. tostring(err) .. "; using Catppuccin", vim.log.levels.WARN)
    end)
  end
end

function M.apply_background()
  local background = require("maya.user").get("theme_background")
  if background ~= "auto" then
    vim.o.background = background
  end
end

function M.setup_default(opts)
  M.apply_background()
  require("catppuccin").setup(opts)
  local theme = selected()
  apply((not theme.plugin or theme.plugin == "catppuccin/nvim") and theme.name or "catppuccin")
  local function highlights()
    bufferline_palette()
    M.apply_transparency()
    -- Keep Markdown backgrounds transparent with every colorscheme.
    vim.api.nvim_set_hl(0, "MayaMarkdownBackground", {})
    if not (vim.g.colors_name or ""):match("^catppuccin") then
      vim.api.nvim_set_hl(0, "GitSignsCurrentLineBlame", { link = "Normal" })
      vim.api.nvim_set_hl(0, "RenderMarkdownCodeInline", { link = "String" })
    end
  end
  vim.api.nvim_create_autocmd("ColorScheme", {
    group = vim.api.nvim_create_augroup("MayaTheme", { clear = true }),
    callback = highlights,
  })
  highlights()
end

function M.plugins()
  local theme = selected()
  if theme.plugin == "catppuccin/nvim" then
    return theme.opts and { { "catppuccin/nvim", name = "catppuccin", opts = theme.opts } } or {}
  end
  if not theme.plugin then
    return {}
  end
  return {
    {
      theme.plugin,
      lazy = false,
      priority = 900, -- Default theme (1000) loads first and remains the fallback.
      config = function()
        if theme.module then
          require(theme.module).setup(theme.opts or {})
        end
        apply(theme.name, theme.inferred_alias)
      end,
    },
  }
end

return M
