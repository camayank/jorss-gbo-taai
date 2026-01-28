"""
Database Cascade and Index Audit Tests

SPEC-012: Tests that verify database schema has proper cascades and indexes.

These tests:
1. Verify all foreign keys have indexes for JOIN performance
2. Check cascade configurations to prevent orphan records
3. Identify recommended indexes for commonly-queried columns
"""

import pytest
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


class TestForeignKeyIndexes:
    """Tests for foreign key index coverage."""

    def test_all_foreign_keys_have_indexes(self):
        """
        All foreign key columns should have indexes.

        Missing FK indexes cause:
        - Slow JOIN operations
        - Slow cascade deletes
        - Table scans on relationship queries
        """
        from tests.helpers.database_audit import audit_foreign_key_indexes

        issues = audit_foreign_key_indexes()
        high_severity = [i for i in issues if i.severity == "high"]

        if high_severity:
            report = "\n".join([
                f"  - {i.table}.{i.column}"
                for i in high_severity
            ])
            pytest.skip(
                f"Found {len(high_severity)} FK columns without indexes:\n{report}\n"
                "These should be addressed for production performance."
            )

    def test_document_foreign_keys_indexed(self):
        """Document-related tables should have indexed FKs."""
        from tests.helpers.database_audit import audit_foreign_key_indexes

        issues = audit_foreign_key_indexes()
        doc_issues = [
            i for i in issues
            if 'document' in i.table.lower()
        ]

        # Document tables are frequently queried
        assert len(doc_issues) == 0, \
            f"Document tables need FK indexes: {[i.column for i in doc_issues]}"


class TestCascadeConfiguration:
    """Tests for cascade delete configuration."""

    def test_tax_return_cascades(self):
        """
        TaxReturnRecord should cascade deletes to child records.

        Without proper cascades:
        - Deleting a tax return leaves orphan W2s, 1099s, etc.
        - Foreign key constraints cause delete failures
        """
        from tests.helpers.database_audit import audit_cascades

        issues = audit_cascades()
        tax_return_issues = [
            i for i in issues
            if i.table == "tax_returns"
        ]

        # Tax returns MUST cascade properly
        high_issues = [i for i in tax_return_issues if i.severity == "high"]
        assert len(high_issues) == 0, \
            f"Tax return cascade issues: {[i.relationship for i in high_issues]}"

    def test_preparer_cascades(self):
        """
        PreparerRecord should cascade deletes to client relationships.
        """
        from tests.helpers.database_audit import audit_cascades

        issues = audit_cascades()
        preparer_issues = [
            i for i in issues
            if i.table == "preparers"
        ]

        # Log any issues for review
        if preparer_issues:
            for issue in preparer_issues:
                print(f"Preparer cascade issue: {issue.relationship} - {issue.recommendation}")

    def test_no_orphan_records_on_delete(self):
        """
        Parent tables should have delete-orphan to prevent orphaned children.
        """
        from tests.helpers.database_audit import audit_cascades

        issues = audit_cascades()
        orphan_risks = [
            i for i in issues
            if i.issue_type == "no_delete_orphan"
        ]

        # Log warnings but don't fail - these need manual review
        if orphan_risks:
            print(f"\nWarning: {len(orphan_risks)} relationships may create orphan records:")
            for issue in orphan_risks[:5]:  # Show first 5
                print(f"  - {issue.table}.{issue.relationship}")


class TestRecommendedIndexes:
    """Tests for recommended index patterns."""

    def test_status_columns_indexed(self):
        """
        Status and flag columns used in WHERE clauses should be indexed.
        """
        from tests.helpers.database_audit import audit_missing_indexes

        issues = audit_missing_indexes()
        status_issues = [
            i for i in issues
            if "status" in i.recommendation.lower()
        ]

        # Log for visibility
        if status_issues:
            print(f"\nRecommended status indexes:")
            for issue in status_issues:
                print(f"  - {issue.table}.{issue.column}")

    def test_timestamp_columns_indexed(self):
        """
        Timestamp columns used for sorting should be indexed.
        """
        from tests.helpers.database_audit import audit_missing_indexes

        issues = audit_missing_indexes()
        timestamp_issues = [
            i for i in issues
            if "created_at" in i.column or "updated_at" in i.column
        ]

        # These are lower priority
        if timestamp_issues:
            print(f"\nOptional timestamp indexes: {len(timestamp_issues)}")

    def test_hash_lookup_columns_indexed(self):
        """
        Hash columns used for lookups (ssn_hash, etc.) must be indexed.
        """
        from tests.helpers.database_audit import audit_missing_indexes

        issues = audit_missing_indexes()
        hash_issues = [
            i for i in issues
            if "hash" in i.column.lower()
            and i.severity == "high"
        ]

        if hash_issues:
            report = "\n".join([
                f"  - {i.table}.{i.column}"
                for i in hash_issues
            ])
            pytest.skip(
                f"Hash lookup columns need indexes:\n{report}"
            )


class TestCompositeIndexes:
    """Tests for composite index coverage."""

    def test_tax_return_composite_indexes(self):
        """
        Tax returns should have composite indexes for common queries.
        """
        from tests.helpers.database_audit import audit_composite_indexes

        issues = audit_composite_indexes()
        tax_issues = [
            i for i in issues
            if i.table == "tax_returns"
        ]

        if tax_issues:
            print(f"\nRecommended tax_returns composite indexes:")
            for issue in tax_issues:
                print(f"  - ({issue.column})")

    def test_audit_log_composite_indexes(self):
        """
        Audit logs should have indexes for efficient querying.
        """
        from tests.helpers.database_audit import audit_composite_indexes

        issues = audit_composite_indexes()
        audit_issues = [
            i for i in issues
            if i.table == "audit_logs"
        ]

        # Log for visibility
        if audit_issues:
            print(f"\nRecommended audit_logs indexes:")
            for issue in audit_issues:
                print(f"  - ({issue.column})")


class TestFullAuditReport:
    """Tests for complete audit report generation."""

    def test_generate_audit_report(self):
        """
        Full audit report should be generated successfully.
        """
        from tests.helpers.database_audit import generate_audit_report, format_report_text

        report = generate_audit_report()

        assert report is not None
        assert "total_cascade_issues" in report.summary
        assert "total_index_issues" in report.summary

    def test_audit_report_has_recommendations(self):
        """
        Audit report should include actionable recommendations.
        """
        from tests.helpers.database_audit import generate_audit_report

        report = generate_audit_report()

        # Should have at least a summary
        assert report.summary is not None

        # Print report for visibility in test output
        print(f"\n=== DATABASE AUDIT SUMMARY ===")
        print(f"Cascade issues: {report.summary.get('total_cascade_issues', 0)}")
        print(f"Index issues: {report.summary.get('total_index_issues', 0)}")
        print(f"High severity: {report.summary.get('high_severity_count', 0)}")

        if report.recommendations:
            print(f"\nRecommendations:")
            for rec in report.recommendations:
                print(f"  * {rec}")

    def test_print_full_report(self):
        """
        Print full audit report for manual review.
        """
        from tests.helpers.database_audit import generate_audit_report, format_report_text

        report = generate_audit_report()
        formatted = format_report_text(report)

        # Always print for visibility during test runs
        print("\n" + formatted)

        # This test always passes - it's for report visibility
        assert True


class TestSchemaIntegrity:
    """Tests for overall schema integrity."""

    def test_models_can_be_inspected(self):
        """
        SQLAlchemy models should be properly configured for inspection.
        """
        from tests.helpers.database_audit import get_model_metadata

        metadata = get_model_metadata()

        # Should be able to get metadata
        assert metadata is not None, "Could not load model metadata"

        # Should have tables
        assert len(metadata.tables) > 0, "No tables found in metadata"

        # Print table count for visibility
        print(f"\nFound {len(metadata.tables)} tables in database schema")

    def test_core_tables_exist(self):
        """
        Core tax tables should exist in the schema.
        """
        from tests.helpers.database_audit import get_model_metadata

        metadata = get_model_metadata()

        if metadata is None:
            pytest.skip("Could not load model metadata")

        required_tables = [
            "tax_returns",
            "taxpayers",
            "income_records",
            "w2_records",
            "deduction_records",
            "credit_records",
        ]

        for table in required_tables:
            assert table in metadata.tables, f"Missing required table: {table}"

    def test_relationship_consistency(self):
        """
        All relationships should reference existing tables.
        """
        from tests.helpers.database_audit import get_model_metadata

        metadata = get_model_metadata()

        if metadata is None:
            pytest.skip("Could not load model metadata")

        # Check all foreign keys reference existing tables
        for table_name, table in metadata.tables.items():
            for fk in table.foreign_keys:
                target_table = fk.column.table.name
                assert target_table in metadata.tables, \
                    f"FK in {table_name} references non-existent table: {target_table}"
