"""One-model presets, saved preference migration and failed setup preservation."""

import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


ai = module("profiles", "scripts/ai_setup.py")
installer = module("profile_installer", "scripts/install.py")
setup = module("profile_setup", "scripts/setup_ollama.py")


class ProfilesTest(unittest.TestCase):
    def test_tiers(self):
        for memory in (2048, 4096, 6144):
            self.assertEqual(
                ai.recommended_profile({"vram_mib": memory})["model"], ai.SWEEP
            )
        for memory in (8192, 12288, 24576):
            self.assertEqual(
                ai.recommended_profile({"vram_mib": memory})["model"], ai.SWEEP
            )
        self.assertIsNone(ai.recommended_profile({}))
        self.assertIsNone(ai.recommended_profile({"shared_mib": 16384}))

    def test_migration_and_idempotence(self):
        for mode in ("dual", "single", "completion-only"):
            saved = {
                "provider": "off",
                "endpoint": "http://localhost:9988",
                "model": "old-qwen",
                "local_mode": mode,
                "next_edit_model": "custom-sweep",
            }
            result = ai.migrate(saved)
            self.assertEqual(result["model"], "custom-sweep")
            self.assertEqual(result["provider"], "off")
            self.assertEqual(result["endpoint"], saved["endpoint"])
            self.assertEqual(result["legacy"]["model"], "old-qwen")
            self.assertNotIn("local_mode", result)
            self.assertEqual(ai.migrate(result), result)
            self.assertEqual(saved["local_mode"], mode)
        self.assertEqual(ai.migrate({"model": "qwen"})["model"], ai.SWEEP)
        self.assertEqual(
            ai.migrate({"schema": 2, "model": "custom", "engine": "zeta-2"})["model"],
            "custom",
        )

    def test_explicit_model_and_saved_off(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp)
            (state / "ai.json").write_text('{"provider":"off"}')
            args = SimpleNamespace(
                ai=None,
                model=None,
                engine=None,
                yes=True,
                skip_bootstrap=False,
                dry_run=False,
            )
            self.assertEqual(installer.choose_ai(args, state), "off")
            args.model = ai.ZETA2
            self.assertEqual(installer.choose_ai(args, state), "ollama")
            self.assertEqual(args.engine, "zeta-2")

    def test_context_alias_and_atomic_failure(self):
        for fail in (False, "server", "residency"):
            with tempfile.TemporaryDirectory() as temp:
                state = Path(temp, "maya-nvim")
                state.mkdir()
                original = '{"provider":"off","model":"old"}'
                (state / "ai.json").write_text(original)
                calls = []

                def api(path, data=None, **kwargs):
                    calls.append((path, data))
                    if path == "/api/tags":
                        return {"models": [{"name": ai.SWEEP}]}
                    if path == "/api/create":
                        return {}
                    if path == "/v1/completions":
                        if fail == "server":
                            raise RuntimeError("server failed")
                        return {"choices": [{"text": "test"}]}
                    if path == "/api/ps":
                        return {"models": []}
                    raise AssertionError(path)

                with (
                    patch.dict("os.environ", {"XDG_STATE_HOME": temp}),
                    patch(
                        "sys.argv",
                        [
                            "setup_ollama.py",
                            "--yes",
                            "--models-dir",
                            temp,
                            "--model",
                            ai.SWEEP,
                        ],
                    ),
                    patch.object(setup, "api", side_effect=api),
                    patch.object(
                        setup,
                        "detect_gpu",
                        return_value={"vram_mib": 8192, "free_mib": 100}
                        if fail == "residency"
                        else {},
                    ),
                ):
                    if fail:
                        with self.assertRaisesRegex(
                            RuntimeError,
                            "server failed" if fail == "server" else "VRAM reserve",
                        ):
                            setup.main()
                        self.assertEqual((state / "ai.json").read_text(), original)
                    else:
                        setup.main()
                        result = json.loads((state / "ai.json").read_text())
                        self.assertEqual(result["engine"], "sweep")
                        self.assertEqual(result["source_model"], ai.SWEEP)
                        self.assertEqual(result["context_size"], 4096)
                create = next(data for path, data in calls if path == "/api/create")
                self.assertEqual(create["parameters"], {"num_ctx": 4096})
                self.assertNotEqual(create["model"], ai.SWEEP)
