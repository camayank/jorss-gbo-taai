"""Casualty and Disaster Loss Tax Rules.

Comprehensive rules for casualty and theft loss deductions.
Based on IRC Sections 165, 1033, 7508A, and related provisions.
Tax Year: 2025

Rules CL001-CL059 covering:
- Federally declared disaster requirements
- Personal casualty loss limitations
- Business casualty losses
- Replacement property rules
- Extended deadlines and special provisions
"""

from __future__ import annotations

from .tax_rule_definitions import TaxRule, RuleCategory, RuleSeverity


# =============================================================================
# CASUALTY AND DISASTER LOSS RULES (59 rules)
# =============================================================================

CASUALTY_LOSS_RULES = [
    # =========================================================================
    # Core Casualty Rules (CL001-CL020)
    # =========================================================================
    TaxRule(
        rule_id="CL001",
        name="Federally Declared Disaster Requirement",
        description="Personal casualty losses are deductible only if attributable to federally declared disaster (post-2017 TCJA rule).",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 165(h)(5)",
        recommendation="Personal casualty losses deductible only for federally declared disasters"
    ),
    TaxRule(
        rule_id="CL002",
        name="Casualty Loss Definition",
        description="Casualty is sudden, unexpected, or unusual event from external force: fires, storms, shipwrecks, other disasters, theft, vandalism.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 165(c)(3)",
        recommendation="Verify loss meets casualty definition requirements"
    ),
    TaxRule(
        rule_id="CL003",
        name="FEMA Disaster Declaration Required",
        description="Federally declared disaster requires Presidential declaration under Stafford Act or FEMA designation.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 165(i)(5)",
        recommendation="Confirm FEMA disaster declaration for loss location"
    ),
    TaxRule(
        rule_id="CL004",
        name="$100 Per-Event Floor",
        description="Each personal casualty loss reduced by $100 before calculating deductible amount.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 165(h)(1)",
        threshold=100.0,
        recommendation="Apply $100 reduction to each casualty event"
    ),
    TaxRule(
        rule_id="CL005",
        name="10% AGI Reduction",
        description="Total personal casualty losses (after $100 per event) reduced by 10% of AGI.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 165(h)(2)",
        rate=0.10,
        recommendation="Subtract 10% of AGI from total casualty losses"
    ),
    TaxRule(
        rule_id="CL006",
        name="Insurance Reimbursement Netting",
        description="Casualty loss must be reduced by insurance or other reimbursement. No loss for fully insured property.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 165(a)",
        recommendation="Reduce loss by all insurance and reimbursements received"
    ),
    TaxRule(
        rule_id="CL007",
        name="Reasonable Prospect of Recovery",
        description="Cannot deduct loss if reasonable prospect of reimbursement exists. File claim before deducting.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="Reg. 1.165-1(d)(2)",
        recommendation="File insurance claims before claiming casualty loss"
    ),
    TaxRule(
        rule_id="CL008",
        name="Loss Calculation Method",
        description="Casualty loss equals lesser of: (1) decline in FMV, or (2) adjusted basis of property.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 165(b)",
        recommendation="Calculate loss as lesser of FMV decline or adjusted basis"
    ),
    TaxRule(
        rule_id="CL009",
        name="FMV Before and After",
        description="Decline in FMV is difference between FMV immediately before and immediately after casualty.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="Reg. 1.165-7(a)(2)",
        recommendation="Appraise property before and after casualty for FMV decline"
    ),
    TaxRule(
        rule_id="CL010",
        name="Cost of Repairs as Evidence",
        description="Cost of repairs may be used as evidence of loss if repairs restore property to pre-casualty condition.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.165-7(a)(2)(ii)",
        recommendation="Use repair costs to evidence loss amount"
    ),
    TaxRule(
        rule_id="CL011",
        name="Complete Destruction Rule",
        description="If property completely destroyed, loss is adjusted basis reduced by salvage value and insurance.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="Reg. 1.165-7(b)(1)",
        recommendation="Use adjusted basis for completely destroyed property"
    ),
    TaxRule(
        rule_id="CL012",
        name="Personal Use Property Single Item",
        description="Personal use property treated as single item for loss calculation. Cannot separate components.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.165-7(b)(2)(i)",
        recommendation="Calculate loss on entire personal property, not components"
    ),
    TaxRule(
        rule_id="CL013",
        name="Business Property Separate Items",
        description="Business or investment property may calculate loss on each item separately.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.165-7(b)(2)(ii)",
        recommendation="Calculate business casualty losses item by item"
    ),
    TaxRule(
        rule_id="CL014",
        name="Form 4684 Required",
        description="Form 4684 required to report casualty and theft losses for both personal and business property.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.CRITICAL,
        irs_reference="Form 4684 Instructions",
        recommendation="Complete Form 4684 for all casualty and theft losses"
    ),
    TaxRule(
        rule_id="CL015",
        name="Itemized Deduction Requirement",
        description="Personal casualty losses require itemizing deductions on Schedule A. Not available with standard deduction.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 165(h)",
        recommendation="Must itemize to claim personal casualty loss"
    ),
    TaxRule(
        rule_id="CL016",
        name="Business Casualty Loss Treatment",
        description="Business casualty losses are deductible on Schedule C or relevant business form. Not subject to personal limitations.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 165(a)",
        recommendation="Deduct business casualty losses on business tax forms"
    ),
    TaxRule(
        rule_id="CL017",
        name="Rental Property Casualty Loss",
        description="Rental property casualty losses deductible on Schedule E. Subject to passive activity rules.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 165(a)",
        recommendation="Report rental casualty losses on Schedule E"
    ),
    TaxRule(
        rule_id="CL018",
        name="Theft Loss Rules",
        description="Theft loss deductible in year theft discovered, not necessarily when theft occurred.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 165(e)",
        recommendation="Claim theft loss in year of discovery"
    ),
    TaxRule(
        rule_id="CL019",
        name="Theft Loss Documentation",
        description="Theft loss requires documentation: police report, proof of ownership, value evidence.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="Reg. 1.165-8",
        recommendation="File police report and document theft for loss deduction"
    ),
    TaxRule(
        rule_id="CL020",
        name="Casualty or Theft Not Covered",
        description="Losses from declined values, normal wear, progressive deterioration, termite damage, and drought generally not deductible.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="Reg. 1.165-7(a)(3)",
        recommendation="Gradual deterioration does not qualify as casualty"
    ),

    # =========================================================================
    # Disaster Relief Provisions (CL021-CL040)
    # =========================================================================
    TaxRule(
        rule_id="CL021",
        name="Prior Year Election",
        description="Disaster losses may be deducted on prior year return by election. Must elect within 6 months of due date.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 165(i)",
        recommendation="Consider prior year election for quicker refund"
    ),
    TaxRule(
        rule_id="CL022",
        name="Prior Year Election Deadline",
        description="Election to claim disaster loss on prior year return must be made by extended due date of return for disaster year.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 165(i)(1)",
        recommendation="Make prior year election timely"
    ),
    TaxRule(
        rule_id="CL023",
        name="Amended Return for Prior Year Election",
        description="File amended return (Form 1040-X) or original return with statement to make prior year disaster loss election.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="Reg. 1.165-11(e)",
        recommendation="File 1040-X with prior year election statement"
    ),
    TaxRule(
        rule_id="CL024",
        name="Revoking Prior Year Election",
        description="Prior year election may be revoked within 90 days of making election by filing another amended return.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.165-11(f)",
        recommendation="Can revoke prior year election within 90 days"
    ),
    TaxRule(
        rule_id="CL025",
        name="Qualified Disaster Distribution",
        description="Qualified disaster distributions from retirement plans allow 3-year repayment without penalty.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 72(t)(11)",
        recommendation="Consider qualified disaster distribution if eligible"
    ),
    TaxRule(
        rule_id="CL026",
        name="Disaster-Related Hardship Distribution",
        description="Plans may allow hardship distributions for disaster relief. Check plan document for availability.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.401(k)-1(d)(3)",
        recommendation="Check if plan allows disaster hardship withdrawals"
    ),
    TaxRule(
        rule_id="CL027",
        name="Employee Retention Credit",
        description="Employers in federally declared disaster areas may qualify for Employee Retention Credit.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 3134",
        recommendation="Check eligibility for disaster-related ERC"
    ),
    TaxRule(
        rule_id="CL028",
        name="Special Disaster Relief Legislation",
        description="Congress often passes special disaster relief laws providing additional tax benefits. Check recent legislation.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="Disaster Tax Relief Acts",
        recommendation="Review disaster-specific legislation for additional relief"
    ),
    TaxRule(
        rule_id="CL029",
        name="Replacement Property Gain Deferral",
        description="Gain from disaster-related involuntary conversion may be deferred if replacement property acquired within deadline.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1033",
        recommendation="Defer gain by purchasing replacement property timely"
    ),
    TaxRule(
        rule_id="CL030",
        name="Replacement Property Deadline",
        description="Replacement property generally must be acquired within 2 years (4 years for federally declared disaster main homes).",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1033(a)(2)(B)",
        recommendation="Replace property within statutory deadline"
    ),
    TaxRule(
        rule_id="CL031",
        name="Similar or Related Use",
        description="Replacement property must be similar or related in service or use to converted property.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1033(a)(2)(A)",
        recommendation="Acquire similar replacement property to defer gain"
    ),
    TaxRule(
        rule_id="CL032",
        name="Like-Kind for Condemned Business Property",
        description="Condemned business real property can use like-kind standard instead of similar use.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 1033(g)",
        recommendation="Use like-kind standard for condemned business realty"
    ),
    TaxRule(
        rule_id="CL033",
        name="Extension to Replace",
        description="IRS may grant extension of replacement period upon application showing reasonable cause.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.1033(a)-2(c)(3)",
        recommendation="Request replacement period extension if needed"
    ),
    TaxRule(
        rule_id="CL034",
        name="Basis of Replacement Property",
        description="Basis of replacement property reduced by deferred gain. Cost minus deferred gain.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1033(b)",
        recommendation="Calculate reduced basis for replacement property"
    ),
    TaxRule(
        rule_id="CL035",
        name="Reporting Involuntary Conversion",
        description="Report involuntary conversion on Form 4797 for business property or Schedule D for investment property.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="Form 4797 Instructions",
        recommendation="Report involuntary conversion on appropriate form"
    ),
    TaxRule(
        rule_id="CL036",
        name="Unimproved Real Property",
        description="Outdoor residential property (trees, shrubs, lawn) included in single item with residence for loss calculation.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.165-7(b)(2)",
        recommendation="Include landscape in residence loss calculation"
    ),
    TaxRule(
        rule_id="CL037",
        name="Vehicle Casualty Loss",
        description="Vehicle casualty loss equals decline in FMV or adjusted basis, less insurance. No $100 floor for business vehicles.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 165",
        recommendation="Document vehicle value before and after casualty"
    ),
    TaxRule(
        rule_id="CL038",
        name="Casualty Gain Possibility",
        description="If insurance exceeds basis, casualty may result in taxable gain. Consider deferral under Section 1033.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 165(a)",
        recommendation="Watch for casualty gain when insurance exceeds basis"
    ),
    TaxRule(
        rule_id="CL039",
        name="Extended Filing Deadlines",
        description="IRS grants automatic extensions for taxpayers in federally declared disaster areas. Check IRS announcements.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 7508A",
        recommendation="Check for automatic deadline extensions in disaster areas"
    ),
    TaxRule(
        rule_id="CL040",
        name="Abatement of Interest and Penalties",
        description="Interest and penalties may be abated for disaster-affected taxpayers during postponement period.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 7508A",
        recommendation="Request penalty abatement if disaster-affected"
    ),

    # =========================================================================
    # Special Situations (CL041-CL050)
    # =========================================================================
    TaxRule(
        rule_id="CL041",
        name="Main Home Exclusion Interaction",
        description="Section 121 gain exclusion applies before determining casualty gain. May exclude up to $250K/$500K.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Sections 121, 1033",
        recommendation="Apply home sale exclusion before casualty gain calculation"
    ),
    TaxRule(
        rule_id="CL042",
        name="Mixed Use Property",
        description="Mixed personal/business property must allocate casualty loss between personal and business portions.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.165-7(b)(3)",
        recommendation="Allocate loss for mixed-use property"
    ),
    TaxRule(
        rule_id="CL043",
        name="Inventory Losses",
        description="Inventory casualties handled through cost of goods sold, not as separate casualty loss.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.165-7(a)(5)",
        recommendation="Report inventory losses through COGS adjustment"
    ),
    TaxRule(
        rule_id="CL044",
        name="Section 1231 Property Casualty",
        description="Business casualty gains and losses are Section 1231 transactions. Netting rules apply.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1231",
        recommendation="Apply Section 1231 netting to business casualty gains/losses"
    ),
    TaxRule(
        rule_id="CL045",
        name="Ponzi Scheme Loss",
        description="Losses from Ponzi-type investment frauds may qualify for theft loss treatment. Rev. Proc. 2009-20 safe harbor.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="Rev. Proc. 2009-20",
        recommendation="Use safe harbor for Ponzi scheme loss if qualified"
    ),
    TaxRule(
        rule_id="CL046",
        name="Embezzlement Loss",
        description="Embezzlement losses deductible as theft loss in year discovered. Must be from specific identifiable act.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 165(c)(3)",
        recommendation="Report embezzlement as theft loss when discovered"
    ),
    TaxRule(
        rule_id="CL047",
        name="Auto Accident Not Caused by Taxpayer",
        description="Auto accident losses deductible if not caused by taxpayer's willful act or willful negligence.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.165-7(a)(3)",
        recommendation="Auto accident loss deductible if not due to willful acts"
    ),
    TaxRule(
        rule_id="CL048",
        name="Fire Loss Documentation",
        description="Fire loss requires documentation of property destroyed, original cost, FMV, and any insurance.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="Form 4684 Instructions",
        recommendation="Document fire losses thoroughly with photos and records"
    ),
    TaxRule(
        rule_id="CL049",
        name="Flood Loss in Disaster Area",
        description="Flood losses in federally declared disaster areas deductible as personal casualty loss.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 165(h)(5)",
        recommendation="Claim flood loss if in FEMA-declared disaster area"
    ),
    TaxRule(
        rule_id="CL050",
        name="Hurricane/Tornado Loss",
        description="Hurricane and tornado losses in declared disaster areas qualify for personal casualty deduction.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 165(h)(5)",
        recommendation="Document storm damage for disaster loss deduction"
    ),

    # =========================================================================
    # Administrative Rules (CL051-CL059)
    # =========================================================================
    TaxRule(
        rule_id="CL051",
        name="Appraisal Requirements",
        description="Appraisal may be needed to establish FMV before and after casualty. Keep appraisal report with records.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="Reg. 1.165-7(a)(2)",
        recommendation="Obtain professional appraisal for significant losses"
    ),
    TaxRule(
        rule_id="CL052",
        name="Photographs as Evidence",
        description="Before and after photographs valuable evidence for casualty loss. Document damage thoroughly.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRS Publication 547",
        recommendation="Take photographs documenting casualty damage"
    ),
    TaxRule(
        rule_id="CL053",
        name="Insurance Claim Requirement",
        description="Must file timely insurance claim to deduct loss. Failure to file claim may deny deduction.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 165(h)(4)(E)",
        recommendation="File insurance claim before claiming tax deduction"
    ),
    TaxRule(
        rule_id="CL054",
        name="Deductible Amount",
        description="Insurance deductible is part of casualty loss. Reduces reimbursement and increases deductible loss.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRS Publication 547",
        recommendation="Include insurance deductible in loss calculation"
    ),
    TaxRule(
        rule_id="CL055",
        name="Living Expenses Reimbursement",
        description="Insurance reimbursement for temporary living expenses is generally tax-free if under policy limits.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 123",
        recommendation="Living expense reimbursement generally not taxable"
    ),
    TaxRule(
        rule_id="CL056",
        name="Government Disaster Relief",
        description="Government disaster relief payments may be excluded from income under qualified disaster relief rules.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 139",
        recommendation="Government disaster payments may be tax-free"
    ),
    TaxRule(
        rule_id="CL057",
        name="Charitable Gifts Not Casualty",
        description="Disaster-related charitable contributions are deductible as contributions, not as casualty losses.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 170",
        recommendation="Report disaster giving as charitable contribution"
    ),
    TaxRule(
        rule_id="CL058",
        name="Statute of Limitations for Disaster",
        description="Claim for refund for disaster loss generally must be filed within 3 years or extended period.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 6511",
        recommendation="File disaster loss claim within statute of limitations"
    ),
    TaxRule(
        rule_id="CL059",
        name="IRS Disaster Relief Information",
        description="IRS maintains disaster relief information at irs.gov/newsroom/tax-relief-in-disaster-situations.",
        category=RuleCategory.CASUALTY_LOSS,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRS.gov",
        recommendation="Check IRS website for current disaster relief guidance"
    ),
]
