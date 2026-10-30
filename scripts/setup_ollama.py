#!/usr/bin/env python3
"""Reuse or install Ollama; validate one local completion/edit model."""

import argparse
import hashlib
import json
import os
import platform
import shutil
import shlex
import urllib.error
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ai_setup import detect_gpu, recommended_profile, SWEEP, migrate, engine_for

ENDPOINT = "http://127.0.0.1:11434"


def api(path, data=None, timeout=180):
    req = urllib.request.Request(
        ENDPOINT + path,
        data=json.dumps(data).encode() if data else None,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read(4096).decode(errors="replace")
        raise RuntimeError(f"Ollama {path}: HTTP {error.code}: {detail}") from error


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
    parser.add_argument("--engine", choices=["sweep", "zeta-2", "zeta-2.1"])
    parser.add_argument("--endpoint")
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="use the default models directory without asking",
    )
    args = parser.parse_args()
    state = (
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        / "maya-nvim"
    )
    try:
        saved = json.loads((state / "ai.json").read_text())
        if not isinstance(saved, dict):
            saved = {}
    except (OSError, ValueError):
        saved = {}
    global ENDPOINT
    ENDPOINT = (
        args.endpoint or saved.get("endpoint") or "http://127.0.0.1:11434"
    ).rstrip("/")
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
        if ENDPOINT != "http://127.0.0.1:11434":
            raise SystemExit(
                "🔔 Configured Ollama endpoint is unavailable: "
                + ENDPOINT
                + "; start that server and rerun. No local fallback was started."
            )
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
    hardware = detect_gpu()
    migrated = migrate(saved)
    profile = recommended_profile(hardware)
    model = args.model or (migrated["model"] if saved else (profile or {}).get("model"))
    if not model:
        raise SystemExit("VRAM unavailable; specify --model and --engine")
    engine = (
        args.engine
        or (migrated.get("engine") if not args.model and saved else None)
        or engine_for(model)
    )
    context_size = 4096 if engine == "sweep" else 8192
    print(f"Local AI: Cursortab / {engine}; model: {model}; hardware: {hardware}")

    def ensure(name):
        if name not in available:
            print("🌺 Downloading missing model: " + name, flush=True)
            try:
                api("/api/pull", {"name": name, "stream": False}, timeout=1800)
            except RuntimeError as error:
                if name != SWEEP or "specified tag is not available" not in str(error):
                    raise RuntimeError(
                        f"{error}\n🔔 Run: ollama pull {shlex.quote(name)}, then rerun setup."
                    ) from error
                source = "hf.co/sweepai/sweep-next-edit-1.5B:sweep-next-edit-1.5b.q8_0.v2.gguf"
                print(
                    "🌠 Hugging Face lacks the Q8_0 alias; downloading its explicit Sweep Q8_0 v2 asset and creating the requested local alias."
                )
                api("/api/pull", {"name": source, "stream": False}, timeout=1800)
                api(
                    "/api/create",
                    {"model": name, "from": source, "stream": False},
                    timeout=1800,
                )
            available.add(name)

    # OpenAI /v1/completions ignores num_ctx; a dedicated alias pins server context.
    # Reuse the source weights, without mutating the user's original model parameters.
    source = (
        saved.get("source_model", model)
        if model.startswith("maya-local-") and model == saved.get("model")
        else model
    )
    ensure(source)
    alias = (
        "maya-local-"
        + hashlib.sha256(f"{source}:{context_size}".encode()).hexdigest()[:12]
    )
    api(
        "/api/create",
        {
            "model": alias,
            "from": source,
            "parameters": {"num_ctx": context_size},
            "stream": False,
        },
        timeout=1800,
    )
    if engine == "sweep":
        prompt = "<|file_sep|>current/example.py\ndef add(a, b):\n    return a +\n<|file_sep|>updated/example.py\ndef add(a, b):\n"
    elif engine == "zeta-2.1":
        prompt = "<[fim-suffix]>\n<[fim-prefix]><filename>example.py\n<|marker_1|>\ndef add(a, b):\n    return a +<|user_cursor|>\n<|marker_2|>\n<[fim-middle]>"
    else:
        prompt = "<[fim-suffix]>\n<[fim-prefix]><filename>example.py\n<<<<<<< CURRENT\ndef add(a, b):\n    return a +<|user_cursor|>\n=======\n<[fim-middle]>"
    times = []
    for _ in range(3):
        start = time.monotonic()
        result = api(
            "/v1/completions",
            {
                "model": alias,
                "prompt": prompt,
                "max_tokens": 96,
                "temperature": 0,
                "stream": False,
            },
            timeout=180,
        )
        if not result.get("choices"):
            raise RuntimeError(
                "Local completion endpoint returned no choices; previous preferences kept"
            )
        times.append(time.monotonic() - start)
    residency = api("/api/ps")
    resident = next(
        (
            item
            for item in residency.get("models", [])
            if item["name"].removesuffix(":latest") == alias
        ),
        None,
    )
    if resident and resident.get("context_length", context_size) < context_size:
        raise RuntimeError(
            "Ollama context is smaller than requested; previous AI preferences kept"
        )
    after = detect_gpu()
    if hardware.get("vram_mib"):
        reserve = max(512, hardware["vram_mib"] * 0.1)
        if (
            not resident
            or resident.get("size_vram", 0) < resident.get("size", 1) * 0.8
            or after.get("free_mib", reserve) < reserve
        ):
            raise RuntimeError(
                "Model did not fit with a VRAM reserve. Previous AI preferences kept. Select Sweep or free GPU memory and rerun."
            )
    preferences = dict(
        migrated,
        provider="ollama",
        endpoint=ENDPOINT,
        models_dir=str(models),
        model=alias,
        source_model=source,
        engine=engine,
        context_size=context_size,
    )
    report = {
        "hardware": hardware,
        "hardware_after": after,
        "model": alias,
        "source_model": source,
        "engine": engine,
        "request_seconds": times,
        "running_models": residency,
        "note": "Endpoint/residency smoke test; not a correctness benchmark.",
    }
    state.mkdir(parents=True, exist_ok=True)
    (state / "ollama-validation.json").write_text(json.dumps(report, indent=2) + "\n")
    temporary = state / "ai.json.tmp"
    temporary.write_text(json.dumps(preferences, indent=2) + "\n")
    temporary.replace(state / "ai.json")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"🔔 Local AI setup failed: {error}", file=sys.stderr)
        print(
            "🔔 Start/check your configured Ollama server, then rerun: "
            + shlex.join([sys.executable, *sys.argv]),
            file=sys.stderr,
        )
        raise SystemExit(1)
