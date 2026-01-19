"""
CA4CPA GLOBAL LLC - RBAC Database Seeding

Seeds the database with roles and permissions.

Usage:
    python -m rbac.seed
"""

import sqlite3
import os
from datetime import datetime
from uuid import uuid4

from .roles import Role, ROLES
from .permissions import Permission, PERMISSIONS, ROLE_PERMISSIONS, Category


# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "jorss_gbo.db")


def create_rbac_tables(conn: sqlite3.Connection):
    """Create RBAC tables if they don't exist."""
    cursor = conn.cursor()

    # Roles table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rbac_roles (
            role_id TEXT PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            level INTEGER NOT NULL,
            is_platform INTEGER DEFAULT 0,
            is_firm INTEGER DEFAULT 0,
            is_client INTEGER DEFAULT 0,
            can_impersonate INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Permissions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rbac_permissions (
            permission_id TEXT PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Role-Permission mapping table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rbac_role_permissions (
            role_id TEXT NOT NULL,
            permission_id TEXT NOT NULL,
            granted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (role_id, permission_id),
            FOREIGN KEY (role_id) REFERENCES rbac_roles(role_id),
            FOREIGN KEY (permission_id) REFERENCES rbac_permissions(permission_id)
        )
    """)

    # User-Role assignment table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rbac_user_roles (
            user_id TEXT NOT NULL,
            role_id TEXT NOT NULL,
            assigned_at TEXT DEFAULT CURRENT_TIMESTAMP,
            assigned_by TEXT,
            expires_at TEXT,
            is_primary INTEGER DEFAULT 1,
            PRIMARY KEY (user_id, role_id),
            FOREIGN KEY (role_id) REFERENCES rbac_roles(role_id)
        )
    """)

    conn.commit()
    print("✓ RBAC tables created/verified")


def seed_roles(conn: sqlite3.Connection):
    """Seed all 8 roles into the database."""
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()

    for role, info in ROLES.items():
        role_id = str(uuid4())

        # Check if role already exists
        cursor.execute("SELECT role_id FROM rbac_roles WHERE code = ?", (role.value,))
        existing = cursor.fetchone()

        if existing:
            # Update existing role
            cursor.execute("""
                UPDATE rbac_roles SET
                    name = ?,
                    description = ?,
                    level = ?,
                    is_platform = ?,
                    is_firm = ?,
                    is_client = ?,
                    can_impersonate = ?,
                    updated_at = ?
                WHERE code = ?
            """, (
                info.name,
                info.description,
                info.level.value,
                1 if info.is_platform else 0,
                1 if info.is_firm else 0,
                1 if info.is_client else 0,
                1 if info.can_impersonate else 0,
                now,
                role.value,
            ))
            print(f"  ↻ Updated role: {role.value}")
        else:
            # Insert new role
            cursor.execute("""
                INSERT INTO rbac_roles (
                    role_id, code, name, description, level,
                    is_platform, is_firm, is_client, can_impersonate,
                    is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                role_id,
                role.value,
                info.name,
                info.description,
                info.level.value,
                1 if info.is_platform else 0,
                1 if info.is_firm else 0,
                1 if info.is_client else 0,
                1 if info.can_impersonate else 0,
                1,
                now,
                now,
            ))
            print(f"  + Added role: {role.value}")

    conn.commit()
    print(f"✓ Seeded {len(ROLES)} roles")


def seed_permissions(conn: sqlite3.Connection):
    """Seed all permissions into the database."""
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()

    for perm, info in PERMISSIONS.items():
        perm_id = str(uuid4())

        # Check if permission already exists
        cursor.execute("SELECT permission_id FROM rbac_permissions WHERE code = ?", (perm.value,))
        existing = cursor.fetchone()

        if existing:
            # Update existing permission
            cursor.execute("""
                UPDATE rbac_permissions SET
                    name = ?,
                    description = ?,
                    category = ?,
                    updated_at = ?
                WHERE code = ?
            """, (
                info.name,
                info.description,
                info.category.value,
                now,
                perm.value,
            ))
        else:
            # Insert new permission
            cursor.execute("""
                INSERT INTO rbac_permissions (
                    permission_id, code, name, description, category,
                    is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                perm_id,
                perm.value,
                info.name,
                info.description,
                info.category.value,
                1,
                now,
                now,
            ))

    conn.commit()
    print(f"✓ Seeded {len(PERMISSIONS)} permissions")


def seed_role_permissions(conn: sqlite3.Connection):
    """Seed role-permission mappings."""
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()

    # Clear existing mappings
    cursor.execute("DELETE FROM rbac_role_permissions")

    count = 0
    for role, permissions in ROLE_PERMISSIONS.items():
        # Get role_id
        cursor.execute("SELECT role_id FROM rbac_roles WHERE code = ?", (role.value,))
        role_row = cursor.fetchone()
        if not role_row:
            print(f"  ! Role not found: {role.value}")
            continue
        role_id = role_row[0]

        for perm in permissions:
            # Get permission_id
            cursor.execute("SELECT permission_id FROM rbac_permissions WHERE code = ?", (perm.value,))
            perm_row = cursor.fetchone()
            if not perm_row:
                continue
            perm_id = perm_row[0]

            cursor.execute("""
                INSERT OR REPLACE INTO rbac_role_permissions (role_id, permission_id, granted_at)
                VALUES (?, ?, ?)
            """, (role_id, perm_id, now))
            count += 1

    conn.commit()
    print(f"✓ Seeded {count} role-permission mappings")


def show_summary(conn: sqlite3.Connection):
    """Show seeding summary."""
    cursor = conn.cursor()

    # Count roles
    cursor.execute("SELECT COUNT(*) FROM rbac_roles")
    role_count = cursor.fetchone()[0]

    # Count permissions
    cursor.execute("SELECT COUNT(*) FROM rbac_permissions")
    perm_count = cursor.fetchone()[0]

    # Count mappings
    cursor.execute("SELECT COUNT(*) FROM rbac_role_permissions")
    mapping_count = cursor.fetchone()[0]

    print()
    print("=" * 60)
    print("RBAC SEEDING COMPLETE")
    print("=" * 60)
    print()
    print(f"  Roles:       {role_count}")
    print(f"  Permissions: {perm_count}")
    print(f"  Mappings:    {mapping_count}")
    print()

    # Show roles
    print("  Roles:")
    cursor.execute("SELECT code, name, level FROM rbac_roles ORDER BY level, code")
    for row in cursor.fetchall():
        level_name = ["PLATFORM", "FIRM", "CLIENT"][row[2]]
        print(f"    [{level_name}] {row[0]}: {row[1]}")
    print()

    # Show permissions by category
    print("  Permissions by Category:")
    cursor.execute("""
        SELECT category, COUNT(*) FROM rbac_permissions
        GROUP BY category ORDER BY category
    """)
    for row in cursor.fetchall():
        print(f"    {row[0]}: {row[1]}")


def seed_all():
    """Run all seeding operations."""
    print()
    print("=" * 60)
    print("CA4CPA GLOBAL LLC - RBAC SEEDING")
    print("=" * 60)
    print()
    print(f"Database: {DB_PATH}")
    print()

    # Ensure database directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    # Connect to database
    conn = sqlite3.connect(DB_PATH)

    try:
        # Create tables
        print("Creating RBAC tables...")
        create_rbac_tables(conn)

        # Seed roles
        print("\nSeeding roles...")
        seed_roles(conn)

        # Seed permissions
        print("\nSeeding permissions...")
        seed_permissions(conn)

        # Seed role-permission mappings
        print("\nSeeding role-permission mappings...")
        seed_role_permissions(conn)

        # Show summary
        show_summary(conn)

    finally:
        conn.close()


if __name__ == "__main__":
    seed_all()
