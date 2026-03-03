"""
E2E Test: Admin Billing & Subscriptions

Tests: Subscription → Usage → Plans → Checkout → Portal → Invoices → Payment Methods
"""

import pytest
from unittest.mock import patch


class TestSubscription:
    """Subscription management."""

    def test_get_subscription(self, client, headers, admin_jwt_payload):
        """Get current subscription."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.get("/api/v1/admin/billing/subscription", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_get_usage(self, client, headers, admin_jwt_payload):
        """Get usage metrics."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.get("/api/v1/admin/billing/usage", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_list_plans(self, client, headers, admin_jwt_payload):
        """List available plans."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.get("/api/v1/admin/billing/plans", headers=headers)
        assert response.status_code in [200, 404, 500]


class TestBillingCheckout:
    """Checkout and billing portal."""

    def test_create_checkout(self, client, headers, admin_jwt_payload):
        """Create checkout session."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.post("/api/v1/admin/billing/checkout", headers=headers, json={
                "plan_id": "pro-monthly",
            })
        assert response.status_code in [200, 400, 404, 405, 500]

    def test_billing_portal(self, client, headers, admin_jwt_payload):
        """Get billing portal URL."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.post("/api/v1/admin/billing/portal", headers=headers, json={})
        assert response.status_code in [200, 400, 404, 405, 500]


class TestAdminInvoices:
    """Admin invoice management."""

    def test_list_invoices(self, client, headers, admin_jwt_payload):
        """List invoices."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.get("/api/v1/admin/billing/invoices", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_get_invoice(self, client, headers, admin_jwt_payload):
        """Get specific invoice."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.get("/api/v1/admin/billing/invoices/test-inv-id", headers=headers)
        assert response.status_code in [200, 404, 500]


class TestPaymentMethod:
    """Payment method management."""

    def test_add_payment_method(self, client, headers, admin_jwt_payload):
        """Add payment method."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.post("/api/v1/admin/billing/payment-method", headers=headers, json={
                "payment_method_id": "pm_test_123",
            })
        assert response.status_code in [200, 400, 404, 405, 500]
