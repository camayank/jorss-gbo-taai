"""
Tests for Form 3800 - General Business Credit

Comprehensive test suite covering:
- Credit aggregation from multiple sources
- Tax liability limitation
- Carryforward/carryback credits
- Specified credits
- Passive activity credits
- Individual credit calculations (R&D, WOTC, etc.)
"""

import pytest
from src.models.form_3800 import (
    Form3800,
    Form3800Part1,
    Form3800Part2,
    Form3800Part3,
    BusinessCredit,
    CreditType,
    CreditSource,
    ResearchCredit,
    WorkOpportunityCredit,
    SmallEmployerHealthCredit,
    calculate_general_business_credit,
)


class TestBusinessCreditBasic:
    """Test basic BusinessCredit functionality."""

    def test_create_credit(self):
        """Test creating a business credit."""
        credit = BusinessCredit(
            credit_type=CreditType.RESEARCH,
            source_form="Form 6765",
            description="R&D Credit",
            credit_amount=50000,
        )
        assert credit.credit_type == CreditType.RESEARCH
        assert credit.credit_amount == 50000
        assert credit.credit_source == CreditSource.CURRENT_YEAR

    def test_credit_types(self):
        """Test credit type enum values."""
        assert CreditType.RESEARCH.value == "research"
        assert CreditType.WORK_OPPORTUNITY.value == "work_opportunity"
        assert CreditType.LOW_INCOME_HOUSING.value == "low_income_housing"
        assert CreditType.DISABLED_ACCESS.value == "disabled_access"

    def test_credit_sources(self):
        """Test credit source enum values."""
        assert CreditSource.CURRENT_YEAR.value == "current_year"
        assert CreditSource.CARRYFORWARD.value == "carryforward"
        assert CreditSource.CARRYBACK.value == "carryback"

    def test_carryforward_credit(self):
        """Test carryforward credit with original year."""
        credit = BusinessCredit(
            credit_type=CreditType.RESEARCH,
            credit_amount=25000,
            credit_source=CreditSource.CARRYFORWARD,
            original_year=2023,
        )
        assert credit.credit_source == CreditSource.CARRYFORWARD
        assert credit.original_year == 2023

    def test_passive_credit(self):
        """Test passive activity credit."""
        credit = BusinessCredit(
            credit_type=CreditType.LOW_INCOME_HOUSING,
            credit_amount=10000,
            is_passive=True,
            passive_allowed=8000,
        )
        assert credit.is_passive is True
        assert credit.passive_allowed == 8000


class TestForm3800Part3:
    """Test Part III credit aggregation."""

    def test_add_single_credit(self):
        """Test adding a single credit."""
        part3 = Form3800Part3(tax_year=2025)
        credit = BusinessCredit(
            credit_type=CreditType.RESEARCH,
            credit_amount=50000,
        )
        part3.add_credit(credit)

        assert len(part3.credits) == 1
        assert part3.total_all_credits == 50000

    def test_add_multiple_credits(self):
        """Test adding multiple credits."""
        part3 = Form3800Part3(tax_year=2025)

        part3.add_credit(BusinessCredit(
            credit_type=CreditType.RESEARCH,
            credit_amount=50000,
        ))
        part3.add_credit(BusinessCredit(
            credit_type=CreditType.WORK_OPPORTUNITY,
            credit_amount=10000,
        ))
        part3.add_credit(BusinessCredit(
            credit_type=CreditType.DISABLED_ACCESS,
            credit_amount=5000,
        ))

        assert part3.total_all_credits == 65000

    def test_credits_by_type(self):
        """Test grouping credits by type."""
        part3 = Form3800Part3(tax_year=2025)

        part3.add_credit(BusinessCredit(
            credit_type=CreditType.RESEARCH,
            credit_amount=30000,
        ))
        part3.add_credit(BusinessCredit(
            credit_type=CreditType.RESEARCH,
            credit_amount=20000,
        ))
        part3.add_credit(BusinessCredit(
            credit_type=CreditType.WORK_OPPORTUNITY,
            credit_amount=10000,
        ))

        by_type = part3.by_credit_type()
        assert by_type["research"] == 50000
        assert by_type["work_opportunity"] == 10000

    def test_credits_by_source(self):
        """Test grouping credits by source."""
        part3 = Form3800Part3(tax_year=2025)

        part3.add_credit(BusinessCredit(
            credit_type=CreditType.RESEARCH,
            credit_amount=40000,
            credit_source=CreditSource.CURRENT_YEAR,
        ))
        part3.add_credit(BusinessCredit(
            credit_type=CreditType.RESEARCH,
            credit_amount=15000,
            credit_source=CreditSource.CARRYFORWARD,
        ))

        assert part3.total_current_year_credits == 40000
        assert part3.total_carryforward_credits == 15000

    def test_passive_credit_totals(self):
        """Test passive credit totaling."""
        part3 = Form3800Part3(tax_year=2025)

        part3.add_credit(BusinessCredit(
            credit_type=CreditType.LOW_INCOME_HOUSING,
            credit_amount=20000,
            is_passive=True,
        ))
        part3.add_credit(BusinessCredit(
            credit_type=CreditType.RESEARCH,
            credit_amount=30000,
            is_passive=False,
        ))

        assert part3.total_passive_credits == 20000
        assert part3.total_all_credits == 50000

    def test_specified_credit_totals(self):
        """Test specified credit totaling."""
        part3 = Form3800Part3(tax_year=2025)

        part3.add_credit(BusinessCredit(
            credit_type=CreditType.SMALL_EMPLOYER_HEALTH,
            credit_amount=5000,
            is_specified_credit=True,
        ))
        part3.add_credit(BusinessCredit(
            credit_type=CreditType.RESEARCH,
            credit_amount=30000,
            is_specified_credit=False,
        ))

        assert part3.total_specified_credits == 5000


class TestForm3800Part1:
    """Test Part I current year credit calculation."""

    def test_subtract_passive(self):
        """Test subtracting passive credits."""
        part1 = Form3800Part1(
            line_1_general_business_credit=100000,
            line_2_passive_credits=20000,
        )
        assert part1.line_3_subtract == 80000

    def test_total_with_carryover(self):
        """Test total including carryforward/carryback."""
        part1 = Form3800Part1(
            line_1_general_business_credit=50000,
            line_2_passive_credits=10000,
            line_4_passive_allowed=8000,
            line_5_carryforward=15000,
            line_6_carryback=5000,
        )
        # Line 3 = 40000, + 8000 + 15000 + 5000 = 68000
        assert part1.line_7_total == 68000


class TestForm3800Part2:
    """Test Part II allowable credit calculation."""

    def test_net_income_tax(self):
        """Test net income tax calculation."""
        part2 = Form3800Part2(
            line_8_regular_tax=100000,
            line_9_amt=5000,
        )
        assert part2.line_10_net_income_tax == 105000

    def test_25_percent_excess(self):
        """Test 25% of net regular tax over $25,000."""
        part2 = Form3800Part2(
            line_11_net_regular_tax=125000,
        )
        # (125000 - 25000) × 25% = 25000
        assert part2.line_12_25_percent_excess == 25000

    def test_25_percent_below_threshold(self):
        """Test 25% calculation when below $25,000."""
        part2 = Form3800Part2(
            line_11_net_regular_tax=20000,
        )
        assert part2.line_12_25_percent_excess == 0

    def test_limitation_calculation(self):
        """Test credit limitation calculation."""
        part2 = Form3800Part2(
            line_8_regular_tax=150000,
            line_9_amt=0,
            line_11_net_regular_tax=150000,
            line_13_tmt=30000,
        )
        # Net income tax = 150000
        # 25% excess = (150000 - 25000) × 25% = 31250
        # Greater of 31250 or 30000 = 31250
        # Limitation = 150000 - 31250 = 118750
        assert part2.line_15_limitation == 118750

    def test_allowable_credit_limited(self):
        """Test allowable credit when limited by tax."""
        part2 = Form3800Part2(
            line_8_regular_tax=100000,
            line_11_net_regular_tax=100000,
            line_13_tmt=20000,
            line_16_credit_from_part1=80000,
        )
        # Limitation is less than credit claimed
        limitation = part2.line_15_limitation
        assert part2.line_36_allowable_credit == min(limitation, 80000)

    def test_allowable_credit_not_limited(self):
        """Test allowable credit when not limited."""
        part2 = Form3800Part2(
            line_8_regular_tax=200000,
            line_11_net_regular_tax=200000,
            line_13_tmt=20000,
            line_16_credit_from_part1=30000,
        )
        # Limitation exceeds credit claimed
        assert part2.line_36_allowable_credit == 30000


class TestForm3800Complete:
    """Test complete Form 3800 functionality."""

    def test_add_credit_via_form(self):
        """Test adding credits through Form 3800."""
        form = Form3800(tax_year=2025)
        form.add_credit(
            credit_type=CreditType.RESEARCH,
            amount=50000,
            source_form="Form 6765",
            description="R&D Credit",
        )

        assert form.total_credits_claimed == 50000
        assert len(form.part_3.credits) == 1

    def test_set_tax_liability(self):
        """Test setting tax liability information."""
        form = Form3800(tax_year=2025)
        form.add_credit(CreditType.RESEARCH, 40000)

        form.set_tax_liability(
            regular_tax=100000,
            amt=5000,
            net_regular_tax=100000,
            tmt=25000,
        )

        assert form.part_2.line_8_regular_tax == 100000
        assert form.part_2.line_9_amt == 5000

    def test_allowable_credit_calculation(self):
        """Test complete allowable credit calculation."""
        form = Form3800(tax_year=2025)
        form.add_credit(CreditType.RESEARCH, 30000)
        form.add_credit(CreditType.WORK_OPPORTUNITY, 10000)

        form.set_tax_liability(
            regular_tax=150000,
            net_regular_tax=150000,
            tmt=20000,
        )

        # Total credits = 40000
        assert form.total_credits_claimed == 40000
        # Should be fully allowable with this tax liability
        assert form.allowable_credit == 40000
        assert form.unused_credit == 0

    def test_credit_limited_by_tax(self):
        """Test when credits exceed tax limitation."""
        form = Form3800(tax_year=2025)
        form.add_credit(CreditType.RESEARCH, 100000)

        form.set_tax_liability(
            regular_tax=50000,
            net_regular_tax=50000,
            tmt=30000,
        )

        # Credits limited by tax liability
        assert form.allowable_credit < form.total_credits_claimed
        assert form.unused_credit > 0
        assert form.has_carryforward is True

    def test_carryforward_calculation(self):
        """Test carryforward calculation."""
        form = Form3800(tax_year=2025)
        form.add_credit(CreditType.RESEARCH, 100000)

        form.set_tax_liability(
            regular_tax=50000,
            net_regular_tax=50000,
            tmt=30000,
        )

        carryforward = form.calculate_carryforward()
        assert carryforward["has_carryforward"] is True
        assert carryforward["amount"] > 0
        assert carryforward["expires_after_year"] == 2045  # 20 years
        assert carryforward["from_year"] == 2025


class TestForm3800WithCarryovers:
    """Test Form 3800 with carryforward and carryback credits."""

    def test_with_carryforward(self):
        """Test including carryforward credits."""
        form = Form3800(tax_year=2025)

        # Current year credit
        form.add_credit(
            credit_type=CreditType.RESEARCH,
            amount=30000,
            source=CreditSource.CURRENT_YEAR,
        )

        # Carryforward from prior year
        form.add_credit(
            credit_type=CreditType.RESEARCH,
            amount=20000,
            source=CreditSource.CARRYFORWARD,
            original_year=2024,
        )

        assert form.part_3.total_current_year_credits == 30000
        assert form.part_3.total_carryforward_credits == 20000
        assert form.total_credits_claimed == 50000

    def test_with_carryback(self):
        """Test including carryback credits."""
        form = Form3800(tax_year=2025)

        form.add_credit(
            credit_type=CreditType.RESEARCH,
            amount=40000,
            source=CreditSource.CURRENT_YEAR,
        )

        form.add_credit(
            credit_type=CreditType.RESEARCH,
            amount=10000,
            source=CreditSource.CARRYBACK,
            original_year=2026,
        )

        assert form.part_3.total_carryback_credits == 10000


class TestResearchCredit:
    """Test R&D (Research) Credit calculation."""

    def test_simplified_credit(self):
        """Test Alternative Simplified Credit calculation."""
        credit = ResearchCredit(
            wages=500000,
            supplies=100000,
            contract_research=150000,  # 65% = 97500
            prior_year_1_qre=600000,
            prior_year_2_qre=550000,
            prior_year_3_qre=500000,
            use_simplified_method=True,
        )
        # Total QRE = 500000 + 100000 + 97500 = 697500
        assert credit.total_qre == 697500

        # Average prior = (600000 + 550000 + 500000) / 3 = 550000
        assert credit.average_prior_qre == 550000

        # Threshold = 550000 × 50% = 275000
        # Excess = 697500 - 275000 = 422500
        # Credit = 422500 × 14% = 59150
        assert abs(credit.simplified_credit - 59150) < 0.01
        assert abs(credit.credit_amount - 59150) < 0.01

    def test_regular_credit(self):
        """Test regular research credit (20% method)."""
        credit = ResearchCredit(
            wages=400000,
            supplies=50000,
            base_amount=200000,
            use_simplified_method=False,
        )
        # Total QRE = 450000
        # Excess = 450000 - 200000 = 250000
        # Credit = 250000 × 20% = 50000
        assert credit.regular_credit == 50000
        assert credit.credit_amount == 50000

    def test_to_form_3800(self):
        """Test conversion to Form 3800 credit."""
        credit = ResearchCredit(
            wages=200000,
            prior_year_1_qre=150000,
            prior_year_2_qre=150000,
            prior_year_3_qre=150000,
        )
        business_credit = credit.to_form_3800()

        assert business_credit.credit_type == CreditType.RESEARCH
        assert business_credit.source_form == "Form 6765"
        assert business_credit.credit_amount == credit.credit_amount


class TestWorkOpportunityCredit:
    """Test Work Opportunity Credit calculation."""

    def test_first_year_credit(self):
        """Test first year WOTC calculation."""
        credit = WorkOpportunityCredit(
            qualified_first_year_wages=60000,  # 10 employees × $6000 max
        )
        # 40% of wages = 24000
        assert credit.first_year_credit == 24000
        assert credit.total_credit == 24000

    def test_second_year_credit(self):
        """Test second year credit for long-term recipients."""
        credit = WorkOpportunityCredit(
            qualified_first_year_wages=30000,
            qualified_second_year_wages=30000,
        )
        # First year: 30000 × 40% = 12000
        # Second year: 30000 × 50% = 15000
        assert credit.first_year_credit == 12000
        assert credit.second_year_credit == 15000
        assert credit.total_credit == 27000

    def test_long_term_recipient_credit(self):
        """Test long-term family assistance recipient credit."""
        credit = WorkOpportunityCredit(
            long_term_recipient_wages=50000,  # 5 × $10000 max
        )
        # 40% of wages = 20000
        assert credit.long_term_credit == 20000

    def test_summer_youth_credit(self):
        """Test summer youth employee credit."""
        credit = WorkOpportunityCredit(
            summer_youth_wages=15000,  # 5 × $3000 max
        )
        # 40% of wages = 6000
        assert credit.summer_youth_credit == 6000

    def test_to_form_3800(self):
        """Test conversion to Form 3800 credit."""
        credit = WorkOpportunityCredit(
            qualified_first_year_wages=30000,
        )
        business_credit = credit.to_form_3800()

        assert business_credit.credit_type == CreditType.WORK_OPPORTUNITY
        assert business_credit.source_form == "Form 5884"


class TestSmallEmployerHealthCredit:
    """Test Small Employer Health Insurance Credit."""

    def test_eligible_employer(self):
        """Test eligible employer calculation."""
        credit = SmallEmployerHealthCredit(
            average_annual_wages=35000,
            fte_count=8,
            premiums_paid=50000,
            state_average_premium=7000,
        )
        assert credit.is_eligible is True
        # 8 FTEs × $7000 = $56000 eligible, actual $50000
        # Credit rate 50% (no reduction for <10 FTEs and wages phase-out)
        assert credit.credit_percentage > 0

    def test_ineligible_too_many_employees(self):
        """Test ineligibility with too many employees."""
        credit = SmallEmployerHealthCredit(
            average_annual_wages=40000,
            fte_count=30,  # > 25 FTEs
            premiums_paid=100000,
        )
        assert credit.is_eligible is False
        assert credit.credit_amount == 0

    def test_ineligible_wages_too_high(self):
        """Test ineligibility with wages too high."""
        credit = SmallEmployerHealthCredit(
            average_annual_wages=60000,  # > $56,000
            fte_count=10,
            premiums_paid=50000,
        )
        assert credit.is_eligible is False

    def test_fte_phaseout(self):
        """Test FTE phase-out reduction."""
        credit1 = SmallEmployerHealthCredit(
            average_annual_wages=25000,
            fte_count=5,  # No phase-out
            premiums_paid=30000,
            state_average_premium=6000,
        )

        credit2 = SmallEmployerHealthCredit(
            average_annual_wages=25000,
            fte_count=20,  # Phase-out applies
            premiums_paid=100000,
            state_average_premium=6000,
        )

        # FTE phase-out reduces credit percentage
        assert credit1.credit_percentage > credit2.credit_percentage

    def test_tax_exempt_rate(self):
        """Test lower rate for tax-exempt employers."""
        credit = SmallEmployerHealthCredit(
            average_annual_wages=25000,
            fte_count=5,
            premiums_paid=30000,
            state_average_premium=6000,
            is_tax_exempt=True,
        )
        # Tax-exempt max is 35% vs 50%
        assert credit.credit_percentage <= 0.35

    def test_is_specified_credit(self):
        """Test that health credit is a specified credit."""
        credit = SmallEmployerHealthCredit(
            average_annual_wages=30000,
            fte_count=8,
            premiums_paid=40000,
            state_average_premium=5000,
        )
        business_credit = credit.to_form_3800()
        assert business_credit.is_specified_credit is True


class TestConvenienceFunction:
    """Test calculate_general_business_credit function."""

    def test_basic_calculation(self):
        """Test basic credit calculation."""
        credits = [
            {"type": "research", "amount": 30000, "source_form": "Form 6765"},
            {"type": "work_opportunity", "amount": 10000, "source_form": "Form 5884"},
        ]

        result = calculate_general_business_credit(
            credits=credits,
            regular_tax=100000,
            net_regular_tax=100000,
            tmt=20000,
        )

        assert result["credits"]["total_claimed"] == 40000
        assert "research" in result["credits"]["by_type"]
        assert result["credits"]["by_type"]["research"] == 30000

    def test_with_carryforward(self):
        """Test calculation with carryforward credits."""
        credits = [
            {"type": "research", "amount": 20000, "source": "current_year"},
            {"type": "research", "amount": 10000, "source": "carryforward"},
        ]

        result = calculate_general_business_credit(
            credits=credits,
            regular_tax=80000,
            net_regular_tax=80000,
            tmt=15000,
        )

        assert result["credits"]["by_source"]["current_year"] == 20000
        assert result["credits"]["by_source"]["carryforward"] == 10000


class TestForm3800ToDictionary:
    """Test dictionary serialization."""

    def test_to_dict(self):
        """Test complete dictionary output."""
        form = Form3800(tax_year=2025)
        form.add_credit(CreditType.RESEARCH, 50000)
        form.add_credit(CreditType.WORK_OPPORTUNITY, 15000)

        form.set_tax_liability(
            regular_tax=150000,
            net_regular_tax=150000,
            tmt=30000,
        )

        result = form.to_dict()

        assert result["tax_year"] == 2025
        assert result["credits"]["total_claimed"] == 65000
        assert "research" in result["credits"]["by_type"]
        assert "result" in result
        assert "carryforward" in result

    def test_to_form_1040(self):
        """Test Form 1040 output."""
        form = Form3800(tax_year=2025)
        form.add_credit(CreditType.RESEARCH, 25000)

        form.set_tax_liability(
            regular_tax=100000,
            net_regular_tax=100000,
            tmt=20000,
        )

        result = form.to_form_1040()
        assert "schedule_3_line_6a" in result
        assert result["schedule_3_line_6a"] == form.allowable_credit


class TestEdgeCases:
    """Test edge cases."""

    def test_zero_tax_liability(self):
        """Test with zero tax liability."""
        form = Form3800(tax_year=2025)
        form.add_credit(CreditType.RESEARCH, 50000)

        form.set_tax_liability(
            regular_tax=0,
            net_regular_tax=0,
            tmt=0,
        )

        assert form.allowable_credit == 0
        assert form.unused_credit == 50000
        assert form.has_carryforward is True

    def test_no_credits(self):
        """Test with no credits."""
        form = Form3800(tax_year=2025)

        form.set_tax_liability(
            regular_tax=100000,
            net_regular_tax=100000,
        )

        assert form.total_credits_claimed == 0
        assert form.allowable_credit == 0
        assert form.has_carryforward is False

    def test_multiple_same_type_credits(self):
        """Test multiple credits of same type."""
        form = Form3800(tax_year=2025)

        # Multiple R&D credits (e.g., from different activities)
        form.add_credit(CreditType.RESEARCH, 20000, description="Product A R&D")
        form.add_credit(CreditType.RESEARCH, 15000, description="Product B R&D")
        form.add_credit(CreditType.RESEARCH, 10000, description="Process R&D")

        by_type = form.part_3.by_credit_type()
        assert by_type["research"] == 45000
