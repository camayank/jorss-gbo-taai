"""
AI-Powered Client Communicator.

Uses Claude for personalized client communication:
- Drafting professional client emails
- Explaining complex tax concepts simply
- Generating follow-up questions
- Creating engagement letters
- Document request communications

Usage:
    from services.client_communicator import get_client_communicator

    communicator = get_client_communicator()

    # Draft a client email
    email = await communicator.draft_client_email(
        purpose="Request missing W-2",
        client=client_info,
        context={"missing_docs": ["W-2 from ABC Corp"]}
    )

    # Explain a tax concept
    explanation = await communicator.explain_tax_concept(
        concept="Roth IRA conversion",
        client_sophistication="intermediate"
    )
"""

import logging
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EmailPurpose(str, Enum):
    """Common email purposes."""
    WELCOME = "welcome"
    DOCUMENT_REQUEST = "document_request"
    FOLLOW_UP = "follow_up"
    STATUS_UPDATE = "status_update"
    QUESTION = "question"
    ENGAGEMENT_LETTER = "engagement_letter"
    TAX_SUMMARY = "tax_summary"
    DEADLINE_REMINDER = "deadline_reminder"
    PAYMENT_REQUEST = "payment_request"
    THANK_YOU = "thank_you"


class CommunicationTone(str, Enum):
    """Communication tone preferences."""
    FORMAL = "formal"
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    CASUAL = "casual"


class ClientSophistication(str, Enum):
    """Client's level of tax/financial sophistication."""
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


@dataclass
class ClientInfo:
    """Client information for personalization."""
    name: str
    email: Optional[str] = None
    preferred_name: Optional[str] = None
    company_name: Optional[str] = None
    tone_preference: CommunicationTone = CommunicationTone.PROFESSIONAL
    sophistication: ClientSophistication = ClientSophistication.INTERMEDIATE
    communication_history: List[str] = field(default_factory=list)
    special_notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "email": self.email,
            "preferred_name": self.preferred_name or (self.name.split()[0] if self.name and self.name.strip() else "Client"),
            "company_name": self.company_name,
            "tone_preference": self.tone_preference.value,
            "sophistication": self.sophistication.value,
            "special_notes": self.special_notes,
        }


@dataclass
class DraftedEmail:
    """A drafted email communication."""
    subject: str
    body: str
    purpose: EmailPurpose
    tone_used: CommunicationTone
    recipient_name: str
    call_to_action: Optional[str]
    follow_up_date: Optional[str]
    attachments_mentioned: List[str]
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject": self.subject,
            "body": self.body,
            "purpose": self.purpose.value,
            "tone_used": self.tone_used.value,
            "recipient_name": self.recipient_name,
            "call_to_action": self.call_to_action,
            "follow_up_date": self.follow_up_date,
            "attachments_mentioned": self.attachments_mentioned,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class TaxExplanation:
    """An explanation of a tax concept."""
    concept: str
    simple_explanation: str
    detailed_explanation: str
    key_points: List[str]
    examples: List[str]
    common_misconceptions: List[str]
    action_items: List[str]
    related_concepts: List[str]
    sophistication_level: ClientSophistication
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "concept": self.concept,
            "simple_explanation": self.simple_explanation,
            "detailed_explanation": self.detailed_explanation,
            "key_points": self.key_points,
            "examples": self.examples,
            "common_misconceptions": self.common_misconceptions,
            "action_items": self.action_items,
            "related_concepts": self.related_concepts,
            "sophistication_level": self.sophistication_level.value,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class FollowUpQuestions:
    """Generated follow-up questions for a client."""
    context: str
    questions: List[Dict[str, str]]  # {"question": "...", "reason": "..."}
    priority_order: List[int]
    estimated_response_time: str
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "context": self.context,
            "questions": self.questions,
            "priority_order": self.priority_order,
            "estimated_response_time": self.estimated_response_time,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class EngagementLetter:
    """A generated engagement letter."""
    client_name: str
    services: List[str]
    scope: str
    fees: Dict[str, Any]
    terms: List[str]
    effective_date: str
    body: str
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "client_name": self.client_name,
            "services": self.services,
            "scope": self.scope,
            "fees": self.fees,
            "terms": self.terms,
            "effective_date": self.effective_date,
            "body": self.body,
            "generated_at": self.generated_at.isoformat(),
        }


class ClaudeClientCommunicator:
    """
    Claude-powered client communication service.

    Generates personalized, professional client communications:
    - Adapts to client tone preferences
    - Adjusts technical language based on sophistication
    - Maintains professional standards
    - Includes appropriate disclaimers
    """

    # Email templates for different purposes
    EMAIL_GUIDELINES = {
        EmailPurpose.WELCOME: "Warm, welcoming, sets expectations",
        EmailPurpose.DOCUMENT_REQUEST: "Clear, specific, helpful",
        EmailPurpose.FOLLOW_UP: "Friendly reminder, not pushy",
        EmailPurpose.STATUS_UPDATE: "Informative, reassuring",
        EmailPurpose.QUESTION: "Clear, easy to respond to",
        EmailPurpose.ENGAGEMENT_LETTER: "Professional, comprehensive",
        EmailPurpose.TAX_SUMMARY: "Clear summary, highlight key points",
        EmailPurpose.DEADLINE_REMINDER: "Urgent but not alarming",
        EmailPurpose.PAYMENT_REQUEST: "Professional, clear terms",
        EmailPurpose.THANK_YOU: "Genuine, appreciative",
    }

    def __init__(self, ai_service=None, firm_name: str = "Your Tax Advisory Firm"):
        """
        Initialize client communicator.

        Args:
            ai_service: UnifiedAIService instance (lazy-loaded if not provided)
            firm_name: Name of the firm for signatures
        """
        self._ai_service = ai_service
        self.firm_name = firm_name

    @property
    def ai_service(self):
        """Lazy-load AI service."""
        if self._ai_service is None:
            from services.ai.unified_ai_service import get_ai_service
            self._ai_service = get_ai_service()
        return self._ai_service

    async def draft_client_email(
        self,
        purpose: EmailPurpose,
        client: ClientInfo,
        context: Dict[str, Any],
        include_signature: bool = True,
    ) -> DraftedEmail:
        """
        Draft a personalized client email.

        Args:
            purpose: Purpose of the email
            client: Client information for personalization
            context: Additional context for the email
            include_signature: Whether to include firm signature

        Returns:
            DraftedEmail with subject and body
        """
        guidelines = self.EMAIL_GUIDELINES.get(purpose, "Professional and clear")

        prompt = f"""Draft a professional email for a tax advisory firm.

CLIENT:
{json.dumps(client.to_dict(), indent=2)}

PURPOSE: {purpose.value}
GUIDELINES: {guidelines}

CONTEXT:
{json.dumps(context, indent=2)}

REQUIREMENTS:
1. Use {client.tone_preference.value} tone
2. Adjust technical language for {client.sophistication.value} level
3. Address client as "{client.preferred_name or (client.name.split()[0] if client.name and client.name.strip() else 'Client')}"
4. Include clear call-to-action
5. Be concise but complete
6. {'Include professional signature block' if include_signature else 'No signature needed'}

Return as JSON:
{{
    "subject": "Email subject line",
    "body": "Full email body with proper formatting",
    "call_to_action": "What you want the client to do",
    "follow_up_date": "Suggested follow-up date if applicable",
    "attachments_mentioned": ["any attachments referenced"]
}}

Make it personal and human, not templated."""

        try:
            from config.ai_providers import AIProvider
            response = await self.ai_service.complete(
                prompt=prompt,
                provider=AIProvider.ANTHROPIC,
                system_prompt=self._get_system_prompt(),
            )

            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            data = json.loads(content)

            return DraftedEmail(
                subject=data.get("subject", f"Re: {purpose.value}"),
                body=data.get("body", ""),
                purpose=purpose,
                tone_used=client.tone_preference,
                recipient_name=client.name,
                call_to_action=data.get("call_to_action"),
                follow_up_date=data.get("follow_up_date"),
                attachments_mentioned=data.get("attachments_mentioned", []),
            )

        except Exception as e:
            logger.error(f"Failed to draft email: {e}")
            return self._fallback_email(purpose, client, context)

    async def explain_tax_concept(
        self,
        concept: str,
        client_sophistication: ClientSophistication = ClientSophistication.INTERMEDIATE,
        specific_situation: Optional[str] = None,
    ) -> TaxExplanation:
        """
        Generate a clear explanation of a tax concept.

        Args:
            concept: The tax concept to explain
            client_sophistication: Client's level of knowledge
            specific_situation: Optional specific situation to relate to

        Returns:
            TaxExplanation with multiple levels of detail
        """
        sophistication_guidance = {
            ClientSophistication.BASIC: "Use everyday language, avoid jargon, use simple analogies",
            ClientSophistication.INTERMEDIATE: "Can use common tax terms, explain complex concepts",
            ClientSophistication.ADVANCED: "Comfortable with tax terminology, focus on nuances",
            ClientSophistication.EXPERT: "Professional-level, can discuss technical details",
        }

        prompt = f"""Explain this tax concept: {concept}

CLIENT LEVEL: {client_sophistication.value}
GUIDANCE: {sophistication_guidance.get(client_sophistication)}

{f'SPECIFIC SITUATION: {specific_situation}' if specific_situation else ''}

Provide explanation as JSON:
{{
    "simple_explanation": "2-3 sentence simple explanation",
    "detailed_explanation": "Comprehensive explanation (2-3 paragraphs)",
    "key_points": ["Most important points to remember"],
    "examples": ["Practical examples"],
    "common_misconceptions": ["Things people often get wrong"],
    "action_items": ["What the client should do"],
    "related_concepts": ["Related tax concepts to know"]
}}

Make it clear, accurate, and helpful. Avoid unnecessary jargon."""

        try:
            from config.ai_providers import AIProvider
            response = await self.ai_service.complete(
                prompt=prompt,
                provider=AIProvider.ANTHROPIC,
                system_prompt=self._get_system_prompt(),
            )

            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            data = json.loads(content)

            return TaxExplanation(
                concept=concept,
                simple_explanation=data.get("simple_explanation", ""),
                detailed_explanation=data.get("detailed_explanation", ""),
                key_points=data.get("key_points", []),
                examples=data.get("examples", []),
                common_misconceptions=data.get("common_misconceptions", []),
                action_items=data.get("action_items", []),
                related_concepts=data.get("related_concepts", []),
                sophistication_level=client_sophistication,
            )

        except Exception as e:
            logger.error(f"Failed to explain concept: {e}")
            return TaxExplanation(
                concept=concept,
                simple_explanation=f"Please consult with your tax advisor about {concept}.",
                detailed_explanation="",
                key_points=[],
                examples=[],
                common_misconceptions=[],
                action_items=["Schedule a consultation"],
                related_concepts=[],
                sophistication_level=client_sophistication,
            )

    async def generate_follow_up_questions(
        self,
        context: str,
        client: ClientInfo,
        max_questions: int = 5,
    ) -> FollowUpQuestions:
        """
        Generate follow-up questions based on client context.

        Args:
            context: Current context (what we know, what's missing)
            client: Client information
            max_questions: Maximum number of questions

        Returns:
            FollowUpQuestions with prioritized questions
        """
        prompt = f"""Generate follow-up questions for this tax client:

CLIENT:
{json.dumps(client.to_dict(), indent=2)}

CONTEXT:
{context}

Generate {max_questions} follow-up questions to gather necessary information.

Return as JSON:
{{
    "questions": [
        {{
            "question": "The question to ask",
            "reason": "Why this is important",
            "answer_type": "text/number/yes_no/document"
        }}
    ],
    "priority_order": [0, 1, 2, ...],
    "estimated_response_time": "X minutes"
}}

Questions should be:
1. Clear and easy to understand
2. Specific (not vague)
3. One question at a time (no compound questions)
4. Appropriate for their sophistication level
5. Prioritized by importance"""

        try:
            from config.ai_providers import AIProvider
            response = await self.ai_service.complete(
                prompt=prompt,
                provider=AIProvider.ANTHROPIC,
            )

            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            data = json.loads(content)

            return FollowUpQuestions(
                context=context,
                questions=data.get("questions", []),
                priority_order=data.get("priority_order", list(range(max_questions))),
                estimated_response_time=data.get("estimated_response_time", "5 minutes"),
            )

        except Exception as e:
            logger.error(f"Failed to generate follow-up questions: {e}")
            return FollowUpQuestions(
                context=context,
                questions=[{"question": "Please provide any additional information", "reason": "General"}],
                priority_order=[0],
                estimated_response_time="Unknown",
            )

    async def draft_engagement_letter(
        self,
        client: ClientInfo,
        services: List[str],
        fees: Dict[str, Any],
        tax_year: int = 2025,
    ) -> EngagementLetter:
        """
        Draft an engagement letter for a new client.

        Args:
            client: Client information
            services: Services to be provided
            fees: Fee structure
            tax_year: Tax year for services

        Returns:
            EngagementLetter with professional content
        """
        prompt = f"""Draft a professional tax engagement letter.

CLIENT: {client.name}
{f'COMPANY: {client.company_name}' if client.company_name else ''}

SERVICES:
{json.dumps(services, indent=2)}

FEES:
{json.dumps(fees, indent=2)}

TAX YEAR: {tax_year}

Create a professional engagement letter that includes:
1. Scope of services
2. Client responsibilities
3. Fee structure
4. Terms and conditions
5. Confidentiality
6. Professional standards

Return as JSON:
{{
    "scope": "Clear description of services",
    "terms": ["Key terms and conditions"],
    "body": "Complete engagement letter text"
}}

Make it professional but readable."""

        try:
            from config.ai_providers import AIProvider
            response = await self.ai_service.complete(
                prompt=prompt,
                provider=AIProvider.ANTHROPIC,
                system_prompt=self._get_system_prompt(),
            )

            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            data = json.loads(content)

            return EngagementLetter(
                client_name=client.name,
                services=services,
                scope=data.get("scope", "Tax preparation services"),
                fees=fees,
                terms=data.get("terms", []),
                effective_date=datetime.now().strftime("%Y-%m-%d"),
                body=data.get("body", ""),
            )

        except Exception as e:
            logger.error(f"Failed to draft engagement letter: {e}")
            return EngagementLetter(
                client_name=client.name,
                services=services,
                scope="Tax services as discussed",
                fees=fees,
                terms=["Standard terms apply"],
                effective_date=datetime.now().strftime("%Y-%m-%d"),
                body="Please contact our office for the engagement letter.",
            )

    async def draft_document_request(
        self,
        client: ClientInfo,
        missing_documents: List[str],
        deadline: Optional[str] = None,
    ) -> DraftedEmail:
        """
        Draft a document request email.

        Args:
            client: Client information
            missing_documents: List of documents needed
            deadline: Optional deadline for documents

        Returns:
            DraftedEmail with document request
        """
        context = {
            "missing_documents": missing_documents,
            "deadline": deadline,
            "document_count": len(missing_documents),
        }

        return await self.draft_client_email(
            purpose=EmailPurpose.DOCUMENT_REQUEST,
            client=client,
            context=context,
        )

    async def draft_status_update(
        self,
        client: ClientInfo,
        status: str,
        completed_items: List[str],
        pending_items: List[str],
        next_steps: List[str],
    ) -> DraftedEmail:
        """
        Draft a status update email.

        Args:
            client: Client information
            status: Current status summary
            completed_items: What has been completed
            pending_items: What is still pending
            next_steps: What happens next

        Returns:
            DraftedEmail with status update
        """
        context = {
            "status": status,
            "completed": completed_items,
            "pending": pending_items,
            "next_steps": next_steps,
        }

        return await self.draft_client_email(
            purpose=EmailPurpose.STATUS_UPDATE,
            client=client,
            context=context,
        )

    def _get_system_prompt(self) -> str:
        """Get system prompt for client communication."""
        return f"""You are a professional tax advisor at {self.firm_name}.

Your communication style:
- Professional but warm and approachable
- Clear and easy to understand
- Avoids unnecessary jargon
- Always accurate about tax matters
- Includes appropriate disclaimers when needed

When drafting communications:
1. Be personable - use the client's name naturally
2. Be clear - one idea per paragraph
3. Be helpful - anticipate questions
4. Be professional - maintain appropriate boundaries
5. Be accurate - don't make up tax rules

Always end with clear next steps or call to action."""

    def _fallback_email(
        self,
        purpose: EmailPurpose,
        client: ClientInfo,
        context: Dict[str, Any],
    ) -> DraftedEmail:
        """Generate fallback email when AI fails."""
        templates = {
            EmailPurpose.DOCUMENT_REQUEST: (
                f"Document Request - Action Required",
                f"""Dear {client.preferred_name or client.name},

We are writing to request the following documents needed to complete your tax preparation:

{chr(10).join('- ' + doc for doc in context.get('missing_documents', ['Required documents']))}

Please provide these documents at your earliest convenience.

Best regards,
{self.firm_name}"""
            ),
            EmailPurpose.STATUS_UPDATE: (
                f"Tax Preparation Status Update",
                f"""Dear {client.preferred_name or client.name},

We wanted to provide you with an update on your tax preparation.

Current Status: {context.get('status', 'In Progress')}

Please let us know if you have any questions.

Best regards,
{self.firm_name}"""
            ),
        }

        subject, body = templates.get(purpose, (
            f"Message from {self.firm_name}",
            f"Dear {client.name},\n\nPlease contact our office.\n\nBest regards,\n{self.firm_name}"
        ))

        return DraftedEmail(
            subject=subject,
            body=body,
            purpose=purpose,
            tone_used=client.tone_preference,
            recipient_name=client.name,
            call_to_action="Please respond to this email",
            follow_up_date=None,
            attachments_mentioned=[],
        )


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_client_communicator: Optional[ClaudeClientCommunicator] = None


def get_client_communicator(firm_name: str = "Your Tax Advisory Firm") -> ClaudeClientCommunicator:
    """Get the singleton client communicator instance."""
    global _client_communicator
    if _client_communicator is None:
        _client_communicator = ClaudeClientCommunicator(firm_name=firm_name)
    return _client_communicator


__all__ = [
    "ClaudeClientCommunicator",
    "ClientInfo",
    "DraftedEmail",
    "TaxExplanation",
    "FollowUpQuestions",
    "EngagementLetter",
    "EmailPurpose",
    "CommunicationTone",
    "ClientSophistication",
    "get_client_communicator",
]
