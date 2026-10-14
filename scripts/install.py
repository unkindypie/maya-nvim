#!/usr/bin/env python3
"""Reversible user-local installation. Never modifies LunarVim or system packages."""
import argparse
import datetime
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BEGIN, END = '# >>> maya-nvim >>>', '# <<< maya-nvim <<<'


def managed(text, body):
    block = BEGIN + '\n' + body + '\n' + END + '\n'
    pattern = re.compile(r'^' + re.escape(BEGIN) + r'\n.*?^' + re.escape(END) + r'\n?', re.M | re.S)
    if pattern.search(text):
        return pattern.sub(lambda _: block, text)
    # The alias must be defined before Maya's exec tmux startup.
    lines = text.splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if line.startswith('if ') and 'tmux' in line), len(lines))
    return ''.join(lines[:start]) + '\n' + block + ''.join(lines[start:])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--yes', '-y', action='store_true', help='use defaults without interactive questions')
    parser.add_argument('--pokemon-sound-on-start', action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument('--reopen-tabs', action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument('--no-shell', action='store_true')
    parser.add_argument('--skip-bootstrap', action='store_true', help='link only, without downloading plugins or language tools')
    parser.add_argument('--tmux-sessionizer', type=Path, metavar='PATH')
    parser.add_argument('--ai', choices=['ollama', 'copilot', 'off'], default='ollama')
    parser.add_argument('--ollama-models-dir', type=Path)
    parser.add_argument('--model', help='Ollama model override; otherwise reuse Qwen 7B or install Qwen 1.5B')
    args = parser.parse_args()
    config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    links = [(config / 'maya-nvim', ROOT), (Path.home() / '.local/bin/mvim', ROOT / 'bin/mvim')]
    # Linux/tmux detects the executable basename, not the shell alias or argv[0].
    nvim = shutil.which('nvim')
    if nvim:
        links.append((Path.home() / '.local/libexec/maya-nvim/mvim', Path(nvim).resolve()))
    personal = config / 'mvim'
    if (personal.exists() or personal.is_symlink()) and not personal.is_dir():
        parser.error(f'Personal config path must be a directory: {personal}')
    edits = []
    if not args.no_shell:
        shell = Path(os.environ.get('ZDOTDIR', Path.home())) / '.zshrc'
        text = shell.read_text() if shell.exists() else ''
        edits.append((shell, managed(text, 'alias mvim=' + shlex.quote(str(links[1][0])))))
    if args.tmux_sessionizer:
        path = args.tmux_sessionizer.expanduser().resolve()
        text = path.read_text()
        marker = '    # >>> maya-nvim directory >>>\n'
        block = marker + "    printf '%s\\n' " + shlex.quote(str(ROOT)) + '\n    # <<< maya-nvim directory <<<\n'
        pattern = re.compile(re.escape(marker) + r'.*?    # <<< maya-nvim directory <<<\n', re.S)
        if pattern.search(text):
            text = pattern.sub(lambda _: block, text)
        else:
            anchor = "    printf '%s\\n' \"$HOME/scripts\" \"$HOME/notes\"\n"
            if anchor not in text:
                parser.error('Unrecognized sessionizer layout; no files changed')
            text = text.replace(anchor, anchor + block, 1)
        edits.append((path, text))
    for target, source in links:
        if (target.exists() or target.is_symlink()) and not (target.is_symlink() and target.resolve() == source):
            parser.error(f'Refusing to replace unrelated path: {target}')
    if not args.skip_bootstrap:
        required = ['nvim', 'git', 'curl', 'tar', 'tree-sitter', 'cc', 'node', 'npm', 'rg']
        missing = [name for name in required if not shutil.which(name)]
        if missing:
            parser.error('Install system prerequisites first: ' + ', '.join(missing))
        version = subprocess.check_output(['nvim', '--version'], text=True).splitlines()[0]
        if not re.search(r'v0\.(?:12|[2-9][0-9])\.', version):
            parser.error('Neovim 0.12+ required; tested on 0.12.5')
        node_version = int(subprocess.check_output(['node', '--version'], text=True).strip().lstrip('v').split('.')[0])
        if node_version < 22:
            parser.error('Node.js 22+ is required')
        ts = subprocess.check_output(['tree-sitter', '--version'], text=True)
        ts_version = tuple(map(int, re.search(r'(\d+)\.(\d+)\.(\d+)', ts).groups()))
        if ts_version < (0, 26, 1):
            parser.error('tree-sitter CLI 0.26.1+ is required')
        if args.ai == 'ollama' and sys.platform.startswith('linux') and not shutil.which('ollama'):
            if not shutil.which('zstd'):
                parser.error('Install zstd before downloading Ollama')
    for target, source in links:
        print(f'Link {target} -> {source}')
    for path, _ in edits:
        print(f'Update managed block: {path}')
    print(f'Create personal config example if missing: {personal / "init.lua"}')
    if args.dry_run:
        print(f'AI: {args.ai}; bootstrap: {not args.skip_bootstrap}; no changes made')
        return
    for target, source in links:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_symlink():
            target.symlink_to(source)
    personal.mkdir(parents=True, exist_ok=True)
    personal_init = personal / 'init.lua'
    if not personal_init.exists() and not personal_init.is_symlink():
        text = (ROOT / 'examples/mvim/init.lua').read_text()
        interactive = sys.stdin.isatty() and not args.yes
        for key, label in [('pokemon_sound_on_start', 'Play a Pokemon cry on startup?'),
                           ('reopen_tabs', 'Reopen saved files and tabs in the same folder?')]:
            value = getattr(args, key)
            if value is None:
                value = ask_boolean(label) if interactive else True
            text = text.replace(f'{key} = true,', f'{key} = {str(value).lower()},')
        personal_init.write_text(text)
    else:
        print(f'Keeping existing preferences: {personal_init}')
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    for path, text in edits:
        if path.exists() and path.read_text() == text:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            shutil.copy2(path, path.with_name(path.name + '.maya-nvim-backup-' + stamp))
        path.write_text(text)
    env = dict(os.environ, NVIM_APPNAME='maya-nvim', MAYA_NVIM_NO_AI='1', MAYA_NVIM_NO_INSTALL='1', MAYA_NVIM_NO_SESSION='1')
    if not args.skip_bootstrap:
        # restore respects the committed lockfile; install fills in missing plugins only.
        subprocess.run(['nvim', '--headless', '+Lazy! restore', '+Lazy! install', '+qa'], env=env, check=True)
        env.pop('MAYA_NVIM_NO_INSTALL')
        subprocess.run(['nvim', '--headless', "+lua dofile(vim.fn.stdpath('config') .. '/scripts/run-bootstrap.lua')"], env=env, check=True)
        if args.ai == 'ollama':
            command = [sys.executable, str(ROOT / 'scripts/setup_ollama.py')]
            if args.ollama_models_dir:
                command += ['--models-dir', str(args.ollama_models_dir.expanduser())]
            if args.model:
                command += ['--model', args.model]
            subprocess.run(command, check=True)
        else:
            import json
            state = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'maya-nvim'
            state.mkdir(parents=True, exist_ok=True)
            (state / 'ai.json').write_text(json.dumps({'provider': args.ai}))
    print('Installed. Open a new zsh or run ~/.local/bin/mvim. LunarVim is unchanged.')


def ask_boolean(question):
    while True:
        try:
            answer = input(question + ' [Y/n] ').strip().lower()
        except EOFError:
            return True
        if answer in ('', 'y', 'yes'):
            return True
        if answer in ('n', 'no'):
            return False
        print('Please answer yes or no.')


if __name__ == '__main__':
    main()
