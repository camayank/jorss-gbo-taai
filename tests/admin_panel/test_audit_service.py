"""
Comprehensive tests for AuditService — audit log creation, filtering,
suspicious activity detection, compliance reporting, retention policies,
and export formatting.
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from uuid import uuid4
import json
import hashlib

import pytest
from unittest.mock import Mock, AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from admin_panel.services.audit_service import AuditService, AuditAction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_service():
    db = AsyncMock()
    svc = AuditService(db)
    return svc


FIRM_ID = "firm-001"
USER_ID = "user-001"

ALL_ACTIONS = [a.value for a in AuditAction]

SECURITY_ACTIONS = [
    AuditAction.LOGIN.value,
    AuditAction.LOGOUT.value,
    AuditAction.LOGIN_FAILED.value,
    AuditAction.PASSWORD_CHANGED.value,
    AuditAction.MFA_ENABLED.value,
    AuditAction.MFA_DISABLED.value,
]

USER_MGMT_ACTIONS = [
    AuditAction.USER_CREATED.value,
    AuditAction.USER_UPDATED.value,
    AuditAction.USER_DEACTIVATED.value,
    AuditAction.USER_REACTIVATED.value,
    AuditAction.ROLE_CHANGED.value,
    AuditAction.INVITATION_SENT.value,
    AuditAction.INVITATION_ACCEPTED.value,
]

DOC_ACTIONS = [
    AuditAction.DOCUMENT_UPLOADED.value,
    AuditAction.DOCUMENT_DOWNLOADED.value,
    AuditAction.DOCUMENT_DELETED.value,
]


# ===================================================================
# AUDIT ACTION ENUM
# ===================================================================

class TestAuditActionEnum:

    @pytest.mark.parametrize("action", list(AuditAction))
    def test_all_actions_are_strings(self, action):
        assert isinstance(action.value, str)

    def test_total_action_count(self):
        assert len(AuditAction) >= 25

    @pytest.mark.parametrize("action_name,expected_value", [
        ("LOGIN", "login"),
        ("LOGOUT", "logout"),
        ("LOGIN_FAILED", "login_failed"),
        ("USER_CREATED", "user_created"),
        ("DOCUMENT_UPLOADED", "document_uploaded"),
        ("RETURN_CREATED", "return_created"),
        ("SUBSCRIPTION_CHANGED", "subscription_changed"),
        ("SETTINGS_UPDATED", "settings_updated"),
        ("IMPERSONATION_STARTED", "impersonation_started"),
        ("DATA_EXPORTED", "data_exported"),
    ])
    def test_action_values(self, action_name, expected_value):
        assert AuditAction[action_name].value == expected_value


# ===================================================================
# LOG CREATION
# ===================================================================

class TestLogAction:

    @pytest.mark.asyncio
    async def test_log_returns_log_id(self):
        svc = _build_service()
        log_id = await svc.log_action(FIRM_ID, USER_ID, AuditAction.LOGIN.value)
        assert log_id is not None
        assert isinstance(log_id, str)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("action", ALL_ACTIONS)
    async def test_log_each_action_type(self, action):
        svc = _build_service()
        log_id = await svc.log_action(FIRM_ID, USER_ID, action)
        assert log_id

    @pytest.mark.asyncio
    async def test_log_with_resource(self):
        svc = _build_service()
        log_id = await svc.log_action(
            FIRM_ID, USER_ID, AuditAction.CLIENT_CREATED.value,
            resource_type="client", resource_id="client-123",
        )
        log = await svc.get_audit_log(FIRM_ID, log_id)
        assert log["resource_type"] == "client"
        assert log["resource_id"] == "client-123"

    @pytest.mark.asyncio
    async def test_log_with_details(self):
        svc = _build_service()
        details = {"old_role": "staff", "new_role": "admin"}
        log_id = await svc.log_action(
            FIRM_ID, USER_ID, AuditAction.ROLE_CHANGED.value,
            details=details,
        )
        log = await svc.get_audit_log(FIRM_ID, log_id)
        assert log["details"] == details

    @pytest.mark.asyncio
    async def test_log_with_ip_address(self):
        svc = _build_service()
        log_id = await svc.log_action(
            FIRM_ID, USER_ID, AuditAction.LOGIN.value,
            ip_address="192.168.1.1",
        )
        log = await svc.get_audit_log(FIRM_ID, log_id)
        assert log["ip_address"] == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_log_with_user_agent(self):
        svc = _build_service()
        log_id = await svc.log_action(
            FIRM_ID, USER_ID, AuditAction.LOGIN.value,
            user_agent="Mozilla/5.0",
        )
        log = await svc.get_audit_log(FIRM_ID, log_id)
        assert log["user_agent"] == "Mozilla/5.0"

    @pytest.mark.asyncio
    async def test_log_with_impersonator(self):
        svc = _build_service()
        log_id = await svc.log_action(
            FIRM_ID, USER_ID, AuditAction.IMPERSONATION_STARTED.value,
            impersonator_id="admin-001",
        )
        log = await svc.get_audit_log(FIRM_ID, log_id)
        assert log["impersonator_id"] == "admin-001"

    @pytest.mark.asyncio
    async def test_log_creates_integrity_hash(self):
        svc = _build_service()
        log_id = await svc.log_action(FIRM_ID, USER_ID, AuditAction.LOGIN.value)
        log = await svc.get_audit_log(FIRM_ID, log_id)
        assert "integrity_hash" in log
        assert len(log["integrity_hash"]) == 64  # SHA-256 hex

    @pytest.mark.asyncio
    async def test_log_has_timestamp(self):
        svc = _build_service()
        log_id = await svc.log_action(FIRM_ID, USER_ID, AuditAction.LOGIN.value)
        log = await svc.get_audit_log(FIRM_ID, log_id)
        datetime.fromisoformat(log["timestamp"])

    @pytest.mark.asyncio
    async def test_log_details_default_empty_dict(self):
        svc = _build_service()
        log_id = await svc.log_action(FIRM_ID, USER_ID, AuditAction.LOGIN.value)
        log = await svc.get_audit_log(FIRM_ID, log_id)
        assert log["details"] == {}

    @pytest.mark.asyncio
    async def test_multiple_logs_unique_ids(self):
        svc = _build_service()
        ids = set()
        for _ in range(10):
            log_id = await svc.log_action(FIRM_ID, USER_ID, AuditAction.LOGIN.value)
            ids.add(log_id)
        assert len(ids) == 10


# ===================================================================
# LOG RETRIEVAL & FILTERING
# ===================================================================

class TestGetAuditLogs:

    @pytest.fixture
    async def populated_service(self):
        svc = _build_service()
        await svc.log_action(FIRM_ID, "user-A", AuditAction.LOGIN.value)
        await svc.log_action(FIRM_ID, "user-A", AuditAction.CLIENT_CREATED.value,
                             resource_type="client", resource_id="c1")
        await svc.log_action(FIRM_ID, "user-B", AuditAction.DOCUMENT_UPLOADED.value,
                             resource_type="document", resource_id="d1")
        await svc.log_action(FIRM_ID, "user-B", AuditAction.LOGIN_FAILED.value,
                             ip_address="10.0.0.1")
        await svc.log_action("other-firm", "user-C", AuditAction.LOGIN.value)
        return svc

    @pytest.mark.asyncio
    async def test_filter_by_firm(self, populated_service):
        svc = populated_service
        logs = await svc.get_audit_logs(FIRM_ID)
        assert all(l["firm_id"] == FIRM_ID for l in logs)

    @pytest.mark.asyncio
    async def test_filter_by_user(self, populated_service):
        svc = populated_service
        logs = await svc.get_audit_logs(FIRM_ID, user_id="user-A")
        assert all(l["user_id"] == "user-A" for l in logs)

    @pytest.mark.asyncio
    async def test_filter_by_action(self, populated_service):
        svc = populated_service
        logs = await svc.get_audit_logs(FIRM_ID, action_filter=[AuditAction.LOGIN.value])
        assert all(l["action"] == "login" for l in logs)

    @pytest.mark.asyncio
    async def test_filter_by_resource_type(self, populated_service):
        svc = populated_service
        logs = await svc.get_audit_logs(FIRM_ID, resource_type="client")
        assert all(l["resource_type"] == "client" for l in logs)

    @pytest.mark.asyncio
    async def test_filter_by_resource_id(self, populated_service):
        svc = populated_service
        logs = await svc.get_audit_logs(FIRM_ID, resource_id="d1")
        assert all(l["resource_id"] == "d1" for l in logs)

    @pytest.mark.asyncio
    async def test_filter_by_date_range(self, populated_service):
        svc = populated_service
        now = datetime.utcnow()
        logs = await svc.get_audit_logs(
            FIRM_ID,
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
        )
        assert len(logs) >= 1

    @pytest.mark.asyncio
    async def test_pagination_limit(self, populated_service):
        svc = populated_service
        logs = await svc.get_audit_logs(FIRM_ID, limit=2)
        assert len(logs) <= 2

    @pytest.mark.asyncio
    async def test_pagination_offset(self, populated_service):
        svc = populated_service
        all_logs = await svc.get_audit_logs(FIRM_ID)
        offset_logs = await svc.get_audit_logs(FIRM_ID, offset=1)
        if len(all_logs) > 1:
            assert len(offset_logs) == len(all_logs) - 1

    @pytest.mark.asyncio
    async def test_logs_sorted_by_timestamp_desc(self, populated_service):
        svc = populated_service
        logs = await svc.get_audit_logs(FIRM_ID)
        timestamps = [l["timestamp"] for l in logs]
        assert timestamps == sorted(timestamps, reverse=True)

    @pytest.mark.asyncio
    async def test_filter_multiple_actions(self, populated_service):
        svc = populated_service
        logs = await svc.get_audit_logs(
            FIRM_ID,
            action_filter=[AuditAction.LOGIN.value, AuditAction.LOGIN_FAILED.value],
        )
        for log in logs:
            assert log["action"] in ["login", "login_failed"]


class TestGetAuditLog:

    @pytest.mark.asyncio
    async def test_get_single_log(self):
        svc = _build_service()
        log_id = await svc.log_action(FIRM_ID, USER_ID, AuditAction.LOGIN.value)
        log = await svc.get_audit_log(FIRM_ID, log_id)
        assert log is not None
        assert log["log_id"] == log_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_log(self):
        svc = _build_service()
        assert await svc.get_audit_log(FIRM_ID, "nope") is None

    @pytest.mark.asyncio
    async def test_get_log_wrong_firm(self):
        svc = _build_service()
        log_id = await svc.log_action(FIRM_ID, USER_ID, AuditAction.LOGIN.value)
        assert await svc.get_audit_log("other-firm", log_id) is None


# ===================================================================
# ACTIVITY TRACKING
# ===================================================================

class TestUserActivity:

    @pytest.mark.asyncio
    async def test_user_activity_summary(self):
        svc = _build_service()
        await svc.log_action(FIRM_ID, USER_ID, AuditAction.LOGIN.value)
        await svc.log_action(FIRM_ID, USER_ID, AuditAction.CLIENT_CREATED.value)
        result = await svc.get_user_activity(FIRM_ID, USER_ID)
        assert result["total_actions"] == 2
        assert result["user_id"] == USER_ID

    @pytest.mark.asyncio
    async def test_user_activity_action_breakdown(self):
        svc = _build_service()
        await svc.log_action(FIRM_ID, USER_ID, AuditAction.LOGIN.value)
        await svc.log_action(FIRM_ID, USER_ID, AuditAction.LOGIN.value)
        result = await svc.get_user_activity(FIRM_ID, USER_ID)
        assert result["action_breakdown"]["login"] == 2

    @pytest.mark.asyncio
    async def test_user_activity_last_login(self):
        svc = _build_service()
        await svc.log_action(FIRM_ID, USER_ID, AuditAction.LOGIN.value)
        result = await svc.get_user_activity(FIRM_ID, USER_ID)
        assert result["last_login"] is not None

    @pytest.mark.asyncio
    async def test_user_activity_no_logins(self):
        svc = _build_service()
        await svc.log_action(FIRM_ID, USER_ID, AuditAction.CLIENT_CREATED.value)
        result = await svc.get_user_activity(FIRM_ID, USER_ID)
        assert result["last_login"] is None

    @pytest.mark.asyncio
    async def test_user_activity_most_common(self):
        svc = _build_service()
        for _ in range(5):
            await svc.log_action(FIRM_ID, USER_ID, AuditAction.CLIENT_ACCESSED.value)
        await svc.log_action(FIRM_ID, USER_ID, AuditAction.LOGIN.value)
        result = await svc.get_user_activity(FIRM_ID, USER_ID)
        assert result["most_common_action"] == "client_accessed"

    @pytest.mark.asyncio
    async def test_user_activity_empty(self):
        svc = _build_service()
        result = await svc.get_user_activity(FIRM_ID, USER_ID)
        assert result["total_actions"] == 0
        assert result["most_common_action"] is None


class TestFirmActivitySummary:

    @pytest.mark.asyncio
    async def test_firm_activity_summary(self):
        svc = _build_service()
        await svc.log_action(FIRM_ID, "u1", AuditAction.LOGIN.value)
        await svc.log_action(FIRM_ID, "u2", AuditAction.LOGIN.value)
        result = await svc.get_firm_activity_summary(FIRM_ID)
        assert result["total_actions"] == 2
        assert result["unique_users"] == 2

    @pytest.mark.asyncio
    async def test_firm_activity_top_users(self):
        svc = _build_service()
        for _ in range(5):
            await svc.log_action(FIRM_ID, "power-user", AuditAction.CLIENT_ACCESSED.value)
        await svc.log_action(FIRM_ID, "casual", AuditAction.LOGIN.value)
        result = await svc.get_firm_activity_summary(FIRM_ID)
        assert result["top_users"][0]["user_id"] == "power-user"


class TestRecentActivity:

    @pytest.mark.asyncio
    async def test_recent_activity_returns_feed(self):
        svc = _build_service()
        await svc.log_action(FIRM_ID, USER_ID, AuditAction.LOGIN.value)
        await svc.log_action(FIRM_ID, USER_ID, AuditAction.CLIENT_CREATED.value,
                             resource_type="client", resource_id="c1")
        feed = await svc.get_recent_activity(FIRM_ID)
        assert len(feed) == 2
        assert "description" in feed[0]

    @pytest.mark.asyncio
    async def test_recent_activity_respects_limit(self):
        svc = _build_service()
        for _ in range(10):
            await svc.log_action(FIRM_ID, USER_ID, AuditAction.LOGIN.value)
        feed = await svc.get_recent_activity(FIRM_ID, limit=3)
        assert len(feed) == 3

    @pytest.mark.asyncio
    async def test_recent_activity_ordered_newest_first(self):
        svc = _build_service()
        await svc.log_action(FIRM_ID, USER_ID, AuditAction.LOGIN.value)
        await svc.log_action(FIRM_ID, USER_ID, AuditAction.LOGOUT.value)
        feed = await svc.get_recent_activity(FIRM_ID)
        assert feed[0]["timestamp"] >= feed[-1]["timestamp"]


# ===================================================================
# SUSPICIOUS ACTIVITY DETECTION
# ===================================================================

class TestComplianceFlags:

    def test_flags_many_failed_logins(self):
        svc = _build_service()
        logs = [
            {"action": AuditAction.LOGIN_FAILED.value, "impersonator_id": None}
            for _ in range(15)
        ]
        flags = svc._check_compliance_flags(logs)
        assert any(f["type"] == "security" for f in flags)

    def test_flags_mfa_disabled(self):
        svc = _build_service()
        logs = [{"action": AuditAction.MFA_DISABLED.value, "impersonator_id": None}]
        flags = svc._check_compliance_flags(logs)
        assert any("MFA" in f["message"] for f in flags)

    def test_flags_impersonation(self):
        svc = _build_service()
        logs = [{"action": AuditAction.LOGIN.value, "impersonator_id": "admin-1"}]
        flags = svc._check_compliance_flags(logs)
        assert any("impersonation" in f["message"].lower() for f in flags)

    def test_no_flags_normal_activity(self):
        svc = _build_service()
        logs = [
            {"action": AuditAction.LOGIN.value, "impersonator_id": None},
            {"action": AuditAction.CLIENT_CREATED.value, "impersonator_id": None},
        ]
        flags = svc._check_compliance_flags(logs)
        assert len(flags) == 0

    def test_flags_severity_values(self):
        svc = _build_service()
        logs = [{"action": AuditAction.LOGIN_FAILED.value, "impersonator_id": None}] * 15
        flags = svc._check_compliance_flags(logs)
        for f in flags:
            assert f["severity"] in ["error", "warning", "info"]

    @pytest.mark.parametrize("fail_count,should_flag", [
        (5, False), (10, False), (11, True), (50, True),
    ])
    def test_failed_login_threshold(self, fail_count, should_flag):
        svc = _build_service()
        logs = [{"action": AuditAction.LOGIN_FAILED.value, "impersonator_id": None}] * fail_count
        flags = svc._check_compliance_flags(logs)
        has_flag = any("failed login" in f["message"].lower() for f in flags)
        assert has_flag == should_flag


# ===================================================================
# COMPLIANCE REPORTING
# ===================================================================

class TestComplianceReport:

    @pytest.mark.asyncio
    async def test_compliance_report_structure(self):
        svc = _build_service()
        await svc.log_action(FIRM_ID, USER_ID, AuditAction.LOGIN.value)
        await svc.log_action(FIRM_ID, USER_ID, AuditAction.LOGIN_FAILED.value)
        await svc.log_action(FIRM_ID, USER_ID, AuditAction.CLIENT_ACCESSED.value)
        now = datetime.utcnow()
        report = await svc.generate_compliance_report(
            FIRM_ID, now - timedelta(days=30), now + timedelta(hours=1),
        )
        assert "summary" in report
        assert "security_events" in report
        assert "data_access_events" in report
        assert "compliance_flags" in report

    @pytest.mark.asyncio
    async def test_compliance_report_counts(self):
        svc = _build_service()
        await svc.log_action(FIRM_ID, USER_ID, AuditAction.LOGIN_FAILED.value)
        await svc.log_action(FIRM_ID, USER_ID, AuditAction.PASSWORD_CHANGED.value)
        now = datetime.utcnow()
        report = await svc.generate_compliance_report(
            FIRM_ID, now - timedelta(days=1), now + timedelta(hours=1),
        )
        assert report["summary"]["security_events"] == 2

    @pytest.mark.asyncio
    async def test_compliance_report_date_range(self):
        svc = _build_service()
        now = datetime.utcnow()
        report = await svc.generate_compliance_report(
            FIRM_ID, now - timedelta(days=30), now,
        )
        assert report["report_period"]["start"] is not None
        assert report["report_period"]["end"] is not None


class TestAccessReport:

    @pytest.mark.asyncio
    async def test_access_report_for_resource(self):
        svc = _build_service()
        await svc.log_action(FIRM_ID, "u1", AuditAction.CLIENT_ACCESSED.value,
                             resource_type="client", resource_id="c1")
        await svc.log_action(FIRM_ID, "u2", AuditAction.CLIENT_ACCESSED.value,
                             resource_type="client", resource_id="c1")
        report = await svc.generate_access_report(FIRM_ID, "client", "c1")
        assert report["total_accesses"] == 2
        assert report["unique_users"] == 2

    @pytest.mark.asyncio
    async def test_access_report_empty(self):
        svc = _build_service()
        report = await svc.generate_access_report(FIRM_ID, "client", "nonexistent")
        assert report["total_accesses"] == 0
        assert report["first_access"] is None


# ===================================================================
# RETENTION POLICIES
# ===================================================================

class TestRetentionPolicy:

    @pytest.mark.asyncio
    async def test_retention_policy_structure(self):
        svc = _build_service()
        policy = await svc.get_retention_policy(FIRM_ID)
        assert "audit_logs" in policy
        assert "client_data" in policy
        assert "session_data" in policy

    @pytest.mark.asyncio
    async def test_audit_log_retention_days(self):
        svc = _build_service()
        policy = await svc.get_retention_policy(FIRM_ID)
        assert policy["audit_logs"]["retention_days"] >= 2555  # 7 years

    @pytest.mark.asyncio
    async def test_session_data_retention(self):
        svc = _build_service()
        policy = await svc.get_retention_policy(FIRM_ID)
        assert policy["session_data"]["retention_days"] == 90


class TestRetentionCompliance:

    @pytest.mark.asyncio
    async def test_retention_compliance_check(self):
        svc = _build_service()
        result = await svc.check_retention_compliance(FIRM_ID)
        assert result["is_compliant"] is True
        assert len(result["checks"]) > 0

    @pytest.mark.asyncio
    async def test_retention_next_review_date(self):
        svc = _build_service()
        result = await svc.check_retention_compliance(FIRM_ID)
        datetime.fromisoformat(result["next_review_date"])


# ===================================================================
# LOG INTEGRITY VERIFICATION
# ===================================================================

class TestLogIntegrity:

    @pytest.mark.asyncio
    async def test_verify_valid_log(self):
        svc = _build_service()
        log_id = await svc.log_action(FIRM_ID, USER_ID, AuditAction.LOGIN.value)
        assert await svc.verify_log_integrity(log_id) is True

    @pytest.mark.asyncio
    async def test_verify_tampered_log(self):
        svc = _build_service()
        log_id = await svc.log_action(FIRM_ID, USER_ID, AuditAction.LOGIN.value)
        # Tamper with the log
        for log in svc._audit_logs:
            if log["log_id"] == log_id:
                log["action"] = "tampered_action"
                break
        assert await svc.verify_log_integrity(log_id) is False

    @pytest.mark.asyncio
    async def test_verify_nonexistent_log(self):
        svc = _build_service()
        assert await svc.verify_log_integrity("nope") is False


# ===================================================================
# ACTION DESCRIPTIONS
# ===================================================================

class TestActionDescriptions:

    @pytest.mark.parametrize("action,contains", [
        (AuditAction.LOGIN.value, "Logged in"),
        (AuditAction.LOGOUT.value, "Logged out"),
        (AuditAction.LOGIN_FAILED.value, "Failed login"),
        (AuditAction.PASSWORD_CHANGED.value, "Changed password"),
        (AuditAction.MFA_ENABLED.value, "two-factor"),
        (AuditAction.MFA_DISABLED.value, "two-factor"),
        (AuditAction.SETTINGS_UPDATED.value, "Updated settings"),
    ])
    def test_action_descriptions(self, action, contains):
        svc = _build_service()
        log = {"action": action, "resource_type": "", "resource_id": ""}
        desc = svc._get_action_description(log)
        assert contains.lower() in desc.lower()

    def test_unknown_action_description(self):
        svc = _build_service()
        log = {"action": "custom_action", "resource_type": "", "resource_id": ""}
        desc = svc._get_action_description(log)
        assert "custom_action" in desc

    @pytest.mark.parametrize("action", [
        AuditAction.USER_CREATED.value,
        AuditAction.USER_UPDATED.value,
        AuditAction.USER_DEACTIVATED.value,
    ])
    def test_user_action_descriptions_include_resource_id(self, action):
        svc = _build_service()
        log = {"action": action, "resource_type": "user", "resource_id": "user-xyz"}
        desc = svc._get_action_description(log)
        assert "user-xyz" in desc


# ===================================================================
# AUDIT EXPORT FORMATTING
# ===================================================================

class TestAuditExport:
    """Tests for audit log export as JSON/CSV."""

    @pytest.mark.asyncio
    async def test_export_as_json(self):
        svc = _build_service()
        await svc.log_action(FIRM_ID, USER_ID, AuditAction.LOGIN.value)
        logs = await svc.get_audit_logs(FIRM_ID)
        json_str = json.dumps(logs)
        parsed = json.loads(json_str)
        assert len(parsed) == 1

    @pytest.mark.asyncio
    async def test_export_as_csv_headers(self):
        svc = _build_service()
        await svc.log_action(FIRM_ID, USER_ID, AuditAction.LOGIN.value)
        logs = await svc.get_audit_logs(FIRM_ID)
        if logs:
            headers = list(logs[0].keys())
            assert "log_id" in headers
            assert "action" in headers
            assert "timestamp" in headers

    @pytest.mark.asyncio
    async def test_export_empty_logs(self):
        svc = _build_service()
        logs = await svc.get_audit_logs(FIRM_ID)
        assert json.dumps(logs) == "[]"

    @pytest.mark.asyncio
    async def test_export_large_batch(self):
        svc = _build_service()
        for i in range(50):
            await svc.log_action(FIRM_ID, f"user-{i}", AuditAction.LOGIN.value)
        logs = await svc.get_audit_logs(FIRM_ID, limit=100)
        json_str = json.dumps(logs)
        assert len(json.loads(json_str)) == 50
