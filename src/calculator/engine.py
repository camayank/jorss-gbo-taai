from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from decimal import Decimal

from models.tax_return import TaxReturn
from calculator.tax_year_config import TaxYearConfig
from calculator.qbi_calculator import QBICalculator
from calculator.decimal_math import (
    add, subtract, multiply, divide, min_decimal, max_decimal, money, to_decimal, to_float
)
from validation.dependent_validator import (
    DependentValidator,
    validate_all_dependents,
    get_eitc_qualifying_children,
    get_ctc_qualifying_children,
    get_other_dependents_count,
)


@dataclass
class CalculationBreakdown:
    """
    Comprehensive breakdown of federal tax calculation.

    Supports all major income types and credits including:
    - Gambling income/losses (BR-0501 to BR-0510)
    - Virtual currency/crypto (BR-0601 to BR-0620)
    - K-1 pass-through income (BR-0701 to BR-0730)
    - Education credits AOTC/LLC (BR-0801 to BR-0830)
    - Premium Tax Credit (BR-0901 to BR-0920)
    - Foreign Tax Credit (BR-0951 to BR-0970)
    """
    tax_year: int
    filing_status: str

    # Income
    gross_income: float = 0.0
    adjustments_to_income: float = 0.0
    agi: float = 0.0
    deduction_type: str = "standard"  # "standard" or "itemized"
    deduction_amount: float = 0.0
    qbi_deduction: float = 0.0
    taxable_income: float = 0.0

    # Income breakdown
    ordinary_income: float = 0.0
    preferential_income: float = 0.0  # Qualified dividends + LTCG

    # Crypto income breakdown (BR-0601 to BR-0620)
    crypto_ordinary_income: float = 0.0  # Mining, staking, airdrops
    crypto_short_term_gains: float = 0.0
    crypto_long_term_gains: float = 0.0
    crypto_losses: float = 0.0

    # K-1 income breakdown (BR-0701 to BR-0730)
    k1_ordinary_income: float = 0.0
    k1_preferential_income: float = 0.0
    k1_self_employment_income: float = 0.0

    # Gambling income (BR-0501 to BR-0510)
    gambling_income: float = 0.0
    gambling_losses_deducted: float = 0.0

    # Capital gain/loss breakdown (IRC Section 1211/1212)
    net_short_term_gain_loss: float = 0.0
    net_long_term_gain_loss: float = 0.0
    capital_loss_deduction: float = 0.0  # Loss deduction against ordinary income (max $3k)
    new_st_loss_carryforward: float = 0.0  # ST loss to carry to next year
    new_lt_loss_carryforward: float = 0.0  # LT loss to carry to next year

    # Tax components
    ordinary_income_tax: float = 0.0
    preferential_income_tax: float = 0.0
    self_employment_tax: float = 0.0
    additional_medicare_tax: float = 0.0
    net_investment_income_tax: float = 0.0
    alternative_minimum_tax: float = 0.0

    # Total tax before credits
    total_tax_before_credits: float = 0.0

    # PTC repayment (if APTC exceeded allowed)
    ptc_repayment: float = 0.0

    # Credits
    nonrefundable_credits: float = 0.0
    refundable_credits: float = 0.0
    total_credits: float = 0.0

    # Final calculations
    total_tax: float = 0.0
    total_payments: float = 0.0
    refund_or_owed: float = 0.0

    # Effective rates
    effective_tax_rate: float = 0.0
    marginal_tax_rate: float = 0.0

    # Detailed breakdowns
    bracket_breakdown: List[Dict[str, float]] = field(default_factory=list)
    credit_breakdown: Dict[str, float] = field(default_factory=dict)
    se_tax_breakdown: Dict[str, float] = field(default_factory=dict)

    # IRA contribution tracking
    roth_ira_eligible_contribution: float = 0.0  # Max eligible Roth IRA contribution after phaseouts

    # Estimated tax penalty (Form 2210)
    estimated_tax_penalty: float = 0.0
    safe_harbor_met: bool = True
    required_annual_payment: float = 0.0

    # HSA (Form 8889)
    hsa_deduction: float = 0.0
    hsa_taxable_distributions: float = 0.0
    hsa_additional_tax: float = 0.0
    hsa_excess_contributions: float = 0.0

    # IRA (Form 8606)
    ira_taxable_distributions: float = 0.0
    ira_nontaxable_distributions: float = 0.0
    ira_early_withdrawal_penalty: float = 0.0
    roth_conversion_taxable: float = 0.0
    ira_basis_carryforward: float = 0.0

    # Form 5329 Additional Taxes on Retirement Accounts
    form_5329_early_distribution_penalty: float = 0.0
    form_5329_excess_contribution_tax: float = 0.0
    form_5329_rmd_penalty: float = 0.0
    form_5329_total_additional_tax: float = 0.0

    # Form 4797 Sales of Business Property
    form_4797_ordinary_income: float = 0.0
    form_4797_section_1231_gain: float = 0.0
    form_4797_section_1231_loss: float = 0.0
    form_4797_unrecaptured_1250_gain: float = 0.0
    form_4797_depreciation_recapture: float = 0.0
    form_4797_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Form 6252 Installment Sale Income
    form_6252_installment_income: float = 0.0
    form_6252_interest_income: float = 0.0
    form_6252_depreciation_recapture: float = 0.0
    form_6252_capital_gain: float = 0.0
    form_6252_ordinary_income: float = 0.0
    form_6252_unrecaptured_1250_gain: float = 0.0
    form_6252_section_453a_interest: float = 0.0
    form_6252_breakdown: Dict[str, Any] = field(default_factory=dict)

    # AMT breakdown (Form 6251)
    amt_breakdown: Dict[str, float] = field(default_factory=dict)

    # Form 8801 Minimum Tax Credit
    form_8801_credit_available: float = 0.0
    form_8801_credit_allowed: float = 0.0
    form_8801_credit_limit: float = 0.0
    form_8801_carryforward: float = 0.0
    form_8801_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Form 1116 Foreign Tax Credit
    form_1116_foreign_taxes_paid: float = 0.0
    form_1116_foreign_source_income: float = 0.0
    form_1116_limitation: float = 0.0
    form_1116_credit_allowed: float = 0.0
    form_1116_carryforward: float = 0.0
    form_1116_simplified_method: bool = False
    form_1116_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Form 8615 Kiddie Tax
    form_8615_subject_to_kiddie_tax: bool = False
    form_8615_unearned_income: float = 0.0
    form_8615_net_unearned_income: float = 0.0
    form_8615_kiddie_tax_increase: float = 0.0
    form_8615_total_child_tax: float = 0.0
    form_8615_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Form 2555 Foreign Earned Income Exclusion
    form_2555_qualifies: bool = False
    form_2555_foreign_earned_income: float = 0.0
    form_2555_exclusion: float = 0.0
    form_2555_housing_exclusion: float = 0.0
    form_2555_housing_deduction: float = 0.0
    form_2555_total_exclusion: float = 0.0
    form_2555_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Schedule H Household Employment Taxes
    schedule_h_must_file: bool = False
    schedule_h_total_tax: float = 0.0
    schedule_h_ss_medicare_tax: float = 0.0
    schedule_h_futa_tax: float = 0.0
    schedule_h_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Form 4952 Investment Interest Expense
    form_4952_total_interest: float = 0.0
    form_4952_net_investment_income: float = 0.0
    form_4952_allowable_deduction: float = 0.0
    form_4952_carryforward: float = 0.0
    form_4952_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Form 5471 Foreign Corporation Reporting
    form_5471_count: int = 0
    form_5471_subpart_f_income: float = 0.0
    form_5471_gilti_income: float = 0.0
    form_5471_total_inclusion: float = 0.0
    form_5471_breakdowns: List[Dict[str, Any]] = field(default_factory=list)

    # Form 8582 Passive Activity Loss Limitations
    form_8582_passive_loss_allowed: float = 0.0
    form_8582_suspended_loss: float = 0.0
    form_8582_rental_allowance: float = 0.0
    form_8582_net_passive_income: float = 0.0
    form_8582_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Passive Activity Loss breakdown (Form 8582) - legacy field
    pal_breakdown: Dict[str, float] = field(default_factory=dict)

    # Depreciation breakdown (Form 4562)
    depreciation_breakdown: Dict[str, float] = field(default_factory=dict)

    # Clean Vehicle Credit breakdown (Form 8936)
    clean_vehicle_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Form 1040 checkbox
    had_virtual_currency_activity: bool = False

    # Schedule A - Itemized Deductions
    schedule_a_total_deductions: float = 0.0
    schedule_a_medical_deduction: float = 0.0
    schedule_a_salt_deduction: float = 0.0
    schedule_a_mortgage_interest: float = 0.0
    schedule_a_charitable: float = 0.0
    schedule_a_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Schedule B - Interest and Ordinary Dividends
    schedule_b_total_interest: float = 0.0
    schedule_b_total_dividends: float = 0.0
    schedule_b_qualified_dividends: float = 0.0
    schedule_b_requires_part_iii: bool = False
    schedule_b_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Schedule D - Capital Gains and Losses
    schedule_d_net_gain_loss: float = 0.0
    schedule_d_short_term_net: float = 0.0
    schedule_d_long_term_net: float = 0.0
    schedule_d_28_rate_gain: float = 0.0
    schedule_d_unrecaptured_1250: float = 0.0
    schedule_d_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Schedule E - Supplemental Income and Loss
    schedule_e_total: float = 0.0
    schedule_e_rental_income: float = 0.0
    schedule_e_partnership_income: float = 0.0
    schedule_e_estate_trust_income: float = 0.0
    schedule_e_se_income: float = 0.0
    schedule_e_qbi: float = 0.0
    schedule_e_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Schedule F - Profit or Loss From Farming
    schedule_f_net_profit_loss: float = 0.0
    schedule_f_gross_income: float = 0.0
    schedule_f_expenses: float = 0.0
    schedule_f_se_income: float = 0.0
    schedule_f_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Form 6781 - Section 1256 Contracts and Straddles
    form_6781_section_1256_net: float = 0.0
    form_6781_short_term: float = 0.0
    form_6781_long_term: float = 0.0
    form_6781_straddle_net: float = 0.0
    form_6781_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Form 8814 - Parent's Election to Report Child's Income
    form_8814_income_to_include: float = 0.0
    form_8814_child_tax: float = 0.0
    form_8814_qualifying_children: int = 0
    form_8814_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Form 8995 - Qualified Business Income Deduction
    form_8995_qbi_deduction: float = 0.0
    form_8995_below_threshold: bool = True
    form_8995_loss_carryforward: float = 0.0
    form_8995_breakdown: Dict[str, Any] = field(default_factory=dict)

    # =========================================================================
    # New Income Types (comprehensive coverage)
    # =========================================================================

    # Form 1099-R Distributions (pensions, annuities, IRAs, 401k)
    form_1099r_taxable: float = 0.0
    form_1099r_early_distribution_penalty: float = 0.0
    form_1099r_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Stock Compensation (ISO, NSO, RSA, RSU, ESPP)
    stock_compensation_income: float = 0.0
    stock_compensation_amt_preference: float = 0.0
    stock_compensation_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Alimony (pre-2019 agreements only)
    alimony_income: float = 0.0

    # Debt Cancellation (Form 1099-C)
    debt_cancellation_income: float = 0.0
    debt_cancellation_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Miscellaneous Income
    prizes_and_awards_income: float = 0.0
    taxable_scholarship_income: float = 0.0
    jury_duty_income: float = 0.0

    # Form 1099-Q (529/Coverdell distributions)
    form_1099q_taxable: float = 0.0
    form_1099q_penalty: float = 0.0
    form_1099q_breakdown: Dict[str, Any] = field(default_factory=dict)

    # State Tax Refund Recovery
    state_refund_taxable: float = 0.0
    state_refund_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Form 1099-OID (Original Issue Discount)
    form_1099oid_taxable: float = 0.0
    form_1099oid_early_withdrawal_penalty: float = 0.0
    form_1099oid_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Form 1099-PATR (Patronage Dividends from Cooperatives)
    form_1099patr_taxable: float = 0.0
    form_1099patr_section_199a: float = 0.0
    form_1099patr_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Form 1099-LTC (Long-Term Care Benefits)
    form_1099ltc_taxable: float = 0.0
    form_1099ltc_gross: float = 0.0
    form_1099ltc_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Form RRB-1099 (Railroad Retirement Benefits)
    form_rrb1099_gross_sseb: float = 0.0
    form_rrb1099_taxable: float = 0.0
    form_rrb1099_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Form 4137 (Unreported Tip Income)
    form_4137_unreported_tips: float = 0.0
    form_4137_ss_tax: float = 0.0
    form_4137_medicare_tax: float = 0.0
    form_4137_total_tax: float = 0.0
    form_4137_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Clergy Housing Allowance (Section 107)
    clergy_housing_excludable: float = 0.0
    clergy_housing_taxable: float = 0.0
    clergy_housing_se_amount: float = 0.0
    clergy_housing_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Military Combat Pay Exclusion (Section 112)
    military_combat_pay_exclusion: float = 0.0
    military_taxable_pay: float = 0.0
    military_eitc_earned_income: float = 0.0
    military_combat_pay_breakdown: Dict[str, Any] = field(default_factory=dict)



    def __setattr__(self, name: str, value):
        """Auto-convert Decimal values to float to prevent Decimal/float mixing errors."""
        if isinstance(value, Decimal):
            value = float(value)
        object.__setattr__(self, name, value)

    def to_dict(self) -> Dict[str, Any]:
        """Convert breakdown to dict for JSON serialization."""
        from dataclasses import asdict

        def _convert(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            if isinstance(obj, dict):
                return {k: _convert(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_convert(v) for v in obj]
            return obj

        return _convert(asdict(self))


class FederalTaxEngine:
    """
    Comprehensive federal tax calculation engine for Tax Year 2025.

    Implements all major federal tax rules including:
    - Progressive tax brackets (7 rates)
    - Qualified dividends / Long-term capital gains preferential rates (0%, 15%, 20%)
    - Self-employment tax with Social Security wage base cap
    - Additional Medicare Tax (0.9%)
    - Net Investment Income Tax (3.8%)
    - Alternative Minimum Tax (AMT)
    - Standard and itemized deductions
    - Tax credits (refundable and nonrefundable)
    """

    def __init__(self, config: Optional[TaxYearConfig] = None):
        self.config = config or TaxYearConfig.for_2025()

    def calculate(self, tax_return: TaxReturn) -> CalculationBreakdown:
        """Execute full federal tax calculation."""
        tax_return.tax_year = tax_return.tax_year or self.config.tax_year

        # Compute taxable Social Security if applicable
        self._maybe_compute_taxable_social_security(tax_return)

        filing_status = tax_return.taxpayer.filing_status.value

        # Calculate self-employment tax first (affects AGI via deduction)
        se_result = self._calculate_self_employment_tax(tax_return, filing_status)

        # Add SE tax deduction to adjustments
        original_other_adj = tax_return.deductions.other_adjustments
        tax_return.deductions.other_adjustments = original_other_adj + se_result['se_tax_deduction']

        # Now calculate AGI and taxable income
        tax_return.calculate()

        # Create breakdown
        breakdown = CalculationBreakdown(
            tax_year=self.config.tax_year,
            filing_status=filing_status,
        )

        # Populate income values
        breakdown.gross_income = tax_return.income.get_total_income()

        # Get taxpayer IRA-related fields (BR2-0009, BR2-0010)
        taxpayer = tax_return.taxpayer
        is_covered_by_employer_plan = getattr(taxpayer, 'is_covered_by_employer_plan', False)
        spouse_covered_by_employer_plan = getattr(taxpayer, 'spouse_covered_by_employer_plan', False)
        is_age_50_plus = getattr(taxpayer, 'is_age_50_plus', False)

        # Calculate taxable compensation for IRA limit (wages + SE net income)
        taxable_compensation = (
            tax_return.income.get_total_wages() +
            max(0, tax_return.income.get_schedule_c_net_profit())
        )

        # For IRA phaseout, MAGI is approximately AGI before IRA deduction
        # Use preliminary AGI from tax_return.calculate() as proxy
        preliminary_agi = tax_return.adjusted_gross_income or 0.0
        # MAGI for IRA = AGI + IRA contributions (to get pre-IRA-deduction MAGI)
        magi_for_ira = preliminary_agi + tax_return.deductions.ira_contributions

        # Calculate adjustments with proper IRA phaseout
        breakdown.adjustments_to_income = tax_return.deductions.get_total_adjustments(
            magi=magi_for_ira,
            filing_status=filing_status,
            is_covered_by_employer_plan=is_covered_by_employer_plan,
            spouse_covered_by_employer_plan=spouse_covered_by_employer_plan,
            is_age_50_plus=is_age_50_plus,
            taxable_compensation=taxable_compensation,
        )

        # Calculate Roth IRA eligible contribution (BR2-0011)
        # Note: Roth contributions are NOT tax-deductible but have income-based limits
        breakdown.roth_ira_eligible_contribution = tax_return.deductions.get_roth_ira_eligible_contribution(
            magi=magi_for_ira,
            filing_status=filing_status,
            is_age_50_plus=is_age_50_plus,
            taxable_compensation=taxable_compensation,
            traditional_ira_contributions=tax_return.deductions.ira_contributions,
        )

        # Recalculate AGI with proper IRA deduction
        breakdown.agi = breakdown.gross_income - breakdown.adjustments_to_income

        # Determine deduction type and amount
        ded = tax_return.deductions
        is_over_65 = getattr(tax_return.taxpayer, 'is_over_65', False)
        is_blind = getattr(tax_return.taxpayer, 'is_blind', False)

        # Get special status flags for standard deduction rules (BR2-0002, BR2-0003, BR2-0004)
        spouse_itemizes = getattr(tax_return.taxpayer, 'spouse_itemizes_deductions', False)
        is_dual_status_alien = getattr(tax_return.taxpayer, 'is_dual_status_alien', False)
        can_be_claimed_as_dependent = getattr(tax_return.taxpayer, 'can_be_claimed_as_dependent', False)
        earned_income_for_dependent = getattr(tax_return.taxpayer, 'earned_income_for_dependent_deduction', 0.0)

        # Get gambling winnings for itemized deduction limitation (BR-0501 to BR-0510)
        gambling_winnings = tax_return.income.get_total_gambling_winnings()

        deduction_amount = ded.get_deduction_amount(
            filing_status, breakdown.agi, is_over_65, is_blind,
            spouse_itemizes, is_dual_status_alien,
            can_be_claimed_as_dependent, earned_income_for_dependent,
            gambling_winnings
        )
        itemized_total = ded.itemized.get_total_itemized(breakdown.agi, gambling_winnings, filing_status)
        standard_total = ded._get_standard_deduction(
            filing_status, is_over_65, is_blind,
            spouse_itemizes, is_dual_status_alien,
            can_be_claimed_as_dependent, earned_income_for_dependent
        )
        breakdown.deduction_type = "itemized" if itemized_total > standard_total else "standard"
        breakdown.deduction_amount = deduction_amount
        # Recalculate taxable income using properly adjusted AGI (with IRA phaseout)
        breakdown.taxable_income = max(0, breakdown.agi - deduction_amount)

        # Calculate QBI deduction (Section 199A)
        # QBI deduction is applied after standard/itemized deduction
        # It reduces taxable income by up to 20% of qualified business income
        # Net capital gain = qualified dividends + long-term capital gains
        inc = tax_return.income
        net_capital_gain = (
            inc.qualified_dividends +
            inc.long_term_capital_gains +
            inc.get_crypto_long_term_gains() +
            inc.get_k1_preferential_income()
        )

        qbi_calculator = QBICalculator()
        qbi_result = qbi_calculator.calculate(
            tax_return=tax_return,
            taxable_income_before_qbi=breakdown.taxable_income,
            net_capital_gain=net_capital_gain,
            filing_status=filing_status,
            config=self.config,
        )
        breakdown.qbi_deduction = qbi_result.final_qbi_deduction

        # Adjust taxable income for QBI deduction
        breakdown.taxable_income = max(0, breakdown.taxable_income - breakdown.qbi_deduction)

        # Split income into ordinary and preferential
        breakdown.ordinary_income, breakdown.preferential_income = self._split_taxable_income(tax_return)

        # Populate crypto income breakdown (BR-0601 to BR-0620)
        inc = tax_return.income
        breakdown.crypto_ordinary_income = inc.get_crypto_ordinary_income()
        breakdown.crypto_short_term_gains = inc.get_crypto_short_term_gains()
        breakdown.crypto_long_term_gains = inc.get_crypto_long_term_gains()
        breakdown.crypto_losses = inc.get_crypto_short_term_losses() + inc.get_crypto_long_term_losses()
        breakdown.had_virtual_currency_activity = inc.has_virtual_currency_activity()

        # Populate K-1 income breakdown (BR-0701 to BR-0730)
        breakdown.k1_ordinary_income = inc.get_k1_ordinary_income()
        breakdown.k1_preferential_income = inc.get_k1_preferential_income()
        breakdown.k1_self_employment_income = se_result.get('k1_self_employment_income', 0.0)

        # Populate gambling income breakdown (BR-0501 to BR-0510)
        breakdown.gambling_income = gambling_winnings
        breakdown.gambling_losses_deducted = inc.get_deductible_gambling_losses() if breakdown.deduction_type == "itemized" else 0.0

        # =====================================================================
        # Populate new income types
        # =====================================================================

        # Form 1099-R distributions (pensions, annuities, IRAs, 401k)
        breakdown.form_1099r_taxable = inc.get_total_1099r_taxable()
        breakdown.form_1099r_early_distribution_penalty = inc.get_1099r_early_distribution_penalty()
        if inc.form_1099r_distributions:
            breakdown.form_1099r_breakdown = {
                'distribution_count': len(inc.form_1099r_distributions),
                'total_gross': sum(d.gross_distribution for d in inc.form_1099r_distributions),
                'total_taxable': breakdown.form_1099r_taxable,
                'total_withholding': inc.get_total_1099r_withholding(),
                'early_distribution_penalty': breakdown.form_1099r_early_distribution_penalty,
            }

        # Stock compensation (ISO, NSO, RSA, RSU, ESPP)
        breakdown.stock_compensation_income = inc.get_total_stock_compensation_income()
        breakdown.stock_compensation_amt_preference = inc.get_total_stock_compensation_amt_preference()
        if inc.stock_compensation_events:
            breakdown.stock_compensation_breakdown = {
                'event_count': len(inc.stock_compensation_events),
                'ordinary_income': breakdown.stock_compensation_income,
                'amt_preference': breakdown.stock_compensation_amt_preference,
                'total_withholding': inc.get_total_stock_compensation_withholding(),
            }

        # Alimony received (pre-2019 agreements only)
        breakdown.alimony_income = inc.get_taxable_alimony_received()

        # Debt cancellation income (Form 1099-C)
        breakdown.debt_cancellation_income = inc.get_total_debt_cancellation_income()
        if inc.form_1099c_debt_cancellation:
            total_canceled = sum(d.amount_canceled for d in inc.form_1099c_debt_cancellation)
            total_excluded = total_canceled - breakdown.debt_cancellation_income
            breakdown.debt_cancellation_breakdown = {
                'form_count': len(inc.form_1099c_debt_cancellation),
                'total_canceled': total_canceled,
                'total_excluded': total_excluded,
                'taxable_amount': breakdown.debt_cancellation_income,
            }

        # Miscellaneous income
        breakdown.prizes_and_awards_income = inc.prizes_and_awards
        breakdown.taxable_scholarship_income = inc.taxable_scholarship
        breakdown.jury_duty_income = inc.get_net_jury_duty_pay()

        # Form 1099-Q (529/Coverdell distributions)
        breakdown.form_1099q_taxable = inc.get_total_1099q_taxable()
        breakdown.form_1099q_penalty = inc.get_total_1099q_penalty()
        if inc.form_1099q_distributions:
            breakdown.form_1099q_breakdown = inc.get_1099q_summary()

        # State tax refund recovery
        breakdown.state_refund_taxable = inc.get_total_taxable_state_refunds()
        if inc.state_tax_refunds:
            breakdown.state_refund_breakdown = inc.get_state_refund_summary()

        # Form 1099-OID (Original Issue Discount)
        breakdown.form_1099oid_taxable = inc.get_total_1099oid_taxable()
        breakdown.form_1099oid_early_withdrawal_penalty = inc.get_total_1099oid_early_withdrawal_penalty()
        if inc.form_1099oid:
            breakdown.form_1099oid_breakdown = inc.get_1099oid_summary()

        # Form 1099-PATR (Patronage Dividends from Cooperatives)
        breakdown.form_1099patr_taxable = inc.get_total_1099patr_taxable()
        breakdown.form_1099patr_section_199a = inc.get_total_1099patr_section_199a()
        if inc.form_1099patr:
            breakdown.form_1099patr_breakdown = inc.get_1099patr_summary()

        # Form 1099-LTC (Long-Term Care Benefits)
        breakdown.form_1099ltc_taxable = inc.get_total_1099ltc_taxable()
        breakdown.form_1099ltc_gross = inc.get_total_1099ltc_gross()
        if inc.form_1099ltc:
            breakdown.form_1099ltc_breakdown = inc.get_1099ltc_summary()

        # Form RRB-1099 (Railroad Retirement Benefits)
        # Note: Taxable amount calculated after MAGI is determined (like Social Security)
        breakdown.form_rrb1099_gross_sseb = inc.get_total_rrb1099_gross_sseb()
        if inc.form_rrb1099:
            breakdown.form_rrb1099_breakdown = inc.get_rrb1099_summary()

        # Form 4137 (Unreported Tip Income)
        breakdown.form_4137_unreported_tips = inc.get_total_unreported_tips()
        breakdown.form_4137_ss_tax = inc.get_total_form4137_ss_tax()
        breakdown.form_4137_medicare_tax = inc.get_total_form4137_medicare_tax()
        breakdown.form_4137_total_tax = inc.get_total_form4137_tax()
        if inc.form_4137_tips:
            breakdown.form_4137_breakdown = inc.get_form4137_summary()

        # Clergy Housing Allowance (Section 107)
        breakdown.clergy_housing_excludable = inc.get_clergy_housing_excludable()
        breakdown.clergy_housing_taxable = inc.get_clergy_housing_taxable()
        breakdown.clergy_housing_se_amount = inc.get_clergy_housing_se_amount()
        if inc.clergy_housing:
            breakdown.clergy_housing_breakdown = inc.get_clergy_housing_summary()

        # Military Combat Pay Exclusion (Section 112)
        breakdown.military_combat_pay_exclusion = inc.get_military_combat_pay_exclusion()
        breakdown.military_taxable_pay = inc.get_military_taxable_pay()
        breakdown.military_eitc_earned_income = inc.get_military_eitc_earned_income()
        if inc.military_combat_pay:
            breakdown.military_combat_pay_breakdown = inc.get_military_combat_pay_summary()

        # Calculate capital gains/losses with carryforward (IRC Section 1211/1212)
        cap_result = inc.calculate_net_capital_gain_loss(
            filing_status=filing_status,
            capital_loss_limit=self.config.capital_loss_limit,
            capital_loss_limit_mfs=self.config.capital_loss_limit_mfs
        )
        (net_gain, loss_ded, new_st_cf, new_lt_cf, net_st, net_lt) = cap_result
        breakdown.net_short_term_gain_loss = net_st
        breakdown.net_long_term_gain_loss = net_lt
        breakdown.capital_loss_deduction = loss_ded
        breakdown.new_st_loss_carryforward = new_st_cf
        breakdown.new_lt_loss_carryforward = new_lt_cf

        # Calculate ordinary income tax
        breakdown.ordinary_income_tax, breakdown.bracket_breakdown = self._compute_ordinary_income_tax(
            taxable_income=breakdown.ordinary_income,
            filing_status=filing_status,
            return_breakdown=True
        )

        # Calculate preferential income tax (LTCG + qualified dividends)
        breakdown.preferential_income_tax = self._compute_preferential_tax(
            filing_status=filing_status,
            ordinary_taxable_income=breakdown.ordinary_income,
            preferential_taxable_income=breakdown.preferential_income,
        )

        # Self-employment tax
        breakdown.self_employment_tax = se_result['total_se_tax']
        breakdown.se_tax_breakdown = se_result

        # Additional Medicare Tax (0.9%)
        breakdown.additional_medicare_tax = self._calculate_additional_medicare_tax(
            tax_return, filing_status
        )

        # Net Investment Income Tax (3.8%)
        breakdown.net_investment_income_tax = self._calculate_niit(
            tax_return, filing_status
        )

        # Alternative Minimum Tax (Form 6251)
        amt_result = self._calculate_amt(tax_return, filing_status, breakdown)
        breakdown.alternative_minimum_tax = amt_result['amt']
        breakdown.amt_breakdown = amt_result

        # Minimum Tax Credit (Form 8801)
        mtc_result = self._calculate_minimum_tax_credit(
            tax_return, filing_status, breakdown, amt_result
        )
        breakdown.form_8801_credit_available = mtc_result['credit_available']
        breakdown.form_8801_credit_allowed = mtc_result['credit_allowed']
        breakdown.form_8801_credit_limit = mtc_result['credit_limit']
        breakdown.form_8801_carryforward = mtc_result['carryforward']
        breakdown.form_8801_breakdown = mtc_result

        # Kiddie Tax (Form 8615)
        if tax_return.income.form_8615:
            kiddie_result = tax_return.income.form_8615.calculate_kiddie_tax()
            breakdown.form_8615_subject_to_kiddie_tax = kiddie_result.get('subject_to_kiddie_tax', False)
            breakdown.form_8615_unearned_income = kiddie_result.get('unearned_income', 0.0)
            breakdown.form_8615_net_unearned_income = kiddie_result.get('net_unearned_income', 0.0)
            breakdown.form_8615_kiddie_tax_increase = kiddie_result.get('kiddie_tax_increase', 0.0)
            breakdown.form_8615_total_child_tax = kiddie_result.get('total_child_tax', 0.0)
            breakdown.form_8615_breakdown = kiddie_result

        # Foreign Earned Income Exclusion (Form 2555)
        if tax_return.income.form_2555:
            feie_result = tax_return.income.form_2555.calculate_exclusion()
            breakdown.form_2555_qualifies = feie_result.get('qualifies', False)
            breakdown.form_2555_foreign_earned_income = feie_result.get('total_foreign_earned_income', 0.0)
            breakdown.form_2555_exclusion = feie_result.get('foreign_earned_income_exclusion', 0.0)
            breakdown.form_2555_housing_exclusion = feie_result.get('housing_exclusion', 0.0)
            breakdown.form_2555_housing_deduction = feie_result.get('housing_deduction', 0.0)
            breakdown.form_2555_total_exclusion = feie_result.get('total_exclusion', 0.0)
            breakdown.form_2555_breakdown = feie_result

            # Apply FEIE to reduce taxable income
            # The exclusion is already subtracted from gross income via Schedule 1 Line 8d
            if breakdown.form_2555_qualifies:
                # Reduce AGI by the exclusion amount (FEIE is an adjustment to income)
                breakdown.agi = max(0.0, breakdown.agi - breakdown.form_2555_total_exclusion)
                # Housing deduction is an additional adjustment
                breakdown.adjustments_to_income += breakdown.form_2555_housing_deduction

        # Household Employment Taxes (Schedule H)
        if tax_return.income.schedule_h:
            sch_h_result = tax_return.income.schedule_h.calculate_schedule_h()
            breakdown.schedule_h_must_file = sch_h_result.get('must_file', False)
            breakdown.schedule_h_total_tax = sch_h_result.get('total_household_employment_tax', 0.0)
            breakdown.schedule_h_ss_medicare_tax = sch_h_result.get('total_ss_medicare_tax', 0.0)
            breakdown.schedule_h_futa_tax = sch_h_result.get('total_futa_tax', 0.0)
            breakdown.schedule_h_breakdown = sch_h_result

        # Investment Interest Expense (Form 4952)
        if tax_return.income.form_4952:
            inv_int_result = tax_return.income.form_4952.calculate_deduction()
            breakdown.form_4952_total_interest = inv_int_result.get('line_3_total_investment_interest', 0.0)
            breakdown.form_4952_net_investment_income = inv_int_result.get('line_6_net_investment_income', 0.0)
            breakdown.form_4952_allowable_deduction = inv_int_result.get('line_8_allowable_deduction', 0.0)
            breakdown.form_4952_carryforward = inv_int_result.get('carryforward_to_next_year', 0.0)
            breakdown.form_4952_breakdown = inv_int_result

        # Foreign Corporation Reporting (Form 5471)
        if tax_return.income.form_5471_list:
            breakdown.form_5471_count = len(tax_return.income.form_5471_list)
            breakdown.form_5471_subpart_f_income = tax_return.income.get_total_subpart_f_income()
            breakdown.form_5471_gilti_income = tax_return.income.get_total_gilti_income()
            breakdown.form_5471_total_inclusion = tax_return.income.get_total_cfc_income_inclusion()
            breakdown.form_5471_breakdowns = tax_return.income.get_form_5471_summaries()

            # CFC income inclusion increases gross income
            if breakdown.form_5471_total_inclusion > 0:
                breakdown.gross_income += breakdown.form_5471_total_inclusion
                breakdown.agi += breakdown.form_5471_total_inclusion

        # Passive Activity Loss (Form 8582)
        pal_result = self._calculate_passive_activity_loss(
            tax_return, filing_status, breakdown.agi
        )
        breakdown.pal_breakdown = pal_result

        # Depreciation (Form 4562 / MACRS)
        depreciation_result = self._calculate_depreciation(
            tax_return, self.config.tax_year
        )
        breakdown.depreciation_breakdown = depreciation_result

        # HSA (Form 8889) calculations
        if tax_return.income.hsa_info:
            hsa_result = tax_return.income.hsa_info.calculate_deduction(
                self.config.hsa_individual_limit,
                self.config.hsa_family_limit,
                self.config.hsa_catchup_55_plus,
            )
            breakdown.hsa_deduction = hsa_result['hsa_deduction']
            breakdown.hsa_excess_contributions = hsa_result['excess_contributions']

            hsa_tax = tax_return.income.hsa_info.calculate_additional_tax()
            breakdown.hsa_taxable_distributions = hsa_tax['taxable_distributions']
            breakdown.hsa_additional_tax = hsa_tax['total_additional_tax']

        # IRA (Form 8606) calculations
        if tax_return.income.ira_info:
            # Calculate taxable portion of IRA distributions
            breakdown.ira_taxable_distributions = (
                tax_return.income.ira_info.calculate_taxable_traditional_distribution() +
                tax_return.income.ira_info.calculate_taxable_roth_distribution(self.config.tax_year)
            )
            breakdown.ira_nontaxable_distributions = (
                tax_return.income.get_total_ira_distributions() -
                breakdown.ira_taxable_distributions
            )
            # Roth conversion taxable amount
            roth_conv = tax_return.income.ira_info.calculate_part_ii_conversion()
            breakdown.roth_conversion_taxable = roth_conv['taxable_conversion']
            # Early withdrawal penalty (10%)
            breakdown.ira_early_withdrawal_penalty = (
                tax_return.income.ira_info.calculate_early_withdrawal_penalty(self.config.tax_year)
            )
            # Basis carryforward for next year
            breakdown.ira_basis_carryforward = tax_return.income.ira_info.get_remaining_basis()

        # Form 5329 Additional Taxes on Retirement Accounts
        if tax_return.income.form_5329:
            # Part I: Early distribution penalty
            breakdown.form_5329_early_distribution_penalty = (
                tax_return.income.get_form_5329_early_distribution_penalty()
            )
            # Parts II-VII: Excess contribution penalties (6%)
            breakdown.form_5329_excess_contribution_tax = (
                tax_return.income.get_form_5329_excess_contribution_tax()
            )
            # Part VIII: RMD failure penalty (25%/10%)
            breakdown.form_5329_rmd_penalty = (
                tax_return.income.get_form_5329_rmd_penalty()
            )
            # Total Form 5329 tax
            breakdown.form_5329_total_additional_tax = (
                tax_return.income.get_form_5329_total_additional_tax()
            )

        # Form 4797 Sales of Business Property
        if tax_return.income.form_4797:
            # Ordinary income from Part II (short-term gains, recapture)
            breakdown.form_4797_ordinary_income = (
                tax_return.income.get_form_4797_ordinary_income(self.config.tax_year)
            )
            # Section 1231 gain (treated as LTCG on Schedule D)
            breakdown.form_4797_section_1231_gain = (
                tax_return.income.get_form_4797_section_1231_gain(self.config.tax_year)
            )
            # Section 1231 loss (treated as ordinary loss)
            breakdown.form_4797_section_1231_loss = (
                tax_return.income.get_form_4797_section_1231_loss(self.config.tax_year)
            )
            # Unrecaptured Section 1250 gain (taxed at max 25%)
            breakdown.form_4797_unrecaptured_1250_gain = (
                tax_return.income.get_form_4797_unrecaptured_1250_gain()
            )
            # Depreciation recapture (ordinary income portion)
            breakdown.form_4797_depreciation_recapture = (
                tax_return.income.get_form_4797_depreciation_recapture(self.config.tax_year)
            )
            # Full breakdown
            breakdown.form_4797_breakdown = (
                tax_return.income.get_form_4797_summary(self.config.tax_year) or {}
            )

        # Form 6252 Installment Sale Income
        if tax_return.income.form_6252:
            # Installment sale income (capital gain portion)
            breakdown.form_6252_installment_income = (
                tax_return.income.get_form_6252_installment_income()
            )
            # Interest income (ordinary income)
            breakdown.form_6252_interest_income = (
                tax_return.income.get_form_6252_interest_income()
            )
            # Depreciation recapture (ordinary income, year of sale only)
            breakdown.form_6252_depreciation_recapture = (
                tax_return.income.get_form_6252_depreciation_recapture()
            )
            # Capital gain from installment sales
            breakdown.form_6252_capital_gain = (
                tax_return.income.get_form_6252_capital_gain()
            )
            # Total ordinary income from installment sales
            breakdown.form_6252_ordinary_income = (
                tax_return.income.get_form_6252_ordinary_income()
            )
            # Unrecaptured Section 1250 gain (25% rate)
            breakdown.form_6252_unrecaptured_1250_gain = (
                tax_return.income.get_form_6252_unrecaptured_1250_gain()
            )
            # Section 453A interest charge (large installment sales)
            breakdown.form_6252_section_453a_interest = (
                tax_return.income.get_form_6252_section_453a_interest()
            )
            # Full breakdown
            breakdown.form_6252_breakdown = (
                tax_return.income.get_form_6252_summary() or {}
            )

        # Form 8582 Passive Activity Loss Limitations
        if tax_return.income.form_8582:
            # Total passive loss allowed
            breakdown.form_8582_passive_loss_allowed = (
                tax_return.income.get_form_8582_passive_loss_allowed()
            )
            # Suspended loss carryforward
            breakdown.form_8582_suspended_loss = (
                tax_return.income.get_form_8582_suspended_loss()
            )
            # Rental real estate allowance used
            breakdown.form_8582_rental_allowance = (
                tax_return.income.get_form_8582_rental_allowance()
            )
            # Net passive income
            breakdown.form_8582_net_passive_income = (
                tax_return.income.get_form_8582_net_passive_income()
            )
            # Full breakdown
            breakdown.form_8582_breakdown = (
                tax_return.income.get_form_8582_summary() or {}
            )

        # Schedule A - Itemized Deductions
        if tax_return.income.schedule_a:
            breakdown.schedule_a_total_deductions = (
                tax_return.income.get_schedule_a_total_deductions()
            )
            breakdown.schedule_a_medical_deduction = (
                tax_return.income.get_schedule_a_medical_deduction()
            )
            breakdown.schedule_a_salt_deduction = (
                tax_return.income.get_schedule_a_salt_deduction()
            )
            breakdown.schedule_a_charitable = (
                tax_return.income.get_schedule_a_charitable_deduction()
            )
            breakdown.schedule_a_breakdown = (
                tax_return.income.get_schedule_a_summary() or {}
            )

        # Schedule B - Interest and Ordinary Dividends
        if tax_return.income.schedule_b:
            breakdown.schedule_b_total_interest = (
                tax_return.income.get_schedule_b_total_interest()
            )
            breakdown.schedule_b_total_dividends = (
                tax_return.income.get_schedule_b_total_dividends()
            )
            breakdown.schedule_b_qualified_dividends = (
                tax_return.income.get_schedule_b_qualified_dividends()
            )
            breakdown.schedule_b_requires_part_iii = (
                tax_return.income.get_schedule_b_requires_part_iii()
            )
            breakdown.schedule_b_breakdown = (
                tax_return.income.get_schedule_b_summary() or {}
            )

        # Schedule D - Capital Gains and Losses
        if tax_return.income.schedule_d:
            breakdown.schedule_d_net_gain_loss = (
                tax_return.income.get_schedule_d_net_gain_loss()
            )
            breakdown.schedule_d_short_term_net = (
                tax_return.income.get_schedule_d_short_term_net()
            )
            breakdown.schedule_d_long_term_net = (
                tax_return.income.get_schedule_d_long_term_net()
            )
            breakdown.schedule_d_28_rate_gain = (
                tax_return.income.get_schedule_d_28_rate_gain()
            )
            breakdown.schedule_d_unrecaptured_1250 = (
                tax_return.income.get_schedule_d_unrecaptured_1250()
            )
            breakdown.schedule_d_breakdown = (
                tax_return.income.get_schedule_d_summary() or {}
            )

        # Schedule E - Supplemental Income and Loss
        if tax_return.income.schedule_e:
            breakdown.schedule_e_total = (
                tax_return.income.get_schedule_e_total()
            )
            breakdown.schedule_e_rental_income = (
                tax_return.income.get_schedule_e_rental_income()
            )
            breakdown.schedule_e_partnership_income = (
                tax_return.income.get_schedule_e_partnership_income()
            )
            breakdown.schedule_e_estate_trust_income = (
                tax_return.income.get_schedule_e_estate_trust_income()
            )
            breakdown.schedule_e_se_income = (
                tax_return.income.get_schedule_e_se_income()
            )
            breakdown.schedule_e_qbi = (
                tax_return.income.get_schedule_e_qbi()
            )
            breakdown.schedule_e_breakdown = (
                tax_return.income.get_schedule_e_summary() or {}
            )

        # Schedule F - Profit or Loss From Farming
        if tax_return.income.schedule_f:
            breakdown.schedule_f_net_profit_loss = (
                tax_return.income.get_schedule_f_net_profit_loss()
            )
            breakdown.schedule_f_gross_income = (
                tax_return.income.get_schedule_f_gross_income()
            )
            breakdown.schedule_f_expenses = (
                tax_return.income.get_schedule_f_expenses()
            )
            breakdown.schedule_f_se_income = (
                tax_return.income.get_schedule_f_se_income()
            )
            breakdown.schedule_f_breakdown = (
                tax_return.income.get_schedule_f_summary() or {}
            )

        # Form 6781 - Section 1256 Contracts and Straddles
        if tax_return.income.form_6781:
            breakdown.form_6781_section_1256_net = (
                tax_return.income.get_form_6781_section_1256_net()
            )
            breakdown.form_6781_short_term = (
                tax_return.income.get_form_6781_short_term()
            )
            breakdown.form_6781_long_term = (
                tax_return.income.get_form_6781_long_term()
            )
            breakdown.form_6781_straddle_net = (
                tax_return.income.get_form_6781_straddle_net()
            )
            breakdown.form_6781_breakdown = (
                tax_return.income.get_form_6781_summary() or {}
            )

        # Form 8814 - Parent's Election to Report Child's Income
        if tax_return.income.form_8814:
            breakdown.form_8814_income_to_include = (
                tax_return.income.get_form_8814_income_to_include()
            )
            breakdown.form_8814_child_tax = (
                tax_return.income.get_form_8814_child_tax()
            )
            breakdown.form_8814_qualifying_children = (
                tax_return.income.get_form_8814_qualifying_children_count()
            )
            breakdown.form_8814_breakdown = (
                tax_return.income.get_form_8814_summary() or {}
            )

        # Form 8995 - Qualified Business Income Deduction
        if tax_return.income.form_8995:
            breakdown.form_8995_qbi_deduction = (
                tax_return.income.get_form_8995_deduction()
            )
            breakdown.form_8995_below_threshold = (
                tax_return.income.get_form_8995_is_below_threshold()
            )
            breakdown.form_8995_loss_carryforward = (
                tax_return.income.get_form_8995_loss_carryforward()
            )
            breakdown.form_8995_breakdown = (
                tax_return.income.get_form_8995_summary() or {}
            )

        # Total tax before credits (includes HSA, IRA penalties, Form 5329, 1099-R, and 1099-Q penalties)
        # Note: 1099-R early distribution penalty is only added if Form 5329 is not handling it
        additional_1099r_penalty = 0.0
        if not tax_return.income.form_5329 and breakdown.form_1099r_early_distribution_penalty > 0:
            additional_1099r_penalty = breakdown.form_1099r_early_distribution_penalty

        breakdown.total_tax_before_credits = float(money(
            breakdown.ordinary_income_tax +
            breakdown.preferential_income_tax +
            breakdown.self_employment_tax +
            breakdown.additional_medicare_tax +
            breakdown.net_investment_income_tax +
            breakdown.alternative_minimum_tax +
            breakdown.hsa_additional_tax +
            breakdown.ira_early_withdrawal_penalty +
            breakdown.form_5329_total_additional_tax +
            additional_1099r_penalty +
            breakdown.form_1099q_penalty +  # 10% penalty on non-qualified 529/Coverdell distributions
            breakdown.form_4137_total_tax  # SS/Medicare tax on unreported tips (Form 4137)
        ))

        # Calculate credits
        breakdown.credit_breakdown = self._calculate_credits(tax_return, breakdown)
        breakdown.nonrefundable_credits = breakdown.credit_breakdown.get('total_nonrefundable', 0)
        breakdown.refundable_credits = breakdown.credit_breakdown.get('total_refundable', 0)
        breakdown.total_credits = breakdown.nonrefundable_credits + breakdown.refundable_credits

        # Store clean vehicle breakdown for easy access
        breakdown.clean_vehicle_breakdown = breakdown.credit_breakdown.get('clean_vehicle_breakdown', {})

        # Handle PTC repayment (excess APTC that must be paid back)
        breakdown.ptc_repayment = breakdown.credit_breakdown.get('ptc_repayment', 0.0)

        # Final tax (nonrefundable credits limited to tax, refundable can exceed)
        income_tax_after_nonrefundable = max(
            0,
            breakdown.total_tax_before_credits - breakdown.nonrefundable_credits
        )
        # Add PTC repayment to tax owed (BR-0901 to BR-0920)
        breakdown.total_tax = float(money(
            income_tax_after_nonrefundable - breakdown.refundable_credits + breakdown.ptc_repayment
        ))

        # Payments
        breakdown.total_payments = self._calculate_total_payments(tax_return)

        # Refund or amount owed
        breakdown.refund_or_owed = float(money(breakdown.total_tax - breakdown.total_payments))

        # Estimated tax penalty (Form 2210)
        penalty_result = self._calculate_estimated_tax_penalty(
            total_tax=breakdown.total_tax,
            total_payments=breakdown.total_payments,
            prior_year_tax=tax_return.income.prior_year_tax,
            prior_year_agi=tax_return.income.prior_year_agi,
            is_farmer_or_fisherman=tax_return.income.is_farmer_or_fisherman,
        )
        breakdown.estimated_tax_penalty = penalty_result['penalty']
        breakdown.safe_harbor_met = penalty_result['safe_harbor_met']
        breakdown.required_annual_payment = penalty_result['required_payment']

        # Effective and marginal rates
        if breakdown.agi > 0:
            breakdown.effective_tax_rate = float(money(breakdown.total_tax / breakdown.agi * 100))
        breakdown.marginal_tax_rate = self._get_marginal_rate(breakdown.taxable_income, filing_status)

        # Restore original adjustments
        tax_return.deductions.other_adjustments = original_other_adj
        tax_return.calculate()

        return breakdown

    def _calculate_self_employment_tax(
        self,
        tax_return: TaxReturn,
        filing_status: str
    ) -> Dict[str, float]:
        """
        Calculate self-employment tax with proper SS wage base cap.

        SE Tax = 12.4% Social Security (up to wage base) + 2.9% Medicare (no cap)
        SE Tax Deduction = 50% of SE tax (above-the-line adjustment)

        Includes:
        - Schedule C net profit
        - K-1 self-employment earnings from partnerships (BR-0701 to BR-0730)
        - K-1 guaranteed payments from partnerships

        Does NOT include:
        - S-Corporation K-1 income (not subject to SE tax)
        - Trust/Estate K-1 income
        """
        inc = tax_return.income

        # Schedule C net self-employment income (uses detailed or simple method)
        schedule_c_se = inc.get_schedule_c_se_income()
        net_se = max(0.0, schedule_c_se)

        # Add K-1 self-employment earnings from partnerships (BR-0701 to BR-0730)
        # Partnership K-1 Box 14 reports SE earnings
        k1_se_earnings = inc.get_k1_self_employment_income()
        net_se += k1_se_earnings

        # Calculate SE earnings (92.35% of net SE)
        se_earnings = net_se * self.config.se_net_earnings_factor  # 92.35%

        # Get W-2 wages for SS wage base consideration
        w2_wages = inc.get_total_wages()

        # Social Security portion (12.4%) - capped at wage base minus W-2 wages
        remaining_ss_base = max(0, self.config.ss_wage_base - w2_wages)
        ss_taxable_se = min(se_earnings, remaining_ss_base)
        ss_tax = float(money(ss_taxable_se * self.config.ss_rate))

        # Medicare portion (2.9%) - no cap
        medicare_tax = float(money(se_earnings * self.config.medicare_rate))

        total_se_tax = ss_tax + medicare_tax
        se_tax_deduction = float(money(total_se_tax / 2.0))

        return {
            'net_self_employment_income': float(money(net_se)),
            'schedule_c_income': float(money(schedule_c_se)),
            'k1_self_employment_income': float(money(k1_se_earnings)),
            'se_earnings_subject_to_tax': float(money(se_earnings)),
            'ss_wage_base': self.config.ss_wage_base,
            'w2_wages': float(money(w2_wages)),
            'remaining_ss_base': float(money(remaining_ss_base)),
            'ss_taxable_se_earnings': float(money(ss_taxable_se)),
            'social_security_tax': ss_tax,
            'medicare_tax': medicare_tax,
            'total_se_tax': float(money(total_se_tax)),
            'se_tax_deduction': se_tax_deduction,
            'schedule_c_businesses': inc.get_schedule_c_summary(),
        }

    def _calculate_additional_medicare_tax(
        self,
        tax_return: TaxReturn,
        filing_status: str
    ) -> float:
        """
        Calculate Additional Medicare Tax (0.9%) on wages and SE income over threshold.

        Applies to:
        - Wages over threshold
        - Self-employment income over threshold (after considering wages)
        """
        if not self.config.additional_medicare_threshold:
            return 0.0

        threshold = self.config.additional_medicare_threshold.get(filing_status, 200000.0)
        rate = self.config.additional_medicare_tax_rate

        # Total Medicare wages and SE income
        wages = tax_return.income.get_total_wages()
        net_se = max(0.0, tax_return.income.get_schedule_c_se_income())
        se_earnings = net_se * self.config.se_net_earnings_factor

        # Additional Medicare Tax on wages
        wages_over_threshold = max(0, wages - threshold)
        amt_on_wages = wages_over_threshold * rate

        # Additional Medicare Tax on SE (threshold reduced by wages)
        se_threshold = max(0, threshold - wages)
        se_over_threshold = max(0, se_earnings - se_threshold)
        amt_on_se = se_over_threshold * rate

        return float(money(amt_on_wages + amt_on_se))

    def _calculate_niit(
        self,
        tax_return: TaxReturn,
        filing_status: str
    ) -> float:
        """
        Calculate Net Investment Income Tax (3.8%).

        NIIT = 3.8% × lesser of:
        1. Net Investment Income
        2. MAGI over threshold

        Net Investment Income includes:
        - Interest, dividends, capital gains
        - Rental and royalty income (passive)
        - Crypto capital gains (BR-0601 to BR-0620)
        - K-1 passive income (BR-0701 to BR-0730)

        Does NOT include:
        - Wages, SE income (active business)
        - Crypto mining/staking if considered active trade
        - K-1 income from actively managed businesses
        """
        if not self.config.niit_threshold:
            return 0.0

        threshold = self.config.niit_threshold.get(filing_status, 200000.0)
        rate = self.config.niit_rate

        # Calculate Net Investment Income
        inc = tax_return.income
        nii = (
            inc.interest_income +
            inc.dividend_income +
            inc.short_term_capital_gains +
            inc.long_term_capital_gains +
            max(0, inc.rental_income - inc.rental_expenses) +
            inc.royalty_income +
            inc.other_investment_income
        )

        # Add crypto capital gains (BR-0601 to BR-0620)
        # Crypto gains are investment income for NIIT purposes
        nii += inc.get_crypto_short_term_gains()
        nii += inc.get_crypto_long_term_gains()
        # Subtract crypto losses (offset against gains)
        nii -= inc.get_crypto_short_term_losses()
        nii -= inc.get_crypto_long_term_losses()

        # Add K-1 investment income from passive activities (BR-0701 to BR-0730)
        for k1 in getattr(inc, 'schedule_k1_forms', []):
            if k1.is_passive_activity:
                # Passive K-1 income is subject to NIIT
                nii += k1.interest_income
                nii += k1.ordinary_dividends
                nii += k1.net_short_term_capital_gain
                nii += k1.net_long_term_capital_gain
                nii += k1.net_rental_real_estate + k1.other_rental_income
                nii += k1.royalties

        nii = max(0, nii)

        # MAGI over threshold (using AGI as approximation for MAGI)
        magi = tax_return.adjusted_gross_income or 0.0
        magi_over_threshold = max(0, magi - threshold)

        # Tax on lesser of NII or excess MAGI
        taxable_amount = min(nii, magi_over_threshold)

        return float(money(taxable_amount * rate))

    def _calculate_amt(
        self,
        tax_return: TaxReturn,
        filing_status: str,
        breakdown: CalculationBreakdown
    ) -> dict:
        """
        Calculate Alternative Minimum Tax (AMT) per Form 6251.

        AMT = max(0, Tentative Minimum Tax - Regular Tax)
        Tentative Minimum Tax = (AMTI - Exemption) × (26% up to threshold, 28% above)

        IRC Sections 55-59 govern AMT calculations.

        Uses Form 6251 model if available, otherwise calculates from
        individual AMT preference fields.

        Returns:
            Dict with 'amt', 'amti', 'exemption', 'tmt', and detailed breakdown
        """
        result = {
            'amt': 0.0,
            'amti': 0.0,
            'exemption_base': 0.0,
            'exemption_after_phaseout': 0.0,
            'amt_taxable_income': 0.0,
            'tmt': 0.0,
            'regular_tax': 0.0,
            # Adjustments (Form 6251 Part I)
            'salt_addback': 0.0,
            'standard_deduction_addback': 0.0,
            'iso_exercise_spread': 0.0,
            'private_activity_bond_interest': 0.0,
            'depreciation_adjustment': 0.0,
            'passive_activity_adjustment': 0.0,
            'loss_limitations_adjustment': 0.0,
            'other_adjustments': 0.0,
            'total_adjustments': 0.0,
            # Prior year credit
            'prior_year_amt_credit': 0.0,
            'amt_after_credit': 0.0,
            # Form 6251 detailed breakdown (if available)
            'form_6251_part_i': None,
            'form_6251_part_ii': None,
            'form_6251_part_iii': None,
        }

        if not self.config.amt_exemption:
            return result

        income = tax_return.income
        regular_tax = breakdown.ordinary_income_tax + breakdown.preferential_income_tax
        result['regular_tax'] = regular_tax

        # ============================================
        # Use Form 6251 if available
        # ============================================
        if income.form_6251:
            form = income.form_6251
            # Set taxable income and filing status
            form.taxable_income = breakdown.taxable_income
            form.filing_status = filing_status

            # Add SALT addback if itemizing
            if breakdown.deduction_type == "itemized" and hasattr(tax_return, 'deductions'):
                itemized = tax_return.deductions.itemized
                salt = min(
                    itemized.state_local_income_tax + itemized.state_local_sales_tax +
                    itemized.real_estate_tax + itemized.personal_property_tax,
                    self.config.salt_cap
                )
                form.line_2a_taxes = salt

            # Calculate using Form 6251 model
            amt_result = form.calculate_amt(
                regular_tax=regular_tax,
                regular_tax_capital_gains=breakdown.preferential_income_tax
            )

            # Map Form 6251 results to our result format
            result['amt'] = amt_result['amt']
            result['amti'] = amt_result['amti']
            result['exemption_base'] = amt_result['exemption_base']
            result['exemption_after_phaseout'] = amt_result['exemption_after_phaseout']
            result['amt_taxable_income'] = amt_result['amt_taxable_income']
            result['tmt'] = amt_result['tentative_minimum_tax']
            result['total_adjustments'] = amt_result['total_adjustments']
            result['salt_addback'] = amt_result.get('salt_addback', 0.0)
            result['iso_exercise_spread'] = amt_result.get('iso_spread', 0.0)
            result['private_activity_bond_interest'] = amt_result.get('pab_interest', 0.0)
            result['depreciation_adjustment'] = amt_result.get('depreciation_adjustment', 0.0)
            result['prior_year_amt_credit'] = form.prior_year_amt_credit
            result['amt_after_credit'] = amt_result.get('amt_after_credit', amt_result['amt'])

            # Include detailed breakdowns
            result['form_6251_part_i'] = amt_result.get('part_i')
            result['form_6251_part_ii'] = amt_result.get('part_ii')
            result['form_6251_part_iii'] = amt_result.get('part_iii')

            return result

        # ============================================
        # Fall back to individual field calculation
        # Use Decimal for precision in AMT calculations
        # ============================================
        exemption_base = to_decimal(self.config.amt_exemption.get(filing_status, 88100.0))
        phaseout_start = to_decimal(self.config.amt_exemption_phaseout_start.get(filing_status, 626350.0) if self.config.amt_exemption_phaseout_start else 626350.0)
        threshold_28 = to_decimal(self.config.amt_28_threshold.get(filing_status, 232600.0) if self.config.amt_28_threshold else 232600.0)

        result['exemption_base'] = to_float(exemption_base)

        # ============================================
        # Calculate AMTI (Alternative Minimum Taxable Income)
        # Start with taxable income and add back certain items
        # Use Decimal for all calculations to avoid rounding errors
        # ============================================
        amti = to_decimal(breakdown.taxable_income)

        # 1. SALT Addback (Form 6251 Line 2a) - if itemizing
        salt_addback = Decimal("0")
        if breakdown.deduction_type == "itemized" and hasattr(tax_return, 'deductions'):
            itemized = tax_return.deductions.itemized
            salt_total = to_decimal(
                itemized.state_local_income_tax + itemized.state_local_sales_tax +
                itemized.real_estate_tax + itemized.personal_property_tax
            )
            salt_cap = to_decimal(self.config.salt_cap)
            salt_addback = min_decimal(salt_total, salt_cap)
            amti = add(amti, salt_addback)
        result['salt_addback'] = to_float(salt_addback)

        # 2. Standard Deduction Addback (if used) - AMT doesn't allow standard deduction
        # But since we started with taxable income, we don't need to add it back
        # The AMTI computation effectively uses itemized deductions with modifications

        # 3. ISO Exercise Spread (Form 6251 Line 2i)
        # The spread between exercise price and FMV on ISO exercise
        iso_spread = to_decimal(getattr(income, 'amt_iso_exercise_spread', 0.0) or 0.0)
        amti = add(amti, iso_spread)
        result['iso_exercise_spread'] = to_float(iso_spread)

        # 4. Private Activity Bond Interest (Form 6251 Line 2g)
        # Tax-exempt interest from private activity bonds is a preference item
        pab_interest = to_decimal(getattr(income, 'amt_private_activity_bond_interest', 0.0) or 0.0)
        amti = add(amti, pab_interest)
        result['private_activity_bond_interest'] = to_float(pab_interest)

        # 5. Depreciation Adjustment (Form 6251 Line 2a)
        # Difference between regular MACRS and AMT ADS depreciation
        depreciation_adj = to_decimal(getattr(income, 'amt_depreciation_adjustment', 0.0) or 0.0)
        amti = add(amti, depreciation_adj)
        result['depreciation_adjustment'] = to_float(depreciation_adj)

        # 6. Passive Activity Loss Adjustment (Form 6251 Line 2e)
        passive_adj = to_decimal(getattr(income, 'amt_passive_activity_adjustment', 0.0) or 0.0)
        amti = add(amti, passive_adj)
        result['passive_activity_adjustment'] = to_float(passive_adj)

        # 7. Loss Limitations Adjustment (Form 6251 Line 2d)
        loss_adj = to_decimal(getattr(income, 'amt_loss_limitations_adjustment', 0.0) or 0.0)
        amti = add(amti, loss_adj)
        result['loss_limitations_adjustment'] = to_float(loss_adj)

        # 8. Other Preference Items - Use Decimal precision for all additions
        other_prefs = Decimal("0")
        other_prefs = add(other_prefs, to_decimal(getattr(income, 'amt_depletion_excess', 0.0) or 0.0))
        other_prefs = add(other_prefs, to_decimal(getattr(income, 'amt_intangible_drilling_costs', 0.0) or 0.0))
        other_prefs = add(other_prefs, to_decimal(getattr(income, 'amt_circulation_expenditures', 0.0) or 0.0))
        other_prefs = add(other_prefs, to_decimal(getattr(income, 'amt_mining_exploration_costs', 0.0) or 0.0))
        other_prefs = add(other_prefs, to_decimal(getattr(income, 'amt_research_experimental_costs', 0.0) or 0.0))
        other_prefs = add(other_prefs, to_decimal(getattr(income, 'amt_long_term_contracts', 0.0) or 0.0))
        other_prefs = add(other_prefs, to_decimal(getattr(income, 'amt_other_adjustments', 0.0) or 0.0))
        amti = add(amti, other_prefs)
        result['other_adjustments'] = to_float(other_prefs)

        # Total adjustments
        total_adjustments = salt_addback
        total_adjustments = add(total_adjustments, iso_spread)
        total_adjustments = add(total_adjustments, pab_interest)
        total_adjustments = add(total_adjustments, depreciation_adj)
        total_adjustments = add(total_adjustments, passive_adj)
        total_adjustments = add(total_adjustments, loss_adj)
        total_adjustments = add(total_adjustments, other_prefs)
        result['total_adjustments'] = to_float(total_adjustments)
        result['amti'] = to_float(amti)

        # ============================================
        # Calculate AMT Exemption with Phaseout
        # Exemption phases out at 25 cents per dollar over threshold
        # Use Decimal for precise phaseout calculation
        # ============================================
        exemption = exemption_base
        if amti > phaseout_start:
            excess = subtract(amti, phaseout_start)
            phaseout_rate = to_decimal(self.config.amt_exemption_phaseout_rate)
            exemption_reduction = multiply(excess, phaseout_rate)
            exemption = max_decimal(Decimal("0"), subtract(exemption_base, exemption_reduction))
        result['exemption_after_phaseout'] = to_float(exemption)

        # ============================================
        # Calculate Tentative Minimum Tax
        # 26% on first $232,600, 28% on remainder (2025 thresholds)
        # Use Decimal to avoid rounding errors in rate calculations
        # ============================================
        amt_taxable = max_decimal(Decimal("0"), subtract(amti, exemption))
        result['amt_taxable_income'] = to_float(amt_taxable)

        amt_rate_26 = to_decimal(self.config.amt_rate_26)
        amt_rate_28 = to_decimal(self.config.amt_rate_28)

        if amt_taxable <= threshold_28:
            tmt = multiply(amt_taxable, amt_rate_26)
        else:
            # Two-bracket calculation: 26% up to threshold, 28% above
            first_bracket = multiply(threshold_28, amt_rate_26)
            excess_amount = subtract(amt_taxable, threshold_28)
            second_bracket = multiply(excess_amount, amt_rate_28)
            tmt = add(first_bracket, second_bracket)

        # Round TMT to cents
        tmt = money(tmt)
        result['tmt'] = to_float(tmt)

        # ============================================
        # Compare to Regular Tax
        # AMT is excess of TMT over regular tax
        # ============================================
        regular_tax_decimal = to_decimal(regular_tax)
        amt = max_decimal(Decimal("0"), subtract(tmt, regular_tax_decimal))
        amt = money(amt)  # Round to cents
        result['amt'] = to_float(amt)

        # ============================================
        # Apply Prior Year AMT Credit (Form 8801)
        # ============================================
        prior_credit = to_decimal(getattr(income, 'prior_year_amt_credit', 0.0) or 0.0)
        result['prior_year_amt_credit'] = to_float(prior_credit)

        # Prior year credit can offset regular tax but not below TMT
        # This is complex - simplified: reduce AMT by credit (not quite right but close)
        amt_after_credit = max_decimal(Decimal("0"), subtract(amt, prior_credit))
        amt_after_credit = money(amt_after_credit)
        result['amt_after_credit'] = to_float(amt_after_credit)

        return result

    def _calculate_minimum_tax_credit(
        self,
        tax_return: TaxReturn,
        filing_status: str,
        breakdown: CalculationBreakdown,
        amt_result: dict
    ) -> dict:
        """
        Calculate Minimum Tax Credit (MTC) per Form 8801.

        The MTC allows recovery of AMT paid in prior years on "deferral" items
        (timing differences that reverse, like ISO exercises and depreciation).

        The credit can reduce regular tax, but not below the tentative minimum tax.

        IRC Section 53 governs the minimum tax credit.

        Returns:
            Dict with credit calculation and carryforward
        """
        income = tax_return.income
        result = {
            'credit_available': 0.0,
            'credit_limit': 0.0,
            'credit_allowed': 0.0,
            'carryforward': 0.0,
            'from_prior_years': 0.0,
            'from_form_8801': False,
        }

        # Get regular tax and TMT from AMT calculation
        regular_tax = amt_result.get('regular_tax', 0.0)
        tmt = amt_result.get('tmt', 0.0)

        # Calculate credit limit: regular tax can be reduced to TMT, not below
        credit_limit = max(0, regular_tax - tmt)
        result['credit_limit'] = float(money(credit_limit))

        # Use Form 8801 if available
        if income.form_8801:
            form = income.form_8801
            # Update form with current year figures
            form.current_year_regular_tax = regular_tax
            form.current_year_tmt = tmt
            form.current_year_amt = amt_result.get('amt', 0.0)
            form.filing_status = filing_status
            form.line_1_amti = amt_result.get('amti', 0.0)

            # Populate deferral item adjustments for Part I
            # These are negative to remove from AMTI
            form.line_5_depreciation = -amt_result.get('depreciation_adjustment', 0.0)
            form.line_7_iso = -amt_result.get('iso_exercise_spread', 0.0)

            # Calculate using Form 8801
            credit_result = form.calculate_credit()

            result['credit_available'] = credit_result['total_mtc_available']
            result['credit_allowed'] = credit_result['minimum_tax_credit']
            result['carryforward'] = credit_result['carryforward']
            result['from_prior_years'] = credit_result['from_prior_years']
            result['from_form_8801'] = True

            # Include detailed breakdown
            result['part_i'] = credit_result.get('part_i')
            result['part_ii'] = credit_result.get('part_ii')
            result['exclusion_tmt'] = credit_result.get('exclusion_tmt', 0.0)

            return result

        # Fall back to simple calculation using prior_year_amt_credit
        prior_credit = getattr(income, 'prior_year_amt_credit', 0.0) or 0.0
        result['credit_available'] = prior_credit
        result['from_prior_years'] = prior_credit

        # Credit allowed is lesser of available and limit
        credit_allowed = min(prior_credit, credit_limit)
        result['credit_allowed'] = float(money(credit_allowed))

        # Carryforward is unused credit
        result['carryforward'] = float(money(prior_credit - credit_allowed))

        return result

    def _calculate_passive_activity_loss(
        self,
        tax_return: TaxReturn,
        filing_status: str,
        agi: float
    ) -> dict:
        """
        Calculate Passive Activity Loss (PAL) limitations per Form 8582 / IRC Section 469.

        Key Rules:
        1. Passive losses can only offset passive income (general rule)
        2. $25,000 rental loss exception for active participants (IRC 469(i))
        3. $25k exception phases out at 50% for AGI $100k-$150k
        4. Real estate professionals: rentals treated as non-passive (IRC 469(c)(7))
        5. Suspended losses carry forward until activity disposition

        Returns:
            Dict with PAL breakdown including allowable losses and suspended amounts
        """
        income = tax_return.income

        result = {
            'rental_income': 0.0,
            'rental_loss': 0.0,
            'net_rental_result': 0.0,
            'passive_business_income': 0.0,
            'passive_business_loss': 0.0,
            'net_passive_business': 0.0,
            'k1_passive_income': 0.0,
            'k1_passive_loss': 0.0,
            'total_passive_income': 0.0,
            'total_passive_loss': 0.0,
            'net_passive_result': 0.0,
            # $25k allowance
            'rental_loss_allowance_base': 0.0,
            'rental_loss_allowance_after_phaseout': 0.0,
            'agi_for_phaseout': agi,
            # Disposition release
            'disposition_gain_loss': 0.0,
            'suspended_loss_released': 0.0,
            # Final results
            'allowable_passive_loss': 0.0,
            'suspended_current_year': 0.0,
            'suspended_carryforward_used': 0.0,
            'new_suspended_carryforward': 0.0,
            # Status flags
            'is_active_participant': False,
            'is_real_estate_professional': False,
            'qualifies_for_25k_allowance': False,
        }

        # ============================================
        # Step 1: Aggregate Rental Activity Income/Loss
        # ============================================
        rental_income = getattr(income, 'rental_income', 0.0) or 0.0
        rental_expenses = getattr(income, 'rental_expenses', 0.0) or 0.0
        net_rental = rental_income - rental_expenses

        result['rental_income'] = rental_income
        result['rental_loss'] = rental_expenses if net_rental < 0 else 0.0
        result['net_rental_result'] = net_rental

        # ============================================
        # Step 2: Aggregate Passive Business Activities
        # ============================================
        passive_biz_income = getattr(income, 'passive_business_income', 0.0) or 0.0
        passive_biz_loss = getattr(income, 'passive_business_losses', 0.0) or 0.0
        net_passive_biz = passive_biz_income - passive_biz_loss

        result['passive_business_income'] = passive_biz_income
        result['passive_business_loss'] = passive_biz_loss
        result['net_passive_business'] = net_passive_biz

        # ============================================
        # Step 3: Aggregate K-1 Passive Activities
        # ============================================
        k1_passive_income = 0.0
        k1_passive_loss = 0.0

        for k1 in getattr(income, 'schedule_k1_forms', []):
            if getattr(k1, 'is_passive_activity', True):
                # Sum all K-1 passive income components
                k1_income = (
                    (getattr(k1, 'ordinary_business_income', 0.0) or 0.0) +
                    (getattr(k1, 'net_rental_real_estate', 0.0) or 0.0) +
                    (getattr(k1, 'other_rental_income', 0.0) or 0.0) +
                    (getattr(k1, 'guaranteed_payments', 0.0) or 0.0)
                )
                if k1_income > 0:
                    k1_passive_income += k1_income
                else:
                    k1_passive_loss += abs(k1_income)

        result['k1_passive_income'] = k1_passive_income
        result['k1_passive_loss'] = k1_passive_loss

        # ============================================
        # Step 4: Calculate Total Passive Income/Loss
        # For PAL purposes, we use NET results from each activity:
        # - Rental: only contributes if net is positive (income) or negative (loss)
        # - Passive business: net of income minus loss
        # - K-1: already separated into income vs loss components
        # ============================================
        # Rental contributes its net result (not gross income/expenses separately)
        rental_passive_income = max(0, net_rental)  # Only if positive
        rental_passive_loss = abs(min(0, net_rental))  # Only if negative

        total_passive_income = rental_passive_income + passive_biz_income + k1_passive_income
        total_passive_loss = rental_passive_loss + passive_biz_loss + k1_passive_loss

        result['total_passive_income'] = total_passive_income
        result['total_passive_loss'] = total_passive_loss
        result['net_passive_result'] = total_passive_income - total_passive_loss

        # ============================================
        # Step 5: Check Real Estate Professional Status
        # ============================================
        is_re_professional = getattr(income, 'is_real_estate_professional', False)
        re_hours = getattr(income, 'real_estate_professional_hours', 0.0) or 0.0

        # IRC 469(c)(7): 750+ hours AND more than 50% of personal services
        if is_re_professional or re_hours >= self.config.pal_real_estate_professional_hours:
            result['is_real_estate_professional'] = True
            # Real estate professional: rental activities are NOT passive
            # All rental losses are fully deductible
            result['allowable_passive_loss'] = total_passive_loss
            result['suspended_current_year'] = 0.0
            return result

        # ============================================
        # Step 6: Check Active Participation (for $25k allowance)
        # ============================================
        is_active_participant = getattr(income, 'is_active_participant_rental', True)
        result['is_active_participant'] = is_active_participant

        # ============================================
        # Step 7: Calculate $25,000 Rental Loss Allowance
        # IRC 469(i): Active participants can deduct up to $25k of rental losses
        # Phases out at 50 cents per dollar for AGI $100k-$150k
        # ============================================
        rental_loss_allowance = 0.0

        if is_active_participant and net_rental < 0:
            rental_loss = abs(net_rental)
            base_allowance = min(rental_loss, self.config.pal_rental_loss_allowance)
            result['rental_loss_allowance_base'] = base_allowance

            # Apply AGI phaseout
            if agi <= self.config.pal_phaseout_start:
                rental_loss_allowance = base_allowance
                result['qualifies_for_25k_allowance'] = True
            elif agi >= self.config.pal_phaseout_end:
                rental_loss_allowance = 0.0
                result['qualifies_for_25k_allowance'] = False
            else:
                # Linear phaseout: 50 cents per dollar over $100k
                excess_agi = agi - self.config.pal_phaseout_start
                reduction = excess_agi * self.config.pal_phaseout_rate
                rental_loss_allowance = max(0, base_allowance - reduction)
                result['qualifies_for_25k_allowance'] = rental_loss_allowance > 0

        result['rental_loss_allowance_after_phaseout'] = float(money(rental_loss_allowance))

        # ============================================
        # Step 8: Calculate Passive Loss Netting
        # Passive losses offset passive income first
        # ============================================
        net_passive = total_passive_income - total_passive_loss

        if net_passive >= 0:
            # Net passive income - no loss limitation needed
            result['allowable_passive_loss'] = total_passive_loss
            result['suspended_current_year'] = 0.0
        else:
            # Net passive loss - apply limitations
            passive_loss_amount = abs(net_passive)

            # Passive losses can offset passive income
            offset_by_income = total_passive_income

            # Plus $25k rental allowance (if applicable)
            allowable_loss = offset_by_income + rental_loss_allowance

            # Plus any suspended losses released on disposition
            disposition = getattr(income, 'passive_activity_dispositions', 0.0) or 0.0
            if disposition != 0:
                result['disposition_gain_loss'] = disposition
                # On complete disposition, release all suspended losses
                suspended_cf = (
                    (getattr(income, 'suspended_passive_loss_carryforward', 0.0) or 0.0) +
                    (getattr(income, 'suspended_rental_loss_carryforward', 0.0) or 0.0)
                )
                result['suspended_loss_released'] = suspended_cf
                allowable_loss += suspended_cf

            # Cap allowable loss at actual passive loss
            allowable_loss = min(allowable_loss, passive_loss_amount)
            suspended = max(0, passive_loss_amount - allowable_loss)

            result['allowable_passive_loss'] = float(money(allowable_loss))
            result['suspended_current_year'] = float(money(suspended))
            result['new_suspended_carryforward'] = float(money(suspended))

        return result

    def _calculate_depreciation(
        self,
        tax_return: TaxReturn,
        tax_year: int
    ) -> dict:
        """
        Calculate MACRS depreciation for all depreciable assets per Form 4562.

        Implements:
        - MACRS General Depreciation System (GDS) per IRC Section 168
        - 200% declining balance (3, 5, 7, 10-year property)
        - 150% declining balance (15, 20-year property)
        - Straight-line (27.5, 39-year real property)
        - Section 179 immediate expensing (IRC Section 179)
        - Bonus depreciation (IRC Section 168(k))
        - Half-year, mid-quarter, and mid-month conventions
        - Listed property restrictions

        Returns:
            Dict with total depreciation, Section 179, bonus, and per-asset breakdown
        """
        income = tax_return.income
        config = self.config

        result = {
            'total_depreciation': 0.0,
            'total_section_179': 0.0,
            'total_bonus_depreciation': 0.0,
            'total_macrs_depreciation': 0.0,
            'section_179_limit': config.section_179_limit,
            'section_179_used': 0.0,
            'bonus_depreciation_rate': config.bonus_depreciation_rate,
            'asset_count': 0,
            'asset_details': [],
        }

        assets = getattr(income, 'depreciable_assets', [])
        if not assets:
            return result

        result['asset_count'] = len(assets)

        # MACRS Depreciation Tables (200% DB, half-year convention)
        # These are the standard IRS percentage tables from Pub. 946
        macrs_tables = {
            # 3-year property (200% DB, half-year)
            "3": [0.3333, 0.4445, 0.1481, 0.0741],
            # 5-year property (200% DB, half-year)
            "5": [0.2000, 0.3200, 0.1920, 0.1152, 0.1152, 0.0576],
            # 7-year property (200% DB, half-year)
            "7": [0.1429, 0.2449, 0.1749, 0.1249, 0.0893, 0.0892, 0.0893, 0.0446],
            # 10-year property (200% DB, half-year)
            "10": [0.1000, 0.1800, 0.1440, 0.1152, 0.0922, 0.0737, 0.0655, 0.0655, 0.0656, 0.0655, 0.0328],
            # 15-year property (150% DB, half-year)
            "15": [0.0500, 0.0950, 0.0855, 0.0770, 0.0693, 0.0623, 0.0590, 0.0590, 0.0591, 0.0590, 0.0591, 0.0590, 0.0591, 0.0590, 0.0591, 0.0295],
            # 20-year property (150% DB, half-year)
            "20": [0.0375, 0.0722, 0.0668, 0.0618, 0.0571, 0.0528, 0.0489, 0.0452, 0.0447, 0.0447, 0.0446, 0.0446, 0.0446, 0.0446, 0.0446, 0.0446, 0.0446, 0.0446, 0.0446, 0.0446, 0.0223],
        }

        # Track Section 179 limit (can be phased out by total property purchases)
        total_property_placed = sum(a.cost_basis for a in assets)
        section_179_available = config.section_179_limit
        if total_property_placed > config.section_179_phaseout_threshold:
            excess = total_property_placed - config.section_179_phaseout_threshold
            section_179_available = max(0, section_179_available - excess)

        total_section_179 = 0.0
        total_bonus = 0.0
        total_macrs = 0.0

        for asset in assets:
            asset_detail = {
                'description': asset.description,
                'cost_basis': asset.cost_basis,
                'property_class': asset.property_class.value,
                'section_179': 0.0,
                'bonus_depreciation': 0.0,
                'macrs_depreciation': 0.0,
                'total_depreciation': 0.0,
                'depreciable_basis': 0.0,
                'year_in_service': 1,
            }

            # Skip disposed assets (partial year handled separately)
            if asset.disposed:
                asset_detail['note'] = 'Disposed during year - partial depreciation'
                result['asset_details'].append(asset_detail)
                continue

            # Calculate business-use adjusted basis
            business_basis = asset.cost_basis * (asset.business_use_percentage / 100)

            # Listed property check - must be >50% business use for MACRS
            if asset.is_listed_property and asset.business_use_percentage <= config.listed_property_min_business_use:
                asset_detail['note'] = f'Listed property <{config.listed_property_min_business_use}% business use - ADS required'
                # Would use ADS (straight-line) instead - simplified: no depreciation
                result['asset_details'].append(asset_detail)
                continue

            # ============================================
            # Section 179 Expensing
            # ============================================
            section_179_for_asset = 0.0
            if asset.section_179_amount > 0:
                # Can't exceed remaining Section 179 limit
                available_179 = max(0, section_179_available - total_section_179)
                # Can't exceed business basis
                section_179_for_asset = min(asset.section_179_amount, available_179, business_basis)
                total_section_179 += section_179_for_asset
                asset_detail['section_179'] = float(money(section_179_for_asset))

            # Reduce basis for Section 179
            remaining_basis = business_basis - section_179_for_asset

            # ============================================
            # Bonus Depreciation (IRC Section 168(k))
            # ============================================
            bonus_for_asset = 0.0
            if not asset.opted_out_bonus and remaining_basis > 0:
                # Real property (27.5, 39-year) is NOT eligible for bonus depreciation
                if asset.property_class.value not in ["27.5", "39"]:
                    if asset.bonus_depreciation_amount > 0:
                        # Use specified amount (capped at remaining basis)
                        bonus_for_asset = min(asset.bonus_depreciation_amount, remaining_basis)
                    else:
                        # Calculate bonus at current rate
                        bonus_for_asset = remaining_basis * config.bonus_depreciation_rate
                    total_bonus += bonus_for_asset
                    asset_detail['bonus_depreciation'] = float(money(bonus_for_asset))

            # Reduce basis for bonus depreciation
            remaining_basis -= bonus_for_asset
            asset_detail['depreciable_basis'] = float(money(remaining_basis))

            # ============================================
            # MACRS Depreciation
            # ============================================
            macrs_for_asset = 0.0
            if remaining_basis > 0:
                prop_class = asset.property_class.value

                # Determine year in recovery period
                # Parse date_placed_in_service to determine year
                try:
                    placed_year = int(asset.date_placed_in_service[:4])
                    year_in_service = tax_year - placed_year + 1  # Year 1 is year placed in service
                except (ValueError, IndexError):
                    year_in_service = 1  # Default to first year

                asset_detail['year_in_service'] = year_in_service

                # Real property uses mid-month convention and straight-line
                if prop_class == "27.5":
                    # Residential rental: 27.5 years straight-line, mid-month
                    annual_rate = 1.0 / 27.5
                    if year_in_service == 1:
                        # Mid-month: assume average of 6.5 months
                        macrs_for_asset = remaining_basis * annual_rate * (6.5 / 12)
                    elif year_in_service <= 28:
                        macrs_for_asset = remaining_basis * annual_rate
                    # After 27.5 years, may have partial year
                elif prop_class == "39":
                    # Nonresidential real property: 39 years straight-line, mid-month
                    annual_rate = 1.0 / 39.0
                    if year_in_service == 1:
                        macrs_for_asset = remaining_basis * annual_rate * (6.5 / 12)
                    elif year_in_service <= 39:
                        macrs_for_asset = remaining_basis * annual_rate
                else:
                    # Personal property uses table percentages
                    table = macrs_tables.get(prop_class, macrs_tables["7"])
                    if 1 <= year_in_service <= len(table):
                        rate = table[year_in_service - 1]
                        # For years after first, use original depreciable basis
                        # (before this year's depreciation)
                        macrs_for_asset = remaining_basis * rate
                    # After recovery period, no more depreciation

                total_macrs += macrs_for_asset
                asset_detail['macrs_depreciation'] = float(money(macrs_for_asset))

            # Total depreciation for this asset
            total_for_asset = section_179_for_asset + bonus_for_asset + macrs_for_asset
            asset_detail['total_depreciation'] = float(money(total_for_asset))
            result['asset_details'].append(asset_detail)

        # Populate summary totals
        result['total_section_179'] = float(money(total_section_179))
        result['section_179_used'] = float(money(total_section_179))
        result['total_bonus_depreciation'] = float(money(total_bonus))
        result['total_macrs_depreciation'] = float(money(total_macrs))
        result['total_depreciation'] = float(money(total_section_179 + total_bonus + total_macrs))

        return result

    def _compute_ordinary_income_tax(
        self,
        taxable_income: float,
        filing_status: str,
        return_breakdown: bool = False
    ):
        """Calculate ordinary income tax using progressive brackets."""
        if taxable_income <= 0:
            if return_breakdown:
                return 0.0, []
            return 0.0

        brackets = self.config.ordinary_income_brackets.get(
            filing_status, self.config.ordinary_income_brackets["single"]
        )

        tax = 0.0
        breakdown = []

        for idx, (floor, rate) in enumerate(brackets):
            if idx == len(brackets) - 1:
                # Top bracket
                amount = max(0.0, taxable_income - floor)
                bracket_tax = amount * rate
                tax += bracket_tax
                if amount > 0:
                    breakdown.append({
                        'bracket': f'{rate*100:.0f}%',
                        'floor': floor,
                        'ceiling': None,
                        'income_in_bracket': float(money(amount)),
                        'tax': float(money(bracket_tax)),
                        'rate': rate
                    })
                break

            next_floor = brackets[idx + 1][0]
            amount = min(max(taxable_income - floor, 0.0), next_floor - floor)
            bracket_tax = amount * rate
            tax += bracket_tax

            if amount > 0:
                breakdown.append({
                    'bracket': f'{rate*100:.0f}%',
                    'floor': floor,
                    'ceiling': next_floor,
                    'income_in_bracket': float(money(amount)),
                    'tax': float(money(bracket_tax)),
                    'rate': rate
                })

        if return_breakdown:
            return float(money(tax)), breakdown
        return float(money(tax))

    def _maybe_compute_taxable_social_security(self, tax_return: TaxReturn) -> None:
        """
        Compute taxable Social Security using provisional income formula.

        Per IRS Publication 915:
        - Provisional Income = Modified AGI + Tax-Exempt Interest + (0.5 × SS Benefits)
        - Tier 1: 0% taxable if provisional <= base1
        - Tier 2: 50% of excess over base1 if base1 < provisional <= base2
        - Tier 3: 85% formula if provisional > base2, capped at 85% of benefits
        """
        inc = tax_return.income
        if inc.social_security_benefits <= 0:
            return
        if inc.taxable_social_security and inc.taxable_social_security > 0:
            return

        filing_status = tax_return.taxpayer.filing_status.value

        # Base amounts from config (IRS Pub. 915)
        if filing_status in ("single", "head_of_household", "qualifying_widow"):
            base1 = self.config.ss_base1_single
            base2 = self.config.ss_base2_single
            lesser_cap = self.config.ss_lesser_cap_single
        elif filing_status == "married_joint":
            base1 = self.config.ss_base1_mfj
            base2 = self.config.ss_base2_mfj
            lesser_cap = self.config.ss_lesser_cap_mfj
        else:  # married_separate - harshest treatment (0 base amounts)
            base1, base2, lesser_cap = 0.0, 0.0, 0.0

        # Provisional income includes ALL income sources
        non_ss_income = (
            # W-2 wages
            inc.get_total_wages() +
            # Self-employment (net) - Schedule C or simple
            max(0, inc.get_schedule_c_net_profit()) +
            # Investment income
            inc.interest_income +
            inc.dividend_income +
            # Capital gains (direct)
            inc.short_term_capital_gains +
            inc.long_term_capital_gains +
            # Rental (net)
            max(0, inc.rental_income - inc.rental_expenses) +
            # Retirement
            inc.retirement_income +
            # Unemployment
            inc.unemployment_compensation +
            # Other
            inc.other_income +
            # K-1 pass-through income
            inc.get_k1_ordinary_income() +
            inc.get_k1_preferential_income() +
            # Crypto income (net of losses)
            inc.get_crypto_ordinary_income() +
            inc.get_crypto_short_term_gains() +
            inc.get_crypto_long_term_gains() -
            inc.get_crypto_short_term_losses() -
            inc.get_crypto_long_term_losses() +
            # Gambling winnings
            inc.get_total_gambling_winnings()
        )
        provisional = non_ss_income + inc.tax_exempt_interest + 0.5 * inc.social_security_benefits

        # Calculate taxable portion based on tier
        if provisional <= base1:
            # Tier 1: No SS benefits taxable
            taxable = 0.0
        elif provisional <= base2:
            # Tier 2: 50% of excess over base1
            taxable = 0.5 * (provisional - base1)
        else:
            # Tier 3: 85% formula with lesser cap
            taxable = 0.85 * (provisional - base2) + min(lesser_cap, 0.5 * (provisional - base1))
            # Cap at 85% of total benefits
            taxable = min(taxable, 0.85 * inc.social_security_benefits)

        inc.taxable_social_security = float(money(max(0.0, min(taxable, inc.social_security_benefits))))

    def _split_taxable_income(self, tax_return: TaxReturn) -> tuple[float, float]:
        """
        Split taxable income into ordinary and preferential portions.

        Preferential income (taxed at 0%/15%/20%):
        - Qualified dividends
        - Long-term capital gains (including crypto held > 1 year)
        - K-1 qualified dividends and long-term gains

        Ordinary income (taxed at regular rates):
        - All other income
        - Short-term capital gains (including crypto held <= 1 year)
        - Crypto mining/staking/airdrop income
        """
        ti = tax_return.taxable_income or 0.0
        inc = tax_return.income

        # Base preferential income
        pref = inc.qualified_dividends + inc.long_term_capital_gains

        # Add crypto long-term gains (BR-0601 to BR-0620)
        pref += inc.get_crypto_long_term_gains()

        # Add K-1 preferential income (BR-0701 to BR-0730)
        pref += inc.get_k1_qualified_dividends()
        st_k1, lt_k1 = inc.get_k1_capital_gains()
        pref += lt_k1

        pref = max(0.0, min(pref, ti))
        ordinary = max(0.0, ti - pref)
        return float(money(ordinary)), float(money(pref))

    def _compute_preferential_tax(
        self,
        filing_status: str,
        ordinary_taxable_income: float,
        preferential_taxable_income: float,
    ) -> float:
        """Compute tax on qualified dividends + LTCG at preferential rates (0%, 15%, 20%)."""
        if preferential_taxable_income <= 0:
            return 0.0

        if not self.config.qd_ltcg_0_rate_threshold or not self.config.qd_ltcg_15_rate_threshold:
            # Fallback: tax at ordinary rates
            return self._compute_ordinary_income_tax(
                ordinary_taxable_income + preferential_taxable_income, filing_status
            ) - self._compute_ordinary_income_tax(ordinary_taxable_income, filing_status)

        t0 = self.config.qd_ltcg_0_rate_threshold.get(filing_status)
        t15 = self.config.qd_ltcg_15_rate_threshold.get(filing_status)

        if t0 is None or t15 is None:
            return self._compute_ordinary_income_tax(
                ordinary_taxable_income + preferential_taxable_income, filing_status
            ) - self._compute_ordinary_income_tax(ordinary_taxable_income, filing_status)

        # Stack preferential income on top of ordinary income
        remaining = preferential_taxable_income
        tax = 0.0

        # 0% band capacity
        cap0 = max(0.0, t0 - ordinary_taxable_income)
        amt0 = min(remaining, cap0)
        remaining -= amt0  # 0% rate, no tax added

        # 15% band capacity
        cap15 = max(0.0, t15 - max(ordinary_taxable_income, t0))
        amt15 = min(remaining, cap15)
        tax += amt15 * 0.15
        remaining -= amt15

        # 20% on the rest
        if remaining > 0:
            tax += remaining * 0.20

        return float(money(tax))

    def _calculate_credits(
        self,
        tax_return: TaxReturn,
        breakdown: CalculationBreakdown
    ) -> Dict[str, float]:
        """
        Calculate tax credits (nonrefundable and refundable).

        Implements:
        - Child Tax Credit (CTC) and Additional CTC (BR-0023 to BR-0027)
        - Other Dependent Credit (ODC)
        - Earned Income Credit (EITC)
        - Education Credits: AOTC and LLC (BR-0801 to BR-0830)
        - Premium Tax Credit (Form 8962)
        - Foreign Tax Credit (Form 1116)
        - Child and Dependent Care Credit
        - Retirement Savings Contribution Credit
        """
        credits = tax_return.credits if hasattr(tax_return, 'credits') else None
        result = {
            'child_tax_credit': 0.0,
            'additional_child_tax_credit': 0.0,
            'other_dependent_credit': 0.0,
            'earned_income_credit': 0.0,
            'child_care_credit': 0.0,
            'education_credit_nonrefundable': 0.0,
            'education_credit_refundable': 0.0,
            'education_credit_type': None,
            'premium_tax_credit': 0.0,
            'ptc_advance_received': 0.0,
            'ptc_net_adjustment': 0.0,
            'foreign_tax_credit': 0.0,
            'foreign_tax_credit_carryforward': 0.0,
            'retirement_savings_credit': 0.0,
            'other_nonrefundable': 0.0,
            'other_refundable': 0.0,
            'total_nonrefundable': 0.0,
            'total_refundable': 0.0,
        }

        if not credits:
            return result

        filing_status = breakdown.filing_status

        # Validate dependents using the qualification tests (BR-0023 to BR-0027, BR3-0206 to BR3-0212)
        taxpayer_agi = breakdown.agi
        num_ctc_children = 0
        num_other_dependents = 0

        if hasattr(tax_return, 'taxpayer') and tax_return.taxpayer.dependents:
            # Use proper dependent qualification tests
            num_ctc_children = get_ctc_qualifying_children(tax_return.taxpayer, taxpayer_agi)
            num_other_dependents = get_other_dependents_count(tax_return.taxpayer, taxpayer_agi)
        else:
            # Fallback to credits model if no taxpayer dependents
            num_ctc_children = getattr(credits, 'num_qualifying_children', 0)

        # Child Tax Credit (nonrefundable portion) - BR-0023 to BR-0027
        num_children = num_ctc_children
        if num_children > 0 and self.config.child_tax_credit_phaseout_start:
            base_ctc = num_children * self.config.child_tax_credit_amount
            phaseout_start = self.config.child_tax_credit_phaseout_start.get(filing_status, 200000.0)
            if breakdown.agi > phaseout_start:
                excess = breakdown.agi - phaseout_start
                # IRS: $50 reduction per $1,000 OR FRACTION THEREOF (round UP)
                # Use ceiling division: (excess + 999) // 1000
                excess_thousands = (int(excess) + 999) // 1000
                reduction = excess_thousands * 50
                base_ctc = max(0, base_ctc - reduction)
            result['child_tax_credit'] = min(base_ctc, breakdown.total_tax_before_credits)

            # Additional Child Tax Credit (refundable portion)
            unused_ctc = base_ctc - result['child_tax_credit']
            if unused_ctc > 0:
                result['additional_child_tax_credit'] = min(
                    unused_ctc,
                    self.config.child_tax_credit_refundable * num_children
                )

        # Other Dependent Credit (ODC) - $500 per qualifying relative or child 17+
        if num_other_dependents > 0:
            odc_amount = num_other_dependents * 500  # $500 per other dependent
            # ODC subject to same phaseout as CTC
            if self.config.child_tax_credit_phaseout_start:
                phaseout_start = self.config.child_tax_credit_phaseout_start.get(filing_status, 200000.0)
                if breakdown.agi > phaseout_start:
                    excess = breakdown.agi - phaseout_start
                    excess_thousands = (int(excess) + 999) // 1000
                    reduction = excess_thousands * 50
                    odc_amount = max(0, odc_amount - reduction)
            result['other_dependent_credit'] = float(money(odc_amount))

        # Earned Income Credit (refundable) - uses proper QC validation (BR-0023 to BR-0027)
        eitc = self._calculate_eitc(tax_return, filing_status, taxpayer_agi)
        result['earned_income_credit'] = eitc

        # Education Credits (BR-0801 to BR-0830: AOTC and LLC)
        if hasattr(credits, 'students') and credits.students:
            # Use the comprehensive education credit calculations
            credit_type, nonref, ref = credits.calculate_best_education_credit(
                magi=breakdown.agi,
                filing_status=filing_status
            )
            result['education_credit_type'] = credit_type
            result['education_credit_nonrefundable'] = nonref
            result['education_credit_refundable'] = ref
        elif hasattr(credits, 'education_expenses') and credits.education_expenses > 0:
            # Legacy fallback for simple education expense input
            result['education_credit_nonrefundable'] = getattr(credits, 'education_credits', 0) or 0

        # Premium Tax Credit (Form 8962) - BR-0901 to BR-0920
        if hasattr(credits, 'marketplace_coverage') and credits.marketplace_coverage:
            household_income = getattr(credits, 'household_income', None) or breakdown.agi
            family_size = getattr(credits, 'family_size', 1)

            total_ptc, aptc_received, net_ptc = credits.calculate_premium_tax_credit(
                household_income=household_income,
                family_size=family_size,
                filing_status=filing_status
            )
            result['premium_tax_credit'] = max(0, total_ptc)
            result['ptc_advance_received'] = aptc_received
            result['ptc_net_adjustment'] = net_ptc

            # If net is positive, it's an additional credit
            # If net is negative, it's a repayment (added to tax)
            if net_ptc > 0:
                result['premium_tax_credit'] = net_ptc
            elif net_ptc < 0:
                # Repayment is handled separately (added to total tax)
                result['ptc_repayment'] = abs(net_ptc)

        # Foreign Tax Credit (Form 1116) - BR-0951 to BR-0970
        inc = tax_return.income

        # Check if Form 1116 is available for detailed calculation
        if inc.form_1116:
            # Use comprehensive Form 1116 calculation
            inc.form_1116.total_taxable_income = breakdown.taxable_income
            inc.form_1116.total_tax_before_credits = breakdown.total_tax_before_credits
            ftc_result = inc.form_1116.calculate_ftc(
                filing_status=filing_status,
                current_year=self.config.tax_year
            )
            result['foreign_tax_credit'] = ftc_result['total_ftc_allowed']
            result['foreign_tax_credit_carryforward'] = ftc_result['new_carryforward']

            # Store Form 1116 breakdown
            breakdown.form_1116_foreign_taxes_paid = ftc_result['total_foreign_taxes_paid']
            breakdown.form_1116_foreign_source_income = ftc_result['total_foreign_source_income']
            breakdown.form_1116_limitation = ftc_result['total_ftc_limitation']
            breakdown.form_1116_credit_allowed = ftc_result['total_ftc_allowed']
            breakdown.form_1116_carryforward = ftc_result['new_carryforward']
            breakdown.form_1116_simplified_method = ftc_result.get('using_simplified', False)
            breakdown.form_1116_breakdown = ftc_result
        else:
            # Fall back to simplified FTC calculation
            foreign_taxes_paid = getattr(credits, 'foreign_tax_credit', 0) or 0
            if foreign_taxes_paid > 0:
                # Calculate foreign source income from K-1s and other sources
                foreign_source_income = sum(
                    k1.foreign_tax_paid * 10  # Approximate: assume foreign tax is ~10% of foreign income
                    for k1 in getattr(inc, 'schedule_k1_forms', [])
                )
                # Add any direct foreign investment income (simplified)
                foreign_source_income = max(foreign_source_income, foreign_taxes_paid * 10)

                ftc_allowed, ftc_carryforward = credits.calculate_foreign_tax_credit(
                    foreign_taxes_paid=foreign_taxes_paid,
                    foreign_source_income=foreign_source_income,
                    total_taxable_income=breakdown.taxable_income,
                    total_tax_before_credits=breakdown.total_tax_before_credits,
                    filing_status=filing_status
                )
                result['foreign_tax_credit'] = ftc_allowed
                result['foreign_tax_credit_carryforward'] = ftc_carryforward

                # Store simplified breakdown
                breakdown.form_1116_foreign_taxes_paid = foreign_taxes_paid
                breakdown.form_1116_foreign_source_income = foreign_source_income
                breakdown.form_1116_credit_allowed = ftc_allowed
                breakdown.form_1116_carryforward = ftc_carryforward
                breakdown.form_1116_simplified_method = True

        # Child and Dependent Care Credit (Form 2441)
        if getattr(credits, 'child_care_expenses', 0) > 0 and getattr(credits, 'num_qualifying_persons', 0) > 0:
            # Get earned income for limit calculation
            inc = tax_return.income
            earned_income_taxpayer = inc.get_total_wages() + max(0, inc.get_schedule_c_net_profit())
            earned_income_spouse = earned_income_taxpayer  # Default to same as taxpayer
            if filing_status == "married_joint":
                # For MFJ, use spouse's earned income if available
                earned_income_spouse = getattr(inc, 'spouse_earned_income', earned_income_taxpayer)

            result['child_care_credit'] = credits.calculate_dependent_care_credit(
                agi=breakdown.agi,
                earned_income_taxpayer=earned_income_taxpayer,
                earned_income_spouse=earned_income_spouse,
                filing_status=filing_status,
            )
        else:
            result['child_care_credit'] = 0.0

        # Retirement Savings Contribution Credit (Saver's Credit - Form 8880)
        # Qualified contributions: IRA + SEP/SIMPLE + 401(k)/403(b)/457
        qualified_contributions = (
            tax_return.deductions.ira_contributions +
            tax_return.deductions.self_employed_sep_simple +
            getattr(credits, 'elective_deferrals_401k', 0)
        )
        if qualified_contributions > 0 and getattr(credits, 'savers_credit_eligible', True):
            result['retirement_savings_credit'] = credits.calculate_savers_credit(
                agi=breakdown.agi,
                filing_status=breakdown.filing_status,
                qualified_contributions=qualified_contributions,
                config=self.config,
            )
        else:
            result['retirement_savings_credit'] = 0.0

        # Residential Energy Credits (Form 5695)
        result['residential_clean_energy_credit'] = 0.0
        result['energy_efficient_home_credit'] = 0.0
        if hasattr(credits, 'calculate_residential_energy_credit'):
            clean_energy_credit, home_improvement_credit = credits.calculate_residential_energy_credit(
                config=self.config,
            )
            result['residential_clean_energy_credit'] = clean_energy_credit
            result['energy_efficient_home_credit'] = home_improvement_credit

        # Clean Vehicle Credit (Form 8936) - IRC Sections 30D and 25E
        result['new_clean_vehicle_credit'] = 0.0
        result['used_clean_vehicle_credit'] = 0.0
        result['clean_vehicle_breakdown'] = {}
        if hasattr(credits, 'clean_vehicles') and credits.clean_vehicles:
            new_credit, used_credit, cv_breakdown = credits.calculate_clean_vehicle_credit(
                magi=breakdown.agi,
                filing_status=filing_status,
                tax_year=self.config.tax_year,
            )
            result['new_clean_vehicle_credit'] = new_credit
            result['used_clean_vehicle_credit'] = used_credit
            result['clean_vehicle_breakdown'] = cv_breakdown

        # Adoption Credit (Form 8839) - IRC Section 23
        result['adoption_credit'] = 0.0
        result['adoption_credit_breakdown'] = {}
        if hasattr(credits, 'adoptions') and credits.adoptions:
            adoption_credit, adoption_breakdown = credits.calculate_adoption_credit(
                magi=breakdown.agi,
                filing_status=filing_status,
                tax_year=self.config.tax_year,
                max_credit=self.config.adoption_credit_max,
                phaseout_start=self.config.adoption_credit_phaseout_start,
                phaseout_end=self.config.adoption_credit_phaseout_end,
            )
            result['adoption_credit'] = adoption_credit
            result['adoption_credit_breakdown'] = adoption_breakdown

        # Credit for the Elderly or Disabled (Schedule R) - IRC Section 22
        result['elderly_disabled_credit'] = 0.0
        result['elderly_disabled_breakdown'] = {}
        if hasattr(credits, 'elderly_disabled_info') and credits.elderly_disabled_info:
            elderly_credit, elderly_breakdown = credits.calculate_elderly_disabled_credit(
                agi=breakdown.agi,
                filing_status=filing_status,
                tax_year=self.config.tax_year,
            )
            result['elderly_disabled_credit'] = elderly_credit
            result['elderly_disabled_breakdown'] = elderly_breakdown

        # Work Opportunity Tax Credit (Form 5884) - IRC Section 51
        result['wotc_credit'] = 0.0
        result['wotc_breakdown'] = {}
        if hasattr(credits, 'wotc_employees') and credits.wotc_employees:
            wotc_credit, wotc_breakdown = credits.calculate_wotc(
                tax_year=self.config.tax_year,
            )
            result['wotc_credit'] = wotc_credit
            result['wotc_breakdown'] = wotc_breakdown

        # Small Employer Health Insurance Credit (Form 8941) - IRC Section 45R
        result['small_employer_health_credit'] = 0.0
        result['small_employer_health_breakdown'] = {}
        if hasattr(credits, 'small_employer_health_info') and credits.small_employer_health_info:
            seh_credit, seh_breakdown = credits.calculate_small_employer_health_credit(
                tax_year=self.config.tax_year,
                wage_threshold=self.config.small_employer_health_wage_threshold,
            )
            result['small_employer_health_credit'] = seh_credit
            result['small_employer_health_breakdown'] = seh_breakdown

        # Disabled Access Credit (Form 8826) - IRC Section 44
        result['disabled_access_credit'] = 0.0
        result['disabled_access_breakdown'] = {}
        if hasattr(credits, 'disabled_access_info') and credits.disabled_access_info:
            dac_credit, dac_breakdown = credits.calculate_disabled_access_credit(
                tax_year=self.config.tax_year,
                min_expenditure=self.config.disabled_access_min_expenditure,
                max_expenditure=self.config.disabled_access_max_expenditure,
                credit_rate=self.config.disabled_access_credit_rate,
            )
            result['disabled_access_credit'] = dac_credit
            result['disabled_access_breakdown'] = dac_breakdown

        # Other credits
        result['other_nonrefundable'] = getattr(credits, 'other_credits', 0) or 0
        result['other_refundable'] = 0.0

        # Sum totals
        result['total_nonrefundable'] = float(money(
            result['child_tax_credit'] +
            result['other_dependent_credit'] +
            result['child_care_credit'] +
            result['education_credit_nonrefundable'] +
            result['foreign_tax_credit'] +
            result['retirement_savings_credit'] +
            result['residential_clean_energy_credit'] +
            result['energy_efficient_home_credit'] +
            result['new_clean_vehicle_credit'] +
            result['used_clean_vehicle_credit'] +
            result['adoption_credit'] +
            result['elderly_disabled_credit'] +
            result['wotc_credit'] +
            result['small_employer_health_credit'] +
            result['disabled_access_credit'] +
            result['other_nonrefundable']
        ))
        result['total_refundable'] = float(money(
            result['additional_child_tax_credit'] +
            result['earned_income_credit'] +
            result['education_credit_refundable'] +
            result['premium_tax_credit'] +
            result['other_refundable']
        ))

        return result

    def _calculate_eitc(
        self,
        tax_return: TaxReturn,
        filing_status: str,
        taxpayer_agi: float = None
    ) -> float:
        """
        Calculate Earned Income Tax Credit using proper QC validation.

        EITC requires qualifying children to meet the 5-part Qualifying Child test
        (BR-0023 to BR-0027) plus additional EITC-specific requirements.
        """
        if not self.config.eitc_max_credit or not self.config.eitc_phaseout_end:
            return 0.0

        # MFS cannot claim EITC (per IRS rules)
        if filing_status == "married_separate":
            return 0.0

        # Use proper dependent qualification tests for EITC qualifying children
        if hasattr(tax_return, 'taxpayer') and tax_return.taxpayer.dependents:
            agi = taxpayer_agi or tax_return.adjusted_gross_income or 0.0
            num_children = get_eitc_qualifying_children(tax_return.taxpayer, agi)
        else:
            credits = tax_return.credits if hasattr(tax_return, 'credits') else None
            # Try num_qualifying_children first, fallback to child_tax_credit_children
            num_children = getattr(credits, 'num_qualifying_children', None) if credits else None
            if num_children is None:
                num_children = getattr(credits, 'child_tax_credit_children', 0) if credits else 0
            num_children = min(num_children, 3)  # Max 3 for EITC purposes

        # Check investment income limit
        inc = tax_return.income
        investment_income = (
            inc.interest_income +
            inc.dividend_income +
            max(0, inc.short_term_capital_gains + inc.long_term_capital_gains)
        )
        if investment_income > self.config.eitc_investment_income_limit:
            return 0.0

        # Get EITC parameters
        max_credit = self.config.eitc_max_credit.get(num_children, 0)
        phaseout_start = self.config.eitc_phaseout_start.get(filing_status, {}).get(num_children, 0) if self.config.eitc_phaseout_start else 0
        phaseout_end = self.config.eitc_phaseout_end.get(filing_status, {}).get(num_children, 0) if self.config.eitc_phaseout_end else 0

        # Calculate earned income
        earned_income = inc.get_total_wages() + max(0, inc.get_schedule_c_net_profit())
        agi = tax_return.adjusted_gross_income or 0.0

        # Use higher of earned income or AGI for phaseout
        income_for_eitc = max(earned_income, agi)

        if income_for_eitc >= phaseout_end:
            return 0.0

        # Get phase-in parameters
        phase_in_end = self.config.eitc_phase_in_end.get(num_children, 0) if self.config.eitc_phase_in_end else 0
        phase_in_rate = self.config.eitc_phase_in_rate.get(num_children, 0) if self.config.eitc_phase_in_rate else 0

        # Phase-in range: Credit builds up based on earned_income x rate
        if earned_income <= phase_in_end and phase_in_rate > 0:
            credit = earned_income * phase_in_rate
            return float(money(min(credit, max_credit)))

        # Plateau range: Full max credit
        if income_for_eitc <= phaseout_start:
            return max_credit

        # In phaseout range
        phaseout_range = phaseout_end - phaseout_start
        excess = income_for_eitc - phaseout_start
        reduction_pct = excess / phaseout_range if phaseout_range > 0 else 1
        credit = max_credit * (1 - reduction_pct)

        return float(money(max(0, credit)))

    def _calculate_total_payments(self, tax_return: TaxReturn) -> float:
        """
        Calculate total tax payments and withholdings.

        Includes:
        - W-2 federal tax withheld
        - Gambling withholding (W-2G Box 4) (BR-0501 to BR-0510)
        - Estimated tax payments
        - Amount paid with extension
        - Excess Social Security withholding (multiple employers)
        """
        inc = tax_return.income
        payments = (
            inc.get_total_federal_withholding() +  # Includes W-2 and gambling withholding
            getattr(inc, 'estimated_tax_payments', 0) +
            getattr(inc, 'amount_paid_with_extension', 0) +
            getattr(inc, 'excess_social_security_withholding', 0)
        )
        return float(money(payments))

    def _calculate_estimated_tax_penalty(
        self,
        total_tax: float,
        total_payments: float,
        prior_year_tax: float,
        prior_year_agi: float,
        is_farmer_or_fisherman: bool = False
    ) -> Dict[str, Any]:
        """
        Calculate estimated tax underpayment penalty per IRS Form 2210.

        Safe Harbor Rules (no penalty if ANY of these are met):
        1. Total payments >= 90% of current year tax
        2. Total payments >= 100% of prior year tax (standard)
        3. Total payments >= 110% of prior year tax (if prior AGI > $150,000)
        4. Underpayment < $1,000 threshold

        Special case: Farmers/fishermen use 66⅔% instead of 90% for current year.

        This implements the simplified annual method (not quarterly compounding).
        """
        cfg = self.config

        # Calculate 90% of current year tax (or 66⅔% for farmers/fishermen)
        if is_farmer_or_fisherman:
            current_year_required = total_tax * cfg.farmer_fisherman_safe_harbor_pct
        else:
            current_year_required = total_tax * cfg.safe_harbor_current_year_pct

        # Calculate prior year safe harbor amount
        # Use 110% if prior AGI > $150k, otherwise 100%
        if prior_year_agi > cfg.safe_harbor_high_income_threshold:
            prior_year_safe_harbor = prior_year_tax * cfg.safe_harbor_high_income_pct
        else:
            prior_year_safe_harbor = prior_year_tax * cfg.safe_harbor_prior_year_pct

        # Required annual payment is the SMALLER of current year or prior year safe harbor
        # BUT: If no prior year tax, use current year requirement only
        if prior_year_tax > 0:
            required_annual_payment = min(current_year_required, prior_year_safe_harbor)
        else:
            required_annual_payment = current_year_required

        # Check safe harbor conditions
        safe_harbor_met = False

        # Safe harbor 1: Payments >= 90% of current year tax
        if total_payments >= current_year_required:
            safe_harbor_met = True

        # Safe harbor 2: Payments >= 100%/110% of prior year tax
        if prior_year_tax > 0 and total_payments >= prior_year_safe_harbor:
            safe_harbor_met = True

        # Safe harbor 3: No tax owed (payments >= total tax)
        if total_payments >= total_tax:
            safe_harbor_met = True

        # Calculate underpayment
        underpayment = max(0, required_annual_payment - total_payments)

        # Apply $1,000 threshold - no penalty if underpayment < $1,000
        if underpayment < cfg.estimated_tax_underpayment_threshold:
            return {
                'penalty': 0.0,
                'safe_harbor_met': True,  # Effectively met by threshold
                'required_payment': float(money(required_annual_payment)),
                'underpayment': float(money(underpayment))
            }

        # If safe harbor met, no penalty
        if safe_harbor_met:
            return {
                'penalty': 0.0,
                'safe_harbor_met': True,
                'required_payment': float(money(required_annual_payment)),
                'underpayment': 0.0
            }

        # Calculate penalty: underpayment × annual rate
        penalty = underpayment * cfg.estimated_tax_penalty_rate

        return {
            'penalty': float(money(penalty)),
            'safe_harbor_met': False,
            'required_payment': float(money(required_annual_payment)),
            'underpayment': float(money(underpayment))
        }

    def _get_marginal_rate(self, taxable_income: float, filing_status: str) -> float:
        """Get the marginal tax rate for given taxable income."""
        if taxable_income <= 0:
            return 0.10

        brackets = self.config.ordinary_income_brackets.get(
            filing_status, self.config.ordinary_income_brackets["single"]
        )

        marginal_rate = 0.10
        for floor, rate in brackets:
            if taxable_income > floor:
                marginal_rate = rate

        return marginal_rate * 100  # Return as percentage
