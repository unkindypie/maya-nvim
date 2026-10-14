"""Exercise shell bootstrap with fake package managers; never touch host packages."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BasePrerequisitesTest(unittest.TestCase):
    def fixture(self, root, failure=False):
        binary = root / 'bin'
        binary.mkdir()
        (binary / 'env').symlink_to(shutil.which('env'))
        scripts = {
            'uname': '#!/bin/bash\necho Linux\n',
            'id': '#!/bin/bash\necho 1000\n',
            'sudo': '#!/bin/bash\nexec "$@"\n',
        }
        for name, text in scripts.items():
            file = binary / name
            file.write_text(text)
            file.chmod(0o755)
        text = '#!/bin/bash\nprintf "%s\\n" "$*" >> "$HOME/package-calls"\n'
        if failure:
            text += 'echo "permission denied" >&2\nexit 1\n'
        else:
            text += f'''if [[ ! -e "$HOME/bin/python3" ]]; then /bin/ln -s {sys.executable!r} "$HOME/bin/python3"; fi
if [[ ! -e "$HOME/bin/git" ]]; then
 printf '#!/bin/bash\\nexit 0\\n' > "$HOME/bin/git"
 /bin/chmod +x "$HOME/bin/git"
fi
'''
        for name in ('dnf', 'apt-get', 'pacman', 'zypper'):
            file = binary / name
            file.write_text(text)
            file.chmod(0o755)
        return dict(os.environ, HOME=str(root), PATH=str(binary))

    def run_base(self, env, flags):
        return subprocess.run(['/bin/bash', '-c', 'source "$1/bootstrap.sh"; shift; maya_base_prerequisites clone "$@"',
                               '--', str(ROOT), *flags], env=env, capture_output=True, text=True, timeout=10)

    def test_install_and_recheck(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = self.fixture(root)
            result = self.run_base(env, ['--yes'])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((root / 'bin/python3').exists())
            before = (root / 'package-calls').read_text()
            result = self.run_base(env, ['--yes'])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / 'package-calls').read_text(), before)

    def test_dry_run_and_decline_do_not_install(self):
        for flags in (['--dry-run'], ['--yes', '--no-install-prerequisites'], []):
            with self.subTest(flags=flags), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                result = self.run_base(self.fixture(root), flags)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((root / 'package-calls').exists())
                self.assertIn('prerequisites', result.stdout + result.stderr)

    def test_permission_failure_prints_manual_command(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.run_base(self.fixture(Path(temp), failure=True), ['--yes'])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Run manually: sudo', result.stderr)
            self.assertIn('Do not run the whole installer with sudo', result.stderr)

    def test_reuse_versioned_python_when_default_is_old(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = self.fixture(root, failure=True)
            (root / 'bin/python3').write_text('#!/bin/bash\nexit 1\n')
            (root / 'bin/python3').chmod(0o755)
            (root / 'bin/python3.13').symlink_to(sys.executable)
            (root / 'bin/git').write_text('#!/bin/bash\nexit 0\n')
            (root / 'bin/git').chmod(0o755)
            result = self.run_base(env, ['--yes'])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((root / 'package-calls').exists())
