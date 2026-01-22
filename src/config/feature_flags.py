"""
Feature Flags Configuration

Allows controlled rollout of the unified tax filing platform.

Usage:
    from src.config.feature_flags import is_enabled

    if is_enabled("unified_filing"):
        # Use new unified flow
    else:
        # Use old fragmented workflows

Environment Variables:
    UNIFIED_FILING=true|false - Enable unified filing flow
    DB_PERSISTENCE=true|false - Use database persistence
    OLD_WORKFLOWS=true|false - Keep old workflows available
    SCENARIOS_ENABLED=true|false - Enable scenario explorer integration
"""

import os
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

# Feature flag definitions
FEATURE_FLAGS: Dict[str, bool] = {
    # === Phase 1: Database Persistence ===
    "database_persistence": os.getenv("DB_PERSISTENCE", "true").lower() == "true",

    # === Phase 2: Permission Fixes ===
    "status_based_permissions": os.getenv("STATUS_PERMISSIONS", "true").lower() == "true",

    # === Phase 3: Unified User Journey ===
    "unified_filing_enabled": os.getenv("UNIFIED_FILING", "true").lower() == "true",
    "new_landing_page": os.getenv("NEW_LANDING", "true").lower() == "true",

    # === Phase 4: Unified API ===
    "unified_api": os.getenv("UNIFIED_API", "true").lower() == "true",

    # === Phase 5: Session Management ===
    "auto_save": os.getenv("AUTO_SAVE", "true").lower() == "true",
    "session_transfer": os.getenv("SESSION_TRANSFER", "true").lower() == "true",

    # === Backward Compatibility ===
    "old_workflows_enabled": os.getenv("OLD_WORKFLOWS", "false").lower() == "true",

    # === Feature Integration ===
    "scenarios_integration": os.getenv("SCENARIOS_ENABLED", "true").lower() == "true",
    "projections_enabled": os.getenv("PROJECTIONS_ENABLED", "true").lower() == "true",

    # === Testing & Development ===
    "debug_mode": os.getenv("DEBUG_MODE", "false").lower() == "true",
    "skip_ocr": os.getenv("SKIP_OCR", "false").lower() == "true",
}


def is_enabled(flag: str) -> bool:
    """
    Check if a feature flag is enabled.

    Args:
        flag: Feature flag name

    Returns:
        True if enabled, False otherwise

    Example:
        >>> is_enabled("unified_filing_enabled")
        True
        >>> is_enabled("old_workflows_enabled")
        False
    """
    enabled = FEATURE_FLAGS.get(flag, False)

    if flag not in FEATURE_FLAGS:
        logger.warning(f"Unknown feature flag: {flag}")

    return enabled


def get_all_flags() -> Dict[str, bool]:
    """
    Get all feature flags and their current values.

    Returns:
        Dict mapping flag names to boolean values
    """
    return FEATURE_FLAGS.copy()


def set_flag(flag: str, enabled: bool) -> None:
    """
    Set a feature flag value at runtime.

    WARNING: This does not persist across restarts.
    Use environment variables for permanent changes.

    Args:
        flag: Feature flag name
        enabled: Whether to enable the flag
    """
    FEATURE_FLAGS[flag] = enabled
    logger.info(f"Feature flag '{flag}' set to {enabled}")


def require_flag(flag: str):
    """
    Decorator to require a feature flag to be enabled.

    Usage:
        @require_flag("unified_filing_enabled")
        @router.get("/file")
        async def unified_filing_page():
            ...

    Args:
        flag: Feature flag name

    Raises:
        HTTPException: 404 if feature is disabled
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            if not is_enabled(flag):
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "FeatureDisabled",
                        "message": f"Feature '{flag}' is not enabled",
                        "flag": flag
                    }
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Rollout configuration
ROLLOUT_CONFIG = {
    # Percentage of users to enable new features for (0-100)
    "unified_filing_rollout_percent": int(os.getenv("UNIFIED_ROLLOUT_PERCENT", "100")),

    # Specific user IDs to always enable (for testing)
    "beta_users": os.getenv("BETA_USERS", "").split(",") if os.getenv("BETA_USERS") else [],

    # Tenant IDs to enable (for multi-tenant deployments)
    "enabled_tenants": os.getenv("ENABLED_TENANTS", "").split(",") if os.getenv("ENABLED_TENANTS") else [],
}


def is_enabled_for_user(flag: str, user_id: str = None) -> bool:
    """
    Check if a feature is enabled for a specific user.

    Supports gradual rollout via percentage and beta user lists.

    Args:
        flag: Feature flag name
        user_id: Optional user identifier

    Returns:
        True if enabled for this user

    Example:
        >>> is_enabled_for_user("unified_filing_enabled", "user123")
        True
    """
    # Check base flag
    if not is_enabled(flag):
        return False

    # If no user ID, just return base flag
    if not user_id:
        return True

    # Check beta users list
    if user_id in ROLLOUT_CONFIG["beta_users"]:
        logger.info(f"Feature '{flag}' enabled for beta user {user_id}")
        return True

    # Check rollout percentage
    rollout_percent = ROLLOUT_CONFIG.get(f"{flag}_rollout_percent",
                                          ROLLOUT_CONFIG.get("unified_filing_rollout_percent", 100))

    if rollout_percent >= 100:
        return True

    if rollout_percent <= 0:
        return False

    # Hash user ID to get consistent assignment
    import hashlib
    user_hash = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
    user_bucket = user_hash % 100

    return user_bucket < rollout_percent


# Migration configuration
MIGRATION_CONFIG = {
    # When to run database migration
    "run_migration_on_startup": os.getenv("RUN_MIGRATION_ON_STARTUP", "false").lower() == "true",

    # Backup database before migration
    "backup_before_migration": os.getenv("BACKUP_BEFORE_MIGRATION", "true").lower() == "true",

    # Fail fast on migration errors
    "fail_on_migration_error": os.getenv("FAIL_ON_MIGRATION_ERROR", "true").lower() == "true",
}


def log_feature_flags():
    """Log all feature flags at startup for debugging."""
    logger.info("=== Feature Flags Configuration ===")
    for flag, enabled in sorted(FEATURE_FLAGS.items()):
        logger.info(f"  {flag}: {'✓ enabled' if enabled else '✗ disabled'}")
    logger.info(f"=== Rollout: {ROLLOUT_CONFIG['unified_filing_rollout_percent']}% ===")


# Log flags on import
if os.getenv("LOG_FEATURE_FLAGS", "true").lower() == "true":
    log_feature_flags()
