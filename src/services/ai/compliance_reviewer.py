"""
AI-Powered Compliance Reviewer.

Uses Claude for comprehensive compliance checking:
- Circular 230 compliance
- Preparer due diligence requirements
- EITC/CTC due diligence (Form 8867)
- Accuracy penalty analysis
- Fraud indicator detection
- Documentation requirements

Usage:
    from services.ai.compliance_reviewer import get_compliance_reviewer

    reviewer = get_compliance_reviewer()

    # Full compliance review
    report = await reviewer.review_return(tax_return_data)

    # Specific due diligence check
    eitc_check = await reviewer.check_eitc_due_diligence(tax_return_data)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from config.ai_providers import AIProvider, ModelCapability
from services.ai.unified_ai_service import (
    UnifiedAIService,
    AIMessage,
    AIResponse,
    get_ai_service,
)

logger = logging.getLogger(__name__)


class ComplianceArea(str, Enum):
    """Areas of compliance review."""
    CIRCULAR_230 = "circular_230"           # Treasury Circular 230
    PREPARER_DUE_DILIGENCE = "preparer_dd"  # General preparer requirements
    EITC_DUE_DILIGENCE = "eitc_dd"          # Form 8867 requirements
    CTC_DUE_DILIGENCE = "ctc_dd"            # Child Tax Credit
    AOTC_DUE_DILIGENCE = "aotc_dd"          # American Opportunity Credit
    HOH_DUE_DILIGENCE = "hoh_dd"            # Head of Household
    ACCURACY_PENALTIES = "accuracy"          # IRC 6662
    FRAUD_PENALTIES = "fraud"               # IRC 6663
    DOCUMENTATION = "documentation"          # Record-keeping requirements


class ComplianceStatus(str, Enum):
    """Status of compliance check."""
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    NEEDS_REVIEW = "needs_review"


@dataclass
class ComplianceIssue:
    """A compliance issue found during review."""
    area: ComplianceArea
    status: ComplianceStatus
    title: str
    description: str
    requirement: str
    current_state: Optional[str] = None
    remediation: Optional[str] = None
    irc_reference: Optional[str] = None
    form_reference: Optional[str] = None
    penalty_risk: Optional[str] = None


@dataclass
class DueDiligenceChecklist:
    """Due diligence checklist for specific credits."""
    credit_type: str  # "EITC", "CTC", "AOTC", "HOH"
    form_number: str  # "8867" for EITC/CTC/AOTC/HOH
    questions: List[Dict[str, Any]]  # Question, answer, compliant flag
    overall_status: ComplianceStatus
    missing_items: List[str]
    recommendations: List[str]


@dataclass
class ComplianceReport:
    """Complete compliance review report."""
    return_id: Optional[str]
    preparer_ptin: Optional[str]
    review_date: datetime
    overall_status: ComplianceStatus
    issues: List[ComplianceIssue]
    due_diligence_checklists: List[DueDiligenceChecklist]
    circular_230_compliant: bool
    penalties_risk_level: str  # "low", "medium", "high"
    estimated_penalty_exposure: float
    recommendations: List[str]
    certifications_needed: List[str]
    raw_analysis: str
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# COMPLIANCE REQUIREMENTS
# =============================================================================

EITC_DUE_DILIGENCE_QUESTIONS = [
    {
        "id": "eitc_1",
        "question": "Did you complete Form 8867 for this return?",
        "requirement": "Required for all returns claiming EITC",
        "irc": "IRC 6695(g)"
    },
    {
        "id": "eitc_2",
        "question": "Did you verify taxpayer's earned income with documentation?",
        "requirement": "W-2s, 1099s, or self-employment records required",
        "irc": "IRC 6695(g)"
    },
    {
        "id": "eitc_3",
        "question": "Did you verify qualifying children meet all tests?",
        "requirement": "Age, relationship, residency, joint return tests",
        "irc": "IRC 32(c)(3)"
    },
    {
        "id": "eitc_4",
        "question": "Did you ask about and document residency?",
        "requirement": "Child must live with taxpayer for more than half the year",
        "irc": "IRC 32(c)(3)(A)(ii)"
    },
    {
        "id": "eitc_5",
        "question": "Did you verify filing status eligibility?",
        "requirement": "Cannot be MFS, must meet other requirements",
        "irc": "IRC 32(d)"
    },
    {
        "id": "eitc_6",
        "question": "Did you retain records as required?",
        "requirement": "Must retain records for 3 years",
        "irc": "IRC 6695(g)"
    },
]

CTC_DUE_DILIGENCE_QUESTIONS = [
    {
        "id": "ctc_1",
        "question": "Did you verify child meets age requirement?",
        "requirement": "Under age 17 at end of tax year",
        "irc": "IRC 24(c)(1)"
    },
    {
        "id": "ctc_2",
        "question": "Did you verify relationship to taxpayer?",
        "requirement": "Son, daughter, stepchild, foster child, sibling, etc.",
        "irc": "IRC 152(c)(2)"
    },
    {
        "id": "ctc_3",
        "question": "Did you verify US citizenship or residency?",
        "requirement": "Child must be US citizen, national, or resident alien",
        "irc": "IRC 24(c)(2)"
    },
    {
        "id": "ctc_4",
        "question": "Did you obtain child's SSN?",
        "requirement": "Valid SSN required (not ITIN)",
        "irc": "IRC 24(h)(7)"
    },
]

CIRCULAR_230_REQUIREMENTS = [
    "Must not sign return if taxpayer refuses to correct known errors",
    "Must exercise due diligence in preparing returns",
    "Must advise taxpayer of penalties for underpayment",
    "Must not take frivolous positions",
    "Must maintain records for 3 years",
    "Must return client records upon request",
    "Must provide copy of return to taxpayer",
]


# =============================================================================
# COMPLIANCE REVIEWER SERVICE
# =============================================================================

class ComplianceReviewer:
    """
    AI-powered compliance reviewer using Claude.

    Features:
    - Comprehensive compliance checking
    - Due diligence verification
    - Penalty risk assessment
    - Documentation requirements
    - Remediation recommendations
    """

    def __init__(self, ai_service: Optional[UnifiedAIService] = None):
        self.ai_service = ai_service or get_ai_service()

    async def review_return(
        self,
        return_data: Dict[str, Any],
        preparer_info: Optional[Dict[str, str]] = None
    ) -> ComplianceReport:
        """
        Perform comprehensive compliance review.

        Args:
            return_data: Tax return data
            preparer_info: Preparer information (PTIN, name, etc.)

        Returns:
            ComplianceReport with all findings
        """
        issues = []
        checklists = []
        recommendations = []
        certifications = []

        # Check due diligence requirements for applicable credits
        if return_data.get("claims_eitc"):
            eitc_checklist = await self.check_eitc_due_diligence(return_data)
            checklists.append(eitc_checklist)
            if eitc_checklist.overall_status != ComplianceStatus.PASS:
                issues.extend(self._checklist_to_issues(eitc_checklist, ComplianceArea.EITC_DUE_DILIGENCE))
            certifications.append("Form 8867 - Paid Preparer's Due Diligence Checklist")

        if return_data.get("claims_ctc"):
            ctc_checklist = await self.check_ctc_due_diligence(return_data)
            checklists.append(ctc_checklist)
            if ctc_checklist.overall_status != ComplianceStatus.PASS:
                issues.extend(self._checklist_to_issues(ctc_checklist, ComplianceArea.CTC_DUE_DILIGENCE))

        if return_data.get("claims_aotc"):
            certifications.append("Form 8863 - Education Credits")

        if return_data.get("filing_status") == "head_of_household":
            hoh_issues = await self._check_hoh_requirements(return_data)
            issues.extend(hoh_issues)

        # Check Circular 230 compliance
        circular_230_issues = await self._check_circular_230(return_data, preparer_info)
        issues.extend(circular_230_issues)
        circular_230_compliant = not any(
            i.area == ComplianceArea.CIRCULAR_230 and i.status == ComplianceStatus.FAIL
            for i in issues
        )

        # Check accuracy penalty exposure
        accuracy_issues = await self._check_accuracy_penalties(return_data)
        issues.extend(accuracy_issues)

        # AI deep compliance analysis
        ai_issues = await self._ai_compliance_analysis(return_data, issues)
        issues.extend(ai_issues)

        # Calculate penalty risk
        penalty_risk, penalty_exposure = self._assess_penalty_risk(issues, return_data)

        # Generate recommendations
        recommendations = self._generate_recommendations(issues)

        # Determine overall status
        overall_status = self._determine_overall_status(issues)

        return ComplianceReport(
            return_id=return_data.get("return_id"),
            preparer_ptin=preparer_info.get("ptin") if preparer_info else None,
            review_date=datetime.now(),
            overall_status=overall_status,
            issues=issues,
            due_diligence_checklists=checklists,
            circular_230_compliant=circular_230_compliant,
            penalties_risk_level=penalty_risk,
            estimated_penalty_exposure=penalty_exposure,
            recommendations=recommendations,
            certifications_needed=certifications,
            raw_analysis=""
        )

    async def check_eitc_due_diligence(
        self,
        return_data: Dict[str, Any]
    ) -> DueDiligenceChecklist:
        """
        Check EITC due diligence requirements (Form 8867).

        Args:
            return_data: Tax return data

        Returns:
            DueDiligenceChecklist for EITC
        """
        questions = []
        missing = []

        for q in EITC_DUE_DILIGENCE_QUESTIONS:
            # Evaluate each question based on return data
            answer, compliant = self._evaluate_eitc_question(q["id"], return_data)

            questions.append({
                "id": q["id"],
                "question": q["question"],
                "requirement": q["requirement"],
                "irc": q["irc"],
                "answer": answer,
                "compliant": compliant
            })

            if not compliant:
                missing.append(q["question"])

        overall = ComplianceStatus.PASS if not missing else (
            ComplianceStatus.FAIL if len(missing) > 2 else ComplianceStatus.WARNING
        )

        recommendations = []
        if missing:
            recommendations.append("Complete all Form 8867 questions before filing")
            recommendations.append("Document all due diligence inquiries made")
            recommendations.append("Retain copies of all supporting documentation")

        return DueDiligenceChecklist(
            credit_type="EITC",
            form_number="8867",
            questions=questions,
            overall_status=overall,
            missing_items=missing,
            recommendations=recommendations
        )

    async def check_ctc_due_diligence(
        self,
        return_data: Dict[str, Any]
    ) -> DueDiligenceChecklist:
        """
        Check Child Tax Credit due diligence requirements.

        Args:
            return_data: Tax return data

        Returns:
            DueDiligenceChecklist for CTC
        """
        questions = []
        missing = []

        for q in CTC_DUE_DILIGENCE_QUESTIONS:
            answer, compliant = self._evaluate_ctc_question(q["id"], return_data)

            questions.append({
                "id": q["id"],
                "question": q["question"],
                "requirement": q["requirement"],
                "irc": q["irc"],
                "answer": answer,
                "compliant": compliant
            })

            if not compliant:
                missing.append(q["question"])

        overall = ComplianceStatus.PASS if not missing else (
            ComplianceStatus.FAIL if len(missing) > 1 else ComplianceStatus.WARNING
        )

        return DueDiligenceChecklist(
            credit_type="CTC",
            form_number="8867",
            questions=questions,
            overall_status=overall,
            missing_items=missing,
            recommendations=["Verify all qualifying children meet requirements"] if missing else []
        )

    async def _check_hoh_requirements(
        self,
        return_data: Dict[str, Any]
    ) -> List[ComplianceIssue]:
        """Check Head of Household requirements."""
        issues = []

        # Must be unmarried (or considered unmarried)
        if return_data.get("marital_status") == "married":
            if not return_data.get("lived_apart_6_months"):
                issues.append(ComplianceIssue(
                    area=ComplianceArea.HOH_DUE_DILIGENCE,
                    status=ComplianceStatus.FAIL,
                    title="HOH Status - Marital Status Issue",
                    description="Taxpayer is married but claiming HOH",
                    requirement="Must be unmarried or considered unmarried (lived apart 6+ months)",
                    remediation="Verify taxpayer lived apart from spouse for last 6 months of year",
                    irc_reference="IRC 2(b)"
                ))

        # Must have qualifying person
        if not return_data.get("qualifying_person"):
            issues.append(ComplianceIssue(
                area=ComplianceArea.HOH_DUE_DILIGENCE,
                status=ComplianceStatus.WARNING,
                title="HOH Status - Qualifying Person",
                description="No qualifying person documented for HOH status",
                requirement="Must have qualifying child or relative",
                remediation="Document qualifying person and their relationship",
                irc_reference="IRC 2(b)(1)"
            ))

        return issues

    async def _check_circular_230(
        self,
        return_data: Dict[str, Any],
        preparer_info: Optional[Dict[str, str]]
    ) -> List[ComplianceIssue]:
        """Check Circular 230 compliance."""
        issues = []

        # Check for frivolous positions
        if return_data.get("has_frivolous_position"):
            issues.append(ComplianceIssue(
                area=ComplianceArea.CIRCULAR_230,
                status=ComplianceStatus.FAIL,
                title="Frivolous Position",
                description="Return contains position that may be considered frivolous",
                requirement="Must not take frivolous positions on returns",
                remediation="Review and remove any positions without substantial authority",
                penalty_risk="$5,000 frivolous return penalty"
            ))

        # Check preparer PTIN
        if preparer_info and not preparer_info.get("ptin"):
            issues.append(ComplianceIssue(
                area=ComplianceArea.CIRCULAR_230,
                status=ComplianceStatus.FAIL,
                title="Missing PTIN",
                description="Preparer PTIN not provided",
                requirement="All paid preparers must have valid PTIN",
                remediation="Obtain PTIN from IRS before signing returns",
                penalty_risk="$50 penalty per return"
            ))

        return issues

    async def _check_accuracy_penalties(
        self,
        return_data: Dict[str, Any]
    ) -> List[ComplianceIssue]:
        """Check for accuracy penalty exposure."""
        issues = []

        # Substantial understatement check
        tax_liability = return_data.get("total_tax", 0)
        understatement = return_data.get("potential_understatement", 0)

        if tax_liability > 0 and understatement > 0:
            understatement_pct = understatement / tax_liability
            threshold = max(5000, tax_liability * 0.10)

            if understatement > threshold:
                issues.append(ComplianceIssue(
                    area=ComplianceArea.ACCURACY_PENALTIES,
                    status=ComplianceStatus.WARNING,
                    title="Substantial Understatement Risk",
                    description=f"Potential understatement of ${understatement:,.0f} exceeds threshold",
                    requirement="Understatement must be less than greater of $5,000 or 10% of tax",
                    current_state=f"Threshold: ${threshold:,.0f}",
                    remediation="Ensure adequate disclosure of positions (Form 8275)",
                    irc_reference="IRC 6662(d)",
                    penalty_risk="20% accuracy-related penalty"
                ))

        return issues

    async def _ai_compliance_analysis(
        self,
        return_data: Dict[str, Any],
        existing_issues: List[ComplianceIssue]
    ) -> List[ComplianceIssue]:
        """Use Claude for deep compliance analysis."""
        prompt = f"""Analyze this tax return for compliance issues not caught by standard checks.

Tax Return Summary:
{self._format_return_for_ai(return_data)}

Already Identified Issues:
{[i.title for i in existing_issues]}

Check for:
1. Circular 230 violations
2. Missing due diligence documentation
3. Positions that lack substantial authority
4. Potential preparer penalties
5. Client penalty exposure
6. Disclosure requirements not met

Return JSON array of additional compliance issues:
[
    {{
        "area": "circular_230|preparer_dd|eitc_dd|ctc_dd|accuracy|fraud|documentation",
        "status": "pass|warning|fail|needs_review",
        "title": "issue title",
        "description": "detailed description",
        "requirement": "what's required",
        "remediation": "how to fix",
        "irc_reference": "IRC section if applicable",
        "penalty_risk": "potential penalty"
    }}
]

Return empty array [] if no additional issues found."""

        try:
            response = await self.ai_service.reason(
                problem=prompt,
                context="Tax return compliance review"
            )

            import json
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            ai_results = json.loads(content)
            issues = []

            for item in ai_results:
                issues.append(ComplianceIssue(
                    area=ComplianceArea(item.get("area", "documentation")),
                    status=ComplianceStatus(item.get("status", "needs_review")),
                    title=item.get("title", "Compliance Issue"),
                    description=item.get("description", ""),
                    requirement=item.get("requirement", ""),
                    remediation=item.get("remediation"),
                    irc_reference=item.get("irc_reference"),
                    penalty_risk=item.get("penalty_risk")
                ))

            return issues

        except Exception as e:
            logger.error(f"AI compliance analysis failed: {e}")
            return []

    def _evaluate_eitc_question(
        self,
        question_id: str,
        return_data: Dict[str, Any]
    ) -> tuple:
        """Evaluate EITC due diligence question."""
        evaluations = {
            "eitc_1": (
                "Form 8867 completed" if return_data.get("form_8867_complete") else "Not completed",
                return_data.get("form_8867_complete", False)
            ),
            "eitc_2": (
                "Income verified" if return_data.get("earned_income_documented") else "Not verified",
                return_data.get("earned_income_documented", False)
            ),
            "eitc_3": (
                "Children verified" if return_data.get("qualifying_children_verified") else "Not verified",
                return_data.get("qualifying_children_verified", False)
            ),
            "eitc_4": (
                "Residency documented" if return_data.get("residency_documented") else "Not documented",
                return_data.get("residency_documented", False)
            ),
            "eitc_5": (
                "Filing status verified" if return_data.get("filing_status_verified") else "Not verified",
                return_data.get("filing_status_verified", False)
            ),
            "eitc_6": (
                "Records retained" if return_data.get("records_retained") else "Not confirmed",
                return_data.get("records_retained", False)
            ),
        }

        return evaluations.get(question_id, ("Unknown", False))

    def _evaluate_ctc_question(
        self,
        question_id: str,
        return_data: Dict[str, Any]
    ) -> tuple:
        """Evaluate CTC due diligence question."""
        children = return_data.get("children", [])

        if question_id == "ctc_1":
            # Age verification
            all_verified = all(c.get("age_verified") for c in children) if children else False
            return ("Ages verified" if all_verified else "Not all verified", all_verified)

        elif question_id == "ctc_2":
            # Relationship verification
            all_verified = all(c.get("relationship_verified") for c in children) if children else False
            return ("Relationships verified" if all_verified else "Not all verified", all_verified)

        elif question_id == "ctc_3":
            # Citizenship verification
            all_verified = all(c.get("citizenship_verified") for c in children) if children else False
            return ("Citizenship verified" if all_verified else "Not all verified", all_verified)

        elif question_id == "ctc_4":
            # SSN verification
            all_have_ssn = all(c.get("has_valid_ssn") for c in children) if children else False
            return ("All SSNs obtained" if all_have_ssn else "Missing SSNs", all_have_ssn)

        return ("Unknown", False)

    def _checklist_to_issues(
        self,
        checklist: DueDiligenceChecklist,
        area: ComplianceArea
    ) -> List[ComplianceIssue]:
        """Convert checklist failures to issues."""
        issues = []

        for item in checklist.missing_items:
            issues.append(ComplianceIssue(
                area=area,
                status=ComplianceStatus.WARNING,
                title=f"{checklist.credit_type} Due Diligence - Incomplete",
                description=item,
                requirement=f"Form {checklist.form_number} requirement",
                remediation="Complete due diligence inquiry and documentation",
                form_reference=f"Form {checklist.form_number}"
            ))

        return issues

    def _assess_penalty_risk(
        self,
        issues: List[ComplianceIssue],
        return_data: Dict[str, Any]
    ) -> tuple:
        """Assess penalty risk level and exposure."""
        total_exposure = 0

        for issue in issues:
            if issue.penalty_risk:
                # Parse penalty amounts from descriptions
                if "$5,000" in issue.penalty_risk:
                    total_exposure += 5000
                elif "20%" in issue.penalty_risk:
                    understatement = return_data.get("potential_understatement", 0)
                    total_exposure += understatement * 0.20
                elif "$50" in issue.penalty_risk:
                    total_exposure += 50

        fail_count = sum(1 for i in issues if i.status == ComplianceStatus.FAIL)
        warning_count = sum(1 for i in issues if i.status == ComplianceStatus.WARNING)

        if fail_count > 0 or total_exposure > 5000:
            risk_level = "high"
        elif warning_count > 2 or total_exposure > 1000:
            risk_level = "medium"
        else:
            risk_level = "low"

        return risk_level, total_exposure

    def _determine_overall_status(
        self,
        issues: List[ComplianceIssue]
    ) -> ComplianceStatus:
        """Determine overall compliance status."""
        if any(i.status == ComplianceStatus.FAIL for i in issues):
            return ComplianceStatus.FAIL
        elif any(i.status == ComplianceStatus.NEEDS_REVIEW for i in issues):
            return ComplianceStatus.NEEDS_REVIEW
        elif any(i.status == ComplianceStatus.WARNING for i in issues):
            return ComplianceStatus.WARNING
        return ComplianceStatus.PASS

    def _generate_recommendations(
        self,
        issues: List[ComplianceIssue]
    ) -> List[str]:
        """Generate prioritized recommendations."""
        recommendations = []

        # Add unique remediation steps
        for issue in sorted(issues, key=lambda i: i.status.value):
            if issue.remediation and issue.remediation not in recommendations:
                recommendations.append(issue.remediation)

        # Add general recommendations
        fail_count = sum(1 for i in issues if i.status == ComplianceStatus.FAIL)
        if fail_count > 0:
            recommendations.insert(0, "CRITICAL: Resolve all FAIL issues before filing")

        return recommendations[:10]

    def _format_return_for_ai(self, return_data: Dict[str, Any]) -> str:
        """Format return data for AI analysis."""
        safe_data = dict(return_data)
        if "ssn" in safe_data:
            ssn = str(safe_data["ssn"])
            safe_data["ssn"] = f"XXX-XX-{ssn[-4:]}" if len(ssn) >= 4 else "XXX-XX-XXXX"

        import json
        return json.dumps(safe_data, indent=2, default=str)


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_compliance_reviewer: Optional[ComplianceReviewer] = None


def get_compliance_reviewer() -> ComplianceReviewer:
    """Get the singleton compliance reviewer instance."""
    global _compliance_reviewer
    if _compliance_reviewer is None:
        _compliance_reviewer = ComplianceReviewer()
    return _compliance_reviewer


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "ComplianceReviewer",
    "ComplianceArea",
    "ComplianceStatus",
    "ComplianceIssue",
    "ComplianceReport",
    "DueDiligenceChecklist",
    "get_compliance_reviewer",
]
