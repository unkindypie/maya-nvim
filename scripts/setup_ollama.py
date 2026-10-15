#!/usr/bin/env python3
"""Reuse or install a user-local Ollama server, select and benchmark a Qwen model."""

import argparse
import hashlib
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ai_setup import detect_gpu, recommended_model

ENDPOINT = "http://127.0.0.1:11434"


def api(path, data=None, timeout=180):
    req = urllib.request.Request(
        ENDPOINT + path,
        data=json.dumps(data).encode() if data else None,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def run(*args):
    subprocess.run(args, check=True)


def install_binary():
    found = shutil.which("ollama")
    local = Path.home() / ".local/bin/ollama"
    if found or local.exists():
        return Path(found) if found else local
    if platform.system() != "Linux":
        raise SystemExit(
            "Install Ollama for your platform, then rerun setup. No existing installation changed."
        )
    if not shutil.which("zstd"):
        raise SystemExit("Install zstd before downloading Ollama")
    arch = {"x86_64": "amd64", "aarch64": "arm64"}.get(platform.machine())
    if not arch:
        raise SystemExit("Unsupported Ollama architecture: " + platform.machine())
    with urllib.request.urlopen(
        "https://api.github.com/repos/ollama/ollama/releases/latest"
    ) as response:
        release = json.load(response)
    name = f"ollama-linux-{arch}.tar.zst"
    asset = next(a for a in release["assets"] if a["name"] == name)
    prefix = Path.home() / ".local"
    prefix.mkdir(parents=True, exist_ok=True)
    print(
        f"Installing Ollama {release['tag_name']} ({asset['size'] // 1048576} MiB), without sudo",
        flush=True,
    )
    with tempfile.TemporaryDirectory(prefix="maya-ollama-") as tmp:
        archive = Path(tmp) / name
        run(
            "curl",
            "-fL",
            "--retry",
            "3",
            "--output",
            str(archive),
            asset["browser_download_url"],
        )
        digest = asset.get("digest")
        if digest:
            with archive.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != digest.removeprefix("sha256:"):
                raise SystemExit("Ollama checksum mismatch")
        run("tar", "--zstd", "--no-same-owner", "-xf", str(archive), "-C", str(prefix))
    return local


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-dir", type=Path)
    parser.add_argument("--model")
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="use the default models directory without asking",
    )
    args = parser.parse_args()
    existing = Path("/mnt/ml/ollama")
    default = Path(
        os.environ.get(
            "OLLAMA_MODELS",
            str(existing if existing.is_dir() else Path.home() / ".ollama/models"),
        )
    )
    models = args.models_dir
    if models is None and os.isatty(0) and not args.yes:
        models = Path(
            input(f"🌸 Ollama models directory [{default}]: ").strip() or default
        )
    models = (models or default).expanduser().resolve()
    models.mkdir(parents=True, exist_ok=True)
    if not os.access(models, os.R_OK | os.W_OK):
        raise SystemExit(f"Models directory must be readable/writable: {models}")
    running = False
    try:
        api("/api/tags", timeout=2)
        running = True
    except Exception:
        pass
    if not running:
        binary = install_binary()
        config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        service = config / "systemd/user/maya-nvim-ollama.service"
        if service.exists():
            old = service.read_text()
            if "# Managed by maya-nvim" not in old:
                raise SystemExit("Refusing to replace unrelated Ollama user service")
        service.parent.mkdir(parents=True, exist_ok=True)
        # Escape systemd specifier expansion, and quote spaces in paths.
        quoted_models = json.dumps("OLLAMA_MODELS=" + str(models)).replace("%", "%%")
        quoted_binary = json.dumps(str(binary)).replace("%", "%%")
        service.write_text(f"""# Managed by maya-nvim
[Unit]
Description=Maya local Ollama completions
After=network.target
[Service]
ExecStart={quoted_binary} serve
Environment={quoted_models}
Environment=OLLAMA_HOST=127.0.0.1:11434
Environment=OLLAMA_NO_CLOUD=1
Environment=OLLAMA_CONTEXT_LENGTH=2048
Restart=on-failure
[Install]
WantedBy=default.target
""")
        run("systemctl", "--user", "daemon-reload")
        run("systemctl", "--user", "enable", "--now", "maya-nvim-ollama.service")
        for _ in range(60):
            try:
                api("/api/tags", timeout=2)
                break
            except Exception:
                time.sleep(1)
        else:
            raise SystemExit(
                "Ollama did not start; journalctl --user -u maya-nvim-ollama"
            )
    else:
        print(
            "Reusing running Ollama; its existing server controls models storage.",
            flush=True,
        )
    available = {m["name"] for m in api("/api/tags")["models"]}
    state = (
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        / "maya-nvim"
    )
    try:
        saved = json.loads((state / "ai.json").read_text())
        saved_model = saved.get("model") if isinstance(saved, dict) else None
    except (OSError, ValueError):
        saved_model = None
    hardware = detect_gpu()
    model = (
        args.model
        or (saved_model if isinstance(saved_model, str) and saved_model else None)
        or recommended_model(hardware)
    )
    print(f"🌺 Local model: {model}; hardware: {hardware}")

    def ensure(name):
        if name not in available:
            print("🌺 Downloading missing model: " + name, flush=True)
            api("/api/pull", {"name": name, "stream": False}, timeout=1800)
            available.add(name)

    def benchmark(name):
        prompt = "<|fim_prefix|>def add(a: int, b: int) -> int:\n    <|fim_suffix|>\n\nprint(add(2, 3))\n<|fim_middle|>"
        data = {
            "model": name,
            "prompt": prompt,
            "raw": True,
            "stream": False,
            "options": {"num_ctx": 2048, "num_predict": 32, "temperature": 0},
        }
        api("/api/generate", {"model": name, "keep_alive": 0})
        cold_start = time.monotonic()
        api("/api/generate", data)
        cold_seconds = time.monotonic() - cold_start
        times = []
        for _ in range(3):
            start = time.monotonic()
            result = api("/api/generate", data)
            times.append(time.monotonic() - start)
        return times, result.get("response", ""), cold_seconds

    ensure(model)
    times, sample, cold_seconds = benchmark(model)
    if not sample.strip():
        raise RuntimeError(
            "Ollama returned an empty completion; previous AI preferences are kept"
        )
    if statistics.median(times) > 2:
        print(
            "🔔 Completion benchmark exceeded two seconds. Consider --model qwen2.5-coder:1.5b-base; the selected model is kept."
        )
    state.mkdir(parents=True, exist_ok=True)
    (state / "ai.json").write_text(
        json.dumps(
            {
                "provider": "ollama",
                "model": model,
                "endpoint": ENDPOINT,
                "models_dir": str(models),
            },
            indent=2,
        )
        + "\n"
    )
    gpu = api("/api/ps")
    report = {
        "model": model,
        "hardware": hardware,
        "cold_seconds": cold_seconds,
        "warm_seconds": times,
        "median_seconds": statistics.median(times),
        "sample": sample,
        "running_models": gpu,
    }
    (state / "ollama-validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
