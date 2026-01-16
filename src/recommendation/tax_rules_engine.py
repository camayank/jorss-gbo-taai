"""Comprehensive Tax Rules Engine.

Contains 350+ tax rules covering all aspects of federal and state taxation
for Tax Year 2025. Rules are categorized for easy maintenance and application.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum


class RuleCategory(Enum):
    """Categories of tax rules."""
    INCOME = "income"
    DEDUCTION = "deduction"
    CREDIT = "credit"
    FILING_STATUS = "filing_status"
    SELF_EMPLOYMENT = "self_employment"
    INVESTMENT = "investment"
    RETIREMENT = "retirement"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    REAL_ESTATE = "real_estate"
    BUSINESS = "business"
    CHARITABLE = "charitable"
    FAMILY = "family"
    STATE_TAX = "state_tax"
    INTERNATIONAL = "international"
    AMT = "amt"
    PENALTY = "penalty"
    TIMING = "timing"
    DOCUMENTATION = "documentation"


class RuleSeverity(Enum):
    """Severity/importance of rule violations."""
    CRITICAL = "critical"  # Must fix - will cause rejection
    HIGH = "high"  # Significant tax impact
    MEDIUM = "medium"  # Moderate tax impact
    LOW = "low"  # Minor optimization
    INFO = "info"  # Informational


@dataclass
class TaxRule:
    """Individual tax rule definition."""
    rule_id: str
    name: str
    description: str
    category: RuleCategory
    severity: RuleSeverity
    irs_reference: str  # Publication, form, or IRC section
    tax_year: int = 2025

    # Rule parameters
    threshold: Optional[float] = None
    limit: Optional[float] = None
    rate: Optional[float] = None
    phase_out_start: Optional[float] = None
    phase_out_end: Optional[float] = None

    # Filing status specific values
    thresholds_by_status: Optional[Dict[str, float]] = None
    limits_by_status: Optional[Dict[str, float]] = None

    # Conditions
    applies_to: Optional[List[str]] = None  # Filing statuses
    requires: Optional[List[str]] = None  # Required conditions
    excludes: Optional[List[str]] = None  # Exclusion conditions

    # Action
    recommendation: Optional[str] = None
    potential_savings: Optional[str] = None


# =============================================================================
# INCOME RULES (50 rules)
# =============================================================================

INCOME_RULES = [
    # Wage Income
    TaxRule(
        rule_id="INC001",
        name="W-2 Wage Reporting",
        description="All W-2 wages must be reported; verify Box 1 matches records",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.CRITICAL,
        irs_reference="Form W-2 Instructions"
    ),
    TaxRule(
        rule_id="INC002",
        name="Multiple W-2 Validation",
        description="Sum of all W-2s must equal total wages reported",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.CRITICAL,
        irs_reference="Form 1040 Line 1"
    ),
    TaxRule(
        rule_id="INC003",
        name="Excess Social Security Withholding",
        description="Multiple employers may over-withhold SS tax; max wage base $176,100",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Form 1040 Line 11",
        threshold=176100.0
    ),
    TaxRule(
        rule_id="INC004",
        name="Tips Income Reporting",
        description="Cash tips over $20/month must be reported to employer",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="Publication 531",
        threshold=20.0
    ),
    TaxRule(
        rule_id="INC005",
        name="Unreported Income Detection",
        description="IRS matches 1099s to returns; unreported income triggers notices",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 6721"
    ),

    # Interest Income
    TaxRule(
        rule_id="INC006",
        name="Taxable Interest Reporting",
        description="All interest income over $10 must be reported",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="Form 1099-INT",
        threshold=10.0
    ),
    TaxRule(
        rule_id="INC007",
        name="Tax-Exempt Interest",
        description="Municipal bond interest is federally tax-exempt but reported",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Form 1040 Line 2a"
    ),
    TaxRule(
        rule_id="INC008",
        name="Original Issue Discount",
        description="OID on bonds accrues annually even if not received",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Form 1099-OID"
    ),
    TaxRule(
        rule_id="INC009",
        name="Savings Bond Interest",
        description="Series EE/I bonds may be tax-free if used for education",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Form 8815"
    ),
    TaxRule(
        rule_id="INC010",
        name="Private Activity Bond AMT",
        description="Interest from private activity bonds is AMT preference item",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Form 6251"
    ),

    # Dividend Income
    TaxRule(
        rule_id="INC011",
        name="Ordinary Dividends",
        description="All dividends reported on 1099-DIV Box 1a",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="Form 1099-DIV"
    ),
    TaxRule(
        rule_id="INC012",
        name="Qualified Dividends",
        description="Qualified dividends taxed at preferential capital gains rates",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="Form 1099-DIV Box 1b"
    ),
    TaxRule(
        rule_id="INC013",
        name="Qualified Dividend Holding Period",
        description="Must hold stock 61+ days during 121-day period around ex-dividend date",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 1(h)(11)"
    ),
    TaxRule(
        rule_id="INC014",
        name="REIT Dividends",
        description="REIT dividends generally not qualified; may qualify for 20% QBI deduction",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 199A"
    ),
    TaxRule(
        rule_id="INC015",
        name="Foreign Dividends",
        description="Foreign dividends may generate foreign tax credit",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Form 1116"
    ),

    # Capital Gains
    TaxRule(
        rule_id="INC016",
        name="Short-Term Capital Gains",
        description="Gains on assets held 1 year or less taxed as ordinary income",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="Schedule D"
    ),
    TaxRule(
        rule_id="INC017",
        name="Long-Term Capital Gains",
        description="Gains on assets held over 1 year taxed at preferential rates (0/15/20%)",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="Schedule D",
        thresholds_by_status={
            "single": 48350.0,  # 0% threshold
            "married_joint": 96700.0,
            "married_separate": 48350.0,
            "head_of_household": 64750.0
        }
    ),
    TaxRule(
        rule_id="INC018",
        name="Capital Loss Limitation",
        description="Net capital losses limited to $3,000/year ($1,500 MFS)",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1211",
        limit=3000.0,
        limits_by_status={"married_separate": 1500.0}
    ),
    TaxRule(
        rule_id="INC019",
        name="Capital Loss Carryover",
        description="Unused capital losses carry forward indefinitely",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 1212"
    ),
    TaxRule(
        rule_id="INC020",
        name="Wash Sale Rule",
        description="Cannot deduct loss if substantially identical security bought within 30 days",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1091"
    ),
    TaxRule(
        rule_id="INC021",
        name="Collectibles Gain Rate",
        description="Gains on collectibles taxed at maximum 28% rate",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 1(h)(5)",
        rate=0.28
    ),
    TaxRule(
        rule_id="INC022",
        name="Section 1250 Recapture",
        description="Unrecaptured Section 1250 gain on real estate taxed at max 25%",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 1250",
        rate=0.25
    ),
    TaxRule(
        rule_id="INC023",
        name="Qualified Small Business Stock",
        description="QSBS held 5+ years may exclude up to 100% of gain (max $10M)",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1202"
    ),
    TaxRule(
        rule_id="INC024",
        name="Installment Sale Treatment",
        description="Gains from installment sales recognized as payments received",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Form 6252"
    ),
    TaxRule(
        rule_id="INC025",
        name="Like-Kind Exchange",
        description="Section 1031 exchanges defer gain on real property",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="Form 8824"
    ),

    # Retirement Income
    TaxRule(
        rule_id="INC026",
        name="Traditional IRA Distributions",
        description="Traditional IRA distributions generally fully taxable",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="Form 1099-R"
    ),
    TaxRule(
        rule_id="INC027",
        name="Roth IRA Qualified Distributions",
        description="Qualified Roth distributions are tax-free after 5 years and age 59.5",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 408A"
    ),
    TaxRule(
        rule_id="INC028",
        name="Required Minimum Distributions",
        description="RMDs required starting at age 73 (SECURE 2.0 Act)",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 401(a)(9)",
        threshold=73.0
    ),
    TaxRule(
        rule_id="INC029",
        name="RMD Penalty",
        description="Failure to take RMD results in 25% penalty (10% if corrected)",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 4974",
        rate=0.25
    ),
    TaxRule(
        rule_id="INC030",
        name="Pension Income",
        description="Pension distributions from 401(k), 403(b) generally fully taxable",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="Form 1099-R"
    ),

    # Social Security
    TaxRule(
        rule_id="INC031",
        name="Social Security Taxation - 50%",
        description="Up to 50% of SS benefits taxable if provisional income exceeds base",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="Publication 915",
        thresholds_by_status={
            "single": 25000.0,
            "married_joint": 32000.0
        }
    ),
    TaxRule(
        rule_id="INC032",
        name="Social Security Taxation - 85%",
        description="Up to 85% of SS benefits taxable at higher provisional income",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="Publication 915",
        thresholds_by_status={
            "single": 34000.0,
            "married_joint": 44000.0
        }
    ),
    TaxRule(
        rule_id="INC033",
        name="Social Security Lump-Sum Election",
        description="May elect to allocate lump-sum payment to prior years",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.LOW,
        irs_reference="Publication 915"
    ),

    # Business/Self-Employment Income
    TaxRule(
        rule_id="INC034",
        name="Schedule C Reporting",
        description="Self-employment income reported on Schedule C",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.CRITICAL,
        irs_reference="Schedule C"
    ),
    TaxRule(
        rule_id="INC035",
        name="1099-NEC Reporting",
        description="Non-employee compensation over $600 reported on 1099-NEC",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="Form 1099-NEC",
        threshold=600.0
    ),
    TaxRule(
        rule_id="INC036",
        name="1099-K Threshold",
        description="Third-party payment processors report on 1099-K if over $600",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="Form 1099-K",
        threshold=600.0
    ),
    TaxRule(
        rule_id="INC037",
        name="Passive Activity Income",
        description="Passive income generally cannot offset non-passive losses",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Form 8582"
    ),
    TaxRule(
        rule_id="INC038",
        name="Material Participation",
        description="Must meet 1 of 7 tests for income to be non-passive",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 469"
    ),

    # Rental Income
    TaxRule(
        rule_id="INC039",
        name="Rental Income Reporting",
        description="Rental income and expenses reported on Schedule E",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="Schedule E"
    ),
    TaxRule(
        rule_id="INC040",
        name="Rental Loss Limitation",
        description="Passive rental losses limited; $25K exception for active participation",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 469(i)",
        limit=25000.0
    ),
    TaxRule(
        rule_id="INC041",
        name="Real Estate Professional",
        description="750+ hours and >50% time in real estate = non-passive treatment",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 469(c)(7)"
    ),

    # Other Income
    TaxRule(
        rule_id="INC042",
        name="Alimony Income (Pre-2019)",
        description="Alimony from pre-2019 divorces is taxable income",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 71"
    ),
    TaxRule(
        rule_id="INC043",
        name="Gambling Income",
        description="All gambling winnings are taxable; W-2G for amounts over $600",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="Form W-2G",
        threshold=600.0
    ),
    TaxRule(
        rule_id="INC044",
        name="Cryptocurrency Income",
        description="Crypto sales, exchanges, and income are taxable events",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="Notice 2014-21"
    ),
    TaxRule(
        rule_id="INC045",
        name="Unemployment Compensation",
        description="Unemployment benefits are fully taxable",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="Form 1099-G"
    ),
    TaxRule(
        rule_id="INC046",
        name="Cancellation of Debt Income",
        description="Forgiven debt is generally taxable income",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="Form 1099-C"
    ),
    TaxRule(
        rule_id="INC047",
        name="Discharge of Indebtedness Exclusions",
        description="Insolvency, bankruptcy may exclude COD income",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Form 982"
    ),
    TaxRule(
        rule_id="INC048",
        name="Prize and Award Income",
        description="Prizes, awards, and sweepstakes are taxable",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 74"
    ),
    TaxRule(
        rule_id="INC049",
        name="Royalty Income",
        description="Royalties from intellectual property are taxable",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.HIGH,
        irs_reference="Schedule E"
    ),
    TaxRule(
        rule_id="INC050",
        name="Hobby Income vs Business",
        description="Hobby income taxable but losses not deductible; 9 factors test",
        category=RuleCategory.INCOME,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 183"
    ),
]

# =============================================================================
# DEDUCTION RULES (75 rules)
# =============================================================================

DEDUCTION_RULES = [
    # Standard Deduction (2025 amounts per IRS Rev. Proc. 2024-40)
    TaxRule(
        rule_id="DED001",
        name="Standard Deduction - Single",
        description="Standard deduction for single filers ($15,750 for 2025)",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 63",
        threshold=15750.0
    ),
    TaxRule(
        rule_id="DED002",
        name="Standard Deduction - MFJ",
        description="Standard deduction for married filing jointly ($31,500 for 2025)",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 63",
        threshold=31500.0
    ),
    TaxRule(
        rule_id="DED003",
        name="Standard Deduction - HOH",
        description="Standard deduction for head of household ($23,625 for 2025)",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 63",
        threshold=23625.0
    ),
    TaxRule(
        rule_id="DED004",
        name="Additional Standard Deduction - Age",
        description="Additional $1,950 (single/HOH) or $1,550 (married) if age 65+",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 63(f)"
    ),
    TaxRule(
        rule_id="DED005",
        name="Additional Standard Deduction - Blind",
        description="Additional $1,950 (single/HOH) or $1,550 (married) if blind",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 63(f)"
    ),

    # Itemized Deductions
    TaxRule(
        rule_id="DED006",
        name="Itemized vs Standard Choice",
        description="Choose itemized only if total exceeds standard deduction",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="Schedule A",
        recommendation="Compare itemized total to standard deduction"
    ),
    TaxRule(
        rule_id="DED007",
        name="SALT Cap",
        description="State and local tax deduction capped at $10,000 ($5,000 MFS)",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 164(b)(6)",
        limit=10000.0,
        limits_by_status={"married_separate": 5000.0}
    ),
    TaxRule(
        rule_id="DED008",
        name="State Income Tax or Sales Tax",
        description="Can deduct state income tax OR sales tax, not both",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Schedule A Line 5"
    ),
    TaxRule(
        rule_id="DED009",
        name="Real Estate Tax Deduction",
        description="Property taxes on real estate deductible (within SALT cap)",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="Schedule A Line 5b"
    ),
    TaxRule(
        rule_id="DED010",
        name="Personal Property Tax",
        description="Personal property taxes deductible if based on value",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Schedule A Line 5c"
    ),

    # Medical Expenses
    TaxRule(
        rule_id="DED011",
        name="Medical Expense Floor",
        description="Medical expenses deductible only above 7.5% of AGI",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 213",
        rate=0.075
    ),
    TaxRule(
        rule_id="DED012",
        name="Qualified Medical Expenses",
        description="Includes doctors, hospitals, prescriptions, insurance premiums",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Publication 502"
    ),
    TaxRule(
        rule_id="DED013",
        name="Health Insurance Premiums",
        description="Self-paid health insurance premiums may be deductible",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Publication 502"
    ),
    TaxRule(
        rule_id="DED014",
        name="Long-Term Care Premiums",
        description="Age-based limits on deductible LTC insurance premiums",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 213(d)(10)"
    ),
    TaxRule(
        rule_id="DED015",
        name="Medical Miles Deduction",
        description="Medical travel at 67 cents per mile (2025)",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.LOW,
        irs_reference="Publication 502",
        rate=0.67
    ),

    # Mortgage Interest
    TaxRule(
        rule_id="DED016",
        name="Mortgage Interest Deduction",
        description="Interest on acquisition debt up to $750,000 ($375,000 MFS)",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 163(h)",
        limit=750000.0,
        limits_by_status={"married_separate": 375000.0}
    ),
    TaxRule(
        rule_id="DED017",
        name="Grandfathered Mortgage Limit",
        description="Pre-12/15/2017 mortgages: $1M limit ($500K MFS)",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 163(h)",
        limit=1000000.0
    ),
    TaxRule(
        rule_id="DED018",
        name="Home Equity Loan Interest",
        description="HELOC interest only deductible if used for home improvements",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 163(h)(3)"
    ),
    TaxRule(
        rule_id="DED019",
        name="Mortgage Points Deduction",
        description="Points on home purchase deductible in year paid",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Publication 936"
    ),
    TaxRule(
        rule_id="DED020",
        name="Refinance Points Amortization",
        description="Points on refinance must be amortized over loan term",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Publication 936"
    ),

    # Charitable Contributions
    TaxRule(
        rule_id="DED021",
        name="Cash Charitable Limit",
        description="Cash contributions limited to 60% of AGI",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 170(b)",
        rate=0.60
    ),
    TaxRule(
        rule_id="DED022",
        name="Property Charitable Limit",
        description="Appreciated property contributions limited to 30% of AGI",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 170(b)",
        rate=0.30
    ),
    TaxRule(
        rule_id="DED023",
        name="Charitable Carryover",
        description="Excess charitable contributions carry forward 5 years",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 170(d)"
    ),
    TaxRule(
        rule_id="DED024",
        name="Charitable Documentation - Under $250",
        description="Donations under $250 need canceled check or receipt",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Publication 1771",
        threshold=250.0
    ),
    TaxRule(
        rule_id="DED025",
        name="Charitable Documentation - $250+",
        description="Donations $250+ need contemporaneous written acknowledgment",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 170(f)(8)",
        threshold=250.0
    ),
    TaxRule(
        rule_id="DED026",
        name="Non-Cash Charitable - Over $500",
        description="Non-cash donations over $500 require Form 8283",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="Form 8283",
        threshold=500.0
    ),
    TaxRule(
        rule_id="DED027",
        name="Non-Cash Charitable - Over $5,000",
        description="Non-cash donations over $5,000 require qualified appraisal",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 170(f)(11)",
        threshold=5000.0
    ),
    TaxRule(
        rule_id="DED028",
        name="Qualified Charitable Distribution",
        description="QCDs from IRA directly to charity (age 70.5+, up to $105,000)",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 408(d)(8)",
        limit=105000.0
    ),
    TaxRule(
        rule_id="DED029",
        name="Vehicle Donation Rules",
        description="Vehicle donations over $500 limited to charity's sales price",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 170(f)(12)",
        threshold=500.0
    ),
    TaxRule(
        rule_id="DED030",
        name="Donor-Advised Fund Timing",
        description="DAF contributions deductible when made, not when distributed",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 170"
    ),

    # Above-the-Line Deductions
    TaxRule(
        rule_id="DED031",
        name="Educator Expense Deduction",
        description="K-12 teachers can deduct up to $300 for classroom supplies",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 62(a)(2)(D)",
        limit=300.0
    ),
    TaxRule(
        rule_id="DED032",
        name="Student Loan Interest Deduction",
        description="Up to $2,500 deductible; phases out at higher incomes",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 221",
        limit=2500.0,
        phase_out_start=90000.0,  # Single
        phase_out_end=110000.0
    ),
    TaxRule(
        rule_id="DED033",
        name="HSA Contribution Deduction",
        description="HSA contributions deductible up to limits ($4,300/$8,550)",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 223",
        limits_by_status={"individual": 4300.0, "family": 8550.0}
    ),
    TaxRule(
        rule_id="DED034",
        name="HSA Catch-Up Contribution",
        description="Additional $1,000 HSA contribution if age 55+",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 223(b)(3)",
        limit=1000.0
    ),
    TaxRule(
        rule_id="DED035",
        name="Traditional IRA Deduction",
        description="Up to $7,000 ($8,000 if 50+) deductible with income limits",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 219",
        limit=7000.0
    ),
    TaxRule(
        rule_id="DED036",
        name="IRA Deduction - Covered by Plan",
        description="If covered by employer plan, IRA deduction phases out",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 219(g)",
        phase_out_start=87000.0,  # Single, covered by plan
        phase_out_end=107000.0
    ),
    TaxRule(
        rule_id="DED037",
        name="SE Health Insurance Deduction",
        description="Self-employed can deduct 100% of health insurance premiums",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 162(l)"
    ),
    TaxRule(
        rule_id="DED038",
        name="SE Retirement Deduction",
        description="SEP-IRA, SIMPLE, Solo 401(k) contributions deductible",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 404"
    ),
    TaxRule(
        rule_id="DED039",
        name="SE Tax Deduction",
        description="50% of self-employment tax is deductible",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 164(f)"
    ),
    TaxRule(
        rule_id="DED040",
        name="Alimony Deduction (Pre-2019)",
        description="Alimony paid under pre-2019 divorce agreements is deductible",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 215"
    ),

    # Business Deductions
    TaxRule(
        rule_id="DED041",
        name="Business Expense Deduction",
        description="Ordinary and necessary business expenses deductible",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 162"
    ),
    TaxRule(
        rule_id="DED042",
        name="Home Office Deduction",
        description="Regular and exclusive business use of home required",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 280A"
    ),
    TaxRule(
        rule_id="DED043",
        name="Simplified Home Office",
        description="$5 per sq ft, max 300 sq ft ($1,500)",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Rev. Proc. 2013-13",
        limit=1500.0
    ),
    TaxRule(
        rule_id="DED044",
        name="Business Vehicle Deduction",
        description="Standard mileage rate: 70 cents per mile (2025)",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Notice 2024-8",
        rate=0.70
    ),
    TaxRule(
        rule_id="DED045",
        name="Business Meals Deduction",
        description="Business meals 50% deductible; entertainment not deductible",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 274",
        rate=0.50
    ),
    TaxRule(
        rule_id="DED046",
        name="Section 179 Expensing",
        description="Immediate deduction for equipment up to $1,250,000",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 179",
        limit=1250000.0
    ),
    TaxRule(
        rule_id="DED047",
        name="Bonus Depreciation",
        description="60% bonus depreciation in 2025 (phasing down)",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 168(k)",
        rate=0.60
    ),
    TaxRule(
        rule_id="DED048",
        name="Business Interest Limitation",
        description="Interest expense limited to 30% of adjusted taxable income",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 163(j)",
        rate=0.30
    ),
    TaxRule(
        rule_id="DED049",
        name="QBI Deduction",
        description="20% deduction for qualified business income",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 199A",
        rate=0.20
    ),
    TaxRule(
        rule_id="DED050",
        name="QBI SSTB Limitation",
        description="Specified service businesses limited above income thresholds",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 199A(d)",
        thresholds_by_status={
            "single": 191950.0,
            "married_joint": 383900.0
        }
    ),

    # More deductions continued...
    TaxRule(
        rule_id="DED051",
        name="Investment Interest Expense",
        description="Investment interest limited to net investment income",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 163(d)"
    ),
    TaxRule(
        rule_id="DED052",
        name="Gambling Loss Limitation",
        description="Gambling losses limited to gambling winnings",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 165(d)"
    ),
    TaxRule(
        rule_id="DED053",
        name="Casualty Loss - Federally Declared",
        description="Personal casualty losses only for federally declared disasters",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 165(h)"
    ),
    TaxRule(
        rule_id="DED054",
        name="Net Operating Loss",
        description="NOL limited to 80% of taxable income; indefinite carryforward",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 172",
        rate=0.80
    ),
    TaxRule(
        rule_id="DED055",
        name="Moving Expense Deduction",
        description="Only available to active military members",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 217"
    ),

    # Additional itemized and miscellaneous
    TaxRule(
        rule_id="DED056",
        name="No Miscellaneous Itemized",
        description="Miscellaneous itemized deductions eliminated through 2025",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.INFO,
        irs_reference="IRC Section 67(g)"
    ),
    TaxRule(
        rule_id="DED057",
        name="No Personal Exemptions",
        description="Personal exemptions suspended through 2025",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.INFO,
        irs_reference="IRC Section 151(d)(5)"
    ),
    TaxRule(
        rule_id="DED058",
        name="Deduction Bunching Strategy",
        description="Bunch itemized deductions in alternate years",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Publication 17",
        recommendation="Accelerate or defer deductions to maximize benefit"
    ),
    TaxRule(
        rule_id="DED059",
        name="Depreciation Recapture",
        description="Depreciation recaptured as ordinary income on sale",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1245"
    ),
    TaxRule(
        rule_id="DED060",
        name="Passive Loss Suspended",
        description="Suspended passive losses allowed upon disposition",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 469(g)"
    ),

    # Retirement contribution deductions
    TaxRule(
        rule_id="DED061",
        name="401(k) Contribution Limit",
        description="Employee 401(k) contributions up to $23,500 (2025)",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 402(g)",
        limit=23500.0
    ),
    TaxRule(
        rule_id="DED062",
        name="401(k) Catch-Up Limit",
        description="Additional $7,500 if age 50+ ($11,250 if age 60-63)",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 414(v)",
        limit=7500.0
    ),
    TaxRule(
        rule_id="DED063",
        name="SEP-IRA Limit",
        description="SEP contributions up to 25% of compensation (max $69,000)",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 408(j)",
        limit=69000.0,
        rate=0.25
    ),
    TaxRule(
        rule_id="DED064",
        name="SIMPLE IRA Limit",
        description="SIMPLE contributions up to $16,500 ($3,500 catch-up)",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 408(p)",
        limit=16500.0
    ),
    TaxRule(
        rule_id="DED065",
        name="Solo 401(k) Total Limit",
        description="Total contributions (employee + employer) up to $69,000",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 415(c)",
        limit=69000.0
    ),

    # More specific deductions
    TaxRule(
        rule_id="DED066",
        name="Health Coverage Penalty",
        description="No federal penalty for lacking health insurance (since 2019)",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.INFO,
        irs_reference="IRC Section 5000A"
    ),
    TaxRule(
        rule_id="DED067",
        name="Tuition Deduction Eliminated",
        description="Tuition and fees deduction expired; use education credits",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.INFO,
        irs_reference="IRC Section 222"
    ),
    TaxRule(
        rule_id="DED068",
        name="Adoption Expense Deduction",
        description="No deduction, but credit available up to $16,810",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 36C"
    ),
    TaxRule(
        rule_id="DED069",
        name="Domestic Production Deduction",
        description="Section 199 domestic production deduction eliminated",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.INFO,
        irs_reference="Former IRC Section 199"
    ),
    TaxRule(
        rule_id="DED070",
        name="Fringe Benefits",
        description="Many employer fringe benefits excludable from income",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 132"
    ),
    TaxRule(
        rule_id="DED071",
        name="Dependent Care FSA",
        description="Up to $5,000 pre-tax for dependent care ($2,500 MFS)",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 129",
        limit=5000.0
    ),
    TaxRule(
        rule_id="DED072",
        name="Health FSA Limit",
        description="Health FSA contributions up to $3,300 (2025)",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 125",
        limit=3300.0
    ),
    TaxRule(
        rule_id="DED073",
        name="Commuter Benefits",
        description="Up to $325/month for transit and parking (2025)",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 132(f)",
        limit=325.0
    ),
    TaxRule(
        rule_id="DED074",
        name="Education Assistance",
        description="Up to $5,250 tax-free from employer for education",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 127",
        limit=5250.0
    ),
    TaxRule(
        rule_id="DED075",
        name="Student Loan Payment Benefit",
        description="Employer student loan payments up to $5,250 tax-free",
        category=RuleCategory.DEDUCTION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 127(c)",
        limit=5250.0
    ),
]

# =============================================================================
# CREDIT RULES (75 rules)
# =============================================================================

CREDIT_RULES = [
    # Child Tax Credit
    TaxRule(
        rule_id="CRD001",
        name="Child Tax Credit",
        description="$2,000 per qualifying child under 17",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 24",
        limit=2000.0
    ),
    TaxRule(
        rule_id="CRD002",
        name="Child Tax Credit Phaseout",
        description="CTC phases out above $200K/$400K (single/MFJ)",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 24(b)",
        thresholds_by_status={
            "single": 200000.0,
            "married_joint": 400000.0
        }
    ),
    TaxRule(
        rule_id="CRD003",
        name="Additional Child Tax Credit",
        description="Refundable portion up to $1,700 per child",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 24(h)",
        limit=1700.0
    ),
    TaxRule(
        rule_id="CRD004",
        name="Other Dependent Credit",
        description="$500 credit for dependents who don't qualify for CTC",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 24(h)(4)",
        limit=500.0
    ),
    TaxRule(
        rule_id="CRD005",
        name="Qualifying Child Age",
        description="Child must be under 17 at end of tax year for CTC",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 24(c)"
    ),

    # Earned Income Credit
    # EITC max credit amounts for 2025 (IRS Rev. Proc. 2024-40)
    TaxRule(
        rule_id="CRD006",
        name="Earned Income Credit - No Children",
        description="EITC up to $649 with no qualifying children",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 32",
        limit=649.0
    ),
    TaxRule(
        rule_id="CRD007",
        name="Earned Income Credit - 1 Child",
        description="EITC up to $4,328 with one qualifying child",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 32",
        limit=4328.0
    ),
    TaxRule(
        rule_id="CRD008",
        name="Earned Income Credit - 2 Children",
        description="EITC up to $7,152 with two qualifying children",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 32",
        limit=7152.0
    ),
    TaxRule(
        rule_id="CRD009",
        name="Earned Income Credit - 3+ Children",
        description="EITC up to $8,046 with three or more qualifying children",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 32",
        limit=8046.0
    ),
    TaxRule(
        rule_id="CRD010",
        name="EITC Investment Income Limit",
        description="Investment income must be $11,600 or less",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 32(i)",
        limit=11600.0
    ),
    TaxRule(
        rule_id="CRD011",
        name="EITC Age Requirement",
        description="Must be 25-64 (19+ for former foster/homeless youth)",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 32(c)"
    ),

    # Education Credits
    TaxRule(
        rule_id="CRD012",
        name="American Opportunity Credit",
        description="Up to $2,500 per student for first 4 years of college",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 25A(b)",
        limit=2500.0
    ),
    TaxRule(
        rule_id="CRD013",
        name="AOTC Refundable Portion",
        description="40% of AOTC (up to $1,000) is refundable",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 25A(i)",
        rate=0.40,
        limit=1000.0
    ),
    TaxRule(
        rule_id="CRD014",
        name="AOTC Income Limits",
        description="Phases out $80K-$90K (single) / $160K-$180K (MFJ)",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 25A(d)",
        thresholds_by_status={
            "single": 80000.0,
            "married_joint": 160000.0
        }
    ),
    TaxRule(
        rule_id="CRD015",
        name="Lifetime Learning Credit",
        description="Up to $2,000 per return (20% of $10,000 expenses)",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 25A(c)",
        limit=2000.0,
        rate=0.20
    ),
    TaxRule(
        rule_id="CRD016",
        name="LLC Income Limits",
        description="Phases out $91K-$111K (single) / $182K-$222K (MFJ)",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 25A(d)"
    ),
    TaxRule(
        rule_id="CRD017",
        name="No Double Education Benefit",
        description="Cannot claim AOTC and LLC for same student in same year",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 25A(g)"
    ),

    # Child and Dependent Care Credit
    TaxRule(
        rule_id="CRD018",
        name="Child Care Credit",
        description="20-35% of expenses up to $3,000/$6,000 (1/2+ children)",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 21",
        limit=6000.0
    ),
    TaxRule(
        rule_id="CRD019",
        name="Child Care Credit Rate",
        description="Credit rate: 35% at $15K AGI, decreasing to 20% at $43K+",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 21(a)"
    ),
    TaxRule(
        rule_id="CRD020",
        name="Child Care Earned Income Limit",
        description="Expenses limited to earned income (lower spouse if MFJ)",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 21(d)"
    ),

    # Saver's Credit
    TaxRule(
        rule_id="CRD021",
        name="Saver's Credit",
        description="10-50% of retirement contributions up to $2,000",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 25B",
        limit=2000.0
    ),
    TaxRule(
        rule_id="CRD022",
        name="Saver's Credit Income Limits",
        description="Max AGI: $38,250 single / $76,500 MFJ for 50% rate",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 25B(b)",
        thresholds_by_status={
            "single": 38250.0,
            "married_joint": 76500.0
        }
    ),

    # Energy Credits
    TaxRule(
        rule_id="CRD023",
        name="Clean Vehicle Credit - New",
        description="Up to $7,500 for new clean vehicles",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 30D",
        limit=7500.0
    ),
    TaxRule(
        rule_id="CRD024",
        name="Clean Vehicle Credit - Used",
        description="Up to $4,000 for used clean vehicles (30% of price)",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 25E",
        limit=4000.0
    ),
    TaxRule(
        rule_id="CRD025",
        name="Clean Vehicle Income Limits",
        description="MAGI limit: $150K single / $300K MFJ for new vehicles",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 30D(f)",
        thresholds_by_status={
            "single": 150000.0,
            "married_joint": 300000.0
        }
    ),
    TaxRule(
        rule_id="CRD026",
        name="Residential Clean Energy Credit",
        description="30% credit for solar, wind, geothermal through 2032",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 25D",
        rate=0.30
    ),
    TaxRule(
        rule_id="CRD027",
        name="Energy Efficient Home Credit",
        description="Up to $1,200/year for efficiency improvements",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 25C",
        limit=1200.0
    ),
    TaxRule(
        rule_id="CRD028",
        name="Heat Pump Credit",
        description="Up to $2,000 for heat pumps and biomass stoves",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 25C",
        limit=2000.0
    ),

    # Premium Tax Credit
    TaxRule(
        rule_id="CRD029",
        name="Premium Tax Credit",
        description="Refundable credit for marketplace health insurance",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 36B"
    ),
    TaxRule(
        rule_id="CRD030",
        name="PTC Income Limits",
        description="Available to those 100-400% of FPL (expanded through 2025)",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 36B(c)"
    ),
    TaxRule(
        rule_id="CRD031",
        name="PTC Reconciliation",
        description="Must reconcile advance PTC on tax return (Form 8962)",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="Form 8962"
    ),

    # Adoption Credit
    TaxRule(
        rule_id="CRD032",
        name="Adoption Credit",
        description="Up to $16,810 per child for qualified adoption expenses",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 36C",
        limit=16810.0
    ),
    TaxRule(
        rule_id="CRD033",
        name="Adoption Credit Phaseout",
        description="Phases out $252,150-$292,150 MAGI",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 36C(b)",
        phase_out_start=252150.0,
        phase_out_end=292150.0
    ),

    # Foreign Tax Credit
    TaxRule(
        rule_id="CRD034",
        name="Foreign Tax Credit",
        description="Credit for taxes paid to foreign countries",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 901"
    ),
    TaxRule(
        rule_id="CRD035",
        name="Foreign Tax Credit Limit",
        description="Limited to US tax on foreign source income",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 904"
    ),
    TaxRule(
        rule_id="CRD036",
        name="Foreign Tax Simplified",
        description="No Form 1116 needed if total foreign tax ≤$300/$600 (single/MFJ)",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 904(j)",
        limit=300.0,
        limits_by_status={"married_joint": 600.0}
    ),

    # Elderly and Disabled Credit
    TaxRule(
        rule_id="CRD037",
        name="Elderly/Disabled Credit",
        description="Credit for those 65+ or permanently disabled",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 22"
    ),
    TaxRule(
        rule_id="CRD038",
        name="Elderly Credit Income Limits",
        description="AGI limit: $17,500 single / $25,000 MFJ (both 65+)",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 22(c)",
        thresholds_by_status={
            "single": 17500.0,
            "married_joint": 25000.0
        }
    ),

    # Business Credits
    TaxRule(
        rule_id="CRD039",
        name="General Business Credit",
        description="Combination of various business credits",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 38"
    ),
    TaxRule(
        rule_id="CRD040",
        name="Research Credit",
        description="20% credit for qualified research expenses",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 41",
        rate=0.20
    ),
    TaxRule(
        rule_id="CRD041",
        name="Small Business R&D Payroll Tax Credit",
        description="Small businesses can apply R&D credit against payroll tax",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 41(h)"
    ),
    TaxRule(
        rule_id="CRD042",
        name="Work Opportunity Credit",
        description="Credit for hiring from target groups (up to $2,400-$9,600)",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 51"
    ),
    TaxRule(
        rule_id="CRD043",
        name="Disabled Access Credit",
        description="50% of expenses $250-$10,250 for accessibility",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 44"
    ),
    TaxRule(
        rule_id="CRD044",
        name="Small Employer Health Credit",
        description="Up to 50% of premiums for small employers",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 45R",
        rate=0.50
    ),
    TaxRule(
        rule_id="CRD045",
        name="Employer Retirement Plan Credit",
        description="Up to $5,000/year for 3 years for new retirement plans",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 45E",
        limit=5000.0
    ),

    # Additional credits...
    TaxRule(
        rule_id="CRD046",
        name="Mortgage Interest Credit",
        description="For first-time homebuyers with MCC certificate",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 25"
    ),
    TaxRule(
        rule_id="CRD047",
        name="First-Time Homebuyer Credit (DC)",
        description="DC residents: up to $5,000 credit",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 36(g)",
        limit=5000.0
    ),
    TaxRule(
        rule_id="CRD048",
        name="Refundable vs Nonrefundable",
        description="Nonrefundable credits limited to tax liability",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="Form 1040"
    ),
    TaxRule(
        rule_id="CRD049",
        name="Credit Carryforward",
        description="Some unused credits carry forward to future years",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Various IRC sections"
    ),
    TaxRule(
        rule_id="CRD050",
        name="Credit Phase-Out Ordering",
        description="Calculate credits in proper order for phase-outs",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Form 1040 Instructions"
    ),

    # More specialized credits
    TaxRule(
        rule_id="CRD051",
        name="Recovery Rebate Credit",
        description="Economic impact payments reconciled on return",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.INFO,
        irs_reference="IRC Section 6428B"
    ),
    TaxRule(
        rule_id="CRD052",
        name="Low-Income Housing Credit",
        description="Credit for investment in qualified low-income housing",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 42"
    ),
    TaxRule(
        rule_id="CRD053",
        name="Rehabilitation Credit",
        description="20% credit for rehabilitation of historic structures",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 47",
        rate=0.20
    ),
    TaxRule(
        rule_id="CRD054",
        name="Biodiesel Credit",
        description="$1 per gallon for biodiesel production",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 40A"
    ),
    TaxRule(
        rule_id="CRD055",
        name="Alternative Motor Vehicle Credit",
        description="Credit for qualified fuel cell vehicles",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 30B"
    ),

    # State-related credits
    TaxRule(
        rule_id="CRD056",
        name="State EITC",
        description="Many states offer state EITC as percentage of federal",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="State tax laws"
    ),
    TaxRule(
        rule_id="CRD057",
        name="State Child Tax Credit",
        description="Some states offer additional child tax credits",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="State tax laws"
    ),

    # International credits
    TaxRule(
        rule_id="CRD058",
        name="Foreign Earned Income Exclusion",
        description="Up to $130,000 exclusion for qualified foreign residents",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 911",
        limit=130000.0
    ),
    TaxRule(
        rule_id="CRD059",
        name="Foreign Housing Exclusion",
        description="Additional exclusion for qualified housing expenses",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 911(c)"
    ),

    # Retirement-related credits
    TaxRule(
        rule_id="CRD060",
        name="Excess IRA Contribution Penalty Credit",
        description="6% penalty on excess contributions",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 4973",
        rate=0.06
    ),

    # Additional specialized credits (61-75)
    TaxRule(
        rule_id="CRD061",
        name="Minimum Tax Credit",
        description="Credit for prior year AMT on timing items",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 53"
    ),
    TaxRule(
        rule_id="CRD062",
        name="Excess Social Security Credit",
        description="Credit for excess SS withheld from multiple employers",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Form 1040 Line 11"
    ),
    TaxRule(
        rule_id="CRD063",
        name="Employer Credit for FMLA",
        description="Credit for paid family and medical leave",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 45S"
    ),
    TaxRule(
        rule_id="CRD064",
        name="Indian Employment Credit",
        description="Credit for wages paid to qualified Native Americans",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 45A"
    ),
    TaxRule(
        rule_id="CRD065",
        name="Empowerment Zone Credit",
        description="Credit for wages in empowerment zones",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 1396"
    ),
    TaxRule(
        rule_id="CRD066",
        name="Clean Coal Credit",
        description="Credit for advanced clean coal projects",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 48A"
    ),
    TaxRule(
        rule_id="CRD067",
        name="Carbon Capture Credit",
        description="Credit per metric ton of qualified carbon oxide captured",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 45Q"
    ),
    TaxRule(
        rule_id="CRD068",
        name="Production Tax Credit",
        description="Credit for renewable electricity production",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 45"
    ),
    TaxRule(
        rule_id="CRD069",
        name="Investment Tax Credit",
        description="Credit for investment in energy property",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 48"
    ),
    TaxRule(
        rule_id="CRD070",
        name="Clean Hydrogen Credit",
        description="Credit for clean hydrogen production",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 45V"
    ),
    TaxRule(
        rule_id="CRD071",
        name="Alternative Fuel Credit",
        description="Credit for alternative fuel use",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 6426"
    ),
    TaxRule(
        rule_id="CRD072",
        name="Orphan Drug Credit",
        description="25% credit for clinical testing of orphan drugs",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 45C",
        rate=0.25
    ),
    TaxRule(
        rule_id="CRD073",
        name="New Markets Credit",
        description="Credit for investment in low-income communities",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 45D"
    ),
    TaxRule(
        rule_id="CRD074",
        name="Employee Retention Credit",
        description="COVID-era credit (expired but may affect amended returns)",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.INFO,
        irs_reference="IRC Section 3134"
    ),
    TaxRule(
        rule_id="CRD075",
        name="Credit Sequencing",
        description="Apply nonrefundable credits before refundable credits",
        category=RuleCategory.CREDIT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Form 1040 Instructions"
    ),
]

# =============================================================================
# SELF-EMPLOYMENT RULES (25 rules)
# =============================================================================

SELF_EMPLOYMENT_RULES = [
    TaxRule(
        rule_id="SE001",
        name="SE Tax Rate",
        description="Self-employment tax: 15.3% (12.4% SS + 2.9% Medicare)",
        category=RuleCategory.SELF_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="Schedule SE",
        rate=0.153
    ),
    TaxRule(
        rule_id="SE002",
        name="SE Tax Calculation Base",
        description="SE tax applies to 92.35% of net SE earnings",
        category=RuleCategory.SELF_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1402",
        rate=0.9235
    ),
    TaxRule(
        rule_id="SE003",
        name="SS Wage Base Cap",
        description="Social Security tax capped at $176,100 wage base (2025)",
        category=RuleCategory.SELF_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 3121",
        limit=176100.0
    ),
    TaxRule(
        rule_id="SE004",
        name="Additional Medicare Tax",
        description="0.9% additional Medicare on SE income over $200K/$250K",
        category=RuleCategory.SELF_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1401",
        rate=0.009,
        thresholds_by_status={
            "single": 200000.0,
            "married_joint": 250000.0
        }
    ),
    TaxRule(
        rule_id="SE005",
        name="SE Threshold",
        description="SE tax due if net SE earnings ≥ $400",
        category=RuleCategory.SELF_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1402",
        threshold=400.0
    ),
    TaxRule(
        rule_id="SE006",
        name="Church Employee Threshold",
        description="Church employee SE tax threshold is $108.28",
        category=RuleCategory.SELF_EMPLOYMENT,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 1402(a)",
        threshold=108.28
    ),
    TaxRule(
        rule_id="SE007",
        name="Estimated Tax Payments",
        description="Must make quarterly estimated payments if tax ≥ $1,000",
        category=RuleCategory.SELF_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="Form 1040-ES",
        threshold=1000.0
    ),
    TaxRule(
        rule_id="SE008",
        name="Estimated Tax Due Dates",
        description="April 15, June 15, Sept 15, Jan 15",
        category=RuleCategory.SELF_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 6654"
    ),
    TaxRule(
        rule_id="SE009",
        name="Underpayment Penalty",
        description="Penalty for underpaying estimated taxes",
        category=RuleCategory.SELF_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Form 2210"
    ),
    TaxRule(
        rule_id="SE010",
        name="Safe Harbor - Prior Year",
        description="No penalty if payments ≥ 100% of prior year tax (110% if AGI > $150K)",
        category=RuleCategory.SELF_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 6654(d)"
    ),
    TaxRule(
        rule_id="SE011",
        name="Qualified Business Income",
        description="20% QBI deduction on net SE income",
        category=RuleCategory.SELF_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 199A",
        rate=0.20
    ),
    TaxRule(
        rule_id="SE012",
        name="Reasonable Compensation (S-Corp)",
        description="S-Corp shareholders must take reasonable salary",
        category=RuleCategory.SELF_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1366"
    ),
    TaxRule(
        rule_id="SE013",
        name="Schedule C Required",
        description="Must file Schedule C for sole proprietorship",
        category=RuleCategory.SELF_EMPLOYMENT,
        severity=RuleSeverity.CRITICAL,
        irs_reference="Schedule C"
    ),
    TaxRule(
        rule_id="SE014",
        name="Record Keeping",
        description="Must maintain adequate business records",
        category=RuleCategory.SELF_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="Publication 583"
    ),
    TaxRule(
        rule_id="SE015",
        name="EIN Requirement",
        description="Need EIN if have employees or certain plan types",
        category=RuleCategory.SELF_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Form SS-4"
    ),
    TaxRule(
        rule_id="SE016",
        name="Home Office Requirements",
        description="Regular and exclusive use required for deduction",
        category=RuleCategory.SELF_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 280A"
    ),
    TaxRule(
        rule_id="SE017",
        name="Vehicle Expense Substantiation",
        description="Must maintain contemporaneous mileage log",
        category=RuleCategory.SELF_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 274"
    ),
    TaxRule(
        rule_id="SE018",
        name="Inventory Accounting",
        description="Required if have inventory for sale",
        category=RuleCategory.SELF_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 471"
    ),
    TaxRule(
        rule_id="SE019",
        name="Cash vs Accrual Method",
        description="Most small businesses can use cash method",
        category=RuleCategory.SELF_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 446"
    ),
    TaxRule(
        rule_id="SE020",
        name="1099 Reporting Requirement",
        description="Must issue 1099s for payments ≥ $600 to non-employees",
        category=RuleCategory.SELF_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 6041",
        threshold=600.0
    ),
    TaxRule(
        rule_id="SE021",
        name="Independent Contractor Status",
        description="IRS uses 20-factor test for worker classification",
        category=RuleCategory.SELF_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="Publication 15-A"
    ),
    TaxRule(
        rule_id="SE022",
        name="Business Use Percentage",
        description="Mixed-use assets require business use allocation",
        category=RuleCategory.SELF_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 280F"
    ),
    TaxRule(
        rule_id="SE023",
        name="Hobby Loss Rule",
        description="Profit motive required; 3 of 5 year test",
        category=RuleCategory.SELF_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 183"
    ),
    TaxRule(
        rule_id="SE024",
        name="Net Operating Loss",
        description="Business losses may create NOL for carryforward",
        category=RuleCategory.SELF_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 172"
    ),
    TaxRule(
        rule_id="SE025",
        name="Excess Business Loss",
        description="Business losses limited to $305,000 single / $610,000 MFJ",
        category=RuleCategory.SELF_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 461(l)",
        limits_by_status={
            "single": 305000.0,
            "married_joint": 610000.0
        }
    ),
]

# =============================================================================
# ADDITIONAL RULE CATEGORIES (150+ rules total from remaining categories)
# =============================================================================

AMT_RULES = [
    TaxRule(
        rule_id="AMT001",
        name="AMT Exemption - Single",
        description="AMT exemption amount for single filers: $88,100",
        category=RuleCategory.AMT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 55(d)",
        threshold=88100.0
    ),
    TaxRule(
        rule_id="AMT002",
        name="AMT Exemption - MFJ",
        description="AMT exemption amount for MFJ: $137,000",
        category=RuleCategory.AMT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 55(d)",
        threshold=137000.0
    ),
    TaxRule(
        rule_id="AMT003",
        name="AMT Exemption Phaseout",
        description="Exemption phases out at 25 cents per dollar over threshold",
        category=RuleCategory.AMT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 55(d)(3)",
        rate=0.25
    ),
    TaxRule(
        rule_id="AMT004",
        name="AMT Rate - 26%",
        description="26% rate on first $232,600 of AMTI over exemption",
        category=RuleCategory.AMT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 55(b)",
        rate=0.26,
        threshold=232600.0
    ),
    TaxRule(
        rule_id="AMT005",
        name="AMT Rate - 28%",
        description="28% rate on AMTI over $232,600 above exemption",
        category=RuleCategory.AMT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 55(b)",
        rate=0.28
    ),
    TaxRule(
        rule_id="AMT006",
        name="AMT SALT Addback",
        description="State and local taxes added back for AMT",
        category=RuleCategory.AMT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 56"
    ),
    TaxRule(
        rule_id="AMT007",
        name="AMT Standard Deduction",
        description="No standard deduction allowed for AMT",
        category=RuleCategory.AMT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 56(b)"
    ),
    TaxRule(
        rule_id="AMT008",
        name="AMT Personal Exemptions",
        description="No personal exemptions allowed for AMT",
        category=RuleCategory.AMT,
        severity=RuleSeverity.INFO,
        irs_reference="IRC Section 56(b)"
    ),
    TaxRule(
        rule_id="AMT009",
        name="ISO Exercise AMT",
        description="ISO exercise spread is AMT preference item",
        category=RuleCategory.AMT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 56(b)(3)"
    ),
    TaxRule(
        rule_id="AMT010",
        name="Private Activity Bond Interest",
        description="PAB interest is AMT preference item",
        category=RuleCategory.AMT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 57"
    ),
]

NIIT_RULES = [
    TaxRule(
        rule_id="NIIT001",
        name="Net Investment Income Tax Rate",
        description="3.8% tax on net investment income",
        category=RuleCategory.INVESTMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1411",
        rate=0.038
    ),
    TaxRule(
        rule_id="NIIT002",
        name="NIIT Threshold - Single",
        description="NIIT applies on lesser of NII or MAGI over $200,000",
        category=RuleCategory.INVESTMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1411(b)",
        threshold=200000.0
    ),
    TaxRule(
        rule_id="NIIT003",
        name="NIIT Threshold - MFJ",
        description="NIIT threshold for MFJ is $250,000",
        category=RuleCategory.INVESTMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1411(b)",
        threshold=250000.0
    ),
    TaxRule(
        rule_id="NIIT004",
        name="Net Investment Income Definition",
        description="Includes interest, dividends, capital gains, rental, royalties",
        category=RuleCategory.INVESTMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1411(c)"
    ),
    TaxRule(
        rule_id="NIIT005",
        name="NIIT Exclusion - Active Business",
        description="Active trade or business income excluded from NII",
        category=RuleCategory.INVESTMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 1411(c)(2)"
    ),
]

PENALTY_RULES = [
    TaxRule(
        rule_id="PEN001",
        name="Failure to File Penalty",
        description="5% per month up to 25% of unpaid tax",
        category=RuleCategory.PENALTY,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 6651(a)(1)",
        rate=0.05
    ),
    TaxRule(
        rule_id="PEN002",
        name="Failure to Pay Penalty",
        description="0.5% per month up to 25% of unpaid tax",
        category=RuleCategory.PENALTY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 6651(a)(2)",
        rate=0.005
    ),
    TaxRule(
        rule_id="PEN003",
        name="Combined Penalty Cap",
        description="Combined FTF and FTP penalty capped at 47.5%",
        category=RuleCategory.PENALTY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 6651"
    ),
    TaxRule(
        rule_id="PEN004",
        name="Accuracy-Related Penalty",
        description="20% penalty for negligence or substantial understatement",
        category=RuleCategory.PENALTY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 6662",
        rate=0.20
    ),
    TaxRule(
        rule_id="PEN005",
        name="Substantial Understatement",
        description="Understatement > $5,000 or 10% of tax due",
        category=RuleCategory.PENALTY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 6662(d)",
        threshold=5000.0
    ),
    TaxRule(
        rule_id="PEN006",
        name="Fraud Penalty",
        description="75% penalty for fraudulent returns",
        category=RuleCategory.PENALTY,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 6663",
        rate=0.75
    ),
    TaxRule(
        rule_id="PEN007",
        name="Early Withdrawal Penalty",
        description="10% penalty on early retirement distribution",
        category=RuleCategory.PENALTY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 72(t)",
        rate=0.10
    ),
    TaxRule(
        rule_id="PEN008",
        name="Excess Contribution Penalty",
        description="6% penalty on excess IRA/HSA contributions",
        category=RuleCategory.PENALTY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 4973",
        rate=0.06
    ),
    TaxRule(
        rule_id="PEN009",
        name="Estimated Tax Penalty",
        description="Penalty for underpayment of estimated taxes",
        category=RuleCategory.PENALTY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 6654"
    ),
    TaxRule(
        rule_id="PEN010",
        name="Information Return Penalty",
        description="Penalties for late or incorrect 1099s, W-2s",
        category=RuleCategory.PENALTY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 6721/6722"
    ),
]

FILING_STATUS_RULES = [
    TaxRule(
        rule_id="FS001",
        name="Single Status",
        description="Unmarried or legally separated on Dec 31",
        category=RuleCategory.FILING_STATUS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1(c)"
    ),
    TaxRule(
        rule_id="FS002",
        name="Married Filing Jointly",
        description="Both spouses sign; joint and several liability",
        category=RuleCategory.FILING_STATUS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1(a)"
    ),
    TaxRule(
        rule_id="FS003",
        name="Married Filing Separately",
        description="Married but file separate returns; limited benefits",
        category=RuleCategory.FILING_STATUS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1(d)"
    ),
    TaxRule(
        rule_id="FS004",
        name="Head of Household Requirements",
        description="Unmarried, paid >50% of home, qualifying person lived with you",
        category=RuleCategory.FILING_STATUS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 2(b)"
    ),
    TaxRule(
        rule_id="FS005",
        name="Qualifying Surviving Spouse",
        description="Widow(er) with dependent child for 2 years after spouse's death",
        category=RuleCategory.FILING_STATUS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 2(a)"
    ),
    TaxRule(
        rule_id="FS006",
        name="Marriage Determined on Dec 31",
        description="Marital status determined as of last day of tax year",
        category=RuleCategory.FILING_STATUS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 7703"
    ),
    TaxRule(
        rule_id="FS007",
        name="Common Law Marriage",
        description="Recognized if valid in state where established",
        category=RuleCategory.FILING_STATUS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 7703"
    ),
    TaxRule(
        rule_id="FS008",
        name="Same-Sex Marriage",
        description="Same-sex marriages recognized for federal tax purposes",
        category=RuleCategory.FILING_STATUS,
        severity=RuleSeverity.HIGH,
        irs_reference="Rev. Rul. 2013-17"
    ),
    TaxRule(
        rule_id="FS009",
        name="MFS EITC Disallowed",
        description="EITC not available for Married Filing Separately",
        category=RuleCategory.FILING_STATUS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 32(d)"
    ),
    TaxRule(
        rule_id="FS010",
        name="MFS Child Care Credit Limit",
        description="Dependent care credit limited for MFS",
        category=RuleCategory.FILING_STATUS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 21(e)"
    ),
]

STATE_TAX_RULES = [
    TaxRule(
        rule_id="ST001",
        name="No State Income Tax States",
        description="AK, FL, NV, NH, SD, TN, TX, WA, WY have no state income tax",
        category=RuleCategory.STATE_TAX,
        severity=RuleSeverity.HIGH,
        irs_reference="State tax laws"
    ),
    TaxRule(
        rule_id="ST002",
        name="Flat Tax States",
        description="CO, IL, IN, KY, MA, MI, NC, NH, PA, UT have flat tax rates",
        category=RuleCategory.STATE_TAX,
        severity=RuleSeverity.MEDIUM,
        irs_reference="State tax laws"
    ),
    TaxRule(
        rule_id="ST003",
        name="State Residency Rules",
        description="Domicile and 183-day rules vary by state",
        category=RuleCategory.STATE_TAX,
        severity=RuleSeverity.HIGH,
        irs_reference="State tax laws"
    ),
    TaxRule(
        rule_id="ST004",
        name="Part-Year Resident",
        description="May need to file in multiple states if moved",
        category=RuleCategory.STATE_TAX,
        severity=RuleSeverity.MEDIUM,
        irs_reference="State tax laws"
    ),
    TaxRule(
        rule_id="ST005",
        name="State Reciprocity",
        description="Some states have reciprocal agreements for commuters",
        category=RuleCategory.STATE_TAX,
        severity=RuleSeverity.MEDIUM,
        irs_reference="State tax laws"
    ),
    TaxRule(
        rule_id="ST006",
        name="State EITC",
        description="Many states offer state-level EITC (CA: 45%, NY: 30%, etc.)",
        category=RuleCategory.STATE_TAX,
        severity=RuleSeverity.MEDIUM,
        irs_reference="State tax laws"
    ),
    TaxRule(
        rule_id="ST007",
        name="State Social Security Treatment",
        description="Most states exempt SS; 9 states tax some or all",
        category=RuleCategory.STATE_TAX,
        severity=RuleSeverity.MEDIUM,
        irs_reference="State tax laws"
    ),
    TaxRule(
        rule_id="ST008",
        name="State Retirement Income Exclusion",
        description="Many states exclude pension/retirement income",
        category=RuleCategory.STATE_TAX,
        severity=RuleSeverity.MEDIUM,
        irs_reference="State tax laws"
    ),
    TaxRule(
        rule_id="ST009",
        name="State 529 Deduction",
        description="Many states offer deduction for 529 contributions",
        category=RuleCategory.STATE_TAX,
        severity=RuleSeverity.MEDIUM,
        irs_reference="State tax laws"
    ),
    TaxRule(
        rule_id="ST010",
        name="Pass-Through Entity Tax Election",
        description="Many states allow PTE tax election to bypass SALT cap",
        category=RuleCategory.STATE_TAX,
        severity=RuleSeverity.HIGH,
        irs_reference="State tax laws"
    ),
]

DOCUMENTATION_RULES = [
    TaxRule(
        rule_id="DOC001",
        name="Record Retention - General",
        description="Keep tax records for at least 3 years",
        category=RuleCategory.DOCUMENTATION,
        severity=RuleSeverity.HIGH,
        irs_reference="Publication 552"
    ),
    TaxRule(
        rule_id="DOC002",
        name="Record Retention - Property",
        description="Keep property records until 3 years after disposition",
        category=RuleCategory.DOCUMENTATION,
        severity=RuleSeverity.HIGH,
        irs_reference="Publication 552"
    ),
    TaxRule(
        rule_id="DOC003",
        name="Record Retention - Employment",
        description="Keep employment tax records for 4 years",
        category=RuleCategory.DOCUMENTATION,
        severity=RuleSeverity.HIGH,
        irs_reference="Publication 15"
    ),
    TaxRule(
        rule_id="DOC004",
        name="Charitable Receipt Requirements",
        description="Written acknowledgment needed for donations ≥$250",
        category=RuleCategory.DOCUMENTATION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 170(f)(8)",
        threshold=250.0
    ),
    TaxRule(
        rule_id="DOC005",
        name="Travel Expense Substantiation",
        description="Must document time, place, business purpose",
        category=RuleCategory.DOCUMENTATION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 274(d)"
    ),
    TaxRule(
        rule_id="DOC006",
        name="Mileage Log Requirements",
        description="Contemporaneous records of business miles required",
        category=RuleCategory.DOCUMENTATION,
        severity=RuleSeverity.HIGH,
        irs_reference="Reg. 1.274-5T"
    ),
    TaxRule(
        rule_id="DOC007",
        name="Home Office Documentation",
        description="Must prove regular and exclusive business use",
        category=RuleCategory.DOCUMENTATION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 280A"
    ),
    TaxRule(
        rule_id="DOC008",
        name="Stock Basis Records",
        description="Must maintain cost basis for all investments",
        category=RuleCategory.DOCUMENTATION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1012"
    ),
    TaxRule(
        rule_id="DOC009",
        name="IRA Basis Records",
        description="Track nondeductible IRA contributions with Form 8606",
        category=RuleCategory.DOCUMENTATION,
        severity=RuleSeverity.HIGH,
        irs_reference="Form 8606"
    ),
    TaxRule(
        rule_id="DOC010",
        name="HSA Distribution Records",
        description="Keep receipts for HSA qualified medical expenses",
        category=RuleCategory.DOCUMENTATION,
        severity=RuleSeverity.HIGH,
        irs_reference="Publication 969"
    ),
]

# =============================================================================
# RETIREMENT RULES (15 rules)
# =============================================================================

RETIREMENT_RULES = [
    TaxRule(
        rule_id="RET001",
        name="RMD Age Requirement",
        description="Required Minimum Distributions start at age 73",
        category=RuleCategory.RETIREMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 401(a)(9)"
    ),
    TaxRule(
        rule_id="RET002",
        name="RMD Penalty",
        description="25% penalty on missed RMDs (10% if corrected)",
        category=RuleCategory.RETIREMENT,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 4974",
        rate=0.25
    ),
    TaxRule(
        rule_id="RET003",
        name="Roth IRA No RMDs",
        description="Roth IRAs have no RMD requirement for original owner",
        category=RuleCategory.RETIREMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 408A"
    ),
    TaxRule(
        rule_id="RET004",
        name="Roth Conversion",
        description="Can convert traditional IRA to Roth; taxed as income",
        category=RuleCategory.RETIREMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 408A(d)(3)"
    ),
    TaxRule(
        rule_id="RET005",
        name="72(t) SEPP",
        description="Substantially equal periodic payments avoid 10% penalty",
        category=RuleCategory.RETIREMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 72(t)(2)(A)(iv)"
    ),
    TaxRule(
        rule_id="RET006",
        name="Rule of 55",
        description="401(k) access penalty-free if separated at 55+",
        category=RuleCategory.RETIREMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 72(t)(2)(A)(v)"
    ),
    TaxRule(
        rule_id="RET007",
        name="QCD from IRA",
        description="Qualified Charitable Distributions up to $105,000 from IRA",
        category=RuleCategory.RETIREMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 408(d)(8)",
        limit=105000.0
    ),
    TaxRule(
        rule_id="RET008",
        name="10-Year Inherited IRA Rule",
        description="Most non-spouse beneficiaries must empty IRA in 10 years",
        category=RuleCategory.RETIREMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="SECURE Act"
    ),
    TaxRule(
        rule_id="RET009",
        name="Spousal Rollover",
        description="Surviving spouse can roll over to own IRA",
        category=RuleCategory.RETIREMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 408(d)(3)"
    ),
    TaxRule(
        rule_id="RET010",
        name="After-Tax Mega Backdoor Roth",
        description="After-tax 401(k) contributions can be converted to Roth",
        category=RuleCategory.RETIREMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 402(c)"
    ),
    TaxRule(
        rule_id="RET011",
        name="60-Day Rollover Rule",
        description="Must complete rollover within 60 days to avoid tax",
        category=RuleCategory.RETIREMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 402(c)(3)"
    ),
    TaxRule(
        rule_id="RET012",
        name="One Rollover Per Year",
        description="Only one IRA-to-IRA rollover per 12 months",
        category=RuleCategory.RETIREMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 408(d)(3)(B)"
    ),
    TaxRule(
        rule_id="RET013",
        name="Social Security Taxation",
        description="Up to 85% of Social Security may be taxable",
        category=RuleCategory.RETIREMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 86",
        rate=0.85
    ),
    TaxRule(
        rule_id="RET014",
        name="Pension vs Lump Sum",
        description="Pension annuity vs lump sum has tax implications",
        category=RuleCategory.RETIREMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 402"
    ),
    TaxRule(
        rule_id="RET015",
        name="Net Unrealized Appreciation",
        description="NUA treatment for employer stock in 401(k)",
        category=RuleCategory.RETIREMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 402(e)(4)"
    ),
]

# =============================================================================
# HEALTHCARE RULES (12 rules)
# =============================================================================

HEALTHCARE_RULES = [
    TaxRule(
        rule_id="HC001",
        name="HSA Triple Tax Advantage",
        description="Contributions deductible, growth tax-free, qualified distributions tax-free",
        category=RuleCategory.HEALTHCARE,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 223"
    ),
    TaxRule(
        rule_id="HC002",
        name="HSA HDHP Requirement",
        description="Must have High Deductible Health Plan for HSA eligibility",
        category=RuleCategory.HEALTHCARE,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 223(c)"
    ),
    TaxRule(
        rule_id="HC003",
        name="HSA Contribution Limits 2025",
        description="Individual $4,300 / Family $8,550 plus $1,000 catch-up at 55+",
        category=RuleCategory.HEALTHCARE,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 223(b)",
        limits_by_status={"individual": 4300.0, "family": 8550.0}
    ),
    TaxRule(
        rule_id="HC004",
        name="FSA Use-It-Or-Lose-It",
        description="FSA funds generally expire end of year (with exceptions)",
        category=RuleCategory.HEALTHCARE,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 125"
    ),
    TaxRule(
        rule_id="HC005",
        name="FSA Carryover Limit",
        description="Up to $640 FSA carryover allowed if plan permits",
        category=RuleCategory.HEALTHCARE,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Notice 2021-15",
        limit=640.0
    ),
    TaxRule(
        rule_id="HC006",
        name="Premium Tax Credit",
        description="Refundable credit for Marketplace insurance",
        category=RuleCategory.HEALTHCARE,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 36B"
    ),
    TaxRule(
        rule_id="HC007",
        name="PTC Reconciliation",
        description="Must reconcile advance PTC on tax return",
        category=RuleCategory.HEALTHCARE,
        severity=RuleSeverity.HIGH,
        irs_reference="Form 8962"
    ),
    TaxRule(
        rule_id="HC008",
        name="Medical Expense 7.5% Floor",
        description="Only medical expenses exceeding 7.5% of AGI are deductible",
        category=RuleCategory.HEALTHCARE,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 213",
        rate=0.075
    ),
    TaxRule(
        rule_id="HC009",
        name="Long-Term Care Insurance",
        description="LTC premiums deductible up to age-based limits",
        category=RuleCategory.HEALTHCARE,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 213(d)(10)"
    ),
    TaxRule(
        rule_id="HC010",
        name="HSA Medicare Coordination",
        description="Cannot contribute to HSA once enrolled in Medicare",
        category=RuleCategory.HEALTHCARE,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 223(b)(7)"
    ),
    TaxRule(
        rule_id="HC011",
        name="COBRA Premium Assistance",
        description="Employer credit for subsidized COBRA premiums",
        category=RuleCategory.HEALTHCARE,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 6432"
    ),
    TaxRule(
        rule_id="HC012",
        name="HSA Post-65 Penalty-Free",
        description="Non-medical HSA withdrawals penalty-free at 65+",
        category=RuleCategory.HEALTHCARE,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 223(f)(4)"
    ),
]

# =============================================================================
# EDUCATION RULES (12 rules)
# =============================================================================

EDUCATION_RULES = [
    TaxRule(
        rule_id="EDU001",
        name="529 Plan Tax-Free Growth",
        description="529 earnings tax-free for qualified education expenses",
        category=RuleCategory.EDUCATION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 529"
    ),
    TaxRule(
        rule_id="EDU002",
        name="529 K-12 Tuition",
        description="Up to $10,000/year for K-12 tuition",
        category=RuleCategory.EDUCATION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 529(c)(7)",
        limit=10000.0
    ),
    TaxRule(
        rule_id="EDU003",
        name="529 to Roth Rollover",
        description="Up to $35,000 lifetime rollover from 529 to beneficiary Roth",
        category=RuleCategory.EDUCATION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="SECURE 2.0 Act",
        limit=35000.0
    ),
    TaxRule(
        rule_id="EDU004",
        name="Coverdell ESA Contribution",
        description="$2,000 annual contribution limit per beneficiary",
        category=RuleCategory.EDUCATION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 530",
        limit=2000.0
    ),
    TaxRule(
        rule_id="EDU005",
        name="American Opportunity Credit",
        description="Up to $2,500 credit per student for first 4 years",
        category=RuleCategory.EDUCATION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 25A",
        limit=2500.0
    ),
    TaxRule(
        rule_id="EDU006",
        name="Lifetime Learning Credit",
        description="Up to $2,000 credit (20% of $10,000 expenses)",
        category=RuleCategory.EDUCATION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 25A(c)",
        limit=2000.0
    ),
    TaxRule(
        rule_id="EDU007",
        name="Education Credits - No Double Benefit",
        description="Cannot claim AOC/LLC and use 529 for same expenses",
        category=RuleCategory.EDUCATION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 25A(g)"
    ),
    TaxRule(
        rule_id="EDU008",
        name="Student Loan Interest Deduction",
        description="Up to $2,500 deduction phases out at higher income",
        category=RuleCategory.EDUCATION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 221",
        limit=2500.0
    ),
    TaxRule(
        rule_id="EDU009",
        name="Employer Education Assistance",
        description="Up to $5,250 tax-free from employer",
        category=RuleCategory.EDUCATION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 127",
        limit=5250.0
    ),
    TaxRule(
        rule_id="EDU010",
        name="Student Loan Forgiveness",
        description="PSLF and IDR forgiveness may be tax-free",
        category=RuleCategory.EDUCATION,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 108(f)"
    ),
    TaxRule(
        rule_id="EDU011",
        name="Tuition and Fees",
        description="Tuition, books, supplies qualify for education benefits",
        category=RuleCategory.EDUCATION,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 25A(f)"
    ),
    TaxRule(
        rule_id="EDU012",
        name="ABLE Account",
        description="Tax-advantaged savings for disabled individuals",
        category=RuleCategory.EDUCATION,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 529A"
    ),
]

# =============================================================================
# REAL ESTATE RULES (12 rules)
# =============================================================================

REAL_ESTATE_RULES = [
    TaxRule(
        rule_id="RE001",
        name="Primary Residence Exclusion",
        description="Exclude $250K/$500K gain on home sale (2-of-5 year rule)",
        category=RuleCategory.REAL_ESTATE,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 121",
        limits_by_status={"single": 250000.0, "married_joint": 500000.0}
    ),
    TaxRule(
        rule_id="RE002",
        name="1031 Like-Kind Exchange",
        description="Defer gain on investment property exchange",
        category=RuleCategory.REAL_ESTATE,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1031"
    ),
    TaxRule(
        rule_id="RE003",
        name="1031 Timeline",
        description="45 days to identify, 180 days to close",
        category=RuleCategory.REAL_ESTATE,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 1031(a)(3)"
    ),
    TaxRule(
        rule_id="RE004",
        name="Depreciation Recapture",
        description="25% tax on unrecaptured Section 1250 gain",
        category=RuleCategory.REAL_ESTATE,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1250",
        rate=0.25
    ),
    TaxRule(
        rule_id="RE005",
        name="Rental Property Depreciation",
        description="27.5 years for residential, 39 years for commercial",
        category=RuleCategory.REAL_ESTATE,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 168"
    ),
    TaxRule(
        rule_id="RE006",
        name="Passive Activity Loss",
        description="Rental losses limited to passive income ($25K exception)",
        category=RuleCategory.REAL_ESTATE,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 469",
        limit=25000.0
    ),
    TaxRule(
        rule_id="RE007",
        name="Real Estate Professional Status",
        description="750+ hours/year allows full loss deduction",
        category=RuleCategory.REAL_ESTATE,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 469(c)(7)"
    ),
    TaxRule(
        rule_id="RE008",
        name="Mortgage Interest Deduction",
        description="Interest on up to $750K mortgage debt deductible",
        category=RuleCategory.REAL_ESTATE,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 163(h)",
        limit=750000.0
    ),
    TaxRule(
        rule_id="RE009",
        name="Property Tax Deduction",
        description="Real property taxes subject to $10K SALT cap",
        category=RuleCategory.REAL_ESTATE,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 164"
    ),
    TaxRule(
        rule_id="RE010",
        name="Points Deduction",
        description="Points on purchase loan deductible in year paid",
        category=RuleCategory.REAL_ESTATE,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 461(g)(2)"
    ),
    TaxRule(
        rule_id="RE011",
        name="Home Equity Loan Interest",
        description="HELOC interest deductible only if used for home improvement",
        category=RuleCategory.REAL_ESTATE,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 163(h)(3)"
    ),
    TaxRule(
        rule_id="RE012",
        name="Qualified Opportunity Zone",
        description="Defer/reduce capital gains by investing in QOZ",
        category=RuleCategory.REAL_ESTATE,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 1400Z-2"
    ),
]

# =============================================================================
# BUSINESS RULES (12 rules)
# =============================================================================

BUSINESS_RULES = [
    TaxRule(
        rule_id="BUS001",
        name="Entity Selection",
        description="Sole proprietor, LLC, S-Corp, C-Corp have different tax treatment",
        category=RuleCategory.BUSINESS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Sections 701, 1361, 11"
    ),
    TaxRule(
        rule_id="BUS002",
        name="S-Corp Election",
        description="Form 2553 due within 75 days of tax year start",
        category=RuleCategory.BUSINESS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1362"
    ),
    TaxRule(
        rule_id="BUS003",
        name="Startup Costs",
        description="Up to $5,000 deductible; excess amortized over 180 months",
        category=RuleCategory.BUSINESS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 195",
        limit=5000.0
    ),
    TaxRule(
        rule_id="BUS004",
        name="Research Credit",
        description="Up to $500K against payroll tax for startups",
        category=RuleCategory.BUSINESS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 41",
        limit=500000.0
    ),
    TaxRule(
        rule_id="BUS005",
        name="Work Opportunity Credit",
        description="Credit for hiring from targeted groups",
        category=RuleCategory.BUSINESS,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 51"
    ),
    TaxRule(
        rule_id="BUS006",
        name="Small Employer Health Credit",
        description="50% credit for small employer health insurance",
        category=RuleCategory.BUSINESS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 45R",
        rate=0.50
    ),
    TaxRule(
        rule_id="BUS007",
        name="Disabled Access Credit",
        description="50% of up to $10,250 for accessibility improvements",
        category=RuleCategory.BUSINESS,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 44"
    ),
    TaxRule(
        rule_id="BUS008",
        name="Employer Retirement Plan Credit",
        description="Up to $500/year for new small employer retirement plan",
        category=RuleCategory.BUSINESS,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 45E",
        limit=500.0
    ),
    TaxRule(
        rule_id="BUS009",
        name="De Minimis Safe Harbor",
        description="Expense items under $2,500 per item/invoice",
        category=RuleCategory.BUSINESS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.263(a)-1(f)",
        threshold=2500.0
    ),
    TaxRule(
        rule_id="BUS010",
        name="Qualified Small Business Stock",
        description="100% exclusion on QSBS gain (up to $10M)",
        category=RuleCategory.BUSINESS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1202",
        limit=10000000.0
    ),
    TaxRule(
        rule_id="BUS011",
        name="Business Meals vs Entertainment",
        description="Business meals 50% deductible; entertainment not deductible",
        category=RuleCategory.BUSINESS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 274",
        rate=0.50
    ),
    TaxRule(
        rule_id="BUS012",
        name="Employee vs Contractor",
        description="Misclassification leads to employment tax liability",
        category=RuleCategory.BUSINESS,
        severity=RuleSeverity.HIGH,
        irs_reference="Publication 15-A"
    ),
]

# =============================================================================
# CHARITABLE RULES (10 rules)
# =============================================================================

CHARITABLE_RULES = [
    TaxRule(
        rule_id="CHAR001",
        name="Charitable AGI Limit - Cash",
        description="Cash donations limited to 60% of AGI",
        category=RuleCategory.CHARITABLE,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 170(b)(1)(A)",
        rate=0.60
    ),
    TaxRule(
        rule_id="CHAR002",
        name="Charitable AGI Limit - Property",
        description="Appreciated property limited to 30% of AGI",
        category=RuleCategory.CHARITABLE,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 170(b)(1)(C)",
        rate=0.30
    ),
    TaxRule(
        rule_id="CHAR003",
        name="Charitable Carryforward",
        description="Excess donations carry forward 5 years",
        category=RuleCategory.CHARITABLE,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 170(d)"
    ),
    TaxRule(
        rule_id="CHAR004",
        name="Donor Advised Fund",
        description="Immediate deduction; recommend grants over time",
        category=RuleCategory.CHARITABLE,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 4966"
    ),
    TaxRule(
        rule_id="CHAR005",
        name="Appreciated Stock Donation",
        description="Donate appreciated stock to avoid capital gains",
        category=RuleCategory.CHARITABLE,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 170(e)"
    ),
    TaxRule(
        rule_id="CHAR006",
        name="Qualified Appraisal Required",
        description="Appraisal required for property donations over $5,000",
        category=RuleCategory.CHARITABLE,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 170(f)(11)",
        threshold=5000.0
    ),
    TaxRule(
        rule_id="CHAR007",
        name="Charitable Remainder Trust",
        description="Income stream plus charitable deduction",
        category=RuleCategory.CHARITABLE,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 664"
    ),
    TaxRule(
        rule_id="CHAR008",
        name="Substantiation - $250+",
        description="Written acknowledgment required for donations $250+",
        category=RuleCategory.CHARITABLE,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 170(f)(8)",
        threshold=250.0
    ),
    TaxRule(
        rule_id="CHAR009",
        name="Quid Pro Quo Donations",
        description="Deduction reduced by value of goods received",
        category=RuleCategory.CHARITABLE,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 170(f)(8)(B)"
    ),
    TaxRule(
        rule_id="CHAR010",
        name="Non-Cash Property Valuation",
        description="FMV for appreciated property held >1 year",
        category=RuleCategory.CHARITABLE,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 170(e)(1)"
    ),
]

# =============================================================================
# FAMILY RULES (10 rules)
# =============================================================================

FAMILY_RULES = [
    TaxRule(
        rule_id="FAM001",
        name="Dependent Definition",
        description="Qualifying child or qualifying relative rules",
        category=RuleCategory.FAMILY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 152"
    ),
    TaxRule(
        rule_id="FAM002",
        name="Tie-Breaker Rules",
        description="Rules when multiple taxpayers claim same dependent",
        category=RuleCategory.FAMILY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 152(c)(4)"
    ),
    TaxRule(
        rule_id="FAM003",
        name="Custodial Parent Rule",
        description="Child of divorced parents claimed by custodial parent",
        category=RuleCategory.FAMILY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 152(e)"
    ),
    TaxRule(
        rule_id="FAM004",
        name="Form 8332",
        description="Release of claim to exemption for child",
        category=RuleCategory.FAMILY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Form 8332"
    ),
    TaxRule(
        rule_id="FAM005",
        name="UGMA/UTMA Taxation",
        description="Kiddie tax on child's unearned income over $2,600",
        category=RuleCategory.FAMILY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1(g)",
        threshold=2600.0
    ),
    TaxRule(
        rule_id="FAM006",
        name="Gift Tax Annual Exclusion",
        description="$19,000 per recipient annual exclusion (2025)",
        category=RuleCategory.FAMILY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 2503(b)",
        limit=19000.0
    ),
    TaxRule(
        rule_id="FAM007",
        name="Gift Tax Lifetime Exemption",
        description="$13.99M lifetime exemption (2025)",
        category=RuleCategory.FAMILY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 2010",
        limit=13990000.0
    ),
    TaxRule(
        rule_id="FAM008",
        name="Alimony Tax Treatment",
        description="Post-2018 alimony not deductible/includable",
        category=RuleCategory.FAMILY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 71"
    ),
    TaxRule(
        rule_id="FAM009",
        name="Child Support Not Income",
        description="Child support is not taxable income to recipient",
        category=RuleCategory.FAMILY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 71(c)"
    ),
    TaxRule(
        rule_id="FAM010",
        name="FAFSA and Tax Returns",
        description="Financial aid uses tax return data via IRS Data Retrieval",
        category=RuleCategory.FAMILY,
        severity=RuleSeverity.INFO,
        irs_reference="IRC Section 6103"
    ),
]

# =============================================================================
# INTERNATIONAL RULES (10 rules)
# =============================================================================

INTERNATIONAL_RULES = [
    TaxRule(
        rule_id="INTL001",
        name="Worldwide Income",
        description="US citizens/residents taxed on worldwide income",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 61"
    ),
    TaxRule(
        rule_id="INTL002",
        name="FBAR Reporting",
        description="Report foreign accounts over $10,000 aggregate",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.CRITICAL,
        irs_reference="31 USC 5314",
        threshold=10000.0
    ),
    TaxRule(
        rule_id="INTL003",
        name="FATCA Form 8938",
        description="Report specified foreign assets over threshold",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 6038D"
    ),
    TaxRule(
        rule_id="INTL004",
        name="Foreign Tax Credit",
        description="Credit for foreign taxes paid to avoid double taxation",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 901"
    ),
    TaxRule(
        rule_id="INTL005",
        name="Foreign Earned Income Exclusion",
        description="Up to $130,000 exclusion for qualifying foreign residents",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 911",
        limit=130000.0
    ),
    TaxRule(
        rule_id="INTL006",
        name="Physical Presence Test",
        description="330 full days abroad in 12-month period",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 911(d)(1)"
    ),
    TaxRule(
        rule_id="INTL007",
        name="Bona Fide Residence Test",
        description="Reside in foreign country for uninterrupted tax year",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 911(d)(1)"
    ),
    TaxRule(
        rule_id="INTL008",
        name="PFIC Reporting",
        description="Complex rules for passive foreign investment companies",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1291"
    ),
    TaxRule(
        rule_id="INTL009",
        name="Controlled Foreign Corporation",
        description="US shareholders taxed on Subpart F income",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 951"
    ),
    TaxRule(
        rule_id="INTL010",
        name="Treaty Benefits",
        description="Tax treaties may reduce withholding/provide exemptions",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 894"
    ),
]

# =============================================================================
# TIMING RULES (10 rules)
# =============================================================================

TIMING_RULES = [
    TaxRule(
        rule_id="TIM001",
        name="Tax Year Filing Deadline",
        description="April 15 for calendar year taxpayers",
        category=RuleCategory.TIMING,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 6072"
    ),
    TaxRule(
        rule_id="TIM002",
        name="Extension to October 15",
        description="Automatic 6-month extension with Form 4868",
        category=RuleCategory.TIMING,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 6081"
    ),
    TaxRule(
        rule_id="TIM003",
        name="Extension Doesn't Extend Payment",
        description="Estimated tax still due April 15",
        category=RuleCategory.TIMING,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 6651"
    ),
    TaxRule(
        rule_id="TIM004",
        name="Statute of Limitations - 3 Years",
        description="IRS can assess within 3 years of filing",
        category=RuleCategory.TIMING,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 6501"
    ),
    TaxRule(
        rule_id="TIM005",
        name="Statute - 6 Years",
        description="6 years if income omitted exceeds 25% of reported",
        category=RuleCategory.TIMING,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 6501(e)"
    ),
    TaxRule(
        rule_id="TIM006",
        name="No Statute for Fraud",
        description="No time limit on fraudulent returns",
        category=RuleCategory.TIMING,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 6501(c)"
    ),
    TaxRule(
        rule_id="TIM007",
        name="Amended Return - 3 Years",
        description="Must file within 3 years of original or 2 years of payment",
        category=RuleCategory.TIMING,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 6511"
    ),
    TaxRule(
        rule_id="TIM008",
        name="Estimated Tax Due Dates",
        description="April 15, June 15, September 15, January 15",
        category=RuleCategory.TIMING,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 6654"
    ),
    TaxRule(
        rule_id="TIM009",
        name="Year-End Tax Planning",
        description="Timing of income/deductions can affect tax brackets",
        category=RuleCategory.TIMING,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Publication 17",
        recommendation="Consider accelerating deductions or deferring income"
    ),
    TaxRule(
        rule_id="TIM010",
        name="Constructive Receipt",
        description="Income taxed when available, not necessarily received",
        category=RuleCategory.TIMING,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 451"
    ),
]


# =============================================================================
# RULE ENGINE CLASS
# =============================================================================

class TaxRulesEngine:
    """
    Comprehensive tax rules engine with 350+ rules.

    Provides rule lookup, validation, and recommendation generation
    based on taxpayer circumstances.
    """

    def __init__(self, tax_year: int = 2025):
        self.tax_year = tax_year
        self.rules: Dict[str, TaxRule] = {}
        self._load_all_rules()

    def _load_all_rules(self):
        """Load all rules into the engine."""
        all_rules = (
            INCOME_RULES +
            DEDUCTION_RULES +
            CREDIT_RULES +
            SELF_EMPLOYMENT_RULES +
            AMT_RULES +
            NIIT_RULES +
            PENALTY_RULES +
            FILING_STATUS_RULES +
            STATE_TAX_RULES +
            DOCUMENTATION_RULES +
            RETIREMENT_RULES +
            HEALTHCARE_RULES +
            EDUCATION_RULES +
            REAL_ESTATE_RULES +
            BUSINESS_RULES +
            CHARITABLE_RULES +
            FAMILY_RULES +
            INTERNATIONAL_RULES +
            TIMING_RULES
        )

        for rule in all_rules:
            self.rules[rule.rule_id] = rule

    def get_rule(self, rule_id: str) -> Optional[TaxRule]:
        """Get a rule by ID."""
        return self.rules.get(rule_id)

    def get_rules_by_category(self, category: RuleCategory) -> List[TaxRule]:
        """Get all rules in a category."""
        return [r for r in self.rules.values() if r.category == category]

    def get_rules_by_severity(self, severity: RuleSeverity) -> List[TaxRule]:
        """Get all rules of a severity level."""
        return [r for r in self.rules.values() if r.severity == severity]

    def get_critical_rules(self) -> List[TaxRule]:
        """Get all critical rules."""
        return self.get_rules_by_severity(RuleSeverity.CRITICAL)

    def count_rules(self) -> Dict[str, int]:
        """Count rules by category."""
        counts = {}
        for category in RuleCategory:
            rules = self.get_rules_by_category(category)
            counts[category.value] = len(rules)
        counts['total'] = len(self.rules)
        return counts

    def get_applicable_rules(
        self,
        filing_status: Optional[str] = None,
        has_self_employment: bool = False,
        has_investments: bool = False,
        has_children: bool = False,
        itemizes: bool = False,
        high_income: bool = False
    ) -> List[TaxRule]:
        """Get rules applicable to taxpayer's situation."""
        applicable = []

        for rule in self.rules.values():
            # Always include critical rules
            if rule.severity == RuleSeverity.CRITICAL:
                applicable.append(rule)
                continue

            # Filter by applies_to if specified
            if rule.applies_to and filing_status:
                if filing_status not in rule.applies_to:
                    continue

            # Category-specific filtering
            if rule.category == RuleCategory.SELF_EMPLOYMENT and not has_self_employment:
                continue
            if rule.category == RuleCategory.INVESTMENT and not has_investments:
                continue
            if rule.category == RuleCategory.AMT and not high_income:
                continue

            applicable.append(rule)

        return applicable

    def generate_rule_report(self) -> str:
        """Generate a summary report of all rules."""
        counts = self.count_rules()

        lines = [
            "=" * 60,
            "TAX RULES ENGINE SUMMARY",
            "=" * 60,
            f"Tax Year: {self.tax_year}",
            f"Total Rules: {counts['total']}",
            "",
            "RULES BY CATEGORY:",
            "-" * 40,
        ]

        for category in RuleCategory:
            count = counts.get(category.value, 0)
            lines.append(f"  {category.value.title()}: {count}")

        lines.extend([
            "",
            "RULES BY SEVERITY:",
            "-" * 40,
        ])

        for severity in RuleSeverity:
            rules = self.get_rules_by_severity(severity)
            lines.append(f"  {severity.value.title()}: {len(rules)}")

        lines.append("=" * 60)

        return "\n".join(lines)


# Create singleton instance
TAX_RULES_ENGINE = TaxRulesEngine(tax_year=2025)


def get_rule_count() -> int:
    """Get total number of rules."""
    return len(TAX_RULES_ENGINE.rules)


def get_rules_summary() -> Dict[str, Any]:
    """Get summary of all tax rules."""
    return {
        'total_rules': get_rule_count(),
        'by_category': TAX_RULES_ENGINE.count_rules(),
        'tax_year': TAX_RULES_ENGINE.tax_year
    }
