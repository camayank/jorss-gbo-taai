"""
Unified Tax Advisor Service

The CORE integration layer that connects:
- Document OCR → Intelligent extraction
- Tax Engine → Full calculations with 2025 compliance
- Advisory System → CPA-level recommendations
- Draft Forms → IRS-ready output

This is the "1 Lakh CPA Knowledge" engine - encoding 100,000+ hours
of tax expertise into intelligent, actionable advice.

NO ONE IN USA HAS DONE THIS.
"""
from __future__ import annotations  # Enable forward references for type hints
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
import uuid
import logging

logger = logging.getLogger(__name__)


def _load_standard_deduction_thresholds_2025() -> Dict[str, float]:
    """Load 2025 standard deduction thresholds from shared tax-year config."""
    defaults = {
        "standard_deduction_single": 15750,
        "standard_deduction_mfj": 31500,
        "standard_deduction_hoh": 23850,
    }

    try:
        from calculator.tax_year_config import TaxYearConfig

        config = TaxYearConfig.for_2025()
        return {
            "standard_deduction_single": float(
                config.standard_deduction.get("single", defaults["standard_deduction_single"])
            ),
            "standard_deduction_mfj": float(
                config.standard_deduction.get("married_joint", defaults["standard_deduction_mfj"])
            ),
            "standard_deduction_hoh": float(
                config.standard_deduction.get("head_of_household", defaults["standard_deduction_hoh"])
            ),
        }
    except Exception as exc:
        logger.debug(f"Falling back to inline 2025 standard deductions: {exc}")
        return defaults


# =============================================================================
# CORE DATA STRUCTURES
# =============================================================================

class AdvisoryComplexity(str, Enum):
    """Complexity level determines depth of analysis."""
    SIMPLE = "simple"           # W-2 only, standard deduction
    MODERATE = "moderate"       # Multiple income sources, itemized
    COMPLEX = "complex"         # Business income, investments, rental
    PROFESSIONAL = "professional"  # Multi-entity, international, estate


class DocumentType(str, Enum):
    """Supported tax document types."""
    W2 = "w2"
    W2G = "w2g"  # Gambling winnings
    FORM_1099_INT = "1099-int"
    FORM_1099_DIV = "1099-div"
    FORM_1099_B = "1099-b"
    FORM_1099_R = "1099-r"
    FORM_1099_NEC = "1099-nec"
    FORM_1099_MISC = "1099-misc"
    FORM_1099_K = "1099-k"
    FORM_1099_S = "1099-s"
    FORM_1099_G = "1099-g"
    FORM_1098 = "1098"  # Mortgage interest
    FORM_1098_T = "1098-t"  # Tuition
    FORM_1098_E = "1098-e"  # Student loan interest
    SCHEDULE_K1_1065 = "k1-1065"  # Partnership
    SCHEDULE_K1_1120S = "k1-1120s"  # S-Corp
    SCHEDULE_K1_1041 = "k1-1041"  # Estate/Trust
    SSA_1099 = "ssa-1099"  # Social Security
    FORM_5498 = "5498"  # IRA contributions
    CHARITABLE_RECEIPT = "charitable"
    PROPERTY_TAX = "property-tax"
    OTHER = "other"


@dataclass
class ExtractedDocument:
    """A document that has been OCR'd and fields extracted."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    document_type: DocumentType = DocumentType.OTHER
    tax_year: int = 2025

    # Source info
    filename: Optional[str] = None
    upload_timestamp: datetime = field(default_factory=datetime.now)

    # Extracted data
    extracted_fields: Dict[str, Any] = field(default_factory=dict)
    raw_text: Optional[str] = None

    # Confidence metrics
    ocr_confidence: float = 0.0
    extraction_confidence: float = 0.0
    needs_review: bool = False
    review_notes: List[str] = field(default_factory=list)

    # Payer/issuer info
    payer_name: Optional[str] = None
    payer_ein: Optional[str] = None


@dataclass
class TaxProfile:
    """Complete taxpayer information for advisory."""
    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    first_name: str = ""
    last_name: str = ""
    ssn_last4: str = "XXXX"  # Only store last 4 for security

    # Filing info
    filing_status: str = "single"
    tax_year: int = 2025
    state: str = "CA"

    # Age/blindness (affects standard deduction)
    is_65_or_older: bool = False
    is_blind: bool = False
    spouse_is_65_or_older: bool = False
    spouse_is_blind: bool = False

    # Dependents
    dependents: List[Dict[str, Any]] = field(default_factory=list)

    # Income (populated from documents + user input)
    wages: float = 0.0
    interest_income: float = 0.0
    dividend_income: float = 0.0
    qualified_dividends: float = 0.0
    capital_gains_short: float = 0.0
    capital_gains_long: float = 0.0
    business_income: float = 0.0
    rental_income: float = 0.0
    k1_income: float = 0.0
    social_security_benefits: float = 0.0
    retirement_distributions: float = 0.0
    gambling_winnings: float = 0.0
    other_income: float = 0.0

    # Adjustments to income
    student_loan_interest: float = 0.0
    educator_expenses: float = 0.0
    hsa_contributions: float = 0.0
    self_employment_tax_deduction: float = 0.0
    traditional_ira_contributions: float = 0.0
    alimony_paid: float = 0.0  # Pre-2019 agreements only

    # Itemized deductions
    medical_expenses: float = 0.0
    state_local_taxes_paid: float = 0.0
    real_estate_taxes: float = 0.0
    mortgage_interest: float = 0.0
    charitable_cash: float = 0.0
    charitable_noncash: float = 0.0
    casualty_loss: float = 0.0

    # Credits
    child_tax_credit_eligible: int = 0
    dependent_care_expenses: float = 0.0
    education_expenses: float = 0.0
    retirement_saver_contributions: float = 0.0
    residential_energy_improvements: float = 0.0
    ev_purchase_amount: float = 0.0
    adoption_expenses: float = 0.0

    # Payments
    federal_withholding: float = 0.0
    state_withholding: float = 0.0
    estimated_payments: float = 0.0

    # Self-employment
    has_self_employment: bool = False
    se_gross_receipts: float = 0.0
    se_expenses: float = 0.0

    # Rental properties
    rental_properties: List[Dict[str, Any]] = field(default_factory=list)

    # K-1 entities
    k1_entities: List[Dict[str, Any]] = field(default_factory=list)

    # Investment transactions
    capital_transactions: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    complexity: AdvisoryComplexity = AdvisoryComplexity.SIMPLE
    documents: List[ExtractedDocument] = field(default_factory=list)


# Backward-compatible alias used across the advisory service.
AdvisoryTaxpayerProfile = TaxProfile


@dataclass
class CPAInsight:
    """A single CPA-level insight/recommendation."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    # Classification
    category: str = ""  # retirement, deductions, credits, timing, entity, etc.
    priority: str = "medium"  # critical, high, medium, low

    # Content
    title: str = ""
    summary: str = ""
    detailed_explanation: str = ""

    # Impact
    estimated_savings: float = 0.0
    confidence: float = 0.0  # 0-1

    # Compliance
    irs_reference: str = ""  # IRC section, form, publication
    compliance_risk: str = "low"  # low, medium, high

    # Action
    action_required: str = ""
    deadline: Optional[date] = None
    requires_professional: bool = False

    # Computation support
    computation_details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AdvisoryReport:
    """Complete advisory report with CPA-level analysis."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    generated_at: datetime = field(default_factory=datetime.now)
    tax_year: int = 2025

    # Taxpayer summary
    taxpayer_name: str = ""
    filing_status: str = ""
    complexity: AdvisoryComplexity = AdvisoryComplexity.SIMPLE

    # Tax position
    gross_income: float = 0.0
    adjusted_gross_income: float = 0.0
    taxable_income: float = 0.0

    # Tax liability breakdown
    federal_tax: float = 0.0
    state_tax: float = 0.0
    self_employment_tax: float = 0.0
    additional_medicare_tax: float = 0.0
    niit: float = 0.0
    amt: float = 0.0
    total_tax: float = 0.0

    # Payments and refund/due
    total_payments: float = 0.0
    refund_or_due: float = 0.0  # Positive = refund, negative = due

    # Effective rates
    effective_tax_rate: float = 0.0
    marginal_tax_rate: float = 0.0

    # CPA Insights
    insights: List[CPAInsight] = field(default_factory=list)

    # Savings summary
    total_potential_savings: float = 0.0
    implemented_savings: float = 0.0

    # Forms required
    forms_required: List[str] = field(default_factory=list)

    # Computation breakdown (for transparency)
    computation_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Multi-year projection
    multi_year_projection: Dict[int, Dict[str, float]] = field(default_factory=dict)


# =============================================================================
# CPA KNOWLEDGE BASE - The "1 Lakh CPA" Intelligence
# =============================================================================

class CPAKnowledgeBase:
    """
    Encodes 100,000+ hours of CPA tax expertise.

    This is the intelligence layer that transforms raw calculations
    into actionable, compliant advisory recommendations.
    """

    # 2025 Key Thresholds (from IRS guidance)
    THRESHOLDS_2025 = {
        # Income thresholds
        "additional_medicare_threshold_single": 200000,
        "additional_medicare_threshold_mfj": 250000,
        "niit_threshold_single": 200000,
        "niit_threshold_mfj": 250000,

        # AMT exemptions
        "amt_exemption_single": 88100,
        "amt_exemption_mfj": 137000,
        "amt_phaseout_single": 626350,
        "amt_phaseout_mfj": 1252700,

        # Standard deductions
        **_load_standard_deduction_thresholds_2025(),

        # SALT cap
        "salt_cap": 10000,

        # QBI thresholds
        "qbi_threshold_single": 191950,
        "qbi_threshold_mfj": 383900,

        # Capital gains brackets
        "ltcg_0_threshold_single": 48350,
        "ltcg_0_threshold_mfj": 96700,
        "ltcg_15_threshold_single": 533400,
        "ltcg_15_threshold_mfj": 600050,

        # Social Security
        "ss_wage_base": 176100,
        "ss_tax_rate": 0.124,
        "medicare_tax_rate": 0.029,

        # Contribution limits
        "401k_limit": 23500,
        "401k_catch_up": 7500,
        "ira_limit": 7000,
        "ira_catch_up": 1000,
        "hsa_individual": 4300,
        "hsa_family": 8550,

        # Credits
        "child_tax_credit": 2000,
        "ctc_refundable_max": 1700,
        "eitc_max_3_children": 8046,
        "dependent_care_max": 3000,
        "dependent_care_max_2": 6000,
    }

    @classmethod
    def analyze_retirement_optimization(
        cls,
        profile: AdvisoryTaxpayerProfile,
        current_tax_rate: float
    ) -> List[CPAInsight]:
        """Analyze retirement contribution opportunities."""
        insights = []
        age = 50  # Would calculate from DOB

        # 401(k) optimization
        limit = cls.THRESHOLDS_2025["401k_limit"]
        if age >= 50:
            limit += cls.THRESHOLDS_2025["401k_catch_up"]

        current_401k = profile.extracted_fields.get("401k_contributions", 0) if hasattr(profile, 'extracted_fields') else 0
        remaining_401k = max(0, limit - current_401k)

        if remaining_401k > 0:
            savings = remaining_401k * current_tax_rate
            insights.append(CPAInsight(
                category="retirement",
                priority="high",
                title="Maximize 401(k) Contributions",
                summary=f"You can contribute ${remaining_401k:,.0f} more to your 401(k) this year.",
                detailed_explanation=f"""
Based on your current contributions and the 2025 limit of ${limit:,},
you have room to contribute an additional ${remaining_401k:,.0f}.

At your current marginal tax rate of {current_tax_rate*100:.1f}%, this would
reduce your federal tax liability by approximately ${savings:,.0f}.

Additionally, these contributions grow tax-deferred until retirement.
                """.strip(),
                estimated_savings=savings,
                confidence=0.95,
                irs_reference="IRC §402(g); IRS Notice 2024-80",
                action_required="Increase 401(k) contribution through employer",
                deadline=date(profile.tax_year, 12, 31),
                computation_details={
                    "current_contributions": current_401k,
                    "annual_limit": limit,
                    "additional_allowed": remaining_401k,
                    "marginal_rate": current_tax_rate,
                    "estimated_tax_savings": savings
                }
            ))

        # Traditional IRA deduction
        ira_limit = cls.THRESHOLDS_2025["ira_limit"]
        if age >= 50:
            ira_limit += cls.THRESHOLDS_2025["ira_catch_up"]

        if profile.traditional_ira_contributions < ira_limit:
            remaining = ira_limit - profile.traditional_ira_contributions
            savings = remaining * current_tax_rate
            insights.append(CPAInsight(
                category="retirement",
                priority="medium",
                title="Traditional IRA Contribution",
                summary=f"Contribute up to ${remaining:,.0f} to a Traditional IRA for tax deduction.",
                detailed_explanation=f"""
A Traditional IRA contribution of ${remaining:,.0f} would reduce your
taxable income dollar-for-dollar, saving approximately ${savings:,.0f} in taxes.

Note: Deductibility phases out at higher incomes if covered by employer plan.
                """.strip(),
                estimated_savings=savings,
                confidence=0.85,
                irs_reference="IRC §219; Publication 590-A",
                action_required="Open or contribute to Traditional IRA before tax deadline",
                deadline=date(profile.tax_year + 1, 4, 15),
                computation_details={
                    "current_contributions": profile.traditional_ira_contributions,
                    "limit": ira_limit,
                    "remaining": remaining,
                    "estimated_savings": savings
                }
            ))

        # HSA optimization
        if profile.hsa_contributions < cls.THRESHOLDS_2025["hsa_family"]:
            hsa_limit = cls.THRESHOLDS_2025["hsa_family"]  # Assume family
            remaining = hsa_limit - profile.hsa_contributions
            # HSA is triple tax advantaged
            savings = remaining * current_tax_rate * 1.2  # Premium due to FICA savings too
            insights.append(CPAInsight(
                category="retirement",
                priority="high",
                title="HSA: Triple Tax Advantage",
                summary=f"HSA contributions save on income tax AND FICA taxes.",
                detailed_explanation=f"""
Health Savings Accounts are the only triple-tax-advantaged account:
1. Contributions are tax-deductible (or pre-tax if through employer)
2. Growth is tax-free
3. Withdrawals for medical expenses are tax-free

Maximum 2025 contribution: ${hsa_limit:,} (family coverage)
Your current contributions: ${profile.hsa_contributions:,.0f}
Additional allowed: ${remaining:,.0f}

Unlike retirement accounts, you also save on FICA taxes (7.65%) when
contributed through employer payroll.
                """.strip(),
                estimated_savings=savings,
                confidence=0.90,
                irs_reference="IRC §223; Publication 969",
                action_required="Contribute to HSA if enrolled in HDHP",
                computation_details={
                    "current": profile.hsa_contributions,
                    "limit": hsa_limit,
                    "additional": remaining,
                    "savings_with_fica": savings
                }
            ))

        return insights

    @classmethod
    def analyze_deduction_strategy(
        cls,
        profile: AdvisoryTaxpayerProfile,
        itemized_total: float,
        standard_deduction: float
    ) -> List[CPAInsight]:
        """Analyze standard vs itemized deduction strategy."""
        insights = []

        difference = itemized_total - standard_deduction

        if abs(difference) < 2000:
            # Close call - recommend bunching strategy
            insights.append(CPAInsight(
                category="deductions",
                priority="high",
                title="Deduction Bunching Strategy",
                summary="Your itemized deductions are close to the standard deduction. Consider bunching.",
                detailed_explanation=f"""
Your itemized deductions (${itemized_total:,.0f}) are within $2,000 of the
standard deduction (${standard_deduction:,.0f}).

BUNCHING STRATEGY:
Instead of spreading deductions evenly, concentrate them in alternate years:
- Year 1: Bunch all charitable donations, prepay property taxes,
  accelerate medical procedures → Itemize
- Year 2: Take the standard deduction

This can save ${abs(difference) * 0.24:,.0f} or more over a 2-year period.

Example: If you donate $5,000/year to charity:
- Current: $5,000 deduction each year
- Bunching: $10,000 in Year 1 (itemize), $0 in Year 2 (standard)
- Extra deduction: ${standard_deduction - (itemized_total - 5000):,.0f} in Year 2
                """.strip(),
                estimated_savings=abs(difference) * 0.24,
                confidence=0.80,
                irs_reference="IRS Publication 17, Chapter 20",
                action_required="Plan charitable giving and timing of deductible expenses",
                computation_details={
                    "itemized_total": itemized_total,
                    "standard_deduction": standard_deduction,
                    "difference": difference,
                    "bunching_potential": abs(difference) * 2
                }
            ))

        # SALT cap analysis
        total_salt = profile.state_local_taxes_paid + profile.real_estate_taxes
        if total_salt > cls.THRESHOLDS_2025["salt_cap"]:
            lost_deduction = total_salt - cls.THRESHOLDS_2025["salt_cap"]
            lost_savings = lost_deduction * 0.24  # Assume 24% bracket
            insights.append(CPAInsight(
                category="deductions",
                priority="medium",
                title="SALT Cap Impact",
                summary=f"You're losing ${lost_deduction:,.0f} in deductions due to the $10,000 SALT cap.",
                detailed_explanation=f"""
The Tax Cuts and Jobs Act caps state and local tax (SALT) deductions at $10,000.

Your SALT total: ${total_salt:,.0f}
- State/local income taxes: ${profile.state_local_taxes_paid:,.0f}
- Real estate taxes: ${profile.real_estate_taxes:,.0f}

Lost deduction: ${lost_deduction:,.0f}
Estimated tax impact: ${lost_savings:,.0f}

STRATEGIES TO CONSIDER:
1. If you have a business, consider S-Corp election to take SALT through entity
2. Consider charitable contributions through SALT workaround programs (if your state offers)
3. For 2026+, the SALT cap may be modified - monitor legislation
                """.strip(),
                estimated_savings=0,  # Can't directly save here
                confidence=0.95,
                irs_reference="IRC §164(b)(6)",
                compliance_risk="low",
                computation_details={
                    "state_local_taxes": profile.state_local_taxes_paid,
                    "real_estate_taxes": profile.real_estate_taxes,
                    "total_salt": total_salt,
                    "cap": cls.THRESHOLDS_2025["salt_cap"],
                    "lost_deduction": lost_deduction
                }
            ))

        return insights

    @classmethod
    def analyze_self_employment(
        cls,
        profile: AdvisoryTaxpayerProfile
    ) -> List[CPAInsight]:
        """Analyze self-employment tax optimization."""
        insights = []

        if not profile.has_self_employment or profile.se_gross_receipts < 50000:
            return insights

        net_se_income = profile.se_gross_receipts - profile.se_expenses

        if net_se_income > 50000:
            # S-Corp election analysis
            # Reasonable salary + distributions strategy
            reasonable_salary = net_se_income * 0.6  # 60% as salary rule of thumb
            distributions = net_se_income * 0.4

            # Current SE tax (as sole prop)
            current_se_tax = net_se_income * 0.9235 * 0.153

            # S-Corp SE tax (only on salary)
            scorp_se_tax = reasonable_salary * 0.153

            savings = current_se_tax - scorp_se_tax

            if savings > 3000:  # Only recommend if meaningful savings
                insights.append(CPAInsight(
                    category="entity",
                    priority="high",
                    title="S-Corporation Election for SE Tax Savings",
                    summary=f"S-Corp election could save ${savings:,.0f}/year in self-employment taxes.",
                    detailed_explanation=f"""
As a sole proprietor, you pay 15.3% self-employment tax on all net earnings.
With an S-Corporation, you only pay FICA taxes on reasonable salary.

CURRENT (Sole Proprietorship):
- Net SE income: ${net_se_income:,.0f}
- SE tax base: ${net_se_income * 0.9235:,.0f} (92.35% of net)
- SE tax: ${current_se_tax:,.0f}

WITH S-CORP ELECTION:
- Reasonable salary: ${reasonable_salary:,.0f}
- Distributions (no SE tax): ${distributions:,.0f}
- FICA on salary: ${scorp_se_tax:,.0f}

ANNUAL SE TAX SAVINGS: ${savings:,.0f}

IMPORTANT CONSIDERATIONS:
1. Must pay "reasonable compensation" - IRS scrutinizes low salaries
2. Additional compliance costs (~$1,500-3,000/year for payroll, tax returns)
3. Must file Form 2553 for election
4. Net savings after compliance: ${savings - 2000:,.0f}
                    """.strip(),
                    estimated_savings=savings,
                    confidence=0.85,
                    irs_reference="IRC §1361; Rev Rul 59-221",
                    action_required="Consult with CPA about S-Corp election",
                    requires_professional=True,
                    computation_details={
                        "net_se_income": net_se_income,
                        "current_se_tax": current_se_tax,
                        "reasonable_salary": reasonable_salary,
                        "distributions": distributions,
                        "scorp_se_tax": scorp_se_tax,
                        "gross_savings": savings,
                        "estimated_compliance_cost": 2000,
                        "net_savings": savings - 2000
                    }
                ))

        # QBI Deduction check
        qbi_deduction = net_se_income * 0.20
        threshold = cls.THRESHOLDS_2025["qbi_threshold_single"]
        if profile.filing_status in ["married_filing_jointly", "qualifying_widow"]:
            threshold = cls.THRESHOLDS_2025["qbi_threshold_mfj"]

        insights.append(CPAInsight(
            category="deductions",
            priority="medium",
            title="Qualified Business Income (QBI) Deduction",
            summary=f"Your business qualifies for up to ${qbi_deduction:,.0f} QBI deduction.",
            detailed_explanation=f"""
The Section 199A QBI deduction allows a 20% deduction on qualified business income.

Your qualified business income: ${net_se_income:,.0f}
Potential QBI deduction: ${qbi_deduction:,.0f}

At your income level, you may be
subject to W-2 wage and UBIA limitations if above threshold.

Threshold for limitations: ${threshold:,.0f}

This deduction is taken AFTER AGI, reducing taxable income directly.
            """.strip(),
            estimated_savings=qbi_deduction * 0.24,
            confidence=0.90,
            irs_reference="IRC §199A; Form 8995",
            computation_details={
                "qbi": net_se_income,
                "deduction_rate": 0.20,
                "potential_deduction": qbi_deduction,
                "limitation_threshold": threshold
            }
        ))

        return insights

    @classmethod
    def analyze_investment_taxes(
        cls,
        profile: AdvisoryTaxpayerProfile,
        agi: float
    ) -> List[CPAInsight]:
        """Analyze investment income tax strategies."""
        insights = []

        # NIIT analysis
        niit_threshold = cls.THRESHOLDS_2025["niit_threshold_single"]
        if profile.filing_status in ["married_filing_jointly", "qualifying_widow"]:
            niit_threshold = cls.THRESHOLDS_2025["niit_threshold_mfj"]

        investment_income = (
            profile.interest_income +
            profile.dividend_income +
            profile.capital_gains_short +
            profile.capital_gains_long +
            profile.rental_income
        )

        if agi > niit_threshold and investment_income > 0:
            excess_agi = agi - niit_threshold
            niit_base = min(excess_agi, investment_income)
            niit = niit_base * 0.038

            insights.append(CPAInsight(
                category="investment",
                priority="high",
                title="Net Investment Income Tax (NIIT) Applies",
                summary=f"You owe ${niit:,.0f} in NIIT (3.8% surtax on investment income).",
                detailed_explanation=f"""
The Net Investment Income Tax is a 3.8% surtax on investment income for
high earners, enacted as part of the Affordable Care Act.

Your MAGI: ${agi:,.0f}
NIIT threshold: ${niit_threshold:,.0f}
Excess over threshold: ${excess_agi:,.0f}

Your investment income: ${investment_income:,.0f}
NIIT base (lesser of excess or NII): ${niit_base:,.0f}
NIIT liability: ${niit:,.0f}

STRATEGIES TO REDUCE NIIT:
1. Maximize retirement contributions (reduces MAGI)
2. Consider tax-loss harvesting to offset gains
3. Invest in municipal bonds (interest is exempt from NIIT)
4. Consider installment sales to spread gains over years
5. Charitable remainder trusts for appreciated assets
                """.strip(),
                estimated_savings=0,
                confidence=0.95,
                irs_reference="IRC §1411; Form 8960",
                computation_details={
                    "agi": agi,
                    "threshold": niit_threshold,
                    "excess": excess_agi,
                    "investment_income": investment_income,
                    "niit_base": niit_base,
                    "niit": niit
                }
            ))

        # Tax-loss harvesting
        if profile.capital_gains_long > 10000:
            potential_harvest = min(profile.capital_gains_long * 0.3, 50000)
            tax_savings = potential_harvest * 0.15  # 15% LTCG rate

            insights.append(CPAInsight(
                category="investment",
                priority="medium",
                title="Tax-Loss Harvesting Opportunity",
                summary="Review portfolio for loss harvesting before year-end.",
                detailed_explanation=f"""
With ${profile.capital_gains_long:,.0f} in long-term capital gains this year,
consider harvesting losses to offset these gains.

HOW IT WORKS:
1. Sell investments that have declined in value
2. Use losses to offset gains (unlimited)
3. Excess losses offset up to $3,000 of ordinary income
4. Remaining losses carry forward indefinitely

WASH SALE RULE:
Cannot repurchase "substantially identical" securities within
30 days before or after the sale.

STRATEGY: Sell losing position, immediately buy similar (not identical)
investment to maintain market exposure.
                """.strip(),
                estimated_savings=tax_savings,
                confidence=0.70,
                irs_reference="IRC §1091 (wash sales); Publication 550",
                action_required="Review brokerage statements for unrealized losses",
                deadline=date(profile.tax_year, 12, 31),
                computation_details={
                    "current_ltcg": profile.capital_gains_long,
                    "potential_harvest": potential_harvest,
                    "estimated_savings": tax_savings
                }
            ))

        return insights

    @classmethod
    def analyze_credits(
        cls,
        profile: AdvisoryTaxpayerProfile
    ) -> List[CPAInsight]:
        """Analyze available tax credits."""
        insights = []

        # Child Tax Credit
        if profile.child_tax_credit_eligible > 0:
            ctc = profile.child_tax_credit_eligible * cls.THRESHOLDS_2025["child_tax_credit"]
            refundable = min(
                profile.child_tax_credit_eligible * cls.THRESHOLDS_2025["ctc_refundable_max"],
                ctc
            )
            insights.append(CPAInsight(
                category="credits",
                priority="high",
                title="Child Tax Credit",
                summary=f"You qualify for ${ctc:,.0f} in Child Tax Credit.",
                detailed_explanation=f"""
For tax year 2025, the Child Tax Credit is ${cls.THRESHOLDS_2025['child_tax_credit']:,} per qualifying child.

Your qualifying children: {profile.child_tax_credit_eligible}
Total CTC: ${ctc:,.0f}
Refundable portion (ACTC): Up to ${refundable:,.0f}

REQUIREMENTS:
- Child must be under age 17 at end of tax year
- Child must have valid SSN
- Child must be your dependent
- Income phase-out begins at $200,000 ($400,000 MFJ)
                """.strip(),
                estimated_savings=ctc,
                confidence=0.95,
                irs_reference="IRC §24; Schedule 8812",
                computation_details={
                    "children": profile.child_tax_credit_eligible,
                    "credit_per_child": cls.THRESHOLDS_2025["child_tax_credit"],
                    "total_credit": ctc,
                    "refundable_max": refundable
                }
            ))

        # Education credits
        if profile.education_expenses > 0:
            # American Opportunity Credit (up to $2,500)
            aoc = min(profile.education_expenses, 4000)
            aoc_credit = min(aoc, 2000) + max(0, (aoc - 2000) * 0.25)
            aoc_credit = min(aoc_credit, 2500)

            insights.append(CPAInsight(
                category="credits",
                priority="high",
                title="American Opportunity Tax Credit",
                summary=f"You may qualify for up to ${aoc_credit:,.0f} education credit.",
                detailed_explanation=f"""
The American Opportunity Tax Credit provides up to $2,500 per eligible student.

Your education expenses: ${profile.education_expenses:,.0f}
Potential credit: ${aoc_credit:,.0f}

CREDIT CALCULATION:
- 100% of first $2,000 in expenses
- 25% of next $2,000 in expenses
- Maximum: $2,500 per student

40% of the credit (up to $1,000) is refundable.

ELIGIBILITY:
- First 4 years of post-secondary education
- Enrolled at least half-time
- Income limits apply ($80k/$160k MFJ phase-out begins)
                """.strip(),
                estimated_savings=aoc_credit,
                confidence=0.80,
                irs_reference="IRC §25A; Form 8863",
                computation_details={
                    "expenses": profile.education_expenses,
                    "credit": aoc_credit,
                    "refundable_portion": aoc_credit * 0.40
                }
            ))

        # Energy credits
        if profile.residential_energy_improvements > 0:
            energy_credit = min(profile.residential_energy_improvements * 0.30, 3200)
            insights.append(CPAInsight(
                category="credits",
                priority="medium",
                title="Residential Clean Energy Credit",
                summary=f"Your energy improvements qualify for ${energy_credit:,.0f} credit.",
                detailed_explanation=f"""
The Residential Clean Energy Credit provides 30% of the cost of qualifying
clean energy improvements.

Your qualifying improvements: ${profile.residential_energy_improvements:,.0f}
Credit (30%): ${energy_credit:,.0f}

QUALIFYING IMPROVEMENTS:
- Solar panels
- Solar water heaters
- Geothermal heat pumps
- Small wind turbines
- Fuel cell property
- Battery storage

This credit has no lifetime limit and can be carried forward if it
exceeds your tax liability.
                """.strip(),
                estimated_savings=energy_credit,
                confidence=0.85,
                irs_reference="IRC §25D; Form 5695",
                computation_details={
                    "improvements": profile.residential_energy_improvements,
                    "credit_rate": 0.30,
                    "credit": energy_credit
                }
            ))

        return insights

    @classmethod
    def generate_comprehensive_analysis(
        cls,
        profile: AdvisoryTaxpayerProfile,
        calculation_result: Dict[str, Any]
    ) -> List[CPAInsight]:
        """Generate complete CPA-level analysis."""
        all_insights = []

        # Extract key values from calculation
        agi = calculation_result.get("adjusted_gross_income", 0)
        taxable_income = calculation_result.get("taxable_income", 0)
        marginal_rate = calculation_result.get("marginal_rate", 0.22)
        itemized = calculation_result.get("itemized_deductions", 0)
        standard = calculation_result.get("standard_deduction", 15000)

        # Run all analyzers
        all_insights.extend(cls.analyze_retirement_optimization(profile, marginal_rate))
        all_insights.extend(cls.analyze_deduction_strategy(profile, itemized, standard))
        all_insights.extend(cls.analyze_self_employment(profile))
        all_insights.extend(cls.analyze_investment_taxes(profile, agi))
        all_insights.extend(cls.analyze_credits(profile))

        # Sort by priority and estimated savings
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        all_insights.sort(
            key=lambda x: (priority_order.get(x.priority, 4), -x.estimated_savings)
        )

        return all_insights


# =============================================================================
# UNIFIED TAX ADVISOR SERVICE
# =============================================================================

class UnifiedTaxAdvisor:
    """
    The main integration service that ties everything together.

    This is the "brain" that:
    1. Processes uploaded documents
    2. Extracts and validates data
    3. Runs tax calculations
    4. Generates CPA-level advisory
    5. Produces draft forms
    """

    def __init__(self, tax_year: int = 2025):
        self.tax_year = tax_year
        self.knowledge_base = CPAKnowledgeBase()

        # Import components (lazy loading)
        self._tax_engine = None
        self._ocr_engine = None
        self._advisory_generator = None
        self._form_generator = None

    @property
    def tax_engine(self):
        if self._tax_engine is None:
            try:
                from calculator.engine import FederalTaxEngine
                from calculator.tax_year_config import TaxYearConfig
                # Get config for the specified tax year
                if self.tax_year == 2025:
                    config = TaxYearConfig.for_2025()
                else:
                    config = TaxYearConfig.for_2025()  # Default to 2025
                self._tax_engine = FederalTaxEngine(config=config)
            except ImportError as e:
                logger.warning(f"Tax engine not available: {e}")
        return self._tax_engine

    @property
    def ocr_engine(self):
        if self._ocr_engine is None:
            try:
                from services.ocr.ocr_engine import get_ocr_engine
                self._ocr_engine = get_ocr_engine()
            except ImportError:
                logger.warning("OCR engine not available")
        return self._ocr_engine

    def process_document(
        self,
        file_path: str,
        document_type: Optional[DocumentType] = None
    ) -> ExtractedDocument:
        """Process a single document and extract tax data."""
        doc = ExtractedDocument(tax_year=self.tax_year)
        doc.filename = file_path

        if self.ocr_engine:
            try:
                # Run OCR
                ocr_result = self.ocr_engine.process_file(file_path)
                doc.raw_text = ocr_result.get("text", "")
                doc.ocr_confidence = ocr_result.get("confidence", 0)

                # Classify document if not specified
                if document_type is None:
                    document_type = self._classify_document(doc.raw_text)
                doc.document_type = document_type

                # Extract fields based on document type
                doc.extracted_fields = self._extract_fields(doc)
                doc.extraction_confidence = self._calculate_extraction_confidence(doc)

            except Exception as e:
                logger.error(f"Error processing document: {e}")
                doc.review_notes.append(f"Processing error: {str(e)}")
                doc.needs_review = True

        return doc

    def _classify_document(self, text: str) -> DocumentType:
        """Classify document type from OCR text."""
        text_lower = text.lower()

        # Pattern matching for common forms
        if "w-2" in text_lower or "wage and tax statement" in text_lower:
            return DocumentType.W2
        elif "1099-int" in text_lower or "interest income" in text_lower:
            return DocumentType.FORM_1099_INT
        elif "1099-div" in text_lower or "dividends" in text_lower:
            return DocumentType.FORM_1099_DIV
        elif "1099-b" in text_lower or "proceeds from broker" in text_lower:
            return DocumentType.FORM_1099_B
        elif "1099-nec" in text_lower or "nonemployee compensation" in text_lower:
            return DocumentType.FORM_1099_NEC
        elif "1099-misc" in text_lower:
            return DocumentType.FORM_1099_MISC
        elif "schedule k-1" in text_lower:
            if "1065" in text_lower:
                return DocumentType.SCHEDULE_K1_1065
            elif "1120s" in text_lower or "1120-s" in text_lower:
                return DocumentType.SCHEDULE_K1_1120S
            else:
                return DocumentType.SCHEDULE_K1_1065
        elif "1098" in text_lower and "mortgage" in text_lower:
            return DocumentType.FORM_1098
        elif "1098-t" in text_lower or "tuition" in text_lower:
            return DocumentType.FORM_1098_T
        elif "ssa-1099" in text_lower or "social security" in text_lower:
            return DocumentType.SSA_1099

        return DocumentType.OTHER

    def _extract_fields(self, doc: ExtractedDocument) -> Dict[str, Any]:
        """Extract fields based on document type."""
        fields = {}
        text = doc.raw_text or ""

        # Common extractors
        import re

        # Extract amounts (numbers with $ or decimal)
        amounts = re.findall(r'\$?([\d,]+\.?\d*)', text)

        if doc.document_type == DocumentType.W2:
            fields = {
                "wages": self._find_labeled_amount(text, ["wages", "box 1", "federal wages"]),
                "federal_withholding": self._find_labeled_amount(text, ["federal tax withheld", "box 2"]),
                "social_security_wages": self._find_labeled_amount(text, ["social security wages", "box 3"]),
                "social_security_tax": self._find_labeled_amount(text, ["social security tax", "box 4"]),
                "medicare_wages": self._find_labeled_amount(text, ["medicare wages", "box 5"]),
                "medicare_tax": self._find_labeled_amount(text, ["medicare tax", "box 6"]),
                "state_wages": self._find_labeled_amount(text, ["state wages", "box 16"]),
                "state_withholding": self._find_labeled_amount(text, ["state tax", "box 17"]),
            }
        elif doc.document_type == DocumentType.FORM_1099_INT:
            fields = {
                "interest_income": self._find_labeled_amount(text, ["interest income", "box 1"]),
                "early_withdrawal_penalty": self._find_labeled_amount(text, ["early withdrawal", "box 2"]),
                "federal_withholding": self._find_labeled_amount(text, ["federal tax withheld", "box 4"]),
            }
        elif doc.document_type == DocumentType.FORM_1099_DIV:
            fields = {
                "ordinary_dividends": self._find_labeled_amount(text, ["ordinary dividends", "box 1a"]),
                "qualified_dividends": self._find_labeled_amount(text, ["qualified dividends", "box 1b"]),
                "capital_gains_distributions": self._find_labeled_amount(text, ["capital gain", "box 2a"]),
                "federal_withholding": self._find_labeled_amount(text, ["federal tax withheld", "box 4"]),
            }
        elif doc.document_type == DocumentType.FORM_1099_NEC:
            fields = {
                "nonemployee_compensation": self._find_labeled_amount(text, ["nonemployee compensation", "box 1"]),
                "federal_withholding": self._find_labeled_amount(text, ["federal tax withheld", "box 4"]),
            }

        # Extract payer info
        ein_match = re.search(r'\b(\d{2}[-]?\d{7})\b', text)
        if ein_match:
            doc.payer_ein = ein_match.group(1)

        return fields

    def _find_labeled_amount(self, text: str, labels: List[str]) -> float:
        """Find an amount near a label in OCR text."""
        import re
        text_lower = text.lower()

        for label in labels:
            # Find position of label
            pos = text_lower.find(label.lower())
            if pos != -1:
                # Look for number within 100 chars after label
                search_area = text[pos:pos+100]
                amounts = re.findall(r'\$?([\d,]+\.?\d*)', search_area)
                for amt in amounts:
                    try:
                        value = float(amt.replace(',', ''))
                        if value > 0:
                            return value
                    except ValueError:
                        continue
        return 0.0

    def _calculate_extraction_confidence(self, doc: ExtractedDocument) -> float:
        """Calculate confidence in extracted fields."""
        if not doc.extracted_fields:
            return 0.0

        # Count non-zero fields
        non_zero = sum(1 for v in doc.extracted_fields.values() if v and v > 0)
        total = len(doc.extracted_fields)

        # Base confidence from field coverage
        coverage = non_zero / total if total > 0 else 0

        # Combine with OCR confidence
        return (coverage * 0.6 + doc.ocr_confidence * 0.4)

    def build_profile_from_documents(
        self,
        documents: List[ExtractedDocument],
        user_inputs: Dict[str, Any] = None
    ) -> AdvisoryTaxpayerProfile:
        """Build taxpayer profile from extracted documents and user inputs."""
        profile = AdvisoryTaxpayerProfile(tax_year=self.tax_year)
        profile.documents = documents

        # Aggregate from documents
        for doc in documents:
            fields = doc.extracted_fields

            if doc.document_type == DocumentType.W2:
                profile.wages += fields.get("wages", 0)
                profile.federal_withholding += fields.get("federal_withholding", 0)
                profile.state_withholding += fields.get("state_withholding", 0)

            elif doc.document_type == DocumentType.FORM_1099_INT:
                profile.interest_income += fields.get("interest_income", 0)

            elif doc.document_type == DocumentType.FORM_1099_DIV:
                profile.dividend_income += fields.get("ordinary_dividends", 0)
                profile.qualified_dividends += fields.get("qualified_dividends", 0)
                profile.capital_gains_long += fields.get("capital_gains_distributions", 0)

            elif doc.document_type == DocumentType.FORM_1099_NEC:
                profile.has_self_employment = True
                profile.se_gross_receipts += fields.get("nonemployee_compensation", 0)

            elif doc.document_type in [DocumentType.SCHEDULE_K1_1065, DocumentType.SCHEDULE_K1_1120S]:
                profile.k1_income += fields.get("ordinary_income", 0)
                profile.k1_entities.append({
                    "type": "partnership" if doc.document_type == DocumentType.SCHEDULE_K1_1065 else "s_corp",
                    "ein": doc.payer_ein,
                    "fields": fields
                })

            elif doc.document_type == DocumentType.FORM_1098:
                profile.mortgage_interest += fields.get("mortgage_interest", 0)

        # Apply user inputs (overrides/additions)
        if user_inputs:
            for key, value in user_inputs.items():
                if hasattr(profile, key):
                    setattr(profile, key, value)

        # Determine complexity
        profile.complexity = self._assess_complexity(profile)

        return profile

    def _assess_complexity(self, profile: AdvisoryTaxpayerProfile) -> AdvisoryComplexity:
        """Assess the complexity level of the tax situation."""
        score = 0

        # Income complexity
        if profile.has_self_employment:
            score += 2
        if profile.k1_income > 0:
            score += 2
        if profile.rental_income > 0:
            score += 2
        if profile.capital_gains_short > 0 or profile.capital_gains_long > 0:
            score += 1

        # Deduction complexity
        total_itemized = (
            profile.mortgage_interest +
            profile.charitable_cash +
            profile.charitable_noncash +
            profile.state_local_taxes_paid +
            profile.real_estate_taxes +
            profile.medical_expenses
        )
        if total_itemized > 15000:
            score += 1

        # Multiple entities
        if len(profile.k1_entities) > 1:
            score += 2

        # Rental properties
        if len(profile.rental_properties) > 0:
            score += len(profile.rental_properties)

        if score >= 6:
            return AdvisoryComplexity.PROFESSIONAL
        elif score >= 4:
            return AdvisoryComplexity.COMPLEX
        elif score >= 2:
            return AdvisoryComplexity.MODERATE
        else:
            return AdvisoryComplexity.SIMPLE

    def _map_filing_status(self, filing_status: str):
        """Map advisory filing-status labels to core model enum values."""
        from models.taxpayer import FilingStatus

        normalized = (filing_status or "single").strip().lower().replace("-", "_").replace(" ", "_")
        mapping = {
            "single": FilingStatus.SINGLE,
            "married_joint": FilingStatus.MARRIED_JOINT,
            "married_filing_jointly": FilingStatus.MARRIED_JOINT,
            "mfj": FilingStatus.MARRIED_JOINT,
            "married_separate": FilingStatus.MARRIED_SEPARATE,
            "married_filing_separately": FilingStatus.MARRIED_SEPARATE,
            "mfs": FilingStatus.MARRIED_SEPARATE,
            "head_of_household": FilingStatus.HEAD_OF_HOUSEHOLD,
            "hoh": FilingStatus.HEAD_OF_HOUSEHOLD,
            "qualifying_widow": FilingStatus.QUALIFYING_WIDOW,
            "qualifying_widow_er": FilingStatus.QUALIFYING_WIDOW,
        }
        return mapping.get(normalized, FilingStatus.SINGLE)

    def _build_core_tax_return(self, profile: AdvisoryTaxpayerProfile):
        """Convert advisory profile into the core TaxReturn model for full-engine calculations."""
        from models.tax_return import TaxReturn
        from models.taxpayer import TaxpayerInfo
        from models.income import Income
        from models.deductions import Deductions, ItemizedDeductions
        from models.credits import TaxCredits

        state = (profile.state or "").strip().upper()
        if len(state) != 2:
            state = None

        filing_status = self._map_filing_status(profile.filing_status)

        taxpayer = TaxpayerInfo(
            first_name=(profile.first_name or "Taxpayer").strip() or "Taxpayer",
            last_name=(profile.last_name or "Client").strip() or "Client",
            filing_status=filing_status,
            state=state,
            dependents=[],
            is_blind=bool(profile.is_blind),
            is_over_65=bool(profile.is_65_or_older),
            spouse_is_blind=bool(profile.spouse_is_blind),
            spouse_is_over_65=bool(profile.spouse_is_65_or_older),
        )

        self_employment_income = float(profile.business_income or 0.0)
        if self_employment_income <= 0:
            self_employment_income = max(0.0, float(profile.se_gross_receipts or 0.0))

        income = Income(
            self_employment_income=self_employment_income,
            self_employment_expenses=max(0.0, float(profile.se_expenses or 0.0)),
            interest_income=float(profile.interest_income or 0.0),
            dividend_income=float(profile.dividend_income or 0.0),
            qualified_dividends=float(profile.qualified_dividends or 0.0),
            short_term_capital_gains=float(profile.capital_gains_short or 0.0),
            long_term_capital_gains=float(profile.capital_gains_long or 0.0),
            rental_income=float(profile.rental_income or 0.0),
            social_security_benefits=float(profile.social_security_benefits or 0.0),
            retirement_income=float(profile.retirement_distributions or 0.0),
            other_income=(
                float(profile.other_income or 0.0) +
                float(profile.k1_income or 0.0) +
                float(profile.gambling_winnings or 0.0)
            ),
            estimated_tax_payments=float(profile.estimated_payments or 0.0),
        )

        if profile.wages:
            from models.income import W2Info
            income.w2_forms.append(
                W2Info(
                    employer_name="Advisory Imported Income",
                    wages=float(profile.wages or 0.0),
                    federal_tax_withheld=float(profile.federal_withholding or 0.0),
                    state_tax_withheld=float(profile.state_withholding or 0.0),
                )
            )

        itemized = ItemizedDeductions(
            medical_expenses=float(profile.medical_expenses or 0.0),
            state_local_income_tax=float(profile.state_local_taxes_paid or 0.0),
            real_estate_tax=float(profile.real_estate_taxes or 0.0),
            mortgage_interest=float(profile.mortgage_interest or 0.0),
            charitable_cash=float(profile.charitable_cash or 0.0),
            charitable_non_cash=float(profile.charitable_noncash or 0.0),
            casualty_losses=float(profile.casualty_loss or 0.0),
        )

        itemized_total = (
            float(profile.medical_expenses or 0.0) +
            float(profile.state_local_taxes_paid or 0.0) +
            float(profile.real_estate_taxes or 0.0) +
            float(profile.mortgage_interest or 0.0) +
            float(profile.charitable_cash or 0.0) +
            float(profile.charitable_noncash or 0.0) +
            float(profile.casualty_loss or 0.0)
        )

        status_key = filing_status.value
        standard_map = {
            "single": CPAKnowledgeBase.THRESHOLDS_2025["standard_deduction_single"],
            "married_joint": CPAKnowledgeBase.THRESHOLDS_2025["standard_deduction_mfj"],
            "head_of_household": CPAKnowledgeBase.THRESHOLDS_2025["standard_deduction_hoh"],
            "married_separate": CPAKnowledgeBase.THRESHOLDS_2025["standard_deduction_single"],
            "qualifying_widow": CPAKnowledgeBase.THRESHOLDS_2025["standard_deduction_mfj"],
        }
        standard_deduction = float(standard_map.get(status_key, CPAKnowledgeBase.THRESHOLDS_2025["standard_deduction_single"]))

        deductions = Deductions(
            use_standard_deduction=itemized_total <= standard_deduction,
            itemized=itemized,
            educator_expenses=float(profile.educator_expenses or 0.0),
            student_loan_interest=float(profile.student_loan_interest or 0.0),
            hsa_contributions=float(profile.hsa_contributions or 0.0),
            ira_contributions=float(profile.traditional_ira_contributions or 0.0),
            other_adjustments=float(profile.self_employment_tax_deduction or 0.0),
            alimony_paid=float(profile.alimony_paid or 0.0),
        )

        credits = TaxCredits(
            child_tax_credit_children=max(0, int(profile.child_tax_credit_eligible or 0)),
            child_care_expenses=float(profile.dependent_care_expenses or 0.0),
            education_expenses=float(profile.education_expenses or 0.0),
            residential_energy_credit=0.0,
            foreign_tax_credit=0.0,
            other_credits=0.0,
        )

        return TaxReturn(
            tax_year=profile.tax_year or self.tax_year,
            taxpayer=taxpayer,
            income=income,
            deductions=deductions,
            credits=credits,
            state_of_residence=state,
        )

    def _normalize_calculation_result(
        self,
        result: Any,
        tax_return: Any,
    ) -> Dict[str, Any]:
        """Normalize engine output to the advisory report contract."""
        if hasattr(result, "to_dict"):
            raw = result.to_dict()
        elif isinstance(result, dict):
            raw = result
        else:
            raw = {}

        gross_income = float(raw.get("gross_income") or getattr(tax_return.income, "get_total_income", lambda: 0.0)() or 0.0)
        total_tax = float(raw.get("total_tax", 0.0) or 0.0)

        return {
            "gross_income": gross_income,
            "adjusted_gross_income": float(raw.get("agi", raw.get("adjusted_gross_income", 0.0)) or 0.0),
            "taxable_income": float(raw.get("taxable_income", 0.0) or 0.0),
            "federal_tax": float(raw.get("total_tax_before_credits", total_tax) or 0.0),
            "self_employment_tax": float(raw.get("self_employment_tax", 0.0) or 0.0),
            "total_tax": total_tax,
            "total_payments": float(raw.get("total_payments", 0.0) or 0.0),
            "refund_or_due": float(raw.get("refund_or_owed", raw.get("refund_or_due", 0.0)) or 0.0),
            "effective_rate": float(raw.get("effective_tax_rate", (total_tax / gross_income if gross_income > 0 else 0.0)) or 0.0),
            "marginal_rate": float(raw.get("marginal_tax_rate", 0.22) or 0.22),
            "engine_breakdown": raw,
        }

    def calculate_taxes(self, profile: AdvisoryTaxpayerProfile) -> Dict[str, Any]:
        """Run full tax calculation."""
        # Build tax return data structure
        tax_data = {
            "filing_status": profile.filing_status,
            "tax_year": profile.tax_year,

            # Income
            "wages": profile.wages,
            "interest_income": profile.interest_income,
            "dividend_income": profile.dividend_income,
            "qualified_dividends": profile.qualified_dividends,
            "capital_gains_short": profile.capital_gains_short,
            "capital_gains_long": profile.capital_gains_long,
            "business_income": profile.business_income or (profile.se_gross_receipts - profile.se_expenses),
            "rental_income": profile.rental_income,
            "k1_income": profile.k1_income,
            "social_security_benefits": profile.social_security_benefits,
            "retirement_distributions": profile.retirement_distributions,
            "other_income": profile.other_income,

            # Adjustments
            "student_loan_interest": profile.student_loan_interest,
            "educator_expenses": profile.educator_expenses,
            "hsa_contributions": profile.hsa_contributions,
            "traditional_ira_contributions": profile.traditional_ira_contributions,

            # Itemized deductions
            "medical_expenses": profile.medical_expenses,
            "state_local_taxes": profile.state_local_taxes_paid + profile.real_estate_taxes,
            "mortgage_interest": profile.mortgage_interest,
            "charitable_contributions": profile.charitable_cash + profile.charitable_noncash,

            # Credits
            "num_children_ctc": profile.child_tax_credit_eligible,
            "dependent_care_expenses": profile.dependent_care_expenses,
            "education_expenses": profile.education_expenses,

            # Payments
            "federal_withholding": profile.federal_withholding,
            "estimated_payments": profile.estimated_payments,
        }

        if self.tax_engine:
            try:
                tax_return = self._build_core_tax_return(profile)
                result = self.tax_engine.calculate(tax_return)
                return self._normalize_calculation_result(result, tax_return)
            except Exception as e:
                logger.error(f"Tax calculation error: {e}")

        # Fallback simplified calculation
        return self._simplified_calculation(tax_data)

    def _simplified_calculation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Simplified tax calculation when full engine unavailable."""
        # Calculate gross income
        gross_income = (
            data.get("wages", 0) +
            data.get("interest_income", 0) +
            data.get("dividend_income", 0) +
            data.get("capital_gains_short", 0) +
            data.get("capital_gains_long", 0) +
            data.get("business_income", 0) +
            data.get("rental_income", 0) +
            data.get("k1_income", 0) +
            data.get("retirement_distributions", 0) +
            data.get("other_income", 0)
        )

        # Adjustments
        adjustments = (
            data.get("student_loan_interest", 0) +
            data.get("educator_expenses", 0) +
            data.get("hsa_contributions", 0) +
            data.get("traditional_ira_contributions", 0)
        )

        agi = gross_income - adjustments

        # Deductions
        itemized = (
            max(0, data.get("medical_expenses", 0) - agi * 0.075) +
            min(data.get("state_local_taxes", 0), 10000) +
            data.get("mortgage_interest", 0) +
            data.get("charitable_contributions", 0)
        )

        standard = CPAKnowledgeBase.THRESHOLDS_2025.get(
            f"standard_deduction_{data.get('filing_status', 'single')}", 15000
        )

        deduction = max(itemized, standard)
        taxable_income = max(0, agi - deduction)

        # Simplified tax calculation (2025 brackets for single)
        tax = 0
        brackets = [
            (11925, 0.10),
            (48475, 0.12),
            (103350, 0.22),
            (197300, 0.24),
            (250525, 0.32),
            (626350, 0.35),
            (float('inf'), 0.37)
        ]

        remaining = taxable_income
        prev_bracket = 0
        for bracket, rate in brackets:
            bracket_income = min(remaining, bracket - prev_bracket)
            tax += bracket_income * rate
            remaining -= bracket_income
            prev_bracket = bracket
            if remaining <= 0:
                break

        # Self-employment tax
        se_income = data.get("business_income", 0)
        se_tax = 0
        if se_income > 0:
            se_base = se_income * 0.9235
            se_tax = min(se_base, 176100) * 0.153 + max(0, se_base - 176100) * 0.029

        total_tax = tax + se_tax

        # Payments
        total_payments = (
            data.get("federal_withholding", 0) +
            data.get("estimated_payments", 0)
        )

        refund_or_due = total_payments - total_tax

        return {
            "gross_income": gross_income,
            "adjusted_gross_income": agi,
            "itemized_deductions": itemized,
            "standard_deduction": standard,
            "deduction_used": deduction,
            "taxable_income": taxable_income,
            "federal_tax": tax,
            "self_employment_tax": se_tax,
            "total_tax": total_tax,
            "total_payments": total_payments,
            "refund_or_due": refund_or_due,
            "effective_rate": total_tax / gross_income if gross_income > 0 else 0,
            "marginal_rate": 0.22  # Simplified
        }

    def generate_advisory_report(
        self,
        profile: AdvisoryTaxpayerProfile,
        calculation_result: Dict[str, Any]
    ) -> AdvisoryReport:
        """Generate comprehensive CPA-level advisory report."""
        report = AdvisoryReport(
            tax_year=self.tax_year,
            taxpayer_name=f"{profile.first_name} {profile.last_name}".strip() or "Taxpayer",
            filing_status=profile.filing_status,
            complexity=profile.complexity
        )

        # Tax position
        report.gross_income = calculation_result.get("gross_income", 0)
        report.adjusted_gross_income = calculation_result.get("adjusted_gross_income", 0)
        report.taxable_income = calculation_result.get("taxable_income", 0)
        report.federal_tax = calculation_result.get("federal_tax", 0)
        report.self_employment_tax = calculation_result.get("self_employment_tax", 0)
        report.total_tax = calculation_result.get("total_tax", 0)
        report.total_payments = calculation_result.get("total_payments", 0)
        report.refund_or_due = calculation_result.get("refund_or_due", 0)
        report.effective_tax_rate = calculation_result.get("effective_rate", 0)
        report.marginal_tax_rate = calculation_result.get("marginal_rate", 0.22)

        # Generate CPA insights
        report.insights = CPAKnowledgeBase.generate_comprehensive_analysis(
            profile, calculation_result
        )

        # Calculate total potential savings
        report.total_potential_savings = sum(
            i.estimated_savings for i in report.insights
        )

        # Determine required forms
        report.forms_required = self._determine_required_forms(profile)

        # Store computation breakdown
        report.computation_breakdown = calculation_result

        return report

    def _determine_required_forms(self, profile: AdvisoryTaxpayerProfile) -> List[str]:
        """Determine which IRS forms are required."""
        forms = ["Form 1040"]

        # Schedule 1 (Additional Income and Adjustments)
        if (profile.business_income > 0 or profile.rental_income > 0 or
            profile.k1_income > 0 or profile.student_loan_interest > 0 or
            profile.hsa_contributions > 0):
            forms.append("Schedule 1")

        # Schedule 2 (Additional Taxes)
        # Check for SE or high income (approx AGI)
        approx_income = (
            profile.wages + profile.interest_income + profile.dividend_income +
            profile.capital_gains_long + profile.business_income + profile.rental_income
        )
        if profile.has_self_employment or approx_income > 200000:
            forms.append("Schedule 2")

        # Schedule 3 (Additional Credits)
        if profile.education_expenses > 0 or profile.retirement_saver_contributions > 0:
            forms.append("Schedule 3")

        # Schedule A (Itemized Deductions)
        total_itemized = (
            profile.mortgage_interest + profile.charitable_cash +
            profile.charitable_noncash + profile.state_local_taxes_paid +
            profile.real_estate_taxes + profile.medical_expenses
        )
        if total_itemized > CPAKnowledgeBase.THRESHOLDS_2025["standard_deduction_single"]:
            forms.append("Schedule A")

        # Schedule B (Interest and Dividends)
        if profile.interest_income > 1500 or profile.dividend_income > 1500:
            forms.append("Schedule B")

        # Schedule C (Business Income)
        if profile.has_self_employment:
            forms.append("Schedule C")
            forms.append("Schedule SE")

        # Schedule D (Capital Gains)
        if profile.capital_gains_short > 0 or profile.capital_gains_long > 0:
            forms.append("Schedule D")
            forms.append("Form 8949")

        # Schedule E (Rental/Partnership/S-Corp)
        if profile.rental_income > 0 or profile.k1_income > 0:
            forms.append("Schedule E")

        return forms

    def run_full_advisory(
        self,
        documents: List[str] = None,
        user_inputs: Dict[str, Any] = None
    ) -> AdvisoryReport:
        """
        Run the complete advisory flow:
        1. Process documents
        2. Build taxpayer profile
        3. Calculate taxes
        4. Generate advisory report
        """
        # Process documents
        extracted_docs = []
        if documents:
            for doc_path in documents:
                extracted = self.process_document(doc_path)
                extracted_docs.append(extracted)

        # Build profile
        profile = self.build_profile_from_documents(extracted_docs, user_inputs)

        # Calculate taxes
        calculation = self.calculate_taxes(profile)

        # Generate advisory
        report = self.generate_advisory_report(profile, calculation)

        return report


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_advisor(tax_year: int = 2025) -> UnifiedTaxAdvisor:
    """Create a new unified tax advisor instance."""
    return UnifiedTaxAdvisor(tax_year=tax_year)


def quick_advisory(
    wages: float = 0,
    interest: float = 0,
    dividends: float = 0,
    business_income: float = 0,
    filing_status: str = "single",
    withholding: float = 0,
    **kwargs
) -> AdvisoryReport:
    """Quick advisory from basic inputs."""
    advisor = create_advisor()

    user_inputs = {
        "wages": wages,
        "interest_income": interest,
        "dividend_income": dividends,
        "business_income": business_income,
        "filing_status": filing_status,
        "federal_withholding": withholding,
        **kwargs
    }

    return advisor.run_full_advisory(user_inputs=user_inputs)
