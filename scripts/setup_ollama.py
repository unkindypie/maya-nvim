#!/usr/bin/env python3
"""Reuse or install Ollama; validate selected completion/next-edit models."""

import argparse
import hashlib
import json
import os
import platform
import shutil
import statistics
import shlex
import urllib.error
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ai_setup import detect_gpu, recommended_model, recommended_profile, SWEEP

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
    parser.add_argument("--ai-mode", choices=["completion-only", "single", "dual"])
    parser.add_argument("--next-edit-model")
    parser.add_argument("--fim-format", choices=["qwen", "mellum"])
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
    if args.ai_mode == "single" and args.model:
        parser.error("Single mode uses --next-edit-model, not --model")
    if args.next_edit_model and args.ai_mode == "completion-only":
        parser.error("--next-edit-model requires single or dual mode")
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
        quoted_python = json.dumps(sys.executable).replace("%", "%%")
        quoted_warm = json.dumps(
            str(Path(__file__).resolve().with_name("warm_ollama.py"))
        ).replace("%", "%%")
        service.write_text(f"""# Managed by maya-nvim
[Unit]
Description=Maya local Ollama completions
After=network.target
[Service]
ExecStart={quoted_binary} serve
Environment=OLLAMA_KEEP_ALIVE=-1
ExecStartPost=-{quoted_python} {quoted_warm}
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
    mode = args.ai_mode or (
        "completion-only" if args.model else saved.get("local_mode", "completion-only")
    )
    if args.next_edit_model and not args.ai_mode:
        mode = "dual"
    model = args.model or saved.get("model")
    if not model and mode != "single":
        profile = recommended_profile(hardware)
        if not profile:
            raise SystemExit("🔔 VRAM unavailable; specify --model or --ai-mode single")
        model = profile.get("model") or recommended_model(hardware)
    next_model = args.next_edit_model or saved.get("next_edit_model") or SWEEP
    fim_format = args.fim_format or saved.get("fim_format")
    if model and "qwen" in model.lower():
        fim_format = "qwen"
    elif model and "mellum" in model.lower():
        fim_format = "mellum"
    if mode == "dual" and not fim_format:
        raise SystemExit(
            "🔔 Custom dual-mode models require --fim-format qwen or mellum"
        )
    print(
        f"🌺 Local AI: {mode}; inline: {model}; next-edit: {next_model}; hardware: {hardware}"
    )

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

    def benchmark(name, next_edit=False):
        prompt = "<|fim_prefix|>def add(a: int, b: int) -> int:\n    <|fim_suffix|>\n\nprint(add(2, 3))\n<|fim_middle|>"
        if next_edit:
            prompt = "<|file_sep|>original/example.py\ndef add(a, b):\n    return a - b\n<|file_sep|>current/example.py\ndef add(a, b):\n    return a + b\n<|file_sep|>updated/example.py\n"
        elif "mellum" in name.lower():
            prompt = "<filename>example.py\n<fim_suffix>\n\nprint(add(2, 3))\n<fim_prefix>def add(a: int, b: int) -> int:\n    <fim_middle>"
        data = {
            "model": name,
            "prompt": prompt,
            "raw": True,
            "stream": False,
            "options": {
                "num_ctx": 4096,
                "num_predict": 512 if next_edit else 96,
                "temperature": 0,
            },
        }
        # Keep dual models resident during validation. Legacy mode retains its cold probe.
        if mode == "completion-only":
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

    required = ([model] if mode != "single" else []) + (
        [next_model] if mode != "completion-only" else []
    )
    previous_model = saved.get("model")
    if (
        args.ai_mode
        and saved.get("provider") == "ollama"
        and previous_model
        and previous_model not in required
    ):
        print(
            "🌠 Releasing the previous completion model from memory; keeping its downloaded weights: "
            + previous_model
        )
        api("/api/generate", {"model": previous_model, "keep_alive": 0})
    reports = {}
    for name in dict.fromkeys(required):
        ensure(name)
        if mode != "completion-only":
            metadata = api("/api/show", {"model": name})
            model_info = metadata.get("model_info", {})
            contexts = [
                value
                for key, value in model_info.items()
                if key.endswith(".context_length") and isinstance(value, (int, float))
            ]
            if contexts and min(contexts) < 4096:
                raise RuntimeError("Model context is below 4096 tokens: " + name)
        times, sample, cold_seconds = benchmark(
            name, next_edit=name == next_model and mode != "completion-only"
        )
        if not sample.strip():
            raise RuntimeError(
                "Ollama returned an empty prediction; previous AI preferences are kept"
            )
        reports[name] = {
            "cold_seconds": cold_seconds,
            "warm_seconds": times,
            "median_seconds": statistics.median(times),
            "sample": sample,
        }
        if statistics.median(times) > 2:
            print(
                "🔔 Prediction exceeded two seconds; consider the single-model preset."
            )
    hardware_after = detect_gpu()
    residency = api("/api/ps")
    resident = {m["name"]: m for m in residency.get("models", [])}
    if mode == "dual":
        reserve = max(512, hardware.get("vram_mib", 0) * 0.1) * 1024**2
        used = sum(m.get("size_vram", 0) for m in resident.values())
        total = hardware.get("vram_mib", 0) * 1024**2
        fits = all(name in resident for name in required)
        if total:
            fits = fits and used + reserve <= total
        if "free_mib" in hardware_after:
            fits = fits and hardware_after["free_mib"] * 1024**2 >= reserve
        for name in required:
            item = resident.get(name, {})
            if (
                total
                and item.get("size", 0)
                and item.get("size_vram", 0) < item["size"] * 0.8
            ):
                fits = False
        if not fits:
            print(
                "🔔 The selected pair could not remain resident with a memory reserve."
            )
            if (
                not args.yes
                and os.isatty(0)
                and input("🌠 Use Sweep single-model mode instead? [Y/n]: ")
                .strip()
                .lower()
                in ("", "y", "yes")
            ):
                mode = "single"
                if model != next_model:
                    api("/api/generate", {"model": model, "keep_alive": 0})
                api("/api/generate", {"model": next_model, "keep_alive": 0})
                api(
                    "/api/generate",
                    {
                        "model": next_model,
                        "prompt": "",
                        "stream": False,
                        "keep_alive": "5m",
                        "options": {"num_ctx": 4096, "num_predict": 1},
                    },
                )
            else:
                raise RuntimeError(
                    "Previous AI preferences kept. Rerun with --ai-mode single --next-edit-model "
                    + next_model
                )
    state.mkdir(parents=True, exist_ok=True)
    preferences = dict(
        saved,
        provider="ollama",
        endpoint=ENDPOINT,
        models_dir=str(models),
        local_mode=mode,
    )
    if mode != "single":
        preferences["model"] = model
    if mode != "completion-only":
        preferences["next_edit_model"] = next_model
    if mode != "completion-only" and fim_format:
        preferences["fim_format"] = fim_format
    report = {
        "mode": mode,
        "hardware": hardware,
        "hardware_after": hardware_after,
        "models": reports,
        "running_models": residency,
    }
    (state / "ollama-validation.json").write_text(json.dumps(report, indent=2) + "\n")
    temporary = state / "ai.json.tmp"
    temporary.write_text(json.dumps(preferences, indent=2) + "\n")
    temporary.replace(state / "ai.json")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"🔔 Local AI setup failed: {error}", file=sys.stderr)
        print(
            "🔔 Start/check your configured Ollama server, then rerun: "
            + shlex.join([sys.executable, *sys.argv]),
            file=sys.stderr,
        )
        raise SystemExit(1)
