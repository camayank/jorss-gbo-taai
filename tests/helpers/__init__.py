"""
Test Utilities Package

SPEC-010: N+1 query detection utilities
SPEC-012: Database cascade and index audit utilities

Available utilities:
- QueryCounter: Context manager for counting database queries
- QueryStats: Statistics about query execution
- QueryInfo: Information about individual queries
- assert_query_count: Decorator to assert max query count
- audit_cascades: Audit relationship cascade configurations
- audit_foreign_key_indexes: Check FK index coverage
- generate_audit_report: Generate comprehensive database audit report
"""

# N+1 Query Detection (SPEC-010)
from .query_counter import (
    QueryCounter,
    QueryStats,
    QueryInfo,
    assert_query_count,
    recommend_eager_loading,
)

# Database Audit (SPEC-012)
from .database_audit import (
    audit_cascades,
    audit_foreign_key_indexes,
    audit_missing_indexes,
    audit_composite_indexes,
    generate_audit_report,
    format_report_text,
    CascadeIssue,
    IndexIssue,
    AuditReport,
)

__all__ = [
    # Query counting
    "QueryCounter",
    "QueryStats",
    "QueryInfo",
    "assert_query_count",
    "recommend_eager_loading",
    # Database audit
    "audit_cascades",
    "audit_foreign_key_indexes",
    "audit_missing_indexes",
    "audit_composite_indexes",
    "generate_audit_report",
    "format_report_text",
    "CascadeIssue",
    "IndexIssue",
    "AuditReport",
]
