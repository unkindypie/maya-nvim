# Local AI simplification experiments

The target is one local AI plugin and one active local model for insertions and
next edits, with Maya's existing capability-based, cached LSP context. Local
inference for both behaviors is a requirement, not a provider preference. Cloud
model results cannot qualify a local implementation. Sweep through blink-edit is
the current candidate; any alternative must demonstrate both behaviors locally.
Legacy compatibility calls for a documented migration, not permanent retention of
a second local AI plugin.

## Reproduce

Run from the repository with the disposable pynvim environment and installed
Ollama models. These checks do not install models or change saved AI preferences.
They create temporary state and buffers, start the editor through `bin/mvim`, and
write JSONL to stdout. Store raw results outside the repository.

```sh
export NVIM_APPNAME=maya-nvim MAYA_NVIM_NO_INSTALL=1
export MAYA_NVIM_TEST_OLLAMA=1
.local/test-env/bin/python tests/ai_benchmark.py > /tmp/maya-ai-baseline.jsonl
.local/test-env/bin/python tests/ai_benchmark_report.py /tmp/maya-ai-baseline.jsonl
# Run sequentially: competing benchmark jobs distort GPU latency.
.local/test-env/bin/python tests/ai_benchmark.py --modes single \
  --single-insert-delay 200 --no-extra-lsp > /tmp/maya-ai-experiment.jsonl
.local/test-env/bin/python tests/ai_benchmark_report.py /tmp/maya-ai-experiment.jsonl
# Isolate the delay change from extra LSP collection:
.local/test-env/bin/python tests/ai_benchmark.py --modes single \
  --single-insert-delay 200 > /tmp/maya-ai-validation.jsonl
# Narrow compatibility probe, not a supported Qwen migration:
.local/test-env/bin/python tests/ai_benchmark.py --modes single \
  --single-insert-delay 200 --blink-qwen > /tmp/maya-ai-blink-qwen.jsonl
.local/test-env/bin/python tests/ai_shared_context.py --mode single
.local/test-env/bin/python tests/ai_shared_context.py --mode single --no-extra-lsp
```

The benchmark has 24 fixed cases: four insertions, two corrections, and two
abstention cases for each of Lua, Python, and TypeScript. Each case gets a first
observation plus ten repetitions. The fixture order uses a fixed shuffle seed.
A fresh editor isolates each fixture; reconfiguration resets Sweep history between
samples. The scheduler, rendering, filters, and acceptance run through real editor
APIs. Results include accepted text, correctness, request timings, preview latency,
model digests, GPU identity, and Ollama residency. Native-response load duration is
recorded when available; a first observation is **not** automatically a cold load.
No shared model is explicitly unloaded.

Python scoring compares ASTs; Lua and TypeScript scoring compares tokens while
preserving string contents. This tolerates formatting differences but is not a
complete semantic equivalence checker. Expected results are intentionally narrow.
The report separates first observations from warm results and computes nearest-rank
p95. Inspect failed outputs before interpreting scores as quality differences.

The model-quality fixtures do not attach real LSPs. Cross-file, incomplete
annotation, member documentation, and Markdown context fidelity are tested by the
HTTP-capture integration suite with real LSPs and deterministic model responses.
Passing those checks does not prove that a model uses the supplied context well.
The `--blink-qwen` probe uses a generic FIM template at the end of the buffer only;
it does not implement cursor/suffix splitting for arbitrary editing positions or
validate Mellum/custom endpoint compatibility.
Repeated small fixtures can benefit from prompt caching; these timings are not an
estimate of everyday project performance or a general model ranking.

## Gates and staged delivery

1. **Before runtime changes:** record current dual, single, and completion-only
   behavior, correctness, preview latency, and failures. Test the scorer itself.
2. **During experiments:** compare single-mode delay and duplicate LSP collection
   independently, preserving the filter and saved preferences. The CLI flags only
   alter the disposable editor instance.
3. **Before migration:** require single mode to match dual correctness separately
   for insertions and edits, introduce no additional unrelated edits, and keep
   warm p95 preview latency within 20% of dual. Investigate multi-second latency.
   Failed gates preserve current defaults and libraries.
4. **Before library removal:** validate the chosen local model and supported local
   endpoints for both behaviors, including completion in the middle of existing
   code. Document migration of legacy Qwen/Mellum configurations. Full compatibility
   with every previous model is not a reason to retain a second plugin indefinitely.
5. **After a passing migration:** repeat the frozen benchmark and context tests,
   run cancellation/ownership/acceptance/undo/provider-switch regressions, and
   perform a Kitty/tmux interactive check. Commit and push only validated stages.

Shared context already works in single mode: `ai_context.setup()` is a no-op;
`ai_coordinator.activity()` calls `refresh()` regardless of local mode. The older
`dual` predicate passed to `setup()` is misleading but does not gate collection.
Do not introduce a new collector or duplicate language metadata to fix it.

## Results

Measured on 2026-10-29 with an RTX 3060 Laptop GPU (6,144 MiB), the installed
Qwen2.5-Coder 1.5B Base Q8 and Sweep 1.5B Q8, and the existing runtime at
`21b9911`. Ten warm repetitions per fixture; first observations excluded.

| Configuration                            | Insertions correct | Insertion median / p95 | Corrections correct        | Edit p95 |
| ---------------------------------------- | ------------------ | ---------------------- | -------------------------- | -------- |
| Existing dual                            | 96/120             | 251.8 / 293.5 ms       | 60/60                      | 793.1 ms |
| Existing Sweep single (650 ms)           | 100/120            | 784.8 / 828.2 ms       | 60/60                      | 789.6 ms |
| Existing Qwen completion-only            | 86/120             | 268.5 / 687.7 ms       | Not supported by this path | —        |
| Sweep single, 200 ms, extra LSP disabled | 100/120            | 331.1 / 367.1 ms       | 60/60                      | 791.1 ms |

All 60 warm abstention cases retained the expected buffer in each applicable
configuration. Ten nevertheless displayed a preview without changing the accepted
buffer: unchanged text alone does not prove a quiet UI. No run changed prefix
lines before the intended completion line. Some Qwen completions appended extra
statements or echoed context; those failed the correctness score.

The Sweep path consistently omitted the final `end` in the Lua function fixture
and filled a `"local"` literal annotation with `"normal"`. The dual path failed the
TypeScript closing-brace fixture and produced inconsistent Lua literal completions.
These are accepted editor outputs, not an isolated comparison of model weights.
Different prompts, output limits, temperatures, and renderers affect the results.

The 200 ms experiment improved scheduling latency substantially but its 367.1 ms
p95 exceeds the agreed 352.2 ms limit (1.2 × 293.5). Correctness passed the aggregate
gate on this small corpus; latency did not. Do not lower the acceptance threshold
retrospectively or present this as proof that either model is generally better.

Sweep's runner reported approximately 1,577 MiB VRAM; Qwen's dual-mode runner
reported approximately 1,745 MiB. These are per-runner measurements, not total GPU
savings: previously used models remained resident during some single-mode samples.
Cold-load latency was not established. The early baseline instrumentation omitted
Sweep load duration; the final harness handles both decoded and raw HTTP bodies
and records native load duration when available.

### Validation and rollout decision

The single-mode HTTP-capture suite passed with extra LSP collection enabled and
disabled, including cross-file Lua/Python/TypeScript annotations and documentation.
Dual-mode context capture and Markdown context regression also passed. Unit tests
(70), syntax/startup checks, and the AI context, annotation, scheduling, coordination,
acceptance/undo, edit-filter, status, and completion-key regressions passed.

Runtime defaults, saved preferences, installer presets, and both libraries remain
unchanged. Migration and library removal are deferred under the plan's gate.
A post-migration benchmark and manual Kitty/tmux check cannot be claimed because
no migration was performed. Before migration, investigate the remaining insertion
failures and prompt/runtime latency on held-out fixtures with real LSP context;
validate cursor/suffix behavior for the selected local model and document legacy
configuration migration before removing Minuet. The original experiment treated
Qwen/Mellum compatibility as a removal gate; the clarified one-plugin goal replaces
that requirement with explicit migration.

The final repeat with the 200 ms delay and extra LSP collection enabled scored
100/120 insertions, 60/60 corrections, and 60/60 unchanged abstention cases. Its
insertion median/p95 was 330.4/353.1 ms; edit p95 was 787.2 ms. This narrowly misses
the same gate, but the 0.9 ms margin is below a meaningful practical distinction
for this small benchmark. The two runs show timing variability, not evidence that
removing extra LSP collection makes inference faster. The quality fixtures do not
attach LSP servers, so use the real-LSP capture checks for context fidelity.

The Qwen generic-provider probe is limited to end-of-buffer completion. It scored
60/120, displayed previews in 80/120 attempts, and left the buffer unchanged in
40/120. Visible-preview median/p95 was 248.4/269.6 ms, while elapsed p95 across all
attempts was 994.4 ms: reporting only visible previews hides rejected-response cost.
Some
responses echoed the source-context section and were rejected by the existing
filter. Others were usable; an omitted terminal TypeScript semicolon also fails
this deliberately narrow token-based scorer despite being valid syntax. Do not
interpret this probe as an unbiased model ranking or evidence of full compatibility.
Mid-line suffix handling, custom transports, and Mellum remain unvalidated.
