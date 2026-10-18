#!/usr/bin/env bash
# SeeGuide Server Execution Script for Linux/macOS
set -euo pipefail

if [ -d ".venv" ]; then
    echo "[*] Activating .venv..."
    source .venv/bin/activate
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

echo "Starting SeeGuide server on ${HOST}:${PORT}..."
exec uvicorn server.main:app --host "${HOST}" --port "${PORT}" --reload
