# 🌙 maya-nvim

A standalone Neovim 0.12.5 setup for Maya: LunarVim muscle memory, transparent
Catppuccin Frappé, modern language tools, local AI, and safe collaboration with
external editors such as Codex. Launch with **`mvim`**. Existing `lvim` stays separate.

## Install

Clone this repository anywhere (Maya uses `~/maya-nvim`), then:

```sh
./install.sh
```

The installer links the repository into `${XDG_CONFIG_HOME:-~/.config}/maya-nvim`,
installs the launcher under `~/.local/bin`, adds a managed zsh alias, restores
locked plugins, installs language tools/parsers and debug adapters, and sets up
local Ollama. It does not install system packages or run sudo. Open a new zsh
session afterwards, or run `~/.local/bin/mvim` immediately.

Prerequisites: Neovim **0.12+** (tested with **0.12.5**), Python 3.11+, Git, curl,
tar, a C compiler, tree-sitter CLI **0.26.1+**, Node.js **22+**, and npm. Linux
Ollama installation additionally requires zstd and a working systemd user
session. A Nerd Font and ripgrep are recommended; Maya's Kitty already uses
FantasqueSansM Nerd Font. macOS users install Ollama separately before selecting
local AI. Linux is the fully validated platform.

```sh
./install.sh --help
./install.sh --dry-run
./install.sh --ai copilot                  # no Ollama installation
./install.sh --ai off                      # language tools without AI
./install.sh --no-shell                    # do not edit zsh configuration
./install.sh --skip-bootstrap              # links/shell integration only
./install.sh --ollama-models-dir /mnt/ml/ollama
./install.sh --ollama-models-dir "$HOME/models" --model qwen2.5-coder:1.5b
./install.sh --tmux-sessionizer "$HOME/scripts/tmux-sessionizer"
```

Ollama setup asks for its models directory on an interactive terminal. It reuses
installed Ollama and existing models, downloads only missing models, and keeps
model files outside this repository. Maya's chosen store is `/mnt/ml/ollama`.
Installation is repeatable; unrelated existing config directories/launchers are
never overwritten. Edited shell/sessionizer files get dated backups.

## Daily use

Space opens which-key. `Space f` finds files, `Space e` toggles the explorer,
`Space st` searches text, `Space w` saves, `Space c` closes a buffer, and `H`/`L`
switch buffers. `Space od` opens the current directory in the desktop file
manager. `Space Ld` opens this README; `Space Lc` opens `init.lua`.

Starting `mvim` with no file arguments restores the last buffers, splits, and
cursor positions for that folder. Explicit file arguments take priority.
`Space bs` saves a session and `Space br` restores it manually. Session files
live in maya-nvim’s state directory; unsaved text is not saved into sessions.
Native swap recovery remains available after crashes.

Formatting runs on save. `Space bW` saves without formatting. Current-line Git
blame shows author, date, and commit summary; `Space gB` toggles it and `Space gL`
shows full blame.

Clean buffers follow external changes within about a second, without switching
buffers. Modified buffers keep Maya's edits and use Neovim's native conflict
warning. `Space bd` / `:MayaDiffDisk` opens a native diff against a disk snapshot.

Python uses **Ruff + ty**. Language servers and parsers install on first opening
a supported filetype, including Rust. `:MayaTools` retries failed installations;
`:Mason` manages tools. See [language tooling](docs/LANGUAGES.md).

## AI suggestions

Ollama and GitHub Copilot are selectable backends; only one is active:

```vim
:MayaAI ollama
:MayaAI copilot
:MayaAI off
```

Use `Space ao/ac/ax` for the same actions. GitHub authentication is through
`:Copilot auth`. Local server failure never silently switches to GitHub.
Tab accepts a visible AI suggestion first, otherwise navigates completion,
jumps/expands snippets, or inserts a normal Tab. Ctrl-J/K navigate completion,
Ctrl-L cycles AI forward, Alt-[ cycles backwards, and Ctrl-] dismisses it.
Enter accepts a selected completion; it does not automatically select one.

Details: [AI setup](docs/AI.md), [keybindings and migration](docs/KEYBINDINGS.md),
[maintenance/troubleshooting](docs/MAINTENANCE.md), [validation](docs/VALIDATION.md).

## Configuration map

| Location | Responsibility |
|---|---|
| `init.lua` | Small ordered entry point |
| `lua/maya/options.lua` | Editor defaults and safe config-file indentation |
| `lua/maya/keymaps.lua` | Familiar global bindings and which-key descriptions |
| `lua/maya/plugins/` | Plugin choices grouped by UI, completion, and tools |
| `lua/maya/languages.lua` | LSP setup and first-use tool/parser inventory |
| `lua/maya/ai.lua` | Provider switching and shared suggestion controls |
| `lua/maya/reload.lua` | Native file-change checks and disk diff |
| `lua/maya/debug.lua` | Python and Node debug adapters |
| `scripts/` | Installer, bootstrap, and Ollama setup |
| `tests/` | Installer and real editor integration checks |

## Updates and removal

Plugin revisions are recorded in `lazy-lock.json`. Review and test updates before
committing the lockfile on `master`. See [maintenance](docs/MAINTENANCE.md) for
rollback, tool versions, testing, and complete uninstall instructions. Removing
maya-nvim never requires deleting LunarVim or Ollama models.

Configuration licensed GPL-3.0; LunarVim-derived mappings are attributed in
[NOTICE](NOTICE). Plugins retain their own licenses.
