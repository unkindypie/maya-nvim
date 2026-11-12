#!/usr/bin/env python3
"""Install pinned PlantUML tools on first use, outside the repository."""

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
import urllib.request

from build_cursortab import toolchain

VERSION = "1.2026.10"
SHA256 = "e9bc9e6b2eb715e8c0c929f3dcb5fc1923be13f37599b09c293c66d354e88686"
LSP_REVISION = "dd37e40914b8c2826c360c8ee7d3a211f7e7af83"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    root = args.directory.resolve()
    root.mkdir(parents=True, exist_ok=True)
    jar = root / "plantuml.jar"
    if not jar.exists() or hashlib.sha256(jar.read_bytes()).hexdigest() != SHA256:
        with urllib.request.urlopen(
            f"https://github.com/plantuml/plantuml/releases/download/v{VERSION}/plantuml.jar",
            timeout=60,
        ) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != SHA256:
            raise RuntimeError("PlantUML checksum mismatch")
        with tempfile.NamedTemporaryFile(dir=root, delete=False) as temp:
            temp.write(data)
        Path(temp.name).replace(jar)
    binary = root / "bin/plantuml-lsp"
    marker = root / "lsp-revision"
    if not binary.exists() or not marker.exists() or marker.read_text() != LSP_REVISION:
        binary.parent.mkdir(exist_ok=True)
        env = dict(os.environ, GOBIN=str(binary.parent))
        subprocess.run(
            [toolchain(), "install", "github.com/ptdewey/plantuml-lsp@" + LSP_REVISION],
            env=env,
            check=True,
        )
        marker.write_text(LSP_REVISION)
    if shutil.which("java") and not (root / "stdlib").is_dir():
        subprocess.run(
            ["java", "-jar", str(jar), "-extractstdlib"], cwd=root, check=True
        )
    print(f"PlantUML {VERSION} and plantuml-lsp ready: {root}")


if __name__ == "__main__":
    main()
