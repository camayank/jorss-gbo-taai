"""
Client Intake Service for CPA Panel

Orchestrates client onboarding, integrating with the interview flow
and benefit estimator to provide real-time intake tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class IntakeStatus(str, Enum):
    """Status of client intake."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    AWAITING_DOCUMENTS = "awaiting_documents"
    REVIEW_NEEDED = "review_needed"
    COMPLETED = "completed"


@dataclass
class IntakeProgress:
    """Progress tracking for client intake."""
    session_id: str
    status: IntakeStatus
    started_at: Optional[str]
    last_activity: Optional[str]
    current_stage: str
    stages_completed: List[str]
    stages_remaining: List[str]
    percent_complete: float
    estimated_benefit: Optional[float]
    questions_answered: int
    questions_total: int
    documents_uploaded: int
    documents_required: int


class IntakeService:
    """
    Service for managing client intake process.

    Integrates with:
    - Interview flow for questionnaire management
    - Benefit estimator for real-time estimates
    - Document processor for required documents
    """

    # Standard intake stages
    INTAKE_STAGES = [
        "personal_info",
        "filing_status",
        "dependents",
        "income",
        "deductions",
        "credits",
        "review",
    ]

    def __init__(self):
        """Initialize intake service."""
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._interview_flow = None
        self._benefit_estimator = None

    @property
    def interview_flow(self):
        """Lazy load interview flow."""
        if self._interview_flow is None:
            try:
                from onboarding.interview_flow import TaxInterviewFlow
                self._interview_flow = TaxInterviewFlow()
            except ImportError:
                logger.warning("Interview flow not available")
        return self._interview_flow

    @property
    def benefit_estimator(self):
        """Lazy load benefit estimator."""
        if self._benefit_estimator is None:
            try:
                from onboarding.benefit_estimator import OnboardingBenefitEstimator
                self._benefit_estimator = OnboardingBenefitEstimator()
            except ImportError:
                logger.warning("Benefit estimator not available")
        return self._benefit_estimator

    def start_intake(
        self,
        session_id: str,
        client_info: Optional[Dict[str, Any]] = None,
        cpa_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Start a new client intake session.

        Args:
            session_id: Unique session identifier
            client_info: Optional pre-filled client information
            cpa_id: CPA initiating the intake

        Returns:
            Intake session info with first questions
        """
        # Initialize session
        session = {
            "session_id": session_id,
            "status": IntakeStatus.IN_PROGRESS.value,
            "started_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
            "cpa_id": cpa_id,
            "current_stage": self.INTAKE_STAGES[0],
            "stages_completed": [],
            "answers": client_info or {},
            "documents": [],
            "estimates": [],
        }

        self._sessions[session_id] = session

        # Get first questions if interview flow available
        first_questions = []
        if self.interview_flow:
            try:
                # Start interview
                self.interview_flow.start_interview()
                current_group = self.interview_flow.get_current_group()
                if current_group:
                    first_questions = self._questions_to_dict(current_group.questions)
                    session["current_stage"] = current_group.group_id
            except Exception as e:
                logger.warning(f"Failed to get first questions: {e}")

        return {
            "success": True,
            "session_id": session_id,
            "status": IntakeStatus.IN_PROGRESS.value,
            "started_at": session["started_at"],
            "current_stage": session["current_stage"],
            "questions": first_questions,
            "message": "Intake session started. Send client the intake link or enter data directly.",
        }

    def get_intake_status(self, session_id: str) -> Dict[str, Any]:
        """
        Get current intake status for a session.

        Args:
            session_id: Session identifier

        Returns:
            Current status, progress, and estimate
        """
        session = self._sessions.get(session_id)

        if not session:
            # Check if there's a tax return for this session
            try:
                from cpa_panel.adapters import TaxReturnAdapter
                adapter = TaxReturnAdapter()
                tax_return = adapter.get_tax_return(session_id)

                if tax_return:
                    return {
                        "success": True,
                        "session_id": session_id,
                        "status": IntakeStatus.COMPLETED.value,
                        "percent_complete": 100,
                        "message": "Tax return data available",
                    }
            except Exception:
                pass

            return {
                "success": False,
                "error": f"Intake session not found: {session_id}",
            }

        # Calculate progress
        stages_done = len(session.get("stages_completed", []))
        total_stages = len(self.INTAKE_STAGES)
        percent = (stages_done / total_stages * 100) if total_stages > 0 else 0

        # Get estimate if available
        estimate = None
        if session.get("estimates"):
            estimate = session["estimates"][-1]

        return {
            "success": True,
            "session_id": session_id,
            "status": session["status"],
            "started_at": session["started_at"],
            "last_activity": session["last_activity"],
            "current_stage": session["current_stage"],
            "stages_completed": session["stages_completed"],
            "stages_remaining": [s for s in self.INTAKE_STAGES if s not in session["stages_completed"]],
            "percent_complete": round(percent, 1),
            "questions_answered": len(session.get("answers", {})),
            "documents_uploaded": len(session.get("documents", [])),
            "current_estimate": estimate,
        }

    def get_intake_progress(self, session_id: str) -> Dict[str, Any]:
        """
        Get detailed progress for intake session.

        Returns stage-by-stage breakdown with completion status.
        """
        session = self._sessions.get(session_id)

        if not session:
            return {
                "success": False,
                "error": f"Intake session not found: {session_id}",
            }

        stages = []
        for stage in self.INTAKE_STAGES:
            is_complete = stage in session.get("stages_completed", [])
            is_current = stage == session.get("current_stage")

            stages.append({
                "stage_id": stage,
                "display_name": stage.replace("_", " ").title(),
                "status": "complete" if is_complete else ("in_progress" if is_current else "pending"),
            })

        return {
            "success": True,
            "session_id": session_id,
            "stages": stages,
            "overall_status": session["status"],
        }

    def get_benefit_estimate(self, session_id: str) -> Dict[str, Any]:
        """
        Get current benefit estimate based on intake answers.

        Uses the benefit estimator to provide real-time
        refund/tax estimate as data is entered.
        """
        session = self._sessions.get(session_id)

        if not session:
            # Try to get estimate from existing tax return
            try:
                from cpa_panel.adapters import TaxReturnAdapter
                adapter = TaxReturnAdapter()
                tax_return = adapter.get_tax_return(session_id)

                if tax_return:
                    refund = tax_return.refund_or_owed or 0
                    return {
                        "success": True,
                        "session_id": session_id,
                        "estimate_type": "refund" if refund > 0 else "owed",
                        "estimated_amount": abs(refund),
                        "confidence": "high",
                        "source": "tax_return",
                    }
            except Exception:
                pass

            return {
                "success": False,
                "error": f"Intake session not found: {session_id}",
            }

        if not self.benefit_estimator:
            return {
                "success": False,
                "error": "Benefit estimator not available",
            }

        try:
            answers = session.get("answers", {})
            estimate = self.benefit_estimator.estimate_from_answers(answers)

            # Store estimate
            session["estimates"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "estimate_type": estimate.estimate_type.value,
                "estimated_amount": estimate.estimated_amount,
                "confidence": estimate.confidence,
            })

            # Get highlights
            highlights = self.benefit_estimator.get_benefit_highlights(answers)

            return {
                "success": True,
                "session_id": session_id,
                "estimate_type": estimate.estimate_type.value,
                "estimated_amount": estimate.estimated_amount,
                "confidence": estimate.confidence,
                "estimated_federal_tax": estimate.estimated_federal_tax,
                "estimated_state_tax": estimate.estimated_state_tax,
                "effective_rate": estimate.effective_rate,
                "marginal_rate": estimate.marginal_rate,
                "potential_improvements": estimate.potential_improvements,
                "highlights": [
                    {
                        "title": h.title,
                        "description": h.description,
                        "estimated_value": h.estimated_value,
                        "category": h.category,
                        "is_potential": h.is_potential,
                    }
                    for h in highlights[:5]
                ],
            }

        except Exception as e:
            logger.error(f"Benefit estimate error for {session_id}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def submit_answers(
        self,
        session_id: str,
        answers: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Submit answers for an intake session.

        Args:
            session_id: Session identifier
            answers: Dictionary of question_id -> answer

        Returns:
            Updated status and next questions
        """
        session = self._sessions.get(session_id)

        if not session:
            return {
                "success": False,
                "error": f"Intake session not found: {session_id}",
            }

        # Update answers
        session["answers"].update(answers)
        session["last_activity"] = datetime.utcnow().isoformat()

        # Process with interview flow if available
        next_questions = []
        if self.interview_flow:
            try:
                # Submit answers to flow
                for question_id, answer in answers.items():
                    self.interview_flow.submit_answer(question_id, answer)

                # Check for stage completion
                current_group = self.interview_flow.get_current_group()
                if current_group:
                    next_questions = self._questions_to_dict(current_group.questions)
                    new_stage = current_group.group_id

                    if new_stage != session["current_stage"]:
                        session["stages_completed"].append(session["current_stage"])
                        session["current_stage"] = new_stage
                else:
                    # Interview complete
                    session["stages_completed"].append(session["current_stage"])
                    session["status"] = IntakeStatus.COMPLETED.value

            except Exception as e:
                logger.warning(f"Interview flow error: {e}")

        return {
            "success": True,
            "session_id": session_id,
            "status": session["status"],
            "current_stage": session["current_stage"],
            "stages_completed": session["stages_completed"],
            "next_questions": next_questions,
            "answers_count": len(session["answers"]),
        }

    def _questions_to_dict(self, questions) -> List[Dict[str, Any]]:
        """Convert Question objects to dictionaries."""
        result = []
        for q in questions:
            q_dict = {
                "question_id": q.question_id,
                "text": q.text,
                "question_type": q.question_type.value if hasattr(q.question_type, 'value') else str(q.question_type),
                "required": q.required,
            }
            if hasattr(q, 'choices') and q.choices:
                q_dict["choices"] = [
                    {"value": c.value, "label": c.label}
                    for c in q.choices
                ]
            if hasattr(q, 'help_text') and q.help_text:
                q_dict["help_text"] = q.help_text
            result.append(q_dict)
        return result


# Singleton instance
_intake_service: Optional[IntakeService] = None


def get_intake_service() -> IntakeService:
    """Get or create singleton intake service."""
    global _intake_service
    if _intake_service is None:
        _intake_service = IntakeService()
    return _intake_service
