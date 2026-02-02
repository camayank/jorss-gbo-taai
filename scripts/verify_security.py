#!/usr/bin/env python3
"""
Security Configuration Verification Script

Verifies that all security configurations are properly set up:
- Environment variables
- Authentication enforcement
- CSRF protection
- CSP headers
- SSN hashing
- Input validation

Usage:
    python scripts/verify_security.py [--production]

Options:
    --production    Run verification in production mode (stricter checks)

Exit codes:
    0 - All checks passed
    1 - Some checks failed (warnings only)
    2 - Critical checks failed (production blockers)
"""

import os
import sys
import argparse
from typing import List, Tuple

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class SecurityChecker:
    """Security configuration checker."""

    def __init__(self, production_mode: bool = False):
        self.production_mode = production_mode
        self.results: List[Tuple[str, str, str]] = []  # (name, status, message)
        self.critical_failures = 0
        self.warnings = 0

    def check(self, name: str, check_func, critical: bool = False):
        """Run a check and record the result."""
        try:
            passed, message = check_func()
            if passed:
                self.results.append((name, "PASS", message))
            elif critical and self.production_mode:
                self.results.append((name, "FAIL", message))
                self.critical_failures += 1
            else:
                self.results.append((name, "WARN", message))
                self.warnings += 1
        except Exception as e:
            self.results.append((name, "ERROR", str(e)))
            if critical and self.production_mode:
                self.critical_failures += 1
            else:
                self.warnings += 1

    def print_results(self):
        """Print verification results."""
        print("\n" + "=" * 70)
        print("SECURITY CONFIGURATION VERIFICATION")
        print("=" * 70)
        print(f"Mode: {'PRODUCTION' if self.production_mode else 'DEVELOPMENT'}")
        print("=" * 70 + "\n")

        for name, status, message in self.results:
            if status == "PASS":
                icon = "\033[92m\u2714\033[0m"  # Green check
            elif status == "FAIL":
                icon = "\033[91m\u2718\033[0m"  # Red X
            elif status == "WARN":
                icon = "\033[93m\u26A0\033[0m"  # Yellow warning
            else:
                icon = "\033[91m!\033[0m"  # Red exclamation

            print(f"{icon} [{status}] {name}")
            print(f"   {message}\n")

        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"  Passed: {sum(1 for r in self.results if r[1] == 'PASS')}")
        print(f"  Warnings: {self.warnings}")
        print(f"  Critical Failures: {self.critical_failures}")

        if self.critical_failures > 0:
            print("\n\033[91mCRITICAL: Application cannot start in production!\033[0m")
            return 2
        elif self.warnings > 0:
            print("\n\033[93mWARNING: Some security configurations need attention.\033[0m")
            return 1
        else:
            print("\n\033[92mAll security checks passed!\033[0m")
            return 0


def check_app_secret_key():
    """Check APP_SECRET_KEY is set and strong."""
    secret = os.environ.get("APP_SECRET_KEY", "")
    if not secret:
        return False, "APP_SECRET_KEY not set"
    if "INSECURE" in secret or secret == "change-me-in-production":
        return False, "APP_SECRET_KEY has insecure default value"
    if len(secret) < 32:
        return False, f"APP_SECRET_KEY too short ({len(secret)} chars, need 32+)"
    return True, f"APP_SECRET_KEY is set ({len(secret)} chars)"


def check_jwt_secret():
    """Check JWT_SECRET is set and strong."""
    secret = os.environ.get("JWT_SECRET", "")
    if not secret:
        return False, "JWT_SECRET not set"
    if len(secret) < 32:
        return False, f"JWT_SECRET too short ({len(secret)} chars, need 32+)"
    return True, f"JWT_SECRET is set ({len(secret)} chars)"


def check_csrf_secret():
    """Check CSRF_SECRET_KEY is set and strong."""
    secret = os.environ.get("CSRF_SECRET_KEY", "")
    if not secret:
        return False, "CSRF_SECRET_KEY not set"
    if len(secret) < 32:
        return False, f"CSRF_SECRET_KEY too short ({len(secret)} chars, need 32+)"
    return True, f"CSRF_SECRET_KEY is set ({len(secret)} chars)"


def check_ssn_hash_secret():
    """Check SSN_HASH_SECRET is set and strong."""
    secret = os.environ.get("SSN_HASH_SECRET", "")
    if not secret:
        return False, "SSN_HASH_SECRET not set"
    if len(secret) < 32:
        return False, f"SSN_HASH_SECRET too short ({len(secret)} chars, need 32+)"
    return True, f"SSN_HASH_SECRET is set ({len(secret)} chars)"


def check_encryption_key():
    """Check ENCRYPTION_MASTER_KEY is set and strong."""
    secret = os.environ.get("ENCRYPTION_MASTER_KEY", "")
    if not secret:
        return False, "ENCRYPTION_MASTER_KEY not set"
    if len(secret) < 32:
        return False, f"ENCRYPTION_MASTER_KEY too short ({len(secret)} chars, need 32+)"
    return True, f"ENCRYPTION_MASTER_KEY is set ({len(secret)} chars)"


def check_auth_secret():
    """Check AUTH_SECRET_KEY is set and strong."""
    secret = os.environ.get("AUTH_SECRET_KEY", "")
    if not secret:
        return False, "AUTH_SECRET_KEY not set"
    if len(secret) < 32:
        return False, f"AUTH_SECRET_KEY too short ({len(secret)} chars, need 32+)"
    return True, f"AUTH_SECRET_KEY is set ({len(secret)} chars)"


def check_password_salt():
    """Check PASSWORD_SALT is set and strong."""
    salt = os.environ.get("PASSWORD_SALT", "")
    if not salt:
        return False, "PASSWORD_SALT not set"
    if len(salt) < 16:
        return False, f"PASSWORD_SALT too short ({len(salt)} chars, need 16+)"
    return True, f"PASSWORD_SALT is set ({len(salt)} chars)"


def check_environment():
    """Check APP_ENVIRONMENT is set correctly."""
    env = os.environ.get("APP_ENVIRONMENT", "")
    if not env:
        return False, "APP_ENVIRONMENT not set (defaults to 'development')"
    if env.lower() in ("production", "prod", "staging"):
        return True, f"APP_ENVIRONMENT is '{env}' (production mode)"
    return True, f"APP_ENVIRONMENT is '{env}' (development mode)"


def check_https_enforcement():
    """Check HTTPS enforcement is enabled."""
    enforce = os.environ.get("APP_ENFORCE_HTTPS", "").lower() == "true"
    if enforce:
        return True, "HTTPS enforcement enabled"
    return False, "HTTPS enforcement disabled (APP_ENFORCE_HTTPS != true)"


def check_auth_decorators():
    """Verify auth decorators use fail-closed logic."""
    try:
        from security.auth_decorators import _DEV_ENVIRONMENTS, _determine_enforcement

        # Verify dev environments are properly defined
        expected = {"development", "dev", "local", "test", "testing"}
        if _DEV_ENVIRONMENTS != expected:
            return False, f"Unexpected dev environments: {_DEV_ENVIRONMENTS}"

        # Verify unknown environments enforce auth
        os.environ["APP_ENVIRONMENT"] = "unknown_env"
        result = _determine_enforcement(None, "test")
        if not result:
            return False, "Unknown environment does not enforce auth (fail-open)"

        return True, "Auth decorators use fail-closed logic"
    except ImportError as e:
        return False, f"Cannot import auth_decorators: {e}"
    finally:
        # Restore environment
        os.environ.pop("APP_ENVIRONMENT", None)


def check_security_middleware():
    """Verify security middleware is properly configured."""
    try:
        from security.middleware import SecurityHeadersMiddleware

        # Check nonce generation works
        mw = SecurityHeadersMiddleware(None)
        nonce = mw._generate_nonce()
        if len(nonce) < 20:
            return False, "CSP nonce generation produces weak nonces"

        # Check CSP includes nonce
        csp = mw._build_csp(nonce)
        if f"nonce-{nonce}" not in csp:
            return False, "CSP does not include nonce for scripts"

        return True, "Security middleware properly configured with nonce-based CSP"
    except ImportError as e:
        return False, f"Cannot import security middleware: {e}"


def check_ssn_hashing():
    """Verify SSN hashing uses HMAC-SHA256."""
    try:
        from security.ssn_hash import secure_hash_ssn, legacy_hash_ssn

        test_ssn = "123-45-6789"
        secure = secure_hash_ssn(test_ssn)
        legacy = legacy_hash_ssn(test_ssn)

        # Hashes should be different (HMAC vs plain SHA256)
        if secure == legacy:
            return False, "Secure hash equals legacy hash (not using HMAC)"

        return True, "SSN hashing uses HMAC-SHA256"
    except ImportError as e:
        return False, f"Cannot import ssn_hash: {e}"


def check_input_validation():
    """Verify input validation module is available."""
    try:
        from security.validation import (
            sanitize_string,
            sanitize_ssn,
            sanitize_email,
            validate_tax_return_data,
        )

        # Test XSS prevention
        result = sanitize_string("<script>alert('xss')</script>")
        if "<script>" in result:
            return False, "XSS sanitization not working"

        # Test SSN validation
        result = sanitize_ssn("000-00-0000")  # Invalid SSN
        if result is not None:
            return False, "SSN validation allows invalid SSNs"

        return True, "Input validation module properly configured"
    except ImportError as e:
        return False, f"Cannot import validation: {e}"


def check_csrf_protection():
    """Verify CSRF protection is configured."""
    try:
        from security.middleware import CSRFMiddleware

        # Check middleware exists and has required methods
        if not hasattr(CSRFMiddleware, 'generate_token'):
            return False, "CSRFMiddleware missing generate_token method"

        return True, "CSRF protection middleware available"
    except ImportError as e:
        return False, f"Cannot import CSRF middleware: {e}"


def main():
    """Run security verification."""
    parser = argparse.ArgumentParser(description="Verify security configuration")
    parser.add_argument(
        "--production",
        action="store_true",
        help="Run in production mode (stricter checks)"
    )
    args = parser.parse_args()

    # Detect production from environment if not specified
    production_mode = args.production or os.environ.get(
        "APP_ENVIRONMENT", ""
    ).lower() in ("production", "prod", "staging")

    checker = SecurityChecker(production_mode=production_mode)

    # Critical environment variables
    checker.check("APP_SECRET_KEY", check_app_secret_key, critical=True)
    checker.check("JWT_SECRET", check_jwt_secret, critical=True)
    checker.check("CSRF_SECRET_KEY", check_csrf_secret, critical=True)
    checker.check("SSN_HASH_SECRET", check_ssn_hash_secret, critical=True)
    checker.check("ENCRYPTION_MASTER_KEY", check_encryption_key, critical=True)
    checker.check("AUTH_SECRET_KEY", check_auth_secret, critical=True)
    checker.check("PASSWORD_SALT", check_password_salt, critical=True)

    # Environment configuration
    checker.check("APP_ENVIRONMENT", check_environment, critical=False)
    checker.check("HTTPS Enforcement", check_https_enforcement, critical=False)

    # Security modules
    checker.check("Auth Decorators (Fail-Closed)", check_auth_decorators, critical=True)
    checker.check("Security Middleware (CSP)", check_security_middleware, critical=True)
    checker.check("SSN Hashing (HMAC-SHA256)", check_ssn_hashing, critical=True)
    checker.check("Input Validation", check_input_validation, critical=True)
    checker.check("CSRF Protection", check_csrf_protection, critical=True)

    # Print results and exit
    exit_code = checker.print_results()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
