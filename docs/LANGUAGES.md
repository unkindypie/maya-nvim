# Language tools

`lua/maya/languages.lua` is the first-use installation inventory. A supported
filetype installs missing Mason tools and its parser asynchronously, then enables
LSP/highlighting in the existing buffer. Failures are reported once; retry with
`:MayaTools`. Offline editing still works. `:MasonLog` contains installation logs.
Unknown filetypes do not trigger arbitrary package downloads.

| Files         | LSP                      | Formatting / diagnostics                                                 |
| ------------- | ------------------------ | ------------------------------------------------------------------------ |
| Python        | Ruff native server + ty  | Ruff import organization and formatting                                  |
| JS/TS/React   | ts_ls + ESLint           | Prettier; project ESLint configuration                                   |
| JSON/JSONC    | jsonls                   | SchemaStore, Prettier; JSON parser supports JSONC highlighting           |
| Lua           | lua_ls + lazydev         | StyLua                                                                   |
| Shell         | bashls                   | shfmt, ShellCheck                                                        |
| Hyprland      | hyprls                   | Manual indentation; guides/Tree-sitter indentation disabled              |
| C/C++         | clangd                   | clang-format                                                             |
| Docker        | dockerls                 | hadolint                                                                 |
| YAML          | yamlls                   | SchemaStore, Prettier                                                    |
| HTML/CSS/SCSS | html/cssls               | Prettier                                                                 |
| Markdown      | marksman                 | Prettier                                                                 |
| PlantUML      | plantuml-lsp (on demand) | Syntax highlighting, local renderer diagnostics and live browser preview |
| Rust          | rust-analyzer            | rustfmt from the user's Rust toolchain                                   |

No C#/.NET installation is included. Rust is deliberately excluded from initial
bootstrap to exercise installation on first use. PlantUML tools are also deferred until a diagram is opened. Other listed tools/parsers and
Python/JS debug adapters are provisioned by the installer. Mason package versions
may move independently of `lazy-lock.json`; inspect installed versions in Mason,
and record/test tool upgrades rather than assuming the plugin lock pins tools.

## Python

Ruff replaces Black, isort and Python lint tools. ty handles type errors,
completion, navigation and hover. Ruff's hover is disabled to avoid competing
providers. Project `pyproject.toml` / Ruff configuration is respected. Formatting
sorts imports then formats code; it does not remove all unused imports or apply
unsafe fixes automatically. Use code actions for those decisions.

A valid project virtual environment is required to resolve third-party imports.
The existing playground `.venv` points at an old `/home/maxb` Python location;
project-local completion/navigation and type errors work, but stdlib navigation
and installed-package resolution can be degraded until Maya recreates that venv.
The editor installer does not replace project environments.

## C/C++ and vita-sdl

clangd searches for compilation databases in `build/mvim`, `build`, `build/linux`,
then the root. Build directories must describe real host paths and headers.
For `~/Desktop/cpp/vita-sdl`, run `make editor-tools` to create a separate native
Linux `build/mvim/compile_commands.json` and generated shader headers. Its
`docs/EDITOR.md` documents prerequisites and checks. Do not feed Docker
`/workspace` paths to host clangd. Vita-only code still requires the Vita build.

## Debugging

`Space dt` sets a breakpoint; `Space dc` starts/continues; `Space di/do/du` steps
in/over/out; `Space dU` toggles the UI. Python uses Mason's debugpy and the project
interpreter selected by nvim-dap-python. Node uses Mason's js-debug-adapter.

For TypeScript launch compiled JS with source maps, or use a project `.vscode/launch.json`
configuration specifying the runtime/loader required by that project. The default
current-file launch runs Node and cannot execute arbitrary TypeScript syntax
without a loader/build. Add project-specific configurations rather than global
assumptions. nvim-dap's launch.json support remains available.

## PlantUML diagrams

Open `.puml`, `.plantuml`, `.iuml` or `.pu` files for syntax highlighting and
PlantUML LSP completion, hover and diagnostics. Tools install asynchronously on
first use: checksum-verified PlantUML 1.2026.10 and plantuml-lsp pinned to
`dd37e40914b8c2826c360c8ee7d3a211f7e7af83`, under mvim's data directory. The setup
reuses the isolated Go toolchain used by Cursortab when necessary. Java must be
installed separately (for example `sudo apt install default-jre` on Ubuntu or
`brew install openjdk` on macOS). Graphviz is optional: preview/export uses the
bundled Smetana Java layout engine when `dot` is unavailable. Some diagram types
may still require Graphviz. The LSP remains an early-development project with
limited user-defined symbol support.

- `Space up` / `:PlantumlPreview`: toggle the current diagram's browser preview.
- `:PlantumlStop`: stop rendering and remove temporary preview files.
- `:PlantumlExport diagram.svg` (or `.png`): export current unsaved contents.
  Existing files require `:PlantumlExport!`. Paths with spaces use normal Ex escaping.
- `:PlantumlSetup`: install/check tools again after a setup failure or upgrade.

Preview is opt-in, local, asynchronous and refreshed after a 500 ms editing pause;
the browser polls the resulting SVG every second. One diagram per buffer is
supported. Relative includes resolve from the source file's directory. Invalid
edits keep the last valid image and report errors in mvim. Closing a buffer or
exiting stops its preview; export never saves the source buffer. Browser zoom
buttons and scrolling handle large diagrams.

Ordinary startup loads no PlantUML module, language server or Java process. Only
the lazy plugin/filetype registration is present. `MAYA_NVIM_NO_INSTALL=1` prevents
automatic downloads; already installed tools can still be used.
