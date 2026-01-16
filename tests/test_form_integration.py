"""
Integration tests for new forms integrated into the calculator engine.

Tests verify that when forms are populated on TaxReturn.income, the
CalculationBreakdown fields are correctly populated by the engine.
"""

import pytest
from models.tax_return import TaxReturn
from models.taxpayer import TaxpayerInfo, FilingStatus
from models.income import Income
from models.deductions import Deductions
from models.credits import TaxCredits
from calculator.engine import FederalTaxEngine

# Import new form models
from models.schedule_a import ScheduleA, MortgageInterestInfo, CharitableContribution
from models.schedule_b import ScheduleB, InterestPayer, DividendPayer
from models.schedule_d import ScheduleD, Form8949Summary
from models.schedule_e import ScheduleE, RentalProperty, PartnershipSCorpK1
from models.schedule_f import ScheduleF, FarmIncome, FarmExpenses
from models.form_6781 import Form6781, Section1256Contract
from models.form_8814 import Form8814, ChildIncome
from models.form_8995 import Form8995, QualifiedBusiness


def create_tax_return(income=None, filing_status=FilingStatus.SINGLE):
    """Helper to create a minimal valid TaxReturn."""
    return TaxReturn(
        tax_year=2025,
        taxpayer=TaxpayerInfo(
            first_name="Test",
            last_name="User",
            filing_status=filing_status,
        ),
        income=income or Income(),
        deductions=Deductions(use_standard_deduction=True),
        credits=TaxCredits(),
    )


class TestScheduleAIntegration:
    """Integration tests for Schedule A with calculator engine."""

    def test_schedule_a_populates_breakdown(self):
        """Schedule A fields appear in breakdown."""
        tax_return = create_tax_return(
            income=Income(
                schedule_a=ScheduleA(
                    medical_expenses_total=15000.0,
                    agi_for_medical=100000.0,
                    state_income_tax=8000.0,
                    real_estate_taxes=5000.0,
                    mortgages=[
                        MortgageInterestInfo(
                            lender_name="Bank",
                            interest_paid=12000.0,
                            original_loan_amount=400000.0,
                        ),
                    ],
                    charitable_contributions=[
                        CharitableContribution(
                            organization_name="Charity",
                            amount=5000.0,
                        ),
                    ],
                ),
            ),
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        # Verify Schedule A breakdown fields are populated
        assert breakdown.schedule_a_total_deductions > 0
        assert breakdown.schedule_a_salt_deduction == 10000.0  # SALT cap
        assert breakdown.schedule_a_charitable == 5000.0
        assert breakdown.schedule_a_breakdown is not None

    def test_schedule_a_salt_cap(self):
        """SALT deduction is capped at $10,000."""
        tax_return = create_tax_return(
            income=Income(
                schedule_a=ScheduleA(
                    state_income_tax=15000.0,
                    real_estate_taxes=8000.0,
                    agi_for_medical=200000.0,
                ),
            ),
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        # Total SALT is $23k but capped at $10k
        assert breakdown.schedule_a_salt_deduction == 10000.0


class TestScheduleBIntegration:
    """Integration tests for Schedule B with calculator engine."""

    def test_schedule_b_populates_breakdown(self):
        """Schedule B fields appear in breakdown."""
        tax_return = create_tax_return(
            income=Income(
                schedule_b=ScheduleB(
                    interest_payers=[
                        InterestPayer(payer_name="Bank A", amount=1500.0),
                        InterestPayer(payer_name="Bank B", amount=2500.0),
                    ],
                    dividend_payers=[
                        DividendPayer(
                            payer_name="Stock Fund",
                            ordinary_dividends=3000.0,
                            qualified_dividends=2500.0,
                        ),
                    ],
                ),
            ),
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        assert breakdown.schedule_b_total_interest == 4000.0
        assert breakdown.schedule_b_total_dividends == 3000.0
        assert breakdown.schedule_b_qualified_dividends == 2500.0

    def test_schedule_b_foreign_account_flag(self):
        """Foreign account flag triggers Part III requirement."""
        tax_return = create_tax_return(
            income=Income(
                schedule_b=ScheduleB(
                    interest_payers=[
                        InterestPayer(payer_name="Bank", amount=1000.0),
                    ],
                    has_foreign_accounts=True,
                    foreign_account_countries=["Switzerland"],
                ),
            ),
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        assert breakdown.schedule_b_requires_part_iii is True


class TestScheduleDIntegration:
    """Integration tests for Schedule D with calculator engine."""

    def test_schedule_d_populates_breakdown(self):
        """Schedule D fields appear in breakdown."""
        tax_return = create_tax_return(
            income=Income(
                schedule_d=ScheduleD(
                    form_8949_box_a=Form8949Summary(
                        box_code="A",
                        proceeds=15000.0,
                        cost_basis=10000.0,
                        adjustments=0.0,
                        gain_loss=5000.0,
                    ),
                    form_8949_box_d=Form8949Summary(
                        box_code="D",
                        proceeds=25000.0,
                        cost_basis=15000.0,
                        adjustments=0.0,
                        gain_loss=10000.0,
                    ),
                ),
            ),
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        assert breakdown.schedule_d_short_term_net == 5000.0
        assert breakdown.schedule_d_long_term_net == 10000.0
        assert breakdown.schedule_d_net_gain_loss == 15000.0

    def test_schedule_d_loss_limitation(self):
        """Capital loss limited to $3,000 against ordinary income."""
        tax_return = create_tax_return(
            income=Income(
                schedule_d=ScheduleD(
                    form_8949_box_a=Form8949Summary(
                        box_code="A",
                        proceeds=5000.0,
                        cost_basis=20000.0,
                        adjustments=0.0,
                        gain_loss=-15000.0,
                    ),
                ),
            ),
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        # $15k loss reported
        assert breakdown.schedule_d_net_gain_loss == -15000.0
        # Capital loss deduction limited to $3k
        assert breakdown.schedule_d_breakdown.get('capital_loss_deduction', 0) == 3000.0


class TestScheduleEIntegration:
    """Integration tests for Schedule E with calculator engine."""

    def test_schedule_e_rental_populates_breakdown(self):
        """Schedule E rental income appears in breakdown."""
        tax_return = create_tax_return(
            income=Income(
                schedule_e=ScheduleE(
                    rental_properties=[
                        RentalProperty(
                            property_address="123 Main St",
                            rents_received=24000.0,
                            repairs=3000.0,
                            insurance=1200.0,
                            taxes=2400.0,
                            mortgage_interest=6000.0,
                            depreciation=5000.0,
                        ),
                    ],
                    is_active_participant=True,
                    agi_for_pal=80000.0,
                ),
            ),
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        # $24k - $17.6k expenses = $6.4k
        assert breakdown.schedule_e_rental_income == 6400.0
        assert breakdown.schedule_e_total > 0

    def test_schedule_e_partnership_k1(self):
        """Schedule E partnership K-1 income appears in breakdown."""
        tax_return = create_tax_return(
            income=Income(
                schedule_e=ScheduleE(
                    partnership_scorp_k1s=[
                        PartnershipSCorpK1(
                            entity_name="ABC Partnership",
                            is_s_corp=False,
                            ordinary_income_loss=25000.0,
                            is_passive=True,
                        ),
                    ],
                ),
            ),
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        assert breakdown.schedule_e_partnership_income == 25000.0


class TestScheduleFIntegration:
    """Integration tests for Schedule F with calculator engine."""

    def test_schedule_f_populates_breakdown(self):
        """Schedule F fields appear in breakdown."""
        tax_return = create_tax_return(
            income=Income(
                schedule_f=ScheduleF(
                    farm_name="Smith Family Farm",
                    farm_income=FarmIncome(
                        produce_sales=100000.0,
                        ag_program_payments=5000.0,
                    ),
                    farm_expenses=FarmExpenses(
                        seeds_plants=15000.0,
                        fertilizers_lime=8000.0,
                        labor_hired=20000.0,
                        depreciation_179=10000.0,
                    ),
                    materially_participated=True,
                ),
            ),
            filing_status=FilingStatus.MARRIED_JOINT,
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        assert breakdown.schedule_f_gross_income == 105000.0
        assert breakdown.schedule_f_expenses == 53000.0
        assert breakdown.schedule_f_net_profit_loss == 52000.0
        assert breakdown.schedule_f_se_income == 52000.0

    def test_schedule_f_loss(self):
        """Schedule F with farm loss."""
        tax_return = create_tax_return(
            income=Income(
                schedule_f=ScheduleF(
                    farm_income=FarmIncome(produce_sales=40000.0),
                    farm_expenses=FarmExpenses(
                        seeds_plants=25000.0,
                        labor_hired=30000.0,
                    ),
                ),
            ),
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        assert breakdown.schedule_f_net_profit_loss == -15000.0


class TestForm6781Integration:
    """Integration tests for Form 6781 with calculator engine."""

    def test_form_6781_populates_breakdown(self):
        """Form 6781 fields appear in breakdown."""
        tax_return = create_tax_return(
            income=Income(
                form_6781=Form6781(
                    section_1256_contracts=[
                        Section1256Contract(
                            description="S&P 500 Futures",
                            proceeds=50000.0,
                            cost_basis=40000.0,
                        ),
                    ],
                ),
            ),
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        # $10k gain split 60/40
        assert breakdown.form_6781_section_1256_net == 10000.0
        assert breakdown.form_6781_short_term == 4000.0  # 40%
        assert breakdown.form_6781_long_term == 6000.0   # 60%

    def test_form_6781_loss_split(self):
        """Form 6781 loss also split 60/40."""
        tax_return = create_tax_return(
            income=Income(
                form_6781=Form6781(
                    section_1256_contracts=[
                        Section1256Contract(
                            description="Futures Loss",
                            proceeds=30000.0,
                            cost_basis=50000.0,
                        ),
                    ],
                ),
            ),
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        # $20k loss split 60/40
        assert breakdown.form_6781_section_1256_net == -20000.0
        assert breakdown.form_6781_short_term == -8000.0   # 40%
        assert breakdown.form_6781_long_term == -12000.0   # 60%


class TestForm8814Integration:
    """Integration tests for Form 8814 with calculator engine."""

    def test_form_8814_populates_breakdown(self):
        """Form 8814 fields appear in breakdown."""
        tax_return = create_tax_return(
            income=Income(
                form_8814=Form8814(
                    children=[
                        ChildIncome(
                            child_name="Junior",
                            child_age=10,
                            taxable_interest=4000.0,
                        ),
                    ],
                ),
            ),
            filing_status=FilingStatus.MARRIED_JOINT,
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        assert breakdown.form_8814_qualifying_children == 1
        # $4,000 - $2,600 excluded = $1,400 to include
        assert breakdown.form_8814_income_to_include == 1400.0
        assert breakdown.form_8814_child_tax > 0

    def test_form_8814_multiple_children(self):
        """Form 8814 with multiple qualifying children."""
        tax_return = create_tax_return(
            income=Income(
                form_8814=Form8814(
                    children=[
                        ChildIncome(
                            child_name="Child 1",
                            child_age=8,
                            taxable_interest=3000.0,
                        ),
                        ChildIncome(
                            child_name="Child 2",
                            child_age=12,
                            ordinary_dividends=2500.0,
                        ),
                    ],
                ),
            ),
            filing_status=FilingStatus.MARRIED_JOINT,
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        assert breakdown.form_8814_qualifying_children == 2


class TestForm8995Integration:
    """Integration tests for Form 8995 with calculator engine."""

    def test_form_8995_populates_breakdown(self):
        """Form 8995 QBI deduction appears in breakdown."""
        tax_return = create_tax_return(
            income=Income(
                form_8995=Form8995(
                    businesses=[
                        QualifiedBusiness(
                            business_name="Consulting LLC",
                            qualified_business_income=100000.0,
                        ),
                    ],
                    taxable_income_before_qbi=100000.0,
                ),
            ),
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        # 20% of $100k = $20k QBI deduction
        assert breakdown.form_8995_qbi_deduction == 20000.0
        assert breakdown.form_8995_below_threshold is True

    def test_form_8995_limited_by_taxable_income(self):
        """QBI deduction limited by taxable income."""
        tax_return = create_tax_return(
            income=Income(
                form_8995=Form8995(
                    businesses=[
                        QualifiedBusiness(
                            business_name="Business",
                            qualified_business_income=100000.0,
                        ),
                    ],
                    taxable_income_before_qbi=50000.0,
                ),
            ),
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        # Limited to 20% of $50k taxable = $10k
        assert breakdown.form_8995_qbi_deduction == 10000.0

    def test_form_8995_loss_carryforward(self):
        """QBI loss creates carryforward."""
        tax_return = create_tax_return(
            income=Income(
                form_8995=Form8995(
                    businesses=[
                        QualifiedBusiness(
                            business_name="Loss Business",
                            qualified_business_income=-30000.0,
                        ),
                    ],
                    taxable_income_before_qbi=50000.0,
                ),
            ),
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        assert breakdown.form_8995_qbi_deduction == 0.0
        assert breakdown.form_8995_loss_carryforward == 30000.0


class TestMultipleFormsIntegration:
    """Integration tests with multiple forms populated."""

    def test_schedule_b_and_d_together(self):
        """Schedule B and D work together."""
        tax_return = create_tax_return(
            income=Income(
                schedule_b=ScheduleB(
                    interest_payers=[
                        InterestPayer(payer_name="Bank", amount=5000.0),
                    ],
                    dividend_payers=[
                        DividendPayer(
                            payer_name="Fund",
                            ordinary_dividends=4000.0,
                            qualified_dividends=3000.0,
                        ),
                    ],
                ),
                schedule_d=ScheduleD(
                    form_8949_box_d=Form8949Summary(
                        box_code="D",
                        proceeds=20000.0,
                        cost_basis=10000.0,
                        adjustments=0.0,
                        gain_loss=10000.0,
                    ),
                ),
            ),
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        assert breakdown.schedule_b_total_interest == 5000.0
        assert breakdown.schedule_b_total_dividends == 4000.0
        assert breakdown.schedule_d_long_term_net == 10000.0

    def test_schedule_e_and_form_8995_together(self):
        """Schedule E and Form 8995 work together."""
        tax_return = create_tax_return(
            income=Income(
                schedule_e=ScheduleE(
                    rental_properties=[
                        RentalProperty(
                            property_address="Rental",
                            rents_received=20000.0,
                            repairs=5000.0,
                        ),
                    ],
                ),
                form_8995=Form8995(
                    businesses=[
                        QualifiedBusiness(
                            business_name="Business",
                            qualified_business_income=50000.0,
                        ),
                    ],
                    taxable_income_before_qbi=80000.0,
                ),
            ),
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        assert breakdown.schedule_e_rental_income == 15000.0
        assert breakdown.form_8995_qbi_deduction == 10000.0

    def test_farm_with_section_1256(self):
        """Schedule F farm income with Form 6781 futures."""
        tax_return = create_tax_return(
            income=Income(
                schedule_f=ScheduleF(
                    farm_income=FarmIncome(produce_sales=80000.0),
                    farm_expenses=FarmExpenses(seeds_plants=20000.0),
                ),
                form_6781=Form6781(
                    section_1256_contracts=[
                        Section1256Contract(
                            description="Corn Futures Hedge",
                            proceeds=15000.0,
                            cost_basis=10000.0,
                        ),
                    ],
                ),
            ),
            filing_status=FilingStatus.MARRIED_JOINT,
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        assert breakdown.schedule_f_net_profit_loss == 60000.0
        assert breakdown.form_6781_section_1256_net == 5000.0


class TestNoFormPopulated:
    """Tests that breakdown fields are zero when forms not populated."""

    def test_no_schedule_a(self):
        """No Schedule A populated - breakdown fields are zero."""
        tax_return = create_tax_return()

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        assert breakdown.schedule_a_total_deductions == 0.0
        assert breakdown.schedule_a_breakdown == {}

    def test_no_schedule_d(self):
        """No Schedule D populated - breakdown fields are zero."""
        tax_return = create_tax_return()

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        assert breakdown.schedule_d_net_gain_loss == 0.0
        assert breakdown.schedule_d_breakdown == {}

    def test_no_form_8995(self):
        """No Form 8995 populated - breakdown fields are zero."""
        tax_return = create_tax_return()

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        assert breakdown.form_8995_qbi_deduction == 0.0
        assert breakdown.form_8995_breakdown == {}
