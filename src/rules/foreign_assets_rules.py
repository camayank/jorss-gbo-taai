"""Foreign Assets Tax Rules.

Comprehensive rules for foreign asset reporting and foreign tax credit.
Based on FBAR requirements (31 USC 5314), FATCA (IRC Section 6038D),
and Foreign Tax Credit (IRC Section 901/904).
Tax Year: 2025

Rules FA001-FA064 covering:
- FBAR filing requirements
- Form 8938 FATCA reporting
- Foreign tax credit calculation and limitations
- Foreign earned income exclusion
- Controlled foreign corporations
"""

from __future__ import annotations

from .tax_rule_definitions import TaxRule, RuleCategory, RuleSeverity


# =============================================================================
# FOREIGN ASSETS RULES (64 rules)
# =============================================================================

FOREIGN_ASSETS_RULES = [
    # =========================================================================
    # FBAR Rules (FA001-FA015)
    # =========================================================================
    TaxRule(
        rule_id="FA001",
        name="FBAR Filing Requirement",
        description="US persons with financial interest in or signature authority over foreign financial accounts must file FBAR if aggregate value exceeds $10,000 at any time during the year.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.CRITICAL,
        irs_reference="31 USC 5314",
        threshold=10000.0,
        recommendation="File FinCEN Form 114 (FBAR) electronically for foreign accounts over $10,000"
    ),
    TaxRule(
        rule_id="FA002",
        name="FBAR Aggregate Threshold",
        description="The $10,000 threshold is based on aggregate maximum value of ALL foreign financial accounts combined, not per account.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.CRITICAL,
        irs_reference="31 CFR 1010.350",
        threshold=10000.0,
        recommendation="Sum all foreign account balances to determine if threshold is met"
    ),
    TaxRule(
        rule_id="FA003",
        name="FBAR Account Types Covered",
        description="FBAR covers bank accounts, securities accounts, brokerage accounts, mutual funds, and other financial accounts held abroad.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="31 CFR 1010.350(c)",
        recommendation="Include all foreign financial account types in FBAR filing"
    ),
    TaxRule(
        rule_id="FA004",
        name="FBAR Signature Authority",
        description="Must file FBAR if you have signature authority over foreign accounts even without financial interest. Common for corporate officers.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="31 CFR 1010.350(f)",
        recommendation="File FBAR for accounts where you have signature authority"
    ),
    TaxRule(
        rule_id="FA005",
        name="FBAR Filing Deadline",
        description="FBAR is due April 15 with automatic extension to October 15. No need to request extension.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="FinCEN Notice 2023-1",
        recommendation="File FBAR by April 15 or use automatic extension to October 15"
    ),
    TaxRule(
        rule_id="FA006",
        name="FBAR Electronic Filing Required",
        description="FBAR must be filed electronically through BSA E-Filing System. Paper filing is not accepted.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="31 CFR 1010.306",
        recommendation="File FBAR electronically at BSA E-Filing website"
    ),
    TaxRule(
        rule_id="FA007",
        name="FBAR Willful vs Non-Willful Penalties",
        description="Non-willful FBAR penalty up to $12,500 per violation. Willful penalty is greater of $100,000 or 50% of account balance.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.CRITICAL,
        irs_reference="31 USC 5321",
        recommendation="File FBAR timely to avoid severe penalties"
    ),
    TaxRule(
        rule_id="FA008",
        name="FBAR Criminal Penalties",
        description="Willful failure to file FBAR may result in criminal penalties including fines up to $500,000 and imprisonment up to 10 years.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.CRITICAL,
        irs_reference="31 USC 5322",
        recommendation="Never willfully fail to file required FBAR"
    ),
    TaxRule(
        rule_id="FA009",
        name="FBAR Joint Account Reporting",
        description="Each person with financial interest in joint account must file separate FBAR for full account value.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="31 CFR 1010.350",
        recommendation="Both joint account holders must file FBAR for full account value"
    ),
    TaxRule(
        rule_id="FA010",
        name="FBAR Reporting Currency Conversion",
        description="Report FBAR amounts in US dollars using Treasury year-end exchange rate.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.MEDIUM,
        irs_reference="31 CFR 1010.306(c)",
        recommendation="Convert foreign currency to USD using Treasury rates for FBAR"
    ),
    TaxRule(
        rule_id="FA011",
        name="FBAR Record Retention",
        description="Must retain FBAR records for 5 years from filing date, including account statements and documentation.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="31 CFR 1010.420",
        recommendation="Keep FBAR supporting records for 5 years"
    ),
    TaxRule(
        rule_id="FA012",
        name="FBAR Delinquent Submission",
        description="Delinquent FBARs can be filed with reasonable cause statement. Streamlined procedures available for certain taxpayers.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="IRS Delinquent FBAR Submission Procedures",
        recommendation="File delinquent FBARs with explanation of reasonable cause"
    ),
    TaxRule(
        rule_id="FA013",
        name="FBAR US Person Definition",
        description="US person for FBAR includes citizens, residents, domestic entities, and trusts or estates under US court jurisdiction.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="31 CFR 1010.350(b)",
        recommendation="Determine if you are a US person for FBAR purposes"
    ),
    TaxRule(
        rule_id="FA014",
        name="FBAR Foreign Pension Exception",
        description="Certain foreign retirement accounts may be exempt from FBAR reporting depending on tax treaty provisions.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.MEDIUM,
        irs_reference="31 CFR 1010.350(c)(4)",
        recommendation="Review treaty provisions for foreign pension FBAR exemption"
    ),
    TaxRule(
        rule_id="FA015",
        name="FBAR Consolidated Reporting",
        description="Parent companies may file consolidated FBAR for certain subsidiary accounts under specific conditions.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.MEDIUM,
        irs_reference="31 CFR 1010.350(g)",
        recommendation="Determine eligibility for consolidated FBAR filing"
    ),

    # =========================================================================
    # Form 8938 FATCA Rules (FA016-FA030)
    # =========================================================================
    TaxRule(
        rule_id="FA016",
        name="Form 8938 Filing Requirement",
        description="US taxpayers with specified foreign financial assets exceeding reporting thresholds must file Form 8938 with tax return.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 6038D",
        recommendation="File Form 8938 with Form 1040 if you exceed FATCA thresholds"
    ),
    TaxRule(
        rule_id="FA017",
        name="Form 8938 Domestic Filing Thresholds Single",
        description="Single filers living in US: $50,000 at year end OR $75,000 at any time during year.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="Reg. 1.6038D-2(a)(1)",
        thresholds_by_status={
            "single": 50000.0,
            "married_separate": 50000.0
        },
        recommendation="File Form 8938 if single with foreign assets over $50,000 at year end"
    ),
    TaxRule(
        rule_id="FA018",
        name="Form 8938 Domestic Filing Thresholds MFJ",
        description="Married filing jointly living in US: $100,000 at year end OR $150,000 at any time during year.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="Reg. 1.6038D-2(a)(2)",
        thresholds_by_status={
            "married_joint": 100000.0
        },
        recommendation="File Form 8938 if MFJ with foreign assets over $100,000 at year end"
    ),
    TaxRule(
        rule_id="FA019",
        name="Form 8938 Foreign Residence Thresholds",
        description="US persons living abroad have higher thresholds: $200,000 (single) or $400,000 (MFJ) at year end.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="Reg. 1.6038D-2(a)(4)",
        thresholds_by_status={
            "single": 200000.0,
            "married_joint": 400000.0
        },
        recommendation="Higher Form 8938 thresholds apply if living abroad"
    ),
    TaxRule(
        rule_id="FA020",
        name="Form 8938 Specified Foreign Financial Assets",
        description="Form 8938 covers financial accounts, stock, securities, financial instruments, contracts, interests in foreign entities.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 6038D(b)",
        recommendation="Report all specified foreign financial assets on Form 8938"
    ),
    TaxRule(
        rule_id="FA021",
        name="Form 8938 vs FBAR Overlap",
        description="Form 8938 and FBAR have different requirements; both may need to be filed. Form 8938 is broader in asset types.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 6038D",
        recommendation="File both Form 8938 and FBAR if thresholds are met for each"
    ),
    TaxRule(
        rule_id="FA022",
        name="Form 8938 Filed with Tax Return",
        description="Form 8938 is filed with annual income tax return, unlike FBAR which is filed separately with FinCEN.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="Reg. 1.6038D-2(a)",
        recommendation="Attach Form 8938 to your Form 1040"
    ),
    TaxRule(
        rule_id="FA023",
        name="Form 8938 Valuation Rules",
        description="Use fair market value in US dollars for all assets. Use year-end exchange rate or reasonable estimate.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.6038D-5",
        recommendation="Value foreign assets at FMV using year-end exchange rate"
    ),
    TaxRule(
        rule_id="FA024",
        name="Form 8938 Maximum Value Reporting",
        description="Report the maximum value of each asset during the tax year, in addition to year-end value.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.6038D-4",
        recommendation="Track and report maximum value during year for each foreign asset"
    ),
    TaxRule(
        rule_id="FA025",
        name="Form 8938 Foreign Trust Interests",
        description="Interests in foreign trusts reported on Form 8938 if no separate Form 3520/3520-A required.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.6038D-3(b)",
        recommendation="Report foreign trust interests on appropriate form"
    ),
    TaxRule(
        rule_id="FA026",
        name="Form 8938 Penalty for Failure",
        description="Failure to file Form 8938 results in $10,000 penalty, plus up to $50,000 for continued failure after notification.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 6038D(d)",
        recommendation="File Form 8938 timely to avoid $10,000+ penalties"
    ),
    TaxRule(
        rule_id="FA027",
        name="Form 8938 Understatement Penalty",
        description="Underpayment attributable to undisclosed foreign financial asset faces 40% penalty (vs normal 20%).",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 6662(j)",
        rate=0.40,
        recommendation="Accurately disclose foreign assets to avoid 40% penalty"
    ),
    TaxRule(
        rule_id="FA028",
        name="Form 8938 Extended Statute of Limitations",
        description="6-year statute of limitations for returns with Form 8938 filing requirement, if omission exceeds $5,000.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 6501(e)(1)(A)",
        recommendation="Keep records for at least 6 years for Form 8938 assets"
    ),
    TaxRule(
        rule_id="FA029",
        name="Form 8938 Reasonable Cause Exception",
        description="Penalties may be waived for reasonable cause and good faith; burden is on taxpayer to prove.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 6038D(g)",
        recommendation="Document reasonable cause for any late or corrected filings"
    ),
    TaxRule(
        rule_id="FA030",
        name="Form 8938 Duplicative Reporting Relief",
        description="Certain assets reported elsewhere need only be identified on Form 8938, not fully detailed.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.6038D-7",
        recommendation="Cross-reference other forms to avoid duplicative reporting"
    ),

    # =========================================================================
    # Foreign Tax Credit Rules (FA031-FA050)
    # =========================================================================
    TaxRule(
        rule_id="FA031",
        name="Foreign Tax Credit Limitation",
        description="Foreign tax credit limited to US tax on foreign source income. Formula: US tax x (foreign source income / worldwide income).",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 904(a)",
        recommendation="Calculate FTC limitation to determine usable credit"
    ),
    TaxRule(
        rule_id="FA032",
        name="Foreign Tax Credit vs Deduction",
        description="Taxpayer may elect to deduct foreign taxes instead of claiming credit. Credit usually more beneficial.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 164(a)(3)",
        recommendation="Compare credit vs deduction; credit usually provides greater benefit"
    ),
    TaxRule(
        rule_id="FA033",
        name="Form 1116 Required",
        description="Form 1116 required for foreign tax credit unless simplified method applies.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="Form 1116 Instructions",
        recommendation="Complete Form 1116 to claim foreign tax credit"
    ),
    TaxRule(
        rule_id="FA034",
        name="Foreign Tax Credit Carryback/Forward",
        description="Excess foreign tax credits can be carried back 1 year or forward 10 years.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 904(c)",
        recommendation="Track excess FTC for carryback/carryforward"
    ),
    TaxRule(
        rule_id="FA035",
        name="Separate Limitation Categories",
        description="FTC calculated separately for passive income and general limitation income categories.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 904(d)",
        recommendation="Separate passive and general income for FTC calculation"
    ),
    TaxRule(
        rule_id="FA036",
        name="Foreign Tax Must Be Income Tax",
        description="Only foreign income taxes (not VAT, sales tax, property tax) qualify for foreign tax credit.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="Reg. 1.901-2",
        recommendation="Verify foreign tax qualifies as income tax for FTC"
    ),
    TaxRule(
        rule_id="FA037",
        name="FTC Foreign Tax Paid or Accrued",
        description="Cash basis taxpayers claim FTC when foreign tax paid; accrual basis when accrued.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 905(a)",
        recommendation="Claim FTC consistent with your accounting method"
    ),
    TaxRule(
        rule_id="FA038",
        name="Treaty-Based FTC Positions",
        description="Some tax treaties modify FTC rules. Disclosure required for treaty-based return positions.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 6114",
        recommendation="Disclose treaty-based positions affecting FTC on Form 8833"
    ),
    TaxRule(
        rule_id="FA039",
        name="Simplified FTC Method Eligibility",
        description="Simplified limitation method available if all foreign tax from qualified passive income and total credit $300 or less ($600 MFJ).",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 904(j)",
        recommendation="Use simplified method if eligible to avoid Form 1116"
    ),
    TaxRule(
        rule_id="FA040",
        name="Simplified Method Threshold",
        description="Simplified method threshold is $300 for single filers, $600 for married filing jointly.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 904(j)(2)",
        thresholds_by_status={
            "single": 300.0,
            "married_joint": 600.0,
            "married_separate": 300.0,
            "head_of_household": 300.0
        },
        recommendation="Check if foreign tax under threshold for simplified method"
    ),
    TaxRule(
        rule_id="FA041",
        name="FTC High-Tax Kickout",
        description="Passive income taxed at high rate may be treated as general category income.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 904(d)(2)(A)(iii)",
        recommendation="Analyze high-tax passive income for potential reclassification"
    ),
    TaxRule(
        rule_id="FA042",
        name="FTC Foreign Source Income Determination",
        description="Income sourcing rules determine foreign vs US source income for FTC limitation calculation.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Sections 861-865",
        recommendation="Apply sourcing rules correctly to determine foreign source income"
    ),
    TaxRule(
        rule_id="FA043",
        name="FTC Timing Difference Adjustments",
        description="Timing differences between US and foreign tax years may require adjustments to FTC calculation.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.905-3",
        recommendation="Adjust for timing differences in FTC calculation"
    ),
    TaxRule(
        rule_id="FA044",
        name="FTC Foreign Tax Redetermination",
        description="If foreign tax liability changes, must notify IRS and adjust FTC within 2 years.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 905(c)",
        recommendation="Report foreign tax changes to IRS within required timeframe"
    ),
    TaxRule(
        rule_id="FA045",
        name="FTC Alternative Minimum Tax",
        description="Separate FTC limitation applies for AMT purposes. AMT FTC may differ from regular FTC.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 59(a)",
        recommendation="Calculate separate FTC limitation for AMT"
    ),
    TaxRule(
        rule_id="FA046",
        name="FTC Foreign Dividend Gross-Up",
        description="Dividends from controlled foreign corporations may require gross-up for deemed paid foreign taxes.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 78",
        recommendation="Include Section 78 gross-up for CFC dividends"
    ),
    TaxRule(
        rule_id="FA047",
        name="FTC Withholding Tax Documentation",
        description="Must have documentation of foreign tax paid to claim FTC. Keep foreign tax receipts and statements.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="Reg. 1.905-2",
        recommendation="Maintain documentation of all foreign taxes paid"
    ),
    TaxRule(
        rule_id="FA048",
        name="FTC Currency Translation",
        description="Convert foreign taxes to US dollars using appropriate exchange rate (payment date or average rate).",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 986",
        recommendation="Use proper exchange rate for foreign tax conversion"
    ),
    TaxRule(
        rule_id="FA049",
        name="FTC GILTI and Section 250",
        description="GILTI inclusions have special FTC rules with 80% haircut on foreign taxes.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 960(d)",
        rate=0.80,
        recommendation="Apply 80% haircut to foreign taxes on GILTI"
    ),
    TaxRule(
        rule_id="FA050",
        name="FTC Tax Treaty Exemptions",
        description="Income exempt from US tax by treaty is not counted in FTC limitation calculation.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 904",
        recommendation="Exclude treaty-exempt income from FTC limitation denominator"
    ),

    # =========================================================================
    # Foreign Earned Income and Other (FA051-FA064)
    # =========================================================================
    TaxRule(
        rule_id="FA051",
        name="Foreign Earned Income Exclusion",
        description="Qualifying taxpayers may exclude up to $130,000 (2025) of foreign earned income from US taxation.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 911",
        limit=130000.0,
        recommendation="Claim FEIE if meeting bona fide residence or physical presence test"
    ),
    TaxRule(
        rule_id="FA052",
        name="FEIE Bona Fide Residence Test",
        description="Must be bona fide resident of foreign country for uninterrupted period including entire tax year.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 911(d)(1)(A)",
        recommendation="Establish bona fide residence in foreign country to qualify for FEIE"
    ),
    TaxRule(
        rule_id="FA053",
        name="FEIE Physical Presence Test",
        description="Must be present in foreign country 330 full days in any 12-month period.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 911(d)(1)(B)",
        threshold=330.0,
        recommendation="Track foreign presence days carefully for 330-day test"
    ),
    TaxRule(
        rule_id="FA054",
        name="Form 2555 Required for FEIE",
        description="Form 2555 required to claim foreign earned income exclusion and housing exclusion.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="Form 2555 Instructions",
        recommendation="Complete Form 2555 to claim FEIE"
    ),
    TaxRule(
        rule_id="FA055",
        name="FEIE Housing Exclusion",
        description="May exclude reasonable foreign housing expenses above base amount (16% of FEIE limit).",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 911(c)",
        rate=0.16,
        recommendation="Claim housing exclusion for qualifying foreign housing costs"
    ),
    TaxRule(
        rule_id="FA056",
        name="FEIE Election Revocation",
        description="FEIE election may be revoked but cannot re-elect for 5 years without IRS approval.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 911(e)",
        recommendation="Consider carefully before revoking FEIE election"
    ),
    TaxRule(
        rule_id="FA057",
        name="Form 3520 Foreign Trust Reporting",
        description="US persons receiving distributions from or transferring property to foreign trusts must file Form 3520.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 6048",
        recommendation="File Form 3520 for foreign trust transactions"
    ),
    TaxRule(
        rule_id="FA058",
        name="Form 3520-A Annual Trust Return",
        description="Foreign trusts with US owners must file annual Form 3520-A information return.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 6048(b)",
        recommendation="Ensure foreign trust files Form 3520-A"
    ),
    TaxRule(
        rule_id="FA059",
        name="Form 5471 CFC Reporting",
        description="US shareholders of controlled foreign corporations must file Form 5471.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 6038",
        recommendation="File Form 5471 for CFC ownership"
    ),
    TaxRule(
        rule_id="FA060",
        name="PFIC Reporting Form 8621",
        description="US shareholders of passive foreign investment companies must file Form 8621.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1298(f)",
        recommendation="File Form 8621 for PFIC ownership and make QEF election if beneficial"
    ),
    TaxRule(
        rule_id="FA061",
        name="Form 8865 Foreign Partnership",
        description="Certain US persons with interests in foreign partnerships must file Form 8865.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 6038B",
        recommendation="File Form 8865 for required foreign partnership interests"
    ),
    TaxRule(
        rule_id="FA062",
        name="GILTI Inclusion",
        description="US shareholders of CFCs must include Global Intangible Low-Taxed Income as ordinary income.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 951A",
        recommendation="Calculate and include GILTI from CFC ownership"
    ),
    TaxRule(
        rule_id="FA063",
        name="Subpart F Income",
        description="Certain passive and related-party income of CFCs is taxed currently to US shareholders.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 951",
        recommendation="Include Subpart F income from CFC ownership"
    ),
    TaxRule(
        rule_id="FA064",
        name="Transition Tax Under TCJA",
        description="One-time transition tax on accumulated foreign earnings. Final installment due 2025 for 8-year election.",
        category=RuleCategory.INTERNATIONAL,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 965",
        recommendation="Ensure transition tax installments are paid on schedule"
    ),
]
