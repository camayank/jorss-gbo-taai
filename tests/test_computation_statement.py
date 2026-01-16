"""
Tests for Big4-Level Computation Statement and Draft Return Generation

Tests verify:
- Computation statement generation
- Assumptions tracking and footnotes
- Draft return completeness analysis
- Schedule requirement detection
- Professional output formatting
"""

import pytest
from src.models.income import Income, W2Info
from src.models.taxpayer import TaxpayerInfo, FilingStatus
from src.models.deductions import Deductions, ItemizedDeductions
from src.models.credits import TaxCredits
from src.models.tax_return import TaxReturn
from src.calculator.engine import FederalTaxEngine
from src.calculator.tax_year_config import TaxYearConfig
from src.export.computation_statement import (
    TaxComputationStatement,
    AssumptionCategory,
)
from src.export.draft_return import (
    DraftReturnGenerator,
    CompletionStatus,
    generate_complete_draft_package,
)


def make_w2(wages: float, federal_withheld: float = 0.0) -> W2Info:
    """Helper to create W2Info for tests."""
    return W2Info(
        employer_name="Test Employer",
        employer_ein="12-3456789",
        wages=wages,
        federal_tax_withheld=federal_withheld,
    )


@pytest.fixture
def engine():
    return FederalTaxEngine(TaxYearConfig.for_2025())


@pytest.fixture
def sample_tax_return():
    """Create a sample tax return for testing."""
    return TaxReturn(
        tax_year=2025,
        taxpayer=TaxpayerInfo(
            first_name="John",
            last_name="Smith",
            ssn="123-45-6789",
            filing_status=FilingStatus.SINGLE,
        ),
        income=Income(
            w2_forms=[make_w2(85000.0, 12000.0)],
            interest_income=500.0,
            ordinary_dividends=1000.0,
            qualified_dividends=800.0,
        ),
        deductions=Deductions(
            use_standard_deduction=True,
        ),
        credits=TaxCredits(),
    )


class TestComputationStatementGeneration:
    """Tests for computation statement generation."""

    def test_basic_generation(self, engine, sample_tax_return):
        """Test basic computation statement generation."""
        breakdown = engine.calculate(sample_tax_return)

        statement = TaxComputationStatement(
            sample_tax_return,
            breakdown,
            preparer_name="Test CPA",
            firm_name="Test Firm LLP"
        )

        data = statement.generate()

        assert "header" in data
        assert "sections" in data
        assert "assumptions" in data
        assert "footnotes" in data
        assert "validation" in data

    def test_header_content(self, engine, sample_tax_return):
        """Test computation statement header."""
        breakdown = engine.calculate(sample_tax_return)

        statement = TaxComputationStatement(
            sample_tax_return,
            breakdown,
            preparer_name="Jane CPA",
            firm_name="Big4 Firm"
        )

        data = statement.generate()
        header = data["header"]

        assert header["title"] == "COMPUTATION OF FEDERAL INCOME TAX"
        assert "2025" in header["subtitle"]
        assert header["taxpayer"]["name"] == "John Smith"
        assert "6789" in header["taxpayer"]["ssn_masked"]
        assert "Single" in header["taxpayer"]["filing_status"]
        assert header["preparer"] == "Jane CPA"
        assert header["firm"] == "Big4 Firm"

    def test_income_section(self, engine, sample_tax_return):
        """Test income section generation."""
        breakdown = engine.calculate(sample_tax_return)

        statement = TaxComputationStatement(
            sample_tax_return,
            breakdown
        )

        data = statement.generate()

        # Find income section
        income_section = None
        for section in data["sections"]:
            if "GROSS INCOME" in section["title"]:
                income_section = section
                break

        assert income_section is not None

        # Check for wages line
        wage_line = None
        for line in income_section["lines"]:
            if "Wages" in line["description"]:
                wage_line = line
                break

        assert wage_line is not None
        assert wage_line["amount"] == 85000.0

    def test_deductions_section(self, engine, sample_tax_return):
        """Test deductions section shows standard deduction."""
        breakdown = engine.calculate(sample_tax_return)

        statement = TaxComputationStatement(
            sample_tax_return,
            breakdown
        )

        data = statement.generate()

        # Find deductions section
        ded_section = None
        for section in data["sections"]:
            if "DEDUCTIONS FROM AGI" in section["title"]:
                ded_section = section
                break

        assert ded_section is not None

        # Check for standard deduction
        std_ded_found = False
        for line in ded_section["lines"]:
            if "standard deduction" in line["description"].lower():
                std_ded_found = True
                assert line["amount"] == 15750.0  # 2025 single standard deduction
                break

        assert std_ded_found

    def test_summary_section(self, engine, sample_tax_return):
        """Test summary section shows final amounts."""
        breakdown = engine.calculate(sample_tax_return)

        statement = TaxComputationStatement(
            sample_tax_return,
            breakdown
        )

        data = statement.generate()

        # Find summary section
        summary_section = None
        for section in data["sections"]:
            if "TAX SUMMARY" in section["title"]:
                summary_section = section
                break

        assert summary_section is not None

        # Should have total tax and payments
        has_total_tax = False
        has_total_payments = False
        for line in summary_section["lines"]:
            if "Total Tax" in line["description"]:
                has_total_tax = True
            if "Total Payments" in line["description"]:
                has_total_payments = True

        assert has_total_tax
        assert has_total_payments


class TestAssumptionsTracking:
    """Tests for assumptions tracking and footnotes."""

    def test_filing_status_assumption(self, engine):
        """Test HOH filing status generates assumption."""
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Jane",
                last_name="Doe",
                filing_status=FilingStatus.HEAD_OF_HOUSEHOLD,
            ),
            income=Income(w2_forms=[make_w2(50000.0)]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)

        statement = TaxComputationStatement(tax_return, breakdown)
        data = statement.generate()

        # Should have HOH assumption
        hoh_assumption = None
        for assumption in data["assumptions"]:
            if "Head of Household" in assumption["description"]:
                hoh_assumption = assumption
                break

        assert hoh_assumption is not None
        assert hoh_assumption["requires_documentation"]

    def test_self_employment_assumption(self, engine):
        """Test SE income generates assumption."""
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Bob",
                last_name="Builder",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                self_employment_income=75000.0,
                self_employment_expenses=15000.0,
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)

        statement = TaxComputationStatement(tax_return, breakdown)
        data = statement.generate()

        # Should have SE assumption
        se_assumption = None
        for assumption in data["assumptions"]:
            if "self-employment" in assumption["description"].lower():
                se_assumption = assumption
                break

        assert se_assumption is not None

    def test_itemized_deduction_assumption(self, engine):
        """Test itemized deductions generate assumptions."""
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Rich",
                last_name="Taxpayer",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(200000.0)]),
            deductions=Deductions(
                use_standard_deduction=False,
                itemized=ItemizedDeductions(
                    mortgage_interest=25000.0,  # Higher to ensure itemizing
                    mortgage_principal=600000.0,
                    state_local_income_tax=15000.0,  # Will be limited to $10k
                    real_estate_tax=5000.0,  # Additional SALT
                    charitable_cash=10000.0,
                ),
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)

        # Verify it's actually itemizing
        assert breakdown.deduction_type == "itemized", f"Expected itemized but got {breakdown.deduction_type}"

        statement = TaxComputationStatement(tax_return, breakdown)
        data = statement.generate()

        # Should have SALT assumption (over $10k limit)
        salt_assumption = None
        for assumption in data["assumptions"]:
            if "SALT" in assumption["description"]:
                salt_assumption = assumption
                break

        assert salt_assumption is not None, f"No SALT assumption found. Assumptions: {[a['description'] for a in data['assumptions']]}"
        assert "$10,000" in salt_assumption["description"]

    def test_footnotes_generation(self, engine, sample_tax_return):
        """Test footnotes are properly generated."""
        breakdown = engine.calculate(sample_tax_return)

        statement = TaxComputationStatement(
            sample_tax_return,
            breakdown
        )

        data = statement.generate()

        # Should have footnotes matching assumptions
        assert len(data["footnotes"]) == len(data["assumptions"])

        # Each footnote should have required fields
        for fn in data["footnotes"]:
            assert "number" in fn
            assert "text" in fn
            assert "reference" in fn
            assert "confidence" in fn


class TestDraftReturnGeneration:
    """Tests for draft return generation."""

    def test_basic_draft_generation(self, engine, sample_tax_return):
        """Test basic draft return generation."""
        breakdown = engine.calculate(sample_tax_return)

        draft = DraftReturnGenerator(
            sample_tax_return,
            breakdown,
            preparer_name="Test CPA",
            firm_name="Test Firm"
        )

        data = draft.generate()

        assert "draft_return" in data
        assert "metadata" in data
        assert data["draft_return"]["header"]["title"] == "DRAFT FEDERAL INCOME TAX RETURN"

    def test_form_1040_summary(self, engine, sample_tax_return):
        """Test Form 1040 summary generation."""
        breakdown = engine.calculate(sample_tax_return)

        draft = DraftReturnGenerator(sample_tax_return, breakdown)
        data = draft.generate()

        summary = data["draft_return"]["form_1040_summary"]

        # Check income section
        assert "income" in summary
        assert summary["income"]["line_1a"]["amount"] == 85000.0  # W-2 wages

        # Check deductions section
        assert "deductions" in summary
        assert summary["deductions"]["line_12"]["amount"] == 15750.0  # Standard deduction

        # Check payments
        assert "payments" in summary
        assert summary["payments"]["line_25a"]["amount"] == 12000.0  # Withholding

    def test_schedule_requirements(self, engine):
        """Test schedule requirements detection."""
        # Return with SE income should require Schedule C and SE
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Self",
                last_name="Employed",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                self_employment_income=50000.0,
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)

        draft = DraftReturnGenerator(tax_return, breakdown)
        data = draft.generate()

        schedules = data["draft_return"]["schedules_required"]
        schedule_names = [s["name"] for s in schedules]

        # Should require Schedule C and Schedule SE
        assert "Schedule C" in schedule_names
        assert "Schedule SE" in schedule_names

    def test_completion_status_complete(self, engine, sample_tax_return):
        """Test completion status for complete return."""
        breakdown = engine.calculate(sample_tax_return)

        draft = DraftReturnGenerator(sample_tax_return, breakdown)
        data = draft.generate()

        # With valid SSN and EIN, should be nearly complete
        status = data["metadata"]["status"]
        assert status in [CompletionStatus.READY_FOR_SIGNATURE.value, CompletionStatus.PENDING_REVIEW.value]

    def test_missing_items_detection(self, engine):
        """Test missing items detection."""
        # Return without SSN should flag missing item
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="No",
                last_name="SSN",
                ssn="",  # Missing SSN
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(50000.0)]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)

        draft = DraftReturnGenerator(tax_return, breakdown)
        data = draft.generate()

        completion = data["draft_return"]["completion_analysis"]

        # Should have missing SSN
        ssn_missing = False
        for item in completion["missing_items"]:
            if "Social Security" in item["description"]:
                ssn_missing = True
                break

        assert ssn_missing
        assert completion["required_count"] >= 1


class TestTextOutput:
    """Tests for text output generation."""

    def test_computation_text_output(self, engine, sample_tax_return):
        """Test computation statement text output."""
        breakdown = engine.calculate(sample_tax_return)

        statement = TaxComputationStatement(
            sample_tax_return,
            breakdown,
            preparer_name="John CPA",
            firm_name="CPA Firm LLC"
        )

        text = statement.to_text()

        # Check header
        assert "COMPUTATION OF FEDERAL INCOME TAX" in text
        assert "John Smith" in text
        assert "John CPA" in text

        # Check sections exist
        assert "GROSS INCOME" in text
        assert "ADJUSTMENTS" in text
        assert "DEDUCTIONS" in text
        assert "TAX COMPUTATION" in text
        assert "CREDITS" in text
        assert "TAX SUMMARY" in text

        # Check footnotes section
        assert "ASSUMPTIONS" in text or "FOOTNOTES" in text

    def test_draft_return_text_output(self, engine, sample_tax_return):
        """Test draft return text output."""
        breakdown = engine.calculate(sample_tax_return)

        draft = DraftReturnGenerator(
            sample_tax_return,
            breakdown,
            preparer_name="Jane EA",
            firm_name="Tax Services Inc"
        )

        text = draft.to_text()

        # Check header
        assert "DRAFT FEDERAL INCOME TAX RETURN" in text
        assert "John Smith" in text
        assert "Jane EA" in text

        # Check sections
        assert "FORM 1040 SUMMARY" in text
        assert "INCOME" in text
        assert "DEDUCTIONS" in text
        assert "PAYMENTS" in text

        # Check disclaimer
        assert "DRAFT" in text
        assert "NOT FOR FILING" in text


class TestCompletePackage:
    """Tests for complete draft package generation."""

    def test_complete_package_generation(self, engine, sample_tax_return):
        """Test generating complete draft package."""
        breakdown = engine.calculate(sample_tax_return)

        package = generate_complete_draft_package(
            sample_tax_return,
            breakdown,
            preparer_name="Tax Pro",
            firm_name="Pro Tax Services"
        )

        assert "draft_return_text" in package
        assert "computation_text" in package
        assert "draft_return_json" in package
        assert "computation_json" in package

        # All should have content
        assert len(package["draft_return_text"]) > 0
        assert len(package["computation_text"]) > 0
        assert len(package["draft_return_json"]) > 0
        assert len(package["computation_json"]) > 0


class TestComplexScenarios:
    """Tests for complex tax scenarios."""

    def test_high_income_with_all_taxes(self, engine):
        """Test high income with SE, NIIT, AMT, etc."""
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="High",
                last_name="Earner",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                w2_forms=[make_w2(300000.0, 80000.0)],
                interest_income=50000.0,
                ordinary_dividends=30000.0,
                qualified_dividends=25000.0,
            ),
            deductions=Deductions(
                use_standard_deduction=False,
                itemized=ItemizedDeductions(
                    state_local_income_tax=25000.0,  # Limited to $10k
                    real_estate_tax=15000.0,
                    mortgage_interest=20000.0,
                    mortgage_principal=400000.0,
                    charitable_cash=10000.0,
                ),
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)

        # Generate both reports
        statement = TaxComputationStatement(tax_return, breakdown)
        draft = DraftReturnGenerator(tax_return, breakdown)

        comp_data = statement.generate()
        draft_data = draft.generate()

        # Should have NIIT
        assert breakdown.net_investment_income_tax > 0

        # Should have SALT limitation assumption
        salt_assumption = False
        for assumption in comp_data["assumptions"]:
            if "SALT" in assumption["description"]:
                salt_assumption = True
                break
        assert salt_assumption

        # Schedule A should be required
        schedules = draft_data["draft_return"]["schedules_required"]
        schedule_names = [s["name"] for s in schedules]
        assert "Schedule A" in schedule_names

    def test_capital_gains_with_carryforward(self, engine):
        """Test capital gains with loss carryforward."""
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Investor",
                last_name="Jones",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                w2_forms=[make_w2(75000.0)],
                short_term_capital_gains=5000.0,
                short_term_capital_losses=15000.0,
                long_term_capital_gains=2000.0,
                long_term_capital_losses=1000.0,
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)

        # Should have capital loss carryforward
        assert breakdown.new_st_loss_carryforward > 0 or breakdown.new_lt_loss_carryforward > 0

        # Generate statement
        statement = TaxComputationStatement(tax_return, breakdown)
        data = statement.generate()

        # Should have carryforward assumption
        cf_assumption = False
        for assumption in data["assumptions"]:
            if "carryforward" in assumption["description"].lower():
                cf_assumption = True
                break
        assert cf_assumption
