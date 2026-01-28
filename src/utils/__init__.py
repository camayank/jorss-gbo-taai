"""
Utilities Module

Common utility functions and classes for the tax platform.
"""

from utils.logo_handler import (
    LogoHandler,
    LogoValidationResult,
    LogoMetadata,
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE,
)

from utils.rate_limiter import (
    RateLimiter,
    RateLimitConfig,
    RateLimitExceeded,
    RateLimitState,
    pdf_rate_limiter,
    report_rate_limiter,
    global_pdf_limiter,
)

from utils.cpa_branding_helper import (
    get_cpa_branding_for_report,
)

__all__ = [
    # Logo handler
    "LogoHandler",
    "LogoValidationResult",
    "LogoMetadata",
    "ALLOWED_EXTENSIONS",
    "MAX_FILE_SIZE",
    # Rate limiter
    "RateLimiter",
    "RateLimitConfig",
    "RateLimitExceeded",
    "RateLimitState",
    "pdf_rate_limiter",
    "report_rate_limiter",
    "global_pdf_limiter",
    # CPA branding
    "get_cpa_branding_for_report",
]
