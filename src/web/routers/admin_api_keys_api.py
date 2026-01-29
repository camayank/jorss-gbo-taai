"""
Admin API Keys Management.

Provides endpoints for CPA firms to:
- Create API keys for integrations
- List and manage API keys
- Revoke API keys
- View API key usage statistics

Security considerations:
- Raw API keys are only shown once at creation
- Keys are stored as hashes
- All key operations are logged
- Keys can be scoped to specific permissions
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timedelta
from uuid import uuid4
import secrets
import hashlib
import logging

from rbac.dependencies import require_auth, require_partner
from rbac.context import AuthContext

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/api-keys",
    tags=["Admin API Keys"],
    responses={403: {"description": "Insufficient permissions"}},
)

# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================


class APIKeyCreate(BaseModel):
    """Request to create a new API key."""
    name: str = Field(..., min_length=1, max_length=100, description="Friendly name for the key")
    description: Optional[str] = Field(None, max_length=500, description="Description of key purpose")
    scopes: List[str] = Field(
        default_factory=list,
        description="Permission scopes (e.g., 'clients:read', 'returns:write')"
    )
    expires_in_days: Optional[int] = Field(
        None, ge=1, le=365,
        description="Days until expiration (null = never expires)"
    )


class APIKeyUpdate(BaseModel):
    """Request to update an API key."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    scopes: Optional[List[str]] = None


# =============================================================================
# IN-MEMORY STORAGE (Replace with database in production)
# =============================================================================


class APIKey:
    """An API key for external integrations."""

    def __init__(
        self,
        key_id: str,
        firm_id: str,
        name: str,
        key_hash: str,
        prefix: str,
        scopes: List[str],
        description: Optional[str],
        created_by: str,
        expires_at: Optional[datetime],
    ):
        self.key_id = key_id
        self.firm_id = firm_id
        self.name = name
        self.key_hash = key_hash
        self.prefix = prefix  # First 8 chars of key for identification
        self.scopes = scopes
        self.description = description
        self.created_by = created_by
        self.created_at = datetime.utcnow()
        self.expires_at = expires_at
        self.last_used_at: Optional[datetime] = None
        self.use_count: int = 0
        self.revoked: bool = False
        self.revoked_at: Optional[datetime] = None

    @property
    def is_active(self) -> bool:
        """Check if key is active (not revoked or expired)."""
        if self.revoked:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True

    def to_dict(self, include_sensitive: bool = False) -> dict:
        """Convert to dictionary for API responses."""
        result = {
            "key_id": self.key_id,
            "name": self.name,
            "prefix": self.prefix,
            "scopes": self.scopes,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "use_count": self.use_count,
            "is_active": self.is_active,
            "revoked": self.revoked,
        }
        if include_sensitive:
            result["revoked_at"] = self.revoked_at.isoformat() if self.revoked_at else None
        return result


# Thread-safe in-memory storage
_api_keys: dict[str, APIKey] = {}

# Available scopes
AVAILABLE_SCOPES = [
    "clients:read",
    "clients:write",
    "returns:read",
    "returns:write",
    "documents:read",
    "documents:write",
    "reports:read",
    "analytics:read",
    "webhooks:manage",
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _generate_api_key() -> tuple[str, str, str]:
    """
    Generate a new API key.

    Returns:
        Tuple of (raw_key, key_hash, prefix)
    """
    # Generate a secure random key
    raw_key = f"jgb_{secrets.token_urlsafe(32)}"

    # Hash for storage
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    # Prefix for identification
    prefix = raw_key[:12]

    return raw_key, key_hash, prefix


def _validate_scopes(scopes: List[str]) -> List[str]:
    """Validate and filter scopes to only valid ones."""
    return [s for s in scopes if s in AVAILABLE_SCOPES]


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.get("")
async def list_api_keys(
    ctx: AuthContext = Depends(require_auth),
    include_revoked: bool = Query(False, description="Include revoked keys"),
):
    """
    List all API keys for the authenticated user's firm.

    Only firm partners can manage API keys.
    """
    firm_id = str(ctx.firm_id) if ctx.firm_id else str(ctx.user_id)

    keys = [
        k.to_dict() for k in _api_keys.values()
        if k.firm_id == firm_id and (include_revoked or not k.revoked)
    ]

    # Sort by created_at descending
    keys.sort(key=lambda k: k["created_at"], reverse=True)

    return {
        "api_keys": keys,
        "total": len(keys),
        "active_count": sum(1 for k in keys if k["is_active"]),
    }


@router.post("")
async def create_api_key(
    data: APIKeyCreate,
    ctx: AuthContext = Depends(require_partner),
):
    """
    Create a new API key.

    Only firm partners can create API keys.

    IMPORTANT: The raw key is only returned once. Store it securely.
    """
    firm_id = str(ctx.firm_id) if ctx.firm_id else str(ctx.user_id)

    # Validate scopes
    valid_scopes = _validate_scopes(data.scopes)
    invalid_scopes = set(data.scopes) - set(valid_scopes)

    if invalid_scopes:
        logger.warning(f"Invalid scopes requested: {invalid_scopes}")

    # Generate key
    raw_key, key_hash, prefix = _generate_api_key()

    # Calculate expiration
    expires_at = None
    if data.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=data.expires_in_days)

    # Create key object
    api_key = APIKey(
        key_id=str(uuid4()),
        firm_id=firm_id,
        name=data.name,
        key_hash=key_hash,
        prefix=prefix,
        scopes=valid_scopes,
        description=data.description,
        created_by=str(ctx.user_id),
        expires_at=expires_at,
    )

    _api_keys[api_key.key_id] = api_key

    logger.info(
        f"[AUDIT] API key created | firm={firm_id} | "
        f"key_id={api_key.key_id} | name={data.name} | "
        f"scopes={valid_scopes} | created_by={ctx.user_id}"
    )

    return {
        "api_key": api_key.to_dict(),
        "secret": raw_key,
        "warning": "Store this key securely. It will NOT be shown again.",
        "invalid_scopes": list(invalid_scopes) if invalid_scopes else None,
    }


@router.get("/scopes")
async def list_available_scopes(
    ctx: AuthContext = Depends(require_auth),
):
    """
    List all available API key scopes.

    Useful for building scope selection UI.
    """
    scope_descriptions = {
        "clients:read": "Read client information",
        "clients:write": "Create and update clients",
        "returns:read": "Read tax return data",
        "returns:write": "Create and update tax returns",
        "documents:read": "Read uploaded documents",
        "documents:write": "Upload and manage documents",
        "reports:read": "Access reports and summaries",
        "analytics:read": "Access analytics data",
        "webhooks:manage": "Manage webhook configurations",
    }

    return {
        "scopes": [
            {"scope": s, "description": scope_descriptions.get(s, "")}
            for s in AVAILABLE_SCOPES
        ]
    }


@router.get("/{key_id}")
async def get_api_key(
    key_id: str,
    ctx: AuthContext = Depends(require_auth),
):
    """
    Get details about a specific API key.

    Does NOT return the key secret (it's only shown at creation).
    """
    firm_id = str(ctx.firm_id) if ctx.firm_id else str(ctx.user_id)

    api_key = _api_keys.get(key_id)
    if not api_key or api_key.firm_id != firm_id:
        raise HTTPException(status_code=404, detail="API key not found")

    return {"api_key": api_key.to_dict(include_sensitive=True)}


@router.patch("/{key_id}")
async def update_api_key(
    key_id: str,
    data: APIKeyUpdate,
    ctx: AuthContext = Depends(require_partner),
):
    """
    Update an API key's metadata.

    Cannot change the key itself - create a new one instead.
    """
    firm_id = str(ctx.firm_id) if ctx.firm_id else str(ctx.user_id)

    api_key = _api_keys.get(key_id)
    if not api_key or api_key.firm_id != firm_id:
        raise HTTPException(status_code=404, detail="API key not found")

    if api_key.revoked:
        raise HTTPException(status_code=400, detail="Cannot update a revoked key")

    if data.name is not None:
        api_key.name = data.name

    if data.description is not None:
        api_key.description = data.description

    if data.scopes is not None:
        api_key.scopes = _validate_scopes(data.scopes)

    logger.info(
        f"[AUDIT] API key updated | key_id={key_id} | "
        f"updated_by={ctx.user_id}"
    )

    return {
        "api_key": api_key.to_dict(),
        "message": "API key updated successfully",
    }


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    ctx: AuthContext = Depends(require_partner),
):
    """
    Revoke an API key.

    The key will immediately stop working. This action cannot be undone.
    """
    firm_id = str(ctx.firm_id) if ctx.firm_id else str(ctx.user_id)

    api_key = _api_keys.get(key_id)
    if not api_key or api_key.firm_id != firm_id:
        raise HTTPException(status_code=404, detail="API key not found")

    if api_key.revoked:
        return {
            "message": "API key was already revoked",
            "revoked_at": api_key.revoked_at.isoformat(),
        }

    api_key.revoked = True
    api_key.revoked_at = datetime.utcnow()

    logger.info(
        f"[AUDIT] API key revoked | key_id={key_id} | "
        f"name={api_key.name} | revoked_by={ctx.user_id}"
    )

    return {
        "status": "revoked",
        "key_id": key_id,
        "revoked_at": api_key.revoked_at.isoformat(),
        "message": "API key revoked successfully. It will no longer work.",
    }


@router.get("/{key_id}/usage")
async def get_api_key_usage(
    key_id: str,
    ctx: AuthContext = Depends(require_auth),
):
    """
    Get usage statistics for an API key.

    Returns usage counts and last used timestamp.
    """
    firm_id = str(ctx.firm_id) if ctx.firm_id else str(ctx.user_id)

    api_key = _api_keys.get(key_id)
    if not api_key or api_key.firm_id != firm_id:
        raise HTTPException(status_code=404, detail="API key not found")

    return {
        "key_id": key_id,
        "name": api_key.name,
        "use_count": api_key.use_count,
        "last_used_at": api_key.last_used_at.isoformat() if api_key.last_used_at else None,
        "is_active": api_key.is_active,
    }


@router.post("/{key_id}/rotate")
async def rotate_api_key(
    key_id: str,
    ctx: AuthContext = Depends(require_partner),
):
    """
    Rotate an API key (create new key, revoke old one).

    Returns a new key with the same name/scopes.
    The old key is immediately revoked.
    """
    firm_id = str(ctx.firm_id) if ctx.firm_id else str(ctx.user_id)

    old_key = _api_keys.get(key_id)
    if not old_key or old_key.firm_id != firm_id:
        raise HTTPException(status_code=404, detail="API key not found")

    if old_key.revoked:
        raise HTTPException(status_code=400, detail="Cannot rotate a revoked key")

    # Generate new key
    raw_key, key_hash, prefix = _generate_api_key()

    # Create new key with same metadata
    new_key = APIKey(
        key_id=str(uuid4()),
        firm_id=firm_id,
        name=old_key.name,
        key_hash=key_hash,
        prefix=prefix,
        scopes=old_key.scopes,
        description=old_key.description,
        created_by=str(ctx.user_id),
        expires_at=old_key.expires_at,
    )

    _api_keys[new_key.key_id] = new_key

    # Revoke old key
    old_key.revoked = True
    old_key.revoked_at = datetime.utcnow()

    logger.info(
        f"[AUDIT] API key rotated | old_key={key_id} | "
        f"new_key={new_key.key_id} | rotated_by={ctx.user_id}"
    )

    return {
        "old_key_id": key_id,
        "new_api_key": new_key.to_dict(),
        "secret": raw_key,
        "warning": "Store this key securely. It will NOT be shown again.",
        "message": "API key rotated. Old key has been revoked.",
    }
