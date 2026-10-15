"""Dependency-free GPU detection and AI setup choices."""

import platform
import subprocess
from pathlib import Path

DEFAULT_MODEL = "qwen2.5-coder:3b-base"
SMALL_MODEL = "qwen2.5-coder:1.5b-base"


def detect_gpu():
    """Return dedicated VRAM in MiB, or separately labeled shared memory."""
    devices = []
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=3,
            check=True,
        )
        for line in result.stdout.splitlines():
            name, memory = line.rsplit(",", 1)
            memory = int(memory.strip())
            if memory > 0:
                devices.append({"name": name.strip(), "vram_mib": memory})
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    if platform.system() == "Linux":
        for device in Path("/sys/class/drm").glob("card[0-9]*/device"):
            try:
                if (device / "vendor").read_text().strip() != "0x1002":
                    continue
                memory = int((device / "mem_info_vram_total").read_text()) // (
                    1024 * 1024
                )
                if memory > 0:
                    devices.append(
                        {"name": "AMD " + device.parent.name, "vram_mib": memory}
                    )
            except (OSError, ValueError):
                pass
    if devices:
        return max(devices, key=lambda device: device["vram_mib"])
    if platform.system() == "Darwin":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True,
                text=True,
                timeout=3,
                check=True,
            )
            return {
                "name": "macOS shared system memory",
                "shared_mib": int(result.stdout) // (1024 * 1024),
            }
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    return {"name": "VRAM unavailable"}


def recommended_model(gpu):
    memory = gpu.get("vram_mib")
    return SMALL_MODEL if memory is not None and memory < 4096 else DEFAULT_MODEL


def choose():
    gpu = detect_gpu()
    recommended = recommended_model(gpu)
    memory = gpu.get("vram_mib")
    detail = (
        f"{memory / 1024:.1f} GiB dedicated VRAM"
        if memory
        else "dedicated VRAM unavailable"
    )
    if "shared_mib" in gpu:
        detail = f"{gpu['shared_mib'] / 1024:.1f} GiB shared system memory (not dedicated VRAM)"
    print(f"🌺 AI setup — {gpu['name']}: {detail}")
    print(f"  1. Recommended: {recommended}")
    print("  2. Qwen2.5-Coder 1.5B Base (lightweight)")
    print("  3. Qwen2.5-Coder 3B Base (balanced)")
    print("  4. Qwen2.5-Coder 7B Base (prefer 8 GB+ VRAM)")
    print("  5. Custom Ollama model")
    print("  6. GitHub Copilot (no Ollama; authenticate with :Copilot auth)")
    print("  7. Skip Ollama models installation (AI off)")
    models = {
        "1": recommended,
        "2": SMALL_MODEL,
        "3": DEFAULT_MODEL,
        "4": "qwen2.5-coder:7b-base",
    }
    while True:
        try:
            answer = input("🌠 Choose AI setup [1]: ").strip().lower() or "1"
        except EOFError:
            return "off", None
        if answer in ("y", "yes"):
            answer = "1"
        if answer in ("n", "no", "7"):
            return "off", None
        if answer == "6":
            return "copilot", None
        if answer in models:
            return "ollama", models[answer]
        if answer == "5":
            try:
                name = input("🌸 Ollama model tag: ").strip()
            except EOFError:
                return "off", None
            if name:
                return "ollama", name
        print("🔔 Choose a number from 1 to 7.")
