#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/local-common.sh"
requested_mode="${1:-auto}"
confirmation="${2:-}"
start_after="${3:-}"
if [[ "$confirmation" != "RESET" ]]; then
  echo "Refusing reset. Pass the exact confirmation token RESET." >&2
  exit 1
fi
mode="$(resolve_shadowgrid_mode "$requested_mode")"
"$shadowgrid_root/scripts/stop-local.sh" "$mode"

cd "$shadowgrid_root"
if [[ "$mode" == "compose" ]]; then
  docker compose down --volumes --remove-orphans
else
  database_path="$shadowgrid_root/.local/shadowgrid.db"
  case "$database_path" in
    "$shadowgrid_root/.local/"*) rm -f -- "$database_path" ;;
    *)
      echo "Resolved SQLite path escaped .local." >&2
      exit 1
      ;;
  esac
fi

"$shadowgrid_root/scripts/setup-local.sh" "$mode"
if [[ "$start_after" == "--start" ]]; then
  "$shadowgrid_root/scripts/start-local.sh" "$mode" --skip-setup
fi
echo "SHADOWGRID $mode local state reset and reseeded."
