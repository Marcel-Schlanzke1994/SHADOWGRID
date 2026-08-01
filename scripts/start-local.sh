#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/local-common.sh"
requested_mode="${1:-auto}"
skip_setup="${2:-}"
mode="$(resolve_shadowgrid_mode "$requested_mode")"

if [[ "$skip_setup" != "--skip-setup" ]]; then
  "$shadowgrid_root/scripts/setup-local.sh" "$mode"
fi

cd "$shadowgrid_root"
if [[ "$mode" == "compose" ]]; then
  docker compose up --build -d postgres redis mailpit minio api worker web prometheus
  docker compose exec -T api python -m shadowgrid.predeploy
  docker compose exec -T api python -m shadowgrid.seed
else
  (
    cd "$shadowgrid_root/apps/api"
    start_shadowgrid_process api uvicorn \
      "$shadowgrid_root/.venv/bin/python" -m uvicorn shadowgrid.main:app \
      --host 127.0.0.1 --port 8000
  )
  (
    cd "$shadowgrid_root/apps"
    start_shadowgrid_process worker local_worker \
      "$shadowgrid_root/.venv/bin/python" -m worker.local_worker
  )
  start_shadowgrid_process web "@shadowgrid/web" \
    pnpm --filter @shadowgrid/web dev
fi

"$shadowgrid_root/scripts/verify-local.sh" "$mode"
if [[ "$mode" == "compose" ]]; then
  web_port="$(shadowgrid_env_value FRONTEND_PORT 3000)"
else
  web_port=5173
fi
echo "SHADOWGRID is ready in $mode mode."
echo "Web: http://localhost:$web_port"
echo "API: http://localhost:8000/api/v1"
if [[ "$mode" == "compose" ]]; then
  echo "Mailpit: http://localhost:8025"
  echo "Prometheus: http://localhost:9090"
fi
echo "Demo credentials: .local/demo-credentials.txt (contents intentionally not printed)."
