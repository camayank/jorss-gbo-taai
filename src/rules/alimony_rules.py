"""Alimony Tax Rules.

Comprehensive rules for alimony and separate maintenance payments.
Based on IRC Sections 71, 215 (pre-TCJA) and TCJA Section 11051.
Tax Year: 2025

Rules AL001-AL068 covering:
- Pre-2019 instrument rules (old law)
- Post-2018 instrument rules (new law)
- Child support distinctions
- Recapture rules
- Property settlement vs alimony
"""

from __future__ import annotations

from .tax_rule_definitions import TaxRule, RuleCategory, RuleSeverity


# =============================================================================
# ALIMONY RULES (68 rules)
# =============================================================================

ALIMONY_RULES = [
    # =========================================================================
    # Pre-2019 Instrument Rules (AL001-AL025)
    # =========================================================================
    TaxRule(
        rule_id="AL001",
        name="Pre-2019 Alimony Deductible",
        description="Alimony paid under divorce/separation instruments executed before 2019 is deductible by payer (above-the-line).",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 215 (pre-TCJA)",
        recommendation="Deduct pre-2019 alimony payments on Schedule 1 Line 19a"
    ),
    TaxRule(
        rule_id="AL002",
        name="Pre-2019 Alimony Taxable to Recipient",
        description="Alimony received under pre-2019 instruments is taxable income to recipient. Report on Form 1040.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 71 (pre-TCJA)",
        recommendation="Report pre-2019 alimony received as income on Schedule 1"
    ),
    TaxRule(
        rule_id="AL003",
        name="Pre-2019 Cash Payment Requirement",
        description="Alimony under pre-2019 rules must be in cash or cash equivalent (checks, money orders). Property transfers not alimony.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 71(b)(1)",
        recommendation="Make pre-2019 alimony payments in cash or cash equivalent"
    ),
    TaxRule(
        rule_id="AL004",
        name="Pre-2019 Written Instrument Requirement",
        description="Payments must be made under divorce decree, separation agreement, or written separation instrument.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 71(b)(2)(A)",
        recommendation="Ensure alimony is specified in written instrument"
    ),
    TaxRule(
        rule_id="AL005",
        name="Pre-2019 Not Same Household",
        description="If legally separated, spouses paying alimony cannot be members of same household when payment made.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 71(b)(1)(C)",
        recommendation="Maintain separate households for alimony deduction"
    ),
    TaxRule(
        rule_id="AL006",
        name="Pre-2019 No Child Support Designation",
        description="Payments cannot be designated as child support. Child support is not alimony.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 71(c)",
        recommendation="Keep alimony separate from child support in instrument"
    ),
    TaxRule(
        rule_id="AL007",
        name="Pre-2019 Terminates at Death",
        description="Liability to pay must terminate at death of recipient spouse. Post-death payments not deductible.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 71(b)(1)(D)",
        recommendation="Ensure instrument specifies termination at recipient's death"
    ),
    TaxRule(
        rule_id="AL008",
        name="Pre-2019 Not Filed Joint Return",
        description="Payer and recipient cannot file joint return with each other in year of payment.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 71(e)",
        recommendation="Cannot deduct alimony if filing joint return with ex-spouse"
    ),
    TaxRule(
        rule_id="AL009",
        name="Pre-2019 Recipient SSN Required",
        description="Payer must include recipient's SSN on return to claim deduction. Penalty for failure.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 215(c)",
        recommendation="Report recipient's SSN on tax return for alimony deduction"
    ),
    TaxRule(
        rule_id="AL010",
        name="Pre-2019 Recapture Rule",
        description="If alimony decreases significantly in years 2 or 3, excess front-loading may be recaptured as income to payer.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 71(f)",
        recommendation="Structure payments to avoid recapture"
    ),
    TaxRule(
        rule_id="AL011",
        name="Pre-2019 Recapture Calculation",
        description="Recapture applies if year 2 payments exceed year 3 by >$15,000 or year 1 exceeds average of years 2-3 by >$15,000.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 71(f)(4)",
        threshold=15000.0,
        recommendation="Calculate potential recapture when structuring payments"
    ),
    TaxRule(
        rule_id="AL012",
        name="Pre-2019 Recapture in Year 3",
        description="If recapture applies, payer includes recapture amount as income in year 3. Recipient deducts.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 71(f)(1)",
        recommendation="Report recapture in year 3 on Schedule 1"
    ),
    TaxRule(
        rule_id="AL013",
        name="Pre-2019 Recapture Exceptions",
        description="Recapture does not apply if payments end due to death or remarriage of recipient in year 2 or 3.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 71(f)(5)",
        recommendation="Recapture rules have death/remarriage exceptions"
    ),
    TaxRule(
        rule_id="AL014",
        name="Pre-2019 Voluntary Payments",
        description="Voluntary payments in excess of instrument requirements are not deductible alimony.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 71(b)",
        recommendation="Voluntary excess payments are not deductible"
    ),
    TaxRule(
        rule_id="AL015",
        name="Pre-2019 Third Party Payments",
        description="Payments to third parties on behalf of spouse (mortgage, rent, tuition) may qualify as alimony if in instrument.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Temp. Reg. 1.71-1T(b)",
        recommendation="Third-party payments may be alimony if specified in instrument"
    ),
    TaxRule(
        rule_id="AL016",
        name="Pre-2019 Life Insurance Premiums",
        description="Life insurance premium payments for policy owned by recipient may be deductible alimony.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Temp. Reg. 1.71-1T(b)",
        recommendation="Life insurance premiums may qualify as alimony"
    ),
    TaxRule(
        rule_id="AL017",
        name="Pre-2019 Mortgage Payments",
        description="Payer's mortgage payments on home where recipient lives may be partly alimony if specified.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Temp. Reg. 1.71-1T(b)",
        recommendation="Document mortgage payments as alimony in instrument"
    ),
    TaxRule(
        rule_id="AL018",
        name="Pre-2019 Contingent Payments",
        description="Payments contingent on child's status (age, schooling) are treated as child support, not alimony.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 71(c)(2)",
        recommendation="Avoid child-contingent provisions in alimony"
    ),
    TaxRule(
        rule_id="AL019",
        name="Pre-2019 Reduction Within 6 Months",
        description="Payment reductions tied to events within 6 months of child's milestone are presumed child support.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="Temp. Reg. 1.71-1T(c)",
        recommendation="Avoid reductions near child milestone dates"
    ),
    TaxRule(
        rule_id="AL020",
        name="Pre-2019 Arrearage Payments",
        description="Alimony arrearage payments are deductible in year paid, taxable in year received.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 71",
        recommendation="Report arrearage payments in year paid/received"
    ),
    TaxRule(
        rule_id="AL021",
        name="Pre-2019 Substitute Payments",
        description="One-time or lump sum payments may not qualify as alimony. Must examine facts and circumstances.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 71",
        recommendation="Structure periodic payments to clearly establish alimony"
    ),
    TaxRule(
        rule_id="AL022",
        name="Pre-2019 State Law Treatment",
        description="State law designation does not control federal tax treatment. Must meet federal requirements.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 71",
        recommendation="Federal rules control regardless of state law label"
    ),
    TaxRule(
        rule_id="AL023",
        name="Pre-2019 Instrument Modification Impact",
        description="Modifying pre-2019 instrument after 2018 may cause old rules to continue unless specifically electing new rules.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="TCJA Section 11051(c)",
        recommendation="Review modification impact on tax treatment"
    ),
    TaxRule(
        rule_id="AL024",
        name="Pre-2019 Annuity Purchase",
        description="Annuity purchased to discharge alimony obligation may have complex tax consequences.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 71",
        recommendation="Consult tax advisor for annuity arrangements"
    ),
    TaxRule(
        rule_id="AL025",
        name="Pre-2019 Instrument Identification",
        description="Critical to identify whether instrument is pre-2019 or post-2018. Execution date controls.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.CRITICAL,
        irs_reference="TCJA Section 11051",
        recommendation="Verify instrument execution date for tax treatment"
    ),

    # =========================================================================
    # Post-2018 Instrument Rules (AL026-AL045)
    # =========================================================================
    TaxRule(
        rule_id="AL026",
        name="Post-2018 Alimony Not Deductible",
        description="Alimony under instruments executed after December 31, 2018 is not deductible by payer.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.CRITICAL,
        irs_reference="TCJA Section 11051",
        recommendation="Post-2018 alimony payments are not tax deductible"
    ),
    TaxRule(
        rule_id="AL027",
        name="Post-2018 Alimony Not Taxable",
        description="Alimony received under post-2018 instruments is not taxable income to recipient.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.CRITICAL,
        irs_reference="TCJA Section 11051",
        recommendation="Post-2018 alimony received is tax-free"
    ),
    TaxRule(
        rule_id="AL028",
        name="December 31 2018 Cutoff Date",
        description="Instrument must be executed before January 1, 2019 for old (deductible) rules to apply.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.CRITICAL,
        irs_reference="TCJA Section 11051",
        recommendation="Pre-2019 execution date required for deductible alimony"
    ),
    TaxRule(
        rule_id="AL029",
        name="Post-2018 Modified Pre-2019 Election",
        description="Pre-2019 instruments modified after 2018 can elect new (non-deductible) rules if modification expressly states.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="TCJA Section 11051(c)(2)",
        recommendation="Can elect new rules by express statement in modification"
    ),
    TaxRule(
        rule_id="AL030",
        name="Post-2018 No Form 1040 Reporting",
        description="Under new rules, alimony is not reported on either payer's or recipient's tax return.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="TCJA Section 11051",
        recommendation="No tax reporting required for post-2018 alimony"
    ),
    TaxRule(
        rule_id="AL031",
        name="Post-2018 No SSN Requirement",
        description="Since no deduction/income, there is no requirement to report recipient's SSN on tax return.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="TCJA Section 11051",
        recommendation="SSN reporting not required for post-2018 alimony"
    ),
    TaxRule(
        rule_id="AL032",
        name="Post-2018 No Recapture",
        description="Recapture rules do not apply to post-2018 instruments since no deduction was ever taken.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="TCJA Section 11051",
        recommendation="No recapture concerns for post-2018 alimony"
    ),
    TaxRule(
        rule_id="AL033",
        name="Post-2018 Higher Payer Income",
        description="Without deduction, paying spouse has higher taxable income. Consider in settlement negotiations.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="TCJA Section 11051",
        recommendation="Factor tax impact into divorce settlement negotiations"
    ),
    TaxRule(
        rule_id="AL034",
        name="Post-2018 Lower Recipient Tax",
        description="Recipient does not report alimony as income. Effective tax-free receipt.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="TCJA Section 11051",
        recommendation="Recipient benefits from tax-free treatment"
    ),
    TaxRule(
        rule_id="AL035",
        name="Post-2018 Settlement Considerations",
        description="Tax change shifts economic burden to higher-income payer. Total family tax typically higher.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="TCJA Section 11051",
        recommendation="Consider overall tax impact in settlement"
    ),
    TaxRule(
        rule_id="AL036",
        name="Post-2018 Property Settlement Alternative",
        description="Larger property settlement may be preferable to ongoing alimony under new rules.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 1041",
        recommendation="Evaluate property settlement vs alimony trade-offs"
    ),
    TaxRule(
        rule_id="AL037",
        name="Post-2018 Retirement Account Division",
        description="QDRO division of retirement accounts may be more tax-efficient than alimony.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 414(p)",
        recommendation="Consider QDRO transfers as alternative to alimony"
    ),
    TaxRule(
        rule_id="AL038",
        name="Post-2018 Timing of Divorce",
        description="Couples divorcing on or before December 31, 2018 could use old rules. Timing was critical.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="TCJA Section 11051",
        recommendation="Historical timing affected available tax treatment"
    ),
    TaxRule(
        rule_id="AL039",
        name="Post-2018 Separated Couples",
        description="Couples separated but not divorced by 2019 generally subject to new rules.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="TCJA Section 11051",
        recommendation="Separation date does not determine rules; execution date does"
    ),
    TaxRule(
        rule_id="AL040",
        name="Post-2018 Pending Divorces",
        description="Divorces pending at end of 2018 but finalized in 2019+ subject to new rules.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="TCJA Section 11051",
        recommendation="2019+ execution dates use new rules"
    ),
    TaxRule(
        rule_id="AL041",
        name="Post-2018 Term Alimony",
        description="Term (fixed duration) alimony under post-2018 rules provides no deduction but also no recapture risk.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="TCJA Section 11051",
        recommendation="Term alimony simplified under new rules"
    ),
    TaxRule(
        rule_id="AL042",
        name="Post-2018 Permanent Alimony",
        description="Permanent (lifetime) alimony under new rules has no deduction but no income to recipient.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="TCJA Section 11051",
        recommendation="Permanent alimony tax-neutral under new rules"
    ),
    TaxRule(
        rule_id="AL043",
        name="Post-2018 State Income Tax",
        description="Some states have not conformed to TCJA. State may still allow deduction/require inclusion.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="State Law",
        recommendation="Check state conformity to federal alimony rules"
    ),
    TaxRule(
        rule_id="AL044",
        name="Post-2018 Community Property States",
        description="Community property division rules not affected by alimony changes. Different analysis applies.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="State Law",
        recommendation="Community property rules separate from alimony"
    ),
    TaxRule(
        rule_id="AL045",
        name="Post-2018 Support Unallocated",
        description="Single payment covering both alimony and child support must be properly allocated.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 71(c)",
        recommendation="Allocate support payments properly in instrument"
    ),

    # =========================================================================
    # Child Support and Property Settlement (AL046-AL060)
    # =========================================================================
    TaxRule(
        rule_id="AL046",
        name="Child Support Not Deductible",
        description="Child support payments are never deductible by payer and never taxable to recipient.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 71(c)",
        recommendation="Child support has no tax impact on either party"
    ),
    TaxRule(
        rule_id="AL047",
        name="Child Support vs Alimony Distinction",
        description="Payments designated as child support, or contingent on child's status, are child support regardless of label.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 71(c)",
        recommendation="Substance over form determines child support treatment"
    ),
    TaxRule(
        rule_id="AL048",
        name="Unallocated Support Payments",
        description="Unallocated family support treated as child support to extent of minimum child support obligation.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 71(c)",
        recommendation="Allocate support payments clearly in instrument"
    ),
    TaxRule(
        rule_id="AL049",
        name="Child Reaching Age Contingency",
        description="Payment reduction when child reaches majority is presumed child support portion.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="Temp. Reg. 1.71-1T(c)",
        recommendation="Avoid payment changes tied to child's age"
    ),
    TaxRule(
        rule_id="AL050",
        name="Child Events Triggering Reduction",
        description="Reductions tied to child leaving school, marrying, dying, or becoming employed are child support.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 71(c)(2)",
        recommendation="Avoid child-event contingencies in alimony"
    ),
    TaxRule(
        rule_id="AL051",
        name="Property Settlement Tax-Free",
        description="Property transfers incident to divorce are tax-free to both parties under Section 1041.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1041",
        recommendation="Property transfers incident to divorce are non-taxable"
    ),
    TaxRule(
        rule_id="AL052",
        name="Section 1041 Carryover Basis",
        description="Recipient of property in divorce takes transferor's basis. No step-up to fair market value.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1041(b)(2)",
        recommendation="Recipient inherits transferor's tax basis"
    ),
    TaxRule(
        rule_id="AL053",
        name="Property Transfer Within One Year",
        description="Property transfer within one year of marriage ending is presumed incident to divorce.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 1041(c)(1)",
        recommendation="Transfers within 1 year presumed related to divorce"
    ),
    TaxRule(
        rule_id="AL054",
        name="Property Transfer Within Six Years",
        description="Transfers related to cessation of marriage within 6 years also qualify under Section 1041.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 1041(c)(2)",
        recommendation="Transfers within 6 years may qualify if divorce-related"
    ),
    TaxRule(
        rule_id="AL055",
        name="Third Party Transfer Exception",
        description="Property transferred to third party for spouse's benefit may not qualify for Section 1041.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 1041",
        recommendation="Direct transfers to spouse preferred for Section 1041"
    ),
    TaxRule(
        rule_id="AL056",
        name="Residence Transfer",
        description="Transfer of marital home incident to divorce is tax-free. Section 121 exclusion separate issue.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1041",
        recommendation="Home transfer tax-free; eventual sale has separate rules"
    ),
    TaxRule(
        rule_id="AL057",
        name="Retirement Account Division",
        description="Retirement accounts divided by QDRO are not taxable to transferor. Recipient taxed on distribution.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 414(p)",
        recommendation="Use QDRO for tax-free retirement account division"
    ),
    TaxRule(
        rule_id="AL058",
        name="IRA Transfer Incident to Divorce",
        description="IRA transfer incident to divorce is not taxable event. Recipient IRA owner for all purposes.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 408(d)(6)",
        recommendation="Transfer IRA incident to divorce tax-free"
    ),
    TaxRule(
        rule_id="AL059",
        name="Stock Options Transfer",
        description="Stock options transferred to spouse incident to divorce result in deferred taxation to recipient.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Rev. Rul. 2002-22",
        recommendation="Stock option transfers shift tax to recipient on exercise"
    ),
    TaxRule(
        rule_id="AL060",
        name="Business Interest Transfer",
        description="Partnership or LLC interests transferred incident to divorce have carryover basis.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 1041",
        recommendation="Business interest transfers have carryover basis"
    ),

    # =========================================================================
    # Special Situations and Compliance (AL061-AL068)
    # =========================================================================
    TaxRule(
        rule_id="AL061",
        name="Legal Fees Allocation",
        description="Legal fees for tax advice on divorce may be deductible. Fees for obtaining alimony generally not.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 212",
        recommendation="Allocate legal fees for potential tax deduction"
    ),
    TaxRule(
        rule_id="AL062",
        name="Estimated Tax Payments",
        description="Recipient of taxable alimony (pre-2019 rules) may need to make estimated tax payments.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 6654",
        recommendation="Make estimated payments for pre-2019 alimony received"
    ),
    TaxRule(
        rule_id="AL063",
        name="Alimony Pendente Lite",
        description="Temporary alimony during divorce proceedings has same tax treatment as permanent alimony.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 71(b)(2)",
        recommendation="Temporary alimony follows same rules as permanent"
    ),
    TaxRule(
        rule_id="AL064",
        name="Separate Maintenance Agreement",
        description="Written separation agreement can establish alimony treatment even without divorce decree.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 71(b)(2)(B)",
        recommendation="Separation agreement can establish alimony for tax purposes"
    ),
    TaxRule(
        rule_id="AL065",
        name="Decree of Support",
        description="Court decree requiring support payments can establish alimony even if not divorce decree.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 71(b)(2)(C)",
        recommendation="Support decrees may qualify as alimony instruments"
    ),
    TaxRule(
        rule_id="AL066",
        name="Noncompliance with Payment Terms",
        description="Failure to make required payments does not change tax treatment of amounts actually paid.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 71",
        recommendation="Report actual payments made/received regardless of obligation"
    ),
    TaxRule(
        rule_id="AL067",
        name="Garnishment of Wages for Alimony",
        description="Alimony paid through wage garnishment has same tax treatment as direct payment.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 71",
        recommendation="Garnished alimony has same tax rules as voluntary payment"
    ),
    TaxRule(
        rule_id="AL068",
        name="International Alimony",
        description="Alimony payments to non-US recipients follow same rules. Withholding may apply for non-residents.",
        category=RuleCategory.ALIMONY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 71/1441",
        recommendation="Consider withholding requirements for foreign recipients"
    ),
]
