"""
Comprehensive tests for Form 1099-INT and Form 1099-DIV

Tests cover:
- All IRS box fields
- Taxable/tax-exempt interest calculations
- Qualified vs nonqualified dividends
- Capital gain distributions
- Foreign tax credit eligibility
- AMT preference items
- Schedule B/D integration
- NIIT calculation inputs
"""

import pytest
from models.form_1099_int_div import (
    Form1099INT, Form1099DIV,
    InvestmentIncomeSummary,
    AccountType, BondType, DividendType,
    StateInfo
)


# =============================================================================
# Form 1099-INT Tests
# =============================================================================

class TestForm1099INTBasic:
    """Test basic Form 1099-INT functionality."""

    def test_basic_taxable_interest(self):
        """Test simple taxable interest."""
        form = Form1099INT(
            payer_name="First National Bank",
            box_1_interest_income=1500.00
        )
        assert form.box_1_interest_income == 1500.00
        assert form.total_taxable_interest == 1500.00

    def test_early_withdrawal_penalty(self):
        """Test early withdrawal penalty (Schedule 1 adjustment)."""
        form = Form1099INT(
            payer_name="Credit Union",
            box_1_interest_income=2000.00,
            box_2_early_withdrawal_penalty=150.00
        )
        assert form.box_2_early_withdrawal_penalty == 150.00
        # Penalty doesn't reduce taxable interest - it's a separate adjustment
        assert form.total_taxable_interest == 2000.00

    def test_us_treasury_interest(self):
        """Test US Savings Bond and Treasury interest (Box 3)."""
        form = Form1099INT(
            payer_name="US Treasury",
            box_1_interest_income=1000.00,
            box_3_us_savings_bonds_treasury=1000.00
        )
        # Treasury interest is taxable federally, but exempt from state tax
        assert form.box_3_us_savings_bonds_treasury == 1000.00
        assert form.total_taxable_interest == 1000.00

    def test_tax_exempt_interest(self):
        """Test tax-exempt municipal bond interest (Box 8)."""
        form = Form1099INT(
            payer_name="Municipal Bond Fund",
            box_1_interest_income=0.0,  # Tax-exempt not in Box 1
            box_8_tax_exempt_interest=3000.00
        )
        assert form.total_taxable_interest == 0.0
        assert form.total_tax_exempt_interest == 3000.00

    def test_private_activity_bond_amt(self):
        """Test private activity bond interest (AMT preference)."""
        form = Form1099INT(
            payer_name="Private Activity Fund",
            box_8_tax_exempt_interest=5000.00,
            box_9_private_activity_bond_interest=3000.00
        )
        assert form.total_tax_exempt_interest == 5000.00
        assert form.amt_preference_interest == 3000.00

    def test_foreign_tax_paid(self):
        """Test foreign tax paid (Form 1116/foreign tax credit)."""
        form = Form1099INT(
            payer_name="International Bank",
            box_1_interest_income=2000.00,
            box_6_foreign_tax_paid=200.00,
            box_7_foreign_country="United Kingdom"
        )
        assert form.box_6_foreign_tax_paid == 200.00
        assert form.box_7_foreign_country == "United Kingdom"
        assert form.has_foreign_tax is True


class TestForm1099INTBondPremium:
    """Test bond premium calculations."""

    def test_bond_premium_reduces_interest(self):
        """Test that bond premium reduces taxable interest."""
        form = Form1099INT(
            payer_name="Bond Fund",
            box_1_interest_income=1000.00,
            box_11_bond_premium=200.00
        )
        assert form.total_taxable_interest == 800.00

    def test_bond_premium_treasury(self):
        """Test bond premium on Treasury obligations (Box 12)."""
        form = Form1099INT(
            payer_name="Treasury Fund",
            box_1_interest_income=1500.00,
            box_3_us_savings_bonds_treasury=1500.00,
            box_12_bond_premium_treasury=100.00
        )
        assert form.box_12_bond_premium_treasury == 100.00

    def test_bond_premium_tax_exempt(self):
        """Test bond premium on tax-exempt bonds (Box 13)."""
        form = Form1099INT(
            payer_name="Muni Fund",
            box_8_tax_exempt_interest=2000.00,
            box_13_bond_premium_tax_exempt=50.00
        )
        assert form.box_13_bond_premium_tax_exempt == 50.00


class TestForm1099INTOther:
    """Test other Form 1099-INT fields."""

    def test_market_discount(self):
        """Test market discount (Box 10)."""
        form = Form1099INT(
            payer_name="Bond Broker",
            box_1_interest_income=500.00,
            box_10_market_discount=50.00
        )
        assert form.box_10_market_discount == 50.00

    def test_oid_bond(self):
        """Test Original Issue Discount bond."""
        form = Form1099INT(
            payer_name="Zero Coupon Bond",
            box_1_interest_income=0.0,
            is_oid=True,
            oid_amount=800.00
        )
        assert form.is_oid is True
        assert form.total_taxable_interest == 800.00

    def test_state_tax_info(self):
        """Test state tax information (Boxes 15-17)."""
        form = Form1099INT(
            payer_name="Multi-State Bank",
            box_1_interest_income=5000.00,
            state_info=[
                StateInfo(state_code="CA", state_id_number="12345", state_tax_withheld=250.00),
                StateInfo(state_code="NY", state_id_number="67890", state_tax_withheld=300.00),
            ]
        )
        assert len(form.state_info) == 2
        assert form.state_info[0].state_code == "CA"
        assert form.state_info[0].state_tax_withheld == 250.00

    def test_schedule_b_entry(self):
        """Test conversion to Schedule B entry."""
        form = Form1099INT(
            payer_name="ABC Bank",
            payer_tin="12-3456789",
            box_1_interest_income=1500.00,
            box_2_early_withdrawal_penalty=75.00,
            box_6_foreign_tax_paid=30.00
        )
        entry = form.to_schedule_b_entry()
        assert entry["payer_name"] == "ABC Bank"
        assert entry["payer_ein"] == "12-3456789"
        assert entry["amount"] == 1500.00
        assert entry["early_withdrawal_penalty"] == 75.00


# =============================================================================
# Form 1099-DIV Tests
# =============================================================================

class TestForm1099DIVBasic:
    """Test basic Form 1099-DIV functionality."""

    def test_ordinary_dividends(self):
        """Test ordinary dividends (Box 1a)."""
        form = Form1099DIV(
            payer_name="Vanguard Total Stock",
            box_1a_ordinary_dividends=2500.00
        )
        assert form.box_1a_ordinary_dividends == 2500.00
        assert form.total_taxable_dividends == 2500.00

    def test_qualified_dividends(self):
        """Test qualified dividends (Box 1b)."""
        form = Form1099DIV(
            payer_name="S&P 500 Index Fund",
            box_1a_ordinary_dividends=3000.00,
            box_1b_qualified_dividends=2800.00
        )
        assert form.box_1b_qualified_dividends == 2800.00
        assert form.nonqualified_dividends == 200.00

    def test_capital_gain_distributions(self):
        """Test capital gain distributions (Box 2a)."""
        form = Form1099DIV(
            payer_name="Growth Fund",
            box_1a_ordinary_dividends=500.00,
            box_2a_capital_gain_distributions=2000.00
        )
        assert form.box_2a_capital_gain_distributions == 2000.00
        assert form.schedule_d_capital_gains == 2000.00

    def test_unrecaptured_1250_gain(self):
        """Test unrecaptured Section 1250 gain (Box 2b)."""
        form = Form1099DIV(
            payer_name="REIT Fund",
            box_2a_capital_gain_distributions=5000.00,
            box_2b_unrecaptured_1250_gain=1000.00
        )
        assert form.box_2b_unrecaptured_1250_gain == 1000.00

    def test_section_1202_gain_qsbs(self):
        """Test Section 1202 QSBS gain (Box 2c)."""
        form = Form1099DIV(
            payer_name="VC Fund",
            box_2a_capital_gain_distributions=10000.00,
            box_2c_section_1202_gain=5000.00
        )
        assert form.box_2c_section_1202_gain == 5000.00

    def test_collectibles_gain(self):
        """Test collectibles (28%) gain (Box 2d)."""
        form = Form1099DIV(
            payer_name="Gold Fund",
            box_2a_capital_gain_distributions=3000.00,
            box_2d_collectibles_gain=3000.00
        )
        assert form.box_2d_collectibles_gain == 3000.00


class TestForm1099DIVSpecialDividends:
    """Test special dividend types."""

    def test_nondividend_distributions(self):
        """Test nondividend distributions (return of capital)."""
        form = Form1099DIV(
            payer_name="MLP Partnership",
            box_1a_ordinary_dividends=1000.00,
            box_3_nondividend_distributions=500.00
        )
        assert form.box_3_nondividend_distributions == 500.00
        assert form.has_return_of_capital is True
        # Return of capital is not taxable (reduces basis)
        assert form.total_taxable_dividends == 1000.00

    def test_section_199a_dividends(self):
        """Test Section 199A REIT/PTP dividends (Box 5)."""
        form = Form1099DIV(
            payer_name="Real Estate Fund",
            box_1a_ordinary_dividends=5000.00,
            box_5_section_199a_dividends=4000.00,
            is_reit=True
        )
        assert form.box_5_section_199a_dividends == 4000.00
        assert form.qbi_eligible_dividends == 4000.00
        assert form.is_reit is True

    def test_section_897_firpta(self):
        """Test Section 897 FIRPTA dividends (Boxes 2e, 2f)."""
        form = Form1099DIV(
            payer_name="REIT",
            box_1a_ordinary_dividends=3000.00,
            box_2a_capital_gain_distributions=2000.00,
            box_2e_section_897_ordinary=1500.00,
            box_2f_section_897_capital_gain=1000.00
        )
        assert form.box_2e_section_897_ordinary == 1500.00
        assert form.box_2f_section_897_capital_gain == 1000.00

    def test_exempt_interest_dividends(self):
        """Test exempt-interest dividends from muni bond funds (Box 12)."""
        form = Form1099DIV(
            payer_name="Tax-Free Bond Fund",
            box_1a_ordinary_dividends=0.0,
            box_12_exempt_interest_dividends=2000.00
        )
        assert form.box_12_exempt_interest_dividends == 2000.00
        assert form.total_tax_exempt == 2000.00

    def test_pab_interest_dividends_amt(self):
        """Test private activity bond interest dividends (AMT)."""
        form = Form1099DIV(
            payer_name="High Yield Muni Fund",
            box_12_exempt_interest_dividends=3000.00,
            box_13_pab_interest_dividends=500.00
        )
        assert form.box_13_pab_interest_dividends == 500.00
        assert form.amt_preference_amount == 500.00


class TestForm1099DIVLiquidation:
    """Test liquidation distributions."""

    def test_cash_liquidation(self):
        """Test cash liquidation distributions (Box 9)."""
        form = Form1099DIV(
            payer_name="Liquidating Company",
            box_9_cash_liquidation=10000.00
        )
        assert form.box_9_cash_liquidation == 10000.00
        assert form.total_liquidation == 10000.00

    def test_noncash_liquidation(self):
        """Test noncash liquidation distributions (Box 10)."""
        form = Form1099DIV(
            payer_name="Liquidating Company",
            box_9_cash_liquidation=5000.00,
            box_10_noncash_liquidation=3000.00
        )
        assert form.total_liquidation == 8000.00


class TestForm1099DIVForeignTax:
    """Test foreign tax credit features."""

    def test_foreign_tax_paid(self):
        """Test foreign tax paid (Box 7)."""
        form = Form1099DIV(
            payer_name="International Fund",
            box_1a_ordinary_dividends=5000.00,
            box_1b_qualified_dividends=4500.00,
            box_7_foreign_tax_paid=500.00,
            box_8_foreign_country="Various"
        )
        assert form.box_7_foreign_tax_paid == 500.00
        assert form.has_foreign_tax is True

    def test_schedule_b_entry(self):
        """Test conversion to Schedule B dividend entry."""
        form = Form1099DIV(
            payer_name="Dividend Fund",
            payer_tin="98-7654321",
            box_1a_ordinary_dividends=3000.00,
            box_1b_qualified_dividends=2500.00,
            box_2a_capital_gain_distributions=1000.00,
            box_4_federal_tax_withheld=300.00,
            box_7_foreign_tax_paid=150.00
        )
        entry = form.to_schedule_b_entry()
        assert entry["payer_name"] == "Dividend Fund"
        assert entry["ordinary_dividends"] == 3000.00
        assert entry["qualified_dividends"] == 2500.00
        assert entry["capital_gain_distributions"] == 1000.00
        assert entry["federal_tax_withheld"] == 300.00


# =============================================================================
# Investment Income Summary Tests
# =============================================================================

class TestInvestmentIncomeSummary:
    """Test InvestmentIncomeSummary aggregation."""

    def test_multiple_1099_int_forms(self):
        """Test aggregating multiple 1099-INT forms."""
        summary = InvestmentIncomeSummary(
            forms_1099_int=[
                Form1099INT(payer_name="Bank A", box_1_interest_income=1000.00),
                Form1099INT(payer_name="Bank B", box_1_interest_income=800.00),
                Form1099INT(payer_name="Bank C", box_1_interest_income=500.00),
            ]
        )
        assert summary.total_taxable_interest == 2300.00

    def test_multiple_1099_div_forms(self):
        """Test aggregating multiple 1099-DIV forms."""
        summary = InvestmentIncomeSummary(
            forms_1099_div=[
                Form1099DIV(
                    payer_name="Fund A",
                    box_1a_ordinary_dividends=2000.00,
                    box_1b_qualified_dividends=1800.00
                ),
                Form1099DIV(
                    payer_name="Fund B",
                    box_1a_ordinary_dividends=1500.00,
                    box_1b_qualified_dividends=1500.00
                ),
            ]
        )
        assert summary.total_ordinary_dividends == 3500.00
        assert summary.total_qualified_dividends == 3300.00

    def test_schedule_b_requirement_interest(self):
        """Test Schedule B required when interest > $1,500."""
        summary = InvestmentIncomeSummary(
            forms_1099_int=[
                Form1099INT(payer_name="Bank", box_1_interest_income=1501.00)
            ]
        )
        assert summary.requires_schedule_b is True

    def test_schedule_b_requirement_dividends(self):
        """Test Schedule B required when dividends > $1,500."""
        summary = InvestmentIncomeSummary(
            forms_1099_div=[
                Form1099DIV(payer_name="Fund", box_1a_ordinary_dividends=1501.00)
            ]
        )
        assert summary.requires_schedule_b is True

    def test_schedule_b_not_required(self):
        """Test Schedule B not required when under threshold."""
        summary = InvestmentIncomeSummary(
            forms_1099_int=[
                Form1099INT(payer_name="Bank", box_1_interest_income=500.00)
            ],
            forms_1099_div=[
                Form1099DIV(payer_name="Fund", box_1a_ordinary_dividends=800.00)
            ]
        )
        assert summary.requires_schedule_b is False

    def test_total_foreign_tax(self):
        """Test total foreign tax paid aggregation."""
        summary = InvestmentIncomeSummary(
            forms_1099_int=[
                Form1099INT(
                    payer_name="Intl Bank",
                    box_1_interest_income=1000.00,
                    box_6_foreign_tax_paid=100.00
                )
            ],
            forms_1099_div=[
                Form1099DIV(
                    payer_name="Intl Fund",
                    box_1a_ordinary_dividends=5000.00,
                    box_7_foreign_tax_paid=400.00
                )
            ]
        )
        assert summary.total_foreign_tax_paid == 500.00

    def test_form_1116_requirement(self):
        """Test Form 1116 requirement (foreign tax > $300)."""
        summary = InvestmentIncomeSummary(
            forms_1099_div=[
                Form1099DIV(
                    payer_name="Intl Fund",
                    box_1a_ordinary_dividends=10000.00,
                    box_7_foreign_tax_paid=350.00
                )
            ]
        )
        assert summary.form_1116_required is True

    def test_form_1116_not_required(self):
        """Test Form 1116 not required (foreign tax <= $300)."""
        summary = InvestmentIncomeSummary(
            forms_1099_div=[
                Form1099DIV(
                    payer_name="Intl Fund",
                    box_1a_ordinary_dividends=5000.00,
                    box_7_foreign_tax_paid=200.00
                )
            ]
        )
        assert summary.form_1116_required is False

    def test_total_capital_gain_distributions(self):
        """Test capital gain distribution aggregation."""
        summary = InvestmentIncomeSummary(
            forms_1099_div=[
                Form1099DIV(
                    payer_name="Fund A",
                    box_2a_capital_gain_distributions=3000.00
                ),
                Form1099DIV(
                    payer_name="Fund B",
                    box_2a_capital_gain_distributions=2000.00
                ),
            ]
        )
        assert summary.total_capital_gain_distributions == 5000.00

    def test_total_amt_preference(self):
        """Test AMT preference aggregation."""
        summary = InvestmentIncomeSummary(
            forms_1099_int=[
                Form1099INT(
                    payer_name="PAB Fund",
                    box_8_tax_exempt_interest=5000.00,
                    box_9_private_activity_bond_interest=2000.00
                )
            ],
            forms_1099_div=[
                Form1099DIV(
                    payer_name="Muni Fund",
                    box_12_exempt_interest_dividends=3000.00,
                    box_13_pab_interest_dividends=500.00
                )
            ]
        )
        assert summary.total_amt_preference == 2500.00

    def test_total_early_withdrawal_penalty(self):
        """Test early withdrawal penalty aggregation."""
        summary = InvestmentIncomeSummary(
            forms_1099_int=[
                Form1099INT(
                    payer_name="Bank A",
                    box_1_interest_income=1000.00,
                    box_2_early_withdrawal_penalty=100.00
                ),
                Form1099INT(
                    payer_name="Bank B",
                    box_1_interest_income=2000.00,
                    box_2_early_withdrawal_penalty=50.00
                ),
            ]
        )
        assert summary.total_early_withdrawal_penalty == 150.00

    def test_investment_income_for_niit(self):
        """Test total investment income for NIIT calculation."""
        summary = InvestmentIncomeSummary(
            forms_1099_int=[
                Form1099INT(payer_name="Bank", box_1_interest_income=5000.00)
            ],
            forms_1099_div=[
                Form1099DIV(
                    payer_name="Fund",
                    box_1a_ordinary_dividends=8000.00,
                    box_2a_capital_gain_distributions=3000.00
                )
            ]
        )
        # NIIT = interest + dividends + capital gain distributions
        assert summary.total_investment_income_niit == 16000.00

    def test_get_form_1040_amounts(self):
        """Test Form 1040 line amounts."""
        summary = InvestmentIncomeSummary(
            forms_1099_int=[
                Form1099INT(
                    payer_name="Bank",
                    box_1_interest_income=2000.00,
                    box_8_tax_exempt_interest=500.00
                )
            ],
            forms_1099_div=[
                Form1099DIV(
                    payer_name="Fund",
                    box_1a_ordinary_dividends=3000.00,
                    box_1b_qualified_dividends=2500.00,
                    box_12_exempt_interest_dividends=200.00
                )
            ]
        )
        amounts = summary.get_form_1040_amounts()
        assert amounts["line_2a_tax_exempt_interest"] == 700.00  # 500 + 200
        assert amounts["line_2b_taxable_interest"] == 2000.00
        assert amounts["line_3a_qualified_dividends"] == 2500.00
        assert amounts["line_3b_ordinary_dividends"] == 3000.00

    def test_get_schedule_d_amounts(self):
        """Test Schedule D amounts."""
        summary = InvestmentIncomeSummary(
            forms_1099_div=[
                Form1099DIV(
                    payer_name="Fund",
                    box_2a_capital_gain_distributions=5000.00,
                    box_2b_unrecaptured_1250_gain=1000.00
                )
            ]
        )
        amounts = summary.get_schedule_d_amounts()
        assert amounts["line_13_capital_gain_distributions"] == 5000.00
        assert amounts["unrecaptured_1250_gain"] == 1000.00

    def test_get_foreign_tax_credit_info(self):
        """Test foreign tax credit information."""
        summary = InvestmentIncomeSummary(
            forms_1099_div=[
                Form1099DIV(
                    payer_name="International Fund",
                    box_1a_ordinary_dividends=10000.00,
                    box_7_foreign_tax_paid=500.00,
                    box_8_foreign_country="Various"
                )
            ]
        )
        info = summary.get_foreign_tax_credit_info()
        assert info["total_foreign_tax"] == 500.00
        assert len(info["sources"]) == 1
        assert info["sources"][0]["country"] == "Various"
        assert info["form_1116_required"] is True


class TestInvestmentIncomeEdgeCases:
    """Test edge cases and validations."""

    def test_empty_summary(self):
        """Test empty investment income summary."""
        summary = InvestmentIncomeSummary()
        assert summary.total_taxable_interest == 0.0
        assert summary.total_ordinary_dividends == 0.0
        assert summary.requires_schedule_b is False

    def test_section_199a_aggregation(self):
        """Test Section 199A dividend aggregation."""
        summary = InvestmentIncomeSummary(
            forms_1099_div=[
                Form1099DIV(
                    payer_name="REIT A",
                    box_1a_ordinary_dividends=3000.00,
                    box_5_section_199a_dividends=2500.00,
                    is_reit=True
                ),
                Form1099DIV(
                    payer_name="REIT B",
                    box_1a_ordinary_dividends=2000.00,
                    box_5_section_199a_dividends=1800.00,
                    is_reit=True
                ),
            ]
        )
        assert summary.total_section_199a_dividends == 4300.00

    def test_nondividend_distribution_aggregation(self):
        """Test nondividend distribution (return of capital) aggregation."""
        summary = InvestmentIncomeSummary(
            forms_1099_div=[
                Form1099DIV(
                    payer_name="MLP A",
                    box_1a_ordinary_dividends=1000.00,
                    box_3_nondividend_distributions=2000.00,
                    is_mlp=True
                ),
                Form1099DIV(
                    payer_name="MLP B",
                    box_1a_ordinary_dividends=500.00,
                    box_3_nondividend_distributions=1500.00,
                    is_mlp=True
                ),
            ]
        )
        assert summary.total_nondividend_distributions == 3500.00

    def test_federal_withholding_aggregation(self):
        """Test federal withholding aggregation."""
        summary = InvestmentIncomeSummary(
            forms_1099_int=[
                Form1099INT(
                    payer_name="Bank",
                    box_1_interest_income=5000.00,
                    box_4_federal_tax_withheld=500.00
                )
            ],
            forms_1099_div=[
                Form1099DIV(
                    payer_name="Fund",
                    box_1a_ordinary_dividends=10000.00,
                    box_4_federal_tax_withheld=1000.00
                )
            ]
        )
        assert summary.total_federal_withholding == 1500.00

    def test_to_dict_serialization(self):
        """Test dictionary serialization."""
        summary = InvestmentIncomeSummary(
            tax_year=2025,
            forms_1099_int=[
                Form1099INT(payer_name="Bank", box_1_interest_income=2000.00)
            ],
            forms_1099_div=[
                Form1099DIV(
                    payer_name="Fund",
                    box_1a_ordinary_dividends=3000.00,
                    box_1b_qualified_dividends=2500.00
                )
            ]
        )
        d = summary.to_dict()
        assert d["tax_year"] == 2025
        assert d["form_count_1099_int"] == 1
        assert d["form_count_1099_div"] == 1
        assert d["total_taxable_interest"] == 2000.00
        assert d["total_ordinary_dividends"] == 3000.00
        assert d["total_qualified_dividends"] == 2500.00


class TestComplexScenarios:
    """Test complex real-world scenarios."""

    def test_diversified_portfolio(self):
        """Test diversified investment portfolio."""
        summary = InvestmentIncomeSummary(
            forms_1099_int=[
                # Savings account
                Form1099INT(
                    payer_name="Savings Bank",
                    box_1_interest_income=500.00
                ),
                # Treasury bonds (state-exempt)
                Form1099INT(
                    payer_name="US Treasury",
                    box_1_interest_income=1000.00,
                    box_3_us_savings_bonds_treasury=1000.00
                ),
                # Municipal bonds (federally exempt)
                Form1099INT(
                    payer_name="CA Muni Fund",
                    box_8_tax_exempt_interest=2000.00,
                    box_9_private_activity_bond_interest=300.00
                ),
            ],
            forms_1099_div=[
                # US stock index fund
                Form1099DIV(
                    payer_name="Total Market Fund",
                    box_1a_ordinary_dividends=5000.00,
                    box_1b_qualified_dividends=4800.00,
                    box_2a_capital_gain_distributions=1500.00
                ),
                # International fund
                Form1099DIV(
                    payer_name="International Fund",
                    box_1a_ordinary_dividends=2000.00,
                    box_1b_qualified_dividends=1600.00,
                    box_7_foreign_tax_paid=200.00,
                    box_8_foreign_country="Various"
                ),
                # REIT
                Form1099DIV(
                    payer_name="Real Estate REIT",
                    box_1a_ordinary_dividends=3000.00,
                    box_1b_qualified_dividends=0.00,  # REIT dividends not qualified
                    box_5_section_199a_dividends=3000.00,
                    is_reit=True
                ),
            ]
        )

        # Verify totals
        assert summary.total_taxable_interest == 1500.00  # 500 + 1000
        assert summary.total_tax_exempt_interest == 2000.00
        assert summary.total_ordinary_dividends == 10000.00  # 5000 + 2000 + 3000
        assert summary.total_qualified_dividends == 6400.00  # 4800 + 1600 + 0
        assert summary.total_capital_gain_distributions == 1500.00
        assert summary.total_section_199a_dividends == 3000.00
        assert summary.total_foreign_tax_paid == 200.00
        assert summary.total_amt_preference == 300.00
        assert summary.requires_schedule_b is True

    def test_high_net_worth_investor(self):
        """Test high net worth investor with NIIT considerations."""
        summary = InvestmentIncomeSummary(
            forms_1099_int=[
                Form1099INT(
                    payer_name="Private Banking",
                    box_1_interest_income=50000.00,
                    box_6_foreign_tax_paid=2000.00,
                    box_7_foreign_country="Switzerland"
                ),
            ],
            forms_1099_div=[
                Form1099DIV(
                    payer_name="Hedge Fund",
                    box_1a_ordinary_dividends=100000.00,
                    box_1b_qualified_dividends=80000.00,
                    box_2a_capital_gain_distributions=50000.00,
                    box_7_foreign_tax_paid=5000.00,
                    box_8_foreign_country="Various"
                ),
            ]
        )

        # NIIT threshold is $200k single / $250k MFJ
        # Total investment income
        assert summary.total_investment_income_niit == 200000.00  # 50k + 100k + 50k
        assert summary.total_foreign_tax_paid == 7000.00
        assert summary.form_1116_required is True
