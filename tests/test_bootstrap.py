"""Run the download bootstrap against a local Git fixture, without network installs."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REMOTE = 'https://github.com/unkindypie/maya-nvim.git'


class BootstrapTest(unittest.TestCase):
    def test_clone_master_forward_flags_and_preserve_stdin(self):
        with tempfile.TemporaryDirectory(prefix='maya bootstrap space ') as temp:
            home = Path(temp)
            source = home / 'source'
            source.mkdir()
            subprocess.run(['git', 'init', '-q', '--initial-branch=master', str(source)], check=True)
            (source / 'install.sh').write_text('''#!/usr/bin/env bash
set -eu
printf 'argument:%s\\n' "$@"
read -r answer
printf 'answer:%s\\n' "$answer"
''')
            subprocess.run(['git', '-C', str(source), 'add', 'install.sh'], check=True)
            subprocess.run(['git', '-C', str(source), '-c', 'user.name=Bootstrap test',
                            '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture'], check=True)
            env = dict(os.environ, HOME=temp, GIT_CONFIG_COUNT='1',
                       GIT_CONFIG_KEY_0='url.' + source.as_uri() + '.insteadOf',
                       GIT_CONFIG_VALUE_0=REMOTE)
            result = subprocess.run(['bash', '-c', (ROOT / 'bootstrap.sh').read_text(), '--', '--ai', 'off'],
                                    env=env, input='n\n', capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('argument:--ai\nargument:off', result.stdout)
            self.assertIn('answer:n', result.stdout)
            destination = home / 'maya-nvim'
            branch = subprocess.check_output(['git', '-C', str(destination), 'branch', '--show-current'], text=True)
            self.assertEqual(branch.strip(), 'master')
            sentinel = destination / 'user-file'
            sentinel.write_text('keep this')
            result = subprocess.run(['bash', str(ROOT / 'bootstrap.sh')], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('local changes are preserved', result.stderr)
            self.assertEqual(sentinel.read_text(), 'keep this')
            alternate = home / 'another clone'
            result = subprocess.run(['bash', str(ROOT / 'bootstrap.sh'), '--yes'],
                                    env=dict(env, MAYA_NVIM_INSTALL_DIR=str(alternate)),
                                    input='yes\n', capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((alternate / '.git').is_dir())
            self.assertIn('argument:--yes', result.stdout)

    def test_failed_clone_does_not_run_installer(self):
        with tempfile.TemporaryDirectory() as temp:
            env = dict(os.environ, HOME=temp, GIT_CONFIG_COUNT='1',
                       GIT_CONFIG_KEY_0='url.' + (Path(temp) / 'missing').as_uri() + '.insteadOf',
                       GIT_CONFIG_VALUE_0=REMOTE)
            result = subprocess.run(['bash', str(ROOT / 'bootstrap.sh')], env=env,
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('Installed.', result.stdout)
