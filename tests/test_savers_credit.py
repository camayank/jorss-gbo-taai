"""
Tests for Saver's Credit (Retirement Savings Contributions Credit - Form 8880)

Tests cover:
- Credit rate tiers (50%, 20%, 10%, 0%)
- Filing status variations
- Contribution limits ($2,000 per person)
- Eligibility requirements
- Integration with engine
"""

import pytest
from src.calculator.engine import FederalTaxEngine
from src.calculator.tax_year_config import TaxYearConfig
from src.models.tax_return import TaxReturn
from src.models.taxpayer import TaxpayerInfo, FilingStatus
from src.models.income import Income, W2Info
from src.models.deductions import Deductions
from src.models.credits import TaxCredits


def make_w2(wages: float, federal_withheld: float = 0.0) -> W2Info:
    """Helper to create W2Info for tests."""
    return W2Info(
        employer_name="Test Employer",
        wages=wages,
        federal_tax_withheld=federal_withheld,
    )


class TestSaversCreditRates:
    """Tests for credit rate tiers based on AGI."""

    def test_50_percent_rate_single(self):
        """Single filer with AGI $20,000 gets 50% rate."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(20000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                ira_contributions=2000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # $20K AGI = 50% rate, $2,000 contribution = $1,000 credit
        assert breakdown.credit_breakdown['retirement_savings_credit'] == 1000.0

    def test_20_percent_rate_single(self):
        """Single filer with AGI in 20% bracket gets 20% rate."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # Need AGI between $23,750 and $25,500 for 20% rate
        # Using 401k (not IRA) to avoid affecting AGI
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(24000.0)]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(
                elective_deferrals_401k=2000.0,  # 401k doesn't reduce AGI
            ),
        )

        breakdown = engine.calculate(tr)

        # $24K AGI (401k doesn't affect AGI) = 20% rate
        # $2,000 * 20% = $400
        assert breakdown.credit_breakdown['retirement_savings_credit'] == 400.0

    def test_10_percent_rate_single(self):
        """Single filer with AGI $30,000 gets 10% rate."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(30000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                ira_contributions=2000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # $30K AGI = 10% rate, $2,000 contribution = $200 credit
        assert breakdown.credit_breakdown['retirement_savings_credit'] == 200.0

    def test_zero_rate_above_threshold(self):
        """Single filer with AGI $50,000 gets 0% rate."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(50000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                ira_contributions=2000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # $50K AGI exceeds $39,375 threshold = 0% rate
        assert breakdown.credit_breakdown['retirement_savings_credit'] == 0.0


class TestSaversCreditFilingStatus:
    """Tests for different filing statuses."""

    def test_mfj_50_percent_rate(self):
        """MFJ with AGI $40,000 gets 50% rate."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Married",
                last_name="Couple",
                filing_status=FilingStatus.MARRIED_JOINT,
            ),
            income=Income(w2_forms=[make_w2(40000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                ira_contributions=2000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # MFJ $40K AGI (below $47,500) = 50% rate
        assert breakdown.credit_breakdown['retirement_savings_credit'] == 1000.0

    def test_hoh_20_percent_rate(self):
        """HOH with AGI in 20% bracket gets 20% rate."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # HOH 20% rate: AGI between $35,625 and $38,250
        # Using 401k to avoid affecting AGI
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Head",
                last_name="Household",
                filing_status=FilingStatus.HEAD_OF_HOUSEHOLD,
            ),
            income=Income(w2_forms=[make_w2(37000.0)]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(
                elective_deferrals_401k=1500.0,  # 401k doesn't reduce AGI
            ),
        )

        breakdown = engine.calculate(tr)

        # HOH $37K AGI (between $35,625 and $38,250) = 20% rate
        # $1,500 * 20% = $300
        assert breakdown.credit_breakdown['retirement_savings_credit'] == 300.0

    def test_mfs_threshold(self):
        """MFS uses same thresholds as Single."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Married",
                last_name="Separate",
                filing_status=FilingStatus.MARRIED_SEPARATE,
            ),
            income=Income(w2_forms=[make_w2(20000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                ira_contributions=2000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # MFS $20K AGI (below $23,750) = 50% rate
        assert breakdown.credit_breakdown['retirement_savings_credit'] == 1000.0


class TestSaversCreditContributions:
    """Tests for contribution limits and types."""

    def test_contribution_capped_at_2000(self):
        """Contribution basis capped at $2,000."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(20000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                ira_contributions=5000.0,  # Over $2,000 limit
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # Even with $5K contribution, credit basis capped at $2,000
        # $2,000 * 50% = $1,000
        assert breakdown.credit_breakdown['retirement_savings_credit'] == 1000.0

    def test_contribution_under_2000(self):
        """Partial contribution gets partial credit."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(20000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                ira_contributions=500.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # $500 * 50% = $250
        assert breakdown.credit_breakdown['retirement_savings_credit'] == 250.0

    def test_401k_contributions_included(self):
        """401(k) contributions count toward credit."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(20000.0)]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(
                elective_deferrals_401k=2000.0,
            ),
        )

        breakdown = engine.calculate(tr)

        # $2,000 401(k) * 50% = $1,000
        assert breakdown.credit_breakdown['retirement_savings_credit'] == 1000.0

    def test_combined_ira_and_401k(self):
        """Combined IRA and 401(k) contributions count together."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(20000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                ira_contributions=1000.0,
            ),
            credits=TaxCredits(
                elective_deferrals_401k=1500.0,
            ),
        )

        breakdown = engine.calculate(tr)

        # Total $2,500 but capped at $2,000, 50% = $1,000
        assert breakdown.credit_breakdown['retirement_savings_credit'] == 1000.0


class TestSaversCreditEligibility:
    """Tests for eligibility requirements."""

    def test_ineligible_no_credit(self):
        """Ineligible taxpayer gets no credit."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Student",
                last_name="Dependent",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(20000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                ira_contributions=2000.0,
            ),
            credits=TaxCredits(
                savers_credit_eligible=False,  # Student/dependent
            ),
        )

        breakdown = engine.calculate(tr)

        # Ineligible = $0 credit
        assert breakdown.credit_breakdown['retirement_savings_credit'] == 0.0

    def test_no_contributions_no_credit(self):
        """No contributions means no credit."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(20000.0)]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # No contributions = $0 credit
        assert breakdown.credit_breakdown['retirement_savings_credit'] == 0.0


class TestSaversCreditBoundaries:
    """Tests for AGI threshold boundaries."""

    def test_at_50_percent_boundary_single(self):
        """Single at exactly $23,750 AGI gets 50% rate."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits()

        result = credits.calculate_savers_credit(
            agi=23750.0,
            filing_status="single",
            qualified_contributions=2000.0,
            config=config,
        )

        # At boundary = still 50%
        assert result == 1000.0

    def test_just_above_50_percent_boundary(self):
        """Single at $23,751 AGI gets 20% rate."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits()

        result = credits.calculate_savers_credit(
            agi=23751.0,
            filing_status="single",
            qualified_contributions=2000.0,
            config=config,
        )

        # Just above 50% boundary = 20%
        assert result == 400.0

    def test_at_20_percent_boundary_single(self):
        """Single at exactly $25,500 AGI gets 20% rate."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits()

        result = credits.calculate_savers_credit(
            agi=25500.0,
            filing_status="single",
            qualified_contributions=2000.0,
            config=config,
        )

        # At boundary = still 20%
        assert result == 400.0

    def test_at_10_percent_boundary_single(self):
        """Single at exactly $39,375 AGI gets 10% rate."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits()

        result = credits.calculate_savers_credit(
            agi=39375.0,
            filing_status="single",
            qualified_contributions=2000.0,
            config=config,
        )

        # At boundary = still 10%
        assert result == 200.0

    def test_just_above_10_percent_boundary(self):
        """Single at $39,376 AGI gets 0% rate."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits()

        result = credits.calculate_savers_credit(
            agi=39376.0,
            filing_status="single",
            qualified_contributions=2000.0,
            config=config,
        )

        # Just above 10% boundary = 0%
        assert result == 0.0


class TestSaversCreditDirect:
    """Direct tests of calculate_savers_credit() method."""

    def test_mfj_boundaries(self):
        """Test MFJ threshold boundaries."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits()

        # MFJ 50% limit: $47,500
        result_50 = credits.calculate_savers_credit(
            agi=47500.0,
            filing_status="married_joint",
            qualified_contributions=2000.0,
            config=config,
        )
        assert result_50 == 1000.0

        # MFJ 20% limit: $51,000
        result_20 = credits.calculate_savers_credit(
            agi=51000.0,
            filing_status="married_joint",
            qualified_contributions=2000.0,
            config=config,
        )
        assert result_20 == 400.0

        # MFJ 10% limit: $78,750
        result_10 = credits.calculate_savers_credit(
            agi=78750.0,
            filing_status="married_joint",
            qualified_contributions=2000.0,
            config=config,
        )
        assert result_10 == 200.0

        # Above MFJ 10% limit
        result_0 = credits.calculate_savers_credit(
            agi=78751.0,
            filing_status="married_joint",
            qualified_contributions=2000.0,
            config=config,
        )
        assert result_0 == 0.0

    def test_hoh_boundaries(self):
        """Test HOH threshold boundaries."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits()

        # HOH 50% limit: $35,625
        result_50 = credits.calculate_savers_credit(
            agi=35625.0,
            filing_status="head_of_household",
            qualified_contributions=2000.0,
            config=config,
        )
        assert result_50 == 1000.0

        # HOH 20% limit: $38,250
        result_20 = credits.calculate_savers_credit(
            agi=38250.0,
            filing_status="head_of_household",
            qualified_contributions=2000.0,
            config=config,
        )
        assert result_20 == 400.0

        # HOH 10% limit: $59,062
        result_10 = credits.calculate_savers_credit(
            agi=59062.0,
            filing_status="head_of_household",
            qualified_contributions=2000.0,
            config=config,
        )
        assert result_10 == 200.0


class TestSaversCreditNonrefundable:
    """Tests verifying credit is nonrefundable."""

    def test_credit_in_nonrefundable_total(self):
        """Saver's Credit should be included in nonrefundable total."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(20000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                ira_contributions=2000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # Saver's Credit should be part of total_nonrefundable
        savers = breakdown.credit_breakdown['retirement_savings_credit']
        total_nonref = breakdown.credit_breakdown['total_nonrefundable']
        assert savers <= total_nonref
        assert savers == 1000.0
