#!/usr/bin/env bash
# Invoked by the local service launcher. exec keeps the PID file accurate.
set -euo pipefail
cd "$(dirname "$0")/.."
service_name="$1"
node_path="${2:-}"
if [[ -f .env ]]; then set -a; source .env; set +a; fi
mkdir -p .local-run
echo "$$" > ".local-run/${service_name}.pid"
case "$service_name" in
  backend)
    exec .venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
    ;;
  frontend)
    unset OPENROUTER_API_KEY JWT_SECRET DATABASE_URL
    export PATH="$(dirname "$node_path"):$PATH"
    cd web
    exec "$node_path" node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173
    ;;
  *) echo 'Unknown service' >&2; exit 1 ;;
esac
