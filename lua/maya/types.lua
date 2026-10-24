---@meta

---@class MayaTheme
---@field plugin? string GitHub repository in "owner/repository" format, for example "catppuccin/nvim"; installed when selected.
---@field name? string Installed colorscheme name, for example "catppuccin-frappe"; inferred from plugin when omitted.
---@field module? string Lua setup module; required for custom plugin opts.
---@field opts? table Theme-specific setup options, merged for Catppuccin.

---@class MayaOptions: vim.bo, vim.wo
---@field [string] any Any option accepted by vim.opt, including list/table values.

---@class MayaConfig
---@field codex_ide_context? boolean Serve read-only open-file and selection context to Codex CLI /ide over its local Unix socket. Default: false. Independent of inline AI providers.
---@field theme_background? "auto"|"dark"|"light" Select the theme background variant before loading it. Default: "auto" (preserve existing behavior). Requires a theme supporting the selected variant; later options.background overrides it.
---@field transparent_background? boolean Clear editor, gutter and floating-window backgrounds to show the terminal background with any theme. Default: false (keep theme behavior).
---@field theme? string|MayaTheme A string containing "/" selects and installs a GitHub repository in "owner/repository" format, for example "catppuccin/nvim". A string without "/" selects an already-installed colorscheme, for example "catppuccin-frappe"; it does not install a plugin. For explicit plugin/name/options, use a MayaTheme table. Default: "catppuccin/nvim" (transparent Frappé).
---@field pokemon_sound_on_start? boolean Play the dashboard Pokémon cry. Default: true.
---@field pokemon_sound_on_start_volume_percentage? number Playback volume from 0 to 100. Default: 50; zero mutes.
---@field reopen_tabs? boolean Restore this folder's saved buffers, tabs, and splits. Default: true.
---@field ai_completion_debounce_ms? number Insert completion idle delay in milliseconds, from 0 to 60000. Default: 200.
---@field ai_next_edit_debounce_ms? number Sweep idle delay in milliseconds, from 0 to 60000. Default: 650.
---@field options? MayaOptions Editor options applied after defaults.
---@field plugins? LazySpec[] Personal plugin specs and overrides.
---@field setup? fun() Runs after built-in options and keymaps.
