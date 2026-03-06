"""
Chat endpoint routes extracted from app.py.

Contains the /api/chat endpoint for the tax preparation agent chat.
"""

import os
import logging

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from security.data_sanitizer import sanitize_for_logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat"])


def _build_tax_context(session_id: str) -> str:
    """Build tax context string from session data for chat personalization."""
    if not session_id:
        return ""
    try:
        from database.session_persistence import SessionPersistence
        persistence = SessionPersistence()
        session_data = persistence.load_session_state(session_id)
        if not session_data:
            return ""

        tc = session_data.get("tax_computation") or {}
        if not tc:
            return ""

        context = (
            f"\n[Tax Context - use to personalize your answer]\n"
            f"Filing Status: {tc.get('filing_status', 'unknown')}\n"
            f"AGI: ${tc.get('agi', 0):,.0f}\n"
            f"Total Tax: ${tc.get('total_tax', 0):,.0f}\n"
            f"Effective Rate: {tc.get('effective_rate', 0):.1f}%\n"
        )

        potential_savings = tc.get("potential_savings", 0)
        if potential_savings:
            context += f"Potential Savings: ${potential_savings:,.0f}\n"

        return context
    except Exception as e:
        logger.warning(f"Could not load tax context for chat: {e}")
        return ""


def _get_app_dependencies():
    """Lazy import of app-level dependencies to avoid circular imports."""
    from web.app import (
        _get_or_create_session_agent,
        _get_persistence,
        get_secure_serializer,
        _calculator,
        _forms,
    )
    from security.secure_serializer import SerializationError
    return (
        _get_or_create_session_agent,
        _get_persistence,
        get_secure_serializer,
        _calculator,
        _forms,
        SerializationError,
    )


@router.post("/api/chat")
async def chat(request: Request, response: Response):
    from security.validation import sanitize_string

    (
        _get_or_create_session_agent,
        _get_persistence,
        get_secure_serializer,
        _calculator,
        _forms,
        SerializationError,
    ) = _get_app_dependencies()

    body = await request.json()

    # Validate and sanitize user message
    user_message_raw = body.get("message", "")
    if not isinstance(user_message_raw, str):
        return JSONResponse(
            {"error": "Invalid message format"},
            status_code=400
        )

    # Sanitize message (prevent XSS, limit length)
    user_message = sanitize_string(user_message_raw, max_length=5000, allow_newlines=True)

    # Validate action
    action_raw = body.get("action", "message")
    if not isinstance(action_raw, str):
        return JSONResponse(
            {"error": "Invalid action format"},
            status_code=400
        )

    action = sanitize_string(action_raw, max_length=50).lower()
    valid_actions = {"message", "reset", "summary", "calculate"}
    if action not in valid_actions:
        action = "message"

    session_id = request.cookies.get("tax_session_id")
    session_id, agent = _get_or_create_session_agent(session_id)
    response.set_cookie(
        "tax_session_id",
        session_id,
        httponly=True,
        samesite="lax",
        secure=os.environ.get("APP_ENVIRONMENT") == "production",
        max_age=86400
    )

    if action == "reset":
        _get_persistence().delete_session(session_id)
        session_id, agent = _get_or_create_session_agent(None)
        response.set_cookie(
            "tax_session_id",
            session_id,
            httponly=True,
            samesite="lax",
            secure=os.environ.get("APP_ENVIRONMENT") == "production",
            max_age=86400
        )
        return JSONResponse({"reply": "Session reset. " + agent.start_conversation()})

    if action == "summary":
        tax_return = agent.get_tax_return()
        if not tax_return:
            return JSONResponse({"reply": "No information collected yet."})
        if agent.is_complete():
            _calculator.calculate_complete_return(tax_return)
        return JSONResponse({"reply": _forms.generate_summary(tax_return)})

    if action == "calculate":
        tax_return = agent.get_tax_return()
        if not tax_return or not agent.is_complete():
            return JSONResponse({"reply": "Not enough information yet. Please continue answering questions."})
        _calculator.calculate_complete_return(tax_return)
        return JSONResponse({"reply": _forms.generate_summary(tax_return)})

    if not user_message or len(user_message.strip()) == 0:
        return JSONResponse({"reply": "Please type a message."})

    # Inject tax context if available
    tax_context = _build_tax_context(session_id)
    if tax_context:
        contextualized_message = f"{tax_context}\nUser question: {user_message}"
    else:
        contextualized_message = user_message

    reply = agent.process_message(contextualized_message)

    # Persist agent state after message processing
    try:
        serializer = get_secure_serializer()
        agent_data = agent.get_state_for_serialization()
        agent_state = serializer.serialize(agent_data)
        _get_persistence().save_session(
            session_id=session_id,
            session_type="agent",
            agent_state=agent_state.encode('utf-8')
        )
    except SerializationError as e:
        logger.warning(f"Security: Failed to serialize agent state: {e}")
    except Exception as e:
        logger.warning(f"Failed to persist agent state: {sanitize_for_logging(str(e))}")

    return JSONResponse({"reply": reply})
