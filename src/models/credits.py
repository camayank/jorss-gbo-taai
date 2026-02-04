from typing import Optional, Tuple, List, TYPE_CHECKING
from decimal import Decimal, ROUND_HALF_UP
from pydantic import BaseModel, Field
from enum import Enum

from models._decimal_utils import money

if TYPE_CHECKING:
    from calculator.tax_year_config import TaxYearConfig


class VehicleType(str, Enum):
    """Vehicle type for MSRP limit determination."""
    SEDAN = "sedan"
    HATCHBACK = "hatchback"
    SUV = "suv"
    VAN = "van"
    TRUCK = "truck"
    PICKUP = "pickup"


class CleanVehiclePurchase(BaseModel):
    """
    Clean vehicle purchase information for Form 8936 (Clean Vehicle Credit).

    Supports both new clean vehicles (IRC Section 30D) and
    previously owned clean vehicles (IRC Section 25E).
    """
    model_config = {"protected_namespaces": ()}

    # Vehicle identification
    vin: str = Field(description="Vehicle Identification Number")
    make: str = Field(default="", description="Vehicle manufacturer")
    model: str = Field(default="", description="Vehicle model")
    model_year: int = Field(ge=2010, description="Vehicle model year")

    # Purchase information
    purchase_date: str = Field(description="Date of purchase (YYYY-MM-DD)")
    purchase_price: float = Field(ge=0, description="Purchase price or sale price")
    msrp: float = Field(ge=0, description="Manufacturer's Suggested Retail Price")
    vehicle_type: VehicleType = Field(default=VehicleType.SEDAN, description="Vehicle type for MSRP limit")

    # New vs Previously Owned
    is_new_vehicle: bool = Field(default=True, description="True for new, False for previously owned")
    is_first_transfer: bool = Field(
        default=True,
        description="For used vehicles: first transfer after Aug 16, 2022"
    )

    # Qualification requirements (New vehicles - IRC Section 30D)
    final_assembly_north_america: bool = Field(
        default=True,
        description="Final assembly in North America (required for new)"
    )
    meets_battery_component_req: bool = Field(
        default=True,
        description="Meets battery component requirements (for $3,750)"
    )
    meets_critical_mineral_req: bool = Field(
        default=True,
        description="Meets critical mineral requirements (for $3,750)"
    )

    # Commercial use (Section 45W - different rules)
    is_commercial_vehicle: bool = Field(
        default=False,
        description="Acquired for business/commercial use (Section 45W)"
    )
    business_use_percentage: float = Field(
        default=0.0, ge=0, le=100,
        description="Percentage of business use"
    )

    # Seller information
    seller_name: Optional[str] = Field(None, description="Seller or dealer name")
    seller_ein: Optional[str] = Field(None, description="Seller's EIN")
    seller_address: Optional[str] = Field(None, description="Seller address")

    # Credit transfer to dealer (starting 2024)
    credit_transferred_to_dealer: bool = Field(
        default=False,
        description="Credit transferred to dealer at point of sale"
    )

    def get_credit_type(self) -> str:
        """Return the type of clean vehicle credit."""
        if self.is_new_vehicle:
            return "new_30D"
        else:
            return "used_25E"


class AdoptionType(str, Enum):
    """Type of adoption for credit timing rules."""
    DOMESTIC = "domestic"  # U.S. child - credit when expenses paid or finalized
    FOREIGN = "foreign"    # Non-U.S. child - credit only when finalized
    SPECIAL_NEEDS = "special_needs"  # Full credit regardless of expenses


class AdoptionInfo(BaseModel):
    """
    Adoption information for Form 8839 (Qualified Adoption Expenses).

    Per IRC Section 23, the adoption credit helps offset costs of adopting
    an eligible child. Credit is nonrefundable but can be carried forward
    up to 5 years.

    Key Rules:
    - Domestic adoption: Credit in year expenses paid OR year finalized
    - Foreign adoption: Credit only in year adoption finalized
    - Special needs: Full maximum credit regardless of actual expenses
    - Child must be under 18 or physically/mentally incapable of self-care
    """
    # Child information
    child_name: str = Field(description="Name of adopted child")
    child_ssn: Optional[str] = Field(None, description="Child's SSN or ATIN")
    child_birth_year: int = Field(ge=1900, description="Child's birth year")
    is_special_needs: bool = Field(
        default=False,
        description="Child has special needs (state-determined)"
    )
    is_disabled: bool = Field(
        default=False,
        description="Child physically/mentally incapable of self-care"
    )

    # Adoption details
    adoption_type: AdoptionType = Field(
        default=AdoptionType.DOMESTIC,
        description="Type of adoption"
    )
    adoption_finalized: bool = Field(
        default=False,
        description="Adoption was finalized in this tax year"
    )
    adoption_finalized_year: Optional[int] = Field(
        None,
        description="Year adoption was finalized"
    )

    # Qualified Adoption Expenses (Form 8839 Part II)
    adoption_fees: float = Field(default=0.0, ge=0, description="Adoption agency fees")
    court_costs: float = Field(default=0.0, ge=0, description="Court costs and legal fees")
    attorney_fees: float = Field(default=0.0, ge=0, description="Attorney fees")
    travel_expenses: float = Field(default=0.0, ge=0, description="Travel expenses")
    other_expenses: float = Field(default=0.0, ge=0, description="Other qualified expenses")

    # Employer benefits (reduces credit)
    employer_adoption_benefits: float = Field(
        default=0.0, ge=0,
        description="Employer-provided adoption benefits (Form 8839 Line 20)"
    )

    # Prior year carryforward
    prior_year_carryforward: float = Field(
        default=0.0, ge=0,
        description="Unused adoption credit from prior years"
    )

    def get_total_qualified_expenses(self) -> float:
        """Calculate total qualified adoption expenses."""
        return (
            self.adoption_fees +
            self.court_costs +
            self.attorney_fees +
            self.travel_expenses +
            self.other_expenses
        )

    def get_expenses_net_of_benefits(self) -> float:
        """Get qualified expenses minus employer benefits."""
        total = self.get_total_qualified_expenses()
        return max(0.0, total - self.employer_adoption_benefits)

    def is_eligible_child(self, tax_year: int) -> bool:
        """Check if child is eligible (under 18 or disabled)."""
        age_at_year_end = tax_year - self.child_birth_year
        return age_at_year_end < 18 or self.is_disabled


class ElderlyDisabledInfo(BaseModel):
    """
    Information for Credit for the Elderly or Disabled (Schedule R / IRC Section 22).

    This credit helps elderly (65+) and permanently disabled taxpayers
    with limited income. It's a nonrefundable credit.

    Eligibility:
    - 65 or older by end of tax year, OR
    - Under 65 and permanently/totally disabled with taxable disability income
    """
    # Taxpayer qualification (primary filer)
    taxpayer_birth_year: int = Field(ge=1900, description="Taxpayer's birth year")
    taxpayer_is_disabled: bool = Field(
        default=False,
        description="Taxpayer is permanently and totally disabled"
    )
    taxpayer_disability_income: float = Field(
        default=0.0, ge=0,
        description="Taxpayer's taxable disability income (if under 65)"
    )

    # Spouse qualification (for MFJ)
    spouse_birth_year: Optional[int] = Field(
        None, ge=1900,
        description="Spouse's birth year (for MFJ)"
    )
    spouse_is_disabled: bool = Field(
        default=False,
        description="Spouse is permanently and totally disabled"
    )
    spouse_disability_income: float = Field(
        default=0.0, ge=0,
        description="Spouse's taxable disability income (if under 65)"
    )

    # Nontaxable income that reduces the credit
    nontaxable_social_security: float = Field(
        default=0.0, ge=0,
        description="Nontaxable Social Security benefits"
    )
    nontaxable_railroad_retirement: float = Field(
        default=0.0, ge=0,
        description="Nontaxable Railroad Retirement benefits (Tier 1)"
    )
    nontaxable_pensions: float = Field(
        default=0.0, ge=0,
        description="Other nontaxable pensions or annuities"
    )
    nontaxable_veterans_benefits: float = Field(
        default=0.0, ge=0,
        description="Veterans' disability benefits"
    )
    other_nontaxable_amounts: float = Field(
        default=0.0, ge=0,
        description="Other nontaxable amounts excluded from AGI"
    )

    # MFS special rule
    lived_apart_all_year: bool = Field(
        default=False,
        description="For MFS: lived apart from spouse all year"
    )

    def get_total_nontaxable_income(self) -> float:
        """Get total nontaxable income that reduces the credit."""
        return (
            self.nontaxable_social_security +
            self.nontaxable_railroad_retirement +
            self.nontaxable_pensions +
            self.nontaxable_veterans_benefits +
            self.other_nontaxable_amounts
        )

    def taxpayer_qualifies_by_age(self, tax_year: int) -> bool:
        """Check if taxpayer qualifies by being 65+ at end of year."""
        age = tax_year - self.taxpayer_birth_year
        return age >= 65

    def taxpayer_qualifies_by_disability(self) -> bool:
        """Check if taxpayer qualifies by disability (under 65)."""
        return self.taxpayer_is_disabled and self.taxpayer_disability_income > 0

    def spouse_qualifies_by_age(self, tax_year: int) -> bool:
        """Check if spouse qualifies by being 65+ at end of year."""
        if self.spouse_birth_year is None:
            return False
        age = tax_year - self.spouse_birth_year
        return age >= 65

    def spouse_qualifies_by_disability(self) -> bool:
        """Check if spouse qualifies by disability (under 65)."""
        return self.spouse_is_disabled and self.spouse_disability_income > 0


class WOTCTargetGroup(str, Enum):
    """
    Target groups for Work Opportunity Tax Credit (IRC Section 51).

    Each group has different wage limits and credit percentages.
    """
    # Standard groups - 40% of $6,000 max wages = $2,400 max credit
    TANF_RECIPIENT = "tanf"  # TANF recipient (long-term)
    SNAP_RECIPIENT = "snap"  # SNAP (food stamps) recipient
    SSI_RECIPIENT = "ssi"  # Supplemental Security Income recipient
    VOCATIONAL_REHAB = "voc_rehab"  # Vocational rehabilitation referral
    EX_FELON = "ex_felon"  # Ex-felon (within 1 year of conviction/release)
    DESIGNATED_COMMUNITY = "designated_community"  # Empowerment zone/rural renewal

    # Veterans - various wage limits
    VETERAN_SNAP = "veteran_snap"  # Veteran + SNAP recipient - $6,000 limit
    VETERAN_DISABLED = "veteran_disabled"  # Disabled veteran - $12,000 limit
    VETERAN_UNEMPLOYED_6MO = "veteran_unemployed_6mo"  # Unemployed 6+ months - $6,000
    VETERAN_DISABLED_UNEMPLOYED = "veteran_disabled_unemployed"  # Disabled + unemployed 6mo - $24,000

    # Special categories
    SUMMER_YOUTH = "summer_youth"  # Summer youth employee - $3,000 limit
    LONG_TERM_FAMILY_ASSISTANCE = "long_term_family"  # Long-term TANF - $10,000/year for 2 years
    LONG_TERM_UNEMPLOYED = "long_term_unemployed"  # Unemployed 27+ weeks - $6,000 limit


class WOTCEmployee(BaseModel):
    """
    Employee information for Work Opportunity Tax Credit (Form 5884).

    WOTC is an employer credit for hiring individuals from target groups
    who face significant barriers to employment.

    Requirements:
    - Employee must work minimum 120 hours for any credit
    - 25% credit rate if 120-399 hours worked
    - 40% credit rate if 400+ hours worked
    - Employer must obtain certification (Form 8850)
    """
    # Employee identification
    employee_name: str = Field(description="Employee name")
    employee_ssn: Optional[str] = Field(None, description="Employee SSN")

    # Target group
    target_group: WOTCTargetGroup = Field(description="WOTC target group")

    # Certification
    certification_received: bool = Field(
        default=True,
        description="Form 8850 certification received from State Workforce Agency"
    )
    hire_date: str = Field(description="Date of hire (YYYY-MM-DD)")

    # First year wages and hours
    first_year_wages: float = Field(ge=0, description="First-year qualified wages")
    hours_worked: int = Field(ge=0, description="Hours worked in first year")

    # Second year (only for long-term family assistance)
    second_year_wages: float = Field(
        default=0.0, ge=0,
        description="Second-year wages (for long-term family assistance only)"
    )
    is_second_year: bool = Field(
        default=False,
        description="This is the second year of employment (for long-term family)"
    )

    def get_wage_limit(self) -> float:
        """Get the qualified wage limit for this target group."""
        wage_limits = {
            WOTCTargetGroup.TANF_RECIPIENT: 6000.0,
            WOTCTargetGroup.SNAP_RECIPIENT: 6000.0,
            WOTCTargetGroup.SSI_RECIPIENT: 6000.0,
            WOTCTargetGroup.VOCATIONAL_REHAB: 6000.0,
            WOTCTargetGroup.EX_FELON: 6000.0,
            WOTCTargetGroup.DESIGNATED_COMMUNITY: 6000.0,
            WOTCTargetGroup.VETERAN_SNAP: 6000.0,
            WOTCTargetGroup.VETERAN_DISABLED: 12000.0,
            WOTCTargetGroup.VETERAN_UNEMPLOYED_6MO: 6000.0,
            WOTCTargetGroup.VETERAN_DISABLED_UNEMPLOYED: 24000.0,
            WOTCTargetGroup.SUMMER_YOUTH: 3000.0,
            WOTCTargetGroup.LONG_TERM_FAMILY_ASSISTANCE: 10000.0,
            WOTCTargetGroup.LONG_TERM_UNEMPLOYED: 6000.0,
        }
        return wage_limits.get(self.target_group, 6000.0)

    def get_credit_rate(self) -> float:
        """
        Get credit rate based on hours worked.
        - 0% if < 120 hours
        - 25% if 120-399 hours
        - 40% if 400+ hours
        """
        if self.hours_worked < 120:
            return 0.0
        elif self.hours_worked < 400:
            return 0.25
        else:
            return 0.40

    def calculate_credit(self) -> float:
        """Calculate WOTC credit for this employee."""
        if not self.certification_received:
            return 0.0

        if self.hours_worked < 120:
            return 0.0

        rate = self.get_credit_rate()
        wage_limit = self.get_wage_limit()

        if self.target_group == WOTCTargetGroup.LONG_TERM_FAMILY_ASSISTANCE:
            # Special: 40% year 1 + 50% year 2, each on up to $10,000
            if self.is_second_year:
                # Second year: 50% of up to $10,000
                qualified_wages = min(self.second_year_wages, wage_limit)
                return qualified_wages * 0.50
            else:
                # First year: 40% of up to $10,000
                qualified_wages = min(self.first_year_wages, wage_limit)
                return qualified_wages * rate
        else:
            # Standard calculation
            qualified_wages = min(self.first_year_wages, wage_limit)
            return qualified_wages * rate


class SmallEmployerHealthInfo(BaseModel):
    """
    Small Employer Health Insurance Credit information (Form 8941 / IRC Section 45R).

    This credit helps small employers afford health insurance for their employees.
    Available for employers with fewer than 25 FTE employees and average wages
    below the threshold (indexed annually).

    Key Rules:
    - Must have fewer than 25 FTE employees
    - Average annual wages must be below threshold (~$59,000 for 2025)
    - Must pay at least 50% of employee-only premium cost
    - Must purchase coverage through SHOP Marketplace (for full credit)
    - Credit available for 2 consecutive years after 2013

    Credit Amounts:
    - Taxable small employers: Up to 50% of premiums paid
    - Tax-exempt employers: Up to 35% of premiums paid

    Phase-out:
    - Phases out as FTEs approach 25
    - Phases out as average wages approach threshold
    """
    # Business information
    is_tax_exempt: bool = Field(
        default=False,
        description="True for tax-exempt organizations (501(c)(3), etc.)"
    )
    is_shop_marketplace: bool = Field(
        default=True,
        description="Coverage purchased through SHOP Marketplace"
    )
    credit_year_number: int = Field(
        default=1,
        ge=1,
        le=2,
        description="Year 1 or 2 of claiming credit (max 2 consecutive years)"
    )

    # Employee counts and wages
    fte_count: float = Field(
        ge=0,
        lt=25,
        description="Number of full-time equivalent employees (must be < 25)"
    )
    total_employee_count: int = Field(
        default=0,
        ge=0,
        description="Total number of employees (for reference)"
    )
    total_wages_paid: float = Field(
        ge=0,
        description="Total wages paid to employees during the year"
    )

    # Premium information
    total_premiums_paid: float = Field(
        ge=0,
        description="Total health insurance premiums paid by employer"
    )
    employee_only_premiums: float = Field(
        default=0.0,
        ge=0,
        description="Premiums for employee-only coverage (not family)"
    )
    employer_contribution_percentage: float = Field(
        ge=50,
        le=100,
        description="Percentage of employee-only premiums paid by employer (must be ≥50%)"
    )

    # State premium information (for small employer average premium limitation)
    state_average_premium: Optional[float] = Field(
        None,
        ge=0,
        description="State average premium for small group market (if known)"
    )

    def get_average_annual_wages(self) -> float:
        """Calculate average annual wages per FTE."""
        if self.fte_count <= 0:
            return 0.0
        return self.total_wages_paid / self.fte_count

    def calculate_fte_phase_out(self) -> float:
        """
        Calculate FTE-based phase-out factor.
        Credit phases out linearly from 10 to 25 FTEs.
        Returns factor from 0.0 (no credit) to 1.0 (full credit).
        """
        if self.fte_count <= 10:
            return 1.0
        elif self.fte_count >= 25:
            return 0.0
        else:
            return (25 - self.fte_count) / 15

    def calculate_wage_phase_out(self, wage_threshold: float = 59000.0) -> float:
        """
        Calculate wage-based phase-out factor.
        Credit phases out linearly from $30,800 to threshold (~$59,000 for 2025).
        Returns factor from 0.0 (no credit) to 1.0 (full credit).
        """
        avg_wages = self.get_average_annual_wages()
        phase_out_start = wage_threshold / 2  # ~$29,500 for 2025

        if avg_wages <= phase_out_start:
            return 1.0
        elif avg_wages >= wage_threshold:
            return 0.0
        else:
            return (wage_threshold - avg_wages) / (wage_threshold - phase_out_start)


class DisabledAccessExpenditureType(str, Enum):
    """
    Types of eligible expenditures for Disabled Access Credit (Form 8826).

    Per IRC Section 44, eligible expenditures include costs to comply with
    the Americans with Disabilities Act (ADA).
    """
    BARRIER_REMOVAL = "barrier_removal"  # Removing architectural/transportation barriers
    INTERPRETER_SERVICES = "interpreter"  # Providing qualified interpreters
    READER_SERVICES = "reader"  # Providing readers for customers/employees
    EQUIPMENT_ACQUISITION = "equipment"  # Acquiring/modifying equipment
    MATERIAL_FORMATS = "materials"  # Providing materials in accessible formats
    OTHER_ACCESSIBILITY = "other"  # Other ADA compliance expenditures


class DisabledAccessExpenditure(BaseModel):
    """
    Individual expenditure for Disabled Access Credit.
    """
    description: str = Field(description="Description of the expenditure")
    expenditure_type: DisabledAccessExpenditureType = Field(
        description="Type of accessibility expenditure"
    )
    amount: float = Field(ge=0, description="Amount spent")
    date_incurred: Optional[str] = Field(None, description="Date expenditure was incurred")


class DisabledAccessInfo(BaseModel):
    """
    Disabled Access Credit information (Form 8826 / IRC Section 44).

    This credit helps eligible small businesses pay for making their
    facilities and services accessible to persons with disabilities.

    Eligibility Requirements:
    - Gross receipts ≤ $1,000,000 in prior year, OR
    - ≤ 30 full-time employees in prior year

    Credit Calculation:
    - 50% of eligible access expenditures
    - Only expenditures between $250 and $10,250 count
    - Maximum credit: $5,000 per year

    Eligible Expenditures (per IRC Section 44(c)):
    - Removing architectural, communication, physical, or transportation barriers
    - Providing qualified interpreters or readers
    - Acquiring or modifying equipment or devices
    - Providing other similar services, modifications, materials, or equipment
    """
    # Business eligibility - must meet ONE of these criteria
    prior_year_gross_receipts: float = Field(
        ge=0,
        description="Prior year gross receipts (must be ≤ $1,000,000 for eligibility)"
    )
    prior_year_full_time_employees: int = Field(
        ge=0,
        description="Number of full-time employees in prior year (must be ≤ 30 for eligibility)"
    )

    # Expenditure information
    expenditures: List[DisabledAccessExpenditure] = Field(
        default_factory=list,
        description="List of eligible access expenditures"
    )

    # Alternative: total expenditures if not itemizing
    total_eligible_expenditures: float = Field(
        default=0.0,
        ge=0,
        description="Total eligible access expenditures (if not listing individually)"
    )

    def is_eligible_small_business(self) -> bool:
        """
        Check if business meets eligibility criteria.
        Must have gross receipts ≤ $1M OR ≤ 30 full-time employees.
        """
        return (
            self.prior_year_gross_receipts <= 1000000 or
            self.prior_year_full_time_employees <= 30
        )

    def get_total_expenditures(self) -> float:
        """Get total expenditures from itemized list or total field."""
        if self.expenditures:
            return sum(exp.amount for exp in self.expenditures)
        return self.total_eligible_expenditures

    def calculate_eligible_amount(
        self,
        min_threshold: float = 250.0,
        max_threshold: float = 10250.0,
    ) -> float:
        """
        Calculate eligible expenditure amount.
        Only amounts between $250 and $10,250 are eligible.
        """
        total = self.get_total_expenditures()

        if total <= min_threshold:
            return 0.0

        # Eligible amount is between min and max thresholds
        eligible = min(total, max_threshold) - min_threshold
        return max(0.0, eligible)


class MarketplaceCoverage(BaseModel):
    """
    Health insurance marketplace coverage information for Form 8962.

    Premium Tax Credit is for individuals who purchased insurance through
    the Health Insurance Marketplace (HealthCare.gov or state exchange).
    """
    # Form 1095-A information
    marketplace_identifier: Optional[str] = None
    policy_start_date: Optional[str] = None
    policy_end_date: Optional[str] = None

    # Monthly amounts from Form 1095-A
    # These are lists of 12 values (January-December), 0 if no coverage that month
    monthly_premium: List[float] = Field(
        default_factory=lambda: [0.0] * 12,
        description="Monthly enrollment premium (Column A)"
    )
    monthly_slcsp: List[float] = Field(
        default_factory=lambda: [0.0] * 12,
        description="Monthly Second Lowest Cost Silver Plan (Column B)"
    )
    monthly_aptc: List[float] = Field(
        default_factory=lambda: [0.0] * 12,
        description="Monthly Advance Premium Tax Credit received (Column C)"
    )

    # Coverage details
    covered_individuals: int = Field(default=1, ge=1, description="Number of individuals covered")
    is_shared_policy: bool = Field(default=False, description="Policy shared with another tax family")
    allocation_percentage: float = Field(default=100.0, ge=0, le=100, description="% of policy allocated to this taxpayer")

    def get_total_premium(self) -> float:
        """Get total annual premium."""
        return sum(self.monthly_premium)

    def get_total_slcsp(self) -> float:
        """Get total annual SLCSP amount."""
        return sum(self.monthly_slcsp)

    def get_total_aptc(self) -> float:
        """Get total advance PTC received."""
        return sum(self.monthly_aptc)

    def get_months_covered(self) -> int:
        """Get number of months with coverage."""
        return sum(1 for p in self.monthly_premium if p > 0)


class EducationCreditType(str, Enum):
    """Types of education credits."""
    AOTC = "aotc"  # American Opportunity Tax Credit
    LLC = "llc"    # Lifetime Learning Credit


class StudentInfo(BaseModel):
    """
    Student information for education credits.

    Each student's eligibility and expenses are tracked separately
    because AOTC is per-student while LLC is per-return.
    """
    name: str
    ssn: Optional[str] = None
    is_taxpayer: bool = Field(default=False, description="Is this the primary taxpayer")
    is_spouse: bool = Field(default=False, description="Is this the spouse")
    is_dependent: bool = Field(default=False, description="Is this a dependent")

    # Eligibility for AOTC (stricter requirements)
    is_enrolled_at_least_half_time: bool = Field(
        default=True,
        description="Enrolled at least half-time for at least one academic period"
    )
    is_first_four_years: bool = Field(
        default=True,
        description="Has not completed first 4 years of post-secondary education"
    )
    years_aotc_claimed: int = Field(
        default=0,
        ge=0,
        le=4,
        description="Number of years AOTC previously claimed for this student (max 4)"
    )
    has_felony_drug_conviction: bool = Field(
        default=False,
        description="Felony drug conviction disqualifies from AOTC"
    )
    is_pursuing_degree: bool = Field(
        default=True,
        description="Enrolled in program leading to degree/credential"
    )

    # Qualified expenses
    tuition_fees: float = Field(default=0.0, ge=0, description="Tuition and required fees")
    books_supplies_equipment: float = Field(default=0.0, ge=0, description="Books, supplies, equipment")

    # Adjustments to expenses
    scholarships_grants: float = Field(default=0.0, ge=0, description="Tax-free scholarships/grants received")
    employer_assistance: float = Field(default=0.0, ge=0, description="Employer educational assistance")
    veterans_benefits: float = Field(default=0.0, ge=0, description="Veterans' educational assistance")
    other_tax_free_assistance: float = Field(default=0.0, ge=0, description="Other tax-free educational assistance")

    # Form 1098-T info
    form_1098t_received: bool = Field(default=True, description="Required unless exception applies")
    institution_ein: Optional[str] = None
    institution_name: Optional[str] = None

    def get_qualified_expenses(self, credit_type: EducationCreditType = EducationCreditType.AOTC) -> float:
        """
        Calculate qualified education expenses net of tax-free assistance.

        For AOTC: Tuition, fees, books, supplies, equipment
        For LLC: Tuition and fees only (books only if required)
        """
        if credit_type == EducationCreditType.AOTC:
            gross_expenses = self.tuition_fees + self.books_supplies_equipment
        else:  # LLC
            gross_expenses = self.tuition_fees

        # Reduce by tax-free assistance
        assistance = (
            self.scholarships_grants +
            self.employer_assistance +
            self.veterans_benefits +
            self.other_tax_free_assistance
        )

        return max(0.0, gross_expenses - assistance)

    def is_aotc_eligible(self) -> bool:
        """Check if student is eligible for AOTC."""
        return (
            self.is_enrolled_at_least_half_time and
            self.is_first_four_years and
            self.years_aotc_claimed < 4 and
            not self.has_felony_drug_conviction and
            self.is_pursuing_degree and
            self.form_1098t_received
        )


class TaxCredits(BaseModel):
    """Tax credits (reduce tax liability dollar-for-dollar)"""
    # Child and dependent care credit (Form 2441)
    child_care_expenses: float = Field(default=0.0, ge=0)
    child_care_provider_tin: Optional[str] = None
    num_qualifying_persons: int = Field(
        default=0,
        ge=0,
        le=10,
        description="Number of qualifying persons (children under 13 or disabled dependents)"
    )

    # Child tax credit
    child_tax_credit_children: int = Field(default=0, ge=0)
    
    # Earned Income Tax Credit (EITC)
    eitc_eligible: bool = False
    
    # Education credits (BR-0801 to BR-0830)
    education_expenses: float = Field(default=0.0, ge=0, description="Legacy field - use students instead")
    education_credit_type: Optional[str] = Field(None, description="AOTC or LLC")
    students: List[StudentInfo] = Field(default_factory=list, description="Students for education credits")

    # Retirement Savings Contributions Credit (Saver's Credit - Form 8880)
    # Note: IRA and SEP contributions are tracked in deductions.py
    elective_deferrals_401k: float = Field(
        default=0.0,
        ge=0,
        description="401(k)/403(b)/457/TSP elective deferrals for Saver's Credit"
    )
    savers_credit_eligible: bool = Field(
        default=True,
        description="Meets eligibility: age 18+, not full-time student, not claimed as dependent"
    )
    
    # Premium Tax Credit (Form 8962)
    marketplace_coverage: List[MarketplaceCoverage] = Field(
        default_factory=list,
        description="Health insurance marketplace policies (Form 1095-A)"
    )
    household_income: Optional[float] = Field(None, description="Household income for PTC calculation")
    family_size: int = Field(default=1, ge=1, description="Family size for FPL calculation")

    # Other credits
    foreign_tax_credit: float = Field(default=0.0, ge=0)
    foreign_tax_credit_carryforward: float = Field(default=0.0, ge=0, description="FTC carryforward from prior years")
    residential_energy_credit: float = Field(default=0.0, ge=0)

    # Residential Clean Energy Credit (Form 5695 Part I) - Section 25D
    solar_electric_expenses: float = Field(default=0.0, ge=0, description="Solar electric system costs")
    solar_water_heating_expenses: float = Field(default=0.0, ge=0, description="Solar water heater costs")
    small_wind_expenses: float = Field(default=0.0, ge=0, description="Small wind turbine costs")
    geothermal_heat_pump_expenses: float = Field(default=0.0, ge=0, description="Geothermal heat pump costs")
    battery_storage_expenses: float = Field(default=0.0, ge=0, description="Battery storage (≥3 kWh) costs")
    fuel_cell_expenses: float = Field(default=0.0, ge=0, description="Fuel cell costs")
    fuel_cell_kilowatt_capacity: float = Field(default=0.0, ge=0, description="Fuel cell capacity in kW")

    # Energy Efficient Home Improvement Credit (Form 5695 Part II) - Section 25C
    insulation_expenses: float = Field(default=0.0, ge=0, description="Insulation and air sealing costs")
    window_expenses: float = Field(default=0.0, ge=0, description="Energy efficient windows/skylights")
    door_expenses: float = Field(default=0.0, ge=0, description="Exterior door costs")
    door_count: int = Field(default=0, ge=0, description="Number of doors for $250/door limit")
    central_ac_expenses: float = Field(default=0.0, ge=0, description="Central A/C or gas water heater costs")
    electric_panel_expenses: float = Field(default=0.0, ge=0, description="Electric panel upgrade costs")
    home_energy_audit_expenses: float = Field(default=0.0, ge=0, description="Home energy audit costs")
    heat_pump_expenses: float = Field(default=0.0, ge=0, description="Heat pump HVAC costs")
    heat_pump_water_heater_expenses: float = Field(default=0.0, ge=0, description="Heat pump water heater costs")
    biomass_stove_expenses: float = Field(default=0.0, ge=0, description="Biomass stove/boiler costs")

    # Clean Vehicle Credits (Form 8936 - IRC Sections 30D and 25E)
    clean_vehicles: List[CleanVehiclePurchase] = Field(
        default_factory=list,
        description="Clean vehicle purchases for Form 8936"
    )

    # Adoption Credit (Form 8839 - IRC Section 23)
    adoptions: List[AdoptionInfo] = Field(
        default_factory=list,
        description="Adoption information for Form 8839"
    )

    # Credit for Elderly or Disabled (Schedule R - IRC Section 22)
    elderly_disabled_info: Optional[ElderlyDisabledInfo] = Field(
        None,
        description="Information for Schedule R credit"
    )

    # Work Opportunity Tax Credit (Form 5884 - IRC Section 51)
    wotc_employees: List[WOTCEmployee] = Field(
        default_factory=list,
        description="Employees qualifying for Work Opportunity Tax Credit"
    )

    # Small Employer Health Insurance Credit (Form 8941 - IRC Section 45R)
    small_employer_health_info: Optional[SmallEmployerHealthInfo] = Field(
        None,
        description="Small employer health insurance credit information"
    )

    # Disabled Access Credit (Form 8826 - IRC Section 44)
    disabled_access_info: Optional[DisabledAccessInfo] = Field(
        None,
        description="Disabled access credit information for ADA compliance"
    )

    other_credits: float = Field(default=0.0, ge=0)
    other_credits_description: Optional[str] = None

    def calculate_clean_vehicle_credit(
        self,
        magi: float,
        filing_status: str,
        tax_year: int = 2025,
    ) -> Tuple[float, float, dict]:
        """
        Calculate Clean Vehicle Credit (Form 8936).

        Implements both:
        - New Clean Vehicle Credit (IRC Section 30D) - up to $7,500
        - Previously Owned Clean Vehicle Credit (IRC Section 25E) - up to $4,000

        Per Inflation Reduction Act of 2022 (as amended):

        New Vehicles (Section 30D):
        - $7,500 total: $3,750 for battery components + $3,750 for critical minerals
        - MSRP limits: $55,000 sedan/hatchback, $80,000 SUV/van/truck/pickup
        - Income limits (MAGI): $150,000 single, $225,000 HOH, $300,000 MFJ
        - Must be assembled in North America
        - Nonrefundable

        Previously Owned Vehicles (Section 25E):
        - 30% of sale price, max $4,000
        - Price limit: $25,000
        - Income limits: $75,000 single, $112,500 HOH, $150,000 MFJ
        - Model year must be at least 2 years older than current year
        - Nonrefundable

        Args:
            magi: Modified Adjusted Gross Income
            filing_status: Filing status for income limit
            tax_year: Tax year for model year requirement

        Returns:
            Tuple of (new_vehicle_credit, used_vehicle_credit, breakdown_dict)
        """
        breakdown = {
            'new_vehicles': [],
            'used_vehicles': [],
            'total_new_credit': 0.0,
            'total_used_credit': 0.0,
            'new_vehicles_qualified': 0,
            'used_vehicles_qualified': 0,
            'vehicles_disqualified_income': 0,
            'vehicles_disqualified_price': 0,
            'vehicles_disqualified_other': 0,
        }

        # Income limits for new vehicles (Section 30D)
        new_vehicle_income_limits = {
            'single': 150000.0,
            'married_separate': 75000.0,
            'head_of_household': 225000.0,
            'married_joint': 300000.0,
            'qualifying_widow': 300000.0,
        }

        # Income limits for used vehicles (Section 25E)
        used_vehicle_income_limits = {
            'single': 75000.0,
            'married_separate': 37500.0,
            'head_of_household': 112500.0,
            'married_joint': 150000.0,
            'qualifying_widow': 150000.0,
        }

        # MSRP limits for new vehicles by vehicle type
        msrp_limits = {
            VehicleType.SEDAN: 55000.0,
            VehicleType.HATCHBACK: 55000.0,
            VehicleType.SUV: 80000.0,
            VehicleType.VAN: 80000.0,
            VehicleType.TRUCK: 80000.0,
            VehicleType.PICKUP: 80000.0,
        }

        total_new_credit = 0.0
        total_used_credit = 0.0

        for vehicle in self.clean_vehicles:
            vehicle_info = {
                'vin': vehicle.vin,
                'make': vehicle.make,
                'model': vehicle.model,
                'model_year': vehicle.model_year,
                'is_new': vehicle.is_new_vehicle,
                'credit': 0.0,
                'qualified': False,
                'disqualification_reason': None,
            }

            if vehicle.is_new_vehicle:
                # === New Clean Vehicle (Section 30D) ===

                # Check income limit
                income_limit = new_vehicle_income_limits.get(filing_status, 150000.0)
                if magi > income_limit:
                    vehicle_info['disqualification_reason'] = f'MAGI ${magi:,.0f} exceeds ${income_limit:,.0f} limit'
                    breakdown['vehicles_disqualified_income'] += 1
                    breakdown['new_vehicles'].append(vehicle_info)
                    continue

                # Check MSRP limit
                msrp_limit = msrp_limits.get(vehicle.vehicle_type, 55000.0)
                if vehicle.msrp > msrp_limit:
                    vehicle_info['disqualification_reason'] = f'MSRP ${vehicle.msrp:,.0f} exceeds ${msrp_limit:,.0f} limit'
                    breakdown['vehicles_disqualified_price'] += 1
                    breakdown['new_vehicles'].append(vehicle_info)
                    continue

                # Check North American assembly
                if not vehicle.final_assembly_north_america:
                    vehicle_info['disqualification_reason'] = 'Not assembled in North America'
                    breakdown['vehicles_disqualified_other'] += 1
                    breakdown['new_vehicles'].append(vehicle_info)
                    continue

                # Calculate credit components
                battery_credit = 3750.0 if vehicle.meets_battery_component_req else 0.0
                mineral_credit = 3750.0 if vehicle.meets_critical_mineral_req else 0.0
                credit = battery_credit + mineral_credit

                vehicle_info['credit'] = credit
                vehicle_info['battery_component_credit'] = battery_credit
                vehicle_info['critical_mineral_credit'] = mineral_credit
                vehicle_info['qualified'] = True
                total_new_credit += credit
                breakdown['new_vehicles_qualified'] += 1
                breakdown['new_vehicles'].append(vehicle_info)

            else:
                # === Previously Owned Clean Vehicle (Section 25E) ===

                # Check income limit
                income_limit = used_vehicle_income_limits.get(filing_status, 75000.0)
                if magi > income_limit:
                    vehicle_info['disqualification_reason'] = f'MAGI ${magi:,.0f} exceeds ${income_limit:,.0f} limit'
                    breakdown['vehicles_disqualified_income'] += 1
                    breakdown['used_vehicles'].append(vehicle_info)
                    continue

                # Check sale price limit ($25,000)
                if vehicle.purchase_price > 25000.0:
                    vehicle_info['disqualification_reason'] = f'Sale price ${vehicle.purchase_price:,.0f} exceeds $25,000 limit'
                    breakdown['vehicles_disqualified_price'] += 1
                    breakdown['used_vehicles'].append(vehicle_info)
                    continue

                # Check model year (must be at least 2 years older)
                min_model_year = tax_year - 2
                if vehicle.model_year > min_model_year:
                    vehicle_info['disqualification_reason'] = f'Model year {vehicle.model_year} must be {min_model_year} or earlier'
                    breakdown['vehicles_disqualified_other'] += 1
                    breakdown['used_vehicles'].append(vehicle_info)
                    continue

                # Check first transfer requirement
                if not vehicle.is_first_transfer:
                    vehicle_info['disqualification_reason'] = 'Not first transfer of vehicle'
                    breakdown['vehicles_disqualified_other'] += 1
                    breakdown['used_vehicles'].append(vehicle_info)
                    continue

                # Calculate credit: 30% of sale price, max $4,000
                credit = min(vehicle.purchase_price * 0.30, 4000.0)

                vehicle_info['credit'] = credit
                vehicle_info['qualified'] = True
                total_used_credit += credit
                breakdown['used_vehicles_qualified'] += 1
                breakdown['used_vehicles'].append(vehicle_info)

        breakdown['total_new_credit'] = float(money(total_new_credit))
        breakdown['total_used_credit'] = float(money(total_used_credit))

        return float(money(total_new_credit)), float(money(total_used_credit)), breakdown

    def calculate_adoption_credit(
        self,
        magi: float,
        filing_status: str,
        tax_year: int = 2025,
        max_credit: float = 16810.0,
        phaseout_start: float = 252150.0,
        phaseout_end: float = 292150.0,
    ) -> Tuple[float, dict]:
        """
        Calculate Adoption Credit (Form 8839 / IRC Section 23).

        The adoption credit helps taxpayers offset costs of adopting an eligible child.
        Credit is nonrefundable but can be carried forward up to 5 years.

        Key Rules:
        - Maximum credit: $16,810 per child for 2025 (indexed for inflation)
        - Special needs: Full maximum credit regardless of actual expenses
        - Domestic adoption: Credit available when expenses paid or finalized
        - Foreign adoption: Credit only available when adoption finalized
        - Income phaseout: Begins at $252,150, fully phased out at $292,150 (2025)
        - Child must be under 18 or physically/mentally incapable of self-care

        Args:
            magi: Modified Adjusted Gross Income
            filing_status: Filing status (affects nothing for adoption credit)
            tax_year: Tax year for child age calculation
            max_credit: Maximum credit per child (from config)
            phaseout_start: MAGI where phaseout begins (from config)
            phaseout_end: MAGI where phaseout ends (from config)

        Returns:
            Tuple of (total_credit, breakdown_dict)
        """
        breakdown = {
            'adoptions': [],
            'total_credit_before_phaseout': 0.0,
            'total_credit_after_phaseout': 0.0,
            'total_carryforward_used': 0.0,
            'phaseout_percentage': 0.0,
            'children_qualified': 0,
            'children_disqualified': 0,
            'max_credit_per_child': max_credit,
        }

        if not self.adoptions:
            return 0.0, breakdown

        # Calculate phaseout percentage
        if magi <= phaseout_start:
            phaseout_pct = 0.0
        elif magi >= phaseout_end:
            phaseout_pct = 1.0  # Fully phased out
        else:
            phaseout_pct = (magi - phaseout_start) / (phaseout_end - phaseout_start)

        breakdown['phaseout_percentage'] = float(money(phaseout_pct * 100))

        total_credit_before = 0.0
        total_carryforward = 0.0

        for adoption in self.adoptions:
            adoption_info = {
                'child_name': adoption.child_name,
                'adoption_type': adoption.adoption_type.value,
                'is_special_needs': adoption.is_special_needs,
                'qualified_expenses': 0.0,
                'credit_before_phaseout': 0.0,
                'credit_after_phaseout': 0.0,
                'carryforward_used': 0.0,
                'qualified': False,
                'disqualification_reason': None,
            }

            # Check if child is eligible (under 18 or disabled)
            if not adoption.is_eligible_child(tax_year):
                adoption_info['disqualification_reason'] = 'Child not eligible (18+ and not disabled)'
                breakdown['children_disqualified'] += 1
                breakdown['adoptions'].append(adoption_info)
                continue

            # Check adoption timing rules
            if adoption.adoption_type == AdoptionType.FOREIGN:
                # Foreign adoption: credit only when finalized
                if not adoption.adoption_finalized:
                    adoption_info['disqualification_reason'] = 'Foreign adoption not yet finalized'
                    breakdown['children_disqualified'] += 1
                    breakdown['adoptions'].append(adoption_info)
                    continue

            # Calculate qualified expenses
            if adoption.is_special_needs or adoption.adoption_type == AdoptionType.SPECIAL_NEEDS:
                # Special needs: full max credit regardless of actual expenses
                qualified_expenses = max_credit
                adoption_info['is_special_needs'] = True
            else:
                # Regular adoption: credit based on actual expenses
                qualified_expenses = adoption.get_expenses_net_of_benefits()

            adoption_info['qualified_expenses'] = float(money(qualified_expenses))

            # Credit is capped at max per child
            credit_for_child = min(qualified_expenses, max_credit)
            adoption_info['credit_before_phaseout'] = float(money(credit_for_child))

            # Apply income phaseout
            credit_after_phaseout = credit_for_child * (1 - phaseout_pct)
            adoption_info['credit_after_phaseout'] = float(money(credit_after_phaseout))

            total_credit_before += credit_for_child

            # Include prior year carryforward
            if adoption.prior_year_carryforward > 0:
                carryforward_after_phaseout = adoption.prior_year_carryforward * (1 - phaseout_pct)
                adoption_info['carryforward_used'] = float(money(carryforward_after_phaseout))
                total_carryforward += carryforward_after_phaseout

            adoption_info['qualified'] = True
            breakdown['children_qualified'] += 1
            breakdown['adoptions'].append(adoption_info)

        breakdown['total_credit_before_phaseout'] = float(money(total_credit_before))
        breakdown['total_carryforward_used'] = float(money(total_carryforward))

        # Apply phaseout to total
        total_credit_after = total_credit_before * (1 - phaseout_pct) + total_carryforward
        breakdown['total_credit_after_phaseout'] = float(money(total_credit_after))

        return float(money(total_credit_after)), breakdown

    def calculate_elderly_disabled_credit(
        self,
        agi: float,
        filing_status: str,
        tax_year: int = 2025,
    ) -> Tuple[float, dict]:
        """
        Calculate Credit for the Elderly or Disabled (Schedule R / IRC Section 22).

        This nonrefundable credit helps elderly (65+) and permanently disabled
        taxpayers with limited income.

        Eligibility:
        - 65 or older by end of tax year, OR
        - Under 65 and permanently/totally disabled with taxable disability income

        Initial Amounts:
        - Single, HOH, QW: $5,000
        - MFJ (both qualify): $7,500
        - MFJ (one qualifies): $5,000
        - MFS: $3,750

        Reductions:
        1. Nontaxable Social Security, pensions, etc.
        2. 50% of AGI exceeding threshold

        Credit = 15% of amount after reductions

        Args:
            agi: Adjusted Gross Income
            filing_status: Filing status
            tax_year: Tax year for age calculation

        Returns:
            Tuple of (credit_amount, breakdown_dict)
        """
        breakdown = {
            'taxpayer_qualifies': False,
            'spouse_qualifies': False,
            'qualification_method': None,
            'initial_amount': 0.0,
            'nontaxable_income_reduction': 0.0,
            'agi_excess_reduction': 0.0,
            'amount_after_reductions': 0.0,
            'credit_rate': 0.15,
            'credit_amount': 0.0,
            'disqualification_reason': None,
        }

        info = self.elderly_disabled_info
        if not info:
            return 0.0, breakdown

        # Initial amounts by filing status
        initial_amounts = {
            'single': 5000.0,
            'head_of_household': 5000.0,
            'qualifying_widow': 5000.0,
            'married_joint_both': 7500.0,
            'married_joint_one': 5000.0,
            'married_separate': 3750.0,
        }

        # AGI thresholds for 50% reduction
        agi_thresholds = {
            'single': 7500.0,
            'head_of_household': 7500.0,
            'qualifying_widow': 7500.0,
            'married_joint': 10000.0,
            'married_separate': 5000.0,
        }

        # AGI limits (if AGI exceeds, likely no credit)
        agi_limits = {
            'single': 17500.0,
            'head_of_household': 17500.0,
            'qualifying_widow': 17500.0,
            'married_joint': 25000.0,
            'married_separate': 12500.0,
        }

        # Nontaxable income limits
        nontaxable_limits = {
            'single': 5000.0,
            'head_of_household': 5000.0,
            'qualifying_widow': 5000.0,
            'married_joint': 7500.0,
            'married_separate': 3750.0,
        }

        # Check MFS special rule
        if filing_status == 'married_separate' and not info.lived_apart_all_year:
            breakdown['disqualification_reason'] = 'MFS must live apart all year'
            return 0.0, breakdown

        # Determine if taxpayer qualifies
        taxpayer_qualifies_age = info.taxpayer_qualifies_by_age(tax_year)
        taxpayer_qualifies_disability = info.taxpayer_qualifies_by_disability()
        taxpayer_qualifies = taxpayer_qualifies_age or taxpayer_qualifies_disability

        if taxpayer_qualifies:
            breakdown['taxpayer_qualifies'] = True
            breakdown['qualification_method'] = 'age_65_plus' if taxpayer_qualifies_age else 'disability'

        # Determine if spouse qualifies (for MFJ)
        spouse_qualifies = False
        if filing_status == 'married_joint':
            spouse_qualifies_age = info.spouse_qualifies_by_age(tax_year)
            spouse_qualifies_disability = info.spouse_qualifies_by_disability()
            spouse_qualifies = spouse_qualifies_age or spouse_qualifies_disability
            breakdown['spouse_qualifies'] = spouse_qualifies

        # Must have at least one qualifying person
        if not taxpayer_qualifies and not spouse_qualifies:
            breakdown['disqualification_reason'] = 'Neither taxpayer nor spouse qualifies'
            return 0.0, breakdown

        # Determine initial amount
        if filing_status == 'married_joint':
            if taxpayer_qualifies and spouse_qualifies:
                initial_amount = initial_amounts['married_joint_both']
            else:
                initial_amount = initial_amounts['married_joint_one']
        elif filing_status == 'married_separate':
            initial_amount = initial_amounts['married_separate']
        else:
            initial_amount = initial_amounts.get(filing_status, 5000.0)

        breakdown['initial_amount'] = initial_amount

        # For disabled individuals under 65, limit initial amount to disability income
        if not taxpayer_qualifies_age and taxpayer_qualifies_disability:
            if filing_status != 'married_joint':
                initial_amount = min(initial_amount, info.taxpayer_disability_income)
            else:
                # Complex rules for MFJ with disability - simplified here
                total_disability = info.taxpayer_disability_income + info.spouse_disability_income
                if not taxpayer_qualifies_age and not info.spouse_qualifies_by_age(tax_year):
                    initial_amount = min(initial_amount, total_disability)

        # Reduction 1: Nontaxable Social Security and other income
        nontaxable_income = info.get_total_nontaxable_income()
        breakdown['nontaxable_income_reduction'] = nontaxable_income

        amount_after_nontaxable = max(0, initial_amount - nontaxable_income)

        # Reduction 2: 50% of AGI over threshold
        if filing_status == 'married_joint':
            agi_threshold = agi_thresholds['married_joint']
        else:
            agi_threshold = agi_thresholds.get(filing_status, 7500.0)

        agi_excess = max(0, agi - agi_threshold)
        agi_reduction = agi_excess * 0.5
        breakdown['agi_excess_reduction'] = agi_reduction

        amount_after_reductions = max(0, amount_after_nontaxable - agi_reduction)
        breakdown['amount_after_reductions'] = float(money(amount_after_reductions))

        # Calculate credit: 15% of remaining amount
        credit = amount_after_reductions * 0.15
        breakdown['credit_amount'] = float(money(credit))

        return float(money(credit)), breakdown

    def calculate_wotc(
        self,
        tax_year: int = 2025,
    ) -> Tuple[float, dict]:
        """
        Calculate Work Opportunity Tax Credit (Form 5884 / IRC Section 51).

        WOTC is an employer credit for hiring individuals from target groups
        who face significant barriers to employment.

        Credit Calculation:
        - 0% if employee works < 120 hours (no credit)
        - 25% of qualified wages if 120-399 hours worked
        - 40% of qualified wages if 400+ hours worked

        Target Group Wage Limits:
        - Most groups: $6,000 qualified wage limit → max $2,400 credit
        - Summer youth: $3,000 limit → max $1,200 credit
        - Disabled veteran: $12,000 limit → max $4,800 credit
        - Disabled unemployed veteran: $24,000 limit → max $9,600 credit
        - Long-term family assistance: $10,000/year for 2 years
          (40% year 1, 50% year 2) → max $9,000 total

        Requirements:
        - Employer must obtain certification from State Workforce Agency (Form 8850)
        - Employee must work minimum 120 hours for any credit
        - Credit claimed on employer's tax return

        Note: WOTC is a general business credit subject to limitations
        under IRC Section 38. This implementation calculates the credit amount
        before any general business credit limitations are applied.

        Args:
            tax_year: Tax year for reporting

        Returns:
            Tuple of (total_credit, breakdown_dict)
        """
        breakdown = {
            'total_credit': 0.0,
            'employees': [],
            'employees_qualified': 0,
            'employees_disqualified': 0,
            'total_first_year_credit': 0.0,
            'total_second_year_credit': 0.0,
            'by_target_group': {},
        }

        if not self.wotc_employees:
            return 0.0, breakdown

        total_credit = 0.0
        first_year_total = 0.0
        second_year_total = 0.0
        target_group_totals = {}

        for employee in self.wotc_employees:
            emp_detail = {
                'name': employee.employee_name,
                'target_group': employee.target_group.value,
                'hours_worked': employee.hours_worked,
                'first_year_wages': employee.first_year_wages,
                'second_year_wages': employee.second_year_wages,
                'is_second_year': employee.is_second_year,
                'credit_rate': 0.0,
                'wage_limit': employee.get_wage_limit(),
                'qualified_wages': 0.0,
                'credit': 0.0,
                'qualified': False,
                'disqualification_reason': None,
            }

            # Check certification
            if not employee.certification_received:
                emp_detail['disqualification_reason'] = 'Form 8850 certification not received'
                breakdown['employees_disqualified'] += 1
                breakdown['employees'].append(emp_detail)
                continue

            # Check minimum hours
            if employee.hours_worked < 120:
                emp_detail['disqualification_reason'] = f'Hours worked ({employee.hours_worked}) < 120 minimum'
                breakdown['employees_disqualified'] += 1
                breakdown['employees'].append(emp_detail)
                continue

            # Calculate credit
            credit = employee.calculate_credit()
            emp_detail['credit_rate'] = employee.get_credit_rate()

            if employee.target_group == WOTCTargetGroup.LONG_TERM_FAMILY_ASSISTANCE:
                if employee.is_second_year:
                    emp_detail['qualified_wages'] = min(employee.second_year_wages, employee.get_wage_limit())
                    second_year_total += credit
                else:
                    emp_detail['qualified_wages'] = min(employee.first_year_wages, employee.get_wage_limit())
                    first_year_total += credit
            else:
                emp_detail['qualified_wages'] = min(employee.first_year_wages, employee.get_wage_limit())
                first_year_total += credit

            emp_detail['credit'] = float(money(credit))
            emp_detail['qualified'] = True
            total_credit += credit
            breakdown['employees_qualified'] += 1

            # Track by target group
            group_key = employee.target_group.value
            if group_key not in target_group_totals:
                target_group_totals[group_key] = {
                    'count': 0,
                    'total_credit': 0.0,
                    'total_wages': 0.0,
                }
            target_group_totals[group_key]['count'] += 1
            target_group_totals[group_key]['total_credit'] += credit
            target_group_totals[group_key]['total_wages'] += emp_detail['qualified_wages']

            breakdown['employees'].append(emp_detail)

        # Populate summary
        breakdown['total_credit'] = float(money(total_credit))
        breakdown['total_first_year_credit'] = float(money(first_year_total))
        breakdown['total_second_year_credit'] = float(money(second_year_total))
        breakdown['by_target_group'] = {
            k: {
                'count': v['count'],
                'total_credit': float(money(v['total_credit'])),
                'total_wages': float(money(v['total_wages'])),
            }
            for k, v in target_group_totals.items()
        }

        return float(money(total_credit)), breakdown

    def calculate_small_employer_health_credit(
        self,
        tax_year: int = 2025,
        wage_threshold: float = 59000.0,
    ) -> Tuple[float, dict]:
        """
        Calculate Small Employer Health Insurance Credit (Form 8941 / IRC Section 45R).

        This credit helps small employers afford health insurance for employees.

        Eligibility Requirements:
        - Fewer than 25 FTE employees
        - Average annual wages below threshold (~$59,000 for 2025)
        - Pay at least 50% of employee-only premium cost
        - Coverage through SHOP Marketplace (for full credit)

        Credit Amounts:
        - Taxable employers: 50% of premiums paid
        - Tax-exempt employers: 35% of premiums paid

        Phase-out:
        - FTE phase-out: Credit reduces linearly from 10 to 25 FTEs
        - Wage phase-out: Credit reduces linearly from ~$29,500 to ~$59,000

        Limitations:
        - Credit cannot exceed premiums paid
        - Credit limited to state average premium if applicable
        - Maximum 2 consecutive years of claiming credit

        Args:
            tax_year: Tax year for calculation
            wage_threshold: Average wage threshold for phase-out (~$59,000 for 2025)

        Returns:
            Tuple of (credit_amount, breakdown_dict)
        """
        breakdown = {
            'credit_amount': 0.0,
            'premiums_paid': 0.0,
            'fte_count': 0.0,
            'average_wages': 0.0,
            'base_credit_rate': 0.0,
            'fte_phase_out_factor': 1.0,
            'wage_phase_out_factor': 1.0,
            'combined_phase_out': 1.0,
            'credit_before_phase_out': 0.0,
            'is_tax_exempt': False,
            'is_shop_marketplace': True,
            'credit_year': 1,
            'qualified': False,
            'disqualification_reason': None,
        }

        info = self.small_employer_health_info
        if not info:
            return 0.0, breakdown

        breakdown['fte_count'] = info.fte_count
        breakdown['premiums_paid'] = info.total_premiums_paid
        breakdown['is_tax_exempt'] = info.is_tax_exempt
        breakdown['is_shop_marketplace'] = info.is_shop_marketplace
        breakdown['credit_year'] = info.credit_year_number

        # Check FTE limit (must be < 25)
        if info.fte_count >= 25:
            breakdown['disqualification_reason'] = f'FTE count ({info.fte_count}) must be less than 25'
            return 0.0, breakdown

        # Calculate average wages
        avg_wages = info.get_average_annual_wages()
        breakdown['average_wages'] = float(money(avg_wages))

        # Check wage threshold
        if avg_wages >= wage_threshold:
            breakdown['disqualification_reason'] = f'Average wages (${avg_wages:,.0f}) exceed ${wage_threshold:,.0f} threshold'
            return 0.0, breakdown

        # Check SHOP marketplace requirement
        if not info.is_shop_marketplace:
            breakdown['disqualification_reason'] = 'Coverage must be through SHOP Marketplace'
            return 0.0, breakdown

        # Check minimum employer contribution (50%)
        if info.employer_contribution_percentage < 50:
            breakdown['disqualification_reason'] = f'Employer contribution ({info.employer_contribution_percentage}%) must be at least 50%'
            return 0.0, breakdown

        # Determine base credit rate
        if info.is_tax_exempt:
            base_rate = 0.35  # 35% for tax-exempt
        else:
            base_rate = 0.50  # 50% for taxable
        breakdown['base_credit_rate'] = base_rate

        # Calculate phase-out factors
        fte_factor = info.calculate_fte_phase_out()
        wage_factor = info.calculate_wage_phase_out(wage_threshold)
        breakdown['fte_phase_out_factor'] = round(fte_factor, 4)
        breakdown['wage_phase_out_factor'] = round(wage_factor, 4)

        # Combined phase-out (multiply factors)
        combined_factor = fte_factor * wage_factor
        breakdown['combined_phase_out'] = round(combined_factor, 4)

        # Calculate credit before phase-out
        # Use employee-only premiums if available, otherwise total premiums
        premiums_for_credit = info.employee_only_premiums if info.employee_only_premiums > 0 else info.total_premiums_paid

        # Apply state average premium limit if applicable
        if info.state_average_premium and info.state_average_premium > 0:
            # Limit premiums to state average × number of employees
            max_premiums = info.state_average_premium * info.fte_count
            premiums_for_credit = min(premiums_for_credit, max_premiums)
            breakdown['state_average_premium_applied'] = True
            breakdown['max_premiums_after_state_limit'] = float(money(max_premiums))

        credit_before_phaseout = premiums_for_credit * base_rate
        breakdown['credit_before_phase_out'] = float(money(credit_before_phaseout))

        # Apply phase-out
        credit = credit_before_phaseout * combined_factor
        breakdown['credit_amount'] = float(money(credit))
        breakdown['qualified'] = True

        return float(money(credit)), breakdown

    def calculate_disabled_access_credit(
        self,
        tax_year: int = 2025,
        min_expenditure: float = 250.0,
        max_expenditure: float = 10250.0,
        credit_rate: float = 0.50,
    ) -> Tuple[float, dict]:
        """
        Calculate Disabled Access Credit (Form 8826 / IRC Section 44).

        This credit helps eligible small businesses pay for making their
        facilities and services accessible to persons with disabilities.

        Eligibility Requirements:
        - Gross receipts ≤ $1,000,000 in prior year, OR
        - ≤ 30 full-time employees in prior year
        (Must meet at least ONE criterion)

        Credit Calculation:
        - 50% of eligible access expenditures
        - Only expenditures between $250 and $10,250 count
        - Maximum credit: $5,000 per year (50% of $10,000)

        Eligible Expenditures (per IRC Section 44(c)):
        - Removing architectural, communication, physical, or transportation barriers
        - Providing qualified interpreters or readers
        - Acquiring or modifying equipment or devices
        - Providing other similar services, modifications, or equipment

        Note: This credit is part of the general business credit and may be
        subject to limitations under IRC Section 38.

        Args:
            tax_year: Tax year for calculation
            min_expenditure: Minimum expenditure threshold ($250)
            max_expenditure: Maximum expenditure threshold ($10,250)
            credit_rate: Credit rate (50%)

        Returns:
            Tuple of (credit_amount, breakdown_dict)
        """
        breakdown = {
            'credit_amount': 0.0,
            'total_expenditures': 0.0,
            'eligible_expenditures': 0.0,
            'min_threshold': min_expenditure,
            'max_threshold': max_expenditure,
            'credit_rate': credit_rate,
            'max_credit': float(money((max_expenditure - min_expenditure) * credit_rate)),
            'prior_year_gross_receipts': 0.0,
            'prior_year_employees': 0,
            'meets_gross_receipts_test': False,
            'meets_employee_test': False,
            'qualified': False,
            'disqualification_reason': None,
            'expenditure_details': [],
        }

        info = self.disabled_access_info
        if not info:
            return 0.0, breakdown

        breakdown['prior_year_gross_receipts'] = info.prior_year_gross_receipts
        breakdown['prior_year_employees'] = info.prior_year_full_time_employees
        breakdown['meets_gross_receipts_test'] = info.prior_year_gross_receipts <= 1000000
        breakdown['meets_employee_test'] = info.prior_year_full_time_employees <= 30

        # Check eligibility (must meet at least one test)
        if not info.is_eligible_small_business():
            breakdown['disqualification_reason'] = (
                f'Business does not qualify: gross receipts (${info.prior_year_gross_receipts:,.0f}) > $1M '
                f'AND employees ({info.prior_year_full_time_employees}) > 30'
            )
            return 0.0, breakdown

        # Get total expenditures
        total_expenditures = info.get_total_expenditures()
        breakdown['total_expenditures'] = float(money(total_expenditures))

        # Check minimum threshold
        if total_expenditures <= min_expenditure:
            breakdown['disqualification_reason'] = (
                f'Total expenditures (${total_expenditures:,.2f}) must exceed ${min_expenditure:,.2f}'
            )
            return 0.0, breakdown

        # Calculate eligible amount (between $250 and $10,250)
        eligible_amount = info.calculate_eligible_amount(min_expenditure, max_expenditure)
        breakdown['eligible_expenditures'] = float(money(eligible_amount))

        # Record itemized expenditures if available
        if info.expenditures:
            breakdown['expenditure_details'] = [
                {
                    'description': exp.description,
                    'type': exp.expenditure_type.value,
                    'amount': exp.amount,
                }
                for exp in info.expenditures
            ]

        # Calculate credit (50% of eligible expenditures)
        credit = eligible_amount * credit_rate
        breakdown['credit_amount'] = float(money(credit))
        breakdown['qualified'] = True

        return float(money(credit)), breakdown

    def calculate_eitc(self, earned_income: float, agi: float, filing_status: str, num_children: int) -> float:
        """
        Calculate Earned Income Tax Credit (EITC) for 2025
        This is a simplified calculation - actual EITC has complex phaseouts
        """
        if not self.eitc_eligible:
            return 0.0
        
        # 2025 EITC max amounts (IRS Rev. Proc. 2024-40)
        eitc_amounts = {
            "single": {
                0: 649.0,
                1: 4328.0,
                2: 7152.0,
                3: 8046.0,
            },
            "married_joint": {
                0: 649.0,
                1: 4328.0,
                2: 7152.0,
                3: 8046.0,
            },
            "head_of_household": {
                0: 649.0,
                1: 4328.0,
                2: 7152.0,
                3: 8046.0,
            }
        }
        
        num_children = min(num_children, 3)
        base_amount = eitc_amounts.get(filing_status, {}).get(num_children, 0.0)
        
        # Phaseout based on AGI (simplified - 2025 inflation-adjusted thresholds)
        phaseout_thresholds = {
            "single": {
                0: 18100.0,  # 2025 inflation-adjusted
                1: 25800.0,
                2: 25800.0,
                3: 25800.0,
            },
            "married_joint": {
                0: 25300.0,  # 2025 inflation-adjusted
                1: 33000.0,
                2: 33000.0,
                3: 33000.0,
            },
            "head_of_household": {
                0: 18100.0,  # 2025 inflation-adjusted
                1: 25800.0,
                2: 25800.0,
                3: 25800.0,
            }
        }
        
        threshold = phaseout_thresholds.get(filing_status, {}).get(num_children, 0.0)
        if agi > threshold:
            # Simplified phaseout calculation
            excess = agi - threshold
            phaseout_rate = 0.1598 if num_children == 0 else 0.2106
            reduction = excess * phaseout_rate
            base_amount = max(0.0, base_amount - reduction)
        
        return min(base_amount, earned_income * 0.4)  # Cap at 40% of earned income
    
    def calculate_child_tax_credit(self, num_children: int, agi: float, filing_status: str) -> Tuple[float, float]:
        """
        Calculate Child Tax Credit for 2025
        $2,200 per qualifying child, partially refundable
        """
        if num_children == 0:
            return 0.0, 0.0
        
        # 2025: $2,200 per child (increased from $2,000), up to $1,800 refundable
        credit_per_child = 2200.0
        refundable_per_child = 1800.0
        
        # Phaseout starts at $200,000 (single) or $400,000 (married joint) - 2025 amounts
        # Note: These thresholds are inflation-adjusted annually
        phaseout_threshold = 400000.0 if filing_status == "married_joint" else 200000.0
        
        if agi <= phaseout_threshold:
            total_credit = credit_per_child * num_children
            refundable_credit = refundable_per_child * num_children
            return total_credit, refundable_credit
        
        # Phaseout calculation
        excess = agi - phaseout_threshold
        phaseout_amount = excess * 0.05  # 5% phaseout rate
        total_credit = max(0.0, (credit_per_child * num_children) - phaseout_amount)
        refundable_credit = max(0.0, (refundable_per_child * num_children) - phaseout_amount)

        return total_credit, refundable_credit

    def calculate_aotc(
        self,
        magi: float,
        filing_status: str
    ) -> Tuple[float, float]:
        """
        Calculate American Opportunity Tax Credit for all eligible students.

        AOTC (Form 8863):
        - Up to $2,500 per eligible student
        - 100% of first $2,000 + 25% of next $2,000 of qualified expenses
        - 40% refundable (up to $1,000 per student)
        - First 4 years of post-secondary education only
        - Student must be enrolled at least half-time

        MAGI Phaseout (2025):
        - Single: $80,000 - $90,000
        - MFJ: $160,000 - $180,000

        Args:
            magi: Modified Adjusted Gross Income
            filing_status: Filing status

        Returns:
            Tuple of (nonrefundable_credit, refundable_credit)
        """
        # MFS cannot claim education credits
        if filing_status == "married_separate":
            return 0.0, 0.0

        total_nonrefundable = 0.0
        total_refundable = 0.0

        # 2025 MAGI phaseout thresholds
        if filing_status == "married_joint":
            phaseout_start = 160000.0
            phaseout_end = 180000.0
        else:
            phaseout_start = 80000.0
            phaseout_end = 90000.0

        # Calculate phaseout percentage
        if magi >= phaseout_end:
            return 0.0, 0.0

        if magi <= phaseout_start:
            phaseout_pct = 1.0
        else:
            phaseout_pct = (phaseout_end - magi) / (phaseout_end - phaseout_start)

        # Calculate credit for each eligible student
        for student in self.students:
            if not student.is_aotc_eligible():
                continue

            qualified_expenses = student.get_qualified_expenses(EducationCreditType.AOTC)
            if qualified_expenses <= 0:
                continue

            # AOTC calculation: 100% of first $2,000 + 25% of next $2,000
            if qualified_expenses <= 2000:
                credit = qualified_expenses
            else:
                credit = 2000 + (min(qualified_expenses - 2000, 2000) * 0.25)

            # Maximum $2,500 per student
            credit = min(credit, 2500)

            # Apply phaseout
            credit = credit * phaseout_pct

            # 40% is refundable (up to $1,000)
            refundable = min(credit * 0.40, 1000)
            nonrefundable = credit - refundable

            total_nonrefundable += nonrefundable
            total_refundable += refundable

        return float(money(total_nonrefundable)), float(money(total_refundable))

    def calculate_llc(
        self,
        magi: float,
        filing_status: str
    ) -> float:
        """
        Calculate Lifetime Learning Credit.

        LLC (Form 8863):
        - Up to $2,000 per tax return (20% of first $10,000 of qualified expenses)
        - Non-refundable
        - No limit on years claimed
        - No half-time enrollment requirement

        MAGI Phaseout (2025):
        - Single: $80,000 - $90,000
        - MFJ: $160,000 - $180,000

        Args:
            magi: Modified Adjusted Gross Income
            filing_status: Filing status

        Returns:
            Nonrefundable LLC amount
        """
        # MFS cannot claim education credits
        if filing_status == "married_separate":
            return 0.0

        # 2025 MAGI phaseout thresholds
        if filing_status == "married_joint":
            phaseout_start = 160000.0
            phaseout_end = 180000.0
        else:
            phaseout_start = 80000.0
            phaseout_end = 90000.0

        # Calculate phaseout percentage
        if magi >= phaseout_end:
            return 0.0

        if magi <= phaseout_start:
            phaseout_pct = 1.0
        else:
            phaseout_pct = (phaseout_end - magi) / (phaseout_end - phaseout_start)

        # Total qualified expenses across all students (for LLC)
        total_expenses = sum(
            student.get_qualified_expenses(EducationCreditType.LLC)
            for student in self.students
        )

        # LLC: 20% of first $10,000 = max $2,000
        credit = min(total_expenses, 10000) * 0.20

        # Apply phaseout
        credit = credit * phaseout_pct

        return float(money(credit))

    def calculate_best_education_credit(
        self,
        magi: float,
        filing_status: str
    ) -> Tuple[str, float, float]:
        """
        Calculate the best education credit option (AOTC vs LLC).

        You cannot claim both AOTC and LLC for the same student in the same year,
        but you can claim different credits for different students.

        For simplicity, this calculates total AOTC vs total LLC and returns
        the better option.

        Args:
            magi: Modified Adjusted Gross Income
            filing_status: Filing status

        Returns:
            Tuple of (credit_type, nonrefundable, refundable)
        """
        aotc_nonref, aotc_ref = self.calculate_aotc(magi, filing_status)
        llc = self.calculate_llc(magi, filing_status)

        total_aotc = aotc_nonref + aotc_ref
        total_llc = llc

        if total_aotc >= total_llc:
            return "AOTC", aotc_nonref, aotc_ref
        else:
            return "LLC", llc, 0.0

    def calculate_premium_tax_credit(
        self,
        household_income: float,
        family_size: int,
        filing_status: str
    ) -> Tuple[float, float, float]:
        """
        Calculate Premium Tax Credit (Form 8962).

        PTC helps eligible individuals afford health insurance through the Marketplace.
        The credit is based on household income relative to the Federal Poverty Level (FPL).

        For 2025:
        - Income must be 100% - 400% of FPL (ACA subsidy cliff temporarily suspended through 2025)
        - Applicable percentage tables determine max household contribution
        - Credit = SLCSP - (Household Income × Applicable Percentage)

        Args:
            household_income: Modified AGI for PTC purposes
            family_size: Number in tax family
            filing_status: Filing status

        Returns:
            Tuple of (total_ptc_allowed, aptc_received, net_ptc_or_repayment)
            - Positive net = additional credit
            - Negative net = repayment required
        """
        # MFS cannot claim PTC (unless victim of domestic abuse or abandonment)
        if filing_status == "married_separate":
            return 0.0, 0.0, 0.0

        if not self.marketplace_coverage:
            return 0.0, 0.0, 0.0

        # 2025 Federal Poverty Level (48 contiguous states)
        # These are updated annually by HHS
        FPL_2025 = {
            1: 15650,
            2: 21150,
            3: 26650,
            4: 32150,
            5: 37650,
            6: 43150,
            7: 48650,
            8: 54150,
        }

        # For family sizes > 8, add $5,500 per additional person
        if family_size <= 8:
            fpl = FPL_2025[family_size]
        else:
            fpl = FPL_2025[8] + (family_size - 8) * 5500

        # Calculate FPL percentage
        fpl_percentage = (household_income / fpl) * 100

        # 2025 Applicable Percentage Table (IRS Rev. Proc. 2024-XX)
        # Income as % of FPL -> Max % of income for premiums
        # Note: Under IRA, the 400% cliff is suspended through 2025
        applicable_percentages = [
            (100, 0.0),      # Up to 100% FPL - 0%
            (133, 0.0),      # 100-133% FPL - 0%
            (150, 2.0),      # 133-150% FPL - up to 2%
            (200, 4.0),      # 150-200% FPL - 2-4%
            (250, 6.0),      # 200-250% FPL - 4-6%
            (300, 8.5),      # 250-300% FPL - 6-8.5%
            (400, 8.5),      # 300-400% FPL - 8.5%
            (float('inf'), 8.5),  # Above 400% - 8.5% (IRA extension)
        ]

        # Determine applicable percentage based on FPL
        applicable_pct = 0.0
        for threshold, pct in applicable_percentages:
            if fpl_percentage <= threshold:
                applicable_pct = pct / 100  # Convert to decimal
                break

        # Calculate annual contribution amount
        annual_contribution = household_income * applicable_pct

        # Calculate PTC for each policy
        total_ptc = 0.0
        total_aptc = 0.0

        for policy in self.marketplace_coverage:
            # Apply allocation if shared policy
            alloc_pct = policy.allocation_percentage / 100

            # Calculate monthly PTC for this policy
            for month in range(12):
                if policy.monthly_premium[month] <= 0:
                    continue

                premium = policy.monthly_premium[month] * alloc_pct
                slcsp = policy.monthly_slcsp[month] * alloc_pct
                aptc = policy.monthly_aptc[month] * alloc_pct

                total_aptc += aptc

                # Monthly contribution (annual / 12)
                monthly_contribution = annual_contribution / 12

                # PTC = lesser of (SLCSP - contribution) or actual premium
                ptc_based_on_slcsp = max(0, slcsp - monthly_contribution)
                monthly_ptc = min(ptc_based_on_slcsp, premium)

                total_ptc += monthly_ptc

        # Round to whole dollars
        total_ptc = float(money(total_ptc).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        total_aptc = float(money(total_aptc).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

        # Net PTC (positive = additional credit, negative = repayment)
        net_ptc = total_ptc - total_aptc

        # Repayment limitation (caps how much APTC excess must be repaid)
        # Based on household income as % of FPL
        if net_ptc < 0:
            net_ptc = self._apply_ptc_repayment_cap(net_ptc, fpl_percentage, filing_status)

        return total_ptc, total_aptc, net_ptc

    def _apply_ptc_repayment_cap(
        self,
        net_ptc: float,
        fpl_percentage: float,
        filing_status: str
    ) -> float:
        """
        Apply repayment limitation caps on excess APTC.

        If household income exceeds 400% FPL, full repayment is required.
        Below 400% FPL, caps apply based on filing status and FPL percentage.
        """
        if fpl_percentage >= 400:
            # No cap - full repayment required
            return net_ptc

        # 2025 repayment caps (IRS Rev. Proc. 2024-XX)
        # These are indexed for inflation annually
        if filing_status == "married_joint":
            if fpl_percentage < 200:
                cap = 350
            elif fpl_percentage < 300:
                cap = 900
            else:  # 300-400%
                cap = 1500
        else:  # Single, HOH, etc.
            if fpl_percentage < 200:
                cap = 175
            elif fpl_percentage < 300:
                cap = 450
            else:  # 300-400%
                cap = 750

        # Apply cap (net_ptc is negative, so compare absolute values)
        if abs(net_ptc) > cap:
            return -cap
        return net_ptc

    def calculate_foreign_tax_credit(
        self,
        foreign_taxes_paid: float,
        foreign_source_income: float,
        total_taxable_income: float,
        total_tax_before_credits: float,
        filing_status: str
    ) -> Tuple[float, float]:
        """
        Calculate Foreign Tax Credit (Form 1116).

        The FTC prevents double taxation on income earned in foreign countries.
        You can claim either a credit or a deduction for foreign taxes paid.

        FTC Limitation Formula:
        Credit = Foreign Taxes Paid × (Foreign Source Income / Total Taxable Income)
        But limited to: Credit ≤ Total Tax × (Foreign Source Income / Total Taxable Income)

        Args:
            foreign_taxes_paid: Total foreign taxes paid or accrued
            foreign_source_income: Income from foreign sources
            total_taxable_income: Total taxable income (Line 15 Form 1040)
            total_tax_before_credits: Tax liability before credits
            filing_status: Filing status

        Returns:
            Tuple of (allowable_credit, carryforward_amount)
        """
        if foreign_taxes_paid <= 0 or foreign_source_income <= 0:
            return 0.0, 0.0

        if total_taxable_income <= 0 or total_tax_before_credits <= 0:
            # All foreign taxes carry forward
            return 0.0, foreign_taxes_paid

        # Calculate the FTC limitation
        # Limit = Total Tax × (Foreign Source Income / Total Taxable Income)
        foreign_income_ratio = min(1.0, foreign_source_income / total_taxable_income)
        ftc_limit = total_tax_before_credits * foreign_income_ratio

        # Allowable credit is lesser of taxes paid or limitation
        allowable_credit = min(foreign_taxes_paid, ftc_limit)

        # Calculate carryforward (unused FTC can be carried forward 10 years)
        carryforward = max(0, foreign_taxes_paid - allowable_credit)

        # Add any existing carryforward
        if self.foreign_tax_credit_carryforward > 0:
            additional_from_carryforward = min(
                self.foreign_tax_credit_carryforward,
                ftc_limit - allowable_credit
            )
            allowable_credit += additional_from_carryforward

        return float(money(allowable_credit)), float(money(carryforward))

    def can_use_simplified_ftc(
        self,
        foreign_taxes_paid: float,
        foreign_source_income: float,
        filing_status: str
    ) -> bool:
        """
        Check if taxpayer can use simplified FTC method (no Form 1116 required).

        Simplified method allowed if:
        1. All foreign source income is passive (dividends, interest, etc.)
        2. All foreign taxes paid are reported on qualified payee statements
           (Form 1099-DIV, 1099-INT, Schedule K-1)
        3. Total foreign taxes ≤ $300 ($600 MFJ)

        Args:
            foreign_taxes_paid: Total foreign taxes paid
            foreign_source_income: Foreign source income
            filing_status: Filing status

        Returns:
            True if simplified method can be used
        """
        threshold = 600 if filing_status == "married_joint" else 300

        if foreign_taxes_paid > threshold:
            return False

        # Simplified method requires passive income only
        # This would need additional income categorization in a full implementation
        return True

    def calculate_savers_credit(
        self,
        agi: float,
        filing_status: str,
        qualified_contributions: float,
        config: "TaxYearConfig",
    ) -> float:
        """
        Calculate Retirement Savings Contributions Credit (Saver's Credit - Form 8880).

        Per IRS Form 8880 for Tax Year 2025:
        - Credit rate (50%, 20%, or 10%) based on AGI and filing status
        - Maximum contribution basis: $2,000 per person
        - Nonrefundable credit (limited to tax liability by engine)
        - Must be 18+, not full-time student, not claimed as dependent

        2025 AGI Thresholds:
        - Single/MFS: 50% up to $23,750, 20% up to $25,500, 10% up to $39,375
        - HOH: 50% up to $35,625, 20% up to $38,250, 10% up to $59,062
        - MFJ/QW: 50% up to $47,500, 20% up to $51,000, 10% up to $78,750

        Args:
            agi: Adjusted Gross Income
            filing_status: Filing status for threshold lookup
            qualified_contributions: Total qualified retirement contributions
            config: Tax year configuration with thresholds

        Returns:
            Credit amount before tax liability limit is applied
        """
        # Check eligibility
        if not self.savers_credit_eligible:
            return 0.0

        if qualified_contributions <= 0:
            return 0.0

        # Cap contributions at $2,000 per person
        max_contribution = config.savers_credit_max_contribution
        contribution_basis = min(qualified_contributions, max_contribution)

        # Get thresholds for filing status
        limit_50 = config.savers_credit_50_pct_limit.get(filing_status, 23750.0)
        limit_20 = config.savers_credit_20_pct_limit.get(filing_status, 25500.0)
        limit_10 = config.savers_credit_10_pct_limit.get(filing_status, 39375.0)

        # Determine credit rate based on AGI
        if agi <= limit_50:
            rate = 0.50
        elif agi <= limit_20:
            rate = 0.20
        elif agi <= limit_10:
            rate = 0.10
        else:
            rate = 0.0

        return float(money(contribution_basis * rate))

    def _get_dependent_care_rate(self, agi: float) -> float:
        """
        Get Dependent Care Credit rate based on AGI (20-35%).

        Rate decreases by 1% for each $2,000 of AGI over $15,000,
        bottoming out at 20% for AGI over $43,000.
        """
        rate_schedule = [
            (15000, 0.35),
            (17000, 0.34),
            (19000, 0.33),
            (21000, 0.32),
            (23000, 0.31),
            (25000, 0.30),
            (27000, 0.29),
            (29000, 0.28),
            (31000, 0.27),
            (33000, 0.26),
            (35000, 0.25),
            (37000, 0.24),
            (39000, 0.23),
            (41000, 0.22),
            (43000, 0.21),
        ]

        for threshold, rate in rate_schedule:
            if agi <= threshold:
                return rate

        return 0.20  # Default rate for AGI > $43,000

    def calculate_dependent_care_credit(
        self,
        agi: float,
        earned_income_taxpayer: float,
        earned_income_spouse: float = 0.0,
        filing_status: str = "single",
    ) -> float:
        """
        Calculate Child and Dependent Care Credit (Form 2441).

        Per IRS Form 2441 for Tax Year 2025:
        - Credit rate 20-35% based on AGI
        - Max expenses: $3,000 (1 qualifying person), $6,000 (2+ persons)
        - Limited to lesser of taxpayer's or spouse's earned income
        - Nonrefundable (engine applies tax liability limit)

        Qualifying persons:
        - Child under age 13
        - Spouse or dependent physically/mentally incapable of self-care

        Args:
            agi: Adjusted Gross Income for rate determination
            earned_income_taxpayer: Taxpayer's earned income
            earned_income_spouse: Spouse's earned income (for MFJ)
            filing_status: Filing status

        Returns:
            Credit amount before tax liability limit is applied
        """
        # Check basic eligibility
        if self.child_care_expenses <= 0 or self.num_qualifying_persons <= 0:
            return 0.0

        # Determine expense limit based on qualifying persons
        if self.num_qualifying_persons == 1:
            expense_limit = 3000.0
        else:
            expense_limit = 6000.0

        # Apply expense limit
        qualified_expenses = min(self.child_care_expenses, expense_limit)

        # Apply earned income limit
        # For MFJ, expenses limited to lesser of taxpayer's or spouse's earned income
        if filing_status == "married_joint":
            earned_income_limit = min(earned_income_taxpayer, earned_income_spouse)
        else:
            earned_income_limit = earned_income_taxpayer

        qualified_expenses = min(qualified_expenses, earned_income_limit)

        if qualified_expenses <= 0:
            return 0.0

        # Determine credit rate based on AGI
        rate = self._get_dependent_care_rate(agi)

        return float(money(qualified_expenses * rate))

    def calculate_residential_energy_credit(
        self,
        config: "TaxYearConfig",
    ) -> tuple:
        """
        Calculate Residential Energy Credits (Form 5695).

        Returns tuple of (clean_energy_credit, home_improvement_credit).
        Both are nonrefundable (engine applies tax liability limit).

        Part I - Residential Clean Energy Credit (Section 25D):
        - 30% of solar, wind, geothermal, battery storage, fuel cell
        - No annual limit except fuel cells ($500/0.5 kW)

        Part II - Energy Efficient Home Improvement Credit (Section 25C):
        - 30% with annual limits:
          - $1,200 aggregate for most improvements
          - $600 for windows, $500 for doors, $600 for panels, $150 for audits
          - $2,000 separate limit for heat pumps/biomass

        Args:
            config: TaxYearConfig with credit rates and limits

        Returns:
            Tuple of (clean_energy_credit, home_improvement_credit)
        """
        rate = config.residential_clean_energy_rate

        # === Part I: Clean Energy Credit (no annual limit except fuel cells) ===
        clean_energy_expenses = (
            self.solar_electric_expenses +
            self.solar_water_heating_expenses +
            self.small_wind_expenses +
            self.geothermal_heat_pump_expenses +
            self.battery_storage_expenses
        )
        clean_energy_credit = clean_energy_expenses * rate

        # Fuel cell: $500 per 0.5 kW capacity
        if self.fuel_cell_expenses > 0 and self.fuel_cell_kilowatt_capacity > 0:
            fuel_cell_limit = (self.fuel_cell_kilowatt_capacity / 0.5) * config.fuel_cell_per_half_kw_limit
            fuel_cell_credit = min(self.fuel_cell_expenses * rate, fuel_cell_limit)
            clean_energy_credit += fuel_cell_credit

        # === Part II: Home Improvement Credit (with annual limits) ===
        # Subcategory limits within $1,200 aggregate
        window_credit = min(self.window_expenses * rate, config.energy_efficient_window_limit)

        # Door credit: $250 per door, max $500 total
        if self.door_count > 0:
            door_credit = min(
                self.door_expenses * rate,
                min(self.door_count * 250, config.energy_efficient_door_limit)
            )
        else:
            # If door_count not specified, just apply expense limit
            door_credit = min(self.door_expenses * rate, config.energy_efficient_door_limit)

        panel_credit = min(self.electric_panel_expenses * rate, config.energy_efficient_panel_limit)
        audit_credit = min(self.home_energy_audit_expenses * rate, config.energy_efficient_audit_limit)

        # Insulation and central A/C go toward remaining $1,200 limit
        other_improvement_credit = (self.insulation_expenses + self.central_ac_expenses) * rate

        # $1,200 aggregate limit for Part II (excluding heat pumps)
        standard_improvement_total = (
            window_credit + door_credit + panel_credit + audit_credit + other_improvement_credit
        )
        standard_improvement_credit = min(standard_improvement_total, config.energy_efficient_annual_limit)

        # Heat pump / biomass: separate $2,000 limit
        heat_pump_total = (
            self.heat_pump_expenses +
            self.heat_pump_water_heater_expenses +
            self.biomass_stove_expenses
        ) * rate
        heat_pump_credit = min(heat_pump_total, config.heat_pump_annual_limit)

        home_improvement_credit = standard_improvement_credit + heat_pump_credit

        return (float(money(clean_energy_credit)), float(money(home_improvement_credit)))
