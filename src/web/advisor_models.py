"""
Pydantic models for the Intelligent Tax Advisor API.

Extracted from intelligent_advisor_api.py to reduce module size
and enable reuse across report generation, parsing, and chat endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class FilingStatus(str, Enum):
    SINGLE = "single"
    MARRIED_JOINT = "married_joint"
    MARRIED_SEPARATE = "married_separate"
    HEAD_OF_HOUSEHOLD = "head_of_household"
    QUALIFYING_WIDOW = "qualifying_widow"


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[datetime] = None


class TaxProfileInput(BaseModel):
    """User's tax profile for analysis."""
    filing_status: Optional[FilingStatus] = None
    total_income: Optional[float] = None
    w2_income: Optional[float] = None
    business_income: Optional[float] = None
    investment_income: Optional[float] = None
    rental_income: Optional[float] = None
    dependents: Optional[int] = 0
    age: Optional[int] = None
    spouse_age: Optional[int] = None
    state: Optional[str] = None

    # Capital gains and investment income
    capital_gains_long: Optional[float] = None
    capital_gains_short: Optional[float] = None
    capital_gains: Optional[float] = None
    dividend_income: Optional[float] = None
    qualified_dividends: Optional[float] = None
    interest_income: Optional[float] = None

    # Deductions
    mortgage_interest: Optional[float] = None
    property_taxes: Optional[float] = None
    state_income_tax: Optional[float] = None
    charitable_donations: Optional[float] = None
    medical_expenses: Optional[float] = None

    # Retirement
    retirement_401k: Optional[float] = None
    retirement_ira: Optional[float] = None
    hsa_contributions: Optional[float] = None

    # Business specific
    is_self_employed: Optional[bool] = False
    business_expenses: Optional[float] = None
    home_office_sqft: Optional[float] = None
    vehicle_miles: Optional[float] = None
    health_insurance_premiums: Optional[float] = None
    w2_wages_paid: Optional[float] = None

    # K-1 Income (Schedule E Part II/III)
    k1_ordinary_income: Optional[float] = None
    k1_rental_income: Optional[float] = None
    k1_interest_income: Optional[float] = None
    k1_dividends: Optional[float] = None
    k1_capital_gains: Optional[float] = None
    k1_section_179: Optional[float] = None
    k1_guaranteed_payments: Optional[float] = None
    k1_is_passive: Optional[bool] = True
    k1_w2_wages: Optional[float] = None
    k1_ubia: Optional[float] = None
    k1_is_sstb: Optional[bool] = False

    # Enhanced Rental Property (Schedule E Part I)
    rental_gross_income: Optional[float] = None
    rental_expenses: Optional[float] = None
    rental_depreciation: Optional[float] = None
    rental_mortgage_interest: Optional[float] = None
    rental_property_taxes: Optional[float] = None
    rental_is_active_participant: Optional[bool] = True
    rental_is_real_estate_professional: Optional[bool] = False

    # Education
    student_loan_interest: Optional[float] = None

    # Withholding and payments
    federal_withholding: Optional[float] = None
    estimated_payments: Optional[float] = None


class ChatRequest(BaseModel):
    """Request for intelligent chat interaction."""
    session_id: str
    message: str
    profile: Optional[TaxProfileInput] = None
    conversation_history: Optional[List[ChatMessage]] = []
    context: Optional[Dict[str, Any]] = {}


class StrategyRecommendation(BaseModel):
    """A single tax strategy recommendation."""
    id: str
    category: str
    title: str
    summary: str
    detailed_explanation: str
    estimated_savings: float
    confidence: str
    priority: str
    action_steps: List[str]
    irs_reference: Optional[str] = None
    deadline: Optional[str] = None


class TaxCalculationResult(BaseModel):
    """Comprehensive tax calculation result with full breakdown."""
    gross_income: float
    adjustments: float
    agi: float
    deductions: float
    deduction_type: str
    taxable_income: float
    federal_tax: float
    state_tax: float
    self_employment_tax: float
    total_tax: float
    effective_rate: float
    marginal_rate: float
    refund_or_owed: float
    is_refund: bool

    amt_tax: Optional[float] = 0.0
    niit_tax: Optional[float] = 0.0
    child_tax_credit: Optional[float] = 0.0
    qbi_deduction: Optional[float] = 0.0
    itemized_breakdown: Optional[Dict[str, float]] = None

    short_term_gains: Optional[float] = 0.0
    long_term_gains: Optional[float] = 0.0
    capital_gains_tax: Optional[float] = 0.0
    capital_loss_deduction: Optional[float] = 0.0
    net_investment_income: Optional[float] = 0.0

    k1_ordinary_income_taxable: Optional[float] = 0.0
    k1_qbi_eligible: Optional[float] = 0.0
    guaranteed_payments: Optional[float] = 0.0
    passive_loss_allowed: Optional[float] = 0.0
    passive_loss_suspended: Optional[float] = 0.0
    passive_loss_carryforward: Optional[float] = 0.0

    rental_net_income: Optional[float] = 0.0
    rental_depreciation_claimed: Optional[float] = 0.0
    rental_loss_allowed: Optional[float] = 0.0
    rental_pal_phase_out: Optional[float] = 0.0

    tax_bracket_detail: Optional[str] = None
    used_fallback: Optional[bool] = False
    tax_notices: Optional[List[str]] = []


class ChatResponse(BaseModel):
    """Response from intelligent chat."""
    session_id: str
    response: str
    response_type: str

    tax_calculation: Optional[TaxCalculationResult] = None
    strategies: Optional[List[StrategyRecommendation]] = []
    next_questions: Optional[List[Dict[str, Any]]] = []
    quick_actions: Optional[List[Dict[str, Any]]] = []

    profile_completeness: float = 0.0
    lead_score: int = 0
    complexity: str = "simple"

    urgency_level: str = "PLANNING"
    urgency_message: str = ""
    days_to_deadline: int = 365

    key_insights: Optional[List[str]] = []
    warnings: Optional[List[str]] = []
    total_potential_savings: float = 0.0

    disclaimer: Optional[str] = None
    requires_professional_review: bool = False

    response_confidence: str = "high"
    confidence_reason: Optional[str] = None


class FullAnalysisRequest(BaseModel):
    """Request for comprehensive tax analysis."""
    session_id: str
    profile: TaxProfileInput


class FullAnalysisResponse(BaseModel):
    """Complete tax analysis with all insights."""
    session_id: str

    current_tax: TaxCalculationResult
    strategies: List[StrategyRecommendation]
    total_potential_savings: float
    top_3_opportunities: List[StrategyRecommendation]

    entity_comparison: Optional[Dict[str, Any]] = None
    five_year_projection: Optional[Dict[str, Any]] = None

    executive_summary: str
    deduction_recommendation: str
    itemized_vs_standard: Dict[str, float]
    eligible_credits: List[Dict[str, Any]]

    confidence: str
    complexity: str

    urgency_level: str = "PLANNING"
    urgency_message: str = ""
    days_to_deadline: int = 365
    lead_score: int = 0

    report_ready: bool = True


class SessionReportRequest(BaseModel):
    """Request for session-based report."""
    session_id: str


class UniversalReportRequest(BaseModel):
    """Request for universal report generation."""
    session_id: str
    cpa_profile: Optional[Dict[str, Any]] = None
    output_format: str = "html"
    tier_level: int = 2
