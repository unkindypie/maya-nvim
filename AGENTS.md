# Supporting maya-nvim

## Purpose and boundaries

Maintain Maya's Neovim 0.12.5 configuration for Kitty and tmux. Familiar LunarVim
keybindings matter; implementations may change for reliability and maintenance.
Use `master`. Do not modify existing LunarVim files, launcher, or plugin store.
Every invocation and check must set `NVIM_APPNAME=maya-nvim` (use `bin/mvim`).

## Structure

Keep `init.lua` small. Editor defaults belong in `options.lua`; mappings in
`keymaps.lua`; plugin specs in `plugins/`; tools and filetype mappings in
`languages.lua`; theme selection in `theme.lua`; AI provider controls in `ai.lua`. Prefer supported Neovim APIs
and documented plugin APIs. Do not patch private LSP tables or add distribution
compatibility shims. Keep language metadata in one inventory. Personal overrides are loaded by
`user.lua` from `$XDG_CONFIG_HOME/mvim`; never overwrite that directory during
updates or commit a user’s personal configuration into this repository.

Keep configuration changes and new features backward compatible: existing
personal configs must keep working when new settings are omitted. Supply safe
defaults, preserve saved preferences, and document migrations. Remove or rename
settings/keybindings only when explicitly requested or with a compatible alias.

Keep repository small from any commited artifacts, too big images, etc. If
image is replaced, make sure to delete it from version history to increase speed of git clone.
Don't commit any not needed large artifacts.

## Workflow

Enable the repository's Markdown/Python formatting hook after cloning:
`git config --local core.hooksPath .githooks`. It uses the same Prettier and Ruff formatters as mvim.

1. Read the relevant module and upstream documentation before changing APIs.
2. Preserve user changes; update documentation with changed defaults/mappings.
3. Format Lua with StyLua and check Python/shell syntax.
4. Run relevant tests below. A plugin update requires startup and integration checks.
5. Commit coherent validated changes on master. Commit the plugin lockfile.
   Use prefixes like feat: ... or fix: ... or doc: ..., chore: ... in commit
6. After committing, if a feature seems to not indroduce big/critical changes - push master to its configured remote (`git push origin master`).
   Never force-push or rewrite remote history without explicit authorization;
   report push failures rather than silently leaving a commit unpushed.

Do not commit credentials, AI state, model blobs, generated parsers, logs, or
machine-specific shell configuration. AI preferences live under
`stdpath('state')/ai.json`. Never silently switch a local AI request to a cloud
provider. Keep one provider active and one suggestion engine active for the current mode.
Dual local mode uses one coordinator: Minuet after 200 ms in Insert mode and
Sweep after 650 ms in Insert or Normal mode. A valid visible preview owns the
preview until accepted, dismissed, or invalidated; never replace it on a timer.
Do not start competing inference while a preview or request is active. Shared
semantic context uses capability-checked standard LSP requests, never server names;
syntax adapters only locate anchors. Prompt hooks read cached context without waiting.
The bundled Minuet and blink-edit sources in `vendor/` are authoritative;
retain their licenses and provenance, exclude images/history, and test their public hooks.
Keep semantic collection independent of LSP server names and cover incomplete
annotated values in Lua, Python, and TypeScript.
Copilot and AI-off must cancel both local engines.

## Checks

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
bash -n bootstrap.sh install.sh bin/mvim
MAYA_NVIM_NO_INSTALL=1 MAYA_NVIM_NO_AI=1 bin/mvim --headless '+lua assert(vim.g.mapleader == " ")' +qa
# Real project tests require pynvim (install it in a disposable uv environment).
.local/test-env/bin/python tests/integration.py
.local/test-env/bin/python tests/advanced.py
.local/test-env/bin/python tests/languages.py
.local/test-env/bin/python tests/ui_helpers.py
.local/test-env/bin/python tests/diffview.py
.local/test-env/bin/python tests/theme_transparency.py
.local/test-env/bin/python tests/explorer.py
.local/test-env/bin/python tests/pokemon_audio.py
.local/test-env/bin/python tests/markdown_preview.py
.local/test-env/bin/python tests/swap_recovery.py
.local/test-env/bin/python tests/update.py
.local/test-env/bin/python tests/update_plugins.py
.local/test-env/bin/python tests/config_completion.py
.local/test-env/bin/python tests/completion_keys.py
.local/test-env/bin/python tests/ai_status.py
.local/test-env/bin/python tests/ai_local.py
.local/test-env/bin/python tests/ai_acceptance_keys.py
.local/test-env/bin/python tests/ai_edit_filter.py
.local/test-env/bin/python tests/ai_context.py
.local/test-env/bin/python tests/ai_annotations.py
.local/test-env/bin/python tests/ai_automatic.py
.local/test-env/bin/python tests/ai_coordination.py
.local/test-env/bin/python tests/ai_shared_context.py
.local/test-env/bin/python tests/ai_markdown_context.py
# Opt-in real model latency/residency measurement:
MAYA_NVIM_TEST_OLLAMA=1 .local/test-env/bin/python tests/ai_latency.py
```

`MAYA_NVIM_NO_INSTALL=1` disables automatic tool downloads during isolated
checks. `MAYA_NVIM_NO_AI=1` disables automatic AI activation. Tests must preserve
existing project files; temporary fixtures must be removed even on failure.
External-change tests must verify unsaved edits survive, not just clean reloads.
Document interactive checks and unverified prerequisites honestly.

The vita-sdl repository has its own AGENTS.md and pre-existing uncommitted work.
Read its rules before touching it; do not stage unrelated edits. Editor metadata
must describe native Linux compilation, never Docker `/workspace` paths.
