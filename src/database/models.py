"""
SQLAlchemy ORM Models for US Tax Return Database.

This module defines the complete database schema for tax return storage
with IRS-compliant structure, proper key relationships, and data types.

Architecture:
- Primary Keys: UUID for all tables (globally unique)
- Secondary Keys: Natural business keys (SSN hash, tax year + SSN composite)
- Filing Status Flags: Enum-based status tracking
- Data Types: Proper decimal precision for monetary values
- Constraints: Foreign keys, check constraints, unique constraints

Tax Year: 2025 (Filing in 2026)
"""

from datetime import datetime, date
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional, List
from uuid import uuid4
import hashlib

from sqlalchemy import (
    Column, String, Integer, Numeric, Boolean, Date, DateTime,
    Text, Enum, ForeignKey, Index, CheckConstraint, UniqueConstraint,
    event, JSON
)
from sqlalchemy.dialects.postgresql import UUID, JSONB as PG_JSONB
from sqlalchemy.orm import declarative_base, relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.types import TypeDecorator


# Cross-database compatible JSON type
# Uses JSONB on PostgreSQL, JSON on SQLite/others
class JSONB(TypeDecorator):
    """A portable JSONB type that works with both PostgreSQL and SQLite."""
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_JSONB())
        else:
            return dialect.type_descriptor(JSON())


Base = declarative_base()


# =============================================================================
# ENUMERATIONS (Filing Status Flags)
# =============================================================================

class FilingStatusFlag(str, PyEnum):
    """IRS Filing Status - determines tax brackets and deductions."""
    SINGLE = "single"
    MARRIED_FILING_JOINTLY = "married_joint"
    MARRIED_FILING_SEPARATELY = "married_separate"
    HEAD_OF_HOUSEHOLD = "head_of_household"
    QUALIFYING_SURVIVING_SPOUSE = "qualifying_widow"


class ReturnStatus(str, PyEnum):
    """Tax return processing status."""
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    PENDING_REVIEW = "pending_review"
    REVIEWED = "reviewed"
    READY_TO_FILE = "ready_to_file"
    FILED = "filed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    AMENDED = "amended"
    ARCHIVED = "archived"


class IncomeSourceType(str, PyEnum):
    """Types of income sources per IRS classifications."""
    W2_WAGES = "w2_wages"
    SELF_EMPLOYMENT = "self_employment"
    INTEREST = "interest"
    DIVIDENDS = "dividends"
    CAPITAL_GAINS_SHORT = "capital_gains_short"
    CAPITAL_GAINS_LONG = "capital_gains_long"
    RENTAL = "rental"
    ROYALTY = "royalty"
    RETIREMENT = "retirement"
    SOCIAL_SECURITY = "social_security"
    UNEMPLOYMENT = "unemployment"
    PARTNERSHIP_K1 = "partnership_k1"
    S_CORP_K1 = "s_corp_k1"
    TRUST_K1 = "trust_k1"
    OTHER = "other"


class Form1099Type(str, PyEnum):
    """IRS 1099 Form Types."""
    FORM_1099_INT = "1099-INT"
    FORM_1099_DIV = "1099-DIV"
    FORM_1099_B = "1099-B"
    FORM_1099_MISC = "1099-MISC"
    FORM_1099_NEC = "1099-NEC"
    FORM_1099_R = "1099-R"
    FORM_1099_G = "1099-G"
    FORM_1099_SSA = "1099-SSA"
    FORM_1099_K = "1099-K"
    FORM_1099_S = "1099-S"
    FORM_1099_C = "1099-C"
    FORM_1099_Q = "1099-Q"


class DeductionType(str, PyEnum):
    """Deduction categories per IRS Schedule A."""
    MEDICAL_DENTAL = "medical_dental"
    STATE_LOCAL_INCOME_TAX = "state_local_income_tax"
    STATE_LOCAL_SALES_TAX = "state_local_sales_tax"
    REAL_ESTATE_TAX = "real_estate_tax"
    PERSONAL_PROPERTY_TAX = "personal_property_tax"
    MORTGAGE_INTEREST = "mortgage_interest"
    MORTGAGE_POINTS = "mortgage_points"
    INVESTMENT_INTEREST = "investment_interest"
    CHARITABLE_CASH = "charitable_cash"
    CHARITABLE_NONCASH = "charitable_noncash"
    CASUALTY_LOSS = "casualty_loss"
    OTHER_ITEMIZED = "other_itemized"
    # Above-the-line adjustments
    EDUCATOR_EXPENSE = "educator_expense"
    HSA_CONTRIBUTION = "hsa_contribution"
    SELF_EMPLOYED_HEALTH = "self_employed_health"
    SELF_EMPLOYED_RETIREMENT = "self_employed_retirement"
    STUDENT_LOAN_INTEREST = "student_loan_interest"
    IRA_CONTRIBUTION = "ira_contribution"
    ALIMONY_PAID = "alimony_paid"


class CreditType(str, PyEnum):
    """Tax credit types per IRS guidelines."""
    CHILD_TAX_CREDIT = "child_tax_credit"
    ADDITIONAL_CHILD_TAX_CREDIT = "additional_child_tax_credit"
    EARNED_INCOME_CREDIT = "earned_income_credit"
    CHILD_DEPENDENT_CARE = "child_dependent_care"
    EDUCATION_AOTC = "education_aotc"
    EDUCATION_LLC = "education_llc"
    RETIREMENT_SAVER = "retirement_saver"
    FOREIGN_TAX = "foreign_tax"
    RESIDENTIAL_ENERGY = "residential_energy"
    EV_CREDIT = "ev_credit"
    ADOPTION = "adoption"
    PREMIUM_TAX_CREDIT = "premium_tax_credit"
    OTHER = "other"


class DependentRelationship(str, PyEnum):
    """Dependent relationship types."""
    SON = "son"
    DAUGHTER = "daughter"
    STEPSON = "stepson"
    STEPDAUGHTER = "stepdaughter"
    FOSTER_CHILD = "foster_child"
    BROTHER = "brother"
    SISTER = "sister"
    HALF_BROTHER = "half_brother"
    HALF_SISTER = "half_sister"
    STEPBROTHER = "stepbrother"
    STEPSISTER = "stepsister"
    PARENT = "parent"
    GRANDPARENT = "grandparent"
    GRANDCHILD = "grandchild"
    NIECE = "niece"
    NEPHEW = "nephew"
    UNCLE = "uncle"
    AUNT = "aunt"
    OTHER_RELATIVE = "other_relative"
    NONE = "none"


# =============================================================================
# CORE MODELS
# =============================================================================

class TaxReturnRecord(Base):
    """
    Primary Tax Return Record - Master table for all tax returns.

    Primary Key: return_id (UUID)
    Secondary Key: (tax_year, taxpayer_ssn_hash) - unique composite

    This table adheres to IRS Form 1040 structure.
    """
    __tablename__ = "tax_returns"

    # Primary Key
    return_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Secondary/Natural Key Components
    tax_year = Column(Integer, nullable=False, index=True)
    taxpayer_ssn_hash = Column(String(64), nullable=False, index=True)  # SHA256 hash

    # Filing Status Flag
    filing_status = Column(
        Enum(FilingStatusFlag),
        nullable=False,
        index=True,
        comment="IRS Filing Status - determines tax brackets"
    )

    # Return Status Tracking
    status = Column(
        Enum(ReturnStatus),
        nullable=False,
        default=ReturnStatus.DRAFT,
        index=True
    )

    # Amendment Tracking
    is_amended = Column(Boolean, default=False, index=True)
    original_return_id = Column(UUID(as_uuid=True), ForeignKey("tax_returns.return_id"), nullable=True)
    amendment_number = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    submitted_at = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)

    # IRS Form 1040 Line Items (Monetary - Decimal precision)
    # Income Section (Lines 1-9)
    line_1_wages = Column(Numeric(12, 2), default=0, comment="Line 1: Wages, salaries, tips")
    line_2a_tax_exempt_interest = Column(Numeric(12, 2), default=0)
    line_2b_taxable_interest = Column(Numeric(12, 2), default=0)
    line_3a_qualified_dividends = Column(Numeric(12, 2), default=0)
    line_3b_ordinary_dividends = Column(Numeric(12, 2), default=0)
    line_4a_ira_distributions = Column(Numeric(12, 2), default=0)
    line_4b_taxable_ira = Column(Numeric(12, 2), default=0)
    line_5a_pensions = Column(Numeric(12, 2), default=0)
    line_5b_taxable_pensions = Column(Numeric(12, 2), default=0)
    line_6a_social_security = Column(Numeric(12, 2), default=0)
    line_6b_taxable_social_security = Column(Numeric(12, 2), default=0)
    line_7_capital_gain_loss = Column(Numeric(12, 2), default=0)
    line_8_other_income = Column(Numeric(12, 2), default=0)
    line_9_total_income = Column(Numeric(12, 2), default=0)

    # Adjustments (Lines 10-11)
    line_10_adjustments = Column(Numeric(12, 2), default=0)
    line_11_agi = Column(Numeric(12, 2), default=0, comment="Adjusted Gross Income")

    # Deductions (Lines 12-14)
    line_12a_standard_deduction = Column(Numeric(12, 2), default=0)
    line_12b_charitable_if_standard = Column(Numeric(12, 2), default=0)
    line_12c_total_deduction = Column(Numeric(12, 2), default=0)
    line_13_qbi_deduction = Column(Numeric(12, 2), default=0, comment="Qualified Business Income")
    line_14_total_deductions = Column(Numeric(12, 2), default=0)

    # Taxable Income (Line 15)
    line_15_taxable_income = Column(Numeric(12, 2), default=0)

    # Tax and Credits (Lines 16-24)
    line_16_tax = Column(Numeric(12, 2), default=0)
    line_17_schedule_2_line_3 = Column(Numeric(12, 2), default=0, comment="Additional taxes")
    line_18_total_tax = Column(Numeric(12, 2), default=0)
    line_19_child_tax_credit = Column(Numeric(12, 2), default=0)
    line_20_schedule_3_line_8 = Column(Numeric(12, 2), default=0, comment="Other credits")
    line_21_total_credits = Column(Numeric(12, 2), default=0)
    line_22_tax_minus_credits = Column(Numeric(12, 2), default=0)
    line_23_other_taxes = Column(Numeric(12, 2), default=0)
    line_24_total_tax_liability = Column(Numeric(12, 2), default=0)

    # Payments (Lines 25-33)
    line_25a_w2_withholding = Column(Numeric(12, 2), default=0)
    line_25b_1099_withholding = Column(Numeric(12, 2), default=0)
    line_25c_other_withholding = Column(Numeric(12, 2), default=0)
    line_25d_total_withholding = Column(Numeric(12, 2), default=0)
    line_26_estimated_payments = Column(Numeric(12, 2), default=0)
    line_27_eic = Column(Numeric(12, 2), default=0, comment="Earned Income Credit")
    line_28_additional_child_credit = Column(Numeric(12, 2), default=0)
    line_29_american_opportunity = Column(Numeric(12, 2), default=0)
    line_30_recovery_rebate = Column(Numeric(12, 2), default=0)
    line_31_schedule_3_line_15 = Column(Numeric(12, 2), default=0)
    line_32_other_payments = Column(Numeric(12, 2), default=0)
    line_33_total_payments = Column(Numeric(12, 2), default=0)

    # Refund or Amount Due (Lines 34-38)
    line_34_overpayment = Column(Numeric(12, 2), default=0)
    line_35a_refund = Column(Numeric(12, 2), default=0)
    line_36_applied_to_next_year = Column(Numeric(12, 2), default=0)
    line_37_amount_owed = Column(Numeric(12, 2), default=0)
    line_38_estimated_penalty = Column(Numeric(12, 2), default=0)

    # Additional Tax Components (Schedule 2)
    self_employment_tax = Column(Numeric(12, 2), default=0)
    additional_medicare_tax = Column(Numeric(12, 2), default=0)
    net_investment_income_tax = Column(Numeric(12, 2), default=0)
    alternative_minimum_tax = Column(Numeric(12, 2), default=0)

    # Effective/Marginal Rates (Computed)
    effective_tax_rate = Column(Numeric(6, 4), default=0)
    marginal_tax_rate = Column(Numeric(6, 4), default=0)

    # State Tax Summary
    state_code = Column(String(2), nullable=True, index=True)
    state_tax_liability = Column(Numeric(12, 2), default=0)
    state_refund_or_owed = Column(Numeric(12, 2), default=0)

    # Combined Totals
    combined_tax_liability = Column(Numeric(12, 2), default=0)
    combined_refund_or_owed = Column(Numeric(12, 2), default=0)

    # Metadata
    preparer_ptin = Column(String(11), nullable=True, comment="Preparer Tax ID Number")
    firm_ein = Column(String(10), nullable=True)
    software_version = Column(String(50), nullable=True)
    calculation_version = Column(String(50), nullable=True)

    # Computed Fields Storage (JSON for flexibility)
    computation_details = Column(JSONB, nullable=True, comment="Detailed computation breakdown")
    validation_results = Column(JSONB, nullable=True, comment="Validation check results")

    # Relationships
    taxpayer = relationship("TaxpayerRecord", back_populates="tax_returns", uselist=False)
    income_records = relationship("IncomeRecord", back_populates="tax_return", cascade="all, delete-orphan")
    w2_records = relationship("W2Record", back_populates="tax_return", cascade="all, delete-orphan")
    form1099_records = relationship("Form1099Record", back_populates="tax_return", cascade="all, delete-orphan")
    deduction_records = relationship("DeductionRecord", back_populates="tax_return", cascade="all, delete-orphan")
    credit_records = relationship("CreditRecord", back_populates="tax_return", cascade="all, delete-orphan")
    dependent_records = relationship("DependentRecord", back_populates="tax_return", cascade="all, delete-orphan")
    state_returns = relationship("StateReturnRecord", back_populates="tax_return", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLogRecord", back_populates="tax_return", cascade="all, delete-orphan")
    computation_worksheets = relationship("ComputationWorksheet", back_populates="tax_return", cascade="all, delete-orphan")
    amended_returns = relationship("TaxReturnRecord", backref="original_return", remote_side=[return_id])

    # Constraints
    __table_args__ = (
        UniqueConstraint('tax_year', 'taxpayer_ssn_hash', 'amendment_number', name='uq_return_natural_key'),
        CheckConstraint('tax_year >= 2020 AND tax_year <= 2030', name='ck_valid_tax_year'),
        CheckConstraint('amendment_number >= 0', name='ck_valid_amendment'),
        Index('ix_return_status_year', 'status', 'tax_year'),
        Index('ix_return_filing_status', 'filing_status', 'tax_year'),
    )

    def __repr__(self):
        return f"<TaxReturn(id={self.return_id}, year={self.tax_year}, status={self.status})>"


class TaxpayerRecord(Base):
    """
    Taxpayer Personal Information.

    Primary Key: taxpayer_id (UUID)
    Secondary Key: ssn_hash (unique within system)

    PII is encrypted at rest. SSN stored as hash for lookup.
    """
    __tablename__ = "taxpayers"

    # Primary Key
    taxpayer_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Link to Tax Return
    return_id = Column(UUID(as_uuid=True), ForeignKey("tax_returns.return_id"), nullable=False, index=True)

    # Secondary Key (for lookup without exposing SSN)
    ssn_hash = Column(String(64), nullable=False, index=True)

    # Personal Information (PII - encrypt at rest)
    ssn_encrypted = Column(String(256), nullable=True, comment="AES-256 encrypted SSN")
    first_name = Column(String(100), nullable=False)
    middle_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=False)
    suffix = Column(String(10), nullable=True)  # Jr., Sr., III, etc.

    # Date of Birth (for age-related deductions)
    date_of_birth = Column(Date, nullable=True)

    # Filing Status Flags
    is_primary = Column(Boolean, default=True, comment="Primary taxpayer vs spouse")
    is_over_65 = Column(Boolean, default=False, index=True, comment="Age 65+ flag for additional deduction")
    is_blind = Column(Boolean, default=False, comment="Blind flag for additional deduction")
    is_deceased = Column(Boolean, default=False)
    date_of_death = Column(Date, nullable=True)

    # Contact Information
    address_line_1 = Column(String(200), nullable=True)
    address_line_2 = Column(String(200), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(2), nullable=True, index=True)
    zip_code = Column(String(10), nullable=True)
    country = Column(String(50), default="USA")

    # Communication
    phone = Column(String(20), nullable=True)
    email = Column(String(200), nullable=True)

    # Spouse Information (for MFJ/MFS)
    spouse_ssn_hash = Column(String(64), nullable=True)
    spouse_ssn_encrypted = Column(String(256), nullable=True)
    spouse_first_name = Column(String(100), nullable=True)
    spouse_middle_name = Column(String(100), nullable=True)
    spouse_last_name = Column(String(100), nullable=True)
    spouse_date_of_birth = Column(Date, nullable=True)
    spouse_is_over_65 = Column(Boolean, default=False)
    spouse_is_blind = Column(Boolean, default=False)
    spouse_is_deceased = Column(Boolean, default=False)
    spouse_date_of_death = Column(Date, nullable=True)

    # Occupation (for Schedule C)
    occupation = Column(String(100), nullable=True)
    spouse_occupation = Column(String(100), nullable=True)

    # Bank Information (for direct deposit - encrypted)
    bank_routing_encrypted = Column(String(256), nullable=True)
    bank_account_encrypted = Column(String(256), nullable=True)
    account_type = Column(String(20), nullable=True)  # checking, savings

    # Identity Protection PIN
    ip_pin = Column(String(6), nullable=True, comment="IRS Identity Protection PIN")
    spouse_ip_pin = Column(String(6), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tax_returns = relationship("TaxReturnRecord", back_populates="taxpayer")

    # Computed Properties
    @hybrid_property
    def full_name(self) -> str:
        parts = [self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        parts.append(self.last_name)
        if self.suffix:
            parts.append(self.suffix)
        return " ".join(parts)

    @hybrid_property
    def age(self) -> Optional[int]:
        if self.date_of_birth:
            today = date.today()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None

    __table_args__ = (
        Index('ix_taxpayer_ssn_hash', 'ssn_hash'),
        Index('ix_taxpayer_name', 'last_name', 'first_name'),
    )


class IncomeRecord(Base):
    """
    Income Summary Record - aggregates all income sources.

    Maps to Form 1040 income lines and Schedule 1.
    """
    __tablename__ = "income_records"

    # Primary Key
    income_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign Key to Tax Return
    return_id = Column(UUID(as_uuid=True), ForeignKey("tax_returns.return_id"), nullable=False, index=True)

    # Income Source Classification
    source_type = Column(Enum(IncomeSourceType), nullable=False, index=True)

    # Gross/Net Amounts (Decimal precision for accuracy)
    gross_amount = Column(Numeric(12, 2), nullable=False, default=0)
    adjustments = Column(Numeric(12, 2), default=0, comment="Above-the-line adjustments")
    taxable_amount = Column(Numeric(12, 2), default=0)

    # Withholding
    federal_withholding = Column(Numeric(12, 2), default=0)
    state_withholding = Column(Numeric(12, 2), default=0)
    local_withholding = Column(Numeric(12, 2), default=0)

    # Source Details
    payer_name = Column(String(200), nullable=True)
    payer_ein = Column(String(10), nullable=True)
    payer_address = Column(Text, nullable=True)

    # Form References
    form_type = Column(String(20), nullable=True, comment="W-2, 1099-INT, etc.")
    document_id = Column(String(100), nullable=True, comment="Reference to uploaded document")

    # Flags
    is_foreign_source = Column(Boolean, default=False)
    is_passive_income = Column(Boolean, default=False)
    is_qbi_eligible = Column(Boolean, default=False, comment="Qualified Business Income eligible")

    # State-specific
    state_code = Column(String(2), nullable=True)
    state_wages = Column(Numeric(12, 2), default=0)

    # Metadata
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tax_return = relationship("TaxReturnRecord", back_populates="income_records")

    __table_args__ = (
        Index('ix_income_source_type', 'source_type', 'return_id'),
        CheckConstraint('gross_amount >= 0 OR source_type IN (\'capital_gains_short\', \'capital_gains_long\')',
                       name='ck_income_positive_or_gain'),
    )


class W2Record(Base):
    """
    W-2 Form Record - Employee wage and tax statement.

    Maps to IRS Form W-2 boxes.
    """
    __tablename__ = "w2_records"

    # Primary Key
    w2_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign Key
    return_id = Column(UUID(as_uuid=True), ForeignKey("tax_returns.return_id"), nullable=False, index=True)

    # Employer Information
    employer_name = Column(String(200), nullable=False)
    employer_ein = Column(String(10), nullable=True, comment="Employer Identification Number")
    employer_address = Column(Text, nullable=True)
    employer_state_id = Column(String(20), nullable=True)

    # Employee Information
    employee_ssn_hash = Column(String(64), nullable=False)

    # W-2 Box Values (IRS W-2 Form Structure)
    box_1_wages = Column(Numeric(12, 2), nullable=False, comment="Box 1: Wages, tips, other compensation")
    box_2_federal_tax = Column(Numeric(12, 2), default=0, comment="Box 2: Federal income tax withheld")
    box_3_ss_wages = Column(Numeric(12, 2), default=0, comment="Box 3: Social Security wages")
    box_4_ss_tax = Column(Numeric(12, 2), default=0, comment="Box 4: Social Security tax withheld")
    box_5_medicare_wages = Column(Numeric(12, 2), default=0, comment="Box 5: Medicare wages and tips")
    box_6_medicare_tax = Column(Numeric(12, 2), default=0, comment="Box 6: Medicare tax withheld")
    box_7_ss_tips = Column(Numeric(12, 2), default=0, comment="Box 7: Social Security tips")
    box_8_allocated_tips = Column(Numeric(12, 2), default=0, comment="Box 8: Allocated tips")
    box_10_dependent_care = Column(Numeric(12, 2), default=0, comment="Box 10: Dependent care benefits")
    box_11_nonqualified_plans = Column(Numeric(12, 2), default=0, comment="Box 11: Nonqualified plans")
    box_12_codes = Column(JSONB, nullable=True, comment="Box 12: Coded compensation items")
    box_13_statutory = Column(Boolean, default=False, comment="Box 13: Statutory employee")
    box_13_retirement = Column(Boolean, default=False, comment="Box 13: Retirement plan")
    box_13_third_party_sick = Column(Boolean, default=False, comment="Box 13: Third-party sick pay")
    box_14_other = Column(JSONB, nullable=True, comment="Box 14: Other")

    # State/Local Sections (Boxes 15-20)
    state_code = Column(String(2), nullable=True, index=True)
    box_16_state_wages = Column(Numeric(12, 2), default=0, comment="Box 16: State wages")
    box_17_state_tax = Column(Numeric(12, 2), default=0, comment="Box 17: State income tax")
    box_18_local_wages = Column(Numeric(12, 2), default=0, comment="Box 18: Local wages")
    box_19_local_tax = Column(Numeric(12, 2), default=0, comment="Box 19: Local income tax")
    box_20_locality = Column(String(50), nullable=True, comment="Box 20: Locality name")

    # Multiple states support
    state_2_code = Column(String(2), nullable=True)
    state_2_wages = Column(Numeric(12, 2), default=0)
    state_2_tax = Column(Numeric(12, 2), default=0)

    # Document reference
    document_id = Column(String(100), nullable=True)
    is_corrected = Column(Boolean, default=False, comment="W-2c correction indicator")

    # Validation
    is_validated = Column(Boolean, default=False)
    validation_notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tax_return = relationship("TaxReturnRecord", back_populates="w2_records")

    __table_args__ = (
        Index('ix_w2_employer', 'employer_ein', 'return_id'),
        CheckConstraint('box_1_wages >= 0', name='ck_w2_wages_positive'),
        CheckConstraint('box_3_ss_wages <= 176100 OR box_3_ss_wages IS NULL',
                       name='ck_w2_ss_wage_base_2025'),  # 2025 SS wage base
    )


class Form1099Record(Base):
    """
    1099 Form Record - Various types of 1099 information returns.
    """
    __tablename__ = "form1099_records"

    # Primary Key
    form1099_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign Key
    return_id = Column(UUID(as_uuid=True), ForeignKey("tax_returns.return_id"), nullable=False, index=True)

    # Form Type
    form_type = Column(Enum(Form1099Type), nullable=False, index=True)

    # Payer Information
    payer_name = Column(String(200), nullable=False)
    payer_tin = Column(String(10), nullable=True, comment="Payer TIN (EIN or SSN)")
    payer_address = Column(Text, nullable=True)

    # Recipient Information
    recipient_ssn_hash = Column(String(64), nullable=False)

    # Common Fields (varies by form type)
    box_1_amount = Column(Numeric(12, 2), default=0, comment="Primary amount field")
    box_2_amount = Column(Numeric(12, 2), default=0, comment="Secondary amount field")
    box_3_amount = Column(Numeric(12, 2), default=0)
    box_4_federal_tax = Column(Numeric(12, 2), default=0, comment="Federal tax withheld")
    box_5_amount = Column(Numeric(12, 2), default=0)

    # 1099-DIV Specific
    qualified_dividends = Column(Numeric(12, 2), default=0)
    capital_gain_distributions = Column(Numeric(12, 2), default=0)
    nondividend_distributions = Column(Numeric(12, 2), default=0)
    section_199a_dividends = Column(Numeric(12, 2), default=0)

    # 1099-INT Specific
    tax_exempt_interest = Column(Numeric(12, 2), default=0)
    private_activity_bond = Column(Numeric(12, 2), default=0)
    us_savings_bond_interest = Column(Numeric(12, 2), default=0)

    # 1099-B Specific (Capital Gains)
    proceeds = Column(Numeric(12, 2), default=0)
    cost_basis = Column(Numeric(12, 2), default=0)
    gain_loss = Column(Numeric(12, 2), default=0)
    is_short_term = Column(Boolean, nullable=True)
    is_covered_security = Column(Boolean, default=True)
    wash_sale_loss = Column(Numeric(12, 2), default=0)

    # 1099-R Specific (Retirement)
    gross_distribution = Column(Numeric(12, 2), default=0)
    taxable_amount = Column(Numeric(12, 2), default=0)
    distribution_code = Column(String(5), nullable=True)
    is_total_distribution = Column(Boolean, default=False)

    # 1099-G Specific (Government Payments)
    unemployment_compensation = Column(Numeric(12, 2), default=0)
    state_tax_refund = Column(Numeric(12, 2), default=0)

    # State Information
    state_code = Column(String(2), nullable=True)
    state_tax_withheld = Column(Numeric(12, 2), default=0)
    state_id_number = Column(String(20), nullable=True)

    # Additional Data (JSON for form-specific fields)
    additional_data = Column(JSONB, nullable=True)

    # Document reference
    document_id = Column(String(100), nullable=True)
    is_corrected = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tax_return = relationship("TaxReturnRecord", back_populates="form1099_records")

    __table_args__ = (
        Index('ix_1099_form_type', 'form_type', 'return_id'),
        Index('ix_1099_payer', 'payer_tin', 'return_id'),
    )


class DeductionRecord(Base):
    """
    Deduction Record - Itemized and above-the-line deductions.

    Maps to Schedule A and Schedule 1 adjustments.
    """
    __tablename__ = "deduction_records"

    # Primary Key
    deduction_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign Key
    return_id = Column(UUID(as_uuid=True), ForeignKey("tax_returns.return_id"), nullable=False, index=True)

    # Deduction Classification
    deduction_type = Column(Enum(DeductionType), nullable=False, index=True)
    is_itemized = Column(Boolean, default=True, comment="True if itemized, False if above-the-line")

    # Amount
    gross_amount = Column(Numeric(12, 2), nullable=False, default=0)
    limitation_amount = Column(Numeric(12, 2), default=0, comment="Amount limited by AGI or cap")
    allowed_amount = Column(Numeric(12, 2), default=0, comment="Final deductible amount")

    # Limitation Tracking
    limitation_type = Column(String(50), nullable=True, comment="AGI floor, SALT cap, etc.")
    limitation_percentage = Column(Numeric(5, 4), nullable=True)
    agi_floor_applied = Column(Numeric(12, 2), default=0)

    # Supporting Details
    payee_name = Column(String(200), nullable=True)
    payee_ein = Column(String(10), nullable=True)
    description = Column(Text, nullable=True)

    # Charitable Contribution Details
    is_cash_contribution = Column(Boolean, nullable=True)
    charity_name = Column(String(200), nullable=True)
    charity_ein = Column(String(10), nullable=True)
    property_description = Column(Text, nullable=True)
    property_fmv = Column(Numeric(12, 2), nullable=True)
    property_cost_basis = Column(Numeric(12, 2), nullable=True)

    # Mortgage Interest Details
    lender_name = Column(String(200), nullable=True)
    mortgage_principal = Column(Numeric(14, 2), nullable=True)
    mortgage_start_date = Column(Date, nullable=True)
    is_home_acquisition_debt = Column(Boolean, nullable=True)

    # Medical Expense Details
    medical_provider = Column(String(200), nullable=True)
    medical_service_type = Column(String(100), nullable=True)

    # Document Reference
    document_id = Column(String(100), nullable=True)
    receipt_required = Column(Boolean, default=False)
    receipt_on_file = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tax_return = relationship("TaxReturnRecord", back_populates="deduction_records")

    __table_args__ = (
        Index('ix_deduction_type', 'deduction_type', 'return_id'),
        CheckConstraint('gross_amount >= 0', name='ck_deduction_positive'),
    )


class CreditRecord(Base):
    """
    Tax Credit Record - Refundable and non-refundable credits.
    """
    __tablename__ = "credit_records"

    # Primary Key
    credit_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign Key
    return_id = Column(UUID(as_uuid=True), ForeignKey("tax_returns.return_id"), nullable=False, index=True)

    # Credit Classification
    credit_type = Column(Enum(CreditType), nullable=False, index=True)
    is_refundable = Column(Boolean, default=False, index=True)

    # Amount Calculation
    tentative_credit = Column(Numeric(12, 2), default=0, comment="Before limitations")
    phaseout_reduction = Column(Numeric(12, 2), default=0)
    other_limitations = Column(Numeric(12, 2), default=0)
    allowed_credit = Column(Numeric(12, 2), default=0, comment="Final allowed amount")

    # Phaseout Information
    phaseout_start = Column(Numeric(12, 2), nullable=True)
    phaseout_end = Column(Numeric(12, 2), nullable=True)
    phaseout_rate = Column(Numeric(5, 4), nullable=True)

    # Credit-Specific Details
    qualifying_children = Column(Integer, default=0)
    qualifying_expenses = Column(Numeric(12, 2), default=0)
    foreign_taxes_paid = Column(Numeric(12, 2), default=0)
    education_expenses = Column(Numeric(12, 2), default=0)

    # Student Information (for education credits)
    student_name = Column(String(200), nullable=True)
    student_ssn_hash = Column(String(64), nullable=True)
    educational_institution = Column(String(200), nullable=True)
    institution_ein = Column(String(10), nullable=True)

    # Form References
    form_number = Column(String(20), nullable=True, comment="Supporting form (8863, 2441, etc.)")

    # Document Reference
    document_id = Column(String(100), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tax_return = relationship("TaxReturnRecord", back_populates="credit_records")

    __table_args__ = (
        Index('ix_credit_type', 'credit_type', 'return_id'),
    )


class DependentRecord(Base):
    """
    Dependent Record - Qualifying children and relatives.
    """
    __tablename__ = "dependent_records"

    # Primary Key
    dependent_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign Key
    return_id = Column(UUID(as_uuid=True), ForeignKey("tax_returns.return_id"), nullable=False, index=True)

    # Dependent Information
    ssn_hash = Column(String(64), nullable=False)
    ssn_encrypted = Column(String(256), nullable=True)
    first_name = Column(String(100), nullable=False)
    middle_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(Date, nullable=True)

    # Relationship Classification
    relation_type = Column(Enum(DependentRelationship), nullable=False)

    # Qualifying Flags (for CTC, EITC, etc.)
    is_qualifying_child = Column(Boolean, default=False, index=True)
    is_qualifying_relative = Column(Boolean, default=False)
    months_lived_with_taxpayer = Column(Integer, default=12)

    # Age-Based Qualifications
    is_under_17 = Column(Boolean, default=False, comment="Qualifies for CTC")
    is_under_19 = Column(Boolean, default=False, comment="Child qualification")
    is_under_24_student = Column(Boolean, default=False, comment="Student child qualification")
    is_permanently_disabled = Column(Boolean, default=False)

    # Student Status
    is_student = Column(Boolean, default=False)
    school_name = Column(String(200), nullable=True)

    # Support Test
    provided_over_half_support = Column(Boolean, default=True)
    dependent_gross_income = Column(Numeric(12, 2), default=0)

    # Credit Eligibility Flags
    eligible_for_ctc = Column(Boolean, default=False)
    eligible_for_odc = Column(Boolean, default=False, comment="Other Dependent Credit")
    eligible_for_eic = Column(Boolean, default=False)
    eligible_for_cdcc = Column(Boolean, default=False, comment="Child & Dependent Care Credit")

    # Citizenship/Residency
    is_us_citizen = Column(Boolean, default=True)
    is_resident_alien = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tax_return = relationship("TaxReturnRecord", back_populates="dependent_records")

    # Computed Properties
    @hybrid_property
    def age(self) -> Optional[int]:
        if self.date_of_birth:
            today = date.today()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None

    __table_args__ = (
        Index('ix_dependent_ssn', 'ssn_hash'),
        CheckConstraint('months_lived_with_taxpayer >= 0 AND months_lived_with_taxpayer <= 12',
                       name='ck_months_valid'),
    )


class StateReturnRecord(Base):
    """
    State Tax Return Record - State-specific tax calculations.
    """
    __tablename__ = "state_returns"

    # Primary Key
    state_return_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign Keys
    return_id = Column(UUID(as_uuid=True), ForeignKey("tax_returns.return_id"), nullable=False, index=True)

    # State Identification
    state_code = Column(String(2), nullable=False, index=True)
    state_name = Column(String(50), nullable=False)
    tax_year = Column(Integer, nullable=False)

    # Residency
    residency_status = Column(String(20), default="full_year", comment="full_year, part_year, nonresident")
    residency_start_date = Column(Date, nullable=True)
    residency_end_date = Column(Date, nullable=True)

    # Filing Status (may differ from federal)
    state_filing_status = Column(Enum(FilingStatusFlag), nullable=False)

    # Income (State Starting Point)
    federal_agi = Column(Numeric(12, 2), default=0)
    state_additions = Column(Numeric(12, 2), default=0)
    state_subtractions = Column(Numeric(12, 2), default=0)
    state_adjusted_income = Column(Numeric(12, 2), default=0)

    # Deductions
    state_standard_deduction = Column(Numeric(12, 2), default=0)
    state_itemized_deduction = Column(Numeric(12, 2), default=0)
    deduction_used = Column(String(20), default="standard")

    # Exemptions
    personal_exemptions = Column(Integer, default=0)
    dependent_exemptions = Column(Integer, default=0)
    exemption_amount = Column(Numeric(12, 2), default=0)

    # Taxable Income
    state_taxable_income = Column(Numeric(12, 2), default=0)

    # Tax Calculation
    state_tax_before_credits = Column(Numeric(12, 2), default=0)
    state_credits = Column(JSONB, nullable=True, comment="State-specific credits breakdown")
    total_state_credits = Column(Numeric(12, 2), default=0)
    state_tax_liability = Column(Numeric(12, 2), default=0)

    # Local Taxes
    local_tax = Column(Numeric(12, 2), default=0)
    local_jurisdiction = Column(String(100), nullable=True)

    # Withholding and Payments
    state_withholding = Column(Numeric(12, 2), default=0)
    estimated_payments = Column(Numeric(12, 2), default=0)

    # Refund/Owed
    state_refund_or_owed = Column(Numeric(12, 2), default=0)

    # Computation Details
    bracket_breakdown = Column(JSONB, nullable=True)
    calculation_details = Column(JSONB, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tax_return = relationship("TaxReturnRecord", back_populates="state_returns")

    __table_args__ = (
        UniqueConstraint('return_id', 'state_code', name='uq_state_return'),
        Index('ix_state_return_state', 'state_code', 'tax_year'),
    )


class AuditLogRecord(Base):
    """
    Audit Log Record - Immutable audit trail for compliance.
    """
    __tablename__ = "audit_logs"

    # Primary Key
    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign Key (optional - system events may not have return)
    return_id = Column(UUID(as_uuid=True), ForeignKey("tax_returns.return_id"), nullable=True, index=True)

    # Event Classification
    event_type = Column(String(50), nullable=False, index=True)
    event_category = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), default="info", comment="info, warning, error, critical")

    # Timestamp (immutable)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # User Information
    user_id = Column(String(100), nullable=True)
    user_role = Column(String(50), nullable=True, comment="taxpayer, preparer, reviewer, admin")
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # Change Tracking
    field_name = Column(String(100), nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)

    # Event Details
    description = Column(Text, nullable=True)
    event_metadata = Column(JSONB, nullable=True)

    # Integrity
    previous_log_id = Column(UUID(as_uuid=True), nullable=True, comment="Chain reference")
    hash_value = Column(String(64), nullable=False, comment="SHA256 for integrity verification")

    # Relationships
    tax_return = relationship("TaxReturnRecord", back_populates="audit_logs")

    __table_args__ = (
        Index('ix_audit_timestamp', 'timestamp'),
        Index('ix_audit_event', 'event_type', 'event_category'),
        Index('ix_audit_user', 'user_id', 'timestamp'),
    )


class ComputationWorksheet(Base):
    """
    Computation Worksheet - IRS worksheet calculations for tax computation.

    Stores step-by-step calculations per IRS worksheet formats.
    """
    __tablename__ = "computation_worksheets"

    # Primary Key
    worksheet_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign Key
    return_id = Column(UUID(as_uuid=True), ForeignKey("tax_returns.return_id"), nullable=False, index=True)

    # Worksheet Identification
    worksheet_type = Column(String(50), nullable=False, index=True, comment="tax_computation, eitc, ctc, etc.")
    worksheet_name = Column(String(200), nullable=False)
    irs_reference = Column(String(100), nullable=True, comment="IRS publication/form reference")

    # Version Tracking
    version = Column(Integer, default=1)
    is_current = Column(Boolean, default=True)

    # Line-by-Line Computation (JSON structure per IRS worksheet)
    lines = Column(JSONB, nullable=False, comment="Line-by-line calculations")

    # Example structure for lines:
    # {
    #     "line_1": {"description": "Taxable income", "amount": 100000.00, "source": "Form 1040 Line 15"},
    #     "line_2": {"description": "Enter amount from Tax Table", "amount": 17400.00},
    #     ...
    # }

    # Summary
    final_result = Column(Numeric(12, 2), nullable=True)
    result_description = Column(String(200), nullable=True)

    # Calculation Metadata
    calculated_at = Column(DateTime, default=datetime.utcnow)
    calculation_engine_version = Column(String(50), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tax_return = relationship("TaxReturnRecord", back_populates="computation_worksheets")

    __table_args__ = (
        Index('ix_worksheet_type', 'worksheet_type', 'return_id'),
        UniqueConstraint('return_id', 'worksheet_type', 'version', name='uq_worksheet_version'),
    )


# =============================================================================
# DOCUMENT STORAGE MODELS (for OCR & Upload)
# =============================================================================

class DocumentType(str, PyEnum):
    """Types of tax documents that can be uploaded."""
    W2 = "w2"
    FORM_1099_INT = "1099-int"
    FORM_1099_DIV = "1099-div"
    FORM_1099_MISC = "1099-misc"
    FORM_1099_NEC = "1099-nec"
    FORM_1099_B = "1099-b"
    FORM_1099_R = "1099-r"
    FORM_1099_G = "1099-g"
    FORM_1098 = "1098"
    FORM_1098_E = "1098-e"
    FORM_1098_T = "1098-t"
    SCHEDULE_K1 = "k1"
    FORM_1095_A = "1095-a"
    FORM_1095_B = "1095-b"
    FORM_1095_C = "1095-c"
    UNKNOWN = "unknown"


class DocumentStatus(str, PyEnum):
    """Status of uploaded document processing."""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    OCR_COMPLETE = "ocr_complete"
    EXTRACTION_COMPLETE = "extraction_complete"
    VERIFIED = "verified"
    APPLIED = "applied"
    FAILED = "failed"
    REJECTED = "rejected"


class DocumentRecord(Base):
    """
    Uploaded Document Record - stores metadata for uploaded tax documents.

    Supports W-2, 1099, 1098, and other tax forms uploaded by users.
    """
    __tablename__ = "documents"

    # Primary Key
    document_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign Keys
    return_id = Column(UUID(as_uuid=True), ForeignKey("tax_returns.return_id"), nullable=True, index=True)
    taxpayer_id = Column(UUID(as_uuid=True), ForeignKey("taxpayers.taxpayer_id"), nullable=True, index=True)

    # Document Classification
    document_type = Column(Enum(DocumentType), nullable=False, default=DocumentType.UNKNOWN)
    tax_year = Column(Integer, nullable=False, index=True)
    status = Column(Enum(DocumentStatus), nullable=False, default=DocumentStatus.UPLOADED)

    # File Information
    original_filename = Column(String(255), nullable=False)
    file_size_bytes = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    file_hash = Column(String(64), nullable=True, comment="SHA256 hash for deduplication")

    # Storage
    storage_path = Column(String(500), nullable=True, comment="S3/local path to file")
    thumbnail_path = Column(String(500), nullable=True)

    # OCR Processing
    ocr_engine = Column(String(50), nullable=True, comment="tesseract, aws_textract, google_vision")
    ocr_confidence = Column(Numeric(5, 2), nullable=True, comment="0-100 confidence score")
    ocr_raw_text = Column(Text, nullable=True)
    ocr_completed_at = Column(DateTime, nullable=True)

    # Extracted Data (JSON)
    extracted_data = Column(JSONB, nullable=True, comment="Structured data extracted from document")
    extraction_confidence = Column(Numeric(5, 2), nullable=True)
    extraction_warnings = Column(JSONB, nullable=True)

    # User Actions
    user_verified = Column(Boolean, default=False)
    user_corrections = Column(JSONB, nullable=True, comment="User corrections to extracted data")
    applied_to_return = Column(Boolean, default=False)
    applied_at = Column(DateTime, nullable=True)

    # Upload Metadata
    uploaded_by = Column(String(100), nullable=True)
    upload_ip_address = Column(String(45), nullable=True)
    upload_user_agent = Column(String(500), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('ix_doc_taxpayer_year', 'taxpayer_id', 'tax_year'),
        Index('ix_doc_type_status', 'document_type', 'status'),
        Index('ix_doc_file_hash', 'file_hash'),
    )


class ExtractedFieldRecord(Base):
    """
    Extracted Field Record - stores individual fields extracted from documents.

    Maps OCR-extracted fields to their target locations in tax return.
    """
    __tablename__ = "extracted_fields"

    # Primary Key
    field_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign Key
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.document_id"), nullable=False, index=True)

    # Field Identification
    source_field_name = Column(String(100), nullable=False, comment="Field name from document (e.g., 'Box 1')")
    source_field_label = Column(String(200), nullable=True, comment="Label on document (e.g., 'Wages, tips, other compensation')")

    # Extracted Value
    extracted_value = Column(Text, nullable=True)
    extracted_value_type = Column(String(50), nullable=True, comment="string, decimal, date, ssn, ein")
    confidence_score = Column(Numeric(5, 2), nullable=True)

    # Bounding Box (for highlighting in UI)
    bbox_left = Column(Integer, nullable=True)
    bbox_top = Column(Integer, nullable=True)
    bbox_width = Column(Integer, nullable=True)
    bbox_height = Column(Integer, nullable=True)
    page_number = Column(Integer, default=1)

    # Target Mapping
    target_table = Column(String(100), nullable=True, comment="Target table (e.g., 'w2_records')")
    target_field = Column(String(100), nullable=True, comment="Target field (e.g., 'wages_tips_compensation')")
    irs_form_reference = Column(String(50), nullable=True, comment="IRS form line reference")

    # Validation
    is_valid = Column(Boolean, default=True)
    validation_errors = Column(JSONB, nullable=True)

    # User Corrections
    user_corrected = Column(Boolean, default=False)
    corrected_value = Column(Text, nullable=True)
    correction_reason = Column(String(200), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('ix_field_document', 'document_id'),
        Index('ix_field_target', 'target_table', 'target_field'),
    )


class DocumentProcessingLog(Base):
    """
    Document Processing Log - audit trail for document processing steps.
    """
    __tablename__ = "document_processing_logs"

    # Primary Key
    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign Key
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.document_id"), nullable=False, index=True)

    # Processing Step
    step_name = Column(String(100), nullable=False, comment="upload, ocr, extraction, validation, apply")
    step_status = Column(String(50), nullable=False, comment="started, completed, failed")

    # Details
    input_data = Column(JSONB, nullable=True)
    output_data = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    error_details = Column(JSONB, nullable=True)

    # Performance
    duration_ms = Column(Integer, nullable=True)

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('ix_processing_log_doc', 'document_id', 'created_at'),
    )


# =============================================================================
# PREPARER / CPA WORKSPACE MODELS (Phase 1-2 Multi-Client Management)
# =============================================================================

class ClientStatusDB(str, PyEnum):
    """Status of a client in the CPA's workspace."""
    NEW = "new"
    IN_PROGRESS = "in_progress"
    READY_FOR_REVIEW = "ready_for_review"
    REVIEWED = "reviewed"
    DELIVERED = "delivered"
    ARCHIVED = "archived"


class PreparerRecord(Base):
    """
    Preparer (CPA) Record - Tax preparer managing multiple clients.

    Phase 1-2: Single preparer, many clients, no teams.
    This is a "firm-lite" model for initial multi-client support.
    """
    __tablename__ = "preparers"

    # Primary Key
    preparer_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Professional Info
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    phone = Column(String(20), nullable=True)

    # Credentials (display only, not verified)
    credentials = Column(JSONB, nullable=True, default=list, comment="['CPA', 'EA']")
    license_state = Column(String(2), nullable=True, comment="Primary state of licensure")

    # Branding (for white-label Phase 4)
    firm_name = Column(String(255), nullable=True)
    logo_url = Column(String(500), nullable=True)
    primary_color = Column(String(7), default="#2E7D32")
    secondary_color = Column(String(7), default="#4CAF50")

    # Settings
    default_tax_year = Column(Integer, default=2025)
    timezone = Column(String(50), default="America/New_York")

    # Metadata
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)

    # Relationships
    client_sessions = relationship("ClientSessionRecord", back_populates="preparer")
    clients = relationship("ClientRecord", back_populates="preparer")

    __table_args__ = (
        Index('ix_preparer_email', 'email'),
        Index('ix_preparer_active', 'is_active'),
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class ClientRecord(Base):
    """
    Client Record - Taxpayer assigned to a preparer.

    Links clients to preparers for multi-client management.
    """
    __tablename__ = "clients"

    # Primary Key
    client_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign Key to Preparer
    preparer_id = Column(UUID(as_uuid=True), ForeignKey("preparers.preparer_id"), nullable=False, index=True)

    # External ID (CPA's own numbering)
    external_id = Column(String(100), nullable=True, index=True)

    # Identity (hashed for privacy)
    ssn_hash = Column(String(64), nullable=True, unique=True, comment="SHA256 hash for lookup")

    # Client Info
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)

    # Address
    street_address = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(2), nullable=True)
    zip_code = Column(String(10), nullable=True)

    # Status
    is_active = Column(Boolean, default=True, index=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    preparer = relationship("PreparerRecord", back_populates="clients")
    sessions = relationship("ClientSessionRecord", back_populates="client")

    __table_args__ = (
        Index('ix_client_preparer', 'preparer_id', 'is_active'),
        Index('ix_client_name', 'last_name', 'first_name'),
        UniqueConstraint('preparer_id', 'external_id', name='uq_client_external_id'),
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class ClientSessionRecord(Base):
    """
    Client Session Record - Persistent work session for a client/tax year.

    Enables "Resume client analysis", "View past scenarios", "Duplicate prior year".
    This is the core table for Phase 1 persistence.
    """
    __tablename__ = "client_sessions"

    # Primary Key
    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign Keys
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.client_id"), nullable=False, index=True)
    preparer_id = Column(UUID(as_uuid=True), ForeignKey("preparers.preparer_id"), nullable=False, index=True)

    # Tax Year
    tax_year = Column(Integer, nullable=False, default=2025, index=True)

    # Status
    status = Column(Enum(ClientStatusDB), nullable=False, default=ClientStatusDB.NEW, index=True)

    # Work State References
    return_id = Column(UUID(as_uuid=True), ForeignKey("tax_returns.return_id"), nullable=True)
    scenario_ids = Column(JSONB, nullable=True, default=list, comment="List of scenario UUIDs")
    recommendation_plan_id = Column(UUID(as_uuid=True), nullable=True)

    # Documents
    document_ids = Column(JSONB, nullable=True, default=list, comment="List of document UUIDs")

    # Progress Tracking
    documents_processed = Column(Integer, default=0)
    calculations_run = Column(Integer, default=0)
    scenarios_analyzed = Column(Integer, default=0)

    # Key Metrics (for dashboard display)
    estimated_refund = Column(Numeric(12, 2), nullable=True)
    estimated_tax_owed = Column(Numeric(12, 2), nullable=True)
    total_income = Column(Numeric(14, 2), nullable=True)
    potential_savings = Column(Numeric(12, 2), nullable=True)

    # Notes
    preparer_notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_accessed_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    client = relationship("ClientRecord", back_populates="sessions")
    preparer = relationship("PreparerRecord", back_populates="client_sessions")
    tax_return = relationship("TaxReturnRecord", foreign_keys=[return_id])

    __table_args__ = (
        UniqueConstraint('client_id', 'tax_year', name='uq_client_session_year'),
        Index('ix_session_preparer_year', 'preparer_id', 'tax_year'),
        Index('ix_session_status', 'status', 'preparer_id'),
        Index('ix_session_last_accessed', 'last_accessed_at'),
    )


# =============================================================================
# DATABASE UTILITY FUNCTIONS
# =============================================================================

def hash_ssn(ssn: str) -> str:
    """
    Create SHA256 hash of SSN for secure lookup.

    Args:
        ssn: Social Security Number (with or without dashes)

    Returns:
        64-character hexadecimal hash string

    H3 SECURITY LIMITATION - DISCLOSED:
    ====================================
    This implementation uses a simple SHA256 hash WITHOUT a salt or pepper.

    Known limitations:
    1. SSNs have limited key space (~1 billion combinations). Pre-computed
       rainbow tables could reverse hashes in <1 second with modern hardware.
    2. Identical SSNs produce identical hashes, enabling correlation attacks
       between records or databases.
    3. This does NOT meet NIST SP 800-132 recommendations for password/secret
       hashing which require adaptive functions (bcrypt, scrypt, Argon2).

    Why this was accepted for FREEZE:
    - SSN hash is used for LOOKUP ONLY (finding client by SSN), not storage
    - Actual SSN is never stored in database (only the hash)
    - Production deployment MUST use encrypted database connections
    - Future enhancement: Add per-tenant salt stored in HSM

    For production security hardening, consider:
    - HMAC-SHA256 with environment-variable secret key
    - Per-tenant salt stored in secure vault
    - Migration to Argon2id with appropriate work factors

    See: OWASP Cryptographic Failures, NIST SP 800-132
    """
    # Remove any formatting
    clean_ssn = ssn.replace("-", "").replace(" ", "")

    # Create hash (H3: No salt - see limitation documentation above)
    return hashlib.sha256(clean_ssn.encode()).hexdigest()


def generate_return_id() -> str:
    """Generate unique return ID."""
    return str(uuid4())


# =============================================================================
# EVENT LISTENERS
# =============================================================================

@event.listens_for(TaxReturnRecord, 'before_update')
def receive_before_update(mapper, connection, target):
    """Update timestamp on record modification."""
    target.updated_at = datetime.utcnow()


@event.listens_for(AuditLogRecord, 'before_insert')
def calculate_audit_hash(mapper, connection, target):
    """Calculate integrity hash for audit record."""
    hash_content = f"{target.log_id}{target.timestamp}{target.event_type}{target.description}"
    target.hash_value = hashlib.sha256(hash_content.encode()).hexdigest()


# =============================================================================
# RBAC MODELS IMPORT
# =============================================================================
# Import RBAC models so they are registered with Base.metadata
# This enables Alembic migrations to detect all tables
try:
    from core.rbac.models import (
        Permission,
        RoleTemplate,
        RolePermission,
        UserRoleAssignment,
        UserPermissionOverride,
        RBACAuditLog,
        PermissionCacheVersion,
        Partner,
        PartnerFirm,
        PartnerAdmin,
        ClientAccessGrant,
    )
except ImportError:
    # core.rbac may not be available in all environments
    pass
