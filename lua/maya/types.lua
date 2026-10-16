---@meta

---@class MayaTheme
---@field plugin? string GitHub owner/repository; installed only when selected.
---@field name? string Colorscheme name; inferred from repository if omitted.
---@field module? string Lua setup module; required for custom plugin opts.
---@field opts? table Theme-specific setup options, merged for Catppuccin.

---@class MayaOptions: vim.bo, vim.wo
---@field [string] any Any option accepted by vim.opt, including list/table values.

---@class MayaConfig
---@field theme? string|MayaTheme Optional repo or colorscheme. Default: catppuccin/nvim (transparent Frappé). Use GitHub repo path format as: "author/repo".
---@field pokemon_sound_on_start? boolean Play the dashboard Pokémon cry. Default: true.
---@field pokemon_sound_on_start_volume_percentage? number Playback volume from 0 to 100. Default: 50; zero mutes.
---@field reopen_tabs? boolean Restore this folder's saved buffers, tabs, and splits. Default: true.
---@field options? MayaOptions Editor options applied after defaults.
---@field plugins? LazySpec[] Personal plugin specs and overrides.
---@field setup? fun() Runs after built-in options and keymaps.
