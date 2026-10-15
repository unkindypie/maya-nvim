#!/usr/bin/env python3
"""Format staged Markdown/Python with mvim's tools, preserving unstaged edits."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def git(*args, data=None):
    return subprocess.check_output(["git", *args], input=data)


def formatter(root):
    # Conform prefers project-local Prettier; Mason prepends its bin directory.
    candidates = [
        root / "node_modules/.bin/prettier",
        Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
        / "maya-nvim/mason/bin/prettier",
    ]
    for path in candidates:
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    return shutil.which("prettier")


def main():
    python = "--python" in sys.argv
    label = "Python" if python else "Markdown"
    root = Path(os.fsdecode(git("rev-parse", "--show-toplevel")).strip())
    os.chdir(root)
    names = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").split(
        b"\0"
    )
    names = [
        name
        for name in names
        if name and os.fsdecode(name).lower().endswith(".py" if python else ".md")
    ]
    if not names:
        return
    prettier = (
        (
            shutil.which("ruff")
            or str(
                Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
                / "maya-nvim/mason/bin/ruff"
            )
        )
        if python
        else formatter(root)
    )
    if not prettier or (python and not shutil.which(prettier)):
        if python:
            raise RuntimeError(
                "Ruff is missing. Install it with :MasonInstall ruff in mvim or pipx install ruff, then retry."
            )
        raise RuntimeError(
            "Prettier is missing. Install it with :MasonInstall prettier in mvim, "
            "or npm install --save-dev prettier, then retry the commit."
        )
    changes = []
    for name in names:
        path = os.fsdecode(name)
        entry = git("ls-files", "--stage", "-z", "--", path).split(b"\0")[0]
        mode, _, stage = entry.split(b"\t", 1)[0].split()
        if stage != b"0" or mode not in (b"100644", b"100755"):
            continue  # Never follow staged Markdown symlinks.
        file = root / path
        if not python:
            info = json.loads(
                subprocess.check_output([prettier, "--file-info", str(file)])
            )
            if info["ignored"]:
                continue
        original = git("show", ":" + path)
        command = (
            [prettier, "format", "--stdin-filename", str(file)]
            if python
            else [prettier, "--stdin-filepath", str(file)]
        )
        result = subprocess.run(
            command, input=original, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if result.returncode:
            raise RuntimeError(
                f"{label} formatter failed for {path!r}:\n" + os.fsdecode(result.stderr)
            )
        if original == result.stdout:
            continue
        blob = git("hash-object", "-w", "--stdin", data=result.stdout).strip()
        changes.append((name, mode, blob, original, result.stdout))
    if not changes:
        return
    # One index update, after every formatter invocation has succeeded.
    entries = b"".join(
        mode + b" " + blob + b"\t" + name + b"\0" for name, mode, blob, _, _ in changes
    )
    git("update-index", "-z", "--index-info", data=entries)
    for name, _, _, original, formatted in changes:
        file = root / os.fsdecode(name)
        if file.is_file() and not file.is_symlink() and file.read_bytes() == original:
            file.write_bytes(formatted)
            print(f"Formatted {label}: {os.fsdecode(name)!r}")
        else:
            print(
                f"Formatted staged {label}: {os.fsdecode(name)!r}; unstaged edits kept unchanged."
            )


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError, OSError, ValueError) as error:
        print(f"Formatting pre-commit: {error}", file=sys.stderr)
        sys.exit(1)
