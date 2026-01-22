#!/usr/bin/env python3
"""
Initialize database with base schema before running migrations.

This creates the session_states, document_processing, and session_tax_returns
tables if they don't exist.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.session_persistence import get_session_persistence

def main():
    print("Initializing database...")
    print(f"Database path: {project_root / 'tax_filing.db'}")

    # This will create base tables if they don't exist
    persistence = get_session_persistence()

    print("✅ Database initialized successfully!")
    print("\nBase tables created:")
    print("  - session_states")
    print("  - document_processing")
    print("  - session_tax_returns")
    print("\nYou can now run migrations with:")
    print("  python3 migrations/run_migration.py")

if __name__ == "__main__":
    main()
