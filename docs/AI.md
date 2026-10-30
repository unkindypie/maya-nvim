# Local AI suggestions

Cursortab is the sole local AI plugin. **One local model supplies both inline
completion and next-edit prediction**, using Maya's existing cached standard-LSP
collector. Local inference needs no cloud account or paid API. GitHub Copilot is
an independent opt-in provider; failures never cause a cloud fallback.

## Installation and models

The installer builds the bundled Cursortab Go daemon and configures Ollama.
It reuses Go 1.25+ or downloads a checksum-verified Go 1.27.3 into the Maya cache.
The binary is generated locally, never committed. Editor updates rebuild it too.

| Dedicated VRAM    | Recommended local model                             | Prompt format |
| ----------------- | --------------------------------------------------- | ------------- |
| 2 GB+ default     | `hf.co/sweepai/sweep-next-edit-1.5B:Q8_0`           | `sweep`       |
| 8 GB+ alternative | `hf.co/mradermacher/zeta-2.1-GGUF:Q4_K_M`           | `zeta-2.1`    |
| 8 GB+ alternative | `hf.co/bartowski/zed-industries_zeta-2-GGUF:Q4_K_M` | `zeta-2`      |

The 8 GB alternatives use Q4 weights to leave space for context and the desktop.
Sweep remains the default on larger GPUs too: both larger models scored below
focused Sweep in Maya's local comparison. They are explicit options, not an automatic upgrade.
Upstream benchmarks used Q8 Zeta-2.1; their quality and latency are not Q4 guarantees.
Zeta-2 scored slightly better for edits; Zeta-2.1 was quieter and faster in that
benchmark. See [upstream results](https://github.com/cursortab/cursortab.nvim#benchmarks)
and [Maya's measurements](AI_CANDIDATES.md). Two GB may require CPU offload.
Unknown/shared memory requires an explicit choice instead of assuming GPU capacity.

```sh
./install.sh --ai ollama
./install.sh --ai ollama --model hf.co/mradermacher/zeta-2.1-GGUF:Q4_K_M
./install.sh --ai ollama --model hf.co/bartowski/zed-industries_zeta-2-GGUF:Q4_K_M
./install.sh --ai off
```

Use `--engine sweep|zeta-2|zeta-2.1` for a custom model name. The format must match
the model's training. Setup pulls only missing weights, validates the local
completion endpoint and checks GPU residency with a reserve. Failed validation
keeps previous preferences. It does not remove downloaded models or silently
choose a smaller/cloud model. Other resident models may need to be unloaded.

Ollama's OpenAI route cannot set `num_ctx`. Setup therefore creates a dedicated
`maya-local-<hash>` alias sharing the chosen weights, with a 4,096-token context
for Sweep or 8,192 for Zeta. The source model's parameters remain unchanged.
Validation is an endpoint/residency smoke test, not a correctness score.

## Controls

- `Space ao` / `:MayaAI ollama`: enable or reload local AI.
- `Space ac` / `:MayaAI copilot`: select Copilot; authenticate with `:Copilot auth`.
- `Space ax` / `:MayaAI off`: cancel and disable AI.
- `Tab`: accept selected ordinary completion first, then a visible AI suggestion.
  Normal-mode Tab accepts an AI preview or retains jump-forward behavior.
- `Space an`, Insert `Ctrl-L` / `Alt-[`: request a suggestion.
- `Space aa`: accept. `Space ad` / `Ctrl-]`: dismiss until the next edit.
- `Space as`: status. `Space am`: edit saved AI preferences, then `Space ao` to reload.

Cursortab uses a 200 ms text-change debounce and 650 ms idle delay. The existing
personal settings `ai_completion_debounce_ms` and `ai_next_edit_debounce_ms` still
control those delays. Leaving Insert does not restart a pending text-change timer.
Automatic Normal-mode previews consisting only of newly added lines are withheld;
use Insert mode or an explicit request to ask for those additions. This avoids
unwanted exports or helper functions after finishing an edit. An unchanged saved buffer is quiet; explicit requests bypass that gate. Preview
ownership lasts until acceptance, dismissal or invalidation. Prefetch and automatic
cursor jumps are disabled. Acceptance has its own undo step. Ordinary completion
and snippets remain available with AI off.

## Preferences and migration

Preferences live in `stdpath('state')/ai.json`, never in the repository:

```json
{
  "schema": 2,
  "provider": "ollama",
  "model": "maya-local-<installer-generated-hash>",
  "source_model": "hf.co/mradermacher/zeta-2.1-GGUF:Q4_K_M",
  "engine": "zeta-2.1",
  "endpoint": "http://127.0.0.1:11434",
  "context_size": 8192
}
```

Old dual/single/completion-only preferences migrate to the saved `next_edit_model`,
or an existing Sweep model, otherwise Sweep 1.5B Q8. Provider and endpoint remain
unchanged. The old inline model/mode/format are retained under `legacy` for reference;
they no longer control execution. Downloaded weights are never deleted. Run the
installer once after upgrading to ensure the chosen weights and context alias exist.
Merely opening mvim does not download a replacement model. An old saved AI-off
preference stays off.

The removed installer flags `--ai-mode`, `--next-edit-model` and `--fim-format`
are replaced by `--model` and optional `--engine`. `Space am` now opens settings;
there is no mode picker. Existing personal debounce settings still work.

## Context and troubleshooting

Maya asynchronously collects hover, signature, definition and type-definition
context according to server capabilities. Lua/Python/TypeScript syntax adapters
locate anchors only. Prompt hooks read the bounded cache without waiting for LSP.
Stale buffer/cursor/definition snapshots are omitted. Cursortab uses the focused
cache view: low-priority definition snippets larger than 1,600 bytes are omitted,
while annotation-driven type snippets and hover/signature hints retain their budgets. Cursortab adds native history,
diagnostics and surrounding code; all three local model formats receive Maya context.

Use `:CursortabStatus`, `:CursortabShowLog`, and `Space as` to diagnose missing
suggestions. Each mvim process owns its own daemon under the state directory.
If the binary is missing, run `python3 scripts/build_cursortab.py` with
`NVIM_APPNAME=maya-nvim`, then restart mvim. Re-run the installer for model or
residency failures. A local OpenAI-compatible endpoint can also be configured
manually; its operator must set a matching model and context size.
