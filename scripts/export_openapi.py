#!/usr/bin/env python3
"""
Export the FastAPI OpenAPI schema to docs/api/openapi.json.

Usage:
    python scripts/export_openapi.py

The script imports the FastAPI app, generates the OpenAPI schema, and writes
it to docs/api/openapi.json.  Run this whenever routes or Pydantic models
change, and commit the updated file alongside your code.

CI / pre-commit usage:
    The pre-commit hook at .git/hooks/pre-commit runs this script and fails if
    the committed openapi.json differs from the freshly generated one.
"""
import json
import sys
from pathlib import Path

# Ensure the src directory is on sys.path so the app can be imported.
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

OUT_PATH = ROOT / "docs" / "api" / "openapi.json"


def main() -> int:
    print("Importing FastAPI app …")
    try:
        # Set a minimal env so the app starts without external services
        import os
        os.environ.setdefault("APP_ENVIRONMENT", "development")
        os.environ.setdefault("JWT_SECRET", "export-script-placeholder-secret-32ch")
        os.environ.setdefault("ENCRYPTION_KEY", "export-script-placeholder-key-32chars!")
        os.environ.setdefault("APP_SECRET_KEY", "export-script-placeholder-appkey-32!")

        from web.app import app
    except Exception as exc:
        print(f"ERROR: Failed to import app: {exc}", file=sys.stderr)
        return 1

    print("Generating OpenAPI schema …")
    try:
        schema = app.openapi()
    except Exception as exc:
        print(f"ERROR: Failed to generate schema: {exc}", file=sys.stderr)
        return 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Written: {OUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
