"""Complete question registry — every question the advisor can ask.

76 questions organised into 13 pools.  Each question declares when it
should appear (eligibility), how relevant it is (score), and what
profile fields it populates.

Pools
─────
basics              Phase 1 – filing status, income, state, dependents, income type
income_details      Withholding, multiple W-2s, side hustle, spouse income, age
self_employment     Entity type, business income, home office, vehicle, equipment …
investments         Stocks, crypto, stock options, loss carryforward …
retirement          Contributions, HSA, SS benefits, pension, RMD, Roth conversion …
dependents          Child ages, childcare, DCFSA, education, 529, adoption, custody
deductions          Mortgage, SALT, charity, medical, student loans, educator …
life_events         Marriage, divorce, baby, home sale, state move, job loss …
rental_property     Rental income, participation, depreciation
k1_partnership      K-1 income
healthcare          ACA marketplace, Medicare premiums
special_situations  Estimated payments, energy credits, foreign income, alimony …
state_specific      Multi-state income, remote worker
"""

from src.web.advisor.flow_engine import FlowQuestion
from src.web.advisor.flow_rules import (
    is_w2_employee,
    is_w2_only,
    is_multiple_w2,
    is_w2_plus_side,
    is_business_or_se,
    is_self_employed_only,
    is_scorp,
    is_retired,
    is_military,
    is_investor,
    is_mfj,
    is_mfs,
    is_single_or_hoh,
    has_dependents,
    has_young_dependents,
    has_no_dependents,
    is_no_income_tax_state,
    is_low_income,
    is_low_income_w2_only,
    is_senior,
    has_investments,
    has_rental,
    has_k1,
    has_business_income,
    income_above,
    income_below,
    _income,
)

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — BASICS  (5 questions, sequential, all required)
# ═══════════════════════════════════════════════════════════════════════════════

BASICS = [
    # Q-01
    FlowQuestion(
        id="filing_status",
        pool="basics", phase=1,
        text="What's your filing status for this tax year?",
        actions=[
            {"label": "Single", "value": "single"},
            {"label": "Married Filing Jointly", "value": "married_joint"},
            {"label": "Head of Household", "value": "head_of_household"},
            {"label": "Married Filing Separately", "value": "married_separate"},
            {"label": "Qualifying Surviving Spouse", "value": "qualifying_widow"},
        ],
        eligibility=lambda p: not p.get("filing_status"),
        base_score=100,
        sets_fields=["filing_status"],
        asked_field="_asked_filing_status",
    ),
    # Q-02
    FlowQuestion(
        id="total_income",
        pool="basics", phase=1,
        text="What's your approximate total annual income? Include all sources — wages, business, investments.",
        actions=[
            {"label": "Under $25K", "value": "income_under_25k"},
            {"label": "$25K – $50K", "value": "income_25_50k"},
            {"label": "$50K – $100K", "value": "income_50_100k"},
            {"label": "$100K – $200K", "value": "income_100_200k"},
            {"label": "$200K – $500K", "value": "income_200_500k"},
            {"label": "Over $500K", "value": "income_over_500k"},
        ],
        eligibility=lambda p: p.get("filing_status") and not p.get("total_income"),
        base_score=99,
        sets_fields=["total_income"],
        asked_field="_asked_total_income",
    ),
    # Q-03
    FlowQuestion(
        id="state",
        pool="basics", phase=1,
        text="Which state do you live in?",
        actions=[{"label": "Select your state", "value": "state_dropdown"}],
        eligibility=lambda p: p.get("total_income") and not p.get("state"),
        base_score=98,
        sets_fields=["state"],
        asked_field="_asked_state",
    ),
    # Q-04
    FlowQuestion(
        id="dependents",
        pool="basics", phase=1,
        text="Do you have any dependents (children, qualifying relatives)?",
        actions=[
            {"label": "No dependents", "value": "0_dependents"},
            {"label": "1 dependent", "value": "1_dependent"},
            {"label": "2 dependents", "value": "2_dependents"},
            {"label": "3 dependents", "value": "3_dependents"},
            {"label": "4+ dependents", "value": "4plus_dependents"},
        ],
        eligibility=lambda p: p.get("state") and p.get("dependents") is None,
        base_score=97,
        sets_fields=["dependents"],
        asked_field="_asked_dependents",
    ),
    # Q-05
    FlowQuestion(
        id="income_type",
        pool="basics", phase=1,
        text="What best describes your income situation?",
        actions=[
            {"label": "W-2 Employee (single job)", "value": "w2_employee"},
            {"label": "Multiple W-2 Jobs", "value": "multiple_w2"},
            {"label": "W-2 + Side Hustle / Freelance", "value": "w2_plus_side"},
            {"label": "Self-Employed / Freelancer (full-time)", "value": "self_employed"},
            {"label": "Business Owner (LLC / S-Corp / Partnership)", "value": "business_owner"},
            {"label": "Retired / Pension", "value": "retired"},
            {"label": "Primarily Investment Income", "value": "investor"},
            {"label": "Military", "value": "military"},
        ],
        eligibility=lambda p: (
            p.get("dependents") is not None
            and not p.get("income_type")
            and not p.get("is_self_employed")
        ),
        base_score=96,
        sets_fields=["income_type"],
        asked_field="_asked_income_type",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — INCOME DETAILS  (7 questions)
# ═══════════════════════════════════════════════════════════════════════════════

INCOME_DETAILS = [
    # Q-06  Withholding (W-2 employees only — NOT retired, NOT investor)
    FlowQuestion(
        id="withholding",
        pool="income_details", phase=2,
        text=(
            "Approximately how much federal tax was withheld from your "
            "paychecks this year? Check your last pay stub for the YTD "
            "Federal Tax amount."
        ),
        actions=[
            {"label": "Under $5,000", "value": "withholding_under_5k"},
            {"label": "$5,000 – $10,000", "value": "withholding_5_10k"},
            {"label": "$10,000 – $20,000", "value": "withholding_10_20k"},
            {"label": "$20,000 – $40,000", "value": "withholding_20_40k"},
            {"label": "Over $40,000", "value": "withholding_over_40k"},
            {"label": "Not sure — estimate for me", "value": "withholding_estimate"},
        ],
        eligibility=lambda p: (
            is_w2_employee(p)
            and not p.get("federal_withholding")
        ),
        base_score=90,
        sets_fields=["federal_withholding"],
        asked_field="_asked_withholding",
    ),
    # Q-07  Multiple W-2 job count
    FlowQuestion(
        id="inc_multiple_w2_count",
        pool="income_details", phase=2,
        text="How many W-2 jobs did you have this year?",
        actions=[
            {"label": "2 jobs", "value": "2_jobs"},
            {"label": "3 or more jobs", "value": "3plus_jobs"},
        ],
        eligibility=lambda p: is_multiple_w2(p) and not p.get("w2_job_count"),
        base_score=88,
        sets_fields=["w2_job_count"],
        asked_field="_asked_w2_count",
    ),
    # Q-08  Side hustle type
    FlowQuestion(
        id="inc_side_hustle_type",
        pool="income_details", phase=2,
        text="What type of side income do you have?",
        actions=[
            {"label": "Freelance / Consulting (1099-NEC)", "value": "freelance"},
            {"label": "Gig Work (Uber, DoorDash, etc.)", "value": "gig_work"},
            {"label": "Online Sales (Etsy, eBay, Shopify)", "value": "online_sales"},
            {"label": "Rental Income", "value": "side_rental"},
            {"label": "Multiple types", "value": "multiple_side"},
        ],
        eligibility=lambda p: is_w2_plus_side(p) and not p.get("side_hustle_type"),
        base_score=87,
        sets_fields=["side_hustle_type"],
        asked_field="_asked_side_type",
    ),
    # Q-09  Side income amount (follow-up)
    FlowQuestion(
        id="inc_side_income_amount",
        pool="income_details", phase=2,
        text="What's your approximate net side income (after expenses)?",
        actions=[
            {"label": "Under $5,000", "value": "side_under_5k"},
            {"label": "$5,000 – $20,000", "value": "side_5_20k"},
            {"label": "$20,000 – $50,000", "value": "side_20_50k"},
            {"label": "Over $50,000", "value": "side_over_50k"},
            {"label": "Skip", "value": "skip_side_income"},
        ],
        eligibility=lambda p: (
            is_w2_plus_side(p)
            and p.get("side_hustle_type")
            and not p.get("side_income")
        ),
        base_score=86,
        sets_fields=["side_income"],
        asked_field="_asked_side_income",
        follow_up_of="inc_side_hustle_type",
    ),
    # Q-10  Spouse income type (MFJ only)
    FlowQuestion(
        id="inc_spouse_income_type",
        pool="income_details", phase=2,
        text="Does your spouse also earn income? If so, what type?",
        actions=[
            {"label": "W-2 Employee", "value": "spouse_w2"},
            {"label": "Self-Employed", "value": "spouse_se"},
            {"label": "Not working / Homemaker", "value": "spouse_none"},
            {"label": "Retired", "value": "spouse_retired"},
            {"label": "Skip", "value": "skip_spouse_income"},
        ],
        eligibility=lambda p: is_mfj(p) and not p.get("spouse_income_type"),
        base_score=85,
        sets_fields=["spouse_income_type"],
        asked_field="_asked_spouse_income_type",
    ),
    # Q-11  Spouse income amount (follow-up)
    FlowQuestion(
        id="inc_spouse_income_amount",
        pool="income_details", phase=2,
        text="What's your spouse's approximate annual income?",
        actions=[
            {"label": "Under $25K", "value": "spouse_under_25k"},
            {"label": "$25K – $50K", "value": "spouse_25_50k"},
            {"label": "$50K – $100K", "value": "spouse_50_100k"},
            {"label": "Over $100K", "value": "spouse_over_100k"},
            {"label": "Skip", "value": "skip_spouse_amount"},
        ],
        eligibility=lambda p: (
            p.get("spouse_income_type") in ("spouse_w2", "spouse_se")
            and not p.get("spouse_income")
        ),
        base_score=84,
        sets_fields=["spouse_income"],
        asked_field="_asked_spouse_income",
        follow_up_of="inc_spouse_income_type",
    ),
    # Q-12  Age
    FlowQuestion(
        id="age",
        pool="income_details", phase=2,
        text=(
            "What is your age? This helps determine your standard deduction "
            "and eligibility for certain credits."
        ),
        actions=[
            {"label": "Under 26", "value": "age_under_26"},
            {"label": "26 – 49", "value": "age_26_49"},
            {"label": "50 – 64", "value": "age_50_64"},
            {"label": "65 or older", "value": "age_65_plus"},
            {"label": "Skip", "value": "skip_age"},
        ],
        eligibility=lambda p: not p.get("age"),
        base_score=75,
        context_boost_keywords=["retire", "senior", "65", "older", "age", "young"],
        sets_fields=["age"],
        asked_field="_asked_age",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — SELF-EMPLOYMENT & BUSINESS  (9 questions)
# ═══════════════════════════════════════════════════════════════════════════════

SELF_EMPLOYMENT = [
    # Q-13  Entity type
    FlowQuestion(
        id="se_entity_type",
        pool="self_employment", phase=2,
        text="What type of business entity do you have?",
        actions=[
            {"label": "Sole Proprietorship (no entity)", "value": "sole_prop"},
            {"label": "Single-Member LLC", "value": "single_llc"},
            {"label": "Multi-Member LLC", "value": "multi_llc"},
            {"label": "S-Corporation", "value": "s_corp"},
            {"label": "C-Corporation", "value": "c_corp"},
            {"label": "Partnership", "value": "partnership"},
            {"label": "Not sure", "value": "entity_unsure"},
        ],
        eligibility=lambda p: is_business_or_se(p) and not p.get("entity_type"),
        base_score=82,
        sets_fields=["entity_type"],
        asked_field="_asked_entity_type",
    ),
    # Q-14  Business income
    FlowQuestion(
        id="se_business_income",
        pool="self_employment", phase=2,
        text="What's your approximate net business income (revenue minus expenses)?",
        actions=[
            {"label": "Under $25K", "value": "biz_under_25k"},
            {"label": "$25K – $50K", "value": "biz_25_50k"},
            {"label": "$50K – $100K", "value": "biz_50_100k"},
            {"label": "$100K – $200K", "value": "biz_100_200k"},
            {"label": "Over $200K", "value": "biz_over_200k"},
            {"label": "Net loss", "value": "biz_net_loss"},
            {"label": "Skip", "value": "skip_business"},
        ],
        eligibility=lambda p: is_business_or_se(p) and not p.get("business_income"),
        base_score=80,
        context_boost_keywords=[
            "freelance", "1099", "business", "contractor", "gig", "revenue",
        ],
        sets_fields=["business_income"],
        asked_field="_asked_business",
    ),
    # Q-15  S-Corp reasonable salary
    FlowQuestion(
        id="se_reasonable_salary",
        pool="self_employment", phase=2,
        text=(
            "As an S-Corp owner, what salary do you pay yourself? "
            "(This affects your self-employment tax savings)"
        ),
        actions=[
            {"label": "Under $50K", "value": "salary_under_50k"},
            {"label": "$50K – $100K", "value": "salary_50_100k"},
            {"label": "$100K – $150K", "value": "salary_100_150k"},
            {"label": "Over $150K", "value": "salary_over_150k"},
            {"label": "Skip", "value": "skip_salary"},
        ],
        eligibility=lambda p: is_scorp(p) and not p.get("reasonable_salary"),
        base_score=78,
        sets_fields=["reasonable_salary"],
        asked_field="_asked_salary",
        follow_up_of="se_entity_type",
    ),
    # Q-16  Home office
    FlowQuestion(
        id="se_home_office",
        pool="self_employment", phase=2,
        text="Do you use part of your home exclusively and regularly for business?",
        actions=[
            {"label": "Yes, I have a dedicated home office", "value": "has_home_office"},
            {"label": "No home office", "value": "no_home_office"},
            {"label": "Skip", "value": "skip_home_office"},
        ],
        eligibility=lambda p: (
            is_business_or_se(p)
            and has_business_income(p)
            and not p.get("home_office_sqft")
        ),
        base_score=70,
        context_boost_keywords=["home", "remote", "office", "wfh"],
        sets_fields=["home_office_sqft"],
        asked_field="_asked_home_office",
    ),
    # Q-17  Vehicle / mileage
    FlowQuestion(
        id="se_vehicle",
        pool="self_employment", phase=2,
        text=(
            "Do you use a vehicle for business? "
            "(Commuting doesn't count — business travel, client visits, deliveries)"
        ),
        actions=[
            {"label": "Yes, I drive for business", "value": "has_biz_vehicle"},
            {"label": "No business vehicle use", "value": "no_biz_vehicle"},
            {"label": "Skip", "value": "skip_vehicle"},
        ],
        eligibility=lambda p: (
            is_business_or_se(p)
            and has_business_income(p)
            and not p.get("business_miles")
        ),
        base_score=65,
        context_boost_keywords=["drive", "car", "vehicle", "mileage", "uber", "delivery"],
        sets_fields=["business_miles"],
        asked_field="_asked_vehicle",
    ),
    # Q-18  Equipment / Section 179
    FlowQuestion(
        id="se_equipment",
        pool="self_employment", phase=2,
        text=(
            "Did you purchase any major equipment or assets for your business "
            "this year? (Computers, machinery, furniture, vehicles)"
        ),
        actions=[
            {"label": "Yes, I bought equipment", "value": "has_equipment"},
            {"label": "No major purchases", "value": "no_equipment"},
            {"label": "Skip", "value": "skip_equipment"},
        ],
        eligibility=lambda p: (
            is_business_or_se(p)
            and _income(p) > 25000
            and has_business_income(p)
            and not p.get("equipment_cost")
        ),
        base_score=55,
        context_boost_keywords=[
            "equipment", "computer", "machine", "section 179", "depreciation",
        ],
        sets_fields=["equipment_cost"],
        asked_field="_asked_equipment",
    ),
    # Q-19  Employees / contractors
    FlowQuestion(
        id="se_employees",
        pool="self_employment", phase=2,
        text="Do you have any employees or pay independent contractors?",
        actions=[
            {"label": "Yes, I have employees", "value": "has_employees"},
            {"label": "Yes, I pay contractors (1099)", "value": "has_contractors"},
            {"label": "Both employees and contractors", "value": "has_both_workers"},
            {"label": "No — solo operation", "value": "solo_operation"},
            {"label": "Skip", "value": "skip_employees"},
        ],
        eligibility=lambda p: (
            is_business_or_se(p)
            and _income(p) > 50000
            and has_business_income(p)
            and not p.get("has_employees_status")
        ),
        base_score=45,
        sets_fields=["has_employees_status"],
        asked_field="_asked_employees",
    ),
    # Q-20  Self-employed health insurance
    FlowQuestion(
        id="se_health_insurance",
        pool="self_employment", phase=2,
        text=(
            "Do you pay for your own health insurance? Self-employed "
            "individuals can deduct 100% of premiums."
        ),
        actions=[
            {"label": "Yes, I pay my own premiums", "value": "has_se_health"},
            {"label": "Covered by spouse's employer", "value": "spouse_coverage"},
            {"label": "ACA Marketplace plan", "value": "aca_plan"},
            {"label": "No health insurance", "value": "no_health_insurance"},
            {"label": "Skip", "value": "skip_se_health"},
        ],
        eligibility=lambda p: (
            is_self_employed_only(p) and not p.get("se_health_insurance")
        ),
        base_score=72,
        context_boost_keywords=["health", "insurance", "premium", "medical"],
        sets_fields=["se_health_insurance"],
        asked_field="_asked_se_health",
    ),
    # Q-21  QBI / SSTB classification
    FlowQuestion(
        id="se_sstb_check",
        pool="self_employment", phase=2,
        text=(
            "Is your business in a 'specified service' field? "
            "(Law, medicine, accounting, consulting, financial services, "
            "performing arts, athletics)"
        ),
        actions=[
            {"label": "Yes — service-based profession", "value": "is_sstb"},
            {"label": "No — product / trade / other", "value": "not_sstb"},
            {"label": "Not sure", "value": "sstb_unsure"},
            {"label": "Skip", "value": "skip_sstb"},
        ],
        eligibility=lambda p: (
            is_business_or_se(p)
            and _income(p) > 182100
            and not p.get("is_sstb")
        ),
        base_score=68,
        context_boost_keywords=["qbi", "199a", "deduction", "service"],
        sets_fields=["is_sstb"],
        asked_field="_asked_sstb",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — INVESTMENTS  (7 questions)
# ═══════════════════════════════════════════════════════════════════════════════

INVESTMENTS = [
    # Q-22  Has investments?
    FlowQuestion(
        id="inv_has_investments",
        pool="investments", phase=2,
        text=(
            "Do you have any investment income? "
            "(Stocks, bonds, crypto, dividends, interest)"
        ),
        actions=[
            {"label": "Yes, I have investments", "value": "has_investments"},
            {"label": "No investment income", "value": "no_investments"},
            {"label": "Skip", "value": "skip_investments"},
        ],
        eligibility=lambda p: (
            not p.get("_has_investments")
            and not p.get("investment_income")
            and not is_investor(p)  # investors are asked differently
        ),
        base_score=50,
        context_boost_keywords=[
            "stock", "invest", "crypto", "dividend", "capital", "trading",
        ],
        sets_fields=["_has_investments"],
        asked_field="_asked_investments",
    ),
    # Q-23  Investment amount
    FlowQuestion(
        id="inv_amount",
        pool="investments", phase=2,
        text=(
            "Approximately how much total investment income? "
            "(Dividends, interest, capital gains combined)"
        ),
        actions=[
            {"label": "Under $5,000", "value": "invest_under_5k"},
            {"label": "$5,000 – $25,000", "value": "invest_5_25k"},
            {"label": "$25,000 – $100,000", "value": "invest_25_100k"},
            {"label": "Over $100,000", "value": "invest_over_100k"},
            {"label": "Skip", "value": "skip_invest_amount"},
        ],
        eligibility=lambda p: (
            (has_investments(p) or is_investor(p))
            and not p.get("investment_income")
        ),
        base_score=65,
        sets_fields=["investment_income"],
        asked_field="_asked_invest_amount",
        follow_up_of="inv_has_investments",
    ),
    # Q-24  Capital gains breakdown
    FlowQuestion(
        id="inv_capital_gains",
        pool="investments", phase=2,
        text=(
            "Did you sell any investments this year? Were the gains mostly "
            "long-term (held > 1 year) or short-term?"
        ),
        actions=[
            {"label": "Mostly long-term gains", "value": "lt_gains"},
            {"label": "Mostly short-term gains", "value": "st_gains"},
            {"label": "Mix of both", "value": "mixed_gains"},
            {"label": "Had losses (not gains)", "value": "had_losses"},
            {"label": "No sales this year", "value": "no_sales"},
            {"label": "Skip", "value": "skip_cap_gains"},
        ],
        eligibility=lambda p: (
            (has_investments(p) or is_investor(p))
            and p.get("investment_income")
            and not p.get("capital_gains_type")
        ),
        base_score=64,
        sets_fields=["capital_gains_type"],
        asked_field="_asked_cap_gains",
        follow_up_of="inv_amount",
    ),
    # Q-25  Crypto
    FlowQuestion(
        id="inv_crypto",
        pool="investments", phase=2,
        text=(
            "Did you have any cryptocurrency activity? "
            "(Trading, mining, staking, DeFi, NFTs)"
        ),
        actions=[
            {"label": "Yes — trading / selling crypto", "value": "crypto_trading"},
            {"label": "Yes — mining or staking", "value": "crypto_mining"},
            {"label": "Yes — multiple activities", "value": "crypto_multiple"},
            {"label": "No crypto activity", "value": "no_crypto"},
            {"label": "Skip", "value": "skip_crypto"},
        ],
        eligibility=lambda p: (
            (has_investments(p) or is_investor(p))
            and not p.get("crypto_activity")
        ),
        base_score=45,
        context_boost_keywords=[
            "crypto", "bitcoin", "ethereum", "nft", "defi", "mining", "staking",
        ],
        context_boost_amount=35,
        sets_fields=["crypto_activity"],
        asked_field="_asked_crypto",
    ),
    # Q-26  Stock options / RSU / ESPP
    FlowQuestion(
        id="inv_stock_options",
        pool="investments", phase=2,
        text=(
            "Do you have any employer stock compensation? "
            "(Stock options, RSUs, or ESPP)"
        ),
        actions=[
            {"label": "Incentive Stock Options (ISO)", "value": "has_iso"},
            {"label": "Non-Qualified Options (NSO)", "value": "has_nso"},
            {"label": "Restricted Stock Units (RSU)", "value": "has_rsu"},
            {"label": "Employee Stock Purchase Plan (ESPP)", "value": "has_espp"},
            {"label": "Multiple types", "value": "multiple_stock_comp"},
            {"label": "None", "value": "no_stock_comp"},
            {"label": "Skip", "value": "skip_stock_comp"},
        ],
        eligibility=lambda p: (
            is_w2_employee(p)
            and _income(p) > 100000
            and not p.get("stock_compensation")
        ),
        base_score=55,
        context_boost_keywords=[
            "iso", "rsu", "espp", "stock option", "vesting", "exercise", "equity",
        ],
        sets_fields=["stock_compensation"],
        asked_field="_asked_stock_comp",
    ),
    # Q-27  Loss carryforward
    FlowQuestion(
        id="inv_loss_carryforward",
        pool="investments", phase=2,
        text=(
            "Do you have any capital loss carryforward from prior years? "
            "(Unused losses from previous tax returns)"
        ),
        actions=[
            {"label": "Yes", "value": "has_loss_carryforward"},
            {"label": "No / Not sure", "value": "no_loss_carryforward"},
            {"label": "Skip", "value": "skip_loss_carryforward"},
        ],
        eligibility=lambda p: (
            (has_investments(p) or is_investor(p))
            and p.get("capital_gains_type") in (
                "had_losses", "lt_gains", "st_gains", "mixed_gains",
            )
            and not p.get("loss_carryforward")
        ),
        base_score=48,
        sets_fields=["loss_carryforward"],
        asked_field="_asked_loss_carryforward",
    ),
    # Q-28  Qualified dividends (high inv income)
    FlowQuestion(
        id="inv_qualified_dividends",
        pool="investments", phase=2,
        text=(
            "Are your dividends mostly qualified (held > 60 days) or "
            "ordinary? Qualified dividends are taxed at lower capital-gains rates."
        ),
        actions=[
            {"label": "Mostly qualified", "value": "qualified_divs"},
            {"label": "Mostly ordinary / not sure", "value": "ordinary_divs"},
            {"label": "Skip", "value": "skip_divs"},
        ],
        eligibility=lambda p: (
            (has_investments(p) or is_investor(p))
            and p.get("investment_income")
            and float(p.get("investment_income", 0) or 0) > 10000
            and not p.get("dividend_type")
        ),
        base_score=42,
        sets_fields=["dividend_type"],
        asked_field="_asked_qualified_divs",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — RETIREMENT & SOCIAL SECURITY  (8 questions)
# ═══════════════════════════════════════════════════════════════════════════════

RETIREMENT = [
    # Q-29  Retirement contributions (non-retired)
    FlowQuestion(
        id="ret_contributions",
        pool="retirement", phase=2,
        text="Are you contributing to any retirement accounts?",
        actions=[
            {"label": "401(k) / 403(b) / TSP", "value": "has_401k"},
            {"label": "Traditional IRA", "value": "has_trad_ira"},
            {"label": "Roth IRA", "value": "has_roth_ira"},
            {"label": "Both employer plan and IRA", "value": "has_both_retirement"},
            {"label": "SEP-IRA (self-employed)", "value": "has_sep"},
            {"label": "Solo 401(k) (self-employed)", "value": "has_solo_401k"},
            {"label": "No retirement contributions", "value": "no_retirement"},
            {"label": "Skip", "value": "skip_retirement"},
        ],
        eligibility=lambda p: (
            not is_retired(p)
            and not p.get("retirement_401k")
            and not p.get("retirement_ira")
        ),
        base_score=60,
        context_boost_keywords=["401k", "ira", "retire", "saving", "roth", "tsp"],
        sets_fields=["retirement_401k", "retirement_ira"],
        asked_field="_asked_retirement",
    ),
    # Q-30  HSA
    FlowQuestion(
        id="ret_hsa",
        pool="retirement", phase=2,
        text=(
            "Do you have a Health Savings Account (HSA)? Contributions are "
            "triple tax-advantaged — deductible, grow tax-free, and withdraw "
            "tax-free for medical expenses."
        ),
        actions=[
            {"label": "Yes, I contribute to an HSA", "value": "has_hsa"},
            {"label": "I have an HDHP but no HSA yet", "value": "has_hdhp_no_hsa"},
            {"label": "No HSA / not eligible", "value": "no_hsa"},
            {"label": "Skip", "value": "skip_hsa"},
        ],
        eligibility=lambda p: not p.get("hsa_contributions"),
        base_score=50,
        context_boost_keywords=["hsa", "health savings", "hdhp", "high deductible"],
        sets_fields=["hsa_contributions"],
        asked_field="_asked_hsa",
    ),
    # Q-31  Social Security benefits (retired)
    FlowQuestion(
        id="ret_ss_benefits",
        pool="retirement", phase=2,
        text=(
            "Did you receive Social Security benefits this year? "
            "If so, approximately how much?"
        ),
        actions=[
            {"label": "Under $15,000", "value": "ss_under_15k"},
            {"label": "$15,000 – $30,000", "value": "ss_15_30k"},
            {"label": "Over $30,000", "value": "ss_over_30k"},
            {"label": "Not receiving SS yet", "value": "no_ss"},
            {"label": "Skip", "value": "skip_ss"},
        ],
        eligibility=lambda p: is_retired(p) and not p.get("ss_benefits"),
        base_score=88,
        sets_fields=["ss_benefits"],
        asked_field="_asked_ss",
    ),
    # Q-32  Pension income (retired)
    FlowQuestion(
        id="ret_pension",
        pool="retirement", phase=2,
        text="Do you receive pension income?",
        actions=[
            {"label": "Yes — fully taxable", "value": "pension_taxable"},
            {"label": "Yes — partially taxable (after-tax contributions)", "value": "pension_partial"},
            {"label": "No pension", "value": "no_pension"},
            {"label": "Skip", "value": "skip_pension"},
        ],
        eligibility=lambda p: is_retired(p) and not p.get("pension_income"),
        base_score=86,
        sets_fields=["pension_income"],
        asked_field="_asked_pension",
    ),
    # Q-33  IRA / 401k distributions
    FlowQuestion(
        id="ret_distributions",
        pool="retirement", phase=2,
        text=(
            "Did you take any distributions (withdrawals) from retirement "
            "accounts this year?"
        ),
        actions=[
            {"label": "Yes — IRA withdrawal", "value": "ira_distribution"},
            {"label": "Yes — 401(k) withdrawal", "value": "401k_distribution"},
            {"label": "Yes — Roth conversion", "value": "roth_conversion"},
            {"label": "No distributions", "value": "no_distributions"},
            {"label": "Skip", "value": "skip_distributions"},
        ],
        eligibility=lambda p: not p.get("retirement_distributions"),
        base_score=40,
        context_boost_keywords=[
            "withdraw", "distribution", "rmd", "rollover", "conversion",
        ],
        sets_fields=["retirement_distributions"],
        asked_field="_asked_distributions",
    ),
    # Q-34  Early withdrawal penalty
    FlowQuestion(
        id="ret_early_withdrawal",
        pool="retirement", phase=2,
        text=(
            "Are you under age 59½? Early withdrawals may incur a 10% penalty "
            "unless an exception applies."
        ),
        actions=[
            {"label": "Under 59½ — no exception", "value": "early_no_exception"},
            {"label": "Under 59½ — exception applies", "value": "early_with_exception"},
            {"label": "59½ or older", "value": "over_59_half"},
            {"label": "Skip", "value": "skip_early"},
        ],
        eligibility=lambda p: (
            p.get("retirement_distributions")
            in ("ira_distribution", "401k_distribution")
            and not p.get("early_withdrawal_status")
        ),
        base_score=75,
        sets_fields=["early_withdrawal_status"],
        asked_field="_asked_early_withdrawal",
        follow_up_of="ret_distributions",
    ),
    # Q-35  RMD (required minimum distributions)
    FlowQuestion(
        id="ret_rmd",
        pool="retirement", phase=2,
        text=(
            "Are you 73 or older? You're required to take minimum "
            "distributions (RMDs). Have you taken yours?"
        ),
        actions=[
            {"label": "Yes — I've taken my RMD", "value": "rmd_taken"},
            {"label": "Not yet — need to before year-end", "value": "rmd_pending"},
            {"label": "Under 73 — RMD not required", "value": "under_73"},
            {"label": "Skip", "value": "skip_rmd"},
        ],
        eligibility=lambda p: (
            is_retired(p)
            and is_senior(p)
            and not p.get("rmd_status")
        ),
        base_score=82,
        sets_fields=["rmd_status"],
        asked_field="_asked_rmd",
    ),
    # Q-36  Roth conversion (strategy)
    FlowQuestion(
        id="ret_roth_conversion",
        pool="retirement", phase=2,
        text=(
            "Have you done or are you considering a Roth conversion this year? "
            "(Moving pre-tax IRA / 401k money into a Roth — taxable now, "
            "but tax-free growth forever)"
        ),
        actions=[
            {"label": "Yes — already converted", "value": "roth_converted"},
            {"label": "Considering it", "value": "roth_considering"},
            {"label": "No / Not interested", "value": "no_roth_conversion"},
            {"label": "Skip", "value": "skip_roth_conversion"},
        ],
        eligibility=lambda p: (
            (p.get("retirement_401k") or p.get("retirement_ira") or is_retired(p))
            and _income(p) > 100000
            and not p.get("roth_conversion_status")
        ),
        base_score=35,
        context_boost_keywords=["roth", "conversion", "backdoor"],
        context_boost_amount=30,
        sets_fields=["roth_conversion_status"],
        asked_field="_asked_roth_conversion",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — DEPENDENTS & CHILDREN  (7 questions)
# ═══════════════════════════════════════════════════════════════════════════════

DEPENDENTS = [
    # Q-37  Dependent age split
    FlowQuestion(
        id="dep_age_split",
        pool="dependents", phase=2,
        text=(
            "Of your {dependents} dependent(s), how many are under age 17? "
            "(Important for the Child Tax Credit — $2,000 per child under 17)"
        ),
        actions=[],  # Dynamic — built at runtime based on count
        eligibility=lambda p: has_dependents(p) and p.get("dependents_under_17") is None,
        base_score=85,
        sets_fields=["dependents_under_17"],
        asked_field="_asked_dependents_age",
    ),
    # Q-38  Childcare costs
    FlowQuestion(
        id="dep_childcare_costs",
        pool="dependents", phase=2,
        text=(
            "Did you pay for childcare or daycare so you (and your spouse) "
            "could work? This may qualify for the Child and Dependent Care Credit."
        ),
        actions=[
            {"label": "Yes — under $3,000 total", "value": "childcare_under_3k"},
            {"label": "Yes — $3,000 – $6,000", "value": "childcare_3_6k"},
            {"label": "Yes — over $6,000", "value": "childcare_over_6k"},
            {"label": "No childcare costs", "value": "no_childcare"},
            {"label": "Skip", "value": "skip_childcare"},
        ],
        eligibility=lambda p: has_young_dependents(p) and not p.get("childcare_costs"),
        base_score=78,
        context_boost_keywords=[
            "daycare", "childcare", "nanny", "babysitter", "preschool",
        ],
        sets_fields=["childcare_costs"],
        asked_field="_asked_childcare",
    ),
    # Q-39  Dependent care FSA
    FlowQuestion(
        id="dep_care_fsa",
        pool="dependents", phase=2,
        text=(
            "Did you or your employer contribute to a Dependent Care FSA? "
            "(Up to $5,000 pre-tax for childcare)"
        ),
        actions=[
            {"label": "Yes", "value": "has_dcfsa"},
            {"label": "No", "value": "no_dcfsa"},
            {"label": "Skip", "value": "skip_dcfsa"},
        ],
        eligibility=lambda p: (
            p.get("childcare_costs")
            and p.get("childcare_costs") != "no_childcare"
            and not p.get("dependent_care_fsa")
        ),
        base_score=72,
        sets_fields=["dependent_care_fsa"],
        asked_field="_asked_dcfsa",
        follow_up_of="dep_childcare_costs",
    ),
    # Q-40  Education
    FlowQuestion(
        id="dep_education",
        pool="dependents", phase=2,
        text=(
            "Did you or a dependent attend college or vocational school? "
            "Tuition may qualify for education credits (up to $2,500)."
        ),
        actions=[
            {"label": "Yes — I'm a student", "value": "self_student"},
            {"label": "Yes — my dependent is a student", "value": "dependent_student"},
            {"label": "Yes — both", "value": "both_students"},
            {"label": "No", "value": "no_education"},
            {"label": "Skip", "value": "skip_education"},
        ],
        eligibility=lambda p: (
            not p.get("education_status")
            and _income(p) < 180000
        ),
        base_score=55,
        context_boost_keywords=[
            "college", "university", "tuition", "student", "1098-t", "education",
        ],
        sets_fields=["education_status"],
        asked_field="_asked_education",
    ),
    # Q-41  529 plan
    FlowQuestion(
        id="dep_529_plan",
        pool="dependents", phase=2,
        text=(
            "Did you contribute to a 529 college savings plan? "
            "(Many states offer a tax deduction for contributions)"
        ),
        actions=[
            {"label": "Yes", "value": "has_529"},
            {"label": "No", "value": "no_529"},
            {"label": "Skip", "value": "skip_529"},
        ],
        eligibility=lambda p: (
            has_dependents(p)
            and not is_no_income_tax_state(p)
            and not p.get("has_529")
        ),
        base_score=30,
        context_boost_keywords=["529", "college savings", "education savings"],
        sets_fields=["has_529"],
        asked_field="_asked_529",
    ),
    # Q-42  Adoption
    FlowQuestion(
        id="dep_adoption",
        pool="dependents", phase=2,
        text=(
            "Did you adopt a child this year? Adoption expenses may qualify "
            "for a credit up to $16,810."
        ),
        actions=[
            {"label": "Yes — domestic adoption", "value": "adoption_domestic"},
            {"label": "Yes — international adoption", "value": "adoption_international"},
            {"label": "Yes — special needs child", "value": "adoption_special_needs"},
            {"label": "No", "value": "no_adoption"},
        ],
        eligibility=lambda p: has_dependents(p) and not p.get("adoption_status"),
        base_score=12,
        context_boost_keywords=["adopt", "adoption"],
        context_boost_amount=50,
        sets_fields=["adoption_status"],
        asked_field="_asked_adoption",
    ),
    # Q-43  Custody (divorced parents)
    FlowQuestion(
        id="dep_custody",
        pool="dependents", phase=2,
        text=(
            "Are you a divorced or separated parent? If so, who claims "
            "the children on their tax return?"
        ),
        actions=[
            {"label": "I claim all children", "value": "custody_self"},
            {"label": "Ex-spouse claims them", "value": "custody_ex"},
            {"label": "We split (Form 8332)", "value": "custody_split"},
            {"label": "Not applicable", "value": "custody_na"},
            {"label": "Skip", "value": "skip_custody"},
        ],
        eligibility=lambda p: (
            is_single_or_hoh(p)
            and has_dependents(p)
            and not p.get("custody_status")
        ),
        base_score=20,
        context_boost_keywords=["divorce", "custody", "ex-spouse", "separated"],
        context_boost_amount=40,
        sets_fields=["custody_status"],
        asked_field="_asked_custody",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — DEDUCTIONS  (8 questions)
# ═══════════════════════════════════════════════════════════════════════════════

DEDUCTIONS = [
    # Q-44  Major deductions check
    FlowQuestion(
        id="ded_major_deductions",
        pool="deductions", phase=2,
        text="Let's check your deductions. Do you have any of these?",
        actions=[
            {"label": "Mortgage interest", "value": "has_mortgage"},
            {"label": "Charitable donations", "value": "has_charitable"},
            {"label": "Property taxes", "value": "has_property_taxes"},
            {"label": "High medical expenses", "value": "has_medical"},
            {"label": "State/local income taxes paid", "value": "has_salt"},
            {"label": "None — I'll take the standard deduction", "value": "no_itemized_deductions"},
            {"label": "Skip", "value": "skip_deductions"},
        ],
        eligibility=lambda p: (
            not p.get("mortgage_interest")
            and not p.get("_asked_deductions")
            and not p.get("_deduction_check")
        ),
        base_score=55,
        context_boost_keywords=[
            "mortgage", "house", "deduct", "charit", "donat", "property tax", "itemiz",
        ],
        sets_fields=["_deduction_check"],
        asked_field="_asked_deductions",
    ),
    # Q-45  Mortgage amount
    FlowQuestion(
        id="ded_mortgage_amount",
        pool="deductions", phase=2,
        text="How much mortgage interest did you pay this year? (Check Form 1098)",
        actions=[
            {"label": "Under $5,000", "value": "mortgage_under_5k"},
            {"label": "$5,000 – $15,000", "value": "mortgage_5_15k"},
            {"label": "$15,000 – $30,000", "value": "mortgage_15_30k"},
            {"label": "Over $30,000", "value": "mortgage_over_30k"},
            {"label": "Skip", "value": "skip_mortgage_amount"},
        ],
        eligibility=lambda p: p.get("_has_mortgage") and not p.get("mortgage_interest"),
        base_score=52,
        sets_fields=["mortgage_interest"],
        asked_field="_asked_mortgage_amount",
        follow_up_of="ded_major_deductions",
    ),
    # Q-46  Property taxes
    FlowQuestion(
        id="ded_property_taxes",
        pool="deductions", phase=2,
        text="How much did you pay in property taxes?",
        actions=[
            {"label": "Under $5,000", "value": "prop_tax_under_5k"},
            {"label": "$5,000 – $10,000", "value": "prop_tax_5_10k"},
            {"label": "Over $10,000 (SALT cap applies)", "value": "prop_tax_over_10k"},
            {"label": "Skip", "value": "skip_prop_tax_amount"},
        ],
        eligibility=lambda p: p.get("_has_property_taxes") and not p.get("property_taxes"),
        base_score=51,
        sets_fields=["property_taxes"],
        asked_field="_asked_prop_tax_amount",
        follow_up_of="ded_major_deductions",
    ),
    # Q-47  Charitable donations
    FlowQuestion(
        id="ded_charitable",
        pool="deductions", phase=2,
        text="How much did you donate to charity this year?",
        actions=[
            {"label": "Under $1,000", "value": "charity_under_1k"},
            {"label": "$1,000 – $5,000", "value": "charity_1_5k"},
            {"label": "$5,000 – $20,000", "value": "charity_5_20k"},
            {"label": "Over $20,000", "value": "charity_over_20k"},
            {"label": "Skip", "value": "skip_charitable_amount"},
        ],
        eligibility=lambda p: p.get("_has_charitable") and not p.get("charitable_donations"),
        base_score=50,
        sets_fields=["charitable_donations"],
        asked_field="_asked_charitable_amount",
        follow_up_of="ded_major_deductions",
    ),
    # Q-48  Medical expenses
    FlowQuestion(
        id="ded_medical",
        pool="deductions", phase=2,
        text=(
            "Approximately how much in unreimbursed medical expenses? "
            "(Only deductible if over 7.5% of your income)"
        ),
        actions=[
            {"label": "Under $5,000", "value": "medical_under_5k"},
            {"label": "$5,000 – $15,000", "value": "medical_5_15k"},
            {"label": "$15,000 – $30,000", "value": "medical_15_30k"},
            {"label": "Over $30,000", "value": "medical_over_30k"},
            {"label": "Skip", "value": "skip_medical_amount"},
        ],
        eligibility=lambda p: p.get("_has_medical") and not p.get("medical_expenses"),
        base_score=49,
        sets_fields=["medical_expenses"],
        asked_field="_asked_medical_amount",
        follow_up_of="ded_major_deductions",
    ),
    # Q-49  Student loans
    FlowQuestion(
        id="ded_student_loans",
        pool="deductions", phase=2,
        text=(
            "Did you pay any student loan interest this year? "
            "(Up to $2,500 may be deductible)"
        ),
        actions=[
            {"label": "Yes", "value": "has_student_loans"},
            {"label": "No student loans", "value": "no_student_loans"},
            {"label": "Skip", "value": "skip_student_loans"},
        ],
        eligibility=lambda p: (
            not p.get("student_loan_interest")
            and _income(p) < 180000
        ),
        base_score=25,
        context_boost_keywords=["student", "loan", "college"],
        sets_fields=["student_loan_interest"],
        asked_field="_asked_student_loans",
    ),
    # Q-50  Educator expenses
    FlowQuestion(
        id="ded_educator",
        pool="deductions", phase=2,
        text=(
            "Are you a K-12 teacher or educator? You may deduct up to $300 "
            "in classroom supplies."
        ),
        actions=[
            {"label": "Yes — I'm an educator", "value": "is_educator"},
            {"label": "No", "value": "not_educator"},
        ],
        eligibility=lambda p: is_w2_employee(p) and not p.get("educator_expenses"),
        base_score=12,
        context_boost_keywords=["teacher", "educator", "school", "classroom"],
        context_boost_amount=45,
        sets_fields=["educator_expenses"],
        asked_field="_asked_educator",
    ),
    # Q-51  State & local taxes (SALT) — if itemizing
    FlowQuestion(
        id="ded_state_local_taxes",
        pool="deductions", phase=2,
        text=(
            "How much did you pay in state and local income taxes? "
            "(Combined with property taxes, capped at $10,000)"
        ),
        actions=[
            {"label": "Under $5,000", "value": "salt_under_5k"},
            {"label": "$5,000 – $10,000", "value": "salt_5_10k"},
            {"label": "Over $10,000 (SALT cap)", "value": "salt_over_10k"},
            {"label": "Skip", "value": "skip_salt"},
        ],
        eligibility=lambda p: (
            p.get("_has_salt")
            and not is_no_income_tax_state(p)
            and not p.get("state_local_taxes")
        ),
        base_score=48,
        sets_fields=["state_local_taxes"],
        asked_field="_asked_salt",
        follow_up_of="ded_major_deductions",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — LIFE EVENTS  (5 questions)
# ═══════════════════════════════════════════════════════════════════════════════

LIFE_EVENTS = [
    # Q-52  Life events check
    FlowQuestion(
        id="life_events",
        pool="life_events", phase=2,
        text=(
            "Did any major life changes happen this year? "
            "These can significantly affect your taxes."
        ),
        actions=[
            {"label": "Got married", "value": "event_married"},
            {"label": "Got divorced / separated", "value": "event_divorced"},
            {"label": "Had a baby / adopted", "value": "event_baby"},
            {"label": "Bought a home", "value": "event_bought_home"},
            {"label": "Sold a home", "value": "event_sold_home"},
            {"label": "Changed jobs", "value": "event_job_change"},
            {"label": "Lost a job", "value": "event_job_loss"},
            {"label": "Started a business", "value": "event_started_biz"},
            {"label": "Moved to a different state", "value": "event_moved_states"},
            {"label": "Retired this year", "value": "event_retired"},
            {"label": "Received an inheritance", "value": "event_inheritance"},
            {"label": "None of these", "value": "no_life_events"},
            {"label": "Skip", "value": "skip_life_events"},
        ],
        eligibility=lambda p: not p.get("life_events"),
        base_score=70,
        context_boost_keywords=[
            "married", "divorced", "baby", "bought", "sold", "moved",
            "new job", "retired", "inherited",
        ],
        sets_fields=["life_events"],
        asked_field="_asked_life_events",
    ),
    # Q-53  Home sale follow-up
    FlowQuestion(
        id="life_home_sale",
        pool="life_events", phase=2,
        text=(
            "For the home you sold — did you live in it for at least 2 of "
            "the last 5 years? (Up to $250K / $500K gain may be tax-free)"
        ),
        actions=[
            {"label": "Yes — primary residence 2+ years", "value": "home_sale_excluded"},
            {"label": "No — investment property or < 2 years", "value": "home_sale_taxable"},
            {"label": "Skip", "value": "skip_home_sale"},
        ],
        eligibility=lambda p: (
            p.get("life_events") == "event_sold_home"
            and not p.get("home_sale_exclusion")
        ),
        base_score=80,
        sets_fields=["home_sale_exclusion"],
        asked_field="_asked_home_sale",
        follow_up_of="life_events",
    ),
    # Q-54  State move follow-up
    FlowQuestion(
        id="life_state_move",
        pool="life_events", phase=2,
        text=(
            "When did you move, and which state did you move from? "
            "(You may need to file part-year returns in both states)"
        ),
        actions=[
            {"label": "Moved in first half of year", "value": "moved_h1"},
            {"label": "Moved in second half of year", "value": "moved_h2"},
            {"label": "Skip", "value": "skip_state_move"},
        ],
        eligibility=lambda p: (
            p.get("life_events") == "event_moved_states"
            and not p.get("move_date")
        ),
        base_score=78,
        sets_fields=["move_date"],
        asked_field="_asked_state_move",
        follow_up_of="life_events",
    ),
    # Q-55  Job loss follow-up
    FlowQuestion(
        id="life_job_loss",
        pool="life_events", phase=2,
        text="Did you receive unemployment benefits or severance pay?",
        actions=[
            {"label": "Unemployment benefits", "value": "had_unemployment"},
            {"label": "Severance pay", "value": "had_severance"},
            {"label": "Both", "value": "had_both_unemployment_severance"},
            {"label": "Neither", "value": "no_unemployment"},
            {"label": "Skip", "value": "skip_job_loss"},
        ],
        eligibility=lambda p: (
            p.get("life_events") == "event_job_loss"
            and not p.get("unemployment_income")
        ),
        base_score=76,
        sets_fields=["unemployment_income"],
        asked_field="_asked_job_loss",
        follow_up_of="life_events",
    ),
    # Q-56  New business follow-up
    FlowQuestion(
        id="life_new_business",
        pool="life_events", phase=2,
        text=(
            "Congratulations on starting a business! Did you have startup "
            "costs? (Up to $5,000 may be deductible in year one)"
        ),
        actions=[
            {"label": "Yes — under $5,000", "value": "startup_under_5k"},
            {"label": "Yes — $5,000 – $50,000", "value": "startup_5_50k"},
            {"label": "Yes — over $50,000", "value": "startup_over_50k"},
            {"label": "No significant startup costs", "value": "no_startup_costs"},
            {"label": "Skip", "value": "skip_startup"},
        ],
        eligibility=lambda p: (
            p.get("life_events") == "event_started_biz"
            and not p.get("startup_costs")
        ),
        base_score=74,
        sets_fields=["startup_costs"],
        asked_field="_asked_startup",
        follow_up_of="life_events",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — RENTAL PROPERTY  (4 questions)
# ═══════════════════════════════════════════════════════════════════════════════

RENTAL_PROPERTY = [
    # Q-57  Has rental?
    FlowQuestion(
        id="rental_has",
        pool="rental_property", phase=2,
        text="Do you own any rental properties?",
        actions=[
            {"label": "Yes — 1 property", "value": "rental_1"},
            {"label": "Yes — 2-4 properties", "value": "rental_2_4"},
            {"label": "Yes — 5+ properties", "value": "rental_5plus"},
            {"label": "No rental properties", "value": "no_rental"},
            {"label": "Skip", "value": "skip_rental"},
        ],
        eligibility=lambda p: (
            not p.get("_has_rental")
            and not is_low_income_w2_only(p)
        ),
        base_score=35,
        context_boost_keywords=["rent", "landlord", "property", "tenant"],
        sets_fields=["_has_rental"],
        asked_field="_asked_rental",
    ),
    # Q-58  Rental income amount
    FlowQuestion(
        id="rental_income_amount",
        pool="rental_property", phase=2,
        text=(
            "What's your approximate annual net rental income (after expenses)?"
        ),
        actions=[
            {"label": "Under $10,000 profit", "value": "rental_under_10k"},
            {"label": "$10,000 – $25,000", "value": "rental_10_25k"},
            {"label": "$25,000 – $50,000", "value": "rental_25_50k"},
            {"label": "Over $50,000", "value": "rental_over_50k"},
            {"label": "Net loss", "value": "rental_net_loss"},
            {"label": "Skip", "value": "skip_rental_amount"},
        ],
        eligibility=lambda p: has_rental(p) and not p.get("rental_income"),
        base_score=55,
        sets_fields=["rental_income"],
        asked_field="_asked_rental_amount",
        follow_up_of="rental_has",
    ),
    # Q-59  Participation status
    FlowQuestion(
        id="rental_participation",
        pool="rental_property", phase=2,
        text=(
            "Do you actively participate in managing your rentals? "
            "(Make decisions, approve tenants, authorize repairs)"
        ),
        actions=[
            {"label": "Yes — I actively manage them", "value": "active_participation"},
            {"label": "I use a property manager for everything", "value": "passive_participation"},
            {"label": "I'm a real estate professional (750+ hrs)", "value": "re_professional"},
            {"label": "Skip", "value": "skip_participation"},
        ],
        eligibility=lambda p: (
            p.get("rental_income") and not p.get("rental_participation")
        ),
        base_score=52,
        sets_fields=["rental_participation"],
        asked_field="_asked_participation",
        follow_up_of="rental_income_amount",
    ),
    # Q-60  Depreciation
    FlowQuestion(
        id="rental_depreciation",
        pool="rental_property", phase=2,
        text=(
            "Are you claiming depreciation on your rental properties? "
            "(Residential rentals depreciate over 27.5 years)"
        ),
        actions=[
            {"label": "Yes — already depreciating", "value": "has_depreciation"},
            {"label": "No — haven't started", "value": "no_depreciation"},
            {"label": "Not sure", "value": "depreciation_unsure"},
            {"label": "Skip", "value": "skip_depreciation"},
        ],
        eligibility=lambda p: (
            p.get("rental_income")
            and _income(p) > 100000
            and not p.get("rental_depreciation")
        ),
        base_score=46,
        sets_fields=["rental_depreciation"],
        asked_field="_asked_depreciation",
        follow_up_of="rental_income_amount",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — K-1 / PARTNERSHIP  (2 questions)
# ═══════════════════════════════════════════════════════════════════════════════

K1_PARTNERSHIP = [
    # Q-61  Has K-1?
    FlowQuestion(
        id="k1_has",
        pool="k1_partnership", phase=2,
        text=(
            "Do you receive any K-1 income from partnerships, "
            "S-corporations, or trusts?"
        ),
        actions=[
            {"label": "Yes, I have K-1 income", "value": "has_k1_income"},
            {"label": "No K-1 income", "value": "no_k1_income"},
            {"label": "Skip", "value": "skip_k1"},
        ],
        eligibility=lambda p: (
            not p.get("_has_k1")
            and not p.get("k1_ordinary_income")
            and not is_low_income_w2_only(p)
        ),
        base_score=25,
        context_boost_keywords=["k-1", "k1", "partner", "s-corp", "trust"],
        context_boost_amount=35,
        sets_fields=["_has_k1"],
        asked_field="_asked_k1",
    ),
    # Q-62  K-1 amount
    FlowQuestion(
        id="k1_amount",
        pool="k1_partnership", phase=2,
        text="What's your approximate K-1 ordinary income?",
        actions=[
            {"label": "Under $25,000", "value": "k1_under_25k"},
            {"label": "$25,000 – $100,000", "value": "k1_25_100k"},
            {"label": "$100,000 – $250,000", "value": "k1_100_250k"},
            {"label": "Over $250,000", "value": "k1_over_250k"},
            {"label": "Skip", "value": "skip_k1_amount"},
        ],
        eligibility=lambda p: has_k1(p) and not p.get("k1_ordinary_income"),
        base_score=50,
        sets_fields=["k1_ordinary_income"],
        asked_field="_asked_k1_amount",
        follow_up_of="k1_has",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — HEALTHCARE  (2 questions)
# ═══════════════════════════════════════════════════════════════════════════════

HEALTHCARE = [
    # Q-63  ACA Marketplace
    FlowQuestion(
        id="hc_aca_marketplace",
        pool="healthcare", phase=2,
        text=(
            "Do you get health insurance through the ACA Marketplace "
            "(Healthcare.gov)? You may qualify for the Premium Tax Credit."
        ),
        actions=[
            {"label": "Yes — with subsidy", "value": "aca_with_subsidy"},
            {"label": "Yes — no subsidy", "value": "aca_no_subsidy"},
            {"label": "No — employer or other coverage", "value": "no_aca"},
            {"label": "Skip", "value": "skip_aca"},
        ],
        eligibility=lambda p: (
            not is_retired(p)
            and not p.get("aca_marketplace")
            and not p.get("se_health_insurance")
        ),
        base_score=28,
        context_boost_keywords=[
            "marketplace", "aca", "obamacare", "healthcare.gov", "subsidy",
            "premium tax credit",
        ],
        context_boost_amount=35,
        sets_fields=["aca_marketplace"],
        asked_field="_asked_aca",
    ),
    # Q-64  Medicare premiums (retired 65+)
    FlowQuestion(
        id="hc_medicare_premiums",
        pool="healthcare", phase=2,
        text=(
            "How much do you pay in Medicare premiums? "
            "(Part B / Part D — may be deductible or trigger IRMAA surcharge)"
        ),
        actions=[
            {"label": "Standard Part B only (~$185/mo)", "value": "medicare_standard"},
            {"label": "Part B + Part D", "value": "medicare_b_and_d"},
            {"label": "IRMAA surcharge (higher premiums)", "value": "medicare_irmaa"},
            {"label": "Skip", "value": "skip_medicare"},
        ],
        eligibility=lambda p: (
            is_retired(p) and is_senior(p) and not p.get("medicare_premiums")
        ),
        base_score=58,
        sets_fields=["medicare_premiums"],
        asked_field="_asked_medicare",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — SPECIAL SITUATIONS  (10 questions)
# ═══════════════════════════════════════════════════════════════════════════════

SPECIAL_SITUATIONS = [
    # Q-65  Estimated payments
    FlowQuestion(
        id="spec_estimated_payments",
        pool="special_situations", phase=2,
        text=(
            "Have you made any estimated tax payments this year? "
            "(Quarterly payments to the IRS)"
        ),
        actions=[
            {"label": "Yes", "value": "has_estimated_payments"},
            {"label": "No", "value": "no_estimated_payments"},
            {"label": "Skip", "value": "skip_estimated"},
        ],
        eligibility=lambda p: (
            (is_business_or_se(p) or _income(p) > 100000 or is_investor(p))
            and not p.get("_has_estimated_payments")
        ),
        base_score=45,
        context_boost_keywords=["estimated", "quarterly", "payment", "1040-es"],
        sets_fields=["_has_estimated_payments"],
        asked_field="_asked_estimated",
    ),
    # Q-66  Estimated amount
    FlowQuestion(
        id="spec_estimated_amount",
        pool="special_situations", phase=2,
        text="How much total in estimated tax payments this year?",
        actions=[
            {"label": "Under $5,000", "value": "est_under_5k"},
            {"label": "$5,000 – $15,000", "value": "est_5_15k"},
            {"label": "$15,000 – $30,000", "value": "est_15_30k"},
            {"label": "Over $30,000", "value": "est_over_30k"},
            {"label": "Skip", "value": "skip_est_amount"},
        ],
        eligibility=lambda p: (
            p.get("_has_estimated_payments") == "has_estimated_payments"
            and not p.get("estimated_payments")
        ),
        base_score=55,
        sets_fields=["estimated_payments"],
        asked_field="_asked_est_amount",
        follow_up_of="spec_estimated_payments",
    ),
    # Q-67  Energy credits
    FlowQuestion(
        id="spec_energy_credits",
        pool="special_situations", phase=2,
        text=(
            "Did you make any energy-efficient home improvements or "
            "purchase an electric vehicle?"
        ),
        actions=[
            {"label": "Installed solar panels", "value": "has_solar"},
            {"label": "Bought an electric vehicle", "value": "has_ev"},
            {"label": "Home energy improvements (insulation, windows, heat pump)", "value": "has_energy_improvements"},
            {"label": "Multiple", "value": "multiple_energy"},
            {"label": "None", "value": "no_energy"},
            {"label": "Skip", "value": "skip_energy"},
        ],
        eligibility=lambda p: not p.get("energy_credits"),
        base_score=22,
        context_boost_keywords=[
            "solar", "ev", "electric vehicle", "tesla", "energy", "heat pump",
        ],
        context_boost_amount=40,
        sets_fields=["energy_credits"],
        asked_field="_asked_energy",
    ),
    # Q-68  Foreign income
    FlowQuestion(
        id="spec_foreign_income",
        pool="special_situations", phase=2,
        text=(
            "Did you earn any income from outside the United States "
            "or pay foreign taxes?"
        ),
        actions=[
            {"label": "Yes — worked abroad", "value": "worked_abroad"},
            {"label": "Yes — foreign investment income / taxes paid", "value": "foreign_investments"},
            {"label": "No foreign income", "value": "no_foreign"},
            {"label": "Skip", "value": "skip_foreign"},
        ],
        eligibility=lambda p: (
            not p.get("foreign_income") and _income(p) > 50000
        ),
        base_score=15,
        context_boost_keywords=[
            "foreign", "abroad", "overseas", "international", "expat",
        ],
        context_boost_amount=45,
        sets_fields=["foreign_income"],
        asked_field="_asked_foreign",
    ),
    # Q-69  Foreign accounts (follow-up)
    FlowQuestion(
        id="spec_foreign_accounts",
        pool="special_situations", phase=2,
        text=(
            "Did you have foreign bank or financial accounts with a "
            "combined value over $10,000 at any point? (FBAR / FATCA reporting)"
        ),
        actions=[
            {"label": "Yes", "value": "has_foreign_accounts"},
            {"label": "No", "value": "no_foreign_accounts"},
            {"label": "Skip", "value": "skip_foreign_accounts"},
        ],
        eligibility=lambda p: (
            p.get("foreign_income")
            and p.get("foreign_income") not in ("no_foreign",)
            and not p.get("foreign_accounts")
        ),
        base_score=60,
        sets_fields=["foreign_accounts"],
        asked_field="_asked_foreign_accounts",
        follow_up_of="spec_foreign_income",
    ),
    # Q-70  Alimony
    FlowQuestion(
        id="spec_alimony",
        pool="special_situations", phase=2,
        text=(
            "Do you pay or receive alimony under a divorce agreement "
            "finalized before 2019? (Post-2018: not deductible/taxable)"
        ),
        actions=[
            {"label": "I pay alimony (pre-2019)", "value": "pays_alimony"},
            {"label": "I receive alimony (pre-2019)", "value": "receives_alimony"},
            {"label": "Post-2018 agreement / N/A", "value": "no_alimony"},
            {"label": "Skip", "value": "skip_alimony"},
        ],
        eligibility=lambda p: (
            is_single_or_hoh(p) and not p.get("alimony_status")
        ),
        base_score=10,
        context_boost_keywords=[
            "alimony", "divorce", "ex-spouse", "spousal support",
        ],
        context_boost_amount=50,
        sets_fields=["alimony_status"],
        asked_field="_asked_alimony",
    ),
    # Q-71  Gambling
    FlowQuestion(
        id="spec_gambling",
        pool="special_situations", phase=2,
        text=(
            "Did you have any gambling winnings or losses? "
            "(Casino, lottery, sports betting — all taxable)"
        ),
        actions=[
            {"label": "Yes — net winnings", "value": "gambling_winnings"},
            {"label": "Yes — but net losses", "value": "gambling_losses"},
            {"label": "No gambling", "value": "no_gambling"},
            {"label": "Skip", "value": "skip_gambling"},
        ],
        eligibility=lambda p: not p.get("gambling_income"),
        base_score=8,
        context_boost_keywords=[
            "gambling", "casino", "lottery", "sports bet", "w-2g",
        ],
        context_boost_amount=50,
        sets_fields=["gambling_income"],
        asked_field="_asked_gambling",
    ),
    # Q-72  Military — combat zone
    FlowQuestion(
        id="spec_military_combat",
        pool="special_situations", phase=2,
        text=(
            "Were you deployed to a combat zone? "
            "Combat pay may be tax-exempt."
        ),
        actions=[
            {"label": "Yes — combat zone deployment", "value": "combat_zone"},
            {"label": "No deployment", "value": "no_combat"},
            {"label": "Skip", "value": "skip_military_combat"},
        ],
        eligibility=lambda p: is_military(p) and not p.get("combat_zone"),
        base_score=85,
        sets_fields=["combat_zone"],
        asked_field="_asked_military_combat",
    ),
    # Q-73  Military — PCS move
    FlowQuestion(
        id="spec_military_pcs",
        pool="special_situations", phase=2,
        text=(
            "Did you have a Permanent Change of Station (PCS) move? "
            "Military moving expenses are still deductible."
        ),
        actions=[
            {"label": "Yes — PCS move", "value": "pcs_move"},
            {"label": "No PCS this year", "value": "no_pcs"},
            {"label": "Skip", "value": "skip_pcs"},
        ],
        eligibility=lambda p: is_military(p) and not p.get("pcs_move"),
        base_score=75,
        sets_fields=["pcs_move"],
        asked_field="_asked_pcs",
    ),
    # Q-74  Household employee (nanny tax)
    FlowQuestion(
        id="spec_household_employee",
        pool="special_situations", phase=2,
        text=(
            "Did you pay a household employee (nanny, housekeeper, caregiver) "
            "more than $2,700? You may owe 'nanny tax' (Schedule H)."
        ),
        actions=[
            {"label": "Yes", "value": "has_household_employee"},
            {"label": "No", "value": "no_household_employee"},
            {"label": "Skip", "value": "skip_household"},
        ],
        eligibility=lambda p: (
            _income(p) > 100000
            and has_dependents(p)
            and not p.get("household_employee")
        ),
        base_score=18,
        context_boost_keywords=["nanny", "housekeeper", "caregiver", "au pair"],
        context_boost_amount=40,
        sets_fields=["household_employee"],
        asked_field="_asked_household",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — STATE-SPECIFIC  (2 questions)
# ═══════════════════════════════════════════════════════════════════════════════

MISSING_COVERAGE = [
    # Q-77  Farm income (Schedule F)
    FlowQuestion(
        id="spec_farm_income",
        pool="special_situations", phase=2,
        text=(
            "Do you have any farm income or agricultural activity? "
            "(Crop sales, livestock, CRP payments, farm rental)"
        ),
        actions=[
            {"label": "Yes — active farming", "value": "active_farm"},
            {"label": "Yes — farm rental income", "value": "farm_rental"},
            {"label": "No farm income", "value": "no_farm"},
            {"label": "Skip", "value": "skip_farm"},
        ],
        eligibility=lambda p: not p.get("farm_income"),
        base_score=6,
        context_boost_keywords=[
            "farm", "agriculture", "crop", "livestock", "ranch",
        ],
        context_boost_amount=55,
        sets_fields=["farm_income"],
        asked_field="_asked_farm",
    ),
    # Q-78  Kiddie tax (Form 8615)
    FlowQuestion(
        id="spec_kiddie_tax",
        pool="special_situations", phase=2,
        text=(
            "Does any of your children (under 19, or under 24 if student) "
            "have investment income over $2,500? This may trigger the 'kiddie tax'."
        ),
        actions=[
            {"label": "Yes — child has investment income", "value": "has_kiddie_tax"},
            {"label": "No", "value": "no_kiddie_tax"},
            {"label": "Skip", "value": "skip_kiddie_tax"},
        ],
        eligibility=lambda p: (
            has_dependents(p)
            and (has_investments(p) or _income(p) > 200000)
            and not p.get("kiddie_tax_status")
        ),
        base_score=14,
        context_boost_keywords=["kiddie", "child investment", "ugma", "utma"],
        context_boost_amount=45,
        sets_fields=["kiddie_tax_status"],
        asked_field="_asked_kiddie_tax",
    ),
    # Q-79  AMT trigger check (Form 6251)
    FlowQuestion(
        id="spec_amt_check",
        pool="special_situations", phase=2,
        text=(
            "Do any of these apply? They can trigger the Alternative Minimum Tax (AMT):\n"
            "• Exercised Incentive Stock Options (ISOs)\n"
            "• Large state/local tax deductions (>$10K)\n"
            "• Private activity bond interest"
        ),
        actions=[
            {"label": "Yes — exercised ISOs", "value": "amt_iso"},
            {"label": "Yes — large SALT deductions", "value": "amt_salt"},
            {"label": "Yes — multiple triggers", "value": "amt_multiple"},
            {"label": "None of these", "value": "no_amt_triggers"},
            {"label": "Skip", "value": "skip_amt"},
        ],
        eligibility=lambda p: (
            _income(p) > 150000
            and not p.get("amt_status")
        ),
        base_score=32,
        context_boost_keywords=["amt", "alternative minimum", "iso", "exercise"],
        context_boost_amount=35,
        sets_fields=["amt_status"],
        asked_field="_asked_amt",
    ),
]

STATE_SPECIFIC = [
    # Q-75  Multi-state income
    FlowQuestion(
        id="state_multi_state",
        pool="state_specific", phase=2,
        text=(
            "Did you earn income in a state other than your home state? "
            "(Out-of-state employer, business travel, remote work)"
        ),
        actions=[
            {"label": "Yes — income in another state", "value": "multi_state_income"},
            {"label": "No — all in my home state", "value": "single_state"},
            {"label": "Skip", "value": "skip_multi_state"},
        ],
        eligibility=lambda p: (
            not p.get("multi_state_income")
            and not is_no_income_tax_state(p)
        ),
        base_score=20,
        context_boost_keywords=[
            "remote", "travel", "commute", "another state", "multi-state",
        ],
        context_boost_amount=35,
        sets_fields=["multi_state_income"],
        asked_field="_asked_multi_state",
    ),
    # Q-76  Remote worker (convenience rule states)
    FlowQuestion(
        id="state_remote_worker",
        pool="state_specific", phase=2,
        text=(
            "Do you work remotely for an employer in a different state? "
            "Some states (NY, CT, PA) tax non-resident remote workers."
        ),
        actions=[
            {"label": "Yes — employer in a different state", "value": "remote_diff_state"},
            {"label": "No — employer in my state", "value": "same_state_employer"},
            {"label": "Skip", "value": "skip_remote"},
        ],
        eligibility=lambda p: (
            is_w2_employee(p)
            and _income(p) > 75000
            and not p.get("remote_worker_status")
            and not is_no_income_tax_state(p)
        ),
        base_score=18,
        context_boost_keywords=["remote", "work from home", "telecommute"],
        context_boost_amount=30,
        sets_fields=["remote_worker_status"],
        asked_field="_asked_remote",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# COMBINED REGISTRY  (all 76 questions)
# ═══════════════════════════════════════════════════════════════════════════════

ALL_QUESTIONS: list[FlowQuestion] = (
    BASICS
    + INCOME_DETAILS
    + SELF_EMPLOYMENT
    + INVESTMENTS
    + RETIREMENT
    + DEPENDENTS
    + DEDUCTIONS
    + LIFE_EVENTS
    + RENTAL_PROPERTY
    + K1_PARTNERSHIP
    + HEALTHCARE
    + SPECIAL_SITUATIONS
    + MISSING_COVERAGE
    + STATE_SPECIFIC
)
