#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/local-common.sh"
mode="$(resolve_shadowgrid_mode "${1:-auto}")"
cd "$shadowgrid_root"

if [[ "$mode" == "compose" ]]; then
  docker compose down
else
  stop_shadowgrid_process web
  stop_shadowgrid_process worker
  stop_shadowgrid_process api
fi
echo "SHADOWGRID $mode services stopped."
