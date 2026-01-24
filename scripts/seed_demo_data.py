#!/usr/bin/env python3
"""
Demo Data Seeding Script

Creates demo tenant, CPA profiles, and sample leads for:
1. Sales demonstrations
2. Beta testing
3. Development/testing

Usage:
    python scripts/seed_demo_data.py
    python scripts/seed_demo_data.py --clean  # Remove existing demo data first

Demo Credentials:
    Email: demo@taxadvisor.com
    CPA Slug: demo-cpa
"""

import sys
import os
import sqlite3
import argparse
import uuid
import random
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from typing import List, Dict, Any


def get_db_path() -> str:
    """Get database path."""
    return os.environ.get(
        "DATABASE_PATH",
        str(Path(__file__).parent.parent / "src" / "database" / "jorss_gbo.db")
    )


def get_connection():
    """Get database connection."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


# =============================================================================
# Demo Data Templates
# =============================================================================

DEMO_CPA = {
    "cpa_id": "demo-cpa-001",
    "cpa_slug": "demo-cpa",
    "first_name": "Sarah",
    "last_name": "Mitchell",
    "credentials": "CPA, MST",
    "firm_name": "Mitchell Tax Advisory",
    "email": "demo@taxadvisor.com",
    "phone": "(555) 123-4567",
    "booking_link": "https://calendly.com/demo-cpa",
    "bio": "15+ years helping clients maximize their tax savings. Specializing in small business and self-employed tax optimization.",
    "specialties": '["Small Business", "Self-Employment", "Retirement Planning", "Real Estate"]',
    "tenant_id": "demo-tenant-001",
    "primary_color": "#1e40af",
    "secondary_color": "#3b82f6",
    "accent_color": "#10b981",
}

DEMO_TENANT = {
    "tenant_id": "demo-tenant-001",
    "tenant_name": "Mitchell Tax Advisory",
    "status": "active",
    "subscription_tier": "professional",
    "branding": '{"company_name": "Mitchell Tax Advisory", "logo_url": null, "primary_color": "#1e40af"}',
    "features": '{"lead_magnet": true, "engagement_letters": true, "nurture_sequences": true}',
}

# Sample lead data for realistic demos
SAMPLE_LEADS = [
    {
        "first_name": "Michael",
        "email": "michael.johnson@email.com",
        "phone": "(555) 234-5678",
        "filing_status": "married_jointly",
        "income_range": "100k_150k",
        "complexity": "moderate",
        "lead_score": 85,
        "lead_temperature": "hot",
        "savings_range": "$2,400 - $4,200",
        "engaged": False,
    },
    {
        "first_name": "Jennifer",
        "email": "jennifer.williams@email.com",
        "phone": "(555) 345-6789",
        "filing_status": "single",
        "income_range": "75k_100k",
        "complexity": "simple",
        "lead_score": 72,
        "lead_temperature": "warm",
        "savings_range": "$1,200 - $2,100",
        "engaged": False,
    },
    {
        "first_name": "Robert",
        "email": "robert.brown@email.com",
        "phone": "(555) 456-7890",
        "filing_status": "married_jointly",
        "income_range": "200k_500k",
        "complexity": "complex",
        "lead_score": 92,
        "lead_temperature": "hot",
        "savings_range": "$5,800 - $9,200",
        "engaged": True,
    },
    {
        "first_name": "Emily",
        "email": "emily.davis@email.com",
        "phone": None,
        "filing_status": "head_of_household",
        "income_range": "50k_75k",
        "complexity": "simple",
        "lead_score": 65,
        "lead_temperature": "warm",
        "savings_range": "$800 - $1,500",
        "engaged": False,
    },
    {
        "first_name": "David",
        "email": "david.miller@email.com",
        "phone": "(555) 567-8901",
        "filing_status": "single",
        "income_range": "150k_200k",
        "complexity": "moderate",
        "lead_score": 78,
        "lead_temperature": "warm",
        "savings_range": "$3,200 - $4,800",
        "engaged": True,
    },
    {
        "first_name": "Amanda",
        "email": "amanda.wilson@email.com",
        "phone": "(555) 678-9012",
        "filing_status": "married_jointly",
        "income_range": "over_500k",
        "complexity": "highly_complex",
        "lead_score": 95,
        "lead_temperature": "hot",
        "savings_range": "$12,000 - $18,500",
        "engaged": False,
    },
    {
        "first_name": "Chris",
        "email": "chris.taylor@email.com",
        "phone": None,
        "filing_status": "single",
        "income_range": "under_50k",
        "complexity": "simple",
        "lead_score": 45,
        "lead_temperature": "cold",
        "savings_range": "$300 - $600",
        "engaged": False,
    },
    {
        "first_name": "Jessica",
        "email": "jessica.anderson@email.com",
        "phone": "(555) 789-0123",
        "filing_status": "married_separately",
        "income_range": "100k_150k",
        "complexity": "moderate",
        "lead_score": 70,
        "lead_temperature": "warm",
        "savings_range": "$2,100 - $3,400",
        "engaged": False,
    },
]

SAMPLE_ACTIVITIES = [
    ("lead_created", "Lead created from tax assessment"),
    ("lead_captured", "Contact info captured"),
    ("report_generated", "Tax advisory report generated"),
    ("email_sent", "Welcome email sent"),
]


def clean_demo_data(conn):
    """Remove existing demo data."""
    cursor = conn.cursor()

    print("Cleaning existing demo data...")

    # Delete demo leads
    cursor.execute("DELETE FROM lead_magnet_leads WHERE cpa_id = ?", (DEMO_CPA["cpa_id"],))
    print(f"  Deleted {cursor.rowcount} demo leads")

    # Delete demo activities
    cursor.execute("""
        DELETE FROM lead_activities
        WHERE lead_id IN (
            SELECT lead_id FROM lead_magnet_leads WHERE cpa_id = ?
        )
    """, (DEMO_CPA["cpa_id"],))

    # Delete demo CPA profile
    cursor.execute("DELETE FROM cpa_profiles WHERE cpa_id = ?", (DEMO_CPA["cpa_id"],))
    print(f"  Deleted demo CPA profile")

    # Delete demo tenant
    cursor.execute("DELETE FROM tenants WHERE tenant_id = ?", (DEMO_TENANT["tenant_id"],))
    print(f"  Deleted demo tenant")

    conn.commit()
    print("Demo data cleaned.\n")


def create_demo_tenant(conn):
    """Create demo tenant."""
    cursor = conn.cursor()

    print("Creating demo tenant...")

    try:
        cursor.execute("""
            INSERT INTO tenants (tenant_id, tenant_name, status, subscription_tier, branding, features)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            DEMO_TENANT["tenant_id"],
            DEMO_TENANT["tenant_name"],
            DEMO_TENANT["status"],
            DEMO_TENANT["subscription_tier"],
            DEMO_TENANT["branding"],
            DEMO_TENANT["features"],
        ))
        print(f"  Created tenant: {DEMO_TENANT['tenant_name']}")
    except sqlite3.IntegrityError:
        print(f"  Tenant already exists, skipping")

    conn.commit()


def create_demo_cpa(conn):
    """Create demo CPA profile."""
    cursor = conn.cursor()

    print("Creating demo CPA profile...")

    try:
        cursor.execute("""
            INSERT INTO cpa_profiles (
                cpa_id, cpa_slug, first_name, last_name, credentials,
                firm_name, email, phone, booking_link, bio, specialties,
                tenant_id, primary_color, secondary_color, accent_color
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            DEMO_CPA["cpa_id"],
            DEMO_CPA["cpa_slug"],
            DEMO_CPA["first_name"],
            DEMO_CPA["last_name"],
            DEMO_CPA["credentials"],
            DEMO_CPA["firm_name"],
            DEMO_CPA["email"],
            DEMO_CPA["phone"],
            DEMO_CPA["booking_link"],
            DEMO_CPA["bio"],
            DEMO_CPA["specialties"],
            DEMO_CPA["tenant_id"],
            DEMO_CPA["primary_color"],
            DEMO_CPA["secondary_color"],
            DEMO_CPA["accent_color"],
        ))
        print(f"  Created CPA: {DEMO_CPA['first_name']} {DEMO_CPA['last_name']}")
        print(f"  CPA Slug: {DEMO_CPA['cpa_slug']}")
        print(f"  Lead Magnet URL: /lead-magnet?cpa={DEMO_CPA['cpa_slug']}")
    except sqlite3.IntegrityError:
        print(f"  CPA already exists, skipping")

    conn.commit()


def create_demo_leads(conn):
    """Create sample leads for demo."""
    cursor = conn.cursor()

    print("Creating demo leads...")

    for i, lead_data in enumerate(SAMPLE_LEADS):
        lead_id = f"demo-lead-{uuid.uuid4().hex[:8]}"
        session_id = f"demo-session-{uuid.uuid4().hex[:8]}"

        # Vary creation dates
        days_ago = random.randint(0, 14)
        created_at = datetime.utcnow() - timedelta(days=days_ago, hours=random.randint(0, 23))

        try:
            cursor.execute("""
                INSERT INTO lead_magnet_leads (
                    lead_id, session_id, cpa_id, tenant_id,
                    first_name, email, phone,
                    filing_status, income_range, complexity,
                    lead_score, lead_temperature, savings_range,
                    engaged, engaged_at, converted,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lead_id,
                session_id,
                DEMO_CPA["cpa_id"],
                DEMO_TENANT["tenant_id"],
                lead_data["first_name"],
                lead_data["email"],
                lead_data["phone"],
                lead_data["filing_status"],
                lead_data["income_range"],
                lead_data["complexity"],
                lead_data["lead_score"],
                lead_data["lead_temperature"],
                lead_data["savings_range"],
                lead_data["engaged"],
                created_at.isoformat() if lead_data["engaged"] else None,
                False,
                created_at.isoformat(),
            ))

            # Create activities for this lead
            for activity_type, description in SAMPLE_ACTIVITIES:
                activity_id = f"act-{uuid.uuid4().hex[:12]}"
                cursor.execute("""
                    INSERT INTO lead_activities (
                        activity_id, lead_id, activity_type, actor,
                        description, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    activity_id,
                    lead_id,
                    activity_type,
                    "system",
                    description,
                    created_at.isoformat(),
                ))

            print(f"  Created lead: {lead_data['first_name']} ({lead_data['lead_temperature']}, score: {lead_data['lead_score']})")

        except sqlite3.IntegrityError as e:
            print(f"  Error creating lead {lead_data['first_name']}: {e}")

    conn.commit()
    print(f"\nCreated {len(SAMPLE_LEADS)} demo leads.")


def print_demo_info():
    """Print demo access information."""
    print("\n" + "=" * 60)
    print("Demo Environment Ready!")
    print("=" * 60)
    print(f"""
Demo CPA Profile:
  Name: {DEMO_CPA['first_name']} {DEMO_CPA['last_name']}, {DEMO_CPA['credentials']}
  Firm: {DEMO_CPA['firm_name']}
  Email: {DEMO_CPA['email']}

Access URLs:
  Lead Magnet: /lead-magnet?cpa={DEMO_CPA['cpa_slug']}
  CPA Dashboard: /cpa/dashboard
  CPA Leads: /cpa/leads

API Endpoints:
  GET /api/cpa/lead-magnet/leads - List all leads
  GET /api/cpa/lead-magnet/leads/hot - Hot leads only
  GET /api/cpa/lead-magnet/leads/stats - Lead statistics

Demo Data:
  - {len(SAMPLE_LEADS)} sample leads with varying scores
  - Mix of hot, warm, and cold leads
  - Activity history for each lead
""")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Seed demo data for Jorss-Gbo")
    parser.add_argument("--clean", action="store_true", help="Clean existing demo data first")
    args = parser.parse_args()

    print("Jorss-Gbo Demo Data Seeder")
    print("-" * 40)
    print(f"Database: {get_db_path()}\n")

    conn = get_connection()

    try:
        if args.clean:
            clean_demo_data(conn)

        create_demo_tenant(conn)
        create_demo_cpa(conn)
        create_demo_leads(conn)
        print_demo_info()

    finally:
        conn.close()


if __name__ == "__main__":
    main()
