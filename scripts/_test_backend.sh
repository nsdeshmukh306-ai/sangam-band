#!/bin/bash
export PATH="/home/nsdeshmukh306/.local/bin:$PATH"
cd /home/nsdeshmukh306/sangam-band
pkill -f 'uvicorn backend.main' 2>/dev/null
sleep 1
nohup uv run uvicorn backend.main:app --port 8000 --host 0.0.0.0 > /tmp/backend_test.log 2>&1 &
echo "Backend PID: $!"
sleep 5
echo "--- curl /health ---"
curl -s http://localhost:8000/health
echo ""
echo "--- curl /app/ (first 3 lines) ---"
curl -s http://localhost:8000/app/ | head -3
echo ""
echo "--- backend log tail ---"
tail -5 /tmp/backend_test.log
pkill -f 'uvicorn backend.main' 2>/dev/null
