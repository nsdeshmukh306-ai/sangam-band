#!/usr/bin/env bash
cd ~/sangam-band
for f in logs/agent_*.pid; do
    name=$(basename "$f" .pid)
    pid=$(cat "$f" 2>/dev/null)
    if kill -0 "$pid" 2>/dev/null; then
        echo "RUNNING: $name (PID $pid)"
    else
        echo "DEAD:    $name (PID $pid)"
    fi
done
