#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/local-common.sh"
mode="$(resolve_shadowgrid_mode "${1:-auto}")"
cd "$shadowgrid_root"

if [[ "$mode" == "compose" ]]; then
  running_services="$(docker compose ps --status running --services)"
  for service in postgres redis api worker web; do
    grep -qx "$service" <<<"$running_services" || {
      echo "Required Compose service '$service' is not running." >&2
      exit 1
    }
  done
else
  for name in api worker web; do
    pid_file="$shadowgrid_run_root/$name.pid"
    [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null || {
      echo "Required SQLite-mode process '$name' is not running." >&2
      exit 1
    }
  done
fi

command -v curl >/dev/null 2>&1 || {
  echo "curl is required for local verification." >&2
  exit 1
}
wait_shadowgrid_http "http://127.0.0.1:8000/api/v1/health"
wait_shadowgrid_http "http://127.0.0.1:8000/api/v1/ready"
if [[ "$mode" == "compose" ]]; then
  web_port="$(shadowgrid_env_value FRONTEND_PORT 3000)"
else
  web_port=5173
fi
wait_shadowgrid_http "http://127.0.0.1:$web_port/healthz"
pnpm data:verify
echo "SHADOWGRID $mode health, readiness, worker and data checks passed."
