#!/bin/bash
# Tax Filing Platform - Development Server Startup Script

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$PROJECT_ROOT/src"

echo "Starting server on http://127.0.0.1:8000 (Ctrl+C to stop)"
exec python3 -m uvicorn web.app:app --host 127.0.0.1 --port 8000
