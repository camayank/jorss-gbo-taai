"""
Inference Engine - Intelligent field inference and validation.

Provides:
- Missing field inference from related fields
- Cross-document validation
- Pattern detection for common scenarios
- Sanity checks and anomaly detection
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple, Set
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
import re


class InferenceType(str, Enum):
    """Types of inference operations."""
    CALCULATED = "calculated"     # Mathematically derived
    ESTIMATED = "estimated"       # Based on typical patterns
    ASSUMED = "assumed"           # Reasonable assumption
    VALIDATED = "validated"       # Cross-validated with other fields


@dataclass
class InferredField:
    """Result of field inference."""
    field_name: str
    inferred_value: Any
    inference_type: InferenceType
    confidence: float  # 0-100
    explanation: str
    source_fields: List[str]
    requires_confirmation: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_name": self.field_name,
            "inferred_value": float(self.inferred_value) if isinstance(self.inferred_value, Decimal) else self.inferred_value,
            "inference_type": self.inference_type.value,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "source_fields": self.source_fields,
            "requires_confirmation": self.requires_confirmation,
        }


@dataclass
class ValidationIssue:
    """An issue found during validation."""
    severity: str  # "error", "warning", "info"
    field_name: str
    message: str
    expected_value: Optional[Any] = None
    actual_value: Optional[Any] = None
    suggestion: Optional[str] = None


@dataclass
class InferenceResult:
    """Complete result of inference operations."""
    inferred_fields: List[InferredField]
    validation_issues: List[ValidationIssue]
    missing_required: List[str]
    document_complete: bool
    completion_percentage: float
    can_proceed: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "inferred_fields": [f.to_dict() for f in self.inferred_fields],
            "validation_issues": [
                {
                    "severity": v.severity,
                    "field_name": v.field_name,
                    "message": v.message,
                    "expected_value": v.expected_value,
                    "actual_value": v.actual_value,
                    "suggestion": v.suggestion,
                }
                for v in self.validation_issues
            ],
            "missing_required": self.missing_required,
            "document_complete": self.document_complete,
            "completion_percentage": self.completion_percentage,
            "can_proceed": self.can_proceed,
        }


class FieldInferenceEngine:
    """
    Intelligent inference engine for tax document fields.

    Uses domain knowledge to:
    - Infer missing fields from related data
    - Validate cross-field consistency
    - Detect anomalies and potential errors
    - Suggest corrections
    """

    # Tax year constants (2024/2025)
    # 2024 Tax Constants
    # 2025 Tax Constants (IRS Rev. Proc. 2024-40)
    TAX_CONSTANTS = {
        "ss_wage_base_2024": Decimal("168600"),
        "ss_wage_base_2025": Decimal("176100"),
        "ss_tax_rate": Decimal("0.062"),
        "medicare_tax_rate": Decimal("0.0145"),
        "additional_medicare_threshold_single": Decimal("200000"),
        "additional_medicare_threshold_mfj": Decimal("250000"),
        "additional_medicare_rate": Decimal("0.009"),
        # 2024 standard deductions
        "standard_deduction_single_2024": Decimal("14600"),
        "standard_deduction_mfj_2024": Decimal("29200"),
        "standard_deduction_hoh_2024": Decimal("21900"),
        # 2025 standard deductions
        "standard_deduction_single_2025": Decimal("15750"),
        "standard_deduction_mfj_2025": Decimal("31500"),
        "standard_deduction_hoh_2025": Decimal("23850"),
    }

    # Required fields by document type
    REQUIRED_FIELDS = {
        "w2": ["wages", "federal_tax_withheld", "employee_ssn", "employer_ein"],
        "1099_int": ["interest_income", "payer_name"],
        "1099_div": ["ordinary_dividends", "payer_name"],
        "1099_nec": ["nonemployee_compensation", "payer_name"],
        "1099_misc": ["payer_name"],  # Various boxes
        "1099_r": ["gross_distribution", "taxable_amount", "payer_name"],
    }

    def __init__(self, tax_year: int = 2025):
        self.tax_year = tax_year

    def infer_and_validate(
        self,
        document_type: str,
        extracted_fields: Dict[str, Any],
        filing_status: Optional[str] = None,
    ) -> InferenceResult:
        """
        Run inference and validation on extracted fields.

        Args:
            document_type: Type of document (w2, 1099_int, etc.)
            extracted_fields: Dict of field_name -> value
            filing_status: Filing status if known

        Returns:
            InferenceResult with inferred fields and validation issues
        """
        inferred_fields = []
        validation_issues = []

        # Run document-specific inference
        if document_type == "w2":
            inferred, issues = self._infer_w2_fields(extracted_fields)
            inferred_fields.extend(inferred)
            validation_issues.extend(issues)

        elif document_type.startswith("1099"):
            inferred, issues = self._infer_1099_fields(
                document_type, extracted_fields
            )
            inferred_fields.extend(inferred)
            validation_issues.extend(issues)

        # Check for missing required fields
        required = self.REQUIRED_FIELDS.get(document_type, [])
        all_fields = set(extracted_fields.keys()) | {
            f.field_name for f in inferred_fields
        }
        missing_required = [f for f in required if f not in all_fields]

        # Calculate completion
        total_fields = len(required)
        found_fields = len([f for f in required if f in all_fields])
        completion_percentage = (found_fields / total_fields * 100) if total_fields > 0 else 100.0

        # Determine if we can proceed
        critical_missing = [f for f in missing_required if f in ["wages", "employee_ssn"]]
        has_errors = any(v.severity == "error" for v in validation_issues)
        can_proceed = len(critical_missing) == 0 and not has_errors

        return InferenceResult(
            inferred_fields=inferred_fields,
            validation_issues=validation_issues,
            missing_required=missing_required,
            document_complete=len(missing_required) == 0,
            completion_percentage=round(completion_percentage, 1),
            can_proceed=can_proceed,
        )

    def _infer_w2_fields(
        self,
        fields: Dict[str, Any]
    ) -> Tuple[List[InferredField], List[ValidationIssue]]:
        """Infer and validate W-2 specific fields."""
        inferred = []
        issues = []

        wages = self._to_decimal(fields.get("wages"))
        fed_withheld = self._to_decimal(fields.get("federal_tax_withheld"))
        ss_wages = self._to_decimal(fields.get("social_security_wages"))
        ss_tax = self._to_decimal(fields.get("social_security_tax"))
        medicare_wages = self._to_decimal(fields.get("medicare_wages"))
        medicare_tax = self._to_decimal(fields.get("medicare_tax"))

        # Infer Social Security Wages if missing
        if ss_wages is None and wages is not None:
            # SS wages capped at wage base
            wage_base = self.TAX_CONSTANTS[f"ss_wage_base_{self.tax_year}"]
            inferred_ss_wages = min(wages, wage_base)
            inferred.append(InferredField(
                field_name="social_security_wages",
                inferred_value=inferred_ss_wages,
                inference_type=InferenceType.CALCULATED,
                confidence=85.0 if wages <= wage_base else 75.0,
                explanation=f"Social Security wages inferred from Box 1 wages (capped at ${wage_base:,.0f} wage base)",
                source_fields=["wages"],
                requires_confirmation=wages > wage_base,
            ))
            ss_wages = inferred_ss_wages

        # Infer Social Security Tax if missing
        if ss_tax is None and ss_wages is not None:
            expected_ss_tax = ss_wages * self.TAX_CONSTANTS["ss_tax_rate"]
            expected_ss_tax = expected_ss_tax.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            inferred.append(InferredField(
                field_name="social_security_tax",
                inferred_value=expected_ss_tax,
                inference_type=InferenceType.CALCULATED,
                confidence=90.0,
                explanation=f"Social Security tax calculated as 6.2% of SS wages",
                source_fields=["social_security_wages"],
            ))
            ss_tax = expected_ss_tax

        # Infer Medicare Wages if missing
        if medicare_wages is None and wages is not None:
            # Medicare wages typically equal Box 1 wages (no cap)
            inferred.append(InferredField(
                field_name="medicare_wages",
                inferred_value=wages,
                inference_type=InferenceType.ASSUMED,
                confidence=90.0,
                explanation="Medicare wages typically equal Box 1 wages",
                source_fields=["wages"],
            ))
            medicare_wages = wages

        # Infer Medicare Tax if missing
        if medicare_tax is None and medicare_wages is not None:
            expected_medicare = medicare_wages * self.TAX_CONSTANTS["medicare_tax_rate"]
            expected_medicare = expected_medicare.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            inferred.append(InferredField(
                field_name="medicare_tax",
                inferred_value=expected_medicare,
                inference_type=InferenceType.CALCULATED,
                confidence=88.0,
                explanation="Medicare tax calculated as 1.45% of Medicare wages",
                source_fields=["medicare_wages"],
            ))
            medicare_tax = expected_medicare

        # VALIDATION: Check Social Security tax matches expected
        if ss_wages is not None and ss_tax is not None:
            expected = ss_wages * self.TAX_CONSTANTS["ss_tax_rate"]
            expected = expected.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            tolerance = Decimal("0.50")  # Allow $0.50 rounding difference

            if abs(ss_tax - expected) > tolerance:
                issues.append(ValidationIssue(
                    severity="warning",
                    field_name="social_security_tax",
                    message=f"Social Security tax (${ss_tax:,.2f}) doesn't match expected 6.2% of SS wages (${expected:,.2f})",
                    expected_value=float(expected),
                    actual_value=float(ss_tax),
                    suggestion="Verify Box 4 matches 6.2% of Box 3",
                ))

        # VALIDATION: Check Medicare tax matches expected
        if medicare_wages is not None and medicare_tax is not None:
            expected = medicare_wages * self.TAX_CONSTANTS["medicare_tax_rate"]
            expected = expected.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            tolerance = Decimal("0.50")

            if abs(medicare_tax - expected) > tolerance:
                issues.append(ValidationIssue(
                    severity="warning",
                    field_name="medicare_tax",
                    message=f"Medicare tax (${medicare_tax:,.2f}) doesn't match expected 1.45% of Medicare wages (${expected:,.2f})",
                    expected_value=float(expected),
                    actual_value=float(medicare_tax),
                    suggestion="Verify Box 6 matches 1.45% of Box 5",
                ))

        # VALIDATION: Federal withholding reasonableness
        if wages is not None and fed_withheld is not None:
            if fed_withheld > wages * Decimal("0.50"):
                issues.append(ValidationIssue(
                    severity="error",
                    field_name="federal_tax_withheld",
                    message=f"Federal withholding (${fed_withheld:,.2f}) exceeds 50% of wages - likely incorrect",
                    expected_value=None,
                    actual_value=float(fed_withheld),
                    suggestion="Verify Box 2 value",
                ))
            elif fed_withheld > wages * Decimal("0.40"):
                issues.append(ValidationIssue(
                    severity="warning",
                    field_name="federal_tax_withheld",
                    message=f"Federal withholding (${fed_withheld:,.2f}) is unusually high (>40% of wages)",
                    expected_value=None,
                    actual_value=float(fed_withheld),
                ))

        # VALIDATION: SS wages shouldn't exceed wage base
        if ss_wages is not None:
            wage_base = self.TAX_CONSTANTS[f"ss_wage_base_{self.tax_year}"]
            if ss_wages > wage_base:
                issues.append(ValidationIssue(
                    severity="error",
                    field_name="social_security_wages",
                    message=f"SS wages (${ss_wages:,.2f}) exceed annual wage base (${wage_base:,.0f})",
                    expected_value=float(wage_base),
                    actual_value=float(ss_wages),
                    suggestion="SS wages should be capped at the wage base",
                ))

        return inferred, issues

    def _infer_1099_fields(
        self,
        document_type: str,
        fields: Dict[str, Any]
    ) -> Tuple[List[InferredField], List[ValidationIssue]]:
        """Infer and validate 1099 specific fields."""
        inferred = []
        issues = []

        if document_type == "1099_div":
            ordinary_div = self._to_decimal(fields.get("ordinary_dividends"))
            qualified_div = self._to_decimal(fields.get("qualified_dividends"))

            # VALIDATION: Qualified dividends <= ordinary dividends
            if ordinary_div is not None and qualified_div is not None:
                if qualified_div > ordinary_div:
                    issues.append(ValidationIssue(
                        severity="error",
                        field_name="qualified_dividends",
                        message=f"Qualified dividends (${qualified_div:,.2f}) exceed ordinary dividends (${ordinary_div:,.2f})",
                        expected_value=float(ordinary_div),
                        actual_value=float(qualified_div),
                        suggestion="Qualified dividends must be <= ordinary dividends",
                    ))

            # If qualified dividends missing, estimate
            if qualified_div is None and ordinary_div is not None:
                # Estimate qualified at 80% of ordinary (typical for US stocks)
                estimated_qualified = ordinary_div * Decimal("0.80")
                estimated_qualified = estimated_qualified.quantize(Decimal("0.01"))
                inferred.append(InferredField(
                    field_name="qualified_dividends",
                    inferred_value=estimated_qualified,
                    inference_type=InferenceType.ESTIMATED,
                    confidence=50.0,  # Low confidence - estimate only
                    explanation="Estimated at ~80% of ordinary dividends (typical for US equity funds)",
                    source_fields=["ordinary_dividends"],
                    requires_confirmation=True,
                ))

        elif document_type == "1099_int":
            interest = self._to_decimal(fields.get("interest_income"))

            # Check for unreasonably high interest
            if interest is not None and interest > Decimal("100000"):
                issues.append(ValidationIssue(
                    severity="info",
                    field_name="interest_income",
                    message=f"High interest income (${interest:,.2f}) - verify this is correct",
                    expected_value=None,
                    actual_value=float(interest),
                ))

        elif document_type == "1099_nec":
            nec = self._to_decimal(fields.get("nonemployee_compensation"))

            # NEC triggers self-employment tax reminder
            if nec is not None and nec >= Decimal("400"):
                issues.append(ValidationIssue(
                    severity="info",
                    field_name="nonemployee_compensation",
                    message=f"Self-employment income of ${nec:,.2f} will be subject to SE tax",
                    expected_value=None,
                    actual_value=float(nec),
                    suggestion="SE tax will be calculated automatically",
                ))

        return inferred, issues

    def infer_filing_status(
        self,
        fields: Dict[str, Any],
        prior_year_status: Optional[str] = None,
    ) -> Tuple[str, float, str]:
        """
        Attempt to infer filing status from available data.

        Returns:
            Tuple of (status, confidence, explanation)
        """
        # Check for spouse information
        has_spouse_ssn = "spouse_ssn" in fields
        has_spouse_name = "spouse_name" in fields

        # Check for dependent information
        dependents = fields.get("dependents", [])
        has_dependents = len(dependents) > 0 if dependents else False

        # Check for specific indicators
        taxpayer_ssn = fields.get("employee_ssn") or fields.get("taxpayer_ssn")

        if has_spouse_ssn or has_spouse_name:
            return (
                "married_joint",
                75.0,
                "Spouse information found, assuming Married Filing Jointly"
            )

        if has_dependents and not has_spouse_ssn:
            return (
                "head_of_household",
                60.0,
                "Dependents found without spouse, may qualify for Head of Household"
            )

        if prior_year_status:
            return (
                prior_year_status,
                70.0,
                f"Assuming same filing status as prior year: {prior_year_status}"
            )

        # Default to single
        return (
            "single",
            50.0,
            "Defaulting to Single - please confirm filing status"
        )

    def infer_deduction_type(
        self,
        extracted_fields: Dict[str, Any],
        filing_status: str,
    ) -> Tuple[str, float, str]:
        """
        Infer whether standard or itemized deduction is better.

        Returns:
            Tuple of (deduction_type, confidence, explanation)
        """
        # Get standard deduction amount
        if filing_status == "married_joint":
            std_deduction = self.TAX_CONSTANTS[f"standard_deduction_mfj_{self.tax_year}"]
        else:
            std_deduction = self.TAX_CONSTANTS[f"standard_deduction_single_{self.tax_year}"]

        # Sum up potential itemized deductions
        itemized_total = Decimal("0")

        # Mortgage interest
        mortgage_interest = self._to_decimal(extracted_fields.get("mortgage_interest", 0))
        if mortgage_interest:
            itemized_total += mortgage_interest

        # Property taxes (capped at $10k SALT)
        property_tax = self._to_decimal(extracted_fields.get("property_tax", 0))
        state_income_tax = self._to_decimal(extracted_fields.get("state_income_tax", 0))
        salt_total = (property_tax or Decimal("0")) + (state_income_tax or Decimal("0"))
        itemized_total += min(salt_total, Decimal("10000"))

        # Charitable contributions
        charitable = self._to_decimal(extracted_fields.get("charitable_contributions", 0))
        if charitable:
            itemized_total += charitable

        # Medical expenses (only amount over 7.5% AGI)
        medical = self._to_decimal(extracted_fields.get("medical_expenses", 0))
        agi = self._to_decimal(extracted_fields.get("agi", 0))
        if medical and agi:
            medical_floor = agi * Decimal("0.075")
            if medical > medical_floor:
                itemized_total += (medical - medical_floor)

        # Compare and recommend
        if itemized_total > std_deduction:
            savings = itemized_total - std_deduction
            return (
                "itemized",
                85.0,
                f"Itemizing saves ${savings:,.0f} over standard deduction"
            )
        else:
            return (
                "standard",
                90.0,
                f"Standard deduction (${std_deduction:,.0f}) is higher than itemized (${itemized_total:,.0f})"
            )

    def _to_decimal(self, value: Any) -> Optional[Decimal]:
        """Convert value to Decimal."""
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        if isinstance(value, str):
            try:
                cleaned = re.sub(r'[$,\s]', '', value)
                return Decimal(cleaned)
            except Exception:
                return None
        return None


class MultiDocumentInference:
    """
    Handles inference across multiple tax documents.

    Aggregates data from multiple W-2s, 1099s, etc. and validates
    consistency across the complete tax picture.
    """

    def __init__(self, tax_year: int = 2024):
        self.tax_year = tax_year
        self.engine = FieldInferenceEngine(tax_year)

    def aggregate_income(
        self,
        documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Aggregate income from multiple documents.

        Args:
            documents: List of document dicts with 'type' and 'fields' keys

        Returns:
            Aggregated income summary
        """
        totals = {
            "total_wages": Decimal("0"),
            "total_federal_withheld": Decimal("0"),
            "total_state_withheld": Decimal("0"),
            "total_interest": Decimal("0"),
            "total_dividends": Decimal("0"),
            "total_qualified_dividends": Decimal("0"),
            "total_nec_income": Decimal("0"),
            "total_misc_income": Decimal("0"),
            "w2_count": 0,
            "1099_count": 0,
        }

        for doc in documents:
            doc_type = doc.get("type", "")
            fields = doc.get("fields", {})

            if doc_type == "w2":
                totals["w2_count"] += 1
                wages = self._to_decimal(fields.get("wages"))
                if wages:
                    totals["total_wages"] += wages
                fed = self._to_decimal(fields.get("federal_tax_withheld"))
                if fed:
                    totals["total_federal_withheld"] += fed
                state = self._to_decimal(fields.get("state_tax"))
                if state:
                    totals["total_state_withheld"] += state

            elif doc_type == "1099_int":
                totals["1099_count"] += 1
                interest = self._to_decimal(fields.get("interest_income"))
                if interest:
                    totals["total_interest"] += interest

            elif doc_type == "1099_div":
                totals["1099_count"] += 1
                ordinary = self._to_decimal(fields.get("ordinary_dividends"))
                if ordinary:
                    totals["total_dividends"] += ordinary
                qualified = self._to_decimal(fields.get("qualified_dividends"))
                if qualified:
                    totals["total_qualified_dividends"] += qualified

            elif doc_type == "1099_nec":
                totals["1099_count"] += 1
                nec = self._to_decimal(fields.get("nonemployee_compensation"))
                if nec:
                    totals["total_nec_income"] += nec

        # Convert to serializable format
        return {
            "total_wages": float(totals["total_wages"]),
            "total_federal_withheld": float(totals["total_federal_withheld"]),
            "total_state_withheld": float(totals["total_state_withheld"]),
            "total_interest": float(totals["total_interest"]),
            "total_dividends": float(totals["total_dividends"]),
            "total_qualified_dividends": float(totals["total_qualified_dividends"]),
            "total_nec_income": float(totals["total_nec_income"]),
            "w2_count": totals["w2_count"],
            "1099_count": totals["1099_count"],
            "estimated_agi": float(
                totals["total_wages"] +
                totals["total_interest"] +
                totals["total_dividends"] +
                totals["total_nec_income"]
            ),
            "has_self_employment": totals["total_nec_income"] > 0,
        }

    def validate_cross_document(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[ValidationIssue]:
        """
        Validate consistency across multiple documents.

        Returns:
            List of cross-document validation issues
        """
        issues = []

        # Group documents by type
        w2s = [d for d in documents if d.get("type") == "w2"]
        div_1099s = [d for d in documents if d.get("type") == "1099_div"]

        # Check for duplicate W-2s (same EIN)
        eins = [d.get("fields", {}).get("employer_ein") for d in w2s]
        eins = [e for e in eins if e]
        if len(eins) != len(set(eins)):
            issues.append(ValidationIssue(
                severity="warning",
                field_name="employer_ein",
                message="Multiple W-2s found with same employer EIN - possible duplicate",
                suggestion="Verify you haven't uploaded the same W-2 twice",
            ))

        # Check total SS wages across W-2s doesn't exceed wage base
        total_ss_wages = Decimal("0")
        for w2 in w2s:
            ss_wages = self._to_decimal(w2.get("fields", {}).get("social_security_wages"))
            if ss_wages:
                total_ss_wages += ss_wages

        wage_base = FieldInferenceEngine.TAX_CONSTANTS[f"ss_wage_base_{self.tax_year}"]
        if total_ss_wages > wage_base:
            issues.append(ValidationIssue(
                severity="info",
                field_name="total_social_security_wages",
                message=f"Total SS wages (${total_ss_wages:,.2f}) exceed annual wage base (${wage_base:,.0f})",
                expected_value=float(wage_base),
                actual_value=float(total_ss_wages),
                suggestion="You may have overpaid SS tax and could receive a credit",
            ))

        return issues

    def _to_decimal(self, value: Any) -> Optional[Decimal]:
        """Convert value to Decimal."""
        return self.engine._to_decimal(value)


# Convenience functions
def infer_document_fields(
    document_type: str,
    fields: Dict[str, Any],
    tax_year: int = 2024,
) -> InferenceResult:
    """Convenience function to infer and validate document fields."""
    engine = FieldInferenceEngine(tax_year)
    return engine.infer_and_validate(document_type, fields)


def aggregate_multi_document_income(
    documents: List[Dict[str, Any]],
    tax_year: int = 2024,
) -> Dict[str, Any]:
    """Convenience function to aggregate income from multiple documents."""
    engine = MultiDocumentInference(tax_year)
    return engine.aggregate_income(documents)
