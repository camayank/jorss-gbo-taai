"""
Shared pytest fixtures for tax matrix tests.

Helper functions and constants are in _helpers.py.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from calculator.tax_calculator import TaxCalculator
from calculator.engine import FederalTaxEngine
from calculator.tax_year_config import TaxYearConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def calculator():
    """Return a TaxCalculator using 2025 config."""
    return TaxCalculator(config=TaxYearConfig.for_2025(), include_state=False)


@pytest.fixture
def calculator_with_state():
    """Return a TaxCalculator with state tax enabled."""
    return TaxCalculator(config=TaxYearConfig.for_2025(), include_state=True)


@pytest.fixture
def federal_engine():
    """Return a FederalTaxEngine using 2025 config."""
    return FederalTaxEngine(config=TaxYearConfig.for_2025())


@pytest.fixture
def config():
    """Return the 2025 TaxYearConfig."""
    return TaxYearConfig.for_2025()
