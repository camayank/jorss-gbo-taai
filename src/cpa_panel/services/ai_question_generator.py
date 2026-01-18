"""
AI Question Generator - Generates smart follow-up questions for tax onboarding.

Uses extracted 1040 data to determine which questions are relevant
for identifying tax optimization opportunities.
"""

from __future__ import annotations

import os
import json
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from decimal import Decimal
from enum import Enum

from .form_1040_parser import Parsed1040Data, FilingStatus

logger = logging.getLogger(__name__)


class QuestionCategory(str, Enum):
    """Categories of follow-up questions."""
    RETIREMENT = "retirement"
    HEALTHCARE = "healthcare"
    DEPENDENTS = "dependents"
    SELF_EMPLOYMENT = "self_employment"
    INVESTMENTS = "investments"
    DEDUCTIONS = "deductions"
    CREDITS = "credits"
    INCOME = "income"
    EDUCATION = "education"
    LIFE_EVENTS = "life_events"


class QuestionPriority(str, Enum):
    """Priority levels for questions."""
    HIGH = "high"  # Likely significant savings opportunity
    MEDIUM = "medium"  # Moderate savings opportunity
    LOW = "low"  # Nice to know, minor impact


@dataclass
class SmartQuestion:
    """
    A smart follow-up question generated based on 1040 data.
    """
    id: str
    question: str
    category: QuestionCategory
    priority: QuestionPriority
    options: List[Dict[str, str]]  # [{value: "yes", label: "Yes"}, ...]
    reason: str  # Why this question is being asked
    potential_impact: str  # What optimization could result
    depends_on: Optional[str] = None  # Question ID this depends on
    show_if_answer: Optional[str] = None  # Show if previous answer matches

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "category": self.category.value,
            "priority": self.priority.value,
            "options": self.options,
            "reason": self.reason,
            "potential_impact": self.potential_impact,
            "depends_on": self.depends_on,
            "show_if_answer": self.show_if_answer,
        }


@dataclass
class QuestionSet:
    """
    Set of smart questions tailored to a specific taxpayer.
    """
    questions: List[SmartQuestion]
    taxpayer_profile: str  # Summary of what we know
    estimated_question_count: int
    categories_covered: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "questions": [q.to_dict() for q in self.questions],
            "taxpayer_profile": self.taxpayer_profile,
            "estimated_question_count": self.estimated_question_count,
            "categories_covered": self.categories_covered,
        }


class AIQuestionGenerator:
    """
    Generates smart follow-up questions based on extracted 1040 data.

    The generator analyzes the tax return data and determines which
    questions would help identify optimization opportunities.
    """

    def __init__(self, use_ai: bool = True):
        """
        Initialize the question generator.

        Args:
            use_ai: Whether to use OpenAI for enhanced question generation.
                   Falls back to rule-based generation if False or API unavailable.
        """
        self.use_ai = use_ai and bool(os.getenv("OPENAI_API_KEY"))
        self._openai_client = None

        if self.use_ai:
            try:
                import openai
                self._openai_client = openai.OpenAI()
            except ImportError:
                logger.warning("OpenAI package not installed, using rule-based generation")
                self.use_ai = False

    def generate_questions(self, parsed_data: Parsed1040Data) -> QuestionSet:
        """
        Generate smart follow-up questions based on extracted 1040 data.

        Args:
            parsed_data: Parsed 1040 data from OCR extraction

        Returns:
            QuestionSet with relevant questions
        """
        questions = []
        categories_covered = set()

        # Analyze what we know and generate relevant questions
        profile_parts = []

        # 1. Filing status based questions
        if parsed_data.filing_status:
            profile_parts.append(f"Filing: {parsed_data.filing_status.value}")

        # 2. Income-based analysis
        agi = parsed_data.adjusted_gross_income or Decimal("0")
        wages = parsed_data.wages_salaries_tips or Decimal("0")

        if wages > 0:
            profile_parts.append(f"W-2 Income: ${wages:,.0f}")

        if agi > 0:
            profile_parts.append(f"AGI: ${agi:,.0f}")

        # Generate questions by category based on what we found
        questions.extend(self._generate_retirement_questions(parsed_data))
        questions.extend(self._generate_healthcare_questions(parsed_data))
        questions.extend(self._generate_dependent_questions(parsed_data))
        questions.extend(self._generate_deduction_questions(parsed_data))
        questions.extend(self._generate_investment_questions(parsed_data))
        questions.extend(self._generate_income_questions(parsed_data))
        questions.extend(self._generate_education_questions(parsed_data))
        questions.extend(self._generate_credit_questions(parsed_data))

        # Track categories
        for q in questions:
            categories_covered.add(q.category.value)

        # Sort by priority
        priority_order = {QuestionPriority.HIGH: 0, QuestionPriority.MEDIUM: 1, QuestionPriority.LOW: 2}
        questions.sort(key=lambda x: priority_order[x.priority])

        # Limit to most important questions (max 8 for short onboarding)
        questions = questions[:8]

        return QuestionSet(
            questions=questions,
            taxpayer_profile=" | ".join(profile_parts) if profile_parts else "New taxpayer",
            estimated_question_count=len(questions),
            categories_covered=list(categories_covered),
        )

    def _generate_retirement_questions(self, data: Parsed1040Data) -> List[SmartQuestion]:
        """Generate retirement-related questions."""
        questions = []
        wages = data.wages_salaries_tips or Decimal("0")
        agi = data.adjusted_gross_income or Decimal("0")

        # If they have W-2 income, ask about 401k
        if wages > 0:
            questions.append(SmartQuestion(
                id="retirement_401k_available",
                question="Does your employer offer a 401(k) or similar retirement plan?",
                category=QuestionCategory.RETIREMENT,
                priority=QuestionPriority.HIGH,
                options=[
                    {"value": "yes_with_match", "label": "Yes, with employer match"},
                    {"value": "yes_no_match", "label": "Yes, but no match"},
                    {"value": "no", "label": "No"},
                    {"value": "unknown", "label": "Not sure"},
                ],
                reason="Employer retirement plans offer significant tax benefits",
                potential_impact="401(k) contributions can save 22-37% in taxes on every dollar contributed",
            ))

            questions.append(SmartQuestion(
                id="retirement_401k_contribution",
                question="What's your current 401(k) contribution rate?",
                category=QuestionCategory.RETIREMENT,
                priority=QuestionPriority.HIGH,
                options=[
                    {"value": "0", "label": "0% (not contributing)"},
                    {"value": "1-5", "label": "1-5%"},
                    {"value": "6-10", "label": "6-10%"},
                    {"value": "11-15", "label": "11-15%"},
                    {"value": "max", "label": "Maxing out ($23,000)"},
                    {"value": "unknown", "label": "Not sure"},
                ],
                reason="Understanding current contributions helps identify optimization",
                potential_impact="Increasing to max could save $2,000-5,000+ in taxes annually",
                depends_on="retirement_401k_available",
                show_if_answer="yes_with_match,yes_no_match",
            ))

        # IRA questions based on income level
        if agi > 0 and agi < Decimal("230000"):  # Under phase-out for Roth IRA (MFJ)
            questions.append(SmartQuestion(
                id="retirement_ira",
                question="Do you contribute to an IRA (Traditional or Roth)?",
                category=QuestionCategory.RETIREMENT,
                priority=QuestionPriority.MEDIUM,
                options=[
                    {"value": "traditional", "label": "Yes, Traditional IRA"},
                    {"value": "roth", "label": "Yes, Roth IRA"},
                    {"value": "both", "label": "Yes, both"},
                    {"value": "no", "label": "No"},
                ],
                reason="IRA contributions provide additional tax benefits",
                potential_impact="Up to $7,000/year in tax-advantaged savings ($8,000 if 50+)",
            ))

        return questions

    def _generate_healthcare_questions(self, data: Parsed1040Data) -> List[SmartQuestion]:
        """Generate healthcare-related questions."""
        questions = []
        wages = data.wages_salaries_tips or Decimal("0")

        if wages > 0:
            questions.append(SmartQuestion(
                id="healthcare_hdhp",
                question="Do you have a High Deductible Health Plan (HDHP)?",
                category=QuestionCategory.HEALTHCARE,
                priority=QuestionPriority.HIGH,
                options=[
                    {"value": "yes", "label": "Yes"},
                    {"value": "no", "label": "No"},
                    {"value": "unknown", "label": "Not sure"},
                ],
                reason="HDHPs qualify for HSA contributions with triple tax benefits",
                potential_impact="HSA contributions save taxes now, grow tax-free, and withdraw tax-free for medical",
            ))

            questions.append(SmartQuestion(
                id="healthcare_hsa",
                question="If you have an HSA, how much do you contribute annually?",
                category=QuestionCategory.HEALTHCARE,
                priority=QuestionPriority.HIGH,
                options=[
                    {"value": "0", "label": "Nothing / Don't have HSA"},
                    {"value": "partial", "label": "Some, but not the max"},
                    {"value": "max", "label": "Maximum allowed"},
                    {"value": "unknown", "label": "Not sure"},
                ],
                reason="HSA max is $4,150 individual / $8,300 family (2024)",
                potential_impact="Maxing HSA could save $1,000-2,000+ in taxes",
                depends_on="healthcare_hdhp",
                show_if_answer="yes",
            ))

            questions.append(SmartQuestion(
                id="healthcare_fsa",
                question="Does your employer offer a Flexible Spending Account (FSA)?",
                category=QuestionCategory.HEALTHCARE,
                priority=QuestionPriority.MEDIUM,
                options=[
                    {"value": "yes_using", "label": "Yes, and I use it"},
                    {"value": "yes_not_using", "label": "Yes, but I don't use it"},
                    {"value": "no", "label": "No"},
                    {"value": "unknown", "label": "Not sure"},
                ],
                reason="FSA allows pre-tax healthcare and dependent care spending",
                potential_impact="$3,200 healthcare FSA + $5,000 dependent care FSA available",
            ))

        return questions

    def _generate_dependent_questions(self, data: Parsed1040Data) -> List[SmartQuestion]:
        """Generate dependent-related questions."""
        questions = []
        ctc = data.child_tax_credit or Decimal("0")
        num_dependents = data.total_dependents or 0

        # If they have CTC or dependents listed
        if ctc > 0 or num_dependents > 0:
            questions.append(SmartQuestion(
                id="dependents_childcare",
                question="Do you pay for childcare or daycare?",
                category=QuestionCategory.DEPENDENTS,
                priority=QuestionPriority.HIGH,
                options=[
                    {"value": "yes_high", "label": "Yes, $5,000+ per year"},
                    {"value": "yes_low", "label": "Yes, under $5,000 per year"},
                    {"value": "no", "label": "No"},
                ],
                reason="Childcare expenses may qualify for tax credits and FSA",
                potential_impact="Child and Dependent Care Credit up to $2,100 + $5,000 FSA savings",
            ))

            questions.append(SmartQuestion(
                id="dependents_ages",
                question="Are any of your children under age 6?",
                category=QuestionCategory.DEPENDENTS,
                priority=QuestionPriority.MEDIUM,
                options=[
                    {"value": "yes", "label": "Yes"},
                    {"value": "no", "label": "No"},
                ],
                reason="Younger children may qualify for enhanced credits",
                potential_impact="Enhanced Child Tax Credit eligibility verification",
            ))

        return questions

    def _generate_deduction_questions(self, data: Parsed1040Data) -> List[SmartQuestion]:
        """Generate deduction-related questions."""
        questions = []
        std_ded = data.standard_deduction or Decimal("0")
        itemized = data.itemized_deductions or Decimal("0")

        # If they took standard deduction, check if itemizing might help
        if std_ded > 0 and itemized == 0:
            questions.append(SmartQuestion(
                id="deductions_mortgage",
                question="Do you pay mortgage interest?",
                category=QuestionCategory.DEDUCTIONS,
                priority=QuestionPriority.MEDIUM,
                options=[
                    {"value": "yes_high", "label": "Yes, significant amount ($10k+)"},
                    {"value": "yes_low", "label": "Yes, smaller amount (under $10k)"},
                    {"value": "no", "label": "No / Rent"},
                ],
                reason="Mortgage interest can push you into itemizing territory",
                potential_impact="Itemizing could save if deductions exceed standard deduction",
            ))

            questions.append(SmartQuestion(
                id="deductions_charity",
                question="How much do you typically donate to charity annually?",
                category=QuestionCategory.DEDUCTIONS,
                priority=QuestionPriority.MEDIUM,
                options=[
                    {"value": "none", "label": "Little to none"},
                    {"value": "low", "label": "Under $1,000"},
                    {"value": "medium", "label": "$1,000 - $5,000"},
                    {"value": "high", "label": "Over $5,000"},
                ],
                reason="Charitable donations are deductible; bunching strategy possible",
                potential_impact="Charitable bunching could save hundreds to thousands",
            ))

            questions.append(SmartQuestion(
                id="deductions_state_local",
                question="Do you pay significant state/local income or property taxes?",
                category=QuestionCategory.DEDUCTIONS,
                priority=QuestionPriority.MEDIUM,
                options=[
                    {"value": "high", "label": "Yes, over $10,000 combined"},
                    {"value": "medium", "label": "Yes, $5,000-$10,000"},
                    {"value": "low", "label": "Under $5,000"},
                    {"value": "none", "label": "No state income tax"},
                ],
                reason="SALT deduction capped at $10,000 but still valuable",
                potential_impact="May affect itemizing vs standard deduction decision",
            ))

        return questions

    def _generate_investment_questions(self, data: Parsed1040Data) -> List[SmartQuestion]:
        """Generate investment-related questions."""
        questions = []
        cap_gains = data.capital_gain_or_loss or Decimal("0")
        dividends = data.ordinary_dividends or Decimal("0")

        if cap_gains != 0 or dividends > 0:
            questions.append(SmartQuestion(
                id="investments_losses",
                question="Do you have any investment losses you haven't sold yet?",
                category=QuestionCategory.INVESTMENTS,
                priority=QuestionPriority.MEDIUM,
                options=[
                    {"value": "yes_significant", "label": "Yes, significant losses"},
                    {"value": "yes_small", "label": "Yes, small losses"},
                    {"value": "no", "label": "No"},
                    {"value": "unknown", "label": "Not sure"},
                ],
                reason="Tax-loss harvesting can offset gains and reduce taxes",
                potential_impact="Can offset gains dollar-for-dollar, plus $3,000 against ordinary income",
            ))

        # For higher income, ask about NIIT
        agi = data.adjusted_gross_income or Decimal("0")
        if agi > Decimal("200000"):
            questions.append(SmartQuestion(
                id="investments_niit",
                question="Are you aware of strategies to minimize the 3.8% Net Investment Income Tax?",
                category=QuestionCategory.INVESTMENTS,
                priority=QuestionPriority.MEDIUM,
                options=[
                    {"value": "yes", "label": "Yes, I'm already planning"},
                    {"value": "interested", "label": "No, but interested"},
                    {"value": "not_applicable", "label": "Doesn't apply to me"},
                ],
                reason="NIIT applies to investment income over threshold",
                potential_impact="Strategic planning can reduce or defer NIIT",
            ))

        return questions

    def _generate_income_questions(self, data: Parsed1040Data) -> List[SmartQuestion]:
        """Generate income-related questions."""
        questions = []
        other_income = data.other_income or Decimal("0")

        # Check for self-employment indicators
        if other_income > Decimal("1000"):
            questions.append(SmartQuestion(
                id="income_self_employment",
                question="Do you have any self-employment or freelance income?",
                category=QuestionCategory.SELF_EMPLOYMENT,
                priority=QuestionPriority.HIGH,
                options=[
                    {"value": "yes_significant", "label": "Yes, significant ($10k+)"},
                    {"value": "yes_side", "label": "Yes, side income (under $10k)"},
                    {"value": "no", "label": "No"},
                ],
                reason="Self-employment opens up additional deduction opportunities",
                potential_impact="Home office, vehicle, equipment, and retirement plan deductions",
            ))

            questions.append(SmartQuestion(
                id="income_home_office",
                question="Do you use part of your home exclusively for business?",
                category=QuestionCategory.SELF_EMPLOYMENT,
                priority=QuestionPriority.MEDIUM,
                options=[
                    {"value": "yes_dedicated", "label": "Yes, dedicated space"},
                    {"value": "yes_partial", "label": "Sometimes"},
                    {"value": "no", "label": "No"},
                ],
                reason="Home office deduction can be significant",
                potential_impact="Deduct portion of rent/mortgage, utilities, internet",
                depends_on="income_self_employment",
                show_if_answer="yes_significant,yes_side",
            ))

        return questions

    def _generate_education_questions(self, data: Parsed1040Data) -> List[SmartQuestion]:
        """Generate education-related questions."""
        questions = []
        aotc = data.american_opportunity_credit or Decimal("0")
        agi = data.adjusted_gross_income or Decimal("0")

        # If they didn't claim AOTC, might be eligible
        if aotc == 0 and agi < Decimal("180000"):  # Under phase-out
            questions.append(SmartQuestion(
                id="education_college",
                question="Are you or a dependent currently enrolled in college?",
                category=QuestionCategory.EDUCATION,
                priority=QuestionPriority.MEDIUM,
                options=[
                    {"value": "yes_undergrad", "label": "Yes, undergraduate"},
                    {"value": "yes_grad", "label": "Yes, graduate school"},
                    {"value": "no", "label": "No"},
                ],
                reason="Education expenses may qualify for credits",
                potential_impact="AOTC up to $2,500/student, LLC up to $2,000",
            ))

        # 529 question
        if data.total_dependents and data.total_dependents > 0:
            questions.append(SmartQuestion(
                id="education_529",
                question="Do you contribute to a 529 education savings plan?",
                category=QuestionCategory.EDUCATION,
                priority=QuestionPriority.LOW,
                options=[
                    {"value": "yes", "label": "Yes"},
                    {"value": "no", "label": "No"},
                    {"value": "interested", "label": "No, but interested"},
                ],
                reason="529 plans offer state tax deductions in many states",
                potential_impact="State tax deduction varies by state, plus tax-free growth",
            ))

        return questions

    def _generate_credit_questions(self, data: Parsed1040Data) -> List[SmartQuestion]:
        """Generate credit-related questions."""
        questions = []
        agi = data.adjusted_gross_income or Decimal("0")
        eic = data.earned_income_credit or Decimal("0")

        # Energy credits
        questions.append(SmartQuestion(
            id="credits_energy",
            question="Have you made any energy-efficient home improvements or bought an EV?",
            category=QuestionCategory.CREDITS,
            priority=QuestionPriority.MEDIUM,
            options=[
                {"value": "ev", "label": "Yes, electric vehicle"},
                {"value": "solar", "label": "Yes, solar panels"},
                {"value": "other", "label": "Yes, other improvements"},
                {"value": "no", "label": "No"},
                {"value": "planning", "label": "Planning to soon"},
            ],
            reason="Energy credits can be significant (up to $7,500 for EVs)",
            potential_impact="EV credit up to $7,500, solar credit 30% of cost",
        ))

        # If near EITC threshold
        if eic == 0 and Decimal("20000") < agi < Decimal("65000"):
            questions.append(SmartQuestion(
                id="credits_eitc_check",
                question="Did you know you might qualify for the Earned Income Tax Credit?",
                category=QuestionCategory.CREDITS,
                priority=QuestionPriority.HIGH,
                options=[
                    {"value": "already_reviewed", "label": "Yes, already reviewed"},
                    {"value": "interested", "label": "No, tell me more"},
                    {"value": "not_eligible", "label": "I know I'm not eligible"},
                ],
                reason="EITC is often overlooked and can be worth thousands",
                potential_impact="EITC ranges from $600 to $7,830 depending on children",
            ))

        return questions

    async def generate_questions_with_ai(
        self,
        parsed_data: Parsed1040Data
    ) -> QuestionSet:
        """
        Use OpenAI to generate enhanced, personalized questions.

        Falls back to rule-based if AI unavailable.
        """
        if not self.use_ai or not self._openai_client:
            return self.generate_questions(parsed_data)

        try:
            # Get rule-based questions first
            base_questions = self.generate_questions(parsed_data)

            # Use AI to enhance and personalize
            prompt = self._build_ai_prompt(parsed_data, base_questions)

            response = self._openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a tax advisor helping identify the most important
                        follow-up questions to ask a client. Based on their tax return data,
                        suggest which questions are most likely to uncover tax savings opportunities.
                        Be specific about potential dollar impacts when possible."""
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.3,
            )

            # Parse AI response to enhance questions
            ai_insights = response.choices[0].message.content

            # For now, add AI insights to profile and return base questions
            # Future: parse AI response to reorder/enhance questions
            enhanced = QuestionSet(
                questions=base_questions.questions,
                taxpayer_profile=f"{base_questions.taxpayer_profile} | AI: {ai_insights[:200]}",
                estimated_question_count=base_questions.estimated_question_count,
                categories_covered=base_questions.categories_covered,
            )

            return enhanced

        except Exception as e:
            logger.error(f"AI question generation failed: {e}, falling back to rule-based")
            return self.generate_questions(parsed_data)

    def _build_ai_prompt(
        self,
        data: Parsed1040Data,
        base_questions: QuestionSet
    ) -> str:
        """Build prompt for AI enhancement."""
        return f"""
        Analyze this tax return data and identify the top 3 areas where
        follow-up questions could uncover significant tax savings:

        Tax Return Summary:
        - Filing Status: {data.filing_status.value if data.filing_status else 'Unknown'}
        - AGI: ${float(data.adjusted_gross_income or 0):,.0f}
        - Wages: ${float(data.wages_salaries_tips or 0):,.0f}
        - Dependents: {data.total_dependents or 0}
        - Standard Deduction Used: ${float(data.standard_deduction or 0):,.0f}
        - Itemized: ${float(data.itemized_deductions or 0):,.0f}
        - Child Tax Credit: ${float(data.child_tax_credit or 0):,.0f}
        - Total Tax: ${float(data.total_tax or 0):,.0f}
        - Refund: ${float(data.refund_amount or 0):,.0f}

        Current questions being asked: {[q.question for q in base_questions.questions[:5]]}

        What are the 3 most important areas to explore? Focus on:
        1. Retirement savings opportunities
        2. Credits they might be missing
        3. Deduction strategies

        Be specific about potential dollar savings.
        """
