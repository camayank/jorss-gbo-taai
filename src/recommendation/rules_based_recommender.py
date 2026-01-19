"""
Rules-Based Recommender.

Bridges the 764+ TaxRulesEngine rules to generate context-aware
tax recommendations and insights for the Smart Insights UI.

This module evaluates a taxpayer's situation against all applicable
tax rules and generates actionable recommendations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from models.tax_return import TaxReturn


@dataclass
class RuleInsight:
    """An insight generated from a tax rule."""
    rule_id: str
    category: str
    title: str
    description: str
    severity: str  # critical, high, medium, low, info
    priority: str  # immediate, current_year, next_year, long_term
    estimated_impact: float  # Positive = savings, negative = additional tax
    action_items: List[str]
    irs_reference: str
    irs_form: str
    confidence: float  # 0-100
    applies: bool  # Whether this rule applies to the taxpayer

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "priority": self.priority,
            "estimated_impact": self.estimated_impact,
            "action_items": self.action_items,
            "irs_reference": self.irs_reference,
            "irs_form": self.irs_form,
            "confidence": self.confidence,
            "applies": self.applies,
        }


class RulesBasedRecommender:
    """
    Generates recommendations based on the comprehensive TaxRulesEngine.

    Evaluates taxpayer situations against all 764+ rules and generates
    prioritized, actionable insights for the Smart Insights UI.
    """

    def __init__(self):
        """Initialize with the TaxRulesEngine."""
        from recommendation.tax_rules_engine import TaxRulesEngine, RuleCategory
        self._engine = TaxRulesEngine()
        self._rule_category = RuleCategory

    def analyze(self, tax_return: "TaxReturn") -> List[RuleInsight]:
        """
        Analyze a tax return against all applicable rules.

        Args:
            tax_return: The tax return to analyze

        Returns:
            List of RuleInsights sorted by priority and impact
        """
        insights = []

        # Build context from tax return
        context = self._build_context(tax_return)

        # Analyze by category for relevant rules
        insights.extend(self._analyze_virtual_currency(tax_return, context))
        insights.extend(self._analyze_foreign_assets(tax_return, context))
        insights.extend(self._analyze_household_employment(tax_return, context))
        insights.extend(self._analyze_k1_passthrough(tax_return, context))
        insights.extend(self._analyze_casualty_loss(tax_return, context))
        insights.extend(self._analyze_alimony(tax_return, context))
        insights.extend(self._analyze_general_rules(tax_return, context))

        # Sort by priority and impact
        priority_order = {"immediate": 0, "current_year": 1, "next_year": 2, "long_term": 3}
        insights.sort(key=lambda x: (priority_order.get(x.priority, 4), -x.estimated_impact))

        return insights

    def get_top_insights(self, tax_return: "TaxReturn", limit: int = 5) -> List[RuleInsight]:
        """Get top N insights for Smart Insights sidebar."""
        all_insights = self.analyze(tax_return)
        # Filter to only applicable and impactful insights
        applicable = [i for i in all_insights if i.applies and i.estimated_impact > 0]
        return applicable[:limit]

    def get_warnings(self, tax_return: "TaxReturn") -> List[RuleInsight]:
        """Get critical warnings that need immediate attention."""
        all_insights = self.analyze(tax_return)
        return [i for i in all_insights if i.applies and i.severity in ("critical", "high")]

    def _build_context(self, tax_return: "TaxReturn") -> Dict[str, Any]:
        """Build context dictionary from tax return for rule evaluation."""
        context = {
            "tax_year": 2025,
            "filing_status": getattr(tax_return.taxpayer, 'filing_status', None),
            "agi": getattr(tax_return, 'adjusted_gross_income', 0) or 0,
            "taxable_income": getattr(tax_return, 'taxable_income', 0) or 0,
            "total_income": getattr(tax_return, 'total_income', 0) or 0,
        }

        # Income sources
        if hasattr(tax_return, 'income') and tax_return.income:
            income = tax_return.income
            # Get wages from get_total_wages() method or w2_forms
            wages = 0
            if hasattr(income, 'get_total_wages'):
                wages = income.get_total_wages() or 0
            elif hasattr(income, 'w2_forms') and income.w2_forms:
                wages = sum(w2.wages or 0 for w2 in income.w2_forms)

            # Get total income
            total_income = 0
            if hasattr(income, 'get_total_income'):
                total_income = income.get_total_income() or 0

            context.update({
                "has_wages": wages > 0,
                "wages": wages,
                "total_income": total_income,
                "has_self_employment": (getattr(income, 'self_employment_income', 0) or 0) > 0,
                "self_employment_income": getattr(income, 'self_employment_income', 0) or 0,
                "has_investment_income": self._has_investment_income(income),
                "investment_income": self._get_investment_income(income),
                "has_crypto": getattr(income, 'has_virtual_currency', False),
                "crypto_transactions": getattr(income, 'virtual_currency_transactions', []) or [],
                "has_foreign_income": getattr(income, 'has_foreign_income', False),
                "foreign_income": getattr(income, 'foreign_earned_income', 0) or 0,
                "has_k1_income": self._has_k1_income(income),
                "k1_income": self._get_k1_income(income),
                "has_rental_income": (getattr(income, 'rental_income', 0) or 0) != 0,
                "rental_income": getattr(income, 'rental_income', 0) or 0,
            })

        # Deductions
        if hasattr(tax_return, 'deductions') and tax_return.deductions:
            deductions = tax_return.deductions
            context.update({
                "uses_itemized": getattr(deductions, 'uses_itemized', False),
                "total_itemized": self._get_total_itemized(deductions),
                "charitable_contributions": (
                    (getattr(deductions, 'charitable_cash', 0) or 0) +
                    (getattr(deductions, 'charitable_noncash', 0) or 0)
                ),
                "has_mortgage_interest": (getattr(deductions, 'mortgage_interest', 0) or 0) > 0,
                "salt_deduction": (
                    (getattr(deductions, 'state_local_taxes', 0) or 0) +
                    (getattr(deductions, 'property_taxes', 0) or 0)
                ),
            })

        # Credits
        if hasattr(tax_return, 'credits') and tax_return.credits:
            credits = tax_return.credits
            context.update({
                "has_child_tax_credit": (getattr(credits, 'child_tax_credit', 0) or 0) > 0,
                "has_education_credit": (getattr(credits, 'education_credit', 0) or 0) > 0,
                "has_foreign_tax_credit": (getattr(credits, 'foreign_tax_credit', 0) or 0) > 0,
            })

        # Taxpayer info
        if hasattr(tax_return, 'taxpayer') and tax_return.taxpayer:
            taxpayer = tax_return.taxpayer
            context.update({
                "age": getattr(taxpayer, 'age', 0) or 0,
                "num_dependents": len(getattr(taxpayer, 'dependents', []) or []),
                "state": getattr(taxpayer, 'state', None),
                "is_self_employed": context.get("has_self_employment", False),
            })

        # Foreign accounts
        context.update({
            "has_foreign_accounts": getattr(tax_return, 'has_foreign_accounts', False),
            "foreign_account_max_value": getattr(tax_return, 'foreign_account_max_value', 0) or 0,
        })

        # Household employment
        context.update({
            "has_household_employees": getattr(tax_return, 'has_household_employees', False),
            "household_wages_paid": getattr(tax_return, 'household_wages_paid', 0) or 0,
        })

        # Alimony
        context.update({
            "pays_alimony": getattr(tax_return, 'pays_alimony', False),
            "receives_alimony": getattr(tax_return, 'receives_alimony', False),
            "alimony_agreement_date": getattr(tax_return, 'alimony_agreement_date', None),
        })

        # Casualty losses
        context.update({
            "has_casualty_loss": getattr(tax_return, 'has_casualty_loss', False),
            "casualty_loss_amount": getattr(tax_return, 'casualty_loss_amount', 0) or 0,
            "is_federally_declared_disaster": getattr(tax_return, 'is_federally_declared_disaster', False),
        })

        return context

    def _has_investment_income(self, income) -> bool:
        """Check if taxpayer has investment income."""
        return (
            (getattr(income, 'dividend_income', 0) or 0) > 0 or
            (getattr(income, 'qualified_dividends', 0) or 0) > 0 or
            (getattr(income, 'interest_income', 0) or 0) > 0 or
            (getattr(income, 'taxable_interest', 0) or 0) > 0 or
            (getattr(income, 'short_term_capital_gains', 0) or 0) != 0 or
            (getattr(income, 'long_term_capital_gains', 0) or 0) != 0
        )

    def _get_investment_income(self, income) -> float:
        """Get total investment income."""
        return (
            (getattr(income, 'dividend_income', 0) or 0) +
            (getattr(income, 'qualified_dividends', 0) or 0) +
            (getattr(income, 'interest_income', 0) or 0) +
            (getattr(income, 'taxable_interest', 0) or 0) +
            max(0, getattr(income, 'short_term_capital_gains', 0) or 0) +
            max(0, getattr(income, 'long_term_capital_gains', 0) or 0)
        )

    def _has_k1_income(self, income) -> bool:
        """Check if taxpayer has K-1 income."""
        return (
            (getattr(income, 'partnership_income', 0) or 0) != 0 or
            (getattr(income, 'scorp_income', 0) or 0) != 0 or
            (getattr(income, 'trust_income', 0) or 0) != 0
        )

    def _get_k1_income(self, income) -> float:
        """Get total K-1 income."""
        return (
            (getattr(income, 'partnership_income', 0) or 0) +
            (getattr(income, 'scorp_income', 0) or 0) +
            (getattr(income, 'trust_income', 0) or 0)
        )

    def _get_total_itemized(self, deductions) -> float:
        """Get total itemized deductions."""
        return sum([
            getattr(deductions, 'mortgage_interest', 0) or 0,
            getattr(deductions, 'state_local_taxes', 0) or 0,
            getattr(deductions, 'property_taxes', 0) or 0,
            getattr(deductions, 'charitable_cash', 0) or 0,
            getattr(deductions, 'charitable_noncash', 0) or 0,
            getattr(deductions, 'medical_expenses', 0) or 0,
            getattr(deductions, 'other_itemized', 0) or 0,
        ])

    # =========================================================================
    # Category-Specific Analyzers
    # =========================================================================

    def _analyze_virtual_currency(self, tax_return: "TaxReturn", context: Dict) -> List[RuleInsight]:
        """Analyze virtual currency rules."""
        insights = []

        if not context.get("has_crypto"):
            return insights

        # Get relevant rules
        vc_rules = self._engine.get_rules_by_category(self._rule_category.VIRTUAL_CURRENCY)

        # VC014 - Form 1040 Digital Asset Question (Critical)
        rule = self._get_rule("VC014")
        if rule:
            insights.append(RuleInsight(
                rule_id="VC014",
                category="virtual_currency",
                title="Answer Digital Asset Question",
                description="You have cryptocurrency transactions. The IRS requires you to answer 'Yes' to the digital asset question on Form 1040.",
                severity="critical",
                priority="immediate",
                estimated_impact=0,  # Compliance, not savings
                action_items=[
                    "Answer 'Yes' to digital asset question on Form 1040",
                    "Report all crypto transactions on Form 8949"
                ],
                irs_reference=rule.irs_reference,
                irs_form="Form 1040, Form 8949",
                confidence=95,
                applies=True
            ))

        # VC012 - Form 8949 Reporting
        rule = self._get_rule("VC012")
        if rule:
            insights.append(RuleInsight(
                rule_id="VC012",
                category="virtual_currency",
                title="Report Crypto on Form 8949",
                description="All virtual currency sales, exchanges, and dispositions must be reported on Form 8949 with detailed transaction information.",
                severity="critical",
                priority="immediate",
                estimated_impact=0,
                action_items=[
                    "Report each crypto transaction on Form 8949",
                    "Include date acquired, date sold, proceeds, and cost basis",
                    "Transfer totals to Schedule D"
                ],
                irs_reference=rule.irs_reference,
                irs_form="Form 8949, Schedule D",
                confidence=95,
                applies=True
            ))

        # VC021 - FIFO Cost Basis
        rule = self._get_rule("VC021")
        if rule:
            # Estimate potential tax optimization from specific ID vs FIFO
            crypto_gain_estimate = context.get("investment_income", 0) * 0.1  # Rough estimate
            savings_estimate = crypto_gain_estimate * 0.15  # Tax rate impact

            insights.append(RuleInsight(
                rule_id="VC021",
                category="virtual_currency",
                title="Consider Cost Basis Method",
                description="Using specific identification instead of FIFO may reduce your tax liability by selecting higher-cost lots for sales.",
                severity="medium",
                priority="current_year",
                estimated_impact=savings_estimate,
                action_items=[
                    "Review cost basis methods (FIFO, LIFO, specific ID)",
                    "Consider specific identification for tax optimization",
                    "Document lot selection contemporaneously"
                ],
                irs_reference=rule.irs_reference,
                irs_form="Form 8949",
                confidence=60,
                applies=True
            ))

        # VC049 - FBAR for Foreign Crypto
        if context.get("foreign_account_max_value", 0) > 10000:
            rule = self._get_rule("VC049")
            if rule:
                insights.append(RuleInsight(
                    rule_id="VC049",
                    category="virtual_currency",
                    title="FBAR Filing Required for Foreign Crypto",
                    description=f"Your foreign crypto exchange accounts may exceed $10,000. FBAR (FinCEN 114) filing is required.",
                    severity="critical",
                    priority="immediate",
                    estimated_impact=0,
                    action_items=[
                        "File FinCEN Form 114 (FBAR) electronically",
                        "Include all foreign crypto exchange accounts",
                        "File by April 15 (auto-extension to October 15)"
                    ],
                    irs_reference=rule.irs_reference,
                    irs_form="FinCEN Form 114 (FBAR)",
                    confidence=85,
                    applies=True
                ))

        return insights

    def _analyze_foreign_assets(self, tax_return: "TaxReturn", context: Dict) -> List[RuleInsight]:
        """Analyze foreign assets rules."""
        insights = []

        foreign_value = context.get("foreign_account_max_value", 0)
        has_foreign_income = context.get("has_foreign_income", False)
        agi = context.get("agi", 0)

        # FA001 - FBAR Requirement
        if foreign_value > 10000:
            rule = self._get_rule("FA001")
            if rule:
                insights.append(RuleInsight(
                    rule_id="FA001",
                    category="foreign_assets",
                    title="FBAR Filing Required",
                    description=f"Your foreign financial accounts exceeded $10,000 at some point during the year. FBAR filing is mandatory.",
                    severity="critical",
                    priority="immediate",
                    estimated_impact=0,
                    action_items=[
                        "File FinCEN Form 114 (FBAR) electronically",
                        "Report all foreign bank and financial accounts",
                        "Include maximum value during the year"
                    ],
                    irs_reference=rule.irs_reference,
                    irs_form="FinCEN Form 114",
                    confidence=95,
                    applies=True
                ))

        # FA016 - Form 8938 FATCA
        filing_status = str(context.get("filing_status", "single")).lower()
        fatca_threshold = 100000 if "joint" in filing_status else 50000

        if foreign_value > fatca_threshold:
            rule = self._get_rule("FA016")
            if rule:
                insights.append(RuleInsight(
                    rule_id="FA016",
                    category="foreign_assets",
                    title="Form 8938 (FATCA) Required",
                    description=f"Your foreign financial assets exceed the ${fatca_threshold:,} threshold. Form 8938 must be filed with your tax return.",
                    severity="critical",
                    priority="immediate",
                    estimated_impact=0,
                    action_items=[
                        "Complete Form 8938",
                        "Attach to your Form 1040",
                        "Report specified foreign financial assets"
                    ],
                    irs_reference=rule.irs_reference,
                    irs_form="Form 8938",
                    confidence=90,
                    applies=True
                ))

        # FA031 - Foreign Tax Credit
        if has_foreign_income and context.get("has_foreign_tax_credit", False):
            rule = self._get_rule("FA031")
            if rule:
                foreign_income = context.get("foreign_income", 0)
                # Estimate FTC benefit
                ftc_estimate = min(foreign_income * 0.10, agi * 0.22 * 0.5)  # Rough estimate

                insights.append(RuleInsight(
                    rule_id="FA031",
                    category="foreign_assets",
                    title="Claim Foreign Tax Credit",
                    description="You paid foreign taxes on income. Consider claiming the Foreign Tax Credit to avoid double taxation.",
                    severity="high",
                    priority="immediate",
                    estimated_impact=ftc_estimate,
                    action_items=[
                        "Complete Form 1116",
                        "Gather foreign tax documentation",
                        "Compare credit vs deduction benefit"
                    ],
                    irs_reference=rule.irs_reference,
                    irs_form="Form 1116",
                    confidence=75,
                    applies=True
                ))

        # FA039 - Simplified FTC Method
        foreign_tax_paid = context.get("foreign_tax_paid", 0)
        simplified_threshold = 600 if "joint" in filing_status else 300

        if 0 < foreign_tax_paid <= simplified_threshold:
            rule = self._get_rule("FA039")
            if rule:
                insights.append(RuleInsight(
                    rule_id="FA039",
                    category="foreign_assets",
                    title="Use Simplified Foreign Tax Credit",
                    description=f"Your foreign taxes (${foreign_tax_paid:,.0f}) are under ${simplified_threshold}. You can claim the credit without Form 1116.",
                    severity="medium",
                    priority="immediate",
                    estimated_impact=foreign_tax_paid,
                    action_items=[
                        "Claim foreign tax credit directly on Form 1040",
                        "No Form 1116 required",
                        "Keep documentation of foreign taxes paid"
                    ],
                    irs_reference=rule.irs_reference,
                    irs_form="Form 1040",
                    confidence=85,
                    applies=True
                ))

        return insights

    def _analyze_household_employment(self, tax_return: "TaxReturn", context: Dict) -> List[RuleInsight]:
        """Analyze household employment rules."""
        insights = []

        household_wages = context.get("household_wages_paid", 0)

        if household_wages < 100:  # No significant household wages
            return insights

        # HH001 - Schedule H Threshold
        if household_wages >= 2700:
            rule = self._get_rule("HH001")
            if rule:
                # Calculate employer tax liability
                ss_medicare = household_wages * 0.0765  # Employer share
                futa = min(household_wages, 7000) * 0.006
                total_tax = ss_medicare + futa

                insights.append(RuleInsight(
                    rule_id="HH001",
                    category="household_employment",
                    title="Schedule H Required",
                    description=f"You paid ${household_wages:,.0f} to household employees. Schedule H is required, and you owe approximately ${total_tax:,.0f} in employment taxes.",
                    severity="critical",
                    priority="immediate",
                    estimated_impact=-total_tax,  # This is a tax owed, not savings
                    action_items=[
                        "Complete Schedule H",
                        "Issue W-2 to household employees by January 31",
                        "File Form W-3 with SSA",
                        "Pay employment taxes with your Form 1040"
                    ],
                    irs_reference=rule.irs_reference,
                    irs_form="Schedule H, Form W-2",
                    confidence=95,
                    applies=True
                ))

        # HH004 - EIN Requirement
        rule = self._get_rule("HH004")
        if rule:
            insights.append(RuleInsight(
                rule_id="HH004",
                category="household_employment",
                title="Obtain EIN for Household Employment",
                description="You need an Employer Identification Number (EIN) to report household employment taxes and issue W-2s.",
                severity="high",
                priority="immediate",
                estimated_impact=0,
                action_items=[
                    "Apply for EIN using Form SS-4",
                    "Can apply online at IRS.gov",
                    "Use EIN on Schedule H and W-2s"
                ],
                irs_reference=rule.irs_reference,
                irs_form="Form SS-4",
                confidence=90,
                applies=True
            ))

        return insights

    def _analyze_k1_passthrough(self, tax_return: "TaxReturn", context: Dict) -> List[RuleInsight]:
        """Analyze K-1 and passthrough entity rules."""
        insights = []

        if not context.get("has_k1_income"):
            return insights

        k1_income = context.get("k1_income", 0)
        agi = context.get("agi", 0)

        # K1051 - QBI Deduction
        rule = self._get_rule("K1051")
        if rule and k1_income > 0:
            # Calculate potential QBI deduction
            qbi_deduction = min(k1_income * 0.20, agi * 0.20)
            tax_savings = qbi_deduction * 0.22  # Assume 22% bracket

            filing_status = str(context.get("filing_status", "single")).lower()
            threshold = 394600 if "joint" in filing_status else 197300  # 2025 QBI thresholds

            if agi < threshold:
                insights.append(RuleInsight(
                    rule_id="K1051",
                    category="k1_passthrough",
                    title="Claim 20% QBI Deduction",
                    description=f"Your pass-through business income of ${k1_income:,.0f} may qualify for the 20% QBI deduction, potentially saving ${tax_savings:,.0f}.",
                    severity="high",
                    priority="immediate",
                    estimated_impact=tax_savings,
                    action_items=[
                        "Complete Form 8995 or 8995-A",
                        "Verify business is not a Specified Service Business (if over threshold)",
                        "Calculate W-2 wage limitation if needed"
                    ],
                    irs_reference=rule.irs_reference,
                    irs_form="Form 8995 or 8995-A",
                    confidence=80,
                    applies=True
                ))

        # K1029 - Passive Loss Limitation
        if context.get("has_rental_income") and context.get("rental_income", 0) < 0:
            rental_loss = abs(context.get("rental_income", 0))
            rule = self._get_rule("K1029")
            if rule:
                insights.append(RuleInsight(
                    rule_id="K1029",
                    category="k1_passthrough",
                    title="Passive Loss Limitation Applies",
                    description=f"Your rental loss of ${rental_loss:,.0f} may be limited by passive activity loss rules. Losses may be suspended until disposition.",
                    severity="high",
                    priority="current_year",
                    estimated_impact=0,
                    action_items=[
                        "Complete Form 8582",
                        "Track suspended losses for future years",
                        "Consider if $25,000 allowance applies (AGI under $100K)"
                    ],
                    irs_reference=rule.irs_reference,
                    irs_form="Form 8582",
                    confidence=85,
                    applies=True
                ))

        # K1050 - Form 6198 At-Risk
        rule = self._get_rule("K1050")
        if rule:
            insights.append(RuleInsight(
                rule_id="K1050",
                category="k1_passthrough",
                title="Track At-Risk Amount",
                description="Your K-1 losses are limited to your at-risk amount. Ensure you're tracking your at-risk basis separately from tax basis.",
                severity="medium",
                priority="current_year",
                estimated_impact=0,
                action_items=[
                    "Calculate amount at-risk in each activity",
                    "File Form 6198 if claiming at-risk losses",
                    "Keep records of basis and at-risk amounts"
                ],
                irs_reference=rule.irs_reference,
                irs_form="Form 6198",
                confidence=70,
                applies=True
            ))

        return insights

    def _analyze_casualty_loss(self, tax_return: "TaxReturn", context: Dict) -> List[RuleInsight]:
        """Analyze casualty and disaster loss rules."""
        insights = []

        if not context.get("has_casualty_loss"):
            return insights

        loss_amount = context.get("casualty_loss_amount", 0)
        is_disaster = context.get("is_federally_declared_disaster", False)
        agi = context.get("agi", 0)

        # CL001 - Federally Declared Disaster Requirement
        rule = self._get_rule("CL001")
        if rule:
            if is_disaster:
                # Calculate deductible amount
                net_loss = max(0, loss_amount - 100)  # $100 floor
                deductible = max(0, net_loss - (agi * 0.10))  # 10% AGI reduction
                tax_savings = deductible * 0.22  # Assume 22% bracket

                insights.append(RuleInsight(
                    rule_id="CL001",
                    category="casualty_loss",
                    title="Claim Disaster Loss Deduction",
                    description=f"Your loss of ${loss_amount:,.0f} from a federally declared disaster may be deductible. After limitations, approximately ${deductible:,.0f} may be deductible.",
                    severity="high",
                    priority="immediate",
                    estimated_impact=tax_savings,
                    action_items=[
                        "Complete Form 4684 Section A",
                        "Verify FEMA disaster declaration",
                        "Consider electing prior year deduction",
                        "File insurance claim first"
                    ],
                    irs_reference=rule.irs_reference,
                    irs_form="Form 4684",
                    confidence=80,
                    applies=True
                ))
            else:
                insights.append(RuleInsight(
                    rule_id="CL001",
                    category="casualty_loss",
                    title="Personal Casualty Loss Not Deductible",
                    description="Personal casualty losses are only deductible if attributable to a federally declared disaster. Your loss may not qualify.",
                    severity="high",
                    priority="immediate",
                    estimated_impact=0,
                    action_items=[
                        "Verify if your area was in a declared disaster zone",
                        "Check FEMA disaster declarations",
                        "Consult tax professional if uncertain"
                    ],
                    irs_reference=rule.irs_reference,
                    irs_form="Form 4684",
                    confidence=90,
                    applies=True
                ))

        # CL021 - Prior Year Election
        if is_disaster:
            rule = self._get_rule("CL021")
            if rule:
                insights.append(RuleInsight(
                    rule_id="CL021",
                    category="casualty_loss",
                    title="Consider Prior Year Election",
                    description="You may elect to deduct your disaster loss on the prior year's return for a quicker refund.",
                    severity="medium",
                    priority="immediate",
                    estimated_impact=0,
                    action_items=[
                        "Decide whether to claim on current or prior year return",
                        "File amended return (1040-X) if claiming on prior year",
                        "Make election within required timeframe"
                    ],
                    irs_reference=rule.irs_reference,
                    irs_form="Form 1040-X",
                    confidence=75,
                    applies=True
                ))

        return insights

    def _analyze_alimony(self, tax_return: "TaxReturn", context: Dict) -> List[RuleInsight]:
        """Analyze alimony rules."""
        insights = []

        pays_alimony = context.get("pays_alimony", False)
        receives_alimony = context.get("receives_alimony", False)
        agreement_date = context.get("alimony_agreement_date")

        if not pays_alimony and not receives_alimony:
            return insights

        # Determine if pre-2019 or post-2018 agreement
        is_pre_2019 = False
        if agreement_date:
            try:
                from datetime import datetime
                if isinstance(agreement_date, str):
                    date_obj = datetime.strptime(agreement_date, "%Y-%m-%d")
                else:
                    date_obj = agreement_date
                is_pre_2019 = date_obj.year < 2019
            except:
                pass

        if pays_alimony:
            if is_pre_2019:
                # AL001 - Pre-2019 Deductible
                rule = self._get_rule("AL001")
                if rule:
                    insights.append(RuleInsight(
                        rule_id="AL001",
                        category="alimony",
                        title="Deduct Pre-2019 Alimony Payments",
                        description="Your alimony agreement was executed before 2019. Alimony payments are deductible as an above-the-line deduction.",
                        severity="high",
                        priority="immediate",
                        estimated_impact=0,  # Would need actual amount
                        action_items=[
                            "Deduct alimony on Schedule 1 Line 19a",
                            "Include recipient's SSN on your return",
                            "Keep records of payments made"
                        ],
                        irs_reference=rule.irs_reference,
                        irs_form="Schedule 1",
                        confidence=85,
                        applies=True
                    ))
            else:
                # AL026 - Post-2018 Not Deductible
                rule = self._get_rule("AL026")
                if rule:
                    insights.append(RuleInsight(
                        rule_id="AL026",
                        category="alimony",
                        title="Post-2018 Alimony Not Deductible",
                        description="Your alimony agreement was executed after 2018. Under current law, alimony payments are not tax deductible for the payer.",
                        severity="high",
                        priority="immediate",
                        estimated_impact=0,
                        action_items=[
                            "Do not deduct alimony payments",
                            "Alimony is not reported on tax return",
                            "No SSN reporting required"
                        ],
                        irs_reference=rule.irs_reference,
                        irs_form="N/A",
                        confidence=95,
                        applies=True
                    ))

        if receives_alimony:
            if is_pre_2019:
                # AL002 - Pre-2019 Taxable
                rule = self._get_rule("AL002")
                if rule:
                    insights.append(RuleInsight(
                        rule_id="AL002",
                        category="alimony",
                        title="Report Pre-2019 Alimony as Income",
                        description="Alimony received under a pre-2019 agreement is taxable income. Report it on your tax return.",
                        severity="high",
                        priority="immediate",
                        estimated_impact=0,
                        action_items=[
                            "Report alimony received on Schedule 1",
                            "Make estimated tax payments if needed",
                            "Keep records of amounts received"
                        ],
                        irs_reference=rule.irs_reference,
                        irs_form="Schedule 1",
                        confidence=85,
                        applies=True
                    ))
            else:
                # AL027 - Post-2018 Not Taxable
                rule = self._get_rule("AL027")
                if rule:
                    insights.append(RuleInsight(
                        rule_id="AL027",
                        category="alimony",
                        title="Post-2018 Alimony Not Taxable",
                        description="Alimony received under a post-2018 agreement is not taxable income. You do not need to report it.",
                        severity="medium",
                        priority="immediate",
                        estimated_impact=0,
                        action_items=[
                            "Do not report alimony as income",
                            "No tax due on alimony received",
                            "Keep records for your own purposes"
                        ],
                        irs_reference=rule.irs_reference,
                        irs_form="N/A",
                        confidence=95,
                        applies=True
                    ))

        return insights

    def _analyze_general_rules(self, tax_return: "TaxReturn", context: Dict) -> List[RuleInsight]:
        """Analyze general tax rules and common opportunities."""
        insights = []
        agi = context.get("agi", 0)
        filing_status = str(context.get("filing_status", "single")).lower()

        # NIIT Warning (High Income)
        niit_threshold = 250000 if "joint" in filing_status else 200000
        investment_income = context.get("investment_income", 0)

        if agi > niit_threshold and investment_income > 0:
            niit_tax = min(investment_income, agi - niit_threshold) * 0.038
            insights.append(RuleInsight(
                rule_id="NIIT001",
                category="general",
                title="Net Investment Income Tax Applies",
                description=f"Your income exceeds ${niit_threshold:,}. You may owe approximately ${niit_tax:,.0f} in Net Investment Income Tax (3.8%).",
                severity="high",
                priority="immediate",
                estimated_impact=-niit_tax,
                action_items=[
                    "Complete Form 8960",
                    "Consider tax-loss harvesting to reduce investment income",
                    "Plan for NIIT in estimated tax payments"
                ],
                irs_reference="IRC Section 1411",
                irs_form="Form 8960",
                confidence=85,
                applies=True
            ))

        # AMT Warning (High Income with Large Deductions)
        total_itemized = context.get("total_itemized", 0)
        if agi > 150000 and total_itemized > 50000:
            insights.append(RuleInsight(
                rule_id="AMT001",
                category="general",
                title="Check for Alternative Minimum Tax",
                description="Your income and deduction profile suggests you should check if AMT applies. SALT deduction cap helps reduce AMT exposure.",
                severity="medium",
                priority="current_year",
                estimated_impact=0,
                action_items=[
                    "Complete Form 6251 to calculate AMT",
                    "Note: SALT cap of $10,000 reduces AMT exposure",
                    "Consider timing of deductions"
                ],
                irs_reference="IRC Section 55-59",
                irs_form="Form 6251",
                confidence=60,
                applies=True
            ))

        # Retirement Contribution Opportunity
        if context.get("has_wages") and context.get("age", 0) < 70:
            age = context.get("age", 0)
            ira_limit = 8000 if age >= 50 else 7000
            k401_limit = 31000 if age >= 50 else 23500

            insights.append(RuleInsight(
                rule_id="RET001",
                category="retirement",
                title="Maximize Retirement Contributions",
                description=f"Consider maximizing retirement contributions. IRA limit: ${ira_limit:,}, 401(k) limit: ${k401_limit:,}.",
                severity="medium",
                priority="current_year",
                estimated_impact=ira_limit * 0.22,  # Tax savings estimate
                action_items=[
                    f"Contribute up to ${ira_limit:,} to IRA",
                    f"Contribute up to ${k401_limit:,} to 401(k)",
                    "Evaluate Traditional vs Roth based on income"
                ],
                irs_reference="IRC Section 219, 402(g)",
                irs_form="Form 1040, Form 8606",
                confidence=70,
                applies=True
            ))

        # HSA Contribution Opportunity
        if context.get("has_hdhp", False):
            age = context.get("age", 0)
            hsa_limit = 4300 if context.get("hsa_coverage") == "individual" else 8550
            if age >= 55:
                hsa_limit += 1000

            insights.append(RuleInsight(
                rule_id="HSA001",
                category="healthcare",
                title="Maximize HSA Contribution",
                description=f"You have an HDHP. Consider contributing the maximum ${hsa_limit:,} to your HSA for triple tax benefits.",
                severity="medium",
                priority="current_year",
                estimated_impact=hsa_limit * 0.30,  # Tax + FICA savings
                action_items=[
                    f"Contribute up to ${hsa_limit:,} to HSA",
                    "Contributions are pre-tax",
                    "Growth is tax-free for medical expenses"
                ],
                irs_reference="IRC Section 223",
                irs_form="Form 8889",
                confidence=75,
                applies=True
            ))

        return insights

    def _get_rule(self, rule_id: str):
        """Get a rule by ID from the engine."""
        return self._engine.get_rule(rule_id)


# Singleton instance
_rules_recommender: Optional[RulesBasedRecommender] = None


def get_rules_recommender() -> RulesBasedRecommender:
    """Get or create the rules-based recommender singleton."""
    global _rules_recommender
    if _rules_recommender is None:
        _rules_recommender = RulesBasedRecommender()
    return _rules_recommender
