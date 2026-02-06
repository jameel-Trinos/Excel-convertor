#!/bin/bash
# Script to restart the backend server with the correct virtual environment

echo "Stopping any running uvicorn servers..."
pkill -f "uvicorn app.main:app" 2>/dev/null || true

echo "Activating virtual environment..."
cd "$(dirname "$0")"

# Determine if using root-level or backend-level venv
if [ -d "../.venv" ]; then
    source ../.venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Error: Virtual environment not found!"
    exit 1
fi

echo "Starting backend server..."
uvicorn app.main:app --reload --port 8000
