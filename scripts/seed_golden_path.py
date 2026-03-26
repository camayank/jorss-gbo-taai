#!/usr/bin/env python3
"""
Seed realistic demo data for the Golden Path.

Creates 20 tax returns at various workflow stages so every screen
(CPA dashboard, return queue, review, results, admin) has real content.

Usage:
    python3 scripts/seed_golden_path.py
"""

import sys
import os
import json
import uuid
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from database.session_persistence import SessionPersistence


def get_persistence():
    # Use same default path as the running app: data/tax_returns.db
    db_path = Path(os.environ.get(
        "SESSION_DB_PATH",
        str(Path(__file__).parent.parent / "data" / "tax_returns.db")
    ))
    return SessionPersistence(db_path=db_path)


# 20 realistic tax profiles
PROFILES = [
    {"name": "Sarah Johnson", "email": "sarah.j@email.com", "filing_status": "single", "wages": 85000, "state": "CA", "withholding": 14200, "deductions": "standard"},
    {"name": "Michael Chen", "email": "m.chen@email.com", "filing_status": "married_filing_jointly", "wages": 145000, "state": "NY", "withholding": 28500, "deductions": "itemized", "mortgage": 18000, "salt": 10000, "charity": 5000},
    {"name": "Jessica Williams", "email": "jwilliams@email.com", "filing_status": "head_of_household", "wages": 62000, "state": "TX", "withholding": 8200, "children": 2, "deductions": "standard"},
    {"name": "David Martinez", "email": "dmartinez@email.com", "filing_status": "single", "wages": 52000, "se_income": 35000, "state": "FL", "withholding": 7800, "deductions": "standard"},
    {"name": "Emily Brown", "email": "ebrown@email.com", "filing_status": "married_filing_jointly", "wages": 210000, "state": "CA", "withholding": 48000, "children": 3, "deductions": "itemized", "mortgage": 24000, "salt": 10000, "charity": 12000},
    {"name": "Robert Taylor", "email": "rtaylor@email.com", "filing_status": "single", "wages": 38000, "state": "OH", "withholding": 4500, "deductions": "standard"},
    {"name": "Amanda Davis", "email": "adavis@email.com", "filing_status": "married_filing_jointly", "wages": 95000, "state": "IL", "withholding": 17500, "children": 1, "deductions": "standard"},
    {"name": "Christopher Lee", "email": "clee@email.com", "filing_status": "single", "wages": 125000, "dividends": 8500, "ltcg": 15000, "state": "WA", "withholding": 24000, "deductions": "standard"},
    {"name": "Lauren Wilson", "email": "lwilson@email.com", "filing_status": "head_of_household", "wages": 48000, "state": "GA", "withholding": 5600, "children": 1, "deductions": "standard"},
    {"name": "James Anderson", "email": "janderson@email.com", "filing_status": "married_filing_jointly", "wages": 175000, "rental_income": 24000, "rental_expenses": 18000, "state": "NJ", "withholding": 35000, "deductions": "itemized", "mortgage": 22000, "salt": 10000},
    {"name": "Sophia Thomas", "email": "sthomas@email.com", "filing_status": "single", "wages": 72000, "state": "MA", "withholding": 12500, "deductions": "standard"},
    {"name": "Daniel Jackson", "email": "djackson@email.com", "filing_status": "married_filing_jointly", "wages": 88000, "se_income": 45000, "state": "PA", "withholding": 13200, "children": 2, "deductions": "standard"},
    {"name": "Rachel White", "email": "rwhite@email.com", "filing_status": "single", "wages": 155000, "state": "CO", "withholding": 32000, "deductions": "standard", "k401": 23500},
    {"name": "Andrew Harris", "email": "aharris@email.com", "filing_status": "married_filing_jointly", "wages": 320000, "state": "CT", "withholding": 75000, "children": 2, "deductions": "itemized", "mortgage": 30000, "salt": 10000, "charity": 20000},
    {"name": "Megan Clark", "email": "mclark@email.com", "filing_status": "head_of_household", "wages": 55000, "state": "AZ", "withholding": 6800, "children": 3, "deductions": "standard"},
    {"name": "Kevin Lewis", "email": "klewis@email.com", "filing_status": "single", "wages": 42000, "se_income": 18000, "state": "NC", "withholding": 5200, "deductions": "standard"},
    {"name": "Natalie Robinson", "email": "nrobinson@email.com", "filing_status": "married_filing_jointly", "wages": 135000, "state": "MI", "withholding": 25000, "children": 1, "deductions": "standard"},
    {"name": "Mark Walker", "email": "mwalker@email.com", "filing_status": "single", "wages": 98000, "dividends": 3200, "state": "VA", "withholding": 18500, "deductions": "standard"},
    {"name": "Olivia Hall", "email": "ohall@email.com", "filing_status": "married_filing_jointly", "wages": 165000, "state": "MN", "withholding": 32000, "children": 2, "deductions": "itemized", "mortgage": 20000, "salt": 9500, "charity": 8000},
    {"name": "Brian Young", "email": "byoung@email.com", "filing_status": "single", "wages": 28000, "state": "TN", "withholding": 2800, "deductions": "standard"},
]

STATUSES = [
    "draft", "draft", "draft",
    "pending_review", "pending_review", "pending_review", "pending_review", "pending_review",
    "in_review", "in_review", "in_review",
    "approved", "approved", "approved", "approved",
    "pending_review", "in_review", "draft", "approved", "pending_review",
]


def simple_tax_calc(p):
    """Quick tax estimate for seeding."""
    wages = p.get("wages", 0)
    se = p.get("se_income", 0)
    divs = p.get("dividends", 0)
    ltcg = p.get("ltcg", 0)
    rental = max(0, p.get("rental_income", 0) - p.get("rental_expenses", 0))
    total_income = wages + se + divs + ltcg + rental

    # Standard vs itemized
    std_ded = {"single": 15750, "married_filing_jointly": 31500, "head_of_household": 23850, "married_filing_separately": 15750}
    std = std_ded.get(p["filing_status"], 15750)
    itemized = p.get("mortgage", 0) + p.get("salt", 0) + p.get("charity", 0)
    deduction = max(std, itemized)

    # AGI adjustments
    se_ded = se * 0.9235 * 0.5 * 0.153 if se > 0 else 0
    k401 = p.get("k401", 0)
    agi = total_income - se_ded - k401
    taxable = max(0, agi - deduction)

    # Simple progressive calc (2025 single as base)
    tax = 0
    if p["filing_status"] in ("married_filing_jointly",):
        brackets = [(23850, .10), (96950, .12), (206700, .22), (394600, .24), (501050, .32), (751600, .35)]
    else:
        brackets = [(11925, .10), (48475, .12), (103350, .22), (197300, .24), (250525, .32), (626350, .35)]

    prev = 0
    for top, rate in brackets:
        chunk = min(taxable, top) - prev
        if chunk > 0:
            tax += chunk * rate
        prev = top
    if taxable > prev:
        tax += (taxable - prev) * 0.37

    # SE tax
    se_tax = se * 0.9235 * 0.153 if se > 0 else 0

    # Credits
    children = p.get("children", 0)
    ctc = min(children * 2000, tax)

    total_tax = tax + se_tax - ctc
    withholding = p.get("withholding", 0)
    refund_or_owed = withholding - total_tax

    return {
        "total_income": round(total_income),
        "adjusted_gross_income": round(agi),
        "taxable_income": round(taxable),
        "tax_liability": round(total_tax),
        "total_payments": withholding,
        "refund_or_owed": round(refund_or_owed),
        "effective_rate": round(total_tax / max(agi, 1) * 100, 1),
        "filing_status": p["filing_status"],
        "deduction_type": "itemized" if itemized > std else "standard",
        "deduction_amount": round(deduction),
        "standard_deduction": std,
        "total_itemized": round(itemized),
    }


def seed():
    persistence = get_persistence()
    tenant_id = "demo-cpa"
    created = 0

    for i, (profile, status) in enumerate(zip(PROFILES, STATUSES)):
        session_id = f"demo-return-{i+1:03d}"
        calc = simple_tax_calc(profile)

        # Save session state (for CPA queue)
        session_data = {
            "profile": {
                "name": profile["name"],
                "email": profile["email"],
                "filing_status": profile["filing_status"],
                "state": profile.get("state", ""),
                "wages": profile.get("wages", 0),
            },
            "tax_year": 2025,
            "workflow_status": status,
            "state": "completed" if status in ("approved",) else "calculation_complete",
            "calculations": calc,
            "lead_score": random.randint(40, 95),
        }

        days_ago = random.randint(1, 30)
        created_at = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()

        persistence.save_session(
            session_id=session_id,
            tenant_id=tenant_id,
            session_type="intelligent_advisor",
            data=session_data,
            metadata={"source": "golden_path_seed", "created_at": created_at},
        )

        # Save tax return data (for review page and results)
        return_data = {
            "taxpayer": {
                "first_name": profile["name"].split()[0],
                "last_name": profile["name"].split()[-1],
                "email": profile["email"],
                "filing_status": profile["filing_status"],
            },
            "state_of_residence": profile.get("state", ""),
            "tax_year": 2025,
            **calc,
        }

        persistence.save_session_tax_return(
            session_id=session_id,
            tenant_id=tenant_id,
            tax_year=2025,
            return_data=return_data,
            calculated_results=calc,
        )

        status_emoji = {"draft": "D", "pending_review": "P", "in_review": "R", "approved": "A"}
        print(f"  [{status_emoji.get(status, '?')}] {profile['name']:20s} | {profile['filing_status']:25s} | AGI ${calc['adjusted_gross_income']:>10,} | {'Refund' if calc['refund_or_owed'] > 0 else 'Owed'} ${abs(calc['refund_or_owed']):>8,} | {status}")
        created += 1

    print(f"\nSeeded {created} demo returns.")
    print(f"  Draft: {STATUSES.count('draft')}")
    print(f"  Pending Review: {STATUSES.count('pending_review')}")
    print(f"  In Review: {STATUSES.count('in_review')}")
    print(f"  Approved: {STATUSES.count('approved')}")


if __name__ == "__main__":
    print("Seeding Golden Path demo data...\n")
    seed()
    print("\nDone! Restart the server and browse:")
    print("  /cpa/dashboard       — CPA metrics")
    print("  /cpa/returns/queue   — Return queue with real data")
    print("  /cpa/returns/demo-return-001/review — Review a return")
    print("  /results?session_id=demo-return-001  — Client results")
