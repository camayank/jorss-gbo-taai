"""
Feature Flag Models - Feature flag management and usage tracking.

Supports:
- Global feature toggles
- Tier-based feature access
- Gradual rollout (percentage-based)
- Per-firm overrides (beta access, blocked)
"""

from datetime import datetime
from typing import Optional, List
from uuid import uuid4

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime,
    Text, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.models import Base, JSONB


class FeatureFlag(Base):
    """
    Feature Flag - Controls feature availability across the platform.

    Access Control Hierarchy:
    1. is_enabled_globally - Master switch
    2. min_tier - Minimum subscription tier required
    3. rollout_percentage - Gradual rollout (0-100%)
    4. enabled_firm_ids - Beta access for specific firms
    5. disabled_firm_ids - Block specific firms
    """
    __tablename__ = "feature_flags"

    # Primary Key
    flag_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Feature Identity
    feature_key = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True, comment="analysis, reporting, integration, etc.")

    # Global Control
    is_enabled_globally = Column(Boolean, default=False, index=True)

    # Tier-Based Access
    min_tier = Column(
        String(20),
        nullable=True,
        comment="starter, professional, enterprise - NULL means all tiers"
    )

    # Gradual Rollout
    rollout_percentage = Column(
        Integer,
        default=0,
        comment="0-100: percentage of firms that see this feature"
    )

    # Firm-Specific Overrides
    enabled_firm_ids = Column(
        JSONB,
        default=list,
        comment="Firms with beta access (bypasses rollout %)"
    )
    disabled_firm_ids = Column(
        JSONB,
        default=list,
        comment="Firms blocked from feature (overrides everything)"
    )

    # Metadata
    owner = Column(String(100), nullable=True, comment="Team/person responsible")
    jira_ticket = Column(String(50), nullable=True)
    documentation_url = Column(String(500), nullable=True)

    # Lifecycle
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deprecated_at = Column(DateTime, nullable=True)
    removal_date = Column(DateTime, nullable=True, comment="Planned removal date")

    # Relationships
    usage_records = relationship("FeatureUsage", back_populates="feature", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_feature_category", "category"),
        Index("ix_feature_enabled", "is_enabled_globally"),
    )

    def __repr__(self):
        return f"<FeatureFlag(key={self.feature_key}, enabled={self.is_enabled_globally})>"

    def is_enabled_for_firm(self, firm_id: str, firm_tier: str) -> bool:
        """
        Check if feature is enabled for a specific firm.

        Args:
            firm_id: UUID of the firm
            firm_tier: Subscription tier (starter, professional, enterprise)

        Returns:
            True if feature is enabled for this firm
        """
        # Check if globally disabled
        if not self.is_enabled_globally:
            # Check for beta access override
            if str(firm_id) in [str(f) for f in (self.enabled_firm_ids or [])]:
                return True
            return False

        # Check if firm is explicitly blocked
        if str(firm_id) in [str(f) for f in (self.disabled_firm_ids or [])]:
            return False

        # Check tier requirement
        if self.min_tier:
            tier_order = {"starter": 1, "professional": 2, "enterprise": 3}
            if tier_order.get(firm_tier, 0) < tier_order.get(self.min_tier, 0):
                return False

        # Check beta access (bypasses rollout)
        if str(firm_id) in [str(f) for f in (self.enabled_firm_ids or [])]:
            return True

        # Check rollout percentage
        if self.rollout_percentage < 100:
            # Use consistent hashing for stable rollout
            import hashlib
            hash_input = f"{self.feature_key}:{firm_id}"
            hash_value = int(hashlib.md5(hash_input.encode()).hexdigest()[:8], 16)
            firm_bucket = hash_value % 100
            return firm_bucket < self.rollout_percentage

        return True

    @property
    def is_deprecated(self) -> bool:
        """Check if feature is deprecated."""
        return self.deprecated_at is not None


class FeatureUsage(Base):
    """
    Feature Usage - Tracks when features are used.

    Used for:
    - Feature adoption analytics
    - Usage-based billing (Enterprise)
    - Identifying underused features
    """
    __tablename__ = "feature_usage"

    # Primary Key
    usage_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign Keys
    firm_id = Column(
        UUID(as_uuid=True),
        ForeignKey("firms.firm_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    feature_key = Column(
        String(100),
        ForeignKey("feature_flags.feature_key", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Usage Details
    used_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    context = Column(JSONB, nullable=True, comment="Additional context about usage")
    # Example context:
    # {"client_id": "...", "action": "generate_report", "duration_ms": 1234}

    # Relationships
    feature = relationship("FeatureFlag", back_populates="usage_records")
    user = relationship("User", back_populates="feature_usage")

    __table_args__ = (
        Index("ix_feature_usage_firm_key", "firm_id", "feature_key"),
        Index("ix_feature_usage_date", "used_at"),
    )

    def __repr__(self):
        return f"<FeatureUsage(firm={self.firm_id}, feature={self.feature_key})>"
