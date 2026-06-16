#!/usr/bin/env bash
cd ~/sangam-band
pid=$(cat logs/agent_intake.pid 2>/dev/null)
if kill -0 "$pid" 2>/dev/null; then
    echo "Stopping intake (PID $pid)..."
    kill "$pid"
    sleep 1
fi
nohup uv run python -m agents.intake_agent >> logs/agent_intake.log 2>&1 &
echo "$!" > logs/agent_intake.pid
echo "Restarted intake (PID $!)"
