# Maintenance and troubleshooting

## Checks and updates

`./install.sh` updates a clean `master` checkout from origin with a fast-forward-only
pull, reloads the updated installer, and reruns setup. The one-command bootstrap
also reuses and updates its existing destination. Use `--no-update` to keep the
current revision, or `--dry-run` to inspect the plan without fetching. Dirty trees,
other branches, unrelated origins, divergence, and network failures stop the
update without discarding work; resolve the reported issue or opt out of updating.

Inside mvim, `Space M u` / `:MayaUpdate` performs the fast-forward pull and then
installs missing plugins and restores the configuration's committed versions.
Both plugin phases run in fresh background processes, so newly pulled plugin
specifications are used without hot-reloading the running editor. Existing
personal-only plugin pins are retained; managed pins come from the pulled
lockfile. Temporary runtime lockfiles keep the repository clean. A personal
lockfile is saved only after the final plugin phase succeeds. The two phases
load independent lock snapshots so installation cannot replace the desired
managed versions with currently installed versions before restoration.

Progress stays visible in the statusline and notification while running. The
completion message reports the config revision and plugin result, including
when the config was already current. Restart after success. `Space M U` /
`:MayaUpdateStatus` shows the latest result in this session; `:MayaUpdateLog`
opens the persistent log at `stdpath('state')/maya-update.log`. A failed plugin
phase does not undo an already completed pull: retry the update after resolving
the logged cause. Dirty checkouts, including lockfile edits from a previous
manual `:Lazy update` or `:Lazy sync`, still require deliberate resolution.

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
bash -n bootstrap.sh install.sh bin/mvim
MAYA_NVIM_NO_INSTALL=1 MAYA_NVIM_NO_AI=1 MAYA_NVIM_NO_SESSION=1 bin/mvim --headless '+checkhealth' +qa
```

For real integration tests, create a disposable test environment:

```sh
uv venv .local/test-env
uv pip install --python .local/test-env/bin/python pynvim
.local/test-env/bin/python tests/integration.py
.local/test-env/bin/python tests/advanced.py
.local/test-env/bin/python tests/languages.py
.local/test-env/bin/python tests/ui_helpers.py
.local/test-env/bin/python tests/explorer.py
.local/test-env/bin/python tests/pokemon_audio.py
.local/test-env/bin/python tests/markdown_preview.py
.local/test-env/bin/python tests/swap_recovery.py
.local/test-env/bin/python tests/update.py
.local/test-env/bin/python tests/update_plugins.py
.local/test-env/bin/python tests/config_completion.py
.local/test-env/bin/python tests/completion_keys.py
.local/test-env/bin/python tests/ai_status.py
```

Tests for Maya's existing Python/C++ projects require those projects. Advanced
tests need the generated C++ database and local Ollama. They create temporary
fixtures and inject unsaved errors, not edits to existing source files. Test
runtimes and logs stay outside Git.

Use `:Lazy update` deliberately, review `lazy-lock.json`, run the checks, then
commit on master. Restore an earlier lockfile with Git and use `:Lazy restore`
to roll plugins back. Tree-sitter updates require matching parser updates;
`:TSUpdate` handles that. Mason packages have independent versions; use its UI
for version selection and record tool upgrades. Neither Neovim nor system
packages are explicitly upgraded by this repository. Missing tools can be installed
with confirmation; see [prerequisite setup and recovery](PREREQUISITES.md).

## Markdown and Python formatting hook

Enable the hook once per clone:

```sh
git config --local core.hooksPath .githooks
```

Commits automatically format staged `.md` files with Prettier, matching mvim's
Markdown formatter and project configuration. The hook prefers repository-local
Prettier, then maya-nvim's Mason installation, then Prettier on PATH. It requires
Python 3 and Prettier; install the formatter with `:MasonInstall prettier` in mvim
if needed. It respects `.prettierignore` and does not download tools on commit.
Staged `.py` files are formatted with `ruff format`, using Ruff on PATH or
maya-nvim's Mason installation. Install missing Ruff with `:MasonInstall ruff`
or `pipx install ruff`. Ruff reads the project's formatting configuration.

Fully staged files are also updated in the working tree. For partially staged
files, only the staged version is formatted; unstaged text stays untouched, so
the remaining working-tree diff may include formatting differences. Unstaged
Markdown and Python files are left alone. A formatter error stops the commit;
formatting already completed for the other language may remain staged.

## Optional local AI during installation

Fresh interactive installations offer GPU-aware local edit models,
GitHub Copilot, and **Skip Ollama models installation**. Unknown VRAM requires
an explicit choice. Saved provider/model/endpoint preferences survive reruns;
old local settings migrate to one Cursortab model; the previous inline model is retained as migration metadata. See
[AI setup](AI.md) for model tiers, migration, and memory validation.

The choice is saved in `ai.json`, also used by `:MayaAI`; no additional personal
config setting is required. Noninteractive fresh installs leave AI off unless
`--yes`, `--ai ollama`, or `--model` is passed. Dry runs and link-only installs
perform no AI installation.

## Pokémon dashboard audio

The personal config at `~/.config/mvim/init.lua` includes these defaults:

```lua
return {
  pokemon_sound_on_start = true,
  pokemon_sound_on_start_volume_percentage = 50, -- 0–100; 0 mutes playback.
  reopen_tabs = true,
  -- Other options, plugins, and setup can also go here.
}
```

The installer asks both questions when creating a new config in an interactive
terminal. Noninteractive installs and `./install.sh --yes` use `true` defaults.
Use `--no-pokemon-sound-on-start` or `--no-reopen-tabs` to explicitly turn either
off in a new config. Reinstallation preserves existing personal configs and does
not ask again; edit that file to change preferences. Lua uses lowercase `true`
and `false`. Missing settings use the defaults above.

After the dashboard renders, mvim asynchronously requests the displayed Pokémon's
game cry from [PokéAPI](https://pokeapi.co/docs/v2#pokemon). This is a game sound,
not a spoken recording of the dashboard quote. Cached `.ogg` files live under
`stdpath('cache')/pokemon-cries`; repeat launches play from cache without network
access. The first available player is used: `mpv`, `ffplay`, `pw-play`, or `paplay`.
Downloads require `curl`. Missing tools, offline requests, and playback failures
are quiet. Playback defaults to 50% volume without changing the system volume. Set
`pokemon_sound_on_start_volume_percentage` to a number from 0 to 100 to adjust it. Headless
launches skip audio, and each launch plays at most once.

To disable it, set `pokemon_sound_on_start = false` in your personal config's
returned table, or launch with `MAYA_NVIM_NO_SOUND=1`. The older
`vim.g.maya_pokemon_sound = false` override still works.
Pokémon assets are excluded from the code's GPL-3.0 license; see `LICENSE` and `NOTICE`.

## External changes

A one-second timer calls native `checktime` for loaded files, plus focus/buffer
checks. Command prompts/terminal mode defer processing until safe. Normal and
idle insert mode do not require leaving the buffer. Native behavior decides
whether reloading is safe; dirty buffers are never force-reloaded.

If Codex changes a file Maya has edited, keep the buffer at the native prompt
and use `:MayaDiffDisk` (`Space bd`). The left buffer is Maya's unsaved text;
the other window is a read-only disk snapshot. Use native `do` to pull desired
hunks into the editable buffer, inspect the result, close the snapshot, run
`:diffoff`, and save deliberately. The snapshot does not update the file.
There is no automatic three-way merge or forced write. Native swap recovery
is available after a crash; sessions do not preserve deliberately discarded text.

## Folder sessions

Persistence writes native session files beneath `stdpath('state')/sessions` on
exit when file buffers are open. No-argument startup restores the current
folder's buffers, tab pages, splits and cursor positions. Branch changes do not select a
different session. Set `reopen_tabs = false` to disable automatic restoration;
manual save/restore still works. Successful automatic restoration shows the
same launch's Pokémon dashboard quote in a top-right notification and plays
its cry if sound is enabled. Explicit file arguments and stdin bypass automatic restore.
`Space bs/br` save/restore manually. To exit without replacing a saved session,
run `:lua require('persistence').stop()` before quitting. Concurrent editors in
the same folder use the last session saved; file contents still use native
conflict handling. Session files are machine-local, not committed.

## Common issues

- Tool install failed: `:MasonLog`, then `:MayaTools`. Install reported runtimes
  (Node/npm, a Rust toolchain, etc.) yourself; the installer does not run sudo.
- Missing icons: install/select a Nerd Font in your terminal.
- C++ header errors: regenerate the real host compilation database; do not
  suppress diagnostics or point host clangd at Docker paths.
- Python import errors: repair the project's virtual environment, not the global
  editor configuration. The playground has an old moved-environment path.
- Clipboard: Maya uses Wayland `wl-copy`; another desktop may need its clipboard
  provider installed. Inspect `:checkhealth vim.provider`.
- AI: see [AI.md](AI.md); status errors never cause cloud fallback.
- Kitty/tmux keys: test Kitty directly first. Keep terminal settings separate;
  this installer does not change Kitty/tmux configurations.

## Uninstall / rollback

1. Close mvim. Remove `~/.config/maya-nvim` and `~/.local/bin/mvim` **only if they
   are the links installed by this repository**. Also remove the installed
   `~/.local/libexec/maya-nvim/mvim` executable symlink. Leave `lvim` alone.
2. Remove the `# >>> maya-nvim >>>` managed block from `.zshrc`, and the
   `# >>> maya-nvim directory >>>` block from the optional sessionizer. Dated
   backups are beside those files; restoring an old backup replaces later edits,
   so removing only the managed block is usually preferable.
3. Optionally remove maya-nvim's data/state/cache directories under your XDG
   paths. Keep them if you want to retain sessions, undo or installed tools.
4. If no other applications need the managed Ollama server, run
   `systemctl --user disable --now maya-nvim-ollama.service`, remove that unit
   from `~/.config/systemd/user`, and run `systemctl --user daemon-reload`.
5. Ollama models and binaries are shared resources; removal is separate and
   manual. **Do not delete `/mnt/ml/ollama` as part of editor uninstall.**

The repository itself can then be moved or removed. No system Neovim defaults or
LunarVim configuration need restoration.

## Swap recovery

Interactive startup shows a floating recovery choice when a file has an existing
swap: recover unsaved edits, open the disk version read-only, or skip for now.
Session restoration continues with other files. No swap is deleted automatically.
After recovery, review and save your buffer; use native `:recover` for additional
recovery files. Headless invocations retain Neovim's native swap handling.

## Personal config completion

Place `---@type MayaConfig` immediately above `return {` in
`~/.config/mvim/init.lua`. New installer examples include this annotation.
LuaLS loads the config schema, Neovim option types, and lazy.nvim plugin types
for completion and hover help, including nested theme fields. The annotation is
optional and existing unannotated configs still work. For `theme`, a string with
`/` is a GitHub `owner/repository` and installs that plugin; a string without `/`
is an already-installed colorscheme name and installs nothing. For example,
`"catppuccin/nvim"` selects the repository, while `"catppuccin-frappe"` selects a
colorscheme. Repository names ending in `-nvim` also try the colorscheme name without that
suffix when the literal name is unavailable: `theme = "savq/melange-nvim"` loads
`melange`. For repositories with a different colorscheme name, use a `MayaTheme`
table such as `{ plugin = "savq/melange-nvim", name = "melange" }`. The table
sets `plugin`, `name`, `module`, and `opts` explicitly. Arbitrary plugin-specific
`opts` remain controlled by each plugin's types.
