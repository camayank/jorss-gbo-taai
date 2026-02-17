#!/usr/bin/env python3
"""
Connor taxpayer funnel launch gate runner.

Runs:
1) preflight checks
2) targeted regression tests
3) optional live smoke test against staging/prod URL

Usage:
  python scripts/run_connor_launch_gate.py
  python scripts/run_connor_launch_gate.py --base-url https://staging.example.com --cpa-slug demo-cpa
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_BIN = sys.executable or "python3"


@dataclass
class GateStep:
    name: str
    cmd: List[str]
    required: bool = True


def run_step(step: GateStep) -> bool:
    print(f"\n=== {step.name} ===")
    printable = " ".join(shlex.quote(part) for part in step.cmd)
    print(f"$ {printable}")
    result = subprocess.run(step.cmd, cwd=str(PROJECT_ROOT))
    if result.returncode == 0:
        print(f"[PASS] {step.name}")
        return True

    marker = "FAIL" if step.required else "WARN"
    print(f"[{marker}] {step.name} (exit={result.returncode})")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Connor funnel launch gate checks")
    parser.add_argument("--base-url", help="Optional deployed URL for live smoke test")
    parser.add_argument("--cpa-slug", default="default", help="CPA slug for live smoke test")
    parser.add_argument("--skip-preflight", action="store_true", help="Skip preflight checks")
    parser.add_argument("--skip-tests", action="store_true", help="Skip pytest checks")
    args = parser.parse_args()

    os.environ.setdefault("PYTHONPYCACHEPREFIX", "/tmp/codex-pycache")

    steps: List[GateStep] = []

    if not args.skip_preflight:
        steps.extend(
            [
                GateStep(
                    name="Preflight (initial)",
                    cmd=[PYTHON_BIN, "scripts/preflight_launch.py", "--mode", "production", "--skip-migration-status"],
                ),
                GateStep(
                    name="Preflight (full)",
                    cmd=[PYTHON_BIN, "scripts/preflight_launch.py", "--mode", "production"],
                ),
            ]
        )

    if not args.skip_tests:
        steps.append(
            GateStep(
                name="Targeted launch tests",
                cmd=[
                    PYTHON_BIN,
                    "-m",
                    "pytest",
                    "tests/test_lead_magnet_connor_funnel.py",
                    "tests/integration/test_lead_magnet_api_smoke.py",
                    "tests/security/test_admin_launch_blockers.py",
                    "tests/security/test_cpa_internal_route_auth.py",
                    "tests/security/test_web_launch_route_guards.py",
                    "tests/security/test_web_duplicate_route_guardrails.py",
                    "-q",
                ],
            )
        )

    if args.base_url:
        steps.append(
            GateStep(
                name="Live smoke test",
                cmd=[
                    PYTHON_BIN,
                    "scripts/smoke_test_lead_magnet.py",
                    "--base-url",
                    args.base_url,
                    "--cpa-slug",
                    args.cpa_slug,
                ],
            )
        )

    if not steps:
        print("No steps selected. Nothing to run.")
        return 0

    all_passed = True
    for step in steps:
        passed = run_step(step)
        if not passed and step.required:
            all_passed = False
            break

    print("\n=== Connor Launch Gate Summary ===")
    if all_passed:
        print("All required checks passed.")
        return 0

    print("Launch gate failed. Resolve blockers and re-run.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
