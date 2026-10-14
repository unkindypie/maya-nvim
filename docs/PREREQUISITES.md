# Prerequisite installation and recovery

Setup detects capabilities in your PATH, including version-manager tools, and
installs only missing prerequisites after displaying a plan and asking `[Y/n]`.
Enter accepts; `n` declines. Existing unsupported versions are not replaced.
Package managers can update transitive dependencies needed for newly installed
packages; setup never runs a system-wide upgrade or adds repositories.

Supported package managers are dnf (Fedora and derivatives), apt-get
(Debian/Ubuntu), pacman (Arch and derivatives), zypper (openSUSE), and existing
Homebrew on macOS. Managed binary downloads support Linux/macOS x86-64 and ARM64.
Ubuntu 24.04+ is recommended; older distro releases may lack Python 3.11 or the
runtime libraries needed by official Neovim binaries. Unsupported systems receive
manual instructions. Homebrew installation is manual: https://brew.sh.

## Manual package commands

These are fallback examples. Install only packages reported missing by setup;
they are not instructions to replace working tools. Omit `sudo` if already root.
Do not run the entire maya-nvim installer with sudo.

| System         | Core packages if missing                                                                                                                       |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Fedora         | `sudo dnf install git python3 curl tar unzip ca-certificates ripgrep gcc gcc-c++ make python3-pip`                                             |
| Debian/Ubuntu  | `sudo apt-get update` then `sudo apt-get install --no-upgrade git python3 curl tar unzip ca-certificates ripgrep build-essential python3-venv` |
| Arch           | `sudo pacman -S --needed git python curl tar unzip ca-certificates ripgrep base-devel`                                                         |
| openSUSE       | `sudo zypper install git python3 curl tar unzip ca-certificates ripgrep gcc gcc-c++ make python3-pip`                                          |
| macOS/Homebrew | `brew install git python@3.13 curl gnu-tar unzip ca-certificates ripgrep`                                                                      |

On Arch, setup never runs `pacman -Sy` or a full system upgrade. If mirrors or
package metadata are stale, follow Arch's normal system maintenance procedure,
then rerun setup. On macOS, missing compiler tools use `xcode-select --install`;
finish Apple's installer, then rerun maya-nvim setup. Homebrew commands disable
automatic update and installed-formula upgrade behavior.

If npm alone is missing, system packages are `npm` on Linux or `node@22` with
Homebrew. Node itself must be 22+. If it is absent, setup downloads verified
Node 22.23.3, including npm, into its private tools directory instead of relying
on potentially older distro versions. For existing incompatible Node versions,
activate a supported version using your current version manager or follow
https://nodejs.org/en/download. No shell-wide Node defaults are changed.

Python must be 3.11+. The shell entry points reuse a compatible `python3.11`,
`python3.12`, `python3.13`, or `python3.14` when `python3` is unsuitable. Install
and activate a supported interpreter manually if necessary:
https://www.python.org/downloads/. A distro venv package must match that selected
interpreter; if it does not, install its matching package as reported by setup.

## Downloaded tools and fonts

Absent Neovim 0.12.5, tree-sitter CLI 0.26.1, and Node 22.23.3 are installed under
`${XDG_DATA_HOME:-~/.local/share}/maya-nvim/tools`. Downloads use pinned official
SHA-256 checksums. Installer subprocesses and `mvim` append this private tools
PATH after your existing PATH. They do not replace system executables or modify
global PATH configuration. No sudo is used for these downloads.

If an existing Neovim or tree-sitter is too old, setup prints the detected and
required versions. Install a supported version manually, activate it in PATH,
then retry:

- Neovim: https://neovim.io/doc/install/
- tree-sitter CLI: https://tree-sitter.github.io/tree-sitter/cli/

Optional audio uses the first available `mpv`, `ffplay`, `pw-play`, or `paplay`.
If none exists and sound is enabled, setup offers mpv (`sudo dnf install mpv`,
`sudo apt-get install mpv`, `sudo pacman -S --needed mpv`,
`sudo zypper install mpv`, or `brew install mpv`). Declining leaves sound silent.

If no Nerd Font is detected, setup offers FantasqueSansMono Nerd Font 3.4.0 from
an official, checksum-verified archive. Its font license stays with the downloaded
fonts. Font files go into `${XDG_DATA_HOME:-~/.local/share}/fonts/maya-nvim` on
Linux or `~/Library/Fonts/maya-nvim` on macOS. Select **FantasqueSansM Nerd Font
Mono** in your terminal settings and reopen the terminal. Detection uses
fontconfig on Linux and the system font inventory on macOS; if detection is
unavailable, setup says so before offering installation.

Ollama stays optional. Its Linux binary download needs zstd
(`sudo dnf install zstd`, `sudo apt-get install zstd`,
`sudo pacman -S --needed zstd`, or `sudo zypper install zstd`) and automatic
service startup needs a working systemd user session. Existing running servers
need neither. On macOS, install/start Ollama separately: https://ollama.com/download/mac.

## Failures and retry

Failed steps print the error, a recovery command, and the installer command to
rerun with your flags. In a terminal, required-dependency failures let you run the
manual command in another terminal and press Enter to recheck, or `q` to exit.
Noninteractive runs exit nonzero instead of waiting. Optional audio/font failures
report recovery steps and continue.

For a permission error, inspect the reported path and its parent with `ls -ld`;
confirm the parent is writable using `test -w /reported/parent`. Correct ownership
or choose a writable installation directory as appropriate. Setup does not
blindly run chown/chmod or recommend sudo for user-local tools/configuration.
For a download failure, check network access and retry; checksum mismatches never
install the unverified file. Bootstrap failures before cloning require rerunning
the original one-command installer; after cloning use its `install.sh`.

`--install-prerequisites` explicitly allows required installations;
`--no-install-prerequisites` reports manual steps. `--yes` accepts installation
plans without questions. Without affirmative flags, noninteractive missing-tool
checks stop and print commands. Optional overrides are `--install-audio`,
`--no-install-audio`, `--install-nerd-font`, and `--no-install-nerd-font`.
`--dry-run` reports actions without mutation; `--skip-bootstrap` remains link-only.

Removing maya-nvim's data directory also removes its private tools. Optional font
files have a separate directory above; remove only that directory if you no
longer want those fonts. System packages remain installed for other applications.
