local vendor = vim.fn.stdpath("config") .. "/vendor/"
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
        ["<S-Tab>"] = {
          function()
            return require("maya.ai").accept(true)
          end,
          "select_prev",
          "snippet_backward",
          "fallback",
        },
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
    dir = vendor .. "cursortab.nvim",
    name = "cursortab.nvim",
    lazy = true,
    build = function()
      local result = vim
        .system({ "python3", vim.fn.stdpath("config") .. "/scripts/build_cursortab.py" }, { text = true })
        :wait()
      assert(result.code == 0, result.stderr)
    end,
  },
  { "nvim-lua/plenary.nvim", lazy = true },
}
