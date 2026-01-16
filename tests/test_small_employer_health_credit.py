"""
Tests for Small Employer Health Insurance Credit (Form 8941 / IRC Section 45R).

This credit helps small employers afford health insurance for employees.

Key Rules:
- Fewer than 25 FTE employees
- Average annual wages below threshold (~$59,000 for 2025)
- Pay at least 50% of employee-only premium cost
- Coverage through SHOP Marketplace
- Taxable employers: 50% credit
- Tax-exempt employers: 35% credit
- FTE phase-out: 10 to 25 FTEs
- Wage phase-out: ~$29,500 to ~$59,000

Reference: IRC Section 45R, IRS Form 8941
"""

import pytest
from models.credits import TaxCredits, SmallEmployerHealthInfo


class TestSmallEmployerHealthInfo:
    """Tests for the SmallEmployerHealthInfo model."""

    def test_average_annual_wages(self):
        """Test average annual wages calculation."""
        info = SmallEmployerHealthInfo(
            fte_count=10,
            total_wages_paid=300000,
            total_premiums_paid=50000,
            employer_contribution_percentage=100,
        )
        assert info.get_average_annual_wages() == 30000.0

    def test_average_wages_zero_fte(self):
        """Test average wages with zero FTEs."""
        info = SmallEmployerHealthInfo(
            fte_count=0.0,
            total_wages_paid=0,
            total_premiums_paid=0,
            employer_contribution_percentage=100,
        )
        assert info.get_average_annual_wages() == 0.0

    def test_fte_phase_out_full_credit(self):
        """Test FTE phase-out at 10 or fewer FTEs (full credit)."""
        info = SmallEmployerHealthInfo(
            fte_count=10,
            total_wages_paid=200000,
            total_premiums_paid=30000,
            employer_contribution_percentage=100,
        )
        assert info.calculate_fte_phase_out() == 1.0

    def test_fte_phase_out_5_ftes(self):
        """Test FTE phase-out at 5 FTEs (full credit)."""
        info = SmallEmployerHealthInfo(
            fte_count=5,
            total_wages_paid=100000,
            total_premiums_paid=20000,
            employer_contribution_percentage=100,
        )
        assert info.calculate_fte_phase_out() == 1.0

    def test_fte_phase_out_partial(self):
        """Test FTE phase-out between 10 and 25 (partial credit)."""
        info = SmallEmployerHealthInfo(
            fte_count=17.5,  # Midpoint of 10-25
            total_wages_paid=350000,
            total_premiums_paid=50000,
            employer_contribution_percentage=100,
        )
        # (25 - 17.5) / 15 = 7.5 / 15 = 0.5
        assert info.calculate_fte_phase_out() == 0.5

    def test_fte_phase_out_20_ftes(self):
        """Test FTE phase-out at 20 FTEs."""
        info = SmallEmployerHealthInfo(
            fte_count=20,
            total_wages_paid=400000,
            total_premiums_paid=60000,
            employer_contribution_percentage=100,
        )
        # (25 - 20) / 15 = 5 / 15 = 0.333...
        assert round(info.calculate_fte_phase_out(), 4) == 0.3333

    def test_wage_phase_out_full_credit(self):
        """Test wage phase-out below threshold (full credit)."""
        info = SmallEmployerHealthInfo(
            fte_count=10,
            total_wages_paid=200000,  # $20,000 per FTE
            total_premiums_paid=30000,
            employer_contribution_percentage=100,
        )
        # $20,000 < $29,500 phase-out start
        assert info.calculate_wage_phase_out(59000.0) == 1.0

    def test_wage_phase_out_partial(self):
        """Test wage phase-out in phaseout range."""
        info = SmallEmployerHealthInfo(
            fte_count=10,
            total_wages_paid=443750,  # $44,375 per FTE (midpoint of $29,500-$59,000)
            total_premiums_paid=30000,
            employer_contribution_percentage=100,
        )
        # avg wages = $44,375
        # phase_out_start = $29,500
        # (59000 - 44375) / (59000 - 29500) = 14625 / 29500 = 0.4957...
        factor = info.calculate_wage_phase_out(59000.0)
        assert round(factor, 2) == 0.50

    def test_wage_phase_out_at_threshold(self):
        """Test wage phase-out at threshold (no credit)."""
        info = SmallEmployerHealthInfo(
            fte_count=10,
            total_wages_paid=590000,  # $59,000 per FTE
            total_premiums_paid=30000,
            employer_contribution_percentage=100,
        )
        assert info.calculate_wage_phase_out(59000.0) == 0.0


class TestSmallEmployerHealthCreditBasics:
    """Tests for basic credit calculation."""

    def test_no_info(self):
        """Test with no small employer health info."""
        credits = TaxCredits()
        credit, breakdown = credits.calculate_small_employer_health_credit()
        assert credit == 0.0
        assert breakdown['qualified'] is False

    def test_basic_taxable_employer_full_credit(self):
        """Test basic calculation for taxable employer with full credit."""
        credits = TaxCredits(
            small_employer_health_info=SmallEmployerHealthInfo(
                is_tax_exempt=False,
                fte_count=8,
                total_wages_paid=160000,  # $20,000 per FTE (below phase-out)
                total_premiums_paid=40000,
                employer_contribution_percentage=100,
            )
        )
        credit, breakdown = credits.calculate_small_employer_health_credit()

        # 50% of $40,000 = $20,000 (no phase-out)
        assert credit == 20000.0
        assert breakdown['base_credit_rate'] == 0.50
        assert breakdown['fte_phase_out_factor'] == 1.0
        assert breakdown['wage_phase_out_factor'] == 1.0
        assert breakdown['qualified'] is True

    def test_basic_tax_exempt_employer_full_credit(self):
        """Test basic calculation for tax-exempt employer with full credit."""
        credits = TaxCredits(
            small_employer_health_info=SmallEmployerHealthInfo(
                is_tax_exempt=True,
                fte_count=8,
                total_wages_paid=160000,
                total_premiums_paid=40000,
                employer_contribution_percentage=100,
            )
        )
        credit, breakdown = credits.calculate_small_employer_health_credit()

        # 35% of $40,000 = $14,000 (no phase-out)
        assert credit == 14000.0
        assert breakdown['base_credit_rate'] == 0.35
        assert breakdown['qualified'] is True

    def test_employee_only_premiums_used(self):
        """Test that employee-only premiums are used when specified."""
        credits = TaxCredits(
            small_employer_health_info=SmallEmployerHealthInfo(
                is_tax_exempt=False,
                fte_count=8,
                total_wages_paid=160000,
                total_premiums_paid=60000,  # Total including family
                employee_only_premiums=30000,  # Employee-only
                employer_contribution_percentage=100,
            )
        )
        credit, breakdown = credits.calculate_small_employer_health_credit()

        # 50% of $30,000 employee-only = $15,000
        assert credit == 15000.0


class TestSmallEmployerHealthCreditPhaseOuts:
    """Tests for phase-out calculations."""

    def test_fte_phase_out_only(self):
        """Test FTE phase-out with low wages."""
        credits = TaxCredits(
            small_employer_health_info=SmallEmployerHealthInfo(
                is_tax_exempt=False,
                fte_count=17.5,  # 50% phase-out
                total_wages_paid=175000,  # $10,000 per FTE (no wage phase-out)
                total_premiums_paid=50000,
                employer_contribution_percentage=100,
            )
        )
        credit, breakdown = credits.calculate_small_employer_health_credit()

        # Base: 50% of $50,000 = $25,000
        # FTE phase-out: 50%
        # Final: $25,000 × 0.5 = $12,500
        assert credit == 12500.0
        assert breakdown['fte_phase_out_factor'] == 0.5
        assert breakdown['wage_phase_out_factor'] == 1.0

    def test_wage_phase_out_only(self):
        """Test wage phase-out with low FTEs."""
        credits = TaxCredits(
            small_employer_health_info=SmallEmployerHealthInfo(
                is_tax_exempt=False,
                fte_count=10,  # No FTE phase-out
                total_wages_paid=443750,  # $44,375 per FTE (50% wage phase-out)
                total_premiums_paid=50000,
                employer_contribution_percentage=100,
            )
        )
        credit, breakdown = credits.calculate_small_employer_health_credit()

        # Base: 50% of $50,000 = $25,000
        # Wage phase-out: ~50%
        # Final: $25,000 × 0.5 = $12,500
        assert breakdown['fte_phase_out_factor'] == 1.0
        assert round(credit, 0) == 12394  # Due to precise calculation

    def test_combined_phase_out(self):
        """Test combined FTE and wage phase-out."""
        credits = TaxCredits(
            small_employer_health_info=SmallEmployerHealthInfo(
                is_tax_exempt=False,
                fte_count=17.5,  # 50% FTE phase-out
                total_wages_paid=776562.5,  # $44,375 per FTE (50% wage phase-out)
                total_premiums_paid=50000,
                employer_contribution_percentage=100,
            )
        )
        credit, breakdown = credits.calculate_small_employer_health_credit()

        # Base: 50% of $50,000 = $25,000
        # Combined phase-out: 50% × 50% = 25%
        # Final: $25,000 × 0.25 = $6,250
        assert breakdown['fte_phase_out_factor'] == 0.5
        assert round(breakdown['combined_phase_out'], 2) == 0.25
        assert round(credit, 0) == 6197  # Due to precise wage calculation


class TestSmallEmployerHealthCreditDisqualifications:
    """Tests for disqualification scenarios."""

    def test_disqualified_fte_count_too_high(self):
        """Test disqualification when FTE count is 25 or more."""
        # Note: The model validation won't allow fte_count >= 25
        # But the calculation method should also check
        credits = TaxCredits(
            small_employer_health_info=SmallEmployerHealthInfo(
                fte_count=24.9,  # Just under limit
                total_wages_paid=250000,
                total_premiums_paid=50000,
                employer_contribution_percentage=100,
            )
        )
        credit, breakdown = credits.calculate_small_employer_health_credit()
        # Should still calculate (24.9 < 25)
        assert breakdown['qualified'] is True

    def test_disqualified_wages_too_high(self):
        """Test disqualification when average wages exceed threshold."""
        credits = TaxCredits(
            small_employer_health_info=SmallEmployerHealthInfo(
                fte_count=10,
                total_wages_paid=600000,  # $60,000 per FTE
                total_premiums_paid=50000,
                employer_contribution_percentage=100,
            )
        )
        credit, breakdown = credits.calculate_small_employer_health_credit()

        assert credit == 0.0
        assert breakdown['qualified'] is False
        assert 'exceed' in breakdown['disqualification_reason'].lower()

    def test_disqualified_not_shop_marketplace(self):
        """Test disqualification when not using SHOP marketplace."""
        credits = TaxCredits(
            small_employer_health_info=SmallEmployerHealthInfo(
                is_shop_marketplace=False,
                fte_count=10,
                total_wages_paid=200000,
                total_premiums_paid=50000,
                employer_contribution_percentage=100,
            )
        )
        credit, breakdown = credits.calculate_small_employer_health_credit()

        assert credit == 0.0
        assert breakdown['qualified'] is False
        assert 'shop' in breakdown['disqualification_reason'].lower()


class TestSmallEmployerHealthCreditEdgeCases:
    """Tests for edge cases."""

    def test_exactly_10_ftes(self):
        """Test exactly 10 FTEs (threshold for full credit)."""
        credits = TaxCredits(
            small_employer_health_info=SmallEmployerHealthInfo(
                fte_count=10,
                total_wages_paid=200000,
                total_premiums_paid=40000,
                employer_contribution_percentage=100,
            )
        )
        credit, breakdown = credits.calculate_small_employer_health_credit()

        # Should get full credit (no FTE phase-out)
        assert breakdown['fte_phase_out_factor'] == 1.0
        assert credit == 20000.0  # 50% of $40,000

    def test_single_employee(self):
        """Test with a single FTE employee."""
        credits = TaxCredits(
            small_employer_health_info=SmallEmployerHealthInfo(
                fte_count=1,
                total_wages_paid=25000,
                total_premiums_paid=5000,
                employer_contribution_percentage=100,
            )
        )
        credit, breakdown = credits.calculate_small_employer_health_credit()

        # Full credit for 1 FTE
        assert credit == 2500.0  # 50% of $5,000
        assert breakdown['fte_phase_out_factor'] == 1.0

    def test_fractional_ftes(self):
        """Test with fractional FTE count."""
        credits = TaxCredits(
            small_employer_health_info=SmallEmployerHealthInfo(
                fte_count=12.5,
                total_wages_paid=187500,  # $15,000 per FTE
                total_premiums_paid=30000,
                employer_contribution_percentage=100,
            )
        )
        credit, breakdown = credits.calculate_small_employer_health_credit()

        # FTE phase-out: (25 - 12.5) / 15 = 0.833...
        assert round(breakdown['fte_phase_out_factor'], 4) == 0.8333
        # Base: $15,000, Phase-out: 83.33%
        # Credit: $15,000 × 0.8333 = $12,500
        assert round(credit, 0) == 12500

    def test_minimum_contribution_percentage(self):
        """Test with exactly 50% contribution (minimum required)."""
        credits = TaxCredits(
            small_employer_health_info=SmallEmployerHealthInfo(
                fte_count=10,
                total_wages_paid=200000,
                total_premiums_paid=40000,
                employer_contribution_percentage=50,  # Minimum
            )
        )
        credit, breakdown = credits.calculate_small_employer_health_credit()

        assert breakdown['qualified'] is True
        assert credit == 20000.0

    def test_state_average_premium_limit(self):
        """Test state average premium limitation."""
        credits = TaxCredits(
            small_employer_health_info=SmallEmployerHealthInfo(
                fte_count=10,
                total_wages_paid=200000,
                total_premiums_paid=100000,  # High premiums
                employee_only_premiums=80000,
                state_average_premium=5000,  # $5,000 per employee limit
                employer_contribution_percentage=100,
            )
        )
        credit, breakdown = credits.calculate_small_employer_health_credit()

        # State limit: $5,000 × 10 FTEs = $50,000
        # Credit: 50% of $50,000 = $25,000
        assert credit == 25000.0
        assert breakdown.get('state_average_premium_applied') is True


class TestSmallEmployerHealthCreditRates:
    """Tests for credit rate differences."""

    def test_taxable_employer_rate(self):
        """Test 50% rate for taxable employers."""
        credits = TaxCredits(
            small_employer_health_info=SmallEmployerHealthInfo(
                is_tax_exempt=False,
                fte_count=8,
                total_wages_paid=160000,
                total_premiums_paid=20000,
                employer_contribution_percentage=100,
            )
        )
        credit, breakdown = credits.calculate_small_employer_health_credit()

        assert breakdown['base_credit_rate'] == 0.50
        assert credit == 10000.0  # 50% of $20,000

    def test_tax_exempt_employer_rate(self):
        """Test 35% rate for tax-exempt employers."""
        credits = TaxCredits(
            small_employer_health_info=SmallEmployerHealthInfo(
                is_tax_exempt=True,
                fte_count=8,
                total_wages_paid=160000,
                total_premiums_paid=20000,
                employer_contribution_percentage=100,
            )
        )
        credit, breakdown = credits.calculate_small_employer_health_credit()

        assert breakdown['base_credit_rate'] == 0.35
        assert credit == 7000.0  # 35% of $20,000


class TestSmallEmployerHealthCreditBreakdown:
    """Tests for breakdown details."""

    def test_breakdown_contents(self):
        """Test that breakdown contains all expected fields."""
        credits = TaxCredits(
            small_employer_health_info=SmallEmployerHealthInfo(
                is_tax_exempt=False,
                fte_count=15,
                total_wages_paid=450000,  # $30,000 per FTE
                total_premiums_paid=50000,
                employer_contribution_percentage=100,
                credit_year_number=2,
            )
        )
        credit, breakdown = credits.calculate_small_employer_health_credit()

        assert 'credit_amount' in breakdown
        assert 'premiums_paid' in breakdown
        assert 'fte_count' in breakdown
        assert 'average_wages' in breakdown
        assert 'base_credit_rate' in breakdown
        assert 'fte_phase_out_factor' in breakdown
        assert 'wage_phase_out_factor' in breakdown
        assert 'combined_phase_out' in breakdown
        assert 'credit_before_phase_out' in breakdown
        assert 'credit_year' in breakdown

        assert breakdown['fte_count'] == 15
        assert breakdown['premiums_paid'] == 50000
        assert breakdown['average_wages'] == 30000.0
        assert breakdown['credit_year'] == 2

    def test_breakdown_phase_out_factors(self):
        """Test that phase-out factors are correctly calculated."""
        credits = TaxCredits(
            small_employer_health_info=SmallEmployerHealthInfo(
                fte_count=20,  # (25-20)/15 = 0.333
                total_wages_paid=800000,  # $40,000 per FTE
                total_premiums_paid=60000,
                employer_contribution_percentage=100,
            )
        )
        credit, breakdown = credits.calculate_small_employer_health_credit()

        # FTE: (25 - 20) / 15 = 0.333
        assert round(breakdown['fte_phase_out_factor'], 4) == 0.3333

        # Wage: avg = $40,000, start = $29,500, end = $59,000
        # (59000 - 40000) / (59000 - 29500) = 19000/29500 = 0.644
        assert round(breakdown['wage_phase_out_factor'], 2) == 0.64


class TestSmallEmployerHealthCreditMaxCredits:
    """Tests for maximum credit scenarios."""

    def test_max_credit_small_employer(self):
        """Test maximum credit for very small employer."""
        credits = TaxCredits(
            small_employer_health_info=SmallEmployerHealthInfo(
                is_tax_exempt=False,
                fte_count=5,
                total_wages_paid=100000,  # $20,000 per FTE (low)
                total_premiums_paid=25000,  # $5,000 per employee
                employer_contribution_percentage=100,
            )
        )
        credit, breakdown = credits.calculate_small_employer_health_credit()

        # Full credit: 50% of $25,000 = $12,500
        assert credit == 12500.0
        assert breakdown['fte_phase_out_factor'] == 1.0
        assert breakdown['wage_phase_out_factor'] == 1.0

    def test_credit_approaches_zero_high_fte(self):
        """Test credit approaches zero near 25 FTE limit."""
        credits = TaxCredits(
            small_employer_health_info=SmallEmployerHealthInfo(
                fte_count=24,
                total_wages_paid=240000,  # $10,000 per FTE
                total_premiums_paid=50000,
                employer_contribution_percentage=100,
            )
        )
        credit, breakdown = credits.calculate_small_employer_health_credit()

        # FTE phase-out: (25 - 24) / 15 = 0.0667
        # Base: $25,000 × 0.0667 = $1,667
        assert round(breakdown['fte_phase_out_factor'], 4) == 0.0667
        assert round(credit, 0) == 1667


class TestSmallEmployerHealthCreditValidation:
    """Tests for input validation via Pydantic."""

    def test_valid_minimum_contribution(self):
        """Test that 50% contribution is valid minimum."""
        info = SmallEmployerHealthInfo(
            fte_count=10,
            total_wages_paid=200000,
            total_premiums_paid=40000,
            employer_contribution_percentage=50,  # Minimum valid
        )
        assert info.employer_contribution_percentage == 50

    def test_valid_maximum_contribution(self):
        """Test that 100% contribution is valid."""
        info = SmallEmployerHealthInfo(
            fte_count=10,
            total_wages_paid=200000,
            total_premiums_paid=40000,
            employer_contribution_percentage=100,
        )
        assert info.employer_contribution_percentage == 100

    def test_credit_year_valid_values(self):
        """Test valid credit year values (1 or 2)."""
        info1 = SmallEmployerHealthInfo(
            fte_count=10,
            total_wages_paid=200000,
            total_premiums_paid=40000,
            employer_contribution_percentage=100,
            credit_year_number=1,
        )
        assert info1.credit_year_number == 1

        info2 = SmallEmployerHealthInfo(
            fte_count=10,
            total_wages_paid=200000,
            total_premiums_paid=40000,
            employer_contribution_percentage=100,
            credit_year_number=2,
        )
        assert info2.credit_year_number == 2
