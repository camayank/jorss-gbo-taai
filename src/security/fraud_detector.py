"""
AI-Powered Fraud Detection for Tax Platform Security.

Uses OpenAI for intelligent fraud detection including:
- Unusual pattern detection
- Identity theft indicators
- Suspicious refund claims
- Known fraud pattern matching
- Anomaly scoring and risk assessment
"""

import os
import json
import hashlib
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class FraudRiskLevel(Enum):
    """Risk levels for fraud detection."""
    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class FraudIndicatorType(Enum):
    """Types of fraud indicators."""
    IDENTITY_THEFT = "identity_theft"
    INCOME_FABRICATION = "income_fabrication"
    DEDUCTION_INFLATION = "deduction_inflation"
    CREDIT_FRAUD = "credit_fraud"
    REFUND_FRAUD = "refund_fraud"
    DOCUMENT_FORGERY = "document_forgery"
    PREPARER_FRAUD = "preparer_fraud"
    GHOST_EMPLOYEE = "ghost_employee"
    SUSPICIOUS_PATTERN = "suspicious_pattern"
    KNOWN_SCHEME = "known_scheme"


@dataclass
class FraudIndicator:
    """Represents a single fraud indicator found."""
    indicator_type: FraudIndicatorType
    risk_level: FraudRiskLevel
    title: str
    description: str
    evidence: List[str]
    confidence_score: float
    recommended_action: str
    irs_referral_recommended: bool = False
    supporting_data: Optional[Dict[str, Any]] = None


@dataclass
class PatternMatch:
    """Represents a match to a known fraud pattern."""
    pattern_name: str
    pattern_id: str
    match_confidence: float
    description: str
    historical_frequency: Optional[str] = None
    typical_loss_amount: Optional[str] = None


@dataclass
class FraudDetectionResult:
    """Complete fraud detection result."""
    return_id: str
    scan_timestamp: datetime
    overall_risk_level: FraudRiskLevel
    risk_score: float  # 0-100
    indicators: List[FraudIndicator] = field(default_factory=list)
    pattern_matches: List[PatternMatch] = field(default_factory=list)
    identity_verification_flags: List[str] = field(default_factory=list)
    refund_risk_assessment: Optional[Dict[str, Any]] = None
    recommended_actions: List[str] = field(default_factory=list)
    irs_referral_recommended: bool = False
    ai_confidence: float = 0.0
    raw_analysis: Optional[str] = None


class OpenAIFraudDetector:
    """
    AI-powered fraud detector using OpenAI for intelligent analysis.

    Provides comprehensive fraud detection for tax returns including:
    - Identity theft detection
    - Income and deduction anomalies
    - Refund fraud indicators
    - Known scheme pattern matching
    - Behavioral analysis
    """

    # Known fraud patterns for pattern matching
    KNOWN_FRAUD_PATTERNS = [
        {
            "id": "PATTERN_001",
            "name": "Ghost W-2 Scheme",
            "description": "Fabricated W-2 forms from non-existent employers",
            "indicators": ["employer_not_found", "round_numbers", "no_state_filing"]
        },
        {
            "id": "PATTERN_002",
            "name": "EITC Maximization Fraud",
            "description": "Income adjusted to maximize EITC benefits",
            "indicators": ["income_near_eitc_cliff", "multiple_dependents", "no_w2_match"]
        },
        {
            "id": "PATTERN_003",
            "name": "Identity Theft Refund Fraud",
            "description": "Filing with stolen SSN to claim refund",
            "indicators": ["ssn_mismatch", "address_change", "direct_deposit_new"]
        },
        {
            "id": "PATTERN_004",
            "name": "Inflated Withholding Scheme",
            "description": "Falsified withholding amounts on W-2",
            "indicators": ["withholding_ratio_abnormal", "no_employer_match"]
        },
        {
            "id": "PATTERN_005",
            "name": "Fictitious Schedule C",
            "description": "Fake self-employment income/losses",
            "indicators": ["no_1099", "round_expenses", "high_loss_pattern"]
        },
        {
            "id": "PATTERN_006",
            "name": "Dependent Fraud",
            "description": "Claiming ineligible dependents",
            "indicators": ["dependent_ssn_used_elsewhere", "age_inconsistency"]
        },
    ]

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the fraud detector.

        Args:
            api_key: OpenAI API key. If not provided, uses OPENAI_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._client: Optional[Any] = None

    @property
    def client(self):
        """Lazy-load the OpenAI client."""
        if self._client is None:
            if not OPENAI_AVAILABLE:
                raise ImportError("openai package not installed. Run: pip install openai")
            if not self.api_key:
                raise ValueError("OPENAI_API_KEY not configured")
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def detect_fraud(
        self,
        tax_return: Dict[str, Any],
        historical_data: Optional[List[Dict[str, Any]]] = None,
        third_party_data: Optional[Dict[str, Any]] = None
    ) -> FraudDetectionResult:
        """
        Perform comprehensive fraud detection on a tax return.

        Args:
            tax_return: The tax return data to analyze.
            historical_data: Previous returns for pattern analysis.
            third_party_data: W-2, 1099, etc. for verification.

        Returns:
            FraudDetectionResult with findings and risk assessment.
        """
        return_id = tax_return.get("return_id", "unknown")

        # Build the fraud detection prompt
        prompt = self._build_fraud_detection_prompt(
            tax_return, historical_data, third_party_data
        )

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert tax fraud detection analyst specializing in
identifying fraudulent tax returns, identity theft, and tax evasion schemes.

Analyze tax returns for fraud indicators using IRS guidelines and known fraud patterns.
Be thorough but avoid false positives. Provide confidence scores for all findings.
Always respond with valid JSON matching the requested structure."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Low temperature for consistent analysis
                max_tokens=4096
            )

            content = response.choices[0].message.content
            return self._parse_fraud_response(return_id, content)

        except Exception as e:
            return FraudDetectionResult(
                return_id=return_id,
                scan_timestamp=datetime.now(),
                overall_risk_level=FraudRiskLevel.MODERATE,
                risk_score=50.0,
                indicators=[FraudIndicator(
                    indicator_type=FraudIndicatorType.SUSPICIOUS_PATTERN,
                    risk_level=FraudRiskLevel.MODERATE,
                    title="Fraud Detection Error",
                    description=f"Unable to complete AI fraud analysis: {str(e)}",
                    evidence=[],
                    confidence_score=0.0,
                    recommended_action="Perform manual fraud review"
                )],
                ai_confidence=0.0,
                raw_analysis=str(e)
            )

    def check_identity_theft_indicators(
        self,
        tax_return: Dict[str, Any],
        prior_filings: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Check for identity theft indicators.

        Args:
            tax_return: Current tax return.
            prior_filings: Historical filing data.

        Returns:
            Identity theft risk assessment.
        """
        prompt = f"""Analyze this tax return for identity theft indicators.

Current Tax Return:
{json.dumps(tax_return, indent=2, default=str)}

Prior Filing History:
{json.dumps(prior_filings or [], indent=2, default=str)}

Check for these identity theft indicators:
1. SSN used on multiple returns
2. Significant changes from prior year (address, bank, employer)
3. Filing pattern anomalies (early/late, different software)
4. Dependent SSN issues
5. W-2/1099 employer verification failures
6. Name/SSN mismatches

Respond with JSON:
{{
  "identity_theft_risk": "minimal/low/moderate/high/critical",
  "risk_score": 0-100,
  "indicators_found": [
    {{
      "indicator": "indicator name",
      "severity": "low/medium/high",
      "description": "detailed description",
      "evidence": ["supporting evidence"],
      "confidence": 0.0-1.0
    }}
  ],
  "verification_recommended": ["list of verifications needed"],
  "immediate_actions": ["urgent actions if any"],
  "explanation": "overall assessment"
}}"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2048
            )

            content = response.choices[0].message.content
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(content[json_start:json_end])
            return {"identity_theft_risk": "unknown", "error": "Could not parse response"}

        except Exception as e:
            return {"identity_theft_risk": "unknown", "error": str(e)}

    def analyze_refund_risk(self, tax_return: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze refund fraud risk.

        Checks for suspicious refund claims including:
        - Unusually large refunds
        - Direct deposit to new accounts
        - Split refunds to multiple accounts
        - Refund timing anomalies

        Args:
            tax_return: The tax return data.

        Returns:
            Refund risk assessment.
        """
        prompt = f"""Analyze this tax return for refund fraud risk.

Tax Return:
{json.dumps(tax_return, indent=2, default=str)}

Check for refund fraud indicators:
1. Refund size relative to income
2. Unusual withholding amounts
3. Refundable credit claims (EITC, CTC, AOTC)
4. Direct deposit to potentially fraudulent accounts
5. Split refund patterns
6. Timing of filing (early filing with large refund)

Respond with JSON:
{{
  "refund_risk_level": "minimal/low/moderate/high/critical",
  "risk_score": 0-100,
  "refund_amount": "amount",
  "refund_to_income_ratio": "ratio",
  "risk_factors": [
    {{
      "factor": "factor name",
      "severity": "low/medium/high",
      "description": "description",
      "contribution_to_risk": "percentage"
    }}
  ],
  "hold_recommendation": true/false,
  "verification_required": ["list of verifications"],
  "explanation": "overall assessment"
}}"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2048
            )

            content = response.choices[0].message.content
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(content[json_start:json_end])
            return {"refund_risk_level": "unknown", "error": "Could not parse response"}

        except Exception as e:
            return {"refund_risk_level": "unknown", "error": str(e)}

    def match_known_patterns(
        self,
        tax_return: Dict[str, Any]
    ) -> List[PatternMatch]:
        """
        Match tax return against known fraud patterns.

        Args:
            tax_return: The tax return data.

        Returns:
            List of matched fraud patterns.
        """
        patterns_json = json.dumps(self.KNOWN_FRAUD_PATTERNS, indent=2)

        prompt = f"""Compare this tax return against known fraud patterns.

Tax Return:
{json.dumps(tax_return, indent=2, default=str)}

Known Fraud Patterns:
{patterns_json}

For each pattern, determine if there's a match and provide confidence score.
Consider partial matches and variations of the patterns.

Respond with JSON array:
[
  {{
    "pattern_id": "PATTERN_XXX",
    "pattern_name": "pattern name",
    "match_confidence": 0.0-1.0,
    "matched_indicators": ["which indicators matched"],
    "description": "how this return matches the pattern",
    "historical_frequency": "how common this pattern is",
    "typical_loss_amount": "typical fraud amount"
  }}
]

Only include patterns with match_confidence > 0.3"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2048
            )

            content = response.choices[0].message.content
            json_start = content.find('[')
            json_end = content.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                matches_data = json.loads(content[json_start:json_end])
                return [
                    PatternMatch(
                        pattern_name=m.get("pattern_name", "Unknown"),
                        pattern_id=m.get("pattern_id", ""),
                        match_confidence=m.get("match_confidence", 0.0),
                        description=m.get("description", ""),
                        historical_frequency=m.get("historical_frequency"),
                        typical_loss_amount=m.get("typical_loss_amount")
                    )
                    for m in matches_data
                    if m.get("match_confidence", 0) > 0.3
                ]
            return []

        except Exception:
            return []

    def detect_anomalies(
        self,
        tax_return: Dict[str, Any],
        population_statistics: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Detect statistical anomalies in the tax return.

        Args:
            tax_return: The tax return data.
            population_statistics: Statistical norms for comparison.

        Returns:
            Anomaly detection results.
        """
        prompt = f"""Perform statistical anomaly detection on this tax return.

Tax Return:
{json.dumps(tax_return, indent=2, default=str)}

Population Statistics (if available):
{json.dumps(population_statistics or {}, indent=2, default=str)}

Analyze for anomalies in:
1. Income levels relative to occupation/industry
2. Deduction ratios (charitable, business, medical)
3. Credit claims relative to income
4. Expense patterns
5. Withholding ratios
6. Dependent-related deductions

Respond with JSON:
{{
  "anomaly_score": 0-100,
  "anomalies_detected": [
    {{
      "field": "field name",
      "reported_value": "value",
      "expected_range": "min-max",
      "deviation": "how far from normal",
      "z_score": "statistical z-score if calculable",
      "severity": "low/medium/high",
      "explanation": "why this is anomalous"
    }}
  ],
  "statistical_summary": {{
    "fields_analyzed": "count",
    "anomalies_found": "count",
    "highest_deviation_field": "field name"
  }},
  "overall_assessment": "explanation"
}}"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2048
            )

            content = response.choices[0].message.content
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(content[json_start:json_end])
            return {"anomaly_score": 0, "error": "Could not parse response"}

        except Exception as e:
            return {"anomaly_score": 0, "error": str(e)}

    def generate_fraud_report(
        self,
        detection_result: FraudDetectionResult
    ) -> Dict[str, str]:
        """
        Generate a formal fraud detection report.

        Args:
            detection_result: The fraud detection result.

        Returns:
            Formatted fraud report sections.
        """
        indicators_summary = "\n".join([
            f"- {i.title}: {i.description} (Confidence: {i.confidence_score:.0%})"
            for i in detection_result.indicators
        ])

        prompt = f"""Generate a formal fraud detection report.

Detection Results:
- Return ID: {detection_result.return_id}
- Scan Time: {detection_result.scan_timestamp}
- Risk Level: {detection_result.overall_risk_level.value}
- Risk Score: {detection_result.risk_score}/100
- IRS Referral Recommended: {detection_result.irs_referral_recommended}

Indicators Found:
{indicators_summary}

Pattern Matches: {len(detection_result.pattern_matches)}

Generate a professional fraud report with these sections:
1. Executive Summary
2. Risk Assessment
3. Detailed Findings
4. Evidence Summary
5. Recommendations
6. Appendix (for IRS referral if applicable)

Respond with JSON:
{{
  "executive_summary": "summary text",
  "risk_assessment": "assessment text",
  "detailed_findings": "findings text",
  "evidence_summary": "evidence text",
  "recommendations": "recommendations text",
  "irs_referral_appendix": "appendix text if referral recommended, otherwise null"
}}"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=4096
            )

            content = response.choices[0].message.content
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(content[json_start:json_end])
            return {"error": "Could not generate report"}

        except Exception as e:
            return {"error": str(e)}

    def _build_fraud_detection_prompt(
        self,
        tax_return: Dict[str, Any],
        historical_data: Optional[List[Dict[str, Any]]],
        third_party_data: Optional[Dict[str, Any]]
    ) -> str:
        """Build the comprehensive fraud detection prompt."""
        return f"""Perform comprehensive fraud detection analysis on this tax return.

TAX RETURN DATA:
{json.dumps(tax_return, indent=2, default=str)}

HISTORICAL FILING DATA:
{json.dumps(historical_data or [], indent=2, default=str)}

THIRD-PARTY VERIFICATION DATA (W-2, 1099, etc.):
{json.dumps(third_party_data or {}, indent=2, default=str)}

FRAUD DETECTION REQUIREMENTS:
1. Check for identity theft indicators
2. Verify income against third-party data
3. Analyze deduction patterns for inflation
4. Check refundable credit claims
5. Identify known fraud scheme patterns
6. Calculate statistical anomaly scores
7. Assess overall fraud risk

Respond with JSON:
{{
  "overall_risk_level": "minimal/low/moderate/high/critical",
  "risk_score": 0-100,
  "indicators": [
    {{
      "indicator_type": "identity_theft/income_fabrication/deduction_inflation/credit_fraud/refund_fraud/document_forgery/preparer_fraud/ghost_employee/suspicious_pattern/known_scheme",
      "risk_level": "minimal/low/moderate/high/critical",
      "title": "indicator title",
      "description": "detailed description",
      "evidence": ["list of evidence"],
      "confidence_score": 0.0-1.0,
      "recommended_action": "what to do",
      "irs_referral_recommended": true/false,
      "supporting_data": {{}}
    }}
  ],
  "pattern_matches": [
    {{
      "pattern_name": "name",
      "pattern_id": "id",
      "match_confidence": 0.0-1.0,
      "description": "description"
    }}
  ],
  "identity_verification_flags": ["list of flags"],
  "refund_risk_assessment": {{
    "risk_level": "level",
    "hold_recommended": true/false,
    "reasons": ["list"]
  }},
  "recommended_actions": ["list of actions"],
  "irs_referral_recommended": true/false,
  "ai_confidence": 0.0-1.0
}}"""

    def _parse_fraud_response(
        self,
        return_id: str,
        content: str
    ) -> FraudDetectionResult:
        """Parse OpenAI's fraud detection response."""
        try:
            json_start = content.find('{')
            json_end = content.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                data = json.loads(content[json_start:json_end])

                # Parse indicators
                indicators = []
                for ind_data in data.get("indicators", []):
                    try:
                        indicators.append(FraudIndicator(
                            indicator_type=FraudIndicatorType(
                                ind_data.get("indicator_type", "suspicious_pattern")
                            ),
                            risk_level=FraudRiskLevel(
                                ind_data.get("risk_level", "moderate")
                            ),
                            title=ind_data.get("title", "Unknown Indicator"),
                            description=ind_data.get("description", ""),
                            evidence=ind_data.get("evidence", []),
                            confidence_score=ind_data.get("confidence_score", 0.5),
                            recommended_action=ind_data.get("recommended_action", ""),
                            irs_referral_recommended=ind_data.get(
                                "irs_referral_recommended", False
                            ),
                            supporting_data=ind_data.get("supporting_data")
                        ))
                    except (ValueError, KeyError):
                        continue

                # Parse pattern matches
                pattern_matches = []
                for pm_data in data.get("pattern_matches", []):
                    pattern_matches.append(PatternMatch(
                        pattern_name=pm_data.get("pattern_name", "Unknown"),
                        pattern_id=pm_data.get("pattern_id", ""),
                        match_confidence=pm_data.get("match_confidence", 0.0),
                        description=pm_data.get("description", "")
                    ))

                return FraudDetectionResult(
                    return_id=return_id,
                    scan_timestamp=datetime.now(),
                    overall_risk_level=FraudRiskLevel(
                        data.get("overall_risk_level", "moderate")
                    ),
                    risk_score=data.get("risk_score", 50.0),
                    indicators=indicators,
                    pattern_matches=pattern_matches,
                    identity_verification_flags=data.get(
                        "identity_verification_flags", []
                    ),
                    refund_risk_assessment=data.get("refund_risk_assessment"),
                    recommended_actions=data.get("recommended_actions", []),
                    irs_referral_recommended=data.get("irs_referral_recommended", False),
                    ai_confidence=data.get("ai_confidence", 0.8),
                    raw_analysis=content
                )

        except (json.JSONDecodeError, KeyError, ValueError):
            pass

        return FraudDetectionResult(
            return_id=return_id,
            scan_timestamp=datetime.now(),
            overall_risk_level=FraudRiskLevel.MODERATE,
            risk_score=50.0,
            ai_confidence=0.0,
            raw_analysis=content
        )


# Singleton instance
_fraud_detector: Optional[OpenAIFraudDetector] = None


def get_fraud_detector() -> OpenAIFraudDetector:
    """Get the singleton OpenAIFraudDetector instance."""
    global _fraud_detector
    if _fraud_detector is None:
        _fraud_detector = OpenAIFraudDetector()
    return _fraud_detector


__all__ = [
    "OpenAIFraudDetector",
    "get_fraud_detector",
    "FraudDetectionResult",
    "FraudIndicator",
    "PatternMatch",
    "FraudRiskLevel",
    "FraudIndicatorType",
]
