"""Native Codex IDE frames, live selections, project routing and router failover."""

import json
import socket
import struct
import tempfile
from pathlib import Path

from integration import start, stop, wait


def request(path, workspace, fragmented=False, method="ide-context", version=0):
    payload = json.dumps(
        {
            "type": "request",
            "requestId": "test-request",
            "sourceClientId": "codex-tui",
            "version": version,
            "method": method,
            "params": {"workspaceRoot": str(workspace)},
        }
    ).encode()
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(4)
        client.connect(str(path))
        frame = struct.pack("<I", len(payload)) + payload
        if fragmented:
            for byte in frame:
                client.sendall(bytes([byte]))
        else:
            client.sendall(frame)

        def read(count):
            result = b""
            while len(result) < count:
                part = client.recv(count - len(result))
                assert part, "provider closed before replying"
                result += part
            return result

        return json.loads(read(struct.unpack("<I", read(4))[0]))


with tempfile.TemporaryDirectory(prefix="maya-codex-") as temp:
    root = Path(temp)
    a, b = root / "project a", root / "project b"
    a.mkdir()
    b.mkdir()
    (a / "unicode.txt").write_text("α😀z\nsecond line\n")
    (b / "other.txt").write_text("OTHER PROJECT\n")
    ipc = root / "ipc" / "ipc.sock"
    editors = []
    try:
        for directory, name in ((a, "unicode.txt"), (b, "other.txt")):
            editor = start()
            editors.append(editor)
            editor.ui_attach(100, 30, rgb=True)
            editor.command("cd " + editor.funcs.fnameescape(str(directory)))
            editor.command("edit " + editor.funcs.fnameescape(str(directory / name)))
            assert editor.exec_lua(
                'return require("maya.codex").start({socket_path=...})', str(ipc)
            )
        first, second = editors
        wait(second, 'require("maya.codex").status().role=="client"')
        first.input("gg0v$")
        wait(first, 'vim.fn.mode()=="v"')
        result = request(ipc, a, fragmented=True)
        assert result["resultType"] == "success", result
        snapshot = result["result"]["ideContext"]
        assert snapshot["activeFile"]["activeSelectionContent"] == "α😀z", snapshot
        assert snapshot["activeFile"]["selection"]["end"] == {
            "line": 0,
            "character": 4,
        }, snapshot
        assert all(tab["path"] == "unicode.txt" for tab in snapshot["openTabs"])
        assert (
            request(ipc, b)["result"]["ideContext"]["activeFile"]["path"] == "other.txt"
        )
        assert request(ipc, root / "unrelated")["resultType"] == "error"
        assert (
            request(ipc, a, method="executeCode")["error"] == "no-handler-for-request"
        )
        assert request(ipc, a, version=99)["error"] == "request-version-mismatch"
        assert ipc.stat().st_mode & 0o777 == 0o600
        with socket.socket(socket.AF_UNIX) as malformed:
            malformed.settimeout(3)
            malformed.connect(str(ipc))
            malformed.sendall(struct.pack("<I", 1048577))
            assert malformed.recv(1) == b"", "oversized frame was not rejected"
        first.input("<Esc>")
        wait(first, 'vim.fn.mode()=="n"')
        assert (
            request(ipc, a)["result"]["ideContext"]["activeFile"][
                "activeSelectionContent"
            ]
            == ""
        )
        first.current.buffer[:] = ["abcd", "efgh"]
        first.input("gg0<C-v>jl")
        wait(first, 'vim.fn.mode()=="\\22"')
        block = request(ipc, a)["result"]["ideContext"]["activeFile"]
        assert block["activeSelectionContent"] == "ab\nef", block
        assert len(block["selections"]) == 2
        first.input("<Esc>")
        wait(first, 'vim.fn.mode()=="n"')
        first.input("ggVj")
        wait(first, 'vim.fn.mode()=="V"')
        linewise = request(ipc, a)["result"]["ideContext"]["activeFile"]
        assert linewise["activeSelectionContent"] == "abcd\nefgh", linewise
        assert linewise["selection"]["end"] == {"line": 2, "character": 0}, linewise
        assert first.current.buffer.options["modified"]
        assert (a / "unicode.txt").read_text() == "α😀z\nsecond line\n"
        original_buf = first.current.buffer.number
        first.exec_lua("""local scratch=vim.api.nvim_create_buf(false,true)
vim.api.nvim_win_set_buf(0,scratch)""")
        retained = request(ipc, a)["result"]["ideContext"]["activeFile"]
        assert retained["path"] == "unicode.txt", retained
        first.exec_lua(
            'vim.api.nvim_buf_set_lines(...,0,-1,false,{"changed while hidden"})',
            original_buf,
        )
        invalidated = request(ipc, a)["result"]["ideContext"]["activeFile"]
        assert invalidated["activeSelectionContent"] == ""
        assert invalidated["selection"]["start"] == invalidated["selection"]["end"]
        # Closing the original router must not strand the other editor.
        first.exec_lua('require("maya.codex").stop()')
        wait(second, 'require("maya.codex").status().role=="router"')
        assert request(ipc, b)["resultType"] == "success"
        second.exec_lua('require("maya.codex").stop()')
        # Never delete a regular file that happens to occupy the socket path.
        ipc.write_text("preserve")
        second.exec_lua('require("maya.codex").start({socket_path=...})', str(ipc))
        wait(second, 'require("maya.codex").status().error ~= nil')
        second.exec_lua('require("maya.codex").stop()')
        assert ipc.read_text() == "preserve"
        for editor in editors:
            assert "Error executing" not in editor.command_output("messages")
        print(
            "PASS native /ide frames, Unicode/line/block selections, unsaved text, isolated projects, reconnect/failover and socket ownership"
        )
    finally:
        for editor in editors:
            stop(editor)
