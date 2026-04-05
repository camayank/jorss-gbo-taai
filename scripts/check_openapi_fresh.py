#!/usr/bin/env python3
"""
Pre-commit check: fail if docs/api/openapi.json is stale.

Used by the pre-commit hook at .git/hooks/pre-commit.
Also callable standalone:

    python scripts/check_openapi_fresh.py

Exit codes:
  0 — openapi.json is up to date
  1 — openapi.json is missing or out of date (regenerate with export_openapi.py)
"""
import json
import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = ROOT / "docs" / "api" / "openapi.json"


def _regenerate() -> dict:
    """Run export_openapi.py in a subprocess and return the freshly generated schema."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export_openapi.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        print("ERROR: export_openapi.py failed:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def main() -> int:
    if not SPEC_PATH.exists():
        print(f"FAIL: {SPEC_PATH.relative_to(ROOT)} does not exist.", file=sys.stderr)
        print("Run: python scripts/export_openapi.py", file=sys.stderr)
        return 1

    committed = json.loads(SPEC_PATH.read_text(encoding="utf-8"))

    # Generate a fresh copy into a temp file by calling the export script
    import tempfile, shutil
    tmp_dir = Path(tempfile.mkdtemp())
    tmp_spec = tmp_dir / "openapi.json"
    try:
        # Temporarily redirect output to tmp
        backup = None
        if SPEC_PATH.exists():
            backup = SPEC_PATH.read_bytes()

        # Re-generate into the real path, then compare
        fresh = _regenerate()

        if json.dumps(committed, sort_keys=True) == json.dumps(fresh, sort_keys=True):
            print("OK: docs/api/openapi.json is up to date.")
            return 0
        else:
            print("FAIL: docs/api/openapi.json is stale.", file=sys.stderr)
            print("Run: python scripts/export_openapi.py && git add docs/api/openapi.json", file=sys.stderr)
            # Restore original so we don't leave dirty working tree
            if backup is not None:
                SPEC_PATH.write_bytes(backup)
            return 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
