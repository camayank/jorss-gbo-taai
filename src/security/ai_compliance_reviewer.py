"""
AI-Powered Compliance Reviewer for Tax Platform Security.

Uses Claude (Anthropic) for intelligent compliance review including:
- Circular 230 compliance verification
- EITC/CTC due diligence requirements
- Preparer penalty risk assessment
- Fraud indicator detection
- Compliance documentation generation
"""

import os
import json
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class ComplianceRiskLevel(Enum):
    """Risk levels for compliance issues."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ComplianceCategory(Enum):
    """Categories of compliance requirements."""
    CIRCULAR_230 = "circular_230"
    EITC_DUE_DILIGENCE = "eitc_due_diligence"
    CTC_DUE_DILIGENCE = "ctc_due_diligence"
    AOTC_DUE_DILIGENCE = "aotc_due_diligence"
    PREPARER_REQUIREMENTS = "preparer_requirements"
    RECORD_KEEPING = "record_keeping"
    DISCLOSURE = "disclosure"
    FRAUD_INDICATORS = "fraud_indicators"


@dataclass
class ComplianceIssue:
    """Represents a single compliance issue found."""
    category: ComplianceCategory
    risk_level: ComplianceRiskLevel
    title: str
    description: str
    regulation_reference: str
    recommended_action: str
    penalty_risk: Optional[str] = None
    documentation_required: Optional[List[str]] = None


@dataclass
class DueDiligenceRequirement:
    """Represents a due diligence requirement."""
    form_number: str  # e.g., "Form 8867"
    credit_type: str
    requirement: str
    is_satisfied: bool
    evidence: Optional[str] = None
    missing_documentation: Optional[List[str]] = None


@dataclass
class ComplianceReviewResult:
    """Complete compliance review result."""
    return_id: str
    review_timestamp: datetime
    overall_risk_level: ComplianceRiskLevel
    issues: List[ComplianceIssue] = field(default_factory=list)
    due_diligence_requirements: List[DueDiligenceRequirement] = field(default_factory=list)
    circular_230_compliant: bool = True
    preparer_penalty_risk: Optional[str] = None
    recommended_actions: List[str] = field(default_factory=list)
    documentation_checklist: List[Dict[str, Any]] = field(default_factory=list)
    ai_confidence: float = 0.0
    raw_analysis: Optional[str] = None


class ClaudeComplianceReviewer:
    """
    AI-powered compliance reviewer using Claude for intelligent analysis.

    Provides comprehensive compliance checking for tax returns including:
    - Circular 230 requirements for tax practitioners
    - EITC/CTC/AOTC due diligence requirements
    - Fraud indicator detection
    - Preparer penalty risk assessment
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the compliance reviewer.

        Args:
            api_key: Anthropic API key. If not provided, uses ANTHROPIC_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._client: Optional[Any] = None

    @property
    def client(self):
        """Lazy-load the Anthropic client."""
        if self._client is None:
            if not ANTHROPIC_AVAILABLE:
                raise ImportError("anthropic package not installed. Run: pip install anthropic")
            if not self.api_key:
                raise ValueError("ANTHROPIC_API_KEY not configured")
            self._client = Anthropic(api_key=self.api_key)
        return self._client

    def review_compliance(
        self,
        tax_return: Dict[str, Any],
        preparer_info: Optional[Dict[str, Any]] = None,
        prior_year_data: Optional[Dict[str, Any]] = None
    ) -> ComplianceReviewResult:
        """
        Perform comprehensive compliance review of a tax return.

        Args:
            tax_return: The tax return data to review.
            preparer_info: Information about the tax preparer.
            prior_year_data: Prior year return for comparison.

        Returns:
            ComplianceReviewResult with findings and recommendations.
        """
        return_id = tax_return.get("return_id", "unknown")

        # Build the compliance review prompt
        prompt = self._build_compliance_prompt(tax_return, preparer_info, prior_year_data)

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                system="""You are an expert tax compliance reviewer specializing in IRS regulations,
Circular 230 requirements, and preparer due diligence obligations.

Analyze tax returns for compliance issues and provide detailed, actionable findings.
Always respond with valid JSON matching the requested structure."""
            )

            # Parse the response
            content = response.content[0].text
            return self._parse_compliance_response(return_id, content)

        except Exception as e:
            # Return result with error indication
            return ComplianceReviewResult(
                return_id=return_id,
                review_timestamp=datetime.now(),
                overall_risk_level=ComplianceRiskLevel.HIGH,
                issues=[ComplianceIssue(
                    category=ComplianceCategory.PREPARER_REQUIREMENTS,
                    risk_level=ComplianceRiskLevel.HIGH,
                    title="Compliance Review Error",
                    description=f"Unable to complete AI compliance review: {str(e)}",
                    regulation_reference="N/A",
                    recommended_action="Perform manual compliance review"
                )],
                ai_confidence=0.0,
                raw_analysis=str(e)
            )

    def check_eitc_due_diligence(self, tax_return: Dict[str, Any]) -> List[DueDiligenceRequirement]:
        """
        Check EITC due diligence requirements (Form 8867).

        The IRS requires paid preparers to complete due diligence for:
        - Earned Income Credit (EIC)
        - Child Tax Credit (CTC)/Additional Child Tax Credit (ACTC)
        - American Opportunity Tax Credit (AOTC)
        - Head of Household filing status

        Args:
            tax_return: The tax return data.

        Returns:
            List of due diligence requirements and their status.
        """
        prompt = f"""Analyze this tax return for EITC due diligence requirements under Form 8867.

Tax Return Data:
{json.dumps(tax_return, indent=2, default=str)}

Check each of the four knowledge requirements:
1. Did the preparer complete the eligibility checklist?
2. Did the preparer document the taxpayer interview?
3. Did the preparer verify supporting documentation?
4. Were there any inconsistencies that required additional inquiry?

Also check for:
- Form 8867 completion requirements
- Record retention requirements (3 years)
- Knowledge requirement violations

Respond with JSON array of due diligence requirements:
[
  {{
    "form_number": "Form 8867",
    "credit_type": "EITC",
    "requirement": "description",
    "is_satisfied": true/false,
    "evidence": "evidence found or null",
    "missing_documentation": ["list of missing docs"] or null
  }}
]"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text
            # Extract JSON from response
            json_start = content.find('[')
            json_end = content.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                requirements_data = json.loads(content[json_start:json_end])
                return [
                    DueDiligenceRequirement(
                        form_number=req.get("form_number", "Form 8867"),
                        credit_type=req.get("credit_type", "Unknown"),
                        requirement=req.get("requirement", ""),
                        is_satisfied=req.get("is_satisfied", False),
                        evidence=req.get("evidence"),
                        missing_documentation=req.get("missing_documentation")
                    )
                    for req in requirements_data
                ]
            return []

        except Exception:
            return []

    def assess_preparer_penalty_risk(
        self,
        tax_return: Dict[str, Any],
        preparer_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Assess preparer penalty risk under IRC sections 6694, 6695, and 6701.

        Args:
            tax_return: The tax return data.
            preparer_info: Information about the preparer.

        Returns:
            Penalty risk assessment with specific risks identified.
        """
        prompt = f"""Assess preparer penalty risk for this tax return under IRS penalty provisions.

Tax Return:
{json.dumps(tax_return, indent=2, default=str)}

Preparer Information:
{json.dumps(preparer_info, indent=2, default=str)}

Analyze for penalties under:
1. IRC 6694(a) - Unreasonable positions ($1,000 or 50% of income)
2. IRC 6694(b) - Willful or reckless conduct ($5,000 or 75% of income)
3. IRC 6695 - Various preparer penalties (PTIN, signing, copies, etc.)
4. IRC 6701 - Aiding and abetting understatement

Respond with JSON:
{{
  "overall_penalty_risk": "low/medium/high/critical",
  "estimated_penalty_exposure": "dollar amount or range",
  "specific_risks": [
    {{
      "irc_section": "section number",
      "violation_type": "description",
      "risk_level": "low/medium/high",
      "potential_penalty": "amount",
      "mitigating_factors": ["list"],
      "recommended_action": "action"
    }}
  ],
  "safe_harbor_analysis": "analysis of reasonable cause/good faith defenses",
  "recommendations": ["list of recommendations"]
}}"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(content[json_start:json_end])
            return {"overall_penalty_risk": "unknown", "error": "Could not parse response"}

        except Exception as e:
            return {"overall_penalty_risk": "unknown", "error": str(e)}

    def generate_compliance_documentation(
        self,
        tax_return: Dict[str, Any],
        review_result: ComplianceReviewResult
    ) -> Dict[str, str]:
        """
        Generate compliance documentation for record-keeping.

        Args:
            tax_return: The tax return data.
            review_result: The compliance review result.

        Returns:
            Dictionary of document types to content.
        """
        prompt = f"""Generate compliance documentation for this tax return review.

Tax Return Summary:
- Return ID: {tax_return.get('return_id', 'N/A')}
- Tax Year: {tax_return.get('tax_year', 'N/A')}
- Filing Status: {tax_return.get('filing_status', 'N/A')}

Review Findings:
- Overall Risk: {review_result.overall_risk_level.value}
- Issues Found: {len(review_result.issues)}
- Due Diligence Items: {len(review_result.due_diligence_requirements)}

Generate the following documents:
1. Due Diligence Certification memo
2. Compliance Review Summary
3. Risk Assessment Documentation
4. Preparer Notes for File

Respond with JSON:
{{
  "due_diligence_certification": "full text of certification memo",
  "compliance_summary": "summary document text",
  "risk_assessment": "risk documentation text",
  "preparer_notes": "notes for the file"
}}"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(content[json_start:json_end])
            return {"error": "Could not generate documentation"}

        except Exception as e:
            return {"error": str(e)}

    def check_circular_230_compliance(
        self,
        preparer_info: Dict[str, Any],
        client_communications: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Check Circular 230 compliance for the tax practitioner.

        Covers key provisions:
        - Section 10.22: Diligence as to accuracy
        - Section 10.33: Best practices
        - Section 10.34: Standards for advising positions
        - Section 10.37: Requirements for written advice

        Args:
            preparer_info: Information about the preparer.
            client_communications: Any written advice or communications.

        Returns:
            Circular 230 compliance assessment.
        """
        prompt = f"""Analyze Circular 230 compliance for this tax practitioner.

Preparer Information:
{json.dumps(preparer_info, indent=2, default=str)}

Client Communications:
{json.dumps(client_communications or [], indent=2, default=str)}

Check compliance with key Circular 230 provisions:
1. Section 10.22 - Diligence as to accuracy
2. Section 10.33 - Best practices for tax advisors
3. Section 10.34 - Standards with respect to tax returns
4. Section 10.35 - Competence
5. Section 10.37 - Requirements for written advice

Respond with JSON:
{{
  "is_compliant": true/false,
  "compliance_score": 0-100,
  "section_analysis": [
    {{
      "section": "10.XX",
      "title": "section title",
      "compliant": true/false,
      "findings": "detailed findings",
      "recommendations": ["list"]
    }}
  ],
  "overall_assessment": "summary assessment",
  "corrective_actions": ["required actions if any"]
}}"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(content[json_start:json_end])
            return {"is_compliant": False, "error": "Could not parse response"}

        except Exception as e:
            return {"is_compliant": False, "error": str(e)}

    def _build_compliance_prompt(
        self,
        tax_return: Dict[str, Any],
        preparer_info: Optional[Dict[str, Any]],
        prior_year_data: Optional[Dict[str, Any]]
    ) -> str:
        """Build the comprehensive compliance review prompt."""
        return f"""Perform a comprehensive compliance review of this tax return.

TAX RETURN DATA:
{json.dumps(tax_return, indent=2, default=str)}

PREPARER INFORMATION:
{json.dumps(preparer_info or {}, indent=2, default=str)}

PRIOR YEAR DATA (for comparison):
{json.dumps(prior_year_data or {}, indent=2, default=str)}

REVIEW REQUIREMENTS:
1. Check Circular 230 compliance requirements
2. Verify EITC/CTC/AOTC due diligence if applicable
3. Identify fraud indicators or red flags
4. Assess preparer penalty risk
5. Generate documentation checklist

Respond with JSON:
{{
  "overall_risk_level": "low/medium/high/critical",
  "circular_230_compliant": true/false,
  "issues": [
    {{
      "category": "circular_230/eitc_due_diligence/ctc_due_diligence/aotc_due_diligence/preparer_requirements/record_keeping/disclosure/fraud_indicators",
      "risk_level": "low/medium/high/critical",
      "title": "issue title",
      "description": "detailed description",
      "regulation_reference": "IRC section or Circular 230 reference",
      "recommended_action": "what to do",
      "penalty_risk": "potential penalty if any",
      "documentation_required": ["list of docs needed"]
    }}
  ],
  "due_diligence_requirements": [
    {{
      "form_number": "form number",
      "credit_type": "credit type",
      "requirement": "requirement description",
      "is_satisfied": true/false,
      "evidence": "evidence found",
      "missing_documentation": ["missing docs"]
    }}
  ],
  "preparer_penalty_risk": "assessment summary",
  "recommended_actions": ["list of recommended actions"],
  "documentation_checklist": [
    {{
      "document": "document name",
      "required": true/false,
      "present": true/false,
      "notes": "any notes"
    }}
  ],
  "ai_confidence": 0.0-1.0
}}"""

    def _parse_compliance_response(
        self,
        return_id: str,
        content: str
    ) -> ComplianceReviewResult:
        """Parse Claude's compliance review response."""
        try:
            # Extract JSON from response
            json_start = content.find('{')
            json_end = content.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                data = json.loads(content[json_start:json_end])

                # Parse issues
                issues = []
                for issue_data in data.get("issues", []):
                    try:
                        issues.append(ComplianceIssue(
                            category=ComplianceCategory(issue_data.get("category", "preparer_requirements")),
                            risk_level=ComplianceRiskLevel(issue_data.get("risk_level", "medium")),
                            title=issue_data.get("title", "Unknown Issue"),
                            description=issue_data.get("description", ""),
                            regulation_reference=issue_data.get("regulation_reference", ""),
                            recommended_action=issue_data.get("recommended_action", ""),
                            penalty_risk=issue_data.get("penalty_risk"),
                            documentation_required=issue_data.get("documentation_required")
                        ))
                    except (ValueError, KeyError):
                        continue

                # Parse due diligence requirements
                dd_requirements = []
                for dd_data in data.get("due_diligence_requirements", []):
                    dd_requirements.append(DueDiligenceRequirement(
                        form_number=dd_data.get("form_number", ""),
                        credit_type=dd_data.get("credit_type", ""),
                        requirement=dd_data.get("requirement", ""),
                        is_satisfied=dd_data.get("is_satisfied", False),
                        evidence=dd_data.get("evidence"),
                        missing_documentation=dd_data.get("missing_documentation")
                    ))

                return ComplianceReviewResult(
                    return_id=return_id,
                    review_timestamp=datetime.now(),
                    overall_risk_level=ComplianceRiskLevel(data.get("overall_risk_level", "medium")),
                    issues=issues,
                    due_diligence_requirements=dd_requirements,
                    circular_230_compliant=data.get("circular_230_compliant", True),
                    preparer_penalty_risk=data.get("preparer_penalty_risk"),
                    recommended_actions=data.get("recommended_actions", []),
                    documentation_checklist=data.get("documentation_checklist", []),
                    ai_confidence=data.get("ai_confidence", 0.8),
                    raw_analysis=content
                )

        except (json.JSONDecodeError, KeyError, ValueError):
            pass

        # Return default result on parse failure
        return ComplianceReviewResult(
            return_id=return_id,
            review_timestamp=datetime.now(),
            overall_risk_level=ComplianceRiskLevel.MEDIUM,
            ai_confidence=0.0,
            raw_analysis=content
        )


# Singleton instance
_compliance_reviewer: Optional[ClaudeComplianceReviewer] = None


def get_compliance_reviewer() -> ClaudeComplianceReviewer:
    """Get the singleton ClaudeComplianceReviewer instance."""
    global _compliance_reviewer
    if _compliance_reviewer is None:
        _compliance_reviewer = ClaudeComplianceReviewer()
    return _compliance_reviewer


__all__ = [
    "ClaudeComplianceReviewer",
    "get_compliance_reviewer",
    "ComplianceReviewResult",
    "ComplianceIssue",
    "DueDiligenceRequirement",
    "ComplianceRiskLevel",
    "ComplianceCategory",
]
