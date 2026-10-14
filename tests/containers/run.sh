#!/usr/bin/env bash
# Real installations happen only inside disposable containers, never on the host.
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
if [[ $# -eq 0 ]]; then set -- fedora:latest ubuntu:24.04; fi
for image in "$@"; do
  docker run --rm -v "$repo:/src:ro" "$image" bash -c '
    source /src/bootstrap.sh
    maya_base_prerequisites clone --yes
    "$MAYA_NVIM_PYTHON" /src/tests/containers/prerequisites.py
    mkdir /work
    tar -C /src --exclude=.git --exclude=.local -cf - . | tar -C /work -xf -
    bash /work/install.sh --yes --ai off --no-shell --no-install-audio --no-install-nerd-font
    MAYA_NVIM_NO_AI=1 MAYA_NVIM_NO_INSTALL=1 MAYA_NVIM_NO_SESSION=1 \
      "$HOME/.local/bin/mvim" --headless "+lua assert(vim.g.mapleader == \" \")" +qa
  '
done
