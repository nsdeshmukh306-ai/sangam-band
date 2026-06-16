#!/usr/bin/env bash
# Start all 6 Sangam agents in the background with nohup.
# Logs go to logs/agent_<name>.log; PIDs to logs/agent_<name>.pid.
#
# Usage (from repo root):
#   bash scripts/start_agents.sh
#
# Stop all:
#   cat logs/agent_*.pid | xargs kill 2>/dev/null

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$REPO_DIR/logs"
mkdir -p "$LOG_DIR"
cd "$REPO_DIR"

declare -A AGENTS=(
    ["intake"]="agents.intake_agent"
    ["patient_profile"]="agents.patient_profile_agent"
    ["structural"]="agents.structural_agent"
    ["pkpd"]="agents.pkpd_agent"
    ["evidence_rag"]="agents.evidence_rag_agent"
    ["compliance"]="agents.compliance_agent"
)

echo "Starting Sangam agents from: $REPO_DIR"
echo ""

for name in intake patient_profile structural pkpd evidence_rag compliance; do
    module="${AGENTS[$name]}"
    log="$LOG_DIR/agent_${name}.log"
    pid_file="$LOG_DIR/agent_${name}.pid"

    # Kill previous instance if pid file exists
    if [[ -f "$pid_file" ]]; then
        old_pid=$(cat "$pid_file")
        if kill -0 "$old_pid" 2>/dev/null; then
            echo "  Stopping previous $name (PID $old_pid)..."
            kill "$old_pid" 2>/dev/null || true
            sleep 0.5
        fi
    fi

    nohup uv run python -m "$module" >> "$log" 2>&1 &
    echo "$!" > "$pid_file"
    echo "  ✓ $name  (PID $!, log: logs/agent_${name}.log)"
done

echo ""
echo "All 6 agents started. Tail a log:"
echo "  tail -f logs/agent_compliance.log"
echo ""
echo "Stop all agents:"
echo "  cat logs/agent_*.pid | xargs kill 2>/dev/null"
