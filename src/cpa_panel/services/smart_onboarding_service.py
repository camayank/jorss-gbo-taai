"""
Smart Onboarding Service - Orchestrates the 60-second client onboarding flow.

This service coordinates:
1. Document upload and OCR processing
2. 1040 data extraction
3. Smart question generation
4. Instant tax analysis
5. Client creation with optimization opportunities
"""

from __future__ import annotations

import os
import uuid
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple, BinaryIO, TYPE_CHECKING
from decimal import Decimal
from datetime import datetime
from enum import Enum
import json

from sqlalchemy import text

from .form_1040_parser import Form1040Parser, Parsed1040Data, FilingStatus
from .ai_question_generator import AIQuestionGenerator, QuestionSet, SmartQuestion

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class OnboardingStatus(str, Enum):
    """Status of the onboarding process."""
    INITIATED = "initiated"
    DOCUMENT_UPLOADED = "document_uploaded"
    OCR_PROCESSING = "ocr_processing"
    OCR_COMPLETE = "ocr_complete"
    QUESTIONS_GENERATED = "questions_generated"
    QUESTIONS_ANSWERED = "questions_answered"
    ANALYSIS_COMPLETE = "analysis_complete"
    CLIENT_CREATED = "client_created"
    FAILED = "failed"


@dataclass
class OptimizationOpportunity:
    """
    A tax optimization opportunity identified during onboarding.
    """
    id: str
    title: str
    category: str
    potential_savings: Decimal
    confidence: str  # high, medium, low
    description: str
    action_required: str
    priority: int  # 1 = highest

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "potential_savings": float(self.potential_savings),
            "confidence": self.confidence,
            "description": self.description,
            "action_required": self.action_required,
            "priority": self.priority,
        }


@dataclass
class InstantAnalysis:
    """
    Instant analysis results from smart onboarding.
    """
    total_potential_savings: Decimal
    opportunities: List[OptimizationOpportunity]
    tax_summary: Dict[str, Any]
    recommendations_count: int
    analysis_confidence: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_potential_savings": float(self.total_potential_savings),
            "opportunities": [o.to_dict() for o in self.opportunities],
            "tax_summary": self.tax_summary,
            "recommendations_count": self.recommendations_count,
            "analysis_confidence": self.analysis_confidence,
        }


@dataclass
class OnboardingSession:
    """
    Tracks the state of a smart onboarding session.
    """
    session_id: str
    cpa_id: str
    status: OnboardingStatus
    created_at: datetime

    # Document data
    document_filename: Optional[str] = None
    document_type: Optional[str] = None

    # Extracted data
    parsed_1040: Optional[Parsed1040Data] = None
    extraction_confidence: float = 0.0

    # Questions
    questions: Optional[QuestionSet] = None
    answers: Dict[str, str] = field(default_factory=dict)

    # Analysis
    analysis: Optional[InstantAnalysis] = None

    # Created client
    client_id: Optional[str] = None
    client_name: Optional[str] = None

    # Errors
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "cpa_id": self.cpa_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "document": {
                "filename": self.document_filename,
                "type": self.document_type,
            },
            "extraction": {
                "confidence": self.extraction_confidence,
                "data": self.parsed_1040.to_dict() if self.parsed_1040 else None,
            },
            "questions": self.questions.to_dict() if self.questions else None,
            "answers": self.answers,
            "analysis": self.analysis.to_dict() if self.analysis else None,
            "client": {
                "id": self.client_id,
                "name": self.client_name,
            },
            "error": self.error_message,
        }


class SmartOnboardingService:
    """
    Service that orchestrates the smart 60-second onboarding flow.

    Flow:
    1. CPA uploads prior year 1040 (PDF/image)
    2. OCR extracts all data (~10 seconds)
    3. AI generates 3-5 targeted questions
    4. CPA answers questions (~30 seconds)
    5. System runs instant analysis
    6. Client created with opportunities identified

    Total time: ~60 seconds
    """

    def __init__(self):
        self.parser = Form1040Parser()
        self.question_generator = AIQuestionGenerator()
        self._sessions: Dict[str, OnboardingSession] = {}
        self._ocr_engine = None
        self._document_processor = None

    def _get_ocr_engine(self):
        """Lazy load OCR engine."""
        if self._ocr_engine is None:
            try:
                from services.ocr.resilient_processor import ResilientOCREngine
                self._ocr_engine = ResilientOCREngine()
            except ImportError:
                try:
                    from services.ocr.ocr_engine import OCREngine
                    self._ocr_engine = OCREngine()
                except ImportError:
                    # Mock OCR engine for testing when OCR not available
                    logger.warning("OCR engine not available, using mock")
                    self._ocr_engine = None
        return self._ocr_engine

    def _get_document_processor(self):
        """Lazy load document processor."""
        if self._document_processor is None:
            try:
                from services.ocr.resilient_processor import ResilientDocumentProcessor
                self._document_processor = ResilientDocumentProcessor()
            except ImportError:
                try:
                    from services.ocr.document_processor import DocumentProcessor
                    self._document_processor = DocumentProcessor()
                except ImportError:
                    logger.warning("Document processor not available")
                    self._document_processor = None
        return self._document_processor

    def start_onboarding(self, cpa_id: str) -> OnboardingSession:
        """
        Start a new smart onboarding session.

        Args:
            cpa_id: ID of the CPA initiating onboarding

        Returns:
            New OnboardingSession
        """
        session = OnboardingSession(
            session_id=str(uuid.uuid4()),
            cpa_id=cpa_id,
            status=OnboardingStatus.INITIATED,
            created_at=datetime.utcnow(),
        )
        self._sessions[session.session_id] = session
        logger.info(f"Started onboarding session {session.session_id} for CPA {cpa_id}")
        return session

    async def process_document(
        self,
        session_id: str,
        file_content: bytes,
        filename: str,
        content_type: str = "application/pdf"
    ) -> OnboardingSession:
        """
        Process uploaded document through OCR and extract 1040 data.

        Args:
            session_id: Onboarding session ID
            file_content: Raw file bytes
            filename: Original filename
            content_type: MIME type

        Returns:
            Updated OnboardingSession with extracted data
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        session.status = OnboardingStatus.DOCUMENT_UPLOADED
        session.document_filename = filename

        try:
            session.status = OnboardingStatus.OCR_PROCESSING

            # Detect document type
            if "pdf" in content_type.lower() or filename.lower().endswith(".pdf"):
                session.document_type = "pdf"
            elif any(ext in filename.lower() for ext in [".jpg", ".jpeg", ".png", ".tiff"]):
                session.document_type = "image"
            else:
                session.document_type = "unknown"

            # Run OCR
            ocr_engine = self._get_ocr_engine()
            ocr_result = await self._run_ocr(ocr_engine, file_content, session.document_type)

            if not ocr_result or not ocr_result.raw_text:
                raise ValueError("OCR failed to extract text from document")

            session.extraction_confidence = ocr_result.confidence

            # Parse 1040 data
            parsed = self.parser.parse(ocr_result)
            session.parsed_1040 = parsed
            session.status = OnboardingStatus.OCR_COMPLETE

            logger.info(
                f"Session {session_id}: OCR complete, "
                f"confidence={ocr_result.confidence:.1f}%, "
                f"fields_extracted={parsed.fields_extracted}"
            )

            # Generate smart questions
            questions = self.question_generator.generate_questions(parsed)
            session.questions = questions
            session.status = OnboardingStatus.QUESTIONS_GENERATED

            logger.info(
                f"Session {session_id}: Generated {len(questions.questions)} questions"
            )

            return session

        except Exception as e:
            logger.error(f"Session {session_id}: Document processing failed: {e}")
            session.status = OnboardingStatus.FAILED
            session.error_message = str(e)
            return session

    async def _run_ocr(self, engine, content: bytes, doc_type: str):
        """Run OCR processing on document content."""
        try:
            # Try resilient engine first
            if hasattr(engine, 'process'):
                return await engine.process(content)
            elif hasattr(engine, 'process_bytes'):
                return engine.process_bytes(content)
            elif hasattr(engine, 'process_file'):
                # Write to temp file
                import tempfile
                suffix = ".pdf" if doc_type == "pdf" else ".jpg"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                    f.write(content)
                    temp_path = f.name
                try:
                    return engine.process_file(temp_path)
                finally:
                    os.unlink(temp_path)
            else:
                # Fallback: create mock result for testing
                logger.warning("No suitable OCR method found, using mock")
                from services.ocr.ocr_engine import OCRResult
                return OCRResult(
                    raw_text="Mock OCR text for testing",
                    blocks=[],
                    confidence=50.0,
                    page_count=1,
                    metadata={}
                )
        except Exception as e:
            logger.error(f"OCR processing error: {e}")
            raise

    def submit_answers(
        self,
        session_id: str,
        answers: Dict[str, str]
    ) -> OnboardingSession:
        """
        Submit answers to the smart questions.

        Args:
            session_id: Onboarding session ID
            answers: Dict of question_id -> answer_value

        Returns:
            Updated session with analysis triggered
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        session.answers = answers
        session.status = OnboardingStatus.QUESTIONS_ANSWERED

        # Run instant analysis
        analysis = self._run_instant_analysis(session)
        session.analysis = analysis
        session.status = OnboardingStatus.ANALYSIS_COMPLETE

        logger.info(
            f"Session {session_id}: Analysis complete, "
            f"potential_savings=${float(analysis.total_potential_savings):,.0f}, "
            f"opportunities={len(analysis.opportunities)}"
        )

        return session

    def _run_instant_analysis(self, session: OnboardingSession) -> InstantAnalysis:
        """
        Run instant analysis based on extracted data and answers.

        Identifies optimization opportunities using rule-based logic
        and optimizer engine hints.
        """
        opportunities = []
        total_savings = Decimal("0")

        parsed = session.parsed_1040
        answers = session.answers

        if not parsed:
            return InstantAnalysis(
                total_potential_savings=Decimal("0"),
                opportunities=[],
                tax_summary={},
                recommendations_count=0,
                analysis_confidence="low",
            )

        agi = parsed.adjusted_gross_income or Decimal("0")
        wages = parsed.wages_salaries_tips or Decimal("0")
        filing_status = parsed.filing_status

        # 1. Retirement optimization
        if answers.get("retirement_401k_available") in ["yes_with_match", "yes_no_match"]:
            contribution = answers.get("retirement_401k_contribution", "unknown")
            if contribution not in ["max", "unknown"]:
                # Estimate savings from increasing 401k
                current_rate = {"0": 0, "1-5": 3, "6-10": 8, "11-15": 13}.get(contribution, 0)
                max_contribution = Decimal("23000")
                current_contribution = wages * Decimal(str(current_rate / 100))
                potential_increase = max_contribution - current_contribution

                if potential_increase > 0:
                    # Tax savings at marginal rate
                    marginal_rate = self._get_marginal_rate(agi, filing_status)
                    savings = potential_increase * marginal_rate
                    savings = min(savings, Decimal("5000"))  # Cap estimate

                    opportunities.append(OptimizationOpportunity(
                        id="opp_401k",
                        title="Maximize 401(k) Contributions",
                        category="retirement",
                        potential_savings=savings.quantize(Decimal("1")),
                        confidence="high",
                        description=f"Increase 401(k) contributions from current level to maximum ${max_contribution:,.0f}",
                        action_required="Contact HR to increase contribution rate",
                        priority=1,
                    ))
                    total_savings += savings

        # 2. HSA optimization
        if answers.get("healthcare_hdhp") == "yes":
            hsa_status = answers.get("healthcare_hsa", "unknown")
            if hsa_status in ["0", "partial"]:
                # HSA family max is $8,300 for 2024
                hsa_max = Decimal("8300") if filing_status == FilingStatus.MARRIED_FILING_JOINTLY else Decimal("4150")
                marginal_rate = self._get_marginal_rate(agi, filing_status)
                savings = hsa_max * marginal_rate

                opportunities.append(OptimizationOpportunity(
                    id="opp_hsa",
                    title="Maximize HSA Contributions",
                    category="healthcare",
                    potential_savings=savings.quantize(Decimal("1")),
                    confidence="high",
                    description=f"Contribute maximum ${hsa_max:,.0f} to your HSA for triple tax benefits",
                    action_required="Set up HSA payroll deductions or make direct contributions",
                    priority=2,
                ))
                total_savings += savings

        # 3. Dependent care FSA
        if answers.get("dependents_childcare") in ["yes_high", "yes_low"]:
            fsa_status = answers.get("healthcare_fsa", "unknown")
            if fsa_status != "yes_using":
                marginal_rate = self._get_marginal_rate(agi, filing_status)
                savings = Decimal("5000") * marginal_rate

                opportunities.append(OptimizationOpportunity(
                    id="opp_dcfsa",
                    title="Dependent Care FSA",
                    category="dependents",
                    potential_savings=savings.quantize(Decimal("1")),
                    confidence="medium",
                    description="Use pre-tax dollars for childcare through Dependent Care FSA",
                    action_required="Enroll in Dependent Care FSA during open enrollment",
                    priority=3,
                ))
                total_savings += savings

        # 4. IRA contribution
        if answers.get("retirement_ira") == "no":
            ira_limit = Decimal("7000")
            marginal_rate = self._get_marginal_rate(agi, filing_status)

            # Check if Traditional IRA deduction available
            if agi < Decimal("143000"):  # MFJ phase-out
                savings = ira_limit * marginal_rate

                opportunities.append(OptimizationOpportunity(
                    id="opp_ira",
                    title="IRA Contribution",
                    category="retirement",
                    potential_savings=savings.quantize(Decimal("1")),
                    confidence="medium",
                    description=f"Contribute up to ${ira_limit:,.0f} to Traditional or Roth IRA",
                    action_required="Open IRA account and set up contributions",
                    priority=4,
                ))
                total_savings += savings

        # 5. Self-employment deductions
        if answers.get("income_self_employment") in ["yes_significant", "yes_side"]:
            if answers.get("income_home_office") == "yes_dedicated":
                # Estimate home office deduction
                home_office_savings = Decimal("1500")  # Simplified estimate

                opportunities.append(OptimizationOpportunity(
                    id="opp_home_office",
                    title="Home Office Deduction",
                    category="self_employment",
                    potential_savings=home_office_savings,
                    confidence="medium",
                    description="Deduct portion of home expenses for business use",
                    action_required="Calculate square footage and keep records of expenses",
                    priority=5,
                ))
                total_savings += home_office_savings

        # 6. Education credits
        if answers.get("education_college") in ["yes_undergrad"]:
            aotc = parsed.american_opportunity_credit or Decimal("0")
            if aotc == 0:
                opportunities.append(OptimizationOpportunity(
                    id="opp_aotc",
                    title="American Opportunity Tax Credit",
                    category="education",
                    potential_savings=Decimal("2500"),
                    confidence="medium",
                    description="Claim up to $2,500 per student for college expenses",
                    action_required="Gather Form 1098-T and tuition receipts",
                    priority=6,
                ))
                total_savings += Decimal("2500")

        # 7. Energy credits
        if answers.get("credits_energy") == "ev":
            opportunities.append(OptimizationOpportunity(
                id="opp_ev",
                title="Electric Vehicle Tax Credit",
                category="credits",
                potential_savings=Decimal("7500"),
                confidence="high",
                description="Claim up to $7,500 for qualifying electric vehicle purchase",
                action_required="Verify vehicle qualifies and claim on tax return",
                priority=7,
            ))
            total_savings += Decimal("7500")
        elif answers.get("credits_energy") == "solar":
            opportunities.append(OptimizationOpportunity(
                id="opp_solar",
                title="Residential Clean Energy Credit",
                category="credits",
                potential_savings=Decimal("5000"),  # Estimate
                confidence="medium",
                description="Claim 30% of solar installation costs",
                action_required="Keep receipts for solar installation",
                priority=7,
            ))
            total_savings += Decimal("5000")

        # 8. Charitable bunching (if applicable)
        if answers.get("deductions_charity") in ["medium", "high"]:
            std_ded = parsed.standard_deduction or Decimal("0")
            if std_ded > 0:  # They took standard deduction
                opportunities.append(OptimizationOpportunity(
                    id="opp_bunching",
                    title="Charitable Bunching Strategy",
                    category="deductions",
                    potential_savings=Decimal("800"),
                    confidence="low",
                    description="Consider bunching 2 years of donations to itemize every other year",
                    action_required="Plan charitable giving timing strategically",
                    priority=8,
                ))
                total_savings += Decimal("800")

        # Sort by priority
        opportunities.sort(key=lambda x: x.priority)

        # Build tax summary
        tax_summary = {
            "tax_year": parsed.tax_year,
            "filing_status": filing_status.value if filing_status else "unknown",
            "adjusted_gross_income": float(agi),
            "total_income": float(parsed.total_income or 0),
            "total_tax": float(parsed.total_tax or 0),
            "effective_rate": float((parsed.total_tax or 0) / agi * 100) if agi > 0 else 0,
            "refund_or_owed": float(parsed.refund_amount or 0) - float(parsed.amount_owed or 0),
        }

        # Determine confidence
        if parsed.extraction_confidence >= 80 and len(opportunities) >= 3:
            confidence = "high"
        elif parsed.extraction_confidence >= 60:
            confidence = "medium"
        else:
            confidence = "low"

        return InstantAnalysis(
            total_potential_savings=total_savings.quantize(Decimal("1")),
            opportunities=opportunities,
            tax_summary=tax_summary,
            recommendations_count=len(opportunities),
            analysis_confidence=confidence,
        )

    def _get_marginal_rate(
        self,
        agi: Decimal,
        filing_status: Optional[FilingStatus]
    ) -> Decimal:
        """Get estimated marginal tax rate based on AGI and filing status."""
        # 2024 tax brackets
        if filing_status == FilingStatus.MARRIED_FILING_JOINTLY:
            brackets = [
                (23200, Decimal("0.10")),
                (94300, Decimal("0.12")),
                (201050, Decimal("0.22")),
                (383900, Decimal("0.24")),
                (487450, Decimal("0.32")),
                (731200, Decimal("0.35")),
                (float("inf"), Decimal("0.37")),
            ]
        else:  # Single and others
            brackets = [
                (11600, Decimal("0.10")),
                (47150, Decimal("0.12")),
                (100525, Decimal("0.22")),
                (191950, Decimal("0.24")),
                (243725, Decimal("0.32")),
                (609350, Decimal("0.35")),
                (float("inf"), Decimal("0.37")),
            ]

        for threshold, rate in brackets:
            if float(agi) <= threshold:
                return rate

        return Decimal("0.37")

    async def create_client(
        self,
        session_id: str,
        client_name: Optional[str] = None,
        db_session: Optional["AsyncSession"] = None,
    ) -> OnboardingSession:
        """
        Create a client from the onboarding session.

        Args:
            session_id: Onboarding session ID
            client_name: Override client name (defaults to extracted name)
            db_session: Database session for persistence

        Returns:
            Updated session with client_id
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        if session.status != OnboardingStatus.ANALYSIS_COMPLETE:
            raise ValueError(f"Session not ready for client creation: {session.status}")

        # Use extracted name or provided name
        name = client_name or (
            session.parsed_1040.taxpayer_name if session.parsed_1040 else None
        ) or "New Client"

        # Split name into first/last
        name_parts = name.split(maxsplit=1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        # Generate client ID
        client_id = str(uuid.uuid4())
        now = datetime.utcnow()

        # Persist to database if session provided
        if db_session:
            try:
                # Build profile data from analysis
                profile_data = {}
                if session.analysis:
                    profile_data["opportunities"] = [
                        o.to_dict() for o in session.analysis.opportunities
                    ]
                    profile_data["potential_savings"] = float(session.analysis.total_potential_savings)
                if session.parsed_1040:
                    profile_data["tax_year"] = session.parsed_1040.tax_year
                    profile_data["filing_status"] = session.parsed_1040.filing_status.value if session.parsed_1040.filing_status else None
                    profile_data["agi"] = float(session.parsed_1040.adjusted_gross_income or 0)

                # Get preparer_id from CPA
                preparer_query = text("""
                    SELECT user_id FROM users WHERE user_id = :cpa_id LIMIT 1
                """)
                preparer_result = await db_session.execute(preparer_query, {"cpa_id": session.cpa_id})
                preparer_row = preparer_result.fetchone()
                preparer_id = str(preparer_row[0]) if preparer_row else None

                # Insert client record
                query = text("""
                    INSERT INTO clients (
                        client_id, preparer_id, first_name, last_name,
                        is_active, created_at, profile_data
                    ) VALUES (
                        :client_id, :preparer_id, :first_name, :last_name,
                        true, :created_at, :profile_data
                    )
                """)
                await db_session.execute(query, {
                    "client_id": client_id,
                    "preparer_id": preparer_id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "created_at": now,
                    "profile_data": json.dumps(profile_data),
                })
                await db_session.commit()

                logger.info(f"Session {session_id}: Persisted client {client_id} to database")
            except Exception as e:
                logger.error(f"Failed to persist client to database: {e}")
                # Continue without database persistence

        session.client_id = client_id
        session.client_name = name
        session.status = OnboardingStatus.CLIENT_CREATED

        logger.info(
            f"Session {session_id}: Created client {client_id} ({name})"
        )

        return session

    def get_session(self, session_id: str) -> Optional[OnboardingSession]:
        """Get an onboarding session by ID."""
        return self._sessions.get(session_id)

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get a summary of the onboarding session for UI display."""
        session = self._sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        summary = {
            "session_id": session.session_id,
            "status": session.status.value,
            "progress": self._calculate_progress(session),
        }

        if session.parsed_1040:
            summary["extracted_data"] = {
                "taxpayer_name": session.parsed_1040.taxpayer_name,
                "filing_status": session.parsed_1040.filing_status.value if session.parsed_1040.filing_status else None,
                "agi": float(session.parsed_1040.adjusted_gross_income or 0),
                "total_tax": float(session.parsed_1040.total_tax or 0),
                "refund": float(session.parsed_1040.refund_amount or 0),
                "dependents": session.parsed_1040.total_dependents,
            }
            summary["extraction_confidence"] = session.extraction_confidence

        if session.questions:
            summary["questions"] = {
                "count": len(session.questions.questions),
                "categories": session.questions.categories_covered,
            }

        if session.analysis:
            summary["analysis"] = {
                "total_potential_savings": float(session.analysis.total_potential_savings),
                "opportunities_count": len(session.analysis.opportunities),
                "top_opportunities": [
                    {
                        "title": o.title,
                        "savings": float(o.potential_savings),
                        "category": o.category,
                    }
                    for o in session.analysis.opportunities[:3]
                ],
            }

        if session.client_id:
            summary["client"] = {
                "id": session.client_id,
                "name": session.client_name,
            }

        return summary

    def _calculate_progress(self, session: OnboardingSession) -> int:
        """Calculate progress percentage."""
        progress_map = {
            OnboardingStatus.INITIATED: 10,
            OnboardingStatus.DOCUMENT_UPLOADED: 20,
            OnboardingStatus.OCR_PROCESSING: 30,
            OnboardingStatus.OCR_COMPLETE: 50,
            OnboardingStatus.QUESTIONS_GENERATED: 60,
            OnboardingStatus.QUESTIONS_ANSWERED: 80,
            OnboardingStatus.ANALYSIS_COMPLETE: 90,
            OnboardingStatus.CLIENT_CREATED: 100,
            OnboardingStatus.FAILED: 0,
        }
        return progress_map.get(session.status, 0)


# Singleton instance
_smart_onboarding_service: Optional[SmartOnboardingService] = None


def get_smart_onboarding_service() -> SmartOnboardingService:
    """Get the singleton smart onboarding service instance."""
    global _smart_onboarding_service
    if _smart_onboarding_service is None:
        _smart_onboarding_service = SmartOnboardingService()
    return _smart_onboarding_service
