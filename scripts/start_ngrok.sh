#!/bin/bash
export PATH="/home/nsdeshmukh306/.local/bin:$PATH"
mkdir -p logs
ngrok http 8000 --log=logs/ngrok.log &
sleep 3
curl -s http://localhost:4040/api/tunnels \
  | python3 -m json.tool | grep public_url
