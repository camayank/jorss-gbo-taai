"""
Core Recommendation Generators - Credits, Deductions, Investment

SPEC-006: Core tax optimization recommendations.
"""

from typing import Dict, Any, List
import logging

from ..models import UnifiedRecommendation
from ..utils import (
    safe_float, safe_int, validate_profile, create_recommendation,
    estimate_marginal_rate, calculate_tax_savings, format_currency
)
from ..constants import (
    CREDIT_LIMITS, DEDUCTION_LIMITS, RETIREMENT_LIMITS,
    get_standard_deduction
)

logger = logging.getLogger(__name__)


def get_credit_optimizer_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Generate tax credit optimization recommendations.

    Analyzes eligibility for:
    - Child Tax Credit
    - Earned Income Tax Credit
    - Education Credits
    - Saver's Credit
    - Child and Dependent Care Credit
    """
    recs = []
    p = validate_profile(profile)

    agi = p.get("agi", 0)
    filing_status = p.get("filing_status", "single")
    num_children = p.get("num_children_under_17", 0)
    num_dependents = p.get("num_dependents", 0)

    # Child Tax Credit
    if num_children > 0:
        ctc_limit = CREDIT_LIMITS["child_tax_credit"]
        phaseout = CREDIT_LIMITS["ctc_phaseout_mfj"] if "married" in filing_status else CREDIT_LIMITS["ctc_phaseout_single"]

        if agi < phaseout:
            potential_credit = num_children * ctc_limit
            recs.append(create_recommendation(
                title="Child Tax Credit",
                description=f"You may qualify for up to {format_currency(potential_credit)} in Child Tax Credit "
                           f"for {num_children} qualifying child(ren) under age 17.",
                potential_savings=potential_credit,
                priority="high",
                category="credits",
                confidence=0.9,
                complexity="simple",
                action_items=[
                    "Verify each child has a valid SSN",
                    "Confirm children lived with you for more than half the year",
                    "Complete Schedule 8812 with your tax return"
                ],
                source="credit_optimizer"
            ))

    # Earned Income Tax Credit
    eitc_limit = CREDIT_LIMITS["eitc_phaseout_mfj"] if "married" in filing_status else CREDIT_LIMITS["eitc_phaseout_single"]
    if agi < eitc_limit and agi > 0:
        if num_dependents >= 3:
            max_eitc = CREDIT_LIMITS["eitc_max_3plus"]
        elif num_dependents == 2:
            max_eitc = 6960
        elif num_dependents == 1:
            max_eitc = 4213
        else:
            max_eitc = 632 if agi < 17640 else 0

        if max_eitc > 0:
            recs.append(create_recommendation(
                title="Earned Income Tax Credit",
                description=f"Based on your income and family size, you may qualify for up to "
                           f"{format_currency(max_eitc)} in EITC - a refundable credit.",
                potential_savings=max_eitc,
                priority="high",
                category="credits",
                confidence=0.85,
                complexity="moderate",
                action_items=[
                    "Verify you have earned income (wages or self-employment)",
                    "Ensure investment income is below $11,600",
                    "Complete Schedule EIC if you have qualifying children"
                ],
                requirements=["Must have earned income", "Investment income limit applies"],
                source="credit_optimizer"
            ))

    # Education Credits (AOTC)
    education_expenses = safe_float(p.get("education_expenses", 0))
    if education_expenses > 0:
        aotc_limit = CREDIT_LIMITS["aotc_max"]
        phaseout = CREDIT_LIMITS["aotc_phaseout_mfj" if "married" in filing_status else "aotc_phaseout_single"]

        if agi < phaseout.get("end", float("inf")):
            # AOTC = 100% of first $2,000 + 25% of next $2,000
            potential_credit = min(aotc_limit, min(education_expenses, 2000) + 0.25 * max(0, min(education_expenses - 2000, 2000)))

            recs.append(create_recommendation(
                title="American Opportunity Tax Credit",
                description=f"Your education expenses may qualify for up to {format_currency(potential_credit)} "
                           f"in AOTC. 40% of this credit is refundable even if you owe no tax.",
                potential_savings=potential_credit,
                priority="high",
                category="credits",
                confidence=0.85,
                complexity="moderate",
                action_items=[
                    "Obtain Form 1098-T from educational institution",
                    "Keep receipts for qualified education expenses",
                    "Complete Form 8863 with your return"
                ],
                requirements=["First 4 years of post-secondary education only"],
                source="credit_optimizer"
            ))

    # Saver's Credit
    retirement_contributions = safe_float(p.get("retirement_contributions", 0))
    if retirement_contributions > 0:
        savers_limit = CREDIT_LIMITS["savers_credit_phaseout_mfj"] if "married" in filing_status else CREDIT_LIMITS["savers_credit_phaseout_single"]

        if agi < savers_limit:
            # Determine credit rate based on AGI
            if filing_status == "married_filing_jointly":
                if agi <= 46000:
                    rate = 0.50
                elif agi <= 50000:
                    rate = 0.20
                else:
                    rate = 0.10
            else:
                if agi <= 23000:
                    rate = 0.50
                elif agi <= 25000:
                    rate = 0.20
                else:
                    rate = 0.10

            contribution_limit = 2000 if filing_status != "married_filing_jointly" else 4000
            credit_amount = min(retirement_contributions, contribution_limit) * rate

            if credit_amount > 0:
                recs.append(create_recommendation(
                    title="Saver's Credit",
                    description=f"Your retirement contributions qualify for a {int(rate*100)}% credit "
                               f"worth up to {format_currency(credit_amount)}.",
                    potential_savings=credit_amount,
                    priority="medium",
                    category="credits",
                    confidence=0.9,
                    complexity="simple",
                    action_items=[
                        "Verify your retirement contributions on W-2 or IRA statements",
                        "Credit is claimed automatically when you report contributions"
                    ],
                    source="credit_optimizer"
                ))

    return recs


def get_deduction_analyzer_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Generate deduction optimization recommendations.

    Analyzes:
    - Standard vs itemized deduction
    - SALT optimization
    - Charitable contribution strategies
    - Medical expense threshold
    """
    recs = []
    p = validate_profile(profile)

    agi = p.get("agi", 0)
    filing_status = p.get("filing_status", "single")
    marginal_rate = estimate_marginal_rate(agi, filing_status)

    # Get standard deduction
    standard_deduction = get_standard_deduction(filing_status)

    # Calculate itemized total
    mortgage_interest = safe_float(p.get("mortgage_interest", 0))
    state_local_taxes = min(safe_float(p.get("state_local_taxes", 0)), DEDUCTION_LIMITS["salt_cap"])
    charitable = safe_float(p.get("charitable_contributions", 0))
    medical = safe_float(p.get("medical_expenses", 0))

    # Medical expense threshold
    medical_threshold = agi * DEDUCTION_LIMITS["medical_agi_threshold"]
    deductible_medical = max(0, medical - medical_threshold)

    itemized_total = mortgage_interest + state_local_taxes + charitable + deductible_medical

    # Standard vs Itemized comparison
    if itemized_total > standard_deduction:
        extra_savings = calculate_tax_savings(itemized_total - standard_deduction, marginal_rate)
        recs.append(create_recommendation(
            title="Itemize Your Deductions",
            description=f"Your itemized deductions ({format_currency(itemized_total)}) exceed the standard "
                       f"deduction ({format_currency(standard_deduction)}). Itemizing saves you an additional "
                       f"{format_currency(extra_savings)} in taxes.",
            potential_savings=extra_savings,
            priority="high",
            category="deductions",
            confidence=0.95,
            complexity="simple",
            action_items=[
                "Gather all receipts for deductible expenses",
                "Complete Schedule A with your return",
                "Keep records for at least 3 years"
            ],
            source="deduction_analyzer"
        ))
    else:
        shortfall = standard_deduction - itemized_total

        # Bunching strategy
        if itemized_total > standard_deduction * 0.7:
            recs.append(create_recommendation(
                title="Consider Deduction Bunching Strategy",
                description=f"Your itemized deductions are {format_currency(shortfall)} short of the standard deduction. "
                           f"Consider 'bunching' - combining two years of deductions into one year to exceed "
                           f"the standard deduction threshold.",
                potential_savings=shortfall * marginal_rate * 0.5,  # Conservative estimate
                priority="medium",
                category="deductions",
                confidence=0.8,
                complexity="moderate",
                action_items=[
                    "Prepay next year's property taxes (subject to SALT cap)",
                    "Make charitable contributions early",
                    "Schedule elective medical procedures in bunching year"
                ],
                source="deduction_analyzer"
            ))

    # SALT Cap Warning
    actual_salt = safe_float(p.get("state_local_taxes", 0))
    if actual_salt > DEDUCTION_LIMITS["salt_cap"]:
        lost_deduction = actual_salt - DEDUCTION_LIMITS["salt_cap"]
        lost_savings = calculate_tax_savings(lost_deduction, marginal_rate)

        recs.append(create_recommendation(
            title="SALT Cap Limitation",
            description=f"Your state and local taxes ({format_currency(actual_salt)}) exceed the {format_currency(DEDUCTION_LIMITS['salt_cap'])} SALT cap. "
                       f"You're losing {format_currency(lost_savings)} in potential tax savings.",
            potential_savings=lost_savings,
            priority="medium",
            category="deductions",
            confidence=0.95,
            complexity="complex",
            action_items=[
                "Consider relocating to a lower-tax state if significant",
                "Maximize other deductions to offset the loss",
                "Explore Pass-Through Entity Tax (PTET) if you have business income"
            ],
            warnings=["SALT cap is a current law limitation"],
            source="deduction_analyzer"
        ))

    # Charitable Contribution Optimization
    if charitable > 0:
        # Donor Advised Fund suggestion for high earners
        if agi > 200000 and charitable > 5000:
            recs.append(create_recommendation(
                title="Donor Advised Fund Strategy",
                description="Consider using a Donor Advised Fund (DAF) to front-load charitable deductions. "
                           "You can take the deduction now and distribute to charities over time.",
                potential_savings=charitable * marginal_rate * 0.2,  # Timing benefit
                priority="medium",
                category="deductions",
                confidence=0.85,
                complexity="moderate",
                action_items=[
                    "Open a DAF account at Fidelity Charitable, Schwab, or similar",
                    "Contribute appreciated securities for additional tax benefit",
                    "Make a lump-sum contribution before year-end"
                ],
                source="deduction_analyzer"
            ))

    return recs


def get_investment_optimizer_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Generate investment tax optimization recommendations.

    Analyzes:
    - Capital gains/losses harvesting
    - Asset location optimization
    - Dividend tax efficiency
    """
    recs = []
    p = validate_profile(profile)

    agi = p.get("agi", 0)
    filing_status = p.get("filing_status", "single")
    capital_gains = safe_float(p.get("capital_gains", 0))
    investment_income = safe_float(p.get("investment_income", 0))
    marginal_rate = estimate_marginal_rate(agi, filing_status)

    # Tax-Loss Harvesting
    if capital_gains > 0:
        # Suggest tax-loss harvesting
        potential_savings = min(capital_gains, 3000) * marginal_rate

        recs.append(create_recommendation(
            title="Tax-Loss Harvesting Opportunity",
            description=f"With {format_currency(capital_gains)} in capital gains, consider selling "
                       f"investments with losses to offset gains. Up to $3,000 in excess losses "
                       f"can offset ordinary income.",
            potential_savings=potential_savings,
            priority="medium",
            category="investment",
            confidence=0.8,
            complexity="moderate",
            action_items=[
                "Review portfolio for positions with unrealized losses",
                "Sell losing positions before year-end",
                "Avoid wash sale rule - wait 31 days before repurchasing similar securities"
            ],
            warnings=["Wash sale rule prohibits repurchasing substantially identical securities within 30 days"],
            source="investment_optimizer"
        ))

    # Long-term vs Short-term gains
    if capital_gains > 10000:
        ltcg_rate = 0.15  # Assume 15% LTCG rate for most
        ordinary_rate = marginal_rate

        if ordinary_rate > ltcg_rate:
            rate_difference = ordinary_rate - ltcg_rate
            potential_benefit = capital_gains * rate_difference

            recs.append(create_recommendation(
                title="Hold Investments for Long-Term Treatment",
                description=f"Long-term capital gains (held >1 year) are taxed at {int(ltcg_rate*100)}% vs "
                           f"{int(ordinary_rate*100)}% for short-term. Holding investments longer could save "
                           f"up to {format_currency(potential_benefit)} on {format_currency(capital_gains)} in gains.",
                potential_savings=potential_benefit,
                priority="medium",
                category="investment",
                confidence=0.9,
                complexity="simple",
                action_items=[
                    "Check holding periods before selling",
                    "If close to 1-year mark, consider waiting",
                    "Track cost basis accurately"
                ],
                source="investment_optimizer"
            ))

    # Qualified Dividends
    if investment_income > 1000:
        recs.append(create_recommendation(
            title="Prioritize Qualified Dividends",
            description="Qualified dividends are taxed at lower long-term capital gains rates (0%, 15%, or 20%) "
                       "rather than ordinary income rates. Consider dividend stocks that pay qualified dividends.",
            potential_savings=investment_income * 0.1,  # Rough estimate of benefit
            priority="low",
            category="investment",
            confidence=0.75,
            complexity="simple",
            action_items=[
                "Review dividend types in your brokerage statements",
                "Prefer US stocks and qualified foreign corporations",
                "Hold dividend stocks for at least 61 days around ex-dividend date"
            ],
            source="investment_optimizer"
        ))

    # Net Investment Income Tax
    niit_threshold = 250000 if "married" in filing_status else 200000
    if agi > niit_threshold and investment_income > 0:
        niit_amount = min(investment_income, agi - niit_threshold) * 0.038

        recs.append(create_recommendation(
            title="Net Investment Income Tax Planning",
            description=f"Your income exceeds the NIIT threshold. You may owe an additional 3.8% tax on "
                       f"investment income ({format_currency(niit_amount)} estimated). Consider strategies to reduce MAGI.",
            potential_savings=niit_amount,
            priority="medium",
            category="investment",
            confidence=0.85,
            complexity="complex",
            action_items=[
                "Maximize above-the-line deductions to reduce MAGI",
                "Consider municipal bonds (exempt from NIIT)",
                "Time investment sales strategically"
            ],
            source="investment_optimizer"
        ))

    return recs
