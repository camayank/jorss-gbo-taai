"""Initial database schema.

Revision ID: 001
Revises:
Create Date: 2026-01-16

Creates all initial tables for the tax platform including:
- tax_returns: Primary tax return records
- taxpayers: Taxpayer personal information
- income_records: Income source records
- w2_records: W-2 form data
- form1099_records: 1099 form data
- deduction_records: Itemized deductions
- credit_records: Tax credits
- dependent_records: Dependent information
- state_returns: State tax returns
- audit_logs: Audit trail
- computation_worksheets: IRS worksheet calculations
- documents: Uploaded document metadata
- extracted_fields: OCR extracted fields
- document_processing_logs: Document processing audit
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all initial tables."""

    # Create enums first
    filing_status_enum = postgresql.ENUM(
        'single', 'married_joint', 'married_separate',
        'head_of_household', 'qualifying_widow',
        name='filingstatus',
        create_type=False
    )

    return_status_enum = postgresql.ENUM(
        'draft', 'in_progress', 'pending_review', 'reviewed',
        'ready_to_file', 'filed', 'accepted', 'rejected', 'amended', 'archived',
        name='returnstatus',
        create_type=False
    )

    income_source_enum = postgresql.ENUM(
        'w2_wages', 'self_employment', 'interest', 'dividends',
        'capital_gains_short', 'capital_gains_long', 'rental', 'royalty',
        'retirement', 'social_security', 'unemployment',
        'partnership_k1', 's_corp_k1', 'trust_k1', 'other',
        name='incomesourcetype',
        create_type=False
    )

    form1099_type_enum = postgresql.ENUM(
        '1099-INT', '1099-DIV', '1099-B', '1099-MISC', '1099-NEC',
        '1099-R', '1099-G', '1099-SSA', '1099-K', '1099-S', '1099-C', '1099-Q',
        name='form1099type',
        create_type=False
    )

    deduction_type_enum = postgresql.ENUM(
        'medical_dental', 'state_local_income_tax', 'state_local_sales_tax',
        'real_estate_tax', 'personal_property_tax', 'mortgage_interest',
        'mortgage_points', 'investment_interest', 'charitable_cash',
        'charitable_noncash', 'casualty_loss', 'other_itemized',
        'educator_expense', 'hsa_contribution', 'self_employed_health',
        'self_employed_retirement', 'student_loan_interest', 'ira_contribution',
        'alimony_paid',
        name='deductiontype',
        create_type=False
    )

    credit_type_enum = postgresql.ENUM(
        'child_tax_credit', 'additional_child_tax_credit', 'earned_income_credit',
        'child_dependent_care', 'education_aotc', 'education_llc',
        'retirement_saver', 'foreign_tax', 'residential_energy',
        'ev_credit', 'adoption', 'premium_tax_credit', 'other',
        name='credittype',
        create_type=False
    )

    dependent_relationship_enum = postgresql.ENUM(
        'son', 'daughter', 'stepson', 'stepdaughter', 'foster_child',
        'brother', 'sister', 'half_brother', 'half_sister', 'stepbrother',
        'stepsister', 'parent', 'grandparent', 'grandchild', 'niece',
        'nephew', 'uncle', 'aunt', 'other_relative', 'none',
        name='dependentrelationship',
        create_type=False
    )

    document_type_enum = postgresql.ENUM(
        'w2', '1099-int', '1099-div', '1099-misc', '1099-nec', '1099-b',
        '1099-r', '1099-g', '1098', '1098-e', '1098-t', 'k1',
        '1095-a', '1095-b', '1095-c', 'unknown',
        name='documenttype',
        create_type=False
    )

    document_status_enum = postgresql.ENUM(
        'uploaded', 'processing', 'ocr_complete', 'extraction_complete',
        'verified', 'applied', 'failed', 'rejected',
        name='documentstatus',
        create_type=False
    )

    # Create enum types
    op.execute("CREATE TYPE filingstatus AS ENUM ('single', 'married_joint', 'married_separate', 'head_of_household', 'qualifying_widow')")
    op.execute("CREATE TYPE returnstatus AS ENUM ('draft', 'in_progress', 'pending_review', 'reviewed', 'ready_to_file', 'filed', 'accepted', 'rejected', 'amended', 'archived')")
    op.execute("CREATE TYPE incomesourcetype AS ENUM ('w2_wages', 'self_employment', 'interest', 'dividends', 'capital_gains_short', 'capital_gains_long', 'rental', 'royalty', 'retirement', 'social_security', 'unemployment', 'partnership_k1', 's_corp_k1', 'trust_k1', 'other')")
    op.execute("CREATE TYPE form1099type AS ENUM ('1099-INT', '1099-DIV', '1099-B', '1099-MISC', '1099-NEC', '1099-R', '1099-G', '1099-SSA', '1099-K', '1099-S', '1099-C', '1099-Q')")
    op.execute("CREATE TYPE deductiontype AS ENUM ('medical_dental', 'state_local_income_tax', 'state_local_sales_tax', 'real_estate_tax', 'personal_property_tax', 'mortgage_interest', 'mortgage_points', 'investment_interest', 'charitable_cash', 'charitable_noncash', 'casualty_loss', 'other_itemized', 'educator_expense', 'hsa_contribution', 'self_employed_health', 'self_employed_retirement', 'student_loan_interest', 'ira_contribution', 'alimony_paid')")
    op.execute("CREATE TYPE credittype AS ENUM ('child_tax_credit', 'additional_child_tax_credit', 'earned_income_credit', 'child_dependent_care', 'education_aotc', 'education_llc', 'retirement_saver', 'foreign_tax', 'residential_energy', 'ev_credit', 'adoption', 'premium_tax_credit', 'other')")
    op.execute("CREATE TYPE dependentrelationship AS ENUM ('son', 'daughter', 'stepson', 'stepdaughter', 'foster_child', 'brother', 'sister', 'half_brother', 'half_sister', 'stepbrother', 'stepsister', 'parent', 'grandparent', 'grandchild', 'niece', 'nephew', 'uncle', 'aunt', 'other_relative', 'none')")
    op.execute("CREATE TYPE documenttype AS ENUM ('w2', '1099-int', '1099-div', '1099-misc', '1099-nec', '1099-b', '1099-r', '1099-g', '1098', '1098-e', '1098-t', 'k1', '1095-a', '1095-b', '1095-c', 'unknown')")
    op.execute("CREATE TYPE documentstatus AS ENUM ('uploaded', 'processing', 'ocr_complete', 'extraction_complete', 'verified', 'applied', 'failed', 'rejected')")

    # tax_returns table
    op.create_table(
        'tax_returns',
        sa.Column('return_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tax_year', sa.Integer(), nullable=False),
        sa.Column('taxpayer_ssn_hash', sa.String(64), nullable=False),
        sa.Column('filing_status', sa.Enum('single', 'married_joint', 'married_separate', 'head_of_household', 'qualifying_widow', name='filingstatus'), nullable=False),
        sa.Column('status', sa.Enum('draft', 'in_progress', 'pending_review', 'reviewed', 'ready_to_file', 'filed', 'accepted', 'rejected', 'amended', 'archived', name='returnstatus'), nullable=False, server_default='draft'),
        sa.Column('is_amended', sa.Boolean(), default=False),
        sa.Column('original_return_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tax_returns.return_id'), nullable=True),
        sa.Column('amendment_number', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        # Income lines
        sa.Column('line_1_wages', sa.Numeric(12, 2), default=0),
        sa.Column('line_2a_tax_exempt_interest', sa.Numeric(12, 2), default=0),
        sa.Column('line_2b_taxable_interest', sa.Numeric(12, 2), default=0),
        sa.Column('line_3a_qualified_dividends', sa.Numeric(12, 2), default=0),
        sa.Column('line_3b_ordinary_dividends', sa.Numeric(12, 2), default=0),
        sa.Column('line_4a_ira_distributions', sa.Numeric(12, 2), default=0),
        sa.Column('line_4b_taxable_ira', sa.Numeric(12, 2), default=0),
        sa.Column('line_5a_pensions', sa.Numeric(12, 2), default=0),
        sa.Column('line_5b_taxable_pensions', sa.Numeric(12, 2), default=0),
        sa.Column('line_6a_social_security', sa.Numeric(12, 2), default=0),
        sa.Column('line_6b_taxable_social_security', sa.Numeric(12, 2), default=0),
        sa.Column('line_7_capital_gain_loss', sa.Numeric(12, 2), default=0),
        sa.Column('line_8_other_income', sa.Numeric(12, 2), default=0),
        sa.Column('line_9_total_income', sa.Numeric(12, 2), default=0),
        # Adjustments
        sa.Column('line_10_adjustments', sa.Numeric(12, 2), default=0),
        sa.Column('line_11_agi', sa.Numeric(12, 2), default=0),
        # Deductions
        sa.Column('line_12a_standard_deduction', sa.Numeric(12, 2), default=0),
        sa.Column('line_12b_charitable_if_standard', sa.Numeric(12, 2), default=0),
        sa.Column('line_12c_total_deduction', sa.Numeric(12, 2), default=0),
        sa.Column('line_13_qbi_deduction', sa.Numeric(12, 2), default=0),
        sa.Column('line_14_total_deductions', sa.Numeric(12, 2), default=0),
        sa.Column('line_15_taxable_income', sa.Numeric(12, 2), default=0),
        # Tax and credits
        sa.Column('line_16_tax', sa.Numeric(12, 2), default=0),
        sa.Column('line_17_schedule_2_line_3', sa.Numeric(12, 2), default=0),
        sa.Column('line_18_total_tax', sa.Numeric(12, 2), default=0),
        sa.Column('line_19_child_tax_credit', sa.Numeric(12, 2), default=0),
        sa.Column('line_20_schedule_3_line_8', sa.Numeric(12, 2), default=0),
        sa.Column('line_21_total_credits', sa.Numeric(12, 2), default=0),
        sa.Column('line_22_tax_minus_credits', sa.Numeric(12, 2), default=0),
        sa.Column('line_23_other_taxes', sa.Numeric(12, 2), default=0),
        sa.Column('line_24_total_tax_liability', sa.Numeric(12, 2), default=0),
        # Payments
        sa.Column('line_25a_w2_withholding', sa.Numeric(12, 2), default=0),
        sa.Column('line_25b_1099_withholding', sa.Numeric(12, 2), default=0),
        sa.Column('line_25c_other_withholding', sa.Numeric(12, 2), default=0),
        sa.Column('line_25d_total_withholding', sa.Numeric(12, 2), default=0),
        sa.Column('line_26_estimated_payments', sa.Numeric(12, 2), default=0),
        sa.Column('line_27_eic', sa.Numeric(12, 2), default=0),
        sa.Column('line_28_additional_child_credit', sa.Numeric(12, 2), default=0),
        sa.Column('line_29_american_opportunity', sa.Numeric(12, 2), default=0),
        sa.Column('line_30_recovery_rebate', sa.Numeric(12, 2), default=0),
        sa.Column('line_31_schedule_3_line_15', sa.Numeric(12, 2), default=0),
        sa.Column('line_32_other_payments', sa.Numeric(12, 2), default=0),
        sa.Column('line_33_total_payments', sa.Numeric(12, 2), default=0),
        # Refund/owed
        sa.Column('line_34_overpayment', sa.Numeric(12, 2), default=0),
        sa.Column('line_35a_refund', sa.Numeric(12, 2), default=0),
        sa.Column('line_36_applied_to_next_year', sa.Numeric(12, 2), default=0),
        sa.Column('line_37_amount_owed', sa.Numeric(12, 2), default=0),
        sa.Column('line_38_estimated_penalty', sa.Numeric(12, 2), default=0),
        # Additional taxes
        sa.Column('self_employment_tax', sa.Numeric(12, 2), default=0),
        sa.Column('additional_medicare_tax', sa.Numeric(12, 2), default=0),
        sa.Column('net_investment_income_tax', sa.Numeric(12, 2), default=0),
        sa.Column('alternative_minimum_tax', sa.Numeric(12, 2), default=0),
        # Rates
        sa.Column('effective_tax_rate', sa.Numeric(6, 4), default=0),
        sa.Column('marginal_tax_rate', sa.Numeric(6, 4), default=0),
        # State
        sa.Column('state_code', sa.String(2), nullable=True),
        sa.Column('state_tax_liability', sa.Numeric(12, 2), default=0),
        sa.Column('state_refund_or_owed', sa.Numeric(12, 2), default=0),
        sa.Column('combined_tax_liability', sa.Numeric(12, 2), default=0),
        sa.Column('combined_refund_or_owed', sa.Numeric(12, 2), default=0),
        # Metadata
        sa.Column('preparer_ptin', sa.String(11), nullable=True),
        sa.Column('firm_ein', sa.String(10), nullable=True),
        sa.Column('software_version', sa.String(50), nullable=True),
        sa.Column('calculation_version', sa.String(50), nullable=True),
        sa.Column('computation_details', postgresql.JSONB(), nullable=True),
        sa.Column('validation_results', postgresql.JSONB(), nullable=True),
        # Session tracking (for legacy support)
        sa.Column('session_id', sa.String(100), nullable=True),
        sa.Column('taxpayer_name', sa.String(200), nullable=True),
        sa.Column('gross_income', sa.Numeric(12, 2), default=0),
        sa.Column('adjusted_gross_income', sa.Numeric(12, 2), default=0),
        sa.Column('taxable_income', sa.Numeric(12, 2), default=0),
        sa.Column('federal_tax_liability', sa.Numeric(12, 2), default=0),
        sa.Column('federal_refund_or_owed', sa.Numeric(12, 2), default=0),
        sa.Column('return_data', postgresql.JSONB(), nullable=True),
    )

    # Indexes for tax_returns
    op.create_index('ix_tax_returns_tax_year', 'tax_returns', ['tax_year'])
    op.create_index('ix_tax_returns_ssn_hash', 'tax_returns', ['taxpayer_ssn_hash'])
    op.create_index('ix_tax_returns_status', 'tax_returns', ['status'])
    op.create_index('ix_tax_returns_filing_status', 'tax_returns', ['filing_status'])
    op.create_index('ix_tax_returns_is_amended', 'tax_returns', ['is_amended'])
    op.create_index('ix_tax_returns_state_code', 'tax_returns', ['state_code'])
    op.create_index('ix_return_status_year', 'tax_returns', ['status', 'tax_year'])
    op.create_index('ix_return_filing_status', 'tax_returns', ['filing_status', 'tax_year'])

    # Unique constraint
    op.create_unique_constraint('uq_return_natural_key', 'tax_returns', ['tax_year', 'taxpayer_ssn_hash', 'amendment_number'])

    # Check constraints
    op.create_check_constraint('ck_valid_tax_year', 'tax_returns', 'tax_year >= 2020 AND tax_year <= 2030')
    op.create_check_constraint('ck_valid_amendment', 'tax_returns', 'amendment_number >= 0')

    # taxpayers table
    op.create_table(
        'taxpayers',
        sa.Column('taxpayer_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('return_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tax_returns.return_id'), nullable=False),
        sa.Column('ssn_hash', sa.String(64), nullable=False),
        sa.Column('ssn_encrypted', sa.String(256), nullable=True),
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('middle_name', sa.String(100), nullable=True),
        sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('suffix', sa.String(10), nullable=True),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('is_primary', sa.Boolean(), default=True),
        sa.Column('is_over_65', sa.Boolean(), default=False),
        sa.Column('is_blind', sa.Boolean(), default=False),
        sa.Column('is_deceased', sa.Boolean(), default=False),
        sa.Column('date_of_death', sa.Date(), nullable=True),
        sa.Column('address_line_1', sa.String(200), nullable=True),
        sa.Column('address_line_2', sa.String(200), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('state', sa.String(2), nullable=True),
        sa.Column('zip_code', sa.String(10), nullable=True),
        sa.Column('country', sa.String(50), default='USA'),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('email', sa.String(200), nullable=True),
        sa.Column('spouse_ssn_hash', sa.String(64), nullable=True),
        sa.Column('spouse_ssn_encrypted', sa.String(256), nullable=True),
        sa.Column('spouse_first_name', sa.String(100), nullable=True),
        sa.Column('spouse_middle_name', sa.String(100), nullable=True),
        sa.Column('spouse_last_name', sa.String(100), nullable=True),
        sa.Column('spouse_date_of_birth', sa.Date(), nullable=True),
        sa.Column('spouse_is_over_65', sa.Boolean(), default=False),
        sa.Column('spouse_is_blind', sa.Boolean(), default=False),
        sa.Column('spouse_is_deceased', sa.Boolean(), default=False),
        sa.Column('spouse_date_of_death', sa.Date(), nullable=True),
        sa.Column('occupation', sa.String(100), nullable=True),
        sa.Column('spouse_occupation', sa.String(100), nullable=True),
        sa.Column('bank_routing_encrypted', sa.String(256), nullable=True),
        sa.Column('bank_account_encrypted', sa.String(256), nullable=True),
        sa.Column('account_type', sa.String(20), nullable=True),
        sa.Column('ip_pin', sa.String(6), nullable=True),
        sa.Column('spouse_ip_pin', sa.String(6), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_index('ix_taxpayer_return_id', 'taxpayers', ['return_id'])
    op.create_index('ix_taxpayer_ssn_hash', 'taxpayers', ['ssn_hash'])
    op.create_index('ix_taxpayer_state', 'taxpayers', ['state'])
    op.create_index('ix_taxpayer_is_over_65', 'taxpayers', ['is_over_65'])
    op.create_index('ix_taxpayer_name', 'taxpayers', ['last_name', 'first_name'])

    # income_records table
    op.create_table(
        'income_records',
        sa.Column('income_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('return_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tax_returns.return_id'), nullable=False),
        sa.Column('source_type', sa.Enum('w2_wages', 'self_employment', 'interest', 'dividends', 'capital_gains_short', 'capital_gains_long', 'rental', 'royalty', 'retirement', 'social_security', 'unemployment', 'partnership_k1', 's_corp_k1', 'trust_k1', 'other', name='incomesourcetype'), nullable=False),
        sa.Column('gross_amount', sa.Numeric(12, 2), nullable=False, default=0),
        sa.Column('adjustments', sa.Numeric(12, 2), default=0),
        sa.Column('taxable_amount', sa.Numeric(12, 2), default=0),
        sa.Column('federal_withholding', sa.Numeric(12, 2), default=0),
        sa.Column('state_withholding', sa.Numeric(12, 2), default=0),
        sa.Column('local_withholding', sa.Numeric(12, 2), default=0),
        sa.Column('payer_name', sa.String(200), nullable=True),
        sa.Column('payer_ein', sa.String(10), nullable=True),
        sa.Column('payer_address', sa.Text(), nullable=True),
        sa.Column('form_type', sa.String(20), nullable=True),
        sa.Column('document_id', sa.String(100), nullable=True),
        sa.Column('is_foreign_source', sa.Boolean(), default=False),
        sa.Column('is_passive_income', sa.Boolean(), default=False),
        sa.Column('is_qbi_eligible', sa.Boolean(), default=False),
        sa.Column('state_code', sa.String(2), nullable=True),
        sa.Column('state_wages', sa.Numeric(12, 2), default=0),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_index('ix_income_return_id', 'income_records', ['return_id'])
    op.create_index('ix_income_source_type', 'income_records', ['source_type', 'return_id'])

    # w2_records table
    op.create_table(
        'w2_records',
        sa.Column('w2_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('return_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tax_returns.return_id'), nullable=False),
        sa.Column('employer_name', sa.String(200), nullable=False),
        sa.Column('employer_ein', sa.String(10), nullable=True),
        sa.Column('employer_address', sa.Text(), nullable=True),
        sa.Column('employer_state_id', sa.String(20), nullable=True),
        sa.Column('employee_ssn_hash', sa.String(64), nullable=False),
        sa.Column('box_1_wages', sa.Numeric(12, 2), nullable=False),
        sa.Column('box_2_federal_tax', sa.Numeric(12, 2), default=0),
        sa.Column('box_3_ss_wages', sa.Numeric(12, 2), default=0),
        sa.Column('box_4_ss_tax', sa.Numeric(12, 2), default=0),
        sa.Column('box_5_medicare_wages', sa.Numeric(12, 2), default=0),
        sa.Column('box_6_medicare_tax', sa.Numeric(12, 2), default=0),
        sa.Column('box_7_ss_tips', sa.Numeric(12, 2), default=0),
        sa.Column('box_8_allocated_tips', sa.Numeric(12, 2), default=0),
        sa.Column('box_10_dependent_care', sa.Numeric(12, 2), default=0),
        sa.Column('box_11_nonqualified_plans', sa.Numeric(12, 2), default=0),
        sa.Column('box_12_codes', postgresql.JSONB(), nullable=True),
        sa.Column('box_13_statutory', sa.Boolean(), default=False),
        sa.Column('box_13_retirement', sa.Boolean(), default=False),
        sa.Column('box_13_third_party_sick', sa.Boolean(), default=False),
        sa.Column('box_14_other', postgresql.JSONB(), nullable=True),
        sa.Column('state_code', sa.String(2), nullable=True),
        sa.Column('box_16_state_wages', sa.Numeric(12, 2), default=0),
        sa.Column('box_17_state_tax', sa.Numeric(12, 2), default=0),
        sa.Column('box_18_local_wages', sa.Numeric(12, 2), default=0),
        sa.Column('box_19_local_tax', sa.Numeric(12, 2), default=0),
        sa.Column('box_20_locality', sa.String(50), nullable=True),
        sa.Column('state_2_code', sa.String(2), nullable=True),
        sa.Column('state_2_wages', sa.Numeric(12, 2), default=0),
        sa.Column('state_2_tax', sa.Numeric(12, 2), default=0),
        sa.Column('document_id', sa.String(100), nullable=True),
        sa.Column('is_corrected', sa.Boolean(), default=False),
        sa.Column('is_validated', sa.Boolean(), default=False),
        sa.Column('validation_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_index('ix_w2_return_id', 'w2_records', ['return_id'])
    op.create_index('ix_w2_state_code', 'w2_records', ['state_code'])
    op.create_index('ix_w2_employer', 'w2_records', ['employer_ein', 'return_id'])

    # form1099_records table
    op.create_table(
        'form1099_records',
        sa.Column('form1099_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('return_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tax_returns.return_id'), nullable=False),
        sa.Column('form_type', sa.Enum('1099-INT', '1099-DIV', '1099-B', '1099-MISC', '1099-NEC', '1099-R', '1099-G', '1099-SSA', '1099-K', '1099-S', '1099-C', '1099-Q', name='form1099type'), nullable=False),
        sa.Column('payer_name', sa.String(200), nullable=False),
        sa.Column('payer_tin', sa.String(10), nullable=True),
        sa.Column('payer_address', sa.Text(), nullable=True),
        sa.Column('recipient_ssn_hash', sa.String(64), nullable=False),
        sa.Column('box_1_amount', sa.Numeric(12, 2), default=0),
        sa.Column('box_2_amount', sa.Numeric(12, 2), default=0),
        sa.Column('box_3_amount', sa.Numeric(12, 2), default=0),
        sa.Column('box_4_federal_tax', sa.Numeric(12, 2), default=0),
        sa.Column('box_5_amount', sa.Numeric(12, 2), default=0),
        sa.Column('qualified_dividends', sa.Numeric(12, 2), default=0),
        sa.Column('capital_gain_distributions', sa.Numeric(12, 2), default=0),
        sa.Column('nondividend_distributions', sa.Numeric(12, 2), default=0),
        sa.Column('section_199a_dividends', sa.Numeric(12, 2), default=0),
        sa.Column('tax_exempt_interest', sa.Numeric(12, 2), default=0),
        sa.Column('private_activity_bond', sa.Numeric(12, 2), default=0),
        sa.Column('us_savings_bond_interest', sa.Numeric(12, 2), default=0),
        sa.Column('proceeds', sa.Numeric(12, 2), default=0),
        sa.Column('cost_basis', sa.Numeric(12, 2), default=0),
        sa.Column('gain_loss', sa.Numeric(12, 2), default=0),
        sa.Column('is_short_term', sa.Boolean(), nullable=True),
        sa.Column('is_covered_security', sa.Boolean(), default=True),
        sa.Column('wash_sale_loss', sa.Numeric(12, 2), default=0),
        sa.Column('gross_distribution', sa.Numeric(12, 2), default=0),
        sa.Column('taxable_amount', sa.Numeric(12, 2), default=0),
        sa.Column('distribution_code', sa.String(5), nullable=True),
        sa.Column('is_total_distribution', sa.Boolean(), default=False),
        sa.Column('unemployment_compensation', sa.Numeric(12, 2), default=0),
        sa.Column('state_tax_refund', sa.Numeric(12, 2), default=0),
        sa.Column('state_code', sa.String(2), nullable=True),
        sa.Column('state_tax_withheld', sa.Numeric(12, 2), default=0),
        sa.Column('state_id_number', sa.String(20), nullable=True),
        sa.Column('additional_data', postgresql.JSONB(), nullable=True),
        sa.Column('document_id', sa.String(100), nullable=True),
        sa.Column('is_corrected', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_index('ix_1099_return_id', 'form1099_records', ['return_id'])
    op.create_index('ix_1099_form_type', 'form1099_records', ['form_type', 'return_id'])
    op.create_index('ix_1099_payer', 'form1099_records', ['payer_tin', 'return_id'])

    # deduction_records table
    op.create_table(
        'deduction_records',
        sa.Column('deduction_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('return_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tax_returns.return_id'), nullable=False),
        sa.Column('deduction_type', sa.Enum('medical_dental', 'state_local_income_tax', 'state_local_sales_tax', 'real_estate_tax', 'personal_property_tax', 'mortgage_interest', 'mortgage_points', 'investment_interest', 'charitable_cash', 'charitable_noncash', 'casualty_loss', 'other_itemized', 'educator_expense', 'hsa_contribution', 'self_employed_health', 'self_employed_retirement', 'student_loan_interest', 'ira_contribution', 'alimony_paid', name='deductiontype'), nullable=False),
        sa.Column('is_itemized', sa.Boolean(), default=True),
        sa.Column('gross_amount', sa.Numeric(12, 2), nullable=False, default=0),
        sa.Column('limitation_amount', sa.Numeric(12, 2), default=0),
        sa.Column('allowed_amount', sa.Numeric(12, 2), default=0),
        sa.Column('limitation_type', sa.String(50), nullable=True),
        sa.Column('limitation_percentage', sa.Numeric(5, 4), nullable=True),
        sa.Column('agi_floor_applied', sa.Numeric(12, 2), default=0),
        sa.Column('payee_name', sa.String(200), nullable=True),
        sa.Column('payee_ein', sa.String(10), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_cash_contribution', sa.Boolean(), nullable=True),
        sa.Column('charity_name', sa.String(200), nullable=True),
        sa.Column('charity_ein', sa.String(10), nullable=True),
        sa.Column('property_description', sa.Text(), nullable=True),
        sa.Column('property_fmv', sa.Numeric(12, 2), nullable=True),
        sa.Column('property_cost_basis', sa.Numeric(12, 2), nullable=True),
        sa.Column('lender_name', sa.String(200), nullable=True),
        sa.Column('mortgage_principal', sa.Numeric(14, 2), nullable=True),
        sa.Column('mortgage_start_date', sa.Date(), nullable=True),
        sa.Column('is_home_acquisition_debt', sa.Boolean(), nullable=True),
        sa.Column('medical_provider', sa.String(200), nullable=True),
        sa.Column('medical_service_type', sa.String(100), nullable=True),
        sa.Column('document_id', sa.String(100), nullable=True),
        sa.Column('receipt_required', sa.Boolean(), default=False),
        sa.Column('receipt_on_file', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_index('ix_deduction_return_id', 'deduction_records', ['return_id'])
    op.create_index('ix_deduction_type', 'deduction_records', ['deduction_type', 'return_id'])

    # credit_records table
    op.create_table(
        'credit_records',
        sa.Column('credit_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('return_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tax_returns.return_id'), nullable=False),
        sa.Column('credit_type', sa.Enum('child_tax_credit', 'additional_child_tax_credit', 'earned_income_credit', 'child_dependent_care', 'education_aotc', 'education_llc', 'retirement_saver', 'foreign_tax', 'residential_energy', 'ev_credit', 'adoption', 'premium_tax_credit', 'other', name='credittype'), nullable=False),
        sa.Column('is_refundable', sa.Boolean(), default=False),
        sa.Column('tentative_credit', sa.Numeric(12, 2), default=0),
        sa.Column('phaseout_reduction', sa.Numeric(12, 2), default=0),
        sa.Column('other_limitations', sa.Numeric(12, 2), default=0),
        sa.Column('allowed_credit', sa.Numeric(12, 2), default=0),
        sa.Column('phaseout_start', sa.Numeric(12, 2), nullable=True),
        sa.Column('phaseout_end', sa.Numeric(12, 2), nullable=True),
        sa.Column('phaseout_rate', sa.Numeric(5, 4), nullable=True),
        sa.Column('qualifying_children', sa.Integer(), default=0),
        sa.Column('qualifying_expenses', sa.Numeric(12, 2), default=0),
        sa.Column('foreign_taxes_paid', sa.Numeric(12, 2), default=0),
        sa.Column('education_expenses', sa.Numeric(12, 2), default=0),
        sa.Column('student_name', sa.String(200), nullable=True),
        sa.Column('student_ssn_hash', sa.String(64), nullable=True),
        sa.Column('educational_institution', sa.String(200), nullable=True),
        sa.Column('institution_ein', sa.String(10), nullable=True),
        sa.Column('form_number', sa.String(20), nullable=True),
        sa.Column('document_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_index('ix_credit_return_id', 'credit_records', ['return_id'])
    op.create_index('ix_credit_type', 'credit_records', ['credit_type', 'return_id'])
    op.create_index('ix_credit_refundable', 'credit_records', ['is_refundable'])

    # dependent_records table
    op.create_table(
        'dependent_records',
        sa.Column('dependent_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('return_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tax_returns.return_id'), nullable=False),
        sa.Column('ssn_hash', sa.String(64), nullable=False),
        sa.Column('ssn_encrypted', sa.String(256), nullable=True),
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('middle_name', sa.String(100), nullable=True),
        sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('relation_type', sa.Enum('son', 'daughter', 'stepson', 'stepdaughter', 'foster_child', 'brother', 'sister', 'half_brother', 'half_sister', 'stepbrother', 'stepsister', 'parent', 'grandparent', 'grandchild', 'niece', 'nephew', 'uncle', 'aunt', 'other_relative', 'none', name='dependentrelationship'), nullable=False),
        sa.Column('is_qualifying_child', sa.Boolean(), default=False),
        sa.Column('is_qualifying_relative', sa.Boolean(), default=False),
        sa.Column('months_lived_with_taxpayer', sa.Integer(), default=12),
        sa.Column('is_under_17', sa.Boolean(), default=False),
        sa.Column('is_under_19', sa.Boolean(), default=False),
        sa.Column('is_under_24_student', sa.Boolean(), default=False),
        sa.Column('is_permanently_disabled', sa.Boolean(), default=False),
        sa.Column('is_student', sa.Boolean(), default=False),
        sa.Column('school_name', sa.String(200), nullable=True),
        sa.Column('provided_over_half_support', sa.Boolean(), default=True),
        sa.Column('dependent_gross_income', sa.Numeric(12, 2), default=0),
        sa.Column('eligible_for_ctc', sa.Boolean(), default=False),
        sa.Column('eligible_for_odc', sa.Boolean(), default=False),
        sa.Column('eligible_for_eic', sa.Boolean(), default=False),
        sa.Column('eligible_for_cdcc', sa.Boolean(), default=False),
        sa.Column('is_us_citizen', sa.Boolean(), default=True),
        sa.Column('is_resident_alien', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_index('ix_dependent_return_id', 'dependent_records', ['return_id'])
    op.create_index('ix_dependent_ssn', 'dependent_records', ['ssn_hash'])
    op.create_index('ix_dependent_qualifying_child', 'dependent_records', ['is_qualifying_child'])

    # state_returns table
    op.create_table(
        'state_returns',
        sa.Column('state_return_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('return_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tax_returns.return_id'), nullable=False),
        sa.Column('state_code', sa.String(2), nullable=False),
        sa.Column('state_name', sa.String(50), nullable=False),
        sa.Column('tax_year', sa.Integer(), nullable=False),
        sa.Column('residency_status', sa.String(20), default='full_year'),
        sa.Column('residency_start_date', sa.Date(), nullable=True),
        sa.Column('residency_end_date', sa.Date(), nullable=True),
        sa.Column('state_filing_status', sa.Enum('single', 'married_joint', 'married_separate', 'head_of_household', 'qualifying_widow', name='filingstatus'), nullable=False),
        sa.Column('federal_agi', sa.Numeric(12, 2), default=0),
        sa.Column('state_additions', sa.Numeric(12, 2), default=0),
        sa.Column('state_subtractions', sa.Numeric(12, 2), default=0),
        sa.Column('state_adjusted_income', sa.Numeric(12, 2), default=0),
        sa.Column('state_standard_deduction', sa.Numeric(12, 2), default=0),
        sa.Column('state_itemized_deduction', sa.Numeric(12, 2), default=0),
        sa.Column('deduction_used', sa.String(20), default='standard'),
        sa.Column('personal_exemptions', sa.Integer(), default=0),
        sa.Column('dependent_exemptions', sa.Integer(), default=0),
        sa.Column('exemption_amount', sa.Numeric(12, 2), default=0),
        sa.Column('state_taxable_income', sa.Numeric(12, 2), default=0),
        sa.Column('state_tax_before_credits', sa.Numeric(12, 2), default=0),
        sa.Column('state_credits', postgresql.JSONB(), nullable=True),
        sa.Column('total_state_credits', sa.Numeric(12, 2), default=0),
        sa.Column('state_tax_liability', sa.Numeric(12, 2), default=0),
        sa.Column('local_tax', sa.Numeric(12, 2), default=0),
        sa.Column('local_jurisdiction', sa.String(100), nullable=True),
        sa.Column('state_withholding', sa.Numeric(12, 2), default=0),
        sa.Column('estimated_payments', sa.Numeric(12, 2), default=0),
        sa.Column('state_refund_or_owed', sa.Numeric(12, 2), default=0),
        sa.Column('bracket_breakdown', postgresql.JSONB(), nullable=True),
        sa.Column('calculation_details', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_index('ix_state_return_return_id', 'state_returns', ['return_id'])
    op.create_index('ix_state_return_state', 'state_returns', ['state_code', 'tax_year'])
    op.create_unique_constraint('uq_state_return', 'state_returns', ['return_id', 'state_code'])

    # audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('log_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('return_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tax_returns.return_id'), nullable=True),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('event_category', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(20), default='info'),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('user_id', sa.String(100), nullable=True),
        sa.Column('user_role', sa.String(50), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('field_name', sa.String(100), nullable=True),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('event_metadata', postgresql.JSONB(), nullable=True),
        sa.Column('previous_log_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('hash_value', sa.String(64), nullable=False),
    )

    op.create_index('ix_audit_return_id', 'audit_logs', ['return_id'])
    op.create_index('ix_audit_event_type', 'audit_logs', ['event_type'])
    op.create_index('ix_audit_event_category', 'audit_logs', ['event_category'])
    op.create_index('ix_audit_timestamp', 'audit_logs', ['timestamp'])
    op.create_index('ix_audit_event', 'audit_logs', ['event_type', 'event_category'])
    op.create_index('ix_audit_user', 'audit_logs', ['user_id', 'timestamp'])

    # computation_worksheets table
    op.create_table(
        'computation_worksheets',
        sa.Column('worksheet_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('return_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tax_returns.return_id'), nullable=False),
        sa.Column('worksheet_type', sa.String(50), nullable=False),
        sa.Column('worksheet_name', sa.String(200), nullable=False),
        sa.Column('irs_reference', sa.String(100), nullable=True),
        sa.Column('version', sa.Integer(), default=1),
        sa.Column('is_current', sa.Boolean(), default=True),
        sa.Column('lines', postgresql.JSONB(), nullable=False),
        sa.Column('final_result', sa.Numeric(12, 2), nullable=True),
        sa.Column('result_description', sa.String(200), nullable=True),
        sa.Column('calculated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('calculation_engine_version', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_index('ix_worksheet_return_id', 'computation_worksheets', ['return_id'])
    op.create_index('ix_worksheet_type', 'computation_worksheets', ['worksheet_type', 'return_id'])
    op.create_unique_constraint('uq_worksheet_version', 'computation_worksheets', ['return_id', 'worksheet_type', 'version'])

    # documents table
    op.create_table(
        'documents',
        sa.Column('document_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('return_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tax_returns.return_id'), nullable=True),
        sa.Column('taxpayer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('taxpayers.taxpayer_id'), nullable=True),
        sa.Column('document_type', sa.Enum('w2', '1099-int', '1099-div', '1099-misc', '1099-nec', '1099-b', '1099-r', '1099-g', '1098', '1098-e', '1098-t', 'k1', '1095-a', '1095-b', '1095-c', 'unknown', name='documenttype'), nullable=False, server_default='unknown'),
        sa.Column('tax_year', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('uploaded', 'processing', 'ocr_complete', 'extraction_complete', 'verified', 'applied', 'failed', 'rejected', name='documentstatus'), nullable=False, server_default='uploaded'),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('file_hash', sa.String(64), nullable=True),
        sa.Column('storage_path', sa.String(500), nullable=True),
        sa.Column('thumbnail_path', sa.String(500), nullable=True),
        sa.Column('ocr_engine', sa.String(50), nullable=True),
        sa.Column('ocr_confidence', sa.Numeric(5, 2), nullable=True),
        sa.Column('ocr_raw_text', sa.Text(), nullable=True),
        sa.Column('ocr_completed_at', sa.DateTime(), nullable=True),
        sa.Column('extracted_data', postgresql.JSONB(), nullable=True),
        sa.Column('extraction_confidence', sa.Numeric(5, 2), nullable=True),
        sa.Column('extraction_warnings', postgresql.JSONB(), nullable=True),
        sa.Column('user_verified', sa.Boolean(), default=False),
        sa.Column('user_corrections', postgresql.JSONB(), nullable=True),
        sa.Column('applied_to_return', sa.Boolean(), default=False),
        sa.Column('applied_at', sa.DateTime(), nullable=True),
        sa.Column('uploaded_by', sa.String(100), nullable=True),
        sa.Column('upload_ip_address', sa.String(45), nullable=True),
        sa.Column('upload_user_agent', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_index('ix_doc_return_id', 'documents', ['return_id'])
    op.create_index('ix_doc_taxpayer_id', 'documents', ['taxpayer_id'])
    op.create_index('ix_doc_tax_year', 'documents', ['tax_year'])
    op.create_index('ix_doc_taxpayer_year', 'documents', ['taxpayer_id', 'tax_year'])
    op.create_index('ix_doc_type_status', 'documents', ['document_type', 'status'])
    op.create_index('ix_doc_file_hash', 'documents', ['file_hash'])

    # extracted_fields table
    op.create_table(
        'extracted_fields',
        sa.Column('field_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.document_id'), nullable=False),
        sa.Column('source_field_name', sa.String(100), nullable=False),
        sa.Column('source_field_label', sa.String(200), nullable=True),
        sa.Column('extracted_value', sa.Text(), nullable=True),
        sa.Column('extracted_value_type', sa.String(50), nullable=True),
        sa.Column('confidence_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('bbox_left', sa.Integer(), nullable=True),
        sa.Column('bbox_top', sa.Integer(), nullable=True),
        sa.Column('bbox_width', sa.Integer(), nullable=True),
        sa.Column('bbox_height', sa.Integer(), nullable=True),
        sa.Column('page_number', sa.Integer(), default=1),
        sa.Column('target_table', sa.String(100), nullable=True),
        sa.Column('target_field', sa.String(100), nullable=True),
        sa.Column('irs_form_reference', sa.String(50), nullable=True),
        sa.Column('is_valid', sa.Boolean(), default=True),
        sa.Column('validation_errors', postgresql.JSONB(), nullable=True),
        sa.Column('user_corrected', sa.Boolean(), default=False),
        sa.Column('corrected_value', sa.Text(), nullable=True),
        sa.Column('correction_reason', sa.String(200), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_index('ix_field_document', 'extracted_fields', ['document_id'])
    op.create_index('ix_field_target', 'extracted_fields', ['target_table', 'target_field'])

    # document_processing_logs table
    op.create_table(
        'document_processing_logs',
        sa.Column('log_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.document_id'), nullable=False),
        sa.Column('step_name', sa.String(100), nullable=False),
        sa.Column('step_status', sa.String(50), nullable=False),
        sa.Column('input_data', postgresql.JSONB(), nullable=True),
        sa.Column('output_data', postgresql.JSONB(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', postgresql.JSONB(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_index('ix_processing_log_doc', 'document_processing_logs', ['document_id', 'created_at'])


def downgrade() -> None:
    """Drop all tables."""
    # Drop in reverse order of dependencies
    op.drop_table('document_processing_logs')
    op.drop_table('extracted_fields')
    op.drop_table('documents')
    op.drop_table('computation_worksheets')
    op.drop_table('audit_logs')
    op.drop_table('state_returns')
    op.drop_table('dependent_records')
    op.drop_table('credit_records')
    op.drop_table('deduction_records')
    op.drop_table('form1099_records')
    op.drop_table('w2_records')
    op.drop_table('income_records')
    op.drop_table('taxpayers')
    op.drop_table('tax_returns')

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS documentstatus")
    op.execute("DROP TYPE IF EXISTS documenttype")
    op.execute("DROP TYPE IF EXISTS dependentrelationship")
    op.execute("DROP TYPE IF EXISTS credittype")
    op.execute("DROP TYPE IF EXISTS deductiontype")
    op.execute("DROP TYPE IF EXISTS form1099type")
    op.execute("DROP TYPE IF EXISTS incomesourcetype")
    op.execute("DROP TYPE IF EXISTS returnstatus")
    op.execute("DROP TYPE IF EXISTS filingstatus")
