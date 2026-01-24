"""
Performance Optimization: Database Indexes

This migration adds indexes to frequently queried columns to improve:
1. Lead list queries (by state, score, created_at)
2. Tenant isolation (tenant_id lookups)
3. Activity timeline queries
4. Notification queries

Run with: python -m database.migrations.add_performance_indexes
"""

import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_db_path() -> str:
    """Get database path."""
    import os
    return os.environ.get(
        "DATABASE_PATH",
        str(Path(__file__).parent.parent.parent / "database" / "jorss_gbo.db")
    )


def run_migration():
    """Add performance indexes to the database."""
    db_path = get_db_path()

    logger.info(f"Running performance index migration on: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Define indexes to create
    indexes = [
        # Lead Magnet Leads indexes
        ("idx_leads_cpa_state", "lead_magnet_leads", "cpa_id, lead_state"),
        ("idx_leads_tenant_created", "lead_magnet_leads", "tenant_id, created_at DESC"),
        ("idx_leads_score_desc", "lead_magnet_leads", "lead_score DESC"),
        ("idx_leads_temperature", "lead_magnet_leads", "lead_temperature, lead_score DESC"),
        ("idx_leads_engaged", "lead_magnet_leads", "engaged, created_at DESC"),
        ("idx_leads_converted", "lead_magnet_leads", "converted, converted_at DESC"),
        ("idx_leads_session", "lead_magnet_leads", "session_id"),
        ("idx_leads_email", "lead_magnet_leads", "email"),

        # Lead Activities indexes
        ("idx_activities_lead_created", "lead_activities", "lead_id, created_at DESC"),
        ("idx_activities_type", "lead_activities", "activity_type, created_at DESC"),
        ("idx_activities_actor", "lead_activities", "actor_id, created_at DESC"),

        # Notifications indexes
        ("idx_notifications_recipient", "notifications", "recipient_email, created_at DESC"),
        ("idx_notifications_status", "notifications", "status, created_at DESC"),
        ("idx_notifications_lead", "notifications", "lead_id"),

        # Follow-up Reminders indexes
        ("idx_reminders_cpa_due", "follow_up_reminders", "cpa_email, due_date"),
        ("idx_reminders_completed", "follow_up_reminders", "completed, due_date"),
        ("idx_reminders_lead", "follow_up_reminders", "lead_id"),

        # Nurture Enrollments indexes
        ("idx_nurture_status_next", "nurture_enrollments", "status, next_email_at"),
        ("idx_nurture_lead", "nurture_enrollments", "lead_id"),

        # Sessions indexes (if table exists)
        ("idx_sessions_cpa", "assessment_sessions", "cpa_slug"),
        ("idx_sessions_created", "assessment_sessions", "created_at DESC"),

        # CPA Profiles indexes (if table exists)
        ("idx_cpa_profiles_slug", "cpa_profiles", "cpa_slug"),
        ("idx_cpa_profiles_tenant", "cpa_profiles", "tenant_id"),

        # Tenants indexes
        ("idx_tenants_domain", "tenants", "custom_domain"),
        ("idx_tenants_status", "tenants", "status"),
    ]

    created = 0
    skipped = 0
    errors = 0

    for index_name, table_name, columns in indexes:
        try:
            # Check if table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
            if not cursor.fetchone():
                logger.debug(f"Table {table_name} does not exist, skipping index {index_name}")
                skipped += 1
                continue

            # Create index if not exists
            sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({columns})"
            cursor.execute(sql)
            logger.info(f"Created index: {index_name} on {table_name}({columns})")
            created += 1

        except sqlite3.OperationalError as e:
            if "already exists" in str(e):
                logger.debug(f"Index {index_name} already exists")
                skipped += 1
            else:
                logger.error(f"Error creating index {index_name}: {e}")
                errors += 1

    conn.commit()
    conn.close()

    logger.info(f"Migration complete: {created} created, {skipped} skipped, {errors} errors")

    return {
        "created": created,
        "skipped": skipped,
        "errors": errors,
    }


def verify_indexes():
    """Verify indexes exist and show their status."""
    db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name, tbl_name, sql
        FROM sqlite_master
        WHERE type='index' AND sql IS NOT NULL
        ORDER BY tbl_name, name
    """)

    indexes = cursor.fetchall()
    conn.close()

    print(f"\n{'='*60}")
    print(f"Database Indexes ({len(indexes)} total)")
    print(f"{'='*60}\n")

    current_table = None
    for name, table, sql in indexes:
        if table != current_table:
            print(f"\n{table}:")
            current_table = table
        print(f"  - {name}")

    return indexes


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Running performance index migration...")
    result = run_migration()
    print(f"\nResult: {result}")

    print("\nVerifying indexes...")
    verify_indexes()
