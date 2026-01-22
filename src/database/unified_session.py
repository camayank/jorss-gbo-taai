"""
Unified Filing Session Model

This module provides a single session model that replaces all workflow-specific
session models (ExpressLaneSession, SmartTaxSession, ChatSession).

All workflows now use the same UnifiedFilingSession model with:
- Database persistence via SessionPersistence
- Support for anonymous and authenticated users
- State machine for tracking progress
- Workflow type differentiation
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime
from uuid import uuid4
import json


class FilingState(Enum):
    """Unified state machine for all filing workflows"""
    ENTRY = "entry"              # Initial state, choosing workflow
    UPLOAD = "upload"            # Uploading documents
    EXTRACT = "extract"          # OCR processing
    VALIDATE = "validate"        # User confirms extracted data
    QUESTIONS = "questions"      # Adaptive question flow
    SCENARIOS = "scenarios"      # What-if scenario exploration
    REVIEW = "review"            # Final review before submission
    SUBMIT = "submit"            # Submitting return
    COMPLETE = "complete"        # Filing complete
    ERROR = "error"              # Error state


class WorkflowType(Enum):
    """Different filing workflow modes"""
    EXPRESS = "express"          # Document-first, 3 min flow
    SMART = "smart"              # Adaptive questions
    CHAT = "chat"                # Conversational AI
    GUIDED = "guided"            # Traditional form-based
    AUTO = "auto"                # Auto-detect based on user actions


class ComplexityLevel(Enum):
    """Tax return complexity classification"""
    SIMPLE = "SIMPLE"            # W2 only, standard deduction
    MODERATE = "MODERATE"        # Multiple income sources, itemized
    COMPLEX = "COMPLEX"          # Business income, investments, etc.
    VERY_COMPLEX = "VERY_COMPLEX"  # Requires CPA review


@dataclass
class DocumentInfo:
    """Information about an uploaded document"""
    document_id: str
    filename: str
    document_type: str
    upload_time: str
    extracted_fields: Dict[str, Any] = field(default_factory=dict)
    confidence_score: float = 0.0


@dataclass
class ConversationMessage:
    """Chat message for conversational workflow"""
    message_id: str
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: str
    extracted_intent: Optional[str] = None


@dataclass
class UnifiedFilingSession:
    """
    Unified session model for all tax filing workflows.

    Replaces:
    - ExpressLaneSession (express_lane_api.py)
    - SmartTaxSession (orchestrator.py)
    - ChatSession (ai_chat_api.py)

    This model is persisted to database via SessionPersistence class.
    """

    # Core identification
    session_id: str = field(default_factory=lambda: str(uuid4()))
    user_id: Optional[str] = None
    is_anonymous: bool = True

    # Workflow tracking
    state: FilingState = FilingState.ENTRY
    workflow_type: WorkflowType = WorkflowType.EXPRESS

    # Tax year
    tax_year: int = field(default_factory=lambda: datetime.now().year - 1)

    # Document data (from uploads)
    documents: List[DocumentInfo] = field(default_factory=list)

    # Extracted data from documents/chat
    extracted_data: Dict[str, Any] = field(default_factory=dict)

    # User-confirmed data (after validation)
    user_confirmed_data: Dict[str, Any] = field(default_factory=dict)

    # Conversation history (for chat mode)
    conversation_history: List[ConversationMessage] = field(default_factory=list)

    # Progress tracking
    completeness_score: float = 0.0  # 0-100%
    confidence_score: float = 0.0    # 0-100%
    complexity_level: ComplexityLevel = ComplexityLevel.SIMPLE

    # Questions asked/answered
    questions_asked: List[str] = field(default_factory=list)
    answers_provided: Dict[str, Any] = field(default_factory=dict)

    # Calculated results (when available)
    calculated_results: Optional[Dict[str, Any]] = None

    # Scenario analysis (if used)
    scenarios_explored: List[Dict[str, Any]] = field(default_factory=list)

    # Link to TaxReturnRecord (when created)
    return_id: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    expires_at: Optional[str] = None

    # Version for optimistic locking
    version: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for JSON serialization"""
        return {
            'session_id': self.session_id,
            'user_id': self.user_id,
            'is_anonymous': self.is_anonymous,
            'state': self.state.value,
            'workflow_type': self.workflow_type.value,
            'tax_year': self.tax_year,
            'documents': [
                {
                    'document_id': doc.document_id,
                    'filename': doc.filename,
                    'document_type': doc.document_type,
                    'upload_time': doc.upload_time,
                    'extracted_fields': doc.extracted_fields,
                    'confidence_score': doc.confidence_score
                }
                for doc in self.documents
            ],
            'extracted_data': self.extracted_data,
            'user_confirmed_data': self.user_confirmed_data,
            'conversation_history': [
                {
                    'message_id': msg.message_id,
                    'role': msg.role,
                    'content': msg.content,
                    'timestamp': msg.timestamp,
                    'extracted_intent': msg.extracted_intent
                }
                for msg in self.conversation_history
            ],
            'completeness_score': self.completeness_score,
            'confidence_score': self.confidence_score,
            'complexity_level': self.complexity_level.value,
            'questions_asked': self.questions_asked,
            'answers_provided': self.answers_provided,
            'calculated_results': self.calculated_results,
            'scenarios_explored': self.scenarios_explored,
            'return_id': self.return_id,
            'metadata': self.metadata,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'expires_at': self.expires_at,
            'version': self.version
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UnifiedFilingSession':
        """Create session from dictionary"""
        # Convert documents
        documents = [
            DocumentInfo(
                document_id=doc['document_id'],
                filename=doc['filename'],
                document_type=doc['document_type'],
                upload_time=doc['upload_time'],
                extracted_fields=doc.get('extracted_fields', {}),
                confidence_score=doc.get('confidence_score', 0.0)
            )
            for doc in data.get('documents', [])
        ]

        # Convert conversation history
        conversation_history = [
            ConversationMessage(
                message_id=msg['message_id'],
                role=msg['role'],
                content=msg['content'],
                timestamp=msg['timestamp'],
                extracted_intent=msg.get('extracted_intent')
            )
            for msg in data.get('conversation_history', [])
        ]

        return cls(
            session_id=data['session_id'],
            user_id=data.get('user_id'),
            is_anonymous=data.get('is_anonymous', True),
            state=FilingState(data.get('state', 'entry')),
            workflow_type=WorkflowType(data.get('workflow_type', 'express')),
            tax_year=data.get('tax_year', datetime.now().year - 1),
            documents=documents,
            extracted_data=data.get('extracted_data', {}),
            user_confirmed_data=data.get('user_confirmed_data', {}),
            conversation_history=conversation_history,
            completeness_score=data.get('completeness_score', 0.0),
            confidence_score=data.get('confidence_score', 0.0),
            complexity_level=ComplexityLevel(data.get('complexity_level', 'SIMPLE')),
            questions_asked=data.get('questions_asked', []),
            answers_provided=data.get('answers_provided', {}),
            calculated_results=data.get('calculated_results'),
            scenarios_explored=data.get('scenarios_explored', []),
            return_id=data.get('return_id'),
            metadata=data.get('metadata', {}),
            created_at=data.get('created_at', datetime.utcnow().isoformat()),
            updated_at=data.get('updated_at', datetime.utcnow().isoformat()),
            expires_at=data.get('expires_at'),
            version=data.get('version', 0)
        )

    def update_state(self, new_state: FilingState) -> None:
        """Update state and timestamp"""
        self.state = new_state
        self.updated_at = datetime.utcnow().isoformat()

    def add_document(self, doc_info: DocumentInfo) -> None:
        """Add uploaded document"""
        self.documents.append(doc_info)
        self.updated_at = datetime.utcnow().isoformat()

    def add_message(self, role: str, content: str, intent: Optional[str] = None) -> None:
        """Add conversation message (for chat mode)"""
        msg = ConversationMessage(
            message_id=str(uuid4()),
            role=role,
            content=content,
            timestamp=datetime.utcnow().isoformat(),
            extracted_intent=intent
        )
        self.conversation_history.append(msg)
        self.updated_at = datetime.utcnow().isoformat()

    def calculate_completeness(self) -> float:
        """
        Calculate how complete the filing is (0-100%)

        Based on required fields for a complete tax return:
        - Personal info (name, SSN, address)
        - Income sources (W2, 1099, etc.)
        - Deductions/credits
        - Filing status
        """
        required_fields = {
            'first_name', 'last_name', 'ssn',
            'address', 'city', 'state', 'zip',
            'filing_status',
            'w2_income'  # At minimum
        }

        # Merge confirmed and extracted data
        all_data = {**self.extracted_data, **self.user_confirmed_data}

        # Count present fields
        present = sum(1 for field in required_fields if field in all_data and all_data[field])

        self.completeness_score = (present / len(required_fields)) * 100
        return self.completeness_score

    def determine_complexity(self) -> ComplexityLevel:
        """
        Determine tax return complexity based on data present
        """
        all_data = {**self.extracted_data, **self.user_confirmed_data}

        # Count complexity factors
        has_business_income = any(k.startswith('schedule_c') for k in all_data)
        has_investments = any(k.startswith('schedule_d') for k in all_data)
        has_rental = any(k.startswith('schedule_e') for k in all_data)
        has_itemized = all_data.get('itemized_deductions', False)
        has_multiple_w2 = len([d for d in self.documents if d.document_type == 'W2']) > 1
        has_1099 = any(d.document_type == '1099' for d in self.documents)

        complexity_score = sum([
            has_business_income * 3,
            has_investments * 2,
            has_rental * 2,
            has_itemized * 1,
            has_multiple_w2 * 1,
            has_1099 * 1
        ])

        if complexity_score >= 6:
            self.complexity_level = ComplexityLevel.VERY_COMPLEX
        elif complexity_score >= 4:
            self.complexity_level = ComplexityLevel.COMPLEX
        elif complexity_score >= 2:
            self.complexity_level = ComplexityLevel.MODERATE
        else:
            self.complexity_level = ComplexityLevel.SIMPLE

        return self.complexity_level

    def should_escalate_to_cpa(self) -> bool:
        """Determine if return should be escalated to CPA review"""
        return self.complexity_level in {ComplexityLevel.COMPLEX, ComplexityLevel.VERY_COMPLEX}

    def should_offer_chat(self) -> bool:
        """Determine if we should offer chat mode to user"""
        # Offer chat if:
        # - Completeness is low after document upload
        # - Complexity is moderate or higher
        # - User has asked many questions
        return (
            (self.completeness_score < 60 and len(self.documents) > 0) or
            self.complexity_level in {ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX} or
            len(self.questions_asked) > 5
        )
