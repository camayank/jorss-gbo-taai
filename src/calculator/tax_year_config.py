from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional


BracketTable = Dict[str, List[Tuple[float, float]]]


@dataclass(frozen=True)
class TaxYearConfig:
    """
    Centralized constants for a given tax year.

    NOTE: Values here should be reviewed annually against IRS published figures.
    The structure is designed to make updates localized and testable.
    """

    tax_year: int
    ordinary_income_brackets: BracketTable
    standard_deduction: Dict[str, float]
    additional_standard_deduction_over_65_or_blind: Dict[str, float]

    # Preferential rate thresholds for Qualified Dividends / Long-Term Capital Gains.
    # If not provided, engine will treat preferential income as ordinary (safe fallback).
    qd_ltcg_0_rate_threshold: Optional[Dict[str, float]] = None
    qd_ltcg_15_rate_threshold: Optional[Dict[str, float]] = None

    # Self-employment (Schedule SE) configuration
    se_net_earnings_factor: float = 0.9235  # 92.35%
    se_tax_rate: float = 0.153  # 12.4% SS + 2.9% Medicare (base SE tax)
    ss_wage_base: float = 176100.0  # Social Security wage base limit for 2025
    medicare_rate: float = 0.029  # 2.9% Medicare (no wage base limit)
    ss_rate: float = 0.124  # 12.4% Social Security (up to wage base)

    # Additional Medicare Tax (0.9% on wages/SE income over threshold)
    additional_medicare_tax_rate: float = 0.009  # 0.9%
    additional_medicare_threshold: Optional[Dict[str, float]] = None

    # Net Investment Income Tax (3.8% on lesser of NII or MAGI over threshold)
    niit_rate: float = 0.038  # 3.8%
    niit_threshold: Optional[Dict[str, float]] = None

    # Alternative Minimum Tax (AMT) configuration
    amt_rate_26: float = 0.26  # 26% on first portion
    amt_rate_28: float = 0.28  # 28% on excess over threshold
    amt_28_threshold: Optional[Dict[str, float]] = None  # Threshold where 28% rate kicks in
    amt_exemption: Optional[Dict[str, float]] = None
    amt_exemption_phaseout_start: Optional[Dict[str, float]] = None
    amt_exemption_phaseout_rate: float = 0.25  # Exemption reduced by 25 cents per dollar over threshold

    # Credit limits and thresholds
    child_tax_credit_amount: float = 2000.0
    child_tax_credit_refundable: float = 1700.0  # Additional Child Tax Credit max
    child_tax_credit_phaseout_start: Optional[Dict[str, float]] = None
    child_tax_credit_phaseout_rate: float = 0.05  # 5% reduction per $1,000 over threshold

    # EITC parameters by number of qualifying children
    eitc_max_credit: Optional[Dict[int, float]] = None  # 0, 1, 2, 3+ children
    eitc_phaseout_start: Optional[Dict[str, Dict[int, float]]] = None
    eitc_phaseout_end: Optional[Dict[str, Dict[int, float]]] = None
    eitc_investment_income_limit: float = 11950.0  # 2025 limit

    # Contribution limits
    traditional_ira_limit: float = 7000.0
    ira_catchup_50_plus: float = 1000.0
    hsa_individual_limit: float = 4300.0
    hsa_family_limit: float = 8550.0
    hsa_catchup_55_plus: float = 1000.0
    k401_limit: float = 23500.0
    k401_catchup_50_plus: float = 7500.0
    sep_ira_limit: float = 69000.0

    # Student loan interest deduction (BR2-0007, BR2-0008)
    student_loan_interest_max: float = 2500.0
    student_loan_phaseout_start: Optional[Dict[str, float]] = None
    student_loan_phaseout_end: Optional[Dict[str, float]] = None

    # Traditional IRA deduction phaseouts (when covered by employer plan)
    # Per IRS Publication 590-A
    trad_ira_phaseout_start_covered: Optional[Dict[str, float]] = None
    trad_ira_phaseout_end_covered: Optional[Dict[str, float]] = None
    # Spouse not covered but taxpayer is covered
    trad_ira_phaseout_start_spouse_covered: Optional[Dict[str, float]] = None
    trad_ira_phaseout_end_spouse_covered: Optional[Dict[str, float]] = None

    # Roth IRA contribution phaseouts
    roth_ira_phaseout_start: Optional[Dict[str, float]] = None
    roth_ira_phaseout_end: Optional[Dict[str, float]] = None

    # Gift and estate
    annual_gift_exclusion: float = 19000.0
    estate_exemption: float = 13990000.0

    # Miscellaneous thresholds
    salt_cap: float = 10000.0  # State and Local Tax deduction cap
    medical_expense_floor_pct: float = 0.075  # 7.5% of AGI
    qbi_deduction_rate: float = 0.20  # 20% QBI deduction

    # QBI (Section 199A) deduction thresholds
    # Below threshold_start: no limitations
    # Between threshold_start and threshold_end: phase-in of limitations
    # Above threshold_end: full W-2 wage/UBIA limitation; SSTB gets $0
    qbi_threshold_start: Optional[Dict[str, float]] = None
    qbi_threshold_end: Optional[Dict[str, float]] = None

    # Saver's Credit (Retirement Savings Contributions Credit - Form 8880)
    # Credit rate (50%, 20%, 10%) based on AGI thresholds
    savers_credit_50_pct_limit: Optional[Dict[str, float]] = None
    savers_credit_20_pct_limit: Optional[Dict[str, float]] = None
    savers_credit_10_pct_limit: Optional[Dict[str, float]] = None
    savers_credit_max_contribution: float = 2000.0

    # Residential Energy Credits (Form 5695)
    # Part I: Residential Clean Energy Credit (Section 25D) - 30% for 2022-2032
    # Part II: Energy Efficient Home Improvement Credit (Section 25C)
    residential_clean_energy_rate: float = 0.30
    energy_efficient_home_rate: float = 0.30
    energy_efficient_annual_limit: float = 1200.0  # $1,200 aggregate for Part II
    energy_efficient_window_limit: float = 600.0
    energy_efficient_door_limit: float = 500.0  # $250/door, $500 max
    energy_efficient_panel_limit: float = 600.0
    energy_efficient_audit_limit: float = 150.0
    heat_pump_annual_limit: float = 2000.0  # Separate $2,000 limit for heat pumps
    fuel_cell_per_half_kw_limit: float = 500.0  # $500 per 0.5 kW capacity

    # Capital Loss Deduction Limits (IRC Section 1211(b))
    # Net capital losses are limited to $3,000/year ($1,500 for MFS)
    # Unused losses carry forward indefinitely (IRC Section 1212)
    capital_loss_limit: float = 3000.0
    capital_loss_limit_mfs: float = 1500.0  # Married Filing Separately

    # Social Security Taxation Thresholds (IRS Pub. 915)
    # Base amounts determine when SS benefits become taxable
    # Tier 1: 0% taxable if provisional income <= base1
    # Tier 2: 50% of excess if base1 < provisional <= base2
    # Tier 3: 85% of excess if provisional > base2 (capped at 85% of benefits)
    ss_base1_single: float = 25000.0  # Single/HOH/QW
    ss_base2_single: float = 34000.0
    ss_base1_mfj: float = 32000.0  # Married Filing Jointly
    ss_base2_mfj: float = 44000.0
    ss_lesser_cap_single: float = 4500.0  # Used in Tier 3 formula
    ss_lesser_cap_mfj: float = 6000.0

    # Estimated Tax Penalty (Form 2210) - IRS Pub. 505
    estimated_tax_underpayment_threshold: float = 1000.0  # Minimum underpayment for penalty
    estimated_tax_penalty_rate: float = 0.08  # 8% annual rate for 2025
    safe_harbor_current_year_pct: float = 0.90  # 90% of current year tax
    safe_harbor_prior_year_pct: float = 1.00  # 100% of prior year tax
    safe_harbor_high_income_pct: float = 1.10  # 110% if prior AGI > $150k
    safe_harbor_high_income_threshold: float = 150000.0  # AGI threshold for 110% rule
    farmer_fisherman_safe_harbor_pct: float = 0.6667  # 66⅔% for farmers/fishermen

    # Passive Activity Loss (PAL) - Form 8582 / IRC Section 469
    pal_rental_loss_allowance: float = 25000.0  # $25,000 rental loss allowance for active participants
    pal_phaseout_start: float = 100000.0  # AGI threshold where $25k allowance begins phaseout
    pal_phaseout_end: float = 150000.0  # AGI threshold where $25k allowance is fully phased out
    pal_phaseout_rate: float = 0.50  # 50 cents per dollar over $100k AGI
    pal_real_estate_professional_hours: float = 750.0  # Min hours for RE professional status

    # Depreciation - Form 4562 / IRC Section 168 (MACRS)
    # Section 179 limits (IRC Section 179) - 2025 values
    section_179_limit: float = 1250000.0  # Maximum Section 179 deduction (indexed annually)
    section_179_phaseout_threshold: float = 3130000.0  # Property threshold where limit begins phaseout
    # Bonus depreciation (IRC Section 168(k)) - phases down after 2022
    # Schedule: 2022=100%, 2023=80%, 2024=60%, 2025=40%, 2026=20%, 2027+=0%
    bonus_depreciation_rate: float = 0.40  # 40% for 2025
    # Listed property business use threshold
    listed_property_min_business_use: float = 50.0  # Must be >50% business to use MACRS
    # Section 280F Luxury Auto Limits (2025)
    luxury_auto_year1_with_bonus: float = 20400.0
    luxury_auto_year1_without_bonus: float = 12400.0
    luxury_auto_year2: float = 19800.0
    luxury_auto_year3: float = 11900.0
    luxury_auto_year4_plus: float = 7160.0

    # Adoption Credit - Form 8839 / IRC Section 23 (2025 values)
    adoption_credit_max: float = 16810.0  # Maximum credit per child
    adoption_credit_phaseout_start: float = 252150.0  # MAGI where phaseout begins
    adoption_credit_phaseout_end: float = 292150.0  # MAGI where credit fully phased out

    # Small Employer Health Insurance Credit - Form 8941 / IRC Section 45R (2025 values)
    # Wage threshold is indexed annually - $59,000 for 2025
    small_employer_health_wage_threshold: float = 59000.0
    small_employer_health_fte_limit: float = 25.0  # Must have fewer than 25 FTEs
    small_employer_health_taxable_rate: float = 0.50  # 50% credit for taxable employers
    small_employer_health_exempt_rate: float = 0.35  # 35% credit for tax-exempt employers
    small_employer_health_fte_phaseout_start: float = 10.0  # Full credit up to 10 FTEs
    small_employer_health_min_contribution: float = 0.50  # Must pay at least 50% of premiums

    # Disabled Access Credit - Form 8826 / IRC Section 44
    disabled_access_min_expenditure: float = 250.0  # Minimum expenditure threshold
    disabled_access_max_expenditure: float = 10250.0  # Maximum expenditure threshold
    disabled_access_credit_rate: float = 0.50  # 50% credit rate
    disabled_access_max_credit: float = 5000.0  # Maximum credit ($10,000 × 50%)
    disabled_access_gross_receipts_limit: float = 1000000.0  # $1M gross receipts limit
    disabled_access_employee_limit: int = 30  # 30 employee limit

    @staticmethod
    def for_2025() -> "TaxYearConfig":
        # Ordinary income brackets (marginal rates) for tax year 2025 (filing in 2026).
        brackets = {
            "single": [
                (0, 0.10),
                (11925, 0.12),
                (48475, 0.22),
                (103350, 0.24),
                (197300, 0.32),
                (250525, 0.35),
                (626350, 0.37),
            ],
            "married_joint": [
                (0, 0.10),
                (23850, 0.12),
                (96950, 0.22),
                (206700, 0.24),
                (394600, 0.32),
                (501050, 0.35),
                (751600, 0.37),
            ],
            "married_separate": [
                (0, 0.10),
                (11925, 0.12),
                (48475, 0.22),
                (103350, 0.24),
                (197300, 0.32),
                (250525, 0.35),
                (375800, 0.37),
            ],
            "head_of_household": [
                (0, 0.10),
                (17050, 0.12),
                (64850, 0.22),
                (103350, 0.24),
                (197300, 0.32),
                (250525, 0.35),
                (626350, 0.37),
            ],
            "qualifying_widow": [
                (0, 0.10),
                (23850, 0.12),
                (96950, 0.22),
                (206700, 0.24),
                (394600, 0.32),
                (501050, 0.35),
                (751600, 0.37),
            ],
        }

        # Standard deduction amounts (tax year 2025). IRS Rev. Proc. 2024-40.
        std = {
            "single": 15750.0,
            "married_joint": 31500.0,
            "married_separate": 15750.0,
            "head_of_household": 23625.0,
            "qualifying_widow": 31500.0,
        }

        # Additional standard deduction amounts per condition (65+ OR blind).
        # Single/HOH: $1,950 each; Married: $1,550 each
        additional = {
            "single": 1950.0,
            "head_of_household": 1950.0,
            "married_joint": 1550.0,
            "married_separate": 1550.0,
            "qualifying_widow": 1550.0,
        }

        # Qualified dividends / Long-term capital gains rate thresholds (2025)
        # 0% rate up to this threshold, 15% rate up to next, 20% above
        qd_ltcg_0 = {
            "single": 48350.0,
            "married_joint": 96700.0,
            "married_separate": 48350.0,
            "head_of_household": 64750.0,
            "qualifying_widow": 96700.0,
        }
        qd_ltcg_15 = {
            "single": 533400.0,
            "married_joint": 600050.0,
            "married_separate": 300025.0,
            "head_of_household": 566700.0,
            "qualifying_widow": 600050.0,
        }

        # Additional Medicare Tax thresholds (0.9% on wages/SE over threshold)
        additional_medicare = {
            "single": 200000.0,
            "married_joint": 250000.0,
            "married_separate": 125000.0,
            "head_of_household": 200000.0,
            "qualifying_widow": 200000.0,
        }

        # Net Investment Income Tax (NIIT) thresholds (3.8%)
        niit = {
            "single": 200000.0,
            "married_joint": 250000.0,
            "married_separate": 125000.0,
            "head_of_household": 200000.0,
            "qualifying_widow": 250000.0,
        }

        # AMT exemption amounts (2025)
        amt_exemption = {
            "single": 88100.0,
            "married_joint": 137000.0,
            "married_separate": 68500.0,
            "head_of_household": 88100.0,
            "qualifying_widow": 137000.0,
        }

        # AMT exemption phaseout starts at
        amt_phaseout_start = {
            "single": 626350.0,
            "married_joint": 1252700.0,
            "married_separate": 626350.0,
            "head_of_household": 626350.0,
            "qualifying_widow": 1252700.0,
        }

        # AMT 28% rate kicks in at (for AMTI over exemption)
        amt_28_threshold = {
            "single": 232600.0,
            "married_joint": 232600.0,
            "married_separate": 116300.0,
            "head_of_household": 232600.0,
            "qualifying_widow": 232600.0,
        }

        # Child Tax Credit phaseout starts at
        ctc_phaseout = {
            "single": 200000.0,
            "married_joint": 400000.0,
            "married_separate": 200000.0,
            "head_of_household": 200000.0,
            "qualifying_widow": 400000.0,
        }

        # EITC max credit by number of qualifying children (2025)
        # IRS Rev. Proc. 2024-40
        eitc_max = {
            0: 649.0,
            1: 4328.0,
            2: 7152.0,
            3: 8046.0,  # 3 or more
        }

        # EITC phaseout start by filing status and children
        eitc_phase_start = {
            "single": {0: 9950.0, 1: 12730.0, 2: 12730.0, 3: 12730.0},
            "married_joint": {0: 16370.0, 1: 19150.0, 2: 19150.0, 3: 19150.0},
            "married_separate": {0: 9950.0, 1: 12730.0, 2: 12730.0, 3: 12730.0},
            "head_of_household": {0: 9950.0, 1: 12730.0, 2: 12730.0, 3: 12730.0},
            "qualifying_widow": {0: 16370.0, 1: 19150.0, 2: 19150.0, 3: 19150.0},
        }

        # EITC phaseout end (no credit above this) - IRS Rev. Proc. 2024-40
        eitc_phase_end = {
            "single": {0: 18591.0, 1: 49084.0, 2: 55768.0, 3: 59899.0},
            "married_joint": {0: 25511.0, 1: 56004.0, 2: 62688.0, 3: 66819.0},
            "married_separate": {0: 18591.0, 1: 49084.0, 2: 55768.0, 3: 59899.0},
            "head_of_household": {0: 18591.0, 1: 49084.0, 2: 55768.0, 3: 59899.0},
            "qualifying_widow": {0: 25511.0, 1: 56004.0, 2: 62688.0, 3: 66819.0},
        }

        # Student loan interest deduction phaseouts (BR2-0007, BR2-0008)
        # IRS Rev. Proc. 2024-40 - MFS cannot claim this deduction
        student_loan_phase_start = {
            "single": 85000.0,
            "married_joint": 170000.0,
            "married_separate": 0.0,  # Cannot claim
            "head_of_household": 85000.0,
            "qualifying_widow": 85000.0,
        }
        student_loan_phase_end = {
            "single": 100000.0,
            "married_joint": 200000.0,
            "married_separate": 0.0,  # Cannot claim
            "head_of_household": 100000.0,
            "qualifying_widow": 100000.0,
        }

        # Traditional IRA deduction phaseouts - when covered by employer plan
        # IRS Publication 590-A for 2025
        trad_ira_phase_start_covered = {
            "single": 79000.0,
            "married_joint": 126000.0,  # Contributor covered by plan
            "married_separate": 0.0,
            "head_of_household": 79000.0,
            "qualifying_widow": 126000.0,
        }
        trad_ira_phase_end_covered = {
            "single": 89000.0,
            "married_joint": 146000.0,
            "married_separate": 10000.0,
            "head_of_household": 89000.0,
            "qualifying_widow": 146000.0,
        }

        # Traditional IRA - spouse covered by plan but taxpayer not covered
        trad_ira_phase_start_spouse_covered = {
            "married_joint": 236000.0,
            "married_separate": 0.0,
        }
        trad_ira_phase_end_spouse_covered = {
            "married_joint": 246000.0,
            "married_separate": 10000.0,
        }

        # Roth IRA contribution phaseouts
        # IRS Publication 590-A for 2025
        roth_ira_phase_start = {
            "single": 150000.0,
            "married_joint": 236000.0,
            "married_separate": 0.0,
            "head_of_household": 150000.0,
            "qualifying_widow": 236000.0,
        }
        roth_ira_phase_end = {
            "single": 165000.0,
            "married_joint": 246000.0,
            "married_separate": 10000.0,
            "head_of_household": 165000.0,
            "qualifying_widow": 246000.0,
        }

        # QBI (Section 199A) deduction thresholds
        # IRS Rev. Proc. 2024-40 - threshold where W-2 wage/UBIA limitations begin
        # Phase-in range is $50,000 for single and $100,000 for MFJ
        qbi_threshold_start = {
            "single": 197300.0,
            "married_joint": 394600.0,
            "married_separate": 197300.0,
            "head_of_household": 197300.0,
            "qualifying_widow": 394600.0,
        }
        qbi_threshold_end = {
            "single": 247300.0,  # +50,000
            "married_joint": 494600.0,  # +100,000
            "married_separate": 247300.0,  # +50,000
            "head_of_household": 247300.0,  # +50,000
            "qualifying_widow": 494600.0,  # +100,000
        }

        # Saver's Credit (Retirement Savings Contributions Credit - Form 8880)
        # AGI thresholds for 2025 - credit rate is 50%, 20%, or 10% based on AGI
        savers_50 = {
            "single": 23750.0,
            "married_joint": 47500.0,
            "married_separate": 23750.0,
            "head_of_household": 35625.0,
            "qualifying_widow": 47500.0,
        }
        savers_20 = {
            "single": 25500.0,
            "married_joint": 51000.0,
            "married_separate": 25500.0,
            "head_of_household": 38250.0,
            "qualifying_widow": 51000.0,
        }
        savers_10 = {
            "single": 39375.0,
            "married_joint": 78750.0,
            "married_separate": 39375.0,
            "head_of_household": 59062.0,
            "qualifying_widow": 78750.0,
        }

        return TaxYearConfig(
            tax_year=2025,
            ordinary_income_brackets=brackets,
            standard_deduction=std,
            additional_standard_deduction_over_65_or_blind=additional,
            # Capital gains / qualified dividends rates
            qd_ltcg_0_rate_threshold=qd_ltcg_0,
            qd_ltcg_15_rate_threshold=qd_ltcg_15,
            # Self-employment tax
            ss_wage_base=176100.0,
            medicare_rate=0.029,
            ss_rate=0.124,
            # Additional Medicare Tax
            additional_medicare_tax_rate=0.009,
            additional_medicare_threshold=additional_medicare,
            # Net Investment Income Tax
            niit_rate=0.038,
            niit_threshold=niit,
            # Alternative Minimum Tax
            amt_rate_26=0.26,
            amt_rate_28=0.28,
            amt_28_threshold=amt_28_threshold,
            amt_exemption=amt_exemption,
            amt_exemption_phaseout_start=amt_phaseout_start,
            amt_exemption_phaseout_rate=0.25,
            # Child Tax Credit
            child_tax_credit_amount=2000.0,
            child_tax_credit_refundable=1700.0,
            child_tax_credit_phaseout_start=ctc_phaseout,
            child_tax_credit_phaseout_rate=0.05,
            # EITC
            eitc_max_credit=eitc_max,
            eitc_phaseout_start=eitc_phase_start,
            eitc_phaseout_end=eitc_phase_end,
            eitc_investment_income_limit=11950.0,
            # Contribution limits (2025)
            traditional_ira_limit=7000.0,
            ira_catchup_50_plus=1000.0,
            hsa_individual_limit=4300.0,
            hsa_family_limit=8550.0,
            hsa_catchup_55_plus=1000.0,
            k401_limit=23500.0,
            k401_catchup_50_plus=7500.0,
            sep_ira_limit=69000.0,
            # Student loan interest phaseouts (BR2-0007, BR2-0008)
            student_loan_interest_max=2500.0,
            student_loan_phaseout_start=student_loan_phase_start,
            student_loan_phaseout_end=student_loan_phase_end,
            # IRA phaseouts
            trad_ira_phaseout_start_covered=trad_ira_phase_start_covered,
            trad_ira_phaseout_end_covered=trad_ira_phase_end_covered,
            trad_ira_phaseout_start_spouse_covered=trad_ira_phase_start_spouse_covered,
            trad_ira_phaseout_end_spouse_covered=trad_ira_phase_end_spouse_covered,
            roth_ira_phaseout_start=roth_ira_phase_start,
            roth_ira_phaseout_end=roth_ira_phase_end,
            # Gift and estate (2025)
            annual_gift_exclusion=19000.0,
            estate_exemption=13990000.0,
            # Miscellaneous
            salt_cap=10000.0,
            medical_expense_floor_pct=0.075,
            qbi_deduction_rate=0.20,
            # QBI (Section 199A) thresholds
            qbi_threshold_start=qbi_threshold_start,
            qbi_threshold_end=qbi_threshold_end,
            # Saver's Credit (Form 8880) thresholds
            savers_credit_50_pct_limit=savers_50,
            savers_credit_20_pct_limit=savers_20,
            savers_credit_10_pct_limit=savers_10,
            savers_credit_max_contribution=2000.0,
        )

    @staticmethod
    def for_year(tax_year: int) -> "TaxYearConfig":
        """
        Load tax configuration for any supported year from YAML files.

        Supported years:
        - 2022, 2023, 2024: Historical data for amended returns and YoY comparisons
        - 2025: Current advisory year (recommended - use for_2025() for inline config)
        - 2026: Projected values for planning purposes

        Args:
            tax_year: The tax year to load (2022-2026)

        Returns:
            TaxYearConfig for the specified year

        Raises:
            ValueError: If the tax year is not supported
        """
        import os
        import yaml
        from pathlib import Path

        if tax_year == 2025:
            # Use the inline configuration for 2025 (current advisory year)
            return TaxYearConfig.for_2025()

        supported_years = [2022, 2023, 2024, 2026]
        if tax_year not in supported_years:
            raise ValueError(
                f"Tax year {tax_year} is not supported. "
                f"Supported years: 2022, 2023, 2024, 2025, 2026"
            )

        # Load from YAML file
        config_dir = Path(__file__).parent.parent / "config" / "tax_parameters"
        yaml_file = config_dir / f"tax_year_{tax_year}.yaml"

        if not yaml_file.exists():
            raise FileNotFoundError(
                f"Tax configuration file not found: {yaml_file}. "
                f"Please ensure tax_year_{tax_year}.yaml exists."
            )

        with open(yaml_file, "r") as f:
            data = yaml.safe_load(f)

        # Convert YAML bracket format [threshold, rate] to tuple format (threshold, rate)
        def convert_brackets(yaml_brackets: dict) -> dict:
            converted = {}
            for status, brackets in yaml_brackets.items():
                converted[status] = [(float(b[0]), float(b[1])) for b in brackets]
            return converted

        # Build ordinary income brackets
        brackets = convert_brackets(data.get("ordinary_income_brackets", {}))

        # Add (0, 0.10) as the first bracket if not present
        for status in brackets:
            if brackets[status] and brackets[status][0][0] != 0:
                brackets[status].insert(0, (0, 0.10))

        # Standard deductions
        std = data.get("standard_deduction", {})
        std = {k: float(v) for k, v in std.items()}

        # Additional standard deduction
        additional_raw = data.get("additional_standard_deduction_65_or_blind", {})
        additional = {
            "single": float(additional_raw.get("single", 1950)),
            "head_of_household": float(additional_raw.get("head_of_household", additional_raw.get("single", 1950))),
            "married_joint": float(additional_raw.get("married", 1550)),
            "married_separate": float(additional_raw.get("married", 1550)),
            "qualifying_widow": float(additional_raw.get("married", 1550)),
        }

        # Capital gains thresholds
        cap_gains = data.get("capital_gains_brackets", {})
        zero_rate = cap_gains.get("zero_rate_threshold", {})
        fifteen_rate = cap_gains.get("fifteen_rate_threshold", {})

        qd_ltcg_0 = {k: float(v) for k, v in zero_rate.items()} if zero_rate else None
        qd_ltcg_15 = {k: float(v) for k, v in fifteen_rate.items()} if fifteen_rate else None

        # Additional Medicare thresholds
        add_medicare_raw = data.get("additional_medicare_threshold", {})
        additional_medicare = {k: float(v) for k, v in add_medicare_raw.items()} if add_medicare_raw else None

        # NIIT thresholds
        niit_raw = data.get("niit_threshold", {})
        niit = {k: float(v) for k, v in niit_raw.items()} if niit_raw else None

        # AMT
        amt_exemption_raw = data.get("amt_exemption", {})
        amt_exemption = {k: float(v) for k, v in amt_exemption_raw.items()} if amt_exemption_raw else None

        amt_phaseout_raw = data.get("amt_exemption_phaseout_start", {})
        amt_phaseout_start = {k: float(v) for k, v in amt_phaseout_raw.items()} if amt_phaseout_raw else None

        amt_28_raw = data.get("amt_28_threshold", {})
        amt_28_threshold = {k: float(v) for k, v in amt_28_raw.items()} if amt_28_raw else None

        # Child Tax Credit phaseout
        ctc_raw = data.get("child_tax_credit_phaseout_start", {})
        ctc_phaseout = {k: float(v) for k, v in ctc_raw.items()} if ctc_raw else None

        # EITC
        eitc_max_raw = data.get("eitc_max_credit", {})
        eitc_max = {int(k): float(v) for k, v in eitc_max_raw.items()} if eitc_max_raw else None

        eitc_limits_raw = data.get("eitc_income_limits", {})
        eitc_phase_end = {}
        for status, limits in eitc_limits_raw.items():
            eitc_phase_end[status] = {int(k): float(v) for k, v in limits.items()}

        # Student loan interest phaseout
        student_loan_raw = data.get("student_loan_phaseout", {})
        student_loan_start = {}
        student_loan_end = {}
        for status, vals in student_loan_raw.items():
            student_loan_start[status] = float(vals.get("start", 0))
            student_loan_end[status] = float(vals.get("end", 0))

        # IRA phaseouts - covered by employer plan
        ira_covered_raw = data.get("ira_phaseout_covered", {})
        trad_ira_start_covered = {}
        trad_ira_end_covered = {}
        for status, vals in ira_covered_raw.items():
            trad_ira_start_covered[status] = float(vals.get("start", 0))
            trad_ira_end_covered[status] = float(vals.get("end", 0))

        # IRA phaseouts - spouse covered
        ira_spouse_raw = data.get("ira_phaseout_spouse_covered", {})
        trad_ira_start_spouse = {}
        trad_ira_end_spouse = {}
        for status, vals in ira_spouse_raw.items():
            trad_ira_start_spouse[status] = float(vals.get("start", 0))
            trad_ira_end_spouse[status] = float(vals.get("end", 0))

        # Roth IRA phaseouts
        roth_raw = data.get("roth_ira_phaseout", {})
        roth_start = {}
        roth_end = {}
        for status, vals in roth_raw.items():
            roth_start[status] = float(vals.get("start", 0))
            roth_end[status] = float(vals.get("end", 0))

        # QBI thresholds
        qbi_raw = data.get("qbi_threshold", {})
        qbi_start = {}
        qbi_end = {}
        for status, vals in qbi_raw.items():
            qbi_start[status] = float(vals.get("start", 0))
            qbi_end[status] = float(vals.get("end", 0))

        # Saver's Credit thresholds
        savers_raw = data.get("savers_credit_thresholds", {})
        savers_50 = {}
        savers_20 = {}
        savers_10 = {}
        for tier, limits in savers_raw.items():
            for status, amount in limits.items():
                if tier == "fifty_percent":
                    savers_50[status] = float(amount)
                elif tier == "twenty_percent":
                    savers_20[status] = float(amount)
                elif tier == "ten_percent":
                    savers_10[status] = float(amount)

        return TaxYearConfig(
            tax_year=tax_year,
            ordinary_income_brackets=brackets,
            standard_deduction=std,
            additional_standard_deduction_over_65_or_blind=additional,
            qd_ltcg_0_rate_threshold=qd_ltcg_0 or None,
            qd_ltcg_15_rate_threshold=qd_ltcg_15 or None,
            ss_wage_base=float(data.get("ss_wage_base", 176100)),
            medicare_rate=float(data.get("medicare_rate", 0.029)),
            ss_rate=float(data.get("ss_rate", 0.124)),
            additional_medicare_tax_rate=float(data.get("additional_medicare_tax_rate", 0.009)),
            additional_medicare_threshold=additional_medicare or None,
            niit_rate=float(data.get("niit_rate", 0.038)),
            niit_threshold=niit or None,
            amt_rate_26=float(data.get("amt_rate_26", 0.26)),
            amt_rate_28=float(data.get("amt_rate_28", 0.28)),
            amt_28_threshold=amt_28_threshold or None,
            amt_exemption=amt_exemption or None,
            amt_exemption_phaseout_start=amt_phaseout_start or None,
            amt_exemption_phaseout_rate=float(data.get("amt_exemption_phaseout_rate", 0.25)),
            child_tax_credit_amount=float(data.get("child_tax_credit_amount", 2000)),
            child_tax_credit_refundable=float(data.get("child_tax_credit_refundable", 1700)),
            child_tax_credit_phaseout_start=ctc_phaseout or None,
            child_tax_credit_phaseout_rate=float(data.get("child_tax_credit_phaseout_rate", 0.05)),
            eitc_max_credit=eitc_max or None,
            eitc_phaseout_end=eitc_phase_end or None,
            eitc_investment_income_limit=float(data.get("eitc_investment_income_limit", 11950)),
            traditional_ira_limit=float(data.get("ira_contribution_limit", 7000)),
            ira_catchup_50_plus=float(data.get("ira_catchup_50_plus", 1000)),
            hsa_individual_limit=float(data.get("hsa_individual_limit", 4300)),
            hsa_family_limit=float(data.get("hsa_family_limit", 8550)),
            hsa_catchup_55_plus=float(data.get("hsa_catchup_55_plus", 1000)),
            k401_limit=float(data.get("k401_contribution_limit", 23500)),
            k401_catchup_50_plus=float(data.get("k401_catchup_50_plus", 7500)),
            sep_ira_limit=float(data.get("sep_ira_limit", 69000)),
            student_loan_interest_max=float(data.get("student_loan_interest_max", 2500)),
            student_loan_phaseout_start=student_loan_start or None,
            student_loan_phaseout_end=student_loan_end or None,
            trad_ira_phaseout_start_covered=trad_ira_start_covered or None,
            trad_ira_phaseout_end_covered=trad_ira_end_covered or None,
            trad_ira_phaseout_start_spouse_covered=trad_ira_start_spouse or None,
            trad_ira_phaseout_end_spouse_covered=trad_ira_end_spouse or None,
            roth_ira_phaseout_start=roth_start or None,
            roth_ira_phaseout_end=roth_end or None,
            annual_gift_exclusion=float(data.get("annual_gift_exclusion", 19000)),
            estate_exemption=float(data.get("estate_exemption", 13990000)),
            salt_cap=float(data.get("salt_cap", 10000)),
            medical_expense_floor_pct=float(data.get("medical_expense_floor_pct", 0.075)),
            qbi_deduction_rate=float(data.get("qbi_deduction_rate", 0.20)),
            qbi_threshold_start=qbi_start or None,
            qbi_threshold_end=qbi_end or None,
            savers_credit_50_pct_limit=savers_50 or None,
            savers_credit_20_pct_limit=savers_20 or None,
            savers_credit_10_pct_limit=savers_10 or None,
            savers_credit_max_contribution=float(data.get("savers_credit_max_contribution", 2000)),
            # Section 179 / Depreciation
            section_179_limit=float(data.get("section_179_limit", 1250000)),
            section_179_phaseout_threshold=float(data.get("section_179_phaseout_threshold", 3130000)),
            bonus_depreciation_rate=float(data.get("bonus_depreciation_rate", 0.40)),
            # Adoption credit
            adoption_credit_max=float(data.get("adoption_credit_max", 16810)),
            adoption_credit_phaseout_start=float(data.get("adoption_credit_phaseout", {}).get("start", 252150)),
            adoption_credit_phaseout_end=float(data.get("adoption_credit_phaseout", {}).get("end", 292150)),
            # Capital loss limits
            capital_loss_limit=float(data.get("capital_loss_limit", 3000)),
            capital_loss_limit_mfs=float(data.get("capital_loss_limit_mfs", 1500)),
            # Energy credits
            residential_clean_energy_rate=float(data.get("residential_clean_energy_rate", 0.30)),
            energy_efficient_home_rate=float(data.get("energy_efficient_home_rate", 0.30)),
            energy_efficient_annual_limit=float(data.get("energy_efficient_annual_limit", 1200)),
        )

    @staticmethod
    def for_2024() -> "TaxYearConfig":
        """
        Load 2024 tax year configuration.

        HISTORICAL YEAR - Use for amended returns and year-over-year comparisons only.
        DO NOT use for current advisory services (use for_2025() instead).
        """
        return TaxYearConfig.for_year(2024)

    @staticmethod
    def for_2023() -> "TaxYearConfig":
        """
        Load 2023 tax year configuration.

        HISTORICAL YEAR - Use for amended returns and year-over-year comparisons only.
        DO NOT use for current advisory services (use for_2025() instead).
        """
        return TaxYearConfig.for_year(2023)

    @staticmethod
    def for_2022() -> "TaxYearConfig":
        """
        Load 2022 tax year configuration.

        HISTORICAL YEAR - Use for amended returns and year-over-year comparisons only.
        DO NOT use for current advisory services (use for_2025() instead).
        """
        return TaxYearConfig.for_year(2022)

    @staticmethod
    def for_2026() -> "TaxYearConfig":
        """
        Load 2026 tax year configuration.

        PROJECTED YEAR - Use for tax planning projections only.
        Values are estimated based on inflation projections until IRS releases official figures.
        DO NOT use for current advisory services (use for_2025() instead).
        """
        return TaxYearConfig.for_year(2026)

    @staticmethod
    def get_current_advisory_year() -> "TaxYearConfig":
        """
        Get the current advisory year configuration.

        This is the RECOMMENDED method for all advisory services and calculations.
        Currently returns 2025 configuration per IRS Rev. Proc. 2024-40.
        """
        return TaxYearConfig.for_2025()

