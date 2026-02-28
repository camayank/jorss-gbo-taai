#!/bin/bash
# =============================================================================
# Database Backup Script — Jorss-GBO Tax Platform
# =============================================================================
#
# Creates a PostgreSQL backup using pg_dump.
#
# Usage:
#   ./scripts/backup_database.sh                    # Uses DATABASE_URL from .env
#   ./scripts/backup_database.sh --url "postgres://..."  # Explicit connection string
#   ./scripts/backup_database.sh --output /path/to/backup.sql
#
# Output: Timestamped SQL dump in ./backups/ directory
#
# Neon PostgreSQL Notes:
#   - Neon free tier includes 7-day point-in-time recovery (PITR) automatically
#   - Neon Pro tier includes 30-day PITR
#   - This script creates an additional on-demand backup for:
#     * Pre-migration snapshots
#     * Cross-region copies
#     * Long-term archival beyond PITR window
#     * Disaster recovery testing
#
# Prerequisites:
#   - pg_dump (PostgreSQL client tools)
#   - DATABASE_URL environment variable or --url flag
#
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DEFAULT_FILENAME="jorss_gbo_backup_${TIMESTAMP}.sql.gz"
DB_URL=""
OUTPUT_PATH=""
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
        --output|-o)
            OUTPUT_PATH="$2"
            shift 2
            ;;
        --verbose|-v)
            VERBOSE=1
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--url DATABASE_URL] [--output PATH] [--verbose]"
            echo ""
            echo "Options:"
            echo "  --url       PostgreSQL connection URL (default: \$DATABASE_URL from .env)"
            echo "  --output    Output file path (default: ./backups/jorss_gbo_backup_TIMESTAMP.sql.gz)"
            echo "  --verbose   Show detailed output"
            echo ""
            echo "Environment:"
            echo "  DATABASE_URL   Fallback connection URL if --url not specified"
            echo "  BACKUP_DIR     Directory for backups (default: ./backups)"
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
# Load .env if present and no explicit URL
# -----------------------------------------------------------------------------
if [ -z "$DB_URL" ]; then
    if [ -f ".env" ]; then
        # Source .env to get DATABASE_URL
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

# -----------------------------------------------------------------------------
# Verify pg_dump is available
# -----------------------------------------------------------------------------
if ! command -v pg_dump >/dev/null 2>&1; then
    echo "ERROR: pg_dump not found."
    echo "  Install PostgreSQL client tools:"
    echo "    macOS:  brew install libpq && brew link --force libpq"
    echo "    Ubuntu: sudo apt-get install postgresql-client"
    echo "    Alpine: apk add postgresql-client"
    exit 1
fi

# -----------------------------------------------------------------------------
# Create backup directory
# -----------------------------------------------------------------------------
mkdir -p "$BACKUP_DIR"

# Set output path
if [ -z "$OUTPUT_PATH" ]; then
    OUTPUT_PATH="${BACKUP_DIR}/${DEFAULT_FILENAME}"
fi

# -----------------------------------------------------------------------------
# Run backup
# -----------------------------------------------------------------------------
echo "=============================================="
echo "Jorss-GBO Database Backup"
echo "=============================================="
echo ""
echo "Timestamp:  ${TIMESTAMP}"
echo "Output:     ${OUTPUT_PATH}"

# Mask password in URL for display
DISPLAY_URL=$(echo "$DB_URL" | sed -E 's|(://[^:]+:)[^@]+(@)|\1****\2|')
echo "Database:   ${DISPLAY_URL}"
echo ""

echo "[1/3] Running pg_dump..."

# pg_dump with options:
#   --no-owner: Don't output ownership commands (Neon manages this)
#   --no-privileges: Skip access privilege commands
#   --format=plain: Plain SQL output (most portable)
#   --verbose: Show progress (if verbose flag set)
#   Pipe through gzip for compression
DUMP_OPTS="--no-owner --no-privileges --format=plain"
if [ "$VERBOSE" = "1" ]; then
    DUMP_OPTS="$DUMP_OPTS --verbose"
fi

if pg_dump "$DB_URL" $DUMP_OPTS | gzip > "$OUTPUT_PATH"; then
    echo "  pg_dump completed successfully"
else
    echo "ERROR: pg_dump failed. Check your connection string and network."
    rm -f "$OUTPUT_PATH"
    exit 1
fi

echo ""
echo "[2/3] Verifying backup..."

# Check file exists and has reasonable size
if [ ! -f "$OUTPUT_PATH" ]; then
    echo "ERROR: Backup file not found at ${OUTPUT_PATH}"
    exit 1
fi

FILE_SIZE=$(stat -f%z "$OUTPUT_PATH" 2>/dev/null || stat -c%s "$OUTPUT_PATH" 2>/dev/null || echo "0")
FILE_SIZE_KB=$((FILE_SIZE / 1024))

if [ "$FILE_SIZE" -lt 100 ]; then
    echo "WARNING: Backup file is suspiciously small (${FILE_SIZE} bytes)."
    echo "  This may indicate an empty database or connection issue."
    echo "  Inspect with: gunzip -c ${OUTPUT_PATH} | head -50"
else
    echo "  Backup size: ${FILE_SIZE_KB} KB"
fi

# Quick content check — verify it contains SQL statements
TABLE_COUNT=$(gunzip -c "$OUTPUT_PATH" 2>/dev/null | grep -c "^CREATE TABLE" || echo "0")
echo "  Tables in backup: ${TABLE_COUNT}"

echo ""
echo "[3/3] Generating backup metadata..."

# Write metadata file alongside backup
META_FILE="${OUTPUT_PATH%.sql.gz}.meta.json"
cat > "$META_FILE" << METAEOF
{
    "timestamp": "${TIMESTAMP}",
    "file": "$(basename "$OUTPUT_PATH")",
    "size_bytes": ${FILE_SIZE},
    "tables": ${TABLE_COUNT},
    "database_url_masked": "${DISPLAY_URL}",
    "pg_dump_version": "$(pg_dump --version | head -1)",
    "created_by": "scripts/backup_database.sh"
}
METAEOF

echo "  Metadata: ${META_FILE}"

echo ""
echo "=============================================="
echo "Backup completed successfully!"
echo "=============================================="
echo ""
echo "Files:"
echo "  Backup:   ${OUTPUT_PATH}"
echo "  Metadata: ${META_FILE}"
echo ""
echo "To restore:"
echo "  ./scripts/restore_database.sh --url \"\$DATABASE_URL\" --input ${OUTPUT_PATH}"
echo ""
echo "Neon PITR (automatic):"
echo "  Neon also provides point-in-time recovery via the dashboard."
echo "  Free tier: 7-day retention | Pro tier: 30-day retention"
echo "  https://console.neon.tech → Project → Branches → Restore"
