# Codex CLI editor context

Maya's optional native bridge lets a Codex CLI running beside mvim (including in
another tmux pane) read the active file, cursor/selection and open file paths.
It uses the actual `/ide` connection rather than pasting text into a second
terminal or launching another agent. It does not replace Qwen/Sweep or change
your selected inline AI provider.

## Enable and use

Add this setting to `~/.config/mvim/init.lua` and restart mvim:

```lua
codex_ide_context = true,
```

The default is `false`. For the current session, run `:MayaCodexStart` instead.
Open the project in mvim, start your existing `codex` CLI in that same project,
and run `/ide` in Codex. On the tested CLI, this toggles editor context; the CLI
reports **IDE context is on** when the connection succeeds. Context is fetched
again for subsequent prompts. Running `/ide` again disables it in that chat.
Keep the selection active in mvim while switching to the Codex terminal if you
want selected text included. Unsaved selected text comes from the buffer.

- `Space ai` / `:MayaCodexStatus`: show bridge role, connection errors and socket.
- `:MayaCodexStart`: start the bridge without changing saved preferences.
- `:MayaCodexStop`: stop this editor's bridge and close its connections.

The CLI and mvim must run as the same Unix user with access to the same local
socket and files. This is not a cross-machine or Windows bridge. `CODEX_HOME`
must agree in both processes when using a custom Codex home. Starting the bridge
does not log into Codex, submit a model prompt, change Codex settings, or enable
cloud inline completions.

## What is shared

The bridge answers the `ide-context` request with the current named file and
open, loaded, listed file buffers underneath the requested workspace. Terminal,
help and other special buffers are excluded. Cursor and selection positions use
UTF-16 offsets expected by the protocol. Characterwise, linewise and blockwise
selections are supported. Leaving Visual mode clears the selection; old `'<` /
`'>` marks are not reused. Special-buffer focus retains the last real-file
context, and a changed hidden buffer invalidates its cached selection.

Only selection text is shared, not the entire contents of every buffer. In
particular, `/ide` does not make all unsaved changes available to Codex: select
the relevant unsaved text or save deliberately. Open-file metadata is capped at
100 buffers, selection text at 40,000 characters, and selections spanning over
1,000 lines are omitted with a marker. No snapshots or source text are written
to disk. Codex itself manages the context it attaches to its conversation.

The bridge exposes no execution, edit, save or diagnostic tools. Existing
Codex filesystem permissions and approvals still govern changes made by Codex.
Use Diffview (`Space gv`) to review saved changes.

## Connection and multiple editors

The endpoint is `$CODEX_HOME/ipc/ipc.sock`, defaulting to `~/.codex/ipc/ipc.sock`.
Sockets created by mvim are owner-only; the directory must be owned by the current user and
not writable by other users. A regular file, symlink or foreign-owned socket
at the endpoint is refused. An active compatible router is joined rather than
replaced. An owned stale socket is removed only after a refused connection and
an inode check. Shutdown removes only the socket this instance created.

The first editor hosts the router; later editors register with it. Requests for
other workspaces are discovered and routed to a matching editor. Clients retry
after disconnects and can take over when the router exits. When multiple
editors have the same workspace open, the router's own matching context takes
precedence, otherwise the first matching provider answers. Stop the unwanted
bridge or use distinct worktrees if you need deterministic selection between
editors of the same workspace. Cooperation with a live official VS Code router
is implemented through the same initialize/discovery messages but has not been
verified against that extension.

If Codex cannot enable context, check `Space ai`, ensure a real file in the
requested project is open, and verify both processes use the same `CODEX_HOME`.
After a Codex update, rerun the compatibility test below rather than assuming
the private protocol is unchanged. Normal editing and local AI still work when
the optional bridge is stopped or unavailable.

## Approach research and compatibility

The [official slash-command documentation](https://developers.openai.com/codex/cli/slash-commands)
describes `/ide` as including open files, selections and IDE context. Official
editor integration documentation does not list Neovim as a supported editor.

| Approach inspected                                                                          | Fit for this configuration                                                                                                                                                                                                               |
| ------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [nwiizo/codex.nvim](https://github.com/nwiizo/codex.nvim) (`4b037a8`)                       | Rich terminal/app-server UI with explicit context sending; useful for an embedded agent, but not a native `/ide` provider for an existing tmux CLI.                                                                                      |
| [sevenc-nanashi/codex-ipc.vim](https://github.com/sevenc-nanashi/codex-ipc.vim) (`7f9a9ce`) | Implements native context, but adds Deno/denops and uses the legacy temporary socket path.                                                                                                                                               |
| [leejh903/codex.nvim](https://github.com/leejh903/codex.nvim) (`ea699ac`)                   | Pure Lua native transport with multiple editors, but the inspected collector reuses old Visual marks, reports byte columns and does not filter open files to the requested workspace; router failover is also documented as unsupported. |
| [wlz6/nvim-context-ipc](https://github.com/wlz6/nvim-context-ipc) (`2ec41ed`)               | Broader multi-agent tool server with write/execute controls, disk snapshots and an extra router process for multiple editors; more surface than the read-only context feature needs.                                                     |
| Official [app-server API](https://developers.openai.com/codex/app-server)                   | Suitable for building a separate agent UI; it does not by itself supply an existing CLI's `/ide` transport.                                                                                                                              |
| Small native bridge in Maya                                                                 | Chosen: no new plugin/runtime dependency, no second conversation, live selections, workspace filtering, reconnect/failover and explicit opt-in.                                                                                          |

Research used the plugins' checked-out upstream source/READMEs and Codex source
at `openai/codex` commit `ca87ef8`, especially
`codex-rs/tui/src/ide_context/{ipc,prompt}.rs`. The wire contract is a private,
unstable Codex implementation detail: length-prefixed little-endian JSON,
request version 0, and `result.ideContext` response data. This is community
compatibility code, not an official Neovim integration. It is isolated in
`lua/maya/codex.lua` and `lua/maya/codex_context.lua` for maintenance.

Verified on Linux, Neovim 0.12.5 and **codex-cli 0.163.0**:

```sh
NVIM_APPNAME=maya-nvim .local/test-env/bin/python tests/codex_ide.py
# Opt-in real installed CLI check, with a temporary Codex home and no-daemon mode.
# Model transport is directed to an unused loopback endpoint; only /ide is issued.
NVIM_APPNAME=maya-nvim MAYA_NVIM_TEST_CODEX=1 .local/test-env/bin/python tests/codex_cli_ide.py
```

The first test covers fragmented frames, Unicode and visual selection modes,
unsaved edits, independent workspaces, router exit and foreign endpoint
preservation. The second uses the real TUI and checks that `/ide` accepts the
response. It requires installed, logged-in Codex and does not establish model
answer quality, Windows support or compatibility with future CLI versions.
