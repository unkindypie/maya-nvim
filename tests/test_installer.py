import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('installer', ROOT / 'scripts/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallerTest(unittest.TestCase):
    def test_declining_ai_skips_ollama_and_persists_off(self):
        with tempfile.TemporaryDirectory() as temp:
            def version(args, **kwargs):
                return {'nvim': 'NVIM v0.12.5', 'node': 'v22.0.0', 'tree-sitter': 'tree-sitter 0.26.1'}[args[0]]
            with patch.dict(os.environ, {'HOME': temp, 'XDG_CONFIG_HOME': temp + '/config', 'XDG_STATE_HOME': temp + '/state'}), \
                 patch('sys.argv', ['install.py', '--no-shell', '--pokemon-sound-on-start', '--reopen-tabs']), \
                 patch.object(installer.shutil, 'which', return_value='/usr/bin/true'), \
                 patch.object(installer.subprocess, 'check_output', side_effect=version), \
                 patch.object(installer.subprocess, 'run') as run, \
                 patch.object(installer.sys.stdin, 'isatty', return_value=True), \
                 patch('builtins.input', return_value='n'):
                installer.main()
                self.assertEqual(run.call_count, 2)  # Only plugin/tool bootstrap.
                self.assertNotIn('setup_ollama.py', str(run.call_args_list))
            import json
            self.assertEqual(json.loads((Path(temp) / 'state/maya-nvim/ai.json').read_text())['provider'], 'off')

    def test_ai_question_overrides_and_saved_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp)
            args = SimpleNamespace(ai=None, skip_bootstrap=False, dry_run=False, yes=False)
            with patch.object(installer.sys.stdin, 'isatty', return_value=True), patch('builtins.input', return_value='n'):
                self.assertEqual(installer.choose_ai(args, state), 'off')
            with patch.object(installer.sys.stdin, 'isatty', return_value=True), patch('builtins.input', return_value=''):
                self.assertEqual(installer.choose_ai(args, state), 'ollama')
            with patch.object(installer.sys.stdin, 'isatty', return_value=False):
                self.assertEqual(installer.choose_ai(args, state), 'off')
                args.yes = True
                self.assertEqual(installer.choose_ai(args, state), 'ollama')
            (state / 'ai.json').write_text('{"provider":"off"}')
            with patch('builtins.input', side_effect=AssertionError('must preserve existing choice')):
                self.assertEqual(installer.choose_ai(args, state), 'off')
                args.ai = 'copilot'
                self.assertEqual(installer.choose_ai(args, state), 'copilot')
            (state / 'ai.json').unlink()
            args.ai = None
            args.dry_run = True
            with patch('builtins.input', side_effect=AssertionError('dry run must not prompt')):
                self.assertEqual(installer.choose_ai(args, state), 'off')

    def test_preference_questions(self):
        with patch('builtins.input', side_effect=['maybe', 'n']):
            self.assertFalse(installer.ask_boolean('Sound?'))
        with patch('builtins.input', return_value=''):
            self.assertTrue(installer.ask_boolean('Tabs?'))

    def test_persist_preferences_and_preserve_on_reinstall(self):
        with tempfile.TemporaryDirectory() as temp:
            env = dict(os.environ, HOME=temp, XDG_CONFIG_HOME=str(Path(temp) / 'config'))
            command = [sys.executable, str(ROOT / 'scripts/install.py'), '--skip-bootstrap', '--no-shell', '--yes']
            subprocess.run(command + ['--no-pokemon-sound-on-start', '--no-reopen-tabs'], env=env, check=True, capture_output=True)
            personal = Path(temp) / 'config/mvim/init.lua'
            text = personal.read_text()
            self.assertIn('pokemon_sound_on_start = false,', text)
            self.assertIn('reopen_tabs = false,', text)
            subprocess.run(command, env=env, check=True, capture_output=True)
            self.assertEqual(personal.read_text(), text)

    def test_managed_block_precedes_tmux_and_is_idempotent(self):
        original = "# settings\nif command -v tmux; then\n  exec tmux\nfi\n"
        updated = installer.managed(original, "alias mvim='/tmp/some path/mvim'")
        self.assertLess(updated.index('alias mvim'), updated.index('if command'))
        self.assertEqual(updated, installer.managed(updated, "alias mvim='/tmp/some path/mvim'"))

    def test_missing_prerequisites_make_no_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            env = dict(os.environ, HOME=temp, XDG_CONFIG_HOME=str(home / 'config'), PATH=str(home / 'empty'))
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/install.py'), '--ai', 'off'], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('prerequisites', result.stderr)
            self.assertFalse((home / '.zshrc').exists())
            self.assertFalse((home / 'config').exists())

    def test_install_repeat_collision_and_dry_run(self):
        with tempfile.TemporaryDirectory(prefix='maya install space ') as temp:
            home = Path(temp)
            env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / 'config space'))
            sessionizer = home / 'sessionizer'
            sessionizer.write_text("discover_directories() {\n    printf '%s\\n' \"$HOME/scripts\" \"$HOME/notes\"\n}\n")
            command = [str(ROOT / 'install.sh'), '--skip-bootstrap', '--ai', 'off', '--tmux-sessionizer', str(sessionizer)]
            before = sessionizer.read_text()
            subprocess.run(command + ['--dry-run'], env=env, check=True, capture_output=True)
            self.assertFalse((home / '.zshrc').exists())
            self.assertEqual(sessionizer.read_text(), before)
            subprocess.run(command, env=env, check=True, capture_output=True)
            self.assertEqual((home / 'config space/maya-nvim').resolve(), ROOT)
            personal = home / 'config space/mvim/init.lua'
            self.assertTrue(personal.is_file())
            self.assertIn('pokemon_sound_on_start = true,', personal.read_text())
            self.assertIn('reopen_tabs = true,', personal.read_text())
            personal.write_text('return {options={number=false}}\n')
            shell = (home / '.zshrc').read_text()
            updated = sessionizer.read_text()
            subprocess.run(command, env=env, check=True, capture_output=True)
            self.assertEqual((home / '.zshrc').read_text(), shell)
            self.assertEqual(personal.read_text(), 'return {options={number=false}}\n')
            self.assertEqual(sessionizer.read_text(), updated)
            self.assertEqual(updated.count(str(ROOT)), 1)
            target = home / '.local/bin/mvim'
            target.unlink()
            target.write_text('unrelated launcher')
            result = subprocess.run(command, env=env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(target.read_text(), 'unrelated launcher')


if __name__ == '__main__':
    unittest.main()
