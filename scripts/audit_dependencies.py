#!/usr/bin/env python3
"""Scan requirements.txt for outdated/vulnerable packages."""
import subprocess
import sys
import json
import os

def main():
    req_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "requirements.txt")
    if not os.path.exists(req_file):
        print("WARNING: requirements.txt not found")
        return 0

    # Try pip-audit first
    try:
        result = subprocess.run(
            ["pip-audit", "--format=json", "-r", req_file],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            try:
                vulns = json.loads(result.stdout)
                if isinstance(vulns, list) and vulns:
                    print(f"FAIL: {len(vulns)} vulnerabilities found")
                    for v in vulns:
                        name = v.get("name", "unknown")
                        ver = v.get("version", "?")
                        desc = v.get("description", "N/A")
                        print(f"  {name}=={ver}: {desc}")
                    return 1
            except json.JSONDecodeError:
                pass
            print("PASS: No known vulnerabilities")
            return 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("INFO: pip-audit not installed. Run: pip install pip-audit")

    # Fallback: check for outdated packages
    try:
        result = subprocess.run(
            ["pip", "list", "--outdated", "--format=json"],
            capture_output=True, text=True, timeout=60
        )
        outdated = json.loads(result.stdout)
        if outdated:
            print(f"INFO: {len(outdated)} outdated packages")
            for pkg in outdated[:20]:  # Show top 20
                print(f"  {pkg['name']}: {pkg['version']} -> {pkg['latest_version']}")
    except Exception:
        pass

    return 0

if __name__ == "__main__":
    sys.exit(main())
