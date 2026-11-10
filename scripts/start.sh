#!/usr/bin/env bash
# Start ISL NOVA on Linux/macOS (after scripts/install_all.sh). Ctrl+C to stop.
#   bash scripts/start.sh [--port 8000]
set -euo pipefail
PORT=8000
[ "${1:-}" = "--port" ] && PORT="$2"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
[ -x .venv/bin/python ] || { echo "ERROR  run scripts/install_all.sh first"; exit 1; }
[ -f frontend/dist/index.html ] || { echo "ERROR  frontend not built: cd frontend && npm run build"; exit 1; }
if (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; then
  echo "ERROR  port $PORT is already in use (ISL NOVA already running?). Use: bash scripts/start.sh --port 8080"; exit 1
fi
[ -f .env ] && { set -a; . ./.env; set +a; }
export PYTHONPATH="$ROOT/backend:$ROOT/ml"
export CORS_ORIGINS="http://127.0.0.1:$PORT,http://localhost:$PORT${CORS_ORIGINS:+,$CORS_ORIGINS}"
.venv/bin/python -m app.migrate >/dev/null
echo "ISL NOVA: http://127.0.0.1:$PORT  (API docs: /api/docs, Ctrl+C to stop)"
exec .venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port "$PORT"
