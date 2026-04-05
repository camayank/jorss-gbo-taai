"""Pytest configuration and fixtures for test suite."""

import os
import sys
from pathlib import Path

import pytest

# Set test environment BEFORE any other imports
# This ensures auth decorators use fail-open mode for tests
os.environ.setdefault("APP_ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "")
os.environ.setdefault("DB_DRIVER", "sqlite+aiosqlite")
os.environ.setdefault("JWT_SECRET", "e2e-test-secret-key-that-is-at-least-32-chars-long")

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


def _reset_db_modules():
    """Reset database module globals to ensure clean state."""
    try:
        import database.async_engine as module
        module._async_engine = None
        module._async_session_factory = None
    except ImportError:
        pass


@pytest.fixture(autouse=True)
def reset_database_globals():
    """Reset database module globals before and after each test."""
    _reset_db_modules()
    yield
    _reset_db_modules()


@pytest.fixture
def mock_async_session():
    """Provide a mock async session for testing."""
    from unittest.mock import AsyncMock
    return AsyncMock()


@pytest.fixture
def mock_redis_client():
    """Provide a mock Redis client for testing."""
    from unittest.mock import AsyncMock, MagicMock

    client = MagicMock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=True)
    client.exists = AsyncMock(return_value=False)
    client.is_connected = True
    return client


# =============================================================================
# CSRF BYPASS HELPERS FOR TESTING
# =============================================================================

# Default headers that bypass CSRF validation in tests
# Uses Bearer auth from a trusted origin (localhost:8000)
CSRF_BYPASS_HEADERS = {
    "Authorization": "Bearer test_token_for_csrf_bypass",
    "Origin": "http://localhost:8000",
}


@pytest.fixture
def csrf_headers():
    """
    Provide headers that bypass CSRF protection for testing.

    Usage:
        def test_my_endpoint(csrf_headers):
            client = TestClient(app)
            response = client.post("/api/endpoint", headers=csrf_headers)
    """
    return CSRF_BYPASS_HEADERS.copy()


@pytest.fixture
def authenticated_client():
    """
    Provide a TestClient with CSRF bypass headers pre-configured.

    Usage:
        def test_my_endpoint(authenticated_client):
            response = authenticated_client.post("/api/endpoint", json={...})
    """
    from fastapi.testclient import TestClient
    from web.app import app

    # Create client with default headers for CSRF bypass
    client = TestClient(app)

    # Wrap request methods to include CSRF bypass headers
    original_request = client.request

    def request_with_csrf(*args, **kwargs):
        headers = kwargs.get("headers") or {}
        headers.update(CSRF_BYPASS_HEADERS)
        kwargs["headers"] = headers
        return original_request(*args, **kwargs)

    client.request = request_with_csrf
    return client


# =============================================================================
# DATABASE FIXTURES FOR TESTING
# =============================================================================


@pytest.fixture(scope="session", autouse=True)
def run_migrations():
    """Create analytics tables and views for test database."""
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine
    from config.database import DatabaseSettings

    db_settings = DatabaseSettings()
    db_url = db_settings.async_url

    async def create_tables_and_views():
        """Create the analytics_events table and views needed for tests."""
        engine = create_async_engine(db_url, echo=False)

        async with engine.begin() as conn:
            # Create analytics_events table for tests
            await conn.execute(__import__('sqlalchemy').text("""
                CREATE TABLE IF NOT EXISTS analytics_events (
                    event_id TEXT PRIMARY KEY,
                    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    firm_id TEXT,
                    event_type TEXT NOT NULL,
                    session_id TEXT,
                    return_id TEXT,
                    document_id TEXT,
                    scenario_id TEXT,
                    report_id TEXT,
                    lead_id TEXT,
                    cpa_id TEXT,
                    profile_completeness NUMERIC,
                    message_text TEXT,
                    document_type TEXT,
                    fields_extracted INTEGER,
                    return_completeness NUMERIC,
                    scenario_name TEXT,
                    scenario_savings NUMERIC,
                    review_status TEXT,
                    review_notes TEXT,
                    download_url TEXT,
                    lead_from_state TEXT,
                    lead_to_state TEXT,
                    lead_trigger TEXT,
                    extracted_forms TEXT,
                    data_json JSON
                )
            """))

            # Create analytics_completion_metrics view
            await conn.execute(__import__('sqlalchemy').text("""
                CREATE VIEW IF NOT EXISTS analytics_completion_metrics AS
                SELECT
                    DATE(received_at) as metric_date,
                    tenant_id,
                    COUNT(DISTINCT CASE WHEN event_type = 'ReturnDraftSaved' THEN return_id END) as total_returns_started,
                    COUNT(DISTINCT CASE WHEN event_type IN ('ReturnDraftSaved', 'ReturnSubmittedForReview') AND return_id IS NOT NULL THEN return_id END) as returns_with_draft,
                    COUNT(DISTINCT CASE WHEN event_type = 'ReturnSubmittedForReview' THEN return_id END) as returns_submitted,
                    COUNT(DISTINCT CASE WHEN event_type = 'DocumentProcessed' THEN document_id END) as documents_processed,
                    ROUND(
                        CAST(COUNT(DISTINCT CASE WHEN event_type = 'ReturnSubmittedForReview' THEN return_id END) AS REAL) /
                        NULLIF(COUNT(DISTINCT CASE WHEN event_type = 'ReturnDraftSaved' THEN return_id END), 0) * 100,
                        2
                    ) as submission_rate_percent,
                    ROUND(AVG(CASE WHEN event_type = 'AdvisorProfileComplete' THEN profile_completeness END), 2) as avg_profile_completeness
                FROM analytics_events
                WHERE tenant_id IS NOT NULL
                GROUP BY DATE(received_at), tenant_id
            """))

            # Create analytics_document_metrics view
            await conn.execute(__import__('sqlalchemy').text("""
                CREATE VIEW IF NOT EXISTS analytics_document_metrics AS
                SELECT
                    DATE(received_at) as metric_date,
                    tenant_id,
                    document_type,
                    COUNT(DISTINCT document_id) as documents_processed,
                    COUNT(DISTINCT user_id) as unique_users_uploading,
                    ROUND(
                        CAST(COUNT(CASE WHEN fields_extracted > 0 THEN 1 END) AS REAL) /
                        NULLIF(COUNT(document_id), 0) * 100,
                        2
                    ) as extraction_success_rate_percent
                FROM analytics_events
                WHERE event_type = 'DocumentProcessed' AND tenant_id IS NOT NULL
                GROUP BY DATE(received_at), tenant_id, document_type
            """))

            # Create analytics_advisor_activity view
            await conn.execute(__import__('sqlalchemy').text("""
                CREATE VIEW IF NOT EXISTS analytics_advisor_activity AS
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
            """))

            # Create analytics_review_metrics view
            await conn.execute(__import__('sqlalchemy').text("""
                CREATE VIEW IF NOT EXISTS analytics_review_metrics AS
                SELECT
                    DATE(received_at) as metric_date,
                    tenant_id,
                    COUNT(DISTINCT CASE WHEN event_type = 'ReturnSubmittedForReview' THEN return_id END) as returns_submitted,
                    COUNT(DISTINCT CASE WHEN event_type = 'ReviewCompleted' THEN return_id END) as returns_reviewed,
                    COUNT(DISTINCT CASE WHEN event_type = 'ReviewCompleted' AND review_status = 'approved' THEN return_id END) as returns_approved,
                    ROUND(
                        CAST(COUNT(DISTINCT CASE WHEN event_type = 'ReviewCompleted' AND review_status = 'approved' THEN return_id END) AS REAL) /
                        NULLIF(COUNT(DISTINCT CASE WHEN event_type = 'ReviewCompleted' THEN return_id END), 0) * 100,
                        2
                    ) as approval_rate_percent,
                    COUNT(DISTINCT CASE WHEN event_type = 'ReviewCompleted' THEN cpa_id END) as cpas_reviewing
                FROM analytics_events
                WHERE tenant_id IS NOT NULL
                GROUP BY DATE(received_at), tenant_id
            """))

            # Create analytics_return_processing_stats view
            await conn.execute(__import__('sqlalchemy').text("""
                CREATE VIEW IF NOT EXISTS analytics_return_processing_stats AS
                WITH return_processing_times AS (
                    SELECT
                        DATE(received_at) as metric_date,
                        tenant_id,
                        return_id,
                        CAST((CAST(julianday(MAX(CASE WHEN event_type = 'ReviewCompleted' THEN received_at END)) AS REAL) -
                              CAST(julianday(MIN(CASE WHEN event_type = 'ReturnDraftSaved' THEN received_at END)) AS REAL)) * 24 AS REAL) as processing_hours
                    FROM analytics_events
                    WHERE event_type IN ('ReturnDraftSaved', 'ReturnSubmittedForReview', 'ReviewCompleted')
                      AND tenant_id IS NOT NULL
                      AND return_id IS NOT NULL
                    GROUP BY DATE(received_at), tenant_id, return_id
                )
                SELECT
                    metric_date,
                    tenant_id,
                    COUNT(DISTINCT return_id) as total_returns,
                    COUNT(DISTINCT CASE WHEN processing_hours IS NOT NULL THEN return_id END) as draft_stage,
                    COUNT(DISTINCT CASE WHEN processing_hours IS NOT NULL THEN return_id END) as submitted_stage,
                    COUNT(DISTINCT CASE WHEN processing_hours IS NOT NULL THEN return_id END) as completed_stage,
                    ROUND(AVG(processing_hours), 2) as avg_processing_hours
                FROM return_processing_times
                GROUP BY metric_date, tenant_id
            """))

            # Create indexes
            try:
                await conn.execute(__import__('sqlalchemy').text(
                    "CREATE INDEX ix_completion_metrics_date_tenant ON analytics_completion_metrics (metric_date, tenant_id)"
                ))
            except:
                pass

            try:
                await conn.execute(__import__('sqlalchemy').text(
                    "CREATE INDEX ix_document_metrics_date_tenant ON analytics_document_metrics (metric_date, tenant_id)"
                ))
            except:
                pass

            try:
                await conn.execute(__import__('sqlalchemy').text(
                    "CREATE INDEX ix_advisor_activity_date_tenant ON analytics_advisor_activity (metric_date, tenant_id)"
                ))
            except:
                pass

            try:
                await conn.execute(__import__('sqlalchemy').text(
                    "CREATE INDEX ix_review_metrics_date_tenant ON analytics_review_metrics (metric_date, tenant_id)"
                ))
            except:
                pass

            try:
                await conn.execute(__import__('sqlalchemy').text(
                    "CREATE INDEX ix_return_stats_date_tenant ON analytics_return_processing_stats (metric_date, tenant_id)"
                ))
            except:
                pass

        await engine.dispose()

    try:
        asyncio.run(create_tables_and_views())
    except Exception as e:
        # If table/view creation fails, continue anyway
        pass


@pytest.fixture
async def db_session():
    """Provide an async database session for tests that need real DB access."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from config.database import DatabaseSettings

    # Get database configuration
    db_settings = DatabaseSettings()
    db_url = db_settings.async_url

    engine = create_async_engine(db_url, echo=False)
    async_session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_factory() as session:
        yield session

    await engine.dispose()
