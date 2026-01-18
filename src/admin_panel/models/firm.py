"""
Firm Model - Core multi-tenancy entity for the platform.

Each CPA firm is a tenant with isolated data, team members, and clients.
"""

from datetime import datetime
from typing import Optional, List
from uuid import uuid4

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime,
    Text, ForeignKey, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

# Import base from existing database module for consistency
from database.models import Base, JSONB


class Firm(Base):
    """
    Firm (CPA Practice) - Primary tenant entity.

    Each firm has:
    - Team members (users) with role-based access
    - Client portfolio (via existing ClientRecord)
    - Subscription tier with feature access
    - Custom branding settings
    """
    __tablename__ = "firms"

    # Primary Key
    firm_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Firm Identity
    name = Column(String(255), nullable=False, index=True)
    legal_name = Column(String(255), nullable=True)
    ein = Column(String(20), nullable=True, unique=True, comment="Employer Identification Number")

    # Contact Information
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    website = Column(String(255), nullable=True)

    # Address
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(2), nullable=True)
    zip_code = Column(String(10), nullable=True)
    country = Column(String(50), default="USA")

    # Branding
    logo_url = Column(String(500), nullable=True)
    primary_color = Column(String(7), default="#059669", comment="Hex color code")
    secondary_color = Column(String(7), default="#1e40af")
    custom_domain = Column(String(255), nullable=True, unique=True, comment="Enterprise only")

    # Subscription Info (denormalized for quick access)
    subscription_tier = Column(
        String(20),
        default="starter",
        index=True,
        comment="starter, professional, enterprise"
    )
    subscription_status = Column(
        String(20),
        default="trial",
        index=True,
        comment="trial, active, past_due, cancelled, suspended"
    )
    trial_ends_at = Column(DateTime, nullable=True)

    # Tier Limits (cached from subscription plan)
    max_team_members = Column(Integer, default=3)
    max_clients = Column(Integer, default=100)
    max_scenarios_per_month = Column(Integer, default=50)
    max_api_calls_per_month = Column(Integer, nullable=True, comment="Enterprise only")

    # Status
    is_active = Column(Boolean, default=True, index=True)
    is_verified = Column(Boolean, default=False, comment="EIN/License verified")
    verification_date = Column(DateTime, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    onboarded_at = Column(DateTime, nullable=True, comment="Completed onboarding flow")
    created_by = Column(UUID(as_uuid=True), nullable=True, comment="Platform admin who created")

    # Settings (JSON for flexibility)
    settings = Column(JSONB, default=dict, comment="Firm-specific settings")

    # Relationships
    users = relationship("User", back_populates="firm", cascade="all, delete-orphan")
    invitations = relationship("Invitation", back_populates="firm", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="firm", cascade="all, delete-orphan")
    usage_metrics = relationship("UsageMetrics", back_populates="firm", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_firm_subscription", "subscription_tier", "subscription_status"),
        Index("ix_firm_created", "created_at"),
        CheckConstraint(
            "subscription_tier IN ('starter', 'professional', 'enterprise')",
            name="ck_firm_tier"
        ),
        CheckConstraint(
            "subscription_status IN ('trial', 'active', 'past_due', 'cancelled', 'suspended')",
            name="ck_firm_status"
        ),
    )

    def __repr__(self):
        return f"<Firm(id={self.firm_id}, name={self.name}, tier={self.subscription_tier})>"

    @property
    def display_name(self) -> str:
        """Return the display name (firm name or legal name)."""
        return self.name or self.legal_name or "Unnamed Firm"

    @property
    def is_trial(self) -> bool:
        """Check if firm is in trial period."""
        return self.subscription_status == "trial"

    @property
    def is_enterprise(self) -> bool:
        """Check if firm has enterprise tier."""
        return self.subscription_tier == "enterprise"

    @property
    def full_address(self) -> Optional[str]:
        """Return formatted full address."""
        parts = []
        if self.address_line1:
            parts.append(self.address_line1)
        if self.address_line2:
            parts.append(self.address_line2)
        if self.city and self.state:
            parts.append(f"{self.city}, {self.state} {self.zip_code or ''}")
        elif self.city:
            parts.append(self.city)
        return "\n".join(parts) if parts else None


class FirmSettings(Base):
    """
    Firm Settings - Extended configuration for firm customization.

    Separated from Firm to keep main table lean and allow
    granular setting management.
    """
    __tablename__ = "firm_settings"

    # Primary Key (same as firm_id - 1:1 relationship)
    firm_id = Column(
        UUID(as_uuid=True),
        ForeignKey("firms.firm_id", ondelete="CASCADE"),
        primary_key=True
    )

    # Tax Settings
    default_tax_year = Column(Integer, default=2025)
    default_state = Column(String(2), nullable=True)

    # Display Settings
    timezone = Column(String(50), default="America/New_York")
    date_format = Column(String(20), default="MM/DD/YYYY")
    currency_display = Column(String(10), default="USD")

    # Security Settings
    mfa_required = Column(Boolean, default=False, comment="Require MFA for all users")
    session_timeout_minutes = Column(Integer, default=60)
    ip_whitelist = Column(JSONB, default=list, comment="Enterprise only - allowed IPs")
    password_expiry_days = Column(Integer, default=90)

    # Notification Settings
    email_notifications = Column(Boolean, default=True)
    notification_preferences = Column(JSONB, default=dict)

    # Workflow Settings
    auto_archive_days = Column(Integer, default=365, comment="Days after filing to auto-archive")
    require_reviewer_approval = Column(Boolean, default=True)
    allow_self_review = Column(Boolean, default=False)

    # Client Portal Settings
    client_portal_enabled = Column(Boolean, default=True)
    client_document_upload = Column(Boolean, default=True)
    client_can_view_scenarios = Column(Boolean, default=False)

    # Branding - Email Templates
    email_signature = Column(Text, nullable=True)
    disclaimer_text = Column(Text, nullable=True)
    welcome_message = Column(Text, nullable=True)

    # Integration Settings
    integrations = Column(JSONB, default=dict, comment="Third-party integration config")
    webhook_url = Column(String(500), nullable=True)
    api_key_enabled = Column(Boolean, default=False)

    # Timestamps
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<FirmSettings(firm_id={self.firm_id})>"
