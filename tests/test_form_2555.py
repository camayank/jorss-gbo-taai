"""
Test suite for Form 2555 - Foreign Earned Income Exclusion.

Tests cover:
- Qualification tests (bona fide residence, physical presence)
- Foreign earned income calculation
- Housing exclusion and deduction
- Prorated exclusions for partial year
- High-cost location adjustments
- Convenience function
"""

import pytest
from models.form_2555 import (
    Form2555,
    QualificationTest,
    ForeignCountryInfo,
    ForeignHousingExpenses,
    calculate_feie,
    HIGH_COST_LOCATIONS,
)


class TestForm2555Qualification:
    """Tests for FEIE qualification determination."""

    def test_physical_presence_330_days_qualifies(self):
        """330+ days in foreign country qualifies under physical presence test."""
        form = Form2555(
            qualification_test=QualificationTest.PHYSICAL_PRESENCE,
            days_in_foreign_country=330,
            wages_salaries_bonuses=100000.0,
        )
        qualifies, reason = form.qualifies_for_exclusion()
        assert qualifies is True
        assert "330" in reason

    def test_physical_presence_329_days_not_qualified(self):
        """329 days (one short) does not qualify."""
        form = Form2555(
            qualification_test=QualificationTest.PHYSICAL_PRESENCE,
            days_in_foreign_country=329,
            wages_salaries_bonuses=100000.0,
        )
        qualifies, reason = form.qualifies_for_exclusion()
        assert qualifies is False
        assert "329" in reason

    def test_bona_fide_residence_qualifies(self):
        """Bona fide resident qualifies."""
        form = Form2555(
            qualification_test=QualificationTest.BONA_FIDE_RESIDENCE,
            is_bona_fide_resident=True,
            wages_salaries_bonuses=100000.0,
        )
        qualifies, reason = form.qualifies_for_exclusion()
        assert qualifies is True
        assert "bona fide" in reason.lower()

    def test_bona_fide_not_resident_not_qualified(self):
        """Not a bona fide resident does not qualify."""
        form = Form2555(
            qualification_test=QualificationTest.BONA_FIDE_RESIDENCE,
            is_bona_fide_resident=False,
            wages_salaries_bonuses=100000.0,
        )
        qualifies, reason = form.qualifies_for_exclusion()
        assert qualifies is False

    def test_full_year_abroad_qualifies(self):
        """Full year (365 days) abroad qualifies."""
        form = Form2555(
            qualification_test=QualificationTest.PHYSICAL_PRESENCE,
            days_in_foreign_country=365,
            wages_salaries_bonuses=150000.0,
        )
        qualifies, _ = form.qualifies_for_exclusion()
        assert qualifies is True


class TestForm2555Exclusion:
    """Tests for foreign earned income exclusion calculation."""

    def test_basic_exclusion_under_limit(self):
        """Income under exclusion limit is fully excluded."""
        form = Form2555(
            qualification_test=QualificationTest.PHYSICAL_PRESENCE,
            days_in_foreign_country=365,
            wages_salaries_bonuses=100000.0,
            qualifying_days_in_year=365,
        )
        result = form.calculate_exclusion()

        assert result['qualifies'] is True
        assert result['foreign_earned_income_exclusion'] == 100000.0
        assert result['remaining_taxable_foreign_income'] == 0.0

    def test_exclusion_capped_at_limit(self):
        """Income above exclusion limit is capped."""
        form = Form2555(
            qualification_test=QualificationTest.PHYSICAL_PRESENCE,
            days_in_foreign_country=365,
            wages_salaries_bonuses=200000.0,  # Above $130k limit
            qualifying_days_in_year=365,
        )
        result = form.calculate_exclusion()

        assert result['qualifies'] is True
        assert result['foreign_earned_income_exclusion'] == 130000.0  # Max limit
        assert result['remaining_taxable_foreign_income'] == 70000.0

    def test_prorated_exclusion_partial_year(self):
        """Exclusion is prorated for partial year."""
        form = Form2555(
            qualification_test=QualificationTest.PHYSICAL_PRESENCE,
            days_in_foreign_country=330,
            wages_salaries_bonuses=100000.0,
            qualifying_days_in_year=182,  # Half year
        )
        result = form.calculate_exclusion()

        # Prorated: $130,000 × (182/365) ≈ $64,876
        assert result['qualifies'] is True
        assert result['prorated_exclusion_limit'] < 130000.0
        assert result['prorated_exclusion_limit'] == pytest.approx(64876.71, rel=0.01)

    def test_combined_wages_and_self_employment(self):
        """Both wages and SE income are combined for exclusion."""
        form = Form2555(
            qualification_test=QualificationTest.PHYSICAL_PRESENCE,
            days_in_foreign_country=365,
            wages_salaries_bonuses=80000.0,
            self_employment_income=40000.0,
            qualifying_days_in_year=365,
        )
        result = form.calculate_exclusion()

        assert result['total_foreign_earned_income'] == 120000.0
        assert result['foreign_earned_income_exclusion'] == 120000.0  # Under limit

    def test_meals_lodging_exclusion_applied(self):
        """Employer-provided meals/lodging reduces income."""
        form = Form2555(
            qualification_test=QualificationTest.PHYSICAL_PRESENCE,
            days_in_foreign_country=365,
            wages_salaries_bonuses=100000.0,
            meals_lodging_exclusion=10000.0,
            qualifying_days_in_year=365,
        )
        result = form.calculate_exclusion()

        assert result['total_foreign_earned_income'] == 90000.0  # Reduced

    def test_not_qualified_no_exclusion(self):
        """No exclusion if not qualified."""
        form = Form2555(
            qualification_test=QualificationTest.PHYSICAL_PRESENCE,
            days_in_foreign_country=200,  # Not enough days
            wages_salaries_bonuses=100000.0,
        )
        result = form.calculate_exclusion()

        assert result['qualifies'] is False
        assert result['foreign_earned_income_exclusion'] == 0.0
        assert result['remaining_taxable_foreign_income'] == 100000.0


class TestForm2555Housing:
    """Tests for foreign housing exclusion/deduction."""

    def test_basic_housing_exclusion(self):
        """Housing expenses above base are excludable."""
        housing = ForeignHousingExpenses(
            rent=30000.0,
            utilities=3000.0,
            employer_housing_allowance=25000.0,
        )
        form = Form2555(
            qualification_test=QualificationTest.PHYSICAL_PRESENCE,
            days_in_foreign_country=365,
            wages_salaries_bonuses=150000.0,
            housing_expenses=housing,
            qualifying_days_in_year=365,
        )
        result = form.calculate_exclusion()

        # Housing base: 16% × $130,000 = $20,800
        # Total housing: $33,000
        # Qualifying: $33,000 - $20,800 = $12,200
        assert result['housing_exclusion'] > 0
        assert result['total_exclusion'] > result['foreign_earned_income_exclusion']

    def test_housing_deduction_self_employed(self):
        """Self-employed gets housing deduction."""
        housing = ForeignHousingExpenses(
            rent=35000.0,
        )
        form = Form2555(
            qualification_test=QualificationTest.PHYSICAL_PRESENCE,
            days_in_foreign_country=365,
            self_employment_income=150000.0,
            housing_expenses=housing,
            qualifying_days_in_year=365,
        )
        result = form.calculate_exclusion()

        # With no employer-provided housing, excess is deduction
        assert result['housing_deduction'] > 0

    def test_housing_limit_standard(self):
        """Housing is limited to 30% of max exclusion."""
        housing = ForeignHousingExpenses(
            rent=60000.0,  # Very high rent
        )
        form = Form2555(
            qualification_test=QualificationTest.PHYSICAL_PRESENCE,
            days_in_foreign_country=365,
            wages_salaries_bonuses=100000.0,
            housing_expenses=housing,
            qualifying_days_in_year=365,
        )
        housing_result = form.calculate_housing_amounts()

        # Limit: 30% × $130,000 = $39,000
        # Base: 16% × $130,000 = $20,800
        # Max qualifying: $39,000 - $20,800 = $18,200
        assert housing_result['qualifying_housing_expenses'] <= 18200.0

    def test_high_cost_location_higher_limit(self):
        """High-cost locations get higher housing limit."""
        housing = ForeignHousingExpenses(
            rent=50000.0,
        )
        country = ForeignCountryInfo(
            country_code="HK",
            city="Hong Kong",
            is_high_cost_location=True,
            housing_limit_multiplier=1.85,
        )
        form = Form2555(
            qualification_test=QualificationTest.PHYSICAL_PRESENCE,
            days_in_foreign_country=365,
            wages_salaries_bonuses=100000.0,
            housing_expenses=housing,
            foreign_country=country,
            qualifying_days_in_year=365,
        )
        housing_result = form.calculate_housing_amounts()

        # Higher limit for Hong Kong (1.85× standard)
        assert housing_result['housing_expense_limit'] > 39000.0


class TestForm2555EdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_income_no_exclusion(self):
        """Zero income means zero exclusion."""
        form = Form2555(
            qualification_test=QualificationTest.PHYSICAL_PRESENCE,
            days_in_foreign_country=365,
            wages_salaries_bonuses=0.0,
            qualifying_days_in_year=365,
        )
        result = form.calculate_exclusion()

        assert result['foreign_earned_income_exclusion'] == 0.0

    def test_exactly_330_days_qualifies(self):
        """Exactly 330 days qualifies (boundary test)."""
        form = Form2555(
            qualification_test=QualificationTest.PHYSICAL_PRESENCE,
            days_in_foreign_country=330,
            wages_salaries_bonuses=100000.0,
        )
        qualifies, _ = form.qualifies_for_exclusion()
        assert qualifies is True

    def test_income_exactly_at_limit(self):
        """Income exactly at exclusion limit."""
        form = Form2555(
            qualification_test=QualificationTest.PHYSICAL_PRESENCE,
            days_in_foreign_country=365,
            wages_salaries_bonuses=130000.0,  # Exactly at limit
            qualifying_days_in_year=365,
        )
        result = form.calculate_exclusion()

        assert result['foreign_earned_income_exclusion'] == 130000.0
        assert result['remaining_taxable_foreign_income'] == 0.0

    def test_one_dollar_over_limit(self):
        """Income one dollar over limit has $1 taxable."""
        form = Form2555(
            qualification_test=QualificationTest.PHYSICAL_PRESENCE,
            days_in_foreign_country=365,
            wages_salaries_bonuses=130001.0,
            qualifying_days_in_year=365,
        )
        result = form.calculate_exclusion()

        assert result['foreign_earned_income_exclusion'] == 130000.0
        assert result['remaining_taxable_foreign_income'] == 1.0


class TestForm2555ConvenienceFunction:
    """Tests for calculate_feie convenience function."""

    def test_convenience_function_basic(self):
        """Convenience function calculates correctly."""
        result = calculate_feie(
            foreign_earned_income=100000.0,
            days_abroad=365,
            is_bona_fide_resident=False,
        )

        assert result['qualifies'] is True
        assert result['foreign_earned_income_exclusion'] == 100000.0

    def test_convenience_function_with_housing(self):
        """Convenience function handles housing."""
        result = calculate_feie(
            foreign_earned_income=150000.0,
            days_abroad=365,
            housing_expenses=30000.0,
            employer_housing=20000.0,
        )

        assert result['qualifies'] is True
        assert result['housing_exclusion'] > 0

    def test_convenience_function_high_cost_city(self):
        """Convenience function applies high-cost multiplier."""
        result = calculate_feie(
            foreign_earned_income=150000.0,
            days_abroad=365,
            housing_expenses=50000.0,
            country="HK",
            city="Hong Kong",
        )

        # Hong Kong is in HIGH_COST_LOCATIONS
        assert result['qualifies'] is True


class TestForm2555SummaryMethods:
    """Tests for summary methods."""

    def test_get_form_2555_summary(self):
        """Summary method returns correct fields."""
        form = Form2555(
            qualification_test=QualificationTest.PHYSICAL_PRESENCE,
            days_in_foreign_country=365,
            wages_salaries_bonuses=120000.0,
            qualifying_days_in_year=365,
        )
        summary = form.get_form_2555_summary()

        assert 'qualifies_for_feie' in summary
        assert 'foreign_earned_income_exclusion' in summary
        assert 'total_exclusion' in summary
        assert summary['qualifies_for_feie'] is True
        assert summary['foreign_earned_income_exclusion'] == 120000.0


class TestForm2555Constants:
    """Tests verifying 2025 constants."""

    def test_max_exclusion_2025(self):
        """Verify 2025 maximum exclusion amount."""
        assert Form2555.MAX_EXCLUSION_2025 == 130000.0

    def test_housing_base_percent(self):
        """Verify housing base percentage."""
        assert Form2555.HOUSING_BASE_PERCENT == 0.16

    def test_housing_limit_percent(self):
        """Verify housing limit percentage."""
        assert Form2555.HOUSING_LIMIT_PERCENT == 0.30

    def test_physical_presence_days_required(self):
        """Verify physical presence requirement."""
        assert Form2555.DAYS_REQUIRED_PHYSICAL_PRESENCE == 330
