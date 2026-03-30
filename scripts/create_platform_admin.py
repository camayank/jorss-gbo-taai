#!/usr/bin/env python3
"""
Create or reset a platform admin account.

Usage:
    PYTHONPATH=src python3 scripts/create_platform_admin.py

Reads DATABASE_URL from environment (or .env.production if present).
Uses bcrypt via the app's own password hasher.
"""

import os
import sys
import getpass
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: load .env.production if DATABASE_URL not already set
# ---------------------------------------------------------------------------
if not os.environ.get("DATABASE_URL"):
    env_file = Path(__file__).resolve().parent.parent / ".env.production"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().split(" #")[0].strip()
            os.environ.setdefault(key, value)

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL is not set. Export it or populate .env.production.")
    sys.exit(1)

if "sqlite" in DATABASE_URL.lower():
    print("ERROR: DATABASE_URL points to SQLite. This script requires PostgreSQL.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Ensure src/ is on the path so app modules resolve
# ---------------------------------------------------------------------------
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# ---------------------------------------------------------------------------
# Imports (after path setup)
# ---------------------------------------------------------------------------
try:
    from admin_panel.auth.password import hash_password, validate_password_strength
except ImportError as exc:
    print(f"ERROR: Could not import password hasher — {exc}")
    print("Make sure PYTHONPATH includes src/ or run with: PYTHONPATH=src python3 scripts/create_platform_admin.py")
    sys.exit(1)

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def prompt_email() -> str:
    while True:
        email = input("Admin email: ").strip().lower()
        if "@" in email and "." in email.split("@")[-1]:
            return email
        print("  Invalid email address, try again.")


def prompt_name() -> str:
    while True:
        name = input("Full name: ").strip()
        if name:
            return name
        print("  Name cannot be empty.")


def prompt_password() -> str:
    while True:
        password = getpass.getpass("Password: ")
        errors = validate_password_strength(password)
        if errors:
            print("  Password does not meet requirements:")
            for err in errors:
                print(f"    - {err}")
            continue
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("  Passwords do not match, try again.")
            continue
        return password


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print()
    print("=== AI Tax Advisor — Platform Admin Setup ===")
    print(f"  Database: {DATABASE_URL.split('@')[-1]}")
    print()

    email = prompt_email()

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT admin_id, email, role, is_active FROM platform_admins WHERE email = %s",
                (email,),
            )
            existing = cur.fetchone()

        if existing:
            print()
            print(f"  Admin already exists: {existing['email']} (role={existing['role']}, active={existing['is_active']})")
            answer = input("Reset password? (y/n): ").strip().lower()
            if answer != "y":
                print("Aborted.")
                return

            new_password = prompt_password()
            hashed = hash_password(new_password)

            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE platform_admins SET password_hash = %s, password_changed_at = NOW(), updated_at = NOW() WHERE email = %s",
                    (hashed, email),
                )
            conn.commit()
            print()
            print(f"✓ Password reset for platform admin: {email}")

        else:
            name = prompt_name()
            print()
            print("  Role options: super_admin, support, billing, compliance, engineering")
            role = input("  Role [super_admin]: ").strip().lower() or "super_admin"
            valid_roles = {"super_admin", "support", "billing", "compliance", "engineering"}
            if role not in valid_roles:
                print(f"ERROR: '{role}' is not a valid role. Choose from: {', '.join(sorted(valid_roles))}")
                return

            new_password = prompt_password()
            hashed = hash_password(new_password)

            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO platform_admins
                        (email, password_hash, name, role, is_active, mfa_enabled, created_at, updated_at)
                    VALUES
                        (%s, %s, %s, %s, true, false, NOW(), NOW())
                    """,
                    (email, hashed, name, role),
                )
            conn.commit()
            print()
            print(f"✓ Platform admin created: {email}  (role={role})")

    except psycopg2.errors.UndefinedTable:
        conn.rollback()
        print()
        print("ERROR: Table 'platform_admins' does not exist.")
        print("Run migrations first: ./migrate.sh")
        sys.exit(1)
    except Exception as exc:
        conn.rollback()
        print(f"\nERROR: {exc}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
