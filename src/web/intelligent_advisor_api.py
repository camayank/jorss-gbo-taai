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

            # Create new session with FULL checkpoint support for multi-turn undo
            # This enables rolling back to ANY previous point in the conversation
            new_session = {
                "id": session_id,
                "created_at": datetime.now(),
                "profile": {},
                "conversation": [],  # [{role, content, timestamp}]
                "state": "greeting",
                "calculations": None,
                "strategies": [],
                "lead_score": 0,
                # Enhanced checkpoint system for multi-turn undo
                # Each checkpoint stores FULL state at that point
                "checkpoints": [],  # List of full checkpoint objects (see below)
                "current_turn": 0,
                "corrections_made": 0,
                # Checkpoint structure:
                # {
                #   "turn": N,
                #   "timestamp": ISO string,
                #   "user_message": "what user said",
                #   "extracted_fields": ["filing_status", "total_income"],  # What was extracted this turn
                #   "profile_snapshot": {full profile at this point},
                #   "conversation_length": N,  # How many messages existed
                #   "summary": "Single, $75k"  # Human-readable summary
                # }
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

    # =========================================================================
    # MULTI-TURN UNDO SYSTEM - Dynamic Checkpoint Management
    # =========================================================================

    def create_checkpoint(self, session_id: str, user_message: str, extracted_fields: List[str]) -> Dict[str, Any]:
        """
        Create a full checkpoint capturing the COMPLETE state at this turn.

        This enables rolling back to ANY previous point in the conversation,
        not just the last turn. Essential for handling "I made a mistake 5 turns ago".

        Args:
            session_id: Session identifier
            user_message: What the user said this turn
            extracted_fields: List of field names that were extracted/changed this turn

        Returns:
            The created checkpoint object
        """
        session = self.get_or_create_session(session_id)
        profile = session.get("profile", {})

        # Create human-readable summary
        summary = self._create_profile_summary(profile)

        checkpoint = {
            "turn": session.get("current_turn", 0),
            "timestamp": datetime.now().isoformat(),
            "user_message": user_message[:200],  # Truncate long messages
            "extracted_fields": extracted_fields,
            "profile_snapshot": profile.copy(),
            "conversation_length": len(session.get("conversation", [])),
            "summary": summary,
            "had_calculation": session.get("calculations") is not None
        }

        # Store checkpoint
        checkpoints = session.get("checkpoints", [])
        checkpoints.append(checkpoint)

        # Keep last 20 checkpoints for comprehensive undo
        if len(checkpoints) > 20:
            checkpoints = checkpoints[-20:]

        session["checkpoints"] = checkpoints
        session["current_turn"] = session.get("current_turn", 0) + 1

        # Persist
        self._save_session_to_db(session_id, session)

        return checkpoint

    def _create_profile_summary(self, profile: Dict[str, Any]) -> str:
        """Create a brief human-readable summary of the profile state."""
        parts = []

        if profile.get("filing_status"):
            status_map = {
                "single": "Single",
                "married_joint": "MFJ",
                "married_separate": "MFS",
                "head_of_household": "HoH",
                "qualifying_widow": "QW"
            }
            parts.append(status_map.get(profile["filing_status"], profile["filing_status"]))

        if profile.get("total_income"):
            income = profile["total_income"]
            if income >= 1000000:
                parts.append(f"${income/1000000:.1f}M")
            elif income >= 1000:
                parts.append(f"${income/1000:.0f}k")
            else:
                parts.append(f"${income:.0f}")

        if profile.get("state"):
            parts.append(profile["state"])

        if profile.get("dependents"):
            parts.append(f"{profile['dependents']} dep")

        return ", ".join(parts) if parts else "Empty"

    def get_undo_options(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get list of checkpoints the user can undo to.

        Returns a list of options showing what was said/changed at each turn,
        so user can pick where to roll back to.

        Returns:
            List of undo options with turn number, message, and changes
        """
        session = self.get_or_create_session(session_id)
        checkpoints = session.get("checkpoints", [])

        if not checkpoints:
            return []

        options = []
        for cp in reversed(checkpoints):  # Most recent first
            option = {
                "turn": cp["turn"],
                "message_preview": cp["user_message"][:50] + ("..." if len(cp["user_message"]) > 50 else ""),
                "fields_changed": cp["extracted_fields"],
                "profile_summary": cp["summary"],
                "timestamp": cp["timestamp"]
            }
            options.append(option)

        return options

    def undo_to_turn(self, session_id: str, target_turn: int) -> Dict[str, Any]:
        """
        Undo to a specific turn, restoring the profile state from BEFORE that turn.

        This removes all checkpoints from target_turn onwards and restores
        the profile to what it was before target_turn was processed.

        Args:
            session_id: Session identifier
            target_turn: The turn number to undo to (will restore state BEFORE this turn)

        Returns:
            Dict with:
                - success: bool
                - restored_profile: The profile state after undo
                - removed_turns: How many turns were undone
                - message: Human-readable result
        """
        session = self.get_or_create_session(session_id)
        checkpoints = session.get("checkpoints", [])

        if not checkpoints:
            return {
                "success": False,
                "message": "No history to undo.",
                "restored_profile": session.get("profile", {}),
                "removed_turns": 0
            }

        # Find the checkpoint BEFORE target_turn
        target_checkpoint = None
        checkpoints_to_keep = []

        for cp in checkpoints:
            if cp["turn"] < target_turn:
                checkpoints_to_keep.append(cp)
                target_checkpoint = cp

        if not target_checkpoint and target_turn > 0:
            # Undoing to turn 0 means reset to empty
            target_checkpoint = {
                "profile_snapshot": {},
                "summary": "Empty",
                "turn": 0
            }
            checkpoints_to_keep = []

        if target_checkpoint is None:
            return {
                "success": False,
                "message": f"Cannot find checkpoint before turn {target_turn}.",
                "restored_profile": session.get("profile", {}),
                "removed_turns": 0
            }

        # Calculate how many turns we're removing
        removed_turns = len(checkpoints) - len(checkpoints_to_keep)

        # Restore the profile
        restored_profile = target_checkpoint.get("profile_snapshot", {}).copy()

        # Update session
        session["profile"] = restored_profile
        session["checkpoints"] = checkpoints_to_keep
        session["current_turn"] = target_checkpoint.get("turn", 0)
        session["calculations"] = None  # Clear calculations - need recalculation
        session["strategies"] = []
        session["corrections_made"] = session.get("corrections_made", 0) + 1

        # Trim conversation history to match
        conv_length = target_checkpoint.get("conversation_length", 0)
        if conv_length > 0 and session.get("conversation"):
            session["conversation"] = session["conversation"][:conv_length]

        # Persist
        self._save_session_to_db(session_id, session)

        return {
            "success": True,
            "restored_profile": restored_profile,
            "removed_turns": removed_turns,
            "restored_to_turn": target_checkpoint.get("turn", 0),
            "profile_summary": target_checkpoint.get("summary", ""),
            "message": f"Rolled back {removed_turns} turn(s). Profile restored to: {target_checkpoint.get('summary', 'Empty')}"
        }

    def undo_last_turn(self, session_id: str) -> Dict[str, Any]:
        """Convenience method to undo just the last turn."""
        session = self.get_or_create_session(session_id)
        current_turn = session.get("current_turn", 0)

        if current_turn <= 0:
            return {
                "success": False,
                "message": "Nothing to undo.",
                "restored_profile": session.get("profile", {}),
                "removed_turns": 0
            }

        return self.undo_to_turn(session_id, current_turn)

    def get_conversation_history_for_undo(self, session_id: str) -> str:
        """
        Generate a formatted view of conversation history with turn numbers.

        This helps users identify which turn they want to undo to.
        """
        session = self.get_or_create_session(session_id)
        checkpoints = session.get("checkpoints", [])

        if not checkpoints:
            return "No conversation history yet."

        lines = ["**Your conversation history:**\n"]

        for cp in checkpoints:
            turn = cp["turn"]
            msg = cp["user_message"][:60] + ("..." if len(cp["user_message"]) > 60 else "")
            fields = ", ".join(cp["extracted_fields"]) if cp["extracted_fields"] else "no data"
            summary = cp["summary"]

            lines.append(f"**Turn {turn}**: \"{msg}\"")
            lines.append(f"   → Extracted: {fields}")
            lines.append(f"   → Profile: {summary}\n")

        lines.append("\n*Say \"undo to turn X\" to roll back to before that turn.*")

        return "\n".join(lines)

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

                # Sanity check: if income > 20k but federal_tax is 0, use fallback
                federal_tax_raw = breakdown.get("total_federal_tax", breakdown.get("federal_tax", 0))
                if income > 20000 and federal_tax_raw == 0:
                    logger.warning(f"Pipeline returned 0 tax for ${income} income, using fallback")
                    return self._fallback_calculation(profile)

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


def parse_user_message(message: str, current_profile: dict) -> dict:
    """
    Comprehensive parser for tax-relevant information from natural language.
    Handles all permutations of filing status, income, deductions, credits, etc.
    """
    import re
    msg_lower = message.lower().strip()
    msg_original = message.strip()
    updates = {}

    # =========================================================================
    # 1. FILING STATUS DETECTION (5 types with variations)
    # =========================================================================
    filing_patterns = {
        "single": [
            r"\bsingle\b", r"\bfiling\s*(as\s*)?single\b",
            r"\bi('m|am)\s*(filing\s*)?(as\s*)?single\b",
            r"\bnot\s*married\b", r"\bunmarried\b"
        ],
        "married_joint": [
            r"\bmarried\s*filing\s*joint", r"\bmarried\s*joint", r"\bmfj\b",
            r"\bjointly\b", r"\bmarried\b(?!.*separate)", r"\bwife\b", r"\bhusband\b",
            r"\bspouse\b(?!.*separate)", r"\bwe\s*(file|are)\s*together\b"
        ],
        "married_separate": [
            r"\bmarried\s*filing\s*separate", r"\bmarried\s*separate", r"\bmfs\b",
            r"\bseparately\b", r"\bfile\s*separate", r"\bown\s*return\b"
        ],
        "head_of_household": [
            r"\bhead\s*of\s*household\b", r"\bhoh\b", r"\bhead\s*household\b",
            r"\bsingle\s*(parent|mom|dad)\b", r"\bunmarried\s*with\s*(kid|child|dependent)\b"
        ],
        "qualifying_widow": [
            r"\bqualifying\s*widow", r"\bsurviving\s*spouse\b", r"\bwidow(er)?\b",
            r"\bspouse\s*(died|passed|deceased)\b"
        ]
    }
    for status, patterns in filing_patterns.items():
        for pattern in patterns:
            if re.search(pattern, msg_lower):
                updates["filing_status"] = status
                break
        if "filing_status" in updates:
            break

    # =========================================================================
    # 2. INCOME DETECTION (Multiple types and formats)
    # =========================================================================

    # Direct dollar amounts with various formats
    income_patterns = [
        r'\$\s*([\d,]+(?:\.\d{2})?)\s*(?:k|K|thousand)?',  # $50,000 or $50k
        r'([\d,]+(?:\.\d{2})?)\s*(?:k|K|thousand)\b',  # 50k, 150K
        r'(?:make|earn|income|salary|gross|net|about|around|approximately)\s*(?:is|of|:)?\s*\$?\s*([\d,]+)',
        r'(?:with|have)\s*(?:an?\s*)?income\s*(?:of|:)?\s*\$?\s*([\d,]+)',  # "with income of 75000"
        r'([\d,]+)\s*(?:per\s*year|annually|a\s*year|yearly)',
    ]

    for pattern in income_patterns:
        match = re.search(pattern, msg_original, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                amount = float(amount_str)
                # Handle 'k' suffix
                if re.search(r'\d\s*[kK]\b', msg_original):
                    if amount < 1000:  # 50k means 50,000 not 50000k
                        amount *= 1000
                # Reasonable income range
                if 1000 <= amount <= 100000000:
                    updates["total_income"] = amount
                    break
            except ValueError:
                pass

    # Income range detection
    income_ranges = {
        25000: [r"under\s*\$?50", r"less\s*than\s*\$?50", r"below\s*\$?50"],
        75000: [r"\$?50.*\$?100", r"50\s*to\s*100", r"between\s*50.*100"],
        150000: [r"\$?100.*\$?200", r"100\s*to\s*200", r"between\s*100.*200"],
        350000: [r"\$?200.*\$?500", r"200\s*to\s*500", r"few\s*hundred\s*thousand"],
        750000: [r"\$?500.*\$?1\s*m", r"half\s*million", r"500\s*to.*million"],
        1500000: [r"over\s*(a\s*)?million", r"more\s*than.*million", r"1\s*m\+"],
    }
    if "total_income" not in updates:
        for amount, patterns in income_ranges.items():
            for pattern in patterns:
                if re.search(pattern, msg_lower):
                    updates["total_income"] = amount
                    break

    # =========================================================================
    # 3. INCOME TYPE DETECTION
    # =========================================================================

    # W-2 Employment
    if re.search(r'\bw-?2\b|\bemployee\b|\bsalaried\b|\bwages\b', msg_lower):
        updates["income_type"] = "w2"
        updates["is_self_employed"] = False

    # Self-Employment / Business
    if re.search(r'\bself[- ]?employ|\b1099\b|\bfreelance|\bcontractor|\bgig\b|\buber\b|\blyft\b|\bside\s*(hustle|business|gig)', msg_lower):
        updates["is_self_employed"] = True
        updates["income_type"] = "self_employed"

    # Business income amount
    biz_match = re.search(r'(?:business|self[- ]?employ|1099|freelance)\s*(?:income|earn|make|revenue)?\s*(?:of\s*)?\$?\s*([\d,]+)', msg_lower)
    if biz_match:
        try:
            updates["business_income"] = float(biz_match.group(1).replace(',', ''))
        except ValueError:
            pass

    # Rental Income
    if re.search(r'\brental|\bland\s*lord|\bproperty\s*income|\btenant', msg_lower):
        updates["has_rental_income"] = True
        rental_match = re.search(r'rental\s*(?:income)?\s*(?:of\s*)?\$?\s*([\d,]+)', msg_lower)
        if rental_match:
            try:
                updates["rental_income"] = float(rental_match.group(1).replace(',', ''))
            except ValueError:
                pass

    # Investment Income
    if re.search(r'\binvestment|\bdividend|\bcapital\s*gain|\bstock|\bcrypto|\btrading', msg_lower):
        updates["has_investment_income"] = True
        inv_match = re.search(r'(?:investment|dividend|capital\s*gain)\s*(?:income)?\s*(?:of\s*)?\$?\s*([\d,]+)', msg_lower)
        if inv_match:
            try:
                updates["investment_income"] = float(inv_match.group(1).replace(',', ''))
            except ValueError:
                pass

    # Retirement Income
    if re.search(r'\bretired|\bpension|\bsocial\s*security|\b401k\s*withdraw|\bira\s*distribut', msg_lower):
        updates["has_retirement_income"] = True

    # =========================================================================
    # 4. STATE DETECTION (All 50 + DC)
    # =========================================================================
    # Full state names (safe to check without word boundaries)
    full_state_names = {
        "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
        "california": "CA", "cali": "CA", "colorado": "CO", "connecticut": "CT",
        "delaware": "DE", "florida": "FL", "georgia": "GA", "hawaii": "HI",
        "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
        "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME",
        "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
        "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
        "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM",
        "new york": "NY", "nyc": "NY", "north carolina": "NC", "north dakota": "ND",
        "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
        "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
        "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
        "virginia": "VA", "washington": "WA", "west virginia": "WV",
        "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC", "washington dc": "DC"
    }
    # Two-letter state abbreviations (need word boundaries)
    state_abbrevs = {
        "al": "AL", "ak": "AK", "az": "AZ", "ar": "AR", "ca": "CA", "co": "CO",
        "ct": "CT", "de": "DE", "fl": "FL", "ga": "GA", "hi": "HI", "id": "ID",
        "il": "IL", "ia": "IA", "ks": "KS", "ky": "KY", "la": "LA",
        "me": "ME", "md": "MD", "ma": "MA", "mi": "MI", "mn": "MN", "ms": "MS",
        "mo": "MO", "mt": "MT", "ne": "NE", "nv": "NV", "nh": "NH", "nj": "NJ",
        "nm": "NM", "ny": "NY", "nc": "NC", "nd": "ND", "oh": "OH", "ok": "OK",
        "pa": "PA", "ri": "RI", "sc": "SC", "sd": "SD", "tn": "TN",
        "tx": "TX", "ut": "UT", "vt": "VT", "va": "VA", "wa": "WA", "wv": "WV",
        "wi": "WI", "wy": "WY", "dc": "DC", "d.c.": "DC"
    }
    # Exclude common words that conflict with state abbreviations
    # (in, or, me, ok, hi, la, ma, pa, oh, co, de, id, ne, md, al, ar, ak)
    # Check longer names first to avoid partial matches
    for state_name in sorted(full_state_names.keys(), key=len, reverse=True):
        if state_name in msg_lower:
            updates["state"] = full_state_names[state_name]
            break
    # If no full name found, check abbreviations with word boundaries
    if "state" not in updates:
        for abbrev, code in state_abbrevs.items():
            # Use word boundaries to avoid matching inside words
            # Also require context like "in", "from", "live", "state" nearby
            pattern = rf'\b{re.escape(abbrev)}\b'
            if re.search(pattern, msg_lower):
                # Additional check: must have location context or be standalone
                context_pattern = rf'(?:in|from|live|state|resident|living)\s+{re.escape(abbrev)}\b|\b{re.escape(abbrev)}\s+(?:state|resident)'
                if re.search(context_pattern, msg_lower) or re.search(rf'^{re.escape(abbrev)}$', msg_lower.strip()):
                    updates["state"] = code
                    break

    # =========================================================================
    # 5. DEPENDENTS DETECTION
    # =========================================================================
    word_to_num = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                   "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}

    # Numeric patterns
    dep_match = re.search(r'(\d+)\s*(?:dependent|child|kid|children|minor)', msg_lower)
    if dep_match:
        updates["dependents"] = min(int(dep_match.group(1)), 20)  # Cap at 20
    else:
        # Word patterns
        for word, num in word_to_num.items():
            if re.search(rf'\b{word}\s*(?:dependent|child|kid|children)', msg_lower):
                updates["dependents"] = num
                break

    # No dependents
    if re.search(r'\bno\s*(?:dependent|child|kid)|don\'t\s*have\s*(?:any\s*)?(?:kid|child|dependent)|childless', msg_lower):
        updates["dependents"] = 0

    # =========================================================================
    # 6. DEDUCTION DETECTION
    # =========================================================================

    # Mortgage interest
    mort_match = re.search(r'mortgage\s*(?:interest)?\s*(?:of\s*)?\$?\s*([\d,]+)', msg_lower)
    if mort_match:
        try:
            updates["mortgage_interest"] = float(mort_match.group(1).replace(',', ''))
        except ValueError:
            pass
    elif re.search(r'\bmortgage\b|\bhome\s*loan\b|\bhomeowner\b', msg_lower):
        updates["has_mortgage"] = True

    # Property tax
    prop_match = re.search(r'property\s*tax\s*(?:of\s*)?\$?\s*([\d,]+)', msg_lower)
    if prop_match:
        try:
            updates["property_taxes"] = float(prop_match.group(1).replace(',', ''))
        except ValueError:
            pass

    # Charitable donations
    char_match = re.search(r'(?:donat|charit|contribut)\w*\s*(?:of\s*)?\$?\s*([\d,]+)', msg_lower)
    if char_match:
        try:
            updates["charitable_donations"] = float(char_match.group(1).replace(',', ''))
        except ValueError:
            pass
    elif re.search(r'\bdonat|\bcharit|\bcontribut|\btithe|\bgive\s*to\s*church', msg_lower):
        updates["has_charitable"] = True

    # Medical expenses
    med_match = re.search(r'medical\s*(?:expense)?\s*(?:of\s*)?\$?\s*([\d,]+)', msg_lower)
    if med_match:
        try:
            updates["medical_expenses"] = float(med_match.group(1).replace(',', ''))
        except ValueError:
            pass

    # Student loan interest
    student_match = re.search(r'student\s*loan\s*(?:interest)?\s*(?:of\s*)?\$?\s*([\d,]+)', msg_lower)
    if student_match:
        try:
            updates["student_loan_interest"] = min(float(student_match.group(1).replace(',', '')), 2500)
        except ValueError:
            pass
    elif re.search(r'\bstudent\s*loan\b', msg_lower):
        updates["has_student_loans"] = True

    # =========================================================================
    # 7. RETIREMENT CONTRIBUTIONS
    # =========================================================================

    # 401k
    k401_match = re.search(r'401\s*k?\s*(?:contribut)?\s*(?:of\s*)?\$?\s*([\d,]+)', msg_lower)
    if k401_match:
        try:
            updates["retirement_401k"] = min(float(k401_match.group(1).replace(',', '')), 30500)
        except ValueError:
            pass
    elif re.search(r'\b401\s*k\b', msg_lower):
        updates["has_401k"] = True

    # IRA
    ira_match = re.search(r'(?:traditional\s*)?ira\s*(?:contribut)?\s*(?:of\s*)?\$?\s*([\d,]+)', msg_lower)
    if ira_match:
        try:
            updates["retirement_ira"] = min(float(ira_match.group(1).replace(',', '')), 8000)
        except ValueError:
            pass

    # HSA
    hsa_match = re.search(r'hsa\s*(?:contribut)?\s*(?:of\s*)?\$?\s*([\d,]+)', msg_lower)
    if hsa_match:
        try:
            updates["hsa_contributions"] = min(float(hsa_match.group(1).replace(',', '')), 8550)
        except ValueError:
            pass
    elif re.search(r'\bhsa\b|\bhealth\s*savings\b', msg_lower):
        updates["has_hsa"] = True

    # =========================================================================
    # 8. LIFE EVENTS
    # =========================================================================

    if re.search(r'\bgot\s*married|\bjust\s*married|\bnewlywed|\bwedding\s*this\s*year', msg_lower):
        updates["life_event"] = "married"
    elif re.search(r'\bdivorc|\bseparat|\bsplit\s*up', msg_lower):
        updates["life_event"] = "divorced"
    elif re.search(r'\bnew\s*baby|\bhad\s*a\s*(baby|child)|\bbaby\s*born|\bnewborn', msg_lower):
        updates["life_event"] = "new_baby"
        if "dependents" not in updates:
            updates["dependents"] = current_profile.get("dependents", 0) + 1
    elif re.search(r'\bbought\s*a?\s*house|\bhome\s*purchase|\bnew\s*home\s*owner|\bfirst\s*time\s*buyer', msg_lower):
        updates["life_event"] = "home_purchase"
        updates["has_mortgage"] = True
    elif re.search(r'\bsold\s*(my\s*)?(house|home)|\bhome\s*sale', msg_lower):
        updates["life_event"] = "home_sale"
    elif re.search(r'\bretir|\bstopped\s*working|\bleft\s*(my\s*)?job.*retire', msg_lower):
        updates["life_event"] = "retired"
    elif re.search(r'\bnew\s*job|\bchanged\s*job|\bswitch.*employ|\bstart.*new\s*position', msg_lower):
        updates["life_event"] = "job_change"
    elif re.search(r'\blost\s*(my\s*)?job|\bunemploy|\blaid\s*off|\bfired', msg_lower):
        updates["life_event"] = "job_loss"
        updates["has_unemployment"] = True

    # =========================================================================
    # 9. YES/NO RESPONSE HANDLING
    # =========================================================================

    yes_patterns = [r'\byes\b', r'\byeah\b', r'\byep\b', r'\bsure\b', r'\bcorrect\b',
                    r'\bthat\'s\s*right\b', r'\baffirmative\b', r'\bi\s*do\b', r'\bi\s*have\b']
    no_patterns = [r'\bno\b', r'\bnope\b', r'\bnah\b', r'\bnegative\b', r'\bi\s*don\'t\b',
                   r'\bi\s*do\s*not\b', r'\bnone\b', r'\bnothing\b']

    is_yes = any(re.search(p, msg_lower) for p in yes_patterns)
    is_no = any(re.search(p, msg_lower) for p in no_patterns)

    if is_yes or is_no:
        updates["_response_type"] = "yes" if is_yes else "no"

    # =========================================================================
    # 10. AGE DETECTION
    # =========================================================================

    age_match = re.search(r'(?:i\'m|i\s*am|age)\s*(\d{2})\s*(?:years?\s*old)?', msg_lower)
    if age_match:
        age = int(age_match.group(1))
        if 18 <= age <= 100:
            updates["age"] = age

    # Over 65 check
    if re.search(r'\bsenior\b|\bover\s*65\b|\bretire[ed]|\belderly\b', msg_lower):
        updates["age"] = max(current_profile.get("age", 65), 65)

    # =========================================================================
    # 11. CORRECTION DETECTION - Detect when user is changing previous answers
    # =========================================================================

    correction_patterns = [
        r'\bactually\b', r'\bi\s*meant\b', r'\bcorrection\b', r'\bsorry\b.*\bwrong\b',
        r'\blet\s*me\s*correct\b', r'\bthat\s*was\s*wrong\b', r'\bi\s*made\s*a\s*mistake\b',
        r'\bchange\s*(that|my|it)\b', r'\bnot\s*\w+\s*but\b', r'\bwait\b.*\bactually\b',
        r'\bundo\b', r'\bgo\s*back\b', r'\bstart\s*over\b', r'\breset\b',
        r'\binstead\s*of\b', r'\brather\b.*\bthan\b'
    ]

    is_correction = any(re.search(p, msg_lower) for p in correction_patterns)
    if is_correction:
        updates["_is_correction"] = True

    # Detect explicit contradictions with current profile
    if current_profile.get("filing_status") and "filing_status" in updates:
        if current_profile["filing_status"] != updates["filing_status"]:
            updates["_is_correction"] = True
            updates["_changed_field"] = "filing_status"

    if current_profile.get("total_income") and "total_income" in updates:
        # If income changed by more than 20%, likely a correction
        old_income = current_profile["total_income"]
        new_income = updates["total_income"]
        if abs(new_income - old_income) / max(old_income, 1) > 0.2:
            updates["_is_correction"] = True
            updates["_changed_field"] = "total_income"

    return updates


# =============================================================================
# ENHANCED PARSING SYSTEM - Robustness Layer
# =============================================================================
# This module adds:
# 1. Confidence scoring for extracted values
# 2. Fuzzy matching for typos
# 3. Word-to-number conversion
# 4. Validation with helpful feedback
# 5. Conflict detection
# 6. Field-specific undo
# 7. Contextual follow-ups
# =============================================================================

class EnhancedParser:
    """
    Enhanced parsing layer that wraps parse_user_message with robustness features.
    """

    # Fuzzy matching dictionaries for common typos
    FILING_STATUS_FUZZY = {
        # Single variations
        "singl": "single", "singel": "single", "singe": "single", "sngle": "single",
        "unmaried": "single", "unmmaried": "single", "not maried": "single",
        # Married joint variations
        "maried": "married_joint", "marred": "married_joint", "marriedjoint": "married_joint",
        "mfj": "married_joint", "jointly": "married_joint", "joint": "married_joint",
        "maried jointly": "married_joint", "married jointley": "married_joint",
        # Married separate variations
        "mfs": "married_separate", "seperately": "married_separate", "seperate": "married_separate",
        "married seperately": "married_separate", "maried seperate": "married_separate",
        # Head of household variations
        "hoh": "head_of_household", "headofhousehold": "head_of_household",
        "head of houshold": "head_of_household", "head of householde": "head_of_household",
        "head of the household": "head_of_household", "household head": "head_of_household",
        # Qualifying widow variations
        "widow": "qualifying_widow", "widower": "qualifying_widow",
        "surviving spouse": "qualifying_widow", "qw": "qualifying_widow",
    }

    STATE_FUZZY = {
        # Common misspellings
        "califronia": "CA", "californai": "CA", "calfornia": "CA", "cali": "CA",
        "newyork": "NY", "new yourk": "NY", "neew york": "NY",
        "texs": "TX", "texaz": "TX", "teaxs": "TX",
        "florda": "FL", "flordia": "FL", "fla": "FL",
        "illinos": "IL", "illinoise": "IL", "ilinois": "IL",
        "pensylvania": "PA", "pennsilvania": "PA", "penn": "PA",
        "massachusets": "MA", "massachussetts": "MA", "mass": "MA",
        "conneticut": "CT", "conecticut": "CT", "conn": "CT",
        "washingon": "WA", "wahsington": "WA",
        "arizonia": "AZ", "arizone": "AZ",
        "colrado": "CO", "colorodo": "CO",
        "michgan": "MI", "michagan": "MI",
        "minnestoa": "MN", "minesota": "MN",
        "georiga": "GA", "goergia": "GA",
        "virgina": "VA", "virgnia": "VA",
        "north carolna": "NC", "north carlina": "NC",
        "south carolna": "SC", "south carlina": "SC",
    }

    # Word-to-number mappings
    WORD_NUMBERS = {
        "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
        "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
        "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
        "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
        "hundred": 100, "thousand": 1000, "million": 1000000, "billion": 1000000000,
        "k": 1000, "m": 1000000, "mil": 1000000,
    }

    # Confidence thresholds
    HIGH_CONFIDENCE = 0.9
    MEDIUM_CONFIDENCE = 0.7
    LOW_CONFIDENCE = 0.5
    CONFIRMATION_THRESHOLD = 0.75  # Ask for confirmation below this

    @classmethod
    def words_to_number(cls, text: str) -> tuple:
        """
        Convert word-based numbers to numeric values.

        Examples:
            "one hundred fifty thousand" -> (150000, 0.95)
            "seventy five K" -> (75000, 0.9)
            "two point five million" -> (2500000, 0.9)

        Returns:
            (number, confidence) or (None, 0) if no number found
        """
        import re
        text_lower = text.lower().strip()

        # Handle "X point Y" patterns (e.g., "two point five million")
        point_match = re.search(
            r'(\w+)\s+point\s+(\w+)\s*(hundred|thousand|k|million|m|mil|billion)?',
            text_lower
        )
        if point_match:
            whole = cls.WORD_NUMBERS.get(point_match.group(1), 0)
            decimal = cls.WORD_NUMBERS.get(point_match.group(2), 0)
            multiplier_word = point_match.group(3) or ""
            multiplier = cls.WORD_NUMBERS.get(multiplier_word, 1)

            if whole > 0 or decimal > 0:
                # Convert decimal part (e.g., "five" -> 0.5)
                decimal_value = decimal / 10 if decimal < 10 else decimal / 100
                result = (whole + decimal_value) * multiplier
                return (result, 0.85)

        # Handle compound word numbers
        # Pattern: [number words] [multiplier]
        # E.g., "one hundred fifty thousand", "seventy five k"

        # First, try to find multiplier
        multiplier = 1
        multiplier_confidence = 1.0
        for word, value in [("billion", 1e9), ("million", 1e6), ("mil", 1e6), ("m", 1e6),
                            ("thousand", 1e3), ("k", 1e3)]:
            if re.search(rf'\b{word}\b', text_lower):
                multiplier = value
                # Remove multiplier from text for further processing
                text_lower = re.sub(rf'\b{word}\b', '', text_lower)
                break

        # Parse remaining number words
        words = text_lower.split()
        number = 0
        current = 0
        found_number = False

        for word in words:
            word = word.strip(',$.')
            if word in cls.WORD_NUMBERS:
                found_number = True
                val = cls.WORD_NUMBERS[word]
                if val == 100:
                    current = (current if current else 1) * 100
                elif val >= 1000:
                    current = (current if current else 1) * val
                    number += current
                    current = 0
                else:
                    current += val
            elif word.isdigit():
                found_number = True
                current += int(word)

        number += current

        if found_number and number > 0:
            result = number * multiplier
            # Confidence based on complexity of parsing
            confidence = 0.9 if multiplier == 1 else 0.85
            return (result, confidence)

        return (None, 0)

    @classmethod
    def fuzzy_match_filing_status(cls, text: str) -> tuple:
        """
        Fuzzy match filing status with confidence score.

        Returns:
            (filing_status, confidence) or (None, 0)
        """
        import re
        text_lower = text.lower().strip()

        # First try exact matches (high confidence)
        exact_patterns = {
            "single": (r'\bsingle\b', 0.95),
            "married_joint": (r'\bmarried\s*filing\s*joint', 0.98),
            "married_separate": (r'\bmarried\s*filing\s*separate', 0.98),
            "head_of_household": (r'\bhead\s*of\s*household\b', 0.98),
            "qualifying_widow": (r'\bqualifying\s*widow', 0.95),
        }

        for status, (pattern, confidence) in exact_patterns.items():
            if re.search(pattern, text_lower):
                return (status, confidence)

        # Try fuzzy matches (lower confidence)
        for typo, correct_status in cls.FILING_STATUS_FUZZY.items():
            if typo in text_lower:
                return (correct_status, 0.75)  # Lower confidence for fuzzy

        return (None, 0)

    @classmethod
    def fuzzy_match_state(cls, text: str) -> tuple:
        """
        Fuzzy match state with confidence score.

        Returns:
            (state_code, confidence) or (None, 0)
        """
        text_lower = text.lower().strip()

        # Check fuzzy matches first
        for typo, correct_state in cls.STATE_FUZZY.items():
            if typo in text_lower:
                return (correct_state, 0.80)  # Medium confidence for typo correction

        return (None, 0)

    @classmethod
    def detect_ambiguous_amounts(cls, text: str) -> list:
        """
        Detect potentially ambiguous amounts that need confirmation.

        Returns list of (amount, interpretation, confidence) tuples
        """
        import re
        ambiguous = []
        text_lower = text.lower()

        # Pattern: bare number without context (e.g., "150" could be $150 or $150,000)
        bare_number = re.search(r'\b(\d{2,3})\b(?!\s*[kK%])', text)
        if bare_number:
            num = int(bare_number.group(1))
            if 50 <= num <= 999:  # Ambiguous range
                ambiguous.append({
                    "value": num,
                    "interpretations": [
                        {"amount": num, "meaning": f"${num:,}"},
                        {"amount": num * 1000, "meaning": f"${num * 1000:,}"}
                    ],
                    "context": "bare_number",
                    "confidence": 0.5
                })

        # Hedging words reduce confidence
        hedging = ["about", "around", "approximately", "roughly", "maybe", "probably",
                   "i think", "not sure", "something like", "somewhere around"]
        for hedge in hedging:
            if hedge in text_lower:
                ambiguous.append({
                    "type": "hedging_detected",
                    "word": hedge,
                    "confidence_reduction": 0.15
                })
                break

        return ambiguous

    @classmethod
    def validate_extracted_data(cls, extracted: dict, current_profile: dict) -> dict:
        """
        Validate extracted data and return warnings/suggestions.

        Returns:
            {
                "valid": bool,
                "warnings": [...],
                "suggestions": [...],
                "auto_corrections": {...}
            }
        """
        result = {
            "valid": True,
            "warnings": [],
            "suggestions": [],
            "auto_corrections": {}
        }

        # Validate income
        income = extracted.get("total_income")
        if income is not None:
            if income < 0:
                result["warnings"].append({
                    "field": "total_income",
                    "message": "Income cannot be negative.",
                    "suggestion": "Please enter a positive income amount."
                })
                result["auto_corrections"]["total_income"] = abs(income)  # Auto-correct to positive
                result["valid"] = False
            elif income < 100:
                result["warnings"].append({
                    "field": "total_income",
                    "message": f"${income:,.0f} seems very low for annual income.",
                    "suggestion": f"Did you mean ${income * 1000:,.0f}?",
                    "possible_correction": income * 1000
                })
                result["valid"] = False
            elif income > 50000000:
                result["warnings"].append({
                    "field": "total_income",
                    "message": f"${income:,.0f} is unusually high.",
                    "suggestion": "Please confirm this is correct."
                })

        # Validate dependents
        dependents = extracted.get("dependents")
        if dependents is not None:
            if dependents > 10:
                result["warnings"].append({
                    "field": "dependents",
                    "message": f"{dependents} dependents is unusual.",
                    "suggestion": "Please confirm the number of dependents."
                })
            elif dependents < 0:
                result["auto_corrections"]["dependents"] = 0
                result["warnings"].append({
                    "field": "dependents",
                    "message": "Dependents cannot be negative. Set to 0.",
                })

        # Check for conflicts with current profile
        if current_profile.get("filing_status") == "single" and extracted.get("dependents", 0) > 0:
            if not extracted.get("filing_status"):
                result["suggestions"].append({
                    "message": "You're filing as Single but have dependents. Would Head of Household be more beneficial?",
                    "action": "consider_hoh"
                })

        # Check spouse-related conflicts
        if extracted.get("filing_status") == "single":
            spouse_words = ["spouse", "wife", "husband", "married"]
            # This would need the original message - handled in enhanced_parse

        return result

    @classmethod
    def detect_field_specific_undo(cls, message: str) -> dict:
        """
        Detect if user wants to change a specific field.

        Examples:
            "change my income to 90000" -> {"field": "total_income", "new_value": 90000}
            "fix my state to Texas" -> {"field": "state", "new_value": "TX"}
            "my filing status should be single" -> {"field": "filing_status", "new_value": "single"}

        Returns:
            {"field": field_name, "new_value": value} or None
        """
        import re
        msg_lower = message.lower().strip()

        # Helper function to parse income with k/K suffix
        def parse_income_value(text: str) -> float:
            text = text.replace(',', '').strip()
            if text.lower().endswith('k'):
                return float(text[:-1]) * 1000
            return float(text)

        # Patterns for field-specific changes
        # NOTE: These patterns should ONLY match when there's clear correction intent
        # (change, update, fix, correct, actually, meant, sorry, no wait)
        # Regular inputs like "my income is 75" should NOT match here
        field_patterns = [
            # Income changes - explicit correction verbs
            (r'(?:change|update|fix|correct)\s*(?:my\s*)?income\s*(?:to|is|should\s*be)\s*\$?([\d,]+k?)',
             "total_income", lambda m: parse_income_value(m.group(1))),
            # Income - "meant to say" pattern
            (r'(?:i\s*)?meant\s*(?:to\s*say|it\'s)\s*\$?([\d,]+k?)(?:\s*(?:for|as)\s*income)?',
             "total_income", lambda m: parse_income_value(m.group(1))),
            # Income - "actually/sorry/no wait" patterns (correction intent)
            (r'(?:actually|no\s*wait|sorry)\s*(?:it\'?s?|my\s*income\s*is)?\s*\$?([\d,]+k?)(?:\s*(?:for|as)?\s*(?:my\s*)?income)?',
             "total_income", lambda m: parse_income_value(m.group(1))),

            # Filing status changes
            (r'(?:change|update|fix|correct)\s*(?:my\s*)?(?:filing\s*)?status\s*(?:to|is|should\s*be)\s*(\w+)',
             "filing_status", lambda m: cls._normalize_filing_status(m.group(1))),
            (r'(?:i\s*)?(?:am|should\s*be)\s*(?:filing\s*(?:as\s*)?)?(\w+)(?:\s*not\s*\w+)?',
             "filing_status", lambda m: cls._normalize_filing_status(m.group(1))),

            # State changes - standard patterns
            (r'(?:change|update|fix|correct)\s*(?:my\s*)?state\s*(?:to|is|should\s*be)\s*(\w+(?:\s+\w+)?)',
             "state", lambda m: cls._normalize_state(m.group(1))),
            (r'(?:i\s*)?(?:live|moved)\s*(?:in|to)\s*(\w+(?:\s+\w+)?)',
             "state", lambda m: cls._normalize_state(m.group(1))),
            # State - "actually my state is X" pattern
            (r'(?:actually|no\s*wait|sorry)\s*(?:my\s*)?state\s*(?:is|should\s*be)\s*(\w+(?:\s+\w+)?)',
             "state", lambda m: cls._normalize_state(m.group(1))),

            # Dependents changes
            (r'(?:change|update|fix|correct)\s*(?:my\s*)?(?:number\s*of\s*)?dependents?\s*(?:to|is|should\s*be)\s*(\d+)',
             "dependents", lambda m: int(m.group(1))),
            (r'(?:i\s*)?have\s*(\d+)\s*(?:kids?|children|dependents?)',
             "dependents", lambda m: int(m.group(1))),
        ]

        for pattern, field, extractor in field_patterns:
            match = re.search(pattern, msg_lower)
            if match:
                try:
                    value = extractor(match)
                    if value is not None:
                        return {"field": field, "new_value": value, "confidence": 0.85}
                except (ValueError, AttributeError):
                    pass

        return None

    @classmethod
    def _normalize_filing_status(cls, status_text: str) -> str:
        """Normalize filing status text to standard values."""
        status_lower = status_text.lower().strip()
        status_map = {
            "single": "single",
            "married": "married_joint",
            "joint": "married_joint",
            "jointly": "married_joint",
            "separate": "married_separate",
            "separately": "married_separate",
            "hoh": "head_of_household",
            "head": "head_of_household",
            "household": "head_of_household",
            "widow": "qualifying_widow",
            "widower": "qualifying_widow",
        }
        return status_map.get(status_lower)

    @classmethod
    def _normalize_state(cls, state_text: str) -> str:
        """Normalize state text to standard 2-letter code."""
        # Full state name mapping
        state_names = {
            "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
            "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
            "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
            "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
            "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
            "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
            "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
            "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
            "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
            "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
            "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
            "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
            "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
        }

        state_lower = state_text.lower().strip()

        # Check full names first
        if state_lower in state_names:
            return state_names[state_lower]

        # Check if it's already a valid 2-letter code
        if len(state_lower) == 2 and state_lower.upper() in state_names.values():
            return state_lower.upper()

        # Check fuzzy matches
        fuzzy_result, _ = EnhancedParser.fuzzy_match_state(state_text)
        return fuzzy_result

    @classmethod
    def detect_conflicts(cls, message: str, extracted: dict, current_profile: dict) -> list:
        """
        Detect conflicting information in the message or with current profile.

        Returns list of conflict descriptions.
        """
        conflicts = []
        msg_lower = message.lower()

        # Single but mentions spouse
        if extracted.get("filing_status") == "single" or current_profile.get("filing_status") == "single":
            spouse_indicators = ["spouse", "wife", "husband", "we file", "our income", "my partner"]
            for indicator in spouse_indicators:
                if indicator in msg_lower:
                    conflicts.append({
                        "type": "status_spouse_conflict",
                        "message": f"You mentioned '{indicator}' but filing status is Single.",
                        "question": "Are you married? Would Married Filing Jointly be correct?",
                        "options": [
                            {"label": "Yes, I'm married", "value": "married_joint"},
                            {"label": "No, I'm single", "value": "single"}
                        ]
                    })
                    break

        # Head of Household but no dependents mentioned
        if extracted.get("filing_status") == "head_of_household":
            if current_profile.get("dependents") == 0 and not extracted.get("dependents"):
                conflicts.append({
                    "type": "hoh_no_dependents",
                    "message": "Head of Household typically requires a qualifying dependent.",
                    "question": "Do you have dependents living with you?",
                    "options": [
                        {"label": "Yes, I have dependents", "value": "has_dependents"},
                        {"label": "No dependents", "value": "reconsider_status"}
                    ]
                })

        # Income type conflicts
        if extracted.get("is_self_employed") and current_profile.get("income_type") == "w2":
            conflicts.append({
                "type": "income_type_change",
                "message": "You previously indicated W-2 employment but now mention self-employment.",
                "question": "Do you have both W-2 and self-employment income?",
                "options": [
                    {"label": "Yes, both", "value": "mixed_income"},
                    {"label": "Only self-employed now", "value": "self_employed_only"},
                    {"label": "Only W-2", "value": "w2_only"}
                ]
            })

        return conflicts


def enhanced_parse_user_message(message: str, current_profile: dict, session: dict = None) -> dict:
    """
    Enhanced wrapper around parse_user_message that adds:
    - Confidence scoring
    - Fuzzy matching
    - Word-to-number conversion
    - Validation
    - Conflict detection
    - Field-specific undo detection

    Returns:
        {
            "extracted": {...},           # Standard extracted data
            "confidence": {...},          # Confidence scores per field
            "needs_confirmation": [...],  # Fields needing confirmation
            "warnings": [...],            # Validation warnings
            "suggestions": [...],         # Helpful suggestions
            "conflicts": [...],           # Detected conflicts
            "field_update": {...},        # If field-specific update detected
            "ambiguous": [...],           # Ambiguous values detected
        }
    """
    import re

    result = {
        "extracted": {},
        "confidence": {},
        "needs_confirmation": [],
        "warnings": [],
        "suggestions": [],
        "conflicts": [],
        "field_update": None,
        "ambiguous": [],
    }

    msg_lower = message.lower().strip()

    # 0. Check for negative income (special case - standard parser won't catch this)
    neg_income_match = re.search(r'income\s*(?:is|of|:)?\s*-\$?\s*([\d,]+)', msg_lower)
    if neg_income_match:
        neg_value = float(neg_income_match.group(1).replace(',', ''))
        result["extracted"]["total_income"] = neg_value  # Auto-correct to positive
        result["warnings"].append({
            "field": "total_income",
            "message": "Income cannot be negative.",
            "suggestion": f"I've corrected this to ${neg_value:,.0f}."
        })
        result["confidence"]["total_income"] = 0.8
        # Don't return early - continue processing for other fields

    # 1. Check for field-specific update first
    field_update = EnhancedParser.detect_field_specific_undo(message)
    if field_update:
        result["field_update"] = field_update
        result["extracted"][field_update["field"]] = field_update["new_value"]
        result["confidence"][field_update["field"]] = field_update.get("confidence", 0.85)
        return result

    # 2. Try word-to-number conversion for income
    word_num, word_conf = EnhancedParser.words_to_number(message)
    if word_num and word_num >= 1000:  # Likely income
        result["extracted"]["total_income"] = word_num
        result["confidence"]["total_income"] = word_conf
        if word_conf < EnhancedParser.CONFIRMATION_THRESHOLD:
            result["needs_confirmation"].append({
                "field": "total_income",
                "value": word_num,
                "message": f"Just to confirm - is your annual income ${word_num:,.0f}?"
            })

    # 3. Run standard parser
    standard_extracted = parse_user_message(message, current_profile)

    # 4. Check for fuzzy matches on any fields the standard parser missed
    if "filing_status" not in standard_extracted:
        fuzzy_status, status_conf = EnhancedParser.fuzzy_match_filing_status(message)
        if fuzzy_status:
            standard_extracted["filing_status"] = fuzzy_status
            result["confidence"]["filing_status"] = status_conf
            if status_conf < EnhancedParser.CONFIRMATION_THRESHOLD:
                result["needs_confirmation"].append({
                    "field": "filing_status",
                    "value": fuzzy_status,
                    "message": f"I understood your filing status as '{fuzzy_status.replace('_', ' ').title()}'. Is that correct?"
                })

    if "state" not in standard_extracted:
        fuzzy_state, state_conf = EnhancedParser.fuzzy_match_state(message)
        if fuzzy_state:
            standard_extracted["state"] = fuzzy_state
            result["confidence"]["state"] = state_conf

    # 5. Merge with word-to-number results (standard parser takes precedence for income)
    if "total_income" in standard_extracted:
        result["extracted"]["total_income"] = standard_extracted["total_income"]
        result["confidence"]["total_income"] = 0.9  # Standard parser = higher confidence

    # Merge all other fields
    for field, value in standard_extracted.items():
        if not field.startswith("_"):
            result["extracted"][field] = value
            if field not in result["confidence"]:
                result["confidence"][field] = 0.9  # Default high confidence for standard parsing

    # Copy internal flags
    for field in ["_is_correction", "_changed_field", "_response_type"]:
        if field in standard_extracted:
            result["extracted"][field] = standard_extracted[field]

    # 6. Check for ambiguous amounts
    ambiguous = EnhancedParser.detect_ambiguous_amounts(message)
    result["ambiguous"] = ambiguous

    # If we found an ambiguous bare number, ask for confirmation
    # This applies whether income was extracted or not, because the bare number IS ambiguous
    for amb in ambiguous:
        if amb.get("context") == "bare_number":
            extracted_income = result["extracted"].get("total_income")
            # Only flag if no income extracted, or if it matches the ambiguous bare number
            if extracted_income is None or extracted_income == amb["value"]:
                result["needs_confirmation"].append({
                    "field": "total_income",
                    "value": amb["interpretations"][1]["amount"],  # Assume thousands
                    "message": f"When you said '{amb['value']}', did you mean ${amb['interpretations'][1]['amount']:,.0f}?",
                    "options": amb["interpretations"]
                })
                # Set extracted value to the more likely interpretation (thousands)
                # This applies whether no income was extracted or if it matches the bare number
                result["extracted"]["total_income"] = amb["interpretations"][1]["amount"]
                result["confidence"]["total_income"] = 0.5  # Low confidence due to ambiguity

    # 7. Validate extracted data
    validation = EnhancedParser.validate_extracted_data(result["extracted"], current_profile)
    result["warnings"].extend(validation["warnings"])
    result["suggestions"].extend(validation["suggestions"])

    # Apply auto-corrections
    for field, corrected_value in validation.get("auto_corrections", {}).items():
        result["extracted"][field] = corrected_value

    # 8. Detect conflicts
    conflicts = EnhancedParser.detect_conflicts(message, result["extracted"], current_profile)
    result["conflicts"] = conflicts

    # 9. Adjust confidence based on hedging words
    for amb in ambiguous:
        if amb.get("type") == "hedging_detected":
            for field in result["confidence"]:
                result["confidence"][field] = max(0.5, result["confidence"][field] - amb["confidence_reduction"])

    return result


# Context tracking for smart follow-ups
class ConversationContext:
    """
    Tracks conversation context for smarter follow-up questions.
    """

    # Topic-specific follow-up questions
    FOLLOW_UPS = {
        "rental_income": [
            "How many rental properties do you have?",
            "What are your annual rental expenses (maintenance, insurance, etc.)?",
        ],
        "business_income": [
            "What type of business do you operate?",
            "Do you have a home office?",
            "How many business miles do you drive annually?",
        ],
        "investment_income": [
            "Did you have any capital gains or losses this year?",
            "Do you have qualified dividends?",
        ],
        "mortgage": [
            "How much mortgage interest did you pay this year?",
            "Did you pay any points on your mortgage?",
        ],
        "dependents": [
            "Are your dependents under 17 years old?",
            "Did you pay for childcare expenses?",
        ],
        "self_employed": [
            "What's your approximate business income?",
            "Do you have any business expenses to deduct?",
            "Do you work from home?",
        ],
        "retirement": [
            "How much did you contribute to your 401(k) this year?",
            "Do you have a traditional or Roth IRA?",
        ],
    }

    @classmethod
    def get_contextual_follow_up(cls, extracted: dict, current_profile: dict, session: dict = None) -> str:
        """
        Get a contextual follow-up question based on what was just discussed.
        """
        # Check what was just extracted and suggest relevant follow-ups
        for field, follow_ups in cls.FOLLOW_UPS.items():
            # Check if this topic was mentioned
            if field in extracted or extracted.get(f"has_{field}"):
                # Check if we've already asked these
                asked = session.get("asked_follow_ups", set()) if session else set()
                for question in follow_ups:
                    if question not in asked:
                        return question

        return None

    @classmethod
    def detect_topic(cls, message: str) -> list:
        """
        Detect which tax topics are mentioned in the message.
        """
        import re
        topics = []
        msg_lower = message.lower()

        topic_patterns = {
            "rental_income": r'rental|landlord|tenant|property\s*income',
            "business_income": r'business|self[- ]?employ|1099|freelance|contractor',
            "investment_income": r'invest|stock|dividend|capital\s*gain|crypto|trading',
            "mortgage": r'mortgage|home\s*loan|house\s*payment',
            "dependents": r'child|kid|dependent|son|daughter',
            "self_employed": r'self[- ]?employ|own\s*business|freelance|contractor',
            "retirement": r'401k|ira|retire|pension',
            "education": r'student|college|tuition|education',
            "medical": r'medical|health|doctor|hospital',
            "charitable": r'donat|charit|church|tithe|non-?profit',
        }

        for topic, pattern in topic_patterns.items():
            if re.search(pattern, msg_lower):
                topics.append(topic)

        return topics


def detect_user_intent(message: str, profile: dict) -> str:
    """
    Detect the user's intent from their message.
    Returns: 'provide_info', 'ask_question', 'request_advice', 'correction', 'undo', 'generate_report'
    """
    import re
    msg_lower = message.lower().strip()

    # Undo/Reset intent
    if re.search(r'\bundo\b|\bgo\s*back\b|\bstart\s*over\b|\breset\b|\bbegin\s*again\b', msg_lower):
        return "undo"

    # Generate report intent
    if re.search(r'\breport\b|\bpdf\b|\bgenerate\b|\bdownload\b|\bsummary\b', msg_lower):
        return "generate_report"

    # Request advice intent
    if re.search(r'\badvice\b|\badvise\b|\brecommend|\bsuggest|\bstrateg|\bhelp\s*me\s*save|\bhow\s*can\s*i\b', msg_lower):
        return "request_advice"

    # Correction intent
    if re.search(r'\bactually\b|\bcorrect|\bwrong|\bmistake|\bchange\b|\binstead\b', msg_lower):
        return "correction"

    # Question intent
    if re.search(r'\?$|\bwhat\b|\bhow\b|\bwhy\b|\bwhen\b|\bwhere\b|\bcan\s*(i|you)\b|\bshould\b', msg_lower):
        return "ask_question"

    # Default: providing information
    return "provide_info"


def _summarize_profile(profile: dict) -> str:
    """Create a human-readable summary of the current profile."""
    parts = []

    if profile.get("filing_status"):
        status_names = {
            "single": "Single",
            "married_joint": "Married Filing Jointly",
            "married_separate": "Married Filing Separately",
            "head_of_household": "Head of Household",
            "qualifying_widow": "Qualifying Surviving Spouse"
        }
        parts.append(status_names.get(profile["filing_status"], profile["filing_status"]))

    if profile.get("total_income"):
        parts.append(f"${profile['total_income']:,.0f} income")

    if profile.get("state"):
        parts.append(f"in {profile['state']}")

    if profile.get("dependents"):
        parts.append(f"{profile['dependents']} dependent(s)")

    if profile.get("is_self_employed"):
        parts.append("self-employed")

    return ", ".join(parts) if parts else "No information yet"


def _get_dynamic_next_question(profile: dict, last_extracted: dict = None) -> tuple:
    """
    Dynamically determine the next question based on what's missing.
    Returns (question_text, quick_actions)
    """
    # Priority order for questions
    if not profile.get("filing_status"):
        return (
            "What's your filing status for this tax year?",
            [
                {"label": "Single", "value": "single"},
                {"label": "Married Filing Jointly", "value": "married_joint"},
                {"label": "Head of Household", "value": "head_of_household"},
                {"label": "Married Filing Separately", "value": "married_separate"}
            ]
        )

    if not profile.get("total_income"):
        return (
            "What's your approximate total annual income? Include all sources - wages, business, investments.",
            [
                {"label": "Under $50K", "value": "income_under_50k"},
                {"label": "$50K - $100K", "value": "income_50_100k"},
                {"label": "$100K - $200K", "value": "income_100_200k"},
                {"label": "Over $200K", "value": "income_over_200k"}
            ]
        )

    if not profile.get("state"):
        return (
            "Which state do you live in? This affects your state tax calculation.",
            [
                {"label": "California", "value": "CA"},
                {"label": "Texas", "value": "TX"},
                {"label": "New York", "value": "NY"},
                {"label": "Florida", "value": "FL"}
            ]
        )

    if profile.get("dependents") is None:
        return (
            "Do you have any dependents (children under 17, qualifying relatives)?",
            [
                {"label": "No dependents", "value": "0_dependents"},
                {"label": "1 dependent", "value": "1_dependent"},
                {"label": "2 dependents", "value": "2_dependents"},
                {"label": "3+ dependents", "value": "3plus_dependents"}
            ]
        )

    # If we have basics, ask about income type
    if not profile.get("income_type") and not profile.get("is_self_employed"):
        return (
            "What's your primary source of income?",
            [
                {"label": "W-2 Employee", "value": "w2_employee"},
                {"label": "Self-Employed", "value": "self_employed"},
                {"label": "Business Owner", "value": "business_owner"},
                {"label": "Retired", "value": "retired"}
            ]
        )

    # All basics collected - ready for analysis
    return (None, None)


@router.post("/chat", response_model=ChatResponse)
async def intelligent_chat(request: ChatRequest):
    """
    Main intelligent chat endpoint with dynamic flow handling.

    Features:
    - Intelligent responses based on context
    - Real-time tax calculations
    - Personalized strategy recommendations
    - Dynamic follow-up questions
    - Checkpoint system for undo/corrections
    - Adaptive conversation flow
    - Comprehensive error handling and recovery
    """
    # Initialize session_id early for error handling
    session_id = request.session_id or f"auto-{datetime.now().timestamp()}"
    request.session_id = session_id

    try:
        # Get or create session
        session = chat_engine.get_or_create_session(session_id)
        profile = session["profile"]
    except Exception as e:
        logger.error(f"Session initialization error: {e}")
        return ChatResponse(
            session_id=session_id,
            response="I'm having trouble accessing your session. Let me start fresh for you.",
            response_type="session_error",
            quick_actions=[
                {"label": "Start Fresh", "value": "start_fresh"},
                {"label": "Try Again", "value": "retry"}
            ]
        )

    # Sanitize and validate message
    msg_original = (request.message or "").strip()
    # Remove potential injection attempts (null bytes, carriage returns)
    msg_original = msg_original.replace('\x00', '').replace('\r', '')
    # Remove potential XSS attempts
    msg_original = msg_original.replace('<script', '').replace('javascript:', '')
    # Limit message length
    if len(msg_original) > 5000:
        msg_original = msg_original[:5000]

    msg_lower = msg_original.lower()

    # =========================================================================
    # GRACEFUL EDGE CASE HANDLING - Handle problematic inputs early
    # =========================================================================

    # Handle empty or very short messages
    if not msg_original or len(msg_original) < 2:
        next_q, next_actions = _get_dynamic_next_question(profile)
        return ChatResponse(
            session_id=request.session_id,
            response=next_q or "I'm here to help with your taxes! What would you like to know?",
            response_type="prompt",
            profile_completeness=chat_engine.calculate_profile_completeness(profile),
            lead_score=chat_engine.calculate_lead_score(profile),
            complexity=chat_engine.determine_complexity(profile),
            quick_actions=next_actions or [
                {"label": "Start Tax Analysis", "value": "start_analysis"},
                {"label": "Upload Documents", "value": "upload_docs"}
            ]
        )

    # Handle greetings
    greeting_patterns = [
        r'^(hi|hello|hey|howdy|greetings|good\s*(morning|afternoon|evening))[\s!.]*$',
        r'^(what\'?s\s*up|sup|yo)[\s!.]*$'
    ]
    import re
    is_greeting = any(re.match(p, msg_lower) for p in greeting_patterns)
    if is_greeting:
        greeting_response = "Hello! I'm your AI tax advisor. I can help you:\n\n"
        greeting_response += "• **Estimate your taxes** for 2025\n"
        greeting_response += "• **Find tax savings** opportunities\n"
        greeting_response += "• **Generate professional reports**\n\n"
        greeting_response += "To get started, what's your filing status?"

        return ChatResponse(
            session_id=request.session_id,
            response=greeting_response,
            response_type="greeting",
            profile_completeness=chat_engine.calculate_profile_completeness(profile),
            lead_score=chat_engine.calculate_lead_score(profile),
            complexity=chat_engine.determine_complexity(profile),
            quick_actions=[
                {"label": "Single", "value": "filing_single"},
                {"label": "Married Filing Jointly", "value": "filing_married"},
                {"label": "Head of Household", "value": "filing_hoh"},
                {"label": "Other", "value": "filing_other"}
            ]
        )

    # Handle frustrated/confused user
    frustrated_patterns = [
        r'(this\s*(is\s*)?(not|doesn\'t)\s*work)',
        r'(i\'?m\s*(so\s*)?(confused|frustrated|lost))',
        r'(i\s*don\'?t\s*understand)',
        r'(help\s*me|i\s*need\s*help)[\s!]*$',
        r'(what|huh|wtf|wth)\?*$'
    ]
    is_frustrated = any(re.search(p, msg_lower) for p in frustrated_patterns)
    if is_frustrated:
        help_response = "I'm sorry for any confusion! Let me help you.\n\n"
        help_response += "**Here's what you can do:**\n"
        help_response += "• Tell me your filing status (single, married, etc.)\n"
        help_response += "• Share your approximate income\n"
        help_response += "• Say \"undo\" to go back\n"
        help_response += "• Say \"reset\" to start over\n"
        help_response += "• Say \"show history\" to see our conversation\n\n"

        if profile:
            help_response += f"**Your current info:** {_summarize_profile(profile)}\n\n"

        help_response += "What would you like to do?"

        return ChatResponse(
            session_id=request.session_id,
            response=help_response,
            response_type="help",
            profile_completeness=chat_engine.calculate_profile_completeness(profile),
            lead_score=chat_engine.calculate_lead_score(profile),
            complexity=chat_engine.determine_complexity(profile),
            quick_actions=[
                {"label": "Start Over", "value": "reset"},
                {"label": "Show My History", "value": "show_history"},
                {"label": "Continue", "value": "continue"}
            ]
        )

    # Handle off-topic messages (detect if message has no tax-related content)
    tax_keywords = [
        'tax', 'income', 'salary', 'wage', 'earn', 'make', 'filing', 'single', 'married',
        'dependent', 'child', 'deduct', 'credit', 'refund', 'owe', 'irs', 'state',
        'business', 'self-employ', '1099', 'w-2', 'w2', 'mortgage', 'rent', 'invest',
        'retire', '401k', 'ira', 'hsa', 'charit', 'donat', 'medical', 'student',
        'capital', 'gain', 'loss', 'dividend', 'interest', 'property', 'home',
        'yes', 'no', 'correct', 'change', 'update', 'undo', 'reset', 'help',
        'k', 'thousand', 'million', 'hundred', '$', 'dollar', 'annual',
        # Common typos (to prevent false off-topic detection)
        'singl', 'maried', 'marred', 'seperately', 'houshold', 'dependant',
        'deductio', 'expens', 'refun', 'californi', 'texs', 'flordia', 'york',
        'hoh', 'mfj', 'mfs', 'jointly', 'separate', 'widow',
    ]

    # Also check if message contains numbers (likely tax-related)
    has_numbers = bool(re.search(r'\d', msg_original))
    has_tax_keyword = any(kw in msg_lower for kw in tax_keywords)

    # Also do a quick fuzzy check for filing status patterns
    fuzzy_status, _ = EnhancedParser.fuzzy_match_filing_status(msg_original)
    fuzzy_state, _ = EnhancedParser.fuzzy_match_state(msg_original)
    has_fuzzy_match = fuzzy_status is not None or fuzzy_state is not None

    if not has_numbers and not has_tax_keyword and not has_fuzzy_match and len(msg_original) > 20:
        # Likely off-topic - gently redirect
        redirect_response = "I'm specifically designed to help with tax questions and planning. "
        redirect_response += "I can help you with:\n\n"
        redirect_response += "• Estimating your tax liability\n"
        redirect_response += "• Finding deductions and credits\n"
        redirect_response += "• Retirement planning strategies\n"
        redirect_response += "• Business tax optimization\n\n"

        if not profile.get("filing_status"):
            redirect_response += "Let's start - what's your filing status?"
        elif not profile.get("total_income"):
            redirect_response += "What's your approximate annual income?"
        else:
            redirect_response += "What tax-related question can I help you with?"

        return ChatResponse(
            session_id=request.session_id,
            response=redirect_response,
            response_type="redirect",
            profile_completeness=chat_engine.calculate_profile_completeness(profile),
            lead_score=chat_engine.calculate_lead_score(profile),
            complexity=chat_engine.determine_complexity(profile),
            quick_actions=[
                {"label": "Calculate My Taxes", "value": "calculate_taxes"},
                {"label": "Find Deductions", "value": "find_deductions"},
                {"label": "Upload Documents", "value": "upload_docs"}
            ]
        )

    # Detect user intent
    user_intent = detect_user_intent(request.message or "", profile) if request.message else "provide_info"

    # =========================================================================
    # MULTI-TURN UNDO SYSTEM - Handle various undo requests dynamically
    # =========================================================================

    # Check for "undo to turn X" pattern
    import re
    undo_to_turn_match = re.search(r'undo\s*(?:to\s*)?(?:turn\s*)?(\d+)', msg_lower)
    show_history = re.search(r'show\s*history|view\s*history|my\s*history|what\s*did\s*i\s*say', msg_lower)
    reset_all = re.search(r'reset\s*(?:all|everything)|start\s*(?:over|fresh)|clear\s*(?:all|everything)', msg_lower)

    # Handle "show history" - Display conversation history for user to pick undo point
    if show_history:
        history_text = chat_engine.get_conversation_history_for_undo(request.session_id)
        return ChatResponse(
            session_id=request.session_id,
            response=history_text,
            response_type="history_display",
            profile_completeness=chat_engine.calculate_profile_completeness(profile),
            lead_score=chat_engine.calculate_lead_score(profile),
            complexity=chat_engine.determine_complexity(profile),
            quick_actions=[
                {"label": "Undo Last Turn", "value": "undo_last"},
                {"label": "Continue", "value": "continue_conversation"}
            ]
        )

    # Handle "reset all" - Complete reset to empty state
    if reset_all:
        # Full reset - clear everything including profile
        session["profile"] = {}
        session["checkpoints"] = []
        session["current_turn"] = 0
        session["calculations"] = None
        session["strategies"] = []
        session["conversation"] = []
        chat_engine._save_session_to_db(request.session_id, session)
        profile = {}

        return ChatResponse(
            session_id=request.session_id,
            response="I've reset everything. Let's start fresh!\n\nWhat's your filing status?",
            response_type="reset_complete",
            profile_completeness=0.0,
            lead_score=0,
            complexity="simple",
            quick_actions=[
                {"label": "Single", "value": "filing_single"},
                {"label": "Married Filing Jointly", "value": "filing_married"},
                {"label": "Head of Household", "value": "filing_hoh"},
                {"label": "Married Filing Separately", "value": "filing_mfs"}
            ]
        )

    # Handle "undo to turn X" - Multi-turn undo to specific point
    if undo_to_turn_match:
        target_turn = int(undo_to_turn_match.group(1))
        result = chat_engine.undo_to_turn(request.session_id, target_turn)

        if result["success"]:
            profile = result["restored_profile"]
            next_q, next_actions = _get_dynamic_next_question(profile)

            response_text = f"✓ {result['message']}\n\n"
            if next_q:
                response_text += next_q
            else:
                response_text += "What would you like to update?"

            return ChatResponse(
                session_id=request.session_id,
                response=response_text,
                response_type="undo_complete",
                profile_completeness=chat_engine.calculate_profile_completeness(profile),
                lead_score=chat_engine.calculate_lead_score(profile),
                complexity=chat_engine.determine_complexity(profile),
                quick_actions=next_actions or [{"label": "Continue", "value": "continue"}]
            )
        else:
            return ChatResponse(
                session_id=request.session_id,
                response=result["message"],
                response_type="error",
                profile_completeness=chat_engine.calculate_profile_completeness(profile),
                lead_score=chat_engine.calculate_lead_score(profile),
                complexity=chat_engine.determine_complexity(profile)
            )

    # Handle simple "undo" - Undo last turn
    if user_intent == "undo":
        result = chat_engine.undo_last_turn(request.session_id)

        if result["success"]:
            profile = result["restored_profile"]
            next_q, next_actions = _get_dynamic_next_question(profile)

            response_text = f"✓ {result['message']}\n\n"
            if next_q:
                response_text += next_q
            else:
                response_text += "What would you like to change?"

            # Show undo options for further undo
            undo_options = chat_engine.get_undo_options(request.session_id)
            if len(undo_options) > 1:
                response_text += f"\n\n*You can also say \"undo to turn X\" to go back further ({len(undo_options)} checkpoints available).*"

            return ChatResponse(
                session_id=request.session_id,
                response=response_text,
                response_type="undo_complete",
                profile_completeness=chat_engine.calculate_profile_completeness(profile),
                lead_score=chat_engine.calculate_lead_score(profile),
                complexity=chat_engine.determine_complexity(profile),
                quick_actions=next_actions or [
                    {"label": "Show History", "value": "show_history"},
                    {"label": "Continue", "value": "continue"}
                ]
            )
        else:
            return ChatResponse(
                session_id=request.session_id,
                response=result["message"],
                response_type="info",
                profile_completeness=chat_engine.calculate_profile_completeness(profile),
                lead_score=chat_engine.calculate_lead_score(profile),
                complexity=chat_engine.determine_complexity(profile)
            )

    # Update profile with any new data from request
    if request.profile:
        profile_dict = request.profile.dict(exclude_none=True)
        session = chat_engine.update_session(request.session_id, {"profile": profile_dict})
        profile = session["profile"]

    # =========================================================================
    # ENHANCED PARSING with confidence scoring, fuzzy matching, validation
    # =========================================================================
    correction_made = False
    changed_fields = []
    extracted_fields = []
    pending_confirmations = []
    detected_conflicts = []
    validation_warnings = []

    if request.message:
        # Use enhanced parser for robustness
        parse_result = enhanced_parse_user_message(request.message, profile, session)

        # Check for field-specific update (e.g., "change my income to 90000")
        if parse_result.get("field_update"):
            field_update = parse_result["field_update"]
            extracted = {field_update["field"]: field_update["new_value"]}
            extracted_fields = [field_update["field"]]
            correction_made = True
            changed_fields = extracted_fields
            logger.info(f"Field-specific update: {field_update}")
        else:
            extracted = parse_result.get("extracted", {})
            extracted_fields = [k for k in extracted.keys() if not k.startswith("_")]

        # Handle needs_confirmation - store for asking user
        if parse_result.get("needs_confirmation"):
            pending_confirmations = parse_result["needs_confirmation"]
            # Store in session for follow-up handling
            session["pending_confirmations"] = pending_confirmations

        # Handle detected conflicts
        if parse_result.get("conflicts"):
            detected_conflicts = parse_result["conflicts"]

        # Handle validation warnings
        if parse_result.get("warnings"):
            validation_warnings = parse_result["warnings"]

        if extracted:
            # Check if this is a correction
            if extracted.get("_is_correction"):
                correction_made = True
                changed_fields = [extracted.get("_changed_field")] if extracted.get("_changed_field") else extracted_fields
                # Clear calculations when corrections are made
                session["calculations"] = None
                session["strategies"] = []

            # Remove internal flags before updating profile
            extracted.pop("_is_correction", None)
            extracted.pop("_changed_field", None)
            extracted.pop("_response_type", None)

            # CREATE CHECKPOINT BEFORE applying changes (for undo capability)
            if extracted_fields:
                chat_engine.create_checkpoint(
                    request.session_id,
                    request.message,
                    extracted_fields
                )

            # Now update the profile with extracted data
            profile.update(extracted)
            session = chat_engine.update_session(request.session_id, {"profile": profile})

            # Log with confidence scores
            confidence_info = parse_result.get("confidence", {})
            logger.info(f"Enhanced extraction: {extracted} (confidence: {confidence_info})")

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

    # Build correction acknowledgment prefix if needed
    correction_prefix = ""
    if correction_made:
        if changed_fields:
            field_names = {"filing_status": "filing status", "total_income": "income",
                          "state": "state", "dependents": "dependents"}
            changed_names = [field_names.get(f, f) for f in changed_fields if f and not f.startswith("_")]
            if changed_names:
                correction_prefix = f"Got it! I've updated your {', '.join(changed_names)}. "
            else:
                correction_prefix = "Got it! I've updated your information. "
        else:
            correction_prefix = "Got it! I've noted that change. "

    # =========================================================================
    # Handle confirmations, conflicts, and validation warnings FIRST
    # =========================================================================

    # If there are pending confirmations, ask for confirmation before proceeding
    if pending_confirmations:
        confirmation = pending_confirmations[0]  # Handle one at a time
        response_text = confirmation.get("message", "Could you please confirm this?")

        # Build confirmation options
        if "options" in confirmation:
            quick_actions = [
                {"label": opt["meaning"], "value": f"confirm_{opt['amount']}"}
                for opt in confirmation["options"]
            ]
            quick_actions.append({"label": "Enter different amount", "value": "enter_custom"})
        else:
            quick_actions = [
                {"label": "Yes, that's correct", "value": "confirm_yes"},
                {"label": "No, let me clarify", "value": "confirm_no"}
            ]

        return ChatResponse(
            session_id=request.session_id,
            response=response_text,
            response_type="confirmation_needed",
            profile_completeness=completeness,
            lead_score=lead_score,
            complexity=complexity,
            quick_actions=quick_actions,
            warnings=[f"⚠️ Low confidence: {confirmation.get('field', 'value')}"]
        )

    # If there are conflicts, ask user to resolve them
    if detected_conflicts:
        conflict = detected_conflicts[0]  # Handle one at a time
        response_text = f"🤔 {conflict.get('message', '')}\n\n{conflict.get('question', 'Which is correct?')}"

        quick_actions = conflict.get("options", [
            {"label": "Continue as is", "value": "conflict_ignore"}
        ])

        return ChatResponse(
            session_id=request.session_id,
            response=response_text,
            response_type="conflict_resolution",
            profile_completeness=completeness,
            lead_score=lead_score,
            complexity=complexity,
            quick_actions=quick_actions
        )

    # If there are validation warnings that need attention
    critical_warnings = [w for w in validation_warnings if not w.get("auto_corrected")]
    if critical_warnings:
        warning = critical_warnings[0]
        response_text = f"⚠️ {warning.get('message', 'Please check this value.')}"
        if warning.get("suggestion"):
            response_text += f"\n\n{warning['suggestion']}"

        quick_actions = []
        if warning.get("possible_correction"):
            quick_actions.append({
                "label": f"Yes, use ${warning['possible_correction']:,.0f}",
                "value": f"correct_{warning['field']}_{warning['possible_correction']}"
            })
        quick_actions.append({"label": "Keep my original value", "value": "keep_value"})
        quick_actions.append({"label": "Enter different value", "value": "enter_custom"})

        return ChatResponse(
            session_id=request.session_id,
            response=response_text,
            response_type="validation_warning",
            profile_completeness=completeness,
            lead_score=lead_score,
            complexity=complexity,
            quick_actions=quick_actions,
            warnings=[warning.get("message", "")]
        )

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

        # Build context-aware response
        filing_display = profile.get('filing_status', 'single').replace('_', ' ').title()
        income_display = f"${profile.get('total_income', 0):,.0f}"
        state_display = f" in {profile.get('state')}" if profile.get('state') else ""
        dependents_display = f" with {profile.get('dependents')} dependent(s)" if profile.get('dependents') else ""

        response_text = f"""{correction_prefix}Based on your profile ({filing_display}, {income_display}{state_display}{dependents_display}):

**Your Tax Position:**
• Federal Tax: **${tax_calculation.federal_tax:,.0f}**
• State Tax: **${tax_calculation.state_tax:,.0f}**
• Total Tax: **${tax_calculation.total_tax:,.0f}**
• Effective Rate: **{tax_calculation.effective_rate:.1f}%**

**🎯 I found ${total_savings:,.0f} in potential savings across {len(strategies)} strategies!**"""

        if strategies:
            response_text += f"\n\nYour top opportunity: **{strategies[0].title}** could save you **${strategies[0].estimated_savings:,.0f}**."

        response_text += "\n\nWould you like me to explain your top strategies, generate your full advisory report, or update any information?"

        quick_actions = [
            {"label": "Show Top Strategies →", "value": "show_strategies", "primary": True},
            {"label": "Generate Full Report", "value": "generate_report"},
            {"label": "Update My Info", "value": "update_info"},
            {"label": "Connect with CPA", "value": "connect_cpa"}
        ]

        key_insights = [
            f"Your marginal tax rate is {tax_calculation.marginal_rate}%",
            f"Taking the {tax_calculation.deduction_type} deduction saves you most"
        ]
        if strategies:
            key_insights.append(f"Top opportunity: {strategies[0].title}")

    else:
        # Need more information - use dynamic question system
        next_q, next_actions = _get_dynamic_next_question(profile)

        if next_q:
            response_text = correction_prefix + next_q
            if next_actions:
                quick_actions = next_actions
        elif not profile.get("filing_status"):
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

    try:
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
    except Exception as e:
        # Catch any response building errors
        logger.error(f"Response building error in intelligent_chat: {e}")
        return ChatResponse(
            session_id=request.session_id,
            response="I encountered an issue processing your request. Let me try a simpler response.",
            response_type="error",
            profile_completeness=completeness if 'completeness' in dir() else 0.0,
            lead_score=lead_score if 'lead_score' in dir() else 0,
            complexity=complexity if 'complexity' in dir() else "simple",
            quick_actions=[
                {"label": "Try Again", "value": "retry"},
                {"label": "Start Over", "value": "reset"}
            ]
        )


@router.post("/analyze", response_model=FullAnalysisResponse)
async def full_analysis(request: FullAnalysisRequest):
    """
    Comprehensive tax analysis with all strategies and insights.

    This is the full advisory engine - use this when you have
    complete profile data and want all recommendations.
    """
    try:
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
    except Exception as e:
        logger.error(f"Full analysis error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unable to complete analysis. Please try again or contact support."
        )


@router.post("/strategies")
async def get_strategies(request: FullAnalysisRequest):
    """Get personalized tax strategies."""
    try:
        profile = request.profile.dict(exclude_none=True)
        calculation = await chat_engine.get_tax_calculation(profile)
        strategies = await chat_engine.get_tax_strategies(profile, calculation)

        return {
            "strategies": [s.dict() for s in strategies],
            "total_potential_savings": sum(s.estimated_savings for s in strategies),
            "top_3": [s.dict() for s in strategies[:3]]
        }
    except Exception as e:
        logger.error(f"Strategies endpoint error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unable to calculate strategies. Please try again."
        )


@router.post("/calculate")
async def calculate_taxes(request: FullAnalysisRequest):
    """Quick tax calculation endpoint."""
    try:
        profile = request.profile.dict(exclude_none=True)
        calculation = await chat_engine.get_tax_calculation(profile)
        return calculation.dict()
    except Exception as e:
        logger.error(f"Calculate endpoint error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unable to calculate taxes. Please check your inputs and try again."
        )


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
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session report error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve session report. Please try again."
        )


@router.post("/generate-report")
async def generate_report(request: FullAnalysisRequest):
    """Generate a professional advisory report."""
    try:
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
    except Exception as e:
        logger.error(f"Generate report error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unable to generate report. Please try again."
        )


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
