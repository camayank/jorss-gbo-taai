"""
Root pytest configuration.

This conftest is loaded before test collection to ensure
src is in the Python path for all imports.
"""

import sys
from pathlib import Path

# Add src to path IMMEDIATELY when this file is loaded
src_path = Path(__file__).parent / "src"
src_str = str(src_path.absolute())

# Ensure it's at the very front
if src_str in sys.path:
    sys.path.remove(src_str)
sys.path.insert(0, src_str)


import pytest


@pytest.fixture(autouse=True)
def _reset_service_registry():
    """Reset the service registry between tests for isolation."""
    yield
    try:
        from core.service_registry import services
        services.reset_all()
    except ImportError:
        pass


def pytest_configure(config):
    """Additional path setup during pytest configuration."""
    # Double-check the path is set
    if src_str not in sys.path:
        sys.path.insert(0, src_str)
