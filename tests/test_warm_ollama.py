"""Warm only the models selected by Maya's saved AI state."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "warm_ollama", ROOT / "scripts/warm_ollama.py"
)
warm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(warm)


class WarmOllamaTest(unittest.TestCase):
    def run_warm(self, state, endpoint="http://127.0.0.1:11434"):
        calls = []

        def api(path, data=None, **kwargs):
            calls.append((path, data))
            if path == "/api/tags":
                return {"models": []}
            if path == "/api/generate":
                return {"response": ""}
            raise AssertionError("Unexpected API request: " + path)

        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "ai.json"
            path.write_text(json.dumps(state))
            with (
                patch.object(warm, "api", side_effect=api),
                patch(
                    "sys.argv",
                    [
                        "warm_ollama.py",
                        "--state",
                        str(path),
                        "--endpoint",
                        endpoint,
                        "--keep-alive",
                        "-1",
                    ],
                ),
            ):
                self.assertEqual(warm.main(), 0)
        return [data for path, data in calls if path == "/api/generate"]

    def test_dual_warms_inline_and_next_edit(self):
        calls = self.run_warm(
            {
                "provider": "ollama",
                "local_mode": "dual",
                "model": "qwen2.5-coder:1.5b-base-q8_0",
                "next_edit_model": "hf.co/sweepai/sweep-next-edit-1.5B:Q8_0",
            }
        )
        self.assertEqual(
            [call["model"] for call in calls],
            [
                "qwen2.5-coder:1.5b-base-q8_0",
                "hf.co/sweepai/sweep-next-edit-1.5B:Q8_0",
            ],
        )
        for call in calls:
            self.assertEqual(call["prompt"], "")
            self.assertEqual(str(call["keep_alive"]), "-1")
            self.assertEqual(call["options"]["num_ctx"], 4096)

    def test_single_warms_next_edit_only(self):
        calls = self.run_warm(
            {
                "provider": "ollama",
                "local_mode": "single",
                "model": "qwen2.5-coder:1.5b-base-q8_0",
                "next_edit_model": "hf.co/sweepai/sweep-next-edit-1.5B:Q8_0",
            }
        )
        self.assertEqual(
            [call["model"] for call in calls],
            ["hf.co/sweepai/sweep-next-edit-1.5B:Q8_0"],
        )

    def test_completion_only_warms_inline_only(self):
        calls = self.run_warm(
            {
                "provider": "ollama",
                "local_mode": "completion-only",
                "model": "qwen2.5-coder:1.5b-base-q8_0",
                "next_edit_model": "hf.co/sweepai/sweep-next-edit-1.5B:Q8_0",
            }
        )
        self.assertEqual(
            [call["model"] for call in calls], ["qwen2.5-coder:1.5b-base-q8_0"]
        )

    def test_off_makes_no_requests(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "ai.json"
            path.write_text(json.dumps({"provider": "off"}))
            with (
                patch.object(
                    warm,
                    "api",
                    side_effect=AssertionError("must not contact Ollama"),
                ),
                patch("sys.argv", ["warm_ollama.py", "--state", str(path)]),
            ):
                self.assertEqual(warm.main(), 0)

    def test_unavailable_server_returns_error(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "ai.json"
            path.write_text(
                json.dumps(
                    {
                        "provider": "ollama",
                        "local_mode": "completion-only",
                        "model": "qwen2.5-coder:1.5b-base-q8_0",
                    }
                )
            )
            with (
                patch.object(warm, "api", side_effect=OSError("offline")),
                patch(
                    "sys.argv",
                    [
                        "warm_ollama.py",
                        "--state",
                        str(path),
                        "--wait",
                        "0",
                    ],
                ),
            ):
                self.assertEqual(warm.main(), 1)


if __name__ == "__main__":
    unittest.main()
