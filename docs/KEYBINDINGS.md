# Keybindings and LunarVim migration

Space is the leader. Which-key describes the available bindings after 150 ms.
The authoritative mappings are in `lua/maya/keymaps.lua` and `plugins/completion.lua`.

| Keys | Action |
|---|---|
| `Space f`, `Space st` | Project files, text search |
| `Space e`, `Space ;` | Explorer, dashboard |
| `Space w/q/c/h` | Save, quit, close buffer, clear search highlight |
| `H/L`, `Space bb/bn` | Previous/next buffer |
| `Space bj/bf/be` | Pick buffer, search buffers, pick buffer to close |
| `Space bh/bl/bD/bL` | Close left/right; sort directory/extension |
| `Space bW` | Save without formatting |
| `Space bd` | Native diff of unsaved text against disk snapshot |
| `Space bs/br` | Save/restore this folder's session |
| `Space gg/gj/gk` | Lazygit, next/previous hunk |
| `Space gl/gL/gB` | Line blame, full blame, inline blame toggle |
| `Space gp/gr/gR/gs/gu/gd` | Preview/reset hunk, reset buffer, stage/undo stage, diff |
| `Space go/gb/gc/gC` | Git status, branches, commits, file commits |
| `Space la/lf/lr` | Code action, format, rename |
| `Space ld/lw/lj/lk` | Buffer/workspace diagnostics, next/previous diagnostic |
| `Space li/lI` | LSP health, Mason |
| `Space ls/lS/le/lq/ll` | Document/workspace symbols, quickfix picker, diagnostic location list, code lens |
| `gd/gD/gr/gI/K/gs/gl` | Definition, declaration, references, implementation, hover, signature, line diagnostics |
| `Space dt/dc/di/do/du/dU` | Breakpoint, continue, step in/over/out, debug UI |
| `Space dr/dp/dd/dq` | Debug REPL, pause, disconnect, close |
| `Space pi/ps/pS/pc/pu/pp/pl/pd` | Lazy install/sync/show/clean/update/profile/log/debug |
| `Space sf/sh/sH/sM/sr/sR/sk/sC/sl/sp/sP` | Files/help/highlights/man/recent/registers/keymaps/commands/resume/colors/projects |
| `Space Lc/Ld/Lf/Lg/Lk/Li/LI` | Config, docs, find/grep config, keymaps, health, changelog |
| `Space Lr/Lu` | Restart instructions, plugin update |
| `Space Lld/Lll/Lln` | Mason/LSP/Neovim logs |
| `Space Ti/Tl` | Tree-sitter health, retry current language tooling |
| `Space od` | Desktop file manager at current directory |
| `Space ao/ac/ax/as` | Ollama/Copilot/off/status |
| `Ctrl-\` | Floating terminal |
| `Ctrl-h/j/k/l` | Window navigation, including terminal mode |
| `Ctrl-arrows`, `Alt-j/k` | Resize windows, move lines/selections |
| `gc`, `gcc`, `Space /` | Native comments / line / selection |

Picker input retains Ctrl-N/P selection, Ctrl-J/K history, Enter open, Ctrl-Q
quickfix. Explorer uses its current supported controls (`?` for help), Enter/l
open, h parent, and `a/d/r` add/delete/rename.

## Intentional changes

| LunarVim implementation | maya-nvim replacement |
|---|---|
| Telescope and its FZF extension | Snacks pickers; same leader search/Git/LSP entry points |
| NvimTree | Snacks explorer sidebar; internal explorer controls documented via `?` |
| Alpha | Snacks dashboard |
| ToggleTerm | Snacks terminal/lazygit |
| project.nvim | Root detection and Snacks projects picker |
| nvim-cmp/LuaSnip | Blink/native snippets; familiar completion controls |
| none-ls, Black/isort, Pyright | Conform, Ruff + ty |
| neodev | lazydev |
| indent-blankline, bigfile, illuminate/navic | Snacks indentation/bigfile; native LSP document highlighting/navigation where available |
| Comment.nvim block-comment `gb` | Native `gc`; use language-appropriate manual block comments |
| `LvimReload` | Restart instruction; avoid unreliable partial plugin reloads |
| LunarVim distribution update/docs/info commands | Repository docs, health, and explicit locked plugin maintenance |
| `TSConfigInfo` | Current Tree-sitter health |
| Config-forced `w!` | Ordinary write, preserving native external-conflict checks |
| Ctrl-K Copilot previous (conflicted with completion) | Alt-[; Ctrl-K stays completion previous |
| `Space lc`, unsupported aliases/log duplicates | Only supported/current equivalents are mapped |

Inactive themes, Lir, distribution logging utilities and private LunarVim
compatibility shims are not carried over. Snacks search windows resemble
LunarVim's layout, but are not pixel-identical. Git pickers show history; use
Lazygit for explicit checkout operations rather than silently checking out a
commit on selection.
