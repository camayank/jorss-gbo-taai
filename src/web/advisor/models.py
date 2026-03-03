"""Pydantic request/response models for the Intelligent Advisor API.

Extracted from intelligent_advisor_api.py for maintainability.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

__all__ = [
    "FilingStatus",
    "ChatMessage",
    "TaxProfileInput",
    "ChatRequest",
    "StrategyRecommendation",
    "TaxCalculationResult",
    "ChatResponse",
    "FullAnalysisRequest",
    "FullAnalysisResponse",
]


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
    capital_gains_long: Optional[float] = None  # Long-term capital gains (>1 year, preferential rates)
    capital_gains_short: Optional[float] = None  # Short-term capital gains (<=1 year, ordinary rates)
    capital_gains: Optional[float] = None  # Alias for long-term (backward compatibility)
    dividend_income: Optional[float] = None  # Total dividend income
    qualified_dividends: Optional[float] = None  # Qualified dividends (preferential rates)
    interest_income: Optional[float] = None  # Interest income (taxable)

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
    health_insurance_premiums: Optional[float] = None  # SE health insurance deduction
    w2_wages_paid: Optional[float] = None  # W-2 wages paid to employees (for QBI limitation)

    # K-1 Income (Schedule E Part II/III)
    k1_ordinary_income: Optional[float] = None  # K-1 Box 1: Ordinary business income
    k1_rental_income: Optional[float] = None  # K-1 Box 2: Rental real estate income
    k1_interest_income: Optional[float] = None  # K-1 Box 5: Interest income
    k1_dividends: Optional[float] = None  # K-1 Box 6: Dividends
    k1_capital_gains: Optional[float] = None  # K-1 Box 8-10: Capital gains
    k1_section_179: Optional[float] = None  # K-1 Box 12: Section 179 deduction
    k1_guaranteed_payments: Optional[float] = None  # K-1 Box 4: Guaranteed payments
    k1_is_passive: Optional[bool] = True  # Is K-1 income passive (affects PAL rules)
    k1_w2_wages: Optional[float] = None  # W-2 wages for QBI limitation
    k1_ubia: Optional[float] = None  # UBIA of qualified property for QBI
    k1_is_sstb: Optional[bool] = False  # Is Specified Service Trade or Business

    # Enhanced Rental Property (Schedule E Part I)
    rental_gross_income: Optional[float] = None  # Total rental income (before expenses)
    rental_expenses: Optional[float] = None  # Total rental expenses
    rental_depreciation: Optional[float] = None  # Depreciation (line 18)
    rental_mortgage_interest: Optional[float] = None  # Mortgage interest on rental
    rental_property_taxes: Optional[float] = None  # Property taxes on rental
    rental_is_active_participant: Optional[bool] = True  # Active participation for $25k PAL allowance
    rental_is_real_estate_professional: Optional[bool] = False  # Real estate professional status

    # Education
    student_loan_interest: Optional[float] = None  # Up to $2,500 deduction

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
    # Tiered conversion fields
    tier: Optional[str] = "free"  # "free" or "premium"
    risk_level: Optional[str] = "low"  # "low", "medium", "high"
    implementation_complexity: Optional[str] = "simple"  # "simple", "moderate", "complex"


class TaxCalculationResult(BaseModel):
    """Comprehensive tax calculation result with full breakdown."""
    gross_income: float
    adjustments: float
    agi: float
    deductions: float
    deduction_type: str  # "standard" or "itemized"
    taxable_income: float
    federal_tax: float
    state_tax: float
    self_employment_tax: float
    total_tax: float
    effective_rate: float
    marginal_rate: float
    refund_or_owed: float
    is_refund: bool

    # Detailed breakdown (optional for enhanced display)
    amt_tax: Optional[float] = 0.0  # Alternative Minimum Tax
    niit_tax: Optional[float] = 0.0  # Net Investment Income Tax (3.8%)
    child_tax_credit: Optional[float] = 0.0  # Child Tax Credit applied
    qbi_deduction: Optional[float] = 0.0  # Section 199A QBI deduction (20% pass-through)
    itemized_breakdown: Optional[Dict[str, float]] = None  # medical, salt, mortgage, charitable

    # Capital gains breakdown
    short_term_gains: Optional[float] = 0.0  # Short-term capital gains (taxed as ordinary)
    long_term_gains: Optional[float] = 0.0  # Long-term capital gains (preferential rates)
    capital_gains_tax: Optional[float] = 0.0  # Tax on preferential income (0/15/20%)
    capital_loss_deduction: Optional[float] = 0.0  # Loss used against ordinary income (max $3k)
    net_investment_income: Optional[float] = 0.0  # NII used for NIIT calculation

    # K-1 and Pass-through breakdown
    k1_ordinary_income_taxable: Optional[float] = 0.0  # K-1 ordinary income in taxable income
    k1_qbi_eligible: Optional[float] = 0.0  # K-1 income eligible for 20% QBI deduction
    guaranteed_payments: Optional[float] = 0.0  # Guaranteed payments (subject to SE tax)
    passive_loss_allowed: Optional[float] = 0.0  # Passive loss allowed this year
    passive_loss_suspended: Optional[float] = 0.0  # Suspended passive loss (carryforward)
    passive_loss_carryforward: Optional[float] = 0.0  # Total suspended losses from prior years

    # Rental income breakdown
    rental_net_income: Optional[float] = 0.0  # Net rental income/loss (Schedule E)
    rental_depreciation_claimed: Optional[float] = 0.0  # Depreciation deduction taken
    rental_loss_allowed: Optional[float] = 0.0  # Allowed loss (PAL $25k special allowance)
    rental_pal_phase_out: Optional[float] = 0.0  # PAL allowance reduction (AGI > $100k)

    # Tax bracket info
    tax_bracket_detail: Optional[str] = None  # e.g., "22% bracket"

    # Calculation method
    used_fallback: Optional[bool] = False  # True if fallback calculator was used instead of main engine

    # Warnings/notices
    tax_notices: Optional[List[str]] = []  # e.g., "AMT applies", "SALT cap reached"


class ChatResponse(BaseModel):
    """Response from intelligent chat."""
    session_id: str
    response: str
    response_type: str  # "greeting", "question", "calculation", "strategy", "report"

    # Dynamic content
    tax_calculation: Optional[TaxCalculationResult] = None
    strategies: Optional[List[StrategyRecommendation]] = []
    next_questions: Optional[List[Dict[str, Any]]] = []
    quick_actions: Optional[List[Dict[str, Any]]] = []

    # Progress
    profile_completeness: float = 0.0
    lead_score: int = 0
    complexity: str = "simple"

    # Urgency (from CPAIntelligenceService)
    urgency_level: str = "PLANNING"  # CRITICAL, HIGH, MODERATE, PLANNING
    urgency_message: str = ""
    days_to_deadline: int = 365

    # Insights
    key_insights: Optional[List[str]] = []
    warnings: Optional[List[str]] = []
    total_potential_savings: float = 0.0

    # Liability disclaimers
    disclaimer: Optional[str] = None
    requires_professional_review: bool = False

    # Response confidence
    response_confidence: str = "high"  # high, medium, low
    confidence_reason: Optional[str] = None  # Why confidence is reduced

    # AI savings tracking
    detected_savings: float = 0.0  # Running total of AI-detected potential savings
    new_opportunities: Optional[List[Dict[str, Any]]] = []  # New opportunities found this turn

    # Tiered conversion fields
    premium_unlocked: bool = False
    safety_summary: Optional[Dict[str, Any]] = None
    safety_checks: Optional[Dict[str, Any]] = None  # Raw safety check results for frontend badges


class FullAnalysisRequest(BaseModel):
    """Request for comprehensive tax analysis."""
    session_id: str
    profile: TaxProfileInput


class FullAnalysisResponse(BaseModel):
    """Complete tax analysis with all insights."""
    session_id: str

    # Tax Position
    current_tax: TaxCalculationResult

    # Strategies (30+ recommendations)
    strategies: List[StrategyRecommendation]
    total_potential_savings: float

    # Top opportunities
    top_3_opportunities: List[StrategyRecommendation]

    # Entity analysis (if self-employed)
    entity_comparison: Optional[Dict[str, Any]] = None

    # Multi-year projection
    five_year_projection: Optional[Dict[str, Any]] = None

    # Executive summary
    executive_summary: str

    # Deduction analysis
    deduction_recommendation: str
    itemized_vs_standard: Dict[str, float]

    # Credit analysis
    eligible_credits: List[Dict[str, Any]]

    # Confidence and complexity
    confidence: str
    complexity: str

    # Urgency (from CPAIntelligenceService)
    urgency_level: str = "PLANNING"
    urgency_message: str = ""
    days_to_deadline: int = 365
    lead_score: int = 0

    # Report ready flag
    report_ready: bool = True
