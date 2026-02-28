#!/bin/bash
# =============================================================================
# Database Restore Script — Jorss-GBO Tax Platform
# =============================================================================
#
# Restores a PostgreSQL database from a backup created by backup_database.sh.
#
# Usage:
#   ./scripts/restore_database.sh --input backups/jorss_gbo_backup_20260228.sql.gz
#   ./scripts/restore_database.sh --url "postgres://..." --input backup.sql.gz
#
# SAFETY:
#   - Prompts for confirmation before restoring (destructive operation)
#   - Use --force to skip confirmation (for CI/automation)
#   - Recommends creating a Neon branch for safe testing
#
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
DB_URL=""
INPUT_PATH=""
FORCE=0
VERBOSE=0

# -----------------------------------------------------------------------------
# Parse arguments
# -----------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case $1 in
        --url)
            DB_URL="$2"
            shift 2
            ;;
        --input|-i)
            INPUT_PATH="$2"
            shift 2
            ;;
        --force|-f)
            FORCE=1
            shift
            ;;
        --verbose|-v)
            VERBOSE=1
            shift
            ;;
        --help|-h)
            echo "Usage: $0 --input BACKUP_FILE [--url DATABASE_URL] [--force] [--verbose]"
            echo ""
            echo "Options:"
            echo "  --input     Path to backup file (.sql.gz or .sql) [required]"
            echo "  --url       PostgreSQL connection URL (default: \$DATABASE_URL from .env)"
            echo "  --force     Skip confirmation prompt"
            echo "  --verbose   Show detailed output"
            echo ""
            echo "Safety:"
            echo "  This is a DESTRUCTIVE operation. The target database will be overwritten."
            echo "  Consider restoring to a Neon branch first for safe testing."
            exit 0
            ;;
        *)
            echo "ERROR: Unknown option: $1"
            echo "Run '$0 --help' for usage."
            exit 1
            ;;
    esac
done

# -----------------------------------------------------------------------------
# Validate inputs
# -----------------------------------------------------------------------------
if [ -z "$INPUT_PATH" ]; then
    echo "ERROR: --input is required."
    echo "Run '$0 --help' for usage."
    exit 1
fi

if [ ! -f "$INPUT_PATH" ]; then
    echo "ERROR: Backup file not found: ${INPUT_PATH}"
    exit 1
fi

# Load .env if needed
if [ -z "$DB_URL" ]; then
    if [ -f ".env" ]; then
        set -a
        # shellcheck disable=SC1091
        source .env
        set +a
    fi
    DB_URL="${DATABASE_URL:-}"
fi

if [ -z "$DB_URL" ]; then
    echo "ERROR: No database URL provided."
    echo "  Set DATABASE_URL in .env or pass --url 'postgresql://...'"
    exit 1
fi

# Verify psql is available
if ! command -v psql >/dev/null 2>&1; then
    echo "ERROR: psql not found."
    echo "  Install PostgreSQL client tools:"
    echo "    macOS:  brew install libpq && brew link --force libpq"
    echo "    Ubuntu: sudo apt-get install postgresql-client"
    exit 1
fi

# -----------------------------------------------------------------------------
# Safety confirmation
# -----------------------------------------------------------------------------
DISPLAY_URL=$(echo "$DB_URL" | sed -E 's|(://[^:]+:)[^@]+(@)|\1****\2|')

echo "=============================================="
echo "Jorss-GBO Database Restore"
echo "=============================================="
echo ""
echo "Source:     ${INPUT_PATH}"
echo "Target:     ${DISPLAY_URL}"
echo ""

# Show backup metadata if available
META_FILE="${INPUT_PATH%.sql.gz}.meta.json"
if [ -f "$META_FILE" ]; then
    echo "Backup metadata:"
    cat "$META_FILE"
    echo ""
fi

if [ "$FORCE" != "1" ]; then
    echo "WARNING: This will OVERWRITE all data in the target database!"
    echo ""
    echo "Safer alternative: Create a Neon branch first:"
    echo "  neonctl branches create --name restore-test --parent main"
    echo "  Then restore to the branch's connection string."
    echo ""
    read -r -p "Type 'RESTORE' to confirm: " CONFIRM
    if [ "$CONFIRM" != "RESTORE" ]; then
        echo "Aborted."
        exit 0
    fi
fi

# -----------------------------------------------------------------------------
# Run restore
# -----------------------------------------------------------------------------
echo ""
echo "[1/3] Preparing restore..."

# Determine if file is gzipped
IS_GZIPPED=0
if [[ "$INPUT_PATH" == *.gz ]]; then
    IS_GZIPPED=1
    echo "  Detected gzipped backup"
fi

echo ""
echo "[2/3] Restoring database..."

if [ "$IS_GZIPPED" = "1" ]; then
    if gunzip -c "$INPUT_PATH" | psql "$DB_URL" --single-transaction --quiet; then
        echo "  Restore completed successfully"
    else
        echo "ERROR: Restore failed. Database may be in an inconsistent state."
        echo "  Consider restoring from Neon PITR instead."
        exit 1
    fi
else
    if psql "$DB_URL" --single-transaction --quiet < "$INPUT_PATH"; then
        echo "  Restore completed successfully"
    else
        echo "ERROR: Restore failed."
        exit 1
    fi
fi

echo ""
echo "[3/3] Verifying restore..."

# Quick verification — count tables
TABLE_COUNT=$(psql "$DB_URL" --tuples-only --no-align -c \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';" \
    2>/dev/null || echo "?")

echo "  Tables in database: ${TABLE_COUNT}"

# Check Alembic migration version
ALEMBIC_HEAD=$(psql "$DB_URL" --tuples-only --no-align -c \
    "SELECT version_num FROM alembic_version LIMIT 1;" \
    2>/dev/null || echo "unknown")

echo "  Alembic head: ${ALEMBIC_HEAD}"

echo ""
echo "=============================================="
echo "Restore completed successfully!"
echo "=============================================="
echo ""
echo "Next steps:"
echo "  1. Verify application connects: python3 scripts/preflight_launch.py --mode production"
echo "  2. Run migration check:         python3 -m alembic -c alembic.ini current"
echo "  3. Spot-check data in the app"
