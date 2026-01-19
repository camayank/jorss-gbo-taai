#!/usr/bin/env python3
"""
Setup CA4CPA GLOBAL LLC Platform Admin

This script creates the PLATFORM ADMIN (super admin) for CA4CPA GLOBAL LLC,
the company that OWNS and OPERATES the tax platform.

Platform Admins can:
- Manage all CPA firms (customers)
- Configure subscriptions and billing
- Manage feature flags
- View system health and metrics
- Impersonate firms for support

This is DIFFERENT from Firm Admins who are customers of the platform.
"""

import os
import sys
import sqlite3
import uuid
import hashlib
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "database", "jorss_gbo.db")

# CA4CPA GLOBAL LLC Platform Admin Configuration
PLATFORM_ADMIN = {
    "admin_id": str(uuid.uuid4()),
    "email": "admin@ca4cpa.com",
    "name": "CA4CPA Platform Admin",
    "password": "CA4CPA2026!",  # Change on first login
    "role": "super_admin",
    "department": "Platform Operations",
    "mfa_enabled": False,  # Enable after first login
}

# Platform Branding for CA4CPA GLOBAL LLC
PLATFORM_CONFIG = {
    "platform_name": "CA4CPA GLOBAL Tax Platform",
    "company_name": "CA4CPA GLOBAL LLC",
    "primary_color": "#1e40af",  # Navy Blue
    "secondary_color": "#3b82f6",  # Bright Blue
    "support_email": "support@ca4cpa.com",
    "sales_email": "sales@ca4cpa.com",
}


def hash_password(password: str) -> str:
    """Create a password hash."""
    return hashlib.sha256(password.encode()).hexdigest()


def create_platform_admin_table(conn: sqlite3.Connection):
    """Create platform_admins table if not exists."""
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS platform_admins (
            admin_id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            avatar_url TEXT,
            department TEXT,
            role TEXT DEFAULT 'support',
            custom_permissions TEXT,
            mfa_enabled INTEGER DEFAULT 0,
            mfa_secret TEXT,
            mfa_backup_codes TEXT,
            failed_login_attempts INTEGER DEFAULT 0,
            locked_until TEXT,
            password_changed_at TEXT,
            is_active INTEGER DEFAULT 1,
            deactivated_at TEXT,
            deactivated_reason TEXT,
            last_login_at TEXT,
            last_login_ip TEXT,
            last_activity_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT
        )
    """)

    # Platform config table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS platform_config (
            config_key TEXT PRIMARY KEY,
            config_value TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        )
    """)

    conn.commit()
    print("✓ Platform admin tables created/verified")


def setup_platform_admin(conn: sqlite3.Connection):
    """Create the CA4CPA Platform Admin."""
    cursor = conn.cursor()

    # Check if platform admin already exists
    cursor.execute("SELECT admin_id FROM platform_admins WHERE email = ?", (PLATFORM_ADMIN["email"],))
    existing = cursor.fetchone()

    if existing:
        print(f"⚠️  Platform Admin '{PLATFORM_ADMIN['email']}' already exists")
        print(f"   Admin ID: {existing[0]}")
        return existing[0]

    now = datetime.utcnow().isoformat()

    cursor.execute("""
        INSERT INTO platform_admins (
            admin_id, email, password_hash, name, department, role,
            mfa_enabled, is_active, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        PLATFORM_ADMIN["admin_id"],
        PLATFORM_ADMIN["email"],
        hash_password(PLATFORM_ADMIN["password"]),
        PLATFORM_ADMIN["name"],
        PLATFORM_ADMIN["department"],
        PLATFORM_ADMIN["role"],
        1 if PLATFORM_ADMIN["mfa_enabled"] else 0,
        1,
        now,
        now,
    ))

    conn.commit()
    print(f"✓ Created Platform Admin: {PLATFORM_ADMIN['email']}")
    print(f"  Admin ID: {PLATFORM_ADMIN['admin_id']}")
    print(f"  Role: {PLATFORM_ADMIN['role']} (full platform access)")

    return PLATFORM_ADMIN["admin_id"]


def setup_platform_config(conn: sqlite3.Connection, admin_id: str):
    """Configure platform branding and settings."""
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()

    for key, value in PLATFORM_CONFIG.items():
        cursor.execute("""
            INSERT OR REPLACE INTO platform_config (config_key, config_value, updated_at, updated_by)
            VALUES (?, ?, ?, ?)
        """, (key, value, now, admin_id))

    conn.commit()
    print("✓ Platform configuration saved")
    print(f"  Platform: {PLATFORM_CONFIG['platform_name']}")
    print(f"  Company: {PLATFORM_CONFIG['company_name']}")
    print(f"  Primary Color: {PLATFORM_CONFIG['primary_color']}")


def show_summary(conn: sqlite3.Connection):
    """Show setup summary."""
    cursor = conn.cursor()

    # Count platform admins
    cursor.execute("SELECT COUNT(*) FROM platform_admins WHERE is_active = 1")
    admin_count = cursor.fetchone()[0]

    # Get platform name
    cursor.execute("SELECT config_value FROM platform_config WHERE config_key = 'platform_name'")
    row = cursor.fetchone()
    platform_name = row[0] if row else "Tax Platform"

    print()
    print("=" * 60)
    print("CA4CPA GLOBAL LLC - PLATFORM ADMIN SETUP COMPLETE")
    print("=" * 60)
    print()
    print("  YOU ARE THE PLATFORM OWNER")
    print("  ─────────────────────────")
    print(f"  Platform: {platform_name}")
    print(f"  Company: CA4CPA GLOBAL LLC")
    print(f"  Platform Admins: {admin_count}")
    print()
    print("  Platform Admin Login:")
    print("    Email:    admin@ca4cpa.com")
    print("    Password: CA4CPA2026!")
    print("    Role:     super_admin (FULL ACCESS)")
    print()
    print("  Your Platform Admin Can:")
    print("    ✓ Manage all CPA firms (your customers)")
    print("    ✓ View platform-wide metrics & MRR")
    print("    ✓ Configure subscriptions & billing")
    print("    ✓ Manage feature flags & rollouts")
    print("    ✓ View system health & errors")
    print("    ✓ Impersonate firms for support")
    print("    ✓ Create white-label partners")
    print()
    print("  Access URLs:")
    print("    Platform Admin:  http://localhost:8000/admin")
    print("    API Docs:        http://localhost:8000/docs")
    print("    System Hub:      http://localhost:8000/hub")
    print()
    print("  CPA Firms (Your Customers):")
    print("    CPA Dashboard:   http://localhost:8000/cpa")
    print("    Client Portal:   http://localhost:8000/client")
    print()
    print("  Next Steps:")
    print("    1. Log into /admin as Platform Admin")
    print("    2. Create your first CPA firm (customer)")
    print("    3. Configure subscription tiers")
    print("    4. Onboard your first CPA client")
    print()


def main():
    print()
    print("=" * 60)
    print("CA4CPA GLOBAL LLC - PLATFORM ADMIN SETUP")
    print("=" * 60)
    print()
    print("  CA4CPA GLOBAL LLC is the PLATFORM OWNER")
    print("  This creates YOUR admin access to manage the platform")
    print()
    print("  Platform Admins ≠ Firm Admins")
    print("  ─────────────────────────────")
    print("  Platform Admin: YOU (CA4CPA) - manage entire platform")
    print("  Firm Admins:    Your CUSTOMERS - manage their own firm")
    print()

    # Connect to database
    print(f"Connecting to database: {DB_PATH}")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    # Create tables
    print("\nCreating platform admin tables...")
    create_platform_admin_table(conn)

    # Setup platform admin
    print("\nCreating CA4CPA Platform Admin...")
    admin_id = setup_platform_admin(conn)

    # Setup platform config
    print("\nConfiguring platform branding...")
    setup_platform_config(conn, admin_id)

    # Show summary
    show_summary(conn)

    conn.close()


if __name__ == "__main__":
    main()
