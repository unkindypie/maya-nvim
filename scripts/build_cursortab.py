#!/usr/bin/env python3
"""Build the bundled Cursortab daemon with an isolated Go toolchain if needed."""

import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VERSION = "go1.27.3"


def toolchain():
    go = shutil.which("go")
    if go:
        try:
            version = subprocess.check_output([go, "version"], text=True)
            match = re.search(r"go(\d+)\.(\d+)", version)
            if match and tuple(map(int, match.groups())) >= (1, 25):
                return go
        except (OSError, subprocess.SubprocessError):
            pass
    cache = (
        Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        / "maya-nvim"
        / VERSION
    )
    binary = cache / "go/bin/go"
    if binary.exists():
        return str(binary)
    system = platform.system().lower()
    arch = {"x86_64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(
        platform.machine()
    )
    with urllib.request.urlopen(
        "https://go.dev/dl/?mode=json&include=all", timeout=30
    ) as response:
        releases = json.load(response)
    release = next(item for item in releases if item["version"] == VERSION)
    asset = next(
        item
        for item in release["files"]
        if item["os"] == system and item["arch"] == arch and item["kind"] == "archive"
    )
    cache.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache.parent) as temp:
        archive = Path(temp) / "go.tar.gz"
        with (
            urllib.request.urlopen(
                "https://go.dev/dl/" + asset["filename"], timeout=60
            ) as response,
            archive.open("wb") as target,
        ):
            shutil.copyfileobj(response, target)
        with archive.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != asset["sha256"]:
                raise RuntimeError("Go checksum mismatch")
        with tarfile.open(archive) as source:
            source.extractall(Path(temp) / "unpacked", filter="data")
        (Path(temp) / "unpacked").rename(cache)
    return str(binary)


def main():
    subprocess.run(
        [toolchain(), "build", "-trimpath", "-o", "cursortab", "."],
        cwd=ROOT / "vendor/cursortab.nvim/server",
        check=True,
    )


if __name__ == "__main__":
    main()
