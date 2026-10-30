# Bundled Cursortab

`cursortab.nvim` is a source snapshot of
[cursortab/cursortab.nvim](https://github.com/cursortab/cursortab.nvim), pinned to
`211f7159ecc9ec56c705cf5a486637f1221ad2fd` (29 October 2026). Its MIT license,
upstream README, contribution guidance, source and tests are retained. Images,
git history, compiled binaries and generated HTML reports are excluded.
Local `dir` plugins have no lazy-lock entry; this pin records the provenance.

Maya's small extensions are:

- `source_context(bufnr)`: optional cached text, captured with the buffer snapshot,
  bounded to 6,000 bytes, omitted on error/staleness and synthetic prefetch snapshots.
  Sweep, Zeta-2 and Zeta-2.1 receive it as a native-format pseudo-file.
- `enabled_predicate()`: optional dynamic eligibility check, including late previews.
- `behavior.prefetch` and `behavior.normal_edit_only`: retained experiment controls;
  runtime uses their native defaults (prefetch on, Normal additions allowed).
- `partial_accept()`: public wrapper around the native handler so Maya can arbitrate
  Shift-Tab with blink.cmp without duplicating acceptance behavior.
- Check eligibility before late cursor predictions as well as completions.
- Read Neovim's actual modified flag so edits before the first daemon sync count.
  Replay a text-change notification after asynchronous connection if needed.
- Separate acceptance from surrounding typing in the undo history.

Cursortab owns all request scheduling, streaming, staging, rendering and acceptance.
Maya supplies provider preferences, existing keys and its cached standard-LSP
collector. No Minuet, blink-edit or dual-engine coordinator remains. Ordinary
`blink.cmp` continues to provide non-AI editor completion.

Build with `NVIM_APPNAME=maya-nvim python3 scripts/build_cursortab.py`. The installer
and editor updater rebuild the source. Run `go test ./...` inside `server` and
Maya's `tests/ai_cursortab.py`, `ai_candidate_context.py`, and `ai_shared_context.py`.
Do not mark upstream E2E fixtures human-verified without a human review.
