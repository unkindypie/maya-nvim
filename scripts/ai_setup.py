"""Local edit-model presets and dependency-free GPU detection."""

import platform
import subprocess
from pathlib import Path

SWEEP = "hf.co/sweepai/sweep-next-edit-1.5B:Q8_0"
ZETA21 = "hf.co/mradermacher/zeta-2.1-GGUF:Q4_K_M"
ZETA2 = "hf.co/bartowski/zed-industries_zeta-2-GGUF:Q4_K_M"


def engine_for(model):
    name = model.lower()
    if "zeta-2.1" in name:
        return "zeta-2.1"
    if "zeta-2" in name:
        return "zeta-2"
    if "sweep" in name:
        return "sweep"
    raise ValueError("Specify --engine sweep, zeta-2 or zeta-2.1 for a custom model")


def migrate(saved):
    result = dict(saved)
    if result.get("schema") != 2:
        result["legacy"] = {
            key: result[key]
            for key in ("model", "local_mode", "fim_format")
            if key in result
        }
        old = result.get("model", "")
        result["model"] = result.get("next_edit_model") or (
            old if "sweep" in old.lower() else SWEEP
        )
        result["engine"] = (
            "zeta-2.1"
            if "zeta-2.1" in result["model"].lower()
            else "zeta-2"
            if "zeta-2" in result["model"].lower()
            else "sweep"
        )
    for key in ("local_mode", "next_edit_model", "fim_format"):
        result.pop(key, None)
    result["schema"] = 2
    result.setdefault("model", SWEEP)
    result.setdefault(
        "engine",
        engine_for(result["model"]) if not result.get("engine") else result["engine"],
    )
    result.setdefault("context_size", 4096 if result["engine"] == "sweep" else 8192)
    return result


def recommended_profile(gpu):
    memory = gpu.get("vram_mib")
    if memory is None or memory < 2048:
        return None
    model = SWEEP
    return {"model": model, "engine": engine_for(model)}


def choose_profile():
    gpu = detect_gpu()
    recommended = recommended_profile(gpu)
    default = "1" if recommended else None
    print(f"Local AI — {gpu}. VRAM tiers are estimates; setup validates residency.")
    print("  1. Sweep 1.5B Q8 (recommended: measured quality and speed)")
    print("  2. Zeta-2.1 8B Q4_K_M (8 GB+ alternative)")
    print("  3. Zeta-2 8B Q4_K_M (8 GB+ alternative)")
    print("  4. Custom local edit model")
    print("  5. GitHub Copilot")
    print("  6. AI off")
    while True:
        try:
            answer = (
                input(f"Choose AI setup [{default or 'required'}]: ").strip() or default
            )
        except EOFError as error:
            raise ValueError(
                "Choose --ai off, --ai copilot, or --ai ollama --model MODEL"
            ) from error
        if answer in ("n", "no"):
            answer = "6"
        if answer in ("5", "6"):
            return ("copilot" if answer == "5" else "off"), {}
        if answer in ("1", "2", "3"):
            model = {"1": SWEEP, "2": ZETA21, "3": ZETA2}[answer]
            return "ollama", {"model": model, "engine": engine_for(model)}
        if answer == "4":
            model = input("Local Ollama model: ").strip()
            engine = input("Prompt format [sweep/zeta-2/zeta-2.1]: ").strip()
            if model and engine in ("sweep", "zeta-2", "zeta-2.1"):
                return "ollama", {"model": model, "engine": engine}
        print("Choose a number from 1 to 6.")


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
