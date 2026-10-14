"""Real package/download smoke test; run only in a disposable Linux container."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, '/src/scripts')
from prerequisites import Prerequisites

args = argparse.Namespace(yes=True, dry_run=False, install_prerequisites=True,
                          install_audio=False, install_nerd_font=False)
p = Prerequisites(args, retry='bash /src/install.sh --yes --ai off')
p.required()
for tool in ('nvim', 'tree-sitter', 'node', 'npm', 'git', 'curl', 'cc', 'rg', 'unzip'):
    subprocess.run([tool, '-v' if tool == 'unzip' else '--version'], check=True, stdout=subprocess.DEVNULL)
assert not p.incompatible()
assert p.has_venv()

# Once installed, the same run must not install or download anything again.
p.packages = lambda *a, **k: (_ for _ in ()).throw(AssertionError('unexpected package reinstall'))
p.managed = lambda *a, **k: (_ for _ in ()).throw(AssertionError('unexpected managed reinstall'))
p.required()
p.optional(sound=False)
print('PASS real prerequisite installation, version checks, and idempotent rerun', flush=True)
