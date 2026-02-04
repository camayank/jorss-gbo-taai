"""
Risk Assessment Section - Audit risk indicators and compliance analysis.

Provides:
- Audit risk score with visual indicator
- Red flag identification
- Compliance status summary
- Risk mitigation recommendations
"""

from __future__ import annotations

from typing import Optional, List, TYPE_CHECKING
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum

if TYPE_CHECKING:
    from universal_report.data_collector import NormalizedReportData
    from universal_report.branding.theme_manager import BrandTheme


class RiskLevel(Enum):
    LOW = "low"
    MODERATE = "moderate"
    ELEVATED = "elevated"
    HIGH = "high"


@dataclass
class AuditRiskFactor:
    """Individual audit risk factor."""
    name: str
    description: str
    risk_level: RiskLevel
    score_impact: int  # 1-10
    mitigation: str
    irs_reference: Optional[str] = None


class RiskAssessmentRenderer:
    """Render audit risk assessment section."""

    # IRS Audit Selection Criteria (DIF Score factors)
    AUDIT_RISK_FACTORS = {
        'high_deductions_ratio': {
            'name': 'High Deductions to Income Ratio',
            'description': 'Your deductions are significantly higher than average for your income level',
            'threshold': 0.35,  # Deductions > 35% of AGI
            'irs_reference': 'IRS DIF Score Factor',
            'mitigation': 'Ensure all deductions are well-documented with receipts and records'
        },
        'large_charitable_contributions': {
            'name': 'Large Charitable Contributions',
            'description': 'Charitable contributions exceeding typical percentages for your income',
            'threshold': 0.10,  # > 10% of AGI
            'irs_reference': 'Publication 526',
            'mitigation': 'Maintain appraisals for items over $5,000 and acknowledgment letters'
        },
        'home_office_deduction': {
            'name': 'Home Office Deduction',
            'description': 'Home office deductions require strict exclusive use requirements',
            'irs_reference': 'Publication 587',
            'mitigation': 'Document exclusive business use with photos and measurements'
        },
        'business_losses': {
            'name': 'Recurring Business Losses',
            'description': 'Business showing losses for multiple consecutive years',
            'threshold': 3,  # 3+ years of losses
            'irs_reference': 'IRC Section 183 (Hobby Loss Rules)',
            'mitigation': 'Document profit motive and business activities'
        },
        'cash_business': {
            'name': 'Cash-Intensive Business',
            'description': 'Businesses with significant cash transactions have higher scrutiny',
            'irs_reference': 'IRS Cash Business Audit Guide',
            'mitigation': 'Maintain meticulous daily records and bank deposits'
        },
        'high_income': {
            'name': 'High Income Level',
            'description': 'Higher incomes face statistically higher audit rates',
            'threshold': 500000,
            'irs_reference': 'IRS Data Book Statistics',
            'mitigation': 'Work with qualified tax professional for complex returns'
        },
        'schedule_c_income': {
            'name': 'Self-Employment Income',
            'description': 'Schedule C filers have higher audit rates than W-2 employees',
            'irs_reference': 'IRS Audit Statistics',
            'mitigation': 'Keep separate business accounts and detailed expense records'
        },
        'rental_losses': {
            'name': 'Rental Property Losses',
            'description': 'Rental losses, especially passive activity losses, face scrutiny',
            'irs_reference': 'IRC Section 469',
            'mitigation': 'Document material participation and active involvement'
        },
        'foreign_accounts': {
            'name': 'Foreign Financial Accounts',
            'description': 'Foreign accounts require FBAR and FATCA reporting',
            'irs_reference': 'FBAR FinCEN 114',
            'mitigation': 'Ensure all foreign accounts are properly disclosed'
        },
        'cryptocurrency': {
            'name': 'Cryptocurrency Transactions',
            'description': 'Virtual currency transactions are high-priority for IRS',
            'irs_reference': 'IRS Notice 2014-21',
            'mitigation': 'Track cost basis and report all taxable transactions'
        },
        'rounding': {
            'name': 'Rounded Numbers',
            'description': 'Returns with many rounded numbers may indicate estimation',
            'irs_reference': 'IRS DIF Score Factor',
            'mitigation': 'Report exact amounts from source documents'
        },
        'employee_expenses': {
            'name': 'Unreimbursed Employee Expenses',
            'description': 'High unreimbursed business expenses raise flags',
            'irs_reference': 'IRS Publication 463',
            'mitigation': 'Document employer reimbursement policy'
        }
    }

    def __init__(
        self,
        data: "NormalizedReportData",
        theme: Optional["BrandTheme"] = None,
    ):
        self.data = data
        self.theme = theme

    def assess_risks(self) -> List[AuditRiskFactor]:
        """Analyze data and identify audit risk factors."""
        risks = []

        # Check deductions ratio
        if self.data.adjusted_gross_income and self.data.total_deductions:
            ratio = float(self.data.total_deductions) / float(self.data.adjusted_gross_income)
            if ratio > 0.35:
                factor = self.AUDIT_RISK_FACTORS['high_deductions_ratio']
                risks.append(AuditRiskFactor(
                    name=factor['name'],
                    description=f"Your deductions ({ratio*100:.0f}% of AGI) exceed the typical threshold",
                    risk_level=RiskLevel.ELEVATED if ratio < 0.5 else RiskLevel.HIGH,
                    score_impact=7 if ratio < 0.5 else 9,
                    mitigation=factor['mitigation'],
                    irs_reference=factor['irs_reference']
                ))

        # Check high income
        if self.data.gross_income and float(self.data.gross_income) > 500000:
            factor = self.AUDIT_RISK_FACTORS['high_income']
            risks.append(AuditRiskFactor(
                name=factor['name'],
                description=f"Income of ${float(self.data.gross_income):,.0f} places you in a higher audit probability bracket",
                risk_level=RiskLevel.MODERATE if float(self.data.gross_income) < 1000000 else RiskLevel.ELEVATED,
                score_impact=5 if float(self.data.gross_income) < 1000000 else 7,
                mitigation=factor['mitigation'],
                irs_reference=factor['irs_reference']
            ))

        # Check for self-employment income
        for income in self.data.income_items:
            if income.category.lower() in ['self-employment', 'business', 'schedule c', '1099']:
                factor = self.AUDIT_RISK_FACTORS['schedule_c_income']
                risks.append(AuditRiskFactor(
                    name=factor['name'],
                    description="Self-employment income on Schedule C has higher audit rates",
                    risk_level=RiskLevel.MODERATE,
                    score_impact=5,
                    mitigation=factor['mitigation'],
                    irs_reference=factor['irs_reference']
                ))
                break

        # Check for rental income/losses
        for income in self.data.income_items:
            if 'rental' in income.category.lower():
                if income.amount < 0:
                    factor = self.AUDIT_RISK_FACTORS['rental_losses']
                    risks.append(AuditRiskFactor(
                        name=factor['name'],
                        description=f"Rental loss of ${abs(float(income.amount)):,.0f} may trigger PAL rules scrutiny",
                        risk_level=RiskLevel.MODERATE,
                        score_impact=5,
                        mitigation=factor['mitigation'],
                        irs_reference=factor['irs_reference']
                    ))
                break

        # Check for home office deduction
        for deduction in self.data.deduction_items:
            if 'home office' in deduction.description.lower():
                factor = self.AUDIT_RISK_FACTORS['home_office_deduction']
                risks.append(AuditRiskFactor(
                    name=factor['name'],
                    description="Home office deductions require strict documentation of exclusive use",
                    risk_level=RiskLevel.MODERATE,
                    score_impact=5,
                    mitigation=factor['mitigation'],
                    irs_reference=factor['irs_reference']
                ))
                break

        # Check charitable contributions ratio
        total_charitable = sum(
            float(d.amount) for d in self.data.deduction_items
            if 'charit' in d.description.lower() or 'donation' in d.description.lower()
        )
        if self.data.adjusted_gross_income and total_charitable > 0:
            ratio = total_charitable / float(self.data.adjusted_gross_income)
            if ratio > 0.10:
                factor = self.AUDIT_RISK_FACTORS['large_charitable_contributions']
                risks.append(AuditRiskFactor(
                    name=factor['name'],
                    description=f"Charitable contributions of {ratio*100:.1f}% of AGI exceed typical levels",
                    risk_level=RiskLevel.MODERATE if ratio < 0.20 else RiskLevel.ELEVATED,
                    score_impact=4 if ratio < 0.20 else 6,
                    mitigation=factor['mitigation'],
                    irs_reference=factor['irs_reference']
                ))

        return risks

    def calculate_risk_score(self, risks: List[AuditRiskFactor]) -> int:
        """Calculate overall risk score (0-100)."""
        if not risks:
            return 15  # Base risk score (everyone has some risk)

        total_impact = sum(r.score_impact for r in risks)
        # Normalize to 0-100 scale, max impact of 50 points = 100 score
        score = min(100, 15 + (total_impact * 1.7))
        return int(score)

    def get_risk_level(self, score: int) -> tuple[RiskLevel, str]:
        """Get risk level and description from score."""
        if score < 25:
            return RiskLevel.LOW, "Your return has typical audit risk"
        elif score < 45:
            return RiskLevel.MODERATE, "Some factors may increase audit attention"
        elif score < 70:
            return RiskLevel.ELEVATED, "Multiple factors warrant careful documentation"
        else:
            return RiskLevel.HIGH, "Consider professional review before filing"

    def render(self) -> str:
        """Render the complete risk assessment section."""
        primary = self.theme.primary_color if self.theme else "#1e3a5f"
        warning_color = self.theme.warning_color if self.theme else "#f59e0b"
        danger_color = self.theme.danger_color if self.theme else "#ef4444"
        success_color = self.theme.accent_color if self.theme else "#10b981"

        # Assess risks
        risks = self.assess_risks()
        risk_score = self.calculate_risk_score(risks)
        risk_level, risk_description = self.get_risk_level(risk_score)

        # Determine colors based on risk level
        level_colors = {
            RiskLevel.LOW: success_color,
            RiskLevel.MODERATE: warning_color,
            RiskLevel.ELEVATED: "#f97316",  # Orange
            RiskLevel.HIGH: danger_color
        }
        level_color = level_colors.get(risk_level, warning_color)

        # Risk gauge
        gauge_html = self._render_risk_gauge(risk_score, level_color, primary)

        # Risk factors cards
        factors_html = self._render_risk_factors(risks, primary, warning_color, danger_color)

        # Compliance checklist
        checklist_html = self._render_compliance_checklist(primary, success_color)

        return f'''
<section class="risk-assessment" style="page-break-before: always;">
  <h2 style="color: {primary}; border-bottom: 2px solid {primary}; padding-bottom: 8px; margin-bottom: 24px;">
    Audit Risk Assessment
  </h2>

  <div style="background: linear-gradient(135deg, {level_color}10 0%, {level_color}20 100%); border: 1px solid {level_color}40; border-radius: 12px; padding: 24px; margin-bottom: 24px;">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 20px;">
      <div>
        <div style="font-size: 0.875rem; color: #6b7280; text-transform: uppercase; letter-spacing: 1px;">Risk Level</div>
        <div style="font-size: 1.75rem; font-weight: 700; color: {level_color}; margin-top: 4px;">
          {risk_level.value.title()}
        </div>
        <div style="font-size: 0.875rem; color: #374151; margin-top: 8px;">
          {risk_description}
        </div>
      </div>

      {gauge_html}
    </div>
  </div>

  {factors_html}

  {checklist_html}

  <div style="background: #f3f4f6; border-radius: 8px; padding: 16px; margin-top: 24px;">
    <p style="margin: 0; font-size: 0.875rem; color: #6b7280;">
      <strong>Note:</strong> This risk assessment is based on statistical factors that may trigger IRS attention.
      A higher risk score does not mean your return is incorrect, only that proper documentation is especially important.
      IRS audit selection also uses proprietary algorithms (DIF scores) that cannot be fully predicted.
    </p>
  </div>
</section>
'''

    def _render_risk_gauge(self, score: int, level_color: str, primary: str) -> str:
        """Render risk score gauge."""
        # Calculate needle rotation (-90 to 90 degrees for 0-100 score)
        rotation = -90 + (score * 1.8)

        return f'''
<div style="text-align: center;">
  <svg viewBox="0 0 200 120" width="180" height="110">
    <!-- Background arc -->
    <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="#e5e7eb" stroke-width="12" stroke-linecap="round"/>

    <!-- Low risk zone (green) -->
    <path d="M 20 100 A 80 80 0 0 1 65 35" fill="none" stroke="#10b981" stroke-width="12" stroke-linecap="round"/>

    <!-- Moderate risk zone (yellow) -->
    <path d="M 65 35 A 80 80 0 0 1 100 20" fill="none" stroke="#f59e0b" stroke-width="12" stroke-linecap="round"/>

    <!-- Elevated risk zone (orange) -->
    <path d="M 100 20 A 80 80 0 0 1 135 35" fill="none" stroke="#f97316" stroke-width="12" stroke-linecap="round"/>

    <!-- High risk zone (red) -->
    <path d="M 135 35 A 80 80 0 0 1 180 100" fill="none" stroke="#ef4444" stroke-width="12" stroke-linecap="round"/>

    <!-- Needle -->
    <g transform="rotate({rotation}, 100, 100)">
      <line x1="100" y1="100" x2="100" y2="35" stroke="{primary}" stroke-width="3" stroke-linecap="round"/>
      <circle cx="100" cy="100" r="8" fill="{primary}"/>
    </g>

    <!-- Score text -->
    <text x="100" y="90" text-anchor="middle" font-size="24" font-weight="700" fill="{level_color}">{score}</text>
    <text x="100" y="108" text-anchor="middle" font-size="10" fill="#6b7280">RISK SCORE</text>
  </svg>
</div>
'''

    def _render_risk_factors(self, risks: List[AuditRiskFactor], primary: str, warning: str, danger: str) -> str:
        """Render identified risk factors."""
        if not risks:
            return f'''
<div style="background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px; padding: 20px; margin-bottom: 24px;">
  <div style="display: flex; align-items: center; gap: 12px;">
    <span style="font-size: 1.5rem;">✓</span>
    <div>
      <div style="font-weight: 600; color: #059669;">No Significant Risk Factors Identified</div>
      <div style="font-size: 0.875rem; color: #6b7280; margin-top: 4px;">
        Your return appears to have typical audit risk based on available data.
      </div>
    </div>
  </div>
</div>
'''

        cards_html = ""
        for risk in sorted(risks, key=lambda r: r.score_impact, reverse=True):
            level_color = danger if risk.risk_level in [RiskLevel.HIGH, RiskLevel.ELEVATED] else warning

            cards_html += f'''
<div style="border: 1px solid #e5e7eb; border-left: 4px solid {level_color}; border-radius: 8px; padding: 16px; margin-bottom: 12px;">
  <div style="display: flex; justify-content: space-between; align-items: flex-start;">
    <div style="flex: 1;">
      <div style="font-weight: 600; color: #111827; margin-bottom: 4px;">{risk.name}</div>
      <div style="font-size: 0.875rem; color: #6b7280; margin-bottom: 8px;">{risk.description}</div>
      <div style="font-size: 0.8125rem; color: #374151;">
        <strong>Mitigation:</strong> {risk.mitigation}
      </div>
      {f'<div style="font-size: 0.75rem; color: #9ca3af; margin-top: 4px;">Reference: {risk.irs_reference}</div>' if risk.irs_reference else ''}
    </div>
    <div style="background: {level_color}15; color: {level_color}; padding: 4px 12px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; white-space: nowrap; margin-left: 12px;">
      {risk.risk_level.value}
    </div>
  </div>
</div>
'''

        return f'''
<h3 style="color: {primary}; margin: 24px 0 16px 0;">Identified Risk Factors ({len(risks)})</h3>
{cards_html}
'''

    def _render_compliance_checklist(self, primary: str, success: str) -> str:
        """Render compliance documentation checklist."""
        checklist_items = [
            ("Keep records for at least 3 years (7 years for property)", "records"),
            ("Document all deductions with receipts or statements", "deductions"),
            ("Maintain mileage logs for vehicle expenses", "vehicle"),
            ("Keep acknowledgment letters for charitable gifts over $250", "charitable"),
            ("Store appraisals for non-cash donations over $5,000", "appraisals"),
            ("Retain bank statements showing business deposits", "banking"),
            ("Document home office square footage and exclusive use", "home_office"),
            ("Keep employment contracts and reimbursement policies", "employment"),
        ]

        items_html = ""
        for item_text, item_key in checklist_items:
            items_html += f'''
<div style="display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid #f3f4f6;">
  <div style="width: 20px; height: 20px; border: 2px solid {primary}; border-radius: 4px; display: flex; align-items: center; justify-content: center;">
    <!-- Checkbox placeholder -->
  </div>
  <span style="font-size: 0.875rem; color: #374151;">{item_text}</span>
</div>
'''

        return f'''
<h3 style="color: {primary}; margin: 24px 0 16px 0;">Documentation Checklist</h3>
<div style="background: #f9fafb; border-radius: 8px; padding: 16px;">
  {items_html}
</div>
'''
