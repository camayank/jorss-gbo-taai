"""
Form 2555 - Foreign Earned Income Exclusion (FEIE)

Implements the foreign earned income exclusion per IRC Section 911 which allows
US citizens and residents living abroad to exclude foreign earned income from
US taxation.

Who Can Claim Form 2555:
1. US citizen who is a bona fide resident of a foreign country for an
   uninterrupted period that includes an entire tax year, OR
2. US citizen or resident present in a foreign country for at least
   330 full days during a period of 12 consecutive months

What Qualifies as Foreign Earned Income:
- Wages, salaries, bonuses, commissions
- Professional fees for personal services
- Self-employment income for services performed abroad
- NOT: Investment income, pensions, social security, US government pay

2025 Exclusion Limits (estimated, indexed for inflation):
- Foreign earned income exclusion: $130,000
- Foreign housing base: 16% of exclusion ($20,800)
- Foreign housing limit: 30% of exclusion ($39,000) - varies by location

Per IRS Form 2555 Instructions, Publication 54, and IRC Section 911.
"""

from typing import Optional, List, Dict, Any, ClassVar
from pydantic import BaseModel, Field, field_validator
from enum import Enum
from datetime import date


class QualificationTest(str, Enum):
    """Test used to qualify for foreign earned income exclusion."""
    BONA_FIDE_RESIDENCE = "bona_fide_residence"
    PHYSICAL_PRESENCE = "physical_presence"


class ForeignCountryInfo(BaseModel):
    """Information about foreign country of residence/work."""
    country_name: str = Field(
        default="",
        description="Name of foreign country"
    )
    country_code: str = Field(
        default="",
        description="ISO country code"
    )
    city: str = Field(
        default="",
        description="City of residence"
    )

    # For high-cost location housing adjustments
    is_high_cost_location: bool = Field(
        default=False,
        description="Location qualifies for higher housing limit"
    )
    housing_limit_multiplier: float = Field(
        default=1.0,
        ge=1.0,
        le=2.0,
        description="Multiplier for housing limit (1.0 = standard, up to 2.0 for high-cost)"
    )


class ForeignHousingExpenses(BaseModel):
    """
    Foreign housing expenses for Form 2555 Part VI.

    Qualifying housing expenses include:
    - Rent
    - Utilities (except telephone)
    - Real and personal property insurance
    - Rental of furniture and accessories
    - Repairs
    - Nonrefundable fees for securing a lease

    NOT included:
    - Mortgage payments, home purchase costs
    - Purchased furniture
    - Domestic labor (maids, gardeners)
    - Pay TV
    - Home improvements
    """
    rent: float = Field(default=0.0, ge=0, description="Rent payments")
    utilities: float = Field(default=0.0, ge=0, description="Utilities (gas, electric, water)")
    property_insurance: float = Field(default=0.0, ge=0, description="Property insurance")
    occupancy_taxes: float = Field(default=0.0, ge=0, description="Occupancy taxes")
    furniture_rental: float = Field(default=0.0, ge=0, description="Furniture/appliance rental")
    repairs: float = Field(default=0.0, ge=0, description="Repairs and maintenance")
    parking: float = Field(default=0.0, ge=0, description="Residential parking")
    other_qualifying: float = Field(default=0.0, ge=0, description="Other qualifying expenses")

    # Employer-provided amounts
    employer_provided_housing: float = Field(
        default=0.0,
        ge=0,
        description="Value of employer-provided housing"
    )
    employer_housing_allowance: float = Field(
        default=0.0,
        ge=0,
        description="Employer housing allowance received"
    )

    def total_housing_expenses(self) -> float:
        """Calculate total qualifying housing expenses."""
        return (
            self.rent +
            self.utilities +
            self.property_insurance +
            self.occupancy_taxes +
            self.furniture_rental +
            self.repairs +
            self.parking +
            self.other_qualifying
        )


class Form2555(BaseModel):
    """
    Form 2555 - Foreign Earned Income Exclusion.

    Calculates the foreign earned income exclusion and foreign housing
    exclusion/deduction for US taxpayers living and working abroad.

    Key 2025 Thresholds (estimated):
    - Maximum exclusion: $130,000
    - Housing base amount: $20,800 (16% of max)
    - Standard housing limit: $39,000 (30% of max)
    """

    # 2025 thresholds (indexed for inflation from 2024's $126,500)
    MAX_EXCLUSION_2025: ClassVar[float] = 130000.0
    HOUSING_BASE_PERCENT: ClassVar[float] = 0.16
    HOUSING_LIMIT_PERCENT: ClassVar[float] = 0.30
    DAYS_REQUIRED_PHYSICAL_PRESENCE: ClassVar[int] = 330

    # Taxpayer identification
    taxpayer_name: str = Field(default="", description="Taxpayer name")

    # Part I: General Information
    foreign_country: ForeignCountryInfo = Field(
        default_factory=ForeignCountryInfo,
        description="Foreign country information"
    )

    # Qualification test
    qualification_test: QualificationTest = Field(
        default=QualificationTest.PHYSICAL_PRESENCE,
        description="Test used to qualify for exclusion"
    )

    # Part II: Bona Fide Residence Test
    bona_fide_residence_start: Optional[date] = Field(
        default=None,
        description="Date bona fide residence began"
    )
    bona_fide_residence_end: Optional[date] = Field(
        default=None,
        description="Date bona fide residence ended (or continuing)"
    )
    is_bona_fide_resident: bool = Field(
        default=False,
        description="Qualifies under bona fide residence test"
    )

    # Part III: Physical Presence Test
    physical_presence_start: Optional[date] = Field(
        default=None,
        description="Start of 12-month period for physical presence test"
    )
    physical_presence_end: Optional[date] = Field(
        default=None,
        description="End of 12-month period for physical presence test"
    )
    days_in_foreign_country: int = Field(
        default=0,
        ge=0,
        le=366,
        description="Days physically present in foreign country during period"
    )

    # Part IV: Foreign Earned Income
    wages_salaries_bonuses: float = Field(
        default=0.0,
        ge=0,
        description="Wages, salaries, bonuses, commissions"
    )
    self_employment_income: float = Field(
        default=0.0,
        ge=0,
        description="Self-employment income earned abroad"
    )
    allowances_reimbursements: float = Field(
        default=0.0,
        ge=0,
        description="Noncash income, allowances, reimbursements"
    )
    other_foreign_earned_income: float = Field(
        default=0.0,
        ge=0,
        description="Other foreign earned income"
    )

    # Income adjustments
    meals_lodging_exclusion: float = Field(
        default=0.0,
        ge=0,
        description="Meals and lodging provided by employer (excludable)"
    )

    # Part VI: Housing
    housing_expenses: ForeignHousingExpenses = Field(
        default_factory=ForeignHousingExpenses,
        description="Foreign housing expenses"
    )

    # For partial year calculations
    qualifying_days_in_year: int = Field(
        default=365,
        ge=1,
        le=366,
        description="Days in tax year that qualify for exclusion"
    )

    # Carryover from prior year (if housing deduction exceeded income)
    prior_year_housing_deduction_carryover: float = Field(
        default=0.0,
        ge=0,
        description="Housing deduction carryover from prior year"
    )

    # Election flags
    revoking_prior_election: bool = Field(
        default=False,
        description="Revoking a prior Form 2555 election"
    )

    def qualifies_for_exclusion(self) -> tuple[bool, str]:
        """
        Determine if taxpayer qualifies for foreign earned income exclusion.

        Returns:
            Tuple of (qualifies: bool, reason: str)
        """
        if self.qualification_test == QualificationTest.BONA_FIDE_RESIDENCE:
            if self.is_bona_fide_resident:
                return True, "Qualifies under bona fide residence test"
            return False, "Does not meet bona fide residence requirements"

        elif self.qualification_test == QualificationTest.PHYSICAL_PRESENCE:
            if self.days_in_foreign_country >= self.DAYS_REQUIRED_PHYSICAL_PRESENCE:
                return True, f"Qualifies with {self.days_in_foreign_country} days in foreign country"
            return False, f"Only {self.days_in_foreign_country} days; need {self.DAYS_REQUIRED_PHYSICAL_PRESENCE}"

        return False, "Unknown qualification test"

    def calculate_total_foreign_earned_income(self) -> float:
        """Calculate total foreign earned income before exclusion."""
        total = (
            self.wages_salaries_bonuses +
            self.self_employment_income +
            self.allowances_reimbursements +
            self.other_foreign_earned_income -
            self.meals_lodging_exclusion
        )
        return max(0.0, total)

    def calculate_prorated_exclusion_limit(self) -> float:
        """
        Calculate the prorated exclusion limit for partial year.

        If taxpayer didn't qualify for full year, prorate the exclusion
        based on qualifying days.
        """
        daily_exclusion = self.MAX_EXCLUSION_2025 / 365
        prorated = daily_exclusion * self.qualifying_days_in_year
        return round(prorated, 2)

    def calculate_housing_amounts(self) -> dict:
        """
        Calculate foreign housing exclusion/deduction amounts.

        Housing Exclusion: For employees (reduces employer-provided amounts)
        Housing Deduction: For self-employed (deduction from gross income)

        Formula:
        1. Total housing expenses
        2. Subtract base housing amount (16% of max exclusion, prorated)
        3. Limited to 30% of max exclusion (or higher for high-cost areas)
        """
        result = {
            'total_housing_expenses': 0.0,
            'base_housing_amount': 0.0,
            'housing_expense_limit': 0.0,
            'qualifying_housing_expenses': 0.0,
            'housing_exclusion': 0.0,
            'housing_deduction': 0.0,
            'employer_provided_total': 0.0,
        }

        # Total housing expenses
        total_expenses = self.housing_expenses.total_housing_expenses()
        result['total_housing_expenses'] = total_expenses

        if total_expenses == 0:
            return result

        # Base housing amount (16% of max, prorated)
        daily_base = (self.MAX_EXCLUSION_2025 * self.HOUSING_BASE_PERCENT) / 365
        base_amount = daily_base * self.qualifying_days_in_year
        result['base_housing_amount'] = round(base_amount, 2)

        # Housing expense limit (30% of max, adjusted for high-cost locations)
        daily_limit = (self.MAX_EXCLUSION_2025 * self.HOUSING_LIMIT_PERCENT) / 365
        limit_amount = daily_limit * self.qualifying_days_in_year

        # Apply high-cost location multiplier if applicable
        if self.foreign_country.is_high_cost_location:
            limit_amount *= self.foreign_country.housing_limit_multiplier

        result['housing_expense_limit'] = round(limit_amount, 2)

        # Qualifying housing expenses = Total - Base, limited to cap
        excess_housing = max(0.0, total_expenses - base_amount)
        qualifying = min(excess_housing, limit_amount - base_amount)
        result['qualifying_housing_expenses'] = round(qualifying, 2)

        # Determine exclusion vs deduction based on income type
        employer_total = (
            self.housing_expenses.employer_provided_housing +
            self.housing_expenses.employer_housing_allowance
        )
        result['employer_provided_total'] = employer_total

        # Housing exclusion (employee portion)
        if employer_total > 0:
            # Exclusion is the lesser of qualifying expenses or employer-provided
            result['housing_exclusion'] = round(min(qualifying, employer_total), 2)

        # Housing deduction (self-employed portion)
        if self.self_employment_income > 0:
            # Deduction for expenses not covered by employer
            remaining = qualifying - result['housing_exclusion']
            result['housing_deduction'] = round(max(0.0, remaining), 2)

        return result

    def calculate_exclusion(self) -> dict:
        """
        Complete Form 2555 calculation.

        Returns comprehensive breakdown including:
        - Qualification status
        - Foreign earned income
        - Foreign earned income exclusion
        - Foreign housing exclusion/deduction
        - Remaining taxable income
        """
        result = {
            'taxpayer_name': self.taxpayer_name,
            'foreign_country': self.foreign_country.country_name,

            # Qualification
            'qualifies': False,
            'qualification_test': self.qualification_test.value,
            'qualification_reason': '',

            # Income
            'total_foreign_earned_income': 0.0,
            'wages_and_salary': self.wages_salaries_bonuses,
            'self_employment': self.self_employment_income,

            # Exclusion calculation
            'max_exclusion_limit': self.MAX_EXCLUSION_2025,
            'prorated_exclusion_limit': 0.0,
            'qualifying_days': self.qualifying_days_in_year,

            # Foreign earned income exclusion
            'foreign_earned_income_exclusion': 0.0,

            # Housing
            'housing_breakdown': {},
            'housing_exclusion': 0.0,
            'housing_deduction': 0.0,

            # Results
            'total_exclusion': 0.0,
            'remaining_taxable_foreign_income': 0.0,

            # Self-employment
            'se_income_after_exclusion': 0.0,
        }

        # Check qualification
        qualifies, reason = self.qualifies_for_exclusion()
        result['qualifies'] = qualifies
        result['qualification_reason'] = reason

        if not qualifies:
            result['total_foreign_earned_income'] = self.calculate_total_foreign_earned_income()
            result['remaining_taxable_foreign_income'] = result['total_foreign_earned_income']
            return result

        # Calculate foreign earned income
        total_income = self.calculate_total_foreign_earned_income()
        result['total_foreign_earned_income'] = total_income

        # Calculate prorated exclusion limit
        prorated_limit = self.calculate_prorated_exclusion_limit()
        result['prorated_exclusion_limit'] = prorated_limit

        # Foreign earned income exclusion (lesser of income or limit)
        feie = min(total_income, prorated_limit)
        result['foreign_earned_income_exclusion'] = round(feie, 2)

        # Calculate housing amounts
        housing = self.calculate_housing_amounts()
        result['housing_breakdown'] = housing
        result['housing_exclusion'] = housing['housing_exclusion']
        result['housing_deduction'] = housing['housing_deduction']

        # Total exclusion
        total_exclusion = feie + housing['housing_exclusion']
        result['total_exclusion'] = round(total_exclusion, 2)

        # Remaining taxable income
        remaining = max(0.0, total_income - total_exclusion)
        result['remaining_taxable_foreign_income'] = round(remaining, 2)

        # Self-employment income after exclusion (for SE tax calculation)
        if self.self_employment_income > 0:
            # SE tax is still owed on excluded income, but at reduced rate
            # This is the income that would be subject to US income tax
            se_ratio = self.self_employment_income / total_income if total_income > 0 else 0
            se_excluded = feie * se_ratio
            result['se_income_after_exclusion'] = round(
                self.self_employment_income - se_excluded, 2
            )

        return result

    def get_form_2555_summary(self) -> dict:
        """Get summary suitable for tax return integration."""
        calc = self.calculate_exclusion()
        return {
            'qualifies_for_feie': calc['qualifies'],
            'foreign_earned_income_exclusion': calc['foreign_earned_income_exclusion'],
            'housing_exclusion': calc['housing_exclusion'],
            'housing_deduction': calc['housing_deduction'],
            'total_exclusion': calc['total_exclusion'],
            'taxable_foreign_income': calc['remaining_taxable_foreign_income'],
        }


# High-cost location data for 2025 (selected major cities)
# In production, this would be a comprehensive database updated annually
HIGH_COST_LOCATIONS = {
    # Format: "country_code:city": housing_limit_multiplier
    "HK:Hong Kong": 1.85,
    "JP:Tokyo": 1.65,
    "CH:Zurich": 1.70,
    "CH:Geneva": 1.65,
    "SG:Singapore": 1.60,
    "GB:London": 1.55,
    "CN:Shanghai": 1.50,
    "CN:Beijing": 1.45,
    "AU:Sydney": 1.45,
    "FR:Paris": 1.40,
    "DE:Munich": 1.35,
    "AE:Dubai": 1.40,
    "AE:Abu Dhabi": 1.35,
    "IL:Tel Aviv": 1.45,
    "KR:Seoul": 1.35,
    "NL:Amsterdam": 1.35,
    "IE:Dublin": 1.35,
    "IT:Milan": 1.30,
    "ES:Madrid": 1.25,
    "CA:Toronto": 1.30,
    "CA:Vancouver": 1.35,
}


def calculate_feie(
    foreign_earned_income: float,
    days_abroad: int,
    housing_expenses: float = 0.0,
    employer_housing: float = 0.0,
    is_bona_fide_resident: bool = False,
    country: str = "",
    city: str = "",
) -> dict:
    """
    Convenience function to calculate foreign earned income exclusion.

    Args:
        foreign_earned_income: Total foreign earned income
        days_abroad: Days in foreign country (for physical presence test)
        housing_expenses: Total qualifying housing expenses
        employer_housing: Employer-provided housing/allowance
        is_bona_fide_resident: True if qualifies under bona fide residence test
        country: Country code
        city: City name

    Returns:
        FEIE calculation results
    """
    # Check for high-cost location
    location_key = f"{country}:{city}"
    is_high_cost = location_key in HIGH_COST_LOCATIONS
    multiplier = HIGH_COST_LOCATIONS.get(location_key, 1.0)

    # Determine qualification test
    if is_bona_fide_resident:
        test = QualificationTest.BONA_FIDE_RESIDENCE
    else:
        test = QualificationTest.PHYSICAL_PRESENCE

    housing = ForeignHousingExpenses(
        rent=housing_expenses,  # Simplified: assume all is rent
        employer_provided_housing=employer_housing,
    )

    country_info = ForeignCountryInfo(
        country_code=country,
        city=city,
        is_high_cost_location=is_high_cost,
        housing_limit_multiplier=multiplier,
    )

    form = Form2555(
        qualification_test=test,
        is_bona_fide_resident=is_bona_fide_resident,
        days_in_foreign_country=days_abroad,
        wages_salaries_bonuses=foreign_earned_income,
        housing_expenses=housing,
        foreign_country=country_info,
        qualifying_days_in_year=min(days_abroad, 365),
    )

    return form.calculate_exclusion()
