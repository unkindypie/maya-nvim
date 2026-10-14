# Supporting maya-nvim

## Purpose and boundaries

Maintain Maya's Neovim 0.12.5 configuration for Kitty and tmux. Familiar LunarVim
keybindings matter; implementations may change for reliability and maintenance.
Use `master`. Do not modify existing LunarVim files, launcher, or plugin store.
Every invocation and check must set `NVIM_APPNAME=maya-nvim` (use `bin/mvim`).

## Structure

Keep `init.lua` small. Editor defaults belong in `options.lua`; mappings in
`keymaps.lua`; plugin specs in `plugins/`; tools and filetype mappings in
`languages.lua`; AI provider controls in `ai.lua`. Prefer supported Neovim APIs
and documented plugin APIs. Do not patch private LSP tables or add distribution
compatibility shims. Keep language metadata in one inventory. Personal overrides are loaded by
`user.lua` from `$XDG_CONFIG_HOME/mvim`; never overwrite that directory during
updates or commit a user’s personal configuration into this repository.

## Workflow

1. Read the relevant module and upstream documentation before changing APIs.
2. Preserve user changes; update documentation with changed defaults/mappings.
3. Format Lua with StyLua and check Python/shell syntax.
4. Run relevant tests below. A plugin update requires startup and integration checks.
5. Commit coherent validated changes on master. Commit the plugin lockfile.
   Use prefixes like feat: ... or fix: ... in commit
6. After committing, push master to its configured remote (`git push origin master`).
   Never force-push or rewrite remote history without explicit authorization;
   report push failures rather than silently leaving a commit unpushed.

Do not commit credentials, AI state, model blobs, generated parsers, logs, or
machine-specific shell configuration. AI preferences live under
`stdpath('state')/ai.json`. Never silently switch a local AI request to a cloud
provider. Keep exactly one suggestion backend enabled.

## Checks

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
bash -n install.sh bin/mvim
MAYA_NVIM_NO_INSTALL=1 MAYA_NVIM_NO_AI=1 bin/mvim --headless '+lua assert(vim.g.mapleader == " ")' +qa
# Real project tests require pynvim (install it in a disposable uv environment).
.local/test-env/bin/python tests/integration.py
.local/test-env/bin/python tests/advanced.py
.local/test-env/bin/python tests/languages.py
.local/test-env/bin/python tests/ui_helpers.py
.local/test-env/bin/python tests/explorer.py
```

`MAYA_NVIM_NO_INSTALL=1` disables automatic tool downloads during isolated
checks. `MAYA_NVIM_NO_AI=1` disables automatic AI activation. Tests must preserve
existing project files; temporary fixtures must be removed even on failure.
External-change tests must verify unsaved edits survive, not just clean reloads.
Document interactive checks and unverified prerequisites honestly.

The vita-sdl repository has its own AGENTS.md and pre-existing uncommitted work.
Read its rules before touching it; do not stage unrelated edits. Editor metadata
must describe native Linux compilation, never Docker `/workspace` paths.
