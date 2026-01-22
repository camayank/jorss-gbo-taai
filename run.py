#!/usr/bin/env python3
"""
Tax Filing Platform - Development Server Runner
This script properly sets up the Python path and starts the server
"""

import sys
import os

# Add the 'src' directory to Python path so imports work correctly
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')

# Insert at beginning of path
if src_path not in sys.path:
    sys.path.insert(0, src_path)

print("=" * 50)
print("Tax Filing Platform - Development Server")
print("=" * 50)
print(f"✓ Project root: {project_root}")
print(f"✓ Python path configured: {src_path}")
print(f"✓ Python version: {sys.version}")
print("=" * 50)
print()

# Now import and run uvicorn
if __name__ == "__main__":
    import uvicorn

    print("Starting server on http://127.0.0.1:8000")
    print("Press Ctrl+C to stop")
    print()

    # Run the server
    uvicorn.run(
        "web.app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=[src_path],
        log_level="info"
    )
