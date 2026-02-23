"""
Tests for EITC phase-in calculation per IRS Pub. 596.
"""

import pytest
from calculator.tax_year_config import TaxYearConfig
from models.income import Income, W2Info
from models.tax_return import TaxReturn
from models.taxpayer import TaxpayerInfo, FilingStatus
from models.deductions import Deductions
from models.credits import TaxCredits
from calculator.engine import FederalTaxEngine


def make_w2(wages: float, federal_withheld: float = 0.0) -> W2Info:
    """Helper to create W2Info for tests."""
    return W2Info(
        employer_name="Test Employer",
        wages=wages,
        federal_tax_withheld=federal_withheld,
    )


def create_eitc_return(
    wages: float,
    filing_status: FilingStatus = FilingStatus.SINGLE,
    num_children: int = 0,
) -> TaxReturn:
    """Helper to create TaxReturn for EITC testing."""
    return TaxReturn(
        tax_year=2025,
        taxpayer=TaxpayerInfo(
            first_name="Test",
            last_name="Taxpayer",
            filing_status=filing_status,
            primary_ssn="123-45-6789",
        ),
        income=Income(
            w2_forms=[make_w2(wages, wages * 0.15)] if wages > 0 else [],
        ),
        deductions=Deductions(use_standard_deduction=True),
        credits=TaxCredits(child_tax_credit_children=num_children),
    )


class TestEitcPhaseInConfig:
    """Test EITC phase-in configuration exists in TaxYearConfig."""

    def test_config_has_phase_in_rate(self):
        """Config should have phase-in rates by number of children."""
        config = TaxYearConfig.for_2025()
        assert config.eitc_phase_in_rate is not None
        assert 0 in config.eitc_phase_in_rate
        assert 1 in config.eitc_phase_in_rate
        assert 2 in config.eitc_phase_in_rate
        assert 3 in config.eitc_phase_in_rate

    def test_config_has_phase_in_end(self):
        """Config should have phase-in end thresholds by children."""
        config = TaxYearConfig.for_2025()
        assert config.eitc_phase_in_end is not None
        assert 0 in config.eitc_phase_in_end
        assert 1 in config.eitc_phase_in_end
        assert 2 in config.eitc_phase_in_end
        assert 3 in config.eitc_phase_in_end

    def test_phase_in_rate_values_per_pub_596(self):
        """Phase-in rates should match IRS Pub. 596."""
        config = TaxYearConfig.for_2025()
        assert config.eitc_phase_in_rate[0] == pytest.approx(0.0765, rel=1e-4)
        assert config.eitc_phase_in_rate[1] == pytest.approx(0.34, rel=1e-4)
        assert config.eitc_phase_in_rate[2] == pytest.approx(0.40, rel=1e-4)
        assert config.eitc_phase_in_rate[3] == pytest.approx(0.45, rel=1e-4)

    def test_phase_in_end_values_per_pub_596(self):
        """Phase-in end thresholds should match IRS Pub. 596."""
        config = TaxYearConfig.for_2025()
        assert config.eitc_phase_in_end[0] == pytest.approx(8490.0, rel=1e-2)
        assert config.eitc_phase_in_end[1] == pytest.approx(12730.0, rel=1e-2)
        assert config.eitc_phase_in_end[2] == pytest.approx(17880.0, rel=1e-2)
        assert config.eitc_phase_in_end[3] == pytest.approx(17880.0, rel=1e-2)


class TestEitcPhaseInCalculation:
    """Test EITC phase-in calculation in engine."""

    def test_zero_income_zero_credit(self):
        """Zero earned income should result in $0 EITC."""
        tax_return = create_eitc_return(wages=0, num_children=1)
        engine = FederalTaxEngine()
        eitc = engine._calculate_eitc(tax_return, "single")
        assert eitc == 0.0

    def test_phase_in_no_children_low_income(self):
        """Test phase-in for no children at $4,000 earned income."""
        # $4,000 x 7.65% = $306 (below max of $649)
        tax_return = create_eitc_return(wages=4000, num_children=0)
        engine = FederalTaxEngine()
        eitc = engine._calculate_eitc(tax_return, "single")
        assert eitc == pytest.approx(306.0, rel=0.01)

    def test_phase_in_one_child_low_income(self):
        """Test phase-in for 1 child at $6,000 earned income."""
        # $6,000 x 34% = $2,040 (below max of $4,328)
        tax_return = create_eitc_return(wages=6000, num_children=1)
        engine = FederalTaxEngine()
        eitc = engine._calculate_eitc(tax_return, "single")
        assert eitc == pytest.approx(2040.0, rel=0.01)

    def test_phase_in_reaches_max_at_threshold(self):
        """At phase-in end, credit should equal max."""
        # 1 child: At $12,730 x 34% = $4,328.20, capped at max $4,328
        tax_return = create_eitc_return(wages=12730, num_children=1)
        engine = FederalTaxEngine()
        eitc = engine._calculate_eitc(tax_return, "single")
        assert eitc == pytest.approx(4328.0, rel=0.01)

    def test_plateau_gets_max_credit(self):
        """Income in plateau range should get max credit."""
        # 0 children: Phase-in ends at $8,490, phaseout starts at $9,950
        # At $9,000 (between phase-in end and phaseout start), should get max $649
        tax_return = create_eitc_return(wages=9000, num_children=0)
        engine = FederalTaxEngine()
        eitc = engine._calculate_eitc(tax_return, "single")
        assert eitc == pytest.approx(649.0, rel=0.01)

    def test_phase_in_two_children(self):
        """Test phase-in for 2 children at $10,000 earned income."""
        # $10,000 x 40% = $4,000 (below max of $7,152)
        tax_return = create_eitc_return(wages=10000, num_children=2)
        engine = FederalTaxEngine()
        eitc = engine._calculate_eitc(tax_return, "single")
        assert eitc == pytest.approx(4000.0, rel=0.01)

    def test_phase_in_three_children(self):
        """Test phase-in for 3+ children at $12,000 earned income."""
        # $12,000 x 45% = $5,400 (below max of $8,046)
        tax_return = create_eitc_return(wages=12000, num_children=3)
        engine = FederalTaxEngine()
        eitc = engine._calculate_eitc(tax_return, "single")
        assert eitc == pytest.approx(5400.0, rel=0.01)
