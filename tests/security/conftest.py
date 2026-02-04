"""Pytest configuration for security tests."""

import sys
import os
from pathlib import Path

import pytest

# Add src to path for security module imports
_src_path = str(Path(__file__).parent.parent.parent / "src")
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

# CSRF headers inherited from parent conftest via pytest fixture inheritance.
# No need to redefine CSRF_BYPASS_HEADERS or csrf_headers fixture here.
