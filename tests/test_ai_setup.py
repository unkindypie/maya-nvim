"""GPU detection and explicit AI menu choices require no extra packages."""

import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "ai_choices", Path(__file__).resolve().parents[1] / "scripts/ai_setup.py"
)
ai = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai)


class AISetupTest(unittest.TestCase):
    def test_thresholds_and_unknown(self):
        self.assertEqual(ai.recommended_model({"vram_mib": 2048}), ai.SMALL_MODEL)
        self.assertEqual(ai.recommended_model({"vram_mib": 4096}), ai.DEFAULT_MODEL)
        self.assertEqual(ai.recommended_model({"shared_mib": 16384}), ai.DEFAULT_MODEL)
        self.assertEqual(ai.recommended_model({}), ai.DEFAULT_MODEL)

    def test_largest_nvidia_gpu_not_sum(self):
        with (
            patch.object(ai.platform, "system", return_value="Linux"),
            patch.object(ai.Path, "glob", return_value=[]),
            patch.object(
                ai.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(
                    [], 0, "GPU A, 2048\nGPU B, 6144\n"
                ),
            ),
        ):
            self.assertEqual(ai.detect_gpu()["vram_mib"], 6144)

    def test_unavailable_or_malformed(self):
        for result in [
            FileNotFoundError(),
            subprocess.TimeoutExpired("nvidia-smi", 3),
            subprocess.CompletedProcess([], 0, "unavailable"),
        ]:
            with (
                patch.object(ai.platform, "system", return_value="Linux"),
                patch.object(ai.Path, "glob", return_value=[]),
                patch.object(
                    ai.subprocess,
                    "run",
                    side_effect=result if isinstance(result, Exception) else None,
                    return_value=result,
                ),
            ):
                self.assertNotIn("vram_mib", ai.detect_gpu())

    def test_amd_and_shared_memory(self):
        with (
            patch.object(ai.platform, "system", return_value="Linux"),
            patch.object(ai.subprocess, "run", side_effect=FileNotFoundError()),
            patch.object(ai.Path, "glob", return_value=[Path("/fake/card0/device")]),
            patch.object(
                ai.Path, "read_text", side_effect=["0x1002", str(8 * 1024**3)]
            ),
        ):
            self.assertEqual(ai.detect_gpu()["vram_mib"], 8192)
        with (
            patch.object(ai.platform, "system", return_value="Darwin"),
            patch.object(
                ai.subprocess,
                "run",
                side_effect=[
                    FileNotFoundError(),
                    subprocess.CompletedProcess([], 0, str(16 * 1024**3)),
                ],
            ),
        ):
            result = ai.detect_gpu()
            self.assertEqual(result["shared_mib"], 16384)
            self.assertNotIn("vram_mib", result)

    def test_menu_recommendation_overrides_copilot_skip(self):
        for inputs, expected in [
            ([""], ("ollama", ai.SMALL_MODEL)),
            (["3"], ("ollama", ai.DEFAULT_MODEL)),
            (["6"], ("copilot", None)),
            (["7"], ("off", None)),
            (["5", "custom:model"], ("ollama", "custom:model")),
            (["bad", "7"], ("off", None)),
        ]:
            with (
                patch.object(
                    ai, "detect_gpu", return_value={"name": "test", "vram_mib": 2048}
                ),
                patch("builtins.input", side_effect=inputs),
            ):
                self.assertEqual(ai.choose(), expected)
