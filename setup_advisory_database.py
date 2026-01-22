#!/usr/bin/env python3
"""
Setup script to create advisory reports database tables.
Run this once to initialize the database for advisory reports.
"""

from sqlalchemy import create_engine
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from database.advisory_models import Base

def setup_advisory_database():
    """Create advisory reports tables in the database."""

    # Database path
    db_path = Path(__file__).parent / "data" / "tax_returns.db"

    # Create engine
    engine = create_engine(f"sqlite:///{db_path}")

    print(f"Creating advisory reports tables in: {db_path}")

    # Create all tables defined in advisory_models.py
    Base.metadata.create_all(engine)

    print("✅ Advisory reports tables created successfully!")
    print("\nTables created:")
    print("  - advisory_reports")
    print("  - report_sections (if defined)")

    # Verify tables were created
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    if "advisory_reports" in tables:
        print("\n✅ Verification: advisory_reports table exists")

        # Show columns
        columns = inspector.get_columns("advisory_reports")
        print(f"\nColumns ({len(columns)} total):")
        for col in columns[:10]:  # Show first 10
            print(f"  - {col['name']}: {col['type']}")
        if len(columns) > 10:
            print(f"  ... and {len(columns) - 10} more columns")
    else:
        print("\n❌ Error: advisory_reports table was not created")
        return False

    return True


if __name__ == "__main__":
    try:
        success = setup_advisory_database()

        if success:
            print("\n🎉 Database setup complete!")
            print("\nNext steps:")
            print("1. Restart your server (if running)")
            print("2. Test advisory report generation at: http://127.0.0.1:8000/file")
            print("3. Click 'Generate Professional Report' after completing tax return")
            sys.exit(0)
        else:
            print("\n❌ Database setup failed!")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
