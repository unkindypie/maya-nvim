return {
  {
    "sindrets/diffview.nvim",
    cmd = {
      "DiffviewOpen",
      "DiffviewClose",
      "DiffviewFileHistory",
      "DiffviewToggleFiles",
      "DiffviewFocusFiles",
      "DiffviewRefresh",
    },
    dependencies = { "nvim-tree/nvim-web-devicons" },
    opts = {
      file_panel = {
        listing_style = "tree",
        tree_options = { flatten_dirs = false },
      },
      keymaps = {
        -- Avoid shadowing Maya's buffer-menu prefix inside Diffview.
        view = { { "n", "<leader>b", false } },
        file_panel = { { "n", "<leader>b", false } },
        file_history_panel = { { "n", "<leader>b", false } },
      },
    },
  },
}
