#!/usr/bin/env python3
"""
Run the FastAPI web UI for the Tax Preparation Agent.
"""

import os
import subprocess
import sys


def _run_preflight_if_production(repo_root: str) -> None:
    """Fail fast on production launch misconfiguration."""
    env = os.getenv("APP_ENVIRONMENT", "development").lower()
    if env not in {"production", "prod", "staging"}:
        return

    preflight_script = os.path.join(repo_root, "scripts", "preflight_launch.py")
    cmd = [sys.executable, preflight_script, "--mode", "production"]
    result = subprocess.run(cmd, cwd=repo_root)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> None:
    # Make src importable
    repo_root = os.path.dirname(__file__)
    sys.path.insert(0, os.path.join(repo_root, "src"))
    _run_preflight_if_production(repo_root)

    import uvicorn

    uvicorn.run(
        "web.app:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )


if __name__ == "__main__":
    main()
