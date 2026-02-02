"""
AI Chat API - IMPROVED VERSION with Robust Error Handling

This improved version includes:
- Comprehensive input validation
- Session management with error recovery
- Better OCR error handling
- Request ID tracking
- Graceful degradation
- User-friendly error messages
- Rate limiting considerations
- Detailed logging

To use: Replace ai_chat_api.py with this file
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import traceback
import tempfile
import os

# Initialize logger early - before try blocks that use it
logger = logging.getLogger(__name__)

try:
    from agent.intelligent_tax_agent import IntelligentTaxAgent, ExtractedEntity, ConversationContext
    AGENT_AVAILABLE = True
except ImportError as e:
    AGENT_AVAILABLE = False
    logger.warning(f"IntelligentTaxAgent not available: {e}")

try:
    from models.tax_return import FilingStatus
except ImportError:
    from enum import Enum
    class FilingStatus(str, Enum):
        SINGLE = "single"
        MARRIED_FILING_JOINTLY = "married_filing_jointly"
        MARRIED_FILING_SEPARATELY = "married_filing_separately"
        HEAD_OF_HOUSEHOLD = "head_of_household"
        QUALIFYING_WIDOW = "qualifying_widow"

try:
    from web.validation_helpers import sanitize_string, validate_positive_integer
except ImportError:
    import html
    import re

    def sanitize_string(s, max_len=1000):
        """Sanitize string by escaping HTML and removing dangerous patterns."""
        if not s:
            return ""
        # Convert to string and truncate
        s = str(s)[:max_len].strip()
        # Escape HTML entities to prevent XSS
        s = html.escape(s, quote=True)
        # Remove any script tags that might have been encoded differently
        s = re.sub(r'(?i)<\s*script[^>]*>.*?<\s*/\s*script\s*>', '', s)
        # Remove javascript: protocol
        s = re.sub(r'(?i)javascript:', '', s)
        # Remove event handlers
        s = re.sub(r'(?i)on\w+\s*=', '', s)
        return s

    def validate_positive_integer(v):
        return max(0, int(v)) if v else 0

# Import database persistence
try:
    from database.unified_session import UnifiedFilingSession, FilingState, WorkflowType, ConversationMessage
    from database.session_persistence import get_session_persistence
    DB_AVAILABLE = True
except ImportError as e:
    DB_AVAILABLE = False
    logger.warning(f"Database persistence not available: {e}")

router = APIRouter(prefix="/api/ai-chat", tags=["ai-chat"])


# ============================================================================
# Session Storage - NOW USING DATABASE (UPDATED)
# ============================================================================

# REPLACED: In-memory chat_sessions dict with database persistence
# OLD: chat_sessions: Dict[str, Dict[str, Any]] = {}
# NEW: Use get_session_persistence() for all operations

# Initialize persistence if available
persistence = None
if DB_AVAILABLE:
    try:
        persistence = get_session_persistence()
    except Exception as e:
        logger.warning(f"Failed to initialize persistence: {e}")

# In-memory fallback for sessions
_chat_sessions: Dict[str, Dict[str, Any]] = {}

# Session limits to prevent abuse
MAX_CONVERSATION_TURNS = 50  # Reduced from 100 to prevent memory bloat

# Conversation history management
try:
    from web.helpers.conversation_history import (
        prune_conversation_history,
        get_optimized_context,
        SLIDING_WINDOW_SIZE,
    )
    HISTORY_MANAGEMENT_AVAILABLE = True
except ImportError:
    HISTORY_MANAGEMENT_AVAILABLE = False
    SLIDING_WINDOW_SIZE = 15

# Rate limiting - track requests per session
_rate_limit_tracker: Dict[str, List[float]] = {}
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 30  # max requests per window


def check_rate_limit(session_id: str) -> bool:
    """
    Check if session has exceeded rate limit.
    Returns True if within limits, False if exceeded.
    """
    import time
    now = time.time()

    # Get request timestamps for this session
    if session_id not in _rate_limit_tracker:
        _rate_limit_tracker[session_id] = []

    timestamps = _rate_limit_tracker[session_id]

    # Remove old timestamps outside the window
    timestamps[:] = [ts for ts in timestamps if now - ts < RATE_LIMIT_WINDOW]

    # Check if limit exceeded
    if len(timestamps) >= RATE_LIMIT_MAX_REQUESTS:
        return False

    # Add current timestamp
    timestamps.append(now)
    return True


# ============================================================================
# Enhanced Request/Response Models with Validation
# ============================================================================

class ChatMessageRequest(BaseModel):
    """User message to AI assistant"""
    session_id: str = Field(..., min_length=1, max_length=100)
    user_message: str = Field(..., min_length=1, max_length=5000)
    conversation_history: List[Dict[str, str]] = Field(default_factory=list, max_items=50)
    extracted_data: Dict[str, Any] = Field(default_factory=dict)

    @validator('session_id')
    def validate_session_id(cls, v):
        """Sanitize session ID"""
        sanitized = sanitize_string(v, 100)
        if not sanitized:
            raise ValueError("Invalid session ID")
        return sanitized

    @validator('user_message')
    def validate_message(cls, v):
        """Sanitize and validate user message"""
        sanitized = sanitize_string(v, 5000)
        if not sanitized or len(sanitized.strip()) == 0:
            raise ValueError("Message cannot be empty")
        return sanitized


class QuickAction(BaseModel):
    """Quick reply button"""
    label: str = Field(..., max_length=50)
    value: str = Field(..., max_length=200)


class DataCard(BaseModel):
    """Data visualization card"""
    icon: str = Field(..., max_length=10)
    title: str = Field(..., max_length=100)
    items: List[Dict[str, str]] = Field(..., max_items=20)


class Insight(BaseModel):
    """AI-generated insight"""
    icon: str = Field(..., max_length=10)
    title: str = Field(..., max_length=100)
    text: str = Field(..., max_length=500)


class Suggestion(BaseModel):
    """Input suggestion"""
    text: str = Field(..., max_length=100)
    value: str = Field(..., max_length=200)


class ProgressUpdate(BaseModel):
    """Progress tracking"""
    current_step: int = Field(..., ge=0, le=10)
    total_steps: int = Field(default=5, ge=1, le=10)
    phase_name: str = Field(..., max_length=50)


class ChatMessageResponse(BaseModel):
    """AI response to user message"""
    response: str
    quick_actions: List[QuickAction] = Field(default_factory=list, max_items=5)
    data_cards: List[DataCard] = Field(default_factory=list, max_items=5)
    insights: List[Insight] = Field(default_factory=list, max_items=3)
    suggestions: List[Suggestion] = Field(default_factory=list, max_items=5)
    extracted_entities: List[ExtractedEntity] = Field(default_factory=list)
    progress_update: Optional[ProgressUpdate] = None


class UploadResponse(BaseModel):
    """Document upload response"""
    success: bool
    response: str
    quick_actions: List[QuickAction] = Field(default_factory=list)
    data_cards: List[DataCard] = Field(default_factory=list)
    extracted_entities: List[ExtractedEntity] = Field(default_factory=list)


class AnalyzeDocumentResponse(BaseModel):
    """Document analysis response for intelligent advisor"""
    ai_response: str
    quick_actions: List[QuickAction] = Field(default_factory=list)
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    completion_percentage: int = Field(default=0, ge=0, le=100)
    extracted_summary: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Endpoints - IMPROVED
# ============================================================================

# Extended ChatRequest model to support system_context from frontend
class ExtendedChatRequest(ChatMessageRequest):
    """Extended request model for /chat endpoint compatibility"""
    system_context: Optional[Dict[str, Any]] = Field(default=None)


@router.post("/chat", response_model=ChatMessageResponse)
async def process_chat_endpoint(request: ExtendedChatRequest):
    """
    Alias endpoint for /message - maintains backward compatibility.
    Accepts additional system_context field from frontend.
    """
    # Convert to base ChatMessageRequest and forward
    base_request = ChatMessageRequest(
        session_id=request.session_id,
        user_message=request.user_message,
        conversation_history=request.conversation_history,
        extracted_data=request.extracted_data
    )
    return await process_chat_message(base_request)


@router.post("/message", response_model=ChatMessageResponse)
async def process_chat_message(request: ChatMessageRequest):
    """
    Process conversational message from user - IMPROVED.

    Enhancements:
    - Request ID tracking for debugging
    - Session validation and cleanup
    - Graceful error handling
    - Turn limit enforcement
    - Better logging
    """
    request_id = f"CHAT-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    try:
        # Rate limit check
        if not check_rate_limit(request.session_id):
            logger.warning(f"[{request_id}] Rate limit exceeded for session {request.session_id}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error_type": "RateLimitExceeded",
                    "user_message": "You're sending messages too quickly. Please wait a moment before trying again.",
                    "request_id": request_id
                }
            )

        logger.info(f"[{request_id}] Chat message received", extra={
            "session_id": request.session_id,
            "message_length": len(request.user_message),
            "request_id": request_id
        })

        # Get or create session - use in-memory as primary (for reliability)
        unified_session = None
        use_memory_fallback = persistence is None

        # First check in-memory storage (always available)
        if request.session_id in _chat_sessions:
            unified_session = _chat_sessions[request.session_id]
            logger.debug(f"[{request_id}] Session loaded from memory: {request.session_id}")

        # Try database if not in memory and database is available
        if unified_session is None and not use_memory_fallback:
            try:
                db_session = persistence.load_unified_session(request.session_id)
                if db_session:
                    # Convert to dict format for consistency
                    unified_session = {
                        "session_id": db_session.session_id,
                        "metadata": db_session.metadata,
                        "extracted_data": db_session.extracted_data,
                        "conversation_history": [
                            {"role": m.role, "content": m.content, "timestamp": m.timestamp}
                            for m in db_session.conversation_history
                        ]
                    }
                    # Cache in memory
                    _chat_sessions[request.session_id] = unified_session.copy()
                    logger.debug(f"[{request_id}] Session loaded from database: {request.session_id}")
            except Exception as e:
                logger.warning(f"[{request_id}] Database load failed: {e}")
                use_memory_fallback = True

        if unified_session is None:
            # Create new session (always use dict-based for reliability)
            unified_session = {
                "session_id": request.session_id,
                "metadata": {"current_phase": "personal_info", "turn_count": 0},
                "extracted_data": {},
                "conversation_history": []
            }

            # Store in memory
            _chat_sessions[request.session_id] = unified_session.copy()

            # Try to save to database if available (but don't fail if it doesn't work)
            if not use_memory_fallback and persistence:
                try:
                    db_session = UnifiedFilingSession(
                        session_id=request.session_id,
                        workflow_type=WorkflowType.CHAT,
                        state=FilingState.QUESTIONS,
                        metadata={"current_phase": "personal_info", "turn_count": 0}
                    )
                    persistence.save_unified_session(db_session)
                    logger.info(f"[{request_id}] New chat session created in database: {request.session_id}")
                except Exception as db_error:
                    logger.warning(f"[{request_id}] Database save failed (using in-memory): {db_error}")
            else:
                logger.info(f"[{request_id}] New chat session created in memory: {request.session_id}")

        # Helper to get session attribute (works with both dict and object)
        def get_session_attr(session, attr, default=None):
            if isinstance(session, dict):
                return session.get(attr, default)
            return getattr(session, attr, default)

        def set_session_attr(session, attr, value):
            if isinstance(session, dict):
                session[attr] = value
            else:
                setattr(session, attr, value)

        # Check turn limit
        metadata = get_session_attr(unified_session, "metadata", {})
        turn_count = metadata.get("turn_count", 0) if isinstance(metadata, dict) else 0
        if turn_count >= MAX_CONVERSATION_TURNS:
            logger.warning(f"[{request_id}] Turn limit reached for session {request.session_id}")
            return ChatMessageResponse(
                response="We've covered a lot! To ensure the best experience, let's start a new conversation. Please refresh the page.",
                quick_actions=[
                    QuickAction(label="Start Over", value="new_session")
                ]
            )

        # Create agent (they don't persist, only data does)
        if not AGENT_AVAILABLE:
            logger.warning(f"[{request_id}] IntelligentTaxAgent not available, using fallback")
            return _create_fallback_response(request.user_message)

        try:
            agent = IntelligentTaxAgent()
        except ValueError as e:
            # OpenAI API key not configured
            logger.warning(f"[{request_id}] Agent initialization failed (likely missing API key): {e}")
            return _create_simple_response(request.user_message)
        except Exception as e:
            logger.error(f"[{request_id}] Agent initialization failed: {e}")
            return _create_fallback_response(request.user_message)

        # Restore conversation history to agent's messages (with pruning/optimization)
        conversation_history = get_session_attr(unified_session, "conversation_history", [])

        # Apply sliding window and optional summarization to prevent memory bloat
        if HISTORY_MANAGEMENT_AVAILABLE and len(conversation_history) > SLIDING_WINDOW_SIZE * 2:
            extracted_data = get_session_attr(unified_session, "extracted_data", {})
            optimized_history = get_optimized_context(
                conversation_history,
                extracted_data,
                max_turns=SLIDING_WINDOW_SIZE
            )
            logger.debug(f"[{request_id}] Optimized history: {len(conversation_history)} -> {len(optimized_history)} messages")
            conversation_history = optimized_history

        for msg in conversation_history:
            if isinstance(msg, dict):
                agent.messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
            elif hasattr(msg, 'role') and hasattr(msg, 'content'):
                agent.messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

        # Add user message to session
        if isinstance(unified_session, dict):
            unified_session.setdefault("conversation_history", []).append({
                "role": "user",
                "content": request.user_message,
                "timestamp": datetime.now().isoformat()
            })
        elif hasattr(unified_session, 'add_message'):
            unified_session.add_message("user", request.user_message)

        # Increment turn count
        turn_count += 1
        metadata["turn_count"] = turn_count
        if isinstance(unified_session, dict):
            unified_session["metadata"] = metadata
        else:
            unified_session.metadata = metadata

        # Process message with agent (with timeout protection)
        # Note: process_message returns a string and stores entities in agent.context.extraction_history
        try:
            ai_response_text = agent.process_message(
                user_input=request.user_message
            )
        except TimeoutError:
            logger.error(f"[{request_id}] Agent processing timeout")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail={
                    "error_type": "ProcessingTimeout",
                    "user_message": "That's taking longer than expected. Could you rephrase your question?",
                    "request_id": request_id
                }
            )
        except Exception as e:
            logger.error(f"[{request_id}] Agent processing failed: {str(e)}", exc_info=True)
            # Return graceful fallback response
            return _create_fallback_response(request.user_message)

        # Get extracted entities from agent's context
        extracted_entities = []
        if hasattr(agent, 'context') and hasattr(agent.context, 'extraction_history'):
            extracted_entities = agent.context.extraction_history

        # Get extracted_data from session
        extracted_data = get_session_attr(unified_session, "extracted_data", {})
        if not isinstance(extracted_data, dict):
            extracted_data = {}

        # Update session data with validation
        for entity in extracted_entities:
            try:
                if hasattr(entity, 'entity_type') and hasattr(entity, 'value'):
                    # Sanitize string values
                    if isinstance(entity.value, str):
                        extracted_data[entity.entity_type] = sanitize_string(entity.value)
                    else:
                        extracted_data[entity.entity_type] = entity.value
            except Exception as e:
                logger.warning(f"[{request_id}] Failed to extract entity: {str(e)}")
                continue

        # Update session's extracted_data
        if isinstance(unified_session, dict):
            unified_session["extracted_data"] = extracted_data
        else:
            unified_session.extracted_data = extracted_data

        # Determine current phase
        current_phase = _determine_phase(extracted_data)
        metadata["current_phase"] = current_phase
        if isinstance(unified_session, dict):
            unified_session["metadata"] = metadata
        else:
            unified_session.metadata = metadata

        # AI response text is already available from process_message
        ai_response = ai_response_text if ai_response_text else "I'm here to help with your taxes. What would you like to know?"

        # Add response to session history
        if isinstance(unified_session, dict):
            unified_session.setdefault("conversation_history", []).append({
                "role": "assistant",
                "content": ai_response,
                "timestamp": datetime.now().isoformat()
            })
        elif hasattr(unified_session, 'add_message'):
            unified_session.add_message("assistant", ai_response)

        # Generate contextual UI elements
        quick_actions = _generate_quick_actions(current_phase, extracted_data)
        data_cards = _generate_data_cards(extracted_data)
        insights = _generate_insights(extracted_data)
        suggestions = _generate_suggestions(current_phase, extracted_data)
        progress_update = _calculate_progress(current_phase, extracted_data)

        # Wire agent's suggested questions to response (Phase 1.2)
        if hasattr(agent, 'context') and hasattr(agent.context, 'suggested_questions'):
            suggested_questions = agent.context.suggested_questions[:2]  # Take top 2
            if suggested_questions and ai_response:
                # Append suggested questions to the response
                questions_text = "\n\n💡 **You might also want to share:**\n"
                for q in suggested_questions:
                    questions_text += f"• {q}\n"
                ai_response += questions_text

        # Save updated session (database or in-memory)
        # Prune history before saving to prevent storage bloat
        try:
            session_history = get_session_attr(unified_session, "conversation_history", [])

            # Apply pruning if history is getting long
            if HISTORY_MANAGEMENT_AVAILABLE and len(session_history) > SLIDING_WINDOW_SIZE * 3:
                pruned_history = prune_conversation_history(session_history, max_turns=SLIDING_WINDOW_SIZE * 2)
                if isinstance(unified_session, dict):
                    unified_session["conversation_history"] = pruned_history
                else:
                    unified_session.conversation_history = pruned_history
                session_history = pruned_history
                logger.info(f"[{request_id}] Pruned stored history to {len(pruned_history)} messages")

            if persistence and not use_memory_fallback:
                persistence.save_unified_session(unified_session)
                logger.info(f"[{request_id}] Session {request.session_id} saved to database")
            else:
                # Save to in-memory fallback
                _chat_sessions[request.session_id] = {
                    "metadata": metadata,
                    "extracted_data": extracted_data,
                    "conversation_history": session_history
                }
                logger.info(f"[{request_id}] Session {request.session_id} saved to in-memory storage")
        except Exception as e:
            logger.error(f"[{request_id}] Failed to save session: {str(e)}")
            # Continue - don't fail the request

        logger.info(f"[{request_id}] Chat response generated successfully", extra={
            "entities_extracted": len(extracted_entities),
            "current_phase": current_phase
        })

        return ChatMessageResponse(
            response=ai_response,
            quick_actions=quick_actions,
            data_cards=data_cards,
            insights=insights,
            suggestions=suggestions,
            extracted_entities=extracted_entities,
            progress_update=progress_update
        )

    except HTTPException:
        raise  # Re-raise formatted exceptions

    except Exception as e:
        logger.error(f"[{request_id}] Unexpected error in chat processing", extra={
            "error": str(e),
            "traceback": traceback.format_exc()
        })

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_type": "UnexpectedError",
                "error_message": "Failed to process chat message",
                "user_message": "I'm having trouble processing that. Could you try rephrasing or start a new conversation?",
                "request_id": request_id
            }
        )


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    session_id: str = Form(...)
):
    """
    Process uploaded document (W-2, 1099, etc.) mid-conversation - IMPROVED.

    Enhancements:
    - Better file validation
    - OCR error recovery
    - Temp file cleanup guarantee
    - Size limits
    - Mime type validation
    """
    request_id = f"UPLOAD-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    try:
        logger.info(f"[{request_id}] Document upload started", extra={
            "session_id": session_id,
            "filename": file.filename,
            "content_type": file.content_type
        })

        # Load session from database or in-memory fallback
        unified_session = None
        use_memory_fallback = persistence is None

        if not use_memory_fallback:
            try:
                unified_session = persistence.load_unified_session(session_id)
            except Exception as e:
                logger.warning(f"[{request_id}] Database load failed, using in-memory fallback: {e}")
                use_memory_fallback = True

        # Try in-memory fallback
        if unified_session is None and session_id in _chat_sessions:
            unified_session = _chat_sessions[session_id]

        if not unified_session:
            logger.warning(f"[{request_id}] Upload to non-existent session: {session_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error_type": "SessionNotFound",
                    "user_message": "Your session has expired. Please start a new conversation.",
                    "request_id": request_id
                }
            )

        # Validate file type
        allowed_types = [
            "application/pdf",
            "image/png",
            "image/jpeg",
            "image/jpg",
            "image/heic"
        ]

        if file.content_type not in allowed_types:
            logger.warning(f"[{request_id}] Invalid file type: {file.content_type}")
            return UploadResponse(
                success=False,
                response=f"File type '{file.content_type}' is not supported. Please upload a PDF or image (PNG, JPG, HEIC).",
                quick_actions=[
                    QuickAction(label="Try another file", value="upload_retry")
                ]
            )

        # Read file with size limit (10MB)
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        contents = await file.read()

        if len(contents) > MAX_FILE_SIZE:
            logger.warning(f"[{request_id}] File too large: {len(contents)} bytes")
            return UploadResponse(
                success=False,
                response="File is too large (max 10MB). Please upload a smaller file or compress it.",
                quick_actions=[
                    QuickAction(label="Try another file", value="upload_retry")
                ]
            )

        # Process with OCR
        extracted_data = {}
        document_type = "unknown"
        temp_path = None

        try:
            # Create temp file
            temp_fd, temp_path = tempfile.mkstemp(suffix=os.path.splitext(file.filename)[1])

            try:
                with os.fdopen(temp_fd, 'wb') as temp_file:
                    temp_file.write(contents)

                # Import and process
                from services.ocr import DocumentProcessor
                doc_processor = DocumentProcessor()

                result = doc_processor.process_bytes(
                    data=contents,
                    mime_type=file.content_type or "application/pdf",
                    original_filename=file.filename,
                    document_type=None,  # Auto-detect
                    tax_year=None,  # Auto-detect
                )

                # Extract data
                for field in result.extracted_fields:
                    # Sanitize extracted values
                    if isinstance(field.value, str):
                        extracted_data[field.field_name] = sanitize_string(field.value)
                    else:
                        extracted_data[field.field_name] = field.value

                document_type = result.document_type or "unknown"
                success = result.status == "success"

                logger.info(f"[{request_id}] OCR processing complete", extra={
                    "document_type": document_type,
                    "fields_extracted": len(extracted_data),
                    "success": success
                })

            finally:
                # Always clean up temp file
                try:
                    if temp_path and os.path.exists(temp_path):
                        os.unlink(temp_path)
                except Exception as cleanup_error:
                    logger.warning(f"[{request_id}] Temp file cleanup failed: {str(cleanup_error)}")

        except ImportError:
            logger.error(f"[{request_id}] OCR service not available")
            return UploadResponse(
                success=False,
                response="Document processing service is temporarily unavailable. Please type the information manually or try again later.",
                quick_actions=[
                    QuickAction(label="Type manually", value="type_manual")
                ]
            )

        except Exception as ocr_error:
            logger.error(f"[{request_id}] OCR processing failed: {str(ocr_error)}", exc_info=True)
            return UploadResponse(
                success=False,
                response="I had trouble reading that document. The image might be blurry or the format unclear. Could you try uploading a clearer image or typing the information?",
                quick_actions=[
                    QuickAction(label="Try another file", value="upload_retry"),
                    QuickAction(label="Type manually", value="type_manual")
                ]
            )

        # Check if we extracted any data
        if not extracted_data:
            logger.warning(f"[{request_id}] No data extracted from document")
            return UploadResponse(
                success=False,
                response="I couldn't find any tax information in that document. Please make sure it's a clear image of a W-2, 1099, or similar tax document.",
                quick_actions=[
                    QuickAction(label="Try another file", value="upload_retry"),
                    QuickAction(label="Type manually", value="type_manual")
                ]
            )

        # Update session data (works with both dict and object)
        if isinstance(unified_session, dict):
            unified_session.setdefault("extracted_data", {}).update(extracted_data)
        else:
            unified_session.extracted_data.update(extracted_data)

        # Phase 1.6: Document-conversation integration - add system message
        fields_summary = ", ".join([f"{k}: {v}" for k, v in list(extracted_data.items())[:5]])
        doc_system_message = {
            "role": "system",
            "content": f"User uploaded {document_type.upper()}. Extracted: {fields_summary}",
            "timestamp": datetime.now().isoformat(),
            "is_document_context": True
        }

        # Add document context to conversation history
        if isinstance(unified_session, dict):
            unified_session.setdefault("conversation_history", []).append(doc_system_message)
        elif hasattr(unified_session, 'add_message'):
            unified_session.add_message("system", doc_system_message["content"])

        # Save updated session
        try:
            if persistence and not use_memory_fallback:
                persistence.save_unified_session(unified_session)
                logger.info(f"[{request_id}] Session {session_id} saved to database after document upload")
            else:
                # Save to in-memory fallback
                if isinstance(unified_session, dict):
                    _chat_sessions[session_id] = unified_session
                else:
                    _chat_sessions[session_id] = {
                        "metadata": getattr(unified_session, "metadata", {}),
                        "extracted_data": getattr(unified_session, "extracted_data", {}),
                        "conversation_history": getattr(unified_session, "conversation_history", [])
                    }
                logger.info(f"[{request_id}] Session {session_id} saved to in-memory storage after document upload")
        except Exception as e:
            logger.error(f"[{request_id}] Failed to save session: {str(e)}")
            # Continue - don't fail the request

        # Create extracted entities list
        extracted_entities = [
            ExtractedEntity(
                entity_type=key,
                value=value,
                confidence="high",
                source="ocr"
            )
            for key, value in extracted_data.items()
        ]

        # Generate conversational response
        response = _generate_document_response(document_type, extracted_data)

        # Generate data card
        data_cards = [
            DataCard(
                icon="📄",
                title=f"From your {document_type.upper()}",
                items=[
                    {"label": key.replace("_", " ").title(), "value": str(value)}
                    for key, value in list(extracted_data.items())[:10]  # Limit to 10 items
                ]
            )
        ]

        # Quick actions
        quick_actions = [
            QuickAction(label="✓ Looks good", value="confirm_data"),
            QuickAction(label="Upload another", value="upload_more"),
            QuickAction(label="Edit info", value="edit_data")
        ]

        logger.info(f"[{request_id}] Document upload successful")

        return UploadResponse(
            success=True,
            response=response,
            quick_actions=quick_actions,
            data_cards=data_cards,
            extracted_entities=extracted_entities
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"[{request_id}] Document upload error: {str(e)}", exc_info=True)
        return UploadResponse(
            success=False,
            response="There was an error processing your document. Please try again or type the information manually.",
            quick_actions=[
                QuickAction(label="Try again", value="upload_retry"),
                QuickAction(label="Type manually", value="type_manual")
            ]
        )


@router.post("/analyze-document", response_model=AnalyzeDocumentResponse)
async def analyze_document(
    file: UploadFile = File(...),
    session_id: str = Form(...)
):
    """
    Analyze uploaded document for intelligent advisor.

    Returns structured response with:
    - ai_response: Conversational message about the document
    - extracted_data: Tax data extracted from document
    - completion_percentage: Updated progress
    - extracted_summary: Summary for UI stats display
    - quick_actions: Suggested next actions
    """
    request_id = f"ANALYZE-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    try:
        logger.info(f"[{request_id}] Document analysis started", extra={
            "session_id": session_id,
            "filename": file.filename,
            "content_type": file.content_type
        })

        # Validate file type
        allowed_types = [
            "application/pdf",
            "image/png",
            "image/jpeg",
            "image/jpg",
            "image/heic"
        ]

        if file.content_type not in allowed_types:
            logger.warning(f"[{request_id}] Invalid file type: {file.content_type}")
            return AnalyzeDocumentResponse(
                ai_response=f"I can't read that file type ({file.content_type}). Please upload a PDF or image (PNG, JPG) of your tax document.",
                quick_actions=[
                    QuickAction(label="Try another file", value="upload_retry"),
                    QuickAction(label="Enter manually", value="type_manual")
                ],
                extracted_data={},
                completion_percentage=0,
                extracted_summary={}
            )

        # Read file with size limit (50MB)
        MAX_FILE_SIZE = 50 * 1024 * 1024
        contents = await file.read()

        if len(contents) > MAX_FILE_SIZE:
            logger.warning(f"[{request_id}] File too large: {len(contents)} bytes")
            return AnalyzeDocumentResponse(
                ai_response="That file is too large (max 50MB). Please upload a smaller file or compress it first.",
                quick_actions=[
                    QuickAction(label="Try smaller file", value="upload_retry")
                ],
                extracted_data={},
                completion_percentage=0,
                extracted_summary={}
            )

        # Process document with OCR
        extracted_data = {}
        document_type = "unknown"
        ocr_confidence = 0.0

        try:
            from services.ocr import DocumentProcessor
            doc_processor = DocumentProcessor()

            result = doc_processor.process_bytes(
                data=contents,
                mime_type=file.content_type or "application/pdf",
                original_filename=file.filename,
                document_type=None,  # Auto-detect
                tax_year=None  # Auto-detect
            )

            # Extract data from result
            for field in result.extracted_fields:
                field_name = getattr(field, 'field_name', getattr(field, 'name', str(field)))
                field_value = getattr(field, 'value', getattr(field, 'normalized_value', None))
                if field_value is not None:
                    # Sanitize string values
                    if isinstance(field_value, str):
                        extracted_data[field_name] = sanitize_string(field_value)
                    else:
                        extracted_data[field_name] = field_value

            document_type = result.document_type or "unknown"
            ocr_confidence = getattr(result, 'ocr_confidence', 0.85)

            logger.info(f"[{request_id}] OCR complete", extra={
                "document_type": document_type,
                "fields_extracted": len(extracted_data),
                "confidence": ocr_confidence
            })

        except ImportError:
            logger.error(f"[{request_id}] OCR service not available")
            return AnalyzeDocumentResponse(
                ai_response="Document processing is temporarily unavailable. Please enter your information manually.",
                quick_actions=[
                    QuickAction(label="Enter W-2 info", value="income_wages"),
                    QuickAction(label="Enter 1099 info", value="income_1099")
                ],
                extracted_data={},
                completion_percentage=0,
                extracted_summary={}
            )

        except Exception as ocr_error:
            logger.error(f"[{request_id}] OCR failed: {str(ocr_error)}", exc_info=True)
            return AnalyzeDocumentResponse(
                ai_response="I had trouble reading that document. The image might be blurry or the format unclear. Could you try a clearer photo or enter the information manually?",
                quick_actions=[
                    QuickAction(label="Try another photo", value="upload_retry"),
                    QuickAction(label="Enter manually", value="type_manual")
                ],
                extracted_data={},
                completion_percentage=0,
                extracted_summary={}
            )

        # Generate AI response based on document type
        ai_response = _generate_analyze_response(document_type, extracted_data, ocr_confidence)

        # Calculate completion percentage based on extracted data
        completion_percentage = _calculate_completion_percentage(extracted_data)

        # Generate summary for stats display
        extracted_summary = _generate_extracted_summary(document_type, extracted_data)

        # Generate quick actions based on what was extracted
        quick_actions = _generate_post_upload_actions(document_type, extracted_data)

        # Update session with extracted data
        try:
            if persistence:
                session = persistence.load_unified_session(session_id)
                if session:
                    if hasattr(session, 'extracted_data'):
                        session.extracted_data.update(extracted_data)
                    persistence.save_unified_session(session)
            elif session_id in _chat_sessions:
                _chat_sessions[session_id].setdefault("extracted_data", {}).update(extracted_data)

            # Phase 1.6: Document-conversation integration
            # Append system message to conversation_history about the document upload
            fields_summary = ", ".join([f"{k}: {v}" for k, v in list(extracted_data.items())[:5]])
            doc_system_message = {
                "role": "system",
                "content": f"User uploaded {document_type.upper()}. Extracted: {fields_summary}",
                "timestamp": datetime.now().isoformat(),
                "is_document_context": True
            }

            # Add to session conversation history
            if persistence and session:
                if hasattr(session, 'add_message'):
                    session.add_message("system", doc_system_message["content"])
                    persistence.save_unified_session(session)
            elif session_id in _chat_sessions:
                _chat_sessions[session_id].setdefault("conversation_history", []).append(doc_system_message)

        except Exception as save_error:
            logger.warning(f"[{request_id}] Failed to save to session: {save_error}")

        logger.info(f"[{request_id}] Document analysis complete", extra={
            "document_type": document_type,
            "fields": len(extracted_data),
            "completion": completion_percentage
        })

        return AnalyzeDocumentResponse(
            ai_response=ai_response,
            quick_actions=quick_actions,
            extracted_data=extracted_data,
            completion_percentage=completion_percentage,
            extracted_summary=extracted_summary
        )

    except Exception as e:
        logger.error(f"[{request_id}] Document analysis error: {str(e)}", exc_info=True)
        return AnalyzeDocumentResponse(
            ai_response="Something went wrong while analyzing your document. Please try again or enter the information manually.",
            quick_actions=[
                QuickAction(label="Try again", value="upload_retry"),
                QuickAction(label="Enter manually", value="type_manual")
            ],
            extracted_data={},
            completion_percentage=0,
            extracted_summary={}
        )


def _generate_analyze_response(document_type: str, extracted_data: Dict[str, Any], confidence: float) -> str:
    """Generate conversational AI response for document analysis"""
    confidence_phrase = "clearly" if confidence > 0.9 else "I think I" if confidence > 0.7 else "I'm having some trouble but I"

    if document_type == "w2":
        employer = extracted_data.get("employer_name", extracted_data.get("employer", "your employer"))
        wages = extracted_data.get("w2_wages", extracted_data.get("wages", 0))
        withheld = extracted_data.get("federal_withheld", extracted_data.get("federal_tax_withheld", 0))

        try:
            wages_fmt = f"${float(wages):,.2f}" if wages else "your wages"
            withheld_fmt = f"${float(withheld):,.2f}" if withheld else "federal tax withheld"
        except (ValueError, TypeError):
            wages_fmt = str(wages) if wages else "your wages"
            withheld_fmt = str(withheld) if withheld else "federal tax withheld"

        return f"I {confidence_phrase} read your W-2 from {employer}. You earned {wages_fmt} with {withheld_fmt} in federal taxes withheld. Does this look correct?"

    elif document_type in ["1099-int", "1099_int"]:
        interest = extracted_data.get("interest_income", extracted_data.get("interest", 0))
        payer = extracted_data.get("payer_name", "your bank")
        try:
            interest_fmt = f"${float(interest):,.2f}" if interest else "interest income"
        except (ValueError, TypeError):
            interest_fmt = str(interest)
        return f"I found a 1099-INT from {payer} showing {interest_fmt} in interest income. Is this accurate?"

    elif document_type in ["1099-div", "1099_div"]:
        dividends = extracted_data.get("dividends", extracted_data.get("ordinary_dividends", 0))
        try:
            div_fmt = f"${float(dividends):,.2f}" if dividends else "dividend income"
        except (ValueError, TypeError):
            div_fmt = str(dividends)
        return f"I read your 1099-DIV showing {div_fmt} in dividends. Does this match your records?"

    elif document_type in ["1099-nec", "1099_nec", "1099-misc", "1099_misc"]:
        income = extracted_data.get("nonemployee_compensation", extracted_data.get("misc_income", 0))
        try:
            income_fmt = f"${float(income):,.2f}" if income else "self-employment income"
        except (ValueError, TypeError):
            income_fmt = str(income)
        return f"I found {income_fmt} in self-employment/contractor income. This will be reported on Schedule C. Is this correct?"

    elif document_type in ["1098", "1098-e"]:
        interest = extracted_data.get("mortgage_interest", extracted_data.get("student_loan_interest", 0))
        try:
            interest_fmt = f"${float(interest):,.2f}" if interest else "deductible interest"
        except (ValueError, TypeError):
            interest_fmt = str(interest)
        return f"Great news! I found {interest_fmt} in deductible interest. This can help reduce your taxes!"

    else:
        field_count = len(extracted_data)
        if field_count > 0:
            return f"I extracted {field_count} fields from your document. Please review the information below to make sure it's correct."
        else:
            return "I had trouble reading this document. Could you try uploading a clearer image, or enter the information manually?"


def _calculate_completion_percentage(extracted_data: Dict[str, Any]) -> int:
    """Calculate tax return completion percentage based on extracted data"""
    # Weight different data categories
    weights = {
        'personal': 20,  # name, ssn, filing_status
        'income': 40,    # wages, 1099s
        'deductions': 25, # mortgage, charity, etc.
        'other': 15      # dependents, bank info
    }

    score = 0

    # Personal info (20%)
    personal_fields = ['first_name', 'last_name', 'ssn', 'filing_status', 'address']
    personal_found = sum(1 for f in personal_fields if extracted_data.get(f))
    score += (personal_found / len(personal_fields)) * weights['personal']

    # Income (40%)
    income_fields = ['w2_wages', 'wages', 'interest_income', 'dividend_income',
                     'business_income', '1099_income', 'federal_withheld']
    income_found = sum(1 for f in income_fields if extracted_data.get(f))
    if income_found > 0:
        score += min((income_found / 3) * weights['income'], weights['income'])

    # Deductions (25%)
    deduction_fields = ['mortgage_interest', 'property_tax', 'charitable_contributions',
                        'medical_expenses', 'state_tax', 'student_loan_interest']
    deduction_found = sum(1 for f in deduction_fields if extracted_data.get(f))
    if deduction_found > 0:
        score += min((deduction_found / 2) * weights['deductions'], weights['deductions'])

    # Other (15%)
    other_fields = ['dependents', 'bank_account', 'employer_name', 'payer_name']
    other_found = sum(1 for f in other_fields if extracted_data.get(f))
    if other_found > 0:
        score += min((other_found / 2) * weights['other'], weights['other'])

    return min(int(score), 95)  # Cap at 95% - final review always needed


def _generate_extracted_summary(document_type: str, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate summary statistics for UI display"""
    summary = {
        "document_type": document_type.upper().replace("_", "-"),
        "fields_extracted": len(extracted_data),
        "key_values": {}
    }

    # Add key financial values to summary
    key_fields = [
        ("w2_wages", "Wages"),
        ("wages", "Wages"),
        ("federal_withheld", "Fed Withheld"),
        ("interest_income", "Interest"),
        ("dividend_income", "Dividends"),
        ("mortgage_interest", "Mortgage Int"),
        ("business_income", "Business Income"),
        ("employer_name", "Employer"),
    ]

    for field, label in key_fields:
        if field in extracted_data and extracted_data[field]:
            value = extracted_data[field]
            try:
                if isinstance(value, (int, float)) or (isinstance(value, str) and value.replace('.', '').replace(',', '').isdigit()):
                    summary["key_values"][label] = f"${float(str(value).replace(',', '')):,.2f}"
                else:
                    summary["key_values"][label] = str(value)
            except (ValueError, TypeError):
                summary["key_values"][label] = str(value)

    return summary


def _generate_post_upload_actions(document_type: str, extracted_data: Dict[str, Any]) -> List[QuickAction]:
    """Generate quick actions after document upload"""
    actions = [
        QuickAction(label="✓ Looks correct", value="confirm_document")
    ]

    if document_type == "w2":
        actions.extend([
            QuickAction(label="Upload another W-2", value="upload_w2"),
            QuickAction(label="Add 1099 income", value="income_1099")
        ])
    elif "1099" in document_type:
        actions.extend([
            QuickAction(label="Upload another 1099", value="upload_1099"),
            QuickAction(label="Done with income", value="income_complete")
        ])
    elif "1098" in document_type:
        actions.extend([
            QuickAction(label="More deductions", value="deductions_more"),
            QuickAction(label="Done with deductions", value="deductions_complete")
        ])
    else:
        actions.extend([
            QuickAction(label="Upload another doc", value="upload_more"),
            QuickAction(label="Continue", value="continue_flow")
        ])

    return actions[:4]  # Limit to 4 actions


# ============================================================================
# Session Management - IMPROVED
# ============================================================================

def _cleanup_old_sessions(force: bool = False):
    """
    Clean up expired sessions from database and in-memory storage.

    Args:
        force: Not used anymore (database handles expiry automatically)
    """
    try:
        # Clean up database sessions if available
        if persistence:
            deleted_count = persistence.cleanup_expired_sessions()
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired sessions from database")

        # Also clean up old in-memory sessions (older than 1 hour)
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=1)
        expired_keys = []
        for session_id, session_data in _chat_sessions.items():
            if isinstance(session_data, dict):
                history = session_data.get("conversation_history", [])
                if history:
                    last_msg = history[-1]
                    if isinstance(last_msg, dict) and "timestamp" in last_msg:
                        try:
                            msg_time = datetime.fromisoformat(last_msg["timestamp"])
                            if msg_time < cutoff:
                                expired_keys.append(session_id)
                        except (ValueError, TypeError):
                            pass
        for key in expired_keys:
            del _chat_sessions[key]
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired in-memory sessions")

    except Exception as e:
        logger.error(f"Session cleanup failed: {str(e)}")


def _create_fallback_response(user_message: str) -> ChatMessageResponse:
    """Create a graceful fallback response when agent fails."""
    return ChatMessageResponse(
        response="I'm having a bit of trouble understanding that. Could you rephrase your question or try one of these common topics?",
        quick_actions=[
            QuickAction(label="Personal info", value="I need help with my personal information"),
            QuickAction(label="Income", value="I have questions about my income"),
            QuickAction(label="Deductions", value="What deductions can I take?")
        ],
        suggestions=[
            Suggestion(text="Start over", value="Let's start from the beginning"),
            Suggestion(text="Get help", value="I need help")
        ]
    )


def _create_simple_response(user_message: str) -> ChatMessageResponse:
    """Create a simple rule-based response when AI is not available."""
    message_lower = user_message.lower()

    # Simple keyword matching for common questions
    if any(word in message_lower for word in ["hello", "hi", "hey", "help"]):
        response = "Hello! I'm your tax assistant. I can help you prepare your tax return. Let's start by gathering your personal information. What is your full name?"
    elif any(word in message_lower for word in ["name", "my name"]):
        response = "Great! Please tell me your full name (first and last name)."
    elif any(word in message_lower for word in ["single", "married", "filing status"]):
        response = "Got it! What is your filing status? (Single, Married Filing Jointly, Married Filing Separately, Head of Household, or Qualifying Widow(er))"
    elif any(word in message_lower for word in ["w-2", "w2", "wages", "salary", "income"]):
        response = "Tell me about your income. How much did you earn from wages (W-2) this year? You can also upload your W-2 document."
    elif any(word in message_lower for word in ["deduction", "mortgage", "charity", "donate"]):
        response = "Deductions can reduce your taxable income. Would you like to take the standard deduction or itemize your deductions? Common itemized deductions include mortgage interest, property taxes, and charitable contributions."
    elif any(word in message_lower for word in ["refund", "owe", "tax"]):
        response = "To calculate your tax or refund, I'll need more information about your income and deductions. Let's start with your W-2 wages."
    else:
        response = "I'm here to help you with your taxes. You can tell me about your income, upload tax documents like W-2s, or ask about deductions. What would you like to do?"

    return ChatMessageResponse(
        response=response,
        quick_actions=[
            QuickAction(label="📄 Upload W-2", value="upload_w2"),
            QuickAction(label="Single", value="I'm filing as Single"),
            QuickAction(label="Married", value="I'm filing Married Filing Jointly")
        ],
        suggestions=[
            Suggestion(text="My name is...", value="My name is "),
            Suggestion(text="I made $X from my job", value="I made $ in wages")
        ]
    )


# ============================================================================
# Helper Functions (Same as original but with better error handling)
# ============================================================================

def _determine_phase(extracted_data: Dict[str, Any]) -> str:
    """Determine current phase of tax preparation based on quality scoring"""
    phase_result = _determine_phase_with_quality(extracted_data)
    return phase_result["phase"]


def _determine_phase_with_quality(extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Determine current phase with quality scoring.

    Returns phase name + quality metrics for UI feedback.
    Requires 75% quality threshold before advancing phases.
    """
    # Import validation helpers
    try:
        from web.validation_helpers import validate_ssn, validate_currency, validate_name
        validators_available = True
    except ImportError:
        validators_available = False

    QUALITY_THRESHOLD = 75  # Require 75% quality to advance

    # Phase 1: Personal Info - validate name, ssn, filing_status
    personal_quality = _calculate_personal_info_quality(extracted_data, validators_available)
    if personal_quality["score"] < QUALITY_THRESHOLD:
        return {
            "phase": "personal_info",
            "quality": personal_quality,
            "message": personal_quality.get("message", "Please complete your personal information")
        }

    # Phase 2: Income - validate wages, withholding
    income_quality = _calculate_income_quality(extracted_data, validators_available)
    if income_quality["score"] < QUALITY_THRESHOLD:
        return {
            "phase": "income",
            "quality": income_quality,
            "message": income_quality.get("message", "Please add your income information")
        }

    # Phase 3: Deductions
    deductions_quality = _calculate_deductions_quality(extracted_data)
    if not extracted_data.get("deductions_confirmed") and deductions_quality["score"] < QUALITY_THRESHOLD:
        return {
            "phase": "deductions",
            "quality": deductions_quality,
            "message": "Review and confirm your deductions"
        }

    # Phase 4: Review
    if not extracted_data.get("review_confirmed"):
        return {
            "phase": "review",
            "quality": {"score": 90, "fields": {}},
            "message": "Please review all your information"
        }

    return {
        "phase": "ready_to_file",
        "quality": {"score": 100, "fields": {}},
        "message": "Ready to file!"
    }


def _calculate_personal_info_quality(extracted_data: Dict[str, Any], validators_available: bool) -> Dict[str, Any]:
    """Calculate quality score for personal info phase (0-100)"""
    fields = {}
    total_weight = 0
    weighted_score = 0

    # First name (weight: 20)
    first_name = extracted_data.get("first_name", "")
    if first_name:
        if validators_available:
            try:
                from web.validation_helpers import validate_name
                is_valid, _ = validate_name(first_name, "First name")
                fields["first_name"] = {"value": first_name, "valid": is_valid, "score": 100 if is_valid else 50}
            except:
                fields["first_name"] = {"value": first_name, "valid": True, "score": 100}
        else:
            fields["first_name"] = {"value": first_name, "valid": len(first_name) >= 2, "score": 100 if len(first_name) >= 2 else 50}
        weighted_score += fields["first_name"]["score"] * 20
    else:
        fields["first_name"] = {"value": None, "valid": False, "score": 0}
    total_weight += 20

    # Last name (weight: 20)
    last_name = extracted_data.get("last_name", "")
    if last_name:
        fields["last_name"] = {"value": last_name, "valid": len(last_name) >= 2, "score": 100 if len(last_name) >= 2 else 50}
        weighted_score += fields["last_name"]["score"] * 20
    else:
        fields["last_name"] = {"value": None, "valid": False, "score": 0}
    total_weight += 20

    # SSN (weight: 35)
    ssn = extracted_data.get("ssn", "")
    if ssn:
        if validators_available:
            try:
                from web.validation_helpers import validate_ssn
                is_valid, error = validate_ssn(ssn)
                fields["ssn"] = {"value": f"***-**-{ssn[-4:]}" if len(ssn) >= 4 else "***", "valid": is_valid, "score": 100 if is_valid else 30}
            except:
                fields["ssn"] = {"value": "***", "valid": True, "score": 80}
        else:
            fields["ssn"] = {"value": "***", "valid": len(ssn.replace("-", "")) == 9, "score": 100 if len(ssn.replace("-", "")) == 9 else 30}
        weighted_score += fields["ssn"]["score"] * 35
    else:
        fields["ssn"] = {"value": None, "valid": False, "score": 0}
    total_weight += 35

    # Filing status (weight: 25)
    filing_status = extracted_data.get("filing_status", "")
    valid_statuses = ["single", "married_filing_jointly", "married_filing_separately", "head_of_household", "qualifying_widow"]
    if filing_status:
        is_valid = filing_status.lower().replace(" ", "_") in valid_statuses or any(s in filing_status.lower() for s in ["single", "married", "head", "widow"])
        fields["filing_status"] = {"value": filing_status, "valid": is_valid, "score": 100 if is_valid else 50}
        weighted_score += fields["filing_status"]["score"] * 25
    else:
        fields["filing_status"] = {"value": None, "valid": False, "score": 0}
    total_weight += 25

    final_score = int(weighted_score / total_weight) if total_weight > 0 else 0

    # Generate helpful message
    missing = [k for k, v in fields.items() if not v["valid"]]
    message = None
    if missing:
        message = f"Please provide: {', '.join(f.replace('_', ' ') for f in missing)}"

    return {"score": final_score, "fields": fields, "message": message}


def _calculate_income_quality(extracted_data: Dict[str, Any], validators_available: bool) -> Dict[str, Any]:
    """Calculate quality score for income phase (0-100)"""
    fields = {}
    total_weight = 0
    weighted_score = 0

    # W2 Wages (weight: 50)
    w2_wages = extracted_data.get("w2_wages") or extracted_data.get("wages")
    if w2_wages is not None:
        try:
            wages_val = float(str(w2_wages).replace(",", "").replace("$", ""))
            is_valid = wages_val >= 0 and wages_val < 10000000  # Reasonable range
            fields["w2_wages"] = {"value": wages_val, "valid": is_valid, "score": 100 if is_valid else 50}
            weighted_score += fields["w2_wages"]["score"] * 50
        except (ValueError, TypeError):
            fields["w2_wages"] = {"value": w2_wages, "valid": False, "score": 30}
            weighted_score += 30 * 50
    else:
        # Check for 1099 income as alternative
        income_1099 = extracted_data.get("income_1099") or extracted_data.get("self_employment_income")
        if income_1099:
            fields["w2_wages"] = {"value": None, "valid": True, "score": 80}  # 1099 is acceptable
            weighted_score += 80 * 50
        else:
            fields["w2_wages"] = {"value": None, "valid": False, "score": 0}
    total_weight += 50

    # Federal Withheld (weight: 30)
    fed_withheld = extracted_data.get("federal_withheld") or extracted_data.get("federal_tax_withheld")
    if fed_withheld is not None:
        try:
            withheld_val = float(str(fed_withheld).replace(",", "").replace("$", ""))
            is_valid = withheld_val >= 0
            fields["federal_withheld"] = {"value": withheld_val, "valid": is_valid, "score": 100 if is_valid else 50}
            weighted_score += fields["federal_withheld"]["score"] * 30
        except (ValueError, TypeError):
            fields["federal_withheld"] = {"value": fed_withheld, "valid": False, "score": 30}
            weighted_score += 30 * 30
    else:
        fields["federal_withheld"] = {"value": None, "valid": False, "score": 0}
    total_weight += 30

    # Employer info (weight: 20) - nice to have
    employer = extracted_data.get("employer_name") or extracted_data.get("employer")
    if employer:
        fields["employer_name"] = {"value": employer, "valid": True, "score": 100}
        weighted_score += 100 * 20
    else:
        fields["employer_name"] = {"value": None, "valid": False, "score": 0}
    total_weight += 20

    final_score = int(weighted_score / total_weight) if total_weight > 0 else 0

    missing = [k for k, v in fields.items() if not v["valid"] and k != "employer_name"]
    message = None
    if missing:
        message = f"Please provide: {', '.join(f.replace('_', ' ') for f in missing)}"

    return {"score": final_score, "fields": fields, "message": message}


def _calculate_deductions_quality(extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate quality score for deductions phase (0-100)"""
    fields = {}

    # Check if user has chosen standard vs itemized
    if extracted_data.get("deduction_type") == "standard":
        return {"score": 100, "fields": {"deduction_type": {"value": "standard", "valid": True, "score": 100}}}

    # Check for common itemized deductions
    deductions_found = 0
    deduction_fields = ["mortgage_interest", "property_taxes", "charitable_contributions",
                        "medical_expenses", "state_tax", "student_loan_interest"]

    for field in deduction_fields:
        val = extracted_data.get(field)
        if val is not None:
            deductions_found += 1
            fields[field] = {"value": val, "valid": True, "score": 100}

    # If no deductions specified, assume standard deduction (which is fine)
    if deductions_found == 0:
        return {"score": 75, "fields": {}, "message": "Using standard deduction by default"}

    return {"score": min(100, 60 + deductions_found * 10), "fields": fields}


def _generate_quick_actions(phase: str, extracted_data: Dict[str, Any]) -> List[QuickAction]:
    """Generate contextual quick action buttons"""
    actions = []

    if phase == "personal_info":
        if not extracted_data.get("filing_status"):
            actions.extend([
                QuickAction(label="Single", value="I'm filing as Single"),
                QuickAction(label="Married", value="I'm filing Married Filing Jointly"),
                QuickAction(label="Head of Household", value="I'm filing as Head of Household")
            ])

    elif phase == "income":
        actions.extend([
            QuickAction(label="📄 Upload W-2", value="upload_w2"),
            QuickAction(label="No other income", value="I have no other income sources")
        ])

    elif phase == "deductions":
        actions.extend([
            QuickAction(label="Standard deduction", value="I want to take the standard deduction"),
            QuickAction(label="I have deductions", value="I have mortgage interest and property taxes")
        ])

    elif phase == "review":
        actions.extend([
            QuickAction(label="✓ Everything looks good", value="Everything looks correct, let's file"),
            QuickAction(label="Edit something", value="I need to change something")
        ])

    return actions[:3]


def _generate_data_cards(extracted_data: Dict[str, Any]) -> List[DataCard]:
    """Generate data visualization cards"""
    cards = []

    # Personal info card
    if extracted_data.get("first_name"):
        personal_items = []
        if extracted_data.get("first_name"):
            personal_items.append({"label": "Name", "value": f"{extracted_data.get('first_name')} {extracted_data.get('last_name', '')}"})
        if extracted_data.get("filing_status"):
            personal_items.append({"label": "Filing Status", "value": extracted_data.get("filing_status")})
        if extracted_data.get("ssn"):
            personal_items.append({"label": "SSN", "value": f"***-**-{extracted_data.get('ssn', '')[-4:]}"})

        if personal_items:
            cards.append(DataCard(icon="👤", title="Personal Information", items=personal_items))

    # Income card
    if extracted_data.get("w2_wages"):
        income_items = [{"label": "W-2 Wages", "value": f"${float(extracted_data.get('w2_wages')):,.2f}"}]
        if extracted_data.get("employer_name"):
            income_items.append({"label": "Employer", "value": str(extracted_data.get("employer_name"))})
        if extracted_data.get("federal_withheld"):
            income_items.append({"label": "Fed Withheld", "value": f"${float(extracted_data.get('federal_withheld')):,.2f}"})

        cards.append(DataCard(icon="💰", title="Income", items=income_items))

    return cards


def _generate_insights(extracted_data: Dict[str, Any]) -> List[Insight]:
    """Generate AI insights based on extracted data"""
    insights = []

    # Estimate refund/tax
    if extracted_data.get("w2_wages") and extracted_data.get("federal_withheld"):
        try:
            wages = float(extracted_data.get("w2_wages", 0))
            withheld = float(extracted_data.get("federal_withheld", 0))

            estimated_tax = wages * 0.12
            refund = withheld - estimated_tax

            if refund > 0:
                insights.append(Insight(
                    icon="💰",
                    title="Estimated Refund",
                    text=f"Based on your income, you may receive a refund of approximately ${refund:,.0f}. We'll calculate the exact amount once we have all your information."
                ))
            else:
                insights.append(Insight(
                    icon="📊",
                    title="Estimated Tax",
                    text=f"You may owe approximately ${abs(refund):,.0f}. Don't worry - we'll help you find deductions to reduce this."
                ))
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to generate refund insight: {str(e)}")

    return insights


def _generate_suggestions(phase: str, extracted_data: Dict[str, Any]) -> List[Suggestion]:
    """Generate input suggestions for current phase"""
    suggestions = []

    if phase == "personal_info":
        suggestions.extend([
            Suggestion(text="My name is...", value="My name is "),
            Suggestion(text="I'm filing as...", value="I'm filing as "),
            Suggestion(text="Upload my W-2", value="upload_w2")
        ])
    elif phase == "income":
        suggestions.extend([
            Suggestion(text="I made $X from my job", value="I made $ "),
            Suggestion(text="Upload W-2", value="upload_w2"),
            Suggestion(text="I have 1099 income", value="I have 1099 income from ")
        ])
    elif phase == "deductions":
        suggestions.extend([
            Suggestion(text="Standard deduction", value="I want to take the standard deduction"),
            Suggestion(text="I have mortgage interest", value="I paid $ in mortgage interest"),
            Suggestion(text="I made charitable donations", value="I donated $ to charity")
        ])

    return suggestions


def _calculate_progress(phase: str, extracted_data: Dict[str, Any]) -> ProgressUpdate:
    """Calculate progress through tax filing"""
    phase_map = {
        "personal_info": (0, "Personal Information"),
        "income": (1, "Income"),
        "deductions": (2, "Deductions & Credits"),
        "review": (3, "Review"),
        "ready_to_file": (4, "Ready to File")
    }

    step, name = phase_map.get(phase, (0, "Getting Started"))

    return ProgressUpdate(
        current_step=step,
        total_steps=5,
        phase_name=name
    )


def _generate_document_response(document_type: str, extracted_data: Dict[str, Any]) -> str:
    """Generate conversational response for uploaded document"""
    try:
        if document_type == "w2":
            employer = extracted_data.get("employer_name", "your employer")
            wages = float(extracted_data.get("w2_wages", 0))
            return f"Great! I've read your W-2 from {employer}. I see you earned ${wages:,.2f} last year. Does this look correct?"

        elif document_type == "1099":
            income = float(extracted_data.get("income", 0))
            return f"I've processed your 1099 form. I extracted ${income:,.2f} in income. Is this accurate?"

        elif document_type == "1098":
            interest = float(extracted_data.get("mortgage_interest", 0))
            return f"I've read your mortgage interest statement. You paid ${interest:,.2f} in mortgage interest. This is a deductible expense!"

        else:
            return "I've processed your document and extracted the information. Please review it to make sure everything looks correct."

    except (ValueError, TypeError):
        return "I've processed your document. Please review the extracted information to make sure everything looks correct."
