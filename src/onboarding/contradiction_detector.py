"""
Tax Return Contradiction Detector

Identifies conflicting or inconsistent information in tax return data.
Helps prevent errors before submission by catching logical contradictions.

Examples of contradictions:
- Filing status HOH but married spouse info provided
- Claiming child tax credit with no qualifying children
- Negative income with no business losses
- Self-employment income but no SE tax
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class ContradictionSeverity(Enum):
    """Severity levels for contradictions."""
    ERROR = "error"      # Must be resolved before filing
    WARNING = "warning"  # Should be reviewed but may be valid
    INFO = "info"        # FYI - unusual but possibly intentional


@dataclass
class Contradiction:
    """A detected contradiction in the tax return."""
    id: str
    severity: ContradictionSeverity
    title: str
    message: str
    fields_involved: List[str]
    suggestion: Optional[str] = None
    irs_reference: Optional[str] = None  # e.g., "Pub 501, Page 12"


@dataclass
class ContradictionResult:
    """Result of contradiction check."""
    has_errors: bool
    contradictions: List[Contradiction]

    @property
    def errors(self) -> List[Contradiction]:
        return [c for c in self.contradictions if c.severity == ContradictionSeverity.ERROR]

    @property
    def warnings(self) -> List[Contradiction]:
        return [c for c in self.contradictions if c.severity == ContradictionSeverity.WARNING]

    @property
    def info(self) -> List[Contradiction]:
        return [c for c in self.contradictions if c.severity == ContradictionSeverity.INFO]


class ContradictionDetector:
    """
    Detects contradictions in tax return data.

    Usage:
        detector = ContradictionDetector()
        result = detector.check(tax_data)

        if result.has_errors:
            for error in result.errors:
                print(f"ERROR: {error.title} - {error.message}")
    """

    def __init__(self):
        self._rules: List[Callable[[Dict], Optional[Contradiction]]] = []
        self._register_default_rules()

    def _register_default_rules(self) -> None:
        """Register all default contradiction rules."""
        # Filing status rules
        self._rules.append(self._check_hoh_with_spouse)
        self._rules.append(self._check_mfs_with_dependent_credit)
        self._rules.append(self._check_qw_requirements)

        # Dependent rules
        self._rules.append(self._check_dependent_age_ctc)
        self._rules.append(self._check_dependent_ssn)
        self._rules.append(self._check_dependent_relationship)

        # Income rules
        self._rules.append(self._check_negative_wages)
        self._rules.append(self._check_se_income_without_se_tax)
        self._rules.append(self._check_investment_income_consistency)

        # Deduction rules
        self._rules.append(self._check_itemized_vs_standard)
        self._rules.append(self._check_mortgage_interest_limits)
        self._rules.append(self._check_salt_cap)

        # Credit rules
        self._rules.append(self._check_eitc_investment_income)
        self._rules.append(self._check_aotc_years)
        self._rules.append(self._check_child_care_credit_income)

    def check(self, data: Dict[str, Any]) -> ContradictionResult:
        """
        Check tax data for contradictions.

        Args:
            data: Tax return data dictionary

        Returns:
            ContradictionResult with all detected issues
        """
        contradictions = []

        for rule in self._rules:
            try:
                result = rule(data)
                if result:
                    contradictions.append(result)
            except Exception as e:
                logger.warning(f"Rule {rule.__name__} failed: {e}")

        has_errors = any(c.severity == ContradictionSeverity.ERROR for c in contradictions)

        return ContradictionResult(
            has_errors=has_errors,
            contradictions=contradictions
        )

    def add_rule(self, rule: Callable[[Dict], Optional[Contradiction]]) -> None:
        """Add a custom contradiction rule."""
        self._rules.append(rule)

    # =========================================================================
    # FILING STATUS RULES
    # =========================================================================

    def _check_hoh_with_spouse(self, data: Dict) -> Optional[Contradiction]:
        """Check for HOH filing status with spouse information."""
        filing_status = data.get("filing_status")
        spouse_ssn = data.get("spouse_ssn") or data.get("spouse", {}).get("ssn")
        spouse_name = data.get("spouse_name") or data.get("spouse", {}).get("name")

        if filing_status == "hoh" and (spouse_ssn or spouse_name):
            return Contradiction(
                id="hoh_with_spouse",
                severity=ContradictionSeverity.ERROR,
                title="Head of Household with Spouse",
                message="You selected Head of Household filing status but provided spouse information. HOH is for unmarried taxpayers or those considered unmarried.",
                fields_involved=["filing_status", "spouse_ssn", "spouse_name"],
                suggestion="If you are married, consider filing as Married Filing Jointly or Married Filing Separately. If you are unmarried, remove the spouse information.",
                irs_reference="Pub 501, Filing Status"
            )
        return None

    def _check_mfs_with_dependent_credit(self, data: Dict) -> Optional[Contradiction]:
        """MFS cannot claim certain credits."""
        filing_status = data.get("filing_status")
        claiming_eitc = data.get("claiming_eitc") or data.get("eitc_amount", 0) > 0
        claiming_aotc = data.get("claiming_aotc") or data.get("aotc_amount", 0) > 0

        if filing_status == "mfs":
            if claiming_eitc:
                return Contradiction(
                    id="mfs_eitc",
                    severity=ContradictionSeverity.ERROR,
                    title="EITC Not Allowed for MFS",
                    message="You cannot claim the Earned Income Tax Credit when filing Married Filing Separately.",
                    fields_involved=["filing_status", "claiming_eitc"],
                    suggestion="Consider filing Married Filing Jointly to claim EITC, or remove the EITC claim.",
                    irs_reference="Pub 596, EITC"
                )
            if claiming_aotc:
                return Contradiction(
                    id="mfs_aotc",
                    severity=ContradictionSeverity.ERROR,
                    title="AOTC Not Allowed for MFS",
                    message="You cannot claim the American Opportunity Tax Credit when filing Married Filing Separately.",
                    fields_involved=["filing_status", "claiming_aotc"],
                    suggestion="Consider filing Married Filing Jointly to claim education credits.",
                    irs_reference="Pub 970, Education Credits"
                )
        return None

    def _check_qw_requirements(self, data: Dict) -> Optional[Contradiction]:
        """Qualifying Widow(er) has specific requirements."""
        filing_status = data.get("filing_status")
        spouse_death_year = data.get("spouse_death_year")
        tax_year = data.get("tax_year", 2025)
        has_dependent_child = data.get("has_dependent_child", False)

        if filing_status == "qw":
            if not spouse_death_year:
                return Contradiction(
                    id="qw_no_death_year",
                    severity=ContradictionSeverity.ERROR,
                    title="Missing Spouse Death Year",
                    message="Qualifying Widow(er) status requires spouse death year information.",
                    fields_involved=["filing_status", "spouse_death_year"],
                    suggestion="Provide the year your spouse passed away, or select a different filing status."
                )

            years_since_death = tax_year - spouse_death_year
            if years_since_death > 2 or years_since_death < 1:
                return Contradiction(
                    id="qw_timing",
                    severity=ContradictionSeverity.ERROR,
                    title="Qualifying Widow(er) Timing",
                    message=f"Qualifying Widow(er) status is only available for 2 years after spouse's death. Your spouse passed {years_since_death} year(s) ago.",
                    fields_involved=["filing_status", "spouse_death_year"],
                    suggestion="For the year of death, file MFJ. After 2 years, file as Single or HOH if eligible."
                )

            if not has_dependent_child:
                return Contradiction(
                    id="qw_no_dependent",
                    severity=ContradictionSeverity.ERROR,
                    title="QW Requires Dependent Child",
                    message="Qualifying Widow(er) status requires a dependent child living with you.",
                    fields_involved=["filing_status", "has_dependent_child"],
                    suggestion="Add dependent child information or select Single/HOH filing status."
                )
        return None

    # =========================================================================
    # DEPENDENT RULES
    # =========================================================================

    def _check_dependent_age_ctc(self, data: Dict) -> Optional[Contradiction]:
        """Child must be under 17 for Child Tax Credit."""
        claiming_ctc = data.get("claiming_ctc") or data.get("ctc_amount", 0) > 0
        dependents = data.get("dependents", [])

        if claiming_ctc and dependents:
            qualifying_children = [d for d in dependents if d.get("age", 0) < 17]
            if not qualifying_children:
                return Contradiction(
                    id="ctc_no_qualifying_child",
                    severity=ContradictionSeverity.ERROR,
                    title="No Qualifying Child for CTC",
                    message="You claimed the Child Tax Credit but have no dependents under age 17.",
                    fields_involved=["claiming_ctc", "dependents"],
                    suggestion="Children must be under 17 at end of year for CTC. You may qualify for Credit for Other Dependents ($500).",
                    irs_reference="Pub 972, Child Tax Credit"
                )
        return None

    def _check_dependent_ssn(self, data: Dict) -> Optional[Contradiction]:
        """Dependents need valid SSN for most credits."""
        dependents = data.get("dependents", [])
        claiming_ctc = data.get("claiming_ctc", False)

        for dep in dependents:
            ssn = dep.get("ssn", "")
            if claiming_ctc and (not ssn or len(ssn.replace("-", "")) != 9):
                return Contradiction(
                    id="dependent_missing_ssn",
                    severity=ContradictionSeverity.WARNING,
                    title="Dependent Missing SSN",
                    message=f"Dependent '{dep.get('name', 'Unknown')}' is missing a valid SSN. This may affect eligibility for credits.",
                    fields_involved=["dependents", f"dependents.{dep.get('name', '')}.ssn"],
                    suggestion="Ensure all dependents have valid SSNs. ITINs may have limitations for certain credits."
                )
        return None

    def _check_dependent_relationship(self, data: Dict) -> Optional[Contradiction]:
        """Check dependent relationship is valid."""
        dependents = data.get("dependents", [])
        valid_relationships = {
            "son", "daughter", "stepson", "stepdaughter",
            "foster child", "brother", "sister", "stepbrother", "stepsister",
            "grandchild", "niece", "nephew", "parent", "grandparent"
        }

        for dep in dependents:
            relationship = dep.get("relationship", "").lower()
            if relationship and relationship not in valid_relationships:
                return Contradiction(
                    id="invalid_dependent_relationship",
                    severity=ContradictionSeverity.WARNING,
                    title="Unusual Dependent Relationship",
                    message=f"'{relationship}' is not a typical qualifying relationship for dependents.",
                    fields_involved=["dependents", f"dependents.{dep.get('name', '')}.relationship"],
                    suggestion="Review IRS qualifying relative rules. Some relationships may require additional documentation."
                )
        return None

    # =========================================================================
    # INCOME RULES
    # =========================================================================

    def _check_negative_wages(self, data: Dict) -> Optional[Contradiction]:
        """Wages cannot be negative."""
        wages = data.get("wages", 0) or data.get("income", {}).get("wages", 0)

        if wages and wages < 0:
            return Contradiction(
                id="negative_wages",
                severity=ContradictionSeverity.ERROR,
                title="Negative Wages",
                message="Wages cannot be negative. W-2 wages are always reported as positive amounts.",
                fields_involved=["wages"],
                suggestion="Enter wages as a positive number. If you had a wage adjustment, it may belong elsewhere."
            )
        return None

    def _check_se_income_without_se_tax(self, data: Dict) -> Optional[Contradiction]:
        """Self-employment income should trigger SE tax."""
        se_income = data.get("self_employment_income", 0) or data.get("schedule_c_profit", 0)
        se_tax = data.get("self_employment_tax", 0)

        if se_income and se_income > 400 and (not se_tax or se_tax == 0):
            return Contradiction(
                id="se_income_no_tax",
                severity=ContradictionSeverity.WARNING,
                title="Self-Employment Income Without SE Tax",
                message=f"You reported ${se_income:,.0f} in self-employment income but no self-employment tax.",
                fields_involved=["self_employment_income", "self_employment_tax"],
                suggestion="Self-employment tax (15.3%) applies to SE income over $400. This may be calculated automatically.",
                irs_reference="Schedule SE"
            )
        return None

    def _check_investment_income_consistency(self, data: Dict) -> Optional[Contradiction]:
        """Investment income should be consistent."""
        dividends = data.get("ordinary_dividends", 0)
        qualified_dividends = data.get("qualified_dividends", 0)

        if qualified_dividends and dividends and qualified_dividends > dividends:
            return Contradiction(
                id="qualified_exceeds_ordinary",
                severity=ContradictionSeverity.ERROR,
                title="Qualified Dividends Exceed Ordinary",
                message="Qualified dividends cannot exceed total ordinary dividends.",
                fields_involved=["ordinary_dividends", "qualified_dividends"],
                suggestion="Qualified dividends are a subset of ordinary dividends. Check your 1099-DIV."
            )
        return None

    # =========================================================================
    # DEDUCTION RULES
    # =========================================================================

    def _check_itemized_vs_standard(self, data: Dict) -> Optional[Contradiction]:
        """Check if itemizing makes sense."""
        will_itemize = data.get("will_itemize", False)
        total_itemized = data.get("total_itemized_deductions", 0)
        filing_status = data.get("filing_status", "single")

        standard_deductions = {
            "single": 15000,
            "mfj": 30000,
            "mfs": 15000,
            "hoh": 22500,
            "qw": 30000,
        }

        standard = standard_deductions.get(filing_status, 15000)

        if will_itemize and total_itemized and total_itemized < standard * 0.8:
            return Contradiction(
                id="itemizing_below_standard",
                severity=ContradictionSeverity.WARNING,
                title="Itemizing Below Standard Deduction",
                message=f"Your itemized deductions (${total_itemized:,.0f}) are less than the standard deduction (${standard:,.0f}).",
                fields_involved=["will_itemize", "total_itemized_deductions"],
                suggestion="Consider taking the standard deduction to reduce your tax liability."
            )
        return None

    def _check_mortgage_interest_limits(self, data: Dict) -> Optional[Contradiction]:
        """Mortgage interest has acquisition debt limits."""
        mortgage_interest = data.get("mortgage_interest", 0)
        acquisition_debt = data.get("mortgage_principal", 0)

        # Post-2017 limit is $750K for new mortgages
        if mortgage_interest > 30000 and acquisition_debt and acquisition_debt > 750000:
            return Contradiction(
                id="mortgage_debt_limit",
                severity=ContradictionSeverity.WARNING,
                title="Mortgage Interest May Be Limited",
                message="Your mortgage exceeds $750,000. Interest deduction may be limited for debt acquired after Dec 15, 2017.",
                fields_involved=["mortgage_interest", "mortgage_principal"],
                suggestion="Only interest on the first $750K of acquisition debt is deductible for post-2017 mortgages.",
                irs_reference="Pub 936"
            )
        return None

    def _check_salt_cap(self, data: Dict) -> Optional[Contradiction]:
        """SALT deduction capped at $10,000."""
        state_taxes = data.get("state_income_taxes", 0)
        property_taxes = data.get("property_taxes", 0)
        salt_claimed = data.get("salt_deduction", 0)

        total_salt = state_taxes + property_taxes

        if salt_claimed and salt_claimed > 10000:
            return Contradiction(
                id="salt_over_cap",
                severity=ContradictionSeverity.ERROR,
                title="SALT Deduction Over Cap",
                message=f"SALT deduction of ${salt_claimed:,.0f} exceeds the $10,000 cap.",
                fields_involved=["salt_deduction", "state_income_taxes", "property_taxes"],
                suggestion="The SALT deduction is capped at $10,000 ($5,000 if MFS).",
                irs_reference="Schedule A"
            )
        return None

    # =========================================================================
    # CREDIT RULES
    # =========================================================================

    def _check_eitc_investment_income(self, data: Dict) -> Optional[Contradiction]:
        """EITC has investment income limit."""
        claiming_eitc = data.get("claiming_eitc", False)
        investment_income = data.get("investment_income", 0)

        # 2025 limit is approximately $11,600
        if claiming_eitc and investment_income and investment_income > 11600:
            return Contradiction(
                id="eitc_investment_limit",
                severity=ContradictionSeverity.ERROR,
                title="EITC Investment Income Limit",
                message=f"Investment income of ${investment_income:,.0f} exceeds EITC limit of $11,600.",
                fields_involved=["claiming_eitc", "investment_income"],
                suggestion="You cannot claim EITC with investment income over $11,600.",
                irs_reference="Pub 596"
            )
        return None

    def _check_aotc_years(self, data: Dict) -> Optional[Contradiction]:
        """AOTC can only be claimed for 4 years."""
        claiming_aotc = data.get("claiming_aotc", False)
        years_claimed = data.get("prior_aotc_years", 0)

        if claiming_aotc and years_claimed and years_claimed >= 4:
            return Contradiction(
                id="aotc_four_year_limit",
                severity=ContradictionSeverity.ERROR,
                title="AOTC Four-Year Limit",
                message=f"AOTC has already been claimed for {years_claimed} years. Maximum is 4 years.",
                fields_involved=["claiming_aotc", "prior_aotc_years"],
                suggestion="Consider the Lifetime Learning Credit instead, which has no year limit.",
                irs_reference="Form 8863"
            )
        return None

    def _check_child_care_credit_income(self, data: Dict) -> Optional[Contradiction]:
        """Child care credit requires earned income."""
        claiming_dcfc = data.get("claiming_dependent_care_credit", False)
        earned_income = data.get("earned_income", 0)

        if claiming_dcfc and (not earned_income or earned_income == 0):
            return Contradiction(
                id="dcfc_no_earned_income",
                severity=ContradictionSeverity.ERROR,
                title="Dependent Care Credit Requires Earned Income",
                message="You claimed the Dependent Care Credit but have no earned income.",
                fields_involved=["claiming_dependent_care_credit", "earned_income"],
                suggestion="Both spouses must have earned income to claim this credit (unless student or disabled).",
                irs_reference="Pub 503"
            )
        return None


# Singleton instance for easy use
_detector = None

def get_detector() -> ContradictionDetector:
    """Get singleton detector instance."""
    global _detector
    if _detector is None:
        _detector = ContradictionDetector()
    return _detector


def check_contradictions(data: Dict[str, Any]) -> ContradictionResult:
    """
    Convenience function to check for contradictions.

    Args:
        data: Tax return data dictionary

    Returns:
        ContradictionResult with all detected issues
    """
    return get_detector().check(data)
