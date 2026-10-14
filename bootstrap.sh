#!/usr/bin/env bash
# Also sourced by install.sh for the minimum Python/Git bootstrap.
set -euo pipefail

maya_base_prerequisites() {
  local mode=$1
  shift
  local automatic=0 disabled=0 dry=0 arg py missing=() packages=() command=() privilege=() metadata=()
  for arg in "$@"; do
    case "$arg" in
      --yes|-y) automatic=1 ;;
      --install-prerequisites) automatic=1; disabled=0 ;;
      --no-install-prerequisites) disabled=1 ;;
      --dry-run|--help|-h) dry=1 ;;
    esac
  done
  # Prefer python3, but reuse a supported versioned interpreter if available.
  export MAYA_NVIM_PYTHON=''
  for py in python3 python3.14 python3.13 python3.12 python3.11; do
    if command -v "$py" >/dev/null 2>&1 && "$py" -c 'import sys; sys.exit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
      MAYA_NVIM_PYTHON=$(command -v "$py")
      break
    fi
  done
  if [[ -z "$MAYA_NVIM_PYTHON" ]]; then
    if command -v python3 >/dev/null 2>&1; then
      echo 'Python exists but is too old or cannot run. Python 3.11+ is required; it will not be replaced.' >&2
      echo 'Install/activate a supported interpreter: https://www.python.org/downloads/' >&2
      echo 'Then rerun the original installation command.' >&2
      return 1
    fi
    missing+=(python3)
  fi
  if [[ "$mode" == clone ]] && ! command -v git >/dev/null 2>&1; then missing+=(git); fi
  if [[ ${#missing[@]} -eq 0 ]]; then return 0; fi
  local system
  system=$(uname -s)
  if [[ "$system" == Darwin ]]; then
    if ! command -v brew >/dev/null 2>&1; then
      echo 'Install Homebrew following https://brew.sh, then rerun the original installation command.' >&2
      printf '%s\n' 'Run manually: /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"' >&2
      return 1
    fi
    for arg in "${missing[@]}"; do
      if [[ "$arg" == python3 ]]; then packages+=(python@3.13); else packages+=("$arg"); fi
    done
    command=(brew install "${packages[@]}")
  elif [[ "$system" == Linux ]]; then
    local ID='' ID_LIKE=''
    if [[ -r /etc/os-release ]]; then source /etc/os-release; fi
    if [[ $(id -u) != 0 ]]; then privilege=(sudo); fi
    case " $ID $ID_LIKE " in
      *fedora*|*rhel*|*centos*) command=("${privilege[@]}" dnf install -y "${missing[@]}") ;;
      *debian*|*ubuntu*)
        metadata=("${privilege[@]}" apt-get update)
        command=("${privilege[@]}" apt-get install --no-upgrade -y "${missing[@]}") ;;
      *arch*|*manjaro*)
        for arg in "${missing[@]}"; do
          if [[ "$arg" == python3 ]]; then packages+=(python); else packages+=("$arg"); fi
        done
        command=("${privilege[@]}" pacman -S --needed --noconfirm "${packages[@]}") ;;
      *suse*) command=("${privilege[@]}" zypper --non-interactive install --no-recommends "${missing[@]}") ;;
      *) echo "Install missing prerequisites manually: ${missing[*]}. Supported: Fedora, Debian/Ubuntu, Arch, openSUSE, macOS/Homebrew." >&2; return 1 ;;
    esac
  else
    echo "Unsupported system $system. Install ${missing[*]} manually and rerun." >&2
    return 1
  fi
  printf 'Missing prerequisites: %s\n' "${missing[*]}"
  if [[ ${#metadata[@]} -gt 0 ]]; then printf 'Proposed command:'; printf ' %q' "${metadata[@]}"; printf '\n'; fi
  printf 'Proposed command:'; printf ' %q' "${command[@]}"; printf '\n'
  if [[ $dry -eq 1 ]]; then return 1; fi
  local answer=''
  if [[ $disabled -eq 0 && $automatic -eq 0 && -t 0 ]]; then
    read -r -p 'Install missing prerequisites? [Y/n] ' answer || answer=n
    case "$answer" in ''|y|Y|yes|YES) automatic=1 ;; esac
  fi
  if [[ $disabled -eq 0 && $automatic -eq 1 ]]; then
    if [[ ${#metadata[@]} -gt 0 ]] && ! "${metadata[@]}"; then
      echo 'Package metadata refresh failed; check network access and permissions.' >&2
    fi
    if ! env HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_UPGRADE=1 HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK=1 "${command[@]}"; then
      echo 'Prerequisite installation failed; check the package-manager error above.' >&2
    fi
  fi
  # Recheck after an attempted install or a manual correction; never assume success.
  while :; do
    for py in python3 python3.14 python3.13 python3.12 python3.11; do
      if command -v "$py" >/dev/null 2>&1 && "$py" -c 'import sys; sys.exit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
        export MAYA_NVIM_PYTHON
        MAYA_NVIM_PYTHON=$(command -v "$py")
        break
      fi
    done
    if [[ -n "$MAYA_NVIM_PYTHON" ]] && { [[ "$mode" != clone ]] || command -v git >/dev/null 2>&1; }; then return 0; fi
    if [[ ${#metadata[@]} -gt 0 ]]; then printf 'Run manually:' >&2; printf ' %q' "${metadata[@]}" >&2; printf '\n' >&2; fi
    printf 'Run manually:' >&2; printf ' %q' "${command[@]}" >&2; printf '\n' >&2
    if [[ "$system" == Darwin ]]; then echo 'After installing Python, activate Homebrew in PATH (brew shellenv) and rerun.' >&2; fi
    echo 'Then rerun the original installation command with the same flags. Do not run the whole installer with sudo.' >&2
    if [[ ! -t 0 || $automatic -eq 1 || $disabled -eq 1 ]]; then return 1; fi
    read -r -p 'Run the command above, then press Enter to recheck; q to exit: ' answer || return 1
    if [[ "$answer" == q ]]; then return 1; fi
  done
}

maya_check_checkout() {
  local destination=$1 origin top
  if [[ ! -d "$destination" || ! -e "$destination/.git" ]]; then
    echo "Refusing unrelated destination: $destination is not a maya-nvim Git checkout." >&2
    return 1
  fi
  top=$(git -C "$destination" rev-parse --show-toplevel) || return 1
  if [[ "$(cd -- "$destination" && pwd -P)" != "$(cd -- "$top" && pwd -P)" ]]; then
    echo "Refusing destination inside another Git checkout: $destination" >&2
    return 1
  fi
  origin=$(git -C "$destination" config --get remote.origin.url) || return 1
  case "$origin" in
    https://github.com/unkindypie/maya-nvim|https://github.com/unkindypie/maya-nvim.git|git@github.com:unkindypie/maya-nvim.git|ssh://git@github.com/unkindypie/maya-nvim.git) ;;
    *) echo "Refusing unrelated origin: $origin" >&2; return 1 ;;
  esac
}

maya_update_repo() {
  local destination=$1 arg dry=0 skip=0 branch changes
  shift
  for arg in "$@"; do
    case "$arg" in
      --dry-run) dry=1 ;;
      --no-update|--help|-h) skip=1 ;;
    esac
  done
  # Local source archives remain installable without Git metadata.
  if [[ ! -e "$destination/.git" ]]; then return 0; fi
  if [[ $skip -eq 1 ]]; then return 0; fi
  if ! command -v git >/dev/null 2>&1; then
    maya_base_prerequisites clone "$@" || return 1
  fi
  maya_check_checkout "$destination" || return 1
  if [[ $dry -eq 1 ]]; then
    printf 'Would update the existing checkout with: git -C %q pull --ff-only --no-rebase --no-autostash origin master\n' "$destination"
    return 0
  fi
  branch=$(git -C "$destination" symbolic-ref --quiet --short HEAD) || branch='detached HEAD'
  changes=$(git -C "$destination" status --porcelain --untracked-files=normal) || return 1
  if [[ "$branch" != master || -n "$changes" ]]; then
    echo "Cannot update $destination: use a clean master checkout (found $branch; local changes are preserved)." >&2
    printf 'Inspect: git -C %q status\n' "$destination" >&2
    echo 'Commit or stash changes yourself and switch to master, then rerun; or use --no-update to install the local version.' >&2
    return 1
  fi
  if ! git -C "$destination" -c pull.rebase=false -c merge.autoStash=false -c rebase.autoStash=false pull --ff-only --no-rebase --no-autostash origin master; then
    echo 'Update failed. Check connectivity, repository permissions, or divergent local commits. No reset, rebase, or automatic stash was performed.' >&2
    printf 'Run manually: git -C %q pull --ff-only --no-rebase --no-autostash origin master\n' "$destination" >&2
    echo 'Then rerun setup, or use --no-update to install the existing local version.' >&2
    return 1
  fi
}

maya_bootstrap() {
  local destination=${MAYA_NVIM_INSTALL_DIR:-"$HOME/maya-nvim"} arg dry=0
  for arg in "$@"; do if [[ "$arg" == --dry-run ]]; then dry=1; fi; done
  if [[ -e "$destination" || -L "$destination" ]]; then
    if [[ ! -d "$destination" || ! -e "$destination/.git" ]]; then
      echo "Refusing unrelated destination: $destination" >&2
      return 1
    fi
    if [[ $dry -eq 1 ]]; then
      printf 'Would validate and update the existing maya-nvim checkout at %s, then run setup.\n' "$destination"
      return 0
    fi
    maya_base_prerequisites clone "$@" || return 1
    maya_check_checkout "$destination" || return 1
    maya_update_repo "$destination" "$@" || return 1
    export MAYA_NVIM_REPO_UPDATED
    MAYA_NVIM_REPO_UPDATED=$(cd -- "$destination" && pwd -P)
    exec bash "$destination/install.sh" "$@"
  fi
  if [[ $dry -eq 1 ]]; then
    maya_base_prerequisites clone "$@" || true
    printf 'Would clone master into %s and run install.sh' "$destination"; printf ' %q' "$@"; printf '\n'
    return 0
  fi
  maya_base_prerequisites clone "$@" || return 1
  if ! git clone --branch master --single-branch -- https://github.com/unkindypie/maya-nvim.git "$destination"; then
    echo "Clone failed. Check network access and ownership/write access to $destination." >&2
    echo 'Rerun the original bootstrap command with the same flags after correcting the error.' >&2
    return 1
  fi
  export MAYA_NVIM_REPO_UPDATED
  MAYA_NVIM_REPO_UPDATED=$(cd -- "$destination" && pwd -P)
  exec bash "$destination/install.sh" "$@"
}

# bash -c has no BASH_SOURCE entry; sourcing this file must not clone anything.
if [[ ${BASH_SOURCE[0]:-} == "$0" || -z ${BASH_SOURCE[0]:-} ]]; then
  maya_bootstrap "$@"
fi
