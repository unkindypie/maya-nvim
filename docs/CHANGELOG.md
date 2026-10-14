# Changelog

- Add simple sound/session preferences and first-install questions, preserving existing configs.
- Show the launch's Pokémon quote and optional cry when automatically restoring a folder session.
- Ensure Explorer Tab collapses an already open directory, including while searching.

- Reduce Pokémon cry playback to 50% volume and close Explorer when Tab opens a file.

- Play the dashboard Pokémon's cry asynchronously through PokéAPI, with local caching.
- Consolidate project code and configuration under GPL-3.0; retain Pokémon asset ownership notices separately.

- Make Explorer Enter toggle multi-selection; Tab opens files or expands directories.

- Add a staged Markdown pre-commit formatter using mvim's Prettier, preserving unstaged edits.

## Initial setup — 2026-10-14

- Standalone Neovim 0.12.5 configuration, isolated from LunarVim.
- LunarVim-style mappings, Catppuccin Frappé, Snacks, Blink, and current APIs.
- Ruff + ty, automatic language tools, Python/Node debugging.
- Current-line blame and native external-change/reconciliation workflow.
- Ollama/GitHub provider selection and reversible user-local installation.

- Automatic folder sessions, including tabs and cursor positions.
- Local randomized Pokémon dashboard sounds and safe Close all others.
- Validated Python/C++ projects, Rust installation, both debuggers and local AI.

- Use explicit semantic which-key icons with broadly supported Nerd Font glyphs.
- Close Explorer after opening a file; keep it open when expanding directories.
- Fix lualine theme name to `catppuccin-frappe`, removing its startup configuration warning.
- Launch through a user-local executable symlink so tmux detects `mvim` instead of `nvim`.
- Remove the 350 ms current-line blame delay for immediate cursor updates.
- Support personal options, plugin specs, keymaps and Lua modules under `~/.config/mvim`.
- Document launching with `mvim` and pushing commits to the configured remote.
- Use Explorer Tab to open/preview while keeping focus, and Enter to select/open and close.
