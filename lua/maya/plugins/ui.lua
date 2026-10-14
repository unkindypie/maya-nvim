local pokemon = require("maya.pokemon_startup")

return {
  {
    "folke/persistence.nvim",
    lazy = false,
    config = function()
      require("maya.session").setup()
    end,
  },
  {
    "catppuccin/nvim",
    name = "catppuccin",
    priority = 1000,
    lazy = false,
    opts = {
      flavour = "frappe",
      transparent_background = true,
      custom_highlights = function(colors)
        return {
          GitSignsCurrentLineBlame = { fg = colors.subtext1, italic = true },
          MayaMarkdownBackground = { bg = "NONE" },
          RenderMarkdownCodeInline = { fg = colors.green, bg = "NONE" },
        }
      end,
      integrations = { blink_cmp = true, snacks = true, gitsigns = true },
    },
    config = function(_, opts)
      require("catppuccin").setup(opts)
      vim.cmd.colorscheme("catppuccin")
    end,
  },
  { "nvim-tree/nvim-web-devicons", lazy = true },
  {
    "MeanderingProgrammer/render-markdown.nvim",
    ft = "markdown",
    cmd = "RenderMarkdown",
    dependencies = { "nvim-treesitter/nvim-treesitter", "nvim-tree/nvim-web-devicons" },
    opts = {
      heading = { backgrounds = { "MayaMarkdownBackground" } },
      code = {
        disable_background = true,
        highlight = "MayaMarkdownBackground",
      },
    },
  },
  {
    "folke/snacks.nvim",
    priority = 1000,
    lazy = false,
    init = function()
      vim.api.nvim_create_autocmd("User", {
        pattern = "SnacksDashboardUpdatePost",
        once = true,
        callback = function()
          vim.schedule(function()
            pokemon.greet(false)
          end)
        end,
      })
    end,
    opts = {
      bigfile = { enabled = true },
      indent = { enabled = true },
      input = { enabled = true },
      notifier = { enabled = true },
      explorer = { enabled = true },
      quickfile = { enabled = true },
      statuscolumn = { enabled = true },
      picker = {
        enabled = true,
        layout = { preset = "telescope" },
        sources = {
          files = { hidden = true },
          grep = { hidden = true },
          explorer = {
            jump = { close = true },
            actions = {
              maya_open = function(picker, item, action)
                local actions = require("snacks.explorer.actions").actions
                if item and item.dir and item.open then
                  actions.explorer_close(picker, item)
                else
                  actions.confirm(picker, item, action)
                end
              end,
            },
            win = { list = { keys = { ["<Tab>"] = "maya_open", ["<CR>"] = "select_and_next" } } },
          },
        },
        win = {
          input = {
            keys = {
              ["<C-n>"] = { "list_down", mode = { "i", "n" } },
              ["<C-p>"] = { "list_up", mode = { "i", "n" } },
              ["<C-j>"] = { "history_forward", mode = { "i", "n" } },
              ["<C-k>"] = { "history_back", mode = { "i", "n" } },
              ["<C-q>"] = { "qflist", mode = { "i", "n" } },
            },
          },
        },
      },
      dashboard = {
        enabled = true,
        preset = {
          header = "🌙  maya-nvim\n\n" .. pokemon.quote,
          keys = {
            { icon = " ", key = "f", desc = "Find file", action = ":lua Snacks.picker.files()" },
            { icon = " ", key = "n", desc = "New file", action = ":ene | startinsert" },
            { icon = " ", key = "g", desc = "Find text", action = ":lua Snacks.picker.grep()" },
            {
              icon = " ",
              key = "r",
              desc = "Recent files",
              action = ":lua Snacks.picker.recent()",
            },
            {
              icon = " ",
              key = "c",
              desc = "Configuration",
              action = ":lua require('maya.util').config_file('init.lua')",
            },
            { icon = "󰒲 ", key = "l", desc = "Plugins", action = ":Lazy" },
            { icon = " ", key = "q", desc = "Quit", action = ":qa" },
          },
        },
      },
    },
  },
  {
    "folke/which-key.nvim",
    event = "VeryLazy",
    opts = {
      preset = "classic",
      delay = 150,
      plugins = {
        marks = false,
        registers = false,
        presets = {
          operators = false,
          motions = false,
          text_objects = false,
          windows = false,
          nav = false,
          z = false,
          g = false,
        },
      },
      win = { border = "single" },
    },
    config = function(_, opts)
      local wk = require("which-key")
      wk.setup(opts)
      -- Explicit, widely supported Nerd Font glyphs avoid ambiguous inferred icons.
      local groups = {
        b = { "Buffers", "", "cyan" },
        d = { "Debug", "", "red" },
        g = { "Git", "", "orange" },
        l = { "LSP", "", "blue" },
        L = { "maya-nvim", "", "purple" },
        p = { "Plugins", "", "yellow" },
        s = { "Search", "", "green" },
        T = { "Treesitter", "", "green" },
        o = { "Open", "", "cyan" },
        a = { "AI", "", "purple" },
      }
      for key, item in pairs(groups) do
        wk.add({
          { "<leader>" .. key, group = item[1], icon = { icon = item[2], color = item[3] } },
        })
      end
      local actions = {
        c = { "Close buffer", "", "red" },
        e = { "Explorer", "", "cyan" },
        f = { "Find project file", "", "green" },
        h = { "Clear search highlight", "", "yellow" },
        q = { "Quit", "", "red" },
        w = { "Save", "", "blue" },
        ["/"] = { "Comment line", "", "grey" },
        [";"] = { "Dashboard", "", "purple" },
      }
      for key, item in pairs(actions) do
        wk.add({ { "<leader>" .. key, desc = item[1], icon = { icon = item[2], color = item[3] } } })
      end
    end,
  },
  {
    "akinsho/bufferline.nvim",
    event = "VeryLazy",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    opts = {
      options = {
        diagnostics = "nvim_lsp",
        always_show_bufferline = true,
        close_command = function(buf)
          Snacks.bufdelete(buf)
        end,
        offsets = { { filetype = "snacks_picker_list", text = "Explorer" } },
      },
    },
  },
  {
    "nvim-lualine/lualine.nvim",
    event = "VeryLazy",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    opts = {
      options = { theme = "catppuccin-frappe", globalstatus = true },
      sections = {
        lualine_c = { { "filename", path = 1 } },
        lualine_x = {
          function()
            return require("maya.ai").status()
          end,
          "encoding",
          "filetype",
        },
      },
    },
  },
  {
    "lewis6991/gitsigns.nvim",
    event = { "BufReadPost", "BufNewFile" },
    opts = {
      current_line_blame = true,
      current_line_blame_opts = { delay = 0, virt_text_pos = "right_align", virt_text_priority = 1 },
      current_line_blame_formatter = function(_, info)
        local text = string.format(
          "%s, %s — %s",
          info.author,
          os.date("%Y-%m-%d", info.author_time),
          info.summary
        )
        local window = vim.fn.getwininfo(vim.api.nvim_get_current_win())[1]
        local available = math.max(
          0,
          vim.api.nvim_win_get_width(0)
            - (window and window.textoff or 0)
            - vim.fn.strdisplaywidth(vim.api.nvim_get_current_line())
            - 2
        )
        if vim.fn.strdisplaywidth(text) > available then
          text = vim.fn.strcharpart(text, 0, math.max(0, available - 1))
          while vim.fn.strdisplaywidth(text) > math.max(0, available - 1) do
            text = vim.fn.strcharpart(text, 0, vim.fn.strchars(text) - 1)
          end
          text = available > 0 and (text .. "…") or ""
        end
        return {
          {
            text,
            "GitSignsCurrentLineBlame",
          },
        }
      end,
    },
  },
}
