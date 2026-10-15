#!/usr/bin/env python3
"""Install absent editor prerequisites; never replace incompatible existing tools."""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import ssl
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MINIMUM = {"nvim": (0, 12, 0), "tree-sitter": (0, 26, 1), "node": (22, 0, 0)}
GUIDES = {
    "nvim": "https://neovim.io/doc/install/",
    "tree-sitter": "https://tree-sitter.github.io/tree-sitter/cli/installation.html",
    "node": "https://nodejs.org/en/download",
    "python3": "https://www.python.org/downloads/",
}
PACKAGES = {
    "apt-get": {
        "git": "git",
        "curl": "curl",
        "tar": "tar",
        "unzip": "unzip",
        "rg": "ripgrep",
        "cc": "build-essential",
        "node": "nodejs",
        "npm": "npm",
        "venv": "python3-venv",
        "zstd": "zstd",
        "mpv": "mpv",
    },
    "dnf": {
        "git": "git",
        "curl": "curl",
        "tar": "tar",
        "unzip": "unzip",
        "rg": "ripgrep",
        "cc": "gcc gcc-c++ make",
        "node": "nodejs",
        "npm": "npm",
        "venv": "python3-pip",
        "zstd": "zstd",
        "mpv": "mpv",
    },
    "pacman": {
        "git": "git",
        "curl": "curl",
        "tar": "tar",
        "unzip": "unzip",
        "rg": "ripgrep",
        "cc": "base-devel",
        "node": "nodejs",
        "npm": "npm",
        "venv": "python",
        "zstd": "zstd",
        "mpv": "mpv",
    },
    "zypper": {
        "git": "git",
        "curl": "curl",
        "tar": "tar",
        "unzip": "unzip",
        "rg": "ripgrep",
        "cc": "gcc gcc-c++ make",
        "node": "nodejs",
        "npm": "npm",
        "venv": "python3-pip",
        "zstd": "zstd",
        "mpv": "mpv",
    },
    "brew": {
        "git": "git",
        "curl": "curl",
        "tar": "gnu-tar",
        "unzip": "unzip",
        "rg": "ripgrep",
        "node": "node@22",
        "npm": "node@22",
        "venv": "python@3.13",
        "zstd": "zstd",
        "mpv": "mpv",
    },
}
# Immutable upstream release SHA-256 digests, not an unverified latest download.
ASSETS = {
    ("node", "Linux", "x86_64"): (
        "node-v22.23.3-linux-x64.tar.gz",
        "1084aa36196bba4c3a5e69a1ee388a6e4ff729dad09445fbcd434b28fe3c24af",
    ),
    ("node", "Linux", "arm64"): (
        "node-v22.23.3-linux-arm64.tar.gz",
        "5ced2d48d1d7198739b7f86804de0171aefb6823b684b12341d3321afc3cb0b2",
    ),
    ("node", "Darwin", "x86_64"): (
        "node-v22.23.3-darwin-x64.tar.gz",
        "8a677b0219178efd6eb0e475457c4afb452b521a92f6e67845a73bd85727f2a8",
    ),
    ("node", "Darwin", "arm64"): (
        "node-v22.23.3-darwin-arm64.tar.gz",
        "23b25245dcfb9af7262f8ff142e9e2e0af025368117329e7a7458a51e5922f53",
    ),
    ("nvim", "Linux", "x86_64"): (
        "nvim-linux-x86_64.tar.gz",
        "bce0f56eda1f1b1db6eee8f4133d7a38813ea07933837dd1777411ca384c6875",
    ),
    ("nvim", "Linux", "arm64"): (
        "nvim-linux-arm64.tar.gz",
        "1aa5ca085249580ae0f91eb14f27ec0919773ff2d99a163d03f3d6c21ac29725",
    ),
    ("nvim", "Darwin", "x86_64"): (
        "nvim-macos-x86_64.tar.gz",
        "81f4518622cb059b450ee2e498c6a1082a222f6bd89589de5bbcf0c6a68aa3fd",
    ),
    ("nvim", "Darwin", "arm64"): (
        "nvim-macos-arm64.tar.gz",
        "65fb000099e47ca1b762584c484cc833f40e30851a0ec450d4174e16317c1f9b",
    ),
    ("tree-sitter", "Linux", "x86_64"): (
        "tree-sitter-linux-x64.gz",
        "d74182fffbf441f247371ad6af77d99b10ac9f788d7e068e4b44992d9d6d7c26",
    ),
    ("tree-sitter", "Linux", "arm64"): (
        "tree-sitter-linux-arm64.gz",
        "98a710e8ab9d502c50b02acd32d553c5fb5d00285cd458e5907af8a580c5a4ea",
    ),
    ("tree-sitter", "Darwin", "x86_64"): (
        "tree-sitter-macos-x64.gz",
        "2162760bd371b4157b26b363550d5dacbfefc359fa85e6e9ac4b31e9e717add8",
    ),
    ("tree-sitter", "Darwin", "arm64"): (
        "tree-sitter-macos-arm64.gz",
        "823254eac2a9d006ed03a74181265249cdaf597b17bd808adc63610c447bb0bf",
    ),
}
for _mapping in PACKAGES.values():
    _mapping["certificates"] = "ca-certificates"


def add_arguments(parser):
    for name in ("prerequisites", "audio", "nerd-font"):
        parser.add_argument(
            "--install-" + name,
            action=argparse.BooleanOptionalAction,
            default=None,
            help="install missing " + name + " (otherwise ask in a terminal)",
        )


def ask(question):
    while True:
        try:
            answer = input("🌠 " + question + " [Y/n] ").strip().lower()
        except EOFError:
            return False
        if answer in ("", "y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("🔔 Please answer yes or no.")


def manager(system=None, os_release=None):
    system = system or platform.system()
    if system == "Darwin":
        return "brew" if shutil.which("brew") else None
    if system != "Linux":
        return None
    if os_release is None:
        try:
            os_release = platform.freedesktop_os_release()
        except OSError:
            os_release = {}
    ids = {os_release.get("ID", ""), *os_release.get("ID_LIKE", "").split()}
    for families, command in (
        ({"fedora", "rhel", "centos"}, "dnf"),
        ({"debian", "ubuntu"}, "apt-get"),
        ({"arch", "manjaro"}, "pacman"),
        ({"opensuse", "opensuse-leap", "opensuse-tumbleweed", "suse"}, "zypper"),
    ):
        if ids & families and shutil.which(command):
            return command
    return None


def tools_root():
    return (
        Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
        / "maya-nvim/tools"
    )


def certificate_file():
    candidates = [
        os.environ.get("SSL_CERT_FILE"),
        ssl.get_default_verify_paths().cafile,
        "/etc/ssl/cert.pem",
        "/etc/ssl/certs/ca-certificates.crt",
        "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",
    ]
    return next(
        (str(path) for path in candidates if path and Path(path).is_file()), None
    )


class Prerequisites:
    def __init__(self, args, retry=None):
        self.args = args
        self.backend = manager()
        self.root = tools_root()
        self.retry = retry or shlex.join(
            ["bash", str(ROOT / "install.sh"), *sys.argv[1:]]
        )
        self.env = dict(
            os.environ,
            HOMEBREW_NO_AUTO_UPDATE="1",
            HOMEBREW_NO_INSTALL_UPGRADE="1",
            HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK="1",
        )
        self.activate()

    def activate(self):
        # Respect the user's PATH first; managed binaries fill absent capabilities.
        parts = os.environ.get("PATH", "").split(os.pathsep)
        for path in (self.root / "bin", self.root / "brew-node/bin"):
            if str(path) not in parts:
                parts.append(str(path))
        os.environ["PATH"] = os.pathsep.join(parts)
        if hasattr(self, "env"):
            self.env["PATH"] = os.environ["PATH"]

    def permitted(self, kind, label):
        if self.args.dry_run:
            return False
        flag = getattr(self.args, "install_" + kind, None)
        if flag is not None:
            return flag
        if self.args.yes:
            return True
        return ask(label) if sys.stdin.isatty() else False

    def recovery(self, label, error, commands, optional=False):
        print(f"\n🔔 {label}: {error}", file=sys.stderr)
        for command in commands:
            print(
                "🔔 Run: "
                + (shlex.join(command) if isinstance(command, list) else command),
                file=sys.stderr,
            )
        print("🔔 Then rerun: " + self.retry, file=sys.stderr)
        if isinstance(error, PermissionError):
            print(
                "🔔 Check ownership and write access to the path above. Do not run the whole installer with sudo.",
                file=sys.stderr,
            )
            if error.filename:
                parent = str(Path(error.filename).parent)
                print(
                    "🔔 Inspect: " + shlex.join(["ls", "-ld", parent, error.filename]),
                    file=sys.stderr,
                )
                print(
                    "🔔 Check write access: " + shlex.join(["test", "-w", parent]),
                    file=sys.stderr,
                )
        if optional:
            print("Continuing without this optional component.", file=sys.stderr)
            return False
        if sys.stdin.isatty() and not self.args.yes:
            try:
                answer = input(
                    "🌠 Run the command above, then press Enter to recheck; q to exit: "
                )
                if answer.strip().lower() != "q":
                    return True
            except EOFError:
                pass
        raise RuntimeError(
            f"{label} is not ready; follow the recovery instructions above."
        )

    def package_commands(self, names):
        if not self.backend:
            raise RuntimeError(
                "No supported package manager. Install Homebrew on macOS (https://brew.sh), or install the listed tools manually on this system."
            )
        if self.backend == "brew" and "cc" in names:
            return [["xcode-select", "--install"]]
        packages = []
        for name in names:
            for package in PACKAGES[self.backend][name].split():
                if package not in packages:
                    packages.append(package)
        prefix = [] if self.backend == "brew" or os.geteuid() == 0 else ["sudo"]
        if self.backend == "apt-get":
            return [
                prefix + ["apt-get", "update"],
                prefix + ["apt-get", "install", "--no-upgrade", "-y", *packages],
            ]
        if self.backend == "pacman":
            return [prefix + ["pacman", "-S", "--needed", "--noconfirm", *packages]]
        if self.backend == "dnf":
            return [prefix + ["dnf", "install", "-y", *packages]]
        if self.backend == "zypper":
            return [
                prefix
                + [
                    "zypper",
                    "--non-interactive",
                    "install",
                    "--no-recommends",
                    *packages,
                ]
            ]
        return [["brew", "install", *packages]]

    def packages(self, names, kind="prerequisites", optional=False):
        if not names:
            return True
        print("💫 Missing " + kind + ": " + ", ".join(names))
        try:
            commands = self.package_commands(names)
        except RuntimeError as error:
            return (
                self.recovery(
                    "Missing " + kind,
                    error,
                    [
                        "Install: " + ", ".join(names),
                        "See " + str(ROOT / "docs/PREREQUISITES.md"),
                    ],
                    optional,
                )
                if not self.args.dry_run
                else False
            )
        for command in commands:
            print("🌟 Proposed command: " + shlex.join(command))
        if self.args.dry_run:
            return False
        if not self.permitted(kind, "Install missing " + kind + "?"):
            return self.recovery(
                "Missing " + kind,
                "Installation declined or not enabled.",
                commands,
                optional,
            )
        try:
            for command in commands:
                subprocess.run(command, env=self.env, check=True)
            if self.backend == "brew" and ("node" in names or "npm" in names):
                prefix = subprocess.check_output(
                    ["brew", "--prefix", "node@22"], env=self.env, text=True
                ).strip()
                self.link(self.root / "brew-node", Path(prefix))
                self.activate()
            if self.backend == "brew" and "cc" in names:
                return self.recovery(
                    "C compiler",
                    "Finish Apple Command Line Tools installation.",
                    commands,
                    optional,
                )
            return True
        except (OSError, subprocess.CalledProcessError) as error:
            if self.backend == "pacman" and isinstance(
                error, subprocess.CalledProcessError
            ):
                print(
                    "🔔 If the error reports stale mirrors/packages, review and run sudo pacman -Syu manually before retrying. Setup never performs that system upgrade.",
                    file=sys.stderr,
                )
            return self.recovery("Installing " + kind, error, commands, optional)

    @staticmethod
    def link(target, source):
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink() and target.resolve() == source.resolve():
            return
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"Refusing to replace unrelated path: {target}")
        target.symlink_to(source)

    def artifact(self, tool):
        arch = {
            "aarch64": "arm64",
            "arm64": "arm64",
            "x86_64": "x86_64",
            "AMD64": "x86_64",
        }.get(platform.machine())
        asset = ASSETS.get((tool, platform.system(), arch))
        if not asset:
            raise RuntimeError(
                f"No managed {tool} download for {platform.system()} {platform.machine()}; install manually: {GUIDES[tool]}"
            )
        repo, version = (
            ("neovim/neovim", "0.12.5")
            if tool == "nvim"
            else ("tree-sitter/tree-sitter", "0.26.1")
        )
        name, digest = asset
        if tool == "node":
            return f"https://nodejs.org/dist/v22.23.3/{name}", digest, "22.23.3"
        return (
            f"https://github.com/{repo}/releases/download/v{version}/{name}",
            digest,
            version,
        )

    @staticmethod
    def download(url, target, digest):
        request = urllib.request.Request(
            url, headers={"User-Agent": "maya-nvim-installer"}
        )
        context = ssl.create_default_context(cafile=certificate_file())
        with (
            urllib.request.urlopen(request, timeout=60, context=context) as response,
            target.open("wb") as output,
        ):
            shutil.copyfileobj(response, output)
        with target.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != digest:
            raise RuntimeError(
                f"SHA-256 mismatch for {url}; no downloaded files were installed."
            )

    @staticmethod
    def extract_tar(tar, destination):
        if hasattr(tarfile, "data_filter"):
            tar.extractall(destination, filter="data")
            return
        # Compatibility with Python 3.11 before extraction filters were backported.
        for member in tar.getmembers():
            target = (destination / member.name).resolve()
            if not target.is_relative_to(destination.resolve()) or member.isdev():
                raise RuntimeError("Unsafe archive member: " + member.name)
            if member.issym() or member.islnk():
                link = (
                    target.parent if member.issym() else destination
                ) / member.linkname
                if not link.resolve().is_relative_to(destination.resolve()):
                    raise RuntimeError("Unsafe archive link: " + member.name)
        tar.extractall(destination)

    def managed(self, tool):
        try:
            url, digest, version = self.artifact(tool)
        except RuntimeError as error:
            if self.args.dry_run:
                print(f"🔔 {error}")
                return
            self.recovery(tool, error, [GUIDES[tool]])
            return
        destination = self.root / f"{tool}-{version}"
        print(f"💫 Missing {tool}: verified download {url} -> {destination}")
        if self.args.dry_run:
            return
        recipe = self.retry + " --install-prerequisites"
        if not self.permitted(
            "prerequisites", f"Install missing {tool} into your user tools directory?"
        ):
            self.recovery(
                tool, "Installation declined or not enabled.", [recipe, GUIDES[tool]]
            )
            return
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(
                dir=self.root, prefix=tool + "-"
            ) as temporary:
                temp = Path(temporary)
                archive = temp / "download"
                self.download(url, archive, digest)
                unpacked = temp / "unpacked"
                unpacked.mkdir()
                if tool in ("nvim", "node"):
                    with tarfile.open(archive, "r:gz") as tar:
                        self.extract_tar(tar, unpacked)
                    binary = next(unpacked.glob("*/bin/" + tool))
                    install = binary.parent.parent
                    relative = Path("bin") / tool
                else:
                    binary = unpacked / "tree-sitter"
                    with (
                        gzip.open(archive, "rb") as stream,
                        binary.open("wb") as output,
                    ):
                        shutil.copyfileobj(stream, output)
                    binary.chmod(0o755)
                    install = unpacked
                    relative = Path("tree-sitter")
                # A successful existing managed directory may survive an interrupted link step.
                if not destination.exists():
                    install.rename(destination)
                elif not (destination / relative).is_file():
                    raise FileExistsError(
                        f"Incomplete or unrelated managed directory: {destination}; inspect it before retrying."
                    )
                self.link(self.root / "bin" / tool, destination / relative)
                if tool == "node":
                    for name in ("npm", "npx"):
                        self.link(self.root / "bin" / name, destination / "bin" / name)
        except (OSError, RuntimeError, StopIteration, tarfile.TarError) as error:
            self.recovery(tool, error, [recipe, GUIDES[tool]])

    def incompatible(self):
        problems = []
        if sys.version_info < (3, 11):
            problems.append(
                "Python 3.11+ required; running "
                + platform.python_version()
                + ". "
                + GUIDES["python3"]
            )
        for tool, minimum in MINIMUM.items():
            if not shutil.which(tool):
                continue
            try:
                output = subprocess.check_output(
                    [tool, "--version"], text=True, stderr=subprocess.STDOUT
                )
                match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", output)
                version = (
                    tuple(int(part or 0) for part in match.groups()) if match else ()
                )
                if version < minimum:
                    problems.append(
                        f"{tool}: found {output.splitlines()[0]}; requires {'.'.join(map(str, minimum))}+. {GUIDES[tool]}"
                    )
            except (OSError, subprocess.CalledProcessError) as error:
                problems.append(
                    f"{tool}: cannot run existing tool ({error}). {GUIDES[tool]}"
                )
        return problems

    @staticmethod
    def has_venv():
        return (
            subprocess.run(
                [sys.executable, "-c", "import venv, ensurepip"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode
            == 0
        )

    @staticmethod
    def has_compiler():
        if not shutil.which("cc"):
            return False
        if platform.system() == "Darwin":
            # Apple's cc stub can exist before the actual developer tools do.
            try:
                subprocess.check_output(
                    ["xcode-select", "-p"], stderr=subprocess.DEVNULL
                )
            except (OSError, subprocess.CalledProcessError):
                return False
        return True

    def required(self):
        while True:
            problems = self.incompatible()
            if problems:
                print("🔔 " + "\n🔔 ".join(problems), file=sys.stderr)
                commands = [
                    [
                        sys.executable,
                        str(ROOT / "scripts/prerequisites.py"),
                        "--tool",
                        tool,
                        "--yes",
                    ]
                    for tool in MINIMUM
                    if any(problem.startswith(tool) for problem in problems)
                ]
                commands += [
                    "export PATH=" + shlex.quote(str(self.root / "bin")) + ':"$PATH"'
                ]
                if not self.args.dry_run and self.recovery(
                    "Incompatible prerequisites",
                    "Existing tools are preserved. The commands below install an isolated supported copy and let you explicitly activate it.",
                    commands,
                ):
                    continue
            missing = [
                name
                for name in ("git", "curl", "tar", "unzip", "rg")
                if not shutil.which(name)
            ]
            if not self.has_compiler():
                missing.append("cc")
            if shutil.which("node") and not shutil.which("npm"):
                missing.append("npm")
            if certificate_file() is None:
                missing.append("certificates")
            if not self.has_venv():
                missing.append("venv")
            managed = [
                name
                for name in ("nvim", "tree-sitter", "node")
                if not shutil.which(name)
            ]
            if not missing and not managed:
                return
            if missing:
                self.packages(missing)
            for tool in managed:
                if not shutil.which(tool):
                    self.managed(tool)
            if self.args.dry_run:
                return
            self.activate()
            still_missing = [
                name
                for name in missing
                if name not in ("venv", "certificates") and not shutil.which(name)
            ]
            if (
                "cc" in missing
                and not self.has_compiler()
                and "cc" not in still_missing
            ):
                still_missing.append("cc")
            if "certificates" in missing and certificate_file() is None:
                still_missing.append("certificates")
            if "venv" in missing and not self.has_venv():
                still_missing.append("venv")
            still_missing.extend(name for name in managed if not shutil.which(name))
            if still_missing:
                self.recovery(
                    "Missing prerequisites",
                    ", ".join(still_missing),
                    self.package_commands(
                        [
                            n
                            for n in still_missing
                            if n not in ("nvim", "tree-sitter", "node")
                        ]
                    )
                    if any(
                        n not in ("nvim", "tree-sitter", "node") for n in still_missing
                    )
                    else [self.retry],
                )

    def font_present(self):
        managed_font = (
            Path.home() / "Library/Fonts"
            if platform.system() == "Darwin"
            else Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
            / "fonts"
        ) / "maya-nvim"
        if any(managed_font.glob("*.ttf")) or any(managed_font.glob("*.otf")):
            return True
        if shutil.which("fc-list"):
            output = subprocess.check_output(["fc-list", ":", "family"], text=True)
            return bool(re.search(r"nerd|\bNF\b", output, re.I))
        if platform.system() == "Darwin":
            output = subprocess.check_output(
                ["system_profiler", "SPFontsDataType", "-json"], text=True
            )
            return bool(re.search(r"Nerd|NerdFont", output, re.I))
        return None

    def font(self):
        try:
            present = self.font_present()
        except (OSError, subprocess.CalledProcessError):
            present = None
        if present:
            return
        if present is None:
            print(
                "Font detection is unavailable; a Nerd Font may already be installed."
            )
        print(
            "🌺 Optional FantasqueSansMono Nerd Font 3.4.0 (user-local; terminal selection is manual)."
        )
        if not self.permitted("nerd_font", "Install FantasqueSansMono Nerd Font?"):
            return
        if self.args.dry_run:
            return
        # FONT_SHA256 is pinned from the upstream v3.4.0 SHA-256.txt manifest.
        url = "https://github.com/ryanoasis/nerd-fonts/releases/download/v3.4.0/FantasqueSansMono.zip"
        destination = (
            Path.home() / "Library/Fonts"
            if platform.system() == "Darwin"
            else Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
            / "fonts"
        ) / "maya-nvim"
        try:
            with tempfile.TemporaryDirectory(prefix="maya-font-") as temporary:
                archive = Path(temporary) / "font.zip"
                self.download(url, archive, FONT_SHA256)
                destination.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(archive) as zipped:
                    for entry in zipped.infolist():
                        filename = Path(entry.filename).name
                        if filename.lower().endswith((".ttf", ".otf", ".txt", ".md")):
                            target = destination / filename
                            if not target.exists():
                                target.write_bytes(zipped.read(entry))
                if shutil.which("fc-cache"):
                    subprocess.run(["fc-cache", "-f", str(destination)], check=True)
            print(
                "🔔 Select FantasqueSansM Nerd Font Mono in your terminal settings, then reopen the terminal."
            )
        except (
            OSError,
            RuntimeError,
            zipfile.BadZipFile,
            subprocess.CalledProcessError,
        ) as error:
            self.recovery(
                "Optional Nerd Font",
                error,
                [
                    [
                        sys.executable,
                        str(ROOT / "scripts/prerequisites.py"),
                        "--tool",
                        "font",
                        "--yes",
                    ],
                    "https://www.nerdfonts.com/font-downloads",
                ],
                optional=True,
            )

    def optional(self, sound=True):
        if sound and not any(
            shutil.which(name) for name in ("mpv", "ffplay", "pw-play", "paplay")
        ):
            self.packages(["mpv"], kind="audio", optional=True)
        self.font()

    def ollama(self):
        # A running server needs neither a new binary nor zstd/systemd.
        while True:
            try:
                with urllib.request.urlopen(
                    "http://127.0.0.1:11434/api/tags", timeout=2
                ) as response:
                    json.load(response)
                return
            except (OSError, ValueError):
                pass
            if platform.system() == "Darwin":
                if self.args.dry_run:
                    print(
                        "🔔 Ollama: install/start separately on macOS: https://ollama.com/download/mac; ollama serve"
                    )
                    return
                if self.recovery(
                    "Local AI",
                    "macOS requires a running Ollama server.",
                    ["https://ollama.com/download/mac", ["ollama", "serve"]],
                ):
                    continue
            if platform.system() == "Linux":
                if not shutil.which("systemctl"):
                    if self.args.dry_run:
                        print(
                            "🔔 Ollama: start a server manually; no systemd user service is available."
                        )
                        return
                    if self.recovery(
                        "Local AI",
                        "No systemd user service manager; install/start Ollama separately or rerun with --ai off.",
                        ["https://ollama.com/download/linux", ["ollama", "serve"]],
                    ):
                        continue
                if (
                    not shutil.which("ollama")
                    and not (Path.home() / ".local/bin/ollama").exists()
                    and not shutil.which("zstd")
                ):
                    self.packages(["zstd"])
                    if not self.args.dry_run and not shutil.which("zstd"):
                        continue
                return
            if self.args.dry_run:
                return
            self.recovery(
                "Local AI",
                "Automatic Ollama setup is unsupported on this platform.",
                ["https://ollama.com/download"],
            )


FONT_SHA256 = "29c6fe2420a61fff58a78c689e27d8b984ccef2990d6ed9c1a7f3661136acd41"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_arguments(parser)
    parser.add_argument("--yes", "-y", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--tool",
        choices=["nvim", "tree-sitter", "node", "font"],
        help="explicitly install an isolated copy for manual recovery",
    )
    args = parser.parse_args()
    p = Prerequisites(
        args,
        retry=shlex.join(
            [sys.executable, str(ROOT / "scripts/prerequisites.py"), *sys.argv[1:]]
        ),
    )
    if args.tool == "font":
        p.font()
    elif args.tool:
        p.managed(args.tool)
        print(
            "🔔 To explicitly select this copy: export PATH="
            + shlex.quote(str(p.root / "bin"))
            + ':"$PATH"'
        )
    else:
        p.required()


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError) as error:
        print(f"🔔 {error}", file=sys.stderr)
        sys.exit(1)
