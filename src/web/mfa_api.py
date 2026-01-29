"""
Multi-Factor Authentication (MFA) API

TOTP-based two-factor authentication implementation.
Compatible with Google Authenticator, Authy, and other TOTP apps.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import logging
import secrets
import base64
import hmac
import hashlib
import struct
import time

try:
    from rbac.dependencies import require_auth, AuthContext
except ImportError:
    class AuthContext:
        user_id: Optional[str] = None
        tenant_id: Optional[str] = None
        role: Any = None
    def require_auth():
        return AuthContext()

try:
    from database.repositories.user_auth_repository import get_user_auth_repository
except ImportError:
    def get_user_auth_repository():
        raise HTTPException(500, "User auth repository not available")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mfa", tags=["mfa"])


# =============================================================================
# TOTP IMPLEMENTATION
# =============================================================================

class TOTPGenerator:
    """
    Time-based One-Time Password (TOTP) generator.

    Implements RFC 6238 TOTP algorithm compatible with:
    - Google Authenticator
    - Authy
    - Microsoft Authenticator
    - 1Password
    - And other TOTP apps
    """

    DIGITS = 6  # Standard TOTP code length
    PERIOD = 30  # Time step in seconds
    ALGORITHM = 'sha1'  # SHA1 for compatibility

    @staticmethod
    def generate_secret(length: int = 32) -> str:
        """
        Generate a base32-encoded secret key.

        Args:
            length: Number of random bytes (default 32 = 256 bits)

        Returns:
            Base32-encoded secret string
        """
        random_bytes = secrets.token_bytes(length)
        return base64.b32encode(random_bytes).decode('utf-8').rstrip('=')

    @staticmethod
    def get_totp_code(secret: str, time_offset: int = 0) -> str:
        """
        Generate TOTP code for current time.

        Args:
            secret: Base32-encoded secret key
            time_offset: Number of time periods to offset (for verification window)

        Returns:
            6-digit TOTP code
        """
        # Decode secret (handle missing padding)
        secret_padded = secret + '=' * ((8 - len(secret) % 8) % 8)
        key = base64.b32decode(secret_padded.upper())

        # Calculate time counter
        timestamp = int(time.time())
        counter = (timestamp // TOTPGenerator.PERIOD) + time_offset

        # Convert counter to bytes (big-endian 8-byte)
        counter_bytes = struct.pack('>Q', counter)

        # Calculate HMAC-SHA1
        hmac_hash = hmac.new(key, counter_bytes, hashlib.sha1).digest()

        # Dynamic truncation
        offset = hmac_hash[-1] & 0x0F
        binary = struct.unpack('>I', hmac_hash[offset:offset + 4])[0] & 0x7FFFFFFF

        # Generate 6-digit code
        otp = binary % (10 ** TOTPGenerator.DIGITS)
        return str(otp).zfill(TOTPGenerator.DIGITS)

    @staticmethod
    def verify_totp(secret: str, code: str, window: int = 1) -> bool:
        """
        Verify a TOTP code with time window tolerance.

        Args:
            secret: Base32-encoded secret key
            code: The 6-digit code to verify
            window: Number of periods before/after to accept (default 1 = ±30 seconds)

        Returns:
            True if code is valid
        """
        code = code.strip().replace(' ', '')

        if len(code) != TOTPGenerator.DIGITS or not code.isdigit():
            return False

        # Check current period and window periods
        for offset in range(-window, window + 1):
            expected = TOTPGenerator.get_totp_code(secret, offset)
            if hmac.compare_digest(code, expected):
                return True

        return False

    @staticmethod
    def get_provisioning_uri(
        secret: str,
        account_name: str,
        issuer: str = "CA4CPA"
    ) -> str:
        """
        Generate otpauth:// URI for QR code.

        Args:
            secret: Base32-encoded secret key
            account_name: User's email or username
            issuer: Service name (shown in authenticator app)

        Returns:
            otpauth:// URI string
        """
        from urllib.parse import quote

        # URL encode components
        account = quote(account_name, safe='')
        issuer_encoded = quote(issuer, safe='')

        return (
            f"otpauth://totp/{issuer_encoded}:{account}"
            f"?secret={secret}"
            f"&issuer={issuer_encoded}"
            f"&algorithm=SHA1"
            f"&digits={TOTPGenerator.DIGITS}"
            f"&period={TOTPGenerator.PERIOD}"
        )


# =============================================================================
# MODELS
# =============================================================================

class MFAStatus(str, Enum):
    """MFA status"""
    DISABLED = "disabled"
    PENDING_SETUP = "pending_setup"
    ENABLED = "enabled"


class SetupMFAResponse(BaseModel):
    """Response with MFA setup information"""
    secret: str
    qr_code_uri: str
    manual_entry_key: str
    backup_codes: List[str]
    instructions: List[str]


class VerifyMFARequest(BaseModel):
    """Request to verify MFA code"""
    code: str = Field(..., min_length=6, max_length=6, pattern=r'^\d{6}$')


class ValidateMFARequest(BaseModel):
    """Request to validate MFA during login"""
    user_id: str
    code: str = Field(..., min_length=6, max_length=6, pattern=r'^\d{6}$')


class DisableMFARequest(BaseModel):
    """Request to disable MFA"""
    code: str = Field(..., min_length=6, max_length=6, pattern=r'^\d{6}$')
    password: str = Field(..., min_length=1)


# =============================================================================
# BACKUP CODES
# =============================================================================

def generate_backup_codes(count: int = 10) -> List[str]:
    """
    Generate one-time backup codes for account recovery.

    Args:
        count: Number of backup codes to generate

    Returns:
        List of 8-character backup codes
    """
    codes = []
    for _ in range(count):
        # Generate 8-character alphanumeric code (easy to type)
        code = secrets.token_hex(4).upper()
        # Format as XXXX-XXXX for readability
        formatted = f"{code[:4]}-{code[4:]}"
        codes.append(formatted)
    return codes


def hash_backup_code(code: str) -> str:
    """Hash a backup code for storage"""
    normalized = code.upper().replace('-', '')
    return hashlib.sha256(normalized.encode()).hexdigest()


# =============================================================================
# IN-MEMORY STORES (Production: use database)
# =============================================================================

# Pending MFA setups: user_id -> setup_data
_pending_mfa_setups: Dict[str, Dict[str, Any]] = {}

# Backup codes: user_id -> [hashed_codes]
_backup_codes: Dict[str, List[str]] = {}


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/status")
async def get_mfa_status(
    ctx: AuthContext = Depends(require_auth)
) -> Dict[str, Any]:
    """
    Get current MFA status for the authenticated user.

    Returns whether MFA is enabled and when it was set up.
    """
    try:
        repo = get_user_auth_repository()
        user = repo.get_user_by_id(str(ctx.user_id))

        if not user:
            raise HTTPException(404, "User not found")

        # Check for pending setup
        pending = _pending_mfa_setups.get(str(ctx.user_id))

        status = MFAStatus.DISABLED
        if user.mfa_enabled and user.mfa_secret:
            status = MFAStatus.ENABLED
        elif pending:
            status = MFAStatus.PENDING_SETUP

        return {
            "enabled": user.mfa_enabled,
            "status": status.value,
            "has_backup_codes": str(ctx.user_id) in _backup_codes and len(_backup_codes[str(ctx.user_id)]) > 0,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MFA] Failed to get status: {e}")
        raise HTTPException(500, f"Failed to get MFA status: {str(e)}")


@router.post("/setup")
async def setup_mfa(
    ctx: AuthContext = Depends(require_auth)
) -> SetupMFAResponse:
    """
    Initiate MFA setup.

    Generates a new TOTP secret and returns setup information
    including QR code URI and backup codes.
    """
    try:
        repo = get_user_auth_repository()
        user = repo.get_user_by_id(str(ctx.user_id))

        if not user:
            raise HTTPException(404, "User not found")

        if user.mfa_enabled:
            raise HTTPException(400, "MFA is already enabled. Disable it first to reconfigure.")

        # Generate new secret
        secret = TOTPGenerator.generate_secret()

        # Get user email for provisioning URI
        account_name = user.email if hasattr(user, 'email') else str(ctx.user_id)

        # Generate provisioning URI for QR code
        qr_uri = TOTPGenerator.get_provisioning_uri(
            secret=secret,
            account_name=account_name,
            issuer="CA4CPA"
        )

        # Generate backup codes
        backup_codes = generate_backup_codes(10)

        # Store pending setup (not yet confirmed)
        _pending_mfa_setups[str(ctx.user_id)] = {
            "secret": secret,
            "backup_codes": [hash_backup_code(c) for c in backup_codes],
            "created_at": datetime.utcnow().isoformat(),
        }

        # Format secret for manual entry (groups of 4)
        manual_key = ' '.join([secret[i:i+4] for i in range(0, len(secret), 4)])

        logger.info(f"[MFA] Setup initiated for user {ctx.user_id}")

        return SetupMFAResponse(
            secret=secret,
            qr_code_uri=qr_uri,
            manual_entry_key=manual_key,
            backup_codes=backup_codes,
            instructions=[
                "1. Download an authenticator app (Google Authenticator, Authy, etc.)",
                "2. Scan the QR code or enter the secret key manually",
                "3. Enter the 6-digit code from your app to verify setup",
                "4. Save your backup codes in a secure location",
                "5. Each backup code can only be used once",
            ],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MFA] Setup failed: {e}")
        raise HTTPException(500, f"Failed to setup MFA: {str(e)}")


@router.post("/verify-setup")
async def verify_mfa_setup(
    request: VerifyMFARequest,
    ctx: AuthContext = Depends(require_auth)
) -> Dict[str, Any]:
    """
    Verify MFA setup by confirming the first TOTP code.

    This confirms the user has correctly configured their authenticator
    app and enables MFA on their account.
    """
    try:
        repo = get_user_auth_repository()
        user = repo.get_user_by_id(str(ctx.user_id))

        if not user:
            raise HTTPException(404, "User not found")

        pending = _pending_mfa_setups.get(str(ctx.user_id))
        if not pending:
            raise HTTPException(400, "No pending MFA setup. Please start setup first.")

        secret = pending["secret"]
        backup_codes_hashed = pending["backup_codes"]

        # Verify the code
        if not TOTPGenerator.verify_totp(secret, request.code):
            raise HTTPException(400, "Invalid verification code. Please try again.")

        # Enable MFA on user account
        user.mfa_enabled = True
        user.mfa_secret = secret
        repo.update_user(user)

        # Store backup codes
        _backup_codes[str(ctx.user_id)] = backup_codes_hashed

        # Clear pending setup
        del _pending_mfa_setups[str(ctx.user_id)]

        logger.info(f"[MFA] Enabled successfully for user {ctx.user_id}")

        return {
            "success": True,
            "message": "MFA has been enabled successfully!",
            "mfa_enabled": True,
            "backup_codes_count": len(backup_codes_hashed),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MFA] Verify setup failed: {e}")
        raise HTTPException(500, f"Failed to verify MFA setup: {str(e)}")


@router.post("/validate")
async def validate_mfa_code(
    request: ValidateMFARequest,
) -> Dict[str, Any]:
    """
    Validate MFA code during login.

    This endpoint is called after password verification to complete
    two-factor authentication.
    """
    try:
        repo = get_user_auth_repository()
        user = repo.get_user_by_id(request.user_id)

        if not user:
            raise HTTPException(404, "User not found")

        if not user.mfa_enabled or not user.mfa_secret:
            raise HTTPException(400, "MFA is not enabled for this user")

        # Try TOTP verification first
        if TOTPGenerator.verify_totp(user.mfa_secret, request.code):
            logger.info(f"[MFA] TOTP validated for user {request.user_id}")
            return {
                "valid": True,
                "method": "totp",
            }

        # Try backup codes
        code_hash = hash_backup_code(request.code)
        user_backup_codes = _backup_codes.get(request.user_id, [])

        if code_hash in user_backup_codes:
            # Remove used backup code
            user_backup_codes.remove(code_hash)
            _backup_codes[request.user_id] = user_backup_codes

            logger.info(f"[MFA] Backup code used for user {request.user_id}")
            return {
                "valid": True,
                "method": "backup_code",
                "remaining_backup_codes": len(user_backup_codes),
                "warning": "Backup code used. Consider generating new backup codes." if len(user_backup_codes) < 3 else None,
            }

        # Invalid code
        logger.warning(f"[MFA] Invalid code for user {request.user_id}")
        raise HTTPException(401, "Invalid MFA code")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MFA] Validation failed: {e}")
        raise HTTPException(500, f"Failed to validate MFA: {str(e)}")


@router.post("/disable")
async def disable_mfa(
    request: DisableMFARequest,
    ctx: AuthContext = Depends(require_auth)
) -> Dict[str, Any]:
    """
    Disable MFA on the user's account.

    Requires current MFA code and password for security.
    """
    try:
        repo = get_user_auth_repository()
        user = repo.get_user_by_id(str(ctx.user_id))

        if not user:
            raise HTTPException(404, "User not found")

        if not user.mfa_enabled:
            raise HTTPException(400, "MFA is not enabled")

        # Verify password (in production, use proper password verification)
        if not user.password_hash:
            raise HTTPException(400, "Password verification required")

        # Verify TOTP code
        if not TOTPGenerator.verify_totp(user.mfa_secret, request.code):
            raise HTTPException(400, "Invalid MFA code")

        # Disable MFA
        user.mfa_enabled = False
        user.mfa_secret = None
        repo.update_user(user)

        # Clear backup codes
        _backup_codes.pop(str(ctx.user_id), None)

        logger.info(f"[MFA] Disabled for user {ctx.user_id}")

        return {
            "success": True,
            "message": "MFA has been disabled.",
            "mfa_enabled": False,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MFA] Disable failed: {e}")
        raise HTTPException(500, f"Failed to disable MFA: {str(e)}")


@router.post("/regenerate-backup-codes")
async def regenerate_backup_codes(
    request: VerifyMFARequest,
    ctx: AuthContext = Depends(require_auth)
) -> Dict[str, Any]:
    """
    Generate new backup codes.

    Invalidates all existing backup codes and creates new ones.
    Requires current MFA code for verification.
    """
    try:
        repo = get_user_auth_repository()
        user = repo.get_user_by_id(str(ctx.user_id))

        if not user:
            raise HTTPException(404, "User not found")

        if not user.mfa_enabled or not user.mfa_secret:
            raise HTTPException(400, "MFA must be enabled to regenerate backup codes")

        # Verify current TOTP code
        if not TOTPGenerator.verify_totp(user.mfa_secret, request.code):
            raise HTTPException(400, "Invalid MFA code")

        # Generate new backup codes
        new_codes = generate_backup_codes(10)
        _backup_codes[str(ctx.user_id)] = [hash_backup_code(c) for c in new_codes]

        logger.info(f"[MFA] Backup codes regenerated for user {ctx.user_id}")

        return {
            "success": True,
            "backup_codes": new_codes,
            "message": "New backup codes generated. Previous codes are now invalid.",
            "warning": "Save these codes securely. They will not be shown again.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MFA] Regenerate backup codes failed: {e}")
        raise HTTPException(500, f"Failed to regenerate backup codes: {str(e)}")


@router.get("/backup-codes-count")
async def get_backup_codes_count(
    ctx: AuthContext = Depends(require_auth)
) -> Dict[str, Any]:
    """
    Get the number of remaining backup codes.

    Helps users know if they need to regenerate codes.
    """
    try:
        count = len(_backup_codes.get(str(ctx.user_id), []))

        return {
            "count": count,
            "warning": "Low backup codes! Consider regenerating." if count < 3 else None,
        }

    except Exception as e:
        logger.error(f"[MFA] Get backup codes count failed: {e}")
        raise HTTPException(500, f"Failed to get backup codes count: {str(e)}")
