#!/usr/bin/env bash
# Download this script with bash -c so stdin remains available for installer questions.
set -euo pipefail

for dependency in git python3; do
  if ! command -v "$dependency" >/dev/null 2>&1; then
    echo "Install $dependency before running the maya-nvim bootstrap." >&2
    exit 1
  fi
done

destination=${MAYA_NVIM_INSTALL_DIR:-"$HOME/maya-nvim"}
if [[ -e "$destination" || -L "$destination" ]]; then
  echo "Destination already exists: $destination" >&2
  echo "Use its install.sh to reinstall, or set MAYA_NVIM_INSTALL_DIR to a new directory." >&2
  exit 1
fi

git clone --branch master --single-branch -- https://github.com/unkindypie/maya-nvim.git "$destination"
exec bash "$destination/install.sh" "$@"
