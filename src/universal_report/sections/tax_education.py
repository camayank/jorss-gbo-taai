"""
Tax Education Section - Educational content explaining tax strategies.

Provides educational value by explaining:
- How each strategy works
- IRS rules and limits
- Common mistakes to avoid
- Step-by-step implementation guides
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from universal_report.data_collector import NormalizedReportData, Recommendation
    from universal_report.branding.theme_manager import BrandTheme


@dataclass
class TaxStrategy:
    """Detailed tax strategy with educational content."""
    id: str
    category: str
    title: str
    short_description: str
    detailed_explanation: str
    how_it_works: str
    irs_rules: List[str]
    eligibility: List[str]
    limitations: List[str]
    implementation_steps: List[str]
    common_mistakes: List[str]
    estimated_savings_formula: str
    irs_references: List[str]
    deadline: Optional[str] = None
    pro_tip: Optional[str] = None


# Tax Strategy Knowledge Base
TAX_STRATEGY_KNOWLEDGE_BASE: Dict[str, TaxStrategy] = {
    "maximize_401k": TaxStrategy(
        id="maximize_401k",
        category="Retirement",
        title="Maximize 401(k) Contributions",
        short_description="Reduce taxable income by maximizing pre-tax retirement contributions.",
        detailed_explanation="""
Contributing to a traditional 401(k) reduces your taxable income dollar-for-dollar,
potentially saving you thousands in federal and state taxes. The money grows tax-deferred
until retirement, allowing compound growth without annual tax drag.
""",
        how_it_works="""
When you contribute to a traditional 401(k), the money comes out of your paycheck
BEFORE federal and state income taxes are calculated. This means if you're in the
24% federal bracket and contribute $20,000, you immediately save $4,800 in federal
taxes alone (plus state tax savings).
""",
        irs_rules=[
            "2025 contribution limit: $23,500 (under age 50)",
            "2025 catch-up contribution: Additional $7,500 (age 50+)",
            "Total limit including employer match: $70,000",
            "Required Minimum Distributions (RMDs) start at age 73",
        ],
        eligibility=[
            "Must be employed by a company offering a 401(k) plan",
            "No income limits for traditional 401(k) contributions",
            "Can contribute regardless of participation in IRA",
        ],
        limitations=[
            "Subject to early withdrawal penalty (10%) before age 59½",
            "Required to start withdrawals at age 73 (RMDs)",
            "Withdrawals taxed as ordinary income in retirement",
            "Limited investment options compared to IRA",
        ],
        implementation_steps=[
            "Log into your employer's benefits portal",
            "Increase your contribution percentage",
            "Consider front-loading contributions if cash flow allows",
            "Review and update beneficiary designations",
            "Set calendar reminders to review contribution levels annually",
        ],
        common_mistakes=[
            "Not contributing enough to get the full employer match (free money!)",
            "Stopping contributions during market downturns",
            "Not increasing contributions when you get a raise",
            "Forgetting to roll over 401(k) when changing jobs",
        ],
        estimated_savings_formula="Contribution × Marginal Tax Rate",
        irs_references=["IRC Section 401(k)", "IRS Publication 560"],
        deadline="December 31 for employee contributions",
        pro_tip="Increase your contribution by 1% every time you get a raise - you won't miss it!",
    ),
    "hsa_triple_tax": TaxStrategy(
        id="hsa_triple_tax",
        category="Healthcare",
        title="HSA Triple Tax Advantage",
        short_description="The only account with triple tax benefits: deductible contributions, tax-free growth, and tax-free qualified withdrawals.",
        detailed_explanation="""
A Health Savings Account (HSA) is the most tax-advantaged account available. Contributions
are tax-deductible, growth is tax-free, and withdrawals for qualified medical expenses are
tax-free. After age 65, you can withdraw for any purpose (taxed as income, like a 401k).
""",
        how_it_works="""
1. DEDUCTION: Contributions reduce your taxable income (like a 401k)
2. GROWTH: Investments grow tax-free (like a Roth)
3. WITHDRAWALS: Tax-free for qualified medical expenses (unlike both!)

You can invest HSA funds and let them grow for decades, then use for medical expenses
in retirement when healthcare costs are typically highest.
""",
        irs_rules=[
            "2025 contribution limit: $4,300 (individual) / $8,550 (family)",
            "Catch-up contribution: Additional $1,000 (age 55+)",
            "Must have High Deductible Health Plan (HDHP)",
            "2025 HDHP minimum deductible: $1,650 (individual) / $3,300 (family)",
        ],
        eligibility=[
            "Enrolled in a qualified High Deductible Health Plan (HDHP)",
            "Not enrolled in Medicare",
            "Not claimed as a dependent on someone else's tax return",
            "No other health coverage (with limited exceptions)",
        ],
        limitations=[
            "Must have HDHP - may not be ideal for those with high medical needs",
            "20% penalty + income tax on non-qualified withdrawals before 65",
            "Can't contribute once enrolled in Medicare (but can still use funds)",
        ],
        implementation_steps=[
            "Enroll in a qualifying HDHP during open enrollment",
            "Open an HSA account (employer-sponsored or independent)",
            "Maximize contributions ($8,550 family in 2025)",
            "Invest HSA funds in low-cost index funds",
            "Pay current medical expenses out-of-pocket and let HSA grow",
            "Keep all medical receipts - you can reimburse yourself years later",
        ],
        common_mistakes=[
            "Using HSA as a spending account instead of investment account",
            "Not investing HSA funds (leaving them in cash)",
            "Contributing when not in a qualifying HDHP",
            "Forgetting to save receipts for future reimbursement",
        ],
        estimated_savings_formula="Contribution × (Federal Rate + State Rate + FICA Rate)",
        irs_references=["IRC Section 223", "IRS Publication 969"],
        deadline="April 15 of following year (tax filing deadline)",
        pro_tip="Keep receipts for ALL medical expenses. You can reimburse yourself from your HSA years later, tax-free, while your investments continue to grow!",
    ),
    "backdoor_roth": TaxStrategy(
        id="backdoor_roth",
        category="Retirement",
        title="Backdoor Roth IRA Conversion",
        short_description="High earners can legally contribute to a Roth IRA through a backdoor strategy.",
        detailed_explanation="""
If your income is too high to contribute directly to a Roth IRA, you can use the
"backdoor" strategy: contribute to a non-deductible traditional IRA, then immediately
convert it to a Roth. This is completely legal and explicitly allowed by the IRS.
""",
        how_it_works="""
1. Contribute to a non-deductible Traditional IRA ($7,000 in 2025)
2. Wait a short period (1-2 days minimum)
3. Convert the Traditional IRA to a Roth IRA
4. Report the conversion on Form 8606

The conversion is tax-free if you have no pre-tax IRA balances (important: this
includes SEP-IRAs and SIMPLE IRAs due to the "pro-rata rule").
""",
        irs_rules=[
            "2025 IRA contribution limit: $7,000 (under 50) / $8,000 (50+)",
            "Roth IRA income limits don't apply to conversions",
            "Pro-rata rule applies if you have pre-tax IRA balances",
            "Must report on Form 8606",
        ],
        eligibility=[
            "Anyone with earned income can do this",
            "Particularly valuable for high earners above Roth income limits",
            "Best for those with no existing pre-tax IRA balances",
        ],
        limitations=[
            "Pro-rata rule complicates if you have traditional IRA balances",
            "Requires annual action - not automatic",
            "Small amount of earnings between contribution and conversion may be taxed",
        ],
        implementation_steps=[
            "Check if you have any existing traditional IRA balances",
            "If you have balances, consider rolling them into employer 401(k)",
            "Open a Traditional IRA (if you don't have one)",
            "Make a non-deductible contribution ($7,000 in 2025)",
            "Wait 1-2 days (or your broker's required period)",
            "Request conversion to Roth IRA",
            "File Form 8606 with your tax return",
        ],
        common_mistakes=[
            "Forgetting about existing traditional IRA balances (pro-rata rule)",
            "Not filing Form 8606 (required even though conversion may be tax-free)",
            "Converting too quickly (some brokers require waiting periods)",
            "Forgetting to repeat the process each year",
        ],
        estimated_savings_formula="Future tax-free growth on $7,000/year for remaining working years",
        irs_references=["IRC Section 408A", "IRS Publication 590-A", "IRS Publication 590-B"],
        deadline="April 15 for prior year contribution, but convert immediately",
        pro_tip="Roll any existing traditional IRA balances into your employer 401(k) BEFORE doing the backdoor Roth to avoid the pro-rata rule!",
    ),
    "qbi_deduction": TaxStrategy(
        id="qbi_deduction",
        category="Business",
        title="Qualified Business Income (QBI) Deduction",
        short_description="Self-employed individuals can deduct up to 20% of qualified business income.",
        detailed_explanation="""
Section 199A allows a deduction of up to 20% of qualified business income from
pass-through entities (sole proprietorships, partnerships, S-corps, LLCs). This
effectively reduces the tax rate on business income by 20%.
""",
        how_it_works="""
If you have $100,000 in qualified business income and qualify for the full deduction,
you can deduct $20,000 from your taxable income. If you're in the 24% bracket, that's
$4,800 in tax savings - just for having business income!

The deduction is calculated as the LESSER of:
1. 20% of QBI, OR
2. 20% of taxable income (before QBI deduction)
""",
        irs_rules=[
            "Maximum deduction: 20% of qualified business income",
            "Phase-out begins at $191,950 (single) / $383,900 (MFJ) in 2025",
            "Specified Service Trades or Businesses (SSTB) have additional limits",
            "W-2 wage and capital limitations apply above threshold",
        ],
        eligibility=[
            "Sole proprietors (Schedule C income)",
            "Partners in partnerships",
            "S-corporation shareholders",
            "LLC members",
            "Rental income (in most cases)",
        ],
        limitations=[
            "SSTBs (law, health, consulting, etc.) phase out above threshold",
            "W-2 wage limitation: 50% of W-2 wages OR 25% wages + 2.5% of property",
            "Cannot exceed 20% of taxable income",
            "Expires after 2025 unless extended by Congress",
        ],
        implementation_steps=[
            "Calculate your qualified business income",
            "Determine if you're below the income threshold",
            "If SSTB, check if you qualify for partial deduction",
            "If above threshold, calculate W-2 wage limitation",
            "Report on Form 8995 or 8995-A",
        ],
        common_mistakes=[
            "Not realizing rental income often qualifies for QBI",
            "Misclassifying business as SSTB when it's not",
            "Not paying yourself W-2 wages from S-corp (affects limitation)",
            "Forgetting that QBI deduction expires after 2025",
        ],
        estimated_savings_formula="QBI × 20% × Marginal Tax Rate",
        irs_references=["IRC Section 199A", "IRS Publication 535", "Form 8995"],
        deadline="Filed with annual tax return",
        pro_tip="If you're above the threshold, paying W-2 wages from your S-corp increases your QBI deduction limit!",
    ),
    "charitable_bunching": TaxStrategy(
        id="charitable_bunching",
        category="Deductions",
        title="Charitable Contribution Bunching",
        short_description="Bunch multiple years of donations into one year to exceed the standard deduction.",
        detailed_explanation="""
With the higher standard deduction ($15,000 single / $30,000 MFJ in 2025), many taxpayers
can no longer itemize. "Bunching" means concentrating 2-3 years of charitable giving into
one year to exceed the standard deduction, then taking the standard deduction in off years.
""",
        how_it_works="""
Example: You normally give $8,000/year to charity. With $12,000 in other itemized
deductions, your total ($20,000) is below the $30,000 standard deduction (MFJ).

Instead: Give $24,000 every third year (3 years of giving). Combined with other
deductions ($12,000), you can itemize $36,000 - saving $6,000 × your tax rate!
""",
        irs_rules=[
            "Charitable deduction limit: 60% of AGI for cash to public charities",
            "30% limit for appreciated assets",
            "20% limit for certain private foundations",
            "5-year carryforward for excess contributions",
            "Donor-advised funds allow immediate deduction with future grants",
        ],
        eligibility=[
            "Anyone who itemizes or could itemize with bunching",
            "Particularly valuable if close to standard deduction threshold",
            "Can use donor-advised fund for flexibility",
        ],
        limitations=[
            "Requires advance planning",
            "AGI limits on charitable deductions",
            "Must have cash flow to bunch donations",
        ],
        implementation_steps=[
            "Calculate your current itemized deductions",
            "Determine how much you'd need to exceed standard deduction",
            "Open a donor-advised fund (DAF) at Fidelity, Schwab, or Vanguard",
            "Contribute 2-3 years of charitable giving to the DAF",
            "Recommend grants to charities over time",
            "Take standard deduction in non-bunching years",
        ],
        common_mistakes=[
            "Not planning far enough ahead",
            "Forgetting to recommend grants from donor-advised fund",
            "Contributing appreciated assets that could get stepped-up basis",
            "Not considering qualified charitable distributions (QCDs) if over 70½",
        ],
        estimated_savings_formula="(Bunched Amount - Standard Deduction) × Tax Rate",
        irs_references=["IRC Section 170", "IRS Publication 526"],
        deadline="December 31 for current year deduction",
        pro_tip="Use a donor-advised fund to get the immediate tax deduction while taking time to decide which charities to support!",
    ),
    "tax_loss_harvesting": TaxStrategy(
        id="tax_loss_harvesting",
        category="Investments",
        title="Tax-Loss Harvesting",
        short_description="Sell investments at a loss to offset gains and reduce taxes.",
        detailed_explanation="""
Tax-loss harvesting involves selling investments that have declined in value to realize
a capital loss. These losses can offset capital gains and up to $3,000 of ordinary income
per year. You can immediately buy a similar (but not "substantially identical") investment
to maintain your market exposure.
""",
        how_it_works="""
1. Identify investments trading below your cost basis
2. Sell to realize the loss
3. Use losses to offset: first capital gains, then up to $3,000 ordinary income
4. Buy a similar investment to maintain exposure (avoid wash sale)
5. Unused losses carry forward indefinitely
""",
        irs_rules=[
            "Losses first offset gains of the same type (short-term vs long-term)",
            "Net losses can offset up to $3,000 of ordinary income per year",
            "Excess losses carry forward to future years (indefinitely)",
            "Wash sale rule: Can't buy substantially identical security within 30 days",
        ],
        eligibility=[
            "Anyone with taxable investment accounts",
            "Most valuable for those with significant capital gains",
            "Not applicable to tax-advantaged accounts (IRA, 401k)",
        ],
        limitations=[
            "Wash sale rule prevents buying back same security for 30 days",
            "$3,000 limit on offsetting ordinary income",
            "Can't use losses in tax-advantaged accounts",
        ],
        implementation_steps=[
            "Review portfolio for positions with unrealized losses",
            "Check if you have realized gains to offset",
            "Sell losing positions before year-end",
            "Wait 31 days OR buy a similar (not identical) investment immediately",
            "Track cost basis carefully for future sales",
            "Consider automated tax-loss harvesting services",
        ],
        common_mistakes=[
            "Triggering wash sale by buying back within 30 days",
            "Buying substantially identical security in IRA (still triggers wash sale!)",
            "Not considering future gains when harvesting losses",
            "Selling only to harvest loss without maintaining investment strategy",
        ],
        estimated_savings_formula="(Losses Offsetting Gains × Cap Gains Rate) + (Up to $3,000 × Ordinary Rate)",
        irs_references=["IRC Section 1211", "IRC Section 1091 (wash sale)", "IRS Publication 550"],
        deadline="December 31 for current year (but review quarterly)",
        pro_tip="Set up automatic tax-loss harvesting through robo-advisors like Betterment or Wealthfront for hands-off optimization!",
    ),
}


class TaxEducationRenderer:
    """Render educational tax content."""

    def __init__(
        self,
        data: "NormalizedReportData",
        theme: Optional["BrandTheme"] = None,
    ):
        self.data = data
        self.theme = theme
        self.knowledge_base = TAX_STRATEGY_KNOWLEDGE_BASE

    def render_strategy_deep_dive(self, strategy_id: str) -> str:
        """Render detailed educational content for a specific strategy."""
        if strategy_id not in self.knowledge_base:
            return ""

        strategy = self.knowledge_base[strategy_id]
        primary = self.theme.primary_color if self.theme else "#2563eb"
        accent = self.theme.accent_color if self.theme else "#10b981"

        # Build sections
        rules_html = "".join([f"<li>{rule}</li>" for rule in strategy.irs_rules])
        eligibility_html = "".join([f"<li>{item}</li>" for item in strategy.eligibility])
        limitations_html = "".join([f"<li>{item}</li>" for item in strategy.limitations])
        steps_html = "".join([
            f"<li><strong>Step {i+1}:</strong> {step}</li>"
            for i, step in enumerate(strategy.implementation_steps)
        ])
        mistakes_html = "".join([f"<li>❌ {mistake}</li>" for mistake in strategy.common_mistakes])
        refs_html = "".join([f"<li>{ref}</li>" for ref in strategy.irs_references])

        pro_tip_html = ""
        if strategy.pro_tip:
            pro_tip_html = f'''
<div style="
  background: linear-gradient(135deg, {accent}10 0%, {accent}20 100%);
  border-left: 4px solid {accent};
  padding: 16px 20px;
  margin: 20px 0;
  border-radius: 0 8px 8px 0;
">
  <strong style="color: {accent};">💡 Pro Tip:</strong>
  <p style="margin: 8px 0 0 0; color: #374151;">{strategy.pro_tip}</p>
</div>
'''

        return f'''
<div class="strategy-deep-dive" style="
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  padding: 32px;
  margin: 24px 0;
">
  <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 24px;">
    <span style="
      background: {primary}15;
      color: {primary};
      padding: 4px 12px;
      border-radius: 12px;
      font-size: 0.75rem;
      font-weight: 600;
    ">{strategy.category}</span>
    <h3 style="margin: 0; font-size: 1.5rem; color: {primary};">{strategy.title}</h3>
  </div>

  <p style="font-size: 1.1rem; color: #374151; line-height: 1.7; margin-bottom: 24px;">
    {strategy.short_description}
  </p>

  <!-- How It Works -->
  <div style="margin-bottom: 24px;">
    <h4 style="color: {primary}; margin-bottom: 12px;">📘 How It Works</h4>
    <div style="background: #f9fafb; padding: 16px; border-radius: 8px; white-space: pre-line; line-height: 1.6;">
      {strategy.how_it_works.strip()}
    </div>
  </div>

  <!-- IRS Rules -->
  <div style="margin-bottom: 24px;">
    <h4 style="color: {primary}; margin-bottom: 12px;">📋 IRS Rules & Limits (2025)</h4>
    <ul style="padding-left: 24px; line-height: 1.8;">{rules_html}</ul>
  </div>

  <!-- Eligibility -->
  <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px;">
    <div>
      <h4 style="color: {accent}; margin-bottom: 12px;">✓ Who Can Use This</h4>
      <ul style="padding-left: 24px; line-height: 1.8;">{eligibility_html}</ul>
    </div>
    <div>
      <h4 style="color: #f59e0b; margin-bottom: 12px;">⚠️ Limitations</h4>
      <ul style="padding-left: 24px; line-height: 1.8;">{limitations_html}</ul>
    </div>
  </div>

  <!-- Implementation Steps -->
  <div style="margin-bottom: 24px;">
    <h4 style="color: {primary}; margin-bottom: 12px;">🎯 Implementation Steps</h4>
    <ol style="padding-left: 24px; line-height: 2;">{steps_html}</ol>
  </div>

  <!-- Common Mistakes -->
  <div style="
    background: #fef2f2;
    padding: 20px;
    border-radius: 8px;
    margin-bottom: 24px;
  ">
    <h4 style="color: #dc2626; margin: 0 0 12px 0;">🚫 Common Mistakes to Avoid</h4>
    <ul style="padding-left: 24px; line-height: 1.8; margin: 0; list-style: none;">{mistakes_html}</ul>
  </div>

  {pro_tip_html}

  <!-- Savings Formula & References -->
  <div style="
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding-top: 20px;
    border-top: 1px solid #e5e7eb;
  ">
    <div>
      <div style="font-size: 0.75rem; color: #6b7280; text-transform: uppercase;">Savings Formula</div>
      <code style="
        display: inline-block;
        margin-top: 4px;
        padding: 4px 12px;
        background: #f3f4f6;
        border-radius: 4px;
        font-size: 0.875rem;
      ">{strategy.estimated_savings_formula}</code>
    </div>
    <div style="text-align: right;">
      <div style="font-size: 0.75rem; color: #6b7280; text-transform: uppercase;">IRS References</div>
      <ul style="list-style: none; padding: 0; margin: 4px 0 0 0; font-size: 0.875rem; color: #6b7280;">{refs_html}</ul>
    </div>
  </div>

  {f'<div style="margin-top: 16px; text-align: center;"><span style="background: #fef3c7; color: #92400e; padding: 4px 12px; border-radius: 12px; font-size: 0.75rem;">📅 Deadline: {strategy.deadline}</span></div>' if strategy.deadline else ''}
</div>
'''

    def render_education_section(self, relevant_strategies: List[str] = None) -> str:
        """Render full education section with multiple strategies."""
        primary = self.theme.primary_color if self.theme else "#2563eb"

        # Determine which strategies to include
        if relevant_strategies:
            strategies_to_show = [s for s in relevant_strategies if s in self.knowledge_base]
        else:
            # Default to showing strategies relevant to the user's situation
            strategies_to_show = self._get_relevant_strategies()

        if not strategies_to_show:
            return ""

        strategies_html = "".join([
            self.render_strategy_deep_dive(s) for s in strategies_to_show[:3]  # Limit to top 3
        ])

        return f'''
<section class="tax-education">
  <h2 style="color: {primary}; border-bottom: 2px solid {primary}; padding-bottom: 8px; margin-bottom: 24px;">
    📚 Understanding Your Tax Strategies
  </h2>

  <p style="font-size: 1.1rem; color: #374151; margin-bottom: 32px;">
    Below are detailed explanations of the tax strategies most relevant to your situation,
    including IRS rules, step-by-step implementation guides, and common mistakes to avoid.
  </p>

  {strategies_html}
</section>
'''

    def _get_relevant_strategies(self) -> List[str]:
        """Determine which strategies are most relevant based on user data."""
        relevant = []

        # Check for retirement-related
        if self.data.income_items:
            has_w2 = any(i.category == "Employment" for i in self.data.income_items)
            has_business = any(i.category in ("Self-Employment", "Business") for i in self.data.income_items)

            if has_w2:
                relevant.append("maximize_401k")
                relevant.append("hsa_triple_tax")

            if has_business:
                relevant.append("qbi_deduction")

        # Check for investment income
        if any(i.category in ("Investments", "Capital Gains") for i in self.data.income_items):
            relevant.append("tax_loss_harvesting")

        # Check for high income (backdoor Roth)
        if self.data.gross_income and float(self.data.gross_income) > 150000:
            relevant.append("backdoor_roth")

        # Check for charitable giving potential
        if self.data.deduction_items:
            has_charitable = any("charitable" in d.description.lower() for d in self.data.deduction_items)
            if has_charitable:
                relevant.append("charitable_bunching")

        return relevant if relevant else ["maximize_401k", "hsa_triple_tax"]  # Default strategies

    def render(self) -> str:
        """Main render method - renders the full education section."""
        return self.render_education_section()
