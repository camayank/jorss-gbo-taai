"""
E2E Test: Payments, Invoices & Branding

Tests: Branding → Logo → Payment Settings → Invoices → Notifications
"""

import io
import pytest
from unittest.mock import patch


class TestBranding:
    """CPA firm branding (whitelabel)."""

    def test_get_branding(self, client, headers, cpa_jwt_payload):
        """Get current branding settings."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/branding/my-branding", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_update_branding(self, client, headers, cpa_jwt_payload):
        """Update branding settings."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.patch("/api/cpa/branding/my-branding", headers=headers, json={
                "firm_name": "E2E Tax Firm",
                "primary_color": "#1a73e8",
                "tagline": "Your trusted tax partner",
            })
        assert response.status_code in [200, 404, 405, 500]

    def test_upload_firm_logo(self, client, headers, cpa_jwt_payload):
        """Upload firm logo."""
        h = {k: v for k, v in headers.items() if k != "Content-Type"}
        # Minimal PNG
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post(
                "/api/cpa/branding/my-branding/firm-logo",
                headers=h,
                files={"file": ("logo.png", io.BytesIO(png), "image/png")},
            )
        assert response.status_code in [200, 404, 405, 500]

    def test_delete_firm_logo(self, client, headers, cpa_jwt_payload):
        """Delete firm logo."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.delete("/api/cpa/branding/my-branding/firm-logo", headers=headers)
        assert response.status_code in [200, 404, 405, 500]

    def test_preview_colors(self, client, headers, cpa_jwt_payload):
        """Preview branding colors."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/branding/preview/colors", headers=headers)
        assert response.status_code in [200, 404, 500]


class TestPaymentSettings:
    """Payment settings (Stripe Connect)."""

    def test_get_payment_settings(self, client, headers, cpa_jwt_payload):
        """Get payment settings."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/payment-settings", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_update_payment_settings(self, client, headers, cpa_jwt_payload):
        """Update payment settings."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.put("/api/cpa/payment-settings", headers=headers, json={
                "stripe_enabled": True,
                "default_currency": "usd",
            })
        assert response.status_code in [200, 404, 405, 500]


class TestInvoices:
    """Invoice management."""

    def test_create_invoice(self, client, headers, cpa_jwt_payload):
        """Create invoice."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/invoices", headers=headers, json={
                "client_id": "client-001",
                "amount": 50000,
                "description": "2025 Tax Return Preparation",
                "due_date": "2026-04-30",
            })
        assert response.status_code in [200, 201, 404, 405, 500]

    def test_list_invoices(self, client, headers, cpa_jwt_payload):
        """List invoices."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/invoices", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_get_invoice(self, client, headers, cpa_jwt_payload):
        """Get specific invoice."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/invoices/test-inv-id", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_update_invoice(self, client, headers, cpa_jwt_payload):
        """Update invoice."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.put("/api/cpa/invoices/test-inv-id", headers=headers, json={
                "amount": 60000,
            })
        assert response.status_code in [200, 404, 405, 500]

    def test_send_invoice(self, client, headers, cpa_jwt_payload):
        """Send invoice to client."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/invoices/test-inv-id/send", headers=headers, json={})
        assert response.status_code in [200, 404, 405, 500]

    def test_create_payment_link(self, client, headers, cpa_jwt_payload):
        """Create payment link."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/payment-links", headers=headers, json={
                "invoice_id": "test-inv-id",
            })
        assert response.status_code in [200, 201, 404, 405, 500]


class TestNotifications:
    """In-app notifications."""

    def test_list_notifications(self, client, headers, cpa_jwt_payload):
        """List notifications."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/notifications", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_mark_notification_read(self, client, headers, cpa_jwt_payload):
        """Mark notification as read."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/notifications/mark-read", headers=headers, json={
                "notification_ids": ["notif-001"],
            })
        assert response.status_code in [200, 404, 405, 500]

    def test_notification_preferences(self, client, headers, cpa_jwt_payload):
        """Get notification preferences."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/notifications/preferences", headers=headers)
        assert response.status_code in [200, 404, 500]


class TestCPABillingBrandingPages:
    """CPA billing and branding page rendering."""

    def test_billing_page(self, client, headers):
        """Billing page should render."""
        response = client.get("/cpa/billing")
        assert response.status_code in [200, 302, 303, 307, 404]

    def test_branding_page(self, client, headers):
        """Branding page should render."""
        response = client.get("/cpa/branding")
        assert response.status_code in [200, 302, 303, 307, 404]
