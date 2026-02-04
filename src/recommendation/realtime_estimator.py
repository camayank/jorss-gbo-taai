"""
Real-Time Tax Estimator

Provides instant tax estimates from minimal data, enabling the document-first
Smart Tax flow where users see feedback immediately after uploading a W-2.

Key Features:
- Instant refund/owed estimates from W-2 data alone
- Confidence bands that narrow as more data is added
- Progressive estimation as documents are added
- Quick opportunity detection for major savings
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from datetime import datetime
from calculator.decimal_math import money, to_decimal


class EstimateConfidence(str, Enum):
    """Confidence level for tax estimates."""
    HIGH = "high"           # All major data present
    MEDIUM = "medium"       # Core data present, some assumptions
    LOW = "low"             # Limited data, wide confidence band
    PRELIMINARY = "preliminary"  # Very rough estimate


@dataclass
class TaxEstimate:
    """Real-time tax estimate with confidence bands."""
    # Primary estimate
    refund_or_owed: float       # Positive = refund, negative = owed
    likely_amount: float        # Most likely outcome

    # Confidence band
    low_estimate: float         # Conservative (worst case)
    high_estimate: float        # Optimistic (best case)
    confidence_score: float     # 0-100
    confidence_level: EstimateConfidence

    # Breakdown
    estimated_tax: float
    total_withholding: float
    estimated_credits: float

    # Data quality
    data_completeness: float    # % of typical data provided
    assumptions_made: List[str]

    # Quick wins identified
    quick_opportunities: List[Dict[str, Any]]

    # Disclaimers
    disclaimer: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "refund_or_owed": float(money(self.refund_or_owed)),
            "likely_amount": float(money(self.likely_amount)),
            "confidence_band": {
                "low": float(money(self.low_estimate)),
                "likely": float(money(self.likely_amount)),
                "high": float(money(self.high_estimate)),
            },
            "confidence_score": round(self.confidence_score, 1),
            "confidence_level": self.confidence_level.value,
            "breakdown": {
                "estimated_tax": float(money(self.estimated_tax)),
                "total_withholding": float(money(self.total_withholding)),
                "estimated_credits": float(money(self.estimated_credits)),
            },
            "data_completeness": round(self.data_completeness, 1),
            "assumptions_made": self.assumptions_made,
            "quick_opportunities": self.quick_opportunities,
            "disclaimer": self.disclaimer,
        }


class RealTimeEstimator:
    """
    Provides instant tax estimates from minimal data.

    Designed for the Smart Tax document-first flow where users
    upload a W-2 and immediately see an estimate.
    """

    # 2025 Tax Constants (IRS Rev. Proc. 2024-40)
    TAX_YEAR = 2025

    # Standard deductions (2025 values)
    STANDARD_DEDUCTIONS = {
        "single": 15750,
        "married_joint": 31500,
        "married_separate": 15750,
        "head_of_household": 23850,
        "qualifying_widow": 31500,
    }

    # Tax brackets (2025)
    TAX_BRACKETS = {
        "single": [
            (11925, 0.10),
            (48475, 0.12),
            (103350, 0.22),
            (197300, 0.24),
            (250525, 0.32),
            (626350, 0.35),
            (float('inf'), 0.37),
        ],
        "married_joint": [
            (23850, 0.10),
            (96950, 0.12),
            (206700, 0.22),
            (394600, 0.24),
            (501050, 0.32),
            (751600, 0.35),
            (float('inf'), 0.37),
        ],
        "head_of_household": [
            (17000, 0.10),
            (64850, 0.12),
            (103350, 0.22),
            (197300, 0.24),
            (250500, 0.32),
            (626350, 0.35),
            (float('inf'), 0.37),
        ],
    }

    # Credit amounts for quick estimates (2025)
    CREDIT_ESTIMATES = {
        "child_tax_credit": 2000,  # Per qualifying child
        "child_tax_credit_refundable": 1700,  # ACTC portion
        "eitc_max_single_0": 649,   # EITC no kids (2025)
        "eitc_max_single_1": 4328,  # EITC 1 kid (2025)
        "eitc_max_single_2": 7152,  # EITC 2 kids (2025)
        "eitc_max_single_3": 8046,  # EITC 3+ kids (2025)
        "savers_credit_max": 2000,  # Per person max
    }

    def __init__(self, tax_year: int = 2025):
        self.tax_year = tax_year

    def estimate_from_w2(
        self,
        w2_data: Dict[str, Any],
        filing_status: str = "single",
        num_dependents: int = 0,
        has_spouse_income: bool = False,
    ) -> TaxEstimate:
        """
        Generate instant estimate from W-2 data alone.

        Args:
            w2_data: Dict with W-2 fields (wages, federal_tax_withheld, etc.)
            filing_status: Filing status (default: single)
            num_dependents: Number of qualifying children
            has_spouse_income: Whether spouse has separate income

        Returns:
            TaxEstimate with confidence band
        """
        assumptions = []

        # Extract W-2 values
        wages = self._to_float(w2_data.get("wages", 0))
        fed_withheld = self._to_float(w2_data.get("federal_tax_withheld", 0))
        ss_wages = self._to_float(w2_data.get("social_security_wages", wages))
        ss_tax = self._to_float(w2_data.get("social_security_tax", 0))
        medicare_tax = self._to_float(w2_data.get("medicare_tax", 0))
        state_tax = self._to_float(w2_data.get("state_tax", 0))

        # Calculate total withholding
        total_withholding = fed_withheld

        # Get standard deduction (assume standard for quick estimate)
        standard_deduction = self.STANDARD_DEDUCTIONS.get(filing_status, 15750)
        assumptions.append(f"Using standard deduction (${standard_deduction:,})")

        # Calculate taxable income
        taxable_income = max(0, wages - standard_deduction)

        # Calculate federal tax
        estimated_tax = self._calculate_tax(taxable_income, filing_status)

        # Estimate credits
        estimated_credits = 0.0
        credit_opportunities = []

        # Child Tax Credit
        if num_dependents > 0:
            ctc_per_child = self.CREDIT_ESTIMATES["child_tax_credit"]
            total_ctc = ctc_per_child * num_dependents

            # Apply income phaseout
            phaseout_start = 200000 if filing_status == "single" else 400000
            if wages > phaseout_start:
                phaseout_amount = ((wages - phaseout_start) // 1000) * 50
                total_ctc = max(0, total_ctc - phaseout_amount)

            if total_ctc > 0:
                estimated_credits += min(total_ctc, estimated_tax)
                # Refundable portion (ACTC)
                refundable_ctc = min(
                    self.CREDIT_ESTIMATES["child_tax_credit_refundable"] * num_dependents,
                    total_ctc - min(total_ctc, estimated_tax)
                )
                estimated_credits += refundable_ctc
                credit_opportunities.append({
                    "name": "Child Tax Credit",
                    "estimated_value": total_ctc,
                    "is_claimed": True,
                })

        # EITC check
        if wages > 0 and wages < 60000:  # Rough EITC eligibility
            eitc_estimate = self._estimate_eitc(wages, filing_status, num_dependents)
            if eitc_estimate > 0:
                estimated_credits += eitc_estimate
                credit_opportunities.append({
                    "name": "Earned Income Tax Credit",
                    "estimated_value": eitc_estimate,
                    "is_claimed": True,
                    "note": "May qualify based on income",
                })

        # Calculate refund/owed
        tax_after_credits = max(0, estimated_tax - estimated_credits)
        refund_or_owed = total_withholding - tax_after_credits

        # Determine confidence and band width
        confidence_score, confidence_level = self._calculate_confidence(
            w2_data, filing_status, num_dependents
        )

        # Calculate confidence band
        band_multiplier = self._get_band_multiplier(confidence_score)
        variation = abs(refund_or_owed) * band_multiplier

        if refund_or_owed >= 0:
            # Expecting refund
            low_estimate = refund_or_owed - variation
            high_estimate = refund_or_owed + variation
        else:
            # Owe taxes
            low_estimate = refund_or_owed - variation  # Owe more
            high_estimate = refund_or_owed + variation  # Owe less

        # Generate quick opportunities
        quick_opps = self._identify_quick_opportunities(
            wages, fed_withheld, filing_status, num_dependents, estimated_tax
        )

        # Data completeness based on what we have
        completeness = self._calculate_data_completeness(w2_data)

        return TaxEstimate(
            refund_or_owed=refund_or_owed,
            likely_amount=refund_or_owed,
            low_estimate=low_estimate,
            high_estimate=high_estimate,
            confidence_score=confidence_score,
            confidence_level=confidence_level,
            estimated_tax=estimated_tax,
            total_withholding=total_withholding,
            estimated_credits=estimated_credits,
            data_completeness=completeness,
            assumptions_made=assumptions,
            quick_opportunities=quick_opps,
            disclaimer=self._get_disclaimer(confidence_level),
        )

    def estimate_from_multiple_documents(
        self,
        documents: List[Dict[str, Any]],
        filing_status: str = "single",
        num_dependents: int = 0,
    ) -> TaxEstimate:
        """
        Generate estimate from multiple documents (W-2s, 1099s, etc.).

        Higher confidence than single W-2 estimate.
        """
        # Aggregate income from all documents
        total_wages = 0.0
        total_withholding = 0.0
        total_interest = 0.0
        total_dividends = 0.0
        total_se_income = 0.0
        assumptions = []

        for doc in documents:
            doc_type = doc.get("type", "")
            fields = doc.get("fields", {})

            if doc_type == "w2":
                total_wages += self._to_float(fields.get("wages", 0))
                total_withholding += self._to_float(fields.get("federal_tax_withheld", 0))

            elif doc_type == "1099_int":
                total_interest += self._to_float(fields.get("interest_income", 0))

            elif doc_type == "1099_div":
                total_dividends += self._to_float(fields.get("ordinary_dividends", 0))

            elif doc_type == "1099_nec":
                total_se_income += self._to_float(fields.get("nonemployee_compensation", 0))

        # Total gross income
        gross_income = total_wages + total_interest + total_dividends + total_se_income

        # Calculate self-employment tax if applicable
        se_tax = 0.0
        if total_se_income >= 400:
            se_tax = total_se_income * 0.9235 * 0.153
            se_deduction = se_tax / 2
            assumptions.append(f"Self-employment tax: ${se_tax:,.0f}")

        # AGI after SE deduction
        agi = gross_income - (se_tax / 2 if se_tax > 0 else 0)

        # Standard deduction
        standard_deduction = self.STANDARD_DEDUCTIONS.get(filing_status, 15750)
        assumptions.append(f"Using standard deduction (${standard_deduction:,})")

        # Taxable income
        taxable_income = max(0, agi - standard_deduction)

        # Calculate tax
        estimated_tax = self._calculate_tax(taxable_income, filing_status)

        # Add SE tax
        total_tax = estimated_tax + se_tax

        # Estimate credits (same as single W-2)
        estimated_credits = 0.0
        quick_opps = []

        if num_dependents > 0:
            ctc = min(2000 * num_dependents, estimated_tax)
            estimated_credits += ctc
            quick_opps.append({
                "name": "Child Tax Credit",
                "estimated_value": ctc,
            })

        # Calculate refund/owed
        tax_after_credits = max(0, total_tax - estimated_credits)
        refund_or_owed = total_withholding - tax_after_credits

        # Higher confidence with multiple documents
        doc_count = len(documents)
        confidence_score = min(85, 50 + doc_count * 10)
        confidence_level = (
            EstimateConfidence.HIGH if confidence_score >= 80
            else EstimateConfidence.MEDIUM if confidence_score >= 60
            else EstimateConfidence.LOW
        )

        # Narrower band with more data
        band_multiplier = self._get_band_multiplier(confidence_score)
        variation = max(500, abs(refund_or_owed) * band_multiplier)

        return TaxEstimate(
            refund_or_owed=refund_or_owed,
            likely_amount=refund_or_owed,
            low_estimate=refund_or_owed - variation,
            high_estimate=refund_or_owed + variation,
            confidence_score=confidence_score,
            confidence_level=confidence_level,
            estimated_tax=total_tax,
            total_withholding=total_withholding,
            estimated_credits=estimated_credits,
            data_completeness=min(100, 30 + doc_count * 15),
            assumptions_made=assumptions,
            quick_opportunities=quick_opps,
            disclaimer=self._get_disclaimer(confidence_level),
        )

    def refine_estimate(
        self,
        current_estimate: TaxEstimate,
        additional_data: Dict[str, Any],
    ) -> TaxEstimate:
        """
        Refine an existing estimate with additional data.

        Used as user answers more questions or uploads more documents.
        """
        # This would merge the additional data and recalculate
        # For now, return adjusted estimate
        new_confidence = min(95, current_estimate.confidence_score + 10)

        # Narrow the band
        new_multiplier = self._get_band_multiplier(new_confidence)
        old_variation = current_estimate.high_estimate - current_estimate.likely_amount
        new_variation = max(200, old_variation * 0.7)

        return TaxEstimate(
            refund_or_owed=current_estimate.refund_or_owed,
            likely_amount=current_estimate.likely_amount,
            low_estimate=current_estimate.likely_amount - new_variation,
            high_estimate=current_estimate.likely_amount + new_variation,
            confidence_score=new_confidence,
            confidence_level=self._get_confidence_level(new_confidence),
            estimated_tax=current_estimate.estimated_tax,
            total_withholding=current_estimate.total_withholding,
            estimated_credits=current_estimate.estimated_credits,
            data_completeness=min(100, current_estimate.data_completeness + 15),
            assumptions_made=current_estimate.assumptions_made[:-1],  # Remove assumptions
            quick_opportunities=current_estimate.quick_opportunities,
            disclaimer=self._get_disclaimer(self._get_confidence_level(new_confidence)),
        )

    def _calculate_tax(self, taxable_income: float, filing_status: str) -> float:
        """Calculate federal income tax using brackets."""
        brackets = self.TAX_BRACKETS.get(filing_status, self.TAX_BRACKETS["single"])

        tax = 0.0
        prev_threshold = 0

        for threshold, rate in brackets:
            if taxable_income <= threshold:
                tax += (taxable_income - prev_threshold) * rate
                break
            else:
                tax += (threshold - prev_threshold) * rate
                prev_threshold = threshold

        return tax

    def _estimate_eitc(
        self,
        earned_income: float,
        filing_status: str,
        num_children: int
    ) -> float:
        """Quick EITC estimate (simplified)."""
        # Very simplified EITC - actual calculation is more complex
        if num_children == 0:
            if earned_income > 17640:
                return 0
            return min(632, earned_income * 0.0765)

        if num_children == 1:
            if earned_income > 46560:
                return 0
            return min(4213, earned_income * 0.34)

        if num_children >= 2:
            if earned_income > 52918:
                return 0
            return min(6960 if num_children == 2 else 7830, earned_income * 0.40)

        return 0

    def _calculate_confidence(
        self,
        w2_data: Dict[str, Any],
        filing_status: str,
        num_dependents: int
    ) -> Tuple[float, EstimateConfidence]:
        """Calculate confidence score and level."""
        score = 40.0  # Base score for having any data

        # Add points for key fields present
        if w2_data.get("wages"):
            score += 15
        if w2_data.get("federal_tax_withheld"):
            score += 15
        if w2_data.get("social_security_wages"):
            score += 5
        if w2_data.get("medicare_wages"):
            score += 5

        # Confirmed filing status adds confidence
        if filing_status != "single":  # Default was changed
            score += 5

        # Dependent info adds confidence
        if num_dependents > 0:
            score += 5

        # Cap at 75 for single W-2 (need more data for higher confidence)
        score = min(75, score)

        level = (
            EstimateConfidence.HIGH if score >= 80
            else EstimateConfidence.MEDIUM if score >= 60
            else EstimateConfidence.LOW if score >= 40
            else EstimateConfidence.PRELIMINARY
        )

        return score, level

    def _get_band_multiplier(self, confidence_score: float) -> float:
        """Get band width multiplier based on confidence."""
        if confidence_score >= 85:
            return 0.05  # ±5%
        elif confidence_score >= 70:
            return 0.10  # ±10%
        elif confidence_score >= 55:
            return 0.20  # ±20%
        else:
            return 0.35  # ±35%

    def _get_confidence_level(self, score: float) -> EstimateConfidence:
        """Get confidence level from score."""
        if score >= 80:
            return EstimateConfidence.HIGH
        elif score >= 60:
            return EstimateConfidence.MEDIUM
        elif score >= 40:
            return EstimateConfidence.LOW
        return EstimateConfidence.PRELIMINARY

    def _identify_quick_opportunities(
        self,
        wages: float,
        withholding: float,
        filing_status: str,
        num_dependents: int,
        estimated_tax: float,
    ) -> List[Dict[str, Any]]:
        """Identify quick tax-saving opportunities."""
        opportunities = []

        # Check if potentially over-withholding
        if withholding > estimated_tax * 1.2:
            opportunities.append({
                "type": "withholding",
                "title": "Consider Adjusting W-4",
                "description": "You may be having too much withheld. Adjusting your W-4 could increase your take-home pay.",
                "potential_benefit": "Higher monthly paycheck",
                "priority": "info",
            })

        # Check for retirement savings opportunity
        if wages > 50000 and wages < 200000:
            max_401k = 23500  # 2025 limit
            potential_savings = min(max_401k * 0.22, wages * 0.05)  # Rough estimate
            opportunities.append({
                "type": "retirement",
                "title": "401(k) Contribution Opportunity",
                "description": f"Contributing to a 401(k) could reduce your taxes.",
                "potential_benefit": f"Up to ${potential_savings:,.0f} tax savings",
                "priority": "current_year",
            })

        # EITC opportunity check
        if num_dependents > 0 and wages < 60000:
            opportunities.append({
                "type": "credit",
                "title": "May Qualify for EITC",
                "description": "Based on your income and dependents, you may qualify for the Earned Income Tax Credit.",
                "potential_benefit": "Refundable credit up to $7,830",
                "priority": "immediate",
            })

        # HOH check for single with dependents
        if filing_status == "single" and num_dependents > 0:
            opportunities.append({
                "type": "filing_status",
                "title": "Check Head of Household Status",
                "description": "If you paid more than half the cost of keeping up a home for a qualifying person, you may file as Head of Household.",
                "potential_benefit": "Lower tax rate and higher standard deduction",
                "priority": "immediate",
            })

        return opportunities

    def _calculate_data_completeness(self, w2_data: Dict[str, Any]) -> float:
        """Calculate data completeness percentage."""
        expected_fields = [
            "wages", "federal_tax_withheld", "social_security_wages",
            "social_security_tax", "medicare_wages", "medicare_tax",
            "employee_ssn", "employer_ein",
        ]
        present = sum(1 for f in expected_fields if w2_data.get(f))
        return (present / len(expected_fields)) * 100

    def _get_disclaimer(self, level: EstimateConfidence) -> str:
        """Get appropriate disclaimer for confidence level."""
        disclaimers = {
            EstimateConfidence.HIGH: "This estimate is based on comprehensive data and should be close to your final result. Review for accuracy before filing.",
            EstimateConfidence.MEDIUM: "This is a reasonable estimate based on available data. Your actual refund or amount owed may vary as you provide more information.",
            EstimateConfidence.LOW: "This is a preliminary estimate based on limited information. The actual amount could vary significantly.",
            EstimateConfidence.PRELIMINARY: "This is a very rough estimate. Please provide more information for a more accurate result.",
        }
        return disclaimers.get(level, disclaimers[EstimateConfidence.PRELIMINARY])

    def _to_float(self, value: Any) -> float:
        """Convert value to float."""
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, str):
            try:
                cleaned = value.replace("$", "").replace(",", "").strip()
                return float(cleaned)
            except ValueError:
                return 0.0
        return 0.0


# Convenience functions
def quick_estimate_from_w2(
    wages: float,
    federal_withheld: float,
    filing_status: str = "single",
    num_dependents: int = 0,
) -> Dict[str, Any]:
    """
    Super quick estimate from basic W-2 info.

    Returns dict with refund estimate and confidence band.
    """
    estimator = RealTimeEstimator()
    estimate = estimator.estimate_from_w2(
        w2_data={
            "wages": wages,
            "federal_tax_withheld": federal_withheld,
        },
        filing_status=filing_status,
        num_dependents=num_dependents,
    )
    return estimate.to_dict()


def get_refund_range(
    wages: float,
    federal_withheld: float,
    filing_status: str = "single",
) -> Tuple[float, float, float]:
    """
    Get simple (low, likely, high) refund range.

    Returns tuple of (low_estimate, likely_estimate, high_estimate)
    """
    estimator = RealTimeEstimator()
    estimate = estimator.estimate_from_w2(
        w2_data={
            "wages": wages,
            "federal_tax_withheld": federal_withheld,
        },
        filing_status=filing_status,
    )
    return (estimate.low_estimate, estimate.likely_amount, estimate.high_estimate)
