#!/usr/bin/env python3
"""
Load Test Data into CPA Panel

Loads the generated test data into the running server via API calls.
Also directly populates database tables for faster loading.
"""

import sys
import os
import json
import sqlite3
import requests
from datetime import datetime
from typing import Dict, List, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

BASE_URL = "http://localhost:8000"
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "database", "jorss_gbo.db")


def load_json_data(filepath: str) -> dict:
    """Load test data from JSON file."""
    with open(filepath, "r") as f:
        return json.load(f)


def check_server():
    """Check if server is running."""
    try:
        response = requests.get(f"{BASE_URL}/api/cpa/leads/queue/summary", timeout=5)
        return response.status_code == 200
    except:
        return False


def create_tables_if_needed(conn: sqlite3.Connection):
    """Create necessary tables if they don't exist."""
    cursor = conn.cursor()

    # Tax returns table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tax_returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            client_id TEXT,
            tax_year INTEGER DEFAULT 2024,
            filing_status TEXT,

            -- Income fields
            w2_income INTEGER DEFAULT 0,
            self_employment_income INTEGER DEFAULT 0,
            self_employment_expenses INTEGER DEFAULT 0,
            dividend_income INTEGER DEFAULT 0,
            qualified_dividends INTEGER DEFAULT 0,
            capital_gains INTEGER DEFAULT 0,
            rental_income INTEGER DEFAULT 0,
            rental_expenses INTEGER DEFAULT 0,
            rental_depreciation INTEGER DEFAULT 0,
            social_security_income INTEGER DEFAULT 0,
            pension_income INTEGER DEFAULT 0,
            rmd_income INTEGER DEFAULT 0,
            rsu_income INTEGER DEFAULT 0,
            iso_income INTEGER DEFAULT 0,
            foreign_income INTEGER DEFAULT 0,
            trust_income INTEGER DEFAULT 0,
            crypto_gains INTEGER DEFAULT 0,
            gross_income INTEGER DEFAULT 0,

            -- Adjustments
            adjustments_json TEXT,
            total_adjustments INTEGER DEFAULT 0,
            agi INTEGER DEFAULT 0,

            -- Deductions
            standard_deduction INTEGER DEFAULT 0,
            itemized_deductions_json TEXT,
            total_itemized INTEGER DEFAULT 0,
            uses_standard_deduction INTEGER DEFAULT 1,
            deduction_amount INTEGER DEFAULT 0,
            qbi_deduction INTEGER DEFAULT 0,

            -- Tax calculation
            taxable_income INTEGER DEFAULT 0,
            federal_tax INTEGER DEFAULT 0,
            self_employment_tax INTEGER DEFAULT 0,
            state_tax INTEGER DEFAULT 0,
            credits_json TEXT,
            total_credits INTEGER DEFAULT 0,
            total_tax INTEGER DEFAULT 0,

            -- Payments
            federal_withheld INTEGER DEFAULT 0,
            state_withheld INTEGER DEFAULT 0,
            estimated_payments INTEGER DEFAULT 0,
            total_payments INTEGER DEFAULT 0,

            -- Result
            balance_due INTEGER DEFAULT 0,
            refund_amount INTEGER DEFAULT 0,

            -- Complexity
            complexity_score INTEGER DEFAULT 1,
            complexity_tier TEXT,
            estimated_fee INTEGER DEFAULT 0,

            -- Flags
            has_amt_exposure INTEGER DEFAULT 0,
            has_foreign_reporting INTEGER DEFAULT 0,
            is_multi_state INTEGER DEFAULT 0,
            has_crypto INTEGER DEFAULT 0,
            has_rental_properties INTEGER DEFAULT 0,
            has_business INTEGER DEFAULT 0,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Clients table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT UNIQUE NOT NULL,
            session_id TEXT,
            first_name TEXT,
            last_name TEXT,
            email TEXT,
            phone TEXT,
            address_json TEXT,
            filing_status TEXT,
            profile_type TEXT,
            complexity TEXT,
            state_code TEXT,
            state_name TEXT,
            state_tax_rate REAL,
            spouse_json TEXT,
            dependents_json TEXT,
            base_income INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Recommendations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rec_id TEXT UNIQUE NOT NULL,
            client_id TEXT,
            session_id TEXT,
            category TEXT,
            title TEXT,
            description TEXT,
            estimated_savings INTEGER DEFAULT 0,
            confidence REAL DEFAULT 0.8,
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Engagement letters table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS engagement_letters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engagement_id TEXT UNIQUE NOT NULL,
            client_id TEXT,
            client_name TEXT,
            client_email TEXT,
            service_type TEXT,
            tax_year INTEGER,
            complexity_tier TEXT,
            base_fee INTEGER DEFAULT 0,
            fee_adjustments_json TEXT,
            total_fee INTEGER DEFAULT 0,
            payment_terms TEXT,
            scope_json TEXT,
            status TEXT DEFAULT 'draft',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            valid_until TEXT
        )
    """)

    conn.commit()


def load_clients(conn: sqlite3.Connection, clients: List[dict]):
    """Load clients into database."""
    cursor = conn.cursor()

    for client in clients:
        cursor.execute("""
            INSERT OR REPLACE INTO clients (
                client_id, session_id, first_name, last_name, email, phone,
                address_json, filing_status, profile_type, complexity,
                state_code, state_name, state_tax_rate, spouse_json,
                dependents_json, base_income, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            client["client_id"],
            client["session_id"],
            client["first_name"],
            client["last_name"],
            client["email"],
            client["phone"],
            json.dumps(client.get("address", {})),
            client["filing_status"],
            client["profile_type"],
            client["complexity"],
            client["state_code"],
            client["state_name"],
            client["state_tax_rate"],
            json.dumps(client.get("spouse")) if client.get("spouse") else None,
            json.dumps(client.get("dependents", [])),
            client["base_income"],
            client.get("created_at", datetime.now().isoformat()),
        ))

    conn.commit()
    print(f"  ✓ Loaded {len(clients)} clients")


def load_tax_returns(conn: sqlite3.Connection, tax_returns: List[dict]):
    """Load tax returns into database."""
    cursor = conn.cursor()

    for tr in tax_returns:
        cursor.execute("""
            INSERT OR REPLACE INTO tax_returns (
                session_id, client_id, tax_year, filing_status,
                w2_income, self_employment_income, self_employment_expenses,
                dividend_income, qualified_dividends, capital_gains,
                rental_income, rental_expenses, rental_depreciation,
                social_security_income, pension_income, rmd_income,
                rsu_income, iso_income, foreign_income, trust_income,
                crypto_gains, gross_income, adjustments_json, total_adjustments,
                agi, standard_deduction, itemized_deductions_json, total_itemized,
                uses_standard_deduction, deduction_amount, qbi_deduction,
                taxable_income, federal_tax, self_employment_tax, state_tax,
                credits_json, total_credits, total_tax,
                federal_withheld, state_withheld, estimated_payments, total_payments,
                balance_due, refund_amount, complexity_score, complexity_tier,
                estimated_fee, has_amt_exposure, has_foreign_reporting,
                is_multi_state, has_crypto, has_rental_properties, has_business
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            tr["session_id"], tr["client_id"], tr["tax_year"], tr["filing_status"],
            tr["w2_income"], tr["self_employment_income"], tr["self_employment_expenses"],
            tr["dividend_income"], tr["qualified_dividends"], tr["capital_gains"],
            tr["rental_income"], tr["rental_expenses"], tr["rental_depreciation"],
            tr["social_security_income"], tr["pension_income"], tr["rmd_income"],
            tr["rsu_income"], tr["iso_income"], tr["foreign_income"], tr["trust_income"],
            tr["crypto_gains"], tr["gross_income"],
            json.dumps(tr.get("adjustments", {})), tr["total_adjustments"],
            tr["agi"], tr["standard_deduction"],
            json.dumps(tr.get("itemized_deductions", {})), tr["total_itemized"],
            1 if tr["uses_standard_deduction"] else 0, tr["deduction_amount"], tr["qbi_deduction"],
            tr["taxable_income"], tr["federal_tax"], tr["self_employment_tax"], tr["state_tax"],
            json.dumps(tr.get("credits", {})), tr["total_credits"], tr["total_tax"],
            tr["federal_withheld"], tr["state_withheld"], tr["estimated_payments"], tr["total_payments"],
            tr["balance_due"], tr["refund_amount"], tr["complexity_score"], tr["complexity_tier"],
            tr["estimated_fee"],
            1 if tr.get("has_amt_exposure") else 0,
            1 if tr.get("has_foreign_reporting") else 0,
            1 if tr.get("is_multi_state") else 0,
            1 if tr.get("has_crypto") else 0,
            1 if tr.get("has_rental_properties") else 0,
            1 if tr.get("has_business") else 0,
        ))

    conn.commit()
    print(f"  ✓ Loaded {len(tax_returns)} tax returns")


def load_recommendations(conn: sqlite3.Connection, recommendations: List[dict]):
    """Load recommendations into database."""
    cursor = conn.cursor()

    for rec in recommendations:
        cursor.execute("""
            INSERT OR REPLACE INTO recommendations (
                rec_id, client_id, session_id, category, title,
                description, estimated_savings, confidence, priority, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rec["rec_id"],
            rec["client_id"],
            rec["session_id"],
            rec["category"],
            rec["title"],
            rec["description"],
            rec["estimated_savings"],
            rec["confidence"],
            rec["priority"],
            rec["status"],
            rec.get("created_at", datetime.now().isoformat()),
        ))

    conn.commit()
    print(f"  ✓ Loaded {len(recommendations)} recommendations")


def load_engagement_letters(conn: sqlite3.Connection, engagements: List[dict]):
    """Load engagement letters into database."""
    cursor = conn.cursor()

    for eng in engagements:
        cursor.execute("""
            INSERT OR REPLACE INTO engagement_letters (
                engagement_id, client_id, client_name, client_email,
                service_type, tax_year, complexity_tier, base_fee,
                fee_adjustments_json, total_fee, payment_terms, scope_json,
                status, created_at, valid_until
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            eng["engagement_id"],
            eng["client_id"],
            eng["client_name"],
            eng["client_email"],
            eng["service_type"],
            eng["tax_year"],
            eng["complexity_tier"],
            eng["base_fee"],
            json.dumps(eng.get("fee_adjustments", [])),
            eng["total_fee"],
            eng["payment_terms"],
            json.dumps([s for s in eng.get("scope", []) if s]),
            eng["status"],
            eng.get("created_at", datetime.now().isoformat()),
            eng.get("valid_until"),
        ))

    conn.commit()
    print(f"  ✓ Loaded {len(engagements)} engagement letters")


def load_leads_via_api(leads: List[dict]):
    """Load leads via API to properly trigger state machine."""
    success = 0
    errors = 0

    for lead in leads:
        try:
            # Create lead
            response = requests.post(
                f"{BASE_URL}/api/cpa/leads",
                json={
                    "lead_id": lead["lead_id"],
                    "session_id": lead["session_id"],
                    "tenant_id": lead.get("tenant_id", "default"),
                },
                timeout=5
            )

            if response.status_code != 200:
                errors += 1
                continue

            # Process signals in batch
            if lead.get("signals"):
                response = requests.post(
                    f"{BASE_URL}/api/cpa/leads/{lead['lead_id']}/signals/batch",
                    json={
                        "signals": lead["signals"],
                        "session_id": lead["session_id"],
                    },
                    timeout=10
                )

            success += 1

        except Exception as e:
            errors += 1

    print(f"  ✓ Loaded {success} leads via API ({errors} errors)")


def show_summary(conn: sqlite3.Connection):
    """Show database summary."""
    cursor = conn.cursor()

    print()
    print("=" * 60)
    print("DATABASE SUMMARY")
    print("=" * 60)

    # Clients
    cursor.execute("SELECT COUNT(*) FROM clients")
    print(f"Clients:            {cursor.fetchone()[0]}")

    # Tax returns
    cursor.execute("SELECT COUNT(*) FROM tax_returns")
    print(f"Tax Returns:        {cursor.fetchone()[0]}")

    # By complexity
    cursor.execute("SELECT complexity_tier, COUNT(*) FROM tax_returns GROUP BY complexity_tier ORDER BY COUNT(*) DESC")
    print("\n  By Complexity:")
    for row in cursor.fetchall():
        print(f"    {row[0]}: {row[1]}")

    # By filing status
    cursor.execute("SELECT filing_status, COUNT(*) FROM tax_returns GROUP BY filing_status ORDER BY COUNT(*) DESC")
    print("\n  By Filing Status:")
    for row in cursor.fetchall():
        print(f"    {row[0]}: {row[1]}")

    # Recommendations
    cursor.execute("SELECT COUNT(*) FROM recommendations")
    print(f"\nRecommendations:    {cursor.fetchone()[0]}")

    cursor.execute("SELECT category, COUNT(*) FROM recommendations GROUP BY category ORDER BY COUNT(*) DESC LIMIT 5")
    print("\n  Top Categories:")
    for row in cursor.fetchall():
        print(f"    {row[0]}: {row[1]}")

    # Total savings potential
    cursor.execute("SELECT SUM(estimated_savings) FROM recommendations")
    total_savings = cursor.fetchone()[0] or 0
    print(f"\n  Total Savings Potential: ${total_savings:,.0f}")

    # Engagement letters
    cursor.execute("SELECT COUNT(*) FROM engagement_letters")
    print(f"\nEngagement Letters: {cursor.fetchone()[0]}")

    cursor.execute("SELECT status, COUNT(*) FROM engagement_letters GROUP BY status")
    print("\n  By Status:")
    for row in cursor.fetchall():
        print(f"    {row[0]}: {row[1]}")

    # Total fees
    cursor.execute("SELECT SUM(total_fee) FROM engagement_letters")
    total_fees = cursor.fetchone()[0] or 0
    print(f"\n  Total Quoted Fees: ${total_fees:,.0f}")


def main():
    print("=" * 60)
    print("LOADING TEST DATA INTO CPA PANEL")
    print("=" * 60)
    print()

    # Check server
    print("Checking server...")
    if not check_server():
        print("⚠️  Server not running. Loading data to database only.")
        print("   Start server with: cd src && ../.venv/bin/python -m uvicorn web.app:app --port 8000")
    else:
        print("✓ Server is running")

    # Load JSON data
    json_path = os.path.join(os.path.dirname(__file__), "test_data.json")
    print(f"\nLoading data from: {json_path}")
    data = load_json_data(json_path)

    # Connect to database
    print(f"\nConnecting to database: {DB_PATH}")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    # Create tables
    print("\nCreating tables if needed...")
    create_tables_if_needed(conn)

    # Load data
    print("\nLoading data...")
    load_clients(conn, data["clients"])
    load_tax_returns(conn, data["tax_returns"])
    load_recommendations(conn, data["recommendations"])
    load_engagement_letters(conn, data["engagement_letters"])

    # Load leads via API
    print("\nLoading leads via API...")
    if check_server():
        load_leads_via_api(data["leads"])
    else:
        print("  ⚠️  Skipping API load (server not running)")

    # Show summary
    show_summary(conn)

    conn.close()

    print()
    print("=" * 60)
    print("TEST DATA LOADED SUCCESSFULLY")
    print("=" * 60)
    print()
    print("Dashboard URL: http://localhost:8000/cpa")
    print()


if __name__ == "__main__":
    main()
