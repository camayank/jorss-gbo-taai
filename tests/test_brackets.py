from src.calculator.engine import FederalTaxEngine
from src.calculator.tax_year_config import TaxYearConfig


def test_ordinary_income_tax_single_basic():
    engine = FederalTaxEngine(TaxYearConfig.for_2025())

    # $10,000 taxable income @ 10%
    tax = engine._compute_ordinary_income_tax(10_000.0, "single")
    assert tax == 1000.0


def test_ordinary_income_tax_single_crosses_bracket():
    engine = FederalTaxEngine(TaxYearConfig.for_2025())

    # Taxable income = 20,000
    # 10% on first 11,925 = 1,192.50
    # 12% on remaining 8,075 = 969.00
    # total = 2,161.50
    tax = engine._compute_ordinary_income_tax(20_000.0, "single")
    assert tax == 2161.5


def test_ordinary_income_tax_mfj_crosses_bracket():
    engine = FederalTaxEngine(TaxYearConfig.for_2025())

    # MFJ taxable income 30,000
    # 10% on first 23,850 = 2,385.00
    # 12% on remaining 6,150 = 738.00
    tax = engine._compute_ordinary_income_tax(30_000.0, "married_joint")
    assert tax == 3123.0

