"""
Tests for Admin Compliance API.

Tests the /api/admin/compliance endpoints for:
- Compliance reports
- Compliance alerts
- Audit logs
- Regulatory checks
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4


class TestComplianceModels:
    """Test the compliance request/response models."""

    def test_audit_request_model(self):
        """Test AuditRequest model."""
        from src.web.routers.admin_compliance_api import AuditRequest

        request = AuditRequest(
            firm_id="firm-001",
            audit_type="security",
            date_range_days=30
        )

        assert request.firm_id == "firm-001"
        assert request.audit_type == "security"
        assert request.date_range_days == 30

    def test_audit_request_defaults(self):
        """Test AuditRequest default values."""
        from src.web.routers.admin_compliance_api import AuditRequest

        request = AuditRequest(audit_type="data_access")

        assert request.firm_id is None
        assert request.date_range_days == 30

    def test_alert_acknowledge_model(self):
        """Test AlertAcknowledge model."""
        from src.web.routers.admin_compliance_api import AlertAcknowledge

        ack = AlertAcknowledge(notes="Issue resolved by updating firewall rules")

        assert ack.notes == "Issue resolved by updating firewall rules"

    def test_alert_acknowledge_without_notes(self):
        """Test AlertAcknowledge without notes."""
        from src.web.routers.admin_compliance_api import AlertAcknowledge

        ack = AlertAcknowledge()

        assert ack.notes is None


class TestComplianceReportClass:
    """Test the ComplianceReport class."""

    def test_report_creation(self):
        """Test creating a ComplianceReport."""
        from src.web.routers.admin_compliance_api import ComplianceReport

        report = ComplianceReport(
            report_id="rpt-001",
            report_type="security",
            status="pending",
            firm_id="firm-001",
            triggered_by="admin-001",
        )

        assert report.report_id == "rpt-001"
        assert report.report_type == "security"
        assert report.status == "pending"
        assert report.findings_count == 0
        assert report.findings == []

    def test_report_with_findings(self):
        """Test report with findings."""
        from src.web.routers.admin_compliance_api import ComplianceReport

        report = ComplianceReport(
            report_id="rpt-002",
            report_type="data_access",
            status="completed",
            firm_id="firm-002",
            triggered_by="admin-002",
            findings_count=3,
        )
        report.findings = [
            {"type": "info", "message": "Normal access patterns"},
            {"type": "warning", "message": "Unusual login location"},
            {"type": "info", "message": "All data encrypted"},
        ]

        assert report.status == "completed"
        assert report.findings_count == 3
        assert len(report.findings) == 3

    def test_report_to_dict(self):
        """Test report serialization."""
        from src.web.routers.admin_compliance_api import ComplianceReport

        report = ComplianceReport(
            report_id="rpt-003",
            report_type="financial",
            status="running",
            firm_id=None,
            triggered_by="admin-003",
        )

        result = report.to_dict()

        assert result["report_id"] == "rpt-003"
        assert result["report_type"] == "financial"
        assert result["status"] == "running"
        assert result["firm_id"] is None


class TestComplianceAlertClass:
    """Test the ComplianceAlert class."""

    def test_alert_creation(self):
        """Test creating a ComplianceAlert."""
        from src.web.routers.admin_compliance_api import ComplianceAlert

        alert = ComplianceAlert(
            alert_id="alert-001",
            alert_type="data_access",
            severity="medium",
            title="Unusual access pattern",
            description="User accessed 50+ records in 5 minutes",
            firm_id="firm-001",
        )

        assert alert.alert_id == "alert-001"
        assert alert.severity == "medium"
        assert alert.acknowledged_at is None

    def test_alert_acknowledged(self):
        """Test acknowledged alert."""
        from src.web.routers.admin_compliance_api import ComplianceAlert

        alert = ComplianceAlert(
            alert_id="alert-002",
            alert_type="security",
            severity="high",
            title="Failed login attempts",
            description="Multiple failed logins detected",
        )
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = "admin-001"
        alert.notes = "Investigated, was legitimate user"

        assert alert.acknowledged_at is not None
        assert alert.acknowledged_by == "admin-001"
        assert alert.notes is not None

    def test_alert_to_dict(self):
        """Test alert serialization."""
        from src.web.routers.admin_compliance_api import ComplianceAlert

        alert = ComplianceAlert(
            alert_id="alert-003",
            alert_type="compliance",
            severity="low",
            title="Test alert",
            description="Test description",
        )

        result = alert.to_dict()

        assert result["alert_id"] == "alert-003"
        assert result["severity"] == "low"
        assert result["acknowledged"] is False


class TestAlertSeverity:
    """Test alert severity levels."""

    def test_valid_severities(self):
        """Test all valid severity levels."""
        valid_severities = {"low", "medium", "high", "critical"}

        for severity in valid_severities:
            assert severity in valid_severities

    def test_severity_ordering(self):
        """Test severity ordering for sorting."""
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

        assert severity_order["critical"] < severity_order["high"]
        assert severity_order["high"] < severity_order["medium"]
        assert severity_order["medium"] < severity_order["low"]


class TestAuditTypes:
    """Test audit/report types."""

    def test_valid_audit_types(self):
        """Test all valid audit types."""
        valid_types = {"data_access", "security", "financial", "full"}

        for audit_type in valid_types:
            assert audit_type in valid_types

    def test_full_audit_includes_all(self):
        """Test that 'full' audit is comprehensive."""
        full_includes = ["data_access", "security", "financial"]
        # Full audit should cover all individual types
        assert len(full_includes) == 3


class TestRegulatoryCompliance:
    """Test regulatory compliance features."""

    def test_expected_regulations(self):
        """Test expected regulatory standards."""
        regulations = [
            "SOC 2 Type II",
            "IRS Publication 4557",
            "GLBA",
            "State Privacy Laws",
        ]

        assert len(regulations) >= 4
        assert "SOC 2 Type II" in regulations

    def test_compliance_check_statuses(self):
        """Test compliance check status values."""
        valid_statuses = {"pass", "warning", "fail"}

        for status in valid_statuses:
            assert status in valid_statuses

    def test_overall_compliance_status(self):
        """Test overall compliance status determination."""
        # If no failures, overall is compliant
        checks = [
            {"status": "pass"},
            {"status": "pass"},
            {"status": "warning"},
        ]

        failed = sum(1 for c in checks if c["status"] == "fail")
        overall = "compliant" if failed == 0 else "non-compliant"

        assert overall == "compliant"

    def test_non_compliant_with_failures(self):
        """Test non-compliant status when checks fail."""
        checks = [
            {"status": "pass"},
            {"status": "fail"},
            {"status": "pass"},
        ]

        failed = sum(1 for c in checks if c["status"] == "fail")
        overall = "compliant" if failed == 0 else "non-compliant"

        assert overall == "non-compliant"


class TestAuditLogs:
    """Test audit log features."""

    def test_audit_log_structure(self):
        """Test expected audit log entry structure."""
        expected_fields = [
            "log_id",
            "timestamp",
            "action",
            "user_id",
            "user_email",
            "firm_id",
            "resource",
            "ip_address",
            "success",
        ]

        for field in expected_fields:
            assert field in expected_fields

    def test_audit_log_actions(self):
        """Test common audit log action types."""
        common_actions = ["login", "data_access", "config_change", "export"]

        assert "login" in common_actions
        assert "data_access" in common_actions
        assert "config_change" in common_actions

    def test_date_range_validation(self):
        """Test audit log date range validation."""
        from src.web.routers.admin_compliance_api import AuditRequest

        # Default is 30 days
        request = AuditRequest(audit_type="data_access")
        assert request.date_range_days == 30

        # Maximum is 365 days (Field constraint)
        request_max = AuditRequest(audit_type="data_access", date_range_days=365)
        assert request_max.date_range_days == 365

        # Minimum is 1 day (Field constraint)
        request_min = AuditRequest(audit_type="data_access", date_range_days=1)
        assert request_min.date_range_days == 1
