#!/usr/bin/env python3
"""
Generate cryptographic secrets for Jorss-GBO deployment.

Prints all required secrets in a format ready to paste into deployment
dashboards (Render, Heroku, AWS, etc.) or into a .env file.

Usage:
  python scripts/generate_secrets.py              # Print secrets
  python scripts/generate_secrets.py --env        # Print in .env format
  python scripts/generate_secrets.py --json       # Print as JSON
  python scripts/generate_secrets.py --verify     # Verify current .env secrets
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from pathlib import Path

# All cryptographic secrets required for production deployment.
# Format: (env_var_name, byte_length, description, required_in_production)
SECRET_SPECS = [
    ("APP_SECRET_KEY", 32, "Main application secret (session signing, CSRF)", True),
    ("JWT_SECRET", 32, "JWT token signing key", True),
    ("AUTH_SECRET_KEY", 32, "Authentication service secret", True),
    ("CSRF_SECRET_KEY", 32, "CSRF token generation/validation", True),
    ("ENCRYPTION_MASTER_KEY", 32, "AES-256-GCM encryption for PII (email, SSN)", True),
    ("SSN_HASH_SECRET", 32, "HMAC-SHA256 secret for SSN hashing", True),
    ("PASSWORD_SALT", 16, "Salt for password hashing (bcrypt)", True),
    ("SERIALIZER_SECRET_KEY", 32, "Data serialization signing key", False),
    ("AUDIT_HMAC_KEY", 32, "Audit log HMAC signature key", False),
]

MIN_LENGTHS = {
    "APP_SECRET_KEY": 32,
    "JWT_SECRET": 32,
    "AUTH_SECRET_KEY": 32,
    "CSRF_SECRET_KEY": 32,
    "ENCRYPTION_MASTER_KEY": 32,
    "SSN_HASH_SECRET": 32,
    "PASSWORD_SALT": 16,
    "SERIALIZER_SECRET_KEY": 16,
    "AUDIT_HMAC_KEY": 16,
}


def generate_all() -> list[tuple[str, str, str, bool]]:
    """Generate fresh secrets for all specs."""
    return [
        (name, secrets.token_hex(nbytes), desc, required)
        for name, nbytes, desc, required in SECRET_SPECS
    ]


def print_secrets(generated: list[tuple[str, str, str, bool]]) -> None:
    """Print secrets in human-readable format."""
    print("=" * 70)
    print("  JORSS-GBO PRODUCTION SECRETS")
    print("  Generated with cryptographic randomness (secrets.token_hex)")
    print("=" * 70)
    print()

    for name, value, desc, required in generated:
        tag = "REQUIRED" if required else "optional"
        print(f"  [{tag}] {name}")
        print(f"  {desc}")
        print(f"  {value}")
        print()

    print("-" * 70)
    print("  Copy these into your deployment dashboard (Render, Heroku, etc.)")
    print("  DO NOT commit these values to version control.")
    print("  Run this script again to generate new secrets for rotation.")
    print("-" * 70)


def print_env_format(generated: list[tuple[str, str, str, bool]]) -> None:
    """Print secrets in .env format."""
    print("# Generated secrets — DO NOT commit to version control")
    print(f"# Generated at: {__import__('datetime').datetime.now().isoformat()}")
    print()
    for name, value, desc, required in generated:
        tag = "REQUIRED" if required else "Optional"
        print(f"# {desc} ({tag})")
        print(f"{name}={value}")
        print()


def print_json_format(generated: list[tuple[str, str, str, bool]]) -> None:
    """Print secrets as JSON (for programmatic consumption)."""
    data = {
        name: {"value": value, "description": desc, "required": required}
        for name, value, desc, required in generated
    }
    print(json.dumps(data, indent=2))


def verify_env(env_path: Path) -> int:
    """Verify secrets in an existing .env file."""
    if not env_path.exists():
        print(f"File not found: {env_path}")
        return 1

    env = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()

    placeholders = ("REPLACE_", "CHANGE_ME", "CHANGEME", "<", "YOUR_")
    issues = []
    warnings = []

    for name, nbytes, desc, required in SECRET_SPECS:
        value = env.get(name, "")
        hex_len = nbytes * 2  # each byte = 2 hex chars

        if not value:
            if required:
                issues.append(f"  MISSING: {name} — {desc}")
            else:
                warnings.append(f"  MISSING (optional): {name}")
            continue

        if any(value.upper().startswith(p) for p in placeholders):
            if required:
                issues.append(f"  PLACEHOLDER: {name} = {value}")
            else:
                warnings.append(f"  PLACEHOLDER (optional): {name}")
            continue

        if len(value) < hex_len:
            issues.append(
                f"  TOO SHORT: {name} — {len(value)} chars "
                f"(need {hex_len}+)"
            )
            continue

    # Check non-secret required vars
    for var in ["APP_ENVIRONMENT", "DATABASE_URL"]:
        val = env.get(var, "")
        if not val or any(val.upper().startswith(p) for p in placeholders):
            warnings.append(f"  NOT SET: {var}")

    if issues:
        print(f"FAIL — {len(issues)} issue(s) found:\n")
        for issue in issues:
            print(issue)
        if warnings:
            print(f"\nWarnings ({len(warnings)}):")
            for w in warnings:
                print(w)
        return 1

    print(f"PASS — All {len(SECRET_SPECS)} secrets are properly configured.")
    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings:
            print(w)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate or verify cryptographic secrets for Jorss-GBO"
    )
    parser.add_argument(
        "--env", action="store_true",
        help="Output in .env file format",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="Verify secrets in existing .env file instead of generating",
    )
    parser.add_argument(
        "--env-file", default=".env",
        help="Path to .env file (for --verify mode)",
    )
    args = parser.parse_args()

    if args.verify:
        return verify_env(Path(args.env_file))

    generated = generate_all()

    if args.json:
        print_json_format(generated)
    elif args.env:
        print_env_format(generated)
    else:
        print_secrets(generated)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
