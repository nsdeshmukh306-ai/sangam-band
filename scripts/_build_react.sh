#!/bin/bash
set -e
NVM_BIN="/home/nsdeshmukh306/.nvm/versions/node/v20.20.2/bin"
export PATH="$NVM_BIN:$PATH"
cd /home/nsdeshmukh306/sangam-band/frontend/react
echo "node: $(which node) $(node --version)"
echo "npm:  $(which npm) $(npm --version)"
npm run build
