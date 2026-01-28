"""
Retirement Recommendation Generators

SPEC-006: Retirement planning and optimization recommendations.
"""

from typing import Dict, Any, List
import logging

from ..models import UnifiedRecommendation
from ..utils import (
    safe_float, safe_int, validate_profile, create_recommendation,
    estimate_marginal_rate, calculate_tax_savings, format_currency
)
from ..constants import (
    RETIREMENT_LIMITS, ROTH_IRA_PHASEOUT, TRAD_IRA_PHASEOUT,
    MEDICARE_IRMAA, SOCIAL_SECURITY_LIMITS
)

logger = logging.getLogger(__name__)


def get_retirement_optimizer_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Generate retirement contribution optimization recommendations.

    Analyzes:
    - 401(k) contribution optimization
    - IRA contribution opportunities
    - Catch-up contribution eligibility
    - HSA triple tax advantage
    """
    recs = []
    p = validate_profile(profile)

    agi = p.get("agi", 0)
    age = p.get("age", 35)
    filing_status = p.get("filing_status", "single")
    marginal_rate = estimate_marginal_rate(agi, filing_status)

    current_401k = safe_float(p.get("retirement_contributions", 0))
    current_ira = safe_float(p.get("ira_contributions", 0))
    has_employer_plan = p.get("has_employer_retirement", False)

    # 401(k) Maximization
    limit_401k = RETIREMENT_LIMITS["401k_limit"]
    catch_up_401k = RETIREMENT_LIMITS["401k_catch_up_50plus"] if age >= 50 else 0

    # Super catch-up for 60-63
    if 60 <= age <= 63:
        catch_up_401k = RETIREMENT_LIMITS["401k_catch_up_60_63"]

    total_401k_limit = limit_401k + catch_up_401k

    if has_employer_plan and current_401k < total_401k_limit:
        additional_contribution = total_401k_limit - current_401k
        tax_savings = calculate_tax_savings(additional_contribution, marginal_rate)

        recs.append(create_recommendation(
            title="Maximize 401(k) Contributions",
            description=f"You can contribute an additional {format_currency(additional_contribution)} to your 401(k) "
                       f"(limit: {format_currency(total_401k_limit)}). This would save approximately "
                       f"{format_currency(tax_savings)} in taxes this year.",
            potential_savings=tax_savings,
            priority="high",
            category="retirement",
            confidence=0.95,
            complexity="simple",
            action_items=[
                "Contact HR to increase your 401(k) contribution percentage",
                "Consider front-loading contributions if your plan allows",
                "Ensure you're getting full employer match first"
            ],
            source="retirement_optimizer"
        ))

    # IRA Contribution
    ira_limit = RETIREMENT_LIMITS["ira_limit"]
    ira_catch_up = RETIREMENT_LIMITS["ira_catch_up_50plus"] if age >= 50 else 0
    total_ira_limit = ira_limit + ira_catch_up

    if current_ira < total_ira_limit:
        additional_ira = total_ira_limit - current_ira

        # Check deductibility for Traditional IRA
        if has_employer_plan:
            phaseout = TRAD_IRA_PHASEOUT.get(filing_status, TRAD_IRA_PHASEOUT["single"])
            if agi < phaseout["start"]:
                deductible = True
            elif agi < phaseout["end"]:
                deductible_pct = (phaseout["end"] - agi) / (phaseout["end"] - phaseout["start"])
                deductible = deductible_pct > 0.5
            else:
                deductible = False
        else:
            deductible = True

        if deductible:
            tax_savings = calculate_tax_savings(additional_ira, marginal_rate)
            recs.append(create_recommendation(
                title="Contribute to Traditional IRA",
                description=f"You can contribute up to {format_currency(additional_ira)} more to a Traditional IRA. "
                           f"This deductible contribution would save {format_currency(tax_savings)} in taxes.",
                potential_savings=tax_savings,
                priority="high",
                category="retirement",
                confidence=0.9,
                complexity="simple",
                action_items=[
                    "Open IRA at preferred brokerage if needed",
                    f"Contribute by April 15, {p.get('tax_year', 2025) + 1} for this tax year",
                    "Choose investments based on your timeline"
                ],
                source="retirement_optimizer"
            ))

    # HSA Triple Tax Advantage
    has_hdhp = p.get("has_hdhp", False)
    current_hsa = safe_float(p.get("hsa_contributions", 0))

    if has_hdhp:
        hsa_limit = RETIREMENT_LIMITS["hsa_family"] if "married" in filing_status else RETIREMENT_LIMITS["hsa_single"]
        hsa_catch_up = RETIREMENT_LIMITS["hsa_catch_up_55plus"] if age >= 55 else 0
        total_hsa_limit = hsa_limit + hsa_catch_up

        if current_hsa < total_hsa_limit:
            additional_hsa = total_hsa_limit - current_hsa
            tax_savings = calculate_tax_savings(additional_hsa, marginal_rate)

            recs.append(create_recommendation(
                title="Maximize HSA Contributions",
                description=f"HSAs offer a triple tax advantage: tax-deductible contributions, tax-free growth, and "
                           f"tax-free withdrawals for medical expenses. You can contribute {format_currency(additional_hsa)} more.",
                potential_savings=tax_savings,
                priority="high",
                category="retirement",
                confidence=0.95,
                complexity="simple",
                action_items=[
                    "Contribute via payroll for FICA tax savings too",
                    "Keep receipts for qualified medical expenses",
                    "Consider investing HSA funds for long-term growth"
                ],
                metadata={"tip": "HSAs can be used like a stealth retirement account"},
                source="retirement_optimizer"
            ))

    return recs


def get_backdoor_roth_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Generate Backdoor Roth IRA recommendations for high earners.
    """
    recs = []
    p = validate_profile(profile)

    agi = p.get("agi", 0)
    filing_status = p.get("filing_status", "single")

    # Check Roth IRA eligibility
    roth_phaseout = ROTH_IRA_PHASEOUT.get(filing_status, ROTH_IRA_PHASEOUT["single"])

    if agi > roth_phaseout["end"]:
        # Income too high for direct Roth contribution
        ira_limit = RETIREMENT_LIMITS["ira_limit"]

        recs.append(create_recommendation(
            title="Backdoor Roth IRA Strategy",
            description=f"Your income ({format_currency(agi)}) exceeds Roth IRA limits. Use the 'Backdoor Roth' strategy: "
                       f"contribute to a non-deductible Traditional IRA, then convert to Roth. This allows up to "
                       f"{format_currency(ira_limit)} annually in tax-free growth.",
            potential_savings=ira_limit * 0.25,  # Long-term tax-free growth benefit estimate
            priority="high",
            category="retirement",
            confidence=0.9,
            complexity="moderate",
            action_items=[
                "Contribute to a non-deductible Traditional IRA",
                "Convert to Roth IRA shortly after (same year if possible)",
                "File Form 8606 to track non-deductible basis",
                "IMPORTANT: Avoid pro-rata rule issues by rolling existing Traditional IRA to 401(k)"
            ],
            warnings=[
                "Pro-rata rule applies if you have other Traditional IRA balances",
                "Consult a tax professional if you have existing Traditional IRA funds"
            ],
            source="backdoor_roth"
        ))

    # Mega Backdoor Roth
    has_401k = p.get("has_employer_retirement", False)
    if has_401k and agi > 200000:
        recs.append(create_recommendation(
            title="Mega Backdoor Roth Opportunity",
            description="If your 401(k) plan allows after-tax contributions with in-service distributions, "
                       "you can contribute up to $69,000 total (including employer match) and convert the "
                       "after-tax portion to Roth. This 'Mega Backdoor Roth' strategy provides significant additional "
                       "tax-advantaged savings.",
            potential_savings=15000,  # Conservative estimate of benefit
            priority="medium",
            category="retirement",
            confidence=0.7,
            complexity="complex",
            action_items=[
                "Check if your 401(k) allows after-tax contributions",
                "Verify in-service distribution or in-plan Roth conversion is available",
                "Coordinate with HR and plan administrator",
                "Consult tax professional for implementation"
            ],
            requirements=["401(k) must allow after-tax contributions", "Must allow in-service distributions"],
            source="backdoor_roth"
        ))

    return recs


def get_medicare_irmaa_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Generate Medicare IRMAA planning recommendations.

    IRMAA = Income-Related Monthly Adjustment Amount
    Affects Medicare Part B and Part D premiums based on MAGI from 2 years prior.
    """
    recs = []
    p = validate_profile(profile)

    agi = p.get("agi", 0)
    age = p.get("age", 35)
    filing_status = p.get("filing_status", "single")

    # IRMAA only applies at age 65+, but planning should start earlier
    if age < 60:
        return recs

    # Get IRMAA thresholds
    thresholds = MEDICARE_IRMAA.get(
        "married_filing_jointly" if "married" in filing_status else "single",
        MEDICARE_IRMAA["single"]
    )

    # Find current IRMAA tier
    current_surcharge = 0
    for threshold, surcharge in thresholds:
        if agi <= threshold:
            current_surcharge = surcharge
            break

    if current_surcharge > 0:
        annual_surcharge = current_surcharge * 12 * (2 if "married" in filing_status else 1)

        # Find next lower threshold
        for i, (threshold, surcharge) in enumerate(thresholds):
            if agi <= threshold:
                if i > 0:
                    target_income = thresholds[i-1][0]
                    reduction_needed = agi - target_income
                    lower_surcharge = thresholds[i-1][1]
                    potential_savings = (current_surcharge - lower_surcharge) * 12 * (2 if "married" in filing_status else 1)

                    recs.append(create_recommendation(
                        title="Reduce Medicare IRMAA Surcharges",
                        description=f"Your income triggers Medicare premium surcharges of {format_currency(annual_surcharge)}/year. "
                                   f"Reducing MAGI by {format_currency(reduction_needed)} to below "
                                   f"{format_currency(target_income)} would save {format_currency(potential_savings)}/year.",
                        potential_savings=potential_savings,
                        priority="high" if potential_savings > 1000 else "medium",
                        category="retirement",
                        confidence=0.9,
                        complexity="moderate",
                        action_items=[
                            "Maximize tax-deferred retirement contributions",
                            "Consider Roth conversions in lower-income years",
                            "Donate appreciated securities directly to charity",
                            "Time capital gains realizations strategically"
                        ],
                        metadata={"irmaa_lookback": "2 years prior"},
                        source="medicare_irmaa"
                    ))
                break

    # Planning for approaching Medicare age
    if 60 <= age < 65:
        recs.append(create_recommendation(
            title="Medicare IRMAA Planning Window",
            description="Medicare premiums are based on income from 2 years prior. Plan now to manage your "
                       "income in the years before you turn 65 to minimize premium surcharges.",
            potential_savings=2000,  # Conservative estimate
            priority="medium",
            category="retirement",
            confidence=0.85,
            complexity="moderate",
            action_items=[
                "Project income for the 2 years before Medicare eligibility",
                "Consider accelerating or deferring income",
                "Plan Roth conversions strategically",
                "Review required minimum distribution strategy"
            ],
            source="medicare_irmaa"
        ))

    return recs


def get_social_security_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Generate Social Security optimization recommendations.
    """
    recs = []
    p = validate_profile(profile)

    age = p.get("age", 35)
    agi = p.get("agi", 0)
    filing_status = p.get("filing_status", "single")

    # Social Security planning for those approaching retirement
    if age < 55:
        return recs

    fra = SOCIAL_SECURITY_LIMITS["full_retirement_age"]

    if 55 <= age < 62:
        recs.append(create_recommendation(
            title="Social Security Claiming Strategy Planning",
            description=f"You're approaching Social Security eligibility. Your Full Retirement Age is {fra}. "
                       f"Claiming at 62 reduces benefits by up to 30%, while delaying to 70 increases benefits 8%/year.",
            potential_savings=10000,  # Long-term benefit of optimal timing
            priority="medium",
            category="retirement",
            confidence=0.9,
            complexity="moderate",
            action_items=[
                "Create an account at ssa.gov to view your benefit estimates",
                "Consider your health, other income sources, and spouse's benefits",
                "Run break-even analyses for different claiming ages",
                "Factor in survivor benefits if married"
            ],
            source="social_security"
        ))

    # Social Security taxation
    ss_benefits = safe_float(p.get("social_security_benefits", 0))
    if ss_benefits > 0:
        # Provisional income calculation
        provisional_income = agi + (ss_benefits * 0.5)

        # Taxation thresholds
        if filing_status == "married_filing_jointly":
            first_threshold = 32000
            second_threshold = 44000
        else:
            first_threshold = 25000
            second_threshold = 34000

        if provisional_income > second_threshold:
            taxable_pct = 0.85
            tax_on_ss = ss_benefits * taxable_pct * estimate_marginal_rate(agi, filing_status)

            recs.append(create_recommendation(
                title="Social Security Taxation Reduction",
                description=f"Up to 85% of your Social Security benefits ({format_currency(ss_benefits)}) "
                           f"may be taxable due to your other income. Consider strategies to reduce "
                           f"provisional income and minimize the taxation of benefits.",
                potential_savings=tax_on_ss * 0.2,  # Potential reduction
                priority="medium",
                category="retirement",
                confidence=0.85,
                complexity="moderate",
                action_items=[
                    "Consider Roth conversions before claiming SS to reduce future RMDs",
                    "Draw from Roth accounts to reduce taxable income",
                    "Time capital gains carefully",
                    "Consider tax-exempt municipal bonds"
                ],
                source="social_security"
            ))

    return recs
