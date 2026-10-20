"""A running Ollama server must not cause binary or model downloads."""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
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
                patch(
                    "sys.argv",
                    ["setup_ollama.py", "--models-dir", temp, "--model", model],
                ),
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

    def test_managed_service_keeps_models_warm(self):
        model = "qwen2.5-coder:3b-base"
        tags_calls = 0

        def api(path, data=None, **kwargs):
            nonlocal tags_calls
            if path == "/api/tags":
                tags_calls += 1
                if tags_calls == 1:
                    raise OSError("server not started")
                return {"models": [{"name": model}]}
            if path == "/api/generate":
                return {"response": "return a + b"}
            if path == "/api/ps":
                return {"models": []}
            raise AssertionError("Unexpected API request: " + path)

        with tempfile.TemporaryDirectory() as temp:
            with (
                patch.dict(
                    os.environ,
                    {
                        "HOME": temp,
                        "XDG_CONFIG_HOME": temp + "/config",
                        "XDG_STATE_HOME": temp + "/state",
                    },
                ),
                patch(
                    "sys.argv",
                    [
                        "setup_ollama.py",
                        "--models-dir",
                        temp,
                        "--model",
                        model,
                        "--yes",
                    ],
                ),
                patch.object(
                    setup,
                    "detect_gpu",
                    return_value={"name": "test", "vram_mib": 6144},
                ),
                patch.object(setup, "api", side_effect=api),
                patch.object(
                    setup, "install_binary", return_value=Path("/usr/bin/true")
                ),
                patch.object(setup, "run"),
            ):
                setup.main()

            service = (
                Path(temp) / "config/systemd/user/maya-nvim-ollama.service"
            ).read_text()
            self.assertIn("Environment=OLLAMA_KEEP_ALIVE=-1", service)
            self.assertIn("ExecStartPost=-", service)
            self.assertIn("warm_ollama.py", service)
            self.assertIn(str(sys.executable), service)
