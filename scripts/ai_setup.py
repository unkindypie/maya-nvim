"""Dependency-free GPU detection and AI setup choices."""

import platform
import subprocess
from pathlib import Path

DEFAULT_MODEL = "qwen2.5-coder:3b-base"
SMALL_MODEL = "qwen2.5-coder:1.5b-base"
QWEN_SMALL = "qwen2.5-coder:1.5b-base-q8_0"
QWEN_LARGE = "qwen2.5-coder:7b-base-q4_K_M"
MELLUM = "hf.co/JetBrains/Mellum-4b-sft-all-gguf:Q8_0"
SWEEP = "hf.co/sweepai/sweep-next-edit-1.5B:Q8_0"


def recommended_profile(gpu):
    memory = gpu.get("vram_mib")
    if memory is None or memory < 2048:
        return None
    if memory < 6144:
        return {"local_mode": "single", "next_edit_model": SWEEP}
    return {
        "local_mode": "dual",
        "model": QWEN_SMALL if memory < 8192 else QWEN_LARGE,
        "next_edit_model": SWEEP,
    }


def choose_profile():
    gpu = detect_gpu()
    recommended = recommended_profile(gpu)
    print(f"🌺 AI setup — {gpu}; VRAM tiers are estimates, not guarantees.")
    print("  1. Sweep single model (2–4 GB; CPU offload may be needed at 2 GB)")
    print("  2. Qwen 1.5B Q8 + Sweep (6 GB)")
    print("  3. Qwen 7B Q4_K_M + Sweep (8 GB+)")
    print("  4. Mellum 4B Q8 + Sweep (8 GB+ alternative)")
    print("  5. Custom / legacy inline completion only")
    print("  6. GitHub Copilot (authenticate with :Copilot auth)")
    print("  7. Skip Ollama models installation (AI off)")
    default = (
        None
        if not recommended
        else (
            "1"
            if recommended["local_mode"] == "single"
            else "2"
            if recommended["model"] == QWEN_SMALL
            else "3"
        )
    )
    while True:
        try:
            answer = (
                input(
                    "🌠 Choose AI setup"
                    + (f" [{default}]" if default else " (required)")
                    + ": "
                ).strip()
                or default
            )
        except EOFError:
            raise ValueError(
                "AI choice required; use --ai off, --ai copilot, or explicit --ai-mode and models"
            )
        if answer in ("n", "no"):
            answer = "7"
        if answer in ("y", "yes") and default:
            answer = default
        if answer == "6":
            return "copilot", {}
        if answer == "7":
            return "off", {}
        if answer == "1":
            return "ollama", {"local_mode": "single", "next_edit_model": SWEEP}
        if answer in ("2", "3", "4"):
            return "ollama", {
                "local_mode": "dual",
                "model": {"2": QWEN_SMALL, "3": QWEN_LARGE, "4": MELLUM}[answer],
                "next_edit_model": SWEEP,
            }
        if answer == "5":
            name = input("🌸 Ollama model tag: ").strip()
            if name:
                return "ollama", {"local_mode": "completion-only", "model": name}
        print("🔔 Choose a number from 1 to 7.")


def detect_gpu():
    """Return dedicated VRAM in MiB, or separately labeled shared memory."""
    devices = []
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=3,
            check=True,
        )
        for line in result.stdout.splitlines():
            columns = line.rsplit(",", 2)
            name, memory = columns[:2]
            memory = int(memory.strip())
            if memory > 0:
                devices.append(
                    {
                        "name": name.strip(),
                        "vram_mib": memory,
                        **(
                            {"free_mib": int(columns[2].strip())}
                            if len(columns) == 3
                            else {}
                        ),
                    }
                )
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
                    info = {"name": "AMD " + device.parent.name, "vram_mib": memory}
                    try:
                        info["free_mib"] = memory - int(
                            (device / "mem_info_vram_used").read_text()
                        ) // (1024 * 1024)
                    except (OSError, ValueError, StopIteration):
                        pass
                    devices.append(info)
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
