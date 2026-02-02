"""Pytest configuration for security tests."""

import sys
import os
from pathlib import Path

import pytest

# Add src to path for security module imports
_src_path = str(Path(__file__).parent.parent.parent / "src")
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

# =============================================================================
# CSRF BYPASS HELPERS FOR TESTING (duplicated from parent conftest)
# =============================================================================
# These are duplicated here because pytest may load this conftest first
# when tests import from conftest directly.

CSRF_BYPASS_HEADERS = {
    "Authorization": "Bearer test_token_for_csrf_bypass",
    "Origin": "http://localhost:8000",
}


@pytest.fixture
def csrf_headers():
    """Provide headers that bypass CSRF protection for testing."""
    return CSRF_BYPASS_HEADERS.copy()
