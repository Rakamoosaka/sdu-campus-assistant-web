#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .local-run
[[ -x .venv/bin/python ]] || { echo 'Create .venv and install backend/requirements.txt first.'; exit 1; }
[[ -d web/node_modules ]] || { echo 'Run npm ci --prefix web first.'; exit 1; }
node_path="$(.venv/bin/python -c 'import os, shutil; print(os.path.realpath(shutil.which("node") or ""))')"
[[ -x "$node_path" ]] || { echo 'Node.js is required.'; exit 1; }
project_key="$(.venv/bin/python -c 'import hashlib,os; print(hashlib.sha256(os.getcwd().encode()).hexdigest()[:12])')"
start_service() {
  local service_name="$1"
  local pidfile=".local-run/${service_name}.pid"
  if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    echo "$service_name is already running (PID $(cat "$pidfile"))"
    return
  fi
  if [[ "$(uname -s)" == Darwin ]]; then
    # launchd owns these jobs, so ending the Codex command/chat does not kill them.
    # submit creates a current-login job only, with no boot/login installation.
    local label="dev.sdu-campus.${project_key}.${service_name}"
    launchctl remove "$label" >/dev/null 2>&1 || true
    echo "$label" > ".local-run/${service_name}.label"
    launchctl submit -l "$label" -o "$PWD/.local-run/${service_name}.log" \
      -e "$PWD/.local-run/${service_name}.err.log" -- \
      /bin/bash "$PWD/scripts/run-web-service.sh" "$service_name" "$node_path"
  else
    .venv/bin/python - "$PWD" "$service_name" "$node_path" <<'PY'
import pathlib, subprocess, sys
root, name, node = sys.argv[1:]
with open(pathlib.Path(root) / '.local-run' / (name+'.log'), 'ab') as log:
    subprocess.Popen(['/bin/bash', str(pathlib.Path(root)/'scripts/run-web-service.sh'), name, node],
                     stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
PY
  fi
}
start_service backend
start_service frontend
for attempt in {1..30}; do
  if [[ -f .local-run/backend.pid && -f .local-run/frontend.pid ]] && \
     kill -0 "$(cat .local-run/backend.pid)" 2>/dev/null && \
     kill -0 "$(cat .local-run/frontend.pid)" 2>/dev/null && \
     curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1 && \
     curl -fsS http://127.0.0.1:5173 >/dev/null 2>&1; then
    echo 'Web app: http://127.0.0.1:5173'
    echo 'API docs: http://127.0.0.1:8000/docs'
    echo 'Logs: .local-run/*.log. Stop: make web-stop'
    exit 0
  fi
  sleep 1
done
echo 'Startup failed. Inspect .local-run/*.log.' >&2
exit 1
