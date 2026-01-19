"""
Adaptive Question Generator

Generates intelligent, contextual questions based on:
- Extracted document data
- Tax situation complexity
- Missing information gaps
- User's filing status and circumstances

Questions are prioritized by impact on:
- Tax liability calculation accuracy
- Refund optimization opportunities
- Compliance requirements
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from decimal import Decimal


class QuestionPriority(str, Enum):
    """Priority levels for questions."""
    CRITICAL = "critical"    # Required for accurate calculation
    HIGH = "high"           # Significantly impacts result
    MEDIUM = "medium"       # Moderate impact
    LOW = "low"            # Nice to have for optimization


class QuestionCategory(str, Enum):
    """Categories of tax questions."""
    INCOME = "income"
    DEDUCTIONS = "deductions"
    CREDITS = "credits"
    FILING_STATUS = "filing_status"
    DEPENDENTS = "dependents"
    LIFE_EVENTS = "life_events"
    COMPLIANCE = "compliance"
    OPTIMIZATION = "optimization"


@dataclass
class AdaptiveQuestion:
    """A dynamically generated tax question."""
    question_id: str
    question_text: str
    help_text: str
    category: QuestionCategory
    priority: QuestionPriority
    input_type: str  # "boolean", "number", "select", "text", "multi_select"
    options: Optional[List[Dict[str, str]]] = None  # For select types
    default_value: Any = None
    validation: Optional[Dict[str, Any]] = None
    impact_description: str = ""  # How this affects the return
    follow_up_questions: List[str] = field(default_factory=list)  # Question IDs to ask if answer is yes/true
    skip_if: Optional[Dict[str, Any]] = None  # Conditions to skip this question

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question_id": self.question_id,
            "question_text": self.question_text,
            "help_text": self.help_text,
            "category": self.category.value,
            "priority": self.priority.value,
            "input_type": self.input_type,
            "options": self.options,
            "default_value": self.default_value,
            "validation": self.validation,
            "impact_description": self.impact_description,
            "follow_up_questions": self.follow_up_questions,
        }


class AdaptiveQuestionGenerator:
    """
    Generates contextual questions based on tax situation.

    Key principles:
    1. Only ask what we don't already know
    2. Prioritize questions that impact the result most
    3. Group related questions together
    4. Adapt based on user's answers
    """

    # Question templates organized by trigger conditions
    QUESTION_TEMPLATES = {
        # Filing Status Questions
        "confirm_filing_status": AdaptiveQuestion(
            question_id="confirm_filing_status",
            question_text="What is your filing status for this year?",
            help_text="Your filing status affects your tax brackets and standard deduction",
            category=QuestionCategory.FILING_STATUS,
            priority=QuestionPriority.CRITICAL,
            input_type="select",
            options=[
                {"value": "single", "label": "Single"},
                {"value": "married_joint", "label": "Married Filing Jointly"},
                {"value": "married_separate", "label": "Married Filing Separately"},
                {"value": "head_of_household", "label": "Head of Household"},
                {"value": "widow", "label": "Qualifying Surviving Spouse"},
            ],
            impact_description="Determines tax brackets and standard deduction amount",
        ),

        "marital_status_changed": AdaptiveQuestion(
            question_id="marital_status_changed",
            question_text="Did your marital status change during the year?",
            help_text="If you got married or divorced, it affects your filing options",
            category=QuestionCategory.LIFE_EVENTS,
            priority=QuestionPriority.HIGH,
            input_type="boolean",
            follow_up_questions=["marriage_date", "divorce_date"],
            impact_description="May affect filing status and certain credits",
        ),

        # Dependent Questions
        "has_dependents": AdaptiveQuestion(
            question_id="has_dependents",
            question_text="Do you have any dependents (children or qualifying relatives)?",
            help_text="Dependents can qualify you for valuable tax credits",
            category=QuestionCategory.DEPENDENTS,
            priority=QuestionPriority.HIGH,
            input_type="boolean",
            follow_up_questions=["num_children_under_17", "num_other_dependents"],
            impact_description="May qualify you for Child Tax Credit (up to $2,000/child)",
        ),

        "num_children_under_17": AdaptiveQuestion(
            question_id="num_children_under_17",
            question_text="How many children under age 17 do you have?",
            help_text="Children under 17 qualify for the Child Tax Credit",
            category=QuestionCategory.DEPENDENTS,
            priority=QuestionPriority.HIGH,
            input_type="number",
            validation={"min": 0, "max": 10},
            impact_description="Each qualifying child = up to $2,000 credit",
        ),

        "childcare_expenses": AdaptiveQuestion(
            question_id="childcare_expenses",
            question_text="Did you pay for childcare or dependent care expenses?",
            help_text="Work-related care expenses may qualify for a tax credit",
            category=QuestionCategory.CREDITS,
            priority=QuestionPriority.MEDIUM,
            input_type="boolean",
            follow_up_questions=["childcare_amount"],
            impact_description="May qualify for Child and Dependent Care Credit",
        ),

        # Income Questions
        "has_additional_income": AdaptiveQuestion(
            question_id="has_additional_income",
            question_text="Did you have any income not shown on your W-2 or 1099 forms?",
            help_text="This includes cash payments, side gigs, cryptocurrency, etc.",
            category=QuestionCategory.INCOME,
            priority=QuestionPriority.CRITICAL,
            input_type="boolean",
            follow_up_questions=["additional_income_types"],
            impact_description="All income must be reported for accurate calculation",
        ),

        "has_self_employment": AdaptiveQuestion(
            question_id="has_self_employment",
            question_text="Did you do any freelance, gig, or self-employment work?",
            help_text="Includes Uber/Lyft, Etsy sales, consulting, etc.",
            category=QuestionCategory.INCOME,
            priority=QuestionPriority.HIGH,
            input_type="boolean",
            follow_up_questions=["self_employment_income", "has_business_expenses"],
            impact_description="Subject to self-employment tax but allows business deductions",
        ),

        "has_rental_income": AdaptiveQuestion(
            question_id="has_rental_income",
            question_text="Did you receive any rental income from property?",
            help_text="Income from renting out a home, apartment, or room",
            category=QuestionCategory.INCOME,
            priority=QuestionPriority.HIGH,
            input_type="boolean",
            follow_up_questions=["rental_income_amount", "rental_expenses"],
            impact_description="Rental income is taxable but expenses are deductible",
        ),

        "has_crypto": AdaptiveQuestion(
            question_id="has_crypto",
            question_text="Did you sell, trade, or receive cryptocurrency?",
            help_text="Includes Bitcoin, Ethereum, NFTs, and other digital assets",
            category=QuestionCategory.INCOME,
            priority=QuestionPriority.HIGH,
            input_type="boolean",
            follow_up_questions=["crypto_transactions"],
            impact_description="Crypto sales are taxable events",
        ),

        "has_stock_sales": AdaptiveQuestion(
            question_id="has_stock_sales",
            question_text="Did you sell any stocks, bonds, or mutual funds?",
            help_text="Capital gains from investment sales are taxable",
            category=QuestionCategory.INCOME,
            priority=QuestionPriority.HIGH,
            input_type="boolean",
            skip_if={"has_1099_b": True},
            impact_description="May result in capital gains or losses",
        ),

        # Deduction Questions
        "itemize_or_standard": AdaptiveQuestion(
            question_id="itemize_or_standard",
            question_text="Do you want to itemize deductions or take the standard deduction?",
            help_text="Most people benefit from the standard deduction",
            category=QuestionCategory.DEDUCTIONS,
            priority=QuestionPriority.MEDIUM,
            input_type="select",
            options=[
                {"value": "standard", "label": "Standard Deduction (Recommended for most)"},
                {"value": "itemize", "label": "Itemize Deductions"},
                {"value": "unsure", "label": "Not sure - help me decide"},
            ],
            follow_up_questions=["mortgage_interest", "property_taxes", "charitable_donations"],
            impact_description="Itemizing only helps if deductions exceed standard amount",
        ),

        "has_mortgage": AdaptiveQuestion(
            question_id="has_mortgage",
            question_text="Do you pay mortgage interest on your home?",
            help_text="Mortgage interest is deductible if you itemize",
            category=QuestionCategory.DEDUCTIONS,
            priority=QuestionPriority.MEDIUM,
            input_type="boolean",
            skip_if={"has_1098": True},
            follow_up_questions=["mortgage_interest_amount"],
            impact_description="May help if you itemize deductions",
        ),

        "has_student_loans": AdaptiveQuestion(
            question_id="has_student_loans",
            question_text="Did you pay student loan interest this year?",
            help_text="Up to $2,500 in student loan interest is deductible",
            category=QuestionCategory.DEDUCTIONS,
            priority=QuestionPriority.MEDIUM,
            input_type="boolean",
            skip_if={"has_1098_e": True},
            follow_up_questions=["student_loan_interest"],
            impact_description="Reduces taxable income by up to $2,500",
        ),

        "charitable_donations": AdaptiveQuestion(
            question_id="charitable_donations",
            question_text="Did you make charitable donations this year?",
            help_text="Cash and property donations to qualified organizations",
            category=QuestionCategory.DEDUCTIONS,
            priority=QuestionPriority.LOW,
            input_type="boolean",
            follow_up_questions=["donation_amount"],
            impact_description="Deductible if you itemize",
        ),

        # Credit Questions
        "has_education_expenses": AdaptiveQuestion(
            question_id="has_education_expenses",
            question_text="Did you pay for college tuition or education expenses?",
            help_text="May qualify for American Opportunity or Lifetime Learning Credit",
            category=QuestionCategory.CREDITS,
            priority=QuestionPriority.MEDIUM,
            input_type="boolean",
            skip_if={"has_1098_t": True},
            follow_up_questions=["education_expenses_amount"],
            impact_description="Up to $2,500 credit per student",
        ),

        "has_retirement_contributions": AdaptiveQuestion(
            question_id="has_retirement_contributions",
            question_text="Did you contribute to a traditional IRA or retirement account?",
            help_text="May be deductible and qualify for Saver's Credit",
            category=QuestionCategory.CREDITS,
            priority=QuestionPriority.MEDIUM,
            input_type="boolean",
            follow_up_questions=["ira_contribution_amount"],
            impact_description="Reduces taxable income and may qualify for credit",
        ),

        "has_hsa": AdaptiveQuestion(
            question_id="has_hsa",
            question_text="Did you contribute to a Health Savings Account (HSA)?",
            help_text="HSA contributions are tax-deductible",
            category=QuestionCategory.DEDUCTIONS,
            priority=QuestionPriority.MEDIUM,
            input_type="boolean",
            skip_if={"has_1099_sa": True},
            follow_up_questions=["hsa_contribution_amount"],
            impact_description="Reduces taxable income",
        ),

        "has_energy_improvements": AdaptiveQuestion(
            question_id="has_energy_improvements",
            question_text="Did you make energy-efficient improvements to your home?",
            help_text="Solar panels, heat pumps, windows, etc.",
            category=QuestionCategory.CREDITS,
            priority=QuestionPriority.LOW,
            input_type="boolean",
            follow_up_questions=["energy_improvement_type"],
            impact_description="May qualify for Residential Clean Energy Credit",
        ),

        # Compliance Questions
        "received_advance_ctc": AdaptiveQuestion(
            question_id="received_advance_ctc",
            question_text="Did you receive advance Child Tax Credit payments in 2024?",
            help_text="Monthly payments sent by IRS - need to reconcile",
            category=QuestionCategory.COMPLIANCE,
            priority=QuestionPriority.HIGH,
            input_type="boolean",
            follow_up_questions=["advance_ctc_amount"],
            impact_description="May affect your refund amount",
        ),

        "health_insurance_all_year": AdaptiveQuestion(
            question_id="health_insurance_all_year",
            question_text="Did you have health insurance coverage all year?",
            help_text="Some states have health insurance requirements",
            category=QuestionCategory.COMPLIANCE,
            priority=QuestionPriority.LOW,
            input_type="boolean",
            impact_description="May affect state tax return",
        ),
    }

    def __init__(self):
        pass

    def generate_questions(
        self,
        extracted_data: Dict[str, Any],
        documents: List[Dict[str, Any]],
        filing_status: str,
        user_answers: Optional[Dict[str, Any]] = None,
        complexity_level: str = "simple",
    ) -> List[AdaptiveQuestion]:
        """
        Generate contextual questions based on the tax situation.

        Args:
            extracted_data: Data extracted from documents
            documents: List of processed documents
            filing_status: User's filing status
            user_answers: Previously answered questions
            complexity_level: Complexity level (simple/moderate/complex/professional)

        Returns:
            Prioritized list of questions to ask
        """
        user_answers = user_answers or {}
        questions = []

        # Get document types we have
        doc_types = set(d.get("type", "") for d in documents)

        # Track what data we already have
        has_data = {
            "has_w2": "w2" in doc_types,
            "has_1099_nec": "1099_nec" in doc_types,
            "has_1099_int": "1099_int" in doc_types,
            "has_1099_div": "1099_div" in doc_types,
            "has_1099_b": "1099_b" in doc_types,
            "has_1098": "1098" in doc_types,
            "has_1098_t": "1098_t" in doc_types,
            "has_1098_e": "1098_e" in doc_types,
            "has_1099_sa": "1099_sa" in doc_types,
            "wages": extracted_data.get("wages", 0) > 0,
            "interest_income": extracted_data.get("interest_income", 0) > 0,
            "dividends": extracted_data.get("ordinary_dividends", 0) > 0,
        }

        # 1. Filing Status - Always confirm if not provided
        if "confirm_filing_status" not in user_answers:
            q = self.QUESTION_TEMPLATES["confirm_filing_status"]
            q.default_value = filing_status
            questions.append(q)

        # 2. Dependents - Important for credits
        if "has_dependents" not in user_answers:
            questions.append(self.QUESTION_TEMPLATES["has_dependents"])
        elif user_answers.get("has_dependents"):
            if "num_children_under_17" not in user_answers:
                questions.append(self.QUESTION_TEMPLATES["num_children_under_17"])
            if "childcare_expenses" not in user_answers:
                questions.append(self.QUESTION_TEMPLATES["childcare_expenses"])

        # 3. Additional Income Sources
        if not has_data["has_1099_nec"] and "has_self_employment" not in user_answers:
            questions.append(self.QUESTION_TEMPLATES["has_self_employment"])

        if "has_rental_income" not in user_answers:
            questions.append(self.QUESTION_TEMPLATES["has_rental_income"])

        if "has_crypto" not in user_answers:
            questions.append(self.QUESTION_TEMPLATES["has_crypto"])

        if not has_data["has_1099_b"] and "has_stock_sales" not in user_answers:
            questions.append(self.QUESTION_TEMPLATES["has_stock_sales"])

        # 4. Deductions - Based on complexity
        if complexity_level in ["moderate", "complex", "professional"]:
            if "itemize_or_standard" not in user_answers:
                questions.append(self.QUESTION_TEMPLATES["itemize_or_standard"])

            if not has_data["has_1098"] and "has_mortgage" not in user_answers:
                questions.append(self.QUESTION_TEMPLATES["has_mortgage"])

        # 5. Education and Retirement
        if not has_data["has_1098_t"] and "has_education_expenses" not in user_answers:
            questions.append(self.QUESTION_TEMPLATES["has_education_expenses"])

        if "has_retirement_contributions" not in user_answers:
            questions.append(self.QUESTION_TEMPLATES["has_retirement_contributions"])

        if not has_data["has_1099_sa"] and "has_hsa" not in user_answers:
            questions.append(self.QUESTION_TEMPLATES["has_hsa"])

        # 6. Student Loans
        if not has_data["has_1098_e"] and "has_student_loans" not in user_answers:
            questions.append(self.QUESTION_TEMPLATES["has_student_loans"])

        # 7. Low priority questions for complex returns
        if complexity_level in ["complex", "professional"]:
            if "charitable_donations" not in user_answers:
                questions.append(self.QUESTION_TEMPLATES["charitable_donations"])

            if "has_energy_improvements" not in user_answers:
                questions.append(self.QUESTION_TEMPLATES["has_energy_improvements"])

        # Sort by priority
        priority_order = {
            QuestionPriority.CRITICAL: 0,
            QuestionPriority.HIGH: 1,
            QuestionPriority.MEDIUM: 2,
            QuestionPriority.LOW: 3,
        }
        questions.sort(key=lambda q: priority_order.get(q.priority, 99))

        return questions

    def get_question_by_id(self, question_id: str) -> Optional[AdaptiveQuestion]:
        """Get a specific question by ID."""
        return self.QUESTION_TEMPLATES.get(question_id)

    def get_follow_up_questions(
        self,
        question_id: str,
        answer: Any,
    ) -> List[AdaptiveQuestion]:
        """Get follow-up questions based on an answer."""
        question = self.QUESTION_TEMPLATES.get(question_id)
        if not question:
            return []

        # Only show follow-ups if answer is positive/truthy
        if not answer or answer == "no" or answer == False:
            return []

        follow_ups = []
        for fq_id in question.follow_up_questions:
            fq = self.QUESTION_TEMPLATES.get(fq_id)
            if fq:
                follow_ups.append(fq)

        return follow_ups

    def estimate_remaining_questions(
        self,
        extracted_data: Dict[str, Any],
        documents: List[Dict[str, Any]],
        user_answers: Dict[str, Any],
        complexity_level: str,
    ) -> int:
        """Estimate how many questions remain."""
        questions = self.generate_questions(
            extracted_data=extracted_data,
            documents=documents,
            filing_status=user_answers.get("confirm_filing_status", "single"),
            user_answers=user_answers,
            complexity_level=complexity_level,
        )
        return len(questions)

    def get_questions_by_category(
        self,
        questions: List[AdaptiveQuestion],
    ) -> Dict[str, List[AdaptiveQuestion]]:
        """Group questions by category."""
        grouped = {}
        for q in questions:
            category = q.category.value
            if category not in grouped:
                grouped[category] = []
            grouped[category].append(q)
        return grouped


def generate_smart_questions(
    extracted_data: Dict[str, Any],
    documents: List[Dict[str, Any]],
    filing_status: str = "single",
    user_answers: Optional[Dict[str, Any]] = None,
    complexity_level: str = "simple",
) -> List[Dict[str, Any]]:
    """
    Convenience function to generate questions.

    Returns list of question dicts ready for API response.
    """
    generator = AdaptiveQuestionGenerator()
    questions = generator.generate_questions(
        extracted_data=extracted_data,
        documents=documents,
        filing_status=filing_status,
        user_answers=user_answers,
        complexity_level=complexity_level,
    )
    return [q.to_dict() for q in questions]
