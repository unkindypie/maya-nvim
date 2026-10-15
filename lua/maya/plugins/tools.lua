return {
  { "b0o/schemastore.nvim", lazy = true },
  { "mason-org/mason.nvim", lazy = false, opts = { ui = { border = "rounded" } } },
  {
    "neovim/nvim-lspconfig",
    lazy = false,
    dependencies = { "mason-org/mason.nvim", "saghen/blink.cmp" },
    config = function()
      require("maya.languages").setup()
    end,
  },
  {
    "nvim-treesitter/nvim-treesitter",
    branch = "main",
    lazy = false,
    build = ":TSUpdate",
    opts = { install_dir = vim.fn.stdpath("data") .. "/site" },
    config = function(_, opts)
      require("nvim-treesitter").setup(opts)
    end,
  },
  {
    "stevearc/conform.nvim",
    event = { "BufReadPost", "BufNewFile", "BufWritePre" },
    cmd = "ConformInfo",
    opts = {
      formatters_by_ft = {
        python = { "ruff_organize_imports", "ruff_format" },
        lua = { "stylua" },
        javascript = { "prettier" },
        javascriptreact = { "prettier" },
        typescript = { "prettier" },
        typescriptreact = { "prettier" },
        json = { "prettier" },
        jsonc = { "prettier" },
        yaml = { "prettier" },
        markdown = { "prettier" },
        html = { "prettier" },
        css = { "prettier" },
        scss = { "prettier" },
        sh = { "shfmt" },
        bash = { "shfmt" },
        c = { "clang_format" },
        cpp = { "clang_format" },
        rust = { "rustfmt" },
      },
      format_on_save = function(buf)
        if vim.b[buf].maya_noformat or vim.bo[buf].buftype ~= "" then
          return
        end
        return { timeout_ms = 1500, lsp_format = "never" }
      end,
    },
  },
  {
    "mfussenegger/nvim-lint",
    event = { "BufReadPost", "BufNewFile" },
    config = function()
      local lint = require("lint")
      lint.linters_by_ft =
        { sh = { "shellcheck" }, bash = { "shellcheck" }, dockerfile = { "hadolint" } }
      vim.api.nvim_create_autocmd({ "BufWritePost", "InsertLeave" }, {
        callback = function()
          if vim.bo.buftype == "" then
            lint.try_lint()
          end
        end,
      })
    end,
  },
  {
    "mfussenegger/nvim-dap",
    lazy = true,
    dependencies = {
      "rcarriga/nvim-dap-ui",
      "nvim-neotest/nvim-nio",
      "mfussenegger/nvim-dap-python",
    },
    config = function()
      require("maya.debug").setup()
    end,
  },
}
