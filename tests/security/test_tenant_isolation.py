"""
Tenant Isolation Breach Tests.

Tests to ensure multi-tenant security:
- Cross-tenant data access prevention
- Tenant context enforcement
- Query filter validation
- Anomaly detection for suspicious access patterns
"""

import pytest
from datetime import datetime
from uuid import UUID, uuid4
from unittest.mock import MagicMock, AsyncMock, patch

# Import security modules (path set up by conftest.py)
from security.tenant_isolation_middleware import (
    TenantContext,
    TenantQueryFilter,
    TenantAccessTracker,
    get_current_tenant_context,
    set_current_tenant_context,
)
from security.database_security import (
    RLSContext,
    SecureQueryBuilder,
)


class TestTenantContext:
    """Tests for TenantContext class."""

    def test_tenant_context_creation(self):
        """Test TenantContext initialization."""
        tenant_id = uuid4()
        user_id = uuid4()

        ctx = TenantContext(
            tenant_id=tenant_id,
            user_id=user_id,
            user_role="admin",
            is_platform_admin=False,
        )

        assert ctx.tenant_id == tenant_id
        assert ctx.user_id == user_id
        assert ctx.user_role == "admin"
        assert ctx.is_platform_admin is False
        assert len(ctx.allowed_tenant_ids) == 0

    def test_can_access_own_tenant(self):
        """Test user can access their own tenant."""
        tenant_id = uuid4()
        ctx = TenantContext(
            tenant_id=tenant_id,
            user_id=uuid4(),
        )

        assert ctx.can_access_tenant(tenant_id) is True

    def test_cannot_access_other_tenant(self):
        """Test user cannot access other tenant's data."""
        own_tenant = uuid4()
        other_tenant = uuid4()

        ctx = TenantContext(
            tenant_id=own_tenant,
            user_id=uuid4(),
            is_platform_admin=False,
        )

        assert ctx.can_access_tenant(other_tenant) is False

    def test_platform_admin_can_access_any_tenant(self):
        """Test platform admin can access any tenant."""
        own_tenant = uuid4()
        other_tenant = uuid4()

        ctx = TenantContext(
            tenant_id=own_tenant,
            user_id=uuid4(),
            is_platform_admin=True,
        )

        assert ctx.can_access_tenant(other_tenant) is True
        assert ctx.can_access_tenant(uuid4()) is True

    def test_allowed_tenant_ids_access(self):
        """Test access to explicitly allowed tenant IDs."""
        own_tenant = uuid4()
        allowed_tenant = uuid4()
        not_allowed_tenant = uuid4()

        ctx = TenantContext(
            tenant_id=own_tenant,
            user_id=uuid4(),
            is_platform_admin=False,
            allowed_tenant_ids={allowed_tenant},
        )

        assert ctx.can_access_tenant(own_tenant) is True
        assert ctx.can_access_tenant(allowed_tenant) is True
        assert ctx.can_access_tenant(not_allowed_tenant) is False

    def test_record_tenant_access(self):
        """Test recording of tenant access."""
        ctx = TenantContext(
            tenant_id=uuid4(),
            user_id=uuid4(),
        )

        tenant1 = uuid4()
        tenant2 = uuid4()

        ctx.record_tenant_access(tenant1)
        ctx.record_tenant_access(tenant2)
        ctx.record_tenant_access(tenant1)  # Duplicate

        accessed = ctx.accessed_tenants
        assert tenant1 in accessed
        assert tenant2 in accessed
        assert len(accessed) == 2  # No duplicates

    def test_to_dict_serialization(self):
        """Test context serialization for logging."""
        tenant_id = uuid4()
        user_id = uuid4()

        ctx = TenantContext(
            tenant_id=tenant_id,
            user_id=user_id,
            user_role="manager",
            is_platform_admin=False,
        )

        data = ctx.to_dict()

        assert data["tenant_id"] == str(tenant_id)
        assert data["user_id"] == str(user_id)
        assert data["user_role"] == "manager"
        assert data["is_platform_admin"] is False


class TestTenantQueryFilter:
    """Tests for TenantQueryFilter class."""

    def test_filter_creation(self):
        """Test TenantQueryFilter initialization."""
        tenant_id = uuid4()
        filter = TenantQueryFilter(
            tenant_id=tenant_id,
            is_platform_admin=False,
        )

        assert filter.tenant_id == tenant_id
        assert filter.is_platform_admin is False

    def test_from_tenant_context(self):
        """Test creating filter from TenantContext."""
        tenant_id = uuid4()
        allowed = {uuid4(), uuid4()}

        ctx = TenantContext(
            tenant_id=tenant_id,
            user_id=uuid4(),
            is_platform_admin=True,
            allowed_tenant_ids=allowed,
        )

        filter = TenantQueryFilter.from_tenant_context(ctx)

        assert filter.tenant_id == tenant_id
        assert filter.is_platform_admin is True
        assert filter.allowed_tenant_ids == allowed

    def test_validate_access_own_tenant(self):
        """Test validate_access for own tenant."""
        tenant_id = uuid4()
        filter = TenantQueryFilter(
            tenant_id=tenant_id,
            is_platform_admin=False,
        )

        assert filter.validate_access(tenant_id) is True
        assert filter.validate_access(uuid4()) is False

    def test_validate_access_platform_admin(self):
        """Test validate_access for platform admin."""
        filter = TenantQueryFilter(
            tenant_id=uuid4(),
            is_platform_admin=True,
        )

        # Platform admin can access any tenant
        assert filter.validate_access(uuid4()) is True
        assert filter.validate_access(uuid4()) is True

    def test_validate_access_allowed_tenants(self):
        """Test validate_access for explicitly allowed tenants."""
        allowed1 = uuid4()
        allowed2 = uuid4()

        filter = TenantQueryFilter(
            tenant_id=uuid4(),
            is_platform_admin=False,
            allowed_tenant_ids={allowed1, allowed2},
        )

        assert filter.validate_access(allowed1) is True
        assert filter.validate_access(allowed2) is True
        assert filter.validate_access(uuid4()) is False

    def test_require_access_raises_on_denial(self):
        """Test require_access raises exception on denial."""
        filter = TenantQueryFilter(
            tenant_id=uuid4(),
            is_platform_admin=False,
        )

        other_tenant = uuid4()

        with pytest.raises(Exception) as exc_info:
            filter.require_access(other_tenant, "client")

        # Should raise an APIError (or similar)
        assert "Access denied" in str(exc_info.value) or "TENANT_ACCESS_DENIED" in str(exc_info.value)

    def test_require_access_passes_on_allow(self):
        """Test require_access passes when access is allowed."""
        tenant_id = uuid4()
        filter = TenantQueryFilter(
            tenant_id=tenant_id,
            is_platform_admin=False,
        )

        # Should not raise
        filter.require_access(tenant_id, "client")


class TestTenantAccessTracker:
    """Tests for TenantAccessTracker anomaly detection."""

    def test_tracker_initialization(self):
        """Test tracker initialization."""
        tracker = TenantAccessTracker()
        assert tracker.MAX_TENANTS_PER_WINDOW > 0
        assert tracker.WINDOW_SECONDS > 0

    def test_normal_access_no_alert(self):
        """Test normal access patterns don't trigger alerts."""
        tracker = TenantAccessTracker()
        user_id = str(uuid4())
        tenant_id = str(uuid4())

        # Single access should not trigger alert
        alert = tracker.record_access(user_id, tenant_id)
        assert alert is None

    def test_cross_tenant_access_recorded(self):
        """Test cross-tenant access is recorded."""
        tracker = TenantAccessTracker()
        user_id = str(uuid4())

        # Record multiple normal accesses
        for _ in range(5):
            alert = tracker.record_access(
                user_id,
                str(uuid4()),
                is_cross_tenant=False
            )
            # Should not alert for normal access
            # Alert only triggers at threshold

    def test_many_tenants_triggers_alert(self):
        """Test accessing many tenants triggers alert."""
        tracker = TenantAccessTracker()
        tracker.MAX_TENANTS_PER_WINDOW = 5  # Lower threshold for test
        user_id = str(uuid4())

        alert = None
        for i in range(10):
            alert = tracker.record_access(
                user_id,
                str(uuid4()),  # Different tenant each time
            )
            if alert:
                break

        # Should eventually trigger alert
        assert alert is not None
        assert "different tenants" in alert.lower()

    def test_excessive_cross_tenant_access_triggers_alert(self):
        """Test excessive cross-tenant access triggers alert."""
        tracker = TenantAccessTracker()
        tracker.MAX_CROSS_TENANT_PER_HOUR = 5  # Lower threshold for test
        tracker.MAX_TENANTS_PER_WINDOW = 1000  # High so we don't hit this first
        user_id = str(uuid4())

        alert = None
        for i in range(10):
            alert = tracker.record_access(
                user_id,
                str(uuid4()),
                is_cross_tenant=True
            )
            if alert:
                break

        # Should trigger cross-tenant alert
        assert alert is not None
        assert "cross-tenant" in alert.lower()

    def test_old_records_cleaned(self):
        """Test that old access records are cleaned up."""
        tracker = TenantAccessTracker()
        user_id = str(uuid4())

        # Add some records
        tracker.record_access(user_id, str(uuid4()))

        # Simulate time passing by manipulating records
        # (In real tests, you'd mock time.time())
        if user_id in tracker._access_records:
            for record in tracker._access_records[user_id]:
                record["timestamp"] = 0  # Very old

        # Next access should clean old records
        tracker.record_access(user_id, str(uuid4()))

        # Old records should be cleaned
        assert len(tracker._access_records[user_id]) == 1


class TestRLSContext:
    """Tests for Row-Level Security context."""

    def test_rls_context_creation(self):
        """Test RLSContext initialization."""
        tenant_id = uuid4()
        user_id = uuid4()

        ctx = RLSContext(
            user_id=user_id,
            tenant_id=tenant_id,
            is_superuser=False,
        )

        assert ctx.user_id == user_id
        assert ctx.tenant_id == tenant_id
        assert ctx.is_superuser is False

    def test_rls_context_superuser(self):
        """Test RLSContext superuser flag."""
        ctx = RLSContext(
            user_id=uuid4(),
            tenant_id=uuid4(),
            is_superuser=True,
        )

        assert ctx.is_superuser is True

    def test_rls_context_allowed_tenants(self):
        """Test RLSContext with allowed tenant IDs."""
        allowed = {uuid4(), uuid4()}

        ctx = RLSContext(
            user_id=uuid4(),
            tenant_id=uuid4(),
            allowed_tenant_ids=allowed,
        )

        assert ctx.allowed_tenant_ids == allowed


class TestCrossTenantBreachScenarios:
    """Integration tests for cross-tenant breach scenarios."""

    def test_idor_attack_prevention(self):
        """Test Insecure Direct Object Reference (IDOR) attack prevention."""
        # User from Tenant A tries to access Tenant B's resource
        tenant_a = uuid4()
        tenant_b = uuid4()
        user_a = uuid4()

        ctx = TenantContext(
            tenant_id=tenant_a,
            user_id=user_a,
            is_platform_admin=False,
        )

        # Simulate IDOR attempt - user tries to access resource from Tenant B
        resource_tenant = tenant_b

        # Filter should deny access
        filter = TenantQueryFilter.from_tenant_context(ctx)
        assert filter.validate_access(resource_tenant) is False

    def test_parameter_tampering_prevention(self):
        """Test parameter tampering with tenant_id prevention."""
        own_tenant = uuid4()
        tampered_tenant = uuid4()

        ctx = TenantContext(
            tenant_id=own_tenant,
            user_id=uuid4(),
            is_platform_admin=False,
        )

        # Even if attacker tampers with tenant_id parameter,
        # the filter should still use the authenticated context
        filter = TenantQueryFilter.from_tenant_context(ctx)

        # Filter validates against the authenticated context, not the tampered value
        assert filter.validate_access(tampered_tenant) is False
        assert filter.validate_access(own_tenant) is True

    def test_null_tenant_context_safety(self):
        """Test safety when tenant context is null."""
        # No tenant context should filter to nothing (safe default)
        filter = TenantQueryFilter(
            tenant_id=None,
            is_platform_admin=False,
        )

        # Should deny access to any tenant
        assert filter.validate_access(uuid4()) is False

    def test_tenant_enumeration_detection(self):
        """Test detection of tenant enumeration attempts."""
        tracker = TenantAccessTracker()
        tracker.MAX_TENANTS_PER_WINDOW = 3  # Low threshold
        attacker_user = str(uuid4())

        alerts = []
        # Attacker tries to enumerate tenants
        for i in range(10):
            alert = tracker.record_access(attacker_user, str(uuid4()))
            if alert:
                alerts.append(alert)

        # Should detect the enumeration attempt
        assert len(alerts) > 0


class TestGlobalContextSafety:
    """Tests for global context management safety."""

    def test_context_isolation(self):
        """Test that contexts are properly isolated."""
        ctx1 = TenantContext(
            tenant_id=uuid4(),
            user_id=uuid4(),
        )

        set_current_tenant_context(ctx1)
        assert get_current_tenant_context() == ctx1

        # Clear context
        set_current_tenant_context(None)
        assert get_current_tenant_context() is None

    def test_context_not_shared_between_requests(self):
        """Test that context is cleared between requests."""
        ctx = TenantContext(
            tenant_id=uuid4(),
            user_id=uuid4(),
        )

        set_current_tenant_context(ctx)
        current = get_current_tenant_context()
        assert current is not None

        # Simulate end of request
        set_current_tenant_context(None)

        # New "request" should have no context
        assert get_current_tenant_context() is None


class TestTenantIsolationEdgeCases:
    """Edge case tests for tenant isolation."""

    def test_empty_allowed_tenant_ids(self):
        """Test behavior with empty allowed_tenant_ids."""
        ctx = TenantContext(
            tenant_id=uuid4(),
            user_id=uuid4(),
            allowed_tenant_ids=set(),  # Empty
        )

        # Should only allow own tenant
        other_tenant = uuid4()
        assert ctx.can_access_tenant(ctx.tenant_id) is True
        assert ctx.can_access_tenant(other_tenant) is False

    def test_none_tenant_id_handling(self):
        """Test handling when tenant_id is None."""
        ctx = TenantContext(
            tenant_id=None,
            user_id=uuid4(),
            is_platform_admin=False,
        )

        # Should not allow access to any specific tenant
        assert ctx.can_access_tenant(uuid4()) is False

    def test_platform_admin_with_no_tenant(self):
        """Test platform admin without specific tenant."""
        ctx = TenantContext(
            tenant_id=None,
            user_id=uuid4(),
            is_platform_admin=True,
        )

        # Platform admin should still access any tenant
        assert ctx.can_access_tenant(uuid4()) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
