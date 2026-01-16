"""
Dependent Qualification Validator.

Implements IRS rules for determining if an individual qualifies as a dependent:
- Qualifying Child (QC) 5-part test: BR-0023 to BR-0027
- Qualifying Relative (QR) 4-part test: BR3-0206 to BR3-0209
- Tiebreaker rules: BR3-0210 to BR3-0212
- Form 8332 release handling: BR3-0213

Based on IRS Publication 501, Publication 596 (EITC), and Tax Year 2025 rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import List, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from models.taxpayer import Dependent, TaxpayerInfo


class DependentQualificationType(str, Enum):
    """Type of dependent qualification."""
    QUALIFYING_CHILD = "qualifying_child"
    QUALIFYING_RELATIVE = "qualifying_relative"
    NOT_QUALIFIED = "not_qualified"


class QualificationFailureReason(str, Enum):
    """Reasons for failing qualification tests."""
    # Qualifying Child failures
    RELATIONSHIP_TEST_FAILED = "relationship_test_failed"
    AGE_TEST_FAILED = "age_test_failed"
    RESIDENCY_TEST_FAILED = "residency_test_failed"
    SUPPORT_TEST_FAILED = "support_test_failed"
    JOINT_RETURN_TEST_FAILED = "joint_return_test_failed"

    # Qualifying Relative failures
    NOT_QC_TEST_FAILED = "not_qc_test_failed"
    QR_RELATIONSHIP_TEST_FAILED = "qr_relationship_test_failed"
    GROSS_INCOME_TEST_FAILED = "gross_income_test_failed"
    QR_SUPPORT_TEST_FAILED = "qr_support_test_failed"

    # Common failures
    CITIZENSHIP_TEST_FAILED = "citizenship_test_failed"
    CLAIMED_BY_ANOTHER = "claimed_by_another"
    TIEBREAKER_LOST = "tiebreaker_lost"


@dataclass
class QualificationTestResult:
    """Result of an individual qualification test."""
    test_name: str
    passed: bool
    reason: str
    details: Optional[str] = None
    rule_reference: Optional[str] = None  # BR number


@dataclass
class DependentQualificationResult:
    """Complete result of dependent qualification analysis."""
    dependent_name: str
    qualification_type: DependentQualificationType
    is_qualified: bool

    # Test results
    qc_test_results: List[QualificationTestResult] = field(default_factory=list)
    qr_test_results: List[QualificationTestResult] = field(default_factory=list)
    tiebreaker_result: Optional[QualificationTestResult] = None

    # Credit eligibility
    eligible_for_ctc: bool = False
    eligible_for_eitc_child: bool = False
    eligible_for_odc: bool = False  # Other Dependent Credit
    eligible_for_dependent_care: bool = False

    # Summary
    failure_reasons: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    # Form 8332 status
    form_8332_applies: bool = False
    form_8332_credit_claimant: Optional[str] = None


# IRS Qualifying Child relationship categories (BR-0024)
QUALIFYING_CHILD_RELATIONSHIPS = {
    # Direct descendants
    "son", "daughter", "stepson", "stepdaughter", "foster_child",
    # Siblings and half-siblings
    "brother", "sister", "half_brother", "half_sister",
    "stepbrother", "stepsister",
    # Descendants of above
    "grandchild", "niece", "nephew",
}

# IRS Qualifying Relative relationships (BR3-0207)
QUALIFYING_RELATIVE_RELATIONSHIPS = QUALIFYING_CHILD_RELATIONSHIPS | {
    # Ancestors
    "parent", "grandparent",
    # Extended family
    "aunt", "uncle", "in_law",
    # Non-relative (must live full year)
    "other_household_member",
}

# Tax Year 2025 thresholds (IRS Rev. Proc. 2024-40)
TAX_YEAR_2025_LIMITS = {
    "qr_gross_income_limit": 5050,  # 2025 Qualifying Relative gross income test
    "qc_age_limit": 19,  # Under 19 at end of year
    "qc_student_age_limit": 24,  # Under 24 if full-time student
    "residency_months_required": 6,  # More than half the year
    "support_percentage_threshold": 50.0,  # More than half
}


class DependentValidator:
    """
    Validates dependent eligibility per IRS rules.

    Implements the complete qualification framework:
    1. Qualifying Child (QC) 5-part test
    2. Qualifying Relative (QR) 4-part test
    3. Tiebreaker rules for multiple claimants
    4. Form 8332 release handling
    """

    def __init__(self, tax_year: int = 2025):
        """Initialize validator with tax year-specific limits."""
        self.tax_year = tax_year
        self.limits = TAX_YEAR_2025_LIMITS.copy()

        # Adjust limits for different tax years if needed
        if tax_year < 2025:
            # 2024 limits
            self.limits["qr_gross_income_limit"] = 4700

    def validate_dependent(
        self,
        dependent: "Dependent",
        taxpayer_agi: float,
        taxpayer_is_parent: bool = False,
    ) -> DependentQualificationResult:
        """
        Validate if an individual qualifies as a dependent.

        First attempts Qualifying Child test, then Qualifying Relative test.

        Args:
            dependent: The Dependent object to validate
            taxpayer_agi: Taxpayer's AGI for tiebreaker rules
            taxpayer_is_parent: Whether taxpayer is parent of the dependent

        Returns:
            DependentQualificationResult with full analysis
        """
        result = DependentQualificationResult(
            dependent_name=dependent.name,
            qualification_type=DependentQualificationType.NOT_QUALIFIED,
            is_qualified=False,
        )

        # First, check citizenship/residency (applies to all dependents)
        citizenship_result = self._test_citizenship_residency(dependent)
        if not citizenship_result.passed:
            result.failure_reasons.append(citizenship_result.reason)
            result.recommendations.append(
                "Dependent must be a U.S. citizen, resident alien, or "
                "resident of Canada or Mexico"
            )
            return result

        # Check if already claimed by another (BR3-0206)
        if dependent.is_claimed_by_another:
            result.failure_reasons.append(
                "Dependent is claimed by another taxpayer"
            )
            return result

        # Try Qualifying Child test first (BR-0023 to BR-0027)
        qc_passed, qc_results = self._test_qualifying_child(dependent)
        result.qc_test_results = qc_results

        if qc_passed:
            # Check tiebreaker if another person might claim
            tiebreaker_passed = True
            if dependent.other_claimant_agi is not None:
                tiebreaker_result = self._apply_tiebreaker_rules(
                    dependent, taxpayer_agi, taxpayer_is_parent
                )
                result.tiebreaker_result = tiebreaker_result
                tiebreaker_passed = tiebreaker_result.passed

            if tiebreaker_passed:
                result.qualification_type = DependentQualificationType.QUALIFYING_CHILD
                result.is_qualified = True

                # Determine credit eligibility
                self._determine_qc_credit_eligibility(dependent, result)

                # Check for Form 8332 (custodial parent release)
                if dependent.has_form_8332_release:
                    self._apply_form_8332_rules(dependent, result)

                return result
            else:
                result.failure_reasons.append("Lost tiebreaker to another claimant")

        # If QC test failed, try Qualifying Relative test (BR3-0206 to BR3-0209)
        qr_passed, qr_results = self._test_qualifying_relative(dependent)
        result.qr_test_results = qr_results

        if qr_passed:
            result.qualification_type = DependentQualificationType.QUALIFYING_RELATIVE
            result.is_qualified = True

            # QRs are not eligible for CTC or EITC child, but may get ODC
            result.eligible_for_odc = True
            result.eligible_for_ctc = False
            result.eligible_for_eitc_child = False

            return result

        # Neither test passed - collect all failure reasons
        for test in qc_results:
            if not test.passed:
                result.failure_reasons.append(f"QC: {test.reason}")
        for test in qr_results:
            if not test.passed:
                result.failure_reasons.append(f"QR: {test.reason}")

        # Add recommendations
        self._add_recommendations(dependent, result)

        return result

    def _test_citizenship_residency(
        self, dependent: "Dependent"
    ) -> QualificationTestResult:
        """
        Test citizenship/residency requirement (applies to all dependents).

        Per IRS rules, dependent must be:
        - U.S. citizen
        - U.S. resident alien
        - U.S. national
        - Resident of Canada or Mexico
        """
        passed = dependent.is_us_citizen or dependent.is_us_resident

        return QualificationTestResult(
            test_name="Citizenship/Residency Test",
            passed=passed,
            reason="Meets citizenship/residency requirement" if passed
                   else "Does not meet citizenship/residency requirement",
            details="Must be U.S. citizen, resident alien, or resident of Canada/Mexico",
            rule_reference="IRS Pub 501"
        )

    def _test_qualifying_child(
        self, dependent: "Dependent"
    ) -> tuple[bool, List[QualificationTestResult]]:
        """
        Apply the 5-part Qualifying Child test (BR-0023 to BR-0027).

        Tests:
        1. Relationship test (BR-0024)
        2. Age test (BR-0025)
        3. Residency test (BR-0026)
        4. Support test (BR-0027)
        5. Joint return test (BR-0023)

        Returns:
            Tuple of (all_passed, list_of_test_results)
        """
        results = []

        # Test 1: Relationship Test (BR-0024)
        relationship = self._normalize_relationship(dependent)
        rel_passed = relationship in QUALIFYING_CHILD_RELATIONSHIPS
        results.append(QualificationTestResult(
            test_name="Relationship Test",
            passed=rel_passed,
            reason=f"Relationship '{relationship}' {'qualifies' if rel_passed else 'does not qualify'} as QC relationship",
            details="Must be child, sibling, or descendant thereof",
            rule_reference="BR-0024"
        ))

        # Test 2: Age Test (BR-0025)
        age_passed = self._check_age_test(dependent)
        age_reason = self._get_age_test_reason(dependent, age_passed)
        results.append(QualificationTestResult(
            test_name="Age Test",
            passed=age_passed,
            reason=age_reason,
            details=f"Under {self.limits['qc_age_limit']}, or under {self.limits['qc_student_age_limit']} if student, or any age if disabled",
            rule_reference="BR-0025"
        ))

        # Test 3: Residency Test (BR-0026)
        res_passed = dependent.months_lived_with_taxpayer > self.limits["residency_months_required"]
        results.append(QualificationTestResult(
            test_name="Residency Test",
            passed=res_passed,
            reason=f"Lived with taxpayer {dependent.months_lived_with_taxpayer} months "
                   f"({'meets' if res_passed else 'does not meet'} >6 month requirement)",
            details="Must live with taxpayer for more than half the year",
            rule_reference="BR-0026"
        ))

        # Test 4: Support Test (BR-0027)
        # Child must NOT have provided more than half of own support
        sup_passed = dependent.provided_own_support_percentage < self.limits["support_percentage_threshold"]
        results.append(QualificationTestResult(
            test_name="Support Test",
            passed=sup_passed,
            reason=f"Dependent provided {dependent.provided_own_support_percentage}% of own support "
                   f"({'passes' if sup_passed else 'fails'} - must be <50%)",
            details="Dependent must NOT have provided more than half of own support",
            rule_reference="BR-0027"
        ))

        # Test 5: Joint Return Test (BR-0023)
        # Cannot file joint return with spouse (exception: only filed to claim refund)
        jr_passed = not dependent.filed_joint_return or dependent.joint_return_only_for_refund
        jr_reason = "Did not file joint return"
        if dependent.filed_joint_return:
            if dependent.joint_return_only_for_refund:
                jr_reason = "Filed joint return only to claim refund (exception applies)"
            else:
                jr_reason = "Filed joint return with spouse (disqualifies as QC)"
        results.append(QualificationTestResult(
            test_name="Joint Return Test",
            passed=jr_passed,
            reason=jr_reason,
            details="Cannot file joint return (unless only to claim refund)",
            rule_reference="BR-0023"
        ))

        all_passed = all(r.passed for r in results)
        return all_passed, results

    def _test_qualifying_relative(
        self, dependent: "Dependent"
    ) -> tuple[bool, List[QualificationTestResult]]:
        """
        Apply the 4-part Qualifying Relative test (BR3-0206 to BR3-0209).

        Tests:
        1. Not a Qualifying Child test (BR3-0206)
        2. Member of household OR relationship test (BR3-0207)
        3. Gross income test (BR3-0208)
        4. Support test (BR3-0209)

        Returns:
            Tuple of (all_passed, list_of_test_results)
        """
        results = []

        # Test 1: Not a Qualifying Child (BR3-0206)
        # The person must not be anyone's qualifying child
        not_qc = not dependent.is_claimed_by_another
        results.append(QualificationTestResult(
            test_name="Not a Qualifying Child Test",
            passed=not_qc,
            reason="Not claimed as qualifying child by another taxpayer" if not_qc
                   else "Is claimed as qualifying child by another taxpayer",
            details="Cannot be qualifying child of another taxpayer",
            rule_reference="BR3-0206"
        ))

        # Test 2: Relationship OR Member of Household Test (BR3-0207)
        relationship = self._normalize_relationship(dependent)
        is_related = relationship in QUALIFYING_RELATIVE_RELATIONSHIPS

        # Non-relatives must live full year
        if relationship == "other_household_member":
            lived_full_year = dependent.months_lived_with_taxpayer >= 12
            rel_passed = lived_full_year
            rel_reason = f"Non-relative lived {dependent.months_lived_with_taxpayer} months (must be 12)"
        else:
            rel_passed = is_related
            rel_reason = f"Relationship '{relationship}' {'qualifies' if is_related else 'does not qualify'}"

        results.append(QualificationTestResult(
            test_name="Relationship/Household Member Test",
            passed=rel_passed,
            reason=rel_reason,
            details="Must be related OR live as member of household full year",
            rule_reference="BR3-0207"
        ))

        # Test 3: Gross Income Test (BR3-0208)
        income_limit = self.limits["qr_gross_income_limit"]
        income_passed = dependent.gross_income < income_limit
        results.append(QualificationTestResult(
            test_name="Gross Income Test",
            passed=income_passed,
            reason=f"Gross income ${dependent.gross_income:,.0f} "
                   f"{'is under' if income_passed else 'exceeds'} ${income_limit:,} limit",
            details=f"Gross income must be less than ${income_limit:,} for {self.tax_year}",
            rule_reference="BR3-0208"
        ))

        # Test 4: Support Test (BR3-0209)
        # Taxpayer must provide MORE than half of support
        support_passed = dependent.taxpayer_provided_support_percentage > self.limits["support_percentage_threshold"]
        results.append(QualificationTestResult(
            test_name="Support Test",
            passed=support_passed,
            reason=f"Taxpayer provided {dependent.taxpayer_provided_support_percentage}% of support "
                   f"({'meets' if support_passed else 'does not meet'} >50% requirement)",
            details="Taxpayer must provide MORE than half of total support",
            rule_reference="BR3-0209"
        ))

        all_passed = all(r.passed for r in results)
        return all_passed, results

    def _apply_tiebreaker_rules(
        self,
        dependent: "Dependent",
        taxpayer_agi: float,
        taxpayer_is_parent: bool
    ) -> QualificationTestResult:
        """
        Apply tiebreaker rules when multiple people can claim the dependent.

        IRS Tiebreaker Rules (BR3-0210 to BR3-0212):
        1. If only one is parent, parent wins (BR3-0210)
        2. If both are parents, parent with longer residence wins (BR3-0211)
        3. If residence equal, parent with higher AGI wins
        4. If neither is parent, person with higher AGI wins (BR3-0212)

        Args:
            dependent: Dependent with other_claimant_agi set
            taxpayer_agi: This taxpayer's AGI
            taxpayer_is_parent: Whether this taxpayer is the parent

        Returns:
            QualificationTestResult indicating if this taxpayer wins
        """
        other_agi = dependent.other_claimant_agi or 0
        other_is_parent = dependent.other_claimant_is_parent

        # Rule 1: Only one is parent (BR3-0210)
        if taxpayer_is_parent and not other_is_parent:
            return QualificationTestResult(
                test_name="Tiebreaker Rule",
                passed=True,
                reason="Taxpayer wins: Parent vs non-parent",
                details="Parent always wins over non-parent",
                rule_reference="BR3-0210"
            )

        if other_is_parent and not taxpayer_is_parent:
            return QualificationTestResult(
                test_name="Tiebreaker Rule",
                passed=False,
                reason="Other claimant wins: They are the parent",
                details="Parent always wins over non-parent",
                rule_reference="BR3-0210"
            )

        # Rule 2 & 3: Both are parents - residence then AGI (BR3-0211)
        if taxpayer_is_parent and other_is_parent:
            # We don't have other parent's residence info, use AGI
            if taxpayer_agi > other_agi:
                return QualificationTestResult(
                    test_name="Tiebreaker Rule",
                    passed=True,
                    reason=f"Taxpayer wins: Higher AGI (${taxpayer_agi:,.0f} vs ${other_agi:,.0f})",
                    details="Between parents, higher AGI wins",
                    rule_reference="BR3-0211"
                )
            else:
                return QualificationTestResult(
                    test_name="Tiebreaker Rule",
                    passed=False,
                    reason=f"Other parent wins: Higher AGI (${other_agi:,.0f} vs ${taxpayer_agi:,.0f})",
                    details="Between parents, higher AGI wins",
                    rule_reference="BR3-0211"
                )

        # Rule 4: Neither is parent - higher AGI wins (BR3-0212)
        if taxpayer_agi > other_agi:
            return QualificationTestResult(
                test_name="Tiebreaker Rule",
                passed=True,
                reason=f"Taxpayer wins: Higher AGI (${taxpayer_agi:,.0f} vs ${other_agi:,.0f})",
                details="Higher AGI wins between non-parents",
                rule_reference="BR3-0212"
            )
        else:
            return QualificationTestResult(
                test_name="Tiebreaker Rule",
                passed=False,
                reason=f"Other claimant wins: Higher AGI (${other_agi:,.0f} vs ${taxpayer_agi:,.0f})",
                details="Higher AGI wins between non-parents",
                rule_reference="BR3-0212"
            )

    def _apply_form_8332_rules(
        self,
        dependent: "Dependent",
        result: DependentQualificationResult
    ) -> None:
        """
        Apply Form 8332 rules for custodial parent release (BR3-0213).

        When custodial parent releases claim to noncustodial parent:
        - Noncustodial parent can claim: CTC/ODC, dependency exemption
        - Custodial parent keeps: EITC, dependent care credit, HOH status
        """
        if not dependent.has_form_8332_release:
            return

        result.form_8332_applies = True

        # Check if this tax year is covered
        if dependent.form_8332_years:
            if self.tax_year in dependent.form_8332_years:
                result.form_8332_credit_claimant = "noncustodial_parent"
                result.recommendations.append(
                    "Form 8332 applies - noncustodial parent claims CTC/dependency, "
                    "custodial parent claims EITC/dependent care credit"
                )
            else:
                result.form_8332_credit_claimant = "custodial_parent"
                result.recommendations.append(
                    f"Form 8332 does not cover tax year {self.tax_year}"
                )
        else:
            # No specific years means all future years
            result.form_8332_credit_claimant = "noncustodial_parent"

    def _determine_qc_credit_eligibility(
        self,
        dependent: "Dependent",
        result: DependentQualificationResult
    ) -> None:
        """
        Determine which credits a Qualifying Child is eligible for.
        """
        # Child Tax Credit: Under age 17 at end of year
        result.eligible_for_ctc = dependent.age < 17

        # EITC child: Meets QC tests (already validated)
        # Additional requirements: age under 19, or under 24 if student,
        # or any age if disabled
        result.eligible_for_eitc_child = (
            dependent.age < 19 or
            (dependent.is_student and dependent.age < 24) or
            dependent.is_permanently_disabled
        )

        # Dependent Care Credit: Under age 13 OR disabled
        result.eligible_for_dependent_care = (
            dependent.age < 13 or dependent.is_permanently_disabled
        )

        # Other Dependent Credit: Age 17+ but qualifies as dependent
        result.eligible_for_odc = not result.eligible_for_ctc

    def _check_age_test(self, dependent: "Dependent") -> bool:
        """Check if dependent passes the QC age test."""
        # Under 19 at end of year
        if dependent.age < self.limits["qc_age_limit"]:
            return True

        # Under 24 AND full-time student
        if dependent.is_student and dependent.age < self.limits["qc_student_age_limit"]:
            return True

        # Any age if permanently and totally disabled
        if dependent.is_permanently_disabled:
            return True

        return False

    def _get_age_test_reason(self, dependent: "Dependent", passed: bool) -> str:
        """Generate descriptive reason for age test result."""
        if dependent.is_permanently_disabled:
            return f"Age {dependent.age}: Permanently disabled (no age limit applies)"

        if dependent.is_student:
            if dependent.age < self.limits["qc_student_age_limit"]:
                return f"Age {dependent.age}: Full-time student under {self.limits['qc_student_age_limit']} (qualifies)"
            else:
                return f"Age {dependent.age}: Student but {self.limits['qc_student_age_limit']}+ (does not qualify)"

        if dependent.age < self.limits["qc_age_limit"]:
            return f"Age {dependent.age}: Under {self.limits['qc_age_limit']} (qualifies)"
        else:
            return f"Age {dependent.age}: {self.limits['qc_age_limit']}+ and not student/disabled (does not qualify)"

    def _normalize_relationship(self, dependent: "Dependent") -> str:
        """Normalize relationship string for comparison."""
        # Use relationship_type if available, otherwise use relationship string
        if dependent.relationship_type:
            return dependent.relationship_type.value.lower()

        relationship = dependent.relationship.lower().strip()

        # Handle common variations
        relationship_map = {
            "child": "son",  # Generic child -> son (works for either)
            "kid": "son",
            "stepchild": "stepson",
            "step-son": "stepson",
            "step-daughter": "stepdaughter",
            "step-child": "stepson",
            "half-brother": "half_brother",
            "half-sister": "half_sister",
            "grand child": "grandchild",
            "grand-child": "grandchild",
            "grand son": "grandchild",
            "grand daughter": "grandchild",
            "grandson": "grandchild",
            "granddaughter": "grandchild",
            "mom": "parent",
            "dad": "parent",
            "mother": "parent",
            "father": "parent",
            "step-parent": "parent",
            "stepparent": "parent",
            "grandmother": "grandparent",
            "grandfather": "grandparent",
            "grandma": "grandparent",
            "grandpa": "grandparent",
            "mother-in-law": "in_law",
            "father-in-law": "in_law",
            "son-in-law": "in_law",
            "daughter-in-law": "in_law",
            "brother-in-law": "in_law",
            "sister-in-law": "in_law",
            "other": "other_household_member",
            "unrelated": "other_household_member",
            "non-relative": "other_household_member",
        }

        return relationship_map.get(relationship, relationship.replace("-", "_").replace(" ", "_"))

    def _add_recommendations(
        self,
        dependent: "Dependent",
        result: DependentQualificationResult
    ) -> None:
        """Add helpful recommendations based on test failures."""
        for test in result.qc_test_results:
            if not test.passed:
                if test.test_name == "Age Test":
                    if dependent.age >= 24:
                        result.recommendations.append(
                            "Consider Qualifying Relative test if taxpayer provides >50% support"
                        )
                    elif dependent.age >= 19 and not dependent.is_student:
                        result.recommendations.append(
                            "If attending school full-time for 5+ months, may qualify as student"
                        )

                elif test.test_name == "Residency Test":
                    result.recommendations.append(
                        "Exceptions exist for temporary absences (school, illness, military)"
                    )

                elif test.test_name == "Support Test":
                    if dependent.provided_own_support_percentage >= 50:
                        result.recommendations.append(
                            "If dependent provided majority of own support, "
                            "they likely cannot be claimed as a dependent"
                        )

        for test in result.qr_test_results:
            if not test.passed:
                if test.test_name == "Gross Income Test":
                    result.recommendations.append(
                        f"Gross income limit for {self.tax_year} is "
                        f"${self.limits['qr_gross_income_limit']:,}. "
                        "Social Security and tax-exempt income may be excluded."
                    )


def validate_all_dependents(
    taxpayer_info: "TaxpayerInfo",
    taxpayer_agi: float
) -> List[DependentQualificationResult]:
    """
    Validate all dependents for a taxpayer.

    Args:
        taxpayer_info: TaxpayerInfo containing list of dependents
        taxpayer_agi: Taxpayer's AGI for tiebreaker rules

    Returns:
        List of DependentQualificationResult for each dependent
    """
    validator = DependentValidator()
    results = []

    for dependent in taxpayer_info.dependents:
        result = validator.validate_dependent(
            dependent,
            taxpayer_agi,
            taxpayer_is_parent=dependent.is_parent_of_child
        )
        results.append(result)

    return results


def get_eitc_qualifying_children(
    taxpayer_info: "TaxpayerInfo",
    taxpayer_agi: float
) -> int:
    """
    Count qualifying children for EITC purposes.

    EITC requires children to meet Qualifying Child tests with
    additional EITC-specific requirements.

    Args:
        taxpayer_info: TaxpayerInfo with dependents
        taxpayer_agi: Taxpayer's AGI

    Returns:
        Number of EITC qualifying children (max 3 for EITC purposes)
    """
    results = validate_all_dependents(taxpayer_info, taxpayer_agi)

    eitc_children = sum(
        1 for r in results
        if r.is_qualified and r.eligible_for_eitc_child
    )

    # EITC maxes out at 3 children
    return min(eitc_children, 3)


def get_ctc_qualifying_children(
    taxpayer_info: "TaxpayerInfo",
    taxpayer_agi: float
) -> int:
    """
    Count qualifying children for Child Tax Credit.

    CTC requires child to be under age 17 at end of tax year.

    Args:
        taxpayer_info: TaxpayerInfo with dependents
        taxpayer_agi: Taxpayer's AGI

    Returns:
        Number of CTC qualifying children
    """
    results = validate_all_dependents(taxpayer_info, taxpayer_agi)

    return sum(
        1 for r in results
        if r.is_qualified and r.eligible_for_ctc
    )


def get_other_dependents_count(
    taxpayer_info: "TaxpayerInfo",
    taxpayer_agi: float
) -> int:
    """
    Count dependents eligible for Other Dependent Credit (ODC).

    ODC is $500 for dependents who don't qualify for CTC.

    Args:
        taxpayer_info: TaxpayerInfo with dependents
        taxpayer_agi: Taxpayer's AGI

    Returns:
        Number of ODC-eligible dependents
    """
    results = validate_all_dependents(taxpayer_info, taxpayer_agi)

    return sum(
        1 for r in results
        if r.is_qualified and r.eligible_for_odc
    )
