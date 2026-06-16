#!/usr/bin/env bash
# Start Sangam FastAPI backend on port 8000.
# Run from the repo root: bash scripts/start_backend.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

LOG_DIR="$REPO_ROOT/logs"
mkdir -p "$LOG_DIR"

echo "[sangam] Starting FastAPI backend on http://localhost:8000"
echo "[sangam] Logs -> $LOG_DIR/backend.log"

nohup ~/.local/bin/uv run uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    > "$LOG_DIR/backend.log" 2>&1 &

BACKEND_PID=$!
echo "[sangam] Backend PID: $BACKEND_PID"
echo "$BACKEND_PID" > "$LOG_DIR/backend.pid"
echo "[sangam] To stop: kill \$(cat $LOG_DIR/backend.pid)"
