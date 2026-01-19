"""
Smart Tax Orchestrator

Central orchestration layer for the Smart Tax document-first workflow.
Coordinates document processing, inference, estimation, and user interaction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum
from uuid import uuid4
import json


class SessionState(str, Enum):
    """States in the Smart Tax workflow."""
    UPLOAD = "upload"           # Waiting for document upload
    PROCESSING = "processing"   # Processing uploaded documents
    CONFIRM = "confirm"         # User confirming extracted data
    QUESTIONS = "questions"     # Answering adaptive questions
    CALCULATING = "calculating" # Running tax calculations
    REPORT = "report"           # Viewing results/report
    ACTION = "action"           # Taking action on recommendations
    COMPLETE = "complete"       # Session complete


class ComplexityLevel(str, Enum):
    """Tax situation complexity levels."""
    SIMPLE = "simple"           # W-2 only, standard deduction (3-5 min)
    MODERATE = "moderate"       # Multiple income sources, some deductions (8-12 min)
    COMPLEX = "complex"         # Self-employment, investments, itemized (15-20 min)
    PROFESSIONAL = "professional"  # Needs CPA review


@dataclass
class SmartTaxSession:
    """Represents a Smart Tax session."""
    session_id: str
    created_at: str
    updated_at: str
    state: SessionState
    complexity: Optional[ComplexityLevel] = None

    # User info
    filing_status: str = "single"
    num_dependents: int = 0
    tax_year: int = 2024

    # Documents
    documents: List[Dict[str, Any]] = field(default_factory=list)

    # Extracted data
    extracted_data: Dict[str, Any] = field(default_factory=dict)
    inferred_data: Dict[str, Any] = field(default_factory=dict)
    user_confirmed_data: Dict[str, Any] = field(default_factory=dict)

    # Estimates
    current_estimate: Optional[Dict[str, Any]] = None
    estimate_history: List[Dict[str, Any]] = field(default_factory=list)

    # Questions
    pending_questions: List[Dict[str, Any]] = field(default_factory=list)
    answered_questions: List[Dict[str, Any]] = field(default_factory=list)

    # Results
    final_calculation: Optional[Dict[str, Any]] = None
    recommendations: List[Dict[str, Any]] = field(default_factory=list)

    # Confidence
    overall_confidence: float = 0.0
    data_completeness: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "state": self.state.value,
            "complexity": self.complexity.value if self.complexity else None,
            "filing_status": self.filing_status,
            "num_dependents": self.num_dependents,
            "tax_year": self.tax_year,
            "document_count": len(self.documents),
            "current_estimate": self.current_estimate,
            "pending_questions": len(self.pending_questions),
            "overall_confidence": self.overall_confidence,
            "data_completeness": self.data_completeness,
        }


class SmartTaxOrchestrator:
    """
    Central orchestrator for the Smart Tax workflow.

    Coordinates:
    - Document upload and OCR processing
    - Field extraction and inference
    - Real-time tax estimation
    - Adaptive question generation
    - Complexity assessment and routing
    - Final calculation and recommendations
    """

    def __init__(self):
        self._sessions: Dict[str, SmartTaxSession] = {}

    def create_session(
        self,
        filing_status: str = "single",
        num_dependents: int = 0,
        tax_year: int = 2024,
    ) -> SmartTaxSession:
        """Create a new Smart Tax session."""
        session_id = str(uuid4())
        now = datetime.now().isoformat()

        session = SmartTaxSession(
            session_id=session_id,
            created_at=now,
            updated_at=now,
            state=SessionState.UPLOAD,
            filing_status=filing_status,
            num_dependents=num_dependents,
            tax_year=tax_year,
        )

        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[SmartTaxSession]:
        """Get an existing session."""
        return self._sessions.get(session_id)

    def process_document(
        self,
        session_id: str,
        document_type: str,
        extracted_fields: Dict[str, Any],
        ocr_confidence: float = 85.0,
    ) -> Dict[str, Any]:
        """
        Process an uploaded document and update session.

        Args:
            session_id: Session ID
            document_type: Type of document (w2, 1099_int, etc.)
            extracted_fields: Fields extracted from OCR
            ocr_confidence: Base OCR confidence score

        Returns:
            Updated estimate and session state
        """
        session = self._sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        # Import here to avoid circular imports
        from src.services.ocr.confidence_scorer import ConfidenceScorer, DocumentConfidenceAggregator
        from src.services.ocr.inference_engine import FieldInferenceEngine
        from src.recommendation.realtime_estimator import RealTimeEstimator

        # Score confidence for each field
        scorer = ConfidenceScorer()
        field_confidences = []
        scored_fields = {}

        for field_name, value in extracted_fields.items():
            field_type = self._get_field_type(field_name)
            result = scorer.calculate_confidence(
                field_name=field_name,
                raw_value=str(value),
                normalized_value=value,
                ocr_confidence=ocr_confidence,
                field_type=field_type,
                related_fields=extracted_fields,
            )
            field_confidences.append(result)
            scored_fields[field_name] = {
                "value": value,
                "confidence": result.overall_score,
                "needs_verification": result.needs_verification,
            }

        # Run inference to fill gaps
        inference_engine = FieldInferenceEngine(session.tax_year)
        inference_result = inference_engine.infer_and_validate(
            document_type=document_type,
            extracted_fields=extracted_fields,
            filing_status=session.filing_status,
        )

        # Add inferred fields
        for inferred in inference_result.inferred_fields:
            if inferred.field_name not in scored_fields:
                scored_fields[inferred.field_name] = {
                    "value": inferred.inferred_value,
                    "confidence": inferred.confidence,
                    "inferred": True,
                    "explanation": inferred.explanation,
                }

        # Store document
        doc_record = {
            "type": document_type,
            "fields": scored_fields,
            "raw_fields": extracted_fields,
            "processed_at": datetime.now().isoformat(),
            "validation_issues": [
                {"severity": v.severity, "field": v.field_name, "message": v.message}
                for v in inference_result.validation_issues
            ],
        }
        session.documents.append(doc_record)

        # Update extracted data
        for field_name, field_info in scored_fields.items():
            session.extracted_data[field_name] = field_info["value"]

        # Aggregate document confidence
        aggregator = DocumentConfidenceAggregator()
        doc_confidence = aggregator.aggregate_document_confidence(field_confidences)

        # Generate real-time estimate
        estimator = RealTimeEstimator(session.tax_year)

        if len(session.documents) == 1 and document_type == "w2":
            # Single W-2 estimate
            estimate = estimator.estimate_from_w2(
                w2_data=extracted_fields,
                filing_status=session.filing_status,
                num_dependents=session.num_dependents,
            )
        else:
            # Multi-document estimate
            doc_list = [
                {"type": d["type"], "fields": d["raw_fields"]}
                for d in session.documents
            ]
            estimate = estimator.estimate_from_multiple_documents(
                documents=doc_list,
                filing_status=session.filing_status,
                num_dependents=session.num_dependents,
            )

        # Update session
        session.current_estimate = estimate.to_dict()
        session.estimate_history.append({
            "estimate": estimate.to_dict(),
            "timestamp": datetime.now().isoformat(),
            "trigger": f"document_added:{document_type}",
        })
        session.overall_confidence = estimate.confidence_score
        session.data_completeness = estimate.data_completeness
        session.state = SessionState.CONFIRM
        session.updated_at = datetime.now().isoformat()

        # Assess complexity
        session.complexity = self._assess_complexity(session)

        # Generate questions if needed
        session.pending_questions = self._generate_questions(session, inference_result)

        return {
            "session_id": session_id,
            "state": session.state.value,
            "document_processed": document_type,
            "fields_extracted": len(scored_fields),
            "fields_inferred": len(inference_result.inferred_fields),
            "validation_issues": len(inference_result.validation_issues),
            "estimate": session.current_estimate,
            "complexity": session.complexity.value if session.complexity else None,
            "pending_questions": len(session.pending_questions),
            "confidence": session.overall_confidence,
        }

    def answer_question(
        self,
        session_id: str,
        question_id: str,
        answer: Any,
    ) -> Dict[str, Any]:
        """
        Process user's answer to a question and update estimate.
        """
        session = self._sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        # Find and remove the question
        question = None
        for i, q in enumerate(session.pending_questions):
            if q.get("id") == question_id:
                question = session.pending_questions.pop(i)
                break

        if not question:
            return {"error": "Question not found"}

        # Record the answer
        question["answer"] = answer
        question["answered_at"] = datetime.now().isoformat()
        session.answered_questions.append(question)

        # Update user confirmed data
        if "field_name" in question:
            session.user_confirmed_data[question["field_name"]] = answer

        # Special handling for certain questions
        if question.get("type") == "filing_status":
            session.filing_status = answer
        elif question.get("type") == "dependents":
            session.num_dependents = int(answer) if answer else 0

        # Recalculate estimate with new data
        from recommendation.realtime_estimator import RealTimeEstimator

        estimator = RealTimeEstimator(session.tax_year)

        if session.documents:
            doc_list = [
                {"type": d["type"], "fields": d["raw_fields"]}
                for d in session.documents
            ]
            estimate = estimator.estimate_from_multiple_documents(
                documents=doc_list,
                filing_status=session.filing_status,
                num_dependents=session.num_dependents,
            )

            session.current_estimate = estimate.to_dict()
            session.estimate_history.append({
                "estimate": estimate.to_dict(),
                "timestamp": datetime.now().isoformat(),
                "trigger": f"question_answered:{question_id}",
            })
            session.overall_confidence = estimate.confidence_score

        # Update state if no more questions
        if not session.pending_questions:
            session.state = SessionState.REPORT

        session.updated_at = datetime.now().isoformat()

        return {
            "session_id": session_id,
            "state": session.state.value,
            "questions_remaining": len(session.pending_questions),
            "estimate": session.current_estimate,
            "confidence": session.overall_confidence,
        }

    def confirm_data(
        self,
        session_id: str,
        confirmed_fields: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        User confirms or corrects extracted data.
        """
        session = self._sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        # Update confirmed data
        session.user_confirmed_data.update(confirmed_fields)

        # Merge with extracted data (user confirmed takes precedence)
        for field_name, value in confirmed_fields.items():
            session.extracted_data[field_name] = value

        # Recalculate with confirmed data
        from recommendation.realtime_estimator import RealTimeEstimator

        estimator = RealTimeEstimator(session.tax_year)

        # Build document list with confirmed values
        if session.documents:
            doc_list = []
            for doc in session.documents:
                fields = doc["raw_fields"].copy()
                # Override with confirmed values
                for field_name, value in confirmed_fields.items():
                    if field_name in fields:
                        fields[field_name] = value
                doc_list.append({"type": doc["type"], "fields": fields})

            estimate = estimator.estimate_from_multiple_documents(
                documents=doc_list,
                filing_status=session.filing_status,
                num_dependents=session.num_dependents,
            )

            session.current_estimate = estimate.to_dict()
            session.overall_confidence = min(95, estimate.confidence_score + 10)  # Boost for confirmation

        # Move to questions if any, otherwise to report
        if session.pending_questions:
            session.state = SessionState.QUESTIONS
        else:
            session.state = SessionState.REPORT

        session.updated_at = datetime.now().isoformat()

        return {
            "session_id": session_id,
            "state": session.state.value,
            "estimate": session.current_estimate,
            "confidence": session.overall_confidence,
            "next_step": "answer_questions" if session.pending_questions else "view_report",
        }

    def get_estimate(self, session_id: str) -> Dict[str, Any]:
        """Get current estimate for session."""
        session = self._sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        return {
            "session_id": session_id,
            "estimate": session.current_estimate,
            "confidence": session.overall_confidence,
            "data_completeness": session.data_completeness,
            "complexity": session.complexity.value if session.complexity else None,
        }

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get full session summary."""
        session = self._sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        return {
            "session": session.to_dict(),
            "documents": [
                {
                    "type": d["type"],
                    "field_count": len(d["fields"]),
                    "issues": len(d.get("validation_issues", [])),
                }
                for d in session.documents
            ],
            "estimate_count": len(session.estimate_history),
            "questions_answered": len(session.answered_questions),
            "questions_pending": len(session.pending_questions),
        }

    def _get_field_type(self, field_name: str) -> str:
        """Map field name to field type."""
        type_map = {
            "wages": "currency",
            "federal_tax_withheld": "currency",
            "social_security_wages": "currency",
            "social_security_tax": "currency",
            "medicare_wages": "currency",
            "medicare_tax": "currency",
            "state_wages": "currency",
            "state_tax": "currency",
            "employee_ssn": "ssn",
            "employer_ein": "ein",
            "interest_income": "currency",
            "ordinary_dividends": "currency",
            "qualified_dividends": "currency",
            "nonemployee_compensation": "currency",
        }
        return type_map.get(field_name, "string")

    def _assess_complexity(self, session: SmartTaxSession) -> ComplexityLevel:
        """Assess tax situation complexity."""
        # Count document types
        doc_types = set(d["type"] for d in session.documents)

        # Check for complexity indicators
        has_w2 = "w2" in doc_types
        has_1099_nec = "1099_nec" in doc_types
        has_investments = "1099_div" in doc_types or "1099_int" in doc_types
        multiple_w2s = sum(1 for d in session.documents if d["type"] == "w2") > 1

        # Check income level
        total_income = sum([
            session.extracted_data.get("wages", 0) or 0,
            session.extracted_data.get("interest_income", 0) or 0,
            session.extracted_data.get("ordinary_dividends", 0) or 0,
            session.extracted_data.get("nonemployee_compensation", 0) or 0,
        ])

        # Complexity rules
        if has_1099_nec:
            # Self-employment income
            nec_amount = session.extracted_data.get("nonemployee_compensation", 0)
            if nec_amount > 50000:
                return ComplexityLevel.COMPLEX
            return ComplexityLevel.MODERATE

        if total_income > 400000:
            return ComplexityLevel.COMPLEX

        if multiple_w2s or has_investments:
            return ComplexityLevel.MODERATE

        if has_w2 and len(doc_types) == 1:
            return ComplexityLevel.SIMPLE

        return ComplexityLevel.MODERATE

    def _generate_questions(
        self,
        session: SmartTaxSession,
        inference_result: Any,
    ) -> List[Dict[str, Any]]:
        """Generate adaptive questions based on extracted data."""
        questions = []

        # Check if filing status needs confirmation
        if session.filing_status == "single" and session.num_dependents > 0:
            questions.append({
                "id": "q_filing_status",
                "type": "filing_status",
                "question": "You have dependents. Would you like to check if you qualify for Head of Household status?",
                "options": [
                    {"value": "head_of_household", "label": "Yes, I qualify for Head of Household"},
                    {"value": "single", "label": "No, file as Single"},
                ],
                "priority": "high",
                "impact": "Could reduce taxes by $500-$2,000",
            })

        # Check for fields needing verification
        for doc in session.documents:
            for issue in doc.get("validation_issues", []):
                if issue["severity"] in ["warning", "error"]:
                    questions.append({
                        "id": f"q_verify_{issue['field']}",
                        "type": "verify_field",
                        "field_name": issue["field"],
                        "question": f"Please verify: {issue['message']}",
                        "current_value": session.extracted_data.get(issue["field"]),
                        "priority": "medium" if issue["severity"] == "warning" else "high",
                    })

        # Check for common deductions
        wages = session.extracted_data.get("wages", 0)
        if wages > 50000:
            questions.append({
                "id": "q_retirement",
                "type": "deduction",
                "question": "Did you contribute to a 401(k), IRA, or other retirement account this year?",
                "options": [
                    {"value": "yes", "label": "Yes"},
                    {"value": "no", "label": "No"},
                ],
                "priority": "medium",
                "impact": "Could reduce taxes significantly",
            })

        # Limit to 5 most important questions
        questions.sort(key=lambda q: {"high": 0, "medium": 1, "low": 2}.get(q.get("priority", "low"), 2))
        return questions[:5]


# Singleton instance for API use
_orchestrator: Optional[SmartTaxOrchestrator] = None


def get_orchestrator() -> SmartTaxOrchestrator:
    """Get the singleton orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SmartTaxOrchestrator()
    return _orchestrator
