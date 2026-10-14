#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
source "$ROOT/bootstrap.sh"
maya_base_prerequisites local "$@"
if [[ ${MAYA_NVIM_REPO_UPDATED:-} != "$ROOT" ]]; then
  maya_update_repo "$ROOT" "$@"
  export MAYA_NVIM_REPO_UPDATED="$ROOT"
  # Reload the installer from the newly pulled revision.
  exec bash "$ROOT/install.sh" "$@"
fi
exec "$MAYA_NVIM_PYTHON" "$ROOT/scripts/install.py" "$@"
