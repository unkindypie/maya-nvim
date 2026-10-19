# AI suggestions

Choose Ollama, GitHub Copilot, or off with `Space ao/ac/ax` or
`:MayaAI ollama|copilot|off`. Ordinary Blink/LSP/snippet completion remains
available with every choice. Local requests never fall back to cloud services.
`Space as` explains the active models, endpoint, mode, and controls for ten seconds.
`Space am` opens the local-mode picker: **Dual** runs inline completion plus
Sweep next edits, **Single** runs Sweep only, and **Completion-only** runs only
the saved inline model. Choosing a mode activates Ollama immediately and saves
that choice in `ai.json`, preserving model names, endpoints, and other preferences.
Canceling the picker keeps the current settings. The picker does not download models.

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

Dual mode requests Minuet after 200 ms of Insert-mode inactivity. Sweep becomes
eligible after 650 ms in Insert or Normal mode, waiting for pending Minuet work
and any visible preview. A valid preview has no expiry: elapsed time never
replaces it or launches competing inference. Typing cancels stale work and gives
Minuet priority. After acceptance, Sweep waits another 650 ms without edits.
Explicit dismissal suppresses automatic suggestions until the next edit.
Explicitly enabling/reloading Ollama (`Space ao`) or choosing a local mode
clears that dismissal pause and restarts scheduling. `Space ax` disables AI;
it is separate from dismissing one preview or choosing the single/dual mode.
`Space as` distinguishes provider enablement, buffer eligibility and the current
scheduler state: waiting for a pause/model, suggestion ready, selected editor
completion, dismissal, or no suggestion to show. An enabled provider does not
prove that the endpoint is reachable or that its model returned useful text.
Single mode uses only Sweep; completion-only mode retains the saved Minuet model
and endpoint. Special, read-only, unmodifiable, and large buffers are excluded.

Sweep may return no preview. Local suggestions are filtered before display:
edits must stay within three lines of the cursor, affect at most three existing
nonblank lines, add at most eight lines and grow by at most 1,200 bytes. Hunks
that remove more nonblank lines than they add are rejected. This deliberately
suppresses deletion-only edits, truncated response windows and broad rewrites,
including some legitimate refactors. Rejection does not retry automatically.
These are conservative bounds, not model confidence or semantic correctness
checks; small incorrect suggestions can still occur. Type-context collection
and prompt assembly are unchanged.

Personal `MayaConfig` settings `ai_completion_debounce_ms` (default 200) and
`ai_next_edit_debounce_ms` (default 650) accept milliseconds from 0 to 60000.
Existing configurations need no migration; saved model and provider preferences
remain unchanged.

- Tab accepts a selected ordinary completion first, then a valid AI suggestion.
- Enter retains ordinary selected-completion acceptance.
- Normal Tab accepts Sweep when visible, otherwise keeps jump-forward behavior.
- `Space an` requests next-edit; `Space aa` accepts; `Space ad` dismisses.
- Ctrl-] dismisses; leaving Insert mode cancels its outstanding request.
- Ctrl-L / Alt-[ cycle Minuet or Copilot inline suggestions, not Sweep edits.
- Selecting an ordinary completion cancels AI previews. An open menu with no
  selected item can coexist with inline AI; ordinary selected completion keeps
  priority on Tab.

Local previews show the generating model's saved identifier in gray at the right
edge of the editor window. The label follows window resizing and disappears with
the preview; it is display-only and is never inserted into the document.

Acceptance stays explicit and undoable. Sweep applies accepted edits after the
completion mapping finishes, rechecking the preview identity before changing text. Provider changes, AI-off, and mode
handover cancel outgoing requests. Monotonic generations reject late callbacks;
display and acceptance also check provider, buffer, changedtick, cursor, and
mode. Old results cannot clear newer requests or overwrite intervening edits.

## Context and prompt formats

Both engines consume the same asynchronous, bounded LSP context cache. It checks
standard hover, signature-help, definition, and type-definition capabilities on
each attached client and uses that client's position encoding. Lua, TypeScript,
and Python syntax adapters locate receivers, expressions, and enclosing
annotations/calls. Incomplete annotated tables, object literals, and dictionaries
retain their enclosing type anchor even when the syntax tree contains an error.
The collector follows definitions to their full bounded annotation/declaration
snippets, then follows referenced field types for up to two additional levels
and twelve requests. Explicit annotations take priority within the 6,000-character
budget. Standard didOpen/didClose notifications synchronize temporary referenced
documents where needed, without opening or modifying user buffers. Source-version
and annotation-scope checks reject stale context. Semantic information comes
from LSP responses; unresolved
expected types are explicitly described as unresolved, with enclosing source
included as a fallback. Location and LocationLink targets yield bounded snippets.
Loaded targets use changedticks; disk targets are revalidated asynchronously by
size and modification time. Valid target snippets can survive nearby source edits.
Delayed or absent replies never block typing or prompt construction.

Shared context is limited to 6,000 characters. Minuet receives it through its FIM
prompt hook; Sweep receives an additional source-snippet section through the
public `source_context` callback. Sweep retains edit history and same-file context.
Markdown FIM prompts include surrounding prose directly, without also wrapping
that same source in an HTML-comment LSP preface. Genuine cached LSP hints still
reach Markdown completions; code completions retain enclosing annotations and
full type snippets.
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

## Bundled AI plugins

Minuet and blink-edit runtime sources are included in `vendor/` and loaded directly
through lazy.nvim local `dir` specs. A fresh clone includes the coordination,
shared-context, cancellation, and model-label hooks. Separate fork clones and
manual patch application are unnecessary. The two obsolete remote lockfile
entries are removed; repository revisions now identify the bundled versions.
Original licenses and snapshot provenance are retained in [vendor/README.md](../vendor/README.md).
Git histories, images, caches, and model files are excluded.

The plugins expose optional `external_scheduler`, pending/request inspection,
explicit dismissal notification, and Sweep's cached `source_context(bufnr)` callback.
Their standalone scheduling remains the default. The shared collector uses
capability-checked standard LSP methods and each client's position encoding;
it never selects behavior by server name.

### Local validation (2026-10-16)

Ten warm samples per engine alternated the Qwen 1.5B Q8 and Sweep 1.5B Q8 models
on the RTX 3060 Laptop GPU (6 GiB), after one warmup per engine. Repeated small
Python fixtures measured from a programmatic edit notification through debounce
to a visible preview, polled every 20 ms. These warm repeated prompts benefit
from server caching; they are not cold-start or large-project estimates.

| Engine | Render median | Render p95 | Request median | Request p95 | Empty/rejected | Failed/timeout |
| ------ | ------------: | ---------: | -------------: | ----------: | -------------: | -------------: |
| Qwen   |      271.6 ms |   272.3 ms |        62.0 ms |     67.3 ms |           0/10 |           0/10 |
| Sweep  |      749.2 ms |   750.2 ms |        88.2 ms |     90.9 ms |           0/10 |           0/10 |

The p95 uses the nearest-rank estimate (the maximum of ten samples). Ollama
reported both models' full sizes in VRAM throughout warm alternation; NVIDIA
reported 3,894 MiB used. No eviction or CPU offloading was observed. Defaults
remain 200/650 ms. `tests/ai_latency.py` reproduces these measurements.

`tests/ai_shared_context.py` uses real lua-language-server, typescript-language-server,
and ty processes and captures outgoing HTTP payloads for both engines with a
local deterministic model endpoint. All four semantic capabilities were advertised
by those servers. Receiver hovers identified `MayaConfig` or `Settings`, and
source snippets preserved field types and documentation in both final prompts.
This verifies delivery, not model quality or reliable expected-type resolution
inside every incomplete table/object literal; that remains best effort and is
labelled unresolved in enclosing-source fallback context.

Deterministic tests cover both previews surviving 1.4-second pauses, pending
serialization, acceptance followed by Sweep, dismissal through navigation,
resumed typing, stale callbacks, provider changes, completion-menu priority,
undo, delayed/absent LSP replies, LocationLink targets, and changed target versions.
The 65 Python unit tests pass, as do the general integration and typed-config
completion checks with normal LSP activation. An initial run with
`MAYA_NVIM_NO_INSTALL=1` timed out because that flag also skips automatic LSP
activation; the focused context test starts its servers explicitly.

The annotated-value regression captures both Qwen and Sweep HTTP requests for
`---@type MayaConfig` followed by an incomplete `theme = `, using the actual
repository schema in a separate library. Every `MayaConfig` field and all
`MayaTheme` fields and formatting guidance survive prompt assembly. Equivalent
TypeScript interface and Python TypedDict fixtures place their schema and nested
type in separate files and verify both prompts with real language servers.
These tests verify context delivery; suggestions can still ignore that context.

The Markdown regression captures the native Qwen HTTP request at a blank line
after an unfinished sentence. It checks that the preceding sentence and suffix
reach the correct FIM positions exactly once and that genuine semantic hints
remain available. In a local reproduction with Qwen 1.5B Q8, the duplicated-source
prompt repeated a prior heading/table in two of three seeded requests; removing
that redundant source copy produced no section repetitions in those three seeds.
The previous line was present in both variants. Some responses still contained
incorrect facts, so this establishes a prompt fix rather than guaranteed prose quality.
