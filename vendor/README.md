# Bundled AI plugins

These runtime source snapshots are loaded directly by lazy.nvim through `dir`
specs. They travel with maya-nvim and need no separate clones or patch application.
Repository updates update their source; local plugins have no lockfile pins.

| Directory         | Upstream                                                                                  | Fork base                                                                              |
| ----------------- | ----------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `minuet-ai.nvim`  | [milanglacier/minuet-ai.nvim](https://github.com/milanglacier/minuet-ai.nvim)             | `maya-nvim` branch `fork/minuet-cancel`, `fb376cbb88c99080fb44d01c323413108ad7e09a`    |
| `blink-edit.nvim` | [BlinkResearchLabs/blink-edit.nvim](https://github.com/BlinkResearchLabs/blink-edit.nvim) | `maya-nvim` branch `fork/blink-edit-async`, `06672de18f5ac1f44916ea15bcf90eae77f00dc7` |

The snapshots include the local coordination, cancellation, shared-source-context,
and model-label changes. Each plugin retains its original license and source
attribution. Runtime Lua, plugin entry points, formatting guidance, and focused
fork regression tests are included. Git history, images, caches, and model files
are excluded.

blink-edit exposes an optional `prediction_filter(snapshot, lines, metadata)`
callback, applied after response realignment to normal and prefetched results.
Returning false discards the result without retrying. Standalone defaults accept
results as before; Maya supplies its conservative local edit filter.

The shared semantic collector lives in `lua/maya/ai_context.lua`. It checks LSP
capabilities and uses standard hover, signature-help, definition, and type-definition
methods with each client's position encoding. Language syntax adapters locate
annotation references; neither plugin selects or assumes a particular LSP server.
