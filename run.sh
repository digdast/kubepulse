#!/usr/bin/env bash
# KubePulse Launcher for Linux & macOS
set -e
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
else
    PYTHON_BIN="python"
fi

if ! $PYTHON_BIN -c "import fastapi, uvicorn, paramiko" >/dev/null 2>&1; then
    echo "[KubePulse] Installing Python dependencies..."
    $PYTHON_BIN -m pip install -r requirements.txt
fi

exec $PYTHON_BIN run.py "$@"
