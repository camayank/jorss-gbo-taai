"""Analytics materialized views refresh scheduler.

Refreshes 5 analytics materialized views on a schedule:
- Business hours (8 AM - 6 PM UTC): every 15 minutes
- Off-hours: every hour

Uses REFRESH MATERIALIZED VIEW CONCURRENTLY to avoid table locks.
Includes CloudWatch monitoring and alarms on refresh failures.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Any

from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker

from config.settings import get_settings
from tasks.celery_app import celery_app, TaskBase

logger = logging.getLogger(__name__)

# Materialized views to refresh
MATERIALIZED_VIEWS = [
    "analytics_completion_metrics",
    "analytics_document_metrics",
    "analytics_advisor_activity",
    "analytics_review_metrics",
    "analytics_return_processing_stats",
]


def get_db_session():
    """Create a database session."""
    settings = get_settings()
    engine = create_engine(settings.database.url, echo=False)
    Session = sessionmaker(bind=engine)
    return Session()


@celery_app.task(base=TaskBase, bind=True, name="tasks.analytics_refresh.refresh_all_views")
def refresh_all_views(self) -> Dict[str, Any]:
    """
    Refresh all analytics materialized views.

    Uses REFRESH MATERIALIZED VIEW CONCURRENTLY to avoid blocking reads.

    Returns:
        Dict with refresh results and timing information
    """
    session = None
    start_time = datetime.now(timezone.utc)
    results = {
        "started_at": start_time.isoformat(),
        "views_refreshed": [],
        "views_failed": [],
        "total_duration_seconds": None,
    }

    try:
        session = get_db_session()

        for view_name in MATERIALIZED_VIEWS:
            try:
                logger.info(f"Refreshing materialized view: {view_name}")
                view_start = datetime.now(timezone.utc)

                # Use CONCURRENTLY to avoid blocking reads
                session.execute(
                    text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}")
                )
                session.commit()

                view_duration = (datetime.now(timezone.utc) - view_start).total_seconds()
                results["views_refreshed"].append({
                    "view": view_name,
                    "duration_seconds": view_duration,
                })
                logger.info(f"✓ {view_name} refreshed in {view_duration:.2f}s")

            except Exception as e:
                logger.error(f"✗ Failed to refresh {view_name}: {e}")
                results["views_failed"].append({
                    "view": view_name,
                    "error": str(e),
                })
                session.rollback()
                # Continue refreshing other views

        # Calculate total duration
        total_duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        results["total_duration_seconds"] = total_duration
        results["completed_at"] = datetime.now(timezone.utc).isoformat()
        results["success"] = len(results["views_failed"]) == 0

        # Log summary
        logger.info(
            f"Analytics view refresh complete: "
            f"{len(results['views_refreshed'])} succeeded, "
            f"{len(results['views_failed'])} failed, "
            f"{total_duration:.2f}s total"
        )

        # Emit CloudWatch metric
        if len(results["views_failed"]) > 0:
            emit_cloudwatch_alarm(results)

        return results

    except Exception as e:
        logger.error(f"Unexpected error during view refresh: {e}")
        results["error"] = str(e)
        results["success"] = False
        emit_cloudwatch_alarm(results)
        raise
    finally:
        if session:
            session.close()


def emit_cloudwatch_alarm(results: Dict[str, Any]) -> None:
    """
    Emit CloudWatch metric/alarm if views failed to refresh.

    Args:
        results: Refresh results dictionary
    """
    try:
        import boto3

        cloudwatch = boto3.client("cloudwatch")
        settings = get_settings()

        failed_count = len(results.get("views_failed", []))

        if failed_count > 0:
            # Put metric about failed views
            cloudwatch.put_metric_data(
                Namespace="AITaxAdvisor/Analytics",
                MetricData=[
                    {
                        "MetricName": "MaterializedViewRefreshFailures",
                        "Value": failed_count,
                        "Unit": "Count",
                        "Timestamp": datetime.now(timezone.utc),
                    }
                ],
            )

            # Send alarm
            alarm_message = (
                f"Analytics materialized view refresh failed:\n"
                f"Failed views: {', '.join(v['view'] for v in results['views_failed'])}\n"
                f"Environment: {settings.environment}\n"
                f"See logs for details."
            )
            logger.error(f"CloudWatch alarm: {alarm_message}")
    except Exception as e:
        logger.error(f"Failed to emit CloudWatch alarm: {e}")
