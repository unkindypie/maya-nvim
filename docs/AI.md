# AI suggestions

Choose Ollama, GitHub Copilot, or off with `Space ao/ac/ax` or
`:MayaAI ollama|copilot|off`. Ordinary Blink/LSP/snippet completion remains
available with every choice. Local requests never fall back to cloud services.
`Space as` explains the active models, endpoint, mode, and controls for ten seconds.

## Local presets

| Estimated dedicated VRAM | Inline completion            | Next-edit     |
| ------------------------ | ---------------------------- | ------------- |
| 2–4 GB                   | Sweep, single-model mode     | Sweep 1.5B Q8 |
| 6 GB                     | Qwen2.5-Coder 1.5B Base Q8   | Sweep 1.5B Q8 |
| 8 GB+                    | Qwen2.5-Coder 7B Base Q4_K_M | Sweep 1.5B Q8 |
| 8 GB+ alternative        | Mellum 4B-SFT-All Q8         | Sweep 1.5B Q8 |

Exact tags:

- `qwen2.5-coder:1.5b-base-q8_0`
- `qwen2.5-coder:7b-base-q4_K_M`
- `hf.co/JetBrains/Mellum-4b-sft-all-gguf:Q8_0`
- `hf.co/sweepai/sweep-next-edit-1.5B:Q8_0`

The Sweep repository currently does not resolve its `Q8_0` shorthand. Setup
reports this and downloads the explicit
`sweep-next-edit-1.5b.q8_0.v2.gguf` asset, then creates the requested local name
as an alias. Both names share the same weights; no second model blob is needed.
Other download failures stop setup and keep previous preferences.

These are estimates, not minimum guarantees. Context, KV cache, desktop usage,
and other GPU applications consume memory too. At 2 GB, Sweep may need CPU
offloading and be slow. Setup checks model metadata and residency after warm-up,
reserving at least 512 MiB or 10% of dedicated VRAM. If a pair cannot stay
resident, interactive setup offers single mode; unattended setup fails with a
retry command instead of silently changing models. It does not evict unrelated
models or change shared Ollama service settings. Explicit profile switches can
release the previously selected completion model from memory, keeping its weights
on disk. Dual validation keeps its selected pair resident rather than repeatedly
unloading it between probes.

Detection uses `nvidia-smi` or readable AMD sysfs counters with Python's standard
library. macOS system memory is reported as shared memory, not dedicated VRAM.
Unknown VRAM requires an explicit menu choice; unattended installation requires
explicit local-model arguments, Copilot, or off. `--yes` does not guess unknown
hardware. A 5 GB GPU receives the conservative single-model recommendation.

## Installation and migration

The installer asks before setting up local models and also offers **GitHub
Copilot** and **Skip Ollama models installation**. Copilot needs `:Copilot auth`;
it downloads no Ollama models. Skipping leaves AI off and normal completion on.
Existing provider/model/endpoint preferences survive reruns.

```sh
# Small dual preset:
./install.sh --ai ollama --ai-mode dual \
  --model qwen2.5-coder:1.5b-base-q8_0 \
  --next-edit-model hf.co/sweepai/sweep-next-edit-1.5B:Q8_0

# One model for insertions and replacements:
./install.sh --ai ollama --ai-mode single

# Existing completion-only setup remains supported:
./install.sh --ai ollama --model your-existing-model
```

`--model` alone retains its original completion-only meaning. New settings are
optional: absent `local_mode` means legacy completion-only mode, without a Sweep
download. An existing custom endpoint keeps its previous transport. New dual
presets use the native Ollama API; custom dual models require the appropriate
`--fim-format qwen|mellum`. Single mode uses `--next-edit-model`, not `--model`.

`--ollama-models-dir PATH` selects storage when starting a managed server.
A running server retains its existing storage and settings. Missing Ollama can
be installed user-locally on Linux with zstd and a working systemd user session;
macOS users install/start Ollama separately. See [prerequisites](PREREQUISITES.md).
No system-wide environment variables are changed.

Preferences live in `${XDG_STATE_HOME:-~/.local/state}/maya-nvim/ai.json`, outside
Git and the personal editor configuration. For example:

```json
{
  "provider": "ollama",
  "local_mode": "dual",
  "model": "qwen2.5-coder:1.5b-base-q8_0",
  "next_edit_model": "hf.co/sweepai/sweep-next-edit-1.5B:Q8_0",
  "endpoint": "http://127.0.0.1:11434",
  "fim_format": "qwen"
}
```

Use `local_mode: "single"` for Sweep in both modes, or `"completion-only"` for
the previous Minuet behavior. Model changes require pulling the model first or
rerunning setup. `Space ao` reloads saved settings without downloading anything.
Validation measurements are stored separately in `ollama-validation.json`.

## Editing behavior

Dual mode uses Minuet automatically in Insert mode and Sweep after 800 ms of
Normal-mode idle. Single mode uses Sweep's next-edit engine for both insertions
and replacements, including Insert mode; it does not use a fabricated Sweep FIM
template. Duet is disabled. Special, read-only, unmodifiable, and large buffers
are excluded.

- Tab accepts a selected ordinary completion first, then a valid AI suggestion.
- Enter retains ordinary selected-completion acceptance.
- Normal Tab accepts Sweep when visible, otherwise keeps jump-forward behavior.
- `Space an` requests next-edit; `Space aa` accepts; `Space ad` dismisses.
- Ctrl-] dismisses; leaving Insert mode cancels its outstanding request.
- Ctrl-L / Alt-[ cycle Minuet or Copilot inline suggestions, not Sweep edits.
- Arrow navigation and the ordinary completion menu cancel AI previews.

Acceptance stays explicit and undoable. Provider changes, AI-off, and mode
handover cancel outgoing requests. Monotonic generations reject late callbacks;
display and acceptance also check provider, buffer, changedtick, cursor, and
mode. Old results cannot clear newer requests or overwrite intervening edits.

## Context and prompt formats

New Minuet presets consume a bounded asynchronous LSP cache for hover types, signatures,
and up to two definition snippets. Requests target a nearby receiver before
`.` / `:` / `->` when possible. Missing or slow LSP replies simply leave hints
absent; typing and prompt construction never wait for them. Entries expire after
two seconds and invalidated results are discarded. Local file snippets are
bounded and read asynchronously when not already loaded.

Sweep uses blink-edit's references and edit history. Its provider does not ask
for hover or definitions, so it does not have equivalent type awareness.

New Minuet presets allow 6,000 source characters and 1,500 LSP-hint characters;
Ollama separately receives a 4,096-token context and a 96-token output cap.
Sweep receives a 4,096-token context, a 512-token output cap, a 21-line edit
window, three history entries, and bounded references. Character budgets and
estimated snippet tokens are not exact tokenizer counts. Server context limits
remain authoritative. Requests time out after ten seconds.

Qwen uses `<|fim_prefix|>…<|fim_suffix|>…<|fim_middle|>`. Mellum uses its
suffix-first `<fim_suffix>…<fim_prefix>…<fim_middle>` format and filename sections.
See [Mellum's model card](https://huggingface.co/JetBrains/Mellum-4b-sft-all-gguf).
Native Ollama requests are built through Minuet's documented prompt/transform
hooks; the OpenAI-compatible endpoint cannot set `num_ctx` directly. See
[Ollama context-size documentation](https://docs.ollama.com/api/openai-compatibility#setting-the-local-context-size).

## Pinned plugin patches

The forks are hosted as dedicated `fork/minuet-cancel` and
`fork/blink-edit-async` branches of the maya-nvim remote, separate from `master`.
Each keeps upstream history and license and adds focused patch commits. This
requires no separate repositories or GitHub API token. lazy.nvim clones each
branch as its own named plugin; commit pins prevent accidental branch updates.

The Minuet fork exposes public `action.cancel()` and guards request identities.
The blink-edit fork adds public cancellation, mode predicates, async cached LSP
references, and stale-response checks. Upstream history and licenses remain
intact; no private LSP tables or runtime monkey patches are used. Pins belong in
the plugin specs and lockfile. Fork regression tests cover delayed callbacks and
request identity changes; maya-nvim tests cover switching, mode handover,
completion keys, prompts, LSP caching, and undo.
