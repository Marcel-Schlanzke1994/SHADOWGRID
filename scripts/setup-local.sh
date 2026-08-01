#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/local-common.sh"
mode="$(resolve_shadowgrid_mode "${1:-auto}")"

for command_name in python3 node pnpm; do
  command -v "$command_name" >/dev/null 2>&1 || {
    echo "Missing required command: $command_name" >&2
    exit 1
  }
done

cd "$shadowgrid_root"
if [[ ! -x "$shadowgrid_root/.venv/bin/python" ]]; then
  python3 -m venv "$shadowgrid_root/.venv"
fi
"$shadowgrid_root/.venv/bin/python" -m pip install --disable-pip-version-check \
  -r "$shadowgrid_root/apps/api/requirements-dev.txt"
pnpm install --frozen-lockfile
"$shadowgrid_root/.venv/bin/python" "$shadowgrid_root/scripts/generate-local-secrets.py"
pnpm migrate
pnpm seed
if [[ "$mode" == "compose" ]]; then
  docker compose build api worker web
fi

echo "SHADOWGRID local setup completed in $mode mode."
echo "Local credentials remain in .local/demo-credentials.txt and are not printed."
