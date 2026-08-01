#!/usr/bin/env bash
set -euo pipefail

shadowgrid_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
shadowgrid_run_root="$shadowgrid_root/.local/run"

resolve_shadowgrid_mode() {
  local requested="${1:-auto}"
  case "$requested" in
    compose)
      command -v docker >/dev/null 2>&1 || {
        echo "Compose mode requires Docker with the Compose plugin." >&2
        return 1
      }
      echo "compose"
      ;;
    sqlite) echo "sqlite" ;;
    auto)
      if compgen -G "$shadowgrid_run_root/*.pid" >/dev/null; then
        echo "sqlite"
      elif command -v docker >/dev/null 2>&1; then
        echo "compose"
      else
        echo "sqlite"
      fi
      ;;
    *)
      echo "Mode must be auto, compose or sqlite." >&2
      return 1
      ;;
  esac
}

wait_shadowgrid_http() {
  local uri="$1"
  local attempts="${2:-45}"
  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if curl --fail --silent --show-error --max-time 5 "$uri" >/dev/null; then
      return 0
    fi
    sleep 2
  done
  echo "Timed out waiting for $uri" >&2
  return 1
}

shadowgrid_env_value() {
  local name="$1"
  local fallback="$2"
  local env_file="$shadowgrid_root/.local/development.env"
  if [[ ! -f "$env_file" ]]; then
    echo "$fallback"
    return
  fi
  local value
  value="$(awk -F= -v key="$name" '$1 == key {value = substr($0, index($0, "=") + 1)} END {print value}' "$env_file")"
  echo "${value:-$fallback}"
}

start_shadowgrid_process() {
  local name="$1"
  local marker="$2"
  shift 2
  mkdir -p "$shadowgrid_run_root"
  local pid_file="$shadowgrid_run_root/$name.pid"
  if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    echo "$name is already running with PID $(cat "$pid_file")."
    return
  fi
  rm -f "$pid_file"
  nohup "$@" \
    >"$shadowgrid_run_root/$name.stdout.log" \
    2>"$shadowgrid_run_root/$name.stderr.log" &
  local pid=$!
  echo "$pid" >"$pid_file"
  echo "$marker" >"$shadowgrid_run_root/$name.marker"
  echo "Started $name with PID $pid."
}

stop_shadowgrid_process() {
  local name="$1"
  local pid_file="$shadowgrid_run_root/$name.pid"
  local marker_file="$shadowgrid_run_root/$name.marker"
  if [[ ! -f "$pid_file" ]]; then
    echo "$name is not recorded as running."
    return
  fi
  local pid
  pid="$(cat "$pid_file")"
  if ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$pid_file" "$marker_file"
    echo "Removed stale $name PID record."
    return
  fi
  local marker
  marker="$(cat "$marker_file")"
  local command_line
  command_line="$(tr '\0' ' ' <"/proc/$pid/cmdline")"
  if [[ "$command_line" != *"$marker"* ]]; then
    echo "Refusing to stop PID $pid because it does not match $name." >&2
    return 1
  fi
  kill "$pid"
  for _ in {1..20}; do
    if ! kill -0 "$pid" 2>/dev/null; then
      rm -f "$pid_file" "$marker_file"
      echo "Stopped $name."
      return
    fi
    sleep 0.25
  done
  kill -9 "$pid"
  rm -f "$pid_file" "$marker_file"
  echo "Stopped $name after graceful timeout."
}
