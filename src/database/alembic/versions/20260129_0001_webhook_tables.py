"""Add webhook tables

Revision ID: 20260129_0001
Revises: 20260128_0002
Create Date: 2026-01-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260129_0001'
down_revision = '20260128_0002'
branch_labels = None
depends_on = None


def upgrade():
    """Create webhook tables."""

    # Create webhook_endpoints table
    op.create_table(
        'webhook_endpoints',
        sa.Column('endpoint_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('firm_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('firms.firm_id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('url', sa.String(2000), nullable=False),
        sa.Column('secret', sa.String(64), nullable=False),
        sa.Column('events', postgresql.JSONB, server_default='[]'),
        sa.Column('status', sa.String(20), server_default='active'),
        sa.Column('custom_headers', postgresql.JSONB, server_default='{}'),
        sa.Column('max_retries', sa.Integer, server_default='5'),
        sa.Column('retry_interval_seconds', sa.Integer, server_default='60'),
        sa.Column('rate_limit_per_minute', sa.Integer, server_default='60'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('last_triggered_at', sa.DateTime, nullable=True),
        sa.Column('total_deliveries', sa.Integer, server_default='0'),
        sa.Column('successful_deliveries', sa.Integer, server_default='0'),
        sa.Column('failed_deliveries', sa.Integer, server_default='0'),
    )

    # Create indexes for webhook_endpoints
    op.create_index('ix_webhook_endpoint_firm_status', 'webhook_endpoints', ['firm_id', 'status'])
    op.create_index('ix_webhook_endpoint_url', 'webhook_endpoints', ['url'])

    # Create webhook_deliveries table
    op.create_table(
        'webhook_deliveries',
        sa.Column('delivery_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('endpoint_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('webhook_endpoints.endpoint_id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_id', sa.String(64), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('request_url', sa.String(2000), nullable=False),
        sa.Column('request_headers', postgresql.JSONB, server_default='{}'),
        sa.Column('request_body', sa.Text, nullable=True),
        sa.Column('response_status_code', sa.Integer, nullable=True),
        sa.Column('response_headers', postgresql.JSONB, server_default='{}'),
        sa.Column('response_body', sa.Text, nullable=True),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('attempt_number', sa.Integer, server_default='1'),
        sa.Column('next_retry_at', sa.DateTime, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('delivered_at', sa.DateTime, nullable=True),
        sa.Column('duration_ms', sa.Integer, nullable=True),
    )

    # Create indexes for webhook_deliveries
    op.create_index('ix_webhook_delivery_endpoint', 'webhook_deliveries', ['endpoint_id'])
    op.create_index('ix_webhook_delivery_event', 'webhook_deliveries', ['event_id'])
    op.create_index('ix_webhook_delivery_status_retry', 'webhook_deliveries', ['status', 'next_retry_at'])
    op.create_index('ix_webhook_delivery_event_type_created', 'webhook_deliveries', ['event_type', 'created_at'])


def downgrade():
    """Drop webhook tables."""
    op.drop_table('webhook_deliveries')
    op.drop_table('webhook_endpoints')
