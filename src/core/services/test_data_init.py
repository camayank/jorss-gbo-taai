"""
Comprehensive Test Data Initialization

Creates test users, firms, tax returns, documents, scenarios, and recommendations
for all possible user types and scenarios.

Usage:
    from core.services.test_data_init import init_all_test_data
    init_all_test_data()
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any
from uuid import uuid4
import hashlib
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# TEST FIRMS
# =============================================================================

TEST_FIRMS = [
    {
        "id": "firm-001",
        "name": "Best Tax Services",
        "display_name": "Best Tax Services LLC",
        "email": "contact@besttax.com",
        "phone": "555-0100",
        "subscription_tier": "professional",
        "subscription_status": "active",
        "max_clients": 500,
        "max_team_members": 20,
    },
    {
        "id": "firm-002",
        "name": "Premier CPA Group",
        "display_name": "Premier CPA Group",
        "email": "info@premiercpa.com",
        "phone": "555-0200",
        "subscription_tier": "enterprise",
        "subscription_status": "active",
        "max_clients": 2000,
        "max_team_members": 100,
    },
    {
        "id": "firm-003",
        "name": "StartUp Tax Co",
        "display_name": "StartUp Tax Co",
        "email": "hello@startuptax.com",
        "phone": "555-0300",
        "subscription_tier": "starter",
        "subscription_status": "trial",
        "max_clients": 50,
        "max_team_members": 5,
    },
]

# =============================================================================
# TEST USERS - ALL SCENARIOS
# =============================================================================

def _hash_password(password: str) -> str:
    """Hash password for testing."""
    import os
    # SECURITY: Use environment variable for salt, or generate a secure one
    salt = os.environ.get("TEST_PASSWORD_SALT", "dev-only-salt-do-not-use-in-production")
    return hashlib.sha256(f"{password}{salt}".encode()).hexdigest()

# SECURITY: Test password should be read from environment in non-dev environments
# All test users use password from env, defaulting to a development value
import os
_default_test_password = "Password123!"
TEST_PASSWORD = os.environ.get("TEST_USER_PASSWORD", _default_test_password)
TEST_PASSWORD_HASH = _hash_password(TEST_PASSWORD)

# SECURITY WARNING: Log if using default credentials
if TEST_PASSWORD == _default_test_password:
    logger.warning("Using default test password - set TEST_USER_PASSWORD env var for production testing")

TEST_USERS = [
    # ==========================================================================
    # CONSUMER USERS (B2C - Direct users)
    # ==========================================================================
    {
        "id": "user-consumer-001",
        "email": "john.consumer@gmail.com",
        "user_type": "consumer",
        "first_name": "John",
        "last_name": "Consumer",
        "phone": "555-1001",
        "is_self_service": True,
        "email_verified": True,
        "mfa_enabled": False,
        "scenario": "Basic consumer - single filer, W-2 income only",
    },
    {
        "id": "user-consumer-002",
        "email": "mary.investor@gmail.com",
        "user_type": "consumer",
        "first_name": "Mary",
        "last_name": "Investor",
        "phone": "555-1002",
        "is_self_service": True,
        "email_verified": True,
        "mfa_enabled": True,
        "scenario": "Consumer with investments - capital gains, dividends",
    },
    {
        "id": "user-consumer-003",
        "email": "bob.freelancer@gmail.com",
        "user_type": "consumer",
        "first_name": "Bob",
        "last_name": "Freelancer",
        "phone": "555-1003",
        "is_self_service": True,
        "email_verified": True,
        "mfa_enabled": False,
        "scenario": "Self-employed - Schedule C, quarterly payments",
    },
    {
        "id": "user-consumer-004",
        "email": "sarah.family@gmail.com",
        "user_type": "consumer",
        "first_name": "Sarah",
        "last_name": "Family",
        "phone": "555-1004",
        "is_self_service": True,
        "email_verified": True,
        "mfa_enabled": False,
        "scenario": "Married filing jointly - dependents, child tax credit",
    },
    {
        "id": "user-consumer-005",
        "email": "new.user@gmail.com",
        "user_type": "consumer",
        "first_name": "New",
        "last_name": "User",
        "phone": None,
        "is_self_service": True,
        "email_verified": False,
        "mfa_enabled": False,
        "scenario": "New unverified user - onboarding not complete",
    },

    # ==========================================================================
    # CPA CLIENTS (B2B2C - Clients of CPA firms)
    # ==========================================================================
    {
        "id": "user-client-001",
        "email": "alice.client@example.com",
        "user_type": "cpa_client",
        "first_name": "Alice",
        "last_name": "Client",
        "phone": "555-2001",
        "firm_id": "firm-001",
        "assigned_cpa_id": "user-cpa-001",
        "assigned_cpa_name": "Mike Preparer",
        "is_self_service": False,
        "email_verified": True,
        "scenario": "Active CPA client - return in progress",
    },
    {
        "id": "user-client-002",
        "email": "george.business@example.com",
        "user_type": "cpa_client",
        "first_name": "George",
        "last_name": "Business",
        "phone": "555-2002",
        "firm_id": "firm-001",
        "assigned_cpa_id": "user-cpa-002",
        "assigned_cpa_name": "Lisa Reviewer",
        "is_self_service": False,
        "email_verified": True,
        "scenario": "Business owner client - Schedule C + K-1",
    },
    {
        "id": "user-client-003",
        "email": "helen.highnet@example.com",
        "user_type": "cpa_client",
        "first_name": "Helen",
        "last_name": "Highnet",
        "phone": "555-2003",
        "firm_id": "firm-002",
        "assigned_cpa_id": "user-cpa-003",
        "assigned_cpa_name": "David Senior",
        "is_self_service": False,
        "email_verified": True,
        "scenario": "High net worth client - complex return, multi-state",
    },
    {
        "id": "user-client-004",
        "email": "unassigned.client@example.com",
        "user_type": "cpa_client",
        "first_name": "Unassigned",
        "last_name": "Client",
        "phone": "555-2004",
        "firm_id": "firm-001",
        "assigned_cpa_id": None,
        "assigned_cpa_name": None,
        "is_self_service": False,
        "email_verified": True,
        "scenario": "Unassigned client - needs CPA assignment",
    },
    {
        "id": "user-client-005",
        "email": "pending.client@example.com",
        "user_type": "cpa_client",
        "first_name": "Pending",
        "last_name": "Client",
        "phone": None,
        "firm_id": "firm-003",
        "assigned_cpa_id": "user-cpa-005",
        "assigned_cpa_name": "New Preparer",
        "is_self_service": False,
        "email_verified": False,
        "scenario": "Pending client - invitation sent, not yet accepted",
    },

    # ==========================================================================
    # CPA TEAM - FIRM 001 (Best Tax Services)
    # ==========================================================================
    {
        "id": "user-firmadmin-001",
        "email": "admin@besttax.com",
        "user_type": "cpa_team",
        "first_name": "Sarah",
        "last_name": "Admin",
        "phone": "555-3001",
        "firm_id": "firm-001",
        "firm_name": "Best Tax Services",
        "cpa_role": "firm_admin",
        "ptin": "P00000001",
        "credentials": "CPA, EA",
        "email_verified": True,
        "mfa_enabled": True,
        "permissions": ["manage_team", "manage_billing", "manage_firm", "view_clients",
                       "edit_returns", "approve_returns", "manage_rbac"],
        "scenario": "Firm Admin - full access to firm",
    },
    {
        "id": "user-cpa-001",
        "email": "mike@besttax.com",
        "user_type": "cpa_team",
        "first_name": "Mike",
        "last_name": "Preparer",
        "phone": "555-3002",
        "firm_id": "firm-001",
        "firm_name": "Best Tax Services",
        "cpa_role": "senior_preparer",
        "ptin": "P00000002",
        "credentials": "CPA",
        "email_verified": True,
        "mfa_enabled": False,
        "permissions": ["view_clients", "edit_returns", "create_scenarios",
                       "send_messages", "view_documents"],
        "scenario": "Senior Preparer - can prepare and review",
    },
    {
        "id": "user-cpa-002",
        "email": "lisa@besttax.com",
        "user_type": "cpa_team",
        "first_name": "Lisa",
        "last_name": "Reviewer",
        "phone": "555-3003",
        "firm_id": "firm-001",
        "firm_name": "Best Tax Services",
        "cpa_role": "reviewer",
        "ptin": "P00000003",
        "credentials": "EA",
        "email_verified": True,
        "mfa_enabled": False,
        "permissions": ["view_clients", "view_returns", "review_returns",
                       "create_notes", "send_messages"],
        "scenario": "Reviewer - can review but not prepare",
    },
    {
        "id": "user-preparer-001",
        "email": "junior@besttax.com",
        "user_type": "cpa_team",
        "first_name": "Junior",
        "last_name": "Preparer",
        "phone": "555-3004",
        "firm_id": "firm-001",
        "firm_name": "Best Tax Services",
        "cpa_role": "preparer",
        "ptin": "P00000004",
        "credentials": None,
        "email_verified": True,
        "mfa_enabled": False,
        "permissions": ["view_clients", "edit_returns", "view_documents"],
        "scenario": "Junior Preparer - limited permissions",
    },
    {
        "id": "user-support-001",
        "email": "support@besttax.com",
        "user_type": "cpa_team",
        "first_name": "Support",
        "last_name": "Staff",
        "phone": "555-3005",
        "firm_id": "firm-001",
        "firm_name": "Best Tax Services",
        "cpa_role": "support",
        "ptin": None,
        "credentials": None,
        "email_verified": True,
        "mfa_enabled": False,
        "permissions": ["view_clients", "send_messages", "create_notes"],
        "scenario": "Support Staff - client communication only",
    },

    # ==========================================================================
    # CPA TEAM - FIRM 002 (Premier CPA Group)
    # ==========================================================================
    {
        "id": "user-firmadmin-002",
        "email": "admin@premiercpa.com",
        "user_type": "cpa_team",
        "first_name": "Robert",
        "last_name": "Director",
        "phone": "555-4001",
        "firm_id": "firm-002",
        "firm_name": "Premier CPA Group",
        "cpa_role": "firm_admin",
        "ptin": "P00000010",
        "credentials": "CPA, JD",
        "email_verified": True,
        "mfa_enabled": True,
        "permissions": ["manage_team", "manage_billing", "manage_firm", "view_clients",
                       "edit_returns", "approve_returns", "manage_rbac", "view_audit"],
        "scenario": "Enterprise Firm Admin - large firm",
    },
    {
        "id": "user-cpa-003",
        "email": "david@premiercpa.com",
        "user_type": "cpa_team",
        "first_name": "David",
        "last_name": "Senior",
        "phone": "555-4002",
        "firm_id": "firm-002",
        "firm_name": "Premier CPA Group",
        "cpa_role": "senior_preparer",
        "ptin": "P00000011",
        "credentials": "CPA",
        "email_verified": True,
        "mfa_enabled": True,
        "permissions": ["view_clients", "edit_returns", "approve_returns",
                       "create_scenarios", "send_messages"],
        "scenario": "Senior with approval rights",
    },

    # ==========================================================================
    # CPA TEAM - FIRM 003 (StartUp Tax Co - Trial)
    # ==========================================================================
    {
        "id": "user-firmadmin-003",
        "email": "owner@startuptax.com",
        "user_type": "cpa_team",
        "first_name": "Startup",
        "last_name": "Owner",
        "phone": "555-5001",
        "firm_id": "firm-003",
        "firm_name": "StartUp Tax Co",
        "cpa_role": "firm_admin",
        "ptin": "P00000020",
        "credentials": "CPA",
        "email_verified": True,
        "mfa_enabled": False,
        "permissions": ["manage_team", "manage_billing", "manage_firm", "view_clients",
                       "edit_returns", "approve_returns"],
        "scenario": "Trial firm admin - limited features",
    },
    {
        "id": "user-cpa-005",
        "email": "new@startuptax.com",
        "user_type": "cpa_team",
        "first_name": "New",
        "last_name": "Preparer",
        "phone": "555-5002",
        "firm_id": "firm-003",
        "firm_name": "StartUp Tax Co",
        "cpa_role": "preparer",
        "ptin": None,
        "credentials": None,
        "email_verified": True,
        "mfa_enabled": False,
        "permissions": ["view_clients", "edit_returns"],
        "scenario": "New preparer at trial firm",
    },

    # ==========================================================================
    # PLATFORM ADMINS
    # ==========================================================================
    {
        "id": "user-platform-001",
        "email": "superadmin@taxflow.com",
        "user_type": "platform_admin",
        "first_name": "Super",
        "last_name": "Admin",
        "phone": "555-9001",
        "firm_id": None,
        "email_verified": True,
        "mfa_enabled": True,
        "permissions": ["*"],
        "scenario": "Super Admin - full platform access",
    },
    {
        "id": "user-platform-002",
        "email": "support@taxflow.com",
        "user_type": "platform_admin",
        "first_name": "Platform",
        "last_name": "Support",
        "phone": "555-9002",
        "firm_id": None,
        "email_verified": True,
        "mfa_enabled": True,
        "permissions": ["view_firms", "view_users", "impersonate", "view_audit"],
        "scenario": "Platform Support - read + impersonate only",
    },
]

# =============================================================================
# TEST TAX RETURNS
# =============================================================================

TEST_TAX_RETURNS = [
    # Consumer returns
    {
        "id": "return-001",
        "user_id": "user-consumer-001",
        "firm_id": None,
        "tax_year": 2025,
        "return_type": "individual",
        "status": "draft",
        "gross_income": 75000.00,
        "adjusted_gross_income": 72500.00,
        "taxable_income": 57500.00,
        "total_tax": 8500.00,
        "refund_amount": 500.00,
        "amount_due": 0.00,
        "completion_percentage": 65,
        "scenario": "Consumer draft return - W-2 only",
    },
    {
        "id": "return-002",
        "user_id": "user-consumer-002",
        "firm_id": None,
        "tax_year": 2025,
        "return_type": "individual",
        "status": "in_progress",
        "gross_income": 150000.00,
        "adjusted_gross_income": 145000.00,
        "taxable_income": 130000.00,
        "total_tax": 25000.00,
        "refund_amount": 0.00,
        "amount_due": 5000.00,
        "completion_percentage": 85,
        "scenario": "Consumer with investments - owes money",
    },
    {
        "id": "return-003",
        "user_id": "user-consumer-003",
        "firm_id": None,
        "tax_year": 2025,
        "return_type": "business",
        "status": "pending_review",
        "gross_income": 95000.00,
        "adjusted_gross_income": 80000.00,
        "taxable_income": 65000.00,
        "total_tax": 10000.00,
        "refund_amount": 0.00,
        "amount_due": 10000.00,
        "completion_percentage": 100,
        "scenario": "Self-employed - Schedule C, estimated payments",
    },

    # CPA Client returns
    {
        "id": "return-004",
        "user_id": "user-client-001",
        "firm_id": "firm-001",
        "tax_year": 2025,
        "return_type": "individual",
        "status": "under_review",
        "gross_income": 185000.00,
        "adjusted_gross_income": 175000.00,
        "taxable_income": 145000.00,
        "total_tax": 25000.00,
        "refund_amount": 3000.00,
        "amount_due": 0.00,
        "completion_percentage": 100,
        "assigned_cpa_id": "user-cpa-001",
        "scenario": "CPA client - in review by preparer",
    },
    {
        "id": "return-005",
        "user_id": "user-client-002",
        "firm_id": "firm-001",
        "tax_year": 2025,
        "return_type": "business",
        "status": "approved",
        "gross_income": 320000.00,
        "adjusted_gross_income": 280000.00,
        "taxable_income": 250000.00,
        "total_tax": 55000.00,
        "refund_amount": 0.00,
        "amount_due": 5000.00,
        "completion_percentage": 100,
        "assigned_cpa_id": "user-cpa-002",
        "scenario": "Business owner - approved, ready to file",
    },
    {
        "id": "return-006",
        "user_id": "user-client-003",
        "firm_id": "firm-002",
        "tax_year": 2025,
        "return_type": "individual",
        "status": "filed",
        "gross_income": 850000.00,
        "adjusted_gross_income": 750000.00,
        "taxable_income": 680000.00,
        "total_tax": 200000.00,
        "refund_amount": 0.00,
        "amount_due": 20000.00,
        "completion_percentage": 100,
        "assigned_cpa_id": "user-cpa-003",
        "scenario": "High net worth - filed with IRS",
    },
    {
        "id": "return-007",
        "user_id": "user-client-001",
        "firm_id": "firm-001",
        "tax_year": 2025,
        "return_type": "individual",
        "status": "filed",
        "gross_income": 165000.00,
        "adjusted_gross_income": 155000.00,
        "taxable_income": 125000.00,
        "total_tax": 20000.00,
        "refund_amount": 2000.00,
        "amount_due": 0.00,
        "completion_percentage": 100,
        "assigned_cpa_id": "user-cpa-001",
        "scenario": "Prior year return - accepted by IRS",
    },
]

# =============================================================================
# TEST DOCUMENTS
# =============================================================================

TEST_DOCUMENTS = [
    # Consumer documents
    {
        "id": "doc-001",
        "user_id": "user-consumer-001",
        "firm_id": None,
        "category": "w2",
        "filename": "w2_acme_2025.pdf",
        "original_filename": "W-2 from Acme Corp.pdf",
        "file_size": 125000,
        "mime_type": "application/pdf",
        "tax_year": 2025,
        "status": "verified",
        "description": "W-2 - OCR extracted and verified",
        "uploaded_by": "user-consumer-001",
        "storage_path": "/uploads/user-consumer-001/w2_acme_2025.pdf",
    },
    {
        "id": "doc-002",
        "user_id": "user-consumer-002",
        "firm_id": None,
        "category": "1099",
        "filename": "1099div_fidelity_2025.pdf",
        "original_filename": "1099-DIV from Fidelity.pdf",
        "file_size": 85000,
        "mime_type": "application/pdf",
        "tax_year": 2025,
        "status": "verified",
        "description": "1099-DIV for dividends",
        "uploaded_by": "user-consumer-002",
        "storage_path": "/uploads/user-consumer-002/1099div_fidelity_2025.pdf",
    },
    {
        "id": "doc-003",
        "user_id": "user-consumer-002",
        "firm_id": None,
        "category": "1099",
        "filename": "1099b_schwab_2025.pdf",
        "original_filename": "1099-B from Schwab.pdf",
        "file_size": 250000,
        "mime_type": "application/pdf",
        "tax_year": 2025,
        "status": "pending",
        "description": "1099-B - needs manual review",
        "uploaded_by": "user-consumer-002",
        "storage_path": "/uploads/user-consumer-002/1099b_schwab_2025.pdf",
    },

    # CPA Client documents
    {
        "id": "doc-004",
        "user_id": "user-client-001",
        "firm_id": "firm-001",
        "category": "w2",
        "filename": "w2_techco_2025.pdf",
        "original_filename": "W-2 from TechCo.pdf",
        "file_size": 130000,
        "mime_type": "application/pdf",
        "tax_year": 2025,
        "status": "verified",
        "description": "Client uploaded W-2",
        "uploaded_by": "user-client-001",
        "storage_path": "/uploads/firm-001/user-client-001/w2_techco_2025.pdf",
    },
    {
        "id": "doc-005",
        "user_id": "user-client-001",
        "firm_id": "firm-001",
        "category": "w2",
        "filename": "w2_healthcorp_spouse_2025.pdf",
        "original_filename": "Spouse W-2 from HealthCorp.pdf",
        "file_size": 128000,
        "mime_type": "application/pdf",
        "tax_year": 2025,
        "status": "verified",
        "description": "Spouse W-2 for joint return",
        "uploaded_by": "user-client-001",
        "storage_path": "/uploads/firm-001/user-client-001/w2_healthcorp_spouse_2025.pdf",
    },
    {
        "id": "doc-006",
        "user_id": "user-client-002",
        "firm_id": "firm-001",
        "category": "1099",
        "filename": "1099k_stripe_2025.pdf",
        "original_filename": "1099-K from Stripe.pdf",
        "file_size": 95000,
        "mime_type": "application/pdf",
        "tax_year": 2025,
        "status": "verified",
        "description": "Business income from Stripe",
        "uploaded_by": "user-client-002",
        "storage_path": "/uploads/firm-001/user-client-002/1099k_stripe_2025.pdf",
    },
    {
        "id": "doc-007",
        "user_id": "user-client-003",
        "firm_id": "firm-002",
        "category": "schedule_k1",
        "filename": "k1_investment_2025.pdf",
        "original_filename": "K-1 from Investment Partnership.pdf",
        "file_size": 180000,
        "mime_type": "application/pdf",
        "tax_year": 2025,
        "status": "pending",
        "description": "Complex K-1 - manual entry needed",
        "uploaded_by": "user-client-003",
        "storage_path": "/uploads/firm-002/user-client-003/k1_investment_2025.pdf",
    },
]

# =============================================================================
# TEST SCENARIOS (What-if)
# =============================================================================

TEST_SCENARIOS = [
    {
        "id": "scenario-001",
        "user_id": "user-consumer-001",
        "firm_id": None,
        "return_id": "return-001",
        "name": "Max IRA Contribution",
        "description": "What if I contribute $7,000 to Traditional IRA",
        "status": "calculated",
        "base_tax": 8500.00,
        "scenario_tax": 6950.00,
        "tax_savings": 1550.00,
        "changes": {"traditional_ira_contribution": 7000},
        "scenario": "Consumer exploring IRA contribution",
    },
    {
        "id": "scenario-002",
        "user_id": "user-client-001",
        "firm_id": "firm-001",
        "return_id": "return-004",
        "name": "HSA Max Contribution",
        "description": "Family HSA contribution analysis",
        "status": "calculated",
        "base_tax": 25000.00,
        "scenario_tax": 23200.00,
        "tax_savings": 1800.00,
        "changes": {"hsa_contribution": 8300},
        "created_by": "user-cpa-001",
        "scenario": "CPA created scenario for client",
    },
    {
        "id": "scenario-003",
        "user_id": "user-client-002",
        "firm_id": "firm-001",
        "return_id": "return-005",
        "name": "S-Corp Election Analysis",
        "description": "Impact of S-Corp election on self-employment tax",
        "status": "draft",
        "base_tax": 55000.00,
        "scenario_tax": 48000.00,
        "tax_savings": 7000.00,
        "changes": {"entity_type": "s_corp", "reasonable_salary": 80000},
        "created_by": "user-cpa-002",
        "scenario": "Complex S-Corp analysis",
    },
]

# =============================================================================
# TEST RECOMMENDATIONS
# =============================================================================

TEST_RECOMMENDATIONS = [
    {
        "id": "rec-001",
        "user_id": "user-consumer-001",
        "firm_id": None,
        "return_id": "return-001",
        "type": "tax_savings",
        "title": "Contribute to Traditional IRA",
        "description": "You can reduce your taxable income by contributing to a Traditional IRA",
        "potential_savings": 1550.00,
        "priority": "high",
        "status": "active",
        "action_steps": [
            "Open a Traditional IRA account",
            "Contribute up to $7,000 for 2025",
            "Make contribution before April 15, 2026"
        ],
        "scenario": "AI-generated recommendation for consumer",
    },
    {
        "id": "rec-002",
        "user_id": "user-client-001",
        "firm_id": "firm-001",
        "return_id": "return-004",
        "type": "tax_savings",
        "title": "Maximize HSA Contribution",
        "description": "Family HSA contribution can provide tax benefits",
        "potential_savings": 1800.00,
        "priority": "high",
        "status": "active",
        "action_steps": [
            "Verify HSA eligibility through employer",
            "Contribute $8,300 (family limit for 2025)",
            "Keep receipts for qualified medical expenses"
        ],
        "created_by": "user-cpa-001",
        "scenario": "CPA recommendation for client",
    },
    {
        "id": "rec-003",
        "user_id": "user-client-002",
        "firm_id": "firm-001",
        "return_id": "return-005",
        "type": "business_structure",
        "title": "Consider S-Corp Election",
        "description": "S-Corp election could reduce self-employment tax",
        "potential_savings": 7000.00,
        "priority": "medium",
        "status": "in_progress",
        "action_steps": [
            "Consult with business attorney",
            "File Form 2553 for S-Corp election",
            "Set up payroll for reasonable salary",
            "Review liability insurance coverage"
        ],
        "created_by": "user-cpa-002",
        "scenario": "Complex business structure recommendation",
    },
    {
        "id": "rec-004",
        "user_id": "user-consumer-002",
        "firm_id": None,
        "return_id": "return-002",
        "type": "tax_planning",
        "title": "Tax Loss Harvesting Opportunity",
        "description": "Review portfolio for tax loss harvesting before year end",
        "potential_savings": 2500.00,
        "priority": "medium",
        "status": "active",
        "action_steps": [
            "Review investment portfolio for unrealized losses",
            "Sell positions with losses to offset gains",
            "Reinvest after 30-day wash sale period"
        ],
        "scenario": "AI-generated for investor",
    },
]

# =============================================================================
# TEST CONVERSATIONS/MESSAGES
# =============================================================================

TEST_CONVERSATIONS = [
    {
        "id": "conv-001",
        "participants": ["user-client-001", "user-cpa-001"],
        "firm_id": "firm-001",
        "subject": "W-2 Verification",
        "status": "active",
        "messages": [
            {
                "id": "msg-001",
                "sender_id": "user-cpa-001",
                "content": "Hi Alice, I received your W-2. Just need to verify the state withholding amount.",
                "sent_at": "2026-01-15T10:30:00Z",
            },
            {
                "id": "msg-002",
                "sender_id": "user-client-001",
                "content": "Hi Mike, the state withholding should be $3,200. Let me know if you need anything else.",
                "sent_at": "2026-01-15T11:45:00Z",
            },
        ],
    },
    {
        "id": "conv-002",
        "participants": ["user-client-002", "user-cpa-002"],
        "firm_id": "firm-001",
        "subject": "S-Corp Election Discussion",
        "status": "active",
        "messages": [
            {
                "id": "msg-003",
                "sender_id": "user-cpa-002",
                "content": "George, I've analyzed the S-Corp election option. It could save you about $7,000 in SE tax.",
                "sent_at": "2026-01-16T14:00:00Z",
            },
        ],
    },
]

# =============================================================================
# INITIALIZATION FUNCTIONS
# =============================================================================

def init_test_users(auth_service) -> Dict[str, Any]:
    """Initialize all test users in the auth service."""
    from core.models.user import UnifiedUser, UserType, CPARole

    results = {"created": 0, "skipped": 0, "errors": []}

    for user_data in TEST_USERS:
        try:
            # Skip if user already exists
            if auth_service._users_db.get(user_data["email"]):
                results["skipped"] += 1
                continue

            user = UnifiedUser(
                id=user_data["id"],
                email=user_data["email"],
                user_type=UserType(user_data["user_type"]),
                first_name=user_data.get("first_name", ""),
                last_name=user_data.get("last_name", ""),
                phone=user_data.get("phone"),
                password_hash=TEST_PASSWORD_HASH,
                email_verified=user_data.get("email_verified", False),
                mfa_enabled=user_data.get("mfa_enabled", False),
                is_self_service=user_data.get("is_self_service", True),
                firm_id=user_data.get("firm_id"),
                firm_name=user_data.get("firm_name"),
                cpa_role=CPARole(user_data["cpa_role"]) if user_data.get("cpa_role") else None,
                ptin=user_data.get("ptin"),
                credentials=user_data.get("credentials"),
                assigned_cpa_id=user_data.get("assigned_cpa_id"),
                assigned_cpa_name=user_data.get("assigned_cpa_name"),
                permissions=user_data.get("permissions", []),
            )

            auth_service._users_db[user.id] = user
            auth_service._users_db[user.email] = user
            results["created"] += 1

        except Exception as e:
            results["errors"].append(f"{user_data['email']}: {str(e)}")

    logger.info(f"Test users initialized: {results['created']} created, {results['skipped']} skipped")
    return results


def init_test_tax_returns(tax_returns_db: dict) -> Dict[str, Any]:
    """Initialize test tax returns."""
    from core.api.tax_returns_routes import TaxReturn, TaxReturnStatus, TaxReturnType

    results = {"created": 0, "skipped": 0, "errors": []}

    for return_data in TEST_TAX_RETURNS:
        try:
            if return_data["id"] in tax_returns_db:
                results["skipped"] += 1
                continue

            tax_return = TaxReturn(
                id=return_data["id"],
                user_id=return_data["user_id"],
                firm_id=return_data.get("firm_id"),
                tax_year=return_data["tax_year"],
                return_type=TaxReturnType(return_data["return_type"]),
                status=TaxReturnStatus(return_data["status"]),
                gross_income=return_data["gross_income"],
                adjusted_gross_income=return_data["adjusted_gross_income"],
                taxable_income=return_data["taxable_income"],
                total_tax=return_data["total_tax"],
                refund_amount=return_data["refund_amount"],
                amount_due=return_data["amount_due"],
                completion_percentage=return_data["completion_percentage"],
                assigned_cpa_id=return_data.get("assigned_cpa_id"),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            tax_returns_db[tax_return.id] = tax_return
            results["created"] += 1

        except Exception as e:
            results["errors"].append(f"{return_data['id']}: {str(e)}")

    logger.info(f"Test tax returns initialized: {results['created']} created, {results['skipped']} skipped")
    return results


def init_test_documents(documents_db: dict) -> Dict[str, Any]:
    """Initialize test documents."""
    from core.api.documents_routes import Document, DocumentCategory, DocumentStatus

    results = {"created": 0, "skipped": 0, "errors": []}

    for doc_data in TEST_DOCUMENTS:
        try:
            if doc_data["id"] in documents_db:
                results["skipped"] += 1
                continue

            document = Document(
                id=doc_data["id"],
                user_id=doc_data["user_id"],
                firm_id=doc_data.get("firm_id"),
                category=DocumentCategory(doc_data["category"]),
                filename=doc_data["filename"],
                original_filename=doc_data["original_filename"],
                file_size=doc_data["file_size"],
                mime_type=doc_data["mime_type"],
                tax_year=doc_data.get("tax_year"),
                status=DocumentStatus(doc_data["status"]),
                description=doc_data.get("description"),
                uploaded_by=doc_data["uploaded_by"],
                uploaded_at=datetime.utcnow(),
                storage_path=doc_data["storage_path"],
            )
            documents_db[document.id] = document
            results["created"] += 1

        except Exception as e:
            results["errors"].append(f"{doc_data['id']}: {str(e)}")

    logger.info(f"Test documents initialized: {results['created']} created, {results['skipped']} skipped")
    return results


def init_test_scenarios(scenarios_db: dict) -> Dict[str, Any]:
    """Initialize test scenarios."""
    from core.api.scenarios_routes import TaxScenario, ScenarioStatus

    results = {"created": 0, "skipped": 0, "errors": []}

    for scenario_data in TEST_SCENARIOS:
        try:
            if scenario_data["id"] in scenarios_db:
                results["skipped"] += 1
                continue

            scenario = TaxScenario(
                id=scenario_data["id"],
                user_id=scenario_data["user_id"],
                firm_id=scenario_data.get("firm_id"),
                return_id=scenario_data.get("return_id"),
                name=scenario_data["name"],
                description=scenario_data.get("description"),
                status=ScenarioStatus(scenario_data["status"]),
                base_tax=scenario_data.get("base_tax"),
                scenario_tax=scenario_data.get("scenario_tax"),
                tax_savings=scenario_data.get("tax_savings"),
                changes=scenario_data.get("changes", {}),
                created_by=scenario_data.get("created_by"),
            )
            scenarios_db[scenario.id] = scenario
            results["created"] += 1

        except Exception as e:
            results["errors"].append(f"{scenario_data['id']}: {str(e)}")

    logger.info(f"Test scenarios initialized: {results['created']} created, {results['skipped']} skipped")
    return results


def init_test_recommendations(recommendations_db: dict) -> Dict[str, Any]:
    """Initialize test recommendations."""
    from core.api.recommendations_routes import TaxRecommendation, RecommendationType, RecommendationPriority, RecommendationStatus

    results = {"created": 0, "skipped": 0, "errors": []}

    for rec_data in TEST_RECOMMENDATIONS:
        try:
            if rec_data["id"] in recommendations_db:
                results["skipped"] += 1
                continue

            rec = TaxRecommendation(
                id=rec_data["id"],
                user_id=rec_data["user_id"],
                firm_id=rec_data.get("firm_id"),
                return_id=rec_data.get("return_id"),
                type=RecommendationType(rec_data["type"]),
                title=rec_data["title"],
                description=rec_data["description"],
                potential_savings=rec_data.get("potential_savings"),
                priority=RecommendationPriority(rec_data["priority"]),
                status=RecommendationStatus(rec_data["status"]),
                action_steps=rec_data.get("action_steps", []),
                created_by=rec_data.get("created_by"),
            )
            recommendations_db[rec.id] = rec
            results["created"] += 1

        except Exception as e:
            results["errors"].append(f"{rec_data['id']}: {str(e)}")

    logger.info(f"Test recommendations initialized: {results['created']} created, {results['skipped']} skipped")
    return results


def init_all_test_data() -> Dict[str, Any]:
    """
    Initialize all test data for the platform.

    This function populates all mock databases with comprehensive test data
    covering all user types and scenarios.

    Returns:
        Dictionary with initialization results for each data type.
    """
    results = {}

    try:
        # Import the data stores
        from core.services.auth_service import CoreAuthService
        from core.api import tax_returns_routes, documents_routes, scenarios_routes, recommendations_routes

        # Get or create auth service instance
        auth_service = CoreAuthService()

        # Initialize users
        results["users"] = init_test_users(auth_service)

        # Initialize tax returns
        results["tax_returns"] = init_test_tax_returns(tax_returns_routes._tax_returns_db)

        # Initialize documents
        results["documents"] = init_test_documents(documents_routes._documents_db)

        # Initialize scenarios
        results["scenarios"] = init_test_scenarios(scenarios_routes._scenarios_db)

        # Initialize recommendations
        results["recommendations"] = init_test_recommendations(recommendations_routes._recommendations_db)

        logger.info("All test data initialized successfully")

    except Exception as e:
        logger.error(f"Error initializing test data: {e}")
        results["error"] = str(e)

    return results


def get_test_user_credentials() -> List[Dict[str, str]]:
    """Get list of test user info for testing (passwords excluded)."""
    return [
        {
            "email": user["email"],
            "user_type": user["user_type"],
            "scenario": user.get("scenario", ""),
        }
        for user in TEST_USERS
    ]


def print_test_users_summary():
    """Print summary of all test users (dev environments only)."""
    _env = os.environ.get("APP_ENVIRONMENT", "").lower().strip()
    if _env not in {"development", "dev", "local", "test", "testing", ""}:
        print("Test user summary is only available in development environments.")
        return

    print("\n" + "="*80)
    print("TEST USERS SUMMARY")
    print("="*80)
    print(f"\nPassword for ALL test users: (set via TEST_USER_PASSWORD env var)\n")

    by_type = {}
    for user in TEST_USERS:
        user_type = user["user_type"]
        if user_type not in by_type:
            by_type[user_type] = []
        by_type[user_type].append(user)

    for user_type, users in by_type.items():
        print(f"\n{user_type.upper()} ({len(users)} users):")
        print("-" * 60)
        for user in users:
            firm_info = f" [Firm: {user.get('firm_name', user.get('firm_id', 'N/A'))}]" if user.get('firm_id') else ""
            role_info = f" [{user.get('cpa_role', '')}]" if user.get('cpa_role') else ""
            print(f"  {user['email']}{firm_info}{role_info}")
            print(f"    -> {user.get('scenario', 'No description')}")

    print("\n" + "="*80)


# Run summary if executed directly
if __name__ == "__main__":
    print_test_users_summary()
