"""Platform plans and failure recovery; never runs a host package manager."""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prerequisites', ROOT / 'scripts/prerequisites.py')
prerequisites = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prerequisites)


class PrerequisiteTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='maya prerequisite tests ')
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, HOME=self.temp.name, XDG_DATA_HOME=self.temp.name + '/data')
        self.env.start()
        self.addCleanup(self.env.stop)
        self.args = argparse.Namespace(dry_run=False, yes=False, install_prerequisites=None,
                                       install_audio=None, install_nerd_font=None)

    def instance(self, backend='apt-get'):
        with patch.object(prerequisites, 'manager', return_value=backend):
            return prerequisites.Prerequisites(self.args, retry='bash /some/path/install.sh --ai off')

    def test_manager_detection(self):
        with patch.object(prerequisites.shutil, 'which', side_effect=lambda value: '/bin/' + value):
            for name, backend in [('fedora', 'dnf'), ('ubuntu', 'apt-get'), ('debian', 'apt-get'),
                                  ('arch', 'pacman'), ('opensuse-tumbleweed', 'zypper')]:
                self.assertEqual(prerequisites.manager('Linux', {'ID': name}), backend)
            self.assertEqual(prerequisites.manager('Linux', {'ID': 'derivative', 'ID_LIKE': 'ubuntu debian'}), 'apt-get')
            self.assertEqual(prerequisites.manager('Darwin'), 'brew')
            self.assertIsNone(prerequisites.manager('Other'))

    def test_commands_and_privileges(self):
        expected = {'apt-get': ['curl', 'build-essential'], 'dnf': ['curl', 'gcc', 'gcc-c++', 'make'],
                    'pacman': ['curl', 'base-devel'], 'zypper': ['curl', 'gcc', 'gcc-c++', 'make'],
                    'brew': ['curl', 'ripgrep']}
        for backend, packages in expected.items():
            p = self.instance(backend)
            with patch.object(prerequisites.os, 'geteuid', return_value=1000):
                commands = p.package_commands(['curl', 'rg'] if backend == 'brew' else ['curl', 'cc'])
            command = commands[-1]
            self.assertEqual(command[-len(packages):], packages)
            self.assertEqual(command[0], 'brew' if backend == 'brew' else 'sudo')
            self.assertNotIn('upgrade', command)
            self.assertNotIn('-Sy', command)
        with patch.object(prerequisites.os, 'geteuid', return_value=0):
            self.assertEqual(self.instance().package_commands(['git'])[0][0], 'apt-get')

    def test_dry_run_never_installs_or_downloads(self):
        self.args.dry_run = True
        p = self.instance()
        with patch.object(prerequisites.subprocess, 'run', side_effect=AssertionError('mutation')), \
             patch.object(p, 'download', side_effect=AssertionError('download')), \
             patch.object(p, 'font_present', return_value=None), \
             patch('builtins.input', side_effect=AssertionError('prompt')):
            p.packages(['git'])
            p.managed('nvim')
            p.font()
        self.assertFalse(p.root.exists())

    def test_noninteractive_decline_has_manual_command(self):
        p = self.instance()
        with patch.object(prerequisites.sys.stdin, 'isatty', return_value=False), \
             patch.object(prerequisites.os, 'geteuid', return_value=1000), \
             contextlib.redirect_stderr(io.StringIO()) as errors:
            with self.assertRaises(RuntimeError):
                p.packages(['git'])
        self.assertIn('sudo apt-get install --no-upgrade -y git', errors.getvalue())
        self.assertIn('bash /some/path/install.sh --ai off', errors.getvalue())

    def test_failed_install_rechecks_after_manual_action(self):
        self.args.install_prerequisites = True
        p = self.instance('dnf')
        with patch.object(prerequisites.subprocess, 'run', side_effect=PermissionError('sudo')), \
             patch.object(prerequisites.sys.stdin, 'isatty', return_value=True), \
             patch('builtins.input', return_value=''), contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertTrue(p.packages(['git']))
        self.assertIn('Do not run the whole installer with sudo', errors.getvalue())
        self.assertIn('dnf install -y git', errors.getvalue())

    def test_only_missing_tools_are_installed_and_rerun_skips(self):
        p = self.instance()
        installed = {'git', 'curl', 'tar', 'unzip', 'cc', 'npm'}
        def packages(names, **kwargs):
            self.assertEqual(names, ['rg'])
            installed.update(names)
        def managed(name):
            installed.add(name)
        with patch.object(prerequisites.shutil, 'which', side_effect=lambda name: '/bin/' + name if name in installed else None), \
             patch.object(p, 'incompatible', return_value=[]), patch.object(p, 'has_venv', return_value=True), \
             patch.object(prerequisites.ssl, 'get_default_verify_paths', return_value=SimpleNamespace(cafile='/ca')), \
             patch.object(p, 'packages', side_effect=packages) as package_call, \
             patch.object(p, 'managed', side_effect=managed) as managed_call:
            p.required()
            self.assertEqual(package_call.call_count, 1)
            self.assertEqual({call.args[0] for call in managed_call.call_args_list}, {'nvim', 'tree-sitter', 'node'})
            p.required()
            self.assertEqual(package_call.call_count, 1)
            self.assertEqual(managed_call.call_count, 3)

    def test_incompatible_existing_tool_is_not_replaced(self):
        self.args.yes = True
        p = self.instance()
        with patch.object(p, 'incompatible', return_value=['node v18; Node 22+ required']), \
             patch.object(p, 'packages', side_effect=AssertionError('must not install')), \
             patch.object(p, 'managed', side_effect=AssertionError('must not replace')), \
             contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(RuntimeError):
                p.required()

    def test_download_checksum_prevents_installing_corrupt_file(self):
        p = self.instance()
        target = Path(self.temp.name) / 'download'
        with patch.object(prerequisites.urllib.request, 'urlopen', return_value=io.BytesIO(b'wrong')):
            with self.assertRaisesRegex(RuntimeError, 'SHA-256 mismatch'):
                p.download('https://example.invalid/tool', target, hashlib.sha256(b'right').hexdigest())

    def test_link_never_replaces_unrelated_file(self):
        p = self.instance()
        target = Path(self.temp.name) / 'existing'
        target.write_text('keep')
        with self.assertRaises(FileExistsError):
            p.link(target, Path('/some/tool'))
        self.assertEqual(target.read_text(), 'keep')

    def test_managed_recovery_preserves_flags_and_overrides_decline(self):
        self.args.install_prerequisites = False
        p = self.instance()
        with patch.object(prerequisites.sys.stdin, 'isatty', return_value=False), \
             patch.object(p, 'download', side_effect=AssertionError('must not download')), \
             contextlib.redirect_stderr(io.StringIO()) as errors:
            with self.assertRaises(RuntimeError):
                p.managed('nvim')
        self.assertIn('bash /some/path/install.sh --ai off --install-prerequisites', errors.getvalue())

    def test_optional_failure_does_not_stop_installation(self):
        self.args.install_audio = True
        p = self.instance('dnf')
        with patch.object(prerequisites.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'dnf')), \
             contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertFalse(p.packages(['mpv'], kind='audio', optional=True))
        self.assertIn('Continuing without this optional component', errors.getvalue())

    def test_all_pinned_artifacts_have_complete_checksums(self):
        p = self.instance()
        for system in ('Linux', 'Darwin'):
            for arch in ('x86_64', 'arm64'):
                for tool in ('nvim', 'tree-sitter', 'node'):
                    with patch.object(prerequisites.platform, 'system', return_value=system), \
                         patch.object(prerequisites.platform, 'machine', return_value=arch):
                        url, digest, version = p.artifact(tool)
                    self.assertTrue(url.startswith('https://'))
                    self.assertRegex(digest, r'^[0-9a-f]{64}$')
                    self.assertIn(version, url)

    def test_macos_compiler_stub_needs_actual_developer_tools(self):
        p = self.instance('brew')
        with patch.object(prerequisites.platform, 'system', return_value='Darwin'), \
             patch.object(prerequisites.shutil, 'which', return_value='/usr/bin/cc'), \
             patch.object(prerequisites.subprocess, 'check_output', side_effect=subprocess.CalledProcessError(1, 'xcode-select')):
            self.assertFalse(p.has_compiler())
        self.assertEqual(p.package_commands(['cc']), [['xcode-select', '--install']])
