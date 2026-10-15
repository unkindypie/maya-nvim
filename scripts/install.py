#!/usr/bin/env python3
"""User-local editor installation with confirmed missing-prerequisite setup."""

import argparse
import datetime
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from prerequisites import Prerequisites, add_arguments

BEGIN, END = "# >>> maya-nvim >>>", "# <<< maya-nvim <<<"


def managed(text, body):
    block = BEGIN + "\n" + body + "\n" + END + "\n"
    pattern = re.compile(
        r"^" + re.escape(BEGIN) + r"\n.*?^" + re.escape(END) + r"\n?", re.M | re.S
    )
    if pattern.search(text):
        return pattern.sub(lambda _: block, text)
    # The alias must be defined before Maya's exec tmux startup.
    lines = text.splitlines(keepends=True)
    start = next(
        (
            i
            for i, line in enumerate(lines)
            if line.startswith("if ") and "tmux" in line
        ),
        len(lines),
    )
    return "".join(lines[:start]) + "\n" + block + "".join(lines[start:])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--no-update",
        action="store_true",
        help="install the current local checkout without pulling master",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="use defaults without interactive questions",
    )
    parser.add_argument(
        "--pokemon-sound-on-start", action=argparse.BooleanOptionalAction, default=None
    )
    parser.add_argument(
        "--reopen-tabs", action=argparse.BooleanOptionalAction, default=None
    )
    parser.add_argument("--no-shell", action="store_true")
    parser.add_argument(
        "--skip-bootstrap",
        action="store_true",
        help="link only, without downloading plugins or language tools",
    )
    parser.add_argument("--tmux-sessionizer", type=Path, metavar="PATH")
    parser.add_argument(
        "--ai",
        choices=["ollama", "copilot", "off"],
        help="override the local-AI question",
    )
    parser.add_argument("--ollama-models-dir", type=Path)
    parser.add_argument(
        "--model",
        help="Ollama model override; otherwise reuse Qwen 7B or install Qwen 1.5B",
    )
    add_arguments(parser)
    args = parser.parse_args()
    config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    links = [
        (config / "maya-nvim", ROOT),
        (Path.home() / ".local/bin/mvim", ROOT / "bin/mvim"),
    ]
    personal = config / "mvim"
    personal_init = personal / "init.lua"
    if (personal.exists() or personal.is_symlink()) and not personal.is_dir():
        parser.error(f"Personal config path must be a directory: {personal}")
    edits = []
    if not args.no_shell:
        shell = Path(os.environ.get("ZDOTDIR", Path.home())) / ".zshrc"
        text = shell.read_text() if shell.exists() else ""
        edits.append(
            (shell, managed(text, "alias mvim=" + shlex.quote(str(links[1][0]))))
        )
    if args.tmux_sessionizer:
        path = args.tmux_sessionizer.expanduser().resolve()
        text = path.read_text()
        marker = "    # >>> maya-nvim directory >>>\n"
        block = (
            marker
            + "    printf '%s\\n' "
            + shlex.quote(str(ROOT))
            + "\n    # <<< maya-nvim directory <<<\n"
        )
        pattern = re.compile(
            re.escape(marker) + r".*?    # <<< maya-nvim directory <<<\n", re.S
        )
        if pattern.search(text):
            text = pattern.sub(lambda _: block, text)
        else:
            anchor = '    printf \'%s\\n\' "$HOME/scripts" "$HOME/notes"\n'
            if anchor not in text:
                parser.error("Unrecognized sessionizer layout; no files changed")
            text = text.replace(anchor, anchor + block, 1)
        edits.append((path, text))
    for target, source in links:
        if (target.exists() or target.is_symlink()) and not (
            target.is_symlink() and target.resolve() == source
        ):
            parser.error(f"Refusing to replace unrelated path: {target}")
    prerequisites = Prerequisites(args)
    if not args.skip_bootstrap:
        prerequisites.required()
    nvim = shutil.which("nvim")
    if nvim:
        engine = Path.home() / ".local/libexec/maya-nvim/mvim"
        resolved = Path(nvim).resolve()
        if (engine.exists() or engine.is_symlink()) and not (
            engine.is_symlink() and engine.resolve() == resolved
        ):
            parser.error(f"Refusing to replace unrelated path: {engine}")
        links.append((engine, resolved))
    state = (
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        / "maya-nvim"
    )
    print("💫 maya-nvim setup")
    args.ai = choose_ai(args, state)
    for target, source in links:
        print(f"Link {target} -> {source}")
    for path, _ in edits:
        print(f"Update managed block: {path}")
    print(f"Create personal config example if missing: {personal / 'init.lua'}")
    if args.dry_run:
        if not args.skip_bootstrap:
            prerequisites.optional(sound=sound_enabled(args, personal_init))
            if args.ai == "ollama":
                prerequisites.ollama()
        print(f"AI: {args.ai}; bootstrap: {not args.skip_bootstrap}; no changes made")
        return
    personal_text = None
    if not personal_init.exists() and not personal_init.is_symlink():
        personal_text = (ROOT / "examples/mvim/init.lua").read_text()
        interactive = sys.stdin.isatty() and not args.yes
        for key, label in [
            ("pokemon_sound_on_start", "Play a Pokemon cry on startup?"),
            ("reopen_tabs", "Reopen saved files and tabs in the same folder?"),
        ]:
            value = getattr(args, key)
            if value is None:
                value = ask_boolean(label) if interactive else True
            setattr(args, key, value)
            personal_text = personal_text.replace(
                f"{key} = true,", f"{key} = {str(value).lower()},"
            )
    if not args.skip_bootstrap:
        prerequisites.optional(sound=sound_enabled(args, personal_init))
        if args.ai == "ollama":
            prerequisites.ollama()
    for target, source in links:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_symlink():
            target.symlink_to(source)
    personal.mkdir(parents=True, exist_ok=True)
    if personal_text is not None:
        personal_init.write_text(personal_text)
    else:
        print(f"Keeping existing preferences: {personal_init}")
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    for path, text in edits:
        if path.exists() and path.read_text() == text:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            shutil.copy2(path, path.with_name(path.name + ".maya-nvim-backup-" + stamp))
        path.write_text(text)
    env = dict(
        os.environ,
        NVIM_APPNAME="maya-nvim",
        MAYA_NVIM_NO_AI="1",
        MAYA_NVIM_NO_INSTALL="1",
        MAYA_NVIM_NO_SESSION="1",
    )
    if not args.skip_bootstrap:
        # restore respects the committed lockfile; install fills in missing plugins only.
        subprocess.run(
            ["nvim", "--headless", "+Lazy! restore", "+Lazy! install", "+qa"],
            env=env,
            check=True,
        )
        env.pop("MAYA_NVIM_NO_INSTALL")
        subprocess.run(
            [
                "nvim",
                "--headless",
                "+lua dofile(vim.fn.stdpath('config') .. '/scripts/run-bootstrap.lua')",
            ],
            env=env,
            check=True,
        )
        if args.ai == "ollama":
            command = [sys.executable, str(ROOT / "scripts/setup_ollama.py")]
            if args.yes:
                command += ["--yes"]
            if args.ollama_models_dir:
                command += ["--models-dir", str(args.ollama_models_dir.expanduser())]
            if args.model:
                command += ["--model", args.model]
            subprocess.run(command, check=True)
        else:
            state.mkdir(parents=True, exist_ok=True)
            (state / "ai.json").write_text(json.dumps({"provider": args.ai}))
    print(
        "🌟 Installed. Open a new zsh or run ~/.local/bin/mvim. LunarVim is unchanged."
    )


def sound_enabled(args, personal_init):
    if args.install_audio is True:
        return True
    if args.pokemon_sound_on_start is not None:
        return args.pokemon_sound_on_start
    if personal_init.is_file():
        # Recognize the simple setting we generate without executing a user's Lua.
        match = re.search(
            r"(?:^|[\n,{])\s*pokemon_sound_on_start\s*=\s*(true|false)\b",
            personal_init.read_text(),
        )
        if match:
            return match[1] == "true"
    return True


def choose_ai(args, state):
    if args.ai is not None:
        return args.ai
    try:
        saved = json.loads((state / "ai.json").read_text()).get("provider")
        if saved in ("ollama", "copilot", "off"):
            return saved
    except (OSError, ValueError, AttributeError):
        pass
    if args.skip_bootstrap or args.dry_run:
        return "off"
    if sys.stdin.isatty() and not args.yes:
        print(
            "💫 Local AI can install Ollama, start a user service, and download a missing Qwen model."
        )
        return "ollama" if ask_boolean("Enable local AI with Ollama?") else "off"
    return "ollama" if args.yes else "off"


def ask_boolean(question):
    while True:
        try:
            answer = input("🌠 " + question + " [Y/n] ").strip().lower()
        except EOFError:
            return True
        if answer in ("", "y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please answer yes or no.")


if __name__ == "__main__":
    while True:
        try:
            main()
            break
        except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
            print(f"Installation stopped: {error}", file=sys.stderr)
            if isinstance(error, PermissionError):
                print(
                    "Check ownership and write access to the reported path; do not run the whole installer with sudo.",
                    file=sys.stderr,
                )
                if error.filename:
                    print(
                        "Inspect: "
                        + shlex.join(
                            [
                                "ls",
                                "-ld",
                                str(Path(error.filename).parent),
                                error.filename,
                            ]
                        ),
                        file=sys.stderr,
                    )
                    print(
                        "Check write access: "
                        + shlex.join(["test", "-w", str(Path(error.filename).parent)]),
                        file=sys.stderr,
                    )
            print(
                "Rerun: "
                + shlex.join(["bash", str(ROOT / "install.sh"), *sys.argv[1:]]),
                file=sys.stderr,
            )
            # Prerequisite RuntimeErrors already handled their own retry/exit prompt.
            if (
                not isinstance(error, RuntimeError)
                and sys.stdin.isatty()
                and not any(arg in sys.argv for arg in ("--yes", "-y"))
            ):
                try:
                    if (
                        input(
                            "🌠 Correct the error above, then press Enter to retry; q to exit: "
                        ).strip()
                        == ""
                    ):
                        continue
                except EOFError:
                    pass
            sys.exit(1)
