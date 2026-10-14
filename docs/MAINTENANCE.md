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
different session. Explicit file arguments and stdin bypass automatic restore.
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
