"""Interview Flow.

Defines the complete tax interview flow with all questions organized
into logical groups that adapt based on user responses.

Persistence Safety: State is persisted to database via OnboardingPersistence
to prevent data loss on restart (Prompt 1 compliance).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from enum import Enum
from datetime import datetime
import logging

from onboarding.questionnaire_engine import (
    QuestionnaireEngine,
    Question,
    QuestionGroup,
    QuestionType,
    ValidationRule,
    Choice,
)

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

logger = logging.getLogger(__name__)


class InterviewStage(Enum):
    """Stages of the tax interview."""
    WELCOME = "welcome"
    PERSONAL_INFO = "personal_info"
    FILING_STATUS = "filing_status"
    DEPENDENTS = "dependents"
    INCOME = "income"
    INCOME_W2 = "income_w2"
    INCOME_1099 = "income_1099"
    INCOME_BUSINESS = "income_business"
    INCOME_INVESTMENTS = "income_investments"
    INCOME_RETIREMENT = "income_retirement"
    INCOME_OTHER = "income_other"
    DEDUCTIONS = "deductions"
    DEDUCTIONS_MORTGAGE = "deductions_mortgage"
    DEDUCTIONS_TAXES = "deductions_taxes"
    DEDUCTIONS_CHARITY = "deductions_charity"
    DEDUCTIONS_MEDICAL = "deductions_medical"
    CREDITS = "credits"
    CREDITS_EDUCATION = "credits_education"
    CREDITS_CHILD = "credits_child"
    CREDITS_ENERGY = "credits_energy"
    HEALTHCARE = "healthcare"
    STATE = "state"
    REVIEW = "review"
    COMPLETE = "complete"


@dataclass
class InterviewState:
    """Current state of the interview."""
    current_stage: InterviewStage = InterviewStage.WELCOME
    started_at: Optional[str] = None
    last_activity: Optional[str] = None
    is_complete: bool = False
    collected_data: Dict[str, Any] = field(default_factory=dict)
    detected_forms: List[str] = field(default_factory=list)
    estimated_refund: Optional[float] = None
    progress_percentage: float = 0.0


class InterviewFlow:
    """
    Manages the complete tax interview flow.

    This class orchestrates the interview process, determining which
    questions to ask based on the taxpayer's situation and previous
    answers. It provides a personalized, adaptive interview experience.

    Persistence: When session_id is provided, state is automatically
    persisted to database and restored on initialization.
    """

    def __init__(self, session_id: Optional[str] = None):
        """
        Initialize the interview flow.

        Args:
            session_id: Optional session ID for persistence. If provided,
                       state will be auto-saved and restored from database.
        """
        self._session_id = session_id
        self._persistence = None
        self._engine = QuestionnaireEngine()
        self._state = InterviewState()
        self._setup_questions()

        # Load persisted state if session_id provided
        if session_id:
            self._load_persisted_state()

    def _setup_questions(self) -> None:
        """Set up all interview question groups."""
        self._setup_personal_info()
        self._setup_filing_status()
        self._setup_dependents()
        self._setup_income_overview()
        self._setup_w2_income()
        self._setup_1099_income()
        self._setup_business_income()
        self._setup_investment_income()
        self._setup_retirement_income()
        self._setup_other_income()
        self._setup_deductions_overview()
        self._setup_mortgage_deductions()
        self._setup_tax_deductions()
        self._setup_charity_deductions()
        self._setup_medical_deductions()
        self._setup_credits_overview()
        self._setup_education_credits()
        self._setup_child_credits()
        self._setup_energy_credits()
        self._setup_healthcare()
        self._setup_state_info()

    def _setup_personal_info(self) -> None:
        """Set up personal information questions."""
        group = QuestionGroup(
            id="personal_info",
            title="Personal Information",
            description="Let's start with some basic information about you.",
            icon="user",
            order=1,
            estimated_time="2 minutes",
            questions=[
                Question(
                    id="first_name",
                    text="What is your first name?",
                    question_type=QuestionType.TEXT,
                    help_text="Enter your legal first name as it appears on your Social Security card",
                    placeholder="First name",
                    data_path="taxpayer.first_name",
                    max_length=50,
                ),
                Question(
                    id="middle_name",
                    text="What is your middle name or initial?",
                    question_type=QuestionType.TEXT,
                    required=False,
                    placeholder="Middle name (optional)",
                    data_path="taxpayer.middle_name",
                    max_length=50,
                ),
                Question(
                    id="last_name",
                    text="What is your last name?",
                    question_type=QuestionType.TEXT,
                    placeholder="Last name",
                    data_path="taxpayer.last_name",
                    max_length=50,
                ),
                Question(
                    id="ssn",
                    text="What is your Social Security Number?",
                    question_type=QuestionType.SSN,
                    help_text="Your SSN is required for tax filing. It will be encrypted and protected.",
                    placeholder="XXX-XX-XXXX",
                    data_path="taxpayer.ssn",
                ),
                Question(
                    id="birth_date",
                    text="What is your date of birth?",
                    question_type=QuestionType.DATE,
                    help_text="This helps determine age-related credits and deductions",
                    placeholder="MM/DD/YYYY",
                    data_path="taxpayer.birth_date",
                    validation_rules=[ValidationRule.PAST_DATE],
                ),
                Question(
                    id="occupation",
                    text="What is your occupation?",
                    question_type=QuestionType.TEXT,
                    required=False,
                    placeholder="e.g., Software Engineer, Teacher, Accountant",
                    data_path="taxpayer.occupation",
                ),
                Question(
                    id="phone",
                    text="What is your phone number?",
                    question_type=QuestionType.PHONE,
                    placeholder="(XXX) XXX-XXXX",
                    data_path="taxpayer.phone",
                ),
                Question(
                    id="email",
                    text="What is your email address?",
                    question_type=QuestionType.EMAIL,
                    help_text="We'll use this to send you important tax documents and updates",
                    placeholder="you@example.com",
                    data_path="taxpayer.email",
                ),
            ],
        )
        self._engine.add_group(group)

    def _setup_filing_status(self) -> None:
        """Set up filing status questions."""
        group = QuestionGroup(
            id="filing_status",
            title="Filing Status",
            description="Your filing status affects your tax rates and deductions.",
            icon="clipboard",
            order=2,
            estimated_time="1 minute",
            questions=[
                Question(
                    id="marital_status",
                    text="What was your marital status on December 31, 2025?",
                    question_type=QuestionType.SINGLE_CHOICE,
                    help_text="Your status on the last day of the year determines your filing options",
                    data_path="taxpayer.marital_status",
                    choices=[
                        Choice(
                            value="single",
                            label="Single",
                            description="Never married, legally separated, or divorced",
                        ),
                        Choice(
                            value="married",
                            label="Married",
                            description="Legally married as of December 31",
                            triggers_followup="spouse_info",
                        ),
                        Choice(
                            value="widowed",
                            label="Widowed",
                            description="Spouse passed away during or before 2025",
                            triggers_followup="widow_questions",
                        ),
                    ],
                ),
                Question(
                    id="filing_status",
                    text="How would you like to file?",
                    question_type=QuestionType.SINGLE_CHOICE,
                    data_path="taxpayer.filing_status",
                    show_if={"question_id": "marital_status", "equals": "married"},
                    choices=[
                        Choice(
                            value="married_joint",
                            label="Married Filing Jointly",
                            description="Combined return with spouse - usually best option",
                        ),
                        Choice(
                            value="married_separate",
                            label="Married Filing Separately",
                            description="Separate returns - may benefit in certain situations",
                        ),
                    ],
                ),
                Question(
                    id="lived_with_spouse",
                    text="Did you live with your spouse during any part of 2025?",
                    question_type=QuestionType.BOOLEAN,
                    show_if={"question_id": "marital_status", "equals": "married"},
                ),
                Question(
                    id="qualify_hoh",
                    text="Did you pay more than half the cost of keeping up a home for a qualifying person?",
                    question_type=QuestionType.BOOLEAN,
                    show_if={"question_id": "marital_status", "equals": "single"},
                    help_text="Head of Household status provides lower tax rates if you qualify",
                ),
                Question(
                    id="spouse_death_year",
                    text="What year did your spouse pass away?",
                    question_type=QuestionType.SINGLE_CHOICE,
                    show_if={"question_id": "marital_status", "equals": "widowed"},
                    choices=[
                        Choice(value="2025", label="2025"),
                        Choice(value="2024", label="2024"),
                        Choice(value="2023", label="2023"),
                        Choice(value="earlier", label="Before 2023"),
                    ],
                ),
            ],
        )
        self._engine.add_group(group)

    def _setup_dependents(self) -> None:
        """Set up dependent questions."""
        group = QuestionGroup(
            id="dependents",
            title="Dependents",
            description="Tell us about anyone you support financially.",
            icon="users",
            order=3,
            estimated_time="3 minutes",
            questions=[
                Question(
                    id="has_dependents",
                    text="Did you support any dependents in 2025?",
                    question_type=QuestionType.BOOLEAN,
                    help_text="Dependents include children, relatives, or others you financially support",
                ),
                Question(
                    id="num_children",
                    text="How many children under 17 do you claim as dependents?",
                    question_type=QuestionType.NUMBER,
                    show_if={"question_id": "has_dependents", "equals": True},
                    help_text="Children under 17 may qualify for the Child Tax Credit",
                    min_value=0,
                    max_value=20,
                    placeholder="0",
                    data_path="dependents.num_children_under_17",
                ),
                Question(
                    id="num_other_dependents",
                    text="How many other dependents (17 or older) do you claim?",
                    question_type=QuestionType.NUMBER,
                    show_if={"question_id": "has_dependents", "equals": True},
                    help_text="This includes adult children, parents, or other qualifying relatives",
                    min_value=0,
                    max_value=20,
                    placeholder="0",
                    data_path="dependents.num_other_dependents",
                ),
                Question(
                    id="child_care_expenses",
                    text="Did you pay for child care so you could work?",
                    question_type=QuestionType.BOOLEAN,
                    show_if={"question_id": "num_children", "answered": True},
                ),
                Question(
                    id="child_care_amount",
                    text="How much did you pay for child care in 2025?",
                    question_type=QuestionType.CURRENCY,
                    show_if={"question_id": "child_care_expenses", "equals": True},
                    prefix="$",
                    placeholder="0.00",
                    data_path="deductions.dependent_care_expenses",
                ),
            ],
        )
        self._engine.add_group(group)

    def _setup_income_overview(self) -> None:
        """Set up income overview questions."""
        group = QuestionGroup(
            id="income_overview",
            title="Income Overview",
            description="Let's understand your income sources for 2025.",
            icon="dollar-sign",
            order=4,
            estimated_time="1 minute",
            questions=[
                Question(
                    id="income_types",
                    text="What types of income did you receive in 2025?",
                    question_type=QuestionType.MULTI_CHOICE,
                    help_text="Select all that apply",
                    choices=[
                        Choice(
                            value="w2",
                            label="W-2 Wages",
                            description="Salary, wages, or tips from an employer",
                            triggers_followup="income_w2",
                        ),
                        Choice(
                            value="1099_nec",
                            label="1099-NEC/1099-MISC",
                            description="Freelance, contract, or gig work income",
                            triggers_followup="income_1099",
                        ),
                        Choice(
                            value="business",
                            label="Business Income",
                            description="Self-employment or small business income",
                            triggers_followup="income_business",
                        ),
                        Choice(
                            value="investments",
                            label="Investment Income",
                            description="Stocks, bonds, dividends, capital gains",
                            triggers_followup="income_investments",
                        ),
                        Choice(
                            value="retirement",
                            label="Retirement Income",
                            description="Pension, IRA, 401(k) distributions, Social Security",
                            triggers_followup="income_retirement",
                        ),
                        Choice(
                            value="rental",
                            label="Rental Income",
                            description="Income from rental properties",
                        ),
                        Choice(
                            value="unemployment",
                            label="Unemployment",
                            description="Unemployment compensation",
                        ),
                        Choice(
                            value="other",
                            label="Other Income",
                            description="Gambling, prizes, alimony, etc.",
                            triggers_followup="income_other",
                        ),
                    ],
                ),
            ],
        )
        self._engine.add_group(group)

    def _setup_w2_income(self) -> None:
        """Set up W-2 income questions."""
        group = QuestionGroup(
            id="income_w2",
            title="W-2 Income",
            description="Enter your W-2 wage information.",
            icon="briefcase",
            order=5,
            estimated_time="3 minutes",
            show_if={"question_id": "income_types", "contains": "w2"},
            questions=[
                Question(
                    id="num_w2s",
                    text="How many W-2 forms do you have?",
                    question_type=QuestionType.NUMBER,
                    min_value=1,
                    max_value=10,
                    placeholder="1",
                ),
                Question(
                    id="w2_employer_1",
                    text="Employer name (W-2 #1)",
                    question_type=QuestionType.TEXT,
                    placeholder="Company name",
                    irs_form="W-2",
                    irs_line="c",
                ),
                Question(
                    id="w2_wages_1",
                    text="Wages, tips, other compensation (Box 1)",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    data_path="income.w2_wages",
                    irs_form="W-2",
                    irs_line="1",
                ),
                Question(
                    id="w2_federal_withheld_1",
                    text="Federal income tax withheld (Box 2)",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    data_path="income.federal_withholding",
                    irs_form="W-2",
                    irs_line="2",
                ),
                Question(
                    id="w2_ss_wages_1",
                    text="Social Security wages (Box 3)",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    irs_form="W-2",
                    irs_line="3",
                ),
                Question(
                    id="w2_ss_withheld_1",
                    text="Social Security tax withheld (Box 4)",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    irs_form="W-2",
                    irs_line="4",
                ),
                Question(
                    id="w2_medicare_wages_1",
                    text="Medicare wages (Box 5)",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    irs_form="W-2",
                    irs_line="5",
                ),
                Question(
                    id="w2_state_wages_1",
                    text="State wages (Box 16)",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    required=False,
                    data_path="income.state_wages",
                    irs_form="W-2",
                    irs_line="16",
                ),
                Question(
                    id="w2_state_withheld_1",
                    text="State income tax withheld (Box 17)",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    required=False,
                    data_path="income.state_withholding",
                    irs_form="W-2",
                    irs_line="17",
                ),
                Question(
                    id="w2_401k_1",
                    text="Did you contribute to a 401(k) or similar retirement plan?",
                    question_type=QuestionType.BOOLEAN,
                    help_text="Look for code D, E, F, or S in Box 12",
                ),
                Question(
                    id="w2_401k_amount_1",
                    text="Total 401(k)/403(b) contributions (Box 12, codes D, E, F, or S)",
                    question_type=QuestionType.CURRENCY,
                    show_if={"question_id": "w2_401k_1", "equals": True},
                    prefix="$",
                    placeholder="0.00",
                    data_path="income.retirement_contributions_401k",
                ),
            ],
        )
        self._engine.add_group(group)

    def _setup_1099_income(self) -> None:
        """Set up 1099 income questions."""
        group = QuestionGroup(
            id="income_1099",
            title="1099 Income",
            description="Enter your freelance, contract, or gig income.",
            icon="file-text",
            order=6,
            estimated_time="3 minutes",
            show_if={"question_id": "income_types", "contains": "1099_nec"},
            questions=[
                Question(
                    id="num_1099s",
                    text="How many 1099-NEC or 1099-MISC forms do you have?",
                    question_type=QuestionType.NUMBER,
                    min_value=1,
                    max_value=20,
                    placeholder="1",
                ),
                Question(
                    id="1099_payer_1",
                    text="Payer name (1099 #1)",
                    question_type=QuestionType.TEXT,
                    placeholder="Company or client name",
                ),
                Question(
                    id="1099_amount_1",
                    text="Nonemployee compensation amount (Box 1)",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    irs_form="1099-NEC",
                    irs_line="1",
                ),
                Question(
                    id="1099_federal_withheld_1",
                    text="Federal income tax withheld (Box 4)",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    required=False,
                    irs_form="1099-NEC",
                    irs_line="4",
                ),
            ],
        )
        self._engine.add_group(group)

    def _setup_business_income(self) -> None:
        """Set up business income questions."""
        group = QuestionGroup(
            id="income_business",
            title="Business Income",
            description="Tell us about your self-employment or business income.",
            icon="store",
            order=7,
            estimated_time="5 minutes",
            show_if={"question_id": "income_types", "contains": "business"},
            questions=[
                Question(
                    id="business_name",
                    text="What is your business name?",
                    question_type=QuestionType.TEXT,
                    placeholder="Business name or 'Self'",
                    data_path="income.business_name",
                ),
                Question(
                    id="business_type",
                    text="What type of business do you have?",
                    question_type=QuestionType.SINGLE_CHOICE,
                    choices=[
                        Choice(value="sole_prop", label="Sole Proprietorship"),
                        Choice(value="single_llc", label="Single-Member LLC"),
                        Choice(value="partnership", label="Partnership"),
                        Choice(value="s_corp", label="S Corporation"),
                        Choice(value="c_corp", label="C Corporation"),
                    ],
                ),
                Question(
                    id="business_gross_income",
                    text="What was your total business income (gross receipts)?",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    data_path="income.self_employment_income",
                    irs_form="Schedule C",
                    irs_line="1",
                ),
                Question(
                    id="business_expenses",
                    text="What were your total business expenses?",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    data_path="income.self_employment_expenses",
                ),
                Question(
                    id="home_office",
                    text="Did you use part of your home regularly and exclusively for business?",
                    question_type=QuestionType.BOOLEAN,
                    help_text="Home office deduction requires exclusive business use",
                ),
                Question(
                    id="home_office_sqft",
                    text="How many square feet is your home office?",
                    question_type=QuestionType.NUMBER,
                    show_if={"question_id": "home_office", "equals": True},
                    help_text="Simplified method: $5 per sq ft, max 300 sq ft",
                    min_value=1,
                    max_value=500,
                    data_path="deductions.home_office_sqft",
                ),
                Question(
                    id="vehicle_expenses",
                    text="Did you use a vehicle for business?",
                    question_type=QuestionType.BOOLEAN,
                ),
                Question(
                    id="business_miles",
                    text="How many miles did you drive for business in 2025?",
                    question_type=QuestionType.NUMBER,
                    show_if={"question_id": "vehicle_expenses", "equals": True},
                    help_text="2025 standard mileage rate: 70 cents per mile",
                    data_path="deductions.business_miles",
                ),
            ],
        )
        self._engine.add_group(group)

    def _setup_investment_income(self) -> None:
        """Set up investment income questions."""
        group = QuestionGroup(
            id="income_investments",
            title="Investment Income",
            description="Tell us about your investment income.",
            icon="trending-up",
            order=8,
            estimated_time="3 minutes",
            show_if={"question_id": "income_types", "contains": "investments"},
            questions=[
                Question(
                    id="dividend_income",
                    text="Total ordinary dividends (1099-DIV Box 1a)",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    data_path="income.dividend_income",
                    irs_form="1099-DIV",
                    irs_line="1a",
                ),
                Question(
                    id="qualified_dividends",
                    text="Qualified dividends (1099-DIV Box 1b)",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    data_path="income.qualified_dividends",
                    help_text="Qualified dividends are taxed at lower capital gains rates",
                    irs_form="1099-DIV",
                    irs_line="1b",
                ),
                Question(
                    id="interest_income",
                    text="Total interest income (1099-INT Box 1)",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    data_path="income.interest_income",
                    irs_form="1099-INT",
                    irs_line="1",
                ),
                Question(
                    id="capital_gains",
                    text="Did you sell any stocks, bonds, or other investments?",
                    question_type=QuestionType.BOOLEAN,
                ),
                Question(
                    id="capital_gain_amount",
                    text="Net capital gain or loss (from 1099-B)",
                    question_type=QuestionType.CURRENCY,
                    show_if={"question_id": "capital_gains", "equals": True},
                    prefix="$",
                    placeholder="0.00",
                    help_text="Enter negative number for losses",
                    data_path="income.capital_gain_income",
                ),
                Question(
                    id="crypto_transactions",
                    text="Did you sell, exchange, or receive cryptocurrency?",
                    question_type=QuestionType.BOOLEAN,
                    help_text="This includes buying NFTs, staking rewards, and crypto payments",
                ),
                Question(
                    id="foreign_taxes",
                    text="Foreign taxes paid (1099-DIV Box 7)",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    required=False,
                    data_path="income.foreign_taxes_paid",
                    help_text="You may be able to claim a credit for foreign taxes paid",
                ),
            ],
        )
        self._engine.add_group(group)

    def _setup_retirement_income(self) -> None:
        """Set up retirement income questions."""
        group = QuestionGroup(
            id="income_retirement",
            title="Retirement Income",
            description="Tell us about your retirement income.",
            icon="umbrella",
            order=9,
            estimated_time="3 minutes",
            show_if={"question_id": "income_types", "contains": "retirement"},
            questions=[
                Question(
                    id="social_security",
                    text="Did you receive Social Security benefits?",
                    question_type=QuestionType.BOOLEAN,
                ),
                Question(
                    id="ss_total",
                    text="Total Social Security benefits (Form SSA-1099, Box 5)",
                    question_type=QuestionType.CURRENCY,
                    show_if={"question_id": "social_security", "equals": True},
                    prefix="$",
                    placeholder="0.00",
                    data_path="income.social_security_income",
                ),
                Question(
                    id="pension_income",
                    text="Did you receive pension or annuity income?",
                    question_type=QuestionType.BOOLEAN,
                ),
                Question(
                    id="pension_amount",
                    text="Taxable pension amount (1099-R Box 2a)",
                    question_type=QuestionType.CURRENCY,
                    show_if={"question_id": "pension_income", "equals": True},
                    prefix="$",
                    placeholder="0.00",
                    data_path="income.retirement_income",
                ),
                Question(
                    id="ira_distribution",
                    text="Did you take any IRA distributions?",
                    question_type=QuestionType.BOOLEAN,
                ),
                Question(
                    id="ira_distribution_amount",
                    text="Taxable IRA distribution amount (1099-R Box 2a)",
                    question_type=QuestionType.CURRENCY,
                    show_if={"question_id": "ira_distribution", "equals": True},
                    prefix="$",
                    placeholder="0.00",
                ),
                Question(
                    id="roth_conversion",
                    text="Did you convert any traditional IRA to Roth IRA?",
                    question_type=QuestionType.BOOLEAN,
                    help_text="Roth conversions are taxable events",
                ),
            ],
        )
        self._engine.add_group(group)

    def _setup_other_income(self) -> None:
        """Set up other income questions."""
        group = QuestionGroup(
            id="income_other",
            title="Other Income",
            description="Tell us about any other income you received.",
            icon="plus-circle",
            order=10,
            estimated_time="2 minutes",
            show_if={"question_id": "income_types", "contains": "other"},
            questions=[
                Question(
                    id="gambling_winnings",
                    text="Gambling winnings (W-2G)",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    required=False,
                    data_path="income.gambling_winnings",
                ),
                Question(
                    id="gambling_losses",
                    text="Gambling losses (to offset winnings)",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    required=False,
                    help_text="Limited to amount of gambling winnings",
                    data_path="deductions.gambling_losses",
                ),
                Question(
                    id="alimony_received",
                    text="Alimony received (pre-2019 agreements only)",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    required=False,
                    help_text="Only taxable if divorce agreement was before 2019",
                ),
                Question(
                    id="jury_duty_pay",
                    text="Jury duty pay",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    required=False,
                ),
                Question(
                    id="prizes_awards",
                    text="Prizes, awards, or contest winnings",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    required=False,
                ),
            ],
        )
        self._engine.add_group(group)

    def _setup_deductions_overview(self) -> None:
        """Set up deductions overview questions."""
        group = QuestionGroup(
            id="deductions_overview",
            title="Deductions Overview",
            description="Let's see what deductions you may qualify for.",
            icon="scissors",
            order=11,
            estimated_time="1 minute",
            questions=[
                Question(
                    id="deduction_types",
                    text="Which of these expenses did you have in 2025?",
                    question_type=QuestionType.MULTI_CHOICE,
                    help_text="Select all that apply - we'll help determine if itemizing benefits you",
                    choices=[
                        Choice(
                            value="mortgage",
                            label="Mortgage Interest",
                            description="Interest paid on home mortgage",
                            triggers_followup="deductions_mortgage",
                        ),
                        Choice(
                            value="property_tax",
                            label="Property Taxes",
                            description="Real estate taxes on your home",
                            triggers_followup="deductions_taxes",
                        ),
                        Choice(
                            value="state_tax",
                            label="State/Local Income Tax",
                            description="State income taxes paid or withheld",
                            triggers_followup="deductions_taxes",
                        ),
                        Choice(
                            value="charity",
                            label="Charitable Contributions",
                            description="Donations to qualified charities",
                            triggers_followup="deductions_charity",
                        ),
                        Choice(
                            value="medical",
                            label="Medical Expenses",
                            description="Out-of-pocket medical costs",
                            triggers_followup="deductions_medical",
                        ),
                        Choice(
                            value="student_loan",
                            label="Student Loan Interest",
                            description="Interest paid on qualified student loans",
                        ),
                        Choice(
                            value="educator",
                            label="Educator Expenses",
                            description="Teachers: classroom supplies (up to $300)",
                        ),
                        Choice(
                            value="none",
                            label="None of these",
                            description="I don't have any of these expenses",
                            exclusive=True,
                        ),
                    ],
                ),
            ],
        )
        self._engine.add_group(group)

    def _setup_mortgage_deductions(self) -> None:
        """Set up mortgage deduction questions."""
        group = QuestionGroup(
            id="deductions_mortgage",
            title="Mortgage Interest",
            description="Enter your mortgage interest information.",
            icon="home",
            order=12,
            estimated_time="2 minutes",
            show_if={"question_id": "deduction_types", "contains": "mortgage"},
            questions=[
                Question(
                    id="mortgage_interest",
                    text="Mortgage interest paid (Form 1098, Box 1)",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    data_path="deductions.mortgage_interest",
                    irs_form="1098",
                    irs_line="1",
                ),
                Question(
                    id="mortgage_points",
                    text="Points paid on home purchase (Form 1098, Box 6)",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    required=False,
                    data_path="deductions.mortgage_points",
                    irs_form="1098",
                    irs_line="6",
                ),
                Question(
                    id="mortgage_insurance",
                    text="Mortgage insurance premiums (Form 1098, Box 5)",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    required=False,
                    help_text="PMI may be deductible if your income is under $109,000",
                    irs_form="1098",
                    irs_line="5",
                ),
            ],
        )
        self._engine.add_group(group)

    def _setup_tax_deductions(self) -> None:
        """Set up tax deduction questions."""
        group = QuestionGroup(
            id="deductions_taxes",
            title="Taxes Paid",
            description="Enter taxes you paid (subject to $10,000 SALT cap).",
            icon="file-minus",
            order=13,
            estimated_time="2 minutes",
            show_if={
                "or": [
                    {"question_id": "deduction_types", "contains": "property_tax"},
                    {"question_id": "deduction_types", "contains": "state_tax"},
                ]
            },
            questions=[
                Question(
                    id="property_taxes",
                    text="Real estate taxes paid",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    data_path="deductions.property_taxes",
                    help_text="Annual property taxes on your primary residence",
                ),
                Question(
                    id="state_local_income_tax",
                    text="State and local income taxes paid",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    required=False,
                    data_path="deductions.state_local_taxes",
                    help_text="From W-2 or estimated payments (minus refunds received)",
                ),
                Question(
                    id="vehicle_registration",
                    text="Vehicle registration fees (personal property tax portion)",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    required=False,
                    help_text="Only the tax portion based on vehicle value, not flat fees",
                ),
            ],
        )
        self._engine.add_group(group)

    def _setup_charity_deductions(self) -> None:
        """Set up charity deduction questions."""
        group = QuestionGroup(
            id="deductions_charity",
            title="Charitable Contributions",
            description="Enter your charitable donations.",
            icon="heart",
            order=14,
            estimated_time="2 minutes",
            show_if={"question_id": "deduction_types", "contains": "charity"},
            questions=[
                Question(
                    id="charity_cash",
                    text="Cash contributions to charity",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    data_path="deductions.charitable_cash",
                    help_text="Include checks, credit card donations, and payroll deductions",
                ),
                Question(
                    id="charity_noncash",
                    text="Non-cash contributions (clothing, household items, etc.)",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    required=False,
                    data_path="deductions.charitable_noncash",
                    help_text="Fair market value of donated items",
                ),
                Question(
                    id="charity_carryover",
                    text="Do you have charitable contribution carryover from prior years?",
                    question_type=QuestionType.BOOLEAN,
                    help_text="If previous year's donations exceeded AGI limits",
                ),
            ],
        )
        self._engine.add_group(group)

    def _setup_medical_deductions(self) -> None:
        """Set up medical deduction questions."""
        group = QuestionGroup(
            id="deductions_medical",
            title="Medical Expenses",
            description="Enter your out-of-pocket medical expenses.",
            icon="activity",
            order=15,
            estimated_time="2 minutes",
            show_if={"question_id": "deduction_types", "contains": "medical"},
            questions=[
                Question(
                    id="medical_expenses",
                    text="Total unreimbursed medical and dental expenses",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    data_path="deductions.medical_expenses",
                    help_text="Only amounts exceeding 7.5% of AGI are deductible",
                ),
                Question(
                    id="health_insurance_premiums",
                    text="Health insurance premiums paid (not through employer)",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    required=False,
                    help_text="Include self-paid health, dental, and vision premiums",
                ),
                Question(
                    id="long_term_care",
                    text="Long-term care insurance premiums",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    required=False,
                    help_text="Deductible amount depends on your age",
                ),
                Question(
                    id="hsa_contribution",
                    text="HSA contributions (not through employer)",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    required=False,
                    data_path="income.hsa_contribution",
                    help_text="2025 limits: $4,300 individual, $8,550 family",
                ),
            ],
        )
        self._engine.add_group(group)

    def _setup_credits_overview(self) -> None:
        """Set up credits overview questions."""
        group = QuestionGroup(
            id="credits_overview",
            title="Tax Credits",
            description="Let's check which tax credits you may qualify for.",
            icon="award",
            order=16,
            estimated_time="1 minute",
            questions=[
                Question(
                    id="credit_situations",
                    text="Which of these apply to you in 2025?",
                    question_type=QuestionType.MULTI_CHOICE,
                    help_text="Tax credits directly reduce your tax - they're valuable!",
                    choices=[
                        Choice(
                            value="education",
                            label="Education Expenses",
                            description="Paid tuition, fees, or student loan interest",
                            triggers_followup="credits_education",
                        ),
                        Choice(
                            value="child_care",
                            label="Child/Dependent Care",
                            description="Paid for care so you could work",
                            triggers_followup="credits_child",
                        ),
                        Choice(
                            value="retirement_savings",
                            label="Retirement Savings",
                            description="Contributed to 401(k), IRA, or similar",
                        ),
                        Choice(
                            value="home_energy",
                            label="Home Energy Improvements",
                            description="Installed solar, EV charger, or efficient windows/doors",
                            triggers_followup="credits_energy",
                        ),
                        Choice(
                            value="ev_purchase",
                            label="Electric Vehicle Purchase",
                            description="Bought or leased an electric vehicle",
                            triggers_followup="credits_energy",
                        ),
                        Choice(
                            value="adoption",
                            label="Adoption",
                            description="Adopted a child in 2025",
                        ),
                        Choice(
                            value="none",
                            label="None of these",
                            exclusive=True,
                        ),
                    ],
                ),
            ],
        )
        self._engine.add_group(group)

    def _setup_education_credits(self) -> None:
        """Set up education credit questions."""
        group = QuestionGroup(
            id="credits_education",
            title="Education Credits",
            description="Enter your education expenses.",
            icon="book",
            order=17,
            estimated_time="2 minutes",
            show_if={"question_id": "credit_situations", "contains": "education"},
            questions=[
                Question(
                    id="student_name",
                    text="Who was the student?",
                    question_type=QuestionType.SINGLE_CHOICE,
                    choices=[
                        Choice(value="self", label="Myself"),
                        Choice(value="spouse", label="My spouse"),
                        Choice(value="dependent", label="A dependent"),
                    ],
                ),
                Question(
                    id="school_name",
                    text="Name of educational institution",
                    question_type=QuestionType.TEXT,
                    placeholder="University/College name",
                ),
                Question(
                    id="tuition_paid",
                    text="Tuition and fees paid (Form 1098-T, Box 1)",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    data_path="credits.education_expenses",
                    irs_form="1098-T",
                    irs_line="1",
                ),
                Question(
                    id="scholarships_received",
                    text="Scholarships or grants received (Form 1098-T, Box 5)",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    required=False,
                    irs_form="1098-T",
                    irs_line="5",
                ),
                Question(
                    id="first_four_years",
                    text="Was the student in the first 4 years of college?",
                    question_type=QuestionType.BOOLEAN,
                    help_text="American Opportunity Credit is available for first 4 years only",
                ),
                Question(
                    id="half_time_student",
                    text="Was the student enrolled at least half-time?",
                    question_type=QuestionType.BOOLEAN,
                ),
                Question(
                    id="student_loan_interest_paid",
                    text="Student loan interest paid (Form 1098-E)",
                    question_type=QuestionType.CURRENCY,
                    prefix="$",
                    placeholder="0.00",
                    required=False,
                    data_path="income.student_loan_interest",
                    help_text="Up to $2,500 is deductible (above-the-line)",
                ),
            ],
        )
        self._engine.add_group(group)

    def _setup_child_credits(self) -> None:
        """Set up child-related credit questions."""
        group = QuestionGroup(
            id="credits_child",
            title="Child-Related Credits",
            description="Additional information for child-related credits.",
            icon="smile",
            order=18,
            estimated_time="2 minutes",
            show_if={"question_id": "credit_situations", "contains": "child_care"},
            questions=[
                Question(
                    id="care_provider_name",
                    text="Child care provider's name",
                    question_type=QuestionType.TEXT,
                    placeholder="Daycare name or individual's name",
                ),
                Question(
                    id="care_provider_ein",
                    text="Care provider's EIN or SSN",
                    question_type=QuestionType.TEXT,
                    placeholder="XX-XXXXXXX",
                    help_text="Required for the credit",
                ),
                Question(
                    id="care_provider_address",
                    text="Care provider's address",
                    question_type=QuestionType.TEXT,
                    placeholder="Street, City, State ZIP",
                ),
                Question(
                    id="dependent_care_fsa",
                    text="Did you receive dependent care FSA benefits from your employer?",
                    question_type=QuestionType.BOOLEAN,
                ),
                Question(
                    id="dependent_care_fsa_amount",
                    text="Dependent care FSA amount received",
                    question_type=QuestionType.CURRENCY,
                    show_if={"question_id": "dependent_care_fsa", "equals": True},
                    prefix="$",
                    placeholder="0.00",
                    help_text="This reduces the expenses eligible for the credit",
                ),
            ],
        )
        self._engine.add_group(group)

    def _setup_energy_credits(self) -> None:
        """Set up energy credit questions."""
        group = QuestionGroup(
            id="credits_energy",
            title="Energy Credits",
            description="Tell us about your clean energy investments.",
            icon="sun",
            order=19,
            estimated_time="2 minutes",
            show_if={
                "or": [
                    {"question_id": "credit_situations", "contains": "home_energy"},
                    {"question_id": "credit_situations", "contains": "ev_purchase"},
                ]
            },
            questions=[
                Question(
                    id="solar_installation",
                    text="Did you install solar panels on your home?",
                    question_type=QuestionType.BOOLEAN,
                ),
                Question(
                    id="solar_cost",
                    text="Total cost of solar installation",
                    question_type=QuestionType.CURRENCY,
                    show_if={"question_id": "solar_installation", "equals": True},
                    prefix="$",
                    placeholder="0.00",
                    data_path="credits.solar_expenses",
                    help_text="30% credit for solar installed in 2025",
                ),
                Question(
                    id="ev_purchased",
                    text="Did you buy or lease an electric vehicle?",
                    question_type=QuestionType.BOOLEAN,
                ),
                Question(
                    id="ev_type",
                    text="Was this a new or used electric vehicle?",
                    question_type=QuestionType.SINGLE_CHOICE,
                    show_if={"question_id": "ev_purchased", "equals": True},
                    choices=[
                        Choice(value="new", label="New", description="Up to $7,500 credit"),
                        Choice(value="used", label="Used", description="Up to $4,000 credit"),
                    ],
                ),
                Question(
                    id="ev_vin",
                    text="Vehicle Identification Number (VIN)",
                    question_type=QuestionType.TEXT,
                    show_if={"question_id": "ev_purchased", "equals": True},
                    placeholder="17-character VIN",
                    help_text="Used to verify vehicle qualifies for credit",
                ),
                Question(
                    id="ev_purchase_price",
                    text="Vehicle purchase price",
                    question_type=QuestionType.CURRENCY,
                    show_if={"question_id": "ev_purchased", "equals": True},
                    prefix="$",
                    placeholder="0.00",
                    data_path="credits.ev_purchase_amount",
                ),
                Question(
                    id="energy_efficient_improvements",
                    text="Did you make other energy-efficient home improvements?",
                    question_type=QuestionType.BOOLEAN,
                    help_text="Doors, windows, insulation, heat pumps, etc.",
                ),
                Question(
                    id="energy_improvement_cost",
                    text="Total cost of energy improvements",
                    question_type=QuestionType.CURRENCY,
                    show_if={"question_id": "energy_efficient_improvements", "equals": True},
                    prefix="$",
                    placeholder="0.00",
                    data_path="credits.clean_energy_expenses",
                ),
            ],
        )
        self._engine.add_group(group)

    def _setup_healthcare(self) -> None:
        """Set up healthcare questions."""
        group = QuestionGroup(
            id="healthcare",
            title="Health Insurance",
            description="Information about your health insurance coverage.",
            icon="shield",
            order=20,
            estimated_time="2 minutes",
            questions=[
                Question(
                    id="health_coverage_type",
                    text="How did you get health insurance in 2025?",
                    question_type=QuestionType.SINGLE_CHOICE,
                    choices=[
                        Choice(value="employer", label="Through employer"),
                        Choice(value="marketplace", label="Healthcare.gov Marketplace"),
                        Choice(value="medicare", label="Medicare"),
                        Choice(value="medicaid", label="Medicaid"),
                        Choice(value="spouse", label="Through spouse's employer"),
                        Choice(value="self_employed", label="Self-employed (deductible)"),
                        Choice(value="uninsured", label="I wasn't insured"),
                    ],
                ),
                Question(
                    id="marketplace_plan",
                    text="Did you receive Form 1095-A from the Marketplace?",
                    question_type=QuestionType.BOOLEAN,
                    show_if={"question_id": "health_coverage_type", "equals": "marketplace"},
                ),
                Question(
                    id="advance_ptc",
                    text="Advance Premium Tax Credit received (1095-A, Part III)",
                    question_type=QuestionType.CURRENCY,
                    show_if={"question_id": "marketplace_plan", "equals": True},
                    prefix="$",
                    placeholder="0.00",
                    data_path="credits.advance_ptc_received",
                    help_text="This will be reconciled on your return",
                ),
                Question(
                    id="marketplace_premium",
                    text="Annual premium amount (1095-A, Column A total)",
                    question_type=QuestionType.CURRENCY,
                    show_if={"question_id": "marketplace_plan", "equals": True},
                    prefix="$",
                    placeholder="0.00",
                    data_path="credits.marketplace_premium",
                ),
            ],
        )
        self._engine.add_group(group)

    def _setup_state_info(self) -> None:
        """Set up state tax information questions."""
        group = QuestionGroup(
            id="state_info",
            title="State Information",
            description="Let's finalize your state tax information.",
            icon="map-pin",
            order=21,
            estimated_time="1 minute",
            questions=[
                Question(
                    id="state_residence",
                    text="What state did you live in for most of 2025?",
                    question_type=QuestionType.SINGLE_CHOICE,
                    data_path="taxpayer.state_of_residence",
                    choices=[
                        Choice(value="AL", label="Alabama"),
                        Choice(value="AK", label="Alaska (No income tax)"),
                        Choice(value="AZ", label="Arizona"),
                        Choice(value="AR", label="Arkansas"),
                        Choice(value="CA", label="California"),
                        Choice(value="CO", label="Colorado"),
                        Choice(value="CT", label="Connecticut"),
                        Choice(value="DE", label="Delaware"),
                        Choice(value="DC", label="District of Columbia"),
                        Choice(value="FL", label="Florida (No income tax)"),
                        Choice(value="GA", label="Georgia"),
                        Choice(value="HI", label="Hawaii"),
                        Choice(value="ID", label="Idaho"),
                        Choice(value="IL", label="Illinois"),
                        Choice(value="IN", label="Indiana"),
                        Choice(value="IA", label="Iowa"),
                        Choice(value="KS", label="Kansas"),
                        Choice(value="KY", label="Kentucky"),
                        Choice(value="LA", label="Louisiana"),
                        Choice(value="ME", label="Maine"),
                        Choice(value="MD", label="Maryland"),
                        Choice(value="MA", label="Massachusetts"),
                        Choice(value="MI", label="Michigan"),
                        Choice(value="MN", label="Minnesota"),
                        Choice(value="MS", label="Mississippi"),
                        Choice(value="MO", label="Missouri"),
                        Choice(value="MT", label="Montana"),
                        Choice(value="NE", label="Nebraska"),
                        Choice(value="NV", label="Nevada (No income tax)"),
                        Choice(value="NH", label="New Hampshire"),
                        Choice(value="NJ", label="New Jersey"),
                        Choice(value="NM", label="New Mexico"),
                        Choice(value="NY", label="New York"),
                        Choice(value="NC", label="North Carolina"),
                        Choice(value="ND", label="North Dakota"),
                        Choice(value="OH", label="Ohio"),
                        Choice(value="OK", label="Oklahoma"),
                        Choice(value="OR", label="Oregon"),
                        Choice(value="PA", label="Pennsylvania"),
                        Choice(value="RI", label="Rhode Island"),
                        Choice(value="SC", label="South Carolina"),
                        Choice(value="SD", label="South Dakota (No income tax)"),
                        Choice(value="TN", label="Tennessee"),
                        Choice(value="TX", label="Texas (No income tax)"),
                        Choice(value="UT", label="Utah"),
                        Choice(value="VT", label="Vermont"),
                        Choice(value="VA", label="Virginia"),
                        Choice(value="WA", label="Washington (No income tax)"),
                        Choice(value="WV", label="West Virginia"),
                        Choice(value="WI", label="Wisconsin"),
                        Choice(value="WY", label="Wyoming (No income tax)"),
                    ],
                ),
                Question(
                    id="moved_during_year",
                    text="Did you move to a different state during 2025?",
                    question_type=QuestionType.BOOLEAN,
                    help_text="You may need to file part-year returns in multiple states",
                ),
                Question(
                    id="worked_other_state",
                    text="Did you earn income in a state other than where you live?",
                    question_type=QuestionType.BOOLEAN,
                    help_text="You may need to file nonresident returns",
                ),
            ],
        )
        self._engine.add_group(group)

    # Public interface methods

    def start_interview(self) -> Dict[str, Any]:
        """Start a new interview session."""
        self._state.started_at = datetime.now().isoformat()
        self._state.last_activity = self._state.started_at
        self._state.current_stage = InterviewStage.PERSONAL_INFO

        # Persist state after starting
        self._persist_state()

        return {
            "status": "started",
            "current_group": self._engine.get_current_group(),
            "current_question": self._engine.get_current_question(),
            "progress": self._engine.get_progress(),
        }

    def get_current_questions(self) -> Dict[str, Any]:
        """Get the current group of questions."""
        group = self._engine.get_current_group()
        if not group:
            return {"status": "complete", "is_complete": True}

        questions = self._engine.get_all_questions_for_group(group.id)

        return {
            "status": "in_progress",
            "group": {
                "id": group.id,
                "title": group.title,
                "description": group.description,
                "icon": group.icon,
                "estimated_time": group.estimated_time,
            },
            "questions": [
                {
                    "id": q.id,
                    "text": q.text,
                    "type": q.question_type.value,
                    "help_text": q.help_text,
                    "placeholder": q.placeholder,
                    "prefix": q.prefix,
                    "suffix": q.suffix,
                    "required": q.required,
                    "choices": [
                        {"value": c.value, "label": c.label, "description": c.description}
                        for c in q.choices
                    ] if q.choices else None,
                    "current_value": self._engine.get_answer(q.id),
                    "irs_form": q.irs_form,
                    "irs_line": q.irs_line,
                }
                for q in questions
            ],
            "progress": self._engine.get_progress(),
        }

    def submit_answers(self, answers: Dict[str, Any]) -> Dict[str, Any]:
        """Submit answers for the current group."""
        self._state.last_activity = datetime.now().isoformat()

        results = self._engine.set_answers(answers)

        # Check for validation errors
        errors = {
            q_id: r.error_message
            for q_id, r in results.items()
            if not r.is_valid
        }

        if errors:
            return {
                "status": "validation_error",
                "errors": errors,
            }

        # Move to next group
        self._engine.next_group()

        # Persist state after successful submission
        self._persist_state()

        return {
            "status": "success",
            "next_group": self.get_current_questions(),
        }

    def go_back(self) -> Dict[str, Any]:
        """Go back to the previous group."""
        self._engine.previous_group()

        # Persist state after navigation
        self._persist_state()

        return self.get_current_questions()

    def get_progress(self) -> Dict[str, Any]:
        """Get current interview progress."""
        return self._engine.get_progress()

    def get_all_collected_data(self) -> Dict[str, Any]:
        """Get all collected data organized by category."""
        return self._engine.get_all_answers()

    def is_complete(self) -> bool:
        """Check if interview is complete."""
        return self._engine.is_complete()

    def export_to_tax_return(self) -> Dict[str, Any]:
        """Export collected data to tax return format."""
        answers = self._engine.get_all_answers()

        # Map answers to tax return structure
        tax_return_data = {
            "taxpayer": {},
            "income": {},
            "deductions": {},
            "credits": {},
            "dependents": [],
        }

        # Process each answer based on data_path
        for group in self._engine._groups:
            for question in group.questions:
                if question.id in answers and question.data_path:
                    value = answers[question.id]
                    path_parts = question.data_path.split(".")

                    if len(path_parts) == 2:
                        category, field = path_parts
                        if category in tax_return_data:
                            tax_return_data[category][field] = value

        return tax_return_data

    def save_state(self) -> Dict[str, Any]:
        """Save interview state for later resumption."""
        return {
            "questionnaire_state": self._engine.export_state(),
            "interview_state": {
                "current_stage": self._state.current_stage.value,
                "started_at": self._state.started_at,
                "last_activity": self._state.last_activity,
            },
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        """Load saved interview state."""
        if "questionnaire_state" in state:
            self._engine.import_state(state["questionnaire_state"])

        if "interview_state" in state:
            self._state.current_stage = InterviewStage(
                state["interview_state"].get("current_stage", "welcome")
            )
            self._state.started_at = state["interview_state"].get("started_at")
            self._state.last_activity = state["interview_state"].get("last_activity")

    # =========================================================================
    # PERSISTENCE METHODS (Prompt 1: Persistence Safety)
    # =========================================================================

    def _get_persistence(self):
        """Get or create the persistence instance."""
        if self._persistence is None:
            try:
                from database.onboarding_persistence import get_onboarding_persistence
                self._persistence = get_onboarding_persistence()
            except Exception as e:
                logger.warning(f"Failed to initialize persistence: {e}")
        return self._persistence

    def _persist_state(self) -> None:
        """Persist current state to database."""
        if not self._session_id:
            return

        persistence = self._get_persistence()
        if not persistence:
            return

        try:
            persistence.save_interview_state(
                session_id=self._session_id,
                current_stage=self._state.current_stage.value,
                started_at=self._state.started_at,
                last_activity=self._state.last_activity,
                is_complete=self._state.is_complete,
                collected_data=self._state.collected_data,
                detected_forms=self._state.detected_forms,
                estimated_refund=self._state.estimated_refund,
                progress_percentage=self._state.progress_percentage,
                questionnaire_state=self._engine.export_state()
            )
        except Exception as e:
            logger.error(f"Failed to persist interview state: {e}")

    def _load_persisted_state(self) -> None:
        """Load state from database if available."""
        if not self._session_id:
            return

        persistence = self._get_persistence()
        if not persistence:
            return

        try:
            record = persistence.load_interview_state(self._session_id)
            if record:
                # Restore interview state
                self._state.current_stage = InterviewStage(record.current_stage)
                self._state.started_at = record.started_at
                self._state.last_activity = record.last_activity
                self._state.is_complete = record.is_complete
                self._state.collected_data = record.collected_data
                self._state.detected_forms = record.detected_forms
                self._state.estimated_refund = record.estimated_refund
                self._state.progress_percentage = record.progress_percentage

                # Restore questionnaire engine state
                if record.questionnaire_state:
                    self._engine.import_state(record.questionnaire_state)

                logger.info(f"Restored interview state for session {self._session_id}")
        except Exception as e:
            logger.error(f"Failed to load persisted interview state: {e}")
