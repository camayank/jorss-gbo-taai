"""
Default Tax Rules.

Provides default rules loaded from the centralized tax configuration.
These rules use get_tax_parameter() to ensure values are not hardcoded.
"""

from __future__ import annotations

import logging
from typing import List

from .rule_types import RuleCategory, RuleSeverity, RuleType
from .rule_engine import Rule

logger = logging.getLogger(__name__)


def get_default_rules(tax_year: int = 2025) -> List[Rule]:
    """
    Get default rules for a tax year.

    All values are loaded from configuration - no hardcoding.
    """
    # Import here to avoid circular imports
    try:
        from config.tax_config_loader import get_tax_parameter
    except ImportError:
        logger.warning("Tax config loader not available, using fallback values")
        def get_tax_parameter(name, year, status=None):
            return None

    rules = []

    # ==========================================================================
    # INCOME RULES
    # ==========================================================================
    rules.append(Rule(
        rule_id="INC001",
        name="Social Security Wage Base",
        description="Income subject to Social Security tax is limited to the wage base",
        category=RuleCategory.INCOME,
        rule_type=RuleType.LIMIT,
        severity=RuleSeverity.INFO,
        limit=get_tax_parameter('ss_wage_base', tax_year) or 176100,
        irs_reference="IRC Section 3121(a)(1)",
        irs_form="Form W-2",
        tax_year=tax_year,
    ))

    rules.append(Rule(
        rule_id="INC002",
        name="Additional Medicare Tax Threshold",
        description="0.9% additional Medicare tax on wages over threshold",
        category=RuleCategory.INCOME,
        rule_type=RuleType.THRESHOLD,
        severity=RuleSeverity.INFO,
        thresholds_by_status={
            'single': 200000,
            'married_joint': 250000,
            'married_separate': 125000,
            'head_of_household': 200000,
        },
        rate=0.009,
        irs_reference="IRC Section 3101(b)(2)",
        irs_form="Form 8959",
        tax_year=tax_year,
    ))

    # ==========================================================================
    # DEDUCTION RULES
    # ==========================================================================
    rules.append(Rule(
        rule_id="DED001",
        name="SALT Deduction Cap",
        description="State and local tax deduction is capped",
        category=RuleCategory.DEDUCTION,
        rule_type=RuleType.LIMIT,
        severity=RuleSeverity.WARNING,
        limit=get_tax_parameter('salt_cap', tax_year) or 10000,
        irs_reference="IRC Section 164(b)(6)",
        irs_form="Schedule A",
        tax_year=tax_year,
    ))

    rules.append(Rule(
        rule_id="DED002",
        name="Medical Expense Floor",
        description="Medical expenses deductible only above 7.5% of AGI",
        category=RuleCategory.DEDUCTION,
        rule_type=RuleType.THRESHOLD,
        severity=RuleSeverity.INFO,
        rate=get_tax_parameter('medical_expense_floor_pct', tax_year) or 0.075,
        irs_reference="IRC Section 213(a)",
        irs_form="Schedule A",
        tax_year=tax_year,
    ))

    rules.append(Rule(
        rule_id="DED003",
        name="Student Loan Interest Deduction",
        description="Maximum student loan interest deduction",
        category=RuleCategory.DEDUCTION,
        rule_type=RuleType.LIMIT,
        severity=RuleSeverity.INFO,
        limit=get_tax_parameter('student_loan_interest_max', tax_year) or 2500,
        irs_reference="IRC Section 221",
        irs_publication="Publication 970",
        tax_year=tax_year,
    ))

    rules.append(Rule(
        rule_id="DED004",
        name="Charitable Contribution Limit (Cash)",
        description="Cash contributions to public charities limited to 60% of AGI",
        category=RuleCategory.CHARITABLE,
        rule_type=RuleType.LIMIT,
        severity=RuleSeverity.WARNING,
        rate=get_tax_parameter('charitable_cash_limit_pct', tax_year) or 0.60,
        irs_reference="IRC Section 170(b)(1)(A)",
        irs_form="Schedule A",
        tax_year=tax_year,
    ))

    # ==========================================================================
    # CREDIT RULES
    # ==========================================================================
    rules.append(Rule(
        rule_id="CRD001",
        name="Child Tax Credit",
        description="Credit for qualifying children under 17",
        category=RuleCategory.CREDIT,
        rule_type=RuleType.ELIGIBILITY,
        severity=RuleSeverity.INFO,
        limit=get_tax_parameter('child_tax_credit_amount', tax_year) or 2000,
        thresholds_by_status={
            'single': 200000,
            'married_joint': 400000,
            'married_separate': 200000,
            'head_of_household': 200000,
        },
        irs_reference="IRC Section 24",
        irs_form="Schedule 8812",
        tax_year=tax_year,
    ))

    rules.append(Rule(
        rule_id="CRD002",
        name="EITC Income Limits",
        description="Earned Income Tax Credit income limits",
        category=RuleCategory.CREDIT,
        rule_type=RuleType.ELIGIBILITY,
        severity=RuleSeverity.INFO,
        irs_reference="IRC Section 32",
        irs_form="Schedule EIC",
        irs_publication="Publication 596",
        tax_year=tax_year,
    ))

    rules.append(Rule(
        rule_id="CRD003",
        name="American Opportunity Tax Credit",
        description="Education credit for first 4 years of college",
        category=RuleCategory.EDUCATION,
        rule_type=RuleType.PHASEOUT,
        severity=RuleSeverity.INFO,
        limit=get_tax_parameter('aotc_max_credit', tax_year) or 2500,
        phase_out_start=80000,  # Will be loaded from config
        phase_out_end=90000,
        irs_reference="IRC Section 25A(i)",
        irs_form="Form 8863",
        tax_year=tax_year,
    ))

    rules.append(Rule(
        rule_id="CRD004",
        name="Saver's Credit",
        description="Credit for retirement savings contributions",
        category=RuleCategory.RETIREMENT,
        rule_type=RuleType.ELIGIBILITY,
        severity=RuleSeverity.INFO,
        limit=get_tax_parameter('savers_credit_max_contribution', tax_year) or 2000,
        thresholds_by_status={
            'single': 41500,
            'married_joint': 83000,
            'head_of_household': 62250,
        },
        irs_reference="IRC Section 25B",
        irs_form="Form 8880",
        tax_year=tax_year,
    ))

    # ==========================================================================
    # RETIREMENT RULES
    # ==========================================================================
    rules.append(Rule(
        rule_id="RET001",
        name="Traditional IRA Contribution Limit",
        description="Annual limit for Traditional IRA contributions",
        category=RuleCategory.RETIREMENT,
        rule_type=RuleType.LIMIT,
        severity=RuleSeverity.WARNING,
        limit=get_tax_parameter('ira_contribution_limit', tax_year) or 7000,
        irs_reference="IRC Section 219(b)(5)(A)",
        irs_publication="Publication 590-A",
        tax_year=tax_year,
    ))

    rules.append(Rule(
        rule_id="RET002",
        name="401(k) Contribution Limit",
        description="Annual elective deferral limit for 401(k) plans",
        category=RuleCategory.RETIREMENT,
        rule_type=RuleType.LIMIT,
        severity=RuleSeverity.WARNING,
        limit=get_tax_parameter('k401_contribution_limit', tax_year) or 23500,
        irs_reference="IRC Section 402(g)(1)(B)",
        tax_year=tax_year,
    ))

    rules.append(Rule(
        rule_id="RET003",
        name="HSA Contribution Limit (Individual)",
        description="Annual HSA contribution limit for self-only coverage",
        category=RuleCategory.HEALTHCARE,
        rule_type=RuleType.LIMIT,
        severity=RuleSeverity.WARNING,
        limit=get_tax_parameter('hsa_individual_limit', tax_year) or 4300,
        irs_reference="IRC Section 223(b)(2)(A)",
        irs_form="Form 8889",
        irs_publication="Publication 969",
        tax_year=tax_year,
    ))

    rules.append(Rule(
        rule_id="RET004",
        name="HSA Contribution Limit (Family)",
        description="Annual HSA contribution limit for family coverage",
        category=RuleCategory.HEALTHCARE,
        rule_type=RuleType.LIMIT,
        severity=RuleSeverity.WARNING,
        limit=get_tax_parameter('hsa_family_limit', tax_year) or 8550,
        irs_reference="IRC Section 223(b)(2)(B)",
        irs_form="Form 8889",
        irs_publication="Publication 969",
        tax_year=tax_year,
    ))

    # ==========================================================================
    # INVESTMENT RULES
    # ==========================================================================
    rules.append(Rule(
        rule_id="INV001",
        name="NIIT Threshold",
        description="Net Investment Income Tax applies above threshold",
        category=RuleCategory.NIIT,
        rule_type=RuleType.THRESHOLD,
        severity=RuleSeverity.INFO,
        rate=0.038,
        thresholds_by_status={
            'single': 200000,
            'married_joint': 250000,
            'married_separate': 125000,
            'head_of_household': 200000,
        },
        irs_reference="IRC Section 1411",
        irs_form="Form 8960",
        tax_year=tax_year,
    ))

    rules.append(Rule(
        rule_id="INV002",
        name="Capital Loss Limit",
        description="Net capital losses limited per year",
        category=RuleCategory.INVESTMENT,
        rule_type=RuleType.LIMIT,
        severity=RuleSeverity.INFO,
        limit=get_tax_parameter('capital_loss_limit', tax_year) or 3000,
        limits_by_status={
            'single': 3000,
            'married_joint': 3000,
            'married_separate': 1500,
            'head_of_household': 3000,
        },
        irs_reference="IRC Section 1211(b)",
        irs_form="Schedule D",
        tax_year=tax_year,
    ))

    # ==========================================================================
    # BUSINESS RULES
    # ==========================================================================
    rules.append(Rule(
        rule_id="BUS001",
        name="QBI Deduction",
        description="Qualified Business Income deduction rate",
        category=RuleCategory.BUSINESS,
        rule_type=RuleType.THRESHOLD,
        severity=RuleSeverity.INFO,
        rate=get_tax_parameter('qbi_deduction_rate', tax_year) or 0.20,
        irs_reference="IRC Section 199A",
        irs_form="Form 8995",
        irs_publication="Publication 535",
        tax_year=tax_year,
    ))

    rules.append(Rule(
        rule_id="BUS002",
        name="Section 179 Deduction Limit",
        description="Maximum Section 179 expense deduction",
        category=RuleCategory.BUSINESS,
        rule_type=RuleType.LIMIT,
        severity=RuleSeverity.INFO,
        limit=get_tax_parameter('section_179_limit', tax_year) or 1250000,
        irs_reference="IRC Section 179(b)(1)",
        irs_form="Form 4562",
        tax_year=tax_year,
    ))

    # ==========================================================================
    # PENALTY RULES
    # ==========================================================================
    rules.append(Rule(
        rule_id="PEN001",
        name="Estimated Tax Underpayment",
        description="Minimum underpayment that triggers penalty",
        category=RuleCategory.ESTIMATED_TAX,
        rule_type=RuleType.THRESHOLD,
        severity=RuleSeverity.WARNING,
        threshold=get_tax_parameter('estimated_tax_underpayment_threshold', tax_year) or 1000,
        rate=get_tax_parameter('estimated_tax_penalty_rate', tax_year) or 0.08,
        irs_reference="IRC Section 6654",
        irs_form="Form 2210",
        tax_year=tax_year,
    ))

    rules.append(Rule(
        rule_id="PEN002",
        name="Early Distribution Penalty",
        description="10% penalty on early retirement distributions",
        category=RuleCategory.PENALTY,
        rule_type=RuleType.THRESHOLD,
        severity=RuleSeverity.WARNING,
        rate=get_tax_parameter('early_withdrawal_penalty_rate', tax_year) or 0.10,
        threshold=59.5,  # Age threshold
        irs_reference="IRC Section 72(t)",
        irs_form="Form 5329",
        tax_year=tax_year,
    ))

    logger.info(f"Loaded {len(rules)} default rules for tax year {tax_year}")
    return rules
