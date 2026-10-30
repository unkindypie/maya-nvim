# Native Copilot integration — 2026-10-30

Cursortab now handles the opt-in Copilot provider through Neovim LSP; the separate
copilot.lua plugin is removed. `tests/ai_copilot.py` uses the real Cursortab daemon
and an in-process simulated Copilot LSP transport to verify request bridging,
preview rendering, Tab acceptance and AI-off client shutdown without cloud access.
Provider migration tests also cover local/Copilot/off switching and delayed Mason
installation after disabling Copilot. Existing completion-menu key tests pass.
Live GitHub authentication and real Copilot prediction quality remain unverified.

# Cursortab migration validation — 2026-10-30

Validated on Neovim 0.12.5, Ollama 0.40.4 and an RTX 3060 Laptop with 6 GB VRAM.
The [experiment report](AI_CANDIDATES.md) separates controlled corpus results,
native typing, model comparison and remaining limitations.

- All 69 Python unit tests and bundled Cursortab Go tests passed.
- Real daemon tests passed automatic startup, preview ownership, cancellation,
  delayed replies, Insert/Normal acceptance, undo boundaries and Normal-mode
  append suppression with explicit-request bypass.
- Cached-context/staleness tests, six real-LSP fidelity fixtures, annotation and
  collector tests, AI status, completion keys and personal-config completion passed.
- Editor integration, all 11 language fixtures, plugin updates, repository updates
  and theme transparency passed. Startup, Python compilation and shell syntax passed.
- Missing-Go installation downloaded and checksum-verified the isolated toolchain
  and built the daemon successfully.

Real LSP startup checks ran with normal tool activation: `MAYA_NVIM_NO_INSTALL=1`
also suppresses automatic LSP activation in this configuration. Headless isolated
checks used it. All Neovim checks used `NVIM_APPNAME=maya-nvim` through `bin/mvim`.
No 8 GB+ GPU, interactive human acceptance review, or new cross-platform container
installation was performed for this migration. Earlier validation follows.

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

## 2026-10-15: GPU-aware setup and Qwen 3B Base

On Maya's RTX 3060 Laptop GPU (6 GiB), installed `qwen2.5-coder:3b-base` in the
existing Ollama store and selected it without removing other models. With a
2,048-token context, the short native FIM benchmark measured **2.93 s** after
unloading the runner and **0.049 s median** across three warmed runs. Ollama
reported **2,085,974,179 bytes** allocated on GPU, with the model fully on GPU.
These are short benchmark timings, not end-to-end editor latency or quality scores.

Streaming `/v1/completions` produced syntax-valid temporary Python, Lua, and C
completion fixtures (about 0.06–0.08 s warmed). An unconstrained first C fixture
exceeded its 32-token budget; the constrained expression fixture completed and
passed GCC syntax checking. A real mvim Minuet backend request also returned
`return a + b` using the saved 3B Base model. Raw reports remain in local state,
outside Git.

Automated checks cover NVIDIA/AMD detection, unknown and shared memory, menu
selection, Copilot/skip avoiding Ollama setup, preservation of saved models, and
`q` closing native quickfix/location-list results. AI reselection reloads the
saved model with one notification; status includes provider details for 10 seconds.

## 2026-10-16: coordinated local completion and next-edit

- Published pinned Minuet and blink-edit fork branches on this repository's
  remote, retaining upstream history/licenses. Fresh independent lazy.nvim
  clones load both plugins and their public cancellation APIs. Other plugin
  pins are unchanged.
- Fork regressions cover cancellation, transport cancellation, late callbacks,
  older responses arriving after newer requests, changed buffer/cursor/tick/model
  identities, scheduled acceptance cancellation, and asynchronous reference caching.
- Real editor regressions cover rapid Ollama/Copilot/off switching for both
  local engines, single/dual mode handover, normal idle triggers, native request
  options, Qwen/Mellum prompt formats, ordinary completion keys, and undo that
  preserves preceding typed text. LSP hints return immediately from the cache;
  delayed or invalidated replies are discarded.
- 65 unit tests pass, including saved-choice migration, unknown VRAM, selective
  downloads, custom endpoints, failed residency preserving preferences, and
  Sweep's missing Hugging Face tag alias fallback. Shell/Python syntax, StyLua,
  startup, and the editor integration suites pass. The integration test now
  waits for the type diagnostic instead of assuming it precedes Ruff's results.
- On Maya's RTX 3060 Laptop GPU (6,144 MiB), Qwen 1.5B Base Q8 and Sweep Q8
  both remain GPU-resident at 4,096 context tokens: approximately 1,745 MiB and
  1,577 MiB respectively, with about 2,021 MiB free in the measured run. Short
  warm probe medians were 0.051 s and 0.106 s. These are small cached-prefix
  probes, not general latency or quality guarantees.
- Real Minuet generated and accepted `return a + b`; Sweep corrected a Python
  method-name typo and generated an insertion in single-model Insert mode. Undo
  restored the preceding user edit. Maya's saved choice now uses the 6 GB dual
  preset; her previous 3B weights remain available on disk.
- Native vita-sdl clangd diagnostics, unsaved C++ error detection/clearing, Python
  Ruff/ty, Rust, debugging, other configured languages, sessions, external file
  changes, explorer, Markdown rendering, swap recovery, updates, personal-config
  completion, and existing UI checks pass.

Not verified on physical 2–4 GB or 8 GB+ GPUs, AMD, or macOS. Mellum and the
7B Q4 preset have prompt/configuration tests but were not downloaded or benchmarked.
Copilot switching and adapter loading are covered; authenticated cloud inference
was not tested. Sweep is still an alpha plugin and model predictions can be
unhelpful; acceptance stays explicit. No upstream PR was submitted.

New checks (the inference test requires the selected Ollama models):

```sh
.local/test-env/bin/python tests/ai_local.py
.local/test-env/bin/python tests/ai_context.py
MAYA_NVIM_TEST_OLLAMA=1 .local/test-env/bin/python tests/ai_inference.py
```
