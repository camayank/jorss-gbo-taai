"""Household Employment Tax Rules.

Comprehensive rules for household employer tax obligations.
Based on IRC Sections 3101, 3111, 3121, 3301, 3306, and Publication 926.
Tax Year: 2025

Rules HH001-HH055 covering:
- Schedule H filing requirements
- Social Security and Medicare taxes
- Federal Unemployment Tax (FUTA)
- State unemployment requirements
- W-2 and reporting obligations
"""

from __future__ import annotations

from .tax_rule_definitions import TaxRule, RuleCategory, RuleSeverity


# =============================================================================
# HOUSEHOLD EMPLOYMENT RULES (55 rules)
# =============================================================================

HOUSEHOLD_EMPLOYMENT_RULES = [
    # =========================================================================
    # Filing Requirements (HH001-HH015)
    # =========================================================================
    TaxRule(
        rule_id="HH001",
        name="Schedule H Filing Threshold",
        description="Household employer must file Schedule H if paying cash wages of $2,700 or more to any one household employee in 2025.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 3121(a)(7)(B)",
        threshold=2700.0,
        recommendation="File Schedule H with Form 1040 if paying household employee $2,700+"
    ),
    TaxRule(
        rule_id="HH002",
        name="FUTA Quarterly Threshold",
        description="FUTA tax applies if paying total cash wages of $1,000 or more in any calendar quarter.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 3306(a)(3)",
        threshold=1000.0,
        recommendation="Pay FUTA if quarterly household wages reach $1,000"
    ),
    TaxRule(
        rule_id="HH003",
        name="Household Employee Definition",
        description="Household employee is worker who performs household services in or around your home including housekeepers, maids, babysitters, gardeners, and home health aides.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="Publication 926",
        recommendation="Determine if worker qualifies as household employee"
    ),
    TaxRule(
        rule_id="HH004",
        name="EIN Requirement for Employers",
        description="Household employers need Employer Identification Number (EIN) to report employment taxes. Apply using Form SS-4.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 6109",
        recommendation="Obtain EIN before filing Schedule H or issuing W-2"
    ),
    TaxRule(
        rule_id="HH005",
        name="Form W-2 Issuance Requirement",
        description="Must issue Form W-2 to household employees by January 31 if wages meet Social Security/Medicare threshold.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 6051",
        recommendation="Issue W-2 to household employees by January 31"
    ),
    TaxRule(
        rule_id="HH006",
        name="Form W-3 Filing",
        description="Must file Form W-3 transmittal with Social Security Administration along with Copy A of W-2s by January 31.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 6051",
        recommendation="File W-3 and W-2 Copy A with SSA by January 31"
    ),
    TaxRule(
        rule_id="HH007",
        name="Schedule H Due Date",
        description="Schedule H is filed with Form 1040 by April 15 (or extended due date). Pay employment taxes with income tax return.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="Schedule H Instructions",
        recommendation="Include Schedule H tax with Form 1040 filing"
    ),
    TaxRule(
        rule_id="HH008",
        name="No Quarterly 941 Filing",
        description="Household employers file annual Schedule H instead of quarterly Form 941. Do not file Form 941.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Schedule H Instructions",
        recommendation="Use Schedule H for household employment; not Form 941"
    ),
    TaxRule(
        rule_id="HH009",
        name="Household Employee vs Contractor Test",
        description="Worker is employee if employer controls what and how work is done. Contractors control their own methods.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.CRITICAL,
        irs_reference="Publication 926",
        recommendation="Apply control test to determine employee vs contractor status"
    ),
    TaxRule(
        rule_id="HH010",
        name="Worker Classification Misclassification Risk",
        description="Misclassifying employee as contractor results in liability for all employment taxes plus penalties and interest.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 3509",
        recommendation="Correctly classify household workers to avoid penalties"
    ),
    TaxRule(
        rule_id="HH011",
        name="Spouse as Household Employee",
        description="Spouse performing household work is not a household employee. No employment taxes on spouse's wages.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 3121(b)(3)(A)",
        recommendation="Spouse wages exempt from household employment taxes"
    ),
    TaxRule(
        rule_id="HH012",
        name="Child Under 21 Exception",
        description="Child under 21 employed by parent is exempt from Social Security and Medicare taxes for household work.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 3121(b)(3)(A)",
        recommendation="No FICA taxes on child under 21 doing household work"
    ),
    TaxRule(
        rule_id="HH013",
        name="Parent Employed by Child",
        description="Parent employed by adult child is exempt from FUTA. Social Security/Medicare may still apply.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 3306(c)(5)",
        recommendation="Review parent employment rules for FUTA exemption"
    ),
    TaxRule(
        rule_id="HH014",
        name="Student Under 18 Exception",
        description="Workers under 18 employed as household employees are exempt from Social Security and Medicare if work is not their principal occupation.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 3121(b)(21)",
        recommendation="Student workers under 18 may be exempt from FICA"
    ),
    TaxRule(
        rule_id="HH015",
        name="Multiple Household Employees",
        description="Threshold applies separately to each household employee. May have some employees above and some below threshold.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Publication 926",
        recommendation="Apply threshold individually to each household employee"
    ),

    # =========================================================================
    # Tax Calculations (HH016-HH035)
    # =========================================================================
    TaxRule(
        rule_id="HH016",
        name="Social Security Tax Rate",
        description="Social Security tax is 12.4% total (6.2% employer + 6.2% employee) on wages up to wage base.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 3101/3111",
        rate=0.124,
        recommendation="Withhold 6.2% from employee; pay 6.2% as employer"
    ),
    TaxRule(
        rule_id="HH017",
        name="Medicare Tax Rate",
        description="Medicare tax is 2.9% total (1.45% employer + 1.45% employee) on all wages with no wage base limit.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 3101/3111",
        rate=0.029,
        recommendation="Withhold 1.45% from employee; pay 1.45% as employer"
    ),
    TaxRule(
        rule_id="HH018",
        name="Social Security Wage Base 2025",
        description="Social Security tax applies only to wages up to $176,100 for 2025. No limit for Medicare.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 3121(a)(1)",
        limit=176100.0,
        recommendation="Stop Social Security withholding when wages reach $176,100"
    ),
    TaxRule(
        rule_id="HH019",
        name="Additional Medicare Tax",
        description="0.9% Additional Medicare Tax applies to wages over $200,000 ($250,000 MFJ). Employee only, no employer match.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 3101(b)(2)",
        rate=0.009,
        thresholds_by_status={
            "single": 200000.0,
            "married_joint": 250000.0,
            "married_separate": 125000.0,
            "head_of_household": 200000.0
        },
        recommendation="Withhold Additional Medicare Tax when applicable"
    ),
    TaxRule(
        rule_id="HH020",
        name="FUTA Gross Tax Rate",
        description="Federal Unemployment Tax (FUTA) gross rate is 6.0% on first $7,000 of wages per employee.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 3301",
        rate=0.06,
        limit=7000.0,
        recommendation="Calculate FUTA on first $7,000 of wages"
    ),
    TaxRule(
        rule_id="HH021",
        name="FUTA State Credit",
        description="Credit of up to 5.4% against FUTA for state unemployment taxes paid, reducing net FUTA to 0.6%.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 3302",
        rate=0.054,
        recommendation="Claim FUTA credit for state unemployment taxes paid"
    ),
    TaxRule(
        rule_id="HH022",
        name="Net FUTA Rate",
        description="Net FUTA rate is typically 0.6% after state unemployment credit (6.0% - 5.4% credit).",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 3302",
        rate=0.006,
        recommendation="Use 0.6% FUTA rate if full state credit applies"
    ),
    TaxRule(
        rule_id="HH023",
        name="Credit Reduction States",
        description="Some states have credit reduction due to federal loan balances, increasing net FUTA rate.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 3302(c)",
        recommendation="Check if state has FUTA credit reduction"
    ),
    TaxRule(
        rule_id="HH024",
        name="Employer May Pay Employee Share",
        description="Employer may pay employee's share of Social Security and Medicare taxes. Paid taxes are additional wages to employee.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Publication 926",
        recommendation="If paying employee share, include as additional wages"
    ),
    TaxRule(
        rule_id="HH025",
        name="Cash Wages Definition",
        description="Cash wages include payments by check, money order, and electronic payment. Does not include value of food and lodging.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="Publication 926",
        recommendation="Count cash payments in all forms toward threshold"
    ),
    TaxRule(
        rule_id="HH026",
        name="Non-Cash Compensation",
        description="Non-cash payments (food, lodging) are generally not subject to employment taxes but may be income.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 3121(a)",
        recommendation="Non-cash benefits generally excluded from FICA wages"
    ),
    TaxRule(
        rule_id="HH027",
        name="Estimated Tax Impact",
        description="Household employment taxes may require adjusting estimated tax payments or W-4 withholding.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Publication 505",
        recommendation="Adjust estimated taxes to cover Schedule H liability"
    ),
    TaxRule(
        rule_id="HH028",
        name="Tax Calculation Example",
        description="Total FICA rate is 15.3% (12.4% SS + 2.9% Medicare). Employer and employee each pay 7.65%.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Sections 3101/3111",
        rate=0.153,
        recommendation="Budget for 7.65% employer share plus 7.65% withheld"
    ),
    TaxRule(
        rule_id="HH029",
        name="Record Keeping Requirements",
        description="Keep payroll records for at least 4 years including dates, hours, wages paid, and taxes withheld.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 6001",
        recommendation="Maintain household payroll records for 4+ years"
    ),
    TaxRule(
        rule_id="HH030",
        name="State Unemployment Insurance",
        description="Most states require household employers to pay state unemployment insurance. Check state-specific rules.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="State Law",
        recommendation="Register with state for unemployment insurance"
    ),
    TaxRule(
        rule_id="HH031",
        name="State Income Tax Withholding",
        description="Some states require withholding state income tax from household employee wages. Check state requirements.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="State Law",
        recommendation="Determine if state income tax withholding required"
    ),
    TaxRule(
        rule_id="HH032",
        name="New Hire Reporting",
        description="Must report new household employees to state within 20 days of hire for child support enforcement.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="42 USC 653a",
        recommendation="Report new household employees to state"
    ),
    TaxRule(
        rule_id="HH033",
        name="I-9 Employment Verification",
        description="Must complete Form I-9 verifying employment eligibility for all household employees.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.CRITICAL,
        irs_reference="8 USC 1324a",
        recommendation="Complete Form I-9 for all household employees"
    ),
    TaxRule(
        rule_id="HH034",
        name="Workers Compensation",
        description="Many states require workers compensation insurance for household employees. Check state requirements.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="State Law",
        recommendation="Obtain workers compensation if required by state"
    ),
    TaxRule(
        rule_id="HH035",
        name="Disability Insurance",
        description="Some states require disability insurance for household employees (CA, NJ, NY, RI, HI).",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="State Law",
        recommendation="Provide disability insurance if required by state"
    ),

    # =========================================================================
    # Special Situations (HH036-HH045)
    # =========================================================================
    TaxRule(
        rule_id="HH036",
        name="Live-In Household Employee",
        description="Live-in household employees have same tax treatment but room and board value excluded from wages.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 119",
        recommendation="Exclude value of lodging from live-in employee wages"
    ),
    TaxRule(
        rule_id="HH037",
        name="Part-Time Babysitter",
        description="Casual babysitters paid under threshold are exempt. Regular babysitters meeting threshold are covered.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Publication 926",
        recommendation="Track babysitter payments to determine if threshold met"
    ),
    TaxRule(
        rule_id="HH038",
        name="Home Health Aide",
        description="Home health aides caring for family members are household employees if employer controls work.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="Publication 926",
        recommendation="Treat home health aides as household employees if applicable"
    ),
    TaxRule(
        rule_id="HH039",
        name="Gardener/Landscaper Classification",
        description="Gardener is household employee if you control the work. Landscaping companies are contractors.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Publication 926",
        recommendation="Classify gardeners based on control test"
    ),
    TaxRule(
        rule_id="HH040",
        name="Au Pair Program",
        description="Au pairs through designated programs may have special rules. Stipend may be taxable income to au pair.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Rev. Proc. 71-8",
        recommendation="Follow au pair program guidelines for tax treatment"
    ),
    TaxRule(
        rule_id="HH041",
        name="Personal Assistant",
        description="Personal assistants performing household duties are household employees subject to Schedule H.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Publication 926",
        recommendation="Treat personal assistants as household employees"
    ),
    TaxRule(
        rule_id="HH042",
        name="Pool or Vacation Home Employee",
        description="Workers at second homes or vacation properties are household employees if work is household services.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Publication 926",
        recommendation="Include second home workers in household employment"
    ),
    TaxRule(
        rule_id="HH043",
        name="Private Chef or Cook",
        description="Private chefs preparing meals in employer's home are household employees.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Publication 926",
        recommendation="Treat private chefs as household employees"
    ),
    TaxRule(
        rule_id="HH044",
        name="Driver/Chauffeur",
        description="Personal drivers providing transportation for family are household employees.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Publication 926",
        recommendation="Treat personal drivers as household employees"
    ),
    TaxRule(
        rule_id="HH045",
        name="Estate or Property Manager",
        description="Estate managers or property managers may be household employees if primarily performing household services.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Publication 926",
        recommendation="Evaluate estate manager duties for classification"
    ),

    # =========================================================================
    # Compliance and Penalties (HH046-HH055)
    # =========================================================================
    TaxRule(
        rule_id="HH046",
        name="Failure to File W-2 Penalty",
        description="Penalty for failure to file correct W-2 ranges from $60 to $310 per form depending on lateness.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 6721",
        recommendation="File W-2s timely to avoid penalties"
    ),
    TaxRule(
        rule_id="HH047",
        name="Failure to Furnish W-2 Penalty",
        description="Penalty for failure to furnish correct W-2 to employee ranges from $60 to $310 per form.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 6722",
        recommendation="Provide W-2 to employee by January 31"
    ),
    TaxRule(
        rule_id="HH048",
        name="Failure to Deposit Penalty",
        description="Household employers generally pay with return but underpayment penalties may apply.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 6656",
        recommendation="Adjust estimated taxes to cover Schedule H liability"
    ),
    TaxRule(
        rule_id="HH049",
        name="Trust Fund Recovery Penalty",
        description="Responsible persons can be personally liable for employee taxes withheld but not remitted.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 6672",
        recommendation="Always remit withheld taxes to IRS"
    ),
    TaxRule(
        rule_id="HH050",
        name="I-9 Violation Penalties",
        description="Civil penalties for I-9 violations range from $252 to $2,507 per employee for first offense.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="8 CFR 274a.10",
        recommendation="Complete and retain I-9 forms properly"
    ),
    TaxRule(
        rule_id="HH051",
        name="Statute of Limitations",
        description="IRS can assess employment taxes for 3 years from return due date or filing date, whichever is later.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 6501",
        recommendation="Keep records for at least 3 years after filing"
    ),
    TaxRule(
        rule_id="HH052",
        name="Backup Withholding",
        description="Backup withholding (24%) required if employee doesn't provide valid SSN.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 3406",
        rate=0.24,
        recommendation="Obtain valid SSN from household employees"
    ),
    TaxRule(
        rule_id="HH053",
        name="Payroll Tax Services",
        description="Using payroll service doesn't relieve employer's obligation but can help ensure compliance.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.LOW,
        irs_reference="Publication 926",
        recommendation="Consider payroll service for household employment compliance"
    ),
    TaxRule(
        rule_id="HH054",
        name="Tax Deductibility of Household Wages",
        description="Household employee wages are generally not deductible unless employee provides business or medical services.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 262",
        recommendation="Household wages generally not tax deductible"
    ),
    TaxRule(
        rule_id="HH055",
        name="Dependent Care Benefits Interaction",
        description="Employer-provided dependent care benefits reduce available dependent care credit. Combined limit applies.",
        category=RuleCategory.HOUSEHOLD_EMPLOYMENT,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 129",
        recommendation="Coordinate dependent care benefits with tax credit"
    ),
]
