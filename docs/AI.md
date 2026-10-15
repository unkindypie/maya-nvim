# AI suggestions

Ollama is the local backend (Minuet virtual text). GitHub Copilot uses
copilot.lua. `:MayaAI ollama|copilot|off` and `Space ao/ac/ax` switch providers;
selection is persisted in `${XDG_STATE_HOME:-~/.local/state}/maya-nvim/ai.json`.
Exactly one backend is active. Server errors never trigger a cloud fallback.

The shared controls are Tab to accept, Ctrl-L for next suggestion, Alt-[ for
previous, and Ctrl-] to dismiss. Ctrl-J/K remain completion-menu navigation.
A selected completion is accepted before AI; AI is checked before other completion and snippet handling. Suggestions remain visible
when completion opens, so Tab precedence stays predictable.

## Local installation and models

Fresh interactive installs show one menu with a hardware-based recommendation,
1.5B/3B/7B Base, a custom Ollama model, GitHub Copilot, and **Skip Ollama models
installation**. Enter accepts the recommendation. Copilot installs no Ollama or
models; authenticate with `:Copilot auth`. Skip starts with AI off, preserving
normal completion and existing models. AI plugin code remains available for later
activation. Reinstalls preserve the saved provider and model.

`--ai ollama|copilot|off` explicitly selects a provider; `--model NAME` selects
Ollama and overrides the saved/recommended model unless Copilot/off is explicitly
chosen. Noninteractive fresh installs leave AI off unless `--ai ollama`,
`--model`, or `--yes` is passed. `--yes` uses the recommendation and skips questions.
Link-only installs (`--skip-bootstrap`) do not set up AI.

VRAM detection uses Python's standard library only: existing `nvidia-smi` for
NVIDIA and readable AMD DRM memory files under `/sys/class/drm` on Linux. Commands
have a three-second timeout. The largest GPU's capacity is used, never summed.
macOS shared system memory is reported separately. Missing tools, unreadable
files, or malformed results do not block setup.

The recommendation is `qwen2.5-coder:3b-base`, switching to
`qwen2.5-coder:1.5b-base` below 4 GiB detected dedicated VRAM. Unknown dedicated
VRAM keeps the 3B recommendation; choose a smaller model or skip if appropriate.
The menu runs before Ollama/model installation.

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

Models are never deleted, moved, or downloaded again if already present.
`--model NAME` overrides the saved selection, including when running
`scripts/setup_ollama.py` directly. Setup reports the initial request and three
warmed runs with a short fill-in-the-middle prompt. A slow benchmark recommends
1.5B Base without silently changing the chosen model. This is a short latency
check, not a general quality guarantee. Results are saved outside Git in
`stdpath('state')/ollama-validation.json`. Minuet uses a 512-character context
and one completion.

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

`Space ao` selects Ollama and reloads its saved model/endpoint, with one provider
notification. It does not install models. Repeating it keeps Ollama active rather
than emitting disable/enable notices. `Space as` shows provider/model/server and
controls for 10 seconds; it does not claim server connectivity or cloud login
has been verified. A selected editor completion still takes priority over AI on Tab.
