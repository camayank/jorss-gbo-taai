from src.calculator.engine import FederalTaxEngine
from src.calculator.tax_year_config import TaxYearConfig
from src.models.tax_return import TaxReturn
from src.models.taxpayer import TaxpayerInfo, FilingStatus
from src.models.income import Income
from src.models.deductions import Deductions
from src.models.credits import TaxCredits


def test_self_employment_tax_added_to_total_tax():
    engine = FederalTaxEngine(TaxYearConfig.for_2025())

    tr = TaxReturn(
        tax_year=2025,
        taxpayer=TaxpayerInfo(first_name="A", last_name="B", filing_status=FilingStatus.SINGLE),
        income=Income(self_employment_income=10_000.0, self_employment_expenses=0.0),
        deductions=Deductions(use_standard_deduction=True),
        credits=TaxCredits(),
    )

    breakdown = engine.calculate(tr)
    # SE tax = SS (10,000 * 0.9235 * 0.124 = 1145.14) + Medicare (10,000 * 0.9235 * 0.029 = 267.81) = 1412.95
    # IRS calculates SS and Medicare separately with independent rounding
    assert breakdown.self_employment_tax == 1412.95
    # SE tax is included in total_tax_before_credits (refundable credits may reduce total_tax below SE tax)
    assert breakdown.total_tax_before_credits >= breakdown.self_employment_tax

