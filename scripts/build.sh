#!/bin/bash
# =============================================================================
# Production Build Script - Jorss-GBO Tax Platform
# =============================================================================
# This script runs during deployment to set up the application.
#
# Usage: ./scripts/build.sh
# =============================================================================

set -e  # Exit on any error

echo "=============================================="
echo "Jorss-GBO Tax Platform - Production Build"
echo "=============================================="

# 1. Install dependencies
echo ""
echo "[1/4] Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# 2. Run database migrations (if Alembic is set up)
echo ""
echo "[2/4] Checking database migrations..."
if [ -f "alembic.ini" ] && [ -n "$DATABASE_URL" ]; then
    echo "Running Alembic migrations..."
    alembic upgrade head
else
    echo "Skipping migrations (no alembic.ini or DATABASE_URL not set)"
fi

# 3. Collect static files (if needed)
echo ""
echo "[3/4] Setting up static files..."
# Static files are already in src/web/static, no collection needed

# 4. Validate configuration
echo ""
echo "[4/4] Validating configuration..."
python -c "
import os
import sys

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
echo "=============================================="
echo "Build completed successfully!"
echo "=============================================="
