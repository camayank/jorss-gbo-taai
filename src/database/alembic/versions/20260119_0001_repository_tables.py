"""Repository Tables for Domain Aggregates

Revision ID: 20260119_0001
Revises: 20260118_0002
Create Date: 2026-01-19

Creates tables for domain aggregate persistence:
- scenarios: Tax scenario storage with JSONB data
- scenario_comparisons: Scenario comparison records
- advisory_plans: Advisory plan storage with JSONB data
- domain_events: Event store for domain events
- Adds profile_data column to clients table
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260119_0001'
down_revision = '20260118_0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # SCENARIOS TABLE
    # =========================================================================
    op.create_table(
        'scenarios',
        sa.Column('scenario_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('return_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('scenario_type', sa.String(50), nullable=False, index=True),
        sa.Column('status', sa.String(20), server_default='draft', index=True),
        sa.Column('is_recommended', sa.Boolean, server_default='false', index=True),
        sa.Column('scenario_data', postgresql.JSONB, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.CheckConstraint(
            "scenario_type IN ('filing_status', 'what_if', 'entity_structure', 'deduction_bunching', "
            "'retirement', 'multi_year', 'roth_conversion', 'capital_gains', 'estimated_tax')",
            name='ck_scenario_type'
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'calculated', 'applied', 'archived')",
            name='ck_scenario_status'
        ),
    )
    op.create_index('ix_scenario_return_type', 'scenarios', ['return_id', 'scenario_type'])
    op.create_index('ix_scenario_recommended', 'scenarios', ['return_id', 'is_recommended'])

    # =========================================================================
    # SCENARIO COMPARISONS TABLE
    # =========================================================================
    op.create_table(
        'scenario_comparisons',
        sa.Column('comparison_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('return_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('scenario_ids', postgresql.JSONB, nullable=False),
        sa.Column('winner_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('comparison_data', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_comparison_return', 'scenario_comparisons', ['return_id'])

    # =========================================================================
    # ADVISORY PLANS TABLE
    # =========================================================================
    op.create_table(
        'advisory_plans',
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('return_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('tax_year', sa.Integer, nullable=False, index=True),
        sa.Column('is_finalized', sa.Boolean, server_default='false', index=True),
        sa.Column('total_potential_savings', sa.Numeric(12, 2), server_default='0'),
        sa.Column('total_realized_savings', sa.Numeric(12, 2), server_default='0'),
        sa.Column('plan_data', postgresql.JSONB, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.CheckConstraint('tax_year >= 2020 AND tax_year <= 2030', name='ck_advisory_year'),
    )
    op.create_index('ix_advisory_client_year', 'advisory_plans', ['client_id', 'tax_year'])
    op.create_index('ix_advisory_return', 'advisory_plans', ['return_id'])

    # =========================================================================
    # DOMAIN EVENTS TABLE (Event Store)
    # =========================================================================
    op.create_table(
        'domain_events',
        sa.Column('event_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('stream_id', sa.String(255), nullable=False, index=True),
        sa.Column('event_type', sa.String(100), nullable=False, index=True),
        sa.Column('event_version', sa.Integer, nullable=False),
        sa.Column('aggregate_type', sa.String(100), nullable=False, index=True),
        sa.Column('aggregate_id', sa.String(100), nullable=False, index=True),
        sa.Column('event_data', postgresql.JSONB, nullable=False),
        sa.Column('occurred_at', sa.DateTime, nullable=False, index=True),
        sa.Column('stored_at', sa.DateTime, server_default=sa.func.now()),
    )
    # Unique constraint to prevent duplicate versions in a stream
    op.create_unique_constraint(
        'uq_event_stream_version',
        'domain_events',
        ['stream_id', 'event_version']
    )
    op.create_index('ix_event_stream_version', 'domain_events', ['stream_id', 'event_version'])
    op.create_index('ix_event_aggregate', 'domain_events', ['aggregate_type', 'aggregate_id'])
    op.create_index('ix_event_occurred', 'domain_events', ['occurred_at'])

    # =========================================================================
    # ADD PROFILE_DATA TO CLIENTS TABLE
    # =========================================================================
    # Add profile_data column to store extended ClientProfile data.
    # Some deployments don't have a clients table in this migration branch.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'clients' in inspector.get_table_names():
        client_columns = {col["name"] for col in inspector.get_columns("clients")}
        if 'profile_data' not in client_columns:
            op.add_column(
                'clients',
                sa.Column('profile_data', postgresql.JSONB, nullable=True)
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'clients' in inspector.get_table_names():
        client_columns = {col["name"] for col in inspector.get_columns("clients")}
        if 'profile_data' in client_columns:
            op.drop_column('clients', 'profile_data')

    # Drop domain_events table
    op.drop_index('ix_event_occurred', table_name='domain_events')
    op.drop_index('ix_event_aggregate', table_name='domain_events')
    op.drop_index('ix_event_stream_version', table_name='domain_events')
    op.drop_constraint('uq_event_stream_version', 'domain_events')
    op.drop_table('domain_events')

    # Drop advisory_plans table
    op.drop_index('ix_advisory_return', table_name='advisory_plans')
    op.drop_index('ix_advisory_client_year', table_name='advisory_plans')
    op.drop_table('advisory_plans')

    # Drop scenario_comparisons table
    op.drop_index('ix_comparison_return', table_name='scenario_comparisons')
    op.drop_table('scenario_comparisons')

    # Drop scenarios table
    op.drop_index('ix_scenario_recommended', table_name='scenarios')
    op.drop_index('ix_scenario_return_type', table_name='scenarios')
    op.drop_table('scenarios')
