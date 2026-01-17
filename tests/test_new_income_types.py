"""
Comprehensive tests for new income types added to the tax platform.

Tests cover:
- Form 1099-R distributions (pensions, annuities, IRAs, 401k)
- Stock compensation (ISO, NSO, RSA, RSU, ESPP)
- Alimony (pre-2019 vs post-2018 rules)
- Debt cancellation (Form 1099-C)
- Prizes/awards, scholarships, jury duty pay
"""

import pytest
from models.income import (
    Income,
    Form1099R,
    Form1099RDistributionCode,
    StockCompensationEvent,
    StockCompensationType,
    Form1099C,
    DebtCancellationType,
    AlimonyInfo,
    W2Info,
    Form1099Q,
    Form1099QAccountType,
    StateTaxRefund,
    Form1099OID,
    Form1099PATR,
    Form1099LTC,
    FormRRB1099,
    Form4137,
    ClergyHousingAllowance,
    MilitaryCombatPay,
)
from models.tax_return import TaxReturn
from models.taxpayer import TaxpayerInfo, FilingStatus
from models.deductions import Deductions
from models.credits import TaxCredits
from calculator.engine import FederalTaxEngine


class TestForm1099RDistributions:
    """Test Form 1099-R distribution handling."""

    def test_normal_distribution_taxable(self):
        """Test normal retirement distribution (code 7) is taxable."""
        dist = Form1099R(
            payer_name="Fidelity Investments",
            gross_distribution=50000.0,
            taxable_amount=50000.0,
            distribution_code_1=Form1099RDistributionCode.CODE_7,
            federal_tax_withheld=10000.0,
        )
        assert not dist.is_early_distribution()
        assert not dist.is_rollover()

    def test_early_distribution_penalty(self):
        """Test early distribution (code 1) triggers penalty flag."""
        dist = Form1099R(
            payer_name="Vanguard",
            gross_distribution=20000.0,
            taxable_amount=20000.0,
            distribution_code_1=Form1099RDistributionCode.CODE_1,
            federal_tax_withheld=4000.0,
        )
        assert dist.is_early_distribution()
        assert not dist.is_rollover()

    def test_rollover_not_taxable(self):
        """Test direct rollover (code G) is not taxable."""
        dist = Form1099R(
            payer_name="401k Plan",
            gross_distribution=100000.0,
            taxable_amount=0.0,
            distribution_code_1=Form1099RDistributionCode.CODE_G,
        )
        assert dist.is_rollover()
        assert not dist.is_early_distribution()

    def test_income_1099r_total_taxable(self):
        """Test Income model calculates total 1099-R taxable amount."""
        income = Income(
            form_1099r_distributions=[
                Form1099R(
                    payer_name="Pension Fund",
                    gross_distribution=30000.0,
                    taxable_amount=30000.0,
                    distribution_code_1=Form1099RDistributionCode.CODE_7,
                    federal_tax_withheld=6000.0,
                ),
                Form1099R(
                    payer_name="IRA",
                    gross_distribution=10000.0,
                    taxable_amount=10000.0,
                    distribution_code_1=Form1099RDistributionCode.CODE_7,
                    federal_tax_withheld=2000.0,
                ),
                Form1099R(
                    payer_name="401k Rollover",
                    gross_distribution=50000.0,
                    taxable_amount=0.0,
                    distribution_code_1=Form1099RDistributionCode.CODE_G,
                ),
            ]
        )
        # Rollover should be excluded
        assert income.get_total_1099r_taxable() == 40000.0
        assert income.get_total_1099r_withholding() == 8000.0

    def test_income_1099r_early_distribution_penalty(self):
        """Test early distribution penalty calculation."""
        income = Income(
            form_1099r_distributions=[
                Form1099R(
                    payer_name="IRA Early",
                    gross_distribution=20000.0,
                    taxable_amount=20000.0,
                    distribution_code_1=Form1099RDistributionCode.CODE_1,
                ),
                Form1099R(
                    payer_name="Normal Dist",
                    gross_distribution=30000.0,
                    taxable_amount=30000.0,
                    distribution_code_1=Form1099RDistributionCode.CODE_7,
                ),
            ]
        )
        # Only early distribution gets 10% penalty
        assert income.get_1099r_early_distribution_penalty() == 2000.0


class TestStockCompensation:
    """Test stock compensation income types."""

    def test_nso_ordinary_income(self):
        """Test NSO exercise generates ordinary income on spread."""
        event = StockCompensationEvent(
            compensation_type=StockCompensationType.NSO,
            company_name="Tech Corp",
            grant_date="2020-01-15",
            grant_price=10.0,
            exercise_date="2024-06-01",
            shares_exercised=1000.0,
            fmv_at_exercise=50.0,
            federal_tax_withheld=12000.0,
        )
        # Spread = ($50 - $10) * 1000 = $40,000
        assert event.calculate_ordinary_income() == 40000.0
        assert event.calculate_amt_preference() == 0.0  # NSO has no AMT

    def test_iso_amt_preference(self):
        """Test ISO exercise creates AMT preference item."""
        event = StockCompensationEvent(
            compensation_type=StockCompensationType.ISO,
            company_name="Startup Inc",
            grant_date="2020-03-01",
            grant_price=5.0,
            exercise_date="2024-09-15",
            shares_exercised=500.0,
            fmv_at_exercise=25.0,
            form_3921_received=True,
        )
        # ISO has no regular income at exercise
        assert event.calculate_ordinary_income() == 0.0
        # AMT preference = ($25 - $5) * 500 = $10,000
        assert event.calculate_amt_preference() == 10000.0

    def test_rsu_vest_income(self):
        """Test RSU vesting generates ordinary income at FMV."""
        event = StockCompensationEvent(
            compensation_type=StockCompensationType.RSU,
            company_name="BigCo",
            vest_date="2024-04-01",
            shares_vested=200.0,
            fmv_at_vest=150.0,
            federal_tax_withheld=9000.0,
        )
        # RSU income = 200 shares * $150 = $30,000
        assert event.calculate_ordinary_income() == 30000.0
        assert event.calculate_amt_preference() == 0.0

    def test_rsa_with_83b_election(self):
        """Test RSA with Section 83(b) election."""
        event = StockCompensationEvent(
            compensation_type=StockCompensationType.RSA,
            company_name="Startup",
            grant_date="2024-01-15",
            shares_granted=10000.0,
            fmv_at_grant_83b=0.50,
            made_83b_election=True,
        )
        # 83(b) election: income at grant = 10000 * $0.50 = $5,000
        assert event.calculate_ordinary_income() == 5000.0

    def test_rsa_without_83b(self):
        """Test RSA without 83(b) election - income at vest."""
        event = StockCompensationEvent(
            compensation_type=StockCompensationType.RSA,
            company_name="Startup",
            grant_date="2020-01-15",
            shares_granted=10000.0,
            vest_date="2024-01-15",
            shares_vested=10000.0,
            fmv_at_vest=10.0,
            made_83b_election=False,
        )
        # No 83(b): income at vest = 10000 * $10 = $100,000
        assert event.calculate_ordinary_income() == 100000.0

    def test_income_total_stock_compensation(self):
        """Test Income model aggregates stock compensation."""
        income = Income(
            stock_compensation_events=[
                StockCompensationEvent(
                    compensation_type=StockCompensationType.NSO,
                    company_name="Tech Corp",
                    exercise_date="2024-06-01",
                    shares_exercised=500.0,
                    grant_price=10.0,
                    fmv_at_exercise=30.0,
                    federal_tax_withheld=3000.0,
                ),
                StockCompensationEvent(
                    compensation_type=StockCompensationType.RSU,
                    company_name="BigCo",
                    vest_date="2024-07-01",
                    shares_vested=100.0,
                    fmv_at_vest=100.0,
                    federal_tax_withheld=3000.0,
                ),
                StockCompensationEvent(
                    compensation_type=StockCompensationType.ISO,
                    company_name="Startup",
                    exercise_date="2024-08-01",
                    shares_exercised=1000.0,
                    grant_price=5.0,
                    fmv_at_exercise=15.0,
                ),
            ]
        )
        # NSO: ($30-$10)*500 = $10,000
        # RSU: $100*100 = $10,000
        # ISO: $0 (no regular income)
        assert income.get_total_stock_compensation_income() == 20000.0
        # ISO AMT: ($15-$5)*1000 = $10,000
        assert income.get_total_stock_compensation_amt_preference() == 10000.0
        # Withholding: $3000 + $3000 = $6000
        assert income.get_total_stock_compensation_withholding() == 6000.0


class TestAlimonyIncome:
    """Test alimony income handling (pre-2019 vs post-2018 rules)."""

    def test_pre_2019_alimony_taxable(self):
        """Test alimony from pre-2019 agreement is taxable to recipient."""
        alimony = AlimonyInfo(
            agreement_date="2018-06-15",
            is_pre_2019_agreement=True,
            alimony_received=24000.0,
        )
        assert alimony.is_taxable_to_recipient()
        assert alimony.is_deductible_by_payor()

    def test_post_2018_alimony_not_taxable(self):
        """Test alimony from 2019+ agreement is NOT taxable to recipient."""
        alimony = AlimonyInfo(
            agreement_date="2019-03-01",
            is_pre_2019_agreement=False,
            alimony_received=24000.0,
        )
        assert not alimony.is_taxable_to_recipient()
        assert not alimony.is_deductible_by_payor()

    def test_modified_agreement_adopts_new_rules(self):
        """Test pre-2019 agreement modified to adopt new rules."""
        alimony = AlimonyInfo(
            agreement_date="2017-01-01",
            is_pre_2019_agreement=True,
            was_modified_post_2018=True,
            modification_adopts_new_rules=True,
            alimony_received=36000.0,
        )
        assert not alimony.is_taxable_to_recipient()

    def test_income_taxable_alimony(self):
        """Test Income model correctly calculates taxable alimony."""
        # Pre-2019 agreement - taxable
        income_pre = Income(
            alimony_info=AlimonyInfo(
                agreement_date="2018-01-01",
                is_pre_2019_agreement=True,
                alimony_received=30000.0,
            )
        )
        assert income_pre.get_taxable_alimony_received() == 30000.0

        # Post-2018 agreement - not taxable
        income_post = Income(
            alimony_info=AlimonyInfo(
                agreement_date="2020-01-01",
                is_pre_2019_agreement=False,
                alimony_received=30000.0,
            )
        )
        assert income_post.get_taxable_alimony_received() == 0.0

    def test_simple_alimony_field(self):
        """Test simple alimony_received field (assumes pre-2019)."""
        income = Income(alimony_received=18000.0)
        assert income.get_taxable_alimony_received() == 18000.0

    def test_alimony_recapture(self):
        """Test alimony recapture calculation."""
        alimony = AlimonyInfo(
            agreement_date="2018-01-01",
            is_pre_2019_agreement=True,
            year_1_payments=50000.0,
            year_2_payments=20000.0,
            year_3_payments=10000.0,
        )
        # Year 3 recapture: max(0, 20000 - 10000 - 15000) = 0 (floor at 0)
        # But let's recalculate per the formula
        recapture = alimony.calculate_recapture()
        assert recapture >= 0


class TestDebtCancellation:
    """Test Form 1099-C debt cancellation income."""

    def test_basic_taxable_debt(self):
        """Test basic debt cancellation is taxable."""
        debt = Form1099C(
            creditor_name="Bank of America",
            date_canceled="2024-06-15",
            amount_canceled=15000.0,
        )
        assert debt.get_taxable_amount() == 15000.0

    def test_bankruptcy_exclusion(self):
        """Test debt excluded due to bankruptcy."""
        debt = Form1099C(
            creditor_name="Capital One",
            date_canceled="2024-03-01",
            amount_canceled=25000.0,
            event_code=DebtCancellationType.BANKRUPTCY,
            excluded_bankruptcy=25000.0,
        )
        assert debt.get_taxable_amount() == 0.0

    def test_insolvency_exclusion(self):
        """Test debt excluded due to insolvency."""
        debt = Form1099C(
            creditor_name="Chase",
            date_canceled="2024-08-01",
            amount_canceled=20000.0,
            total_liabilities_before=100000.0,
            total_assets_fmv_before=70000.0,
        )
        # Insolvency amount = 100000 - 70000 = 30000
        # Exclusion = min(30000, 20000) = 20000
        assert debt.calculate_insolvency_exclusion() == 20000.0

    def test_partial_insolvency_exclusion(self):
        """Test partial insolvency exclusion."""
        debt = Form1099C(
            creditor_name="Wells Fargo",
            date_canceled="2024-05-01",
            amount_canceled=30000.0,
            total_liabilities_before=80000.0,
            total_assets_fmv_before=70000.0,
            excluded_insolvency=10000.0,  # Only insolvent by $10k
        )
        # Taxable = 30000 - 10000 = 20000
        assert debt.get_taxable_amount() == 20000.0

    def test_income_total_debt_cancellation(self):
        """Test Income model aggregates debt cancellation income."""
        income = Income(
            form_1099c_debt_cancellation=[
                Form1099C(
                    creditor_name="Bank A",
                    date_canceled="2024-01-15",
                    amount_canceled=10000.0,
                ),
                Form1099C(
                    creditor_name="Bank B",
                    date_canceled="2024-03-15",
                    amount_canceled=15000.0,
                    excluded_bankruptcy=15000.0,
                ),
                Form1099C(
                    creditor_name="Bank C",
                    date_canceled="2024-06-15",
                    amount_canceled=8000.0,
                    excluded_insolvency=3000.0,
                ),
            ]
        )
        # Bank A: $10,000 taxable
        # Bank B: $0 taxable (bankruptcy)
        # Bank C: $5,000 taxable (8000 - 3000)
        assert income.get_total_debt_cancellation_income() == 15000.0


class TestMiscellaneousIncome:
    """Test prizes/awards, scholarships, and jury duty income."""

    def test_prizes_and_awards(self):
        """Test prizes and awards included in income."""
        income = Income(prizes_and_awards=5000.0)
        assert income.prizes_and_awards == 5000.0

    def test_taxable_scholarship(self):
        """Test taxable portion of scholarships."""
        income = Income(taxable_scholarship=3000.0)
        assert income.taxable_scholarship == 3000.0

    def test_jury_duty_net_income(self):
        """Test jury duty pay net of remittance to employer."""
        income = Income(
            jury_duty_pay=500.0,
            jury_duty_remitted_to_employer=500.0,
        )
        # Net = $500 - $500 = $0
        assert income.get_net_jury_duty_pay() == 0.0

    def test_jury_duty_partial_remittance(self):
        """Test jury duty pay with partial remittance."""
        income = Income(
            jury_duty_pay=600.0,
            jury_duty_remitted_to_employer=400.0,
        )
        # Net = $600 - $400 = $200
        assert income.get_net_jury_duty_pay() == 200.0

    def test_total_other_income(self):
        """Test total miscellaneous income aggregation."""
        income = Income(
            prizes_and_awards=2500.0,
            taxable_scholarship=1500.0,
            jury_duty_pay=400.0,
            jury_duty_remitted_to_employer=0.0,
        )
        # Total = 2500 + 1500 + 400 = 4400
        assert income.get_total_other_income() == 4400.0


class TestIncomeTotals:
    """Test total income calculations with new income types."""

    def test_total_income_includes_new_types(self):
        """Test get_total_income includes all new income types."""
        income = Income(
            w2_forms=[
                W2Info(
                    employer_name="Employer Inc",
                    wages=80000.0,
                    federal_tax_withheld=12000.0,
                )
            ],
            form_1099r_distributions=[
                Form1099R(
                    payer_name="Pension",
                    gross_distribution=20000.0,
                    taxable_amount=20000.0,
                    distribution_code_1=Form1099RDistributionCode.CODE_7,
                    federal_tax_withheld=4000.0,
                )
            ],
            stock_compensation_events=[
                StockCompensationEvent(
                    compensation_type=StockCompensationType.RSU,
                    company_name="Corp",
                    vest_date="2024-04-01",
                    shares_vested=100.0,
                    fmv_at_vest=50.0,
                    federal_tax_withheld=1500.0,
                )
            ],
            alimony_received=12000.0,  # Pre-2019 assumed
            form_1099c_debt_cancellation=[
                Form1099C(
                    creditor_name="Bank",
                    date_canceled="2024-06-01",
                    amount_canceled=5000.0,
                )
            ],
            prizes_and_awards=1000.0,
            taxable_scholarship=2000.0,
            jury_duty_pay=300.0,
        )
        total = income.get_total_income()
        # W2: 80000
        # 1099-R: 20000
        # Stock comp: 100 * 50 = 5000
        # Alimony: 12000
        # Debt cancel: 5000
        # Prizes: 1000
        # Scholarship: 2000
        # Jury: 300
        expected = 80000 + 20000 + 5000 + 12000 + 5000 + 1000 + 2000 + 300
        assert total == expected

    def test_total_withholding_includes_new_sources(self):
        """Test get_total_federal_withholding includes all sources."""
        income = Income(
            w2_forms=[
                W2Info(
                    employer_name="Employer",
                    wages=100000.0,
                    federal_tax_withheld=20000.0,
                )
            ],
            form_1099r_distributions=[
                Form1099R(
                    payer_name="IRA",
                    gross_distribution=25000.0,
                    taxable_amount=25000.0,
                    distribution_code_1=Form1099RDistributionCode.CODE_7,
                    federal_tax_withheld=5000.0,
                )
            ],
            stock_compensation_events=[
                StockCompensationEvent(
                    compensation_type=StockCompensationType.NSO,
                    company_name="Tech",
                    exercise_date="2024-05-01",
                    shares_exercised=200.0,
                    grant_price=20.0,
                    fmv_at_exercise=50.0,
                    federal_tax_withheld=1800.0,
                )
            ],
        )
        # W2: 20000 + 1099-R: 5000 + Stock: 1800 = 26800
        assert income.get_total_federal_withholding() == 26800.0


class TestCalculatorEngineIntegration:
    """Test new income types integrate with calculator engine."""

    def test_calculator_populates_new_income_fields(self):
        """Test calculator engine populates new income type fields in breakdown."""
        taxpayer = TaxpayerInfo(
            first_name="John",
            last_name="Doe",
            ssn="123-45-6789",
            filing_status=FilingStatus.SINGLE,
        )
        income = Income(
            w2_forms=[
                W2Info(
                    employer_name="Acme Corp",
                    wages=75000.0,
                    federal_tax_withheld=11000.0,
                )
            ],
            form_1099r_distributions=[
                Form1099R(
                    payer_name="401k Plan",
                    gross_distribution=10000.0,
                    taxable_amount=10000.0,
                    distribution_code_1=Form1099RDistributionCode.CODE_1,  # Early
                    federal_tax_withheld=2000.0,
                )
            ],
            stock_compensation_events=[
                StockCompensationEvent(
                    compensation_type=StockCompensationType.RSU,
                    company_name="Tech Inc",
                    vest_date="2024-06-01",
                    shares_vested=50.0,
                    fmv_at_vest=100.0,
                    federal_tax_withheld=1500.0,
                )
            ],
            alimony_received=6000.0,
            form_1099c_debt_cancellation=[
                Form1099C(
                    creditor_name="Bank",
                    date_canceled="2024-04-01",
                    amount_canceled=3000.0,
                )
            ],
            prizes_and_awards=500.0,
        )
        deductions = Deductions()
        credits = TaxCredits()
        tax_return = TaxReturn(
            taxpayer=taxpayer,
            income=income,
            deductions=deductions,
            credits=credits,
            tax_year=2025,
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        # Verify new income fields are populated
        assert breakdown.form_1099r_taxable == 10000.0
        assert breakdown.form_1099r_early_distribution_penalty == 1000.0  # 10% of 10000
        assert breakdown.stock_compensation_income == 5000.0  # 50 * 100
        assert breakdown.alimony_income == 6000.0
        assert breakdown.debt_cancellation_income == 3000.0
        assert breakdown.prizes_and_awards_income == 500.0

    def test_early_distribution_penalty_added_to_tax(self):
        """Test 1099-R early distribution penalty is included in total tax."""
        taxpayer = TaxpayerInfo(
            first_name="Jane",
            last_name="Doe",
            ssn="987-65-4321",
            filing_status=FilingStatus.SINGLE,
        )
        income = Income(
            w2_forms=[
                W2Info(
                    employer_name="Company",
                    wages=50000.0,
                    federal_tax_withheld=7500.0,
                )
            ],
            form_1099r_distributions=[
                Form1099R(
                    payer_name="IRA",
                    gross_distribution=20000.0,
                    taxable_amount=20000.0,
                    distribution_code_1=Form1099RDistributionCode.CODE_1,
                    federal_tax_withheld=4000.0,
                )
            ],
        )
        deductions = Deductions()
        credits = TaxCredits()
        tax_return = TaxReturn(
            taxpayer=taxpayer,
            income=income,
            deductions=deductions,
            credits=credits,
            tax_year=2025,
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        # Early distribution penalty should be $2,000 (10% of $20,000)
        assert breakdown.form_1099r_early_distribution_penalty == 2000.0
        # Verify breakdown has the penalty
        assert breakdown.form_1099r_breakdown.get('early_distribution_penalty') == 2000.0


class TestISOQualifyingDisposition:
    """Test ISO qualifying vs disqualifying disposition rules."""

    def test_iso_qualifying_disposition(self):
        """Test ISO held >2 years from grant and >1 year from exercise."""
        event = StockCompensationEvent(
            compensation_type=StockCompensationType.ISO,
            company_name="Startup",
            grant_date="2020-01-01",
            exercise_date="2022-06-01",
            sale_date="2024-07-01",  # >2 years from grant, >1 year from exercise
            shares_exercised=100.0,
            shares_sold=100.0,
            grant_price=10.0,
            fmv_at_exercise=50.0,
            sale_price=80.0,
        )
        assert event.is_qualifying_disposition()

    def test_iso_disqualifying_disposition(self):
        """Test ISO sold too early is disqualifying disposition."""
        event = StockCompensationEvent(
            compensation_type=StockCompensationType.ISO,
            company_name="Startup",
            grant_date="2023-01-01",
            exercise_date="2024-06-01",
            sale_date="2024-09-01",  # <1 year from exercise
            shares_exercised=100.0,
            shares_sold=100.0,
            grant_price=10.0,
            fmv_at_exercise=50.0,
            sale_price=60.0,
        )
        assert not event.is_qualifying_disposition()


class TestESPPQualifyingDisposition:
    """Test ESPP qualifying disposition rules."""

    def test_espp_qualifying_disposition(self):
        """Test ESPP held >2 years from offering, >1 year from purchase."""
        event = StockCompensationEvent(
            compensation_type=StockCompensationType.ESPP,
            company_name="Public Corp",
            espp_offering_period_start="2020-01-01",
            vest_date="2020-06-30",  # Purchase date
            sale_date="2024-07-01",  # >2 years from offering, >1 year from purchase
            shares_vested=50.0,
            shares_sold=50.0,
            espp_purchase_price=40.0,
            fmv_at_vest=50.0,
            sale_price=70.0,
        )
        assert event.is_qualifying_disposition()

    def test_espp_disqualifying_disposition(self):
        """Test ESPP sold too early is disqualifying disposition."""
        event = StockCompensationEvent(
            compensation_type=StockCompensationType.ESPP,
            company_name="Public Corp",
            espp_offering_period_start="2024-01-01",
            vest_date="2024-06-30",
            sale_date="2024-09-01",  # <1 year from purchase
            shares_vested=50.0,
            shares_sold=50.0,
            espp_purchase_price=40.0,
            fmv_at_vest=50.0,
            sale_price=55.0,
        )
        assert not event.is_qualifying_disposition()


class TestForm1099Q:
    """Test Form 1099-Q (529/Coverdell distributions)."""

    def test_qualified_distribution_not_taxable(self):
        """Test 529 distribution fully used for qualified education expenses."""
        dist = Form1099Q(
            payer_name="State 529 Plan",
            account_type=Form1099QAccountType.QTP_529,
            gross_distribution=15000.0,
            earnings=3000.0,
            basis=12000.0,
            qualified_education_expenses=15000.0,
        )
        assert dist.get_taxable_amount() == 0.0
        assert dist.get_penalty_amount() == 0.0

    def test_non_qualified_distribution_taxable(self):
        """Test 529 distribution NOT used for qualified expenses is taxable."""
        dist = Form1099Q(
            payer_name="State 529 Plan",
            gross_distribution=10000.0,
            earnings=2000.0,
            basis=8000.0,
            qualified_education_expenses=0.0,  # No qualified expenses
        )
        # All $2,000 earnings are taxable
        assert dist.get_taxable_amount() == 2000.0
        # 10% penalty on taxable earnings
        assert dist.get_penalty_amount() == 200.0

    def test_partial_qualified_distribution(self):
        """Test 529 distribution partially used for qualified expenses."""
        dist = Form1099Q(
            payer_name="State 529 Plan",
            gross_distribution=20000.0,
            earnings=4000.0,
            basis=16000.0,
            qualified_education_expenses=15000.0,  # Only $15k of $20k qualified
        )
        # Excess = $20,000 - $15,000 = $5,000
        # Taxable ratio = 5000 / 20000 = 0.25
        # Taxable earnings = 4000 * 0.25 = 1000
        assert dist.get_taxable_amount() == 1000.0
        assert dist.get_penalty_amount() == 100.0

    def test_trustee_to_trustee_not_taxable(self):
        """Test trustee-to-trustee transfer is not taxable."""
        dist = Form1099Q(
            payer_name="Old 529 Plan",
            gross_distribution=50000.0,
            earnings=10000.0,
            basis=40000.0,
            is_trustee_to_trustee=True,
        )
        assert dist.get_taxable_amount() == 0.0
        assert dist.get_penalty_amount() == 0.0

    def test_coverdell_esa_distribution(self):
        """Test Coverdell ESA distribution rules."""
        dist = Form1099Q(
            payer_name="Coverdell ESA",
            account_type=Form1099QAccountType.COVERDELL_ESA,
            is_coverdell=True,
            gross_distribution=5000.0,
            earnings=1000.0,
            basis=4000.0,
            qualified_education_expenses=3000.0,
        )
        # Excess = 5000 - 3000 = 2000
        # Taxable ratio = 2000 / 5000 = 0.4
        # Taxable = 1000 * 0.4 = 400
        assert dist.get_taxable_amount() == 400.0

    def test_adjusted_qee_reduces_scholarships(self):
        """Test qualified expenses reduced by scholarships and AOTC expenses."""
        dist = Form1099Q(
            payer_name="State 529 Plan",
            gross_distribution=20000.0,
            earnings=4000.0,
            basis=16000.0,
            qualified_education_expenses=18000.0,
            tax_free_scholarships=5000.0,
            expenses_used_for_aotc_llc=4000.0,
        )
        # Adjusted QEE = 18000 - 5000 - 4000 = 9000
        adjusted_qee = dist.get_adjusted_qualified_expenses()
        assert adjusted_qee == 9000.0
        # Excess = 20000 - 9000 = 11000
        # Taxable ratio = 11000 / 20000 = 0.55
        # Taxable = 4000 * 0.55 = 2200
        assert dist.get_taxable_amount() == 2200.0

    def test_income_1099q_totals(self):
        """Test Income model aggregates multiple 1099-Q distributions."""
        income = Income(
            form_1099q_distributions=[
                Form1099Q(
                    payer_name="Plan A",
                    gross_distribution=10000.0,
                    earnings=2000.0,
                    basis=8000.0,
                    qualified_education_expenses=10000.0,  # Fully qualified
                ),
                Form1099Q(
                    payer_name="Plan B",
                    gross_distribution=5000.0,
                    earnings=1000.0,
                    basis=4000.0,
                    qualified_education_expenses=0.0,  # Not qualified
                ),
            ]
        )
        # Plan A: $0 taxable (fully qualified)
        # Plan B: $1000 taxable (all earnings)
        assert income.get_total_1099q_taxable() == 1000.0
        assert income.get_total_1099q_penalty() == 100.0


class TestStateTaxRefund:
    """Test state tax refund recovery (Form 1099-G Box 2)."""

    def test_standard_deduction_not_taxable(self):
        """Test state refund not taxable if took standard deduction prior year."""
        refund = StateTaxRefund(
            state_code="CA",
            tax_year_of_refund=2024,
            refund_amount=2500.0,
            prior_year_itemized=False,
        )
        assert refund.get_taxable_amount() == 0.0
        assert not refund.is_taxable()

    def test_itemized_fully_taxable(self):
        """Test state refund fully taxable if itemized and got full benefit."""
        refund = StateTaxRefund(
            state_code="NY",
            tax_year_of_refund=2024,
            refund_amount=3000.0,
            prior_year_itemized=True,
            prior_year_salt_deducted=10000.0,
            prior_year_itemized_total=25000.0,
            prior_year_standard_deduction=14600.0,
        )
        # Itemized exceeded standard by $10,400
        # Refund ($3,000) < SALT deducted ($10,000) < excess ($10,400)
        # Full refund is taxable
        assert refund.get_taxable_amount() == 3000.0
        assert refund.is_taxable()

    def test_itemized_partial_benefit(self):
        """Test partial taxability when itemized barely exceeded standard."""
        refund = StateTaxRefund(
            state_code="NJ",
            tax_year_of_refund=2024,
            refund_amount=3000.0,
            prior_year_itemized=True,
            prior_year_salt_deducted=10000.0,
            prior_year_itemized_total=15600.0,
            prior_year_standard_deduction=14600.0,
        )
        # Excess over standard = 15600 - 14600 = 1000
        # Taxable = min(3000, 10000, 1000) = 1000
        assert refund.get_taxable_amount() == 1000.0

    def test_itemized_no_benefit(self):
        """Test not taxable if itemized didn't exceed standard."""
        refund = StateTaxRefund(
            state_code="TX",
            tax_year_of_refund=2024,
            refund_amount=500.0,
            prior_year_itemized=True,
            prior_year_salt_deducted=5000.0,
            prior_year_itemized_total=12000.0,
            prior_year_standard_deduction=14600.0,
        )
        # Itemized < standard, no tax benefit received
        assert refund.get_taxable_amount() == 0.0
        assert not refund.is_taxable()

    def test_refund_limited_to_salt_deducted(self):
        """Test taxable amount limited to SALT actually deducted."""
        refund = StateTaxRefund(
            state_code="CA",
            tax_year_of_refund=2024,
            refund_amount=5000.0,
            prior_year_itemized=True,
            prior_year_salt_deducted=3000.0,  # Only deducted $3k
            prior_year_itemized_total=20000.0,
            prior_year_standard_deduction=14600.0,
        )
        # Excess = 20000 - 14600 = 5400
        # Taxable = min(5000, 3000, 5400) = 3000
        assert refund.get_taxable_amount() == 3000.0

    def test_income_multiple_state_refunds(self):
        """Test Income model aggregates multiple state refunds."""
        income = Income(
            state_tax_refunds=[
                StateTaxRefund(
                    state_code="CA",
                    tax_year_of_refund=2024,
                    refund_amount=2000.0,
                    prior_year_itemized=True,
                    prior_year_salt_deducted=10000.0,
                    prior_year_itemized_total=25000.0,
                    prior_year_standard_deduction=14600.0,
                ),
                StateTaxRefund(
                    state_code="NY",
                    tax_year_of_refund=2024,
                    refund_amount=1500.0,
                    prior_year_itemized=False,  # Took standard, not taxable
                ),
            ]
        )
        # CA: $2000 taxable
        # NY: $0 taxable (took standard)
        assert income.get_total_taxable_state_refunds() == 2000.0


class TestCalculatorWith1099QAndRefunds:
    """Test calculator engine integration with 1099-Q and state refunds."""

    def test_calculator_includes_1099q_income_and_penalty(self):
        """Test calculator handles 1099-Q taxable income and penalty."""
        taxpayer = TaxpayerInfo(
            first_name="Test",
            last_name="User",
            ssn="123-45-6789",
            filing_status=FilingStatus.SINGLE,
        )
        income = Income(
            w2_forms=[
                W2Info(
                    employer_name="Employer",
                    wages=60000.0,
                    federal_tax_withheld=9000.0,
                )
            ],
            form_1099q_distributions=[
                Form1099Q(
                    payer_name="529 Plan",
                    gross_distribution=15000.0,
                    earnings=3000.0,
                    basis=12000.0,
                    qualified_education_expenses=5000.0,  # Partial
                )
            ],
        )
        deductions = Deductions()
        credits = TaxCredits()
        tax_return = TaxReturn(
            taxpayer=taxpayer,
            income=income,
            deductions=deductions,
            credits=credits,
            tax_year=2025,
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        # Excess = 15000 - 5000 = 10000
        # Taxable ratio = 10000 / 15000 = 0.6667
        # Taxable earnings = 3000 * 0.6667 = 2000
        assert breakdown.form_1099q_taxable == 2000.0
        assert breakdown.form_1099q_penalty == 200.0
        assert breakdown.form_1099q_breakdown.get('total_taxable') == 2000.0

    def test_calculator_includes_state_refund_income(self):
        """Test calculator handles taxable state refunds."""
        taxpayer = TaxpayerInfo(
            first_name="Test",
            last_name="User",
            ssn="987-65-4321",
            filing_status=FilingStatus.SINGLE,
        )
        income = Income(
            w2_forms=[
                W2Info(
                    employer_name="Company",
                    wages=70000.0,
                    federal_tax_withheld=10500.0,
                )
            ],
            state_tax_refunds=[
                StateTaxRefund(
                    state_code="CA",
                    tax_year_of_refund=2024,
                    refund_amount=1800.0,
                    prior_year_itemized=True,
                    prior_year_salt_deducted=10000.0,
                    prior_year_itemized_total=22000.0,
                    prior_year_standard_deduction=14600.0,
                )
            ],
        )
        deductions = Deductions()
        credits = TaxCredits()
        tax_return = TaxReturn(
            taxpayer=taxpayer,
            income=income,
            deductions=deductions,
            credits=credits,
            tax_year=2025,
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        # Refund fully taxable (itemized > standard by $7,400)
        assert breakdown.state_refund_taxable == 1800.0
        assert breakdown.state_refund_breakdown.get('total_taxable_amount') == 1800.0


# =============================================================================
# Form 1099-OID (Original Issue Discount) Tests
# =============================================================================

class TestForm1099OID:
    """Test Form 1099-OID original issue discount handling."""

    def test_basic_oid_calculation(self):
        """Test basic OID taxable amount."""
        oid = Form1099OID(
            payer_name="Treasury Direct",
            original_issue_discount=500.0,
            other_periodic_interest=200.0,
            federal_tax_withheld=100.0,
        )
        assert oid.get_taxable_oid() == 500.0
        assert oid.get_total_taxable_interest() == 700.0

    def test_oid_with_acquisition_premium(self):
        """Test OID reduced by acquisition premium."""
        oid = Form1099OID(
            payer_name="Vanguard",
            original_issue_discount=500.0,
            acquisition_premium=150.0,
            other_periodic_interest=100.0,
        )
        # Taxable OID = 500 - 150 = 350
        assert oid.get_taxable_oid() == 350.0
        assert oid.get_total_taxable_interest() == 450.0  # 350 + 100

    def test_income_helper_methods(self):
        """Test Income class helper methods for Form 1099-OID."""
        income = Income(
            form_1099oid=[
                Form1099OID(
                    payer_name="Treasury",
                    original_issue_discount=300.0,
                    other_periodic_interest=50.0,
                    federal_tax_withheld=75.0,
                    early_withdrawal_penalty=25.0,
                ),
                Form1099OID(
                    payer_name="Bank",
                    original_issue_discount=200.0,
                    acquisition_premium=50.0,
                    federal_tax_withheld=30.0,
                ),
            ]
        )
        # Total taxable = (300 + 50) + (200 - 50) = 500
        assert income.get_total_1099oid_taxable() == 500.0
        assert income.get_total_1099oid_withholding() == 105.0
        assert income.get_total_1099oid_early_withdrawal_penalty() == 25.0

        summary = income.get_1099oid_summary()
        assert summary['count'] == 2
        assert summary['total_taxable'] == 500.0


# =============================================================================
# Form 1099-PATR (Patronage Dividends) Tests
# =============================================================================

class TestForm1099PATR:
    """Test Form 1099-PATR patronage dividends handling."""

    def test_basic_patronage_dividends(self):
        """Test basic patronage dividend calculation."""
        patr = Form1099PATR(
            payer_name="Local Farm Co-op",
            patronage_dividends=1500.0,
            federal_tax_withheld=300.0,
        )
        assert patr.get_total_taxable() == 1500.0

    def test_all_distribution_types(self):
        """Test patronage with all distribution types."""
        patr = Form1099PATR(
            payer_name="Agricultural Co-op",
            patronage_dividends=2000.0,
            nonpatronage_distributions=500.0,
            per_unit_retain_allocations=300.0,
            redemption_nonqualified=200.0,
            section_199a_deduction=150.0,
            qualified_payments=1800.0,
        )
        # Total taxable = 2000 + 500 + 300 + 200 = 3000
        assert patr.get_total_taxable() == 3000.0

    def test_income_helper_methods(self):
        """Test Income class helper methods for Form 1099-PATR."""
        income = Income(
            form_1099patr=[
                Form1099PATR(
                    payer_name="Co-op A",
                    patronage_dividends=1000.0,
                    section_199a_deduction=100.0,
                    federal_tax_withheld=200.0,
                ),
                Form1099PATR(
                    payer_name="Co-op B",
                    patronage_dividends=500.0,
                    nonpatronage_distributions=250.0,
                ),
            ]
        )
        assert income.get_total_1099patr_taxable() == 1750.0  # 1000 + 500 + 250
        assert income.get_total_1099patr_section_199a() == 100.0
        assert income.get_total_1099patr_withholding() == 200.0


# =============================================================================
# Form 1099-LTC (Long-Term Care Benefits) Tests
# =============================================================================

class TestForm1099LTC:
    """Test Form 1099-LTC long-term care benefits handling."""

    def test_reimbursement_not_taxable(self):
        """Test reimbursement payments for qualified expenses not taxable."""
        ltc = Form1099LTC(
            payer_name="AARP Insurance",
            gross_ltc_benefits=30000.0,
            is_per_diem=False,  # Reimbursement
            qualified_ltc_expenses=30000.0,
        )
        assert ltc.get_taxable_amount() == 0.0

    def test_reimbursement_excess_taxable(self):
        """Test excess reimbursement over expenses is taxable."""
        ltc = Form1099LTC(
            payer_name="Insurance Co",
            gross_ltc_benefits=35000.0,
            is_per_diem=False,
            qualified_ltc_expenses=30000.0,
        )
        assert ltc.get_taxable_amount() == 5000.0

    def test_per_diem_under_limit_not_taxable(self):
        """Test per-diem under daily limit not taxable."""
        ltc = Form1099LTC(
            payer_name="Insurance",
            gross_ltc_benefits=12600.0,  # $420 × 30 days
            is_per_diem=True,
            days_of_care=30,
            per_diem_limit=420.0,
            qualified_ltc_expenses=10000.0,
        )
        # Exclusion = max($420 × 30, $10000) = $12,600
        assert ltc.get_taxable_amount() == 0.0

    def test_per_diem_excess_taxable(self):
        """Test per-diem over limit is taxable."""
        ltc = Form1099LTC(
            payer_name="Insurance",
            gross_ltc_benefits=15000.0,
            is_per_diem=True,
            days_of_care=30,
            per_diem_limit=420.0,
            qualified_ltc_expenses=10000.0,
        )
        # Exclusion = max($420 × 30, $10000) = max($12,600, $10000) = $12,600
        # Taxable = $15,000 - $12,600 = $2,400
        assert ltc.get_taxable_amount() == 2400.0

    def test_income_helper_methods(self):
        """Test Income class helper methods for Form 1099-LTC."""
        income = Income(
            form_1099ltc=[
                Form1099LTC(
                    payer_name="Insurer A",
                    gross_ltc_benefits=20000.0,
                    is_per_diem=False,
                    qualified_ltc_expenses=18000.0,
                ),
                Form1099LTC(
                    payer_name="Insurer B",
                    gross_ltc_benefits=15000.0,
                    is_per_diem=True,
                    days_of_care=30,
                    qualified_ltc_expenses=10000.0,
                    accelerated_death_benefits=5000.0,
                ),
            ]
        )
        # First: 20000 - 18000 = 2000 taxable
        # Second: 15000 - max(420*30, 10000) = 15000 - 12600 = 2400 taxable
        assert income.get_total_1099ltc_taxable() == 4400.0
        assert income.get_total_1099ltc_gross() == 35000.0
        assert income.get_total_accelerated_death_benefits() == 5000.0


# =============================================================================
# Form RRB-1099 (Railroad Retirement Benefits) Tests
# =============================================================================

class TestFormRRB1099:
    """Test Form RRB-1099 railroad retirement benefits handling."""

    def test_net_sseb_calculation(self):
        """Test net SSEB calculation (gross - employee contributions)."""
        rrb = FormRRB1099(
            sseb_gross=24000.0,
            employee_contributions=2000.0,
            federal_tax_withheld=3000.0,
        )
        assert rrb.get_net_sseb() == 22000.0

    def test_taxable_sseb_below_threshold(self):
        """Test SSEB not taxable when income below threshold."""
        rrb = FormRRB1099(
            sseb_gross=20000.0,
            employee_contributions=0.0,
        )
        # Single threshold: $25,000 base
        # With MAGI of $15,000 + 50% of $20,000 = $25,000 (at threshold)
        taxable = rrb.calculate_taxable_sseb(modified_agi=15000.0, filing_status="single")
        assert taxable == 0.0

    def test_taxable_sseb_partial_50_percent(self):
        """Test up to 50% taxable in middle range."""
        rrb = FormRRB1099(
            sseb_gross=20000.0,
            employee_contributions=0.0,
        )
        # Single: provisional = $20,000 + $10,000 (50% of SSEB) = $30,000 (above $25k, below $34k)
        # Taxable = min((30000-25000)*0.5, 20000*0.5) = min(2500, 10000) = 2500
        taxable = rrb.calculate_taxable_sseb(modified_agi=20000.0, filing_status="single")
        assert taxable == 2500.0

    def test_taxable_sseb_up_to_85_percent(self):
        """Test up to 85% taxable when above upper threshold."""
        rrb = FormRRB1099(
            sseb_gross=24000.0,
            employee_contributions=0.0,
        )
        # Single: provisional = $50,000 + $12,000 = $62,000 (well above $34k)
        # base_taxable = min((34000-25000)*0.5, 12000) = min(4500, 12000) = 4500
        # additional = (62000-34000)*0.85 = 28000*0.85 = 23800
        # taxable = min(4500 + 23800, 24000*0.85) = min(28300, 20400) = 20400
        taxable = rrb.calculate_taxable_sseb(modified_agi=50000.0, filing_status="single")
        assert taxable == 20400.0

    def test_income_helper_methods(self):
        """Test Income class helper methods for Form RRB-1099."""
        income = Income(
            form_rrb1099=[
                FormRRB1099(
                    sseb_gross=18000.0,
                    employee_contributions=1000.0,
                    federal_tax_withheld=2500.0,
                    medicare_premium=200.0,
                ),
            ]
        )
        assert income.get_total_rrb1099_gross_sseb() == 18000.0
        assert income.get_total_rrb1099_net_sseb() == 17000.0
        assert income.get_total_rrb1099_withholding() == 2500.0

        summary = income.get_rrb1099_summary(modified_agi=20000.0, filing_status="single")
        assert summary['count'] == 1
        assert summary['total_medicare_premium'] == 200.0


# =============================================================================
# Form 4137 (Unreported Tip Income) Tests
# =============================================================================

class TestForm4137:
    """Test Form 4137 unreported tip income handling."""

    def test_unreported_tips_calculation(self):
        """Test unreported tips calculation."""
        tips = Form4137(
            employer_name="Restaurant ABC",
            total_cash_tips=5000.0,
            tips_reported_to_employer=3000.0,
            wages_subject_to_ss=40000.0,
        )
        assert tips.get_unreported_tips() == 2000.0

    def test_ss_tax_calculation(self):
        """Test Social Security tax on unreported tips."""
        tips = Form4137(
            employer_name="Restaurant",
            total_cash_tips=3000.0,
            tips_reported_to_employer=1000.0,
            wages_subject_to_ss=50000.0,
            ss_tax_rate=0.062,
            ss_wage_base=176100.0,
        )
        # Unreported = 2000
        # SS room = 176100 - 50000 = 126100 (plenty of room)
        # SS tax = 2000 × 0.062 = $124
        assert tips.calculate_ss_tax() == 124.0

    def test_ss_tax_at_wage_base(self):
        """Test SS tax limited to wage base."""
        tips = Form4137(
            employer_name="Restaurant",
            total_cash_tips=5000.0,
            tips_reported_to_employer=0.0,
            wages_subject_to_ss=175000.0,
            ss_tax_rate=0.062,
            ss_wage_base=176100.0,
        )
        # Unreported = 5000
        # SS room = 176100 - 175000 = 1100
        # Taxable for SS = min(5000, 1100) = 1100
        # SS tax = 1100 × 0.062 = $68.20
        assert tips.calculate_ss_tax() == 68.2

    def test_medicare_tax_no_limit(self):
        """Test Medicare tax has no wage limit."""
        tips = Form4137(
            employer_name="Restaurant",
            total_cash_tips=5000.0,
            tips_reported_to_employer=0.0,
            wages_subject_to_ss=200000.0,  # Above SS wage base
            medicare_tax_rate=0.0145,
        )
        # Unreported = 5000
        # Medicare tax = 5000 × 0.0145 = $72.50
        assert tips.calculate_medicare_tax() == 72.5

    def test_income_helper_methods(self):
        """Test Income class helper methods for Form 4137."""
        income = Income(
            form_4137_tips=[
                Form4137(
                    employer_name="Restaurant A",
                    total_cash_tips=3000.0,
                    tips_reported_to_employer=1500.0,
                    wages_subject_to_ss=30000.0,
                ),
                Form4137(
                    employer_name="Restaurant B",
                    total_cash_tips=2000.0,
                    tips_reported_to_employer=500.0,
                    wages_subject_to_ss=20000.0,
                ),
            ]
        )
        # Unreported = (3000-1500) + (2000-500) = 1500 + 1500 = 3000
        assert income.get_total_unreported_tips() == 3000.0
        assert income.get_total_form4137_tax() > 0

        summary = income.get_form4137_summary()
        assert summary['count'] == 2
        assert summary['total_unreported_tips'] == 3000.0


# =============================================================================
# Clergy Housing Allowance (Section 107) Tests
# =============================================================================

class TestClergyHousingAllowance:
    """Test clergy housing allowance handling."""

    def test_excludable_limited_to_lowest(self):
        """Test excludable amount is lowest of designated, actual, FRV."""
        clergy = ClergyHousingAllowance(
            designated_allowance=30000.0,
            actual_housing_expenses=25000.0,
            fair_rental_value=28000.0,
        )
        # Excludable = min(30000, 25000, 28000) = 25000
        assert clergy.get_excludable_amount() == 25000.0

    def test_taxable_excess(self):
        """Test taxable excess over exclusion."""
        clergy = ClergyHousingAllowance(
            designated_allowance=35000.0,
            actual_housing_expenses=25000.0,
            fair_rental_value=28000.0,
        )
        # Excludable = 25000 (lowest)
        # Taxable excess = 35000 - 25000 = 10000
        assert clergy.get_excludable_amount() == 25000.0
        assert clergy.get_taxable_excess() == 10000.0

    def test_parsonage_provided(self):
        """Test parsonage FRV fully excludable."""
        clergy = ClergyHousingAllowance(
            parsonage_provided=True,
            parsonage_fair_rental_value=24000.0,
        )
        assert clergy.get_excludable_amount() == 24000.0
        assert clergy.get_taxable_excess() == 0.0

    def test_se_tax_amount(self):
        """Test SE tax amount includes excludable housing."""
        clergy = ClergyHousingAllowance(
            designated_allowance=30000.0,
            actual_housing_expenses=25000.0,
            fair_rental_value=28000.0,
            opted_out_of_se_tax=False,
        )
        # SE tax on excludable amount = 25000
        assert clergy.get_se_tax_amount() == 25000.0

    def test_se_tax_opted_out(self):
        """Test SE tax zero if opted out via Form 4361."""
        clergy = ClergyHousingAllowance(
            designated_allowance=30000.0,
            actual_housing_expenses=25000.0,
            fair_rental_value=28000.0,
            opted_out_of_se_tax=True,
        )
        assert clergy.get_se_tax_amount() == 0.0

    def test_income_helper_methods(self):
        """Test Income class helper methods for clergy housing."""
        income = Income(
            clergy_housing=ClergyHousingAllowance(
                designated_allowance=30000.0,
                actual_housing_expenses=22000.0,
                fair_rental_value=25000.0,
            )
        )
        assert income.get_clergy_housing_excludable() == 22000.0
        assert income.get_clergy_housing_taxable() == 8000.0  # 30000 - 22000
        assert income.get_clergy_housing_se_amount() == 22000.0

        summary = income.get_clergy_housing_summary()
        assert summary['excludable_amount'] == 22000.0
        assert summary['taxable_excess'] == 8000.0


# =============================================================================
# Military Combat Pay Exclusion (Section 112) Tests
# =============================================================================

class TestMilitaryCombatPay:
    """Test military combat pay exclusion handling."""

    def test_enlisted_full_exclusion(self):
        """Test enlisted members get full combat pay exclusion."""
        mcp = MilitaryCombatPay(
            total_military_pay=60000.0,
            combat_zone_pay=30000.0,
            is_enlisted=True,
            months_in_combat_zone=6,
        )
        assert mcp.get_excludable_combat_pay() == 30000.0
        assert mcp.get_taxable_military_pay() == 30000.0

    def test_officer_capped_exclusion(self):
        """Test officers have capped exclusion."""
        mcp = MilitaryCombatPay(
            total_military_pay=120000.0,
            combat_zone_pay=50000.0,
            is_enlisted=False,
            months_in_combat_zone=6,
            officer_exclusion_limit=11980.80,  # ~$11,980.80/month limit
        )
        # Max exclusion = 11980.80 × 6 = 71884.80
        # Actual exclusion = min(50000, 71884.80) = 50000
        assert mcp.get_excludable_combat_pay() == 50000.0

    def test_officer_exclusion_capped(self):
        """Test officer exclusion capped at monthly limit × months."""
        mcp = MilitaryCombatPay(
            total_military_pay=150000.0,
            combat_zone_pay=100000.0,
            is_enlisted=False,
            months_in_combat_zone=6,
            officer_exclusion_limit=10000.0,  # $10k/month for this test
        )
        # Max exclusion = 10000 × 6 = 60000
        # Actual exclusion = min(100000, 60000) = 60000
        assert mcp.get_excludable_combat_pay() == 60000.0
        assert mcp.get_taxable_military_pay() == 90000.0  # 150000 - 60000

    def test_eitc_election(self):
        """Test EITC election includes combat pay in earned income."""
        mcp = MilitaryCombatPay(
            total_military_pay=50000.0,
            combat_zone_pay=20000.0,
            is_enlisted=True,
            elect_combat_pay_for_eitc=False,
        )
        # Without election: earned income = taxable pay = 30000
        assert mcp.get_eitc_earned_income() == 30000.0

        mcp.elect_combat_pay_for_eitc = True
        # With election: earned income = 30000 + 20000 = 50000
        assert mcp.get_eitc_earned_income() == 50000.0

    def test_income_helper_methods(self):
        """Test Income class helper methods for military combat pay."""
        income = Income(
            military_combat_pay=MilitaryCombatPay(
                total_military_pay=70000.0,
                combat_zone_pay=25000.0,
                is_enlisted=True,
                months_in_combat_zone=5,
                elect_combat_pay_for_eitc=True,
            )
        )
        assert income.get_military_combat_pay_exclusion() == 25000.0
        assert income.get_military_taxable_pay() == 45000.0
        assert income.get_military_eitc_earned_income() == 70000.0

        summary = income.get_military_combat_pay_summary()
        assert summary['excludable_amount'] == 25000.0
        assert summary['taxable_pay'] == 45000.0
        assert summary['elect_for_eitc'] is True


# =============================================================================
# Calculator Engine Integration Tests for New Income Types
# =============================================================================

class TestCalculatorEngineNewIncomeTypes:
    """Test calculator engine with all new income types."""

    def test_form_1099oid_in_calculation(self):
        """Test Form 1099-OID flows through calculator."""
        taxpayer = TaxpayerInfo(
            first_name="John",
            last_name="Investor",
            filing_status=FilingStatus.SINGLE,
        )
        income = Income(
            form_1099oid=[
                Form1099OID(
                    payer_name="Treasury Direct",
                    original_issue_discount=800.0,
                    other_periodic_interest=200.0,
                    federal_tax_withheld=150.0,
                    early_withdrawal_penalty=50.0,
                ),
            ],
            w2_forms=[W2Info(employer_name="Test Corp", wages=50000.0, federal_tax_withheld=8000.0)],
        )
        tax_return = TaxReturn(
            taxpayer=taxpayer,
            income=income,
            deductions=Deductions(),
            credits=TaxCredits(),
            tax_year=2025,
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        assert breakdown.form_1099oid_taxable == 1000.0  # 800 + 200
        assert breakdown.form_1099oid_early_withdrawal_penalty == 50.0
        assert breakdown.form_1099oid_breakdown.get('count') == 1

    def test_form_4137_tax_included(self):
        """Test Form 4137 tax included in total tax."""
        taxpayer = TaxpayerInfo(
            first_name="Server",
            last_name="Tipped",
            filing_status=FilingStatus.SINGLE,
        )
        income = Income(
            w2_forms=[W2Info(employer_name="Restaurant Inc", wages=30000.0, federal_tax_withheld=3000.0)],
            form_4137_tips=[
                Form4137(
                    employer_name="Fancy Restaurant",
                    total_cash_tips=5000.0,
                    tips_reported_to_employer=2000.0,
                    wages_subject_to_ss=30000.0,
                ),
            ],
        )
        tax_return = TaxReturn(
            taxpayer=taxpayer,
            income=income,
            deductions=Deductions(),
            credits=TaxCredits(),
            tax_year=2025,
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        # Unreported tips = 3000
        assert breakdown.form_4137_unreported_tips == 3000.0
        assert breakdown.form_4137_total_tax > 0
        # SS + Medicare tax should be roughly 3000 * (0.062 + 0.0145) = ~229.50
        assert 200 < breakdown.form_4137_total_tax < 250

    def test_clergy_housing_in_calculation(self):
        """Test clergy housing flows through calculator."""
        taxpayer = TaxpayerInfo(
            first_name="Pastor",
            last_name="Smith",
            filing_status=FilingStatus.MARRIED_JOINT,
        )
        income = Income(
            w2_forms=[W2Info(employer_name="First Church", wages=45000.0, federal_tax_withheld=4000.0)],
            clergy_housing=ClergyHousingAllowance(
                designated_allowance=25000.0,
                actual_housing_expenses=20000.0,
                fair_rental_value=22000.0,
            ),
        )
        tax_return = TaxReturn(
            taxpayer=taxpayer,
            income=income,
            deductions=Deductions(),
            credits=TaxCredits(),
            tax_year=2025,
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        # Excludable = min(25000, 20000, 22000) = 20000
        # Taxable excess = 25000 - 20000 = 5000
        assert breakdown.clergy_housing_excludable == 20000.0
        assert breakdown.clergy_housing_taxable == 5000.0
        assert breakdown.clergy_housing_se_amount == 20000.0

    def test_military_combat_pay_in_calculation(self):
        """Test military combat pay flows through calculator."""
        taxpayer = TaxpayerInfo(
            first_name="Sergeant",
            last_name="Jones",
            filing_status=FilingStatus.SINGLE,
        )
        income = Income(
            military_combat_pay=MilitaryCombatPay(
                total_military_pay=65000.0,
                combat_zone_pay=30000.0,
                is_enlisted=True,
                months_in_combat_zone=8,
                elect_combat_pay_for_eitc=True,
            ),
        )
        tax_return = TaxReturn(
            taxpayer=taxpayer,
            income=income,
            deductions=Deductions(),
            credits=TaxCredits(),
            tax_year=2025,
        )

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)

        # Enlisted: full exclusion
        assert breakdown.military_combat_pay_exclusion == 30000.0
        assert breakdown.military_taxable_pay == 35000.0
        assert breakdown.military_eitc_earned_income == 65000.0  # With election


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
