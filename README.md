# 🌙 maya-nvim

A standalone Neovim 0.12.5 setup for Maya: LunarVim muscle memory, transparent
Catppuccin Frappé, modern language tools, local AI, and safe collaboration with
external editors such as Codex. Launch with **`mvim`**. Isolated from other nvim distros..

Installation is one command, with guided questions and automatic setup of missing
prerequisites. Existing tools are kept; incompatible versions receive manual
instructions.

## Install

Supported systems: **Fedora, Debian/Ubuntu, Arch, openSUSE, and macOS with
Homebrew**. Managed downloads support **x86-64 and ARM64**. Prerequisite installation
is tested in Fedora 44 and Ubuntu 24.04 containers; macOS and the other Linux
package-manager paths are covered by command-plan tests, not full system tests.

One-command installation (clones into `~/maya-nvim`, then runs setup):

```sh
bash -c "$(curl -fsSL https://raw.githubusercontent.com/unkindypie/maya-nvim/master/bootstrap.sh)"
```

The command itself needs Bash and curl. The bootstrap can install missing Git
and Python; setup detects the remaining prerequisites, shows the proposed commands,
and asks `Install missing prerequisites? [Y/n]`. Enter installs them; `n` prints
manual instructions. System packages may require a sudo password. Homebrew on
macOS must already be installed.
To choose another directory add this ENV at the start of the install script:
`MAYA_NVIM_INSTALL_DIR="$HOME/projects/maya-nvim"`

Alternatively, clone this repository anywhere (Maya uses `~/maya-nvim`), then:

```sh
./install.sh
```

Launch your new maya-nvim:

```sh
mvim
```

![maya-nvim running in Kitty with restored buffers and a Pokémon notification](docs/images/mvim.png)

The installer links the repository into `${XDG_CONFIG_HOME:-~/.config}/maya-nvim`,
installs the launcher under `~/.local/bin` and an executable symlink under
`~/.local/libexec/maya-nvim` (so tmux displays `mvim`), adds a managed zsh alias, restores
locked plugins, installs language tools/parsers and debug adapters, and optionally sets up
local Ollama after asking. Only missing prerequisites are installed, after showing
the commands; package managers may update dependencies needed by those packages.
Open a new zsh
session afterwards, or run `~/.local/bin/mvim` immediately.

Prerequisites are normally installed automatically. This table lists the tools
and versions for reference **if automatic installation fails**. Copyable commands
for each system and manual recovery are in [prerequisite troubleshooting](docs/PREREQUISITES.md).

| Prerequisite                       | Required version            | Automatic installation                                                                        |
| ---------------------------------- | --------------------------- | --------------------------------------------------------------------------------------------- |
| Bash and curl                      | System version              | Bash is required to start; missing curl can be installed by the local installer               |
| Python                             | 3.11+                       | System package; existing older versions are preserved                                         |
| Git, tar, unzip, CA certificates   | System versions             | System packages when missing                                                                  |
| Neovim                             | 0.12+; tested/pinned 0.12.5 | Verified user-local download when absent                                                      |
| tree-sitter CLI                    | 0.26.1+                     | Verified user-local 0.26.1 download when absent                                               |
| Node.js and npm                    | Node 22+                    | Verified user-local Node 22.23.3 with npm when Node is absent; system package for missing npm |
| C compiler and ripgrep             | System versions             | System compiler tools and `ripgrep` packages                                                  |
| Python virtual-environment support | Matches selected Python     | Distro package when missing                                                                   |
| Audio player                       | Optional                    | Offer mpv if no supported player exists and sound is enabled                                  |
| Nerd Font                          | Optional                    | Offer user-local FantasqueSansMono Nerd Font 3.4.0; select it in terminal settings yourself   |
| Ollama / zstd                      | Optional local AI           | Reuse existing Ollama; install zstd only if a Linux binary download needs it                  |

Fresh installs also ask about sound, saved tabs, and local Ollama AI. Linux Ollama
automatic startup needs a working systemd user session; macOS users install/start
Ollama separately. Declining optional audio/font setup does not block the editor.

```sh
./install.sh --help
./install.sh --dry-run
./install.sh --install-prerequisites       # allow missing prerequisite installation
./install.sh --no-install-prerequisites    # print manual instructions instead
./install.sh --no-install-audio --no-install-nerd-font
./install.sh --yes --ai off                # unattended setup, including missing prerequisites
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

## Personal configuration

Use `~/.config/mvim/init.lua` to extend the managed configuration without editing
this repository (`$XDG_CONFIG_HOME/mvim` when XDG_CONFIG_HOME is set). Installation
creates a commented example if the file does not already exist. `Space LC`
opens it; `Space Lc` still opens the managed entry point.

```lua
return {
  pokemon_sound_on_start = true, -- Play a Pokémon cry at 50% volume.
  reopen_tabs = true, -- Restore this folder's files, tabs, and splits.

  options = {
    -- relativenumber = true,
    -- shiftwidth = 4,
  },

  plugins = {
    -- Add plugins or override their settings:
    -- { "folke/which-key.nvim", opts = { delay = 200 } },
  },

  setup = function()
    -- Add custom keybindings or other setup here.
  end,
}
```

Use lowercase `true` / `false`. The installer asks about sound and tab restoration
when creating a new config; reinstalling preserves your existing file.

Options and `setup()` run after the built-in defaults/keymaps. Plugin specs are
merged after the built-in specs, so they can add plugins, override `opts`, or
use `enabled = false`. For larger setups, put modules in `lua/mvim/` and use
`require("mvim.name")`, or import plugin specs with `{ import = "mvim.plugins" }`.
Personal `ftplugin/` and `after/` directories are supported too. Restart mvim to
apply changes. Configuration errors are reported without discarding defaults.

When personal plugin specs are present, their lockfile is
`~/.config/mvim/lazy-lock.json`, initially copied from the repository's lockfile.
It is independent afterwards: plugin updates/restore use that local lockfile.
To adopt newer repository pins, back up or remove the personal lockfile and
restart; it will be seeded again. A read-only personal directory uses a lockfile
in maya-nvim's state directory instead. Keep personal config and locks when
uninstalling unless you explicitly want to remove them.

## Daily use

The dashboard picks a Pokémon sound from a tiny local Lua bank on startup.
No network request or external command is needed.

Space opens which-key. `Space f` finds files, `Space e` toggles the explorer,
`Space st` searches text, `Space w` saves, `Space c` closes a buffer, and `H`/`L`
switch buffers. `Space bo` closes all other buffers/tab pages, with native
confirmation for unsaved edits. `Space od` opens the current directory in the desktop file
manager. `Space Ld` opens this README; `Space Lc` opens `init.lua`.

Starting `mvim` with no file arguments restores the last buffers, tab pages, splits, and
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

| Location                 | Responsibility                                      |
| ------------------------ | --------------------------------------------------- |
| `init.lua`               | Small ordered entry point                           |
| `lua/maya/options.lua`   | Editor defaults and safe config-file indentation    |
| `lua/maya/keymaps.lua`   | Familiar global bindings and which-key descriptions |
| `lua/maya/plugins/`      | Plugin choices grouped by UI, completion, and tools |
| `lua/maya/languages.lua` | LSP setup and first-use tool/parser inventory       |
| `lua/maya/ai.lua`        | Provider switching and shared suggestion controls   |
| `lua/maya/pokemon.lua`   | Local dashboard sound bank                          |
| `lua/maya/session.lua`   | Native folder session save/restore                  |
| `lua/maya/reload.lua`    | Native file-change checks and disk diff             |
| `lua/maya/debug.lua`     | Python and Node debug adapters                      |
| `scripts/`               | Installer, bootstrap, and Ollama setup              |
| `tests/`                 | Installer and real editor integration checks        |

## Updates and removal

Plugin revisions are recorded in `lazy-lock.json`. Review and test updates before
committing the lockfile on `master`. See [maintenance](docs/MAINTENANCE.md) for
rollback, tool versions, testing, and complete uninstall instructions. Removing
maya-nvim never requires deleting LunarVim or Ollama models.

Configuration licensed GPL-3.0; LunarVim-derived mappings are attributed in
[NOTICE](NOTICE). Plugins retain their own licenses.
