"""Create materialized views for CPA dashboard analytics.

Revision ID: 20260405_0002
Revises: 20260405_0001
Create Date: 2026-04-05

Materializes aggregated analytics from analytics_events table for dashboard queries.
Views compute completion rates, document processing metrics, advisor activity,
review turnaround, and return processing statistics.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260405_0002"
down_revision = "20260405_0001"
branch_labels = None
depends_on = None


def upgrade():
    """Create 5 materialized views aggregating analytics_events data."""

    # View 1: Completion metrics (completion rates, documents processed, etc.)
    op.execute("""
        CREATE MATERIALIZED VIEW analytics_completion_metrics AS
        SELECT
            DATE(received_at) as metric_date,
            tenant_id,
            COUNT(DISTINCT CASE WHEN event_type = 'ReturnDraftSaved' THEN return_id END) as total_returns_started,
            COUNT(DISTINCT CASE WHEN event_type IN ('ReturnDraftSaved', 'ReturnSubmittedForReview') AND return_id IS NOT NULL THEN return_id END) as returns_with_draft,
            COUNT(DISTINCT CASE WHEN event_type = 'ReturnSubmittedForReview' THEN return_id END) as returns_submitted,
            COUNT(DISTINCT CASE WHEN event_type = 'DocumentProcessed' THEN document_id END) as documents_processed,
            ROUND(
                COUNT(DISTINCT CASE WHEN event_type = 'ReturnSubmittedForReview' THEN return_id END)::numeric /
                NULLIF(COUNT(DISTINCT CASE WHEN event_type = 'ReturnDraftSaved' THEN return_id END), 0) * 100,
                2
            ) as submission_rate_percent,
            ROUND(AVG(CASE WHEN event_type = 'AdvisorProfileComplete' THEN profile_completeness END), 2) as avg_profile_completeness
        FROM analytics_events
        WHERE tenant_id IS NOT NULL
        GROUP BY DATE(received_at), tenant_id
    """)

    # Create index on materialized view for performance
    op.execute("CREATE INDEX ix_completion_metrics_date_tenant ON analytics_completion_metrics (metric_date, tenant_id)")

    # View 2: Document metrics (document types, extraction success)
    op.execute("""
        CREATE MATERIALIZED VIEW analytics_document_metrics AS
        SELECT
            DATE(received_at) as metric_date,
            tenant_id,
            document_type,
            COUNT(DISTINCT document_id) as documents_processed,
            COUNT(DISTINCT user_id) as unique_users_uploading,
            ROUND(
                COUNT(CASE WHEN fields_extracted > 0 THEN 1 END)::numeric /
                NULLIF(COUNT(document_id), 0) * 100,
                2
            ) as extraction_success_rate_percent
        FROM analytics_events
        WHERE event_type = 'DocumentProcessed' AND tenant_id IS NOT NULL
        GROUP BY DATE(received_at), tenant_id, document_type
    """)

    op.execute("CREATE INDEX ix_document_metrics_date_tenant ON analytics_document_metrics (metric_date, tenant_id)")

    # View 3: Advisor activity (profiles, messages, sessions)
    op.execute("""
        CREATE MATERIALIZED VIEW analytics_advisor_activity AS
        SELECT
            DATE(received_at) as metric_date,
            tenant_id,
            COUNT(DISTINCT CASE WHEN event_type = 'AdvisorProfileComplete' THEN cpa_id END) as profiles_completed,
            COUNT(DISTINCT CASE WHEN event_type = 'AdvisorMessageSent' THEN cpa_id END) as unique_cpas_messaging,
            COUNT(CASE WHEN event_type = 'AdvisorMessageSent' THEN 1 END) as total_messages_sent,
            COUNT(DISTINCT CASE WHEN event_type IN ('AdvisorProfileComplete', 'AdvisorMessageSent', 'DocumentProcessed') AND session_id IS NOT NULL THEN session_id END) as sessions_with_activity,
            ROUND(AVG(CASE WHEN event_type = 'AdvisorProfileComplete' THEN profile_completeness END), 2) as avg_profile_completeness
        FROM analytics_events
        WHERE tenant_id IS NOT NULL
        GROUP BY DATE(received_at), tenant_id
    """)

    op.execute("CREATE INDEX ix_advisor_activity_date_tenant ON analytics_advisor_activity (metric_date, tenant_id)")

    # View 4: Review metrics (review turnaround, approval rates)
    op.execute("""
        CREATE MATERIALIZED VIEW analytics_review_metrics AS
        SELECT
            DATE(received_at) as metric_date,
            tenant_id,
            COUNT(DISTINCT CASE WHEN event_type = 'ReturnSubmittedForReview' THEN return_id END) as returns_submitted,
            COUNT(DISTINCT CASE WHEN event_type = 'ReviewCompleted' THEN return_id END) as returns_reviewed,
            COUNT(DISTINCT CASE WHEN event_type = 'ReviewCompleted' AND review_status = 'approved' THEN return_id END) as returns_approved,
            ROUND(
                COUNT(DISTINCT CASE WHEN event_type = 'ReviewCompleted' AND review_status = 'approved' THEN return_id END)::numeric /
                NULLIF(COUNT(DISTINCT CASE WHEN event_type = 'ReviewCompleted' THEN return_id END), 0) * 100,
                2
            ) as approval_rate_percent,
            COUNT(DISTINCT CASE WHEN event_type = 'ReviewCompleted' THEN cpa_id END) as cpas_reviewing
        FROM analytics_events
        WHERE tenant_id IS NOT NULL
        GROUP BY DATE(received_at), tenant_id
    """)

    op.execute("CREATE INDEX ix_review_metrics_date_tenant ON analytics_review_metrics (metric_date, tenant_id)")

    # View 5: Return processing stats (processing time by stage)
    op.execute("""
        CREATE MATERIALIZED VIEW analytics_return_processing_stats AS
        SELECT
            DATE(received_at) as metric_date,
            tenant_id,
            COUNT(DISTINCT return_id) as total_returns,
            COUNT(DISTINCT CASE WHEN event_type = 'ReturnDraftSaved' THEN return_id END) as draft_stage,
            COUNT(DISTINCT CASE WHEN event_type = 'ReturnSubmittedForReview' THEN return_id END) as submitted_stage,
            COUNT(DISTINCT CASE WHEN event_type = 'ReviewCompleted' THEN return_id END) as completed_stage,
            ROUND(
                EXTRACT(EPOCH FROM (MAX(CASE WHEN event_type = 'ReviewCompleted' THEN received_at END) -
                                   MIN(CASE WHEN event_type = 'ReturnDraftSaved' THEN received_at END))) / 3600,
                2
            ) as avg_processing_hours
        FROM analytics_events
        WHERE event_type IN ('ReturnDraftSaved', 'ReturnSubmittedForReview', 'ReviewCompleted')
          AND tenant_id IS NOT NULL
          AND return_id IS NOT NULL
        GROUP BY DATE(received_at), tenant_id
    """)

    op.execute("CREATE INDEX ix_return_stats_date_tenant ON analytics_return_processing_stats (metric_date, tenant_id)")


def downgrade():
    """Drop materialized views and indexes."""
    op.execute("DROP MATERIALIZED VIEW IF EXISTS analytics_return_processing_stats CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS analytics_review_metrics CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS analytics_advisor_activity CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS analytics_document_metrics CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS analytics_completion_metrics CASCADE")
