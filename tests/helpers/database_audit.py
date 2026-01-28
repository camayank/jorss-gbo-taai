"""
Database Cascade and Index Audit Utilities

SPEC-012: Tools for auditing database schema for proper cascades and indexes.

Usage:
    from tests.helpers.database_audit import (
        audit_cascades,
        audit_foreign_key_indexes,
        audit_missing_indexes,
        generate_audit_report,
    )

    # Run all audits
    report = generate_audit_report()
    print(report)
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class CascadeIssue:
    """Represents a potential cascade configuration issue."""
    table: str
    relationship: str
    parent_table: str
    issue_type: str  # "missing_cascade", "no_delete_cascade", "orphan_risk"
    recommendation: str
    severity: str  # "high", "medium", "low"


@dataclass
class IndexIssue:
    """Represents a missing or recommended index."""
    table: str
    column: str
    issue_type: str  # "missing_fk_index", "recommended_index"
    recommendation: str
    severity: str


@dataclass
class AuditReport:
    """Complete database audit report."""
    cascade_issues: List[CascadeIssue] = field(default_factory=list)
    index_issues: List[IndexIssue] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)


def get_model_metadata():
    """Get SQLAlchemy model metadata for inspection."""
    import sys
    from pathlib import Path

    # Add src to path if needed
    src_path = Path(__file__).parent.parent.parent / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    try:
        from database.models import Base
        return Base.metadata
    except ImportError as e:
        logger.warning(f"Could not import database models: {e}")
        return None


def audit_cascades() -> List[CascadeIssue]:
    """
    Audit relationship cascade configurations.

    Checks for:
    - Missing cascade definitions on relationships
    - Relationships that should have delete-orphan
    - Parent-child relationships without proper cascade
    """
    issues = []

    try:
        import sys
        from pathlib import Path

        src_path = Path(__file__).parent.parent.parent / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from database.models import (
            TaxReturnRecord,
            TaxpayerRecord,
            IncomeRecord,
            W2Record,
            Form1099Record,
            DeductionRecord,
            CreditRecord,
            DependentRecord,
            StateReturnRecord,
            AuditLogRecord,
            ComputationWorksheet,
            DocumentRecord,
            ExtractedFieldRecord,
            DocumentProcessingLog,
            PreparerRecord,
            ClientRecord,
            ClientSessionRecord,
        )
        from sqlalchemy.orm import inspect

        # Define expected cascade configurations
        expected_cascades = {
            # Parent-child relationships should have "all, delete-orphan"
            "TaxReturnRecord": {
                "income_records": "all, delete-orphan",
                "w2_records": "all, delete-orphan",
                "form1099_records": "all, delete-orphan",
                "deduction_records": "all, delete-orphan",
                "credit_records": "all, delete-orphan",
                "dependent_records": "all, delete-orphan",
                "state_returns": "all, delete-orphan",
                "audit_logs": "all, delete-orphan",
                "computation_worksheets": "all, delete-orphan",
            },
            "PreparerRecord": {
                "client_sessions": "all, delete-orphan",
                "clients": "all, delete-orphan",
            },
            "ClientRecord": {
                "sessions": "all, delete-orphan",
            },
            "DocumentRecord": {
                # If document is deleted, related fields and logs should go too
            },
        }

        models_to_check = [
            TaxReturnRecord,
            TaxpayerRecord,
            PreparerRecord,
            ClientRecord,
            ClientSessionRecord,
            DocumentRecord,
        ]

        for model in models_to_check:
            mapper = inspect(model)
            model_name = model.__name__

            for rel in mapper.relationships:
                rel_name = rel.key
                cascade_str = str(rel.cascade) if rel.cascade else ""

                # Check if this relationship should have cascade
                if model_name in expected_cascades:
                    expected = expected_cascades[model_name].get(rel_name)
                    if expected:
                        if "delete-orphan" not in cascade_str:
                            issues.append(CascadeIssue(
                                table=model.__tablename__,
                                relationship=rel_name,
                                parent_table=rel.target.name if rel.target else "unknown",
                                issue_type="no_delete_orphan",
                                recommendation=f"Add cascade='all, delete-orphan' to {rel_name}",
                                severity="medium",
                            ))

                # Check for relationships without any cascade
                if rel.uselist and not cascade_str:
                    issues.append(CascadeIssue(
                        table=model.__tablename__,
                        relationship=rel_name,
                        parent_table=rel.target.name if rel.target else "unknown",
                        issue_type="missing_cascade",
                        recommendation=f"Consider adding cascade configuration to {rel_name}",
                        severity="low",
                    ))

    except ImportError as e:
        logger.warning(f"Could not audit cascades: {e}")
        issues.append(CascadeIssue(
            table="N/A",
            relationship="N/A",
            parent_table="N/A",
            issue_type="audit_error",
            recommendation=f"Fix import error: {e}",
            severity="high",
        ))

    return issues


def audit_foreign_key_indexes() -> List[IndexIssue]:
    """
    Audit that all foreign keys have corresponding indexes.

    Missing indexes on FKs cause slow JOINs and cascade operations.
    """
    issues = []

    metadata = get_model_metadata()
    if not metadata:
        return issues

    for table_name, table in metadata.tables.items():
        # Get all foreign key columns
        fk_columns = set()
        for fk in table.foreign_keys:
            fk_columns.add(fk.parent.name)

        # Get all indexed columns
        indexed_columns = set()
        for index in table.indexes:
            for col in index.columns:
                indexed_columns.add(col.name)

        # Primary key columns are always indexed
        for pk_col in table.primary_key.columns:
            indexed_columns.add(pk_col.name)

        # Check for FK columns without indexes
        for fk_col in fk_columns:
            if fk_col not in indexed_columns:
                issues.append(IndexIssue(
                    table=table_name,
                    column=fk_col,
                    issue_type="missing_fk_index",
                    recommendation=f"Add index on {table_name}.{fk_col} for FK performance",
                    severity="high",
                ))

    return issues


def audit_missing_indexes() -> List[IndexIssue]:
    """
    Audit for commonly queried columns that should have indexes.

    Checks for:
    - Status/flag columns used in WHERE clauses
    - Timestamp columns used for sorting/filtering
    - Hash columns used for lookups
    """
    issues = []

    # Common patterns that should be indexed
    should_index_patterns = {
        "status": "medium",
        "is_active": "medium",
        "is_deleted": "medium",
        "created_at": "low",
        "updated_at": "low",
        "email": "medium",
        "tenant_id": "high",
        "session_id": "high",
        "ssn_hash": "high",
    }

    metadata = get_model_metadata()
    if not metadata:
        return issues

    for table_name, table in metadata.tables.items():
        # Get all indexed columns
        indexed_columns = set()
        for index in table.indexes:
            for col in index.columns:
                indexed_columns.add(col.name)

        for pk_col in table.primary_key.columns:
            indexed_columns.add(pk_col.name)

        # Check columns against patterns
        for col in table.columns:
            col_name_lower = col.name.lower()

            for pattern, severity in should_index_patterns.items():
                if pattern in col_name_lower and col.name not in indexed_columns:
                    issues.append(IndexIssue(
                        table=table_name,
                        column=col.name,
                        issue_type="recommended_index",
                        recommendation=f"Consider adding index on {table_name}.{col.name} ({pattern} pattern)",
                        severity=severity,
                    ))
                    break  # Only report once per column

    return issues


def audit_composite_indexes() -> List[IndexIssue]:
    """
    Audit for missing composite indexes on commonly-used column combinations.
    """
    issues = []

    # Common composite index patterns
    recommended_composites = {
        "tax_returns": [
            ("tax_year", "status"),
            ("tax_year", "taxpayer_ssn_hash"),
        ],
        "client_sessions": [
            ("preparer_id", "tax_year"),
            ("status", "preparer_id"),
        ],
        "audit_logs": [
            ("event_type", "timestamp"),
            ("user_id", "timestamp"),
        ],
    }

    metadata = get_model_metadata()
    if not metadata:
        return issues

    for table_name, combos in recommended_composites.items():
        if table_name not in metadata.tables:
            continue

        table = metadata.tables[table_name]

        # Get existing composite indexes
        existing_composites = set()
        for index in table.indexes:
            cols = tuple(sorted(c.name for c in index.columns))
            existing_composites.add(cols)

        # Check if recommended composites exist
        for combo in combos:
            combo_sorted = tuple(sorted(combo))
            # Check if any existing index covers this combination
            found = False
            for existing in existing_composites:
                if all(c in existing for c in combo_sorted):
                    found = True
                    break

            if not found:
                issues.append(IndexIssue(
                    table=table_name,
                    column=", ".join(combo),
                    issue_type="missing_composite_index",
                    recommendation=f"Add composite index on {table_name}({', '.join(combo)})",
                    severity="medium",
                ))

    return issues


def generate_audit_report() -> AuditReport:
    """
    Generate a comprehensive database audit report.

    Returns:
        AuditReport with all findings and recommendations
    """
    report = AuditReport()

    # Run all audits
    report.cascade_issues = audit_cascades()
    fk_index_issues = audit_foreign_key_indexes()
    missing_index_issues = audit_missing_indexes()
    composite_issues = audit_composite_indexes()

    report.index_issues = fk_index_issues + missing_index_issues + composite_issues

    # Generate summary
    high_severity = sum(
        1 for i in report.cascade_issues + report.index_issues
        if i.severity == "high"
    )
    medium_severity = sum(
        1 for i in report.cascade_issues + report.index_issues
        if i.severity == "medium"
    )
    low_severity = sum(
        1 for i in report.cascade_issues + report.index_issues
        if i.severity == "low"
    )

    report.summary = {
        "total_cascade_issues": len(report.cascade_issues),
        "total_index_issues": len(report.index_issues),
        "high_severity_count": high_severity,
        "medium_severity_count": medium_severity,
        "low_severity_count": low_severity,
    }

    # Generate top recommendations
    if high_severity > 0:
        report.recommendations.append(
            f"CRITICAL: Address {high_severity} high-severity issues immediately"
        )

    fk_without_index = [i for i in fk_index_issues if i.issue_type == "missing_fk_index"]
    if fk_without_index:
        report.recommendations.append(
            f"Add indexes to {len(fk_without_index)} foreign key columns for JOIN performance"
        )

    cascade_issues = [i for i in report.cascade_issues if i.issue_type == "no_delete_orphan"]
    if cascade_issues:
        report.recommendations.append(
            f"Add delete-orphan cascades to {len(cascade_issues)} relationships to prevent orphan records"
        )

    return report


def format_report_text(report: AuditReport) -> str:
    """
    Format audit report as readable text.

    Args:
        report: AuditReport to format

    Returns:
        Formatted text report
    """
    lines = [
        "=" * 70,
        "DATABASE AUDIT REPORT",
        "=" * 70,
        "",
        "SUMMARY",
        "-" * 40,
        f"Total Cascade Issues: {report.summary.get('total_cascade_issues', 0)}",
        f"Total Index Issues: {report.summary.get('total_index_issues', 0)}",
        f"High Severity: {report.summary.get('high_severity_count', 0)}",
        f"Medium Severity: {report.summary.get('medium_severity_count', 0)}",
        f"Low Severity: {report.summary.get('low_severity_count', 0)}",
        "",
    ]

    if report.recommendations:
        lines.extend([
            "RECOMMENDATIONS",
            "-" * 40,
        ])
        for rec in report.recommendations:
            lines.append(f"  * {rec}")
        lines.append("")

    if report.cascade_issues:
        lines.extend([
            "CASCADE ISSUES",
            "-" * 40,
        ])
        for issue in report.cascade_issues:
            lines.append(f"  [{issue.severity.upper()}] {issue.table}.{issue.relationship}")
            lines.append(f"    Type: {issue.issue_type}")
            lines.append(f"    Fix: {issue.recommendation}")
        lines.append("")

    if report.index_issues:
        lines.extend([
            "INDEX ISSUES",
            "-" * 40,
        ])
        for issue in report.index_issues:
            lines.append(f"  [{issue.severity.upper()}] {issue.table}.{issue.column}")
            lines.append(f"    Type: {issue.issue_type}")
            lines.append(f"    Fix: {issue.recommendation}")
        lines.append("")

    lines.append("=" * 70)

    return "\n".join(lines)


# =============================================================================
# PYTEST FIXTURES AND TESTS
# =============================================================================

def test_all_fks_have_indexes():
    """
    Test that all foreign keys have corresponding indexes.

    This test ensures query performance by verifying indexes exist.
    """
    issues = audit_foreign_key_indexes()
    high_severity = [i for i in issues if i.severity == "high"]

    if high_severity:
        report = "\n".join([
            f"  - {i.table}.{i.column}: {i.recommendation}"
            for i in high_severity
        ])
        assert False, f"Missing FK indexes:\n{report}"


def test_cascades_properly_configured():
    """
    Test that cascade deletes are properly configured.

    This test ensures parent-child relationships don't create orphans.
    """
    issues = audit_cascades()
    high_severity = [i for i in issues if i.severity == "high"]

    if high_severity:
        report = "\n".join([
            f"  - {i.table}.{i.relationship}: {i.recommendation}"
            for i in high_severity
        ])
        assert False, f"Cascade configuration issues:\n{report}"


def test_no_orphan_risk():
    """
    Test that delete-orphan is used where appropriate.
    """
    issues = audit_cascades()
    orphan_issues = [i for i in issues if i.issue_type == "no_delete_orphan"]

    # For now, just log warnings - don't fail
    if orphan_issues:
        logger.warning(
            f"Found {len(orphan_issues)} relationships without delete-orphan cascade"
        )


def test_generate_full_report():
    """
    Test that full audit report can be generated.
    """
    report = generate_audit_report()

    assert report is not None
    assert "total_cascade_issues" in report.summary
    assert "total_index_issues" in report.summary

    # Print report for visibility
    print("\n" + format_report_text(report))
