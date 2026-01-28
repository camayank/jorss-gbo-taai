"""
Webhook Models

Database models for webhook endpoint registration and delivery tracking.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from uuid import uuid4
from dataclasses import dataclass, field

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime,
    Text, ForeignKey, Index, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship

from database.models import Base, JSONB


class WebhookStatus(str, Enum):
    """Webhook endpoint status."""
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


class DeliveryStatus(str, Enum):
    """Webhook delivery attempt status."""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


class WebhookEndpoint(Base):
    """
    Webhook Endpoint Registration.

    Stores registered webhook URLs with their configuration,
    including which events to receive and authentication secrets.
    """
    __tablename__ = "webhook_endpoints"

    # Primary Key
    endpoint_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Ownership
    firm_id = Column(
        UUID(as_uuid=True),
        ForeignKey("firms.firm_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    created_by = Column(UUID(as_uuid=True), nullable=True)

    # Endpoint Configuration
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    url = Column(String(2000), nullable=False)

    # Security
    secret = Column(String(64), nullable=False, comment="HMAC signing secret")

    # Event Filtering
    events = Column(JSONB, default=list, comment="List of event types to receive")

    # Status
    status = Column(
        String(20),
        default=WebhookStatus.ACTIVE.value,
        index=True
    )

    # Headers (custom headers to include in requests)
    custom_headers = Column(JSONB, default=dict)

    # Retry Configuration
    max_retries = Column(Integer, default=5)
    retry_interval_seconds = Column(Integer, default=60)

    # Rate Limiting
    rate_limit_per_minute = Column(Integer, default=60)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_triggered_at = Column(DateTime, nullable=True)

    # Statistics (denormalized for quick access)
    total_deliveries = Column(Integer, default=0)
    successful_deliveries = Column(Integer, default=0)
    failed_deliveries = Column(Integer, default=0)

    # Relationships
    deliveries = relationship(
        "WebhookDelivery",
        back_populates="endpoint",
        cascade="all, delete-orphan",
        order_by="desc(WebhookDelivery.created_at)"
    )

    __table_args__ = (
        Index("ix_webhook_endpoint_firm_status", "firm_id", "status"),
        Index("ix_webhook_endpoint_url", "url"),
    )

    def __repr__(self):
        return f"<WebhookEndpoint(id={self.endpoint_id}, name={self.name}, url={self.url[:50]}...)>"

    @property
    def is_active(self) -> bool:
        """Check if endpoint is active."""
        return self.status == WebhookStatus.ACTIVE.value

    def should_receive_event(self, event_type: str) -> bool:
        """Check if this endpoint should receive the given event type."""
        if not self.events:
            return True  # Empty list = all events
        return event_type in self.events or "*" in self.events


class WebhookDelivery(Base):
    """
    Webhook Delivery Attempt.

    Tracks each delivery attempt including request/response details
    for debugging and monitoring.
    """
    __tablename__ = "webhook_deliveries"

    # Primary Key
    delivery_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Parent Endpoint
    endpoint_id = Column(
        UUID(as_uuid=True),
        ForeignKey("webhook_endpoints.endpoint_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Event Information
    event_id = Column(String(64), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)

    # Request Details
    request_url = Column(String(2000), nullable=False)
    request_headers = Column(JSONB, default=dict)
    request_body = Column(Text, nullable=True)

    # Response Details
    response_status_code = Column(Integer, nullable=True)
    response_headers = Column(JSONB, default=dict)
    response_body = Column(Text, nullable=True)

    # Delivery Status
    status = Column(
        String(20),
        default=DeliveryStatus.PENDING.value,
        index=True
    )

    # Retry Information
    attempt_number = Column(Integer, default=1)
    next_retry_at = Column(DateTime, nullable=True)

    # Error Information
    error_message = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True)

    # Timing
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    delivered_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True, comment="Request duration in milliseconds")

    # Relationships
    endpoint = relationship("WebhookEndpoint", back_populates="deliveries")

    __table_args__ = (
        Index("ix_webhook_delivery_status_retry", "status", "next_retry_at"),
        Index("ix_webhook_delivery_event", "event_type", "created_at"),
    )

    def __repr__(self):
        return f"<WebhookDelivery(id={self.delivery_id}, event={self.event_type}, status={self.status})>"

    @property
    def is_successful(self) -> bool:
        """Check if delivery was successful."""
        return self.status == DeliveryStatus.DELIVERED.value

    @property
    def can_retry(self) -> bool:
        """Check if delivery can be retried."""
        return (
            self.status in (DeliveryStatus.FAILED.value, DeliveryStatus.RETRYING.value)
            and self.endpoint
            and self.attempt_number < self.endpoint.max_retries
        )


@dataclass
class WebhookEvent:
    """
    Webhook Event Data Structure.

    Used internally to pass event data to the delivery service.
    """
    event_id: str
    event_type: str
    timestamp: datetime
    firm_id: str
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> Dict[str, Any]:
        """Convert to webhook payload format."""
        return {
            "id": self.event_id,
            "type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "metadata": self.metadata,
        }
