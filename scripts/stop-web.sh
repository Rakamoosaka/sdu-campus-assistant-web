#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
for service_name in frontend backend; do
  label_file=".local-run/${service_name}.label"
  if [[ "$(uname -s)" == Darwin && -f "$label_file" ]]; then
    launchctl remove "$(cat "$label_file")" 2>/dev/null || true
    rm "$label_file"
  fi
  pidfile=".local-run/${service_name}.pid"
  if [[ -f "$pidfile" ]]; then
    service_pid="$(cat "$pidfile")"
    if kill -0 "$service_pid" 2>/dev/null; then
      pkill -TERM -P "$service_pid" 2>/dev/null || true
      kill -TERM "$service_pid" 2>/dev/null || true
      for attempt in {1..50}; do
        kill -0 "$service_pid" 2>/dev/null || break
        sleep 0.1
      done
    fi
    rm "$pidfile"
    echo "Stopped $service_name"
  fi
done
