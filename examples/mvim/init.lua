-- Personal overrides. Restart mvim after editing this file.
-- Lua modules can live in lua/mvim/ and be loaded with require("mvim.name").
return {
  theme = "catppuccin-frappe", -- Also: tokyonight-moon, kanagawa-wave, or a built-in theme.
  pokemon_sound_on_start = true, -- Play the dashboard Pokemon's cry.
  pokemon_sound_on_start_volume_percentage = 50, -- 0–100; 0 mutes playback.
  reopen_tabs = true, -- Restore this folder's files, tabs, and splits on startup.
  options = {
    -- relativenumber = true,
    -- shiftwidth = 4,
  },
  plugins = {
    -- Extend or override an existing plugin's opts (lazy.nvim merges these).
    -- { "folke/which-key.nvim", opts = { delay = 200 } },
    -- Add plugins here, or import specs from lua/mvim/plugins/:
    -- { import = "mvim.plugins" },
  },
  setup = function()
    -- Runs after the built-in settings and keymaps.
    -- vim.keymap.set("n", "<leader>w", "<cmd>write<cr>", { desc = "My save" })
    -- vim.lsp.config("ty", { settings = { ty = {} } })
  end,
}
