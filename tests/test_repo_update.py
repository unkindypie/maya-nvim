"""Update real disposable Git checkouts without contacting GitHub."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REMOTE = 'https://github.com/unkindypie/maya-nvim.git'


class RepoUpdateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='maya repo update ')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.source = self.home / 'source'
        self.source.mkdir()
        self.git(self.source, 'init', '-q', '--initial-branch=master')
        (self.source / 'install.sh').write_text('#!/bin/bash\nprintf "revision:old\\n"\n')
        self.commit(self.source, 'initial')
        self.env = dict(os.environ, HOME=str(self.home), GIT_CONFIG_COUNT='1',
                        GIT_CONFIG_KEY_0='url.' + self.source.as_uri() + '.insteadOf',
                        GIT_CONFIG_VALUE_0=REMOTE)
        self.destination = self.home / 'maya-nvim'
        subprocess.run(['git', 'clone', '-q', REMOTE, str(self.destination)], env=self.env, check=True)

    def git(self, directory, *args):
        return subprocess.check_output(['git', '-C', str(directory), *args], text=True,
                                       env=getattr(self, 'env', None)).strip()

    def commit(self, directory, message):
        self.git(directory, 'add', '.')
        self.git(directory, '-c', 'user.name=Update test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', message)

    def upstream_update(self):
        (self.source / 'install.sh').write_text('#!/bin/bash\nprintf "revision:new\\n"\n')
        self.commit(self.source, 'upstream update')

    def bootstrap(self, *args):
        return subprocess.run(['bash', str(ROOT / 'bootstrap.sh'), *args], env=self.env,
                              capture_output=True, text=True, timeout=20)

    def update(self, *args):
        return subprocess.run(['bash', '-c', 'source "$1/bootstrap.sh"; shift; destination=$1; shift; maya_update_repo "$destination" "$@"',
                               '--', str(ROOT), str(self.destination), *args], env=self.env,
                              capture_output=True, text=True, timeout=20)

    def test_rerun_pulls_master_and_runs_new_installer(self):
        self.upstream_update()
        result = self.bootstrap('--ai', 'off')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('revision:new', result.stdout)
        self.assertEqual(self.git(self.destination, 'rev-parse', 'HEAD'), self.git(self.source, 'rev-parse', 'HEAD'))
        result = self.bootstrap()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_no_update_and_dry_run_do_not_fetch(self):
        before = self.git(self.destination, 'rev-parse', 'HEAD')
        self.upstream_update()
        for flags in (['--no-update'], ['--dry-run']):
            result = self.bootstrap(*flags)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.git(self.destination, 'rev-parse', 'HEAD'), before)
            self.assertFalse((self.destination / '.git/FETCH_HEAD').exists())

    def test_dirty_tree_and_other_branch_are_preserved(self):
        self.upstream_update()
        (self.destination / 'install.sh').write_text('local edits\n')
        result = self.bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.destination / 'install.sh').read_text(), 'local edits\n')
        self.commit(self.destination, 'local edit')
        self.git(self.destination, 'switch', '-qc', 'my-work')
        result = self.update()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git(self.destination, 'branch', '--show-current'), 'my-work')

    def test_divergence_is_not_rebased_or_reset(self):
        (self.destination / 'local-file').write_text('keep')
        self.commit(self.destination, 'local commit')
        before = self.git(self.destination, 'rev-parse', 'HEAD')
        self.upstream_update()
        result = self.update()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git(self.destination, 'rev-parse', 'HEAD'), before)
        self.assertEqual((self.destination / 'local-file').read_text(), 'keep')

    def test_unrelated_origin_or_directory_is_rejected(self):
        self.git(self.destination, 'remote', 'set-url', 'origin', 'https://example.invalid/unrelated.git')
        result = self.bootstrap('--no-update')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('unrelated origin', result.stderr)

    def test_network_failure_keeps_checkout_and_skips_setup(self):
        before = self.git(self.destination, 'rev-parse', 'HEAD')
        self.env['GIT_CONFIG_KEY_0'] = 'url.' + (self.home / 'missing').as_uri() + '.insteadOf'
        result = self.bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('revision:old', result.stdout)
        self.assertEqual(self.git(self.destination, 'rev-parse', 'HEAD'), before)

    def test_local_installer_reloads_itself_after_pull(self):
        original = (ROOT / 'install.sh').read_text()
        target = 'exec "$MAYA_NVIM_PYTHON" "$ROOT/scripts/install.py" "$@"'
        (self.source / 'install.sh').write_text(original.replace(target, 'echo installer:old\n' + target))
        (self.source / 'bootstrap.sh').write_text((ROOT / 'bootstrap.sh').read_text())
        (self.source / 'scripts').mkdir()
        (self.source / 'scripts/install.py').write_text('print("setup executed")\n')
        self.commit(self.source, 'old local installer')
        self.git(self.destination, 'pull', '--ff-only', 'origin', 'master')
        (self.source / 'install.sh').write_text(original.replace(target, 'echo installer:new\n' + target))
        self.commit(self.source, 'new local installer')
        result = subprocess.run(['bash', str(self.destination / 'install.sh'), '--ai', 'off'], env=self.env,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('installer:new', result.stdout)
        self.assertNotIn('installer:old', result.stdout)
        self.assertIn('setup executed', result.stdout)
