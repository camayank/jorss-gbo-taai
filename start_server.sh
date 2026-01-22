#!/bin/bash

# Tax Filing Platform - Development Server Startup Script
# This script starts the FastAPI server with proper Python path configuration

echo "========================================="
echo "Starting Tax Filing Platform Server"
echo "========================================="
echo ""

# Set the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

echo "✓ Project root: $PROJECT_ROOT"
echo "✓ Python path configured"
echo ""

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is not installed"
    echo "Please install Python 3.9 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1)
echo "✓ Python: $PYTHON_VERSION"

# Check if required packages are installed
echo ""
echo "Checking dependencies..."

if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "❌ Error: fastapi is not installed"
    echo ""
    echo "Please install dependencies:"
    echo "  pip3 install -r requirements.txt"
    exit 1
fi

if ! python3 -c "import uvicorn" 2>/dev/null; then
    echo "❌ Error: uvicorn is not installed"
    echo ""
    echo "Please install dependencies:"
    echo "  pip3 install -r requirements.txt"
    exit 1
fi

echo "✓ FastAPI and Uvicorn are installed"
echo ""

# Start the server
echo "========================================="
echo "Starting server on http://127.0.0.1:8000"
echo "========================================="
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

cd "$PROJECT_ROOT"
python3 -m uvicorn src.web.app:app --reload --port 8000 --host 127.0.0.1
