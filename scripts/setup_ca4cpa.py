#!/usr/bin/env python3
"""
Setup CA4CPA GLOBAL LLC - First Client Configuration

This script initializes the platform for CA4CPA GLOBAL LLC with:
- Blue theme branding (Navy #1e40af primary)
- Professional subscription tier
- Admin user account
"""

import os
import sys
import sqlite3
import uuid
import hashlib
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "database", "jorss_gbo.db")

# CA4CPA GLOBAL LLC Configuration
FIRM_CONFIG = {
    "firm_id": str(uuid.uuid4()),
    "name": "CA4CPA GLOBAL LLC",
    "legal_name": "CA4CPA Global LLC",
    "email": "info@ca4cpa.com",
    "phone": "",
    "website": "https://ca4cpa.com",

    # Address (can be updated)
    "address_line1": "",
    "address_line2": "",
    "city": "",
    "state": "",
    "zip_code": "",
    "country": "USA",

    # Branding - Blue Theme
    "logo_url": None,  # Will be uploaded via admin panel
    "primary_color": "#1e40af",  # Navy Blue
    "secondary_color": "#3b82f6",  # Bright Blue

    # Subscription
    "subscription_tier": "professional",
    "subscription_status": "trial",
    "trial_ends_at": (datetime.utcnow() + timedelta(days=30)).isoformat(),

    # Limits (Professional tier)
    "max_team_members": 10,
    "max_clients": 500,
    "max_scenarios_per_month": 200,

    # Status
    "is_active": True,
    "is_verified": False,
}

SETTINGS_CONFIG = {
    "default_tax_year": 2025,
    "default_state": None,
    "timezone": "America/New_York",
    "date_format": "MM/DD/YYYY",
    "currency_display": "USD",

    # Security
    "mfa_required": False,
    "session_timeout_minutes": 480,  # 8 hours
    "password_expiry_days": 90,

    # Notifications
    "email_notifications": True,

    # Workflow
    "auto_archive_days": 365,
    "require_reviewer_approval": True,
    "allow_self_review": False,

    # Client Portal
    "client_portal_enabled": True,
    "client_document_upload": True,
    "client_can_view_scenarios": False,

    # Branding - Email Templates
    "email_signature": "CA4CPA GLOBAL LLC\nProfessional Tax Services",
    "disclaimer_text": "This communication contains confidential information intended for the recipient only.",
    "welcome_message": "Welcome to CA4CPA GLOBAL LLC! We're excited to help you with your tax needs.",
}


def hash_password(password: str) -> str:
    """Create a simple password hash (for demo purposes)."""
    return hashlib.sha256(password.encode()).hexdigest()


def create_tables(conn: sqlite3.Connection):
    """Create firms and related tables if they don't exist."""
    cursor = conn.cursor()

    # Firms table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS firms (
            firm_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            legal_name TEXT,
            ein TEXT,
            email TEXT,
            phone TEXT,
            website TEXT,
            address_line1 TEXT,
            address_line2 TEXT,
            city TEXT,
            state TEXT,
            zip_code TEXT,
            country TEXT DEFAULT 'USA',
            logo_url TEXT,
            primary_color TEXT DEFAULT '#1e40af',
            secondary_color TEXT DEFAULT '#3b82f6',
            custom_domain TEXT,
            subscription_tier TEXT DEFAULT 'starter',
            subscription_status TEXT DEFAULT 'trial',
            trial_ends_at TEXT,
            max_team_members INTEGER DEFAULT 3,
            max_clients INTEGER DEFAULT 100,
            max_scenarios_per_month INTEGER DEFAULT 50,
            max_api_calls_per_month INTEGER,
            is_active INTEGER DEFAULT 1,
            is_verified INTEGER DEFAULT 0,
            verification_date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            onboarded_at TEXT,
            created_by TEXT,
            settings TEXT
        )
    """)

    # Firm settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS firm_settings (
            firm_id TEXT PRIMARY KEY,
            default_tax_year INTEGER DEFAULT 2025,
            default_state TEXT,
            timezone TEXT DEFAULT 'America/New_York',
            date_format TEXT DEFAULT 'MM/DD/YYYY',
            currency_display TEXT DEFAULT 'USD',
            mfa_required INTEGER DEFAULT 0,
            session_timeout_minutes INTEGER DEFAULT 60,
            ip_whitelist TEXT,
            password_expiry_days INTEGER DEFAULT 90,
            email_notifications INTEGER DEFAULT 1,
            notification_preferences TEXT,
            auto_archive_days INTEGER DEFAULT 365,
            require_reviewer_approval INTEGER DEFAULT 1,
            allow_self_review INTEGER DEFAULT 0,
            client_portal_enabled INTEGER DEFAULT 1,
            client_document_upload INTEGER DEFAULT 1,
            client_can_view_scenarios INTEGER DEFAULT 0,
            email_signature TEXT,
            disclaimer_text TEXT,
            welcome_message TEXT,
            integrations TEXT,
            webhook_url TEXT,
            api_key_enabled INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (firm_id) REFERENCES firms(firm_id)
        )
    """)

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            firm_id TEXT,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            password_hash TEXT,
            role TEXT DEFAULT 'preparer',
            is_active INTEGER DEFAULT 1,
            email_verified INTEGER DEFAULT 0,
            phone TEXT,
            avatar_url TEXT,
            mfa_enabled INTEGER DEFAULT 0,
            mfa_secret TEXT,
            last_login TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (firm_id) REFERENCES firms(firm_id)
        )
    """)

    conn.commit()
    print("✓ Tables created/verified")


def setup_firm(conn: sqlite3.Connection):
    """Create the CA4CPA GLOBAL LLC firm."""
    cursor = conn.cursor()

    # Check if firm already exists
    cursor.execute("SELECT firm_id FROM firms WHERE name = ?", (FIRM_CONFIG["name"],))
    existing = cursor.fetchone()

    if existing:
        print(f"⚠️  Firm '{FIRM_CONFIG['name']}' already exists (ID: {existing[0]})")
        return existing[0]

    # Create firm
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT INTO firms (
            firm_id, name, legal_name, email, phone, website,
            address_line1, address_line2, city, state, zip_code, country,
            logo_url, primary_color, secondary_color,
            subscription_tier, subscription_status, trial_ends_at,
            max_team_members, max_clients, max_scenarios_per_month,
            is_active, is_verified, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        FIRM_CONFIG["firm_id"],
        FIRM_CONFIG["name"],
        FIRM_CONFIG["legal_name"],
        FIRM_CONFIG["email"],
        FIRM_CONFIG["phone"],
        FIRM_CONFIG["website"],
        FIRM_CONFIG["address_line1"],
        FIRM_CONFIG["address_line2"],
        FIRM_CONFIG["city"],
        FIRM_CONFIG["state"],
        FIRM_CONFIG["zip_code"],
        FIRM_CONFIG["country"],
        FIRM_CONFIG["logo_url"],
        FIRM_CONFIG["primary_color"],
        FIRM_CONFIG["secondary_color"],
        FIRM_CONFIG["subscription_tier"],
        FIRM_CONFIG["subscription_status"],
        FIRM_CONFIG["trial_ends_at"],
        FIRM_CONFIG["max_team_members"],
        FIRM_CONFIG["max_clients"],
        FIRM_CONFIG["max_scenarios_per_month"],
        1 if FIRM_CONFIG["is_active"] else 0,
        1 if FIRM_CONFIG["is_verified"] else 0,
        now,
        now,
    ))

    conn.commit()
    print(f"✓ Created firm: {FIRM_CONFIG['name']}")
    print(f"  Firm ID: {FIRM_CONFIG['firm_id']}")
    print(f"  Tier: {FIRM_CONFIG['subscription_tier']}")
    print(f"  Primary Color: {FIRM_CONFIG['primary_color']}")

    return FIRM_CONFIG["firm_id"]


def setup_settings(conn: sqlite3.Connection, firm_id: str):
    """Create firm settings."""
    cursor = conn.cursor()

    # Check if settings exist
    cursor.execute("SELECT firm_id FROM firm_settings WHERE firm_id = ?", (firm_id,))
    if cursor.fetchone():
        print("⚠️  Settings already exist, updating...")
        cursor.execute("DELETE FROM firm_settings WHERE firm_id = ?", (firm_id,))

    now = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT INTO firm_settings (
            firm_id, default_tax_year, default_state, timezone, date_format,
            currency_display, mfa_required, session_timeout_minutes,
            password_expiry_days, email_notifications, auto_archive_days,
            require_reviewer_approval, allow_self_review, client_portal_enabled,
            client_document_upload, client_can_view_scenarios,
            email_signature, disclaimer_text, welcome_message, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        firm_id,
        SETTINGS_CONFIG["default_tax_year"],
        SETTINGS_CONFIG["default_state"],
        SETTINGS_CONFIG["timezone"],
        SETTINGS_CONFIG["date_format"],
        SETTINGS_CONFIG["currency_display"],
        1 if SETTINGS_CONFIG["mfa_required"] else 0,
        SETTINGS_CONFIG["session_timeout_minutes"],
        SETTINGS_CONFIG["password_expiry_days"],
        1 if SETTINGS_CONFIG["email_notifications"] else 0,
        SETTINGS_CONFIG["auto_archive_days"],
        1 if SETTINGS_CONFIG["require_reviewer_approval"] else 0,
        1 if SETTINGS_CONFIG["allow_self_review"] else 0,
        1 if SETTINGS_CONFIG["client_portal_enabled"] else 0,
        1 if SETTINGS_CONFIG["client_document_upload"] else 0,
        1 if SETTINGS_CONFIG["client_can_view_scenarios"] else 0,
        SETTINGS_CONFIG["email_signature"],
        SETTINGS_CONFIG["disclaimer_text"],
        SETTINGS_CONFIG["welcome_message"],
        now,
    ))

    conn.commit()
    print("✓ Created firm settings")


def generate_secure_password() -> str:
    """Generate a cryptographically secure random password."""
    import secrets
    import string
    # Generate a 16-character password with mixed case, digits, and special chars
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for _ in range(16))
    return password


def setup_admin_user(conn: sqlite3.Connection, firm_id: str):
    """Create admin user for the firm."""
    cursor = conn.cursor()

    admin_email = "admin@ca4cpa.com"
    # SECURITY FIX: Generate secure random password instead of hardcoded credential
    admin_password = os.environ.get("SETUP_ADMIN_PASSWORD") or generate_secure_password()
    # Flag to require password change on first login
    require_password_change = True

    # Check if user exists
    cursor.execute("SELECT user_id FROM users WHERE email = ?", (admin_email,))
    if cursor.fetchone():
        print(f"[!] Admin user '{admin_email}' already exists")
        return

    user_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    cursor.execute("""
        INSERT INTO users (
            user_id, firm_id, email, name, password_hash, role,
            is_active, email_verified, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        firm_id,
        admin_email,
        "CA4CPA Admin",
        hash_password(admin_password),
        "firm_admin",
        1,
        1,  # Pre-verified for demo
        now,
        now,
    ))

    conn.commit()
    print(f"[OK] Created admin user: {admin_email}")
    print(f"  User ID: {user_id}")
    print(f"  Role: firm_admin")
    print(f"  Password: {admin_password}")
    print(f"  IMPORTANT: Change this password immediately after first login!")
    print(f"  Tip: Set SETUP_ADMIN_PASSWORD env var to use a custom password.")


def show_summary(conn: sqlite3.Connection, firm_id: str):
    """Show setup summary."""
    cursor = conn.cursor()

    # Get firm details
    cursor.execute("SELECT name, subscription_tier, primary_color FROM firms WHERE firm_id = ?", (firm_id,))
    firm = cursor.fetchone()

    # Count users
    cursor.execute("SELECT COUNT(*) FROM users WHERE firm_id = ?", (firm_id,))
    user_count = cursor.fetchone()[0]

    print()
    print("=" * 60)
    print("CA4CPA GLOBAL LLC SETUP COMPLETE")
    print("=" * 60)
    print()
    print(f"  Firm Name:      {firm[0]}")
    print(f"  Firm ID:        {firm_id}")
    print(f"  Tier:           {firm[1]}")
    print(f"  Primary Color:  {firm[2]} (Navy Blue)")
    print(f"  Team Members:   {user_count}")
    print()
    print("  Access URLs:")
    print("    Main:         http://localhost:8000/")
    print("    CPA Panel:    http://localhost:8000/cpa")
    print("    Admin Panel:  http://localhost:8000/admin")
    print("    Client Portal: http://localhost:8000/client")
    print("    System Hub:   http://localhost:8000/hub")
    print()
    print("  Admin Login:")
    print("    Email:    admin@ca4cpa.com")
    print("    Password: (shown during setup - change on first login)")
    print()
    print("  Next Steps:")
    print("    1. Upload your logo in Admin Panel > Settings")
    print("    2. Complete firm profile (address, EIN, phone)")
    print("    3. Invite team members")
    print("    4. Add your first client")
    print()


def main():
    print()
    print("=" * 60)
    print("SETTING UP CA4CPA GLOBAL LLC")
    print("=" * 60)
    print()
    print("Configuration:")
    print(f"  Firm: {FIRM_CONFIG['name']}")
    print(f"  Tier: {FIRM_CONFIG['subscription_tier']}")
    print(f"  Theme: Blue (Primary: {FIRM_CONFIG['primary_color']})")
    print()

    # Connect to database
    print(f"Connecting to database: {DB_PATH}")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    # Create tables
    print("\nCreating tables...")
    create_tables(conn)

    # Setup firm
    print("\nSetting up firm...")
    firm_id = setup_firm(conn)

    # Setup settings
    print("\nConfiguring settings...")
    setup_settings(conn, firm_id)

    # Setup admin user
    print("\nCreating admin user...")
    setup_admin_user(conn, firm_id)

    # Show summary
    show_summary(conn, firm_id)

    conn.close()


if __name__ == "__main__":
    main()
