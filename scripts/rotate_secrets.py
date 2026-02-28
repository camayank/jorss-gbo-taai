#!/usr/bin/env python3
"""
Rotate cryptographic secrets in a .env file.

Generates new secret values while preserving all other configuration.
Use this for quarterly secret rotation or incident response.

Usage:
  python scripts/rotate_secrets.py                          # Rotate ALL secrets
  python scripts/rotate_secrets.py --only JWT_SECRET        # Rotate one secret
  python scripts/rotate_secrets.py --only JWT_SECRET APP_SECRET_KEY  # Rotate specific secrets
  python scripts/rotate_secrets.py --dry-run                # Preview without writing
  python scripts/rotate_secrets.py --env-file .env.production  # Target specific file

IMPORTANT:
  - After rotating ENCRYPTION_MASTER_KEY, existing encrypted PII (email, SSN)
    becomes unreadable. Re-encrypt or migrate data first!
  - After rotating PASSWORD_SALT, all existing passwords are invalidated.
    Users will need to reset passwords.
"""

from __future__ import annotations

import argparse
import secrets
import sys
from datetime import datetime
from pathlib import Path

# Must match generate_secrets.py SECRET_SPECS
SECRET_SPECS = {
    "APP_SECRET_KEY": 32,
    "JWT_SECRET": 32,
    "AUTH_SECRET_KEY": 32,
    "CSRF_SECRET_KEY": 32,
    "ENCRYPTION_MASTER_KEY": 32,
    "SSN_HASH_SECRET": 32,
    "PASSWORD_SALT": 16,
    "SERIALIZER_SECRET_KEY": 32,
    "AUDIT_HMAC_KEY": 32,
}

# Secrets that require special handling before rotation
DANGEROUS_SECRETS = {
    "ENCRYPTION_MASTER_KEY": "Rotating this invalidates ALL encrypted PII (email, phone, SSN). Re-encrypt data first!",
    "PASSWORD_SALT": "Rotating this invalidates ALL user passwords. Requires mass password reset!",
}


def read_env_file(path: Path) -> list[str]:
    """Read .env file preserving all lines (comments, blanks, values)."""
    if not path.exists():
        print(f"Error: {path} not found")
        sys.exit(1)
    return path.read_text().splitlines()


def rotate_in_lines(
    lines: list[str],
    targets: set[str],
) -> tuple[list[str], list[tuple[str, str, str]]]:
    """Replace secret values in-place. Returns (new_lines, [(name, old, new)])."""
    rotated = []
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue

        key, _, old_value = line.partition("=")
        key = key.strip()

        if key in targets and key in SECRET_SPECS:
            new_value = secrets.token_hex(SECRET_SPECS[key])
            new_lines.append(f"{key}={new_value}")
            rotated.append((key, old_value.strip(), new_value))
        else:
            new_lines.append(line)

    return new_lines, rotated


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rotate cryptographic secrets in a .env file"
    )
    parser.add_argument(
        "--env-file", default=".env",
        help="Path to .env file (default: .env)",
    )
    parser.add_argument(
        "--only", nargs="+", metavar="SECRET",
        help="Rotate only these secrets (default: all)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview changes without writing",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Skip confirmation for dangerous secrets",
    )
    args = parser.parse_args()

    env_path = Path(args.env_file)
    lines = read_env_file(env_path)

    if args.only:
        targets = set(args.only)
        unknown = targets - set(SECRET_SPECS.keys())
        if unknown:
            print(f"Error: unknown secret(s): {', '.join(sorted(unknown))}")
            print(f"Valid secrets: {', '.join(sorted(SECRET_SPECS.keys()))}")
            return 1
    else:
        targets = set(SECRET_SPECS.keys())

    # Warn about dangerous rotations
    if not args.force:
        dangerous_targets = targets & set(DANGEROUS_SECRETS.keys())
        if dangerous_targets:
            print("WARNING — Dangerous rotation(s):")
            for name in sorted(dangerous_targets):
                print(f"  {name}: {DANGEROUS_SECRETS[name]}")
            print()
            try:
                answer = input("Continue? [y/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nAborted.")
                return 1
            if answer != "y":
                print("Aborted.")
                return 1

    new_lines, rotated = rotate_in_lines(lines, targets)

    if not rotated:
        print(f"No matching secrets found in {env_path}")
        print("(Secrets must already exist as KEY=value lines in the file)")
        return 0

    print(f"\n{'DRY RUN — ' if args.dry_run else ''}Rotating {len(rotated)} secret(s) in {env_path}:\n")
    for name, old, new in rotated:
        old_preview = old[:8] + "..." if len(old) > 8 else old
        new_preview = new[:8] + "..."
        print(f"  {name}: {old_preview} -> {new_preview}")

    if args.dry_run:
        print("\nDry run complete. No changes written.")
        return 0

    # Update the rotation timestamp comment if present
    timestamp = datetime.now().strftime("%Y-%m-%d")
    final_lines = []
    for line in new_lines:
        if "rotated" in line.lower() and line.strip().startswith("#"):
            final_lines.append(f"# --- Cryptographic Secrets (rotated {timestamp}) ---")
        else:
            final_lines.append(line)

    env_path.write_text("\n".join(final_lines) + "\n")
    print(f"\nRotated {len(rotated)} secret(s). Updated {env_path}")
    print(f"Run: python3 scripts/generate_secrets.py --verify --env-file {env_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
