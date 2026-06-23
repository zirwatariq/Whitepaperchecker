#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/venv"

if [ ! -d "$VENV" ]; then
  echo "Creating virtual environment..."
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q -r "$ROOT/backend/requirements.txt"
fi

echo "Starting backend on http://127.0.0.1:5050"
cd "$ROOT/backend"
"$VENV/bin/python" app.py &
BACKEND_PID=$!

echo "Opening frontend..."
sleep 1
open "$ROOT/frontend/index.html"

wait $BACKEND_PID
