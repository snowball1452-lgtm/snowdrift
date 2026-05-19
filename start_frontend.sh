#!/bin/bash
set -e

export EXPO_NO_TELEMETRY=1
export EXPO_NO_GIT_STATUS=1
export CI=1

echo "Starting proxy server on port 5000..."
cd /home/runner/workspace
node proxy.js &
PROXY_PID=$!

echo "Starting Expo web (Metro on port 8081)..."
cd /home/runner/workspace/frontend
exec npx expo start --web --localhost
