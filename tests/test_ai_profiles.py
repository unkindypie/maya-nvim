"""Preset selection and migration do not require a GPU or Ollama."""

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
    def args(self, **kwargs):
        return SimpleNamespace(
            ai=None,
            model=None,
            ai_mode=None,
            next_edit_model=None,
            skip_bootstrap=False,
            dry_run=False,
            yes=True,
            **kwargs,
        )

    def test_tiers_and_unknown(self):
        for memory, mode, model in (
            (2048, "single", None),
            (4096, "single", None),
            (5120, "single", None),
            (6144, "dual", ai.QWEN_SMALL),
            (8192, "dual", ai.QWEN_LARGE),
        ):
            profile = ai.recommended_profile({"vram_mib": memory})
            self.assertEqual(profile["local_mode"], mode)
            self.assertEqual(profile.get("model"), model)
            self.assertEqual(profile["next_edit_model"], ai.SWEEP)
        self.assertIsNone(ai.recommended_profile({}))
        self.assertIsNone(ai.recommended_profile({"vram_mib": 1024}))
        self.assertIsNone(ai.recommended_profile({"shared_mib": 32768}))

    def test_unknown_noninteractive_requires_selection(self):
        with (
            tempfile.TemporaryDirectory() as temp,
            patch.object(installer, "detect_gpu", return_value={}),
        ):
            with self.assertRaisesRegex(ValueError, "VRAM unavailable"):
                installer.choose_ai(self.args(), Path(temp))
            args = self.args()
            args.ai_mode = "single"
            self.assertEqual(installer.choose_ai(args, Path(temp)), "ollama")
            args = self.args()
            args.ai = "copilot"
            self.assertEqual(installer.choose_ai(args, Path(temp)), "copilot")

    def test_unknown_interactive_no_implicit_default(self):
        with (
            patch.object(ai, "detect_gpu", return_value={"name": "unknown"}),
            patch("builtins.input", side_effect=["", "6"]),
        ):
            self.assertEqual(ai.choose_profile(), ("copilot", {}))

    def test_legacy_and_dual_saved_preferences(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp)
            for mode in (None, "single", "dual"):
                saved = {
                    "provider": "ollama",
                    "model": "custom:old",
                    "endpoint": "http://custom:123",
                    "next_edit_model": "custom:sweep",
                }
                if mode:
                    saved["local_mode"] = mode
                (state / "ai.json").write_text(json.dumps(saved))
                args = self.args()
                self.assertEqual(installer.choose_ai(args, state), "ollama")
                self.assertEqual(args.ai_mode, mode)
                self.assertEqual(args.model, None if mode == "single" else "custom:old")
                self.assertEqual(json.loads((state / "ai.json").read_text()), saved)

    def test_explicit_legacy_model_and_conflicts(self):
        with tempfile.TemporaryDirectory() as temp:
            args = self.args()
            args.model = "custom:new"
            self.assertEqual(installer.choose_ai(args, Path(temp)), "ollama")
            self.assertEqual(args.ai_mode, "completion-only")
            args = self.args()
            args.model = "custom:new"
            args.ai_mode = "single"
            with self.assertRaisesRegex(ValueError, "Single mode"):
                installer.choose_ai(args, Path(temp))

    def test_download_only_required_and_preserve_custom_endpoint(self):
        for mode in ("single", "dual"):
            with tempfile.TemporaryDirectory() as temp:
                state = Path(temp) / "maya-nvim"
                state.mkdir()
                saved = {
                    "provider": "off",
                    "model": "legacy:keep",
                    "endpoint": "http://custom:123",
                    "custom_key": True,
                }
                (state / "ai.json").write_text(json.dumps(saved))
                pulled = []

                def api(path, data=None, **kwargs):
                    if path == "/api/tags":
                        return {"models": []}
                    if path == "/api/pull":
                        pulled.append(data["name"])
                        return {}
                    if path == "/api/show":
                        return {"model_info": {"qwen.context_length": 8192}}
                    if path == "/api/generate":
                        return {"response": "prediction"}
                    if path == "/api/ps":
                        return {
                            "models": [
                                {"name": name, "size": 100, "size_vram": 100}
                                for name in pulled
                            ]
                        }
                    raise AssertionError(path)

                argv = [
                    "setup_ollama.py",
                    "--yes",
                    "--models-dir",
                    temp,
                    "--ai-mode",
                    mode,
                ]
                if mode == "dual":
                    argv += ["--model", ai.QWEN_SMALL]
                with (
                    patch.dict("os.environ", {"XDG_STATE_HOME": temp}),
                    patch("sys.argv", argv),
                    patch.object(setup, "api", side_effect=api),
                    patch.object(setup, "detect_gpu", return_value={"vram_mib": 6144}),
                ):
                    setup.main()
                self.assertEqual(
                    pulled,
                    [ai.SWEEP] if mode == "single" else [ai.QWEN_SMALL, ai.SWEEP],
                )
                result = json.loads((state / "ai.json").read_text())
                self.assertEqual(result["endpoint"], saved["endpoint"])
                self.assertTrue(result["custom_key"])
                if mode == "single":
                    self.assertEqual(result["model"], "legacy:keep")

    def test_sweep_missing_tag_uses_same_q8_asset_alias(self):
        with tempfile.TemporaryDirectory() as temp:
            calls = []

            def api(path, data=None, **kwargs):
                calls.append((path, data))
                if path == "/api/tags":
                    return {"models": []}
                if path == "/api/pull":
                    if data["name"] == ai.SWEEP:
                        raise RuntimeError("The specified tag is not available")
                    return {}
                if path in ("/api/show", "/api/create"):
                    return {}
                if path == "/api/generate":
                    return {"response": "prediction"}
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
                        "--ai-mode",
                        "single",
                    ],
                ),
                patch.object(setup, "api", side_effect=api),
                patch.object(setup, "detect_gpu", return_value={}),
            ):
                setup.main()
            creates = [data for path, data in calls if path == "/api/create"]
            self.assertEqual(
                creates,
                [
                    {
                        "model": ai.SWEEP,
                        "from": "hf.co/sweepai/sweep-next-edit-1.5B:sweep-next-edit-1.5b.q8_0.v2.gguf",
                        "stream": False,
                    }
                ],
            )

    def test_failed_residency_preserves_state(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / "maya-nvim"
            state.mkdir()
            original = '{"provider":"off","model":"old"}'
            (state / "ai.json").write_text(original)

            def api(path, data=None, **kwargs):
                if path == "/api/tags":
                    return {
                        "models": [{"name": name} for name in (ai.QWEN_SMALL, ai.SWEEP)]
                    }
                if path == "/api/show":
                    return {}
                if path == "/api/generate":
                    return {"response": "prediction"}
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
                        "--ai-mode",
                        "dual",
                        "--model",
                        ai.QWEN_SMALL,
                    ],
                ),
                patch.object(setup, "api", side_effect=api),
                patch.object(setup, "detect_gpu", return_value={"vram_mib": 6144}),
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "Previous AI preferences kept"
                ):
                    setup.main()
            self.assertEqual((state / "ai.json").read_text(), original)
