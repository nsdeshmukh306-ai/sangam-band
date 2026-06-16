#!/usr/bin/env bash
# Start Sangam React dev server on port 3000.
# Requires: Node.js 20 via nvm (curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash && nvm install 20)
# Run from the repo root: bash scripts/start_react.sh
set -euo pipefail

# Load nvm if present
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REACT_DIR="$REPO_ROOT/frontend/react"
LOG_DIR="$REPO_ROOT/logs"
mkdir -p "$LOG_DIR"

cd "$REACT_DIR"

if [ ! -d node_modules ]; then
  echo "[sangam] Installing npm dependencies…"
  npm install
fi

echo "[sangam] Starting React dev server on http://localhost:3000"
echo "[sangam] Proxies /api/* → http://localhost:8000"
echo "[sangam] Logs → $LOG_DIR/react.log"

nohup npm run dev > "$LOG_DIR/react.log" 2>&1 &
REACT_PID=$!
echo "[sangam] React PID: $REACT_PID"
echo "$REACT_PID" > "$LOG_DIR/react.pid"
echo "[sangam] To stop: kill \$(cat $LOG_DIR/react.pid)"
