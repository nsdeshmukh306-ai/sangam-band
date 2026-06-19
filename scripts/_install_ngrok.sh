#!/bin/bash
set -e
INSTALL_DIR="/home/nsdeshmukh306/.local/bin"
mkdir -p "$INSTALL_DIR"
echo "Downloading ngrok..."
curl -sSL https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz -o /tmp/ngrok.tgz
tar -xzf /tmp/ngrok.tgz -C "$INSTALL_DIR"
chmod +x "$INSTALL_DIR/ngrok"
rm /tmp/ngrok.tgz
echo "Installed: $("$INSTALL_DIR/ngrok" version)"
