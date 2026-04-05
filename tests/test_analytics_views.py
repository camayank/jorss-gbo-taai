"""Test analytics materialized views."""

import pytest
from sqlalchemy import text, inspect


class TestAnalyticsViews:
    """Test materialized views for analytics dashboard."""

    async def _view_exists(self, db_session, view_name: str) -> bool:
        """Check if a view exists in the database.

        Works with both PostgreSQL and SQLite.
        """
        # Get database dialect to determine query method
        dialect = db_session.get_bind().dialect

        if "postgresql" in dialect.name or "postgres" in dialect.name:
            # PostgreSQL query
            result = await db_session.execute(
                text(f"""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = '{view_name}'
                    AND table_type = 'MATERIALIZED VIEW'
                )
                """)
            )
            return result.scalar()
        else:
            # SQLite query using sqlite_master
            result = await db_session.execute(
                text(f"""
                SELECT EXISTS(
                    SELECT 1 FROM sqlite_master
                    WHERE type = 'view' AND name = '{view_name}'
                )
                """)
            )
            return result.scalar() == 1

    async def test_completion_metrics_view_exists(self, db_session):
        """Verify analytics_completion_metrics view exists and is queryable."""
        exists = await self._view_exists(db_session, 'analytics_completion_metrics')
        assert exists, "analytics_completion_metrics view does not exist"

    async def test_document_metrics_view_exists(self, db_session):
        """Verify analytics_document_metrics view exists."""
        exists = await self._view_exists(db_session, 'analytics_document_metrics')
        assert exists, "analytics_document_metrics view does not exist"

    async def test_advisor_activity_view_exists(self, db_session):
        """Verify analytics_advisor_activity view exists."""
        exists = await self._view_exists(db_session, 'analytics_advisor_activity')
        assert exists, "analytics_advisor_activity view does not exist"

    async def test_review_metrics_view_exists(self, db_session):
        """Verify analytics_review_metrics view exists."""
        exists = await self._view_exists(db_session, 'analytics_review_metrics')
        assert exists, "analytics_review_metrics view does not exist"

    async def test_return_processing_view_exists(self, db_session):
        """Verify analytics_return_processing_stats view exists."""
        exists = await self._view_exists(db_session, 'analytics_return_processing_stats')
        assert exists, "analytics_return_processing_stats view does not exist"

    async def test_completion_metrics_columns(self, db_session):
        """Verify completion metrics view has expected columns."""
        dialect = db_session.get_bind().dialect

        if "postgresql" in dialect.name or "postgres" in dialect.name:
            # PostgreSQL query
            result = await db_session.execute(
                text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'analytics_completion_metrics'
                ORDER BY ordinal_position
                """)
            )
            columns = [row[0] for row in result]
        else:
            # SQLite query
            result = await db_session.execute(
                text("PRAGMA table_info(analytics_completion_metrics)")
            )
            columns = [row[1] for row in result]

        # Verify key columns exist
        expected_columns = [
            'metric_date', 'tenant_id', 'total_returns_started', 'returns_with_draft',
            'returns_submitted', 'submission_rate', 'avg_completion_pct',
            'documents_processed'
        ]
        for col in expected_columns:
            assert col in columns, f"Expected column '{col}' not found in completion_metrics"

    async def test_document_metrics_columns(self, db_session):
        """Verify document metrics view has expected columns."""
        dialect = db_session.get_bind().dialect

        if "postgresql" in dialect.name or "postgres" in dialect.name:
            # PostgreSQL query
            result = await db_session.execute(
                text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'analytics_document_metrics'
                ORDER BY ordinal_position
                """)
            )
            columns = [row[0] for row in result]
        else:
            # SQLite query
            result = await db_session.execute(
                text("PRAGMA table_info(analytics_document_metrics)")
            )
            columns = [row[1] for row in result]

        expected_columns = [
            'metric_date', 'tenant_id', 'document_type', 'documents_processed',
            'unique_documents', 'users_uploading', 'sessions_with_documents',
            'extraction_success_rate', 'returns_with_doc_type'
        ]
        for col in expected_columns:
            assert col in columns, f"Expected column '{col}' not found in document_metrics"

    async def test_views_have_indexes(self, db_session):
        """Verify materialized views have performance indexes.

        Note: Index verification is PostgreSQL-specific. SQLite will skip this test.
        """
        dialect = db_session.get_bind().dialect

        # Skip index check for SQLite as it doesn't use named indexes the same way
        if "sqlite" in dialect.name:
            pytest.skip("Index checking not supported for SQLite")

        view_indexes = [
            ('analytics_completion_metrics', 'idx_completion_metrics_date_tenant'),
            ('analytics_document_metrics', 'idx_document_metrics_date_type'),
            ('analytics_advisor_activity', 'idx_advisor_activity_date_tenant'),
            ('analytics_review_metrics', 'idx_review_metrics_date_tenant'),
            ('analytics_return_processing_stats', 'idx_processing_stats_date_tenant'),
        ]

        for view_name, index_name in view_indexes:
            result = await db_session.execute(
                text(f"""
                SELECT EXISTS(
                    SELECT 1 FROM pg_indexes
                    WHERE tablename = '{view_name}' AND indexname = '{index_name}'
                )
                """)
            )
            exists = result.scalar()
            assert exists, f"Index '{index_name}' not found on '{view_name}'"

    async def test_views_are_queryable(self, db_session):
        """Verify all materialized views are queryable without errors."""
        views = [
            'analytics_completion_metrics',
            'analytics_document_metrics',
            'analytics_advisor_activity',
            'analytics_review_metrics',
            'analytics_return_processing_stats',
        ]

        for view_name in views:
            result = await db_session.execute(
                text(f"SELECT COUNT(*) FROM {view_name} LIMIT 1")
            )
            count = result.scalar()
            assert count is not None, f"Failed to query {view_name}"
