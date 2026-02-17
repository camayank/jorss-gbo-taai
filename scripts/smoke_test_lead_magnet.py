#!/usr/bin/env python3
"""
Lead magnet staging smoke test (taxpayer funnel).

Validates the Connor-style end-taxpayer path against a live/staging deployment:
1. Landing page responds
2. Session starts
3. Profile submission returns score/personalization payload
4. Tier-1 report returns comparison/share payload
5. Contact capture succeeds (lead conversion)
6. Report is still retrievable with lead attached

Usage:
  python scripts/smoke_test_lead_magnet.py --base-url https://your-app.example.com --cpa-slug demo-cpa
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


DEFAULT_TIMEOUT = 20


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str


def _request_json(
    method: str,
    url: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Tuple[int, Dict[str, Any]]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, data=body, headers=headers, method=method.upper())

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
            raw = resp.read().decode("utf-8")
            parsed = json.loads(raw) if raw else {}
            return status, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"raw": raw}
        return exc.code, parsed


def _request_text(method: str, url: str, timeout: int = DEFAULT_TIMEOUT) -> Tuple[int, str]:
    req = urllib.request.Request(url=url, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def _ok(status: int, low: int = 200, high: int = 299) -> bool:
    return low <= status <= high


def run_smoke(base_url: str, cpa_slug: str, timeout: int = DEFAULT_TIMEOUT) -> int:
    base = base_url.rstrip("/")
    results: list[StepResult] = []

    # 1) Landing page
    landing_url = f"{base}/lead-magnet/?cpa={urllib.parse.quote(cpa_slug)}"
    status, html = _request_text("GET", landing_url, timeout=timeout)
    landing_ok = _ok(status) and "Tax Health Score" in html
    results.append(
        StepResult(
            name="landing_page",
            ok=landing_ok,
            detail=f"status={status}, contains_tax_health_score={'yes' if 'Tax Health Score' in html else 'no'}",
        )
    )
    if not landing_ok:
        return _print_and_exit(results, code=2)

    # 2) Start session
    start_url = f"{base}/api/cpa/lead-magnet/start"
    status, start_payload = _request_json(
        "POST",
        start_url,
        {"cpa_slug": cpa_slug, "assessment_mode": "quick", "referral_source": "smoke_test"},
        timeout=timeout,
    )
    session_id = start_payload.get("session_id")
    start_ok = _ok(status) and bool(session_id)
    results.append(
        StepResult(
            name="start_session",
            ok=start_ok,
            detail=f"status={status}, session_id={'present' if session_id else 'missing'}",
        )
    )
    if not start_ok:
        return _print_and_exit(results, code=2)

    # 3) Submit profile
    profile_url = f"{base}/api/cpa/lead-magnet/{session_id}/profile"
    profile_payload = {
        "filing_status": "single",
        "state_code": "CA",
        "dependents_count": 1,
        "has_children_under_17": True,
        "income_range": "200k_500k",
        "income_sources": ["self_employed", "investments"],
        "is_homeowner": True,
        "retirement_savings": "none",
        "healthcare_type": "hdhp_hsa",
        "life_events": ["new_job", "business_start"],
        "has_student_loans": False,
        "has_business": True,
        "privacy_consent": True,
    }
    status, profile_result = _request_json("POST", profile_url, profile_payload, timeout=timeout)
    has_score = bool(profile_result.get("score_preview"))
    has_personalization = bool(profile_result.get("personalization_line"))
    profile_ok = _ok(status) and has_score and has_personalization
    results.append(
        StepResult(
            name="submit_profile",
            ok=profile_ok,
            detail=(
                f"status={status}, score_preview={'yes' if has_score else 'no'}, "
                f"personalization_line={'yes' if has_personalization else 'no'}"
            ),
        )
    )
    if not profile_ok:
        return _print_and_exit(results, code=2)

    # 4) Get Tier-1 report
    report_url = f"{base}/api/cpa/lead-magnet/{session_id}/report"
    status, report_payload = _request_json("GET", report_url, timeout=timeout)
    has_comparison = bool(report_payload.get("comparison_chart"))
    has_share = bool(report_payload.get("share_payload"))
    has_tax_score = bool(report_payload.get("tax_health_score"))
    report_ok = _ok(status) and has_comparison and has_share and has_tax_score
    results.append(
        StepResult(
            name="tier1_report_before_contact",
            ok=report_ok,
            detail=(
                f"status={status}, tax_health_score={'yes' if has_tax_score else 'no'}, "
                f"comparison_chart={'yes' if has_comparison else 'no'}, "
                f"share_payload={'yes' if has_share else 'no'}"
            ),
        )
    )
    if not report_ok:
        return _print_and_exit(results, code=2)

    # 5) Capture contact (conversion)
    contact_url = f"{base}/api/cpa/lead-magnet/{session_id}/contact"
    form_started_at_ms = int(time.time() * 1000) - 3000
    contact_payload = {
        "first_name": "Smoke",
        "email": f"smoke+{int(time.time())}@example.com",
        "phone": "5555551212",
        "website": "",
        "form_started_at_ms": form_started_at_ms,
    }
    status, contact_result = _request_json("POST", contact_url, contact_payload, timeout=timeout)
    lead_id = contact_result.get("lead_id")
    contact_ok = _ok(status) and bool(lead_id)
    results.append(
        StepResult(
            name="capture_contact",
            ok=contact_ok,
            detail=f"status={status}, lead_id={'present' if lead_id else 'missing'}",
        )
    )
    if not contact_ok:
        return _print_and_exit(results, code=2)

    # 6) Report after contact should include lead_id
    status, report_after_payload = _request_json("GET", report_url, timeout=timeout)
    report_after_ok = _ok(status) and bool(report_after_payload.get("lead_id"))
    results.append(
        StepResult(
            name="tier1_report_after_contact",
            ok=report_after_ok,
            detail=f"status={status}, lead_id={'present' if report_after_payload.get('lead_id') else 'missing'}",
        )
    )

    return _print_and_exit(results, code=0 if report_after_ok else 2)


def _print_and_exit(results: list[StepResult], code: int) -> int:
    print("=" * 72)
    print("Lead Magnet Smoke Test")
    print("=" * 72)
    for step in results:
        marker = "PASS" if step.ok else "FAIL"
        print(f"[{marker}] {step.name}: {step.detail}")
    print("-" * 72)
    if code == 0:
        print("Smoke test passed.")
    else:
        print("Smoke test failed.")
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description="Run taxpayer funnel smoke test against staging/prod")
    parser.add_argument("--base-url", required=True, help="Base URL, e.g. https://staging.example.com")
    parser.add_argument("--cpa-slug", default="default", help="CPA slug to test branded flow")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP request timeout seconds")
    args = parser.parse_args()

    return run_smoke(base_url=args.base_url, cpa_slug=args.cpa_slug, timeout=args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
