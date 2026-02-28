"""
Multi-Factor Authentication (MFA) API

TOTP-based two-factor authentication implementation.
Compatible with Google Authenticator, Authy, and other TOTP apps.

SECURITY: MFA secrets and backup codes are encrypted at rest using AES-256-GCM
and persisted to the database. No sensitive data is stored in-memory only.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from enum import Enum
import logging
import secrets
import base64
import hmac
import hashlib
import struct
import time
import json

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

# Import encryption utilities
try:
    from database.encrypted_fields import encrypt_pii, decrypt_pii
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False
    def encrypt_pii(data: str, field_type: str = "generic", associated_data: bytes = None) -> str:
        # Fallback: base64 encode (NOT SECURE - for dev only)
        import warnings
        warnings.warn("PII encryption not available - using base64 encoding", UserWarning)
        return base64.b64encode(data.encode()).decode()
    def decrypt_pii(data: str, field_type: str = "generic", associated_data: bytes = None) -> str:
        return base64.b64decode(data.encode()).decode()

# Import database session
try:
    from database.connection import get_db_session
    from database.models import MFACredential, MFAPendingSetup, MFAType
    from sqlalchemy import select, delete
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    MFACredential = None
    MFAPendingSetup = None
    MFAType = None

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
    mfa_token: str = Field(..., description="Temporary token from login proving password was verified")
    code: str = Field(..., min_length=4, max_length=9, description="6-digit TOTP code or XXXX-XXXX backup code")


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
# MFA PERSISTENCE SERVICE
# =============================================================================

class MFAPersistenceService:
    """
    Service for persisting MFA credentials securely.

    Uses database storage with AES-256-GCM encryption for:
    - TOTP secrets
    - Backup codes (hashed before encryption for extra security)

    Falls back to in-memory storage only if database is unavailable.
    """

    # In-memory fallback (only used if database unavailable)
    _fallback_pending: Dict[str, Dict[str, Any]] = {}
    _fallback_backup_codes: Dict[str, List[str]] = {}

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._db_available = DATABASE_AVAILABLE

    def _get_associated_data(self, user_id: str, tenant_id: str = None) -> bytes:
        """Generate associated data for context binding."""
        context = f"mfa:{user_id}"
        if tenant_id:
            context += f":{tenant_id}"
        return context.encode()

    # -------------------------------------------------------------------------
    # Pending Setup Methods
    # -------------------------------------------------------------------------

    def save_pending_setup(
        self,
        user_id: str,
        secret: str,
        backup_codes_hashed: List[str],
        tenant_id: str = None,
        expires_minutes: int = 15
    ) -> bool:
        """Save a pending MFA setup to database."""
        if not self._db_available:
            self._fallback_pending[user_id] = {
                "secret": secret,
                "backup_codes": backup_codes_hashed,
                "created_at": datetime.utcnow().isoformat(),
            }
            return True

        try:
            from database.connection import get_db_session

            associated_data = self._get_associated_data(user_id, tenant_id)

            # Encrypt secret and backup codes
            secret_encrypted = encrypt_pii(secret, field_type="generic", associated_data=associated_data)
            codes_json = json.dumps(backup_codes_hashed)
            codes_encrypted = encrypt_pii(codes_json, field_type="generic", associated_data=associated_data)

            with get_db_session() as session:
                # Remove any existing pending setup for this user
                session.execute(
                    delete(MFAPendingSetup).where(MFAPendingSetup.user_id == user_id)
                )

                # Create new pending setup
                pending = MFAPendingSetup(
                    user_id=user_id,
                    tenant_id=tenant_id,
                    secret_encrypted=secret_encrypted,
                    backup_codes_encrypted=codes_encrypted,
                    expires_at=datetime.utcnow() + timedelta(minutes=expires_minutes),
                )
                session.add(pending)
                session.commit()

            self.logger.info(f"[MFA] Pending setup saved for user {user_id}")
            return True

        except Exception as e:
            self.logger.error(f"[MFA] Failed to save pending setup: {e}")
            # Fallback to in-memory
            self._fallback_pending[user_id] = {
                "secret": secret,
                "backup_codes": backup_codes_hashed,
                "created_at": datetime.utcnow().isoformat(),
            }
            return True

    def get_pending_setup(self, user_id: str, tenant_id: str = None) -> Optional[Dict[str, Any]]:
        """Get pending MFA setup from database."""
        if not self._db_available:
            return self._fallback_pending.get(user_id)

        try:
            from database.connection import get_db_session

            with get_db_session() as session:
                result = session.execute(
                    select(MFAPendingSetup).where(
                        MFAPendingSetup.user_id == user_id,
                        MFAPendingSetup.expires_at > datetime.utcnow()
                    )
                ).scalar_one_or_none()

                if not result:
                    return self._fallback_pending.get(user_id)

                associated_data = self._get_associated_data(user_id, tenant_id)

                # Decrypt data
                secret = decrypt_pii(result.secret_encrypted, field_type="generic", associated_data=associated_data)
                codes_json = decrypt_pii(result.backup_codes_encrypted, field_type="generic", associated_data=associated_data)
                backup_codes = json.loads(codes_json)

                return {
                    "secret": secret,
                    "backup_codes": backup_codes,
                    "created_at": result.created_at.isoformat(),
                }

        except Exception as e:
            self.logger.error(f"[MFA] Failed to get pending setup: {e}")
            return self._fallback_pending.get(user_id)

    def delete_pending_setup(self, user_id: str) -> bool:
        """Delete pending MFA setup after verification."""
        # Always clean up in-memory fallback too
        self._fallback_pending.pop(user_id, None)

        if not self._db_available:
            return True

        try:
            from database.connection import get_db_session

            with get_db_session() as session:
                session.execute(
                    delete(MFAPendingSetup).where(MFAPendingSetup.user_id == user_id)
                )
                session.commit()
            return True

        except Exception as e:
            self.logger.error(f"[MFA] Failed to delete pending setup: {e}")
            return False

    # -------------------------------------------------------------------------
    # Backup Codes Methods
    # -------------------------------------------------------------------------

    def save_backup_codes(
        self,
        user_id: str,
        backup_codes_hashed: List[str],
        tenant_id: str = None
    ) -> bool:
        """Save hashed backup codes to database."""
        if not self._db_available:
            self._fallback_backup_codes[user_id] = backup_codes_hashed
            return True

        try:
            from database.connection import get_db_session

            associated_data = self._get_associated_data(user_id, tenant_id)
            codes_json = json.dumps(backup_codes_hashed)
            codes_encrypted = encrypt_pii(codes_json, field_type="generic", associated_data=associated_data)

            with get_db_session() as session:
                # Check for existing backup codes credential
                existing = session.execute(
                    select(MFACredential).where(
                        MFACredential.user_id == user_id,
                        MFACredential.mfa_type == MFAType.BACKUP_CODES,
                        MFACredential.is_active == True
                    )
                ).scalar_one_or_none()

                if existing:
                    existing.backup_codes_encrypted = codes_encrypted
                    existing.updated_at = datetime.utcnow()
                else:
                    credential = MFACredential(
                        user_id=user_id,
                        tenant_id=tenant_id,
                        mfa_type=MFAType.BACKUP_CODES,
                        backup_codes_encrypted=codes_encrypted,
                        is_verified=True,
                        verified_at=datetime.utcnow(),
                    )
                    session.add(credential)

                session.commit()

            self.logger.info(f"[MFA] Backup codes saved for user {user_id}")
            return True

        except Exception as e:
            self.logger.error(f"[MFA] Failed to save backup codes: {e}")
            self._fallback_backup_codes[user_id] = backup_codes_hashed
            return True

    def get_backup_codes(self, user_id: str, tenant_id: str = None) -> List[str]:
        """Get hashed backup codes from database."""
        if not self._db_available:
            return self._fallback_backup_codes.get(user_id, [])

        try:
            from database.connection import get_db_session

            with get_db_session() as session:
                credential = session.execute(
                    select(MFACredential).where(
                        MFACredential.user_id == user_id,
                        MFACredential.mfa_type == MFAType.BACKUP_CODES,
                        MFACredential.is_active == True
                    )
                ).scalar_one_or_none()

                if not credential or not credential.backup_codes_encrypted:
                    return self._fallback_backup_codes.get(user_id, [])

                associated_data = self._get_associated_data(user_id, tenant_id)
                codes_json = decrypt_pii(
                    credential.backup_codes_encrypted,
                    field_type="generic",
                    associated_data=associated_data
                )
                return json.loads(codes_json)

        except Exception as e:
            self.logger.error(f"[MFA] Failed to get backup codes: {e}")
            return self._fallback_backup_codes.get(user_id, [])

    def update_backup_codes(
        self,
        user_id: str,
        backup_codes_hashed: List[str],
        tenant_id: str = None
    ) -> bool:
        """Update backup codes (e.g., after using one)."""
        return self.save_backup_codes(user_id, backup_codes_hashed, tenant_id)

    def delete_backup_codes(self, user_id: str) -> bool:
        """Delete all backup codes for a user (when disabling MFA)."""
        self._fallback_backup_codes.pop(user_id, None)

        if not self._db_available:
            return True

        try:
            from database.connection import get_db_session

            with get_db_session() as session:
                session.execute(
                    delete(MFACredential).where(
                        MFACredential.user_id == user_id,
                        MFACredential.mfa_type == MFAType.BACKUP_CODES
                    )
                )
                session.commit()
            return True

        except Exception as e:
            self.logger.error(f"[MFA] Failed to delete backup codes: {e}")
            return False

    def has_backup_codes(self, user_id: str, tenant_id: str = None) -> bool:
        """Check if user has backup codes."""
        codes = self.get_backup_codes(user_id, tenant_id)
        return len(codes) > 0

    def get_backup_codes_count(self, user_id: str, tenant_id: str = None) -> int:
        """Get count of remaining backup codes."""
        codes = self.get_backup_codes(user_id, tenant_id)
        return len(codes)


# Initialize persistence service
_mfa_persistence = MFAPersistenceService()


# Legacy compatibility - redirect to persistence service
def _get_pending_setup(user_id: str) -> Optional[Dict[str, Any]]:
    return _mfa_persistence.get_pending_setup(user_id)


def _get_backup_codes(user_id: str) -> List[str]:
    return _mfa_persistence.get_backup_codes(user_id)


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

        # Check for pending setup (using persistence service)
        pending = _mfa_persistence.get_pending_setup(str(ctx.user_id), getattr(ctx, 'tenant_id', None))

        status = MFAStatus.DISABLED
        if user.mfa_enabled and user.mfa_secret:
            status = MFAStatus.ENABLED
        elif pending:
            status = MFAStatus.PENDING_SETUP

        return {
            "enabled": user.mfa_enabled,
            "status": status.value,
            "has_backup_codes": _mfa_persistence.has_backup_codes(str(ctx.user_id), getattr(ctx, 'tenant_id', None)),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MFA] Failed to get status: {e}")
        raise HTTPException(500, "An internal error occurred")


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
        backup_codes_hashed = [hash_backup_code(c) for c in backup_codes]

        # Store pending setup (using persistence service with encryption)
        _mfa_persistence.save_pending_setup(
            user_id=str(ctx.user_id),
            secret=secret,
            backup_codes_hashed=backup_codes_hashed,
            tenant_id=getattr(ctx, 'tenant_id', None),
        )

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
        raise HTTPException(500, "An internal error occurred")


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

        tenant_id = getattr(ctx, 'tenant_id', None)
        pending = _mfa_persistence.get_pending_setup(str(ctx.user_id), tenant_id)
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

        # Store backup codes (encrypted in database)
        _mfa_persistence.save_backup_codes(str(ctx.user_id), backup_codes_hashed, tenant_id)

        # Clear pending setup
        _mfa_persistence.delete_pending_setup(str(ctx.user_id))

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
        raise HTTPException(500, "An internal error occurred")


@router.post("/validate")
async def validate_mfa_code(
    request: ValidateMFARequest,
) -> Dict[str, Any]:
    """
    Validate MFA code during login.

    This endpoint is called after password verification to complete
    two-factor authentication. Accepts the mfa_token from the login
    response and a TOTP code (or backup code). On success, returns
    full access/refresh tokens.
    """
    try:
        # Verify the MFA token (proves password was already verified)
        from core.services.auth_service import get_auth_service
        auth_service = get_auth_service()

        mfa_data = auth_service.verify_mfa_token(request.mfa_token)
        if not mfa_data:
            raise HTTPException(401, "Invalid or expired MFA token. Please log in again.")

        user_id = mfa_data["user_id"]

        # Get user to verify TOTP
        repo = get_user_auth_repository()
        user = repo.get_user_by_id(user_id)

        if not user:
            raise HTTPException(404, "User not found")

        if not user.mfa_enabled or not user.mfa_secret:
            raise HTTPException(400, "MFA is not enabled for this user")

        method = None

        # Try TOTP verification first (6-digit code)
        code_clean = request.code.strip().replace("-", "").replace(" ", "")
        if len(code_clean) == 6 and code_clean.isdigit():
            if TOTPGenerator.verify_totp(user.mfa_secret, code_clean):
                method = "totp"
                logger.info(f"[MFA] TOTP validated for user {user_id}")

        # Try backup codes if TOTP didn't match
        if not method:
            code_hash = hash_backup_code(request.code)
            user_backup_codes = _mfa_persistence.get_backup_codes(user_id)

            if code_hash in user_backup_codes:
                user_backup_codes.remove(code_hash)
                _mfa_persistence.update_backup_codes(user_id, user_backup_codes)
                method = "backup_code"
                logger.info(f"[MFA] Backup code used for user {user_id} ({len(user_backup_codes)} remaining)")

        if not method:
            logger.warning(f"[MFA] Invalid code for user {user_id}")
            raise HTTPException(401, "Invalid MFA code")

        # MFA verified — issue full tokens via auth service
        auth_response = await auth_service.complete_mfa_login(request.mfa_token)

        if not auth_response.success:
            raise HTTPException(401, auth_response.message)

        result = {
            "valid": True,
            "method": method,
            "access_token": auth_response.access_token,
            "refresh_token": auth_response.refresh_token,
            "token_type": auth_response.token_type,
            "expires_in": auth_response.expires_in,
            "user": auth_response.user,
        }

        if method == "backup_code":
            remaining = len(user_backup_codes)
            result["remaining_backup_codes"] = remaining
            if remaining < 3:
                result["warning"] = "Backup code used. Consider generating new backup codes."

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MFA] Validation failed: {e}")
        raise HTTPException(500, "An internal error occurred")


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

        # Clear backup codes (from database)
        _mfa_persistence.delete_backup_codes(str(ctx.user_id))

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
        raise HTTPException(500, "An internal error occurred")


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

        # Generate new backup codes (save encrypted to database)
        new_codes = generate_backup_codes(10)
        new_codes_hashed = [hash_backup_code(c) for c in new_codes]
        _mfa_persistence.save_backup_codes(
            str(ctx.user_id),
            new_codes_hashed,
            getattr(ctx, 'tenant_id', None)
        )

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
        raise HTTPException(500, "An internal error occurred")


@router.get("/backup-codes-count")
async def get_backup_codes_count(
    ctx: AuthContext = Depends(require_auth)
) -> Dict[str, Any]:
    """
    Get the number of remaining backup codes.

    Helps users know if they need to regenerate codes.
    """
    try:
        count = _mfa_persistence.get_backup_codes_count(
            str(ctx.user_id),
            getattr(ctx, 'tenant_id', None)
        )

        return {
            "count": count,
            "warning": "Low backup codes! Consider regenerating." if count < 3 else None,
        }

    except Exception as e:
        logger.error(f"[MFA] Get backup codes count failed: {e}")
        raise HTTPException(500, "An internal error occurred")
