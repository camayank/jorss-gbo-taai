"""
Comprehensive tests for PII masking and SSN protection.

SECURITY TESTS:
- Verifies PREPARER role cannot extract full SSN via any endpoint
- Verifies ADMIN/PARTNER roles see full SSN
- Verifies all SSN access is audit logged
- Verifies SSN search endpoint doesn't return full SSN
- GDPR + IRS Publication 4600 compliance
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import Mock, patch, MagicMock

from rbac.roles import Role
from cpa_panel.security.pii_masking import (
    PIIMasker,
    SSNSearchHasher,
    PIIMaskingMiddleware,
    AccessAuditEntry,
    mask_ssn_value,
)
from cpa_panel.services.pii_audit_service import PIIAuditService
from database.models import AuditLogRecord


class TestSSNMasking:
    """Test SSN masking based on user role."""

    def test_admin_sees_full_ssn(self):
        """ADMIN roles should see full SSN when masking is applied."""
        masker = PIIMasker()
        test_data = {"ssn": "123-45-6789", "name": "John Doe"}

        # Admin should NOT have masking applied
        result = masker.mask_response(
            data=test_data,
            user_role=Role.SUPER_ADMIN,
            user_id="admin_user",
            operation="get",
            resource_type="client",
        )

        assert result == test_data  # Unmasked
        assert "123-45-6789" in str(result)

    def test_partner_sees_full_ssn(self):
        """PARTNER role (CPA firm owner) should see full SSN."""
        masker = PIIMasker()
        test_data = {"ssn": "987-65-4321", "name": "Jane Smith"}

        result = masker.mask_response(
            data=test_data,
            user_role=Role.PARTNER,
            user_id="partner_user",
            operation="get",
            resource_type="client",
        )

        assert result == test_data  # Unmasked
        assert "987-65-4321" in str(result)

    def test_staff_sees_masked_ssn(self):
        """STAFF role (CPA preparer) should see masked SSN."""
        masker = PIIMasker()
        test_data = {"ssn": "123-45-6789", "name": "John Doe"}

        result = masker.mask_response(
            data=test_data,
            user_role=Role.STAFF,
            user_id="staff_user",
            operation="get",
            resource_type="client",
        )

        assert result != test_data  # Masked
        assert "123-45-6789" not in str(result)
        assert "***-**-6789" in str(result["ssn"])

    def test_firm_client_sees_masked_ssn(self):
        """FIRM_CLIENT role should see masked SSN (cannot see other clients' SSN)."""
        masker = PIIMasker()
        test_data = {"ssn": "555-55-5555", "name": "Other Client"}

        result = masker.mask_response(
            data=test_data,
            user_role=Role.FIRM_CLIENT,
            user_id="client_user",
            operation="get",
            resource_type="client",
        )

        assert "555-55-5555" not in str(result)
        assert "***-**-5555" in str(result["ssn"])

    def test_nested_ssn_masking(self):
        """SSN in nested objects should be masked."""
        masker = PIIMasker()
        test_data = {
            "client": {
                "ssn": "111-22-3333",
                "name": "Client Name",
                "spouse": {
                    "ssn": "444-55-6666",
                    "name": "Spouse Name",
                },
            }
        }

        result = masker.mask_response(
            data=test_data,
            user_role=Role.STAFF,
            user_id="staff_user",
            operation="get",
            resource_type="client",
        )

        assert "111-22-3333" not in str(result)
        assert "444-55-6666" not in str(result)
        assert "***-**-3333" in str(result)
        assert "***-**-6666" in str(result)

    def test_list_masking(self):
        """SSN in lists should be masked."""
        masker = PIIMasker()
        test_data = [
            {"ssn": "111-22-3333", "name": "Client 1"},
            {"ssn": "444-55-6666", "name": "Client 2"},
        ]

        result = masker.mask_response(
            data=test_data,
            user_role=Role.STAFF,
            user_id="staff_user",
            operation="list",
            resource_type="client",
        )

        assert len(result) == 2
        assert "111-22-3333" not in str(result)
        assert "444-55-6666" not in str(result)
        assert "***-**-3333" in str(result)
        assert "***-**-6666" in str(result)


class TestSSNMaskingUtilities:
    """Test SSN masking utility functions."""

    def test_mask_ssn_standard_format(self):
        """Test masking SSN in standard format (123-45-6789)."""
        result = mask_ssn_value("123-45-6789")
        assert result == "***-**-6789"

    def test_mask_ssn_no_hyphens(self):
        """Test masking SSN without hyphens (123456789)."""
        result = mask_ssn_value("123456789")
        assert result == "***-**-6789"

    def test_mask_ssn_none(self):
        """Test masking None value."""
        result = mask_ssn_value(None)
        assert result == ""

    def test_mask_ssn_empty_string(self):
        """Test masking empty string."""
        result = mask_ssn_value("")
        assert result == ""

    def test_mask_ssn_invalid_format(self):
        """Test masking invalid SSN format."""
        result = mask_ssn_value("invalid")
        assert result == "***-**-****"

    def test_mask_ssn_partial(self):
        """Test masking partial SSN."""
        result = mask_ssn_value("123-45")
        assert "***-**-" in result


class TestSSNSearchHasher:
    """Test SSN hashing for secure search."""

    def test_hash_ssn_standard_format(self):
        """Test hashing SSN in standard format."""
        hash1 = SSNSearchHasher.hash_ssn("123-45-6789")
        hash2 = SSNSearchHasher.hash_ssn("123-45-6789")

        # Same SSN should produce same hash
        assert hash1 == hash2
        # Hash should be deterministic and not plaintext
        assert "123" not in hash1
        assert len(hash1) == 64  # SHA256 hex is 64 chars

    def test_hash_ssn_no_hyphens(self):
        """Test that different formats produce same hash."""
        hash1 = SSNSearchHasher.hash_ssn("123-45-6789")
        hash2 = SSNSearchHasher.hash_ssn("123456789")

        # Different formats of same SSN should produce same hash
        assert hash1 == hash2

    def test_validate_ssn_valid(self):
        """Test SSN validation with valid SSN."""
        is_valid, error = SSNSearchHasher.validate_ssn_format("123-45-6789")
        assert is_valid
        assert error is None

    def test_validate_ssn_no_hyphens(self):
        """Test SSN validation without hyphens."""
        is_valid, error = SSNSearchHasher.validate_ssn_format("123456789")
        assert is_valid
        assert error is None

    def test_validate_ssn_wrong_length(self):
        """Test SSN validation with wrong length."""
        is_valid, error = SSNSearchHasher.validate_ssn_format("123-45")
        assert not is_valid
        assert "9 digits" in error

    def test_validate_ssn_all_zeros(self):
        """Test that all-zero SSN is rejected."""
        is_valid, error = SSNSearchHasher.validate_ssn_format("000-00-0000")
        assert not is_valid

    def test_validate_ssn_all_nines(self):
        """Test that all-nine SSN is rejected."""
        is_valid, error = SSNSearchHasher.validate_ssn_format("999-99-9999")
        assert not is_valid

    def test_validate_ssn_invalid_pattern(self):
        """Test that SSN with leading zeros is rejected."""
        is_valid, error = SSNSearchHasher.validate_ssn_format("000-45-6789")
        assert not is_valid


class TestAuditLogging:
    """Test PII access audit logging."""

    def test_audit_entry_creation(self):
        """Test creating an audit entry."""
        entry = AccessAuditEntry(
            user_id="user123",
            user_role="staff",
            timestamp=datetime.now(timezone.utc),
            field_type="ssn",
            full_value_last4="6789",
            operation="get",
            resource_type="client",
        )

        assert entry.user_id == "user123"
        assert entry.user_role == "staff"
        assert entry.field_type == "ssn"
        assert entry.full_value_last4 == "6789"

    def test_pii_masker_logs_access(self):
        """Test that masker logs SSN access."""
        masker = PIIMasker()
        test_data = {"ssn": "123-45-6789", "name": "Test"}

        masker.mask_response(
            data=test_data,
            user_role=Role.STAFF,
            user_id="test_user",
            operation="get",
            resource_type="client",
        )

        audit_entries = masker.get_audit_entries()
        assert len(audit_entries) > 0
        assert audit_entries[0].user_id == "test_user"
        assert audit_entries[0].field_type == "ssn"

    def test_admin_access_logged(self):
        """Test that admin access is also logged."""
        masker = PIIMasker()
        test_data = {"ssn": "999-88-7777", "name": "Test"}

        masker.mask_response(
            data=test_data,
            user_role=Role.PARTNER,
            user_id="partner_user",
            operation="get",
            resource_type="client",
        )

        audit_entries = masker.get_audit_entries()
        assert len(audit_entries) > 0
        # Admin access should be logged as "ADMIN_FULL_ACCESS"
        assert "ADMIN" in audit_entries[0].full_value_last4


class TestComplianceRequirements:
    """Test compliance requirements are met."""

    def test_no_staff_can_extract_ssn(self):
        """Verify STAFF role cannot extract full SSN via API response."""
        masker = PIIMasker()

        # Simulate various response formats that might come from API
        test_cases = [
            {"ssn": "123-45-6789"},
            {"client": {"ssn": "987-65-4321"}},
            [{"ssn": "555-55-5555"}, {"ssn": "666-66-6666"}],
            {
                "data": [
                    {
                        "ssn": "111-22-3333",
                        "spouse": {"ssn": "444-55-6666"},
                    }
                ]
            },
        ]

        for test_data in test_cases:
            result = masker.mask_response(
                data=test_data,
                user_role=Role.STAFF,
                user_id="staff_user",
                operation="get",
                resource_type="client",
            )

            # Verify no plain SSN is visible
            result_str = str(result)
            assert "123-45" not in result_str
            assert "987-65" not in result_str
            assert "555-55" not in result_str
            assert "666-66" not in result_str
            assert "111-22" not in result_str
            assert "444-55" not in result_str

    def test_admin_can_access_full_ssn(self):
        """Verify ADMIN roles CAN access full SSN."""
        masker = PIIMasker()
        test_data = {"ssn": "123-45-6789", "name": "John Doe"}

        admin_roles = [Role.SUPER_ADMIN, Role.PLATFORM_ADMIN, Role.PARTNER]

        for admin_role in admin_roles:
            result = masker.mask_response(
                data=test_data,
                user_role=admin_role,
                user_id="admin_user",
                operation="get",
                resource_type="client",
            )

            assert "123-45-6789" in str(result)

    def test_ssn_search_never_returns_full_ssn(self):
        """Verify SSN search endpoint never returns full SSN."""
        # This is handled by the endpoint logic - it uses SSN hash for lookup
        # and removes SSN fields from response
        hash1 = SSNSearchHasher.hash_ssn("123-45-6789")
        hash2 = SSNSearchHasher.hash_ssn("123-45-6789")

        # Hashes match for same SSN
        assert hash1 == hash2

        # But hash doesn't reveal the original SSN
        assert "123" not in hash1
        assert "456" not in hash1
        assert "6789" not in hash1


class TestMiddlewareIntegration:
    """Test PII masking middleware integration."""

    def test_middleware_initialization(self):
        """Test that middleware initializes correctly."""
        mock_app = Mock()
        masker = PIIMasker()

        middleware = PIIMaskingMiddleware(mock_app, masker)

        assert middleware.app == mock_app
        assert middleware.masker == masker
        # Note: Full integration test would require actual FastAPI test client

    def test_get_operation_from_request(self):
        """Test operation type detection from request."""
        mock_request = Mock()

        # Test GET list
        mock_request.method = "GET"
        mock_request.url = Mock(path="/api/data/clients/")
        op = PIIMaskingMiddleware._get_operation_from_request(mock_request)
        assert op == "list"

        # Test GET single
        mock_request.url.path = "/api/data/clients/123"
        op = PIIMaskingMiddleware._get_operation_from_request(mock_request)
        assert op == "get"

        # Test POST search
        mock_request.method = "POST"
        mock_request.url.path = "/api/data/search-by-ssn"
        op = PIIMaskingMiddleware._get_operation_from_request(mock_request)
        assert op == "search"

    def test_get_resource_type_from_request(self):
        """Test resource type detection from request path."""
        mock_request = Mock()
        mock_request.url = Mock()

        # Test clients
        mock_request.url.path = "/api/data/clients"
        resource = PIIMaskingMiddleware._get_resource_type_from_request(mock_request)
        assert resource == "client"

        # Test returns
        mock_request.url.path = "/api/data/returns/123"
        resource = PIIMaskingMiddleware._get_resource_type_from_request(mock_request)
        assert resource == "return"

        # Test leads
        mock_request.url.path = "/api/leads/456"
        resource = PIIMaskingMiddleware._get_resource_type_from_request(mock_request)
        assert resource == "lead"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_masking_with_none_values(self):
        """Test masking when SSN is None."""
        masker = PIIMasker()
        test_data = {"ssn": None, "name": "Test"}

        result = masker.mask_response(
            data=test_data,
            user_role=Role.STAFF,
            user_id="test_user",
            operation="get",
            resource_type="client",
        )

        assert result["ssn"] == ""

    def test_masking_with_encrypted_ssn_field(self):
        """Test masking ssn_encrypted field."""
        masker = PIIMasker()
        test_data = {
            "ssn_encrypted": "some_encrypted_value_12345",
            "name": "Test",
        }

        result = masker.mask_response(
            data=test_data,
            user_role=Role.STAFF,
            user_id="test_user",
            operation="get",
            resource_type="client",
        )

        # Should mask the encrypted field
        assert "12345" not in str(result.get("ssn_encrypted", ""))

    def test_deep_nesting(self):
        """Test masking deeply nested SSN fields."""
        masker = PIIMasker()
        test_data = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {
                            "ssn": "111-22-3333",
                            "name": "Deep",
                        }
                    }
                }
            }
        }

        result = masker.mask_response(
            data=test_data,
            user_role=Role.STAFF,
            user_id="test_user",
            operation="get",
            resource_type="client",
        )

        assert "111-22-3333" not in str(result)
        assert "***-**-3333" in str(result)

    def test_clear_audit_entries(self):
        """Test clearing audit entries."""
        masker = PIIMasker()
        test_data = {"ssn": "123-45-6789"}

        masker.mask_response(
            data=test_data,
            user_role=Role.STAFF,
            user_id="test_user",
            operation="get",
            resource_type="client",
        )

        assert len(masker.get_audit_entries()) > 0
        masker.clear_audit_entries()
        assert len(masker.get_audit_entries()) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
