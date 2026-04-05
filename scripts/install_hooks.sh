#!/usr/bin/env bash
# Install git hooks for this repository.
# Run once after cloning: bash scripts/install_hooks.sh

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOKS_SRC="$REPO_ROOT/scripts/hooks"
HOOKS_DST="$REPO_ROOT/.git/hooks"

mkdir -p "$HOOKS_SRC"

# ----- pre-commit hook -------------------------------------------------------
cat > "$HOOKS_SRC/pre-commit" << 'HOOK'
#!/bin/sh
# Pre-commit hook: fail if docs/api/openapi.json is stale.
# To skip (emergency only): git commit --no-verify

CHANGED=$(git diff --cached --name-only 2>/dev/null)
NEEDS_CHECK=0

for f in $CHANGED; do
  case "$f" in
    src/web/app.py|src/web/routers/*.py|src/web/routes/*.py|\
    src/core/api/*.py|src/cpa_panel/api*.py|src/admin_panel/api*.py)
      NEEDS_CHECK=1
      break
      ;;
  esac
done

echo "$CHANGED" | grep -q "docs/api/openapi.json" && NEEDS_CHECK=1

if [ "$NEEDS_CHECK" = "0" ]; then
  exit 0
fi

echo "Checking docs/api/openapi.json freshness..."
python scripts/check_openapi_fresh.py
STATUS=$?

if [ $STATUS -ne 0 ]; then
  echo ""
  echo "FAIL: docs/api/openapi.json is stale or missing."
  echo "  Run: python scripts/export_openapi.py && git add docs/api/openapi.json"
  exit 1
fi

echo "OK: openapi.json is up to date."
exit 0
HOOK

chmod +x "$HOOKS_SRC/pre-commit"
cp "$HOOKS_SRC/pre-commit" "$HOOKS_DST/pre-commit"
echo "Installed: .git/hooks/pre-commit"
