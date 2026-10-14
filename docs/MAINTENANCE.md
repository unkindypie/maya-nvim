# Maintenance and troubleshooting

## Checks and updates

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
bash -n install.sh bin/mvim
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
packages are upgraded by this repository.

## Markdown formatting hook

Enable the hook once per clone:

```sh
git config --local core.hooksPath .githooks
```

Commits automatically format staged `.md` files with Prettier, matching mvim's
Markdown formatter and project configuration. The hook prefers repository-local
Prettier, then maya-nvim's Mason installation, then Prettier on PATH. It requires
Python 3 and Prettier; install the formatter with `:MasonInstall prettier` in mvim
if needed. It respects `.prettierignore` and does not download tools on commit.

Fully staged files are also updated in the working tree. For partially staged
files, only the staged version is formatted; unstaged text stays untouched, so
the remaining working-tree diff may include formatting differences. Unstaged
Markdown files are left alone. A formatter error stops the commit before any
formatted content is staged.

## Pokémon dashboard audio

The personal config at `~/.config/mvim/init.lua` includes these defaults:

```lua
return {
  pokemon_sound_on_start = true,
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
are quiet. Playback uses 50% volume without changing the system volume. Headless
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
