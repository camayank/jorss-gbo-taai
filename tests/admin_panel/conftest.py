"""
Pytest fixtures for admin panel tests.

Provides mock data and fixtures for testing:
- Firm context and tenant data
- Subscription and billing data
- Team member management
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class MockUser:
    """Mock user for testing authentication."""
    user_id: str
    email: str
    name: str
    role: str
    firm_id: Optional[str] = None
    permissions: list = None

    def __post_init__(self):
        if self.permissions is None:
            self.permissions = []


@dataclass
class MockFirm:
    """Mock firm for tenant context."""
    firm_id: str
    name: str
    subscription_tier: str = "professional"
    is_active: bool = True
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@pytest.fixture
def mock_firm_id():
    """Generate a unique firm ID for testing."""
    return str(uuid4())


@pytest.fixture
def mock_user_id():
    """Generate a unique user ID for testing."""
    return str(uuid4())


@pytest.fixture
def mock_firm_context(mock_firm_id):
    """Create a mock firm context for testing."""
    return MockFirm(
        firm_id=mock_firm_id,
        name="Test CPA Firm LLC",
        subscription_tier="professional",
        is_active=True,
    )


@pytest.fixture
def mock_admin_user(mock_user_id, mock_firm_id):
    """Create a mock admin user."""
    return MockUser(
        user_id=mock_user_id,
        email="admin@testfirm.com",
        name="Admin User",
        role="firm_admin",
        firm_id=mock_firm_id,
        permissions=["manage_team", "manage_billing", "view_analytics"],
    )


@pytest.fixture
def mock_platform_admin(mock_user_id):
    """Create a mock platform admin (super admin)."""
    return MockUser(
        user_id=mock_user_id,
        email="superadmin@platform.com",
        name="Platform Admin",
        role="platform_admin",
        firm_id=None,
        permissions=["*"],
    )


@pytest.fixture
def mock_subscription_data(mock_firm_id):
    """Create mock subscription data."""
    return {
        "subscription_id": str(uuid4()),
        "firm_id": mock_firm_id,
        "plan_id": str(uuid4()),
        "plan_name": "Professional",
        "status": "active",
        "billing_cycle": "monthly",
        "monthly_price": 199.00,
        "annual_price": 1990.00,
        "current_period_start": datetime.utcnow().isoformat(),
        "current_period_end": (datetime.utcnow() + timedelta(days=30)).isoformat(),
        "seats_included": 5,
        "seats_used": 3,
        "features": {
            "ai_advisor": True,
            "document_ocr": True,
            "multi_state": True,
            "api_access": False,
            "white_label": False,
        },
    }


@pytest.fixture
def mock_team_member(mock_user_id, mock_firm_id):
    """Create a mock team member."""
    return {
        "user_id": mock_user_id,
        "firm_id": mock_firm_id,
        "email": "preparer@testfirm.com",
        "name": "Tax Preparer",
        "role": "preparer",
        "status": "active",
        "invited_at": datetime.utcnow().isoformat(),
        "joined_at": datetime.utcnow().isoformat(),
        "last_active": datetime.utcnow().isoformat(),
        "permissions": ["prepare_returns", "view_clients"],
    }


@pytest.fixture
def mock_team_invitation():
    """Create a mock team invitation."""
    return {
        "invitation_id": str(uuid4()),
        "email": "newmember@example.com",
        "role": "preparer",
        "status": "pending",
        "invited_by": "admin@testfirm.com",
        "invited_at": datetime.utcnow().isoformat(),
        "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat(),
    }


@pytest.fixture
def mock_dashboard_metrics():
    """Create mock dashboard metrics."""
    return {
        "returns_in_progress": 15,
        "returns_completed_this_month": 42,
        "revenue_this_month": 12500.00,
        "clients_active": 78,
        "documents_pending": 5,
        "alerts": [
            {
                "type": "deadline",
                "message": "Q1 estimated payments due in 5 days",
                "severity": "warning",
            },
        ],
    }


@pytest.fixture
def mock_activity_feed():
    """Create mock activity feed data."""
    return [
        {
            "activity_id": str(uuid4()),
            "type": "return_submitted",
            "user": "preparer@testfirm.com",
            "description": "Filed return for John Smith",
            "timestamp": datetime.utcnow().isoformat(),
        },
        {
            "activity_id": str(uuid4()),
            "type": "document_uploaded",
            "user": "client@example.com",
            "description": "Uploaded W-2 form",
            "timestamp": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
        },
    ]


@pytest.fixture
def mock_invoice_data(mock_firm_id):
    """Create mock invoice data."""
    return {
        "invoice_id": str(uuid4()),
        "firm_id": mock_firm_id,
        "amount": 199.00,
        "status": "paid",
        "due_date": datetime.utcnow().isoformat(),
        "paid_at": datetime.utcnow().isoformat(),
        "payment_method": "card",
        "description": "Professional Plan - Monthly",
    }
