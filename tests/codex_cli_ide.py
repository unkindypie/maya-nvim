"""Opt-in real Codex TUI /ide handshake; sends no model prompt or editor contents to a model."""

import fcntl
import json
import os
import pty
import re
import select
import shutil
import struct
import subprocess
import tempfile
import termios
import time
from pathlib import Path

from integration import start, stop

if os.environ.get("MAYA_NVIM_TEST_CODEX") != "1":
    raise SystemExit("SKIP: set MAYA_NVIM_TEST_CODEX=1 to test the installed Codex CLI")

codex = shutil.which("codex")
original_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
assert codex and (original_home / "auth.json").is_file(), (
    "Requires installed, logged-in Codex CLI"
)
with tempfile.TemporaryDirectory(
    prefix="codex-cli-", dir=Path(__file__).resolve().parents[1] / ".local"
) as temp:
    root = Path(temp)
    home = root / "codex"
    home.mkdir(mode=0o700)
    (home / "auth.json").symlink_to(original_home / "auth.json")
    if (original_home / "models_cache.json").is_file():
        shutil.copy(original_home / "models_cache.json", home / "models_cache.json")
    (home / "config.toml").write_text(
        """check_for_update_on_startup = false
model_provider = "ide-test"
[model_providers.ide-test]
name = "Local IDE handshake only"
base_url = "http://127.0.0.1:9/v1"
wire_api = "responses"
requires_openai_auth = false
[projects."""
        + json.dumps(str(root))
        + ']\ntrust_level = "trusted"\n'
    )
    (root / "fixture.txt").write_text("IDE context fixture\n")
    nvim = start()
    process = None
    master, slave = pty.openpty()
    try:
        nvim.command("cd " + nvim.funcs.fnameescape(str(root)))
        nvim.command("edit " + nvim.funcs.fnameescape(str(root / "fixture.txt")))
        nvim.exec_lua(
            'assert(require("maya.codex").start({socket_path=...}))',
            str(home / "ipc/ipc.sock"),
        )
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
        process = subprocess.Popen(
            [
                codex,
                "--no-daemon",
                "--no-alt-screen",
                "-C",
                str(root),
                "--sandbox",
                "read-only",
                "--ask-for-approval",
                "never",
            ],
            env=dict(os.environ, CODEX_HOME=str(home), TERM="xterm-256color"),
            stdin=slave,
            stdout=slave,
            stderr=slave,
        )
        os.close(slave)
        slave = -1
        output = bytearray()

        def read_for(seconds):
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                ready, _, _ = select.select(
                    [master], [], [], min(0.1, end - time.monotonic())
                )
                if not ready:
                    continue
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    break
                output.extend(chunk)
                if b"\x1b[6n" in chunk:
                    os.write(master, b"\x1b[1;1R")
            return re.sub(
                r"\x1b\[[0-?]*[ -/]*[@-~]", "", output.decode(errors="replace")
            )

        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            text = read_for(0.3)
            if "Tip:" in text and "Ask Codex to do anything" in text:
                break
        else:
            raise AssertionError("Codex composer did not become ready: " + text[-2500:])
        os.write(master, b"/ide")
        read_for(0.5)
        os.write(master, b"\r")
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            text = read_for(0.3)
            if "IDE context is on" in text:
                break
        else:
            raise AssertionError("Codex /ide did not connect: " + text[-3500:])
        assert nvim.exec_lua('return require("maya.codex").requests or 0') > 0
        print(
            "PASS real "
            + subprocess.check_output([codex, "--version"], text=True).strip()
            + ": /ide connected to mvim; remote model transport disabled"
        )
    finally:
        if process:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        os.close(master)
        if slave >= 0:
            os.close(slave)
        stop(nvim)
