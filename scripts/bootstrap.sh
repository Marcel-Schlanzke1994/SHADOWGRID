#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
venv_python="$project_root/.venv/bin/python"

cd "$project_root"

for command_name in python3 node pnpm; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command: $command_name" >&2
    exit 1
  fi
done

if [[ ! -x "$venv_python" ]]; then
  python3 -m venv "$project_root/.venv"
fi

"$venv_python" -m pip install --disable-pip-version-check \
  -r "$project_root/apps/api/requirements-dev.txt"
pnpm install --frozen-lockfile
"$venv_python" "$project_root/scripts/generate-local-secrets.py"
pnpm migrate
pnpm seed

echo "SHADOWGRID bootstrap complete."
