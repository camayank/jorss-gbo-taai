"""
Form 8867: Paid Preparer's Due Diligence Checklist.

Required for paid preparers claiming EITC, CTC/ACTC/ODC, AOTC, or HOH filing status.
Penalty: $600 per failure (2025) per IRC §6695(g).

This is a SCAFFOLD implementation for Phase 1.
Full workflow integration is deferred to Phase 2.

References:
- IRS Form 8867 and Instructions
- IRC §6695(g) - Due diligence requirements for paid preparers
- IRS Pub. 4687 - EITC Due Diligence Training Module
"""

from enum import Enum
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field


class CreditType(str, Enum):
    """Credits requiring Form 8867 due diligence."""
    EITC = "eitc"      # Earned Income Tax Credit
    CTC = "ctc"        # Child Tax Credit
    ACTC = "actc"      # Additional Child Tax Credit
    ODC = "odc"        # Other Dependent Credit
    AOTC = "aotc"      # American Opportunity Tax Credit
    HOH = "hoh"        # Head of Household filing status


class DueDiligenceQuestion(BaseModel):
    """Individual due diligence question/requirement."""

    question_id: str = Field(..., description="Unique identifier for the question")
    question_text: str = Field(..., description="The due diligence question")
    credit_types: List[CreditType] = Field(
        default_factory=list,
        description="Credit types this question applies to"
    )
    answer: Optional[bool] = Field(
        default=None,
        description="Preparer's answer (True=Yes, False=No, None=Unanswered)"
    )
    notes: str = Field(
        default="",
        description="Preparer notes for this question"
    )


# Standard due diligence questions per Form 8867 instructions
STANDARD_DUE_DILIGENCE_QUESTIONS = [
    DueDiligenceQuestion(
        question_id="knowledge_1",
        question_text="Did you ask the taxpayer about the information you used to determine eligibility?",
        credit_types=[CreditType.EITC, CreditType.CTC, CreditType.ACTC, CreditType.ODC, CreditType.AOTC, CreditType.HOH],
    ),
    DueDiligenceQuestion(
        question_id="knowledge_2",
        question_text="Did you document the questions you asked and the taxpayer's responses?",
        credit_types=[CreditType.EITC, CreditType.CTC, CreditType.ACTC, CreditType.ODC, CreditType.AOTC, CreditType.HOH],
    ),
    DueDiligenceQuestion(
        question_id="eligibility_1",
        question_text="Did you review information to determine if the taxpayer is eligible for the credit(s)?",
        credit_types=[CreditType.EITC, CreditType.CTC, CreditType.ACTC, CreditType.ODC, CreditType.AOTC],
    ),
    DueDiligenceQuestion(
        question_id="hoh_1",
        question_text="Did you determine if the taxpayer has a qualifying person for HOH status?",
        credit_types=[CreditType.HOH],
    ),
]


class Form8867(BaseModel):
    """
    IRS Form 8867: Paid Preparer's Due Diligence Checklist.

    This scaffold tracks due diligence requirements for paid preparers
    claiming EITC, CTC/ACTC/ODC, AOTC, or HOH filing status.

    Phase 1: Data model and validation
    Phase 2: Integration with filing workflow (future)
    """

    # Tax year
    tax_year: int = Field(default=2025, description="Tax year for this form")

    # Preparer identification
    preparer_name: str = Field(default="", description="Paid preparer's name")
    preparer_ptin: str = Field(
        default="",
        description="Preparer Tax Identification Number (PTIN)"
    )
    firm_name: str = Field(default="", description="Firm name if applicable")
    firm_ein: str = Field(default="", description="Firm EIN if applicable")

    # Credits claimed on this return
    credits_claimed: List[CreditType] = Field(
        default_factory=list,
        description="Credits requiring due diligence on this return"
    )

    # Part I: Due Diligence Requirements (simplified for scaffold)
    knowledge_obtained: bool = Field(
        default=False,
        description="Preparer obtained knowledge about taxpayer's eligibility"
    )

    # Part II: Knowledge Documentation
    documents_reviewed: bool = Field(
        default=False,
        description="Preparer reviewed required documents"
    )
    document_list: List[str] = Field(
        default_factory=list,
        description="List of documents reviewed"
    )

    # Part III: Record Retention
    record_retention_acknowledged: bool = Field(
        default=False,
        description="Preparer acknowledges record retention requirements"
    )

    # Detailed questions (for full implementation)
    questions: List[DueDiligenceQuestion] = Field(
        default_factory=list,
        description="Individual due diligence questions"
    )

    # Notes and comments
    preparer_notes: str = Field(
        default="",
        description="Additional preparer notes"
    )

    # Penalty rate for 2025
    PENALTY_PER_FAILURE: float = 600.0

    def validate_completeness(self) -> Tuple[bool, List[str]]:
        """
        Validate that all required due diligence is complete.

        Returns:
            Tuple of (is_complete, list_of_missing_items)
        """
        missing = []

        if not self.preparer_name:
            missing.append("Preparer name required")

        if not self.preparer_ptin:
            missing.append("PTIN required")

        if not self.credits_claimed:
            missing.append("No credits specified - form may not be required")

        if not self.knowledge_obtained:
            missing.append("Part I: Knowledge about eligibility not confirmed")

        if not self.documents_reviewed:
            missing.append("Part II: Document review not confirmed")

        if not self.record_retention_acknowledged:
            missing.append("Part III: Record retention not acknowledged")

        is_complete = len(missing) == 0
        return is_complete, missing

    def calculate_potential_penalty(self) -> float:
        """
        Calculate potential penalty for incomplete due diligence.

        Per IRC §6695(g): $600 per failure for 2025.
        Each credit type is a separate potential failure.

        Returns:
            Total potential penalty amount
        """
        if not self.credits_claimed:
            return 0.0

        # Each credit type is a separate $600 penalty
        return len(self.credits_claimed) * self.PENALTY_PER_FAILURE

    def get_applicable_questions(self) -> List[DueDiligenceQuestion]:
        """
        Get due diligence questions applicable to claimed credits.

        Returns:
            List of questions that apply to the credits on this return
        """
        applicable = []
        for question in STANDARD_DUE_DILIGENCE_QUESTIONS:
            for credit in self.credits_claimed:
                if credit in question.credit_types:
                    applicable.append(question)
                    break
        return applicable

    def generate_checklist_summary(self) -> dict:
        """Generate summary for preparer review."""
        is_complete, missing = self.validate_completeness()

        return {
            'tax_year': self.tax_year,
            'preparer': {
                'name': self.preparer_name,
                'ptin': self.preparer_ptin,
                'firm': self.firm_name,
            },
            'credits_claimed': [c.value for c in self.credits_claimed],
            'is_complete': is_complete,
            'missing_items': missing,
            'potential_penalty': self.calculate_potential_penalty(),
            'documents_reviewed': self.document_list,
        }
