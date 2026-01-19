"""
Lead Magnet Service - Smart Tax Advisory Lead Magnet Flow

This service powers the lead magnet funnel:
1. Start assessment session with CPA branding
2. Process smart tax profile questions
3. Detect complexity from answers
4. Capture contact info and create lead
5. Calculate lead score for CPA
6. Generate Tier 1 (FREE) and Tier 2 (Full) reports
"""

from __future__ import annotations

import uuid
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal
from datetime import datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================

class AssessmentMode(str, Enum):
    """Assessment mode selection."""
    QUICK = "quick"  # 2 minutes
    FULL = "full"  # 5 minutes


class TaxComplexity(str, Enum):
    """Tax situation complexity levels."""
    SIMPLE = "simple"  # W-2 only + standard deduction
    MODERATE = "moderate"  # Multiple W-2s OR investments OR homeowner
    COMPLEX = "complex"  # Self-employment OR rental OR multi-state
    PROFESSIONAL = "professional"  # Business owner + high income + K-1s


class LeadTemperature(str, Enum):
    """Lead temperature for follow-up prioritization."""
    HOT = "hot"  # High savings, engaged quickly
    WARM = "warm"  # Moderate potential
    COLD = "cold"  # Lower priority


class FilingStatus(str, Enum):
    """Tax filing status."""
    SINGLE = "single"
    MARRIED_JOINTLY = "married_jointly"
    MARRIED_SEPARATELY = "married_separately"
    HEAD_OF_HOUSEHOLD = "head_of_household"
    QUALIFYING_WIDOW = "qualifying_widow"


class IncomeSource(str, Enum):
    """Income source types."""
    W2 = "w2"
    SELF_EMPLOYED = "self_employed"
    INVESTMENTS = "investments"
    RENTAL = "rental"
    RETIREMENT = "retirement"


class LifeEvent(str, Enum):
    """Recent life events affecting taxes."""
    NEW_JOB = "new_job"
    BABY = "baby"
    HOME_PURCHASE = "home_purchase"
    MARRIAGE = "marriage"
    DIVORCE = "divorce"
    RETIREMENT_START = "retirement_start"
    COLLEGE_START = "college_start"
    BUSINESS_START = "business_start"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CPAProfile:
    """CPA/Firm profile for branding."""
    cpa_id: str
    cpa_slug: str
    first_name: str
    last_name: str
    credentials: str = "CPA"  # CPA, EA, CMA, etc.
    firm_name: Optional[str] = None
    logo_url: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    booking_link: Optional[str] = None
    address: Optional[str] = None
    bio: Optional[str] = None
    specialties: List[str] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        return f"{self.first_name} {self.last_name}, {self.credentials}"

    @property
    def full_title(self) -> str:
        if self.firm_name:
            return f"{self.display_name} - {self.firm_name}"
        return self.display_name

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cpa_id": self.cpa_id,
            "cpa_slug": self.cpa_slug,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "credentials": self.credentials,
            "display_name": self.display_name,
            "full_title": self.full_title,
            "firm_name": self.firm_name,
            "logo_url": self.logo_url,
            "email": self.email,
            "phone": self.phone,
            "booking_link": self.booking_link,
            "address": self.address,
            "bio": self.bio,
            "specialties": self.specialties,
        }


@dataclass
class TaxProfile:
    """Smart tax profile from quick questions."""
    filing_status: FilingStatus = FilingStatus.SINGLE
    dependents_count: int = 0
    children_under_17: bool = False
    income_range: str = "50k-75k"  # Slider value
    income_sources: List[IncomeSource] = field(default_factory=list)
    is_homeowner: bool = False
    retirement_savings: str = "some"  # none, some, maxed
    healthcare_type: str = "employer"  # employer, hdhp_hsa, marketplace
    life_events: List[LifeEvent] = field(default_factory=list)
    has_student_loans: bool = False  # Student loan interest deduction
    has_business: bool = False  # Business owner or side hustle

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filing_status": self.filing_status.value,
            "dependents_count": self.dependents_count,
            "children_under_17": self.children_under_17,
            "income_range": self.income_range,
            "income_sources": [s.value for s in self.income_sources],
            "is_homeowner": self.is_homeowner,
            "retirement_savings": self.retirement_savings,
            "healthcare_type": self.healthcare_type,
            "life_events": [e.value for e in self.life_events],
            "has_student_loans": self.has_student_loans,
            "has_business": self.has_business,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaxProfile":
        # Handle income_sources - may be strings or IncomeSource enums
        income_sources = []
        for s in data.get("income_sources", []):
            try:
                income_sources.append(IncomeSource(s) if isinstance(s, str) else s)
            except ValueError:
                pass  # Skip invalid income sources

        # Handle life_events - may be strings or LifeEvent enums
        life_events = []
        for e in data.get("life_events", []):
            try:
                life_events.append(LifeEvent(e) if isinstance(e, str) else e)
            except ValueError:
                pass  # Skip invalid life events

        return cls(
            filing_status=FilingStatus(data.get("filing_status", "single")),
            dependents_count=data.get("dependents_count", 0),
            children_under_17=data.get("children_under_17", False),
            income_range=data.get("income_range", "50k-75k"),
            income_sources=income_sources,
            is_homeowner=data.get("is_homeowner", False),
            retirement_savings=data.get("retirement_savings", "some"),
            healthcare_type=data.get("healthcare_type", "employer"),
            life_events=life_events,
            has_student_loans=data.get("has_student_loans", False),
            has_business=data.get("has_business", False),
        )


@dataclass
class TaxInsight:
    """A single tax insight/opportunity."""
    insight_id: str
    title: str
    category: str  # credits, deductions, retirement, healthcare, etc.
    description_teaser: str  # Short for Tier 1
    description_full: str  # Detailed for Tier 2
    savings_low: float = 0
    savings_high: float = 0
    action_items: List[str] = field(default_factory=list)
    irs_reference: Optional[str] = None
    deadline: Optional[str] = None
    priority: str = "medium"  # high, medium, low

    def to_dict(self, tier: int = 1) -> Dict[str, Any]:
        base = {
            "insight_id": self.insight_id,
            "title": self.title,
            "category": self.category,
            "priority": self.priority,
        }

        if tier == 1:
            # Tier 1: Teaser only
            base["description"] = self.description_teaser
            base["savings_range"] = f"${self.savings_low:,.0f} - ${self.savings_high:,.0f}"
        else:
            # Tier 2: Full details
            base["description"] = self.description_full
            base["savings_low"] = self.savings_low
            base["savings_high"] = self.savings_high
            base["action_items"] = self.action_items
            base["irs_reference"] = self.irs_reference
            base["deadline"] = self.deadline

        return base


@dataclass
class LeadMagnetSession:
    """A lead magnet assessment session."""
    session_id: str
    cpa_profile: Optional[CPAProfile] = None
    assessment_mode: AssessmentMode = AssessmentMode.QUICK
    current_screen: str = "welcome"
    privacy_consent: bool = False
    tax_profile: Optional[TaxProfile] = None
    complexity: TaxComplexity = TaxComplexity.SIMPLE
    contact_captured: bool = False
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    time_spent_seconds: int = 0
    referral_source: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "cpa_profile": self.cpa_profile.to_dict() if self.cpa_profile else None,
            "assessment_mode": self.assessment_mode.value,
            "current_screen": self.current_screen,
            "privacy_consent": self.privacy_consent,
            "tax_profile": self.tax_profile.to_dict() if self.tax_profile else None,
            "complexity": self.complexity.value,
            "contact_captured": self.contact_captured,
            "started_at": self.started_at.isoformat(),
            "time_spent_seconds": self.time_spent_seconds,
        }


@dataclass
class LeadMagnetLead:
    """A captured lead with scoring."""
    lead_id: str
    session_id: str
    cpa_id: Optional[str] = None
    first_name: str = ""
    email: str = ""
    phone: Optional[str] = None
    filing_status: Optional[str] = None
    complexity: TaxComplexity = TaxComplexity.SIMPLE
    income_range: Optional[str] = None
    lead_score: int = 50  # 1-100
    lead_temperature: LeadTemperature = LeadTemperature.WARM
    estimated_engagement_value: float = 0  # $ value
    conversion_probability: float = 0.5  # 0-1
    savings_range_low: float = 0
    savings_range_high: float = 0
    engaged: bool = False
    engaged_at: Optional[datetime] = None
    engagement_letter_acknowledged: bool = False  # REQUIRED for Tier 2 unlock
    engagement_letter_acknowledged_at: Optional[datetime] = None
    converted: bool = False
    converted_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def can_access_tier_two(self) -> bool:
        """
        Check if lead can access Tier 2 full report.
        COMPLIANCE REQUIREMENT: Both conditions must be true:
        1. CPA has marked lead as engaged
        2. Engagement letter has been acknowledged
        """
        return self.engaged and self.engagement_letter_acknowledged

    def to_dict(self, include_cpa_only: bool = False) -> Dict[str, Any]:
        base = {
            "lead_id": self.lead_id,
            "session_id": self.session_id,
            "first_name": self.first_name,
            "complexity": self.complexity.value,
            "savings_range": f"${self.savings_range_low:,.0f} - ${self.savings_range_high:,.0f}",
            "engaged": self.engaged,
            "created_at": self.created_at.isoformat(),
        }

        if include_cpa_only:
            # CPA-only data - hidden from client
            base.update({
                "email": self.email,
                "phone": self.phone,
                "filing_status": self.filing_status,
                "income_range": self.income_range,
                "lead_score": self.lead_score,
                "lead_temperature": self.lead_temperature.value,
                "estimated_engagement_value": self.estimated_engagement_value,
                "conversion_probability": self.conversion_probability,
                "savings_range_low": self.savings_range_low,
                "savings_range_high": self.savings_range_high,
                "engaged_at": self.engaged_at.isoformat() if self.engaged_at else None,
                "engagement_letter_acknowledged": self.engagement_letter_acknowledged,
                "engagement_letter_acknowledged_at": self.engagement_letter_acknowledged_at.isoformat() if self.engagement_letter_acknowledged_at else None,
                "can_access_tier_two": self.can_access_tier_two(),
                "converted": self.converted,
                "converted_at": self.converted_at.isoformat() if self.converted_at else None,
                "cpa_id": self.cpa_id,
            })

        return base


# =============================================================================
# LEAD MAGNET SERVICE
# =============================================================================

class LeadMagnetService:
    """
    Service for the Smart Tax Advisory Lead Magnet flow.

    Flow:
    1. start_assessment() - Create session with CPA branding
    2. submit_profile() - Process answers, detect complexity
    3. capture_contact() - Create lead, generate report
    4. generate_tier_one_report() - FREE teaser report
    5. generate_tier_two_report() - Full report (after engagement)
    """

    def __init__(self):
        self._sessions: Dict[str, LeadMagnetSession] = {}
        self._leads: Dict[str, LeadMagnetLead] = {}
        self._cpa_profiles: Dict[str, CPAProfile] = {}
        self._default_cpa = self._create_default_cpa()

    def _get_db_connection(self):
        """Get database connection."""
        db_path = Path(__file__).parent.parent.parent / "database" / "jorss_gbo.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _create_default_cpa(self) -> CPAProfile:
        """Create a default CPA profile for unbranded sessions."""
        return CPAProfile(
            cpa_id="default",
            cpa_slug="tax-advisory",
            first_name="Your",
            last_name="Tax Advisor",
            credentials="CPA",
            firm_name="Tax Advisory Services",
        )

    # =========================================================================
    # CPA PROFILE MANAGEMENT
    # =========================================================================

    def get_cpa_profile(self, cpa_slug: str) -> Optional[CPAProfile]:
        """Get CPA profile by slug."""
        if cpa_slug in self._cpa_profiles:
            return self._cpa_profiles[cpa_slug]

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM cpa_profiles WHERE cpa_slug = ? AND active = 1",
                (cpa_slug,)
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                profile = CPAProfile(
                    cpa_id=row["cpa_id"],
                    cpa_slug=row["cpa_slug"],
                    first_name=row["first_name"],
                    last_name=row["last_name"],
                    credentials=row["credentials"] or "CPA",
                    firm_name=row["firm_name"],
                    logo_url=row["logo_url"],
                    email=row["email"],
                    phone=row["phone"],
                    booking_link=row["booking_link"],
                    address=row["address"],
                    bio=row["bio"],
                    specialties=json.loads(row["specialties_json"]) if row["specialties_json"] else [],
                )
                self._cpa_profiles[cpa_slug] = profile
                return profile
        except Exception as e:
            logger.warning(f"Could not load CPA profile for {cpa_slug}: {e}")

        return None

    def create_cpa_profile(
        self,
        first_name: str,
        last_name: str,
        cpa_slug: Optional[str] = None,
        credentials: str = "CPA",
        firm_name: Optional[str] = None,
        logo_url: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        booking_link: Optional[str] = None,
        address: Optional[str] = None,
        bio: Optional[str] = None,
        specialties: List[str] = None,
    ) -> Dict[str, Any]:
        """Create a new CPA profile."""
        cpa_id = f"cpa-{uuid.uuid4().hex[:12]}"
        final_slug = cpa_slug or self._generate_slug(first_name, last_name)

        profile = CPAProfile(
            cpa_id=cpa_id,
            cpa_slug=final_slug,
            first_name=first_name,
            last_name=last_name,
            credentials=credentials,
            firm_name=firm_name,
            logo_url=logo_url,
            email=email,
            phone=phone,
            booking_link=booking_link,
            address=address,
            bio=bio,
            specialties=specialties or [],
        )

        # Persist to database
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO cpa_profiles (
                    cpa_id, cpa_slug, first_name, last_name, credentials,
                    firm_name, logo_url, email, phone, booking_link,
                    address, bio, specialties_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cpa_id, cpa_slug, profile.first_name, profile.last_name,
                profile.credentials, profile.firm_name, profile.logo_url,
                profile.email, profile.phone, profile.booking_link,
                profile.address, profile.bio, json.dumps(profile.specialties),
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to create CPA profile: {e}")

        self._cpa_profiles[final_slug] = profile
        return profile.to_dict()

    def _generate_slug(self, first_name: str, last_name: str) -> str:
        """Generate URL-friendly slug from name."""
        slug = f"{first_name}-{last_name}".lower()
        slug = "".join(c if c.isalnum() or c == "-" else "-" for c in slug)
        return slug

    # =========================================================================
    # ASSESSMENT SESSION MANAGEMENT
    # =========================================================================

    def start_assessment(
        self,
        cpa_slug: Optional[str] = None,
        assessment_mode: str = "quick",
        referral_source: Optional[str] = None,
    ) -> LeadMagnetSession:
        """
        Start a new assessment session with CPA branding.

        Args:
            cpa_slug: URL-friendly CPA identifier (e.g., "john-smith-cpa")
            assessment_mode: "quick" (2 min) or "full" (5 min)
            referral_source: Where the lead came from

        Returns:
            New LeadMagnetSession
        """
        session_id = f"lm-{uuid.uuid4().hex[:12]}"

        # Get CPA profile
        cpa_profile = None
        if cpa_slug:
            cpa_profile = self.get_cpa_profile(cpa_slug)

        if not cpa_profile:
            cpa_profile = self._default_cpa

        mode = AssessmentMode.QUICK if assessment_mode == "quick" else AssessmentMode.FULL

        session = LeadMagnetSession(
            session_id=session_id,
            cpa_profile=cpa_profile,
            assessment_mode=mode,
            current_screen="welcome",
            referral_source=referral_source,
        )

        # Persist to database
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO lead_magnet_sessions (
                    session_id, cpa_id, cpa_slug, assessment_mode,
                    current_screen, referral_source
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                cpa_profile.cpa_id,
                cpa_profile.cpa_slug,
                mode.value,
                "welcome",
                referral_source,
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to persist session: {e}")

        self._sessions[session_id] = session
        logger.info(f"Started lead magnet session {session_id} for CPA {cpa_profile.cpa_slug}")

        return session

    def get_session(self, session_id: str) -> Optional[LeadMagnetSession]:
        """Get session by ID."""
        if session_id in self._sessions:
            return self._sessions[session_id]

        # Try loading from database
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM lead_magnet_sessions WHERE session_id = ?",
                (session_id,)
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                cpa_profile = self.get_cpa_profile(row["cpa_slug"]) if row["cpa_slug"] else self._default_cpa
                profile_data = json.loads(row["profile_data_json"]) if row["profile_data_json"] else None

                session = LeadMagnetSession(
                    session_id=row["session_id"],
                    cpa_profile=cpa_profile,
                    assessment_mode=AssessmentMode(row["assessment_mode"]),
                    current_screen=row["current_screen"],
                    privacy_consent=bool(row["privacy_consent"]),
                    tax_profile=TaxProfile.from_dict(profile_data) if profile_data else None,
                    contact_captured=bool(row["contact_captured"]),
                    time_spent_seconds=row["time_spent_seconds"] or 0,
                    referral_source=row["referral_source"],
                )
                self._sessions[session_id] = session
                return session
        except Exception as e:
            logger.warning(f"Could not load session {session_id}: {e}")

        return None

    def update_session_screen(self, session_id: str, screen: str) -> Optional[LeadMagnetSession]:
        """Update current screen for session."""
        session = self.get_session(session_id)
        if not session:
            return None

        session.current_screen = screen
        session.last_activity = datetime.utcnow()

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE lead_magnet_sessions SET
                    current_screen = ?,
                    last_activity = ?
                WHERE session_id = ?
            """, (screen, datetime.utcnow().isoformat(), session_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to update session screen: {e}")

        return session

    # =========================================================================
    # PROFILE SUBMISSION & COMPLEXITY DETECTION
    # =========================================================================

    def submit_profile(
        self,
        session_id: str,
        profile_data: Dict[str, Any],
    ) -> Tuple[LeadMagnetSession, TaxComplexity, List[TaxInsight]]:
        """
        Process smart tax profile answers and detect complexity.

        Args:
            session_id: Session ID
            profile_data: Answers from the smart profile questions

        Returns:
            Updated session, detected complexity, and generated insights
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Parse profile data
        tax_profile = TaxProfile.from_dict(profile_data)
        session.tax_profile = tax_profile

        # Detect complexity
        complexity = self._detect_complexity(tax_profile)
        session.complexity = complexity

        # Generate insights based on profile
        insights = self._generate_insights(tax_profile, complexity)

        # Persist
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE lead_magnet_sessions SET
                    profile_data_json = ?,
                    current_screen = 'contact',
                    last_activity = ?
                WHERE session_id = ?
            """, (json.dumps(profile_data), datetime.utcnow().isoformat(), session_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to persist profile: {e}")

        logger.info(f"Profile submitted for {session_id}, complexity: {complexity.value}")

        return session, complexity, insights

    def _detect_complexity(self, profile: TaxProfile) -> TaxComplexity:
        """
        Detect tax complexity from profile.

        Rules:
        - SIMPLE: W-2 only + standard deduction signals
        - MODERATE: Multiple W-2s OR investments OR homeowner
        - COMPLEX: Self-employment OR rental OR multi-state
        - PROFESSIONAL: Business owner + high income (>$200k) OR complex + high income
        """
        sources = set(profile.income_sources)
        income = self._parse_income_range(profile.income_range)

        # Flags
        has_self_employed = IncomeSource.SELF_EMPLOYED in sources
        has_rental = IncomeSource.RENTAL in sources
        has_investments = IncomeSource.INVESTMENTS in sources
        has_business = profile.has_business or has_self_employed
        high_income = income >= 200000  # Lowered threshold
        very_high_income = income >= 500000

        # PROFESSIONAL: Complex situation + high income
        # OR any business/self-employed + very high income
        if very_high_income and (has_business or has_rental or has_investments):
            return TaxComplexity.PROFESSIONAL

        if high_income and has_business:
            return TaxComplexity.PROFESSIONAL

        if has_business and has_rental and has_investments:
            return TaxComplexity.PROFESSIONAL

        # COMPLEX: Self-employment OR rental income OR starting a business
        if has_self_employed or has_rental or has_business:
            return TaxComplexity.COMPLEX

        # Check for business start life event
        if LifeEvent.BUSINESS_START in profile.life_events:
            return TaxComplexity.COMPLEX

        # MODERATE: Investments OR homeowner OR multiple income sources
        multiple_sources = len(sources) > 1

        if multiple_sources or has_investments or profile.is_homeowner:
            return TaxComplexity.MODERATE

        # SIMPLE: W-2 only with standard deduction indicators
        return TaxComplexity.SIMPLE

    def _parse_income_range(self, range_str: str) -> int:
        """Parse income range string to approximate value.

        Supports multiple formats:
        - Frontend format: under_50k, 50k_75k, over_500k
        - Legacy format: 0-25k, 50k-75k, 500k+
        """
        # Normalize the string
        normalized = range_str.lower().replace("-", "_").replace("+", "")

        range_map = {
            # Frontend format
            "under_50k": 25000,
            "50k_75k": 62500,
            "75k_100k": 87500,
            "100k_150k": 125000,
            "150k_200k": 175000,
            "200k_500k": 350000,
            "over_500k": 750000,
            # Legacy format (normalized)
            "0_25k": 12500,
            "25k_50k": 37500,
            "50k_75k": 62500,
            "75k_100k": 87500,
            "100k_150k": 125000,
            "150k_200k": 175000,
            "200k_300k": 250000,
            "300k_500k": 400000,
            "500k": 600000,
        }
        return range_map.get(normalized, 62500)

    # =========================================================================
    # INSIGHT GENERATION
    # =========================================================================

    def _generate_insights(
        self,
        profile: TaxProfile,
        complexity: TaxComplexity,
    ) -> List[TaxInsight]:
        """Generate tax insights based on profile."""
        insights = []
        income = self._parse_income_range(profile.income_range)

        # Child Tax Credit
        if profile.children_under_17:
            savings = 2000 * profile.dependents_count
            insights.append(TaxInsight(
                insight_id=f"ctc-{uuid.uuid4().hex[:8]}",
                title="Child Tax Credit Optimization",
                category="credits",
                description_teaser="You may be eligible for significant child tax credits.",
                description_full=(
                    f"With {profile.dependents_count} qualifying child(ren) under 17, you may be "
                    f"eligible for the Child Tax Credit worth up to $2,000 per child. The credit "
                    f"is partially refundable up to $1,600 per child."
                ),
                savings_low=savings * 0.5,
                savings_high=savings,
                action_items=[
                    "Verify children's SSNs are valid for work",
                    "Confirm residency requirements (lived with you > 6 months)",
                    "Check income phase-out thresholds",
                ],
                irs_reference="IRS Publication 972",
                priority="high",
            ))

        # Retirement savings opportunity
        if profile.retirement_savings != "maxed" and income > 30000:
            max_401k = 23500  # 2025 limit (IRS Rev. Proc. 2024-40)
            marginal_rate = self._estimate_marginal_rate(income, profile.filing_status)
            savings = max_401k * marginal_rate

            insights.append(TaxInsight(
                insight_id=f"ret-{uuid.uuid4().hex[:8]}",
                title="Retirement Contribution Opportunity",
                category="retirement",
                description_teaser="Maximize tax-advantaged retirement savings.",
                description_full=(
                    f"Based on your income, increasing your 401(k) or IRA contributions could "
                    f"significantly reduce your taxable income. The 2025 401(k) limit is $23,500 "
                    f"($31,000 if over 50). Each dollar contributed saves approximately "
                    f"{marginal_rate * 100:.0f}% in taxes."
                ),
                savings_low=savings * 0.3,
                savings_high=savings,
                action_items=[
                    "Review current 401(k) contribution percentage",
                    "Check if employer offers matching",
                    "Consider catch-up contributions if over 50",
                    "Evaluate Roth vs Traditional based on tax bracket",
                ],
                irs_reference="IRS Publication 590-A",
                priority="high",
            ))

        # HSA opportunity
        if profile.healthcare_type == "hdhp_hsa":
            hsa_limit = 8550 if profile.filing_status == FilingStatus.MARRIED_JOINTLY else 4300  # 2025 limits
            marginal_rate = self._estimate_marginal_rate(income, profile.filing_status)
            savings = hsa_limit * marginal_rate

            insights.append(TaxInsight(
                insight_id=f"hsa-{uuid.uuid4().hex[:8]}",
                title="HSA Triple Tax Advantage",
                category="healthcare",
                description_teaser="Maximize your Health Savings Account benefits.",
                description_full=(
                    f"Your HDHP eligibility allows HSA contributions up to ${hsa_limit:,}. "
                    f"HSAs offer triple tax benefits: deductible contributions, tax-free growth, "
                    f"and tax-free withdrawals for medical expenses."
                ),
                savings_low=savings * 0.5,
                savings_high=savings,
                action_items=[
                    "Verify HDHP eligibility requirements",
                    f"Contribute maximum ${hsa_limit:,} for the year",
                    "Consider investing HSA funds for long-term growth",
                ],
                irs_reference="IRS Publication 969",
                priority="high",
            ))

        # Homeowner deductions
        if profile.is_homeowner:
            # Estimate based on income (rough proxy for home value)
            estimated_property_tax = income * 0.015
            estimated_mortgage_interest = income * 0.02

            insights.append(TaxInsight(
                insight_id=f"home-{uuid.uuid4().hex[:8]}",
                title="Homeowner Tax Benefits",
                category="deductions",
                description_teaser="Review mortgage interest and property tax deductions.",
                description_full=(
                    "As a homeowner, you may benefit from itemizing deductions including "
                    "mortgage interest and property taxes. The SALT deduction cap is $10,000, "
                    "which includes state income taxes and property taxes combined."
                ),
                savings_low=2000,
                savings_high=min(10000, estimated_property_tax + estimated_mortgage_interest) * 0.22,
                action_items=[
                    "Gather Form 1098 for mortgage interest",
                    "Compile property tax statements",
                    "Compare itemized vs standard deduction",
                ],
                irs_reference="IRS Schedule A",
                priority="medium",
            ))

        # Self-employment deductions
        if IncomeSource.SELF_EMPLOYED in profile.income_sources:
            insights.append(TaxInsight(
                insight_id=f"se-{uuid.uuid4().hex[:8]}",
                title="Self-Employment Tax Strategies",
                category="business",
                description_teaser="Multiple deductions available for self-employed individuals.",
                description_full=(
                    "Self-employment opens numerous tax planning opportunities including "
                    "the QBI deduction (up to 20% of qualified income), home office deduction, "
                    "health insurance premiums, retirement plans (SEP-IRA, Solo 401k), and "
                    "business expense deductions."
                ),
                savings_low=income * 0.05,
                savings_high=income * 0.15,
                action_items=[
                    "Track all business expenses",
                    "Calculate home office deduction",
                    "Review QBI deduction eligibility",
                    "Consider SEP-IRA or Solo 401(k)",
                ],
                irs_reference="IRS Schedule C, Form 8829",
                priority="high",
            ))

        # Life events
        if LifeEvent.BABY in profile.life_events:
            insights.append(TaxInsight(
                insight_id=f"baby-{uuid.uuid4().hex[:8]}",
                title="New Baby Tax Benefits",
                category="credits",
                description_teaser="Several tax benefits are available for new parents.",
                description_full=(
                    "Congratulations on your new addition! This triggers several tax benefits "
                    "including the Child Tax Credit, potential dependent care FSA, and if "
                    "applicable, the Earned Income Tax Credit."
                ),
                savings_low=1500,
                savings_high=3600,
                action_items=[
                    "Get SSN for newborn ASAP",
                    "Update W-4 withholding",
                    "Sign up for dependent care FSA if available",
                ],
                priority="high",
            ))

        if LifeEvent.HOME_PURCHASE in profile.life_events:
            insights.append(TaxInsight(
                insight_id=f"newh-{uuid.uuid4().hex[:8]}",
                title="New Home Tax Considerations",
                category="deductions",
                description_teaser="First-year homeowner tax planning opportunities.",
                description_full=(
                    "Your home purchase may result in significant deductible expenses "
                    "including mortgage points, PMI (if income qualifies), and prorated "
                    "property taxes. Keep all closing documents for tax preparation."
                ),
                savings_low=1000,
                savings_high=5000,
                action_items=[
                    "Keep HUD-1 settlement statement",
                    "Note any points paid on mortgage",
                    "Track property tax payments",
                ],
                priority="high",
            ))

        # Ensure minimum insights
        if len(insights) < 3:
            # Add generic opportunities
            insights.append(TaxInsight(
                insight_id=f"gen-{uuid.uuid4().hex[:8]}",
                title="Tax Filing Optimization",
                category="planning",
                description_teaser="Review your overall tax strategy with a professional.",
                description_full=(
                    "A professional tax review can identify additional savings opportunities "
                    "based on your complete financial picture. This includes timing strategies, "
                    "charitable giving optimization, and education credits if applicable."
                ),
                savings_low=200,
                savings_high=1500,
                action_items=["Schedule consultation with tax professional"],
                priority="medium",
            ))

        return insights

    def _estimate_marginal_rate(
        self,
        income: int,
        filing_status: FilingStatus,
    ) -> float:
        """Estimate marginal tax rate (2025 brackets)."""
        # 2025 brackets (IRS Rev. Proc. 2024-40)
        if filing_status == FilingStatus.MARRIED_JOINTLY:
            if income < 23850:
                return 0.10
            elif income < 96950:
                return 0.12
            elif income < 206700:
                return 0.22
            elif income < 394600:
                return 0.24
            else:
                return 0.32
        else:
            if income < 11925:
                return 0.10
            elif income < 48475:
                return 0.12
            elif income < 103350:
                return 0.22
            elif income < 197300:
                return 0.24
            else:
                return 0.32

    # =========================================================================
    # CONTACT CAPTURE & LEAD CREATION
    # =========================================================================

    def capture_contact(
        self,
        session_id: str,
        first_name: str,
        email: str,
        phone: Optional[str] = None,
    ) -> Tuple[LeadMagnetLead, List[TaxInsight]]:
        """
        Capture contact info and create lead.

        Args:
            session_id: Session ID
            first_name: Lead's first name
            email: Lead's email (required)
            phone: Lead's phone (optional)

        Returns:
            Created lead and insights for report generation
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        if not session.tax_profile:
            raise ValueError("Profile must be submitted before contact capture")

        # Generate insights if not already done
        insights = self._generate_insights(session.tax_profile, session.complexity)

        # Calculate lead score
        lead_score, temperature, engagement_value = self._calculate_lead_score(
            session.tax_profile,
            session.complexity,
            insights,
            session.time_spent_seconds,
        )

        # Calculate savings range
        savings_low = sum(i.savings_low for i in insights)
        savings_high = sum(i.savings_high for i in insights)

        # Create lead
        lead_id = f"lead-{uuid.uuid4().hex[:12]}"
        lead = LeadMagnetLead(
            lead_id=lead_id,
            session_id=session_id,
            cpa_id=session.cpa_profile.cpa_id if session.cpa_profile else None,
            first_name=first_name,
            email=email,
            phone=phone,
            filing_status=session.tax_profile.filing_status.value,
            complexity=session.complexity,
            income_range=session.tax_profile.income_range,
            lead_score=lead_score,
            lead_temperature=temperature,
            estimated_engagement_value=engagement_value,
            conversion_probability=lead_score / 100,
            savings_range_low=savings_low,
            savings_range_high=savings_high,
        )

        # Persist lead
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            # Update session
            cursor.execute("""
                UPDATE lead_magnet_sessions SET
                    contact_captured = 1,
                    current_screen = 'report',
                    completed_at = ?,
                    last_activity = ?
                WHERE session_id = ?
            """, (datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), session_id))

            # Insert lead
            cursor.execute("""
                INSERT INTO lead_magnet_leads (
                    lead_id, session_id, cpa_id, first_name, email, phone,
                    filing_status, complexity, income_range,
                    lead_score, lead_temperature, estimated_engagement_value,
                    conversion_probability, savings_range_low, savings_range_high
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lead_id, session_id, lead.cpa_id, first_name, email, phone,
                lead.filing_status, lead.complexity.value, lead.income_range,
                lead_score, temperature.value, engagement_value,
                lead.conversion_probability, savings_low, savings_high,
            ))

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to persist lead: {e}")

        session.contact_captured = True
        self._leads[lead_id] = lead

        logger.info(f"Lead {lead_id} captured for session {session_id}, score: {lead_score}")

        # =================================================================
        # TRIGGER NOTIFICATIONS
        # =================================================================
        self._send_lead_notifications(session, lead, insights)

        return lead, insights

    def _send_lead_notifications(
        self,
        session: LeadMagnetSession,
        lead: LeadMagnetLead,
        insights: List[TaxInsight],
    ):
        """Send notifications when a new lead is captured."""
        try:
            from .notification_service import get_notification_service

            notification_service = get_notification_service()
            cpa_profile = session.cpa_profile or self._default_cpa

            # 1. Notify CPA of new lead
            if cpa_profile.email:
                lead_data = {
                    "lead_id": lead.lead_id,
                    "first_name": lead.first_name,
                    "email": lead.email,
                    "phone": lead.phone,
                    "lead_score": lead.lead_score,
                    "lead_temperature": lead.lead_temperature.value,
                    "complexity": lead.complexity.value,
                    "savings_range": f"${lead.savings_range_low:,.0f} - ${lead.savings_range_high:,.0f}",
                    "dashboard_url": f"/cpa/dashboard?lead={lead.lead_id}",
                }
                notification_service.notify_new_lead(
                    cpa_email=cpa_profile.email,
                    cpa_name=cpa_profile.display_name,
                    lead_data=lead_data,
                )
                logger.info(f"Sent new lead notification to CPA: {cpa_profile.email}")

            # 2. Send report to prospect
            report_data = {
                "session_id": session.session_id,
                "savings_range": f"${lead.savings_range_low:,.0f} - ${lead.savings_range_high:,.0f}",
                "total_insights": len(insights),
                "locked_count": max(0, len(insights) - 3),
                "insights": [i.to_dict(tier=1) for i in insights[:3]],
                "booking_link": cpa_profile.booking_link or "#contact",
            }
            notification_service.send_report_to_prospect(
                prospect_email=lead.email,
                prospect_name=lead.first_name,
                cpa_name=cpa_profile.display_name,
                cpa_firm=cpa_profile.firm_name,
                report_data=report_data,
            )
            logger.info(f"Sent report notification to prospect: {lead.email}")

        except Exception as e:
            logger.warning(f"Failed to send notifications: {e}")

    def _calculate_lead_score(
        self,
        profile: TaxProfile,
        complexity: TaxComplexity,
        insights: List[TaxInsight],
        time_spent: int,
    ) -> Tuple[int, LeadTemperature, float]:
        """
        Calculate lead score, temperature, and engagement value.

        Factors:
        - Complexity (more complex = higher value)
        - Income range (higher = higher value)
        - Number of insights (more opportunities = higher value)
        - Total potential savings
        - Time spent (engagement indicator)
        """
        score = 50  # Base score

        # Complexity bonus
        complexity_bonus = {
            TaxComplexity.SIMPLE: 0,
            TaxComplexity.MODERATE: 10,
            TaxComplexity.COMPLEX: 20,
            TaxComplexity.PROFESSIONAL: 30,
        }
        score += complexity_bonus.get(complexity, 0)

        # Income bonus
        income = self._parse_income_range(profile.income_range)
        if income >= 200000:
            score += 20
        elif income >= 100000:
            score += 10
        elif income >= 75000:
            score += 5

        # Savings potential
        total_savings = sum(i.savings_high for i in insights)
        if total_savings >= 5000:
            score += 15
        elif total_savings >= 2500:
            score += 10
        elif total_savings >= 1000:
            score += 5

        # Time spent engagement
        if time_spent >= 180:  # 3+ minutes
            score += 5
        elif time_spent >= 120:  # 2+ minutes
            score += 3

        # Cap at 100
        score = min(100, score)

        # Determine temperature
        if score >= 80:
            temperature = LeadTemperature.HOT
        elif score >= 60:
            temperature = LeadTemperature.WARM
        else:
            temperature = LeadTemperature.COLD

        # Estimate engagement value (simplified)
        # Complex returns typically have higher fees
        base_value = {
            TaxComplexity.SIMPLE: 200,
            TaxComplexity.MODERATE: 400,
            TaxComplexity.COMPLEX: 800,
            TaxComplexity.PROFESSIONAL: 1500,
        }
        engagement_value = base_value.get(complexity, 300) * (score / 50)

        return score, temperature, engagement_value

    # =========================================================================
    # LEAD MANAGEMENT (CPA SIDE)
    # =========================================================================

    def get_lead(self, lead_id: str) -> Optional[LeadMagnetLead]:
        """Get lead by ID."""
        if lead_id in self._leads:
            return self._leads[lead_id]

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM lead_magnet_leads WHERE lead_id = ?", (lead_id,))
            row = cursor.fetchone()
            conn.close()

            if row:
                lead = LeadMagnetLead(
                    lead_id=row["lead_id"],
                    session_id=row["session_id"],
                    cpa_id=row["cpa_id"],
                    first_name=row["first_name"],
                    email=row["email"],
                    phone=row["phone"],
                    filing_status=row["filing_status"],
                    complexity=TaxComplexity(row["complexity"]),
                    income_range=row["income_range"],
                    lead_score=row["lead_score"],
                    lead_temperature=LeadTemperature(row["lead_temperature"]),
                    estimated_engagement_value=row["estimated_engagement_value"],
                    conversion_probability=row["conversion_probability"],
                    savings_range_low=row["savings_range_low"],
                    savings_range_high=row["savings_range_high"],
                    engaged=bool(row["engaged"]),
                    converted=bool(row["converted"]),
                )
                self._leads[lead_id] = lead
                return lead
        except Exception as e:
            logger.warning(f"Could not load lead {lead_id}: {e}")

        return None

    def mark_lead_engaged(
        self,
        lead_id: str,
        engagement_letter_acknowledged: bool = False
    ) -> Optional[LeadMagnetLead]:
        """
        Mark lead as engaged by CPA.

        COMPLIANCE NOTE: For Tier 2 report access, BOTH conditions must be met:
        1. engaged = True (CPA marks as engaged)
        2. engagement_letter_acknowledged = True (client acknowledges engagement letter)

        Args:
            lead_id: The lead ID to mark as engaged
            engagement_letter_acknowledged: Whether engagement letter has been acknowledged

        Returns:
            Updated LeadMagnetLead or None if not found
        """
        lead = self.get_lead(lead_id)
        if not lead:
            return None

        lead.engaged = True
        lead.engaged_at = datetime.utcnow()

        if engagement_letter_acknowledged:
            lead.engagement_letter_acknowledged = True
            lead.engagement_letter_acknowledged_at = datetime.utcnow()

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE lead_magnet_leads SET
                    engaged = 1,
                    engaged_at = ?,
                    engagement_letter_acknowledged = ?,
                    engagement_letter_acknowledged_at = ?
                WHERE lead_id = ?
            """, (
                datetime.utcnow().isoformat(),
                1 if engagement_letter_acknowledged else 0,
                datetime.utcnow().isoformat() if engagement_letter_acknowledged else None,
                lead_id
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to update lead engagement: {e}")

        return lead

    def acknowledge_engagement_letter(self, lead_id: str) -> Optional[LeadMagnetLead]:
        """
        Mark that the engagement letter has been acknowledged.

        COMPLIANCE REQUIREMENT: This must be called BEFORE Tier 2 report can be accessed.
        The engagement letter establishes the CPA-client relationship and liability terms.

        Args:
            lead_id: The lead ID

        Returns:
            Updated LeadMagnetLead or None if not found
        """
        lead = self.get_lead(lead_id)
        if not lead:
            return None

        lead.engagement_letter_acknowledged = True
        lead.engagement_letter_acknowledged_at = datetime.utcnow()

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE lead_magnet_leads SET
                    engagement_letter_acknowledged = 1,
                    engagement_letter_acknowledged_at = ?
                WHERE lead_id = ?
            """, (datetime.utcnow().isoformat(), lead_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to update engagement letter acknowledgment: {e}")

        return lead

    def can_access_tier_two_report(self, lead_id: str) -> Tuple[bool, str]:
        """
        Check if a lead can access the Tier 2 full report.

        COMPLIANCE GUARDRAIL: This enforces the two-step requirement:
        1. CPA must mark lead as engaged
        2. Engagement letter must be acknowledged

        Returns:
            Tuple of (can_access: bool, reason: str)
        """
        lead = self.get_lead(lead_id)
        if not lead:
            return False, "Lead not found"

        if not lead.engaged:
            return False, "CPA has not marked this lead as engaged"

        if not lead.engagement_letter_acknowledged:
            return False, "Engagement letter has not been acknowledged"

        return True, "Access granted"

    def can_access_tier_two_report_by_session(self, session_id: str) -> Tuple[bool, str]:
        """
        Check if a session's lead can access the Tier 2 full report.

        COMPLIANCE GUARDRAIL: This enforces the two-step requirement:
        1. CPA must mark lead as engaged
        2. Engagement letter must be acknowledged

        Returns:
            Tuple of (can_access: bool, reason: str)
        """
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT lead_id, engaged, engagement_letter_acknowledged
                FROM lead_magnet_leads
                WHERE session_id = ?
            """, (session_id,))
            row = cursor.fetchone()
            conn.close()

            if not row:
                return False, "No lead found for this session"

            if not row["engaged"]:
                return False, "CPA has not marked this lead as engaged"

            if not row["engagement_letter_acknowledged"]:
                return False, "Engagement letter has not been acknowledged"

            return True, "Access granted"

        except Exception as e:
            logger.error(f"Failed to check Tier 2 access for session {session_id}: {e}")
            return False, f"Error checking access: {e}"

    def get_leads_for_cpa(
        self,
        cpa_id: str,
        include_engaged: bool = True,
    ) -> List[LeadMagnetLead]:
        """Get all leads for a CPA."""
        leads = []

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            query = "SELECT * FROM lead_magnet_leads WHERE cpa_id = ?"
            params = [cpa_id]

            if not include_engaged:
                query += " AND engaged = 0"

            query += " ORDER BY lead_score DESC, created_at DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            for row in rows:
                lead = LeadMagnetLead(
                    lead_id=row["lead_id"],
                    session_id=row["session_id"],
                    cpa_id=row["cpa_id"],
                    first_name=row["first_name"],
                    email=row["email"],
                    phone=row["phone"],
                    filing_status=row["filing_status"],
                    complexity=TaxComplexity(row["complexity"]),
                    income_range=row["income_range"],
                    lead_score=row["lead_score"],
                    lead_temperature=LeadTemperature(row["lead_temperature"]),
                    estimated_engagement_value=row["estimated_engagement_value"],
                    conversion_probability=row["conversion_probability"],
                    savings_range_low=row["savings_range_low"],
                    savings_range_high=row["savings_range_high"],
                    engaged=bool(row["engaged"]),
                    converted=bool(row["converted"]),
                )
                leads.append(lead)
        except Exception as e:
            logger.error(f"Failed to get leads for CPA: {e}")

        return leads

    # =========================================================================
    # ALIAS METHODS - For API route compatibility
    # =========================================================================

    def start_assessment_session(
        self,
        cpa_slug: Optional[str] = None,
        assessment_mode: str = "quick",
        referral_source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Alias for start_assessment - API route compatibility. Returns dict."""
        session = self.start_assessment(cpa_slug, assessment_mode, referral_source)
        return {
            "session_id": session.session_id,
            "cpa_profile": session.cpa_profile.to_dict() if session.cpa_profile else None,
            "assessment_mode": session.assessment_mode.value,
            "current_screen": session.current_screen,
            "referral_source": session.referral_source,
        }

    def submit_tax_profile(
        self,
        session_id: str,
        filing_status: str,
        dependents_count: int = 0,
        has_children_under_17: bool = False,
        income_range: str = "",
        income_sources: List[str] = None,
        is_homeowner: bool = False,
        retirement_savings: str = "none",
        healthcare_type: str = "employer",
        life_events: List[str] = None,
        has_student_loans: bool = False,
        has_business: bool = False,
        privacy_consent: bool = False,
    ) -> Dict[str, Any]:
        """Submit tax profile - API route compatibility. Returns dict."""
        # Build profile data dict
        profile_data = {
            "filing_status": filing_status,
            "dependents_count": dependents_count,
            "children_under_17": has_children_under_17,
            "income_range": income_range,
            "income_sources": income_sources or [],
            "is_homeowner": is_homeowner,
            "retirement_savings": retirement_savings,
            "healthcare_type": healthcare_type,
            "life_events": life_events or [],
        }

        # Add business to income sources if indicated
        if has_business and "self_employed" not in (income_sources or []):
            profile_data["income_sources"].append("self_employed")

        # Call core method
        session, complexity, insights = self.submit_profile(session_id, profile_data)

        return {
            "session_id": session_id,
            "complexity": complexity.value,
            "insights_count": len(insights),
            "insights_preview": [i.to_dict(tier=1) for i in insights[:3]],
        }

    def capture_contact_and_create_lead(
        self,
        session_id: str,
        first_name: str,
        email: str,
        phone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Capture contact and create lead - API route compatibility. Returns dict."""
        lead, insights = self.capture_contact(session_id, first_name, email, phone)
        return {
            "lead_id": lead.lead_id,
            "session_id": session_id,
            "first_name": lead.first_name,
            "email": lead.email,
            "lead_score": lead.lead_score,
            "lead_temperature": lead.lead_temperature.value,
            "complexity": lead.complexity.value,
            "savings_range_low": lead.savings_range_low,
            "savings_range_high": lead.savings_range_high,
            "insights_count": len(insights),
        }

    def get_cpa_profile_by_slug(self, cpa_slug: str) -> Optional[Dict[str, Any]]:
        """Get CPA profile by slug and return as dict."""
        profile = self.get_cpa_profile(cpa_slug)
        if profile:
            return profile.to_dict()
        return None

    # =========================================================================
    # REPORT GENERATION
    # =========================================================================

    def get_tier_one_report(self, session_id: str) -> Dict[str, Any]:
        """
        Generate Tier 1 (FREE) report for a session.

        Shows:
        - CPA branding
        - Savings range (not exact)
        - 3-5 teaser insights
        - CTA to contact CPA
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        # Get lead if exists
        lead = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM lead_magnet_leads WHERE session_id = ?",
                (session_id,)
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                lead = LeadMagnetLead(
                    lead_id=row["lead_id"],
                    session_id=row["session_id"],
                    cpa_id=row["cpa_id"],
                    first_name=row["first_name"],
                    email=row["email"],
                    phone=row["phone"],
                    filing_status=row["filing_status"],
                    complexity=TaxComplexity(row["complexity"]) if row["complexity"] else TaxComplexity.SIMPLE,
                    income_range=row["income_range"],
                    lead_score=row["lead_score"],
                    lead_temperature=LeadTemperature(row["lead_temperature"]) if row["lead_temperature"] else LeadTemperature.WARM,
                    estimated_engagement_value=row["estimated_engagement_value"],
                    conversion_probability=row["conversion_probability"],
                    savings_range_low=row["savings_range_low"],
                    savings_range_high=row["savings_range_high"],
                    engaged=bool(row["engaged"]),
                    engagement_letter_acknowledged=bool(row["engagement_letter_acknowledged"]) if "engagement_letter_acknowledged" in row.keys() else False,
                )
        except Exception as e:
            logger.warning(f"Could not load lead for session {session_id}: {e}")

        # Get CPA profile
        cpa_profile = session.cpa_profile if session.cpa_profile else self._default_cpa

        # Parse profile data from tax_profile
        profile_data = session.tax_profile.to_dict() if session.tax_profile else {}
        complexity = session.complexity if session.complexity else TaxComplexity.SIMPLE

        # Get insights (limited to 3-5 for Tier 1)
        insights = profile_data.get("insights", [])[:5]

        # Calculate savings range
        savings_low = lead.savings_range_low if lead else 500
        savings_high = lead.savings_range_high if lead else 2000

        # Generate insights from tax profile if we have it
        generated_insights = []
        if session.tax_profile:
            generated_insights = self._generate_insights(session.tax_profile, complexity)

        return {
            "session_id": session_id,
            "lead_id": lead.lead_id if lead else None,
            "tier": 1,
            "cpa_name": cpa_profile.full_title,  # property, not method
            "cpa_firm": cpa_profile.firm_name or "",
            "cpa_email": cpa_profile.email or "",
            "cpa_phone": cpa_profile.phone or "",
            "booking_link": cpa_profile.booking_link or "#contact",
            "client_name": lead.first_name if lead else "Valued Client",
            "filing_status": profile_data.get("filing_status", "single"),
            "complexity": complexity.value,
            "savings_range": f"${savings_low:,.0f} - ${savings_high:,.0f}",
            "insights": [
                i.to_dict(tier=1) for i in generated_insights[:5]
            ] if generated_insights else [],
            "total_insights": len(generated_insights) if generated_insights else 3,
            "locked_count": max(0, len(generated_insights) - 5) if generated_insights else 3,
            "cta_text": f"Schedule a consultation with {cpa_profile.first_name} to unlock your full analysis",
            "report_html": "",  # Can generate HTML if needed
        }

    def get_tier_two_report(self, session_id: str) -> Dict[str, Any]:
        """
        Generate Tier 2 (Full) report for a session.

        COMPLIANCE: This should only be called after verifying access via
        can_access_tier_two_report_by_session()

        Shows everything from Tier 1 plus:
        - Exact savings amounts
        - All insights with full details
        - Action items with deadlines
        - IRS references
        - Tax calendar
        """
        # Get Tier 1 data as base
        report = self.get_tier_one_report(session_id)
        report["tier"] = 2

        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        # Get all insights from tax profile
        all_insights = []
        if session.tax_profile:
            complexity = session.complexity if session.complexity else TaxComplexity.SIMPLE
            all_insights = self._generate_insights(session.tax_profile, complexity)

        # Calculate exact savings
        total_savings = sum(i.savings_high for i in all_insights)

        # Generate action items
        action_items = []
        for insight in all_insights:
            if insight.action_items:
                for action in insight.action_items:
                    action_items.append({
                        "title": action,
                        "description": f"Related to: {insight.title}",
                        "deadline": insight.deadline or "",
                        "irs_reference": insight.irs_reference or "",
                    })

        # Generate tax calendar
        tax_calendar = [
            {"date": "2025-04-15", "title": "Tax Filing Deadline", "description": "Federal and state returns due"},
            {"date": "2025-01-15", "title": "Q4 Estimated Tax", "description": "Fourth quarter estimated payment due"},
            {"date": "2025-06-15", "title": "Q2 Estimated Tax", "description": "Second quarter estimated payment due"},
        ]

        report.update({
            "total_savings": f"${total_savings:,.0f}",
            "total_savings_amount": total_savings,
            "all_insights": [i.to_dict(tier=2) for i in all_insights],
            "action_items": action_items,
            "tax_calendar": tax_calendar,
            "locked_count": 0,
        })

        return report

    # =========================================================================
    # LEAD MANAGEMENT
    # =========================================================================

    def get_leads(
        self,
        cpa_id: Optional[str] = None,
        temperature: Optional[str] = None,
        engaged: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get leads with filtering options."""
        leads = []

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            query = "SELECT * FROM lead_magnet_leads WHERE 1=1"
            params = []

            if cpa_id:
                query += " AND cpa_id = ?"
                params.append(cpa_id)

            if temperature:
                query += " AND lead_temperature = ?"
                params.append(temperature)

            if engaged is not None:
                query += " AND engaged = ?"
                params.append(1 if engaged else 0)

            query += " ORDER BY lead_score DESC, created_at DESC"
            query += f" LIMIT {limit} OFFSET {offset}"

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            for row in rows:
                leads.append({
                    "lead_id": row["lead_id"],
                    "session_id": row["session_id"],
                    "cpa_id": row["cpa_id"],
                    "first_name": row["first_name"],
                    "email": row["email"],
                    "phone": row["phone"],
                    "filing_status": row["filing_status"],
                    "complexity": row["complexity"],
                    "income_range": row["income_range"],
                    "lead_score": row["lead_score"],
                    "lead_temperature": row["lead_temperature"],
                    "estimated_engagement_value": row["estimated_engagement_value"],
                    "conversion_probability": row["conversion_probability"],
                    "savings_range_low": row["savings_range_low"],
                    "savings_range_high": row["savings_range_high"],
                    "savings_range": f"${row['savings_range_low']:,.0f} - ${row['savings_range_high']:,.0f}",
                    "engaged": bool(row["engaged"]),
                    "engagement_letter_acknowledged": bool(row["engagement_letter_acknowledged"]) if "engagement_letter_acknowledged" in row.keys() else False,
                    "created_at": row["created_at"],
                })

        except Exception as e:
            logger.error(f"Failed to get leads: {e}")

        return leads

    def get_lead_statistics(self, cpa_id: Optional[str] = None) -> Dict[str, Any]:
        """Get aggregate statistics for leads."""
        stats = {
            "total_leads": 0,
            "by_temperature": {"hot": 0, "warm": 0, "cold": 0},
            "by_complexity": {"simple": 0, "moderate": 0, "complex": 0, "professional": 0},
            "engaged_count": 0,
            "converted_count": 0,
            "average_lead_score": 0,
            "total_potential_value": 0,
        }

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            query = "SELECT * FROM lead_magnet_leads"
            params = []
            if cpa_id:
                query += " WHERE cpa_id = ?"
                params.append(cpa_id)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return stats

            total_score = 0
            for row in rows:
                stats["total_leads"] += 1

                temp = row["lead_temperature"]
                if temp in stats["by_temperature"]:
                    stats["by_temperature"][temp] += 1

                complexity = row["complexity"]
                if complexity in stats["by_complexity"]:
                    stats["by_complexity"][complexity] += 1

                if row["engaged"]:
                    stats["engaged_count"] += 1

                if row["converted"]:
                    stats["converted_count"] += 1

                total_score += row["lead_score"]
                stats["total_potential_value"] += row["estimated_engagement_value"]

            stats["average_lead_score"] = total_score / stats["total_leads"] if stats["total_leads"] > 0 else 0

        except Exception as e:
            logger.error(f"Failed to get lead statistics: {e}")

        return stats

    def convert_lead(self, lead_id: str) -> Dict[str, Any]:
        """Convert a lead to a client."""
        lead = self.get_lead(lead_id)
        if not lead:
            raise ValueError(f"Lead not found: {lead_id}")

        if not lead.engaged:
            raise ValueError("Lead must be engaged before converting")

        now = datetime.utcnow()

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE lead_magnet_leads SET
                    converted = 1,
                    converted_at = ?
                WHERE lead_id = ?
            """, (now.isoformat(), lead_id))
            conn.commit()
            conn.close()

            return {
                "lead_id": lead_id,
                "converted": True,
                "converted_at": now.isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to convert lead: {e}")
            raise

    def update_cpa_profile(
        self,
        cpa_id: str,
        first_name: str,
        last_name: str,
        cpa_slug: str,
        credentials: Optional[str] = "CPA",
        firm_name: Optional[str] = None,
        logo_url: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        booking_link: Optional[str] = None,
        address: Optional[str] = None,
        bio: Optional[str] = None,
        specialties: List[str] = None,
    ) -> Dict[str, Any]:
        """Update an existing CPA profile."""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE cpa_profiles SET
                    first_name = ?,
                    last_name = ?,
                    cpa_slug = ?,
                    credentials = ?,
                    firm_name = ?,
                    logo_url = ?,
                    email = ?,
                    phone = ?,
                    booking_link = ?,
                    address = ?,
                    bio = ?,
                    specialties_json = ?,
                    updated_at = ?
                WHERE cpa_id = ?
            """, (
                first_name,
                last_name,
                cpa_slug,
                credentials,
                firm_name,
                logo_url,
                email,
                phone,
                booking_link,
                address,
                bio,
                json.dumps(specialties or []),
                datetime.utcnow().isoformat(),
                cpa_id,
            ))
            conn.commit()
            conn.close()

            return {
                "cpa_id": cpa_id,
                "cpa_slug": cpa_slug,
                "first_name": first_name,
                "last_name": last_name,
                "credentials": credentials,
                "firm_name": firm_name,
                "email": email,
                "phone": phone,
                "booking_link": booking_link,
            }

        except Exception as e:
            logger.error(f"Failed to update CPA profile: {e}")
            raise ValueError(f"Failed to update profile: {e}")


# =============================================================================
# SINGLETON
# =============================================================================

_lead_magnet_service: Optional[LeadMagnetService] = None


def get_lead_magnet_service() -> LeadMagnetService:
    """Get the singleton lead magnet service instance."""
    global _lead_magnet_service
    if _lead_magnet_service is None:
        _lead_magnet_service = LeadMagnetService()
    return _lead_magnet_service
