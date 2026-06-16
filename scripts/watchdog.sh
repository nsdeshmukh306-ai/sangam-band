#!/usr/bin/env bash
# Sangam agent watchdog — detects and restarts silenced/crashed agents.
#
# The "silent-deaf-agent" bug: a Band WebSocket connection drops without
# notifying the agent process, so the agent stops receiving new messages
# but its OS process remains alive. The watchdog catches both cases:
#   1. Process is dead → restart immediately.
#   2. Log file has not been written for MAX_SILENCE_SECS → restart.
#
# Usage:
#   # Run once:
#   bash scripts/watchdog.sh
#
#   # Run in a loop every 60 s (from cron or a background terminal):
#   while true; do bash scripts/watchdog.sh; sleep 60; done
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$REPO_ROOT/logs"
MAX_SILENCE_SECS="${SANGAM_MAX_SILENCE:-300}"   # 5 min default; override via env

AGENTS=(intake patient_profile structural pkpd evidence_rag compliance)
declare -A MODULES=(
    [intake]="agents.intake_agent"
    [patient_profile]="agents.patient_profile_agent"
    [structural]="agents.structural_agent"
    [pkpd]="agents.pkpd_agent"
    [evidence_rag]="agents.evidence_rag_agent"
    [compliance]="agents.compliance_agent"
)

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

restart_agent() {
    local name="$1"
    local module="${MODULES[$name]}"
    local log="$LOG_DIR/agent_${name}.log"
    local pid_file="$LOG_DIR/agent_${name}.pid"

    echo "[$(ts)] [watchdog] Restarting $name (module: $module)..."

    # Kill existing process if still running
    if [[ -f "$pid_file" ]]; then
        local old_pid
        old_pid=$(cat "$pid_file" 2>/dev/null || echo "")
        if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
            kill "$old_pid" 2>/dev/null || true
            sleep 1
        fi
    fi

    cd "$REPO_ROOT"
    nohup ~/.local/bin/uv run python -m "$module" >> "$log" 2>&1 &
    local new_pid=$!
    echo "$new_pid" > "$pid_file"
    echo "[$(ts)] [watchdog] $name restarted (new PID: $new_pid)"
}

mkdir -p "$LOG_DIR"

for name in "${AGENTS[@]}"; do
    pid_file="$LOG_DIR/agent_${name}.pid"
    log_file="$LOG_DIR/agent_${name}.log"

    # ── Case 1: no PID file → agent was never started or was clean-stopped ──
    if [[ ! -f "$pid_file" ]]; then
        echo "[$(ts)] [watchdog] $name: no PID file — skipping (run start_agents.sh first)"
        continue
    fi

    pid=$(cat "$pid_file" 2>/dev/null || echo "")

    # ── Case 2: process is dead ──
    if [[ -z "$pid" ]] || ! kill -0 "$pid" 2>/dev/null; then
        echo "[$(ts)] [watchdog] $name (PID ${pid:-?}): process is dead → restarting"
        restart_agent "$name"
        continue
    fi

    # ── Case 3: process alive but log hasn't been updated in MAX_SILENCE_SECS ──
    if [[ -f "$log_file" ]]; then
        if command -v stat &>/dev/null; then
            # GNU stat
            last_mod=$(stat -c %Y "$log_file" 2>/dev/null || date +%s)
        else
            # macOS/BSD stat
            last_mod=$(stat -f %m "$log_file" 2>/dev/null || date +%s)
        fi
        now=$(date +%s)
        age=$(( now - last_mod ))
        if (( age > MAX_SILENCE_SECS )); then
            echo "[$(ts)] [watchdog] $name (PID $pid): silent for ${age}s (>${MAX_SILENCE_SECS}s) → restarting"
            restart_agent "$name"
            continue
        fi
    fi

    echo "[$(ts)] [watchdog] $name (PID $pid): OK"
done
