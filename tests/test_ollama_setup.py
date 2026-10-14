"""A running Ollama server must not cause binary or model downloads."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ollama_setup', ROOT / 'scripts/setup_ollama.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class OllamaSetupTest(unittest.TestCase):
    def test_reuses_running_server_and_existing_model(self):
        with tempfile.TemporaryDirectory() as temp:
            def api(path, data=None, **kwargs):
                if path == '/api/tags':
                    return {'models': [{'name': 'qwen2.5-coder:1.5b'}]}
                if path == '/api/generate':
                    return {'response': 'return a + b'}
                if path == '/api/ps':
                    return {'models': []}
                raise AssertionError('Unexpected API request: ' + path)
            with patch.dict(os.environ, {'XDG_STATE_HOME': temp}), \
                 patch('sys.argv', ['setup_ollama.py', '--models-dir', temp]), \
                 patch.object(setup, 'api', side_effect=api), \
                 patch.object(setup, 'install_binary', side_effect=AssertionError('must reuse server')), \
                 patch.object(setup, 'run', side_effect=AssertionError('must not install/start service')):
                setup.main()
            state = json.loads((Path(temp) / 'maya-nvim/ai.json').read_text())
            self.assertEqual(state['provider'], 'ollama')
            self.assertEqual(state['model'], 'qwen2.5-coder:1.5b')
