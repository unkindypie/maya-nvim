return {
  {
    "saghen/blink.cmp",
    version = "1.*",
    event = { "InsertEnter", "CmdlineEnter" },
    dependencies = { "rafamadriz/friendly-snippets" },
    opts = {
      fuzzy = { implementation = "prefer_rust_with_warning" },
      keymap = {
        preset = "none",
        ["<Tab>"] = {
          "accept",
          function()
            return require("maya.ai").accept()
          end,
          "select_next",
          "snippet_forward",
          "fallback",
        },
        ["<Down>"] = {
          function(cmp)
            if cmp.is_visible() then
              require("maya.ai").action("dismiss")
            end
          end,
          "select_next",
          "fallback",
        },
        ["<Up>"] = {
          function(cmp)
            if cmp.is_visible() then
              require("maya.ai").action("dismiss")
            end
          end,
          "select_prev",
          "fallback",
        },
        ["<S-Tab>"] = { "select_prev", "snippet_backward", "fallback" },
        ["<C-j>"] = { "select_next", "fallback" },
        ["<C-k>"] = { "select_prev", "fallback" },
        ["<C-Space>"] = { "show", "show_documentation", "hide_documentation" },
        ["<C-e>"] = { "hide", "fallback" },
        ["<C-y>"] = { "accept", "fallback" },
        ["<CR>"] = { "accept", "fallback" },
        ["<C-d>"] = { "scroll_documentation_up", "fallback" },
        ["<C-f>"] = { "scroll_documentation_down", "fallback" },
      },
      completion = {
        list = { selection = { preselect = false, auto_insert = false } },
        documentation = { auto_show = true },
      },
      sources = { default = { "lsp", "path", "snippets", "buffer" } },
      signature = { enabled = true },
    },
  },
  { "windwp/nvim-autopairs", event = "InsertEnter", opts = {} },
  { "folke/lazydev.nvim", ft = "lua", opts = {} },
  {
    url = "https://github.com/unkindypie/maya-nvim.git",
    name = "minuet-ai.nvim",
    branch = "fork/minuet-cancel",
    commit = "fb376cbb88c99080fb44d01c323413108ad7e09a",
    lazy = true,
    dependencies = { "nvim-lua/plenary.nvim" },
  },
  {
    -- lazy.nvim identifies specs by URL; use a distinct spelling for this fork branch.
    url = "https://github.com/unkindypie/maya-nvim",
    name = "blink-edit.nvim",
    branch = "fork/blink-edit-async",
    commit = "06672de18f5ac1f44916ea15bcf90eae77f00dc7",
    lazy = true,
  },
  { "zbirenbaum/copilot.lua", lazy = true },
  { "nvim-lua/plenary.nvim", lazy = true },
}
