import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('installer', ROOT / 'scripts/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallerTest(unittest.TestCase):
    def test_managed_block_precedes_tmux_and_is_idempotent(self):
        original = "# settings\nif command -v tmux; then\n  exec tmux\nfi\n"
        updated = installer.managed(original, "alias mvim='/tmp/some path/mvim'")
        self.assertLess(updated.index('alias mvim'), updated.index('if command'))
        self.assertEqual(updated, installer.managed(updated, "alias mvim='/tmp/some path/mvim'"))

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
            shell = (home / '.zshrc').read_text()
            updated = sessionizer.read_text()
            subprocess.run(command, env=env, check=True, capture_output=True)
            self.assertEqual((home / '.zshrc').read_text(), shell)
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
