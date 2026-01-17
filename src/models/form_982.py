"""
Form 982 - Reduction of Tax Attributes Due to Discharge of Indebtedness

Complete IRS Form 982 implementation for cancellation of debt (COD) income exclusion:

Key concepts:
- Cancellation of debt (COD) income is generally taxable
- IRC Section 108 provides exclusions from gross income
- Excluded COD requires reduction of tax attributes

Exclusion Types (IRC Section 108):
1. Bankruptcy (Title 11 case) - Full exclusion
2. Insolvency - Limited to extent of insolvency
3. Qualified farm indebtedness - Special rules for farmers
4. Qualified real property business indebtedness (QRPBI)
5. Qualified principal residence indebtedness (expired for most, extended for some)

Tax Attribute Reduction Order (IRC Section 108(b)):
1. Net operating losses (NOLs)
2. General business credits
3. Minimum tax credits
4. Capital loss carryovers
5. Basis of property (Section 1017)
6. Passive activity loss carryovers
7. Foreign tax credit carryovers

Section 1017 Basis Reduction:
- Reduce basis of property when COD excluded
- Can elect to reduce depreciable property basis first
- Cannot reduce below liabilities secured by property

Insolvency Calculation:
- Insolvent = Liabilities exceed FMV of assets
- Exclusion limited to amount of insolvency
- Must calculate immediately before discharge
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, computed_field, model_validator
from datetime import date
from decimal import Decimal, ROUND_HALF_UP


class ExclusionType(str, Enum):
    """Types of COD income exclusions under IRC Section 108."""
    BANKRUPTCY = "bankruptcy"  # Title 11 case
    INSOLVENCY = "insolvency"  # Liabilities exceed assets
    QUALIFIED_FARM = "qualified_farm"  # Qualified farm indebtedness
    QUALIFIED_REAL_PROPERTY = "qualified_real_property"  # QRPBI
    QUALIFIED_PRINCIPAL_RESIDENCE = "qualified_principal_residence"  # QPRI
    NONE = "none"  # No exclusion (COD is taxable)


class DebtType(str, Enum):
    """Types of discharged debt."""
    CREDIT_CARD = "credit_card"
    MORTGAGE = "mortgage"
    AUTO_LOAN = "auto_loan"
    STUDENT_LOAN = "student_loan"
    BUSINESS_LOAN = "business_loan"
    MEDICAL_DEBT = "medical_debt"
    PERSONAL_LOAN = "personal_loan"
    FARM_DEBT = "farm_debt"
    REAL_PROPERTY_BUSINESS = "real_property_business"
    OTHER = "other"


class TaxAttributeType(str, Enum):
    """Tax attributes that can be reduced under Section 108(b)."""
    NOL = "nol"  # Net Operating Loss
    GENERAL_BUSINESS_CREDIT = "general_business_credit"
    MINIMUM_TAX_CREDIT = "minimum_tax_credit"
    CAPITAL_LOSS_CARRYOVER = "capital_loss_carryover"
    BASIS_REDUCTION = "basis_reduction"  # Section 1017
    PASSIVE_ACTIVITY_LOSS = "passive_activity_loss"
    PASSIVE_ACTIVITY_CREDIT = "passive_activity_credit"
    FOREIGN_TAX_CREDIT = "foreign_tax_credit"


class DischargedDebt(BaseModel):
    """Information about a specific discharged debt."""
    creditor_name: str = Field(description="Name of creditor")
    debt_type: DebtType = Field(default=DebtType.OTHER, description="Type of debt")
    original_amount: float = Field(default=0.0, ge=0, description="Original debt amount")
    amount_discharged: float = Field(default=0.0, ge=0, description="Amount discharged/cancelled")
    date_discharged: Optional[date] = Field(None, description="Date of discharge")
    form_1099c_received: bool = Field(default=False, description="Form 1099-C received")

    # For secured debts
    is_recourse: bool = Field(default=True, description="Is this recourse debt?")
    is_secured: bool = Field(default=False, description="Is debt secured by property?")
    secured_property_fmv: float = Field(default=0.0, ge=0, description="FMV of securing property")
    secured_property_basis: float = Field(default=0.0, ge=0, description="Basis of securing property")

    @computed_field
    @property
    def cod_income(self) -> float:
        """Cancellation of debt income amount."""
        return self.amount_discharged


class InsolvencyCalculation(BaseModel):
    """
    Insolvency calculation for IRC Section 108(a)(1)(B).

    Taxpayer is insolvent if total liabilities exceed total FMV of assets.
    Exclusion is limited to the extent of insolvency.
    """
    # Assets at FMV immediately before discharge
    cash_and_bank_accounts: float = Field(default=0.0, ge=0)
    real_estate_fmv: float = Field(default=0.0, ge=0)
    vehicles_fmv: float = Field(default=0.0, ge=0)
    retirement_accounts: float = Field(default=0.0, ge=0)
    stocks_and_investments: float = Field(default=0.0, ge=0)
    personal_property_fmv: float = Field(default=0.0, ge=0)
    business_assets_fmv: float = Field(default=0.0, ge=0)
    other_assets_fmv: float = Field(default=0.0, ge=0)

    # Liabilities immediately before discharge
    mortgage_debt: float = Field(default=0.0, ge=0)
    credit_card_debt: float = Field(default=0.0, ge=0)
    auto_loans: float = Field(default=0.0, ge=0)
    student_loans: float = Field(default=0.0, ge=0)
    medical_debt: float = Field(default=0.0, ge=0)
    business_liabilities: float = Field(default=0.0, ge=0)
    tax_debt: float = Field(default=0.0, ge=0)
    other_liabilities: float = Field(default=0.0, ge=0)

    @computed_field
    @property
    def total_assets(self) -> float:
        """Total FMV of all assets."""
        return (
            self.cash_and_bank_accounts +
            self.real_estate_fmv +
            self.vehicles_fmv +
            self.retirement_accounts +
            self.stocks_and_investments +
            self.personal_property_fmv +
            self.business_assets_fmv +
            self.other_assets_fmv
        )

    @computed_field
    @property
    def total_liabilities(self) -> float:
        """Total liabilities."""
        return (
            self.mortgage_debt +
            self.credit_card_debt +
            self.auto_loans +
            self.student_loans +
            self.medical_debt +
            self.business_liabilities +
            self.tax_debt +
            self.other_liabilities
        )

    @computed_field
    @property
    def is_insolvent(self) -> bool:
        """Check if taxpayer is insolvent."""
        return self.total_liabilities > self.total_assets

    @computed_field
    @property
    def insolvency_amount(self) -> float:
        """Amount by which taxpayer is insolvent."""
        if not self.is_insolvent:
            return 0.0
        return self.total_liabilities - self.total_assets

    @computed_field
    @property
    def net_worth(self) -> float:
        """Net worth (can be negative if insolvent)."""
        return self.total_assets - self.total_liabilities


class TaxAttributeReduction(BaseModel):
    """
    Tax attribute reduction under IRC Section 108(b).

    When COD income is excluded, tax attributes must be reduced
    in a specific order, dollar-for-dollar (or 1/3 for credits).
    """
    attribute_type: TaxAttributeType = Field(description="Type of tax attribute")
    beginning_balance: float = Field(default=0.0, ge=0, description="Balance before reduction")
    reduction_amount: float = Field(default=0.0, ge=0, description="Amount of reduction")

    @computed_field
    @property
    def ending_balance(self) -> float:
        """Balance after reduction."""
        return max(0, self.beginning_balance - self.reduction_amount)

    @computed_field
    @property
    def is_credit(self) -> bool:
        """Check if this is a credit (reduces at 1/3 rate)."""
        return self.attribute_type in [
            TaxAttributeType.GENERAL_BUSINESS_CREDIT,
            TaxAttributeType.MINIMUM_TAX_CREDIT,
            TaxAttributeType.PASSIVE_ACTIVITY_CREDIT,
            TaxAttributeType.FOREIGN_TAX_CREDIT
        ]


class BasisReduction(BaseModel):
    """
    Section 1017 basis reduction for excluded COD income.

    Can reduce basis of:
    - Property held at beginning of tax year following discharge
    - Property acquired during year if from same creditor
    """
    property_description: str = Field(default="", description="Description of property")
    property_type: str = Field(default="", description="Type of property")
    is_depreciable: bool = Field(default=False, description="Is property depreciable?")

    original_basis: float = Field(default=0.0, ge=0, description="Original basis")
    accumulated_depreciation: float = Field(default=0.0, ge=0, description="Accumulated depreciation")
    liabilities_secured: float = Field(default=0.0, ge=0, description="Liabilities secured by property")

    reduction_amount: float = Field(default=0.0, ge=0, description="Basis reduction amount")

    @computed_field
    @property
    def adjusted_basis_before(self) -> float:
        """Adjusted basis before reduction."""
        return self.original_basis - self.accumulated_depreciation

    @computed_field
    @property
    def minimum_basis(self) -> float:
        """
        Minimum basis after reduction.

        Cannot reduce below aggregate liabilities secured by property
        immediately after discharge (Section 1017(b)(2)).
        """
        return self.liabilities_secured

    @computed_field
    @property
    def maximum_reduction(self) -> float:
        """Maximum allowable reduction."""
        return max(0, self.adjusted_basis_before - self.minimum_basis)

    @computed_field
    @property
    def actual_reduction(self) -> float:
        """Actual reduction (limited by maximum)."""
        return min(self.reduction_amount, self.maximum_reduction)

    @computed_field
    @property
    def adjusted_basis_after(self) -> float:
        """Adjusted basis after reduction."""
        return self.adjusted_basis_before - self.actual_reduction


class Form982PartI(BaseModel):
    """
    Form 982 Part I - General Information

    Identify the type of discharge and exclusion being claimed.
    """
    # Line 1a - Discharge in Title 11 case (bankruptcy)
    line_1a_bankruptcy: bool = Field(
        default=False,
        description="Discharge of indebtedness in a Title 11 case"
    )

    # Line 1b - Discharge when insolvent
    line_1b_insolvency: bool = Field(
        default=False,
        description="Discharge of indebtedness to extent insolvent (not in Title 11 case)"
    )

    # Line 1c - Qualified farm indebtedness
    line_1c_qualified_farm: bool = Field(
        default=False,
        description="Discharge of qualified farm indebtedness"
    )

    # Line 1d - Qualified real property business indebtedness
    line_1d_qrpbi: bool = Field(
        default=False,
        description="Discharge of qualified real property business indebtedness"
    )

    # Line 1e - Qualified principal residence indebtedness
    line_1e_qpri: bool = Field(
        default=False,
        description="Discharge of qualified principal residence indebtedness"
    )

    # Line 2 - Total amount excluded
    line_2_excluded_amount: float = Field(
        default=0.0, ge=0,
        description="Total amount of discharged indebtedness excluded from gross income"
    )

    @computed_field
    @property
    def exclusion_type(self) -> ExclusionType:
        """Determine the exclusion type based on checkboxes."""
        if self.line_1a_bankruptcy:
            return ExclusionType.BANKRUPTCY
        if self.line_1b_insolvency:
            return ExclusionType.INSOLVENCY
        if self.line_1c_qualified_farm:
            return ExclusionType.QUALIFIED_FARM
        if self.line_1d_qrpbi:
            return ExclusionType.QUALIFIED_REAL_PROPERTY
        if self.line_1e_qpri:
            return ExclusionType.QUALIFIED_PRINCIPAL_RESIDENCE
        return ExclusionType.NONE

    @computed_field
    @property
    def requires_attribute_reduction(self) -> bool:
        """Check if exclusion requires tax attribute reduction."""
        # QPRI (line 1e) reduces basis only, not other attributes
        if self.line_1e_qpri:
            return False
        return self.line_2_excluded_amount > 0


class Form982PartII(BaseModel):
    """
    Form 982 Part II - Reduction of Tax Attributes

    Report the reduction of tax attributes due to excluded COD income.
    Attributes are reduced in the order specified in IRC Section 108(b).
    """
    # Line 3 - NOL reduction
    line_3_nol_reduction: float = Field(
        default=0.0, ge=0,
        description="Reduction of net operating loss"
    )

    # Line 4 - General business credit reduction
    line_4_general_business_credit: float = Field(
        default=0.0, ge=0,
        description="Reduction of general business credit carryover"
    )

    # Line 5 - Minimum tax credit reduction
    line_5_minimum_tax_credit: float = Field(
        default=0.0, ge=0,
        description="Reduction of minimum tax credit"
    )

    # Line 6 - Net capital loss reduction
    line_6_capital_loss: float = Field(
        default=0.0, ge=0,
        description="Reduction of net capital loss"
    )

    # Line 7 - Basis reduction (Section 1017)
    line_7_basis_reduction: float = Field(
        default=0.0, ge=0,
        description="Reduction of basis"
    )

    # Line 8 - Passive activity loss carryover reduction
    line_8_passive_loss: float = Field(
        default=0.0, ge=0,
        description="Reduction of passive activity loss carryover"
    )

    # Line 9 - Passive activity credit carryover reduction
    line_9_passive_credit: float = Field(
        default=0.0, ge=0,
        description="Reduction of passive activity credit carryover"
    )

    # Line 10 - Foreign tax credit carryover reduction
    line_10_foreign_tax_credit: float = Field(
        default=0.0, ge=0,
        description="Reduction of foreign tax credit carryover"
    )

    @computed_field
    @property
    def total_attribute_reduction(self) -> float:
        """Total reduction of all tax attributes."""
        # Credits reduce COD at 1/3 rate, so multiply credits by 3
        loss_reductions = (
            self.line_3_nol_reduction +
            self.line_6_capital_loss +
            self.line_7_basis_reduction +
            self.line_8_passive_loss
        )
        credit_reductions = (
            self.line_4_general_business_credit +
            self.line_5_minimum_tax_credit +
            self.line_9_passive_credit +
            self.line_10_foreign_tax_credit
        ) * 3  # Credits reduce at 1/3 rate

        return loss_reductions + credit_reductions


class Form982PartIII(BaseModel):
    """
    Form 982 Part III - Consent to Adjust Basis of Property Under Section 1082(a)(2)

    For corporate acquisitions involving stock-for-debt exchanges.
    (Less commonly used section)
    """
    consent_given: bool = Field(
        default=False,
        description="Consent to basis adjustment under Section 1082(a)(2)"
    )

    # Property descriptions and adjustments would go here
    property_adjustments: List[BasisReduction] = Field(
        default_factory=list,
        description="List of property basis adjustments"
    )


class Form982(BaseModel):
    """
    IRS Form 982 - Reduction of Tax Attributes Due to Discharge of Indebtedness

    Used when cancellation of debt income can be excluded from gross income.

    Usage:
        # Insolvency exclusion
        form = Form982(
            tax_year=2025,
            total_cod_income=50000,
            exclusion_type=ExclusionType.INSOLVENCY,
            insolvency_calculation=InsolvencyCalculation(
                total_assets=100000,
                total_liabilities=130000
            )
        )

        print(f"Excluded amount: ${form.excluded_amount}")
        print(f"Taxable COD: ${form.taxable_cod_income}")
    """
    tax_year: int = Field(default=2025, description="Tax year")

    # Total COD income
    total_cod_income: float = Field(
        default=0.0, ge=0,
        description="Total cancellation of debt income"
    )

    # Exclusion type
    exclusion_type: ExclusionType = Field(
        default=ExclusionType.NONE,
        description="Type of exclusion claimed"
    )

    # Insolvency calculation (required for insolvency exclusion)
    insolvency_calculation: Optional[InsolvencyCalculation] = Field(
        None,
        description="Insolvency calculation worksheet"
    )

    # Discharged debts
    discharged_debts: List[DischargedDebt] = Field(
        default_factory=list,
        description="List of discharged debts"
    )

    # Form sections
    part_i: Optional[Form982PartI] = Field(
        None,
        description="Part I - General Information"
    )

    part_ii: Optional[Form982PartII] = Field(
        None,
        description="Part II - Reduction of Tax Attributes"
    )

    part_iii: Optional[Form982PartIII] = Field(
        None,
        description="Part III - Consent to Adjust Basis"
    )

    # Tax attributes available for reduction
    nol_carryover: float = Field(default=0.0, ge=0, description="NOL carryover available")
    general_business_credit: float = Field(default=0.0, ge=0, description="General business credit available")
    minimum_tax_credit: float = Field(default=0.0, ge=0, description="Minimum tax credit available")
    capital_loss_carryover: float = Field(default=0.0, ge=0, description="Capital loss carryover available")
    passive_activity_loss: float = Field(default=0.0, ge=0, description="Passive activity loss carryover")
    passive_activity_credit: float = Field(default=0.0, ge=0, description="Passive activity credit carryover")
    foreign_tax_credit: float = Field(default=0.0, ge=0, description="Foreign tax credit carryover")

    # Basis of property for Section 1017 reduction
    property_basis_available: float = Field(
        default=0.0, ge=0,
        description="Total basis of property available for reduction"
    )

    # Elections
    elect_reduce_depreciable_first: bool = Field(
        default=False,
        description="Elect to reduce depreciable property basis first (Section 1017(b)(3)(C))"
    )

    # QRPBI specific
    qrpbi_property_basis: float = Field(
        default=0.0, ge=0,
        description="Basis of qualified real property business property"
    )

    @computed_field
    @property
    def is_bankruptcy(self) -> bool:
        """Check if exclusion is for bankruptcy."""
        return self.exclusion_type == ExclusionType.BANKRUPTCY

    @computed_field
    @property
    def is_insolvency(self) -> bool:
        """Check if exclusion is for insolvency."""
        return self.exclusion_type == ExclusionType.INSOLVENCY

    @computed_field
    @property
    def is_qualified_farm(self) -> bool:
        """Check if exclusion is for qualified farm indebtedness."""
        return self.exclusion_type == ExclusionType.QUALIFIED_FARM

    @computed_field
    @property
    def is_qrpbi(self) -> bool:
        """Check if exclusion is for qualified real property business indebtedness."""
        return self.exclusion_type == ExclusionType.QUALIFIED_REAL_PROPERTY

    @computed_field
    @property
    def is_qpri(self) -> bool:
        """Check if exclusion is for qualified principal residence indebtedness."""
        return self.exclusion_type == ExclusionType.QUALIFIED_PRINCIPAL_RESIDENCE

    @computed_field
    @property
    def insolvency_limit(self) -> float:
        """Maximum exclusion under insolvency rule."""
        if not self.is_insolvency:
            return float('inf')
        if not self.insolvency_calculation:
            return 0.0
        return self.insolvency_calculation.insolvency_amount

    @computed_field
    @property
    def qrpbi_limit(self) -> float:
        """Maximum exclusion under QRPBI rule (limited to basis)."""
        if not self.is_qrpbi:
            return float('inf')
        return self.qrpbi_property_basis

    @computed_field
    @property
    def maximum_exclusion(self) -> float:
        """Maximum allowable exclusion based on exclusion type."""
        if self.exclusion_type == ExclusionType.NONE:
            return 0.0

        if self.is_bankruptcy:
            # Bankruptcy: full exclusion
            return self.total_cod_income

        if self.is_insolvency:
            # Insolvency: limited to insolvency amount
            return min(self.total_cod_income, self.insolvency_limit)

        if self.is_qrpbi:
            # QRPBI: limited to aggregate basis of depreciable real property
            return min(self.total_cod_income, self.qrpbi_limit)

        if self.is_qualified_farm:
            # Qualified farm: special rules (simplified here)
            return self.total_cod_income

        if self.is_qpri:
            # QPRI: up to $750,000 for debt discharged through 2025
            return min(self.total_cod_income, 750000)

        return 0.0

    @computed_field
    @property
    def excluded_amount(self) -> float:
        """Amount actually excluded from gross income."""
        return min(self.total_cod_income, self.maximum_exclusion)

    @computed_field
    @property
    def taxable_cod_income(self) -> float:
        """COD income that remains taxable after exclusion."""
        return max(0, self.total_cod_income - self.excluded_amount)

    @computed_field
    @property
    def attribute_reduction_required(self) -> float:
        """
        Amount of tax attribute reduction required.

        Generally equals excluded amount, but:
        - QPRI reduces basis only (not other attributes)
        - Credits reduce at 1/3 rate
        """
        if self.is_qpri:
            return 0.0  # QPRI reduces basis only
        return self.excluded_amount

    def calculate_attribute_reductions(self) -> List[TaxAttributeReduction]:
        """
        Calculate tax attribute reductions in required order.

        Order under IRC Section 108(b)(2):
        1. NOL (current and carryovers)
        2. General business credit
        3. Minimum tax credit
        4. Capital loss (current and carryovers)
        5. Basis of property (Section 1017)
        6. Passive activity loss carryover
        7. Passive activity credit carryover
        8. Foreign tax credit carryover
        """
        reductions = []
        remaining = self.attribute_reduction_required

        # 1. NOL reduction
        if remaining > 0 and self.nol_carryover > 0:
            reduction = min(remaining, self.nol_carryover)
            reductions.append(TaxAttributeReduction(
                attribute_type=TaxAttributeType.NOL,
                beginning_balance=self.nol_carryover,
                reduction_amount=reduction
            ))
            remaining -= reduction

        # 2. General business credit (reduces at 1/3 rate)
        if remaining > 0 and self.general_business_credit > 0:
            # $1 of credit reduces $3 of COD
            credit_reduction = min(self.general_business_credit, remaining / 3)
            reductions.append(TaxAttributeReduction(
                attribute_type=TaxAttributeType.GENERAL_BUSINESS_CREDIT,
                beginning_balance=self.general_business_credit,
                reduction_amount=credit_reduction
            ))
            remaining -= credit_reduction * 3

        # 3. Minimum tax credit (reduces at 1/3 rate)
        if remaining > 0 and self.minimum_tax_credit > 0:
            credit_reduction = min(self.minimum_tax_credit, remaining / 3)
            reductions.append(TaxAttributeReduction(
                attribute_type=TaxAttributeType.MINIMUM_TAX_CREDIT,
                beginning_balance=self.minimum_tax_credit,
                reduction_amount=credit_reduction
            ))
            remaining -= credit_reduction * 3

        # 4. Capital loss carryover
        if remaining > 0 and self.capital_loss_carryover > 0:
            reduction = min(remaining, self.capital_loss_carryover)
            reductions.append(TaxAttributeReduction(
                attribute_type=TaxAttributeType.CAPITAL_LOSS_CARRYOVER,
                beginning_balance=self.capital_loss_carryover,
                reduction_amount=reduction
            ))
            remaining -= reduction

        # 5. Basis reduction (Section 1017)
        if remaining > 0 and self.property_basis_available > 0:
            reduction = min(remaining, self.property_basis_available)
            reductions.append(TaxAttributeReduction(
                attribute_type=TaxAttributeType.BASIS_REDUCTION,
                beginning_balance=self.property_basis_available,
                reduction_amount=reduction
            ))
            remaining -= reduction

        # 6. Passive activity loss carryover
        if remaining > 0 and self.passive_activity_loss > 0:
            reduction = min(remaining, self.passive_activity_loss)
            reductions.append(TaxAttributeReduction(
                attribute_type=TaxAttributeType.PASSIVE_ACTIVITY_LOSS,
                beginning_balance=self.passive_activity_loss,
                reduction_amount=reduction
            ))
            remaining -= reduction

        # 7. Passive activity credit (reduces at 1/3 rate)
        if remaining > 0 and self.passive_activity_credit > 0:
            credit_reduction = min(self.passive_activity_credit, remaining / 3)
            reductions.append(TaxAttributeReduction(
                attribute_type=TaxAttributeType.PASSIVE_ACTIVITY_CREDIT,
                beginning_balance=self.passive_activity_credit,
                reduction_amount=credit_reduction
            ))
            remaining -= credit_reduction * 3

        # 8. Foreign tax credit (reduces at 1/3 rate)
        if remaining > 0 and self.foreign_tax_credit > 0:
            credit_reduction = min(self.foreign_tax_credit, remaining / 3)
            reductions.append(TaxAttributeReduction(
                attribute_type=TaxAttributeType.FOREIGN_TAX_CREDIT,
                beginning_balance=self.foreign_tax_credit,
                reduction_amount=credit_reduction
            ))
            remaining -= credit_reduction * 3

        return reductions

    def get_part_i(self) -> Form982PartI:
        """Generate Part I of Form 982."""
        return Form982PartI(
            line_1a_bankruptcy=self.is_bankruptcy,
            line_1b_insolvency=self.is_insolvency,
            line_1c_qualified_farm=self.is_qualified_farm,
            line_1d_qrpbi=self.is_qrpbi,
            line_1e_qpri=self.is_qpri,
            line_2_excluded_amount=self.excluded_amount
        )

    def get_part_ii(self) -> Form982PartII:
        """Generate Part II of Form 982 based on calculated reductions."""
        reductions = self.calculate_attribute_reductions()

        part_ii = Form982PartII()
        for reduction in reductions:
            if reduction.attribute_type == TaxAttributeType.NOL:
                part_ii.line_3_nol_reduction = reduction.reduction_amount
            elif reduction.attribute_type == TaxAttributeType.GENERAL_BUSINESS_CREDIT:
                part_ii.line_4_general_business_credit = reduction.reduction_amount
            elif reduction.attribute_type == TaxAttributeType.MINIMUM_TAX_CREDIT:
                part_ii.line_5_minimum_tax_credit = reduction.reduction_amount
            elif reduction.attribute_type == TaxAttributeType.CAPITAL_LOSS_CARRYOVER:
                part_ii.line_6_capital_loss = reduction.reduction_amount
            elif reduction.attribute_type == TaxAttributeType.BASIS_REDUCTION:
                part_ii.line_7_basis_reduction = reduction.reduction_amount
            elif reduction.attribute_type == TaxAttributeType.PASSIVE_ACTIVITY_LOSS:
                part_ii.line_8_passive_loss = reduction.reduction_amount
            elif reduction.attribute_type == TaxAttributeType.PASSIVE_ACTIVITY_CREDIT:
                part_ii.line_9_passive_credit = reduction.reduction_amount
            elif reduction.attribute_type == TaxAttributeType.FOREIGN_TAX_CREDIT:
                part_ii.line_10_foreign_tax_credit = reduction.reduction_amount

        return part_ii

    def to_dict(self) -> Dict[str, Any]:
        """Convert form to dictionary for reporting."""
        return {
            "tax_year": self.tax_year,
            "total_cod_income": self.total_cod_income,
            "exclusion_type": self.exclusion_type.value,

            "maximum_exclusion": self.maximum_exclusion,
            "excluded_amount": self.excluded_amount,
            "taxable_cod_income": self.taxable_cod_income,

            "is_bankruptcy": self.is_bankruptcy,
            "is_insolvency": self.is_insolvency,
            "is_qualified_farm": self.is_qualified_farm,
            "is_qrpbi": self.is_qrpbi,
            "is_qpri": self.is_qpri,

            "insolvency_amount": self.insolvency_calculation.insolvency_amount if self.insolvency_calculation else None,

            "attribute_reduction_required": self.attribute_reduction_required,
            "attribute_reductions": [
                {
                    "type": r.attribute_type.value,
                    "beginning": r.beginning_balance,
                    "reduction": r.reduction_amount,
                    "ending": r.ending_balance
                }
                for r in self.calculate_attribute_reductions()
            ]
        }

    def to_form_1040(self) -> Dict[str, float]:
        """Generate adjustments for Form 1040."""
        return {
            "excluded_cod_income": self.excluded_amount,
            "taxable_cod_income": self.taxable_cod_income,
            "other_income_cod": self.taxable_cod_income
        }


def calculate_insolvency(
    total_assets: float,
    total_liabilities: float,
    cod_income: float
) -> Dict[str, Any]:
    """
    Quick insolvency calculation.

    Args:
        total_assets: Total FMV of assets before discharge
        total_liabilities: Total liabilities before discharge
        cod_income: Amount of debt cancelled

    Returns:
        Dictionary with insolvency analysis
    """
    insolvency = InsolvencyCalculation(
        other_assets_fmv=total_assets,
        other_liabilities=total_liabilities
    )

    form = Form982(
        total_cod_income=cod_income,
        exclusion_type=ExclusionType.INSOLVENCY,
        insolvency_calculation=insolvency
    )

    return {
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "is_insolvent": insolvency.is_insolvent,
        "insolvency_amount": insolvency.insolvency_amount,
        "cod_income": cod_income,
        "excluded_amount": form.excluded_amount,
        "taxable_cod": form.taxable_cod_income
    }


def calculate_bankruptcy_exclusion(
    cod_income: float,
    nol_carryover: float = 0.0,
    capital_loss_carryover: float = 0.0,
    property_basis: float = 0.0
) -> Dict[str, Any]:
    """
    Calculate exclusion and attribute reductions for bankruptcy.

    Args:
        cod_income: Total COD income
        nol_carryover: Available NOL carryover
        capital_loss_carryover: Available capital loss carryover
        property_basis: Available property basis for reduction

    Returns:
        Dictionary with exclusion and reduction details
    """
    form = Form982(
        total_cod_income=cod_income,
        exclusion_type=ExclusionType.BANKRUPTCY,
        nol_carryover=nol_carryover,
        capital_loss_carryover=capital_loss_carryover,
        property_basis_available=property_basis
    )

    return form.to_dict()


def calculate_qpri_exclusion(
    cod_income: float,
    principal_residence_basis: float
) -> Dict[str, Any]:
    """
    Calculate qualified principal residence indebtedness exclusion.

    Args:
        cod_income: Mortgage debt forgiven
        principal_residence_basis: Basis of principal residence

    Returns:
        Dictionary with exclusion details
    """
    form = Form982(
        total_cod_income=cod_income,
        exclusion_type=ExclusionType.QUALIFIED_PRINCIPAL_RESIDENCE,
        property_basis_available=principal_residence_basis
    )

    return {
        "cod_income": cod_income,
        "maximum_exclusion": min(cod_income, 750000),
        "excluded_amount": form.excluded_amount,
        "taxable_cod": form.taxable_cod_income,
        "basis_reduction": min(form.excluded_amount, principal_residence_basis),
        "new_basis": max(0, principal_residence_basis - form.excluded_amount)
    }
