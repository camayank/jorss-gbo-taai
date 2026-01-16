from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class FilingStatus(str, Enum):
    """IRS filing status options"""
    SINGLE = "single"
    MARRIED_JOINT = "married_joint"
    MARRIED_SEPARATE = "married_separate"
    HEAD_OF_HOUSEHOLD = "head_of_household"
    QUALIFYING_WIDOW = "qualifying_widow"


class DependentRelationship(str, Enum):
    """IRS-recognized dependent relationships for Qualifying Child/Relative tests."""
    # Qualifying Child relationships (BR-0024)
    SON = "son"
    DAUGHTER = "daughter"
    STEPSON = "stepson"
    STEPDAUGHTER = "stepdaughter"
    FOSTER_CHILD = "foster_child"
    BROTHER = "brother"
    SISTER = "sister"
    HALF_BROTHER = "half_brother"
    HALF_SISTER = "half_sister"
    STEPBROTHER = "stepbrother"
    STEPSISTER = "stepsister"
    # Descendants of above
    GRANDCHILD = "grandchild"
    NIECE = "niece"
    NEPHEW = "nephew"
    # Qualifying Relative relationships (BR3-0207)
    PARENT = "parent"
    GRANDPARENT = "grandparent"
    AUNT = "aunt"
    UNCLE = "uncle"
    IN_LAW = "in_law"
    # Non-relative (must live with taxpayer full year)
    OTHER_HOUSEHOLD_MEMBER = "other_household_member"


class Dependent(BaseModel):
    """
    Tax dependent information with full QC/QR test support.

    Implements IRS Pub. 501 and Pub. 596 dependent rules:
    - Qualifying Child (QC) 5-part test: BR-0023 to BR-0027
    - Qualifying Relative (QR) 4-part test: BR3-0206 to BR3-0209
    - Tiebreaker rules: BR3-0210 to BR3-0212
    """
    name: str
    ssn: Optional[str] = None
    relationship: str  # Kept as string for backwards compatibility
    relationship_type: Optional[DependentRelationship] = None
    date_of_birth: Optional[str] = None  # YYYY-MM-DD format
    age: int

    # Qualifying Child Test Fields (BR-0023 to BR-0027)
    is_student: bool = Field(default=False, description="Full-time student for 5+ months")
    is_permanently_disabled: bool = Field(default=False, description="Permanently and totally disabled")
    months_lived_with_taxpayer: int = Field(default=12, ge=0, le=12, description="Months lived with taxpayer in tax year")
    provided_own_support_percentage: float = Field(default=0.0, ge=0, le=100, description="Percentage of own support provided")
    filed_joint_return: bool = Field(default=False, description="Filed joint return with spouse")
    joint_return_only_for_refund: bool = Field(default=False, description="Joint return filed only to claim refund")

    # Qualifying Relative Test Fields (BR3-0206 to BR3-0209)
    gross_income: float = Field(default=0.0, ge=0, description="Dependent's gross income for the year")
    taxpayer_provided_support_percentage: float = Field(default=100.0, ge=0, le=100, description="% of support taxpayer provided")
    is_claimed_by_another: bool = Field(default=False, description="Can be claimed as QC by another taxpayer")

    # Citizenship/Residency (required for all dependents)
    is_us_citizen: bool = Field(default=True, description="US citizen or resident alien")
    is_us_resident: bool = Field(default=True, description="US, Canada, or Mexico resident")

    # For tiebreaker rules (BR3-0210 to BR3-0212)
    is_parent_of_child: bool = Field(default=False, description="Taxpayer is parent of this dependent")
    other_claimant_agi: Optional[float] = Field(default=None, description="AGI of other person claiming this dependent")
    other_claimant_is_parent: bool = Field(default=False, description="Other claimant is parent of this dependent")

    # Legacy compatibility
    is_disabled: bool = False  # Deprecated: use is_permanently_disabled
    lives_with_you: bool = True  # Deprecated: use months_lived_with_taxpayer

    # Form 8332 Release (BR3-0213)
    has_form_8332_release: bool = Field(default=False, description="Custodial parent released claim via Form 8332")
    form_8332_years: Optional[List[int]] = Field(default=None, description="Tax years covered by Form 8332")


class TaxpayerInfo(BaseModel):
    """Primary taxpayer information"""
    first_name: str
    last_name: str
    ssn: Optional[str] = Field(None, description="Social Security Number (stored securely)")
    date_of_birth: Optional[str] = None
    filing_status: FilingStatus
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    dependents: List[Dependent] = Field(default_factory=list)
    is_blind: bool = False
    is_over_65: bool = False
    
    # Spouse information (if applicable)
    spouse_first_name: Optional[str] = None
    spouse_last_name: Optional[str] = None
    spouse_ssn: Optional[str] = None
    spouse_date_of_birth: Optional[str] = None
    spouse_is_blind: bool = False
    spouse_is_over_65: bool = False

    # Special status flags (BR2-0002, BR2-0003, BR2-0004)
    spouse_itemizes_deductions: bool = Field(
        default=False,
        description="For MFS: if True, taxpayer's standard deduction is $0 (BR2-0002)"
    )
    is_dual_status_alien: bool = Field(
        default=False,
        description="If True, standard deduction is $0 (BR2-0003)"
    )
    can_be_claimed_as_dependent: bool = Field(
        default=False,
        description="If True, use dependent standard deduction formula (BR2-0004)"
    )
    earned_income_for_dependent_deduction: float = Field(
        default=0.0,
        ge=0,
        description="Earned income used to calculate dependent's standard deduction"
    )

    # IRA deduction eligibility (BR2-0009, BR2-0010)
    is_covered_by_employer_plan: bool = Field(
        default=False,
        description="Taxpayer is covered by employer retirement plan (affects Traditional IRA deduction)"
    )
    spouse_covered_by_employer_plan: bool = Field(
        default=False,
        description="Spouse is covered by employer retirement plan (affects IRA deduction for non-covered taxpayer)"
    )
    is_age_50_plus: bool = Field(
        default=False,
        description="Taxpayer is age 50 or older (eligible for IRA catchup contribution)"
    )

    @field_validator('filing_status', mode='before')
    def validate_filing_status(cls, v):
        if isinstance(v, str):
            v = v.lower().replace(' ', '_')
        return v
    
    def get_total_exemptions(self) -> int:
        """Calculate total exemptions (taxpayer + spouse + dependents)"""
        exemptions = 1  # Taxpayer
        if self.filing_status in [FilingStatus.MARRIED_JOINT, FilingStatus.MARRIED_SEPARATE]:
            exemptions += 1  # Spouse
        exemptions += len(self.dependents)
        return exemptions
