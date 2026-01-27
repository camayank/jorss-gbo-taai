"""
Intelligent Advisor API - World-Class Tax Chatbot Backend

This API integrates ALL backend capabilities to create a truly intelligent
tax advisory chatbot experience:

- Real AI-powered responses
- 30+ tax optimization strategies
- Real-time tax calculations
- Document OCR and extraction
- Multi-year projections
- Entity structure analysis
- Professional report generation

NO ONE IN USA HAS DONE THIS.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import logging
import uuid
import json
import threading

logger = logging.getLogger(__name__)

# Import rate limiter and logo handler
try:
    from utils.rate_limiter import pdf_rate_limiter, global_pdf_limiter, RateLimitExceeded
    RATE_LIMITER_AVAILABLE = True
except ImportError:
    RATE_LIMITER_AVAILABLE = False
    logger.warning("Rate limiter not available")

try:
    from utils.logo_handler import LogoHandler, logo_handler
    LOGO_HANDLER_AVAILABLE = True
except ImportError:
    LOGO_HANDLER_AVAILABLE = False
    logger.warning("Logo handler not available")

try:
    from utils.cpa_branding_helper import (
        get_cpa_branding_for_report,
        create_pdf_brand_config,
        get_cpa_branding_for_html_report
    )
    CPA_BRANDING_HELPER_AVAILABLE = True
except ImportError:
    CPA_BRANDING_HELPER_AVAILABLE = False
    logger.warning("CPA branding helper not available")

# Import session persistence for database-backed storage
try:
    from database.session_persistence import get_session_persistence, SessionPersistence
    SESSION_PERSISTENCE_AVAILABLE = True
except ImportError:
    SESSION_PERSISTENCE_AVAILABLE = False
    logger.warning("Session persistence not available - using in-memory only")

# Import for PDF generation
try:
    from fastapi.responses import FileResponse
    from advisory.report_generator import AdvisoryReportGenerator, ReportType
    from models.tax_return import TaxReturn, TaxpayerInfo, Income, Deductions, TaxCredits
    from models.taxpayer import FilingStatus as TaxFilingStatus
    PDF_GENERATION_AVAILABLE = True
except ImportError as e:
    PDF_GENERATION_AVAILABLE = False
    logger.warning(f"PDF generation dependencies not available: {e}")

router = APIRouter(prefix="/api/advisor", tags=["Intelligent Advisor"])


# =============================================================================
# PROFILE TO TAX RETURN CONVERSION
# =============================================================================

def convert_profile_to_tax_return(profile: Dict[str, Any], session_id: str = None) -> Dict[str, Any]:
    """
    Convert intelligent advisor profile format to advisory API return_data format.

    Args:
        profile: Chatbot profile with flat structure
        session_id: Optional session ID for naming

    Returns:
        Dictionary in return_data format expected by advisory API
    """
    # Map filing status from chatbot format to tax return format
    # Uses enum names from models/taxpayer.py FilingStatus
    filing_status_map = {
        "single": "SINGLE",
        "married_joint": "MARRIED_JOINT",
        "married_separate": "MARRIED_SEPARATE",
        "head_of_household": "HEAD_OF_HOUSEHOLD",
        "qualifying_widow": "QUALIFYING_WIDOW"
    }

    filing_status = profile.get("filing_status", "single")
    tax_filing_status = filing_status_map.get(filing_status, "SINGLE")

    # Calculate income breakdown
    total_income = profile.get("total_income", 0) or 0
    w2_income = profile.get("w2_income", 0) or 0
    business_income = profile.get("business_income", 0) or 0
    investment_income = profile.get("investment_income", 0) or 0
    rental_income = profile.get("rental_income", 0) or 0

    # If only total_income provided, assume it's W-2
    if total_income > 0 and w2_income == 0 and business_income == 0:
        w2_income = total_income - investment_income - rental_income

    # Calculate deductions
    mortgage_interest = profile.get("mortgage_interest", 0) or 0
    property_taxes = profile.get("property_taxes", 0) or 0
    state_income_tax = profile.get("state_income_tax", 0) or 0
    charitable = profile.get("charitable_donations", 0) or 0

    # SALT cap at $10,000
    salt = min(property_taxes + state_income_tax, 10000)
    total_itemized = mortgage_interest + salt + charitable

    # Determine if itemizing makes sense
    standard_deductions = {
        "SINGLE": 15000,
        "MARRIED_FILING_JOINTLY": 30000,
        "HEAD_OF_HOUSEHOLD": 22500,
        "MARRIED_FILING_SEPARATELY": 15000,
        "QUALIFYING_WIDOW": 30000
    }
    standard_ded = standard_deductions.get(tax_filing_status, 15000)
    use_standard = total_itemized < standard_ded

    # Calculate credits
    dependents = profile.get("dependents", 0) or 0
    child_tax_credit = dependents * 2000  # $2000 per child

    # Estimate withholding (rough estimate: 20% of W-2)
    federal_withholding = profile.get("federal_withholding", 0) or (w2_income * 0.20)

    return {
        "taxpayer": {
            "first_name": profile.get("first_name", "Tax"),
            "last_name": profile.get("last_name", "Client"),
            "ssn": profile.get("ssn", "000-00-0000"),
            "filing_status": tax_filing_status,
            "state": profile.get("state", ""),
            "dependents": dependents
        },
        "income": {
            "w2_wages": float(w2_income),
            "federal_withholding": float(federal_withholding),
            "self_employment_income": float(business_income),
            "self_employment_expenses": float(profile.get("business_expenses", 0) or 0),
            "investment_income": float(investment_income),
            "capital_gains": float(profile.get("capital_gains_long", 0) or profile.get("capital_gains", 0) or 0),
            "rental_income": float(rental_income),
            "dividend_income": float(profile.get("dividend_income", 0) or 0),
            "interest_income": float(profile.get("interest_income", 0) or 0)
        },
        "deductions": {
            "use_standard_deduction": use_standard,
            "itemized_deductions": float(total_itemized),
            "state_local_taxes": float(salt),
            "mortgage_interest": float(mortgage_interest),
            "charitable_contributions": float(charitable),
            "medical_expenses": float(profile.get("medical_expenses", 0) or 0)
        },
        "credits": {
            "child_tax_credit": float(child_tax_credit),
            "education_credits": 0.0,
            "retirement_savers_credit": 0.0
        },
        "retirement": {
            "traditional_401k": float(profile.get("retirement_401k", 0) or 0),
            "traditional_ira": float(profile.get("retirement_ira", 0) or 0),
            "hsa_contributions": float(profile.get("hsa_contributions", 0) or 0)
        }
    }


def build_tax_return_from_profile(profile: Dict[str, Any]) -> "TaxReturn":
    """
    Build a TaxReturn object from chatbot profile for PDF generation.

    Args:
        profile: Chatbot profile dictionary

    Returns:
        TaxReturn object ready for report generation
    """
    if not PDF_GENERATION_AVAILABLE:
        raise ImportError("PDF generation dependencies not available")

    return_data = convert_profile_to_tax_return(profile)

    # Map filing status - uses enum names from models/taxpayer.py
    filing_status_map = {
        "SINGLE": TaxFilingStatus.SINGLE,
        "MARRIED_JOINT": TaxFilingStatus.MARRIED_JOINT,
        "MARRIED_SEPARATE": TaxFilingStatus.MARRIED_SEPARATE,
        "HEAD_OF_HOUSEHOLD": TaxFilingStatus.HEAD_OF_HOUSEHOLD,
        "QUALIFYING_WIDOW": TaxFilingStatus.QUALIFYING_WIDOW
    }

    taxpayer_data = return_data["taxpayer"]
    income_data = return_data["income"]
    deductions_data = return_data["deductions"]
    credits_data = return_data["credits"]

    filing_status = filing_status_map.get(
        taxpayer_data["filing_status"],
        TaxFilingStatus.SINGLE
    )

    taxpayer = TaxpayerInfo(
        first_name=taxpayer_data.get("first_name", "Tax"),
        last_name=taxpayer_data.get("last_name", "Client"),
        ssn=taxpayer_data.get("ssn", "000-00-0000"),
        filing_status=filing_status,
    )

    income = Income(
        w2_wages=income_data.get("w2_wages", 0),
        federal_withholding=income_data.get("federal_withholding", 0),
        self_employment_income=income_data.get("self_employment_income", 0),
        self_employment_expenses=income_data.get("self_employment_expenses", 0),
        investment_income=income_data.get("investment_income", 0),
        capital_gains=income_data.get("capital_gains", 0),
        rental_income=income_data.get("rental_income", 0),
    )

    deductions = Deductions(
        use_standard_deduction=deductions_data.get("use_standard_deduction", True),
        itemized_deductions=deductions_data.get("itemized_deductions", 0),
        state_local_taxes=deductions_data.get("state_local_taxes", 0),
        mortgage_interest=deductions_data.get("mortgage_interest", 0),
        charitable_contributions=deductions_data.get("charitable_contributions", 0),
    )

    credits = TaxCredits(
        child_tax_credit=credits_data.get("child_tax_credit", 0),
    )

    return TaxReturn(
        tax_year=2025,
        taxpayer=taxpayer,
        income=income,
        deductions=deductions,
        credits=credits,
    )


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

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


# =============================================================================
# INTELLIGENT CHAT ENGINE
# =============================================================================

class IntelligentChatEngine:
    """
    The brain of the chatbot - orchestrates all backend services.

    Now with database-backed persistence! Sessions are:
    1. Cached in memory for fast access
    2. Persisted to SQLite database for durability
    3. Automatically loaded from database if not in memory
    """

    def __init__(self):
        # In-memory cache for fast access
        self.sessions: Dict[str, Dict[str, Any]] = {}
        # Lock for thread-safe operations
        self._lock = threading.Lock()
        # Database persistence layer
        self._persistence: Optional[SessionPersistence] = None
        if SESSION_PERSISTENCE_AVAILABLE:
            try:
                self._persistence = get_session_persistence()
                logger.info("Intelligent Advisor: Database persistence enabled")
            except Exception as e:
                logger.warning(f"Could not initialize persistence: {e}")

    def _serialize_session_for_db(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize session data for database storage."""
        # Create a copy to avoid modifying the original
        data = {}
        for key, value in session.items():
            if key == "calculations" and value is not None:
                # Convert TaxCalculationResult to dict
                data[key] = value.dict() if hasattr(value, 'dict') else value
            elif key == "strategies" and value:
                # Convert StrategyRecommendation list to dicts
                data[key] = [s.dict() if hasattr(s, 'dict') else s for s in value]
            elif key == "created_at" and isinstance(value, datetime):
                data[key] = value.isoformat()
            else:
                data[key] = value
        return data

    def _deserialize_session_from_db(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize session data from database storage."""
        session = dict(data)
        # Convert datetime string back to datetime
        if "created_at" in session and isinstance(session["created_at"], str):
            try:
                session["created_at"] = datetime.fromisoformat(session["created_at"])
            except (ValueError, TypeError):
                session["created_at"] = datetime.now()
        return session

    def _save_session_to_db(self, session_id: str, session: Dict[str, Any]) -> None:
        """Save session to database asynchronously."""
        if not self._persistence:
            return

        try:
            serialized = self._serialize_session_for_db(session)
            self._persistence.save_session(
                session_id=session_id,
                tenant_id="default",
                session_type="intelligent_advisor",
                data=serialized,
                metadata={
                    "lead_score": session.get("lead_score", 0),
                    "state": session.get("state", "greeting"),
                    "has_calculation": session.get("calculations") is not None
                }
            )
            logger.debug(f"Session {session_id} saved to database")
        except Exception as e:
            logger.warning(f"Failed to save session {session_id} to database: {e}")

    def _load_session_from_db(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session from database."""
        if not self._persistence:
            return None

        try:
            record = self._persistence.load_session(session_id)
            if record and record.data:
                session = self._deserialize_session_from_db(record.data)
                logger.info(f"Session {session_id} loaded from database")
                return session
        except Exception as e:
            logger.warning(f"Failed to load session {session_id} from database: {e}")

        return None

    def get_or_create_session(self, session_id: str) -> Dict[str, Any]:
        """
        Get existing session or create new one.

        1. Check in-memory cache first (fast path)
        2. Try loading from database if not in memory
        3. Create new session if not found anywhere
        4. Save new sessions to database
        """
        with self._lock:
            # Fast path: check in-memory cache
            if session_id in self.sessions:
                # Touch the session in DB to extend expiry
                if self._persistence:
                    try:
                        self._persistence.touch_session(session_id)
                    except Exception:
                        pass
                return self.sessions[session_id]

            # Try loading from database
            loaded_session = self._load_session_from_db(session_id)
            if loaded_session:
                self.sessions[session_id] = loaded_session
                return loaded_session

            # Create new session
            new_session = {
                "id": session_id,
                "created_at": datetime.now(),
                "profile": {},
                "conversation": [],
                "state": "greeting",
                "calculations": None,
                "strategies": [],
                "lead_score": 0
            }
            self.sessions[session_id] = new_session

            # Save to database
            self._save_session_to_db(session_id, new_session)

            return new_session

    def update_session(self, session_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update session with new data and persist to database.

        Also saves tax return data in the format expected by the advisory API
        for PDF generation support.

        Args:
            session_id: Session identifier
            updates: Dictionary of updates to apply

        Returns:
            Updated session
        """
        session = self.get_or_create_session(session_id)

        with self._lock:
            # Apply updates
            for key, value in updates.items():
                if key == "profile" and isinstance(value, dict):
                    # Merge profile updates
                    session["profile"].update(value)
                else:
                    session[key] = value

            # Save to database
            self._save_session_to_db(session_id, session)

            # Also save tax return data for PDF generation compatibility
            profile = session.get("profile", {})
            if profile.get("filing_status") and profile.get("total_income"):
                self._save_tax_return_for_advisory(session_id, profile)

        return session

    def _save_tax_return_for_advisory(self, session_id: str, profile: Dict[str, Any]) -> None:
        """
        Save tax return data in the format expected by the advisory API.

        This enables PDF generation from chatbot sessions.

        Args:
            session_id: Session identifier
            profile: Chatbot profile data
        """
        if not self._persistence:
            return

        try:
            # Convert profile to tax return format
            return_data = convert_profile_to_tax_return(profile, session_id)

            # Save to session_tax_returns table
            self._persistence.save_session_tax_return(
                session_id=session_id,
                tenant_id="default",
                tax_year=2025,
                return_data=return_data,
                calculated_results=None  # Will be calculated when report is generated
            )
            logger.debug(f"Tax return data saved for session {session_id} (PDF generation enabled)")
        except Exception as e:
            logger.warning(f"Failed to save tax return data for {session_id}: {e}")

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session from both memory and database.

        Args:
            session_id: Session identifier

        Returns:
            True if session was deleted
        """
        with self._lock:
            # Remove from memory
            removed = self.sessions.pop(session_id, None) is not None

            # Remove from database
            if self._persistence:
                try:
                    self._persistence.delete_session(session_id)
                except Exception as e:
                    logger.warning(f"Failed to delete session {session_id} from database: {e}")

            return removed

    def get_session_count(self) -> Dict[str, int]:
        """Get count of sessions in memory and database."""
        memory_count = len(self.sessions)
        db_count = 0

        if self._persistence:
            try:
                # Count sessions by listing them
                sessions = self._persistence.list_sessions("default")
                db_count = len([s for s in sessions if s.session_type == "intelligent_advisor"])
            except Exception:
                pass

        return {
            "in_memory": memory_count,
            "in_database": db_count
        }

    def calculate_profile_completeness(self, profile: Dict[str, Any]) -> float:
        """Calculate how complete the user's profile is."""
        required_fields = [
            "filing_status", "total_income", "dependents", "state"
        ]
        optional_fields = [
            "w2_income", "business_income", "mortgage_interest",
            "charitable_donations", "retirement_401k"
        ]

        required_count = sum(1 for f in required_fields if profile.get(f))
        optional_count = sum(1 for f in optional_fields if profile.get(f))

        required_weight = 0.6
        optional_weight = 0.4

        required_score = (required_count / len(required_fields)) * required_weight
        optional_score = (optional_count / len(optional_fields)) * optional_weight

        return min(1.0, required_score + optional_score)

    def calculate_lead_score(self, profile: Dict[str, Any]) -> int:
        """Calculate lead quality score for CPA handoff."""
        score = 0

        # Base score for engagement
        score += 20

        # Income indicates potential value
        income = profile.get("total_income", 0) or 0
        if income > 200000:
            score += 30
        elif income > 100000:
            score += 20
        elif income > 50000:
            score += 10

        # Complexity indicates need for CPA
        if profile.get("business_income"):
            score += 15
        if profile.get("rental_income"):
            score += 10
        if profile.get("investment_income"):
            score += 10
        if profile.get("is_self_employed"):
            score += 15

        # Contact info
        # (would add if email/phone collected)

        return min(100, score)

    def determine_complexity(self, profile: Dict[str, Any]) -> str:
        """Determine tax situation complexity."""
        if profile.get("business_income") or profile.get("rental_income"):
            if profile.get("is_self_employed") and (profile.get("total_income", 0) or 0) > 100000:
                return "professional"
            return "complex"
        if profile.get("investment_income"):
            return "moderate"
        return "simple"

    async def get_tax_calculation(self, profile: Dict[str, Any]) -> TaxCalculationResult:
        """
        Get comprehensive tax calculation using validated, cached pipeline.

        Uses the centralized calculation_helper which provides:
        - 11 validation rules (IRS limits, format checks, consistency)
        - Calculation caching for repeat requests
        - Graceful fallback if pipeline unavailable
        """
        try:
            from web.calculation_helper import calculate_taxes

            # Use centralized calculation with validation and caching
            session_id = profile.get("session_id")
            result = await calculate_taxes(
                tax_data=profile,
                session_id=session_id,
                use_cache=True,
                validate=True,  # Enable validation
                is_profile_format=True
            )

            if result.success and result.breakdown:
                breakdown = result.breakdown
                income = profile.get("total_income", 0) or profile.get("w2_income", 0) or 0

                # Log cache hit for monitoring
                if result.cache_hit:
                    logger.info(f"Tax calculation cache HIT for session {session_id}")

                # Log validation warnings
                for warning in result.warnings:
                    logger.info(f"Validation warning: {warning}")

                return TaxCalculationResult(
                    gross_income=income,
                    adjustments=breakdown.get("above_the_line_deductions", breakdown.get("adjustments_to_income", 0)),
                    agi=breakdown.get("adjusted_gross_income", breakdown.get("agi", income)),
                    deductions=breakdown.get("total_deductions", breakdown.get("deduction_amount", 15000)),
                    deduction_type=breakdown.get("deduction_type", "standard"),
                    taxable_income=breakdown.get("taxable_income", max(0, income - 15000)),
                    federal_tax=breakdown.get("total_federal_tax", breakdown.get("federal_tax", 0)),
                    state_tax=breakdown.get("total_state_tax", breakdown.get("state_tax", 0)),
                    self_employment_tax=breakdown.get("self_employment_tax", breakdown.get("se_tax", 0)),
                    total_tax=breakdown.get("total_tax", 0),
                    effective_rate=breakdown.get("effective_tax_rate", breakdown.get("effective_rate", 0)),
                    marginal_rate=breakdown.get("marginal_bracket", breakdown.get("marginal_tax_rate", 22)),
                    refund_or_owed=breakdown.get("refund_or_owed", 0),
                    is_refund=breakdown.get("refund_or_owed", 0) > 0,
                    # Capital gains breakdown
                    short_term_gains=breakdown.get("net_short_term_gain_loss", 0),
                    long_term_gains=breakdown.get("net_long_term_gain_loss", 0),
                    capital_gains_tax=breakdown.get("preferential_income_tax", 0),
                    capital_loss_deduction=breakdown.get("capital_loss_deduction", 0),
                    net_investment_income=breakdown.get("net_investment_income", 0),
                    niit_tax=breakdown.get("net_investment_income_tax", 0),
                    amt_tax=breakdown.get("alternative_minimum_tax", 0),
                    qbi_deduction=breakdown.get("qbi_deduction", 0),
                    # K-1 and pass-through breakdown
                    k1_ordinary_income_taxable=breakdown.get("k1_ordinary_income", 0),
                    k1_qbi_eligible=breakdown.get("schedule_e_qbi", 0),
                    guaranteed_payments=breakdown.get("guaranteed_payments", 0),
                    passive_loss_allowed=breakdown.get("form_8582_passive_loss_allowed", 0),
                    passive_loss_suspended=breakdown.get("form_8582_suspended_loss", 0),
                    # Rental breakdown
                    rental_net_income=breakdown.get("schedule_e_rental_income", 0),
                    rental_depreciation_claimed=breakdown.get("rental_depreciation", 0),
                    rental_loss_allowed=breakdown.get("form_8582_rental_allowance", 0),
                )
            else:
                # Pipeline failed or returned errors, use fallback
                logger.warning(f"Pipeline calculation failed: {result.errors}")
                return self._fallback_calculation(profile)

        except ImportError as e:
            logger.warning(f"calculation_helper not available: {e}")
            return self._fallback_calculation(profile)
        except Exception as e:
            logger.warning(f"Using fallback calculation: {e}")
            return self._fallback_calculation(profile)

    # =========================================================================
    # 2025 TAX CONSTANTS (IRS Rev. Proc. 2024-40)
    # =========================================================================

    # Standard Deductions 2025
    STANDARD_DEDUCTIONS_2025 = {
        "single": 15000,
        "married_joint": 30000,
        "head_of_household": 22500,
        "married_separate": 15000,
        "qualifying_widow": 30000
    }

    # Additional standard deduction for 65+ or blind
    ADDITIONAL_STD_DEDUCTION_2025 = {
        "single": 2000,
        "head_of_household": 2000,
        "married_joint": 1600,
        "married_separate": 1600,
        "qualifying_widow": 1600
    }

    # 2025 Federal Tax Brackets by filing status
    TAX_BRACKETS_2025 = {
        "single": [
            (11925, 0.10),
            (48475, 0.12),
            (103350, 0.22),
            (197300, 0.24),
            (250500, 0.32),
            (626350, 0.35),
            (float('inf'), 0.37)
        ],
        "married_joint": [
            (23850, 0.10),
            (96950, 0.12),
            (206700, 0.22),
            (394600, 0.24),
            (501050, 0.32),
            (751600, 0.35),
            (float('inf'), 0.37)
        ],
        "married_separate": [
            (11925, 0.10),
            (48475, 0.12),
            (103350, 0.22),
            (197300, 0.24),
            (250525, 0.32),
            (375800, 0.35),
            (float('inf'), 0.37)
        ],
        "head_of_household": [
            (17000, 0.10),
            (64850, 0.12),
            (103350, 0.22),
            (197300, 0.24),
            (250500, 0.32),
            (626350, 0.35),
            (float('inf'), 0.37)
        ],
        "qualifying_widow": [  # Same as MFJ
            (23850, 0.10),
            (96950, 0.12),
            (206700, 0.22),
            (394600, 0.24),
            (501050, 0.32),
            (751600, 0.35),
            (float('inf'), 0.37)
        ]
    }

    # NIIT (Net Investment Income Tax) thresholds - IRC §1411
    NIIT_THRESHOLDS = {
        "single": 200000,
        "married_joint": 250000,
        "married_separate": 125000,
        "head_of_household": 200000,
        "qualifying_widow": 250000
    }

    # AMT Exemptions 2025
    AMT_EXEMPTIONS_2025 = {
        "single": 88100,
        "married_joint": 137000,
        "married_separate": 68500,
        "head_of_household": 88100,
        "qualifying_widow": 137000
    }

    # AMT Phase-out thresholds 2025
    AMT_PHASEOUT_2025 = {
        "single": 626350,
        "married_joint": 1252700,
        "married_separate": 626350,
        "head_of_household": 626350,
        "qualifying_widow": 1252700
    }

    # Child Tax Credit 2025
    CTC_AMOUNT = 2000  # Per qualifying child
    CTC_REFUNDABLE_MAX = 1700  # ACTC refundable portion
    CTC_PHASEOUT_START = {
        "single": 200000,
        "married_joint": 400000,
        "married_separate": 200000,
        "head_of_household": 200000,
        "qualifying_widow": 400000
    }

    # SALT Cap (State and Local Tax deduction limit) - IRC §164(b)(6)
    SALT_CAP = 10000  # $10,000 limit through 2025

    # QBI Deduction Thresholds 2025 (Section 199A) - IRC §199A
    # 20% deduction on qualified business income for pass-through entities
    QBI_DEDUCTION_RATE = 0.20
    QBI_TAXABLE_INCOME_THRESHOLD = {
        "single": 191950,
        "married_joint": 383900,
        "married_separate": 191950,
        "head_of_household": 191950,
        "qualifying_widow": 383900
    }
    QBI_PHASEOUT_RANGE = {
        "single": 50000,  # Phase-out over $50K
        "married_joint": 100000,  # Phase-out over $100K
        "married_separate": 50000,
        "head_of_household": 50000,
        "qualifying_widow": 100000
    }

    # State Tax Brackets 2025 (Progressive rates for major states)
    STATE_TAX_BRACKETS = {
        "CA": [  # California - highest state income tax
            (10412, 0.01), (24684, 0.02), (38959, 0.04), (54081, 0.06),
            (68350, 0.08), (349137, 0.093), (418961, 0.103), (698271, 0.113),
            (float('inf'), 0.133)
        ],
        "NY": [  # New York
            (8500, 0.04), (11700, 0.045), (13900, 0.0525), (80650, 0.055),
            (215400, 0.06), (1077550, 0.0685), (5000000, 0.0965),
            (25000000, 0.103), (float('inf'), 0.109)
        ],
        "NJ": [  # New Jersey
            (20000, 0.014), (35000, 0.0175), (40000, 0.035), (75000, 0.05525),
            (500000, 0.0637), (1000000, 0.0897), (float('inf'), 0.1075)
        ],
        "IL": [(float('inf'), 0.0495)],  # Flat rate
        "PA": [(float('inf'), 0.0307)],  # Flat rate
        "OH": [  # Ohio
            (26050, 0.00), (100000, 0.02765), (float('inf'), 0.0375)
        ],
        "GA": [  # Georgia
            (750, 0.01), (2250, 0.02), (3750, 0.03), (5250, 0.04),
            (7000, 0.05), (float('inf'), 0.055)
        ],
        "NC": [(float('inf'), 0.0475)],  # Flat rate
        "MI": [(float('inf'), 0.0425)],  # Flat rate
        "MA": [(float('inf'), 0.05)],  # Flat rate (plus 4% surtax on income >$1M)
        "AZ": [  # Arizona
            (28653, 0.0259), (57305, 0.0334), (171913, 0.0417),
            (float('inf'), 0.045)
        ],
        "CO": [(float('inf'), 0.044)],  # Flat rate
        "VA": [  # Virginia
            (3000, 0.02), (5000, 0.03), (17000, 0.05), (float('inf'), 0.0575)
        ],
        "MN": [  # Minnesota
            (31690, 0.0535), (104090, 0.068), (183340, 0.0785),
            (float('inf'), 0.0985)
        ],
        "OR": [  # Oregon
            (4050, 0.0475), (10200, 0.0675), (125000, 0.0875),
            (float('inf'), 0.099)
        ],
        "CT": [  # Connecticut
            (10000, 0.02), (50000, 0.045), (100000, 0.055), (200000, 0.06),
            (250000, 0.065), (500000, 0.069), (float('inf'), 0.0699)
        ],
        # No income tax states
        "TX": [], "FL": [], "WA": [], "NV": [], "WY": [], "SD": [], "AK": [],
        "TN": [], "NH": []  # NH only taxes interest/dividends
    }

    def _calculate_federal_tax(self, taxable_income: float, filing_status: str) -> tuple:
        """Calculate federal income tax using progressive brackets."""
        brackets = self.TAX_BRACKETS_2025.get(filing_status, self.TAX_BRACKETS_2025["single"])

        tax = 0.0
        marginal_rate = 10
        prev_limit = 0

        for limit, rate in brackets:
            if taxable_income <= 0:
                break
            bracket_income = min(taxable_income, limit - prev_limit)
            tax += bracket_income * rate
            taxable_income -= bracket_income
            if taxable_income > 0:
                marginal_rate = int(rate * 100)
            prev_limit = limit

        return tax, marginal_rate

    def _calculate_state_tax(self, income: float, state: str, filing_status: str) -> float:
        """Calculate state income tax using actual state brackets."""
        if not state or state.upper() not in self.STATE_TAX_BRACKETS:
            # Default to 5% for unknown states
            return income * 0.05

        state = state.upper()
        brackets = self.STATE_TAX_BRACKETS.get(state, [])

        if not brackets:  # No income tax state
            return 0.0

        # Adjust for married filing jointly (most states double brackets)
        multiplier = 2.0 if filing_status in ["married_joint", "qualifying_widow"] else 1.0

        tax = 0.0
        prev_limit = 0
        remaining_income = income

        for limit, rate in brackets:
            if remaining_income <= 0:
                break
            adjusted_limit = limit * multiplier if limit != float('inf') else float('inf')
            bracket_income = min(remaining_income, adjusted_limit - prev_limit)
            tax += bracket_income * rate
            remaining_income -= bracket_income
            prev_limit = adjusted_limit

        return tax

    def _calculate_niit(self, profile: Dict[str, Any], agi: float) -> float:
        """Calculate Net Investment Income Tax (3.8%) - IRC §1411."""
        filing_status = profile.get("filing_status", "single")
        threshold = self.NIIT_THRESHOLDS.get(filing_status, 200000)

        # Net investment income includes interest, dividends, capital gains, rental
        investment_income = (
            (profile.get("investment_income", 0) or 0) +
            (profile.get("rental_income", 0) or 0)
        )

        if agi <= threshold or investment_income <= 0:
            return 0.0

        # NIIT is 3.8% on the lesser of:
        # 1. Net investment income, or
        # 2. AGI over the threshold
        excess_agi = agi - threshold
        niit_base = min(investment_income, excess_agi)

        return niit_base * 0.038

    def _calculate_amt(self, profile: Dict[str, Any], regular_tax: float, agi: float) -> float:
        """Calculate Alternative Minimum Tax - IRC §55."""
        filing_status = profile.get("filing_status", "single")

        # AMT exemption
        exemption = self.AMT_EXEMPTIONS_2025.get(filing_status, 88100)
        phaseout_start = self.AMT_PHASEOUT_2025.get(filing_status, 626350)

        # AMT income starts with AGI and adds back certain deductions
        # Simplified: Add back SALT deduction and misc itemized
        salt_addback = min(
            (profile.get("property_taxes", 0) or 0) +
            (profile.get("state_income_tax", 0) or 0),
            self.SALT_CAP
        )

        amti = agi + salt_addback

        # Phase out exemption (25 cents per dollar over threshold)
        if amti > phaseout_start:
            exemption_reduction = (amti - phaseout_start) * 0.25
            exemption = max(0, exemption - exemption_reduction)

        amt_taxable = max(0, amti - exemption)

        if amt_taxable <= 0:
            return 0.0

        # AMT rates: 26% up to $232,600 (MFS $116,300), 28% above
        amt_bracket = 232600 if filing_status != "married_separate" else 116300

        if amt_taxable <= amt_bracket:
            amt = amt_taxable * 0.26
        else:
            amt = amt_bracket * 0.26 + (amt_taxable - amt_bracket) * 0.28

        # AMT only applies if it exceeds regular tax
        return max(0, amt - regular_tax)

    def _calculate_child_tax_credit(self, profile: Dict[str, Any], agi: float) -> float:
        """Calculate Child Tax Credit with phase-out - IRC §24."""
        dependents = profile.get("dependents", 0) or 0
        if dependents <= 0:
            return 0.0

        filing_status = profile.get("filing_status", "single")
        phaseout_start = self.CTC_PHASEOUT_START.get(filing_status, 200000)

        # Full credit amount
        full_credit = dependents * self.CTC_AMOUNT

        # Phase-out: $50 reduction per $1,000 (or fraction) over threshold
        if agi > phaseout_start:
            excess = agi - phaseout_start
            reduction = (int(excess / 1000) + (1 if excess % 1000 > 0 else 0)) * 50
            full_credit = max(0, full_credit - reduction)

        return full_credit

    def _calculate_qbi_deduction(self, profile: Dict[str, Any], taxable_income: float) -> float:
        """
        Calculate Qualified Business Income (QBI) deduction - IRC §199A.

        The QBI deduction is 20% of qualified business income from pass-through
        entities (sole proprietors, partnerships, S-corps).

        Limitations apply based on taxable income:
        - Below threshold: Full 20% deduction
        - In phase-out range: W-2 wage limitation and UBIA limitation apply
        - Above phase-out: Stricter limitations
        """
        business_income = profile.get("business_income", 0) or 0
        if business_income <= 0:
            return 0.0

        filing_status = profile.get("filing_status", "single")
        threshold = self.QBI_TAXABLE_INCOME_THRESHOLD.get(filing_status, 191950)
        phaseout_range = self.QBI_PHASEOUT_RANGE.get(filing_status, 50000)

        # QBI is generally net business income (simplified - using gross here)
        # In reality, QBI excludes reasonable compensation, capital gains, etc.
        qbi = business_income

        # Calculate tentative QBI deduction (20%)
        tentative_deduction = qbi * self.QBI_DEDUCTION_RATE

        # If taxable income is below threshold, get full deduction
        if taxable_income <= threshold:
            # Also limited to 20% of taxable income (minus capital gains)
            return min(tentative_deduction, taxable_income * 0.20)

        # If in phase-out range, apply partial limitation
        if taxable_income < threshold + phaseout_range:
            # Phase-out percentage
            excess = taxable_income - threshold
            phaseout_pct = excess / phaseout_range

            # For simplicity, reduce deduction proportionally
            # (Full calculation would involve W-2 wages and UBIA)
            reduced_deduction = tentative_deduction * (1 - phaseout_pct * 0.5)
            return min(reduced_deduction, taxable_income * 0.20)

        # Above phase-out: Apply stricter W-2 wage limitation
        # Simplified: Greater of 50% of W-2 wages OR 25% of W-2 wages + 2.5% of UBIA
        # For sole proprietors with no employees, this often means $0
        # We'll use a simplified 50% reduction for high earners
        w2_wages_paid = profile.get("w2_wages_paid", 0) or 0
        if w2_wages_paid > 0:
            wage_limitation = w2_wages_paid * 0.50
            return min(tentative_deduction, wage_limitation, taxable_income * 0.20)

        # High-income sole proprietor with no W-2 wages paid to employees
        # QBI deduction phases out completely
        return 0.0

    def _calculate_itemized_deductions(self, profile: Dict[str, Any], agi: float) -> tuple:
        """Calculate itemized deductions with SALT cap and AGI floors."""
        # Medical expenses (only amount exceeding 7.5% of AGI)
        medical = profile.get("medical_expenses", 0) or 0
        medical_floor = agi * 0.075
        medical_deduction = max(0, medical - medical_floor)

        # SALT (capped at $10,000)
        salt = min(
            (profile.get("property_taxes", 0) or 0) +
            (profile.get("state_income_tax", 0) or 0),
            self.SALT_CAP
        )

        # Mortgage interest (limited to $750K acquisition debt)
        mortgage_interest = profile.get("mortgage_interest", 0) or 0

        # Charitable contributions (limited to 60% of AGI for cash)
        charitable = profile.get("charitable_donations", 0) or 0
        charitable_limit = agi * 0.60
        charitable_deduction = min(charitable, charitable_limit)

        total_itemized = (
            medical_deduction +
            salt +
            mortgage_interest +
            charitable_deduction
        )

        return total_itemized, {
            "medical": medical_deduction,
            "salt": salt,
            "mortgage_interest": mortgage_interest,
            "charitable": charitable_deduction
        }

    def _fallback_calculation(self, profile: Dict[str, Any]) -> TaxCalculationResult:
        """
        Comprehensive tax calculation with:
        - Progressive federal brackets by filing status
        - Progressive state tax brackets for major states
        - SALT $10K cap on itemized deductions
        - NIIT (3.8% Net Investment Income Tax)
        - AMT (Alternative Minimum Tax)
        - Child Tax Credit with phase-out
        - Proper itemized vs standard deduction comparison
        """
        income = profile.get("total_income", 0) or 0
        filing_status = profile.get("filing_status", "single")
        state = profile.get("state", "").upper()

        # Calculate AGI (income minus above-the-line deductions)
        adjustments = 0.0

        # SE tax deduction (1/2 of SE tax) - IRC §164(f)
        se_income = (profile.get("business_income", 0) or 0) * 0.9235
        se_tax = se_income * 0.153 if se_income > 0 else 0
        se_deduction = se_tax * 0.5
        adjustments += se_deduction

        # SE Health Insurance Deduction - IRC §162(l)
        # Self-employed can deduct 100% of health insurance premiums
        if profile.get("is_self_employed") and profile.get("business_income", 0) > 0:
            se_health_insurance = profile.get("health_insurance_premiums", 0) or 0
            # Limited to net SE income (after SE tax deduction)
            net_se_income = profile.get("business_income", 0) - se_deduction
            se_health_deduction = min(se_health_insurance, max(0, net_se_income))
            adjustments += se_health_deduction

        # HSA contributions
        adjustments += profile.get("hsa_contributions", 0) or 0

        # Traditional IRA (simplified - assume deductible)
        adjustments += profile.get("retirement_ira", 0) or 0

        # Student loan interest deduction (up to $2,500)
        student_loan_interest = profile.get("student_loan_interest", 0) or 0
        adjustments += min(student_loan_interest, 2500)

        agi = income - adjustments

        # Calculate deductions (standard vs itemized)
        standard_deduction = self.STANDARD_DEDUCTIONS_2025.get(filing_status, 15000)

        # Add additional deduction for 65+ (simplified - check age)
        age = profile.get("age", 0) or 0
        if age >= 65:
            standard_deduction += self.ADDITIONAL_STD_DEDUCTION_2025.get(filing_status, 1600)

        # Calculate itemized deductions
        itemized_total, itemized_breakdown = self._calculate_itemized_deductions(profile, agi)

        # Use the larger deduction
        if itemized_total > standard_deduction:
            deduction = itemized_total
            deduction_type = "itemized"
        else:
            deduction = standard_deduction
            deduction_type = "standard"

        taxable_income_before_qbi = max(0, agi - deduction)

        # Calculate QBI deduction (Section 199A) for business income
        qbi_deduction = self._calculate_qbi_deduction(profile, taxable_income_before_qbi)
        taxable_income = max(0, taxable_income_before_qbi - qbi_deduction)

        # Calculate federal income tax
        federal_tax, marginal_rate = self._calculate_federal_tax(taxable_income, filing_status)

        # Calculate Child Tax Credit
        ctc = self._calculate_child_tax_credit(profile, agi)
        federal_tax = max(0, federal_tax - ctc)

        # Calculate AMT
        amt = self._calculate_amt(profile, federal_tax, agi)
        federal_tax += amt

        # Calculate NIIT
        niit = self._calculate_niit(profile, agi)
        federal_tax += niit

        # Calculate state tax using progressive brackets
        state_tax = self._calculate_state_tax(agi, state, filing_status)

        # Total tax
        total_tax = federal_tax + se_tax + state_tax
        effective_rate = (total_tax / income * 100) if income > 0 else 0

        # Calculate withholding/payments vs tax owed
        withholding = profile.get("federal_withholding", 0) or 0
        estimated_payments = profile.get("estimated_payments", 0) or 0
        total_payments = withholding + estimated_payments
        refund_or_owed = total_payments - federal_tax

        # Build tax notices for transparency
        tax_notices = []
        if qbi_deduction > 0:
            tax_notices.append(f"QBI deduction (§199A): ${qbi_deduction:,.0f} saved")
        if amt > 0:
            tax_notices.append(f"AMT applies: ${amt:,.0f} additional tax")
        if niit > 0:
            tax_notices.append(f"NIIT (3.8%) applies: ${niit:,.0f} on investment income")
        if deduction_type == "itemized" and itemized_breakdown.get("salt", 0) >= self.SALT_CAP:
            tax_notices.append(f"SALT deduction capped at ${self.SALT_CAP:,}")
        if ctc > 0:
            tax_notices.append(f"Child Tax Credit applied: ${ctc:,.0f}")

        # Calculate capital gains info
        short_term_gains = profile.get("capital_gains_short", 0) or 0
        long_term_gains = profile.get("capital_gains_long", 0) or profile.get("capital_gains", 0) or 0
        # Preferential rate on LTCG (simplified 15% rate)
        capital_gains_tax = long_term_gains * 0.15 if long_term_gains > 0 else 0
        # Net investment income for NIIT
        net_investment_income = (
            (profile.get("interest_income", 0) or 0) +
            (profile.get("dividend_income", 0) or 0) +
            short_term_gains + long_term_gains +
            (profile.get("rental_income", 0) or 0)
        )

        # Calculate K-1 and rental info for fallback
        k1_ordinary = (profile.get("k1_ordinary_income", 0) or 0)
        k1_qbi = k1_ordinary if not profile.get("k1_is_sstb", False) else 0
        rental_net = (profile.get("rental_gross_income", 0) or 0) - (profile.get("rental_expenses", 0) or 0)
        if rental_net == 0:
            rental_net = profile.get("rental_income", 0) or 0

        return TaxCalculationResult(
            gross_income=round(income, 2),
            adjustments=round(adjustments, 2),
            agi=round(agi, 2),
            deductions=round(deduction, 2),
            deduction_type=deduction_type,
            taxable_income=round(taxable_income, 2),
            federal_tax=round(federal_tax, 2),
            state_tax=round(state_tax, 2),
            self_employment_tax=round(se_tax, 2),
            total_tax=round(total_tax, 2),
            effective_rate=round(effective_rate, 2),
            marginal_rate=marginal_rate,
            refund_or_owed=round(refund_or_owed, 2),
            is_refund=refund_or_owed > 0,
            # Enhanced breakdown
            amt_tax=round(amt, 2),
            niit_tax=round(niit, 2),
            child_tax_credit=round(ctc, 2),
            qbi_deduction=round(qbi_deduction, 2),
            itemized_breakdown=itemized_breakdown if deduction_type == "itemized" else None,
            tax_bracket_detail=f"{marginal_rate}% bracket",
            tax_notices=tax_notices,
            # Capital gains breakdown
            short_term_gains=round(short_term_gains, 2),
            long_term_gains=round(long_term_gains, 2),
            capital_gains_tax=round(capital_gains_tax, 2),
            capital_loss_deduction=0.0,
            net_investment_income=round(net_investment_income, 2),
            # K-1 and pass-through breakdown
            k1_ordinary_income_taxable=round(k1_ordinary, 2),
            k1_qbi_eligible=round(k1_qbi, 2),
            guaranteed_payments=round(profile.get("k1_guaranteed_payments", 0) or 0, 2),
            passive_loss_allowed=0.0,  # Would need full PAL calc
            passive_loss_suspended=0.0,
            # Rental breakdown
            rental_net_income=round(rental_net, 2),
            rental_depreciation_claimed=round(profile.get("rental_depreciation", 0) or 0, 2),
            rental_loss_allowed=0.0,  # Would need PAL calc
        )

    async def get_tax_strategies(self, profile: Dict[str, Any], calculation: TaxCalculationResult) -> List[StrategyRecommendation]:
        """Get personalized tax optimization strategies."""
        strategies = []
        marginal_rate = calculation.marginal_rate / 100

        # 1. Retirement Optimization
        current_401k = profile.get("retirement_401k", 0) or 0
        max_401k = 23500
        age = profile.get("age", 40) or 40
        if age >= 50:
            max_401k += 7500  # Catch-up

        remaining_401k = max(0, max_401k - current_401k)
        if remaining_401k > 0:
            savings = remaining_401k * marginal_rate
            strategies.append(StrategyRecommendation(
                id="retirement-401k",
                category="Retirement",
                title="Maximize 401(k) Contributions",
                summary=f"Contribute ${remaining_401k:,.0f} more to your 401(k) to save ${savings:,.0f} in taxes.",
                detailed_explanation=f"""Your 401(k) contributions reduce your taxable income dollar-for-dollar.
At your {calculation.marginal_rate}% marginal tax rate, every $1,000 you contribute saves you ${marginal_rate * 1000:,.0f} in taxes immediately,
while building your retirement wealth tax-deferred.""",
                estimated_savings=round(savings, 2),
                confidence="high",
                priority="high" if savings > 2000 else "medium",
                action_steps=[
                    "Log into your employer's benefits portal",
                    f"Increase your contribution rate to reach ${max_401k:,.0f} by December",
                    "Consider front-loading contributions if cash flow allows"
                ],
                irs_reference="IRS Publication 560"
            ))

        # 2. IRA Contributions - Check income limits for deductibility
        current_ira = profile.get("retirement_ira", 0) or 0
        max_ira = 7000
        if age >= 50:
            max_ira += 1000

        total_income = profile.get("total_income", 0) or 0
        filing_status = profile.get("filing_status", "single")
        has_workplace_plan = (profile.get("retirement_401k", 0) or 0) > 0 or profile.get("has_401k", False)

        # IRS 2025 Traditional IRA deduction limits when covered by workplace plan
        # Single: Phase-out $77,000 - $87,000
        # MFJ: Phase-out $123,000 - $143,000
        if filing_status in ["married_filing_jointly", "married filing jointly"]:
            ira_deduction_limit = 143000
            ira_phaseout_start = 123000
        else:
            ira_deduction_limit = 87000
            ira_phaseout_start = 77000

        remaining_ira = max(0, max_ira - current_ira)

        # Determine if Traditional IRA is deductible for this user
        is_high_earner = total_income > ira_deduction_limit
        partially_deductible = total_income > ira_phaseout_start and total_income <= ira_deduction_limit

        if remaining_ira > 0:
            if is_high_earner and has_workplace_plan:
                # High earner with workplace plan - recommend Backdoor Roth IRA
                strategies.append(StrategyRecommendation(
                    id="retirement-backdoor-roth",
                    category="Retirement",
                    title="Backdoor Roth IRA",
                    summary=f"Use Backdoor Roth IRA strategy to contribute ${remaining_ira:,.0f} to tax-free retirement savings.",
                    detailed_explanation=f"""At ${total_income:,.0f} income with a workplace retirement plan, Traditional IRA
contributions are NOT tax-deductible. However, you can use the Backdoor Roth IRA strategy:

1. Contribute ${remaining_ira:,.0f} to a Traditional IRA (non-deductible)
2. Immediately convert to Roth IRA
3. Enjoy tax-free growth and tax-free withdrawals in retirement

This is a legal strategy used by high earners to access Roth benefits despite income limits.""",
                    estimated_savings=round(remaining_ira * marginal_rate * 0.5, 2),  # Future tax-free growth
                    confidence="high",
                    priority="high",
                    action_steps=[
                        "Ensure you have NO pre-tax Traditional IRA balances (to avoid pro-rata rule)",
                        f"Contribute ${remaining_ira:,.0f} to a Traditional IRA (non-deductible)",
                        "Immediately convert the entire balance to a Roth IRA",
                        "Report on Form 8606 with your tax return"
                    ],
                    irs_reference="IRS Publication 590-A, Form 8606"
                ))
            elif is_high_earner:
                # High earner without workplace plan - may still be able to deduct, but recommend Roth
                savings = remaining_ira * marginal_rate
                strategies.append(StrategyRecommendation(
                    id="retirement-ira",
                    category="Retirement",
                    title="Traditional or Backdoor Roth IRA",
                    summary=f"Consider Traditional IRA (deductible) or Backdoor Roth IRA strategy.",
                    detailed_explanation=f"""At ${total_income:,.0f} income without a workplace retirement plan,
you may still be able to deduct Traditional IRA contributions. However, with your high income,
consider whether tax-free growth in a Roth IRA might benefit you more long-term.""",
                    estimated_savings=round(savings, 2),
                    confidence="medium",
                    priority="medium",
                    action_steps=[
                        f"Contribute up to ${max_ira:,.0f} before the April tax deadline",
                        "Evaluate Traditional vs Roth based on expected retirement tax rates",
                        "Consider Backdoor Roth if you want tax-free growth"
                    ],
                    irs_reference="IRS Publication 590-A"
                ))
            else:
                # Lower income - Traditional IRA is deductible
                savings = remaining_ira * marginal_rate
                strategies.append(StrategyRecommendation(
                    id="retirement-ira",
                    category="Retirement",
                    title="Traditional IRA Contribution",
                    summary=f"Contribute ${remaining_ira:,.0f} to a Traditional IRA for ${savings:,.0f} tax savings.",
                    detailed_explanation=f"""Traditional IRA contributions are tax-deductible at your income level.
At your {calculation.marginal_rate}% marginal tax rate, every $1,000 you contribute saves you ${marginal_rate * 1000:,.0f} in taxes immediately.""",
                    estimated_savings=round(savings, 2),
                    confidence="high",
                    priority="medium",
                    action_steps=[
                        "Open a Traditional IRA if you don't have one",
                        f"Contribute up to ${max_ira:,.0f} before the April tax deadline",
                        "Consider Roth IRA if you expect higher taxes in retirement"
                    ],
                    irs_reference="IRS Publication 590-A"
                ))

        # 2b. Mega Backdoor Roth for high earners with 401(k)
        if is_high_earner and has_workplace_plan:
            mega_contribution = 46000  # 2025 limit: $69,000 total - $23,000 employee
            mega_future_value = mega_contribution * 0.07 * 20  # 7% for 20 years simplified
            strategies.append(StrategyRecommendation(
                id="retirement-mega-backdoor",
                category="Retirement",
                title="Mega Backdoor Roth",
                summary=f"Contribute up to ${mega_contribution:,.0f} extra to Roth via after-tax 401(k) contributions.",
                detailed_explanation=f"""The Mega Backdoor Roth allows high earners to contribute significantly more to Roth accounts:

1. Max out your regular 401(k) ($23,500 in 2025)
2. Make after-tax contributions to your 401(k) (if your plan allows)
3. Convert these after-tax contributions to Roth 401(k) or roll to Roth IRA
4. The 2025 total 401(k) limit is $69,000 (including employer match)

This could add ${mega_contribution:,.0f} more per year to tax-free retirement savings.""",
                estimated_savings=round(mega_future_value * 0.25, 2),  # Estimated future tax savings
                confidence="medium",
                priority="high",
                action_steps=[
                    "Check if your 401(k) plan allows after-tax contributions",
                    "Verify your plan allows in-plan Roth conversions or in-service distributions",
                    "Coordinate with HR/plan administrator",
                    "Consider timing - convert quickly to minimize taxable gains"
                ],
                irs_reference="IRS Notice 2014-54"
            ))

        # 3. HSA Contributions (if applicable)
        if profile.get("hsa_contributions") is not None or True:  # Assume eligible
            current_hsa = profile.get("hsa_contributions", 0) or 0
            max_hsa = 4300 if profile.get("filing_status") == "single" else 8550
            if age >= 55:
                max_hsa += 1000

            remaining_hsa = max(0, max_hsa - current_hsa)
            if remaining_hsa > 0:
                savings = remaining_hsa * marginal_rate
                strategies.append(StrategyRecommendation(
                    id="healthcare-hsa",
                    category="Healthcare",
                    title="Health Savings Account (HSA)",
                    summary=f"Contribute ${remaining_hsa:,.0f} to HSA for triple tax advantage.",
                    detailed_explanation="""HSA offers the only triple tax benefit in the tax code:
1. Tax-deductible contributions
2. Tax-free growth
3. Tax-free withdrawals for medical expenses

After age 65, HSA funds can be used for any purpose (just taxed as ordinary income, like an IRA).""",
                    estimated_savings=round(savings, 2),
                    confidence="high",
                    priority="high",
                    action_steps=[
                        "Verify you have a high-deductible health plan (HDHP)",
                        f"Set up automatic HSA contributions to reach ${max_hsa:,.0f}",
                        "Keep receipts for medical expenses - reimburse yourself later"
                    ],
                    irs_reference="IRS Publication 969"
                ))

        # 4. Charitable Giving Strategy
        charitable = profile.get("charitable_donations", 0) or 0
        if charitable > 0 or profile.get("total_income", 0) > 100000:
            strategies.append(StrategyRecommendation(
                id="charitable-bunching",
                category="Charitable",
                title="Charitable Donation Bunching",
                summary="Bunch 2-3 years of donations into one year to itemize deductions.",
                detailed_explanation=f"""With the $15,000 standard deduction, many people can't itemize.
By 'bunching' multiple years of charitable donations into a single year, you can exceed the standard deduction
and get a larger tax benefit. Consider a Donor-Advised Fund (DAF) for flexibility.""",
                estimated_savings=round(charitable * 0.3 * marginal_rate, 2),
                confidence="medium",
                priority="medium" if charitable > 5000 else "low",
                action_steps=[
                    "Calculate your total itemized deductions",
                    "If close to standard deduction, consider bunching",
                    "Open a Donor-Advised Fund for flexibility",
                    "Donate appreciated stock instead of cash to avoid capital gains"
                ],
                irs_reference="IRS Publication 526"
            ))

        # 5. Business/Self-Employment Strategies
        if profile.get("is_self_employed") or profile.get("business_income"):
            business_income = profile.get("business_income", 0) or 0

            # S-Corp Election
            if business_income > 50000:
                se_savings = business_income * 0.5 * 0.153  # Save SE tax on distributions
                strategies.append(StrategyRecommendation(
                    id="entity-scorp",
                    category="Business Structure",
                    title="S-Corporation Election",
                    summary=f"S-Corp election could save you ${se_savings:,.0f} in self-employment taxes.",
                    detailed_explanation=f"""As a sole proprietor, you pay 15.3% self-employment tax on all net earnings.
With an S-Corp, you pay yourself a 'reasonable salary' (SE tax applies), but remaining profits
are distributions (no SE tax). At ${business_income:,.0f} income, this can mean significant savings.""",
                    estimated_savings=round(se_savings, 2),
                    confidence="high",
                    priority="high" if se_savings > 3000 else "medium",
                    action_steps=[
                        "Consult with a CPA about reasonable salary requirements",
                        "File Form 2553 to elect S-Corp status",
                        "Set up payroll for yourself",
                        "Consider timing - election typically takes effect next year"
                    ],
                    irs_reference="IRS Form 2553"
                ))

            # Home Office Deduction
            if profile.get("home_office_sqft"):
                sqft = profile.get("home_office_sqft", 200)
                home_office_deduction = min(sqft * 5, 1500)  # Simplified method
                savings = home_office_deduction * marginal_rate
                strategies.append(StrategyRecommendation(
                    id="business-homeoffice",
                    category="Business Deductions",
                    title="Home Office Deduction",
                    summary=f"Claim ${home_office_deduction:,.0f} home office deduction.",
                    detailed_explanation="""If you use part of your home regularly and exclusively for business,
you can deduct home office expenses. The simplified method allows $5 per square foot (up to 300 sq ft = $1,500).
The regular method may yield higher deductions but requires more recordkeeping.""",
                    estimated_savings=round(savings, 2),
                    confidence="high",
                    priority="medium",
                    action_steps=[
                        "Measure your dedicated home office space",
                        "Choose simplified ($5/sqft) or regular method",
                        "Take photos of your home office for documentation",
                        "Keep utility bills and home expense records"
                    ],
                    irs_reference="IRS Publication 587"
                ))

            # QBI Deduction
            if business_income > 0:
                qbi_deduction = business_income * 0.20  # Simplified
                savings = qbi_deduction * marginal_rate
                strategies.append(StrategyRecommendation(
                    id="business-qbi",
                    category="Business Deductions",
                    title="Qualified Business Income (QBI) Deduction",
                    summary=f"Claim up to ${qbi_deduction:,.0f} QBI deduction (20% pass-through).",
                    detailed_explanation="""The QBI deduction allows you to deduct up to 20% of qualified business income
from pass-through entities (sole proprietorships, S-corps, partnerships). Income limits may apply.""",
                    estimated_savings=round(savings, 2),
                    confidence="high",
                    priority="high",
                    action_steps=[
                        "Verify your business qualifies (most do)",
                        "Ensure proper recordkeeping of business income",
                        "Be aware of W-2 wage and property limitations at higher incomes"
                    ],
                    irs_reference="IRS Form 8995"
                ))

        # 6. Education Credits
        if profile.get("dependents", 0) > 0:
            strategies.append(StrategyRecommendation(
                id="credits-education",
                category="Education",
                title="American Opportunity Tax Credit",
                summary="Up to $2,500 per student for college expenses.",
                detailed_explanation="""The AOTC provides up to $2,500 per eligible student for the first 4 years of college.
It's 100% of the first $2,000 and 25% of the next $2,000 in qualified expenses.
40% is refundable (up to $1,000), meaning you get it even if you owe no taxes.""",
                estimated_savings=2500,
                confidence="medium",
                priority="high",
                action_steps=[
                    "Gather Form 1098-T from the educational institution",
                    "Keep receipts for books, supplies, and equipment",
                    "Verify income limits ($90,000 single, $180,000 MFJ)"
                ],
                irs_reference="IRS Form 8863"
            ))

        # 7. Child Tax Credit
        dependents = profile.get("dependents", 0) or 0
        if dependents > 0:
            ctc_amount = dependents * 2000
            strategies.append(StrategyRecommendation(
                id="credits-ctc",
                category="Family",
                title="Child Tax Credit",
                summary=f"Claim ${ctc_amount:,.0f} in Child Tax Credit for {dependents} dependent(s).",
                detailed_explanation=f"""The Child Tax Credit provides $2,000 per qualifying child under 17.
Up to $1,700 per child is refundable as the Additional Child Tax Credit.
Phase-out begins at $200,000 (single) or $400,000 (MFJ).""",
                estimated_savings=ctc_amount,
                confidence="high",
                priority="high",
                action_steps=[
                    "Verify each child is under 17 at year-end",
                    "Ensure you have valid SSN for each child",
                    "Complete Schedule 8812 with your return"
                ],
                irs_reference="IRS Schedule 8812"
            ))

        # 8. Tax-Loss Harvesting - Show when user has capital gains or high income
        investment_income = profile.get("investment_income", 0) or 0
        short_term_gains = profile.get("capital_gains_short", 0) or calculation.short_term_gains or 0
        long_term_gains = profile.get("capital_gains_long", 0) or profile.get("capital_gains", 0) or calculation.long_term_gains or 0
        total_cap_gains = short_term_gains + long_term_gains

        if total_cap_gains > 0 or investment_income > 0 or total_income > 200000:
            # Calculate potential savings from harvesting
            if total_cap_gains > 0:
                # Can offset gains directly + $3k ordinary income
                potential_offset = total_cap_gains
                # ST gains save at ordinary rate, LT at preferential
                savings = (short_term_gains * marginal_rate) + (long_term_gains * 0.15)
                savings += min(3000, max(0, 10000 - total_cap_gains)) * marginal_rate  # Extra ordinary income offset
            else:
                # No gains yet - estimate based on income level
                estimated_harvesting_potential = min(10000, total_income * 0.02) if total_income > 200000 else 3000
                potential_offset = estimated_harvesting_potential
                savings = min(3000, estimated_harvesting_potential) * marginal_rate

            # Check for NIIT exposure (adds 3.8% value to harvesting)
            niit_threshold = 200000 if filing_status == "single" else 250000
            has_niit_exposure = calculation.niit_tax > 0 or total_income > niit_threshold
            if has_niit_exposure and total_cap_gains > 0:
                savings += total_cap_gains * 0.038  # NIIT savings

            gain_detail = f"You have ${total_cap_gains:,.0f} in capital gains " if total_cap_gains > 0 else "Even without current gains, "
            niit_note = f"\n\n**NIIT Alert**: With NIIT exposure, harvesting saves an additional 3.8% on investment income!" if has_niit_exposure else ""

            strategies.append(StrategyRecommendation(
                id="investment-tlh",
                category="Investment",
                title="Tax-Loss Harvesting",
                summary=f"Harvest losses to offset ${potential_offset:,.0f} in gains, saving ${savings:,.0f} in taxes.",
                detailed_explanation=f"""{gain_detail}making tax-loss harvesting valuable:

1. **Offset Capital Gains**: Sell investments at a loss to offset gains dollar-for-dollar
   - Short-term gains (taxed at {calculation.marginal_rate}%): ${short_term_gains:,.0f}
   - Long-term gains (taxed at 15-20%): ${long_term_gains:,.0f}
2. **Ordinary Income Deduction**: Deduct up to $3,000 of excess losses against your ordinary income
3. **Carry Forward**: Unused losses carry forward indefinitely{niit_note}

Estimated tax savings: **${savings:,.0f}**""",
                estimated_savings=round(savings, 2),
                confidence="high" if total_cap_gains > 0 else "medium",
                priority="high" if total_cap_gains > 10000 or has_niit_exposure else "medium",
                action_steps=[
                    "Review your brokerage accounts for unrealized losses",
                    "Identify positions down 10%+ that you can harvest",
                    f"Target losses of ${potential_offset:,.0f}+ to offset your gains",
                    "Sell losing positions before year-end (or anytime markets dip)",
                    "Wait 31+ days before repurchasing same security (wash sale rule)",
                    "Consider similar (not identical) replacement investments immediately"
                ],
                irs_reference="IRS Publication 550",
                deadline="December 31, 2025" if total_cap_gains > 0 else None
            ))

        # Sort by estimated savings
        strategies.sort(key=lambda x: x.estimated_savings, reverse=True)

        return strategies

    def generate_executive_summary(self, profile: Dict, calculation: TaxCalculationResult, strategies: List[StrategyRecommendation]) -> str:
        """Generate an executive summary of the tax analysis."""
        total_savings = sum(s.estimated_savings for s in strategies)
        top_strategies = strategies[:3]

        income = profile.get("total_income", 0) or 0
        filing_status = profile.get("filing_status", "single").replace("_", " ").title()

        summary = f"""## Executive Tax Analysis Summary

**Client Profile:** {filing_status} filer with ${income:,.0f} annual income

**Current Tax Position:**
- Federal Tax: ${calculation.federal_tax:,.0f}
- State Tax: ${calculation.state_tax:,.0f}
- Total Tax Liability: ${calculation.total_tax:,.0f}
- Effective Tax Rate: {calculation.effective_rate:.1f}%
- Marginal Tax Rate: {calculation.marginal_rate}%

**Total Optimization Opportunity:** ${total_savings:,.0f}

**Top 3 Recommendations:**
"""
        for i, strategy in enumerate(top_strategies, 1):
            summary += f"\n{i}. **{strategy.title}** - Save ${strategy.estimated_savings:,.0f}\n   {strategy.summary}\n"

        summary += f"""
**Next Steps:**
1. Review the detailed recommendations below
2. Prioritize high-impact strategies ({len([s for s in strategies if s.priority == 'high'])} identified)
3. Consult with a CPA for implementation guidance
4. Take action before applicable deadlines
"""

        return summary


# Initialize the chat engine
chat_engine = IntelligentChatEngine()


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint with session persistence status."""
    session_counts = chat_engine.get_session_count()
    return {
        "status": "healthy",
        "service": "intelligent-advisor",
        "persistence_enabled": chat_engine._persistence is not None,
        "sessions": session_counts
    }


@router.get("/sessions/stats")
async def get_session_stats():
    """Get statistics about active sessions."""
    session_counts = chat_engine.get_session_count()
    return {
        "in_memory_sessions": session_counts["in_memory"],
        "database_sessions": session_counts["in_database"],
        "persistence_enabled": chat_engine._persistence is not None,
        "persistence_type": "SQLite" if chat_engine._persistence else "In-memory only"
    }


@router.post("/chat", response_model=ChatResponse)
async def intelligent_chat(request: ChatRequest):
    """
    Main intelligent chat endpoint.

    This endpoint handles all chat interactions, providing:
    - Intelligent responses based on context
    - Real-time tax calculations
    - Personalized strategy recommendations
    - Dynamic follow-up questions
    """
    session = chat_engine.get_or_create_session(request.session_id)

    # Update profile with any new data and persist
    if request.profile:
        profile_dict = request.profile.dict(exclude_none=True)
        session = chat_engine.update_session(request.session_id, {"profile": profile_dict})

    profile = session["profile"]

    # Calculate metrics
    completeness = chat_engine.calculate_profile_completeness(profile)
    lead_score = chat_engine.calculate_lead_score(profile)
    complexity = chat_engine.determine_complexity(profile)

    # Get urgency info from CPAIntelligenceService
    urgency_level = "PLANNING"
    urgency_message = "Perfect timing for tax planning!"
    days_to_deadline = 365
    try:
        from services.cpa_intelligence_service import calculate_urgency_level
        urgency_level, urgency_message, days_to_deadline = calculate_urgency_level()
    except Exception as e:
        logger.debug(f"Urgency calculation skipped: {e}")

    # Determine response type and content
    response_type = "question"
    response_text = ""
    tax_calculation = None
    strategies = []
    next_questions = []
    quick_actions = []
    key_insights = []
    warnings = []
    total_potential_savings = 0.0

    # If we have enough data, calculate taxes
    if profile.get("total_income") and profile.get("filing_status"):
        tax_calculation = await chat_engine.get_tax_calculation(profile)

        # Get strategies
        strategies = await chat_engine.get_tax_strategies(profile, tax_calculation)

        # Update session with calculations and strategies, and persist to database
        chat_engine.update_session(request.session_id, {
            "calculations": tax_calculation,
            "strategies": strategies,
            "lead_score": chat_engine.calculate_lead_score(profile)
        })

        total_savings = sum(s.estimated_savings for s in strategies)
        total_potential_savings = total_savings

        response_type = "calculation"
        response_text = f"""Based on your {profile.get('filing_status', 'single').replace('_', ' ')} filing status and ${profile.get('total_income', 0):,.0f} income, here's your tax analysis:

**Your Tax Position:**
• Federal Tax: **${tax_calculation.federal_tax:,.0f}**
• State Tax: **${tax_calculation.state_tax:,.0f}**
• Total Tax: **${tax_calculation.total_tax:,.0f}**
• Effective Rate: **{tax_calculation.effective_rate:.1f}%**

**🎯 I found ${total_savings:,.0f} in potential savings across {len(strategies)} strategies!**

Your top opportunity: **{strategies[0].title}** could save you **${strategies[0].estimated_savings:,.0f}**.

Would you like me to explain your top strategies, or generate your full advisory report?"""

        quick_actions = [
            {"label": "Show Top Strategies →", "value": "show_strategies", "primary": True},
            {"label": "Generate Full Report", "value": "generate_report"},
            {"label": "Connect with CPA", "value": "connect_cpa"}
        ]

        key_insights = [
            f"Your marginal tax rate is {tax_calculation.marginal_rate}%",
            f"Taking the {tax_calculation.deduction_type} deduction saves you most",
            f"Top opportunity: {strategies[0].title}"
        ]

    else:
        # Need more information
        if not profile.get("filing_status"):
            response_text = "To provide accurate tax strategies, I need to know your filing status. What's your current situation?"
            next_questions = [
                {"question": "What's your filing status?", "type": "select", "options": [
                    {"label": "Single", "value": "single"},
                    {"label": "Married Filing Jointly", "value": "married_joint"},
                    {"label": "Head of Household", "value": "head_of_household"},
                    {"label": "Married Filing Separately", "value": "married_separate"},
                    {"label": "Qualifying Surviving Spouse", "value": "qualifying_widow"}
                ]}
            ]
            quick_actions = [
                {"label": "Single", "value": "filing_single"},
                {"label": "Married Filing Jointly", "value": "filing_married"},
                {"label": "Head of Household", "value": "filing_hoh"},
                {"label": "Married Separately", "value": "filing_mfs"},
                {"label": "Qualifying Surviving Spouse", "value": "filing_qss"}
            ]
        elif not profile.get("total_income"):
            response_text = "What's your approximate total annual income for 2025? Include all sources - W-2 wages, self-employment, investments, etc."
            quick_actions = [
                {"label": "$0 - $50,000", "value": "income_0_50k"},
                {"label": "$50,000 - $100,000", "value": "income_50_100k"},
                {"label": "$100,000 - $200,000", "value": "income_100_200k"},
                {"label": "$200,000 - $500,000", "value": "income_200_500k"},
                {"label": "Over $500,000", "value": "income_500k_plus"}
            ]

    # Add urgency warning if critical
    if urgency_level == "CRITICAL":
        warnings.append(f"⚠️ {urgency_message}")
    elif urgency_level == "HIGH":
        key_insights.insert(0, f"📅 {urgency_message}")

    return ChatResponse(
        session_id=request.session_id,
        response=response_text,
        response_type=response_type,
        tax_calculation=tax_calculation,
        strategies=[StrategyRecommendation(**s.dict()) for s in strategies[:5]] if strategies else [],
        next_questions=next_questions,
        quick_actions=quick_actions,
        profile_completeness=completeness,
        lead_score=lead_score,
        complexity=complexity,
        urgency_level=urgency_level,
        urgency_message=urgency_message,
        days_to_deadline=days_to_deadline,
        key_insights=key_insights,
        warnings=warnings,
        total_potential_savings=total_potential_savings
    )


@router.post("/analyze", response_model=FullAnalysisResponse)
async def full_analysis(request: FullAnalysisRequest):
    """
    Comprehensive tax analysis with all strategies and insights.

    This is the full advisory engine - use this when you have
    complete profile data and want all recommendations.
    """
    profile = request.profile.dict(exclude_none=True)

    # Get tax calculation
    calculation = await chat_engine.get_tax_calculation(profile)

    # Get all strategies
    strategies = await chat_engine.get_tax_strategies(profile, calculation)

    total_savings = sum(s.estimated_savings for s in strategies)

    # Entity comparison if self-employed
    entity_comparison = None
    if profile.get("is_self_employed") or profile.get("business_income"):
        business_income = profile.get("business_income", 0) or 0
        entity_comparison = {
            "sole_proprietorship": {
                "tax": calculation.total_tax,
                "se_tax": calculation.self_employment_tax
            },
            "s_corporation": {
                "salary": business_income * 0.5,
                "distribution": business_income * 0.5,
                "se_tax_savings": business_income * 0.5 * 0.153,
                "recommended": business_income > 50000
            }
        }

    # 5-year projection
    five_year = {}
    for year in range(2025, 2030):
        growth_factor = 1 + (0.03 * (year - 2025))  # 3% annual growth
        projected_income = (profile.get("total_income", 0) or 0) * growth_factor
        projected_tax = calculation.total_tax * growth_factor
        five_year[str(year)] = {
            "income": round(projected_income, 2),
            "tax": round(projected_tax, 2),
            "savings_if_optimized": round(total_savings * growth_factor, 2)
        }

    # Executive summary
    summary = chat_engine.generate_executive_summary(profile, calculation, strategies)

    # Deduction analysis
    deduction_rec = "standard" if calculation.deduction_type == "standard" else "itemized"
    itemized_est = (
        (profile.get("mortgage_interest", 0) or 0) +
        (profile.get("property_taxes", 0) or 0) +
        min((profile.get("state_income_tax", 0) or 0), 10000) +
        (profile.get("charitable_donations", 0) or 0)
    )

    # Eligible credits
    credits = []
    if profile.get("dependents", 0) > 0:
        credits.append({
            "name": "Child Tax Credit",
            "amount": profile.get("dependents", 0) * 2000,
            "refundable": True
        })

    # Get urgency info
    urgency_level = "PLANNING"
    urgency_message = "Perfect timing for tax planning!"
    days_to_deadline = 365
    try:
        from services.cpa_intelligence_service import calculate_urgency_level
        urgency_level, urgency_message, days_to_deadline = calculate_urgency_level()
    except Exception:
        pass

    lead_score = chat_engine.calculate_lead_score(profile)

    return FullAnalysisResponse(
        session_id=request.session_id,
        current_tax=calculation,
        strategies=[StrategyRecommendation(**s.dict()) for s in strategies],
        total_potential_savings=total_savings,
        top_3_opportunities=[StrategyRecommendation(**s.dict()) for s in strategies[:3]],
        entity_comparison=entity_comparison,
        five_year_projection=five_year,
        executive_summary=summary,
        deduction_recommendation=f"Based on your situation, taking the **{deduction_rec} deduction** is optimal.",
        itemized_vs_standard={
            "standard": calculation.deductions,
            "itemized_estimate": itemized_est
        },
        eligible_credits=credits,
        confidence="high" if chat_engine.calculate_profile_completeness(profile) > 0.7 else "medium",
        complexity=chat_engine.determine_complexity(profile),
        urgency_level=urgency_level,
        urgency_message=urgency_message,
        days_to_deadline=days_to_deadline,
        lead_score=lead_score,
        report_ready=True
    )


@router.post("/strategies")
async def get_strategies(request: FullAnalysisRequest):
    """Get personalized tax strategies."""
    profile = request.profile.dict(exclude_none=True)
    calculation = await chat_engine.get_tax_calculation(profile)
    strategies = await chat_engine.get_tax_strategies(profile, calculation)

    return {
        "strategies": [s.dict() for s in strategies],
        "total_potential_savings": sum(s.estimated_savings for s in strategies),
        "top_3": [s.dict() for s in strategies[:3]]
    }


@router.post("/calculate")
async def calculate_taxes(request: FullAnalysisRequest):
    """Quick tax calculation endpoint."""
    profile = request.profile.dict(exclude_none=True)
    calculation = await chat_engine.get_tax_calculation(profile)
    return calculation.dict()


@router.post("/upload-document")
async def upload_document(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    document_type: str = Form(None)
):
    """
    Upload and process a tax document with OCR.

    Supported documents: W-2, 1099, 1098, K-1, etc.
    """
    try:
        # Try to use the unified tax advisor for OCR
        from services.unified_tax_advisor import UnifiedTaxAdvisor, DocumentType

        advisor = UnifiedTaxAdvisor()

        # Save uploaded file temporarily
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # Determine document type
            doc_type = DocumentType(document_type) if document_type else DocumentType.OTHER

            # Process document
            extracted = advisor.process_document(tmp_path, doc_type)

            return {
                "success": True,
                "document_type": extracted.document_type.value,
                "extracted_fields": extracted.extracted_fields,
                "confidence": extracted.extraction_confidence,
                "needs_review": extracted.needs_review,
                "payer_name": extracted.payer_name,
                "message": f"Successfully extracted data from {file.filename}"
            }
        finally:
            os.unlink(tmp_path)

    except Exception as e:
        logger.error(f"Document processing error: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Unable to process document. Please try again or enter the information manually."
        }


class SessionReportRequest(BaseModel):
    """Request for session-based report."""
    session_id: str


@router.post("/report")
async def get_session_report(request: SessionReportRequest):
    """Get report data for a session (used by report preview page).

    Now with database persistence! Will load session from database
    if not found in memory.
    """
    # Use get_or_create_session which checks memory, then database
    session = chat_engine.get_or_create_session(request.session_id)

    # Check if session has meaningful data (not just newly created)
    if not session.get("profile"):
        raise HTTPException(status_code=404, detail="Session not found or has no data")

    calculation = session.get("calculations")
    strategies = session.get("strategies", [])
    profile = session.get("profile", {})

    # If no calculation exists, generate one from the profile and persist
    if not calculation and profile and profile.get("total_income") and profile.get("filing_status"):
        calculation = await chat_engine.get_tax_calculation(profile)
        strategies = await chat_engine.get_tax_strategies(profile, calculation)

        # Persist the generated calculation to database
        chat_engine.update_session(request.session_id, {
            "calculations": calculation,
            "strategies": strategies
        })

    if not calculation:
        raise HTTPException(
            status_code=400,
            detail="No tax calculation available. Please complete the tax analysis first."
        )

    return {
        "session_id": request.session_id,
        "tax_calculation": calculation.dict() if hasattr(calculation, 'dict') else calculation,
        "strategies": [s.dict() if hasattr(s, 'dict') else s for s in strategies],
        "profile": profile
    }


@router.post("/generate-report")
async def generate_report(request: FullAnalysisRequest):
    """Generate a professional advisory report."""
    profile = request.profile.dict(exclude_none=True)
    calculation = await chat_engine.get_tax_calculation(profile)
    strategies = await chat_engine.get_tax_strategies(profile, calculation)

    # Generate executive summary
    summary = chat_engine.generate_executive_summary(profile, calculation, strategies)

    return {
        "session_id": request.session_id,
        "report": {
            "title": "Tax Advisory Report - 2025",
            "generated_at": datetime.now().isoformat(),
            "executive_summary": summary,
            "tax_position": calculation.dict(),
            "strategies": [s.dict() for s in strategies],
            "total_potential_savings": sum(s.estimated_savings for s in strategies),
            "action_items": [
                {
                    "priority": s.priority,
                    "action": s.action_steps[0] if s.action_steps else s.title,
                    "deadline": s.deadline
                }
                for s in strategies[:5]
            ],
            "disclaimer": """This report is for informational purposes only and does not constitute professional tax advice.
Please consult with a licensed CPA or tax professional before making any tax-related decisions.
Tax laws are subject to change, and individual circumstances may vary."""
        },
        "download_url": f"/api/advisor/report/{request.session_id}/pdf"
    }


# =============================================================================
# PDF GENERATION ENDPOINTS
# =============================================================================

@router.get("/report/{session_id}/pdf")
async def get_session_pdf(
    session_id: str,
    include_charts: bool = True,
    include_toc: bool = True,
    cpa_id: Optional[str] = None,  # CPA profile ID to load branding from
    firm_name: Optional[str] = None,
    advisor_name: Optional[str] = None,
    advisor_credentials: Optional[str] = None,  # Comma-separated
    contact_email: Optional[str] = None,
    contact_phone: Optional[str] = None,
    primary_color: Optional[str] = None,
    watermark: Optional[str] = None,
):
    """
    Generate and download PDF report for a session.

    This endpoint generates a professional tax advisory PDF from the
    chatbot session data with optional CPA branding and visualizations.

    Query Parameters:
        - include_charts: Include visualizations (default: True)
        - include_toc: Include table of contents (default: True)
        - cpa_id: CPA profile ID to load branding from (overrides manual params)
        - firm_name: CPA firm name for branding (used if cpa_id not provided)
        - advisor_name: Advisor name for branding
        - advisor_credentials: Comma-separated credentials (e.g., "CPA,CFP,MST")
        - contact_email: Contact email for footer
        - contact_phone: Contact phone for footer
        - primary_color: Primary brand color (hex, e.g., "#2c5aa0")
        - watermark: Watermark text (e.g., "DRAFT")
    """
    import tempfile
    from pathlib import Path

    # Apply rate limiting
    if RATE_LIMITER_AVAILABLE:
        if not pdf_rate_limiter.is_allowed(session_id):
            remaining = pdf_rate_limiter.get_remaining(session_id)
            reset_time = pdf_rate_limiter.get_reset_time(session_id)
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "message": "Too many PDF generation requests. Please wait before trying again.",
                    "remaining": remaining,
                    "retry_after": int(reset_time) + 1,
                }
            )
        pdf_rate_limiter.record_request(session_id)

    # Get session data
    session = chat_engine.sessions.get(session_id)

    if not session:
        # Try loading from database
        session = chat_engine.get_or_create_session(session_id)
        if not session.get("profile"):
            raise HTTPException(status_code=404, detail="Session not found or has no data")

    profile = session.get("profile", {})

    if not profile.get("filing_status") or not profile.get("total_income"):
        raise HTTPException(
            status_code=400,
            detail="Insufficient data for PDF generation. Please complete the tax analysis first."
        )

    # Check if PDF generation is available
    if not PDF_GENERATION_AVAILABLE:
        # Fallback: redirect to advisory API
        raise HTTPException(
            status_code=503,
            detail="PDF generation service temporarily unavailable. Please try the advisory reports API."
        )

    try:
        # Import PDF exporter with branding support
        from export.advisory_pdf_exporter import (
            export_advisory_report_to_pdf,
            CPABrandConfig
        )

        # Build TaxReturn from profile
        tax_return = build_tax_return_from_profile(profile)

        # Generate report using the advisory report generator
        generator = AdvisoryReportGenerator()
        report = generator.generate_report(
            tax_return=tax_return,
            report_type=ReportType.FULL_ANALYSIS,
            include_entity_comparison=profile.get("is_self_employed", False),
            include_multi_year=True,
            years_ahead=3
        )

        # Build brand config - try CPA profile first, then manual parameters
        brand_config = None

        # Option 1: Load from CPA profile (preferred)
        if cpa_id and CPA_BRANDING_HELPER_AVAILABLE:
            brand_config = create_pdf_brand_config(cpa_id)
            if brand_config:
                logger.info(f"Using CPA branding from profile: {cpa_id}")

        # Option 2: Use manual parameters
        if not brand_config and any([firm_name, advisor_name, contact_email, contact_phone, primary_color]):
            credentials_list = []
            if advisor_credentials:
                credentials_list = [c.strip() for c in advisor_credentials.split(",")]

            brand_config = CPABrandConfig(
                firm_name=firm_name or "Tax Advisory Services",
                advisor_name=advisor_name,
                advisor_credentials=credentials_list,
                contact_email=contact_email,
                contact_phone=contact_phone,
                primary_color=primary_color or "#2c5aa0",
            )

        # Generate PDF using the exporter
        output_dir = Path("/tmp/advisor_reports")
        output_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = str(output_dir / f"report_{session_id}.pdf")

        export_advisory_report_to_pdf(
            report=report,
            output_path=pdf_path,
            watermark=watermark,
            include_charts=include_charts,
            include_toc=include_toc,
            brand_config=brand_config,
        )

        # Return PDF file
        return FileResponse(
            path=pdf_path,
            media_type="application/pdf",
            filename=f"tax_advisory_report_{session_id}.pdf"
        )

    except Exception as e:
        logger.error(f"PDF generation failed for session {session_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate PDF: {str(e)}"
        )


@router.post("/report/{session_id}/generate-pdf")
async def generate_session_pdf(session_id: str):
    """
    Generate PDF via the advisory reports API.

    This endpoint uses the main advisory reports system for PDF generation,
    which provides more features like background generation and storage.
    """
    # Get session and ensure it has data
    session = chat_engine.get_or_create_session(session_id)
    profile = session.get("profile", {})

    if not profile.get("filing_status") or not profile.get("total_income"):
        raise HTTPException(
            status_code=400,
            detail="Insufficient data. Please complete the tax analysis first."
        )

    # Ensure tax return data is saved for advisory API
    chat_engine._save_tax_return_for_advisory(session_id, profile)

    # Generate report via advisory API
    try:
        from web.advisory_api import (
            _report_store, _pdf_store, _session_reports, _report_session,
            _get_tax_return_from_session, _generate_report_sync, _generate_pdf_async
        )
        from advisory.report_generator import ReportType

        # Get tax return
        tax_return = _get_tax_return_from_session(session_id)

        # Generate report
        report = _generate_report_sync(
            tax_return=tax_return,
            report_type=ReportType.FULL_ANALYSIS,
            include_entity_comparison=profile.get("is_self_employed", False),
            include_multi_year=True,
            years_ahead=3
        )

        # Store report
        _report_store[report.report_id] = report
        if session_id not in _session_reports:
            _session_reports[session_id] = []
        _session_reports[session_id].append(report.report_id)
        _report_session[report.report_id] = session_id

        # Generate PDF (this function runs synchronously despite the name)
        _generate_pdf_async(report.report_id, report, watermark=None)
        pdf_available = report.report_id in _pdf_store

        return {
            "success": True,
            "report_id": report.report_id,
            "session_id": session_id,
            "pdf_available": pdf_available,
            "pdf_url": f"/api/v1/advisory-reports/{report.report_id}/pdf",
            "taxpayer_name": report.taxpayer_name,
            "potential_savings": float(report.potential_savings),
            "recommendations_count": report.top_recommendations_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate PDF for session {session_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate report: {str(e)}"
        )


# =============================================================================
# UNIVERSAL REPORT ENDPOINTS
# =============================================================================

class UniversalReportRequest(BaseModel):
    """Request for universal report generation."""
    session_id: str
    cpa_profile: Optional[Dict[str, Any]] = None
    output_format: str = "html"  # "html", "pdf", "both"
    tier_level: int = 2  # 1=teaser, 2=full, 3=complete


@router.post("/universal-report")
async def generate_universal_report(request: UniversalReportRequest):
    """
    Generate a universal report with dynamic visualizations.

    Features:
    - Savings gauge/meter
    - Charts and graphs
    - CPA branding/white-label support
    - Multiple output formats
    """
    try:
        from universal_report import UniversalReportEngine

        # Get session data
        session = chat_engine.get_or_create_session(request.session_id)
        profile = session.get("profile", {})

        if not profile.get("filing_status"):
            raise HTTPException(
                status_code=400,
                detail="Insufficient data. Please complete the tax analysis first."
            )

        # Ensure calculations exist
        calculation = session.get("calculations")
        strategies = session.get("strategies", [])

        if not calculation and profile.get("total_income"):
            calculation = await chat_engine.get_tax_calculation(profile)
            strategies = await chat_engine.get_tax_strategies(profile, calculation)
            chat_engine.update_session(request.session_id, {
                "calculations": calculation,
                "strategies": strategies
            })

        # Prepare session data for report engine
        session_data = {
            "profile": profile,
            "calculations": calculation.dict() if hasattr(calculation, 'dict') else calculation,
            "strategies": [s.dict() if hasattr(s, 'dict') else s for s in strategies],
            "lead_score": session.get("lead_score", 0),
            "complexity": chat_engine.determine_complexity(profile),
            "key_insights": session.get("key_insights", []),
            "warnings": session.get("warnings", []),
        }

        # Generate report
        engine = UniversalReportEngine()
        output = engine.generate_report(
            source_type='chatbot',
            source_id=request.session_id,
            source_data=session_data,
            cpa_profile=request.cpa_profile,
            output_format=request.output_format,
            tier_level=request.tier_level,
        )

        return {
            "success": True,
            "report_id": output.report_id,
            "session_id": request.session_id,
            "html_content": output.html_content if request.output_format in ('html', 'both') else None,
            "pdf_available": output.pdf_bytes is not None,
            "taxpayer_name": output.taxpayer_name,
            "tax_year": output.tax_year,
            "potential_savings": output.potential_savings,
            "recommendation_count": output.recommendation_count,
            "total_sections": output.total_sections,
        }

    except ImportError as e:
        logger.error(f"Universal report module not available: {e}")
        raise HTTPException(
            status_code=503,
            detail="Universal report generation not available"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Universal report generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate report: {str(e)}"
        )


@router.get("/universal-report/{session_id}/html")
async def get_universal_report_html(
    session_id: str,
    cpa: Optional[str] = None,
    tier: int = 2
):
    """
    Get HTML universal report for a session.

    Query params:
    - cpa: CPA profile identifier for branding
    - tier: Report tier level (1=teaser, 2=full, 3=complete)
    """
    try:
        from universal_report import UniversalReportEngine

        # Get session
        session = chat_engine.get_or_create_session(session_id)
        profile = session.get("profile", {})

        if not profile.get("filing_status"):
            raise HTTPException(status_code=404, detail="Session not found or has no data")

        # Get CPA profile if specified
        cpa_profile = None
        if cpa:
            # TODO: Load CPA profile from database
            cpa_profile = {"firm_name": cpa, "preset": "professional"}

        # Ensure calculations
        calculation = session.get("calculations")
        strategies = session.get("strategies", [])

        if not calculation and profile.get("total_income"):
            calculation = await chat_engine.get_tax_calculation(profile)
            strategies = await chat_engine.get_tax_strategies(profile, calculation)

        session_data = {
            "profile": profile,
            "calculations": calculation.dict() if hasattr(calculation, 'dict') else calculation,
            "strategies": [s.dict() if hasattr(s, 'dict') else s for s in strategies],
            "lead_score": session.get("lead_score", 0),
            "complexity": chat_engine.determine_complexity(profile),
        }

        engine = UniversalReportEngine()
        html = engine.generate_html_report(
            source_type='chatbot',
            source_id=session_id,
            source_data=session_data,
            cpa_profile=cpa_profile,
            tier_level=tier,
        )

        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html, media_type="text/html")

    except ImportError as e:
        logger.error(f"Universal report module not available: {e}")
        raise HTTPException(status_code=503, detail="Universal report not available")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Universal report HTML failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/universal-report/{session_id}/pdf")
async def get_universal_report_pdf(
    session_id: str,
    cpa: Optional[str] = None,
    tier: int = 2
):
    """
    Get PDF universal report for a session.

    Query params:
    - cpa: CPA profile identifier for branding
    - tier: Report tier level (1=teaser, 2=full, 3=complete)
    """
    import tempfile
    from pathlib import Path

    try:
        from universal_report import UniversalReportEngine

        # Get session
        session = chat_engine.get_or_create_session(session_id)
        profile = session.get("profile", {})

        if not profile.get("filing_status"):
            raise HTTPException(status_code=404, detail="Session not found or has no data")

        # Get CPA profile if specified
        cpa_profile = None
        if cpa:
            cpa_profile = {"firm_name": cpa, "preset": "professional"}

        # Ensure calculations
        calculation = session.get("calculations")
        strategies = session.get("strategies", [])

        if not calculation and profile.get("total_income"):
            calculation = await chat_engine.get_tax_calculation(profile)
            strategies = await chat_engine.get_tax_strategies(profile, calculation)

        session_data = {
            "profile": profile,
            "calculations": calculation.dict() if hasattr(calculation, 'dict') else calculation,
            "strategies": [s.dict() if hasattr(s, 'dict') else s for s in strategies],
            "lead_score": session.get("lead_score", 0),
            "complexity": chat_engine.determine_complexity(profile),
        }

        engine = UniversalReportEngine()
        output = engine.generate_report(
            source_type='chatbot',
            source_id=session_id,
            source_data=session_data,
            cpa_profile=cpa_profile,
            output_format='pdf',
            tier_level=tier,
        )

        if output.pdf_bytes:
            # Save to temp file and return
            output_dir = Path("/tmp/universal_reports")
            output_dir.mkdir(parents=True, exist_ok=True)
            pdf_path = output_dir / f"universal_report_{session_id}.pdf"
            pdf_path.write_bytes(output.pdf_bytes)

            return FileResponse(
                path=str(pdf_path),
                media_type="application/pdf",
                filename=f"tax_report_{session_id}.pdf"
            )
        else:
            raise HTTPException(status_code=500, detail="PDF generation failed")

    except ImportError as e:
        logger.error(f"Universal report module not available: {e}")
        raise HTTPException(status_code=503, detail="Universal report not available")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Universal report PDF failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# LOGO UPLOAD ENDPOINTS
# =============================================================================

@router.post("/branding/upload-logo")
async def upload_logo(
    cpa_id: str = Form(...),
    file: UploadFile = File(...),
):
    """
    Upload a logo for CPA branding.

    This endpoint allows CPAs to upload their firm logo for use in
    branded PDF reports and HTML reports.

    Form Data:
        - cpa_id: CPA identifier (e.g., "john-smith-cpa")
        - file: Logo image file (PNG, JPG, GIF, WebP, SVG)

    Limits:
        - Maximum file size: 5MB
        - Maximum dimensions: 2000x2000 pixels
        - Minimum dimensions: 50x50 pixels
    """
    if not LOGO_HANDLER_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Logo upload service not available"
        )

    # Validate CPA ID
    if not cpa_id or len(cpa_id) < 3:
        raise HTTPException(
            status_code=400,
            detail="Invalid CPA ID. Must be at least 3 characters."
        )

    # Read file content
    content = await file.read()

    # Upload logo
    success, logo_path, error = logo_handler.upload_logo(
        file_content=content,
        filename=file.filename,
        cpa_id=cpa_id,
        content_type=file.content_type,
    )

    if not success:
        raise HTTPException(status_code=400, detail=error)

    return {
        "success": True,
        "message": "Logo uploaded successfully",
        "cpa_id": cpa_id,
        "logo_path": logo_path,
        "logo_url": f"/api/advisor/branding/logo/{cpa_id}",
    }


@router.get("/branding/logo/{cpa_id}")
async def get_logo(cpa_id: str):
    """
    Get the logo for a CPA.

    Returns the logo image file for the specified CPA.
    """
    if not LOGO_HANDLER_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Logo service not available"
        )

    logo_path = logo_handler.get_logo_path(cpa_id)

    if not logo_path:
        raise HTTPException(
            status_code=404,
            detail=f"No logo found for CPA: {cpa_id}"
        )

    from pathlib import Path

    # Determine content type
    ext = Path(logo_path).suffix.lower()
    content_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.svg': 'image/svg+xml',
    }
    content_type = content_types.get(ext, 'application/octet-stream')

    return FileResponse(
        path=logo_path,
        media_type=content_type,
        filename=f"logo_{cpa_id}{ext}"
    )


@router.delete("/branding/logo/{cpa_id}")
async def delete_logo(cpa_id: str):
    """
    Delete the logo for a CPA.
    """
    if not LOGO_HANDLER_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Logo service not available"
        )

    success = logo_handler.delete_logo(cpa_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"No logo found for CPA: {cpa_id}"
        )

    return {
        "success": True,
        "message": f"Logo deleted for CPA: {cpa_id}"
    }


@router.get("/rate-limit/status")
async def get_rate_limit_status(session_id: str):
    """
    Get rate limit status for a session.

    Returns the current rate limit status including remaining requests
    and time until reset.
    """
    if not RATE_LIMITER_AVAILABLE:
        return {
            "rate_limiting": False,
            "message": "Rate limiting not enabled"
        }

    return {
        "rate_limiting": True,
        "session_id": session_id,
        "pdf_generation": {
            "remaining": pdf_rate_limiter.get_remaining(session_id),
            "reset_in_seconds": int(pdf_rate_limiter.get_reset_time(session_id)),
            "limit": pdf_rate_limiter.config.max_requests,
            "window_seconds": pdf_rate_limiter.config.window_seconds,
        }
    }


# Register the router
def register_intelligent_advisor_routes(app):
    """Register the intelligent advisor routes with the main app."""
    app.include_router(router)
    logger.info("Intelligent Advisor API routes registered at /api/advisor")
