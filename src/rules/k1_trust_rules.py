"""K-1, Trust, and Estate Tax Rules.

Comprehensive rules for pass-through entity income reporting.
Based on IRC Sections 701, 1366, 469, 465, and 199A.
Tax Year: 2025

Rules K1001-K1060 covering:
- Schedule K-1 reporting (partnerships and S-corps)
- Passive activity loss limitations
- At-risk limitations
- QBI deduction (Section 199A)
- Trust and estate income
"""

from __future__ import annotations

from .tax_rule_definitions import TaxRule, RuleCategory, RuleSeverity


# =============================================================================
# K-1, TRUST, AND ESTATE RULES (60 rules)
# =============================================================================

K1_TRUST_RULES = [
    # =========================================================================
    # K-1 Reporting (K1001-K1020)
    # =========================================================================
    TaxRule(
        rule_id="K1001",
        name="Schedule K-1 Partnership Form 1065",
        description="Partners receive Schedule K-1 (Form 1065) reporting distributive share of partnership income, deductions, and credits.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 701",
        recommendation="Report all K-1 items on appropriate individual tax forms"
    ),
    TaxRule(
        rule_id="K1002",
        name="Schedule K-1 S-Corp Form 1120-S",
        description="S corporation shareholders receive Schedule K-1 (Form 1120-S) reporting pro-rata share of S corp income and deductions.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1366",
        recommendation="Report S corp K-1 items on Schedule E and other applicable forms"
    ),
    TaxRule(
        rule_id="K1003",
        name="Schedule K-1 Estate/Trust Form 1041",
        description="Beneficiaries receive Schedule K-1 (Form 1041) reporting distributive share of trust or estate income.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 652/662",
        recommendation="Report trust/estate K-1 income on Schedule E"
    ),
    TaxRule(
        rule_id="K1004",
        name="Box 1 Ordinary Business Income",
        description="K-1 Box 1 ordinary business income is reported on Schedule E Part II. May be subject to SE tax for general partners.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="Schedule K-1 Instructions",
        recommendation="Report Box 1 income on Schedule E; check SE tax applicability"
    ),
    TaxRule(
        rule_id="K1005",
        name="Box 2 Net Rental Real Estate Income",
        description="K-1 Box 2 rental real estate income is generally passive unless real estate professional exception applies.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 469",
        recommendation="Report rental income on Schedule E; apply passive activity rules"
    ),
    TaxRule(
        rule_id="K1006",
        name="Box 3 Other Net Rental Income",
        description="K-1 Box 3 other net rental income includes equipment rentals and other rental activities.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Schedule K-1 Instructions",
        recommendation="Report Box 3 rental income on Schedule E"
    ),
    TaxRule(
        rule_id="K1007",
        name="Box 4a Guaranteed Payments for Services",
        description="Guaranteed payments for services are ordinary income to partner regardless of partnership profit. Subject to SE tax.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 707(c)",
        recommendation="Report guaranteed payments as ordinary income subject to SE tax"
    ),
    TaxRule(
        rule_id="K1008",
        name="Box 4b Guaranteed Payments for Capital",
        description="Guaranteed payments for capital are ordinary income but generally not subject to self-employment tax.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 707(c)",
        recommendation="Report Box 4b as ordinary income without SE tax"
    ),
    TaxRule(
        rule_id="K1009",
        name="Box 5 Interest Income",
        description="K-1 interest income flows through to partner's return. Report on Schedule B.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Schedule K-1 Instructions",
        recommendation="Report K-1 interest income on Schedule B"
    ),
    TaxRule(
        rule_id="K1010",
        name="Box 6 Dividends",
        description="K-1 dividend income includes both ordinary and qualified dividends. Report on Schedule B.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Schedule K-1 Instructions",
        recommendation="Report dividends on Schedule B; distinguish qualified vs ordinary"
    ),
    TaxRule(
        rule_id="K1011",
        name="Box 7 Royalties",
        description="K-1 royalty income is reported on Schedule E. Not subject to SE tax unless in trade or business.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Schedule K-1 Instructions",
        recommendation="Report royalties on Schedule E Part I"
    ),
    TaxRule(
        rule_id="K1012",
        name="Box 8 Net Short-Term Capital Gain/Loss",
        description="K-1 short-term capital gains flow through to Schedule D. Holding period determined at entity level.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="Schedule K-1 Instructions",
        recommendation="Report short-term capital gains on Schedule D"
    ),
    TaxRule(
        rule_id="K1013",
        name="Box 9a Net Long-Term Capital Gain/Loss",
        description="K-1 long-term capital gains flow through to Schedule D at preferential tax rates.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="Schedule K-1 Instructions",
        recommendation="Report long-term capital gains on Schedule D"
    ),
    TaxRule(
        rule_id="K1014",
        name="Box 11 Section 179 Deduction",
        description="Section 179 expense deduction passes through to partners/shareholders. Subject to individual limits.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 179",
        recommendation="Apply Section 179 deduction on Form 4562"
    ),
    TaxRule(
        rule_id="K1015",
        name="Box 14 Self-Employment Earnings",
        description="K-1 Box 14 reports self-employment income for calculating SE tax. General partners only.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1402",
        recommendation="Use Box 14 for Schedule SE calculation"
    ),
    TaxRule(
        rule_id="K1016",
        name="Box 15 Credits and Credit Recapture",
        description="K-1 credits flow through to individual return. Each credit type has specific form requirements.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Schedule K-1 Instructions",
        recommendation="Report credits on appropriate individual tax forms"
    ),
    TaxRule(
        rule_id="K1017",
        name="Box 16 Foreign Transactions",
        description="K-1 foreign income and taxes flow through for foreign tax credit calculation.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 901",
        recommendation="Use Box 16 for Form 1116 foreign tax credit"
    ),
    TaxRule(
        rule_id="K1018",
        name="Box 20 Code Z Section 199A QBI",
        description="K-1 Box 20 Code Z provides QBI information for Section 199A deduction calculation.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 199A",
        recommendation="Use Box 20 Code Z for Form 8995/8995-A"
    ),
    TaxRule(
        rule_id="K1019",
        name="K-1 Basis Adjustment",
        description="Partner's basis is adjusted annually by share of income, losses, contributions, and distributions.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 705",
        recommendation="Track outside basis annually for loss limitation"
    ),
    TaxRule(
        rule_id="K1020",
        name="K-1 Late Receipt Issues",
        description="K-1s often arrive late requiring filing extension. Request extension to avoid penalties.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 6081",
        recommendation="File extension if K-1 not received by filing deadline"
    ),

    # =========================================================================
    # Passive Activity Rules (K1021-K1040)
    # =========================================================================
    TaxRule(
        rule_id="K1021",
        name="Passive Activity Definition",
        description="Passive activity is trade/business where taxpayer doesn't materially participate, or any rental activity (with exceptions).",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 469(c)",
        recommendation="Determine material participation for each activity"
    ),
    TaxRule(
        rule_id="K1022",
        name="Material Participation 500 Hour Test",
        description="Material participation if individual participates more than 500 hours during tax year.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 469(h)",
        threshold=500.0,
        recommendation="Track hours to meet 500-hour test"
    ),
    TaxRule(
        rule_id="K1023",
        name="Material Participation Substantially All Test",
        description="Material participation if participation constitutes substantially all participation by all individuals.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.469-5T(a)(2)",
        recommendation="Document if you are sole or primary participant"
    ),
    TaxRule(
        rule_id="K1024",
        name="Material Participation 100 Hour Test",
        description="Material participation if participate 100+ hours and not less than any other individual.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.469-5T(a)(3)",
        threshold=100.0,
        recommendation="Meet 100-hour test if not meeting 500-hour test"
    ),
    TaxRule(
        rule_id="K1025",
        name="Material Participation Significant Activities Test",
        description="Material participation if aggregate participation in all significant activities exceeds 500 hours.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.469-5T(a)(4)",
        recommendation="Aggregate hours across significant participation activities"
    ),
    TaxRule(
        rule_id="K1026",
        name="Material Participation 5 of 10 Years Test",
        description="Material participation if materially participated in any 5 of preceding 10 tax years.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.469-5T(a)(5)",
        recommendation="Review prior year participation history"
    ),
    TaxRule(
        rule_id="K1027",
        name="Material Participation Personal Service Test",
        description="Material participation in personal service activity if materially participated in any 3 prior years.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.469-5T(a)(6)",
        recommendation="Track participation in personal service activities"
    ),
    TaxRule(
        rule_id="K1028",
        name="Material Participation Facts and Circumstances",
        description="Material participation based on all facts and circumstances if participate 100+ hours regularly, continuously, and substantially.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.469-5T(a)(7)",
        threshold=100.0,
        recommendation="Document regular, continuous, substantial participation"
    ),
    TaxRule(
        rule_id="K1029",
        name="Passive Loss Limitation",
        description="Passive activity losses can only offset passive activity income. Excess losses are suspended.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 469(a)",
        recommendation="Track suspended passive losses by activity"
    ),
    TaxRule(
        rule_id="K1030",
        name="$25,000 Rental Real Estate Allowance",
        description="Up to $25,000 of rental real estate losses may offset active income if AGI under $100,000 with active participation.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 469(i)",
        limit=25000.0,
        thresholds_by_status={
            "single": 100000.0,
            "married_joint": 100000.0,
            "married_separate": 50000.0,
            "head_of_household": 100000.0
        },
        recommendation="Claim rental loss allowance if meeting active participation test"
    ),
    TaxRule(
        rule_id="K1031",
        name="Active Participation Standard",
        description="Active participation requires meaningful participation in management decisions. Less stringent than material participation.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 469(i)(6)",
        recommendation="Document involvement in rental property management"
    ),
    TaxRule(
        rule_id="K1032",
        name="$25,000 Allowance Phase-Out",
        description="$25,000 rental loss allowance phases out $1 for every $2 of AGI over $100,000. Fully phased out at $150,000.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 469(i)(3)",
        phase_out_start=100000.0,
        phase_out_end=150000.0,
        recommendation="Calculate allowance reduction based on AGI"
    ),
    TaxRule(
        rule_id="K1033",
        name="Rental Activity Definition",
        description="Rental activity where payments principally for use of tangible property. Generally passive regardless of participation.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 469(j)(8)",
        recommendation="Rental activities are generally passive"
    ),
    TaxRule(
        rule_id="K1034",
        name="Real Estate Professional Exception",
        description="Real estate professionals may treat rentals as non-passive if 750+ hours and more than half of personal services in real estate.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 469(c)(7)",
        threshold=750.0,
        recommendation="Qualify as real estate professional to deduct rental losses"
    ),
    TaxRule(
        rule_id="K1035",
        name="Form 8582 Passive Activity Losses",
        description="Form 8582 required to report passive activity loss limitations and calculate allowable deductions.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="Form 8582 Instructions",
        recommendation="Complete Form 8582 to calculate passive loss limitations"
    ),
    TaxRule(
        rule_id="K1036",
        name="Disposition of Entire Interest",
        description="Suspended passive losses fully deductible when entire interest in activity is disposed of in taxable transaction.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 469(g)",
        recommendation="Release suspended losses upon complete disposition"
    ),
    TaxRule(
        rule_id="K1037",
        name="Grouping of Activities",
        description="Taxpayer may group activities as single activity if constitute appropriate economic unit.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.469-4",
        recommendation="Consider grouping related activities for passive loss purposes"
    ),
    TaxRule(
        rule_id="K1038",
        name="Self-Rental Rule",
        description="Net rental income from property rented to taxpayer's business is recharacterized as non-passive.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.469-2(f)(6)",
        recommendation="Self-rental income is non-passive; cannot offset other passive losses"
    ),
    TaxRule(
        rule_id="K1039",
        name="Closely Held C Corporation Rules",
        description="Closely held C corps can offset passive losses against active business income but not portfolio income.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 469(e)(2)",
        recommendation="Apply special rules for closely held C corporations"
    ),
    TaxRule(
        rule_id="K1040",
        name="Limited Partner Material Participation",
        description="Limited partners can only satisfy material participation through Tests 1, 5, or 6. Cannot use 500-hour test.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="Reg. 1.469-5T(e)",
        recommendation="Limited partners have restricted material participation tests"
    ),

    # =========================================================================
    # At-Risk Rules (K1041-K1050)
    # =========================================================================
    TaxRule(
        rule_id="K1041",
        name="At-Risk Limitation",
        description="Losses from activities are limited to amount taxpayer has at risk in the activity.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 465(a)",
        recommendation="Track at-risk basis separate from tax basis"
    ),
    TaxRule(
        rule_id="K1042",
        name="Amount At Risk Definition",
        description="At-risk amount includes cash contributed, adjusted basis of property, and amounts borrowed for which personally liable.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 465(b)",
        recommendation="Calculate at-risk amount annually"
    ),
    TaxRule(
        rule_id="K1043",
        name="Nonrecourse Debt Not At Risk",
        description="Nonrecourse borrowing generally not included in at-risk amount. Limited exception for qualified nonrecourse real estate financing.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 465(b)(2)",
        recommendation="Exclude nonrecourse debt from at-risk calculation"
    ),
    TaxRule(
        rule_id="K1044",
        name="Qualified Nonrecourse Real Estate Financing",
        description="Qualified nonrecourse financing secured by real property is included in at-risk amount for real estate activities.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 465(b)(6)",
        recommendation="Include qualified real estate financing in at-risk basis"
    ),
    TaxRule(
        rule_id="K1045",
        name="At-Risk Loss Carryforward",
        description="Losses disallowed under at-risk rules carry forward indefinitely and allowed when at-risk increases.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 465(a)(2)",
        recommendation="Track suspended at-risk losses by activity"
    ),
    TaxRule(
        rule_id="K1046",
        name="At-Risk Recapture",
        description="If at-risk amount goes below zero, previously allowed losses may be recaptured as income.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 465(e)",
        recommendation="Monitor at-risk amount to avoid recapture"
    ),
    TaxRule(
        rule_id="K1047",
        name="Related Party Borrowing",
        description="Amounts borrowed from related parties or protected against loss are not at-risk.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 465(b)(3)",
        recommendation="Exclude protected and related-party debt from at-risk"
    ),
    TaxRule(
        rule_id="K1048",
        name="At-Risk Activities Aggregation",
        description="Certain film, farming, oil/gas, and geothermal activities cannot be aggregated for at-risk purposes.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 465(c)(2)",
        recommendation="Apply at-risk limits separately to specified activities"
    ),
    TaxRule(
        rule_id="K1049",
        name="At-Risk vs Basis Comparison",
        description="Both basis and at-risk limitations apply. Losses limited to lesser of basis or at-risk amount.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Sections 704(d) and 465",
        recommendation="Apply both basis and at-risk limitations"
    ),
    TaxRule(
        rule_id="K1050",
        name="Form 6198 Filing Requirement",
        description="Form 6198 required to report at-risk limitations for activities with losses or recapture.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="Form 6198 Instructions",
        recommendation="File Form 6198 to calculate at-risk limitations"
    ),

    # =========================================================================
    # QBI Deduction Section 199A (K1051-K1060)
    # =========================================================================
    TaxRule(
        rule_id="K1051",
        name="QBI Deduction 20 Percent",
        description="Qualified Business Income deduction equals 20% of QBI from pass-through entities and sole proprietorships.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 199A(a)",
        rate=0.20,
        recommendation="Calculate 20% QBI deduction from eligible business income"
    ),
    TaxRule(
        rule_id="K1052",
        name="QBI Taxable Income Limitation",
        description="QBI deduction cannot exceed 20% of taxable income minus net capital gains.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 199A(a)(2)",
        rate=0.20,
        recommendation="Apply taxable income limitation to QBI deduction"
    ),
    TaxRule(
        rule_id="K1053",
        name="QBI W-2 Wage Limitation",
        description="For income above threshold, QBI deduction limited to greater of 50% of W-2 wages or 25% of wages plus 2.5% of UBIA.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 199A(b)(2)",
        thresholds_by_status={
            "single": 197300.0,  # 2025 QBI threshold
            "married_joint": 394600.0,  # 2025 QBI threshold
            "married_separate": 197300.0,  # 2025 QBI threshold
            "head_of_household": 197300.0  # 2025 QBI threshold
        },
        recommendation="Calculate W-2 wage limitation if income above threshold"
    ),
    TaxRule(
        rule_id="K1054",
        name="QBI Threshold Phase-In",
        description="W-2 wage limitation phases in over $50,000 (single) or $100,000 (MFJ) above threshold.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 199A(b)(3)",
        phase_out_start=197300.0,  # 2025 QBI threshold (single)
        phase_out_end=247300.0,  # 2025 QBI phase-out end (single)
        recommendation="Phase in W-2 wage limitation within income range"
    ),
    TaxRule(
        rule_id="K1055",
        name="SSTB Definition",
        description="Specified Service Trade or Business (SSTB) includes health, law, accounting, actuarial, performing arts, consulting, athletics, financial services, and brokerage.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 199A(d)(2)",
        recommendation="Determine if business is SSTB for QBI limitation"
    ),
    TaxRule(
        rule_id="K1056",
        name="SSTB Exclusion Above Threshold",
        description="SSTB income excluded from QBI for taxpayers above threshold. Fully excluded above $241,950 single/$483,900 MFJ.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 199A(d)(3)",
        thresholds_by_status={
            "single": 241950.0,
            "married_joint": 483900.0,
            "married_separate": 241950.0,
            "head_of_household": 241950.0
        },
        recommendation="SSTB income ineligible for QBI above threshold"
    ),
    TaxRule(
        rule_id="K1057",
        name="QBI Loss Carryforward",
        description="Net QBI losses carry forward to reduce QBI in future years. Track by qualified trade or business.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 199A(c)(2)",
        recommendation="Track QBI losses for carryforward"
    ),
    TaxRule(
        rule_id="K1058",
        name="QBI Aggregation Election",
        description="Taxpayer may aggregate trades or businesses meeting requirements for QBI calculation.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.199A-4",
        recommendation="Consider aggregating related businesses for QBI"
    ),
    TaxRule(
        rule_id="K1059",
        name="REIT and PTP Dividends QBI",
        description="REIT dividends and publicly traded partnership income qualify for 20% deduction separately from W-2 limitation.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 199A(b)(1)(B)",
        rate=0.20,
        recommendation="Include REIT dividends and PTP income in QBI calculation"
    ),
    TaxRule(
        rule_id="K1060",
        name="Form 8995 or 8995-A Filing",
        description="Form 8995 (simplified) or 8995-A (standard) required to calculate and claim QBI deduction.",
        category=RuleCategory.K1_TRUST,
        severity=RuleSeverity.HIGH,
        irs_reference="Form 8995 Instructions",
        recommendation="File Form 8995 or 8995-A to claim QBI deduction"
    ),
]
