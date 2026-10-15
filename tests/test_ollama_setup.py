"""A running Ollama server must not cause binary or model downloads."""

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "ollama_setup", ROOT / "scripts/setup_ollama.py"
)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class OllamaSetupTest(unittest.TestCase):
    def test_reuses_running_server_and_existing_model(self):
        self.check_existing_model("qwen2.5-coder:3b-base")

    def test_preserves_saved_older_model(self):
        self.check_existing_model("qwen2.5-coder:7b", saved=True)

    def check_existing_model(self, model, saved=False):
        with tempfile.TemporaryDirectory() as temp:
            if saved:
                state = Path(temp) / "maya-nvim"
                state.mkdir()
                (state / "ai.json").write_text(
                    json.dumps({"provider": "ollama", "model": model})
                )

            def api(path, data=None, **kwargs):
                if path == "/api/tags":
                    return {"models": [{"name": model}]}
                if path == "/api/generate":
                    return {"response": "return a + b"}
                if path == "/api/ps":
                    return {"models": []}
                raise AssertionError("Unexpected API request: " + path)

            with (
                patch.dict(os.environ, {"XDG_STATE_HOME": temp}),
                patch("sys.argv", ["setup_ollama.py", "--models-dir", temp]),
                patch.object(
                    setup, "detect_gpu", return_value={"name": "test", "vram_mib": 6144}
                ),
                patch.object(setup, "api", side_effect=api),
                patch.object(
                    setup,
                    "install_binary",
                    side_effect=AssertionError("must reuse server"),
                ),
                patch.object(
                    setup,
                    "run",
                    side_effect=AssertionError("must not install/start service"),
                ),
            ):
                setup.main()
            state = json.loads((Path(temp) / "maya-nvim/ai.json").read_text())
            self.assertEqual(state["provider"], "ollama")
            self.assertEqual(state["model"], model)
