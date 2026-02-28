#!/usr/bin/env python3
"""
Production Smoke Test — Jorss-GBO Tax Platform

Hits critical endpoints after deployment to verify the app is running.

Usage:
    python scripts/smoke_test.py https://your-app.onrender.com
    python scripts/smoke_test.py http://localhost:8000
    python scripts/smoke_test.py  # defaults to http://localhost:8000
"""

import sys
import json
import time
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# Test definitions
# ---------------------------------------------------------------------------
TESTS = [
    # (method, path, expected_status, body_check_key, body_check_value, description)
    ("GET",  "/",                    200, None, None, "Landing page"),
    ("GET",  "/api/health",          200, "status", "healthy", "API health"),
    ("GET",  "/login",               200, None, None, "Login page"),
    ("GET",  "/intelligent-advisor", 200, None, None, "Advisor page"),
    ("GET",  "/static/css/core/variables.css", 200, None, None, "Static CSS"),
    ("POST", "/api/calculate-tax",   200, None, None, "Tax calculation"),
]

CALCULATE_TAX_BODY = json.dumps({
    "filing_status": "single",
    "tax_year": 2025,
    "income": {"wages": 75000},
}).encode("utf-8")


def run_test(base_url: str, method: str, path: str, expected_status: int,
             body_key: str | None, body_value: str | None, desc: str) -> bool:
    """Run a single endpoint test. Returns True on pass."""
    url = f"{base_url.rstrip('/')}{path}"
    start = time.time()

    try:
        req = urllib.request.Request(url, method=method)
        req.add_header("Accept", "application/json, text/html")

        if method == "POST" and path == "/api/calculate-tax":
            req.add_header("Content-Type", "application/json")
            req.data = CALCULATE_TAX_BODY

        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", errors="replace")
            elapsed = int((time.time() - start) * 1000)

    except urllib.error.HTTPError as e:
        status = e.code
        body = ""
        elapsed = int((time.time() - start) * 1000)
    except Exception as e:
        print(f"  FAIL  {desc:30s}  error: {e}")
        return False

    # Check status
    if status != expected_status:
        print(f"  FAIL  {desc:30s}  expected {expected_status}, got {status} ({elapsed}ms)")
        return False

    # Check body content
    if body_key and body_value:
        try:
            data = json.loads(body)
            actual = data.get(body_key)
            if str(actual) != str(body_value):
                print(f"  FAIL  {desc:30s}  {body_key}={actual!r}, expected {body_value!r} ({elapsed}ms)")
                return False
        except (json.JSONDecodeError, AttributeError):
            print(f"  FAIL  {desc:30s}  response is not valid JSON ({elapsed}ms)")
            return False

    print(f"  PASS  {desc:30s}  {status} ({elapsed}ms)")
    return True


def main():
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

    print("=" * 60)
    print("Jorss-GBO Smoke Test")
    print(f"Target: {base_url}")
    print("=" * 60)

    passed = 0
    failed = 0

    for method, path, expected, bk, bv, desc in TESTS:
        if run_test(base_url, method, path, expected, bk, bv, desc):
            passed += 1
        else:
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
