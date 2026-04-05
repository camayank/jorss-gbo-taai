"""
Database migrations package.

Contains incremental schema changes and optimizations:
- add_core_indexes.py: Critical indexes for common queries
- add_performance_indexes.py: Performance optimization indexes
- add_stripe_connect_fields.py: Stripe integration fields
- create_analytics_views.py: Materialized views for CPA dashboard metrics
"""

from .create_analytics_views import (
    ANALYTICS_VIEWS,
    run_migration_sync,
    verify_views,
)

__all__ = [
    "ANALYTICS_VIEWS",
    "run_migration_sync",
    "verify_views",
]
