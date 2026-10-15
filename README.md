# 🌙 maya-nvim

Hi. I'm Maya and it's my Neovim config/distro.

A standalone Neovim 0.12.5 setup for Mac and Linux: **LunarVim muscle memory**, transparent
**Catppuccin Frappé**, modern language tools, **local AI**, and **safe collaboration** with
**external editors** such as **Codex** or **Claude Code**. Launch with **`mvim`**. Isolated from other nvim distros.

Installation is one command, with guided questions and automatic setup of missing
prerequisites. Existing tools are kept; incompatible versions receive manual
instructions.

## 💫 Install

Supported systems: **Fedora, Debian/Ubuntu, Arch, openSUSE,** and **macOS with
Homebrew**. Managed downloads support **x86-64** and **ARM64**.

**One-command installation** (clones into `~/maya-nvim`, or updates that checkout, then runs setup):

```sh
bash -c "$(curl -fsSL https://raw.githubusercontent.com/unkindypie/maya-nvim/master/bootstrap.sh)"
```

The command itself needs Bash and curl. The bootstrap can install missing Git
and Python; setup detects the remaining prerequisites or shows install command on failure.
System packages may require a sudo password. Homebrew on macOS must already be installed.

To choose another directory add this ENV at the start of the install script install command
(before `bash` separated by a space):
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

Missing tools install automatically; see [prerequisites and versions](docs/PREREQUISITES.md#prerequisites-and-versions) for details and manual fallback commands.

See [installer options](docs/PREREQUISITES.md#installer-options) for custom setup, AI choices, and update controls, or run:

```sh
./install.sh --help
```

Rerun the installer to update the same checkout and repeat setup; your personal configuration is preserved.

## 🌠 Personal configuration

Use `~/.config/mvim/init.lua` to extend the managed configuration without editing
this repository (`$XDG_CONFIG_HOME/mvim` when XDG_CONFIG_HOME is set). Installation
creates a commented example if the file does not already exist. `Space LC`
opens it; `Space Lc` still opens the managed entry point.

```lua
return {
  pokemon_sound_on_start = true, -- Play a Pokémon cry.
  pokemon_sound_on_start_volume_percentage = 50, -- 0–100; 0 mutes playback.
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

## 🌟 Daily use

Press Space for which-key. `Space f` finds files, `Space e` opens the explorer,
`Space st` searches text, and `Space w` saves. `H`/`L` switch buffers;
`Space c` closes one and `Space bo` closes all others.

Files format on save and reload after external changes; unsaved edits use native
conflict handling. Launching `mvim` without file arguments restores the folder's
saved files and tabs when enabled.

See [keybindings](docs/KEYBINDINGS.md), [language tools](docs/LANGUAGES.md), and
[sessions and troubleshooting](docs/MAINTENANCE.md) for more.

## 🌠 AI suggestions

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

## 💫 Configuration map

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

## 🌟 Updates and removal

Plugin revisions are recorded in `lazy-lock.json`. Review and test updates before
committing the lockfile on `master`. See [maintenance](docs/MAINTENANCE.md) for
rollback, tool versions, testing, and complete uninstall instructions. Removing
maya-nvim never requires deleting LunarVim or Ollama models.

Configuration licensed GPL-3.0; LunarVim-derived mappings are attributed in
[NOTICE](NOTICE). Plugins retain their own licenses.
