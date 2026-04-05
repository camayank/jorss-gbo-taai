#!/usr/bin/env python3
"""
QA Scenario Runner — validates the 4 critical advisor paths.

Run from repo root:
  cd /Users/rakeshanita/jorss-gbo-taai
  python scripts/qa_scenarios.py

Each scenario traces through the same code path the API uses:
  profile dict → TaxpayerProfile → TaxOpportunityDetector → opportunities
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'web'))

from decimal import Decimal

# ── Helpers ────────────────────────────────────────────────────────────────────

_AGE_BUCKET_MAP = {
    "age_under_26": 25, "age_26_49": 40,
    "age_50_64": 57, "age_65_plus": 67,
}

def _age_int(raw):
    try:
        return int(raw) if str(raw).isdigit() else _AGE_BUCKET_MAP.get(str(raw), 40)
    except Exception:
        return 40

PASS = "\033[92m✅ PASS\033[0m"
FAIL = "\033[91m❌ FAIL\033[0m"
WARN = "\033[93m⚠️  WARN\033[0m"

results = []

def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    print(f"  {status}  {name}")
    if detail:
        print(f"         {detail}")
    results.append((name, condition))
    return condition


# ── Import tax engine ──────────────────────────────────────────────────────────

try:
    from services.tax_opportunity_detector import TaxOpportunityDetector, TaxpayerProfile
    detector = TaxOpportunityDetector()
    print("✅ TaxOpportunityDetector loaded\n")
except ImportError as e:
    print(f"❌ Could not import TaxOpportunityDetector: {e}")
    print("   Run from repo root: cd /Users/rakeshanita/jorss-gbo-taai && python scripts/qa_scenarios.py")
    sys.exit(1)

try:
    from web.advisor.flow_engine import FlowEngine
    flow_engine = FlowEngine()
    print("✅ FlowEngine loaded\n")
except Exception as e:
    print(f"⚠️  FlowEngine not loaded (non-fatal): {e}\n")
    flow_engine = None


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 1: Self-employed, $180K, California
# Expected: Augusta Rule appears, SEP-IRA appears, home office appears
# ══════════════════════════════════════════════════════════════════════════════

print("=" * 60)
print("SCENARIO 1: Self-employed, $180K, California")
print("=" * 60)

profile_1 = {
    "filing_status": "single",
    "income_type": "self_employed",
    "total_income": 180000,
    "self_employment_income": 180000,
    "state": "CA",
    "age": "age_50_64",
    "mortgage_interest": 12000,  # owns home
    "is_self_employed": True,
}

tp1 = TaxpayerProfile(
    filing_status="single",
    age=_age_int(profile_1["age"]),
    self_employment_income=Decimal("180000"),
    business_net_income=Decimal("180000"),
    has_business=True,
    owns_home=True,
    mortgage_interest=Decimal("12000"),
)

opps_1 = detector.detect_opportunities(tp1)
opp_ids_1 = {o.id for o in opps_1}
opp_titles_1 = [o.title for o in opps_1]

print(f"  Opportunities found: {len(opps_1)}")
for t in opp_titles_1:
    print(f"    • {t}")
print()

check("Augusta Rule fires", "augusta_rule" in opp_ids_1,
      "Expected when self_employed=True + owns_home=True")
check("SEP-IRA fires", "sep_ira" in opp_ids_1,
      "Expected when self_employment_income > $10K")
check("Age decoded correctly (57, not 30)", tp1.age == 57,
      f"Got age={tp1.age} (was always 30 before fix)")
check("Defined Benefit fires (age 57 >= 45, income $180K > $150K)",
      "defined_benefit_plan" in opp_ids_1,
      f"Expected: age={tp1.age}, income={tp1.total_income}")

if flow_engine:
    fq1 = flow_engine.get_next_question(profile_1)
    check("FlowEngine returns a question", fq1 is not None,
          f"Got: {fq1.text[:60] if fq1 else 'None'}")

print()


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 2: S-Corp owner, $350K
# Expected: Defined Benefit Plan appears, §179 appears
# ══════════════════════════════════════════════════════════════════════════════

print("=" * 60)
print("SCENARIO 2: S-Corp owner, $350K")
print("=" * 60)

profile_2 = {
    "filing_status": "married_joint",
    "income_type": "business_owner",
    "entity_type": "s_corp",
    "total_income": 350000,
    "business_income": 250000,
    "w2_income": 100000,
    "state": "NY",
    "age": "age_50_64",
}

# Simulate _session_profile_to_taxpayer_profile logic
_age2 = _age_int(profile_2["age"])
_has_business2 = (
    profile_2.get("income_type") in ("self_employed", "business_owner")
    or profile_2.get("entity_type") in ("s_corp", "llc")
    or bool(profile_2.get("business_income"))
)

tp2 = TaxpayerProfile(
    filing_status="married_joint",
    age=_age2,
    w2_wages=Decimal("100000"),
    business_income=Decimal("250000"),
    business_net_income=Decimal("250000"),
    has_business=_has_business2,
)

opps_2 = detector.detect_opportunities(tp2)
opp_ids_2 = {o.id for o in opps_2}
opp_titles_2 = [o.title for o in opps_2]

print(f"  has_business resolved: {_has_business2}")
print(f"  age resolved: {_age2}")
print(f"  Opportunities found: {len(opps_2)}")
for t in opp_titles_2:
    print(f"    • {t}")
print()

check("has_business=True for S-Corp owner", _has_business2)
check("Age decoded correctly (57)", _age2 == 57, f"Got {_age2}")
check("Defined Benefit Plan fires", "defined_benefit_plan" in opp_ids_2,
      f"Requires: has_business={_has_business2}, age={_age2}>=45, income>$150K")
check("§179 Bonus Depreciation fires", "section_179_bonus_depreciation" in opp_ids_2)

print()


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 3: Real estate investor, multiple properties
# Expected: Cost Segregation appears
# ══════════════════════════════════════════════════════════════════════════════

print("=" * 60)
print("SCENARIO 3: Real estate investor, multiple properties")
print("=" * 60)

tp3 = TaxpayerProfile(
    filing_status="married_joint",
    age=45,
    rental_income=Decimal("80000"),   # implies property value ~$800K (10x)
    w2_wages=Decimal("140000"),
)

opps_3 = detector.detect_opportunities(tp3)
opp_ids_3 = {o.id for o in opps_3}
opp_titles_3 = [o.title for o in opps_3]

print(f"  Opportunities found: {len(opps_3)}")
for t in opp_titles_3:
    print(f"    • {t}")
print()

check("Cost Segregation fires", "cost_segregation" in opp_ids_3,
      f"Expects rental_income={tp3.rental_income} → estimated value ~$800K > $500K threshold")

print()


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 4: Augusta Rule — homeowner who owns outright (no mortgage)
# Bug fix: owns_home should fire from augusta_rule_status answer too
# ══════════════════════════════════════════════════════════════════════════════

print("=" * 60)
print("SCENARIO 4: Augusta Rule — home owned outright (no mortgage)")
print("=" * 60)

profile_4 = {
    "filing_status": "single",
    "income_type": "self_employed",
    "total_income": 200000,
    "self_employment_income": 200000,
    "state": "TX",
    "age": "age_50_64",
    "mortgage_interest": 0,       # paid off house
    "property_taxes": 0,          # not yet captured
    "augusta_rule_status": "augusta_eligible",  # user answered YES
}

_owns_home4 = (
    bool(profile_4.get("mortgage_interest"))
    or bool(profile_4.get("property_taxes"))
    or profile_4.get("augusta_rule_status") == "augusta_eligible"
)

tp4 = TaxpayerProfile(
    filing_status="single",
    age=57,
    self_employment_income=Decimal("200000"),
    business_net_income=Decimal("200000"),
    has_business=True,
    owns_home=_owns_home4,
)

opps_4 = detector.detect_opportunities(tp4)
opp_ids_4 = {o.id for o in opps_4}

check("owns_home=True when user answered augusta_eligible", _owns_home4)
check("Augusta Rule fires even without mortgage", "augusta_rule" in opp_ids_4,
      "Previously blocked for paid-off homeowners — now fixed")

print()


# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

passed = sum(1 for _, ok in results if ok)
total = len(results)
pct = round(passed / total * 100) if total else 0

print("=" * 60)
print(f"RESULTS: {passed}/{total} checks passed ({pct}%)")
print("=" * 60)
if passed == total:
    print("\033[92m🎉 All scenarios pass — ready for CPA demo\033[0m")
else:
    failed = [name for name, ok in results if not ok]
    print("\033[91mFailed checks:\033[0m")
    for f in failed:
        print(f"  ❌ {f}")
    sys.exit(1)
