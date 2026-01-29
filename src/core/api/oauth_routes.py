"""
OAuth Authentication Routes

Endpoints for social login via Google and Microsoft.

Flow:
1. Frontend calls GET /auth/oauth/{provider}/start
2. Frontend redirects user to returned authorization_url
3. User authenticates with provider
4. Provider redirects to GET /auth/oauth/{provider}/callback
5. Backend exchanges code for tokens and creates session
6. Backend redirects to frontend with session token
"""

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse, JSONResponse
import logging
from typing import Optional

from ..services.oauth_service import (
    get_oauth_service,
    OAuthService,
    OAuthConfig,
    OAuthStartResponse,
)
from ..services.auth_service import AuthResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth", tags=["OAuth Authentication"])


# =============================================================================
# OAUTH CONFIGURATION STATUS
# =============================================================================

@router.get("/providers")
async def list_oauth_providers():
    """
    List available OAuth providers and their configuration status.

    Returns which OAuth providers are configured and available.
    """
    config = OAuthConfig()
    return {
        "providers": {
            "google": {
                "available": config.is_google_configured(),
                "name": "Google",
                "icon": "google"
            },
            "microsoft": {
                "available": config.is_microsoft_configured(),
                "name": "Microsoft",
                "icon": "microsoft"
            }
        }
    }


# =============================================================================
# GOOGLE OAUTH
# =============================================================================

@router.get("/google/start", response_model=OAuthStartResponse)
async def start_google_oauth(
    request: Request,
    redirect_uri: Optional[str] = Query(None, description="Custom callback URL"),
):
    """
    Start Google OAuth flow.

    Returns authorization URL to redirect user to.
    Frontend should redirect user to this URL.
    """
    oauth_service = get_oauth_service()

    try:
        # Use request origin for callback if not specified
        if not redirect_uri:
            origin = request.headers.get("origin", "")
            if origin:
                redirect_uri = f"{origin}/api/core/auth/oauth/google/callback"

        result = oauth_service.start_oauth("google", redirect_uri)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/google/callback")
async def google_oauth_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State token for CSRF validation"),
    error: Optional[str] = Query(None, description="Error from OAuth provider"),
    error_description: Optional[str] = Query(None),
):
    """
    Handle Google OAuth callback.

    Called by Google after user authenticates.
    Exchanges code for tokens and creates user session.
    """
    # Handle OAuth errors
    if error:
        logger.warning(f"Google OAuth error: {error} - {error_description}")
        # Redirect to login page with error
        return RedirectResponse(
            url=f"/login?error=oauth_failed&provider=google&message={error_description or error}",
            status_code=status.HTTP_302_FOUND
        )

    oauth_service = get_oauth_service()

    try:
        # Exchange code for user info
        user_info = await oauth_service.handle_callback("google", code, state)

        # Create or link user account
        result = await oauth_service.create_or_link_user(user_info)

        # Redirect to frontend with token
        # In production, use secure cookie or fragment identifier
        redirect_url = f"/login?oauth_success=true&token={result['access_token']}&is_new={result['is_new_user']}"

        return RedirectResponse(
            url=redirect_url,
            status_code=status.HTTP_302_FOUND
        )

    except ValueError as e:
        logger.error(f"Google OAuth callback failed: {e}")
        return RedirectResponse(
            url=f"/login?error=oauth_failed&provider=google&message={str(e)}",
            status_code=status.HTTP_302_FOUND
        )
    except Exception as e:
        logger.exception(f"Google OAuth callback error: {e}")
        return RedirectResponse(
            url="/login?error=oauth_failed&provider=google&message=Authentication%20failed",
            status_code=status.HTTP_302_FOUND
        )


@router.post("/google/token", response_model=AuthResponse)
async def google_oauth_token(
    code: str,
    state: str,
    redirect_uri: Optional[str] = None,
):
    """
    Exchange Google OAuth code for tokens (API-based flow).

    Alternative to callback redirect for SPA frontends.
    Frontend exchanges code directly for tokens.
    """
    oauth_service = get_oauth_service()

    try:
        # Exchange code for user info
        user_info = await oauth_service.handle_callback("google", code, state, redirect_uri)

        # Create or link user account
        result = await oauth_service.create_or_link_user(user_info)

        return AuthResponse(
            success=True,
            message="Google authentication successful",
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            expires_in=3600,
            user=result["user"]
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# =============================================================================
# MICROSOFT OAUTH
# =============================================================================

@router.get("/microsoft/start", response_model=OAuthStartResponse)
async def start_microsoft_oauth(
    request: Request,
    redirect_uri: Optional[str] = Query(None, description="Custom callback URL"),
):
    """
    Start Microsoft OAuth flow.

    Returns authorization URL to redirect user to.
    Frontend should redirect user to this URL.
    """
    oauth_service = get_oauth_service()

    try:
        # Use request origin for callback if not specified
        if not redirect_uri:
            origin = request.headers.get("origin", "")
            if origin:
                redirect_uri = f"{origin}/api/core/auth/oauth/microsoft/callback"

        result = oauth_service.start_oauth("microsoft", redirect_uri)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/microsoft/callback")
async def microsoft_oauth_callback(
    code: str = Query(..., description="Authorization code from Microsoft"),
    state: str = Query(..., description="State token for CSRF validation"),
    error: Optional[str] = Query(None, description="Error from OAuth provider"),
    error_description: Optional[str] = Query(None),
):
    """
    Handle Microsoft OAuth callback.

    Called by Microsoft after user authenticates.
    Exchanges code for tokens and creates user session.
    """
    # Handle OAuth errors
    if error:
        logger.warning(f"Microsoft OAuth error: {error} - {error_description}")
        return RedirectResponse(
            url=f"/login?error=oauth_failed&provider=microsoft&message={error_description or error}",
            status_code=status.HTTP_302_FOUND
        )

    oauth_service = get_oauth_service()

    try:
        # Exchange code for user info
        user_info = await oauth_service.handle_callback("microsoft", code, state)

        # Create or link user account
        result = await oauth_service.create_or_link_user(user_info)

        # Redirect to frontend with token
        redirect_url = f"/login?oauth_success=true&token={result['access_token']}&is_new={result['is_new_user']}"

        return RedirectResponse(
            url=redirect_url,
            status_code=status.HTTP_302_FOUND
        )

    except ValueError as e:
        logger.error(f"Microsoft OAuth callback failed: {e}")
        return RedirectResponse(
            url=f"/login?error=oauth_failed&provider=microsoft&message={str(e)}",
            status_code=status.HTTP_302_FOUND
        )
    except Exception as e:
        logger.exception(f"Microsoft OAuth callback error: {e}")
        return RedirectResponse(
            url="/login?error=oauth_failed&provider=microsoft&message=Authentication%20failed",
            status_code=status.HTTP_302_FOUND
        )


@router.post("/microsoft/token", response_model=AuthResponse)
async def microsoft_oauth_token(
    code: str,
    state: str,
    redirect_uri: Optional[str] = None,
):
    """
    Exchange Microsoft OAuth code for tokens (API-based flow).

    Alternative to callback redirect for SPA frontends.
    Frontend exchanges code directly for tokens.
    """
    oauth_service = get_oauth_service()

    try:
        # Exchange code for user info
        user_info = await oauth_service.handle_callback("microsoft", code, state, redirect_uri)

        # Create or link user account
        result = await oauth_service.create_or_link_user(user_info)

        return AuthResponse(
            success=True,
            message="Microsoft authentication successful",
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            expires_in=3600,
            user=result["user"]
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
