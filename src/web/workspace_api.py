"""
CPA Workspace API Endpoints.

Phase 1-2: Multi-client management for tax preparers.

Routes:
- POST   /api/workspace/preparer/register    : Register new preparer
- GET    /api/workspace/preparer/me          : Get current preparer profile
- PUT    /api/workspace/preparer/branding    : Update branding (Phase 4)
- POST   /api/workspace/clients              : Add new client
- GET    /api/workspace/clients              : List clients (with search/filter/sort)
- GET    /api/workspace/clients/{id}         : Get client details
- PUT    /api/workspace/clients/{id}         : Update client
- DELETE /api/workspace/clients/{id}         : Archive client
- POST   /api/workspace/sessions             : Create/open session for client
- GET    /api/workspace/sessions/{id}        : Get session details
- PUT    /api/workspace/sessions/{id}/status : Update session status
- POST   /api/workspace/sessions/duplicate   : Duplicate prior year
- GET    /api/workspace/dashboard            : Get dashboard stats
"""

from typing import Optional, List
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, EmailStr

import logging

logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(prefix="/api/workspace", tags=["workspace"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class PreparerRegisterRequest(BaseModel):
    """Request to register a new preparer."""
    email: str = Field(..., description="Preparer's email (unique)")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    firm_name: Optional[str] = Field(None, description="Firm name for branding")
    credentials: Optional[List[str]] = Field(None, description="Credentials (CPA, EA, etc.)")
    license_state: Optional[str] = Field(None, description="Primary state of licensure")
    phone: Optional[str] = None


class PreparerBrandingRequest(BaseModel):
    """Request to update preparer branding."""
    firm_name: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    secondary_color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")


class ClientCreateRequest(BaseModel):
    """Request to create a new client."""
    first_name: str = Field(..., description="Client's first name")
    last_name: str = Field(..., description="Client's last name")
    email: Optional[str] = None
    external_id: Optional[str] = Field(None, description="CPA's own client ID")
    ssn: Optional[str] = Field(None, description="SSN (will be hashed)")
    phone: Optional[str] = None
    street_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = Field(None, max_length=2)
    zip_code: Optional[str] = None


class ClientUpdateRequest(BaseModel):
    """Request to update a client."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    external_id: Optional[str] = None
    phone: Optional[str] = None
    street_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None


class SessionCreateRequest(BaseModel):
    """Request to create/open a session."""
    client_id: str = Field(..., description="Client UUID")
    tax_year: int = Field(2025, description="Tax year")


class SessionStatusRequest(BaseModel):
    """Request to update session status."""
    status: str = Field(..., description="new, in_progress, ready_for_review, reviewed, delivered, archived")


class DuplicateYearRequest(BaseModel):
    """Request to duplicate prior year."""
    client_id: str = Field(..., description="Client UUID")
    from_year: int = Field(..., description="Source tax year")
    to_year: int = Field(..., description="Target tax year")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_preparer_id_from_request(request: Request) -> Optional[str]:
    """
    Get preparer ID from request.

    For Phase 1-2, we use a cookie or header.
    Future: JWT token validation.
    """
    # Try header first (for API clients)
    preparer_id = request.headers.get("X-Preparer-ID")
    if preparer_id:
        return preparer_id

    # Try cookie (for web clients)
    preparer_id = request.cookies.get("preparer_id")
    return preparer_id


def get_workspace_service():
    """Get workspace service instance."""
    try:
        from services.workspace_service import get_workspace_service as _get_ws
        return _get_ws()
    except Exception as e:
        logger.error(f"Failed to get workspace service: {e}")
        raise HTTPException(status_code=500, detail="Workspace service unavailable")


# =============================================================================
# PREPARER ENDPOINTS
# =============================================================================

@router.post("/preparer/register")
async def register_preparer(request_data: PreparerRegisterRequest):
    """
    Register a new preparer (CPA).

    Returns preparer profile with preparer_id.
    """
    service = get_workspace_service()

    try:
        preparer = service.register_preparer(
            email=request_data.email,
            first_name=request_data.first_name,
            last_name=request_data.last_name,
            firm_name=request_data.firm_name,
            credentials=request_data.credentials,
            license_state=request_data.license_state,
            phone=request_data.phone,
        )

        response = JSONResponse({
            "success": True,
            "preparer": preparer,
        })

        # Set cookie for web clients
        response.set_cookie(
            key="preparer_id",
            value=preparer["preparer_id"],
            httponly=True,
            samesite="lax",
            max_age=30 * 24 * 60 * 60,  # 30 days
        )

        return response

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Register preparer error: {e}")
        raise HTTPException(status_code=500, detail="Failed to register preparer")


@router.get("/preparer/me")
async def get_current_preparer(request: Request):
    """
    Get current preparer profile.

    Requires X-Preparer-ID header or preparer_id cookie.
    """
    preparer_id = get_preparer_id_from_request(request)
    if not preparer_id:
        raise HTTPException(status_code=401, detail="Preparer ID required")

    service = get_workspace_service()

    try:
        preparer = service.get_preparer(UUID(preparer_id))
        if not preparer:
            raise HTTPException(status_code=404, detail="Preparer not found")

        # Record login
        service.record_preparer_login(UUID(preparer_id))

        return JSONResponse({
            "success": True,
            "preparer": preparer,
        })

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid preparer ID")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get preparer error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get preparer")


@router.put("/preparer/branding")
async def update_preparer_branding(request: Request, request_data: PreparerBrandingRequest):
    """
    Update preparer branding for white-label (Phase 4).
    """
    preparer_id = get_preparer_id_from_request(request)
    if not preparer_id:
        raise HTTPException(status_code=401, detail="Preparer ID required")

    service = get_workspace_service()

    try:
        preparer = service.update_preparer_branding(
            preparer_id=UUID(preparer_id),
            firm_name=request_data.firm_name,
            logo_url=request_data.logo_url,
            primary_color=request_data.primary_color,
            secondary_color=request_data.secondary_color,
        )

        return JSONResponse({
            "success": True,
            "preparer": preparer,
        })

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Update branding error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update branding")


# =============================================================================
# CLIENT ENDPOINTS
# =============================================================================

@router.post("/clients")
async def create_client(request: Request, request_data: ClientCreateRequest):
    """
    Add a new client to the preparer's workspace.
    """
    preparer_id = get_preparer_id_from_request(request)
    if not preparer_id:
        raise HTTPException(status_code=401, detail="Preparer ID required")

    service = get_workspace_service()

    try:
        client = service.add_client(
            preparer_id=UUID(preparer_id),
            first_name=request_data.first_name,
            last_name=request_data.last_name,
            email=request_data.email,
            external_id=request_data.external_id,
            ssn=request_data.ssn,
            phone=request_data.phone,
            street_address=request_data.street_address,
            city=request_data.city,
            state=request_data.state,
            zip_code=request_data.zip_code,
        )

        return JSONResponse({
            "success": True,
            "client": client,
        })

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Create client error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create client")


@router.get("/clients")
async def list_clients(
    request: Request,
    search: Optional[str] = Query(None, description="Search by name, email, or external_id"),
    status: Optional[str] = Query(None, description="Filter by status"),
    tax_year: int = Query(2025, description="Tax year for session info"),
    sort_by: str = Query("last_accessed", description="Sort field: name, status, last_accessed, created"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    List clients for the preparer with search, filter, and sort.

    Returns clients with their current session info for the specified tax year.
    """
    preparer_id = get_preparer_id_from_request(request)
    if not preparer_id:
        raise HTTPException(status_code=401, detail="Preparer ID required")

    service = get_workspace_service()

    try:
        from services.workspace_service import SortField, SortOrder as SO

        sort_field_map = {
            "name": SortField.NAME,
            "status": SortField.STATUS,
            "last_accessed": SortField.LAST_ACCESSED,
            "created": SortField.CREATED,
            "tax_year": SortField.TAX_YEAR,
            "refund": SortField.REFUND,
        }

        result = service.list_clients(
            preparer_id=UUID(preparer_id),
            search=search,
            status_filter=status,
            tax_year=tax_year,
            sort_by=sort_field_map.get(sort_by, SortField.LAST_ACCESSED),
            sort_order=SO.DESC if sort_order == "desc" else SO.ASC,
            limit=limit,
            offset=offset,
        )

        return JSONResponse({
            "success": True,
            **result,
        })

    except Exception as e:
        logger.error(f"List clients error: {e}")
        raise HTTPException(status_code=500, detail="Failed to list clients")


@router.get("/clients/{client_id}")
async def get_client(request: Request, client_id: str):
    """
    Get client details by ID.
    """
    preparer_id = get_preparer_id_from_request(request)
    if not preparer_id:
        raise HTTPException(status_code=401, detail="Preparer ID required")

    service = get_workspace_service()

    try:
        client = service.get_client(UUID(client_id))
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Verify client belongs to this preparer
        if client["preparer_id"] != preparer_id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Get client history (all tax years)
        history = service.get_client_history(UUID(client_id))

        return JSONResponse({
            "success": True,
            "client": client,
            "history": history,
        })

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get client error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get client")


@router.put("/clients/{client_id}")
async def update_client(request: Request, client_id: str, request_data: ClientUpdateRequest):
    """
    Update client information.
    """
    preparer_id = get_preparer_id_from_request(request)
    if not preparer_id:
        raise HTTPException(status_code=401, detail="Preparer ID required")

    service = get_workspace_service()

    try:
        # Verify ownership
        client = service.get_client(UUID(client_id))
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        if client["preparer_id"] != preparer_id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Update
        updates = {k: v for k, v in request_data.model_dump().items() if v is not None}
        updated_client = service.update_client(UUID(client_id), **updates)

        return JSONResponse({
            "success": True,
            "client": updated_client,
        })

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update client error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update client")


@router.delete("/clients/{client_id}")
async def archive_client(request: Request, client_id: str):
    """
    Archive (soft delete) a client.
    """
    preparer_id = get_preparer_id_from_request(request)
    if not preparer_id:
        raise HTTPException(status_code=401, detail="Preparer ID required")

    service = get_workspace_service()

    try:
        # Verify ownership
        client = service.get_client(UUID(client_id))
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        if client["preparer_id"] != preparer_id:
            raise HTTPException(status_code=403, detail="Access denied")

        success = service.archive_client(UUID(client_id))

        return JSONResponse({
            "success": success,
            "message": "Client archived" if success else "Failed to archive client",
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Archive client error: {e}")
        raise HTTPException(status_code=500, detail="Failed to archive client")


# =============================================================================
# SESSION ENDPOINTS
# =============================================================================

@router.post("/sessions")
async def create_session(request: Request, request_data: SessionCreateRequest):
    """
    Create or open a session for a client and tax year.

    If session already exists, returns existing session.
    """
    preparer_id = get_preparer_id_from_request(request)
    if not preparer_id:
        raise HTTPException(status_code=401, detail="Preparer ID required")

    service = get_workspace_service()

    try:
        # Verify client ownership
        client = service.get_client(UUID(request_data.client_id))
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        if client["preparer_id"] != preparer_id:
            raise HTTPException(status_code=403, detail="Access denied")

        session = service.create_session(
            client_id=UUID(request_data.client_id),
            preparer_id=UUID(preparer_id),
            tax_year=request_data.tax_year,
        )

        return JSONResponse({
            "success": True,
            "session": session,
            "client": client,
        })

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create session error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create session")


@router.get("/sessions/{session_id}")
async def get_session(request: Request, session_id: str):
    """
    Get session details.

    Updates last_accessed timestamp.
    """
    preparer_id = get_preparer_id_from_request(request)
    if not preparer_id:
        raise HTTPException(status_code=401, detail="Preparer ID required")

    service = get_workspace_service()

    try:
        session = service.get_session(UUID(session_id))
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Verify ownership
        if session["preparer_id"] != preparer_id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Get client info
        client = service.get_client(UUID(session["client_id"]))

        return JSONResponse({
            "success": True,
            "session": session,
            "client": client,
        })

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get session error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get session")


@router.put("/sessions/{session_id}/status")
async def update_session_status(request: Request, session_id: str, request_data: SessionStatusRequest):
    """
    Update session status.

    Valid statuses: new, in_progress, ready_for_review, reviewed, delivered, archived
    """
    preparer_id = get_preparer_id_from_request(request)
    if not preparer_id:
        raise HTTPException(status_code=401, detail="Preparer ID required")

    service = get_workspace_service()

    try:
        # Verify ownership
        session = service.get_session(UUID(session_id))
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session["preparer_id"] != preparer_id:
            raise HTTPException(status_code=403, detail="Access denied")

        valid_statuses = ["new", "in_progress", "ready_for_review", "reviewed", "delivered", "archived"]
        if request_data.status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )

        updated_session = service.update_session_status(
            session_id=UUID(session_id),
            status=request_data.status,
        )

        return JSONResponse({
            "success": True,
            "session": updated_session,
        })

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update session status error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update session status")


@router.post("/sessions/duplicate")
async def duplicate_prior_year(request: Request, request_data: DuplicateYearRequest):
    """
    Duplicate a prior year session to a new year.

    Copies notes and creates a fresh session for the new year.
    """
    preparer_id = get_preparer_id_from_request(request)
    if not preparer_id:
        raise HTTPException(status_code=401, detail="Preparer ID required")

    service = get_workspace_service()

    try:
        # Verify client ownership
        client = service.get_client(UUID(request_data.client_id))
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        if client["preparer_id"] != preparer_id:
            raise HTTPException(status_code=403, detail="Access denied")

        session = service.duplicate_prior_year(
            client_id=UUID(request_data.client_id),
            preparer_id=UUID(preparer_id),
            from_year=request_data.from_year,
            to_year=request_data.to_year,
        )

        return JSONResponse({
            "success": True,
            "session": session,
            "message": f"Duplicated {request_data.from_year} to {request_data.to_year}",
        })

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Duplicate year error: {e}")
        raise HTTPException(status_code=500, detail="Failed to duplicate year")


# =============================================================================
# DASHBOARD ENDPOINTS
# =============================================================================

@router.get("/dashboard")
async def get_dashboard(
    request: Request,
    tax_year: int = Query(2025, description="Tax year for stats"),
):
    """
    Get dashboard statistics for the preparer.

    Returns client counts, status breakdown, and activity metrics.
    """
    preparer_id = get_preparer_id_from_request(request)
    if not preparer_id:
        raise HTTPException(status_code=401, detail="Preparer ID required")

    service = get_workspace_service()

    try:
        stats = service.get_dashboard_stats(
            preparer_id=UUID(preparer_id),
            tax_year=tax_year,
        )

        # Get preparer info for display
        preparer = service.get_preparer(UUID(preparer_id))

        return JSONResponse({
            "success": True,
            "preparer": preparer,
            "stats": stats,
        })

    except Exception as e:
        logger.error(f"Get dashboard error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get dashboard")
