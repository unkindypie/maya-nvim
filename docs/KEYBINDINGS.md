# Keybindings and LunarVim migration

Space is the leader. Which-key describes the available bindings after 150 ms.
The authoritative mappings are in `lua/maya/keymaps.lua` and `plugins/completion.lua`.

| Keys                                     | Action                                                                                  |
| ---------------------------------------- | --------------------------------------------------------------------------------------- |
| `Space f`, `Space st`                    | Project files, text search                                                              |
| `Space e`, `Space ;`                     | Explorer, dashboard                                                                     |
| `Space w/q/c/h`                          | Save, quit, close buffer, clear search highlight                                        |
| `H/L`, `Space bb/bn`                     | Previous/next buffer                                                                    |
| `Space bj/bf/be`                         | Pick buffer, search buffers, pick buffer to close                                       |
| `Space bh/bl/bD/bL`                      | Close left/right; sort directory/extension                                              |
| `Space bo`                               | Close all other buffers/tab pages (confirm unsaved changes)                             |
| `Space bW`                               | Save without formatting                                                                 |
| `Space bd`                               | Native diff of unsaved text against disk snapshot                                       |
| `Space bs/br`                            | Save/restore this folder's session                                                      |
| `Space gs/gg`                            | Full-screen Lazygit (`gg` remains an alias)                                             |
| `Space gj/gk`                            | Next/previous hunk                                                                      |
| `Space gl/gL/gB`                         | Line blame, full blame, inline blame toggle                                             |
| `Space gp/gr/gR/gS/gu/gd`                | Preview/reset hunk, reset buffer, stage/undo stage, diff                                |
| `Space go/gb/gc/gC`                      | Git status, branches, commits, file commits                                             |
| `Space gv/gV/gq`                         | Changed-file diff tree, compare branch/revision, close diff view                        |
| `Space gS/gs` (Visual mode)              | Stage selected lines (`gs` retains its Visual-mode behavior)                            |
| `Space la/lf/lr`                         | Code action, format, rename                                                             |
| `Space ld/lw/lj/lk`                      | Buffer/workspace diagnostics, next/previous diagnostic                                  |
| `Space li/lI`                            | LSP info popup, Mason                                                                   |
| `Space ls/lS/le/lq/ll`                   | Document/workspace symbols, quickfix picker, diagnostic location list, code lens        |
| `gd/gD/gr/gI/K/gs/gl`                    | Definition, declaration, references, implementation, hover, signature, line diagnostics |
| `Space dt/dc/di/do/du/dU`                | Breakpoint, continue, step in/over/out, debug UI                                        |
| `Space dr/dp/dd/dq`                      | Debug REPL, pause, disconnect, close                                                    |
| `Space pi/ps/pS/pc/pu/pp/pl/pd`          | Lazy install/sync/show/clean/update/profile/log/debug                                   |
| `Space sf/sh/sH/sM/sr/sR/sk/sC/sl/sp/sP` | Files/help/highlights/man/recent/registers/keymaps/commands/resume/colors/projects      |
| `Space Mc`                               | Edit personal `~/.config/mvim/init.lua`                                                 |
| `Space Md/Mf/Mg/Mk/Mi/MI`                | Docs, find/grep config, keymaps, health, changelog                                      |
| `Space Mr/Mu/MU`                         | Restart instructions, update config/plugins, last update result                         |
| `Space Mld/Mll/Mln`                      | Mason/MSP/Neovim logs                                                                   |
| `Space Ti/Tl`                            | Tree-sitter health, retry current language tooling                                      |
| `Space od`                               | Desktop file manager at current directory                                               |
| `Space om`                               | Toggle in-editor Markdown preview                                                       |
| `Space ao/ac/ax/as`                      | Ollama/Copilot/off/status                                                               |
| `Ctrl-\`                                 | Floating terminal                                                                       |
| `Ctrl-h/j/k/l`                           | Window navigation, including terminal mode                                              |
| `Ctrl-arrows`, `Alt-j/k`                 | Resize windows, move lines/selections                                                   |
| `gc`, `gcc`, `Space /`                   | Native comments / line / selection                                                      |

## Explorer keybindings

Open Explorer with `Space e`. These shortcuts apply in the file list unless noted.

| Keys                           | Action                                                                                  |
| ------------------------------ | --------------------------------------------------------------------------------------- |
| `Enter` or `Tab`               | Open a file and close Explorer, or expand/collapse a folder; also works in search input |
| `s`                            | Toggle selection and move to the next item                                              |
| `a` or `n`                     | New file; end the name with `/` to create a folder                                      |
| `d`                            | Delete the current or selected files                                                    |
| `r`                            | Rename the current file                                                                 |
| `c` / `m`                      | Copy / move the current or selected files                                               |
| `y` / `p`                      | Yank paths / paste files                                                                |
| `j` / `k` or arrow keys        | Move down / up                                                                          |
| `h`                            | Collapse a folder or its parent                                                         |
| `Backspace`                    | Go to the parent directory                                                              |
| `i`                            | Focus search input                                                                      |
| `Escape` in search insert mode | Leave typing mode                                                                       |
| `H` / `I`                      | Toggle hidden / Git-ignored files                                                       |
| `P`                            | Toggle file preview                                                                     |
| `u`                            | Refresh files                                                                           |
| `?`                            | Open compact help; `?`, `q`, or Escape closes the help panel                            |
| `q`                            | Close Explorer                                                                          |

### Customize your keybindings

Edit `~/.config/mvim/init.lua` (`Space Mc`), or
`$XDG_CONFIG_HOME/mvim/init.lua` if you use a custom config location. Add the
examples below to the table your config already returns; keep a single
`return { ... }`, and merge with any existing `setup` or `plugins` entries.
Restart mvim after changing mappings. Personal overrides survive updates.

For normal editor mappings, use `setup`, which runs after mvim's defaults:

```lua
return {
  setup = function()
    vim.keymap.set("n", "<leader>w", "<cmd>write<cr>", { desc = "Save file" })
    vim.keymap.set("n", "<leader>ee", function()
      Snacks.explorer()
    end, { desc = "Explorer" })
    -- Remove a default mapping (only if it exists):
    vim.keymap.del("n", "<leader>od")
  end,
}
```

Explorer has buffer-local mappings managed by Snacks. Override those through
its plugin options instead of global `vim.keymap.set` calls:

```lua
return {
  plugins = {
    {
      "folke/snacks.nvim",
      opts = {
        picker = {
          sources = {
            explorer = {
              win = {
                list = {
                  keys = {
                    ["x"] = "select_and_next", -- Add another selection key.
                    ["n"] = false, -- Disable n; a still creates files.
                    ["<Tab>"] = "maya_open", -- Open / expand / collapse.
                  },
                },
                input = {
                  keys = {
                    ["<C-o>"] = { "maya_open", mode = { "i", "n" } },
                  },
                },
              },
            },
          },
        },
      },
    },
  },
}
```

`list` applies to the file tree; `input` applies to the search field.
Use Neovim key notation such as `<CR>` for Enter, `<Tab>`, and `<C-o>` for
Ctrl+o. Action names include `maya_open`, `select_and_next`, `explorer_add`,
`explorer_del`, `explorer_rename`, and `maya_help`. Setting a key to `false`
disables its plugin mapping. Other keys keep their defaults.

The compact `?` panel describes mvim's defaults, so it does not automatically
reflect personal remappings. For Snacks' complete list of actual mappings,
set `["?"] = "toggle_help_list"` in the Explorer `list.keys` table above.

Current-line Git blame aligns to the right edge of the editor window. Long
author/date/commit text is shortened to fit beside the file content.
Neovim's native `eol_right_align` placement avoids stale-window sizing errors
when switching into a diff tab.

Markdown files render headings, tables, checkboxes, and code blocks inside the
buffer. Use `Space om` or `:RenderMarkdown toggle` to switch rendering off/on.
Long Markdown lines wrap visually at word boundaries, with indentation carried
onto continuation rows. Wrapping adapts to the window width in both editing and
preview modes; it does not insert newlines or reformat the file. Other filetypes
keep their existing no-wrap default. Use `:setlocal nowrap` to disable wrapping
in the current window, or `:setlocal wrap` to enable it again.
Insert mode shows raw text for editing; rendering does not change file contents.

Picker input retains Ctrl-N/P selection, Ctrl-J/K history, Enter open, Ctrl-Q
quickfix. Explorer uses its current supported controls (`?` for help), l
open, h parent, and `a` or `n` to add, `d` to delete, `r` to rename. Tab or Enter expands/collapses a directory
or opens a file in the main window and closes Explorer, including from the search input. `s` toggles
selection of a file or directory and moves to the next item, keeping Explorer
open for multi-selection actions such as copy, move, or delete.

## Intentional changes

| LunarVim implementation                              | maya-nvim replacement                                                                   |
| ---------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Telescope and its FZF extension                      | Snacks pickers; same leader search/Git/MSP entry points                                 |
| NvimTree                                             | Snacks explorer sidebar; internal explorer controls documented via `?`                  |
| Alpha                                                | Snacks dashboard                                                                        |
| ToggleTerm                                           | Snacks terminal/lazygit                                                                 |
| project.nvim                                         | Root detection and Snacks projects picker                                               |
| nvim-cmp/MuaSnip                                     | Blink/native snippets; familiar completion controls                                     |
| none-ls, Black/isort, Pyright                        | Conform, Ruff + ty                                                                      |
| neodev                                               | lazydev                                                                                 |
| indent-blankline, bigfile, illuminate/navic          | Snacks indentation/bigfile; native LSP document highlighting/navigation where available |
| Comment.nvim block-comment `gb`                      | Native `gc`; use language-appropriate manual block comments                             |
| `LvimReload`                                         | Restart instruction; avoid unreliable partial plugin reloads                            |
| LunarVim distribution update/docs/info commands      | Repository docs, health, and explicit locked plugin maintenance                         |
| `TSConfigInfo`                                       | Current Tree-sitter health                                                              |
| Config-forced `w!`                                   | Ordinary write, preserving native external-conflict checks                              |
| Ctrl-K Copilot previous (conflicted with completion) | Alt-[; Ctrl-K stays completion previous                                                 |
| `Space lc`, unsupported aliases/log duplicates       | Only supported/current equivalents are mapped                                           |

Inactive themes, Lir, distribution logging utilities and private LunarVim
compatibility shims are not carried over. Snacks search windows resemble
LunarVim's layout, but are not pixel-identical. Git pickers show history; use
Lazygit for explicit checkout operations rather than silently checking out a
commit on selection.

The right status line shows tools for the current buffer: `LSP` lists attached
language servers, `Lint` lists configured linters, and `Fmt` lists available
formatters selected for formatting. Empty groups are hidden; buffers with
`vim.b.maya_noformat = true` hide `Fmt`. Ruff diagnostics appear under `LSP`
because Ruff runs as a language server.

Formatter steps from the same tool share one short name (for example,
`ruff_format` and `ruff_organize_imports` appear as `Fmt: ruff`).

`Space li` opens a rounded buffer-local LSP panel. Press `h` for the full
health report, `m` for Mason, or `q`/Escape to close.

Explorer shows hidden and Git-ignored files in the tree by default. Searching
excludes hidden and Git-ignored paths; clearing the search restores the full tree. The search bar shows
a small `i` hint: press `i` from the file list to search. The header shows
`? - help` as a reminder of Explorer’s help shortcut. `H` toggles hidden files; `I` toggles ignored files. Lowercase
`h` collapses a directory or moves to and collapses its parent.

Explorer `?` opens a compact help panel with grouped shortcuts and common file
actions first. Press `?`, `q`, or Escape to close the panel.

`Space Mu` updates a clean `master` checkout from `unkindypie/maya-nvim` using a
fast-forward pull, then installs missing plugins and restores shipped plugin
versions in fresh background mvim processes using the pulled configuration.
The statusline and a persistent progress notification show the current phase;
the final result distinguishes an updated config, an already-current config,
and a failure. `Space MU` / `:MayaUpdateStatus` reopens the result;
`:MayaUpdateLog` opens the saved details. `:MayaUpdate` runs the same update as
the hotkey. Repeated presses while running show progress without starting again.
Local edits, a different branch, or a
diverged history stop the update without resetting or stashing your work. Commit
or stash changes yourself before retrying. Restart mvim after syncing to load new
configuration. The updater keeps the repository lockfile clean, refreshes managed
pins in personal lockfiles and preserves personal-only plugin entries. Git or
plugin failures stop the update and include a log pointer; a successful pull is
not reported as a completed update when plugin synchronization fails.
`Space Mc` is the sole edit-config shortcut and
opens your personal config. The maya-nvim group now uses `Space M`.

In insert-mode completion, Down selects the first suggestion and subsequent
presses move down; Up moves back. Arrow navigation dismisses the current
Copilot/Ollama suggestion. Enter or Tab accepts the selected completion. With
no completion selected, Tab retains AI acceptance and snippet/indent fallbacks.

Native quickfix and location-list result windows (including multiple `gd` results)
close with `q`, returning to the file window.

`Space as` shows AI provider/model/server, buffer restrictions, scheduler pause
or request state, and controls for 10 seconds. `Space ao`
enables Ollama or reloads its saved local model and clears dismissal pauses.
`Space ax` disables all AI. `Space am` chooses a local mode and enables Ollama;
single/dual mode is separate from whether AI is enabled. Menu labels state these
actions explicitly. Dismissing a preview (`Space ad` / `Ctrl-]`) pauses automatic
suggestions until the next edit, rather than disabling the provider.

`Space ai` / `:MayaCodexStatus` shows the optional native Codex CLI context
bridge. Enable `codex_ide_context = true` in your personal config and run `/ide`
in Codex in the same project. This is separate from inline AI. See
[Codex IDE context](CODEX.md) for compatibility and selection behavior.

### Git diff tree and branch comparisons

`Space gv` opens Diffview with a directory tree of changed files on the left and
side-by-side diffs on the right. `Space gV` prompts for a Git revision or range;
cancel or empty input leaves the editor unchanged. `Space gq` closes the view.
Lazygit remains on `Space gs` / `Space gg`, and `Space gd` keeps its existing
single-file Gitsigns diff behavior.

| Command                            | Comparison                                                                    |
| ---------------------------------- | ----------------------------------------------------------------------------- |
| `:DiffviewOpen`                    | Unstaged changes against the index, with staged changes in a separate section |
| `:DiffviewOpen main`               | Working copy against the local `main` branch                                  |
| `:DiffviewOpen origin/main`        | Working copy against the fetched remote-tracking branch                       |
| `:DiffviewOpen origin/main...HEAD` | Committed branch changes since the common ancestor                            |
| `:DiffviewOpen main..feature`      | Two committed branch tips                                                     |

Run `git fetch origin` when you need current remote refs; opening a comparison
does not fetch automatically. Commit-range comparisons exclude uncommitted edits.
Use `Tab` / `Shift-Tab` to cycle changed files, `Space e` to focus the file tree,
and `Enter` to select a file. `:DiffviewToggleFiles` toggles the tree.
Use `:DiffviewFileHistory %` for the current file's commit history.

The pinned upstream Diffview version is verified on Linux with Neovim 0.12.5 for
file-tree review, branch/range comparisons and preservation of unsaved edits.
Upstream's last commit is from June 2024; an open
[Windows/Neovim 0.12 memory-growth report](https://github.com/sindrets/diffview.nvim/issues/613)
remains unresolved. Short integration checks do not establish long-session memory
behavior or compatibility with every future Neovim release.

### Local next-edit

| Key                   | Action                                                  |
| --------------------- | ------------------------------------------------------- |
| `Space an`            | Request Sweep next-edit                                 |
| `Space aa`            | Accept the current AI suggestion                        |
| `Space ad` / `Ctrl-]` | Cancel and dismiss                                      |
| Normal `Tab`          | Accept visible Sweep prediction; otherwise jump forward |

Dual local mode runs Minuet in Insert mode and Sweep on Normal idle. Single
mode uses Sweep in both modes. Selected ordinary completion takes priority on
Insert Tab; Enter and arrow navigation keep their existing completion behavior.
