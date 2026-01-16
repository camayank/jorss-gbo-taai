#!/usr/bin/env python3
"""
Run the FastAPI web UI for the Tax Preparation Agent.
"""

import os
import sys


def main() -> None:
    # Make src importable
    repo_root = os.path.dirname(__file__)
    sys.path.insert(0, os.path.join(repo_root, "src"))

    import uvicorn

    uvicorn.run(
        "web.app:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )


if __name__ == "__main__":
    main()

