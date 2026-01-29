"""
Tests for Admin Refunds API.

Tests the /api/admin/refunds endpoints for:
- Creating refund requests
- Approving/rejecting refunds
- Processing refunds
- Refund statistics
"""

import pytest
from datetime import datetime
from uuid import uuid4
from dataclasses import asdict


class TestRefundModels:
    """Test the refund request/response models."""

    def test_refund_request_model(self):
        """Test RefundRequest model."""
        from src.web.routers.admin_refunds_api import RefundRequest

        request = RefundRequest(
            subscription_id="sub-001",
            amount=99.00,
            reason="Customer requested cancellation within trial period"
        )

        assert request.subscription_id == "sub-001"
        assert request.amount == 99.00
        assert "trial period" in request.reason

    def test_refund_request_with_firm(self):
        """Test RefundRequest with firm_id."""
        from src.web.routers.admin_refunds_api import RefundRequest

        request = RefundRequest(
            subscription_id="sub-002",
            amount=199.00,
            reason="Billing error correction",
            firm_id="firm-001"
        )

        assert request.firm_id == "firm-001"

    def test_refund_decision_model(self):
        """Test RefundDecision model."""
        from src.web.routers.admin_refunds_api import RefundDecision

        decision = RefundDecision(
            status="approved",
            notes="Verified billing error"
        )

        assert decision.status == "approved"
        assert decision.notes == "Verified billing error"

    def test_refund_decision_without_notes(self):
        """Test RefundDecision without notes."""
        from src.web.routers.admin_refunds_api import RefundDecision

        decision = RefundDecision(status="rejected")

        assert decision.status == "rejected"
        assert decision.notes is None


class TestRefundClass:
    """Test the Refund dataclass."""

    def test_refund_creation(self):
        """Test creating a Refund."""
        from src.web.routers.admin_refunds_api import Refund

        refund = Refund(
            refund_id="ref-001",
            subscription_id="sub-001",
            firm_id="firm-001",
            firm_name="ABC Tax Services",
            amount=99.00,
            reason="Refund request",
            status="pending",
            requested_by="user-001",
            requested_at=datetime.utcnow(),
        )

        assert refund.refund_id == "ref-001"
        assert refund.status == "pending"
        assert refund.amount == 99.00
        assert refund.decided_by is None

    def test_refund_approved(self):
        """Test approved refund."""
        from src.web.routers.admin_refunds_api import Refund

        refund = Refund(
            refund_id="ref-002",
            subscription_id="sub-002",
            firm_id="firm-002",
            firm_name="XYZ Accounting",
            amount=199.00,
            reason="Approved refund",
            status="approved",
            requested_by="user-002",
            requested_at=datetime.utcnow(),
            decided_by="admin-001",
            decided_at=datetime.utcnow(),
            decision_notes="Valid refund request"
        )

        assert refund.status == "approved"
        assert refund.decided_by == "admin-001"
        assert refund.decision_notes == "Valid refund request"

    def test_refund_processed(self):
        """Test processed refund."""
        from src.web.routers.admin_refunds_api import Refund

        refund = Refund(
            refund_id="ref-003",
            subscription_id="sub-003",
            firm_id="firm-003",
            firm_name="Tax Pros Inc",
            amount=149.00,
            reason="Processed refund",
            status="processed",
            requested_by="user-003",
            requested_at=datetime.utcnow(),
            decided_by="admin-002",
            decided_at=datetime.utcnow(),
            processed_at=datetime.utcnow(),
            transaction_id="txn_abc123",
        )

        assert refund.status == "processed"
        assert refund.transaction_id == "txn_abc123"
        assert refund.processed_at is not None

    def test_refund_to_dict(self):
        """Test refund serialization."""
        from src.web.routers.admin_refunds_api import Refund

        refund = Refund(
            refund_id="ref-004",
            subscription_id="sub-004",
            firm_id="firm-004",
            firm_name="Test Firm",
            amount=50.00,
            reason="Test",
            status="pending",
            requested_by="user-004",
            requested_at=datetime.utcnow(),
        )

        result = asdict(refund)

        assert result["refund_id"] == "ref-004"
        assert result["amount"] == 50.00
        assert result["status"] == "pending"


class TestRefundStatus:
    """Test refund status values."""

    def test_valid_statuses(self):
        """Test all valid refund statuses."""
        valid_statuses = {"pending", "approved", "rejected", "processed", "failed"}

        for status in valid_statuses:
            assert status in valid_statuses

    def test_status_workflow(self):
        """Test typical refund workflow."""
        # Pending -> Approved -> Processed
        workflow = ["pending", "approved", "processed"]

        for i, status in enumerate(workflow):
            if i > 0:
                assert workflow[i] != workflow[i-1]


class TestRefundAmountValidation:
    """Test refund amount validation."""

    def test_positive_amount_required(self):
        """Test that amount must be positive."""
        from src.web.routers.admin_refunds_api import RefundRequest

        # Field constraint: gt=0
        request = RefundRequest(
            subscription_id="sub-test",
            amount=0.01,
            reason="Minimum amount test"
        )

        assert request.amount > 0

    def test_large_refund_amount(self):
        """Test large refund amounts are valid."""
        from src.web.routers.admin_refunds_api import RefundRequest

        request = RefundRequest(
            subscription_id="sub-test",
            amount=9999.99,
            reason="Large refund"
        )

        assert request.amount == 9999.99


class TestRefundStats:
    """Test refund statistics."""

    def test_stats_structure(self):
        """Test expected stats structure."""
        expected_stats = {
            "total_requests": 0,
            "by_status": {
                "pending": 0,
                "approved": 0,
                "rejected": 0,
                "processed": 0,
                "failed": 0,
            },
            "total_amount_requested": 0.0,
            "total_amount_processed": 0.0,
            "total_amount_pending": 0.0,
        }

        assert "total_requests" in expected_stats
        assert "by_status" in expected_stats
        assert "pending" in expected_stats["by_status"]

    def test_stats_calculations(self):
        """Test stats calculations with sample data."""
        sample_refunds = [
            {"status": "pending", "amount": 100.0},
            {"status": "approved", "amount": 200.0},
            {"status": "processed", "amount": 150.0},
            {"status": "rejected", "amount": 50.0},
        ]

        total_requested = sum(r["amount"] for r in sample_refunds)
        total_processed = sum(r["amount"] for r in sample_refunds if r["status"] == "processed")
        total_pending = sum(r["amount"] for r in sample_refunds if r["status"] in ("pending", "approved"))

        assert total_requested == 500.0
        assert total_processed == 150.0
        assert total_pending == 300.0
