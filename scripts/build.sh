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

# 1. Install dependencies (from lock file for reproducible builds)
echo ""
echo "[1/5] Installing Python dependencies..."
if [ "$SKIP_DEP_INSTALL" = "1" ]; then
    echo "Skipping dependency installation (SKIP_DEP_INSTALL=1)"
elif [ -f "requirements.lock" ]; then
    "$PYTHON_BIN" -m pip install --upgrade pip --disable-pip-version-check
    "$PYTHON_BIN" -m pip install -r requirements.lock --disable-pip-version-check
else
    echo "WARNING: requirements.lock not found, falling back to requirements.txt"
    "$PYTHON_BIN" -m pip install --upgrade pip --disable-pip-version-check
    "$PYTHON_BIN" -m pip install -r requirements.txt --disable-pip-version-check
fi

# 2. Minify static assets (CSS) if Node.js is available
echo ""
echo "[2/5] Optimizing static assets..."
if command -v node >/dev/null 2>&1 && [ -f "package.json" ]; then
    if [ -f "node_modules/.package-lock.json" ] || [ -f "package-lock.json" ]; then
        echo "Running CSS minification..."
        NODE_ENV=production npx postcss 'src/web/static/css/**/*.css' \
            --dir src/web/static/css --no-map --replace 2>/dev/null \
            && echo "CSS minified successfully" \
            || echo "CSS minification skipped (postcss not configured)"
    else
        echo "Skipping minification (node_modules not installed)"
    fi
else
    echo "Skipping minification (Node.js not available)"
fi

# 3. Run launch preflight checks (env + secrets + migration graph)
echo ""
echo "[3/5] Running launch preflight (pre-migration)..."
"$PYTHON_BIN" scripts/preflight_launch.py --mode production --skip-migration-status

# 4. Run database migrations (if Alembic is set up)
echo ""
echo "[4/5] Checking database migrations..."
if [ -f "alembic.ini" ] && [ -n "$DATABASE_URL" ]; then
    # Create pre-migration backup if pg_dump is available
    if command -v pg_dump >/dev/null 2>&1 && [ "${SKIP_PRE_MIGRATION_BACKUP:-0}" != "1" ]; then
        echo "Creating pre-migration backup..."
        BACKUP_DIR="${BACKUP_DIR:-./backups}" \
            ./scripts/backup_database.sh --url "$DATABASE_URL" 2>/dev/null \
            && echo "Pre-migration backup created" \
            || echo "WARNING: Pre-migration backup failed (continuing with migration)"
    fi
    echo "Running Alembic migrations..."
    "$PYTHON_BIN" -m alembic -c alembic.ini upgrade head
else
    echo "Skipping migrations (no alembic.ini or DATABASE_URL not set)"
fi

# 5. Final preflight (full — includes migration status)
echo ""
echo "[5/5] Running final launch preflight..."
"$PYTHON_BIN" scripts/preflight_launch.py --mode production

echo ""
echo "=============================================="
echo "Build completed successfully!"
echo "=============================================="
