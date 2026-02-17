#!/bin/bash
# =============================================================================
# Production Build Script - Jorss-GBO Tax Platform
# =============================================================================
# This script runs during deployment to set up the application.
#
# Usage: ./scripts/build.sh
# =============================================================================

set -e  # Exit on any error

PYTHON_BIN="${PYTHON_BIN:-python3}"
SKIP_DEP_INSTALL="${SKIP_DEP_INSTALL:-0}"
export PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-/tmp/codex-pycache}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp}"
SRC_PATH="$(pwd)/src"
if [ -n "${PYTHONPATH:-}" ]; then
    export PYTHONPATH="$SRC_PATH:$PYTHONPATH"
else
    export PYTHONPATH="$SRC_PATH"
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    if command -v python >/dev/null 2>&1; then
        PYTHON_BIN="python"
    else
        echo "ERROR: Python interpreter not found (python3/python)"
        exit 1
    fi
fi

# Load local environment file for CLI runs (deployment platforms already inject env vars).
if [ -f ".env" ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

echo "=============================================="
echo "Jorss-GBO Tax Platform - Production Build"
echo "=============================================="

# 1. Install dependencies
echo ""
echo "[1/5] Installing Python dependencies..."
if [ "$SKIP_DEP_INSTALL" = "1" ]; then
    echo "Skipping dependency installation (SKIP_DEP_INSTALL=1)"
else
    "$PYTHON_BIN" -m pip install --upgrade pip --disable-pip-version-check
    "$PYTHON_BIN" -m pip install -r requirements.txt --disable-pip-version-check
fi

# 2. Run launch preflight checks (env + migration graph + tooling)
echo ""
echo "[2/5] Running launch preflight (initial)..."
"$PYTHON_BIN" scripts/preflight_launch.py --mode production --skip-migration-status

# 3. Run database migrations (if Alembic is set up)
echo ""
echo "[3/5] Checking database migrations..."
if [ -f "alembic.ini" ] && [ -n "$DATABASE_URL" ]; then
    echo "Running Alembic migrations..."
    "$PYTHON_BIN" -m alembic -c alembic.ini upgrade head
else
    echo "Skipping migrations (no alembic.ini or DATABASE_URL not set)"
fi

# 4. Collect static files (if needed)
echo ""
echo "[4/5] Setting up static files..."
# Static files are already in src/web/static, no collection needed

# 5. Validate configuration
echo ""
echo "[5/5] Validating configuration..."
"$PYTHON_BIN" -c "
import os
import sys

# Load .env for local/CLI runs where vars are not pre-exported.
try:
    from dotenv import load_dotenv
    load_dotenv('.env', override=False)
except Exception:
    pass

# Check required environment variables
required_vars = ['APP_SECRET_KEY', 'DATABASE_URL']
optional_vars = ['REDIS_URL', 'OPENAI_API_KEY']

print('Checking required environment variables...')
missing = []
for var in required_vars:
    if os.environ.get(var):
        print(f'  {var}: OK')
    else:
        print(f'  {var}: MISSING')
        missing.append(var)

print('')
print('Checking optional environment variables...')
for var in optional_vars:
    if os.environ.get(var):
        print(f'  {var}: OK')
    else:
        print(f'  {var}: Not set (optional)')

if missing:
    print('')
    print(f'ERROR: Missing required variables: {missing}')
    print('Set these in your Render dashboard under Environment.')
    sys.exit(1)

print('')
print('Configuration validated successfully!')
"

echo ""
echo "Running final launch preflight..."
"$PYTHON_BIN" scripts/preflight_launch.py --mode production

echo ""
echo "=============================================="
echo "Build completed successfully!"
echo "=============================================="
