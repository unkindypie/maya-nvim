# Validation — 2026-10-14

## Automatic prerequisite installation

Fresh Docker containers running **Fedora 44** and **Ubuntu 24.04**, both x86-64,
passed real Git/Python bootstrap, missing system-package installation, verified
Neovim 0.12.5 / tree-sitter 0.26.1 / Node 22.23.3 downloads, and a second
prerequisite pass that installed/downloaded nothing. Both then passed full
editor installation with AI/audio/font setup disabled, including locked plugins,
Mason tools, parser compilation (`MAYA_BOOTSTRAP_OK`), and a headless launch
through the installed `mvim` executable.

A separate Ubuntu container passed the optional FantasqueSansMono Nerd Font
download/checksum, retained its font license, and skipped downloading it on a
second invocation. Package operations ran as root **inside containers**. Non-root
sudo commands, permission failures, manual rechecks, dry runs, unsupported/old
tools, and download corruption are covered by isolated tests with fake package
managers. No host system packages were installed.

Reproduce the Linux container checks with `bash tests/containers/run.sh`.
Arch, openSUSE, macOS/Homebrew, and ARM64 have command/asset coverage only; actual
installation on those platforms remains unverified. Docker does not test GUI
font selection, speakers, or systemd user services.

## Existing editor validation

Tested on Maya's Linux desktop, Neovim **0.12.5**, Node **22.23.1**, Tree-sitter
CLI **0.26.11**, Ruff **0.17.0**, ty **0.0.86**, clangd **23.1.0**, and Ollama
**0.40.4**. Plugin revisions are in `lazy-lock.json`.

## Passed

| Area                   | Evidence                                                                                                                                                                                                          |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Installation           | Full `install.sh --ai ollama --ollama-models-dir /mnt/ml/ollama --tmux-sessionizer ~/scripts/tmux-sessionizer` completed, reusing installed plugins/tools/models                                                  |
| Installer safety       | Unit tests cover repeat installation, managed block placement, paths containing spaces, dry-run, unrelated-launcher collision refusal, and missing prerequisites without changes                                  |
| Startup                | Clean headless startup; 26 plugins in the configuration, deferred loading where appropriate; no startup errors in real Kitty or isolated tmux                                                                     |
| Language inventory     | Python, TypeScript, JSON, YAML, Lua, shell, Docker, HTML, CSS, Markdown, Hyprland and Rust servers/parsers attached to test files                                                                                 |
| Python project         | In `~/Desktop/python/playground`, Ruff reported unused imports, organized imports and formatted code; ty detected/cleared a type error and returned completion and definition responses                           |
| JS/TS                  | TypeScript detected a deliberate type error; ESLint attached only with project configuration and reported `no-unused-vars`; Prettier formatted JS correctly                                                       |
| C/C++ project          | Separate host `make editor-tools` build; all **38** project/test translation units passed clangd checks; real `src/main.cpp` editor diagnostics had no errors and detected/cleared an injected unsaved type error |
| C++ regressions        | `make test`: **18/18 passed**; `make vita`: VPK built                                                                                                                                                             |
| First-use installation | Starting with no Rust server/parser installed, opening a Cargo fixture installed both and activated them in the same buffer, producing a real type diagnostic                                                     |
| Debugging              | Python and Node breakpoints, step-over, continue, termination; dap-ui loaded successfully                                                                                                                         |
| External edits         | Timer reloaded the same buffer in normal mode and idle insert mode, including atomic replacement; dirty edits were preserved; native diff showed a read-only disk snapshot                                        |
| Folder sessions        | Separate processes restored file buffers, **two tab pages**, splits and cursor positions; another folder stayed separate; explicit file arguments bypassed restore                                                |
| Close others           | `Space bo` kept the current unsaved buffer, closed other buffers/tab pages, preserved dirty buffers/tabs on cancellation, and discarded only after explicit approval                                              |
| AI                     | Real Ollama virtual text accepted through Tab; GitHub/off switching worked; AI-first Tab dispatch checked; no automatic cloud fallback                                                                            |
| Blame/comments         | Native comment shortcut toggled correctly; inline blame contained actual author, date and commit summary                                                                                                          |
| Desktop explorer       | Thunar selected; stub process verified a path containing spaces was forwarded as exactly one argument                                                                                                             |
| Kitty/tmux             | Inspected transparent Catppuccin dashboard and which-key in real Kitty; explorer and UI input/select hooks worked; isolated tmux used `tmux-256color`, RGB and expected navigation mappings                       |
| Pokémon sounds         | Dashboard text came from the local Lua bank; five startup processes produced different sounds without external commands/network                                                                                   |
| Isolation              | SHA-256 comparison: all **131** recorded LunarVim files unchanged; all **27** pre-existing dirty vita-sdl files unchanged at isolation check                                                                      |
| Integration files      | zsh/bash syntax checks passed; sessionizer discovers exactly one `~/maya-nvim` root entry                                                                                                                         |

## Performance and local AI

Five warm, installed **headless process** startups (including process launch/exit)
measured **79–87 ms**, median **82.6 ms**. The real Kitty dashboard reported
approximately **207 ms**. These are different measurements and do not include
first-time plugin/tool downloads, language-server indexing or cold model loading.
The Pokémon bank is a small local Lua table; AI activation is deferred to insert
mode and tools install asynchronously.

Reused `/mnt/ml/ollama` and the existing **qwen2.5-coder:7b** model; no replacement
model was downloaded. Setup's latest short warmed completion benchmark had a
median of **0.162 s**; real editor inline suggestions also worked. Ollama reported
about **4.53 GB GPU memory** for the loaded model on the RTX 3060 Laptop GPU
(6 GiB VRAM). This benchmark does not promise latency for arbitrary contexts.
The completion request timeout allows a cold load; warm completion remains fast.

## Practical limits / existing environment

- Live GitHub-generated text was not verified: that requires Maya's sign-in and
  subscription. The plugin loaded and provider switching was exercised.
- Playground's existing `.venv` points at a moved `/home/maxb` Python installation.
  Project-local features passed; third-party/stdlib navigation may need a repaired
  venv. The installer did not rewrite that environment.
- C++ checks describe native Linux compilation. Vita-only code is covered by its
  separate build, not host clangd. `--check-lines=1` still parses/checks the entire
  translation unit while limiting unrelated per-token refactoring self-tests;
  clangd 23 otherwise reports ExtractFunction/ExpandDeducedType self-test failures.
- Health reports optional disabled image/LaTeX/Mermaid tooling and unused Mason
  ecosystems as unavailable. Those are outside this configuration's feature set.
  Headless checks before VimEnter can report deferred UI hooks as not installed;
  the hooks were verified after real UI startup.
- Maya's existing tmux configuration inherits terminal naming that can produce a
  Neovim terminal-health warning. The isolated tmux check used `tmux-256color`.
  Kitty/tmux configuration was intentionally left untouched.
- macOS portability is implemented but untested. Ollama installation there is
  manual. Language-tool upgrades are independent of the plugin lockfile.

## Reproduce

```sh
python3 -m unittest discover -s tests -p 'test_installer.py' -v
.local/test-env/bin/python tests/integration.py
.local/test-env/bin/python tests/advanced.py
.local/test-env/bin/python tests/languages.py
.local/test-env/bin/python tests/ui_helpers.py
```

Set up the disposable pynvim environment as described in MAINTENANCE.md.
Raw development logs/screenshots remain in `/tmp`, not in the repository.

## Personal configuration extension

Real startup tests cover options/keymap precedence, merged plugin options,
disabling a bundled plugin, importing and loading an additional local plugin,
Lua module lookup, personal filetype files, separate personal plugin locks,
missing configuration, malformed Lua, invalid options and setup failures.
Installer tests verify that existing personal configuration is not overwritten.

Explorer key tests verify Tab expands directories, opens files without closing
or losing focus, and Enter opens the selected file and closes the sidebar.
