local M = {}
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
      theme.name = theme.name
        or theme.plugin:match("/([^/]+)$"):gsub("%.nvim$", ""):gsub("^nvim%-", "")
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

local function apply(name)
  local ok, err = pcall(vim.cmd.colorscheme, name)
  if not ok then
    vim.cmd.colorscheme("catppuccin")
    vim.schedule(function()
      vim.notify("mvim theme: " .. tostring(err) .. "; using Catppuccin", vim.log.levels.WARN)
    end)
  end
end

function M.setup_default(opts)
  require("catppuccin").setup(opts)
  local theme = selected()
  apply((not theme.plugin or theme.plugin == "catppuccin/nvim") and theme.name or "catppuccin")
  local function highlights()
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
        apply(theme.name)
      end,
    },
  }
end

return M
