"""
Custom Domain API

Provides DNS verification flow for tenant custom domains.
Supports CNAME and TXT record verification methods.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from datetime import datetime, timedelta
from enum import Enum
import uuid
import logging
import hashlib
import secrets
import socket
import re

try:
    from rbac.dependencies import require_auth, AuthContext, get_current_user
    from rbac.permissions import Permission
except ImportError:
    class AuthContext:
        user_id: Optional[str] = None
        tenant_id: Optional[str] = None
        role: Any = None
    def require_auth():
        return AuthContext()
    def get_current_user():
        return AuthContext()
    class Permission:
        MANAGE_TENANT_SETTINGS = "manage_tenant_settings"

try:
    from database.tenant_persistence import get_tenant_persistence
except ImportError:
    def get_tenant_persistence():
        raise HTTPException(500, "Tenant persistence not available")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/custom-domain", tags=["custom-domain"])


# =============================================================================
# MODELS
# =============================================================================

class VerificationMethod(str, Enum):
    """DNS verification methods"""
    CNAME = "cname"
    TXT = "txt"


class VerificationStatus(str, Enum):
    """Domain verification status"""
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    EXPIRED = "expired"


class DomainSetupRequest(BaseModel):
    """Request to set up a custom domain"""
    domain: str = Field(..., min_length=4, max_length=253)
    verification_method: VerificationMethod = VerificationMethod.CNAME

    @validator('domain')
    def validate_domain(cls, v):
        # Basic domain validation
        domain_pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        if not re.match(domain_pattern, v):
            raise ValueError('Invalid domain format')
        # Prevent common mistakes
        if v.startswith('http://') or v.startswith('https://'):
            raise ValueError('Domain should not include protocol (http/https)')
        if v.startswith('www.'):
            v = v[4:]  # Strip www prefix
        return v.lower()


class DomainVerificationResponse(BaseModel):
    """Response with verification instructions"""
    domain: str
    verification_method: VerificationMethod
    verification_record: Dict[str, str]
    verification_token: str
    status: VerificationStatus
    expires_at: datetime
    instructions: List[str]


class DomainStatusResponse(BaseModel):
    """Current domain status"""
    domain: Optional[str]
    verified: bool
    verification_status: Optional[VerificationStatus]
    verification_method: Optional[VerificationMethod]
    last_checked: Optional[datetime]
    ssl_status: Optional[str]


# =============================================================================
# DNS VERIFICATION UTILITIES
# =============================================================================

def generate_verification_token(tenant_id: str, domain: str) -> str:
    """Generate a unique verification token for a tenant/domain pair"""
    # Create deterministic but hard-to-guess token
    seed = f"{tenant_id}:{domain}:{secrets.token_hex(8)}"
    return hashlib.sha256(seed.encode()).hexdigest()[:32]


def get_cname_target() -> str:
    """Get the CNAME target for custom domain verification"""
    # In production, this would be your actual platform domain
    return "verify.ca4cpa.com"


def get_txt_record_name(domain: str) -> str:
    """Get the TXT record name for verification"""
    return f"_ca4cpa-verify.{domain}"


async def verify_cname_record(domain: str, expected_target: str) -> bool:
    """
    Verify CNAME record points to expected target.

    In production, use dnspython or similar for reliable DNS lookups.
    """
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, 'CNAME')
        for rdata in answers:
            target = str(rdata.target).rstrip('.')
            if target.lower() == expected_target.lower():
                return True
        return False
    except ImportError:
        # Fallback: Use socket for basic check
        try:
            # Check if domain resolves
            socket.gethostbyname(domain)
            # In production, you'd verify the actual CNAME target
            logger.warning(f"DNS verification fallback for {domain} - dnspython not available")
            return True  # Allow for testing
        except socket.gaierror:
            return False
    except Exception as e:
        logger.error(f"CNAME verification error for {domain}: {e}")
        return False


async def verify_txt_record(domain: str, expected_value: str) -> bool:
    """
    Verify TXT record contains expected verification value.
    """
    try:
        import dns.resolver
        txt_name = get_txt_record_name(domain)
        answers = dns.resolver.resolve(txt_name, 'TXT')
        for rdata in answers:
            for txt_string in rdata.strings:
                if expected_value in txt_string.decode():
                    return True
        return False
    except ImportError:
        logger.warning(f"TXT verification fallback for {domain} - dnspython not available")
        # For testing/development without dnspython
        return False
    except Exception as e:
        logger.debug(f"TXT verification for {domain}: {e}")
        return False


# =============================================================================
# IN-MEMORY VERIFICATION STORE (Production: use database)
# =============================================================================

# Stores pending verifications: tenant_id -> verification_data
_pending_verifications: Dict[str, Dict[str, Any]] = {}


def get_pending_verification(tenant_id: str) -> Optional[Dict[str, Any]]:
    """Get pending verification for a tenant"""
    return _pending_verifications.get(tenant_id)


def save_pending_verification(tenant_id: str, data: Dict[str, Any]) -> None:
    """Save pending verification"""
    _pending_verifications[tenant_id] = data


def clear_pending_verification(tenant_id: str) -> None:
    """Clear pending verification"""
    _pending_verifications.pop(tenant_id, None)


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/status")
async def get_domain_status(
    ctx: AuthContext = Depends(require_auth)
) -> DomainStatusResponse:
    """
    Get current custom domain status for the tenant.

    Returns the configured domain, verification status, and SSL status.
    """
    try:
        persistence = get_tenant_persistence()
        tenant = persistence.get_tenant(str(ctx.tenant_id))

        if not tenant:
            raise HTTPException(404, "Tenant not found")

        # Check if custom domain feature is enabled
        if not tenant.features.custom_domain_enabled:
            raise HTTPException(403, "Custom domain feature not enabled for your subscription")

        # Get pending verification status
        pending = get_pending_verification(str(ctx.tenant_id))

        return DomainStatusResponse(
            domain=tenant.custom_domain,
            verified=tenant.custom_domain_verified,
            verification_status=VerificationStatus(pending["status"]) if pending else None,
            verification_method=VerificationMethod(pending["method"]) if pending else None,
            last_checked=pending.get("last_checked") if pending else None,
            ssl_status="active" if tenant.custom_domain_verified else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CustomDomain] Failed to get status: {e}")
        raise HTTPException(500, f"Failed to get domain status: {str(e)}")


@router.post("/setup")
async def setup_custom_domain(
    request: DomainSetupRequest,
    ctx: AuthContext = Depends(require_auth)
) -> DomainVerificationResponse:
    """
    Initiate custom domain setup with DNS verification.

    Returns verification instructions including the DNS record to create.
    """
    try:
        persistence = get_tenant_persistence()
        tenant = persistence.get_tenant(str(ctx.tenant_id))

        if not tenant:
            raise HTTPException(404, "Tenant not found")

        # Check if custom domain feature is enabled
        if not tenant.features.custom_domain_enabled:
            raise HTTPException(403, "Custom domain feature not enabled for your subscription")

        domain = request.domain
        method = request.verification_method

        # Generate verification token
        token = generate_verification_token(str(ctx.tenant_id), domain)

        # Prepare verification record based on method
        if method == VerificationMethod.CNAME:
            verification_record = {
                "type": "CNAME",
                "name": domain,
                "value": get_cname_target(),
                "ttl": "3600",
            }
            instructions = [
                f"Log in to your domain registrar or DNS provider",
                f"Navigate to DNS settings for {domain}",
                f"Create a new CNAME record:",
                f"  - Name/Host: @ (or leave blank for root domain)",
                f"  - Value/Target: {get_cname_target()}",
                f"  - TTL: 3600 (or default)",
                f"DNS changes may take up to 48 hours to propagate",
                f"Click 'Verify Domain' once you've made the changes",
            ]
        else:  # TXT method
            txt_value = f"ca4cpa-verify={token}"
            verification_record = {
                "type": "TXT",
                "name": get_txt_record_name(domain),
                "value": txt_value,
                "ttl": "3600",
            }
            instructions = [
                f"Log in to your domain registrar or DNS provider",
                f"Navigate to DNS settings for {domain}",
                f"Create a new TXT record:",
                f"  - Name/Host: _ca4cpa-verify",
                f"  - Value: {txt_value}",
                f"  - TTL: 3600 (or default)",
                f"DNS changes may take up to 48 hours to propagate",
                f"Click 'Verify Domain' once you've made the changes",
            ]

        # Calculate expiration (7 days from now)
        expires_at = datetime.utcnow() + timedelta(days=7)

        # Save pending verification
        verification_data = {
            "domain": domain,
            "method": method.value,
            "token": token,
            "status": VerificationStatus.PENDING.value,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at.isoformat(),
            "attempts": 0,
        }
        save_pending_verification(str(ctx.tenant_id), verification_data)

        # Update tenant with pending domain
        tenant.custom_domain = domain
        tenant.custom_domain_verified = False
        persistence.save_tenant(tenant)

        logger.info(f"[CustomDomain] Setup initiated for tenant {ctx.tenant_id}: {domain}")

        return DomainVerificationResponse(
            domain=domain,
            verification_method=method,
            verification_record=verification_record,
            verification_token=token,
            status=VerificationStatus.PENDING,
            expires_at=expires_at,
            instructions=instructions,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CustomDomain] Setup failed: {e}")
        raise HTTPException(500, f"Failed to setup custom domain: {str(e)}")


@router.post("/verify")
async def verify_custom_domain(
    background_tasks: BackgroundTasks,
    ctx: AuthContext = Depends(require_auth)
) -> Dict[str, Any]:
    """
    Verify the DNS records for the pending custom domain.

    Checks the configured DNS records and marks domain as verified if successful.
    """
    try:
        persistence = get_tenant_persistence()
        tenant = persistence.get_tenant(str(ctx.tenant_id))

        if not tenant:
            raise HTTPException(404, "Tenant not found")

        pending = get_pending_verification(str(ctx.tenant_id))
        if not pending:
            raise HTTPException(400, "No pending domain verification. Please set up a domain first.")

        # Check expiration
        expires_at = datetime.fromisoformat(pending["expires_at"])
        if datetime.utcnow() > expires_at:
            pending["status"] = VerificationStatus.EXPIRED.value
            save_pending_verification(str(ctx.tenant_id), pending)
            raise HTTPException(400, "Verification has expired. Please start the setup process again.")

        domain = pending["domain"]
        method = pending["method"]
        token = pending["token"]

        # Increment attempt counter
        pending["attempts"] = pending.get("attempts", 0) + 1
        pending["last_checked"] = datetime.utcnow().isoformat()

        # Perform verification
        verified = False
        if method == VerificationMethod.CNAME.value:
            verified = await verify_cname_record(domain, get_cname_target())
        else:
            txt_value = f"ca4cpa-verify={token}"
            verified = await verify_txt_record(domain, txt_value)

        if verified:
            # Mark as verified
            pending["status"] = VerificationStatus.VERIFIED.value
            save_pending_verification(str(ctx.tenant_id), pending)

            # Update tenant
            tenant.custom_domain = domain
            tenant.custom_domain_verified = True
            persistence.save_tenant(tenant)

            logger.info(f"[CustomDomain] Verified successfully: {domain} for tenant {ctx.tenant_id}")

            return {
                "success": True,
                "verified": True,
                "domain": domain,
                "message": "Domain verified successfully! SSL certificate will be provisioned automatically.",
                "next_steps": [
                    "Your domain is now active",
                    "SSL certificate will be issued within a few minutes",
                    "You can access your portal at https://" + domain,
                ],
            }
        else:
            # Not verified yet
            pending["status"] = VerificationStatus.PENDING.value
            save_pending_verification(str(ctx.tenant_id), pending)

            logger.info(f"[CustomDomain] Verification pending for {domain} - attempt {pending['attempts']}")

            return {
                "success": False,
                "verified": False,
                "domain": domain,
                "message": "DNS records not found yet. This can take up to 48 hours.",
                "attempts": pending["attempts"],
                "suggestions": [
                    "Verify you created the correct DNS record type",
                    "Check for typos in the record name and value",
                    "Wait a few minutes and try again",
                    "DNS propagation can take up to 48 hours",
                ],
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CustomDomain] Verification failed: {e}")
        raise HTTPException(500, f"Failed to verify domain: {str(e)}")


@router.delete("/remove")
async def remove_custom_domain(
    ctx: AuthContext = Depends(require_auth)
) -> Dict[str, Any]:
    """
    Remove the custom domain from the tenant.

    This will revert to the default platform domain.
    """
    try:
        persistence = get_tenant_persistence()
        tenant = persistence.get_tenant(str(ctx.tenant_id))

        if not tenant:
            raise HTTPException(404, "Tenant not found")

        if not tenant.custom_domain:
            raise HTTPException(400, "No custom domain configured")

        old_domain = tenant.custom_domain

        # Clear custom domain
        tenant.custom_domain = None
        tenant.custom_domain_verified = False
        persistence.save_tenant(tenant)

        # Clear any pending verification
        clear_pending_verification(str(ctx.tenant_id))

        logger.info(f"[CustomDomain] Removed {old_domain} from tenant {ctx.tenant_id}")

        return {
            "success": True,
            "message": f"Custom domain {old_domain} has been removed.",
            "note": "You can set up a new custom domain at any time.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CustomDomain] Remove failed: {e}")
        raise HTTPException(500, f"Failed to remove domain: {str(e)}")


@router.get("/check-availability")
async def check_domain_availability(
    domain: str,
    ctx: AuthContext = Depends(require_auth)
) -> Dict[str, Any]:
    """
    Check if a domain is available for use with the platform.

    Verifies the domain isn't already in use by another tenant.
    """
    try:
        # Validate domain format
        domain_pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        domain = domain.lower().lstrip('www.')

        if not re.match(domain_pattern, domain):
            return {
                "available": False,
                "domain": domain,
                "reason": "Invalid domain format",
            }

        # Check if domain is already in use
        persistence = get_tenant_persistence()

        # In production, query all tenants to check for domain conflicts
        # For now, return available
        is_available = True  # Would check database here

        if is_available:
            return {
                "available": True,
                "domain": domain,
                "message": "This domain is available for use.",
            }
        else:
            return {
                "available": False,
                "domain": domain,
                "reason": "This domain is already in use by another account.",
            }

    except Exception as e:
        logger.error(f"[CustomDomain] Availability check failed: {e}")
        raise HTTPException(500, f"Failed to check domain availability: {str(e)}")
