"""
Tax Return Anomaly Detection Service.

Uses AI to detect unusual patterns and potential issues in tax returns:
- Unusual deduction patterns
- Potential audit triggers
- Data entry errors
- Statistical outliers
- Fraud indicators

Usage:
    from services.ai.anomaly_detector import get_anomaly_detector

    detector = get_anomaly_detector()

    # Analyze a tax return for anomalies
    anomalies = await detector.analyze_return(tax_return_data)

    # Get specific risk assessment
    audit_risk = await detector.assess_audit_risk(tax_return_data)
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


class AnomalySeverity(str, Enum):
    """Severity levels for detected anomalies."""
    LOW = "low"           # Minor inconsistency, likely not an issue
    MEDIUM = "medium"     # Should be reviewed, potential issue
    HIGH = "high"         # Likely error or audit trigger
    CRITICAL = "critical" # Definite error or fraud indicator


class AnomalyCategory(str, Enum):
    """Categories of anomalies."""
    DATA_ENTRY = "data_entry"           # Typos, transposed digits
    MATHEMATICAL = "mathematical"        # Calculation errors
    CONSISTENCY = "consistency"          # Internal inconsistencies
    STATISTICAL = "statistical"          # Outliers vs norms
    COMPLIANCE = "compliance"            # Rule violations
    AUDIT_TRIGGER = "audit_trigger"      # Known IRS flags
    FRAUD_INDICATOR = "fraud_indicator"  # Potential fraud


@dataclass
class Anomaly:
    """A detected anomaly in a tax return."""
    category: AnomalyCategory
    severity: AnomalySeverity
    field: str
    description: str
    current_value: Any
    expected_range: Optional[str] = None
    recommendation: Optional[str] = None
    irs_reference: Optional[str] = None
    confidence: float = 0.5


@dataclass
class AnomalyReport:
    """Complete anomaly analysis report."""
    total_anomalies: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    anomalies: List[Anomaly]
    overall_risk_score: float  # 0-100
    audit_risk_level: str  # "low", "medium", "high"
    recommendations: List[str]
    raw_analysis: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AuditRiskAssessment:
    """IRS audit risk assessment."""
    overall_risk: str  # "low", "medium", "high"
    risk_score: float  # 0-100
    primary_triggers: List[str]
    contributing_factors: List[str]
    mitigating_factors: List[str]
    recommendations: List[str]
    comparable_audit_rate: float  # Estimated % based on DIF score factors


# =============================================================================
# DETECTION RULES
# =============================================================================

# Statistical norms for anomaly detection (simplified)
STATISTICAL_NORMS = {
    "charitable_pct_of_agi": {
        "typical_range": (0.01, 0.10),
        "audit_threshold": 0.15,
        "description": "Charitable deductions as % of AGI"
    },
    "business_expense_ratio": {
        "typical_range": (0.30, 0.70),
        "audit_threshold": 0.85,
        "description": "Business expenses as % of gross revenue"
    },
    "home_office_sqft": {
        "typical_range": (100, 400),
        "audit_threshold": 600,
        "description": "Home office square footage"
    },
    "vehicle_business_pct": {
        "typical_range": (0.50, 0.80),
        "audit_threshold": 0.95,
        "description": "Vehicle business use percentage"
    },
    "meal_expense_ratio": {
        "typical_range": (0.01, 0.05),
        "audit_threshold": 0.10,
        "description": "Meal expenses as % of gross revenue"
    },
}

# Known IRS audit triggers
AUDIT_TRIGGERS = [
    {
        "name": "high_income",
        "condition": lambda d: d.get("agi", 0) > 500000,
        "description": "High income (AGI > $500K) increases audit probability",
        "severity": AnomalySeverity.MEDIUM
    },
    {
        "name": "large_charitable",
        "condition": lambda d: d.get("charitable_pct", 0) > 0.15,
        "description": "Charitable deductions exceed 15% of AGI",
        "severity": AnomalySeverity.HIGH
    },
    {
        "name": "cash_business",
        "condition": lambda d: d.get("business_type", "").lower() in ["restaurant", "retail", "bar", "salon"],
        "description": "Cash-intensive business type has higher audit rates",
        "severity": AnomalySeverity.MEDIUM
    },
    {
        "name": "schedule_c_loss",
        "condition": lambda d: d.get("schedule_c_profit", 0) < 0 and d.get("has_w2_income", False),
        "description": "Schedule C loss while having W-2 income (hobby loss rules)",
        "severity": AnomalySeverity.HIGH
    },
    {
        "name": "round_numbers",
        "condition": lambda d: d.get("round_number_count", 0) > 5,
        "description": "Multiple round numbers suggest estimated values",
        "severity": AnomalySeverity.MEDIUM
    },
    {
        "name": "high_vehicle_deduction",
        "condition": lambda d: d.get("vehicle_deduction", 0) > 20000,
        "description": "Vehicle deduction over $20K triggers scrutiny",
        "severity": AnomalySeverity.MEDIUM
    },
    {
        "name": "excessive_home_office",
        "condition": lambda d: d.get("home_office_pct", 0) > 0.30,
        "description": "Home office exceeds 30% of home is unusual",
        "severity": AnomalySeverity.HIGH
    },
    {
        "name": "crypto_unreported",
        "condition": lambda d: d.get("has_crypto", False) and not d.get("crypto_reported", False),
        "description": "Crypto activity indicated but not reported",
        "severity": AnomalySeverity.CRITICAL
    },
]


# =============================================================================
# ANOMALY DETECTOR SERVICE
# =============================================================================

class AnomalyDetector:
    """
    AI-powered anomaly detection for tax returns.

    Features:
    - Statistical outlier detection
    - Known audit trigger identification
    - Data consistency checking
    - Fraud indicator flagging
    - Risk scoring
    """

    def __init__(self, ai_service: Optional[UnifiedAIService] = None):
        self.ai_service = ai_service or get_ai_service()

    async def analyze_return(
        self,
        return_data: Dict[str, Any],
        prior_year_data: Optional[Dict[str, Any]] = None
    ) -> AnomalyReport:
        """
        Perform comprehensive anomaly analysis on a tax return.

        Args:
            return_data: Current year tax return data
            prior_year_data: Optional prior year for comparison

        Returns:
            AnomalyReport with all detected anomalies
        """
        anomalies = []

        # Rule-based detection
        rule_anomalies = self._check_rules(return_data)
        anomalies.extend(rule_anomalies)

        # Statistical anomaly detection
        stat_anomalies = self._check_statistical(return_data)
        anomalies.extend(stat_anomalies)

        # Year-over-year comparison
        if prior_year_data:
            yoy_anomalies = self._check_year_over_year(return_data, prior_year_data)
            anomalies.extend(yoy_anomalies)

        # AI-powered deep analysis
        ai_anomalies = await self._ai_deep_analysis(return_data, anomalies)
        anomalies.extend(ai_anomalies)

        # Calculate risk score
        risk_score = self._calculate_risk_score(anomalies)
        audit_risk = self._determine_audit_risk(risk_score)

        # Generate recommendations
        recommendations = self._generate_recommendations(anomalies)

        # Count by severity
        critical = sum(1 for a in anomalies if a.severity == AnomalySeverity.CRITICAL)
        high = sum(1 for a in anomalies if a.severity == AnomalySeverity.HIGH)
        medium = sum(1 for a in anomalies if a.severity == AnomalySeverity.MEDIUM)
        low = sum(1 for a in anomalies if a.severity == AnomalySeverity.LOW)

        return AnomalyReport(
            total_anomalies=len(anomalies),
            critical_count=critical,
            high_count=high,
            medium_count=medium,
            low_count=low,
            anomalies=anomalies,
            overall_risk_score=risk_score,
            audit_risk_level=audit_risk,
            recommendations=recommendations,
            raw_analysis=""
        )

    async def assess_audit_risk(
        self,
        return_data: Dict[str, Any]
    ) -> AuditRiskAssessment:
        """
        Assess IRS audit risk for a tax return.

        Args:
            return_data: Tax return data

        Returns:
            AuditRiskAssessment with detailed risk analysis
        """
        prompt = f"""Analyze this tax return data for IRS audit risk.

Tax Return Data:
{self._format_return_for_ai(return_data)}

Assess audit risk considering:
1. DIF (Discriminant Information Function) score factors
2. Known IRS audit triggers
3. Statistical outliers vs national averages
4. Document support requirements
5. Filing status and income level audit rates

Return JSON:
{{
    "overall_risk": "low|medium|high",
    "risk_score": 0-100,
    "primary_triggers": ["list of main audit triggers"],
    "contributing_factors": ["other risk factors"],
    "mitigating_factors": ["factors that reduce risk"],
    "recommendations": ["specific actions to reduce risk"],
    "estimated_audit_rate": 0.0-10.0 (percentage),
    "reasoning": "brief explanation"
}}"""

        try:
            response = await self.ai_service.complete(
                prompt=prompt,
                system_prompt="You are an expert tax auditor with 20 years IRS experience. Analyze returns for audit risk factors.",
                capability=ModelCapability.STANDARD,
                temperature=0.2
            )

            import json
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            result = json.loads(content)

            return AuditRiskAssessment(
                overall_risk=result.get("overall_risk", "medium"),
                risk_score=result.get("risk_score", 50),
                primary_triggers=result.get("primary_triggers", []),
                contributing_factors=result.get("contributing_factors", []),
                mitigating_factors=result.get("mitigating_factors", []),
                recommendations=result.get("recommendations", []),
                comparable_audit_rate=result.get("estimated_audit_rate", 1.0)
            )

        except Exception as e:
            logger.error(f"Audit risk assessment failed: {e}")
            return AuditRiskAssessment(
                overall_risk="unknown",
                risk_score=50,
                primary_triggers=[],
                contributing_factors=[],
                mitigating_factors=[],
                recommendations=["Unable to complete risk assessment"],
                comparable_audit_rate=1.0
            )

    async def check_data_entry_errors(
        self,
        return_data: Dict[str, Any]
    ) -> List[Anomaly]:
        """
        Check for common data entry errors.

        Args:
            return_data: Tax return data

        Returns:
            List of data entry anomalies
        """
        anomalies = []

        # Check for transposed digits in SSN
        ssn = str(return_data.get("ssn", ""))
        if ssn and len(ssn) >= 4:
            # Check for obvious patterns
            if ssn[-4:] in ["0000", "1111", "1234", "9999"]:
                anomalies.append(Anomaly(
                    category=AnomalyCategory.DATA_ENTRY,
                    severity=AnomalySeverity.HIGH,
                    field="ssn",
                    description="SSN appears to have placeholder or test values",
                    current_value=f"XXX-XX-{ssn[-4:]}",
                    recommendation="Verify SSN is entered correctly"
                ))

        # Check for reasonable income amounts
        wages = return_data.get("wages", 0)
        if wages and wages > 0:
            if wages < 1000 and return_data.get("filing_status") != "dependent":
                anomalies.append(Anomaly(
                    category=AnomalyCategory.DATA_ENTRY,
                    severity=AnomalySeverity.MEDIUM,
                    field="wages",
                    description="Wages appear unusually low - possible missing digits",
                    current_value=wages,
                    expected_range="Typically > $10,000 for full-time work",
                    recommendation="Verify W-2 wages are entered correctly"
                ))

        # Check for impossibly high values
        if wages and wages > 50000000:  # $50M
            anomalies.append(Anomaly(
                category=AnomalyCategory.DATA_ENTRY,
                severity=AnomalySeverity.HIGH,
                field="wages",
                description="Wages exceed reasonable maximum - check for extra digits",
                current_value=wages,
                recommendation="Verify W-2 Box 1 amount"
            ))

        # Check withholding vs income
        federal_withholding = return_data.get("federal_withholding", 0)
        if federal_withholding and wages:
            withholding_rate = federal_withholding / wages if wages > 0 else 0
            if withholding_rate > 0.50:
                anomalies.append(Anomaly(
                    category=AnomalyCategory.DATA_ENTRY,
                    severity=AnomalySeverity.HIGH,
                    field="federal_withholding",
                    description="Federal withholding exceeds 50% of wages - verify W-2 Box 2",
                    current_value=federal_withholding,
                    expected_range=f"Typically 10-35% of wages (${wages * 0.1:,.0f} - ${wages * 0.35:,.0f})",
                    recommendation="Check if withholding and wages are from correct boxes"
                ))

        return anomalies

    def _check_rules(self, return_data: Dict[str, Any]) -> List[Anomaly]:
        """Check against known audit triggers."""
        anomalies = []

        for trigger in AUDIT_TRIGGERS:
            try:
                if trigger["condition"](return_data):
                    anomalies.append(Anomaly(
                        category=AnomalyCategory.AUDIT_TRIGGER,
                        severity=trigger["severity"],
                        field=trigger["name"],
                        description=trigger["description"],
                        current_value=None,
                        confidence=0.8
                    ))
            except Exception:
                pass  # Skip if data missing

        return anomalies

    def _check_statistical(self, return_data: Dict[str, Any]) -> List[Anomaly]:
        """Check for statistical outliers."""
        anomalies = []
        agi = return_data.get("agi", 0)

        if agi <= 0:
            return anomalies

        # Charitable deduction check
        charitable = return_data.get("charitable_deductions", 0)
        if charitable > 0:
            charitable_pct = charitable / agi
            norm = STATISTICAL_NORMS["charitable_pct_of_agi"]

            if charitable_pct > norm["audit_threshold"]:
                anomalies.append(Anomaly(
                    category=AnomalyCategory.STATISTICAL,
                    severity=AnomalySeverity.HIGH,
                    field="charitable_deductions",
                    description=f"Charitable deductions ({charitable_pct:.1%} of AGI) exceed audit threshold",
                    current_value=charitable,
                    expected_range=f"{norm['typical_range'][0]:.0%} - {norm['typical_range'][1]:.0%} of AGI",
                    recommendation="Ensure documentation for all charitable contributions over $250",
                    irs_reference="Publication 526"
                ))
            elif charitable_pct > norm["typical_range"][1]:
                anomalies.append(Anomaly(
                    category=AnomalyCategory.STATISTICAL,
                    severity=AnomalySeverity.MEDIUM,
                    field="charitable_deductions",
                    description=f"Charitable deductions ({charitable_pct:.1%} of AGI) above typical range",
                    current_value=charitable,
                    expected_range=f"{norm['typical_range'][0]:.0%} - {norm['typical_range'][1]:.0%} of AGI",
                    recommendation="Keep receipts and appraisals for all donations"
                ))

        return anomalies

    def _check_year_over_year(
        self,
        current: Dict[str, Any],
        prior: Dict[str, Any]
    ) -> List[Anomaly]:
        """Check for suspicious year-over-year changes."""
        anomalies = []

        # Income change check
        current_income = current.get("total_income", 0)
        prior_income = prior.get("total_income", 0)

        if prior_income > 0:
            income_change = (current_income - prior_income) / prior_income

            if income_change < -0.50:  # Income dropped 50%+
                anomalies.append(Anomaly(
                    category=AnomalyCategory.CONSISTENCY,
                    severity=AnomalySeverity.MEDIUM,
                    field="total_income",
                    description=f"Income dropped {abs(income_change):.0%} from prior year",
                    current_value=current_income,
                    expected_range=f"Prior year: ${prior_income:,.0f}",
                    recommendation="Document reason for income change (job loss, retirement, etc.)"
                ))

        return anomalies

    async def _ai_deep_analysis(
        self,
        return_data: Dict[str, Any],
        existing_anomalies: List[Anomaly]
    ) -> List[Anomaly]:
        """Use AI for deep pattern analysis."""
        prompt = f"""Analyze this tax return for anomalies not caught by standard rules.

Tax Return Summary:
{self._format_return_for_ai(return_data)}

Already Detected Anomalies:
{[a.description for a in existing_anomalies]}

Look for:
1. Internal inconsistencies (values that don't make sense together)
2. Missing deductions they should likely have
3. Unusual combinations of income sources
4. Potential errors in complex situations (K-1s, investments)
5. Red flags for specific filing situations

Return JSON array of additional anomalies:
[
    {{
        "field": "field_name",
        "description": "what's unusual",
        "severity": "low|medium|high|critical",
        "category": "data_entry|mathematical|consistency|statistical|compliance|audit_trigger|fraud_indicator",
        "recommendation": "what to do",
        "confidence": 0.0-1.0
    }}
]

Return empty array [] if no additional anomalies found."""

        try:
            response = await self.ai_service.complete(
                prompt=prompt,
                system_prompt="You are a tax fraud detection specialist. Identify subtle anomalies that automated rules miss.",
                capability=ModelCapability.STANDARD,
                temperature=0.2
            )

            import json
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            ai_results = json.loads(content)
            anomalies = []

            for item in ai_results:
                anomalies.append(Anomaly(
                    category=AnomalyCategory(item.get("category", "consistency")),
                    severity=AnomalySeverity(item.get("severity", "medium")),
                    field=item.get("field", "general"),
                    description=item.get("description", ""),
                    current_value=None,
                    recommendation=item.get("recommendation"),
                    confidence=item.get("confidence", 0.7)
                ))

            return anomalies

        except Exception as e:
            logger.error(f"AI deep analysis failed: {e}")
            return []

    def _calculate_risk_score(self, anomalies: List[Anomaly]) -> float:
        """Calculate overall risk score from anomalies."""
        if not anomalies:
            return 0.0

        score = 0
        weights = {
            AnomalySeverity.CRITICAL: 30,
            AnomalySeverity.HIGH: 15,
            AnomalySeverity.MEDIUM: 5,
            AnomalySeverity.LOW: 1
        }

        for anomaly in anomalies:
            score += weights.get(anomaly.severity, 1) * anomaly.confidence

        # Cap at 100
        return min(100, score)

    def _determine_audit_risk(self, risk_score: float) -> str:
        """Determine audit risk level from score."""
        if risk_score >= 70:
            return "high"
        elif risk_score >= 40:
            return "medium"
        else:
            return "low"

    def _generate_recommendations(self, anomalies: List[Anomaly]) -> List[str]:
        """Generate prioritized recommendations."""
        recommendations = []

        # Add unique recommendations from anomalies
        for anomaly in sorted(anomalies, key=lambda a: a.severity.value, reverse=True):
            if anomaly.recommendation and anomaly.recommendation not in recommendations:
                recommendations.append(anomaly.recommendation)

        # Add general recommendations based on severity counts
        critical = sum(1 for a in anomalies if a.severity == AnomalySeverity.CRITICAL)
        high = sum(1 for a in anomalies if a.severity == AnomalySeverity.HIGH)

        if critical > 0:
            recommendations.insert(0, "CRITICAL: Review flagged items before filing - potential errors or fraud indicators")
        if high > 2:
            recommendations.insert(1 if critical > 0 else 0, "Multiple high-severity issues detected - consider professional review")

        return recommendations[:10]  # Limit to top 10

    def _format_return_for_ai(self, return_data: Dict[str, Any]) -> str:
        """Format return data for AI analysis."""
        # Mask sensitive data
        safe_data = dict(return_data)
        if "ssn" in safe_data:
            ssn = str(safe_data["ssn"])
            safe_data["ssn"] = f"XXX-XX-{ssn[-4:]}" if len(ssn) >= 4 else "XXX-XX-XXXX"

        import json
        return json.dumps(safe_data, indent=2, default=str)


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_anomaly_detector: Optional[AnomalyDetector] = None


def get_anomaly_detector() -> AnomalyDetector:
    """Get the singleton anomaly detector instance."""
    global _anomaly_detector
    if _anomaly_detector is None:
        _anomaly_detector = AnomalyDetector()
    return _anomaly_detector


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "AnomalyDetector",
    "Anomaly",
    "AnomalyReport",
    "AnomalySeverity",
    "AnomalyCategory",
    "AuditRiskAssessment",
    "get_anomaly_detector",
]
