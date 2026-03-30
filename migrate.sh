#!/usr/bin/env bash
# =============================================================================
# migrate.sh — Run Alembic migrations with correct environment
# Usage:
#   ./migrate.sh                     # upgrade to head (uses .env.production)
#   ./migrate.sh current             # show current revision
#   ./migrate.sh history             # show migration history
#   ./migrate.sh downgrade -1        # roll back one step
#   ENV_FILE=.env ./migrate.sh       # use a different env file
# =============================================================================

set -euo pipefail

ENV_FILE="${ENV_FILE:-.env.production}"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: $ENV_FILE not found. Create it first."
  exit 1
fi

# Load env file (skip comments and blank lines)
set -o allexport
# shellcheck disable=SC2046
eval $(grep -v '^\s*#' "$ENV_FILE" | grep -v '^\s*$' | sed 's/ #.*//')
set +o allexport

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL is not set in $ENV_FILE"
  exit 1
fi

export PYTHONPATH="${PYTHONPATH:-src}"

CMD="${1:-upgrade head}"
shift 2>/dev/null || true
EXTRA_ARGS="${*:-}"

echo "▶ alembic $CMD $EXTRA_ARGS"
echo "  DB: ${DATABASE_URL%%@*}@$(echo "$DATABASE_URL" | sed 's/.*@//')"
echo "  PYTHONPATH: $PYTHONPATH"
echo ""

python3 -m alembic $CMD $EXTRA_ARGS
