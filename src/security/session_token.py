"""
Session Token Authentication for Advisor API

Provides lightweight session-ownership tokens for anonymous chatbot users.
Each session gets a cryptographically random token at creation time.
All subsequent API calls must present this token via X-Session-Token header.

This prevents session hijacking and IDOR attacks without requiring user login.
"""

import secrets
import hmac
import logging
from fastapi import Header, HTTPException, Request

logger = logging.getLogger(__name__)

SESSION_TOKEN_KEY = "_session_token"


def generate_session_token() -> str:
    """Generate a cryptographically secure 32-byte URL-safe token."""
    return secrets.token_urlsafe(32)


def verify_token(provided: str, stored: str) -> bool:
    """Constant-time comparison to prevent timing attacks."""
    if not provided or not stored:
        return False
    return hmac.compare_digest(provided, stored)


async def verify_session_token(
    request: Request,
    x_session_token: str = Header(None),
) -> str:
    """
    FastAPI dependency that validates the session ownership token.

    Extracts session_id from the request (path params, query params, or JSON body),
    looks up the session, and validates the provided token.

    Returns the validated session_id on success.
    Raises 401 (missing token), 403 (wrong token), 404 (session not found).
    """
    if not x_session_token:
        raise HTTPException(status_code=401, detail="Missing X-Session-Token header")

    # Extract session_id from request — try path params, query params, then body
    session_id = request.path_params.get("session_id")

    if not session_id:
        session_id = request.query_params.get("session_id")

    if not session_id:
        # Read JSON body (Starlette caches internally via request.body())
        try:
            body_bytes = await request.body()
            if body_bytes:
                import json
                body = json.loads(body_bytes)
                session_id = body.get("session_id")
        except Exception:
            pass

    if not session_id:
        # Try form data for multipart uploads
        try:
            form = await request.form()
            session_id = form.get("session_id")
        except Exception:
            pass

    if not session_id:
        raise HTTPException(status_code=400, detail="No session_id found in request")

    # Look up session in the chat engine
    from src.web.intelligent_advisor_api import chat_engine

    if not chat_engine:
        logger.error("Chat engine not initialized")
        raise HTTPException(status_code=503, detail="Service not ready")

    # Check if session exists without auto-creating
    session = chat_engine.sessions.get(session_id)

    if not session:
        # Try loading from database (Redis or SQLite)
        session = await chat_engine._load_session_from_db(session_id)
        if session:
            chat_engine.sessions[session_id] = session

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    stored_token = session.get(SESSION_TOKEN_KEY)
    if not stored_token:
        raise HTTPException(status_code=403, detail="Session has no token — recreate session")

    if not verify_token(x_session_token, stored_token):
        logger.warning(f"Invalid session token for session {session_id}")
        raise HTTPException(status_code=403, detail="Invalid session token")

    return session_id
