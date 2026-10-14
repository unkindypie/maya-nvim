# AI suggestions

Ollama is the local backend (Minuet virtual text). GitHub Copilot uses
copilot.lua. `:MayaAI ollama|copilot|off` and `Space ao/ac/ax` switch providers;
selection is persisted in `${XDG_STATE_HOME:-~/.local/state}/maya-nvim/ai.json`.
Exactly one backend is active. Server errors never trigger a cloud fallback.

The shared controls are Tab to accept, Ctrl-L for next suggestion, Alt-[ for
previous, and Ctrl-] to dismiss. Ctrl-J/K remain completion-menu navigation.
AI is checked before completion and snippet handling. Suggestions remain visible
when completion opens, so Tab precedence stays predictable.

## Local installation and models

`install.sh --ollama-models-dir PATH` accepts the chosen storage directory. Without
that option an interactive installer asks, defaulting to `OLLAMA_MODELS`, an
existing `/mnt/ml/ollama`, or `~/.ollama/models`. It must be readable and writable.
The chosen path contains `blobs/` and `manifests/`, not another `models/` subfolder.

The installer reuses a running server and existing binary. It downloads official
Linux Ollama binaries into `~/.local` only when needed and verifies the release
asset SHA-256 when GitHub supplies it. It does not upgrade an existing binary.
When no server is running it creates a managed **user** systemd service
`maya-nvim-ollama.service` with `OLLAMA_MODELS` on the server process, loopback
binding, and cloud features disabled. No sudo, root service, or shell-wide model
path is required.

A reused independently managed server retains its existing model directory.
Changing the editor's environment cannot change a running server's storage:
configure that server's `OLLAMA_MODELS` and restart it yourself. For the managed
maya-nvim service, stop it before rerunning setup with a new directory:

```sh
systemctl --user stop maya-nvim-ollama.service
python3 scripts/setup_ollama.py --models-dir /your/models
```

The models are never deleted, moved or re-downloaded if already present. Setup
tries existing `qwen2.5-coder:7b`; otherwise it downloads
`qwen2.5-coder:1.5b`. If 7B fails or its warmed median for the short benchmark is
above two seconds, it unloads 7B and selects 1.5B. `--model NAME` overrides this
selection. This is a short completion benchmark, not a general model-quality or
performance guarantee. Minuet uses a 512-character context and one completion.

Maya's RTX 3060 Laptop GPU has 6 GiB VRAM. The existing Qwen 7B model produced
`return a + b` in roughly 0.20 seconds warmed and used about 4.38 GB GPU memory;
there was no need to download another model. Exact setup results are saved outside
Git in `stdpath('state')/ollama-validation.json`.

```sh
systemctl --user status maya-nvim-ollama.service
journalctl --user -u maya-nvim-ollama.service
ollama ps
```

## GitHub Copilot

Select GitHub explicitly, then run `:Copilot auth`. Existing authentication may
be reused by Copilot's own shared credential store; maya-nvim never copies tokens
or logs credentials. First use may download the upstream native language server.
An active GitHub subscription/sign-in is needed to validate live GitHub responses.

## Adjusting local preferences

Exit mvim, edit `ai.json`, and restart it to change model or endpoint. To use a
new model, pull it into the running server first. Keep this file out of Git.
