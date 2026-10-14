#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$ROOT/bootstrap.sh"
maya_base_prerequisites local "$@"
exec "$MAYA_NVIM_PYTHON" "$ROOT/scripts/install.py" "$@"
