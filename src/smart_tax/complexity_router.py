"""
Complexity Router

Assesses tax situation complexity and routes users to appropriate flows:
- SIMPLE: W-2 only, standard deduction (3-5 minute flow)
- MODERATE: Multiple income sources (8-12 minute flow)
- COMPLEX: Self-employment, investments, itemized (15-20 minute flow)
- PROFESSIONAL: Needs CPA review
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum


class ComplexityFactor(str, Enum):
    """Factors that increase tax complexity."""
    SELF_EMPLOYMENT = "self_employment"
    RENTAL_INCOME = "rental_income"
    INVESTMENT_INCOME = "investment_income"
    MULTIPLE_W2S = "multiple_w2s"
    ITEMIZED_DEDUCTIONS = "itemized_deductions"
    CAPITAL_GAINS = "capital_gains"
    FOREIGN_INCOME = "foreign_income"
    CRYPTO_TRANSACTIONS = "crypto_transactions"
    HSA_FSA = "hsa_fsa"
    EDUCATION_CREDITS = "education_credits"
    DEPENDENTS = "dependents"
    MARRIED_SEPARATE = "married_separate"
    HIGH_INCOME = "high_income"
    AMT_RISK = "amt_risk"
    BUSINESS_EXPENSES = "business_expenses"


@dataclass
class ComplexityAssessment:
    """Result of complexity assessment."""
    level: str  # simple, moderate, complex, professional
    score: int  # 0-100
    factors: List[ComplexityFactor]
    factor_details: Dict[str, Any]
    estimated_time_minutes: Tuple[int, int]  # (min, max)
    recommended_flow: str
    cpa_recommended: bool
    cpa_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level,
            "score": self.score,
            "factors": [f.value for f in self.factors],
            "factor_details": self.factor_details,
            "estimated_time_minutes": {
                "min": self.estimated_time_minutes[0],
                "max": self.estimated_time_minutes[1],
            },
            "recommended_flow": self.recommended_flow,
            "cpa_recommended": self.cpa_recommended,
            "cpa_reason": self.cpa_reason,
        }


@dataclass
class RoutingDecision:
    """Decision on how to route the user."""
    flow: str  # "smart_simple", "smart_moderate", "smart_complex", "cpa_handoff"
    assessment: ComplexityAssessment
    next_steps: List[str]
    questions_needed: int
    can_self_file: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flow": self.flow,
            "assessment": self.assessment.to_dict(),
            "next_steps": self.next_steps,
            "questions_needed": self.questions_needed,
            "can_self_file": self.can_self_file,
        }


class ComplexityRouter:
    """
    Routes users to appropriate tax preparation flows based on
    their situation complexity.
    """

    # Complexity weights for each factor
    FACTOR_WEIGHTS = {
        ComplexityFactor.SELF_EMPLOYMENT: 25,
        ComplexityFactor.RENTAL_INCOME: 20,
        ComplexityFactor.INVESTMENT_INCOME: 10,
        ComplexityFactor.MULTIPLE_W2S: 5,
        ComplexityFactor.ITEMIZED_DEDUCTIONS: 10,
        ComplexityFactor.CAPITAL_GAINS: 15,
        ComplexityFactor.FOREIGN_INCOME: 30,
        ComplexityFactor.CRYPTO_TRANSACTIONS: 15,
        ComplexityFactor.HSA_FSA: 5,
        ComplexityFactor.EDUCATION_CREDITS: 5,
        ComplexityFactor.DEPENDENTS: 5,
        ComplexityFactor.MARRIED_SEPARATE: 10,
        ComplexityFactor.HIGH_INCOME: 15,
        ComplexityFactor.AMT_RISK: 20,
        ComplexityFactor.BUSINESS_EXPENSES: 15,
    }

    # Thresholds for complexity levels
    THRESHOLDS = {
        "simple": 15,      # 0-15
        "moderate": 35,    # 16-35
        "complex": 60,     # 36-60
        "professional": 100,  # 61+
    }

    # Estimated times by complexity
    TIME_ESTIMATES = {
        "simple": (3, 5),
        "moderate": (8, 12),
        "complex": (15, 20),
        "professional": (30, 60),
    }

    def __init__(self):
        pass

    def assess_complexity(
        self,
        documents: List[Dict[str, Any]],
        extracted_data: Dict[str, Any],
        filing_status: str = "single",
        user_inputs: Optional[Dict[str, Any]] = None,
    ) -> ComplexityAssessment:
        """
        Assess the complexity of a tax situation.

        Args:
            documents: List of processed documents
            extracted_data: Aggregated extracted data
            filing_status: User's filing status
            user_inputs: Additional user-provided information

        Returns:
            ComplexityAssessment with complexity level and factors
        """
        user_inputs = user_inputs or {}
        factors = []
        factor_details = {}
        score = 0

        # Check document types for income sources
        doc_types = [d.get("type", "") for d in documents]
        w2_count = doc_types.count("w2")

        # Multiple W-2s
        if w2_count > 1:
            factors.append(ComplexityFactor.MULTIPLE_W2S)
            factor_details["w2_count"] = w2_count
            score += self.FACTOR_WEIGHTS[ComplexityFactor.MULTIPLE_W2S]

        # Self-employment (1099-NEC)
        if "1099_nec" in doc_types:
            factors.append(ComplexityFactor.SELF_EMPLOYMENT)
            nec_amount = extracted_data.get("nonemployee_compensation", 0)
            factor_details["self_employment_income"] = nec_amount
            score += self.FACTOR_WEIGHTS[ComplexityFactor.SELF_EMPLOYMENT]

            # Business expenses compound complexity
            if user_inputs.get("has_business_expenses"):
                factors.append(ComplexityFactor.BUSINESS_EXPENSES)
                score += self.FACTOR_WEIGHTS[ComplexityFactor.BUSINESS_EXPENSES]

        # Investment income
        if "1099_div" in doc_types or "1099_int" in doc_types:
            factors.append(ComplexityFactor.INVESTMENT_INCOME)
            div_amount = extracted_data.get("ordinary_dividends", 0)
            int_amount = extracted_data.get("interest_income", 0)
            factor_details["investment_income"] = div_amount + int_amount
            score += self.FACTOR_WEIGHTS[ComplexityFactor.INVESTMENT_INCOME]

        # Capital gains
        if "1099_b" in doc_types or user_inputs.get("has_stock_sales"):
            factors.append(ComplexityFactor.CAPITAL_GAINS)
            factor_details["has_capital_gains"] = True
            score += self.FACTOR_WEIGHTS[ComplexityFactor.CAPITAL_GAINS]

        # Crypto transactions
        if user_inputs.get("has_crypto"):
            factors.append(ComplexityFactor.CRYPTO_TRANSACTIONS)
            factor_details["has_crypto"] = True
            score += self.FACTOR_WEIGHTS[ComplexityFactor.CRYPTO_TRANSACTIONS]

        # Rental income
        if user_inputs.get("has_rental_income"):
            factors.append(ComplexityFactor.RENTAL_INCOME)
            factor_details["has_rental_income"] = True
            score += self.FACTOR_WEIGHTS[ComplexityFactor.RENTAL_INCOME]

        # Foreign income
        if user_inputs.get("has_foreign_income"):
            factors.append(ComplexityFactor.FOREIGN_INCOME)
            factor_details["has_foreign_income"] = True
            score += self.FACTOR_WEIGHTS[ComplexityFactor.FOREIGN_INCOME]

        # Itemized deductions
        if user_inputs.get("will_itemize"):
            factors.append(ComplexityFactor.ITEMIZED_DEDUCTIONS)
            factor_details["will_itemize"] = True
            score += self.FACTOR_WEIGHTS[ComplexityFactor.ITEMIZED_DEDUCTIONS]

        # HSA/FSA
        if "1099_sa" in doc_types or user_inputs.get("has_hsa"):
            factors.append(ComplexityFactor.HSA_FSA)
            factor_details["has_hsa_fsa"] = True
            score += self.FACTOR_WEIGHTS[ComplexityFactor.HSA_FSA]

        # Education credits
        if "1098_t" in doc_types or user_inputs.get("has_education_expenses"):
            factors.append(ComplexityFactor.EDUCATION_CREDITS)
            factor_details["has_education"] = True
            score += self.FACTOR_WEIGHTS[ComplexityFactor.EDUCATION_CREDITS]

        # Dependents
        num_dependents = user_inputs.get("num_dependents", 0)
        if num_dependents > 0:
            factors.append(ComplexityFactor.DEPENDENTS)
            factor_details["num_dependents"] = num_dependents
            score += self.FACTOR_WEIGHTS[ComplexityFactor.DEPENDENTS]

        # Filing status
        if filing_status == "married_separate":
            factors.append(ComplexityFactor.MARRIED_SEPARATE)
            factor_details["filing_status"] = filing_status
            score += self.FACTOR_WEIGHTS[ComplexityFactor.MARRIED_SEPARATE]

        # High income
        total_income = sum([
            extracted_data.get("wages", 0),
            extracted_data.get("interest_income", 0),
            extracted_data.get("ordinary_dividends", 0),
            extracted_data.get("nonemployee_compensation", 0),
        ])

        if total_income > 400000:
            factors.append(ComplexityFactor.HIGH_INCOME)
            factors.append(ComplexityFactor.AMT_RISK)
            factor_details["high_income"] = True
            factor_details["total_income"] = total_income
            score += self.FACTOR_WEIGHTS[ComplexityFactor.HIGH_INCOME]
            score += self.FACTOR_WEIGHTS[ComplexityFactor.AMT_RISK]
        elif total_income > 200000:
            factors.append(ComplexityFactor.HIGH_INCOME)
            factor_details["high_income"] = True
            factor_details["total_income"] = total_income
            score += self.FACTOR_WEIGHTS[ComplexityFactor.HIGH_INCOME]

        # Determine complexity level
        if score <= self.THRESHOLDS["simple"]:
            level = "simple"
        elif score <= self.THRESHOLDS["moderate"]:
            level = "moderate"
        elif score <= self.THRESHOLDS["complex"]:
            level = "complex"
        else:
            level = "professional"

        # Check for automatic CPA recommendation
        cpa_recommended = False
        cpa_reason = None

        if ComplexityFactor.FOREIGN_INCOME in factors:
            cpa_recommended = True
            cpa_reason = "Foreign income requires specialized knowledge for tax treaty and FBAR compliance"
        elif total_income > 500000:
            cpa_recommended = True
            cpa_reason = "High income situations benefit from professional tax planning"
        elif len(factors) > 5:
            cpa_recommended = True
            cpa_reason = "Multiple complexity factors suggest professional review would be beneficial"

        return ComplexityAssessment(
            level=level,
            score=score,
            factors=factors,
            factor_details=factor_details,
            estimated_time_minutes=self.TIME_ESTIMATES[level],
            recommended_flow=f"smart_{level}" if level != "professional" else "cpa_handoff",
            cpa_recommended=cpa_recommended or level == "professional",
            cpa_reason=cpa_reason,
        )

    def route_user(
        self,
        assessment: ComplexityAssessment,
    ) -> RoutingDecision:
        """
        Determine the routing decision based on complexity assessment.
        """
        # Determine flow
        if assessment.cpa_recommended and assessment.level == "professional":
            flow = "cpa_handoff"
            can_self_file = False
        else:
            flow = f"smart_{assessment.level}"
            can_self_file = True

        # Determine next steps
        next_steps = self._get_next_steps(assessment.level, assessment.factors)

        # Estimate questions needed
        questions_needed = self._estimate_questions(assessment)

        return RoutingDecision(
            flow=flow,
            assessment=assessment,
            next_steps=next_steps,
            questions_needed=questions_needed,
            can_self_file=can_self_file,
        )

    def _get_next_steps(
        self,
        level: str,
        factors: List[ComplexityFactor]
    ) -> List[str]:
        """Get next steps based on complexity level."""
        steps = []

        if level == "simple":
            steps = [
                "Review extracted W-2 information",
                "Confirm filing status",
                "View your estimated refund",
                "Download or e-file your return",
            ]
        elif level == "moderate":
            steps = [
                "Review all extracted income",
                "Answer a few questions about deductions",
                "Review tax-saving opportunities",
                "Confirm your return and file",
            ]
        elif level == "complex":
            steps = [
                "Review all income sources",
                "Complete Schedule C (if self-employed)",
                "Review investment transactions",
                "Answer questions about deductions and credits",
                "Review detailed tax breakdown",
                "Consider recommended strategies",
            ]
        else:  # professional
            steps = [
                "We'll prepare your documents for CPA review",
                "A tax professional will contact you",
                "Review and approve CPA recommendations",
                "Sign and file with professional assistance",
            ]

        # Add factor-specific steps
        if ComplexityFactor.SELF_EMPLOYMENT in factors and level != "professional":
            steps.insert(1, "Enter business income and expenses")

        if ComplexityFactor.CRYPTO_TRANSACTIONS in factors and level != "professional":
            steps.insert(2, "Import or enter crypto transactions")

        return steps

    def _estimate_questions(self, assessment: ComplexityAssessment) -> int:
        """Estimate number of questions user will need to answer."""
        base_questions = {
            "simple": 3,
            "moderate": 8,
            "complex": 15,
            "professional": 20,
        }

        questions = base_questions.get(assessment.level, 10)

        # Reduce if we have good data
        if len(assessment.factor_details) > 3:
            questions = max(2, questions - 2)

        return questions


def assess_and_route(
    documents: List[Dict[str, Any]],
    extracted_data: Dict[str, Any],
    filing_status: str = "single",
    user_inputs: Optional[Dict[str, Any]] = None,
) -> RoutingDecision:
    """
    Convenience function to assess complexity and get routing decision.
    """
    router = ComplexityRouter()
    assessment = router.assess_complexity(
        documents=documents,
        extracted_data=extracted_data,
        filing_status=filing_status,
        user_inputs=user_inputs,
    )
    return router.route_user(assessment)
