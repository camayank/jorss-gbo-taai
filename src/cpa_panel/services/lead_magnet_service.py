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
import re
import sqlite3
import os
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal
from datetime import datetime, date, timezone
from enum import Enum
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse

from config.database import get_database_settings
from ..config.lead_magnet_score_config import SCORE_BENCHMARKS, get_score_weights
logger = logging.getLogger(__name__)

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except Exception:  # pragma: no cover - optional runtime dependency path
    psycopg2 = None
    RealDictCursor = None


STATE_DISPLAY_NAMES: Dict[str, str] = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
    "DC": "District of Columbia",
}

HIGH_TAX_STATES = {"CA", "NY", "NJ", "OR", "MN", "HI", "MA", "VT", "DC"}
PROPERTY_TAX_HEAVY_STATES = {"TX", "NJ", "IL", "CT", "NH", "VT"}


class _DbCursorAdapter:
    """Normalize sqlite/postgres cursor behavior for existing query code."""

    def __init__(self, cursor: Any, is_postgres: bool):
        self._cursor = cursor
        self._is_postgres = is_postgres

    @staticmethod
    def _normalize_query(query: str, is_postgres: bool) -> str:
        if not is_postgres:
            return query
        # Existing service queries use sqlite-style '?' placeholders.
        return query.replace("?", "%s")

    def execute(self, query: str, params: Optional[Tuple[Any, ...]] = None):
        normalized_query = self._normalize_query(query, self._is_postgres)
        if params is None:
            self._cursor.execute(normalized_query)
        else:
            self._cursor.execute(normalized_query, params)
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        # sqlite3.Row supports key access but not .get() — normalize to dict
        if row is not None and not self._is_postgres and hasattr(row, "keys"):
            return dict(row)
        return row

    def fetchall(self):
        rows = self._cursor.fetchall()
        if rows and not self._is_postgres and rows and hasattr(rows[0], "keys"):
            return [dict(r) for r in rows]
        return rows

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


class _DbConnectionAdapter:
    """Wrap native DB connections with a consistent cursor() contract."""

    def __init__(self, connection: Any, is_postgres: bool):
        self._connection = connection
        self._is_postgres = is_postgres

    def cursor(self) -> _DbCursorAdapter:
        if self._is_postgres:
            return _DbCursorAdapter(
                self._connection.cursor(cursor_factory=RealDictCursor),
                is_postgres=True,
            )
        return _DbCursorAdapter(self._connection.cursor(), is_postgres=False)

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()


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
    firm_id: Optional[str] = None
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
            "firm_id": self.firm_id,
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
    state_code: str = "US"
    occupation_type: str = "w2"
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
            "state_code": self.state_code,
            "occupation_type": self.occupation_type,
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
                logger.debug(f"Skipping invalid income source: {s!r}")

        # Handle life_events - may be strings or LifeEvent enums
        life_events = []
        for e in data.get("life_events", []):
            try:
                life_events.append(LifeEvent(e) if isinstance(e, str) else e)
            except ValueError:
                logger.debug(f"Skipping invalid life event: {e!r}")

        return cls(
            filing_status=FilingStatus(data.get("filing_status", "single")),
            state_code=(data.get("state_code") or "US").upper(),
            occupation_type=data.get("occupation_type", "w2"),
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
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    time_spent_seconds: int = 0
    referral_source: Optional[str] = None
    variant_id: str = "A"
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    device_type: Optional[str] = None

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
            "referral_source": self.referral_source,
            "variant_id": self.variant_id,
            "utm_source": self.utm_source,
            "utm_medium": self.utm_medium,
            "utm_campaign": self.utm_campaign,
            "device_type": self.device_type,
        }


@dataclass
class LeadMagnetLead:
    """A captured lead with scoring."""
    lead_id: str
    session_id: str
    cpa_id: Optional[str] = None
    firm_id: Optional[str] = None
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
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

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
        self._db_settings = get_database_settings()
        self._db_backend = "postgres" if self._db_settings.is_postgres else "sqlite"
        # Keep SQLite fallback aligned with shared DB settings while honoring
        # test/runtime overrides and legacy local data paths.
        configured_sqlite_path = Path(self._db_settings.sqlite_path).expanduser()
        override_sqlite_path = os.environ.get("DATABASE_PATH", "").strip()
        legacy_sqlite_path = Path(__file__).parent.parent.parent / "database" / "jorss_gbo.db"

        if override_sqlite_path:
            self._sqlite_db_path = Path(override_sqlite_path).expanduser()
        elif (
            configured_sqlite_path.exists()
            and self._sqlite_has_table(configured_sqlite_path, "lead_magnet_sessions")
        ):
            self._sqlite_db_path = configured_sqlite_path
        elif legacy_sqlite_path.exists():
            self._sqlite_db_path = legacy_sqlite_path
        else:
            self._sqlite_db_path = configured_sqlite_path
        if self._db_backend == "sqlite":
            self._ensure_core_tables()
            self._ensure_event_table()
            self._ensure_session_columns()

    def _get_db_connection(self):
        """Get database connection."""
        if self._db_backend == "postgres":
            if psycopg2 is None or RealDictCursor is None:
                raise RuntimeError(
                    "PostgreSQL backend selected but psycopg2 is unavailable."
                )
            sync_url = self._db_settings.sync_url
            # psycopg2 accepts a PostgreSQL URI, not SQLAlchemy dialect+driver format.
            if sync_url.startswith("postgresql+psycopg2://"):
                sync_url = sync_url.replace("postgresql+psycopg2://", "postgresql://", 1)
            conn = psycopg2.connect(sync_url)
            return _DbConnectionAdapter(conn, is_postgres=True)

        self._sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._sqlite_db_path))
        conn.row_factory = sqlite3.Row
        return _DbConnectionAdapter(conn, is_postgres=False)

    def _sqlite_has_table(self, db_path: Path, table_name: str) -> bool:
        """Return True when a SQLite database file already contains a table."""
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
                (table_name,),
            )
            exists = cursor.fetchone() is not None
            conn.close()
            return exists
        except Exception:
            return False

    def _ensure_core_tables(self):
        """Ensure core lead magnet tables exist (idempotent — safe to run on every startup)."""
        if self._db_backend == "postgres":
            return
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cpa_profiles (
                    cpa_id TEXT PRIMARY KEY,
                    cpa_slug TEXT UNIQUE,
                    firm_name TEXT,
                    logo_url TEXT,
                    primary_color TEXT,
                    accent_color TEXT,
                    cpa_email TEXT,
                    active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS lead_magnet_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    cpa_id TEXT,
                    cpa_slug TEXT,
                    assessment_mode TEXT DEFAULT 'quick',
                    current_screen TEXT DEFAULT 'welcome',
                    privacy_consent INTEGER DEFAULT 0,
                    profile_data_json TEXT DEFAULT '{}',
                    contact_captured INTEGER DEFAULT 0,
                    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_activity TEXT DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT,
                    time_spent_seconds INTEGER DEFAULT 0,
                    referral_source TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS lead_magnet_leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lead_id TEXT UNIQUE NOT NULL,
                    session_id TEXT NOT NULL,
                    cpa_id TEXT,
                    firm_id TEXT,
                    first_name TEXT,
                    email TEXT NOT NULL,
                    phone TEXT,
                    filing_status TEXT,
                    complexity TEXT DEFAULT 'simple',
                    income_range TEXT,
                    lead_score INTEGER DEFAULT 50,
                    lead_temperature TEXT DEFAULT 'warm',
                    estimated_engagement_value REAL DEFAULT 0,
                    conversion_probability REAL DEFAULT 0.5,
                    savings_range_low REAL DEFAULT 0,
                    savings_range_high REAL DEFAULT 0,
                    engaged INTEGER DEFAULT 0,
                    engaged_at TEXT,
                    engagement_letter_acknowledged INTEGER DEFAULT 0,
                    engagement_letter_acknowledged_at TEXT,
                    converted INTEGER DEFAULT 0,
                    converted_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tiered_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_id TEXT UNIQUE NOT NULL,
                    session_id TEXT NOT NULL,
                    lead_id TEXT,
                    report_type TEXT DEFAULT 'tier1',
                    report_data_json TEXT DEFAULT '{}',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.warning("Failed to ensure core lead magnet tables: %s", exc)

    def _ensure_event_table(self):
        """Ensure analytics event table exists for funnel instrumentation."""
        if self._db_backend == "postgres":
            return
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS lead_magnet_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT UNIQUE NOT NULL,
                    session_id TEXT NOT NULL,
                    cpa_id TEXT,
                    event_name TEXT NOT NULL,
                    step TEXT,
                    variant_id TEXT,
                    utm_source TEXT,
                    utm_medium TEXT,
                    utm_campaign TEXT,
                    device_type TEXT,
                    metadata_json TEXT DEFAULT '{}',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_lead_magnet_events_session
                ON lead_magnet_events(session_id, created_at DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_lead_magnet_events_name
                ON lead_magnet_events(event_name, created_at DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_lead_magnet_events_variant
                ON lead_magnet_events(variant_id, created_at DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_lead_magnet_events_utm_source
                ON lead_magnet_events(utm_source, created_at DESC)
            """)
            self._ensure_column(
                cursor,
                table_name="lead_magnet_events",
                column_name="variant_id",
                column_def="TEXT",
            )
            self._ensure_column(
                cursor,
                table_name="lead_magnet_events",
                column_name="utm_source",
                column_def="TEXT",
            )
            self._ensure_column(
                cursor,
                table_name="lead_magnet_events",
                column_name="utm_medium",
                column_def="TEXT",
            )
            self._ensure_column(
                cursor,
                table_name="lead_magnet_events",
                column_name="utm_campaign",
                column_def="TEXT",
            )
            self._ensure_column(
                cursor,
                table_name="lead_magnet_events",
                column_name="device_type",
                column_def="TEXT",
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.warning("Failed to ensure lead_magnet_events table: %s", exc)

    @staticmethod
    def _validate_sql_identifier(name: str) -> str:
        """Validate a SQL identifier (table/column name) to prevent injection."""
        if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', name):
            raise ValueError(f"Invalid SQL identifier: {name!r}")
        return name

    def _ensure_column(
        self,
        cursor: sqlite3.Cursor,
        table_name: str,
        column_name: str,
        column_def: str,
    ) -> None:
        """Idempotently add a column to a SQLite table if missing."""
        try:
            self._validate_sql_identifier(table_name)
            self._validate_sql_identifier(column_name)
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = {row[1] for row in cursor.fetchall()}
            if column_name not in columns:
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
        except Exception as exc:
            logger.debug("Skipping ensure column %s.%s: %s", table_name, column_name, exc)

    def _ensure_session_columns(self):
        """Ensure lead_magnet_sessions has experiment and attribution columns."""
        if self._db_backend == "postgres":
            return
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            self._ensure_column(cursor, "lead_magnet_sessions", "variant_id", "TEXT DEFAULT 'A'")
            self._ensure_column(cursor, "lead_magnet_sessions", "utm_source", "TEXT")
            self._ensure_column(cursor, "lead_magnet_sessions", "utm_medium", "TEXT")
            self._ensure_column(cursor, "lead_magnet_sessions", "utm_campaign", "TEXT")
            self._ensure_column(cursor, "lead_magnet_sessions", "device_type", "TEXT")
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.debug("Could not ensure lead_magnet_sessions columns: %s", exc)

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

    def _persistable_cpa_id(self, cpa_profile: Optional[CPAProfile]) -> Optional[str]:
        """
        Return a database-safe CPA id.

        The fallback default profile is in-memory only, so it should not be
        written into FK-constrained PostgreSQL tables.
        """
        if not cpa_profile:
            return None
        if cpa_profile.cpa_id == self._default_cpa.cpa_id:
            return None
        return cpa_profile.cpa_id

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
                "SELECT * FROM cpa_profiles WHERE cpa_slug = ? AND active = TRUE",
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
                    firm_id=row.get("firm_id"),
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
                    cpa_id, cpa_slug, firm_id, first_name, last_name, credentials,
                    firm_name, logo_url, email, phone, booking_link,
                    address, bio, specialties_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cpa_id, final_slug, profile.firm_id, profile.first_name, profile.last_name,
                profile.credentials, profile.firm_name, profile.logo_url,
                profile.email, profile.phone, profile.booking_link,
                profile.address, profile.bio, json.dumps(profile.specialties),
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to create CPA profile: {e}")
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass

        self._cpa_profiles[final_slug] = profile
        return profile.to_dict()

    def _generate_slug(self, first_name: str, last_name: str) -> str:
        """Generate URL-friendly slug from name."""
        slug = f"{first_name}-{last_name}".lower()
        slug = "".join(c if c.isalnum() or c == "-" else "-" for c in slug)
        return slug

    def _extract_utm_from_referral(self, referral_source: Optional[str]) -> Dict[str, Optional[str]]:
        """Extract UTM parameters from a referral URL if available."""
        if not referral_source:
            return {
                "utm_source": None,
                "utm_medium": None,
                "utm_campaign": None,
            }
        try:
            parsed = urlparse(referral_source)
            params = dict(parse_qsl(parsed.query))
            return {
                "utm_source": params.get("utm_source"),
                "utm_medium": params.get("utm_medium"),
                "utm_campaign": params.get("utm_campaign"),
            }
        except Exception:
            return {
                "utm_source": None,
                "utm_medium": None,
                "utm_campaign": None,
            }

    # =========================================================================
    # ASSESSMENT SESSION MANAGEMENT
    # =========================================================================

    def start_assessment(
        self,
        cpa_slug: Optional[str] = None,
        assessment_mode: str = "quick",
        referral_source: Optional[str] = None,
        variant_id: Optional[str] = None,
        utm_source: Optional[str] = None,
        utm_medium: Optional[str] = None,
        utm_campaign: Optional[str] = None,
        device_type: Optional[str] = None,
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
        inferred_utm = self._extract_utm_from_referral(referral_source)
        final_utm_source = utm_source or inferred_utm["utm_source"]
        final_utm_medium = utm_medium or inferred_utm["utm_medium"]
        final_utm_campaign = utm_campaign or inferred_utm["utm_campaign"]

        session = LeadMagnetSession(
            session_id=session_id,
            cpa_profile=cpa_profile,
            assessment_mode=mode,
            current_screen="welcome",
            referral_source=referral_source,
            variant_id=(variant_id or "A").upper(),
            utm_source=final_utm_source,
            utm_medium=final_utm_medium,
            utm_campaign=final_utm_campaign,
            device_type=device_type,
        )

        # Persist to database
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            stored_cpa_id = self._persistable_cpa_id(cpa_profile)
            cursor.execute("""
                INSERT INTO lead_magnet_sessions (
                    session_id, cpa_id, cpa_slug, assessment_mode,
                    current_screen, referral_source, variant_id,
                    utm_source, utm_medium, utm_campaign, device_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                stored_cpa_id,
                cpa_profile.cpa_slug,
                mode.value,
                "welcome",
                referral_source,
                session.variant_id,
                final_utm_source,
                final_utm_medium,
                final_utm_campaign,
                device_type,
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to persist session: {e}")
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass

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
                    variant_id=row["variant_id"] if "variant_id" in row.keys() and row["variant_id"] else "A",
                    utm_source=row["utm_source"] if "utm_source" in row.keys() else None,
                    utm_medium=row["utm_medium"] if "utm_medium" in row.keys() else None,
                    utm_campaign=row["utm_campaign"] if "utm_campaign" in row.keys() else None,
                    device_type=row["device_type"] if "device_type" in row.keys() else None,
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
        session.last_activity = datetime.now(timezone.utc)

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE lead_magnet_sessions SET
                    current_screen = ?,
                    last_activity = ?
                WHERE session_id = ?
            """, (screen, datetime.now(timezone.utc).isoformat(), session_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to update session screen: {e}")
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass

        return session

    def track_event(
        self,
        session_id: str,
        event_name: str,
        step: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        variant_id: Optional[str] = None,
        utm_source: Optional[str] = None,
        utm_medium: Optional[str] = None,
        utm_campaign: Optional[str] = None,
        device_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Persist a funnel analytics event.

        This powers launch KPIs:
        - start
        - step_complete
        - drop_off
        - lead_submit
        - report_view
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        event_id = f"evt-{uuid.uuid4().hex[:12]}"
        created_at = datetime.now(timezone.utc).isoformat()
        safe_metadata = metadata or {}
        derived_variant = (
            variant_id
            or safe_metadata.get("variant_id")
            or safe_metadata.get("hero_variant")
            or session.variant_id
            or "A"
        )
        derived_utm_source = utm_source or safe_metadata.get("utm_source") or session.utm_source
        derived_utm_medium = utm_medium or safe_metadata.get("utm_medium") or session.utm_medium
        derived_utm_campaign = utm_campaign or safe_metadata.get("utm_campaign") or session.utm_campaign
        derived_device = device_type or safe_metadata.get("device_type") or safe_metadata.get("device") or session.device_type

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO lead_magnet_events (
                    event_id, session_id, cpa_id, event_name, step, variant_id,
                    utm_source, utm_medium, utm_campaign, device_type, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id,
                session_id,
                self._persistable_cpa_id(session.cpa_profile),
                event_name,
                step,
                derived_variant,
                derived_utm_source,
                derived_utm_medium,
                derived_utm_campaign,
                derived_device,
                json.dumps(safe_metadata),
                created_at,
            ))
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.error("Failed to persist lead magnet event: %s", exc)
            raise

        if step:
            self.update_session_screen(session_id, step)

        logger.debug("Tracked lead-magnet event %s for session %s", event_name, session_id)
        return {
            "event_id": event_id,
            "session_id": session_id,
            "event_name": event_name,
            "step": step,
            "variant_id": derived_variant,
            "utm_source": derived_utm_source,
            "utm_medium": derived_utm_medium,
            "utm_campaign": derived_utm_campaign,
            "device_type": derived_device,
            "created_at": created_at,
        }

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
                    current_screen = 'teaser',
                    last_activity = ?
                WHERE session_id = ?
            """, (json.dumps(profile_data), datetime.now(timezone.utc).isoformat(), session_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to persist profile: {e}")

        logger.info(f"Profile submitted for {session_id}, complexity: {complexity.value}")

        return session, complexity, insights

    def _detect_complexity(self, profile: TaxProfile) -> TaxComplexity:
        """Detect tax complexity from profile. Delegates to calculator sub-module."""
        from cpa_panel.services.lead_magnet.calculator import detect_complexity
        return detect_complexity(profile)

    def _parse_income_range(self, range_str: str) -> int:
        """Parse income range string to approximate value. Delegates to calculator sub-module."""
        from cpa_panel.services.lead_magnet.calculator import parse_income_range
        return parse_income_range(range_str)

    # =========================================================================
    # INSIGHT GENERATION
    # =========================================================================

    def _generate_insights(
        self,
        profile: TaxProfile,
        complexity: TaxComplexity,
    ) -> List[TaxInsight]:
        """Generate tax insights based on profile. Delegates to generator sub-module."""
        from cpa_panel.services.lead_magnet.generator import generate_insights
        return generate_insights(profile, complexity)

    def _estimate_marginal_rate(self, income: int, filing_status: FilingStatus) -> float:
        """Estimate marginal tax rate. Delegates to calculator sub-module."""
        from cpa_panel.services.lead_magnet.calculator import estimate_marginal_rate
        return estimate_marginal_rate(income, filing_status)

    def _normalize_state_code(self, state_code: Optional[str]) -> str:
        """Normalize a state code. Delegates to generator sub-module."""
        from cpa_panel.services.lead_magnet.generator import normalize_state_code
        return normalize_state_code(state_code)

    def _filing_status_display(self, filing_status: FilingStatus) -> str:
        """Human-readable filing status. Delegates to generator sub-module."""
        from cpa_panel.services.lead_magnet.generator import filing_status_display
        return filing_status_display(filing_status)

    def _income_range_display(self, income_range: str) -> str:
        """Human-readable income range. Delegates to generator sub-module."""
        from cpa_panel.services.lead_magnet.generator import income_range_display
        return income_range_display(income_range)

    def _normalize_occupation_type(self, occupation_type: Optional[str], profile: Optional[TaxProfile] = None) -> str:
        """Normalize occupation type. Delegates to payloads sub-module."""
        from cpa_panel.services.lead_magnet.payloads import normalize_occupation_type
        return normalize_occupation_type(occupation_type, profile)

    def _occupation_display(self, profile: TaxProfile) -> str:
        """Human-readable occupation label. Delegates to payloads sub-module."""
        from cpa_panel.services.lead_magnet.payloads import occupation_display
        return occupation_display(profile)

    def _build_personalization_payload(self, profile, complexity, savings_low, savings_high):
        """Build personalization tokens. Delegates to payloads sub-module."""
        from cpa_panel.services.lead_magnet.payloads import build_personalization_payload
        return build_personalization_payload(profile, complexity, savings_low, savings_high)

    def _build_deadline_payload(self):
        """Build deadline urgency context. Delegates to payloads sub-module."""
        from cpa_panel.services.lead_magnet.payloads import build_deadline_payload
        return build_deadline_payload()

    def _build_comparison_chart_payload(self, savings_low, savings_high, score_overall):
        """Build comparison chart data. Delegates to payloads sub-module."""
        from cpa_panel.services.lead_magnet.payloads import build_comparison_chart_payload
        return build_comparison_chart_payload(savings_low, savings_high, score_overall)

    def _build_strategy_waterfall_payload(self, insights, limit=None):
        """Build strategy waterfall data. Delegates to payloads sub-module."""
        from cpa_panel.services.lead_magnet.payloads import build_strategy_waterfall_payload
        return build_strategy_waterfall_payload(insights, limit)

    def _build_tax_calendar_payload(self, max_items=5):
        """Build tax calendar events. Delegates to payloads sub-module."""
        from cpa_panel.services.lead_magnet.payloads import build_tax_calendar_payload
        return build_tax_calendar_payload(max_items)

    def _build_share_payload(self, session_id, score_overall, score_band, state_code, cpa_slug=None, estimated_savings=None):
        """Build share payload. Delegates to payloads sub-module."""
        from cpa_panel.services.lead_magnet.payloads import build_share_payload
        return build_share_payload(session_id, score_overall, score_band, state_code, cpa_slug, estimated_savings)

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
            cpa_id=self._persistable_cpa_id(session.cpa_profile),
            firm_id=session.cpa_profile.firm_id if session.cpa_profile else None,
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
                    contact_captured = TRUE,
                    current_screen = 'report',
                    completed_at = ?,
                    last_activity = ?
                WHERE session_id = ?
            """, (datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat(), session_id))

            # Insert lead
            cursor.execute("""
                INSERT INTO lead_magnet_leads (
                    lead_id, session_id, cpa_id, firm_id, first_name, email, phone,
                    filing_status, complexity, income_range,
                    lead_score, lead_temperature, estimated_engagement_value,
                    conversion_probability, savings_range_low, savings_range_high
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lead_id, session_id, lead.cpa_id, lead.firm_id, first_name, email, phone,
                lead.filing_status, lead.complexity.value, lead.income_range,
                lead_score, temperature.value, engagement_value,
                lead.conversion_probability, savings_low, savings_high,
            ))

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to persist lead: {e}")
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass

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
        """Calculate lead score, temperature, and engagement value. Delegates to calculator sub-module."""
        from cpa_panel.services.lead_magnet.calculator import calculate_lead_score
        return calculate_lead_score(profile, complexity, insights, time_spent)

    def _build_tax_health_score(
        self,
        profile: Optional[TaxProfile],
        complexity: TaxComplexity,
        insights: List[TaxInsight],
        savings_low: float,
        savings_high: float,
    ) -> Dict[str, Any]:
        """Build proprietary Tax Health Score. Delegates to calculator sub-module."""
        from cpa_panel.services.lead_magnet.calculator import build_tax_health_score
        return build_tax_health_score(profile, complexity, insights, savings_low, savings_high)

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
                    firm_id=row.get("firm_id"),
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
        lead.engaged_at = datetime.now(timezone.utc)

        if engagement_letter_acknowledged:
            lead.engagement_letter_acknowledged = True
            lead.engagement_letter_acknowledged_at = datetime.now(timezone.utc)

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE lead_magnet_leads SET
                    engaged = TRUE,
                    engaged_at = ?,
                    engagement_letter_acknowledged = ?,
                    engagement_letter_acknowledged_at = ?
                WHERE lead_id = ?
            """, (
                datetime.now(timezone.utc).isoformat(),
                bool(engagement_letter_acknowledged),
                datetime.now(timezone.utc).isoformat() if engagement_letter_acknowledged else None,
                lead_id
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to update lead engagement: {e}")
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass

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
        lead.engagement_letter_acknowledged_at = datetime.now(timezone.utc)

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE lead_magnet_leads SET
                    engagement_letter_acknowledged = TRUE,
                    engagement_letter_acknowledged_at = ?
                WHERE lead_id = ?
            """, (datetime.now(timezone.utc).isoformat(), lead_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to update engagement letter acknowledgment: {e}")
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass

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
                query += " AND engaged = FALSE"

            query += " ORDER BY lead_score DESC, created_at DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            for row in rows:
                lead = LeadMagnetLead(
                    lead_id=row["lead_id"],
                    session_id=row["session_id"],
                    cpa_id=row["cpa_id"],
                    firm_id=row.get("firm_id"),
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
        variant_id: Optional[str] = None,
        utm_source: Optional[str] = None,
        utm_medium: Optional[str] = None,
        utm_campaign: Optional[str] = None,
        device_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Alias for start_assessment - API route compatibility. Returns dict."""
        session = self.start_assessment(
            cpa_slug=cpa_slug,
            assessment_mode=assessment_mode,
            referral_source=referral_source,
            variant_id=variant_id,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            device_type=device_type,
        )
        return {
            "session_id": session.session_id,
            "cpa_profile": session.cpa_profile.to_dict() if session.cpa_profile else None,
            "assessment_mode": session.assessment_mode.value,
            "current_screen": session.current_screen,
            "referral_source": session.referral_source,
            "variant_id": session.variant_id,
        }

    def submit_tax_profile(
        self,
        session_id: str,
        filing_status: str,
        state_code: str = "US",
        occupation_type: Optional[str] = None,
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
            "state_code": self._normalize_state_code(state_code),
            "occupation_type": self._normalize_occupation_type(occupation_type),
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
            if profile_data["occupation_type"] == "w2":
                profile_data["occupation_type"] = "business_owner"

        # Call core method
        session, complexity, insights = self.submit_profile(session_id, profile_data)
        savings_low = sum(i.savings_low for i in insights)
        savings_high = sum(i.savings_high for i in insights)
        score = self._build_tax_health_score(
            session.tax_profile,
            complexity,
            insights,
            savings_low,
            savings_high,
        )
        personalization = self._build_personalization_payload(
            session.tax_profile,
            complexity,
            savings_low,
            savings_high,
        )
        comparison_chart = self._build_comparison_chart_payload(
            savings_low=savings_low,
            savings_high=savings_high,
            score_overall=score["overall"],
        )
        deadline_context = self._build_deadline_payload()

        return {
            "session_id": session_id,
            "complexity": complexity.value,
            "insights_count": len(insights),
            "insights_preview": [i.to_dict(tier=1) for i in insights[:3]],
            "score_preview": score["overall"],
            "score_band": score["band"],
            "missed_savings_range": score["missed_savings_range"],
            "personalization_line": personalization["line"],
            "personalization_tokens": personalization["tokens"],
            "comparison_chart": comparison_chart,
            "deadline_context": deadline_context,
            "score_benchmark": score.get("benchmark", {}),
        }

    def capture_contact_and_create_lead(
        self,
        session_id: str,
        first_name: str,
        email: str,
        phone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Capture contact and create lead - API route compatibility. Returns dict."""
        session = self.get_session(session_id)
        lead, insights = self.capture_contact(session_id, first_name, email, phone)
        return {
            "lead_id": lead.lead_id,
            "session_id": session_id,
            "first_name": lead.first_name,
            "email": lead.email,
            "cpa_email": session.cpa_profile.email if session and session.cpa_profile else None,
            "cpa_name": session.cpa_profile.display_name if session and session.cpa_profile else None,
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
                    firm_id=row.get("firm_id"),
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
            if not lead:
                savings_low = sum(i.savings_low for i in generated_insights)
                savings_high = sum(i.savings_high for i in generated_insights)
        score_payload = self._build_tax_health_score(
            session.tax_profile,
            complexity,
            generated_insights,
            savings_low,
            savings_high,
        )
        personalization = self._build_personalization_payload(
            session.tax_profile,
            complexity,
            savings_low,
            savings_high,
        )
        comparison_chart = self._build_comparison_chart_payload(
            savings_low=savings_low,
            savings_high=savings_high,
            score_overall=score_payload["overall"],
        )
        deadline_context = self._build_deadline_payload()
        estimated_savings_midpoint = int(round((savings_low + savings_high) / 2))
        share_payload = self._build_share_payload(
            session_id=session_id,
            score_overall=score_payload["overall"],
            score_band=score_payload["band"],
            state_code=self._normalize_state_code(session.tax_profile.state_code if session.tax_profile else None),
            cpa_slug=cpa_profile.cpa_slug if cpa_profile else None,
            estimated_savings=estimated_savings_midpoint,
        )
        teaser_insights = [i.to_dict(tier=1) for i in generated_insights[:3]] if generated_insights else []
        locked_titles = [i.title for i in generated_insights[3:8]] if generated_insights else []
        strategy_waterfall = self._build_strategy_waterfall_payload(generated_insights, limit=6)

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
            "state_code": profile_data.get("state_code", "US"),
            "complexity": complexity.value,
            "savings_range": f"${savings_low:,.0f} - ${savings_high:,.0f}",
            "insights": [
                i.to_dict(tier=1) for i in generated_insights[:5]
            ] if generated_insights else [],
            "teaser_insights": teaser_insights,
            "locked_strategy_titles": locked_titles,
            "total_insights": len(generated_insights) if generated_insights else 3,
            "locked_count": max(0, len(generated_insights) - 5) if generated_insights else 3,
            "cta_text": f"Schedule a consultation with {cpa_profile.first_name} to unlock your full analysis",
            "tax_health_score": score_payload,
            "personalization": personalization,
            "comparison_chart": comparison_chart,
            "strategy_waterfall": strategy_waterfall,
            "deadline_context": deadline_context,
            "share_payload": share_payload,
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

        # Bridge lead magnet profile to advisory-compatible format for richer analysis
        if session.tax_profile:
            try:
                from cpa_panel.services.lead_magnet_report_builder import build_tax_profile_input
                report["advisory_profile"] = build_tax_profile_input(session.tax_profile)
            except Exception as e:
                logger.warning("Schema bridge failed, continuing without advisory profile: %s", e)

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

        strategy_waterfall = self._build_strategy_waterfall_payload(all_insights)
        tax_calendar = self._build_tax_calendar_payload()

        report.update({
            "total_savings": f"${total_savings:,.0f}",
            "total_savings_amount": total_savings,
            "all_insights": [i.to_dict(tier=2) for i in all_insights],
            "action_items": action_items,
            "strategy_waterfall": strategy_waterfall,
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
        firm_id: Optional[str] = None,
        temperature: Optional[str] = None,
        engaged: Optional[bool] = None,
        state: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get leads with filtering options.

        Args:
            state: Filter by lifecycle state — "new", "engaged", "converted", or "all".
            search: Free-text search against first_name and email.
        """
        leads = []

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            query = "SELECT * FROM lead_magnet_leads WHERE 1=1"
            params: list = []

            if cpa_id:
                query += " AND cpa_id = ?"
                params.append(cpa_id)

            if firm_id:
                query += " AND firm_id = ?"
                params.append(firm_id)

            if temperature:
                query += " AND lead_temperature = ?"
                params.append(temperature)

            if engaged is not None:
                query += " AND engaged = ?"
                params.append(1 if engaged else 0)

            # State filtering (lifecycle stage)
            if state and state != "all":
                if state == "converted":
                    query += " AND converted = TRUE"
                elif state == "engaged":
                    query += " AND engaged = TRUE AND converted = FALSE"
                elif state == "new":
                    query += " AND engaged = FALSE AND converted = FALSE"

            # Free-text search on name and email
            if search:
                query += " AND (first_name LIKE ? OR email LIKE ?)"
                like_term = f"%{search}%"
                params.extend([like_term, like_term])

            query += " ORDER BY lead_score DESC, created_at DESC"
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

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
                    "converted": bool(row["converted"]) if "converted" in row.keys() else False,
                    "engagement_letter_acknowledged": bool(row["engagement_letter_acknowledged"]) if "engagement_letter_acknowledged" in row.keys() else False,
                    "state": "converted" if row.get("converted") else ("engaged" if row.get("engaged") else "new"),
                    "state_display": "Converted" if row.get("converted") else ("Engaged" if row.get("engaged") else "New Lead"),
                    "created_at": row["created_at"],
                })

        except Exception as e:
            logger.error(f"Failed to get leads: {e}")

        return leads

    def list_leads(
        self,
        cpa_id: Optional[str] = None,
        firm_id: Optional[str] = None,
        temperature: Optional[str] = None,
        engaged: Optional[bool] = None,
        state: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Alias for get_leads() for backward compatibility."""
        return self.get_leads(
            cpa_id=cpa_id,
            firm_id=firm_id,
            temperature=temperature,
            engaged=engaged,
            state=state,
            search=search,
            limit=limit,
            offset=offset,
        )

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

    def get_funnel_kpis(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        variant_id: Optional[str] = None,
        utm_source: Optional[str] = None,
        device_type: Optional[str] = None,
        cpa_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return funnel KPI aggregates by date window and experiment variant."""
        where_clauses = ["1=1"]
        params: List[Any] = []
        if date_from:
            where_clauses.append("date(created_at) >= date(?)")
            params.append(date_from)
        if date_to:
            where_clauses.append("date(created_at) <= date(?)")
            params.append(date_to)
        if variant_id:
            where_clauses.append("variant_id = ?")
            params.append(variant_id)
        if utm_source:
            where_clauses.append("utm_source = ?")
            params.append(utm_source)
        if device_type:
            where_clauses.append("device_type = ?")
            params.append(device_type)
        if cpa_id:
            where_clauses.append("cpa_id = ?")
            params.append(cpa_id)

        clause = " AND ".join(where_clauses)
        event_counts: Dict[Tuple[str, Optional[str]], int] = {}
        total_events = 0
        score_interactions = 0

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT event_name, step, COUNT(*) AS cnt
                FROM lead_magnet_events
                WHERE {clause}
                GROUP BY event_name, step
                """,
                params,
            )
            rows = cursor.fetchall()
            for row in rows:
                key = (row["event_name"], row["step"])
                count = int(row["cnt"] or 0)
                event_counts[key] = count
                total_events += count

            cursor.execute(
                f"""
                SELECT COUNT(*) AS cnt
                FROM lead_magnet_events
                WHERE {clause}
                  AND event_name = 'step_complete'
                  AND (
                    step = 'score_interaction'
                    OR metadata_json LIKE '%subscore_click%'
                  )
                """,
                params,
            )
            score_interactions = int((cursor.fetchone() or {"cnt": 0})["cnt"] or 0)
            conn.close()
        except Exception as exc:
            logger.error("Failed to compute funnel KPIs: %s", exc)
            return {
                "filters": {
                    "date_from": date_from,
                    "date_to": date_to,
                    "variant_id": variant_id,
                    "utm_source": utm_source,
                    "device_type": device_type,
                    "cpa_id": cpa_id,
                },
                "error": str(exc),
            }

        starts = sum(count for (name, _), count in event_counts.items() if name == "start")
        profile_complete = event_counts.get(("step_complete", "profile"), 0)
        teaser_views = event_counts.get(("step_complete", "teaser_view"), 0)
        contact_views = event_counts.get(("step_complete", "contact_view"), 0)
        lead_submits = sum(count for (name, _), count in event_counts.items() if name == "lead_submit")
        report_views = sum(count for (name, _), count in event_counts.items() if name == "report_view")

        def _rate(numerator: int, denominator: int) -> float:
            if denominator <= 0:
                return 0.0
            return round((numerator / denominator) * 100.0, 2)

        return {
            "filters": {
                "date_from": date_from,
                "date_to": date_to,
                "variant_id": variant_id,
                "utm_source": utm_source,
                "device_type": device_type,
                "cpa_id": cpa_id,
            },
            "counts": {
                "events_total": total_events,
                "start": starts,
                "profile_complete": profile_complete,
                "teaser_view": teaser_views,
                "contact_view": contact_views,
                "lead_submit": lead_submits,
                "report_view": report_views,
                "score_interaction": score_interactions,
            },
            "rates": {
                "start_to_profile_pct": _rate(profile_complete, starts),
                "profile_to_teaser_pct": _rate(teaser_views, profile_complete),
                "teaser_to_contact_submit_pct": _rate(lead_submits, teaser_views),
                "contact_submit_to_report_pct": _rate(report_views, lead_submits),
                "score_interaction_rate_pct": _rate(score_interactions, teaser_views + report_views),
            },
        }

    def convert_lead(
        self,
        lead_id: str,
        cpa_id: Optional[str] = None,
        firm_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Convert a lead to a client.

        Creates a real ClientRecord in the database (if available) and marks
        the lead as converted in the lead_magnet_leads table.
        """
        lead = self.get_lead(lead_id)
        if not lead:
            raise ValueError(f"Lead not found: {lead_id}")

        if not lead.engaged:
            raise ValueError("Lead must be engaged before converting")

        now = datetime.now(timezone.utc)
        resolved_cpa_id = cpa_id or lead.cpa_id
        client_id: Optional[str] = None

        # Create a real ClientRecord in the relational database
        try:
            from database.models import ClientRecord
            from database.session import get_db_session
            import uuid as _uuid

            name_parts = (lead.first_name or "").strip().split(None, 1)
            first_name = name_parts[0] if name_parts else "Unknown"
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            client_uuid = _uuid.uuid4()
            client_id = str(client_uuid)

            with get_db_session() as db:
                client_record = ClientRecord(
                    client_id=client_uuid,
                    preparer_id=_uuid.UUID(resolved_cpa_id) if resolved_cpa_id else client_uuid,
                    firm_id=_uuid.UUID(firm_id) if firm_id else None,
                    first_name=first_name,
                    last_name=last_name,
                    email=lead.email,
                    phone=lead.phone,
                )
                db.add(client_record)
            logger.info(f"Created ClientRecord {client_id} from lead {lead_id}")
        except ImportError:
            logger.warning("Database module unavailable; skipping ClientRecord creation")
        except Exception as exc:
            logger.error(f"Failed to create ClientRecord for lead {lead_id}: {exc}")

        # Update the lead_magnet_leads row
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE lead_magnet_leads SET
                    converted = TRUE,
                    converted_at = ?
                WHERE lead_id = ?
            """, (now.isoformat(), lead_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to update lead conversion flag: {e}")
            raise

        return {
            "lead_id": lead_id,
            "converted": True,
            "converted_at": now.isoformat(),
            "client_id": client_id,
        }

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
                datetime.now(timezone.utc).isoformat(),
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
# RE-EXPORTS FROM DECOMPOSED SUB-MODULES (backward compatibility)
# =============================================================================
# These sub-modules extract logic from this monolith for maintainability.
# Import them here so existing consumers can use the original import paths.
try:
    from cpa_panel.services.lead_magnet.calculator import (  # noqa: F401
        detect_complexity as _ext_detect_complexity,
        parse_income_range as _ext_parse_income_range,
        estimate_marginal_rate as _ext_estimate_marginal_rate,
        calculate_lead_score as _ext_calculate_lead_score,
        build_tax_health_score as _ext_build_tax_health_score,
    )
    from cpa_panel.services.lead_magnet.generator import (  # noqa: F401
        normalize_state_code as _ext_normalize_state,
        filing_status_display as _ext_filing_display,
        income_range_display as _ext_income_display,
        generate_insights as _ext_generate_insights,
    )
    from cpa_panel.services.lead_magnet.payloads import (  # noqa: F401
        build_personalization_payload as _ext_build_personalization,
        build_deadline_payload as _ext_build_deadline,
        build_comparison_chart_payload as _ext_build_comparison,
        build_strategy_waterfall_payload as _ext_build_waterfall,
        build_tax_calendar_payload as _ext_build_calendar,
        build_share_payload as _ext_build_share,
        normalize_occupation_type as _ext_normalize_occupation,
        occupation_display as _ext_occupation_display,
    )
    from cpa_panel.services.lead_magnet.delivery import (  # noqa: F401
        send_lead_notifications as _ext_send_notifications,
    )
    logger.debug("Lead magnet sub-modules loaded successfully")
except ImportError as e:
    logger.debug(f"Lead magnet sub-modules not yet available: {e}")


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
