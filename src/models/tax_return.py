from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from .taxpayer import TaxpayerInfo
from .income import Income
from .deductions import Deductions
from .credits import TaxCredits


class TaxReturn(BaseModel):
    """Complete tax return information"""
    tax_year: int = 2025
    taxpayer: TaxpayerInfo
    income: Income
    deductions: Deductions
    credits: TaxCredits

    # Calculated federal values
    adjusted_gross_income: Optional[float] = None
    taxable_income: Optional[float] = None
    tax_liability: Optional[float] = None
    total_credits: Optional[float] = None
    total_payments: Optional[float] = None
    refund_or_owed: Optional[float] = None

    # State tax fields
    state_of_residence: Optional[str] = Field(
        default=None,
        description="Two-letter state code for primary residence"
    )
    state_tax_result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="State tax calculation breakdown"
    )
    state_tax_liability: Optional[float] = Field(
        default=None,
        description="State income tax liability"
    )
    state_refund_or_owed: Optional[float] = Field(
        default=None,
        description="State refund or amount owed"
    )

    # Combined federal + state totals
    combined_tax_liability: Optional[float] = Field(
        default=None,
        description="Total federal + state tax liability"
    )
    combined_refund_or_owed: Optional[float] = Field(
        default=None,
        description="Total federal + state refund or amount owed"
    )
    
    def calculate(self):
        """Perform all tax calculations"""
        # Calculate AGI
        total_income = self.income.get_total_income()
        adjustments = self.deductions.get_total_adjustments()
        self.adjusted_gross_income = total_income - adjustments
        
        # Calculate taxable income
        agi = self.adjusted_gross_income
        is_over_65 = self.taxpayer.is_over_65
        is_blind = self.taxpayer.is_blind

        # Get special status flags for standard deduction rules
        spouse_itemizes = getattr(self.taxpayer, 'spouse_itemizes_deductions', False)
        is_dual_status_alien = getattr(self.taxpayer, 'is_dual_status_alien', False)
        can_be_claimed_as_dependent = getattr(self.taxpayer, 'can_be_claimed_as_dependent', False)
        earned_income_for_dependent = getattr(self.taxpayer, 'earned_income_for_dependent_deduction', 0.0)

        deduction = self.deductions.get_deduction_amount(
            self.taxpayer.filing_status.value,
            agi,
            is_over_65,
            is_blind,
            spouse_itemizes,
            is_dual_status_alien,
            can_be_claimed_as_dependent,
            earned_income_for_dependent
        )
        self.taxable_income = max(0.0, agi - deduction)
        
        # Calculate tax liability (handled by calculator)
        # This will be set by the tax calculator
        
        # Calculate credits
        earned_income = self.income.get_total_wages() + self.income.self_employment_income
        num_children = len(self.taxpayer.dependents)
        
        eitc = self.credits.calculate_eitc(
            earned_income,
            self.adjusted_gross_income,
            self.taxpayer.filing_status.value,
            num_children
        )
        
        child_tax_credit, refundable_child_credit = self.credits.calculate_child_tax_credit(
            num_children,
            self.adjusted_gross_income,
            self.taxpayer.filing_status.value
        )
        
        self.total_credits = (
            eitc +
            child_tax_credit +
            self.credits.child_care_expenses * 0.20 +  # Simplified child care credit
            self.credits.foreign_tax_credit +
            self.credits.residential_energy_credit +
            self.credits.other_credits
        )
        
        # Calculate payments
        self.total_payments = self.income.get_total_federal_withholding()
        
        # Calculate refund or amount owed
        if self.tax_liability is not None:
            net_tax = self.tax_liability - self.total_credits
            self.refund_or_owed = self.total_payments - net_tax
