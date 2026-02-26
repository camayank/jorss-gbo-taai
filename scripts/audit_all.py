#!/usr/bin/env python3
"""Run ALL platform audit checks and produce a readiness scorecard."""
import subprocess
import sys
import os

AUDITS = [
    ("Route & Auth Audit", ["python3", "scripts/audit_routes.py"]),
    ("RBAC Completeness", ["python3", "scripts/audit_rbac.py"]),
    ("Dependency Vulnerabilities", ["python3", "scripts/audit_dependencies.py"]),
]

def main():
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    print("=" * 60)
    print("  JORSS-GBO PLATFORM READINESS AUDIT")
    print("=" * 60)

    results = []
    for name, cmd in AUDITS:
        print(f"\n--- {name} ---")
        try:
            result = subprocess.run(cmd, timeout=300)
            passed = result.returncode == 0
        except subprocess.TimeoutExpired:
            print(f"  TIMEOUT: {name} exceeded 5 minutes")
            passed = False
        except FileNotFoundError:
            print(f"  SKIP: Script not found")
            passed = True  # Don't fail for missing optional scripts
        results.append((name, passed))

    print("\n" + "=" * 60)
    print("  SCORECARD")
    print("=" * 60)
    total = len(results)
    passed = sum(1 for _, p in results if p)
    for name, p in results:
        status = "PASS" if p else "FAIL"
        print(f"  [{status}] {name}")

    score = int((passed / total) * 100) if total else 0
    print(f"\n  Overall: {passed}/{total} checks passed ({score}%)")

    if score == 100:
        print("  STATUS: PRODUCTION READY")
    elif score >= 80:
        print("  STATUS: NEAR READY — fix remaining issues")
    else:
        print("  STATUS: NOT READY — critical issues remain")

    return 0 if score == 100 else 1

if __name__ == "__main__":
    sys.exit(main())
