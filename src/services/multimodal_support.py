"""
AI-Powered Multimodal Support Service.

Uses Gemini for voice, video, and image processing:
- Voice message transcription and analysis
- Video call summarization
- Screen recording analysis
- Document photo processing
- Meeting notes extraction

Usage:
    from services.multimodal_support import get_multimodal_support

    multimodal = get_multimodal_support()

    # Process a voice message
    result = await multimodal.process_voice_message(audio_bytes)

    # Summarize a client call recording
    summary = await multimodal.summarize_client_call(video_bytes)

    # Process a document photo
    document = await multimodal.process_document_photo(image_bytes)
"""

import logging
import json
import base64
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MediaType(str, Enum):
    """Supported media types."""
    AUDIO = "audio"
    VIDEO = "video"
    IMAGE = "image"
    SCREEN_RECORDING = "screen_recording"


class TranscriptSpeaker(str, Enum):
    """Speaker types in transcripts."""
    CLIENT = "client"
    ADVISOR = "advisor"
    UNKNOWN = "unknown"


@dataclass
class TranscriptionResult:
    """Result of audio/video transcription."""
    text: str
    language: str
    confidence: float
    duration_seconds: float
    word_count: int
    speakers: List[Dict[str, Any]]  # speaker segments
    tax_relevant_topics: List[str]
    action_items_mentioned: List[str]
    questions_asked: List[str]
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "language": self.language,
            "confidence": self.confidence,
            "duration_seconds": self.duration_seconds,
            "word_count": self.word_count,
            "speakers": self.speakers,
            "tax_relevant_topics": self.tax_relevant_topics,
            "action_items_mentioned": self.action_items_mentioned,
            "questions_asked": self.questions_asked,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class CallSummary:
    """Summary of a client call."""
    call_duration: str
    participants: List[str]
    main_topics: List[str]
    key_decisions: List[str]
    action_items: List[Dict[str, str]]  # {"task": "...", "owner": "...", "deadline": "..."}
    follow_up_needed: bool
    follow_up_items: List[str]
    client_concerns: List[str]
    advisor_recommendations: List[str]
    documents_discussed: List[str]
    next_meeting_suggested: Optional[str]
    summary_text: str
    transcript_excerpt: Optional[str]
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_duration": self.call_duration,
            "participants": self.participants,
            "main_topics": self.main_topics,
            "key_decisions": self.key_decisions,
            "action_items": self.action_items,
            "follow_up_needed": self.follow_up_needed,
            "follow_up_items": self.follow_up_items,
            "client_concerns": self.client_concerns,
            "advisor_recommendations": self.advisor_recommendations,
            "documents_discussed": self.documents_discussed,
            "next_meeting_suggested": self.next_meeting_suggested,
            "summary_text": self.summary_text,
            "transcript_excerpt": self.transcript_excerpt,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class ScreenAnalysis:
    """Analysis of a screen recording."""
    duration_seconds: float
    screens_detected: List[str]
    tax_software_used: Optional[str]
    forms_visible: List[str]
    data_entered: Dict[str, Any]
    potential_errors: List[str]
    workflow_steps: List[str]
    recommendations: List[str]
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "duration_seconds": self.duration_seconds,
            "screens_detected": self.screens_detected,
            "tax_software_used": self.tax_software_used,
            "forms_visible": self.forms_visible,
            "data_entered": self.data_entered,
            "potential_errors": self.potential_errors,
            "workflow_steps": self.workflow_steps,
            "recommendations": self.recommendations,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class DocumentPhotoResult:
    """Result of processing a document photo."""
    document_type: str
    confidence: float
    extracted_text: str
    structured_data: Dict[str, Any]
    quality_issues: List[str]
    recommendations: List[str]
    is_complete: bool
    missing_sections: List[str]
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_type": self.document_type,
            "confidence": self.confidence,
            "extracted_text": self.extracted_text,
            "structured_data": self.structured_data,
            "quality_issues": self.quality_issues,
            "recommendations": self.recommendations,
            "is_complete": self.is_complete,
            "missing_sections": self.missing_sections,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class MeetingNotes:
    """Extracted meeting notes."""
    meeting_date: str
    attendees: List[str]
    agenda_items: List[str]
    discussion_points: List[Dict[str, str]]
    decisions_made: List[str]
    action_items: List[Dict[str, str]]
    open_questions: List[str]
    next_steps: List[str]
    notes_text: str
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "meeting_date": self.meeting_date,
            "attendees": self.attendees,
            "agenda_items": self.agenda_items,
            "discussion_points": self.discussion_points,
            "decisions_made": self.decisions_made,
            "action_items": self.action_items,
            "open_questions": self.open_questions,
            "next_steps": self.next_steps,
            "notes_text": self.notes_text,
            "generated_at": self.generated_at.isoformat(),
        }


class GeminiMultimodalSupport:
    """
    Gemini-powered multimodal support service.

    Processes various media types for tax advisory context:
    - Audio transcription with tax topic extraction
    - Video call analysis and summarization
    - Screen recording workflow analysis
    - Document photo OCR and structuring
    """

    # Tax-relevant keywords for extraction
    TAX_KEYWORDS = [
        "deduction", "credit", "income", "expense", "w-2", "1099",
        "refund", "owe", "audit", "irs", "filing", "deadline",
        "tax return", "dependent", "exemption", "withholding",
        "estimated tax", "quarterly", "extension", "amendment",
        "capital gains", "loss", "depreciation", "business expense",
        "home office", "mileage", "charity", "donation", "retirement",
        "401k", "ira", "roth", "hsa", "fsa", "schedule c", "schedule e",
    ]

    def __init__(self, ai_service=None):
        """
        Initialize multimodal support service.

        Args:
            ai_service: UnifiedAIService instance (lazy-loaded if not provided)
        """
        self._ai_service = ai_service

    @property
    def ai_service(self):
        """Lazy-load AI service."""
        if self._ai_service is None:
            from services.ai.unified_ai_service import get_ai_service
            self._ai_service = get_ai_service()
        return self._ai_service

    async def process_voice_message(
        self,
        audio_data: bytes,
        audio_format: str = "mp3",
        extract_tax_topics: bool = True,
    ) -> TranscriptionResult:
        """
        Process and transcribe a voice message.

        Args:
            audio_data: Audio file bytes
            audio_format: Format of the audio (mp3, wav, etc.)
            extract_tax_topics: Whether to extract tax-relevant topics

        Returns:
            TranscriptionResult with transcription and analysis
        """
        # Encode audio for API
        audio_b64 = base64.b64encode(audio_data).decode("utf-8")

        prompt = f"""Transcribe this audio message and analyze it for tax-relevant content.

The audio is a voice message from a tax client or about tax matters.

Provide transcription and analysis as JSON:
{{
    "transcription": "Full transcription of the audio",
    "language": "detected language",
    "confidence": 0.0-1.0,
    "duration_estimate": "estimated duration in seconds",
    "speakers": [
        {{"speaker": "Speaker 1", "segments": ["what they said"]}}
    ],
    "tax_topics": ["tax topics mentioned"],
    "action_items": ["any action items mentioned"],
    "questions": ["any questions asked"]
}}

Focus on accuracy and identifying tax-relevant information."""

        try:
            from config.ai_providers import AIProvider

            # Use Gemini for multimodal processing
            response = await self.ai_service.analyze_audio(
                audio_data=audio_data,
                prompt=prompt,
                audio_format=audio_format,
            )

            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            data = json.loads(content)

            return TranscriptionResult(
                text=data.get("transcription", ""),
                language=data.get("language", "en"),
                confidence=data.get("confidence", 0.8),
                duration_seconds=float(data.get("duration_estimate", 0)),
                word_count=len(data.get("transcription", "").split()),
                speakers=data.get("speakers", []),
                tax_relevant_topics=data.get("tax_topics", []),
                action_items_mentioned=data.get("action_items", []),
                questions_asked=data.get("questions", []),
            )

        except Exception as e:
            logger.error(f"Failed to process voice message: {e}")
            return TranscriptionResult(
                text="Unable to transcribe audio",
                language="unknown",
                confidence=0.0,
                duration_seconds=0,
                word_count=0,
                speakers=[],
                tax_relevant_topics=[],
                action_items_mentioned=[],
                questions_asked=[],
            )

    async def summarize_client_call(
        self,
        video_data: bytes,
        video_format: str = "mp4",
        client_name: Optional[str] = None,
    ) -> CallSummary:
        """
        Summarize a recorded client call.

        Args:
            video_data: Video file bytes
            video_format: Format of the video
            client_name: Optional client name for context

        Returns:
            CallSummary with comprehensive call summary
        """
        prompt = f"""Analyze this recorded client call and create a comprehensive summary.

{f'Client: {client_name}' if client_name else ''}

This is a tax advisory call. Extract:
1. Main topics discussed
2. Key decisions made
3. Action items for each party
4. Client concerns raised
5. Advisor recommendations
6. Documents mentioned
7. Follow-up items needed

Provide as JSON:
{{
    "duration": "estimated duration",
    "participants": ["identified participants"],
    "main_topics": ["main discussion topics"],
    "key_decisions": ["decisions made"],
    "action_items": [
        {{"task": "task description", "owner": "who", "deadline": "when"}}
    ],
    "follow_up_needed": true/false,
    "follow_up_items": ["items requiring follow-up"],
    "client_concerns": ["concerns raised by client"],
    "advisor_recommendations": ["recommendations given"],
    "documents_discussed": ["documents mentioned"],
    "next_meeting": "suggested next meeting if any",
    "summary": "2-3 paragraph summary of the call"
}}"""

        try:
            from config.ai_providers import AIProvider

            response = await self.ai_service.analyze_video(
                video_data=video_data,
                prompt=prompt,
                video_format=video_format,
            )

            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            data = json.loads(content)

            return CallSummary(
                call_duration=data.get("duration", "Unknown"),
                participants=data.get("participants", []),
                main_topics=data.get("main_topics", []),
                key_decisions=data.get("key_decisions", []),
                action_items=data.get("action_items", []),
                follow_up_needed=data.get("follow_up_needed", False),
                follow_up_items=data.get("follow_up_items", []),
                client_concerns=data.get("client_concerns", []),
                advisor_recommendations=data.get("advisor_recommendations", []),
                documents_discussed=data.get("documents_discussed", []),
                next_meeting_suggested=data.get("next_meeting"),
                summary_text=data.get("summary", ""),
                transcript_excerpt=None,
            )

        except Exception as e:
            logger.error(f"Failed to summarize client call: {e}")
            return CallSummary(
                call_duration="Unknown",
                participants=[],
                main_topics=["Unable to analyze call"],
                key_decisions=[],
                action_items=[],
                follow_up_needed=True,
                follow_up_items=["Review call manually"],
                client_concerns=[],
                advisor_recommendations=[],
                documents_discussed=[],
                next_meeting_suggested=None,
                summary_text="Call analysis failed. Please review manually.",
                transcript_excerpt=None,
            )

    async def analyze_screen_recording(
        self,
        video_data: bytes,
        video_format: str = "mp4",
        context: Optional[str] = None,
    ) -> ScreenAnalysis:
        """
        Analyze a screen recording (e.g., tax software walkthrough).

        Args:
            video_data: Video file bytes
            video_format: Format of the video
            context: Optional context about what's being shown

        Returns:
            ScreenAnalysis with workflow and data extraction
        """
        prompt = f"""Analyze this screen recording of tax-related work.

{f'Context: {context}' if context else ''}

Identify:
1. What software/screens are shown
2. Tax forms visible
3. Data being entered
4. Any potential errors or issues
5. Workflow steps taken

Provide as JSON:
{{
    "duration": estimated_seconds,
    "screens": ["screens/applications shown"],
    "tax_software": "identified tax software if any",
    "forms": ["tax forms visible"],
    "data_entered": {{"field": "value"}},
    "potential_errors": ["any errors or issues spotted"],
    "workflow": ["step by step what was done"],
    "recommendations": ["suggestions for improvement"]
}}"""

        try:
            from config.ai_providers import AIProvider

            response = await self.ai_service.analyze_video(
                video_data=video_data,
                prompt=prompt,
                video_format=video_format,
            )

            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            data = json.loads(content)

            return ScreenAnalysis(
                duration_seconds=float(data.get("duration", 0)),
                screens_detected=data.get("screens", []),
                tax_software_used=data.get("tax_software"),
                forms_visible=data.get("forms", []),
                data_entered=data.get("data_entered", {}),
                potential_errors=data.get("potential_errors", []),
                workflow_steps=data.get("workflow", []),
                recommendations=data.get("recommendations", []),
            )

        except Exception as e:
            logger.error(f"Failed to analyze screen recording: {e}")
            return ScreenAnalysis(
                duration_seconds=0,
                screens_detected=[],
                tax_software_used=None,
                forms_visible=[],
                data_entered={},
                potential_errors=["Analysis failed"],
                workflow_steps=[],
                recommendations=["Manual review required"],
            )

    async def process_document_photo(
        self,
        image_data: bytes,
        expected_document_type: Optional[str] = None,
    ) -> DocumentPhotoResult:
        """
        Process a photo of a tax document.

        Args:
            image_data: Image file bytes
            expected_document_type: Optional expected document type

        Returns:
            DocumentPhotoResult with OCR and structured data
        """
        prompt = f"""Process this photo of a tax document.

{f'Expected document type: {expected_document_type}' if expected_document_type else ''}

Extract:
1. Document type
2. All readable text
3. Structured data (fields and values)
4. Image quality issues
5. Missing or unclear sections

Provide as JSON:
{{
    "document_type": "identified document type",
    "confidence": 0.0-1.0,
    "text": "all extracted text",
    "data": {{
        "field_name": "value"
    }},
    "quality_issues": ["any image quality problems"],
    "recommendations": ["suggestions for better capture"],
    "is_complete": true/false,
    "missing": ["sections that are missing or unreadable"]
}}"""

        try:
            from config.ai_providers import AIProvider

            response = await self.ai_service.analyze_image(
                image_data=image_data,
                prompt=prompt,
            )

            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            data = json.loads(content)

            return DocumentPhotoResult(
                document_type=data.get("document_type", "Unknown"),
                confidence=data.get("confidence", 0.5),
                extracted_text=data.get("text", ""),
                structured_data=data.get("data", {}),
                quality_issues=data.get("quality_issues", []),
                recommendations=data.get("recommendations", []),
                is_complete=data.get("is_complete", False),
                missing_sections=data.get("missing", []),
            )

        except Exception as e:
            logger.error(f"Failed to process document photo: {e}")
            return DocumentPhotoResult(
                document_type="Unknown",
                confidence=0.0,
                extracted_text="",
                structured_data={},
                quality_issues=["Processing failed"],
                recommendations=["Please retake the photo with better lighting"],
                is_complete=False,
                missing_sections=["Unable to process"],
            )

    async def extract_meeting_notes(
        self,
        audio_or_video_data: bytes,
        media_type: MediaType,
        meeting_date: Optional[str] = None,
    ) -> MeetingNotes:
        """
        Extract structured meeting notes from audio/video.

        Args:
            audio_or_video_data: Media file bytes
            media_type: Type of media (audio or video)
            meeting_date: Optional meeting date

        Returns:
            MeetingNotes with structured extraction
        """
        date_str = meeting_date or datetime.now().strftime("%Y-%m-%d")

        prompt = f"""Extract structured meeting notes from this {media_type.value}.

Meeting Date: {date_str}

Create comprehensive meeting notes including:
1. Attendees identified
2. Agenda items (inferred)
3. Discussion points
4. Decisions made
5. Action items with owners
6. Open questions
7. Next steps

Provide as JSON:
{{
    "attendees": ["identified attendees"],
    "agenda": ["agenda items discussed"],
    "discussion": [
        {{"topic": "topic", "summary": "what was discussed"}}
    ],
    "decisions": ["decisions made"],
    "actions": [
        {{"task": "task", "owner": "who", "deadline": "when"}}
    ],
    "questions": ["unresolved questions"],
    "next_steps": ["agreed next steps"],
    "notes": "narrative summary of the meeting"
}}"""

        try:
            from config.ai_providers import AIProvider

            if media_type == MediaType.AUDIO:
                response = await self.ai_service.analyze_audio(
                    audio_data=audio_or_video_data,
                    prompt=prompt,
                )
            else:
                response = await self.ai_service.analyze_video(
                    video_data=audio_or_video_data,
                    prompt=prompt,
                )

            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            data = json.loads(content)

            return MeetingNotes(
                meeting_date=date_str,
                attendees=data.get("attendees", []),
                agenda_items=data.get("agenda", []),
                discussion_points=data.get("discussion", []),
                decisions_made=data.get("decisions", []),
                action_items=data.get("actions", []),
                open_questions=data.get("questions", []),
                next_steps=data.get("next_steps", []),
                notes_text=data.get("notes", ""),
            )

        except Exception as e:
            logger.error(f"Failed to extract meeting notes: {e}")
            return MeetingNotes(
                meeting_date=date_str,
                attendees=[],
                agenda_items=[],
                discussion_points=[],
                decisions_made=[],
                action_items=[],
                open_questions=["Meeting extraction failed"],
                next_steps=["Manual note-taking required"],
                notes_text="Unable to extract meeting notes automatically.",
            )


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_multimodal_support: Optional[GeminiMultimodalSupport] = None


def get_multimodal_support() -> GeminiMultimodalSupport:
    """Get the singleton multimodal support instance."""
    global _multimodal_support
    if _multimodal_support is None:
        _multimodal_support = GeminiMultimodalSupport()
    return _multimodal_support


__all__ = [
    "GeminiMultimodalSupport",
    "TranscriptionResult",
    "CallSummary",
    "ScreenAnalysis",
    "DocumentPhotoResult",
    "MeetingNotes",
    "MediaType",
    "get_multimodal_support",
]
