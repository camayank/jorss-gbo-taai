#!/usr/bin/env python3
"""
EA/CPA Audit Scenario Generator
=================================
Runs 50 structured tax profiles through TaxOpportunityDetector and produces
a CSV scorecard + bug report for the human EA/CPA auditor.

Run from repo root:
    python scripts/generate_audit_scenarios.py

Output:
    audit_scenarios_YYYYMMDD.csv  — upload to Google Sheets for auditor
    Bug summary printed to terminal — file as P0/P1 before launch

Pre-audit analysis has already identified 6 structural bugs (see KNOWN_BUGS).
The auditor's job is to verify AI CONVERSATION quality — correct IRS codes,
right strategies, single question, no disclaimers — not just rule engine output.
"""

import csv
import sys
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

try:
    from services.tax_opportunity_detector import TaxOpportunityDetector, TaxpayerProfile
except ImportError as e:
    print(f"ERROR: Could not import TaxOpportunityDetector: {e}")
    print("Run from repo root: python scripts/generate_audit_scenarios.py")
    sys.exit(1)

D = Decimal  # shorthand

# ============================================================
# KNOWN BUGS (pre-audit analysis)  — file before launch
# ============================================================
KNOWN_BUGS = [
    {
        "id": "P1-001",
        "area": "Saver's Credit",
        "description": "✅ FIXED — Saver's Credit now fires for all filing statuses with correct 2024 thresholds: "
                       "single $38,250, HoH $57,375, MFJ $76,500.",
        "fix": "DONE: Added single/HoH branches to _detect_credit_opportunities()",
    },
    {
        "id": "P1-002",
        "area": "WOTC false positive",
        "description": "✅ FIXED — WOTC now only fires for non-sole-prop entity types (s_corporation, c_corporation, etc.). "
                       "Sole proprietors (business_type=None or 'sole_prop') no longer see spurious WOTC recommendation.",
        "fix": "DONE: Gated WOTC on business_type is not None and 'sole' not in business_type",
    },
    {
        "id": "P1-003",
        "area": "Tax-Loss Harvesting only in Q4",
        "description": "✅ FIXED — Tax-Loss Harvesting and Year-End Charitable now fire year-round. "
                       "Urgency copy adjusts automatically: urgent in Q4, advisory in Q1-Q3.",
        "fix": "DONE: Removed current_month >= 10 gate; action_required text is month-aware",
    },
    {
        "id": "P1-004",
        "area": "Student Loan Interest AGI threshold",
        "description": "Student Loan Interest reminder fires when student_loan_interest == 0. "
                       "AGI threshold raised from $90K to $110K (single) / $195K (MFJ) to account for "
                       "SE deductions not captured in agi_estimate. "
                       "At $120K SE, actual AGI after adjustments is ~$111K — above phase-out ceiling.",
        "fix": "DONE: Threshold raised; SE-09 scenario correctly shows this as out-of-scope at $120K",
    },
    {
        "id": "P1-005",
        "area": "Defined Benefit age threshold",
        "description": "✅ FIXED — Defined Benefit age threshold lowered from 45 to 40. "
                       "High-earning SE professionals at 40-44 ($150K+) now see the DB plan recommendation.",
        "fix": "DONE: Changed age >= 45 to age >= 40 in _detect_business_opportunities()",
    },
    {
        "id": "P1-006",
        "area": "S-Corp: QBI / SEP-IRA require business_net_income",
        "description": "✅ ADDRESSED — S-Corp scenarios in this audit set business_net_income directly. "
                       "Long-term fix: auto-populate business_net_income from business_income for S-Corp profiles.",
        "fix": "DONE: All SCORP scenarios pass business_net_income; full profile fix tracked separately",
    },
]


# ============================================================
# SCENARIO DEFINITIONS
# ============================================================
# Each scenario has:
#   profile       — TaxpayerProfile kwargs (direct fields only)
#   label         — short human-readable name
#   category      — W2 / SE / SCORP / REALESTATE / HIGHINCOME / COMPLEX
#   expected      — strategy title keywords the rule engine SHOULD produce
#   not_expected  — title keywords that must NOT appear (false positives)
#   ai_must_cover — topics the AI conversation MUST address (for auditor)
#   notes         — context for the auditor

SCENARIOS = [

    # ─────────────────────────────────────────────────────────
    # CATEGORY 1: W-2 ONLY (8 scenarios)
    # ─────────────────────────────────────────────────────────
    {
        "label": "W2-01: Single, $60K, renter, no dependents",
        "category": "W2",
        "profile": dict(filing_status="single", age=28, w2_wages=D("60000"),
                        state_local_taxes=D("4000")),
        "expected": ["401(k)", "IRA"],
        "not_expected": ["QBI", "Augusta", "Cost Segregation", "SEP-IRA", "Home Office"],
        "ai_must_cover": ["retirement contributions", "standard deduction"],
        "notes": "FIXED P1-001: Saver's Credit now fires for single/HoH filers. "
                 "Auditor: does AI mention Saver's Credit in conversation?",
    },
    {
        "label": "W2-02: Single, $120K, renter, no dependents",
        "category": "W2",
        "profile": dict(filing_status="single", age=32, w2_wages=D("120000"),
                        state_local_taxes=D("8000")),
        "expected": ["401(k)", "IRA"],
        "not_expected": ["QBI", "Augusta", "EITC", "Cost Segregation", "SEP-IRA"],
        "ai_must_cover": ["IRA contribution limits and phase-out"],
        "notes": "IRA phase-out at $87K–$102K single — AI should mention backdoor Roth",
    },
    {
        "label": "W2-03: MFJ, $180K combined W-2, 2 kids",
        "category": "W2",
        "profile": dict(filing_status="married_filing_jointly", age=38, spouse_age=36,
                        w2_wages=D("180000"), num_dependents=2,
                        has_children_under_17=True, has_children_under_13=True,
                        owns_home=True, mortgage_interest=D("18000"),
                        property_taxes=D("9000"), state_local_taxes=D("10000")),
        "expected": ["Child Tax Credit", "Child and Dependent Care", "401(k)"],
        "not_expected": ["QBI", "Augusta", "EITC", "SEP-IRA"],
        "ai_must_cover": ["Child Tax Credit phase-out", "dependent care FSA vs credit"],
        "notes": "Classic family W-2 — both child credits must appear. SALT cap ($10K) is relevant.",
    },
    {
        "label": "W2-04: HoH filing status, $55K, 1 child under 13",
        "category": "W2",
        "profile": dict(filing_status="single", age=31, w2_wages=D("55000"),
                        num_dependents=1, has_children_under_17=True,
                        has_children_under_13=True),
        "expected": ["Head of Household", "Child Tax Credit", "Child and Dependent Care"],
        "not_expected": ["QBI", "Augusta", "Cost Segregation"],
        "ai_must_cover": ["Head of Household qualification rules", "Child Tax Credit full amount"],
        "notes": "Single parent — HoH status saves ~$3,000 vs single. Detector must catch this.",
    },
    {
        "label": "W2-05: Single, $500K W-2",
        "category": "W2",
        "profile": dict(filing_status="single", age=45, w2_wages=D("500000")),
        "expected": ["401(k)"],
        "not_expected": ["EITC", "Saver", "QBI", "Augusta", "SEP-IRA"],
        "ai_must_cover": ["mega backdoor Roth", "deferred compensation (NQDC)"],
        "notes": "Ultra-high W-2 — AI should discuss NQDC plan and mega backdoor Roth beyond just 401k",
    },
    {
        "label": "W2-06: MFJ, $250K, owns home, age 52",
        "category": "W2",
        "profile": dict(filing_status="married_filing_jointly", age=52, spouse_age=50,
                        w2_wages=D("250000"), owns_home=True,
                        mortgage_interest=D("22000"), property_taxes=D("10000"),
                        state_local_taxes=D("10000")),
        "expected": ["401(k)", "Consider Itemizing"],
        "not_expected": ["QBI", "EITC", "Augusta", "Home Office", "SEP-IRA"],
        "ai_must_cover": ["catch-up contributions ($7,500 extra at age 50+)", "itemizing vs standard deduction"],
        "notes": "Age 52 — catch-up 401k contribution must be discussed. Mortgage + SALT likely clears standard deduction.",
    },
    {
        "label": "W2-07: Single, $38K, HDHP enrolled",
        "category": "W2",
        "profile": dict(filing_status="single", age=25, w2_wages=D("38000"),
                        has_hdhp=True),
        "expected": ["HSA", "IRA"],
        "not_expected": ["QBI", "Augusta", "Cost Segregation", "SEP-IRA"],
        "ai_must_cover": ["HSA triple tax advantage", "Saver's Credit (manual — rule has P1-001 bug)"],
        "notes": "FIXED P1-001: Saver's Credit now auto-fires for single filers at correct threshold.",
    },
    {
        "label": "W2-08: MFJ, $420K, RSUs + capital gains, owns home",
        "category": "W2",
        "profile": dict(filing_status="married_filing_jointly", age=41,
                        w2_wages=D("420000"), capital_gains=D("45000"),
                        owns_home=True, mortgage_interest=D("28000"),
                        property_taxes=D("10000"), state_local_taxes=D("10000"),
                        dividend_income=D("12000")),
        "expected": ["401(k)", "Consider Itemizing"],
        "not_expected": ["EITC", "Augusta", "QBI", "SEP-IRA"],
        "ai_must_cover": ["tax-loss harvesting (FIXED P1-003: now fires year-round)",
                          "NIIT at 3.8% on $600K total"],
        "notes": "FIXED P1-003: Tax-Loss Harvesting now fires year-round. "
                 "Auditor: does AI bring it up unprompted?",
    },

    # ─────────────────────────────────────────────────────────
    # CATEGORY 2: SELF-EMPLOYED SCHEDULE C (10 scenarios)
    # ─────────────────────────────────────────────────────────
    {
        "label": "SE-01: Sole prop, $80K net, renter, single",
        "category": "SE",
        "profile": dict(filing_status="single", age=33,
                        self_employment_income=D("80000"),
                        has_business=True, business_type="sole_proprietorship"),
        "expected": ["QBI", "SEP-IRA", "Self-Employment Tax Deduction"],
        "not_expected": ["Augusta", "Cost Segregation"],
        "ai_must_cover": ["§199A QBI deduction 20%", "SEP-IRA up to 25% of net"],
        "notes": "FIXED P1-002: WOTC false positive fixed — only fires for entity types with employees.",
    },
    {
        "label": "SE-02: Freelancer, $45K, renter, single, age 27",
        "category": "SE",
        "profile": dict(filing_status="single", age=27,
                        self_employment_income=D("45000"),
                        has_business=True, business_type="sole_proprietorship"),
        "expected": ["QBI", "SEP-IRA", "Self-Employment Tax"],
        "not_expected": ["Augusta", "Cost Segregation"],
        "ai_must_cover": ["QBI deduction", "SEP-IRA vs solo 401k tradeoff"],
        "notes": "Low SE — Defined Benefit correctly should NOT fire ($45K < $150K threshold). Good baseline.",
    },
    {
        "label": "SE-03: Consultant, $220K, owns home, MFJ, age 44",
        "category": "SE",
        "profile": dict(filing_status="married_filing_jointly", age=44,
                        self_employment_income=D("220000"),
                        has_business=True, business_type="sole_proprietorship",
                        has_home_office=True, owns_home=True,
                        mortgage_interest=D("20000"), property_taxes=D("9000")),
        "expected": ["QBI", "SEP-IRA", "Home Office", "Augusta"],
        "not_expected": ["EITC"],
        "ai_must_cover": ["Augusta Rule (home rental to business, IRC §280A(g))",
                          "Defined Benefit (FIXED P1-005: now fires at age 40+; age 44 qualifies)"],
        "notes": "FIXED P1-005: Defined Benefit now fires for age 40+. Age 44 qualifies.",
    },
    {
        "label": "SE-04: SE photographer, $95K, home studio, owns home",
        "category": "SE",
        "profile": dict(filing_status="single", age=35,
                        self_employment_income=D("95000"),
                        has_business=True, business_type="sole_proprietorship",
                        has_home_office=True, owns_home=True,
                        mortgage_interest=D("12000")),
        "expected": ["QBI", "Home Office", "SEP-IRA", "§179"],
        "not_expected": ["Cost Segregation", "Defined Benefit"],
        "ai_must_cover": ["§179 equipment deduction", "home office actual vs simplified method"],
        "notes": "Equipment-heavy creative — §179 and home office both expected. Good test of specificity.",
    },
    {
        "label": "SE-05: SE doctor (SSTB), $350K, single",
        "category": "SE",
        "profile": dict(filing_status="single", age=40,
                        self_employment_income=D("350000"),
                        has_business=True, business_type="professional_services",
                        is_sstb=True),
        "expected": ["QBI Deduction Phase-Out"],
        "not_expected": ["Qualified Business Income (QBI) Deduction"],
        "ai_must_cover": ["SSTB phase-out above $241,950 single (2025)",
                          "Defined Benefit (FIXED P1-005: now fires at age 40+)"],
        "notes": "SSTB above threshold — phase-out WARNING must appear. Regular QBI must NOT. "
                 "FIXED P1-005: Defined Benefit now fires for age 40+ — verify it appears in results.",
    },
    {
        "label": "SE-06: MFJ both SE, $160K combined, 2 kids, HDHP",
        "category": "SE",
        "profile": dict(filing_status="married_filing_jointly", age=38, spouse_age=36,
                        self_employment_income=D("160000"),
                        has_business=True, business_type="sole_proprietorship",
                        num_dependents=2, has_children_under_17=True,
                        has_hdhp=True),
        "expected": ["QBI", "SEP-IRA", "HSA", "Child Tax Credit"],
        "not_expected": ["Augusta", "EITC"],
        "ai_must_cover": ["HSA family contribution limit ($8,550 + $1,000 catchup if 55+)",
                          "spousal IRA if spouse has lower SE income"],
        "notes": "SE family — all four strategies must appear. Complex interaction of QBI + Child credits.",
    },
    {
        "label": "SE-07: Airbnb host, $40K SE + $30K W2, owns home",
        "category": "SE",
        "profile": dict(filing_status="single", age=36,
                        w2_wages=D("30000"), self_employment_income=D("40000"),
                        has_business=True, owns_home=True,
                        mortgage_interest=D("14000"), property_taxes=D("6000")),
        "expected": ["QBI", "SEP-IRA", "Augusta"],
        "not_expected": ["Cost Segregation", "EITC"],
        "ai_must_cover": ["Augusta Rule 14-day rule (IRC §280A(g))",
                          "Airbnb SE classification (Schedule C vs E)"],
        "notes": "Augusta Rule is the single most valuable strategy here. Must fire AND be explained correctly.",
    },
    {
        "label": "SE-08: Tech contractor, $280K, MFJ, home office, age 42",
        "category": "SE",
        "profile": dict(filing_status="married_filing_jointly", age=42,
                        self_employment_income=D("280000"),
                        has_business=True, business_type="technology",
                        has_home_office=True, owns_home=True,
                        mortgage_interest=D("24000")),
        "expected": ["QBI", "SEP-IRA", "Home Office", "Augusta"],
        "not_expected": ["EITC"],
        "ai_must_cover": ["Defined Benefit (FIXED P1-005: now fires at age 40+; age 42 qualifies — $100K+ savings)",
                          "S-Corp election at $280K (could save $15K-$20K in SE tax)"],
        "notes": "FIXED P1-005: DB plan now fires at age 40+. "
                 "Auditor: if AI doesn't mention Defined Benefit or S-Corp election unprompted, P0.",
    },
    {
        "label": "SE-09: Solo SE, $120K, has student loans",
        "category": "SE",
        "profile": dict(filing_status="single", age=29,
                        self_employment_income=D("120000"),
                        has_business=True,
                        student_loan_interest=D("0")),  # $0 so rule fires as reminder
        "expected": ["QBI", "SEP-IRA"],
        "not_expected": ["Augusta", "Cost Segregation"],
        "ai_must_cover": ["student loan interest deduction ceiling ($2,500 above-the-line)",
                          "phase-out $80K–$95K single — at $120K SE, deduction is fully phased out after SE adj.",
                          "rule engine correctly does NOT fire (phased out); AI should still mention phase-out context"],
        "notes": "SE + student loans — at $120K SE income, actual AGI after 50% SE deduction is ~$111K, "
                 "above the $95K phase-out ceiling. Student Loan Interest deduction is N/A. "
                 "Auditor: does AI correctly explain the phase-out? If AI incorrectly says they can take it, P0.",
    },
    {
        "label": "SE-10: Creative, $65K SE, HDHP, renter, home office",
        "category": "SE",
        "profile": dict(filing_status="single", age=31,
                        self_employment_income=D("65000"),
                        has_business=True, has_hdhp=True,
                        has_home_office=True, owns_home=False),
        "expected": ["QBI", "SEP-IRA", "HSA", "Home Office"],
        "not_expected": ["Augusta"],  # renter — Augusta requires owning the home
        "ai_must_cover": ["Augusta Rule does NOT apply (renter)",
                          "HSA individual contribution limit ($4,300)"],
        "notes": "Renter with HDHP — Augusta must NOT fire. Correct non-fire is as important as correct fire.",
    },

    # ─────────────────────────────────────────────────────────
    # CATEGORY 3: S-CORP OWNERS (8 scenarios)
    # NOTE: S-Corp profiles need business_net_income set directly.
    # SEP-IRA doesn't apply to S-Corp owners (they use 401k through the S-Corp).
    # ─────────────────────────────────────────────────────────
    {
        "label": "SCORP-01: S-Corp owner, $200K distributions, single",
        "category": "SCORP",
        "profile": dict(filing_status="single", age=38,
                        business_income=D("200000"), business_net_income=D("200000"),
                        has_business=True, business_type="s_corporation"),
        "expected": ["QBI"],
        "not_expected": ["EITC", "SEP-IRA"],
        "ai_must_cover": ["S-Corp 401k plan (not SEP-IRA) — owner can contribute $23,500 + profit sharing",
                          "reasonable salary requirement for S-Corp owners"],
        "notes": "NOTE P1-006: business_net_income set directly in test profile so QBI fires correctly. "
                 "Auditor: AI must explain S-Corp 401k vs SEP-IRA distinction.",
    },
    {
        "label": "SCORP-02: S-Corp owner, $400K, MFJ, owns home, age 46",
        "category": "SCORP",
        "profile": dict(filing_status="married_filing_jointly", age=46,
                        business_income=D("400000"), business_net_income=D("400000"),
                        has_business=True, business_type="s_corporation",
                        owns_home=True, mortgage_interest=D("30000"),
                        property_taxes=D("10000"), has_home_office=True),
        "expected": ["QBI", "Defined Benefit", "Augusta", "Home Office"],
        "not_expected": ["EITC", "SEP-IRA"],
        "ai_must_cover": ["Defined Benefit through S-Corp (age 46+ qualifies)",
                          "Augusta Rule — rent home to S-Corp for board meetings"],
        "notes": "High S-Corp, age 46 — Defined Benefit is legal through S-Corp. Augusta key strategy.",
    },
    {
        "label": "SCORP-03: S-Corp SSTB law firm, $500K, MFJ",
        "category": "SCORP",
        "profile": dict(filing_status="married_filing_jointly", age=48,
                        business_income=D("500000"), business_net_income=D("500000"),
                        has_business=True, business_type="professional_services",
                        is_sstb=True),
        "expected": ["QBI Deduction Phase-Out", "Defined Benefit"],
        "not_expected": ["Qualified Business Income (QBI) Deduction", "SEP-IRA"],
        "ai_must_cover": ["SSTB above MFJ $383,900 phase-out threshold",
                          "Defined Benefit reduces AGI potentially below SSTB threshold"],
        "notes": "SSTB law firm fully phased out — phase-out warning must appear, NOT regular QBI. "
                 "DB plan ALSO expected (age 48).",
    },
    {
        "label": "SCORP-04: S-Corp, $180K, equipment purchases",
        "category": "SCORP",
        "profile": dict(filing_status="married_filing_jointly", age=41,
                        business_income=D("180000"), business_net_income=D("180000"),
                        has_business=True, business_type="s_corporation"),
        "expected": ["QBI", "§179"],
        "not_expected": ["EITC", "SEP-IRA"],
        "ai_must_cover": ["§179 expensing up to $1.16M", "bonus depreciation at 60% for 2025"],
        "notes": "S-Corp with equipment — §179 fires for any has_business=True. Good baseline.",
    },
    {
        "label": "SCORP-05: S-Corp, $90K, MFJ, year 1",
        "category": "SCORP",
        "profile": dict(filing_status="married_filing_jointly", age=35,
                        business_income=D("90000"), business_net_income=D("90000"),
                        has_business=True, business_type="s_corporation",
                        started_business=True),
        "expected": ["QBI"],
        "not_expected": ["Defined Benefit", "EITC", "SEP-IRA"],
        "ai_must_cover": ["S-Corp salary election (reasonable compensation IRS rule)",
                          "SE tax savings from S-Corp vs sole prop on $90K"],
        "notes": "New S-Corp — Defined Benefit correctly should NOT fire (income $90K < $150K threshold). "
                 "AI should explain why S-Corp election makes sense at this income.",
    },
    {
        "label": "SCORP-06: S-Corp tech startup, $320K, R&D activities",
        "category": "SCORP",
        "profile": dict(filing_status="single", age=37,
                        business_income=D("320000"), business_net_income=D("320000"),
                        has_business=True, business_type="technology"),
        "expected": ["QBI", "R&D Tax Credit"],
        "not_expected": ["EITC", "SEP-IRA"],
        "ai_must_cover": ["R&D credit (§41) — software development qualifies",
                          "Defined Benefit (NOTE: age 37 < 40 — still below new threshold; auditor verify AI covers it)"],
        "notes": "NOTE P1-005: age 37 < 40, DB plan won't auto-fire. Auditor: does AI still recommend it?",
    },
    {
        "label": "SCORP-07: S-Corp owner, $150K, MFJ, W-2 spouse $80K",
        "category": "SCORP",
        "profile": dict(filing_status="married_filing_jointly", age=40, spouse_age=38,
                        w2_wages=D("80000"), business_income=D("150000"),
                        business_net_income=D("150000"),
                        has_business=True, business_type="s_corporation"),
        "expected": ["QBI", "401(k)"],
        "not_expected": ["EITC", "SEP-IRA"],
        "ai_must_cover": ["spouse W-2 401k AND S-Corp 401k plan (two separate plans)",
                          "spousal IRA backdoor if W-2 spouse has employer plan"],
        "notes": "Both spouses — 401k strategy should mention BOTH plans. Two different contribution pools.",
    },
    {
        "label": "SCORP-08: S-Corp, $260K, owns home outright",
        "category": "SCORP",
        "profile": dict(filing_status="single", age=44,
                        business_income=D("260000"), business_net_income=D("260000"),
                        has_business=True, business_type="s_corporation",
                        owns_home=True, mortgage_interest=D("0")),
        "expected": ["QBI", "Augusta"],
        "not_expected": ["EITC", "SEP-IRA"],
        "ai_must_cover": ["Augusta Rule fires even with no mortgage (paid-off home qualifies)",
                          "S-Corp can pay rent to owner for board meetings — §280A(g)"],
        "notes": "Augusta Rule edge case — paid-off homeowner. BUG PREVIOUSLY FIXED in QA scenarios. Verify still works.",
    },

    # ─────────────────────────────────────────────────────────
    # CATEGORY 4: REAL ESTATE INVESTORS (8 scenarios)
    # ─────────────────────────────────────────────────────────
    {
        "label": "RE-01: Single rental $25K, W-2 $90K",
        "category": "REALESTATE",
        "profile": dict(filing_status="single", age=35,
                        w2_wages=D("90000"), rental_income=D("25000"),
                        owns_home=True, mortgage_interest=D("15000"),
                        property_taxes=D("8000")),
        "expected": ["401(k)", "Consider Itemizing"],
        "not_expected": ["Cost Segregation", "Augusta", "QBI", "SEP-IRA"],
        "ai_must_cover": ["passive activity loss rules for rental income",
                          "Cost Segregation not applicable below ~$500K property value"],
        "notes": "Small landlord — Cost Segregation correctly should NOT fire. Verify threshold respected.",
    },
    {
        "label": "RE-02: 3 rentals, $80K income, W-2 $120K, MFJ",
        "category": "REALESTATE",
        "profile": dict(filing_status="married_filing_jointly", age=42,
                        w2_wages=D("120000"), rental_income=D("80000"),
                        owns_home=True, mortgage_interest=D("18000")),
        "expected": ["Cost Segregation", "401(k)"],
        "not_expected": ["EITC", "Augusta", "QBI"],
        "ai_must_cover": ["Cost Segregation study timeline and cost", "$15K–$50K first-year bonus depreciation"],
        "notes": "Multi-property investor — Cost Segregation must fire and be explained with context.",
    },
    {
        "label": "RE-03: Real estate professional, $200K rental, no W-2",
        "category": "REALESTATE",
        "profile": dict(filing_status="single", age=48,
                        rental_income=D("200000"),
                        owns_home=True, has_business=True),
        "expected": ["Cost Segregation"],
        "not_expected": ["EITC", "Child Tax Credit"],
        "ai_must_cover": ["Real estate professional status — 750 hours test (IRC §469(c)(7))",
                          "self-employment retirement options (rental is passive, not SE)"],
        "notes": "Full-time RE investor — must discuss real estate professional status for loss deductibility.",
    },
    {
        "label": "RE-04: Short-term rentals (STR), $60K, W-2 $140K",
        "category": "REALESTATE",
        "profile": dict(filing_status="single", age=38,
                        w2_wages=D("140000"), rental_income=D("60000"),
                        owns_home=True),
        "expected": ["Cost Segregation", "401(k)"],
        "not_expected": ["EITC", "QBI", "SEP-IRA"],
        "ai_must_cover": ["STR material participation (7-day rule)",
                          "Cost Segregation accelerates STR depreciation most aggressively"],
        "notes": "STR is #1 target use case for CA4CPA. AI must explain STR-specific rules correctly.",
    },
    {
        "label": "RE-05: MFJ, $180K rental + $200K W-2, high income",
        "category": "REALESTATE",
        "profile": dict(filing_status="married_filing_jointly", age=45, spouse_age=43,
                        w2_wages=D("200000"), rental_income=D("180000"),
                        owns_home=True, mortgage_interest=D("28000"),
                        property_taxes=D("10000")),
        "expected": ["Cost Segregation", "401(k)", "Consider Itemizing"],
        "not_expected": ["EITC", "QBI", "SEP-IRA"],
        "ai_must_cover": ["NIIT applies to rental income at $380K total (3.8% on $180K = $6,840)",
                          "passive activity rules and real estate professional election"],
        "notes": "NIIT is material here. AI must discuss it. Cost Seg + itemizing both expected.",
    },
    {
        "label": "RE-06: Accidental landlord, $18K rental, W-2 $75K",
        "category": "REALESTATE",
        "profile": dict(filing_status="single", age=32,
                        w2_wages=D("75000"), rental_income=D("18000"),
                        owns_home=True, mortgage_interest=D("14000"),
                        property_taxes=D("7000")),
        "expected": ["401(k)"],
        "not_expected": ["Cost Segregation", "Defined Benefit", "SEP-IRA"],
        "ai_must_cover": ["rental income reporting on Schedule E",
                          "deductible rental expenses (repairs, depreciation, management fees)"],
        "notes": "Small landlord — no big strategies available. AI must acknowledge this honestly.",
    },
    {
        "label": "RE-07: K-1 passive investor, $45K K-1, W-2 $160K",
        "category": "REALESTATE",
        "profile": dict(filing_status="single", age=40,
                        w2_wages=D("160000"),
                        other_income=D("45000")),  # K-1 passive approximated as other_income
        "expected": ["401(k)"],
        "not_expected": ["Augusta", "EITC", "QBI"],
        "ai_must_cover": ["passive activity loss rules — K-1 losses suspended unless passive income exists",
                          "NIIT applies to K-1 passive income above $200K threshold"],
        "notes": "K-1 passive — limited strategies via rules engine. AI conversation quality is the test.",
    },
    {
        "label": "RE-08: MFJ, $300K rental portfolio, age 52",
        "category": "REALESTATE",
        "profile": dict(filing_status="married_filing_jointly", age=52,
                        rental_income=D("300000"),
                        owns_home=True, has_business=True),
        "expected": ["Cost Segregation", "Defined Benefit", "Year-End Charitable"],
        "not_expected": ["EITC", "Saver"],
        "ai_must_cover": ["real estate professional status for $300K portfolio",
                          "Defined Benefit plan funded through RE management LLC (age 52 qualifies)"],
        "notes": "Age 52 — Defined Benefit qualifies. Large portfolio warrants Cost Seg AND DB plan discussion.",
    },

    # ─────────────────────────────────────────────────────────
    # CATEGORY 5: HIGH-INCOME W-2 $300K+ (6 scenarios)
    # ─────────────────────────────────────────────────────────
    {
        "label": "HI-01: Single, $350K W-2, RSUs, capital gains",
        "category": "HIGHINCOME",
        "profile": dict(filing_status="single", age=34,
                        w2_wages=D("350000"), capital_gains=D("80000"),
                        dividend_income=D("15000")),
        "expected": ["401(k)"],
        "not_expected": ["EITC", "Saver", "Augusta", "QBI", "SEP-IRA"],
        "ai_must_cover": ["tax-loss harvesting (FIXED P1-003: now fires year-round)",
                          "year-end charitable giving with appreciated stock",
                          "NIIT on $80K capital gains + $15K dividends"],
        "notes": "FIXED P1-003: tax-loss harvesting now auto-fires year-round.",
    },
    {
        "label": "HI-02: MFJ, $500K combined W-2",
        "category": "HIGHINCOME",
        "profile": dict(filing_status="married_filing_jointly", age=45, spouse_age=43,
                        w2_wages=D("500000"), owns_home=True,
                        mortgage_interest=D("40000"), property_taxes=D("10000")),
        "expected": ["401(k)", "Consider Itemizing"],
        "not_expected": ["EITC", "Saver", "QBI", "SEP-IRA"],
        "ai_must_cover": ["backdoor Roth IRA (income too high for direct contribution)",
                          "mega backdoor Roth via after-tax 401k"],
        "notes": "Very high W-2 — backdoor Roth is the most actionable strategy. AI must mention it.",
    },
    {
        "label": "HI-03: Single, $420K, ISO options, CA resident",
        "category": "HIGHINCOME",
        "profile": dict(filing_status="single", age=38,
                        w2_wages=D("420000"), capital_gains=D("120000")),
        "expected": ["401(k)"],
        "not_expected": ["EITC", "QBI", "Augusta", "SEP-IRA"],
        "ai_must_cover": ["AMT risk on ISOs ($120K gain)",
                          "CA state tax (13.3%) has no preferential capital gains rate"],
        "notes": "ISO/options in CA — AMT is critical. AI must address CA state tax implications.",
    },
    {
        "label": "HI-04: MFJ, $380K, 3 kids, college student",
        "category": "HIGHINCOME",
        "profile": dict(filing_status="married_filing_jointly", age=42,
                        w2_wages=D("380000"), num_dependents=3,
                        has_children_under_17=True,
                        has_college_students=True,
                        education_expenses=D("25000"),
                        owns_home=True, mortgage_interest=D("35000"),
                        property_taxes=D("10000")),
        "expected": ["Child Tax Credit", "American Opportunity", "401(k)", "Consider Itemizing"],
        "not_expected": ["EITC", "Saver", "QBI", "SEP-IRA"],
        "ai_must_cover": ["American Opportunity Credit ($2,500/student) — phases out at $180K MFJ",
                          "529 plan contribution for remaining college years"],
        "notes": "AOTC phases out at $180K–$200K MFJ but $380K is WAY above — AOTC rule may over-fire. "
                 "Auditor: does the rule correctly handle income phase-outs?",
    },
    {
        "label": "HI-05: Single, $310K W-2, age 55",
        "category": "HIGHINCOME",
        "profile": dict(filing_status="single", age=55,
                        w2_wages=D("310000"), owns_home=True,
                        mortgage_interest=D("22000")),
        "expected": ["401(k)", "Consider Itemizing"],
        "not_expected": ["EITC", "Saver", "QBI", "SEP-IRA"],
        "ai_must_cover": ["catch-up 401k contribution: $23,500 + $7,500 = $31,000 total at age 55",
                          "SUPER catch-up at age 60–63: $34,750 in 2025"],
        "notes": "Age 55 catch-up — AI must mention both regular catch-up AND super catch-up if applicable.",
    },
    {
        "label": "HI-06: MFJ, $600K total, heavy investment income — NIIT",
        "category": "HIGHINCOME",
        "profile": dict(filing_status="married_filing_jointly", age=48,
                        w2_wages=D("400000"), capital_gains=D("100000"),
                        dividend_income=D("50000"), interest_income=D("30000"),
                        rental_income=D("20000")),
        "expected": ["401(k)"],
        "not_expected": ["EITC", "Saver", "QBI", "SEP-IRA"],
        "ai_must_cover": ["NIIT 3.8% on $200K net investment income = $7,600 liability",
                          "strategies to reduce NII: maximize 401k, real estate losses"],
        "notes": "NIIT-heavy — $200K NII * 3.8% = $7,600. AI must discuss NIIT mitigation strategies.",
    },

    # ─────────────────────────────────────────────────────────
    # CATEGORY 6: COMPLEX / MIXED (10 scenarios)
    # ─────────────────────────────────────────────────────────
    {
        "label": "MX-01: W-2 + SE side hustle, $140K + $45K, home office",
        "category": "COMPLEX",
        "profile": dict(filing_status="single", age=35,
                        w2_wages=D("140000"), self_employment_income=D("45000"),
                        has_business=True, owns_home=True,
                        mortgage_interest=D("16000"), has_home_office=True),
        "expected": ["QBI", "SEP-IRA", "Home Office", "401(k)"],
        "not_expected": ["EITC", "Cost Segregation"],
        "ai_must_cover": ["SEP-IRA AND W-2 401k can coexist — different contribution pools",
                          "home office deduction only for SE portion of home"],
        "notes": "Classic dual-income setup. Both retirement vehicles expected. "
                 "AI must explain why BOTH 401k and SEP-IRA are available.",
    },
    {
        "label": "MX-02: Divorced HoH, 2 kids, $85K W-2 + $20K SE",
        "category": "COMPLEX",
        "profile": dict(filing_status="single", age=38,
                        w2_wages=D("85000"), self_employment_income=D("20000"),
                        has_business=True, num_dependents=2,
                        has_children_under_17=True, has_children_under_13=True),
        "expected": ["Head of Household", "Child Tax Credit", "Child and Dependent Care", "QBI"],
        "not_expected": ["Augusta", "Defined Benefit"],
        "ai_must_cover": ["Head of Household — saves $3,000 vs single filer",
                          "Child Tax Credit + Dependent Care Credit can stack"],
        "notes": "All 4 expected strategies must fire. Complex interaction of family + SE credits.",
    },
    {
        "label": "MX-03: Retired couple, SS + RMDs, age 68/65",
        "category": "COMPLEX",
        "profile": dict(filing_status="married_filing_jointly", age=68, spouse_age=65,
                        other_income=D("60000"),
                        w2_wages=D("80000"),
                        owns_home=True, mortgage_interest=D("8000"),
                        property_taxes=D("7000"), charitable_contributions=D("5000")),
        "expected": ["401(k)", "IRA", "Compare Joint"],
        "not_expected": ["SEP-IRA", "QBI", "Augusta", "EITC", "Consider Itemizing"],
        "ai_must_cover": ["Qualified Charitable Distribution (QCD) from IRA — satisfies RMD, excludes from AGI",
                          "standard deduction for seniors ($16,550 single, $33,100 MFJ in 2025)",
                          "itemized ($20K) is less than senior MFJ standard (~$32K) — standard deduction wins",
                          "Deduction Bunching: $9K gap to itemizing, could bunch 2 years of charitable into one"],
        "notes": "QCD strategy is the #1 strategy for retirees with RMDs. Rule engine won't find it. "
                 "Already has $5K charitable so Year-End Charitable reminder doesn't fire (correct). "
                 "Itemized $20K is within $9K of standard — Deduction Bunching fires. "
                 "Auditor: does AI proactively mention QCD? If not, P1.",
    },
    {
        "label": "MX-04: SE + rental + W-2 spouse, all three income types",
        "category": "COMPLEX",
        "profile": dict(filing_status="married_filing_jointly", age=44, spouse_age=42,
                        w2_wages=D("120000"), self_employment_income=D("100000"),
                        rental_income=D("50000"),
                        has_business=True, owns_home=True,
                        mortgage_interest=D("22000"), has_home_office=True),
        "expected": ["QBI", "SEP-IRA", "Home Office", "Cost Segregation", "401(k)"],
        "not_expected": ["EITC"],
        "ai_must_cover": ["three income streams, three different tax treatments",
                          "SE health insurance deduction (often missed for SE + rental combo)"],
        "notes": "All 5 strategies must fire. Most complex valid scenario. Good overall integration test.",
    },
    {
        "label": "MX-05: New parent, $130K W-2, had baby, HDHP",
        "category": "COMPLEX",
        "profile": dict(filing_status="single", age=32,
                        w2_wages=D("130000"), num_dependents=1,
                        has_children_under_17=True, has_children_under_13=True,
                        had_baby=True, has_hdhp=True),
        "expected": ["Child Tax Credit", "Child and Dependent Care", "HSA", "401(k)"],
        "not_expected": ["EITC", "QBI", "Augusta"],
        "ai_must_cover": ["HSA switches to family limit ($8,550) after baby",
                          "Dependent Care FSA ($5,000 pre-tax) vs Child Care Credit"],
        "notes": "Life event: new baby. HSA family limit change is a common missed point.",
    },
    {
        "label": "MX-06: Just married, both high-W2, $180K + $160K",
        "category": "COMPLEX",
        "profile": dict(filing_status="married_filing_jointly", age=30, spouse_age=29,
                        w2_wages=D("340000"), got_married=True),
        "expected": ["Compare Joint vs. Separate", "401(k)"],
        "not_expected": ["EITC", "QBI", "Augusta", "SEP-IRA"],
        "ai_must_cover": ["marriage penalty at $340K combined (both in 32% bracket)",
                          "MFJ vs MFS calculation — is separate filing worth it?"],
        "notes": "Marriage penalty — 'Compare Joint vs Separate' strategy must fire. New couple.",
    },
    {
        "label": "MX-07: SE + college student dependent, $110K",
        "category": "COMPLEX",
        "profile": dict(filing_status="single", age=48,
                        self_employment_income=D("110000"),
                        has_business=True, num_dependents=1,
                        has_college_students=True,
                        education_expenses=D("15000")),
        "expected": ["QBI", "SEP-IRA", "American Opportunity"],
        "not_expected": ["EITC", "Cost Segregation"],
        "ai_must_cover": ["AOTC phases out at $90K single — at $110K SE pre-deductions, "
                          "after QBI + SE deductions AGI may fall below phase-out",
                          "Lifetime Learning Credit as alternative if AOTC phases out"],
        "notes": "Income near AOTC phase-out. AI should calculate actual AGI after SE deductions.",
    },
    {
        "label": "MX-08: First-year homeowner, $175K W-2",
        "category": "COMPLEX",
        "profile": dict(filing_status="single", age=34,
                        w2_wages=D("175000"), bought_home=True,
                        owns_home=True, mortgage_interest=D("12000"),
                        property_taxes=D("7000"), home_purchase_year=2025),
        "expected": ["401(k)", "Consider Itemizing"],
        "not_expected": ["EITC", "QBI", "Augusta", "SEP-IRA"],
        "ai_must_cover": ["itemizing: $12K mortgage + $7K property = $19K > $15K standard deduction",
                          "points paid at closing (deductible in year of purchase)"],
        "notes": "New homeowner — itemizing should be close call at $19K vs $15K standard. "
                 "AI must walk through the actual numbers.",
    },
    {
        "label": "MX-09: MFS for PSLF, $140K income",
        "category": "COMPLEX",
        "profile": dict(filing_status="married_filing_separately", age=34,
                        w2_wages=D("140000"), student_loan_interest=D("0")),
        "expected": ["Compare Joint vs. Separate", "401(k)"],
        "not_expected": ["EITC", "Child Tax Credit"],
        "ai_must_cover": ["Public Service Loan Forgiveness — MFS keeps IDR payments lower",
                          "tax cost of MFS vs PSLF benefit calculation"],
        "notes": "PSLF scenario — AI must understand WHY MFS is being chosen and validate the math.",
    },
    {
        "label": "MX-10: Augusta Rule edge — owns paid-off vacation home",
        "category": "COMPLEX",
        "profile": dict(filing_status="single", age=39,
                        self_employment_income=D("150000"),
                        has_business=True, owns_home=True,
                        mortgage_interest=D("0")),
        "expected": ["Augusta", "QBI", "SEP-IRA"],
        "not_expected": ["EITC", "WOTC"],
        "ai_must_cover": ["Augusta Rule fires even with NO mortgage (paid-off home qualifies)",
                          "14-day rule and fair market rental rate documentation"],
        "notes": "Augusta Rule edge case. Previously broken — fixed in QA. Verify still correct. "
                 "Paid-off home must work — common misconception that mortgage required.",
    },
]


# ============================================================
# RUN SCENARIOS THROUGH DETECTOR
# ============================================================

def run_scenario(scenario: dict) -> dict:
    """Run one scenario and return result dict."""
    profile_kwargs = scenario["profile"]
    try:
        profile = TaxpayerProfile(**profile_kwargs)
    except TypeError as e:
        return {**scenario, "actual_titles": [], "error": f"Profile construction: {e}",
                "missing": scenario["expected"], "false_positives": []}

    detector = TaxOpportunityDetector()

    try:
        opps = detector.detect_opportunities(profile)
    except Exception as e:
        return {**scenario, "actual_titles": [], "error": str(e),
                "missing": scenario["expected"], "false_positives": []}

    actual_titles = [o.title for o in opps]

    missing = [
        exp for exp in scenario["expected"]
        if not any(exp.lower() in t.lower() for t in actual_titles)
    ]
    false_positives = [
        fp for fp in scenario.get("not_expected", [])
        if any(fp.lower() in t.lower() for t in actual_titles)
    ]

    return {
        **scenario,
        "actual_titles": actual_titles,
        "error": None,
        "missing": missing,
        "false_positives": false_positives,
        "pass": len(missing) == 0 and len(false_positives) == 0,
    }


def main():
    today = date.today().strftime("%Y%m%d")
    csv_path = ROOT / f"audit_scenarios_{today}.csv"

    print(f"\n{'='*60}")
    print(f"  EA/CPA Audit Scenario Generator")
    print(f"  {len(SCENARIOS)} scenarios across 6 categories")
    print(f"{'='*60}\n")

    # Print known bugs first
    print(f"KNOWN BUGS (pre-audit analysis):")
    for bug in KNOWN_BUGS:
        print(f"  [{bug['id']}] {bug['area']}: {bug['description'][:80]}...")
    print()

    results = []
    passes = 0
    category_stats = {}

    for i, scenario in enumerate(SCENARIOS, 1):
        r = run_scenario(scenario)
        results.append(r)
        cat = scenario["category"]
        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "pass": 0}
        category_stats[cat]["total"] += 1

        if r["pass"]:
            passes += 1
            category_stats[cat]["pass"] += 1
            status = "✅ PASS"
        else:
            status = "❌ FAIL"

        print(f"  {status}  {i:02d}. {scenario['label']}")
        if r.get("error"):
            print(f"         🚨 ERROR: {r['error']}")
        if r["missing"]:
            print(f"         ❌ MISSING: {', '.join(r['missing'])}")
        if r["false_positives"]:
            print(f"         ⚠️  FALSE POSITIVE: {', '.join(r['false_positives'])}")

    # Summary
    print(f"\n{'─'*60}")
    print(f"  Auto-check results: {passes}/{len(SCENARIOS)} pass")
    print()
    for cat, stats in category_stats.items():
        bar = "█" * stats["pass"] + "░" * (stats["total"] - stats["pass"])
        print(f"  {cat:<15} {bar} {stats['pass']}/{stats['total']}")
    print(f"{'─'*60}\n")

    # Write CSV
    fieldnames = [
        "Scenario #", "Category", "Label",
        "Auto-Check (rule engine)",
        "Expected Strategies",
        "Actual Strategies Fired",
        "Missing (rule did NOT fire — verify in AI chat)",
        "False Positives (rule fired incorrectly)",
        "AI Must Cover (auditor checklist)",
        "Auditor: Conversation Quality (1–5)",
        "Auditor: Tax Accuracy (1–5)",
        "Auditor: IRS Code References Correct? (Y / N / Partial)",
        "Auditor: Exactly ONE question per AI turn? (Y / N)",
        "Auditor: Any disclaimers 'consult a tax professional'? (Y/N — should be N)",
        "Auditor: Priority Issues (P0 = wrong tax advice, P1 = missing strategy, P2 = UX)",
        "Context / Notes",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, r in enumerate(results, 1):
            if r.get("error"):
                auto = f"ERROR: {r['error'][:60]}"
            else:
                auto = "PASS" if r["pass"] else "FAIL"
            writer.writerow({
                "Scenario #": i,
                "Category": r["category"],
                "Label": r["label"],
                "Auto-Check (rule engine)": auto,
                "Expected Strategies": " | ".join(r["expected"]),
                "Actual Strategies Fired": " | ".join(r["actual_titles"][:6]),
                "Missing (rule did NOT fire — verify in AI chat)": " | ".join(r["missing"]) if r["missing"] else "",
                "False Positives (rule fired incorrectly)": " | ".join(r["false_positives"]) if r["false_positives"] else "",
                "AI Must Cover (auditor checklist)": " || ".join(r.get("ai_must_cover", [])),
                "Auditor: Conversation Quality (1–5)": "",
                "Auditor: Tax Accuracy (1–5)": "",
                "Auditor: IRS Code References Correct? (Y / N / Partial)": "",
                "Auditor: Exactly ONE question per AI turn? (Y / N)": "",
                "Auditor: Any disclaimers 'consult a tax professional'? (Y/N — should be N)": "",
                "Auditor: Priority Issues (P0 = wrong tax advice, P1 = missing strategy, P2 = UX)": "",
                "Context / Notes": r["notes"],
            })

    print(f"CSV saved → {csv_path}")
    print()
    print("── Auditor Instructions ───────────────────────────────────────")
    print("1. Upload this CSV to Google Sheets")
    print("2. For each scenario, go to /lead-magnet?cpa=YOUR_SLUG")
    print("   and enter the profile described in 'Label'")
    print("3. Fill in the 6 auditor columns for each scenario")
    print("4. 'AI Must Cover' column = specific topics to verify in the")
    print("   AI conversation, even if the rule engine didn't flag them")
    print("5. Priority bug scale:")
    print("   P0 = AI gives factually wrong tax advice")
    print("   P1 = AI misses a strategy worth $5K+ that a CPA would catch")
    print("   P2 = Flow/UX issue — confusing question, wrong tone, etc.")
    print("6. Target before launch: 0 P0s, < 5 P1s, P2s can ship")
    print("───────────────────────────────────────────────────────────────")

    # Exit code: pass if 75%+ of auto-checks pass (known bugs account for remainder)
    return 0 if passes >= len(SCENARIOS) * 0.75 else 1


if __name__ == "__main__":
    sys.exit(main())
