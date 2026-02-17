#!/usr/bin/env python3
"""
Bootstrap launch-ready environment variables into .env.

What this script does:
- Preserves existing .env keys
- Generates strong secrets for missing/placeholder keys
- Sets production-safe defaults
- Flags values that must be supplied manually (DATABASE_URL, OPENAI_API_KEY)

Usage:
  python scripts/setup_launch_env.py
  python scripts/setup_launch_env.py --env-file .env --environment production
  python scripts/setup_launch_env.py --database-url "postgresql://..." --openai-api-key "sk-..."
"""

from __future__ import annotations

import argparse
import secrets
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Tuple


PLACEHOLDER_PREFIXES = ("REPLACE_", "CHANGE_ME", "CHANGEME", "<", "YOUR_")


def is_placeholder(value: str) -> bool:
    text = (value or "").strip()
    if not text:
        return True
    upper = text.upper()
    return any(upper.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES)


def parse_env_file(path: Path) -> OrderedDict[str, str]:
    values: OrderedDict[str, str] = OrderedDict()
    if not path.exists():
        return values

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def set_if_missing_or_placeholder(
    env: OrderedDict[str, str],
    key: str,
    value: str,
) -> bool:
    current = env.get(key, "")
    if key not in env or is_placeholder(current):
        env[key] = value
        return True
    return False


def write_env(path: Path, env: OrderedDict[str, str]) -> None:
    lines = [
        "# Auto-generated launch bootstrap values",
        "# Review and replace placeholder values before production launch.",
        "",
    ]
    for key, value in env.items():
        lines.append(f"{key}={value}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap launch env variables")
    parser.add_argument("--env-file", default=".env", help="Path to .env file")
    parser.add_argument(
        "--environment",
        default="production",
        choices=["production", "staging", "development"],
        help="Environment to write",
    )
    parser.add_argument("--database-url", default="", help="Set DATABASE_URL")
    parser.add_argument("--openai-api-key", default="", help="Set OPENAI_API_KEY")
    args = parser.parse_args()

    env_path = Path(args.env_file)
    env = parse_env_file(env_path)

    changes: List[str] = []

    if set_if_missing_or_placeholder(env, "APP_ENVIRONMENT", args.environment):
        changes.append("APP_ENVIRONMENT")
    if set_if_missing_or_placeholder(env, "ENVIRONMENT", args.environment):
        changes.append("ENVIRONMENT")

    enforce_https = "true" if args.environment in {"production", "staging"} else "false"
    if set_if_missing_or_placeholder(env, "APP_ENFORCE_HTTPS", enforce_https):
        changes.append("APP_ENFORCE_HTTPS")

    secret_specs: List[Tuple[str, int]] = [
        ("APP_SECRET_KEY", 32),
        ("JWT_SECRET", 32),
        ("AUTH_SECRET_KEY", 32),
        ("CSRF_SECRET_KEY", 32),
        ("ENCRYPTION_MASTER_KEY", 32),
        ("SSN_HASH_SECRET", 32),
        ("SERIALIZER_SECRET_KEY", 32),
        ("AUDIT_HMAC_KEY", 32),
        ("PASSWORD_SALT", 16),
    ]

    for key, nbytes in secret_specs:
        if set_if_missing_or_placeholder(env, key, secrets.token_hex(nbytes)):
            changes.append(key)

    if args.database_url:
        env["DATABASE_URL"] = args.database_url.strip()
        changes.append("DATABASE_URL")
    else:
        set_if_missing_or_placeholder(env, "DATABASE_URL", "REPLACE_WITH_DATABASE_URL")

    if args.openai_api_key:
        env["OPENAI_API_KEY"] = args.openai_api_key.strip()
        changes.append("OPENAI_API_KEY")
    else:
        set_if_missing_or_placeholder(env, "OPENAI_API_KEY", "REPLACE_WITH_OPENAI_API_KEY")

    set_if_missing_or_placeholder(env, "LOG_LEVEL", "INFO")
    set_if_missing_or_placeholder(env, "DB_PERSISTENCE", "true")
    set_if_missing_or_placeholder(env, "UNIFIED_FILING", "true")

    write_env(env_path, env)

    unresolved = []
    if is_placeholder(env.get("DATABASE_URL", "")):
        unresolved.append("DATABASE_URL")
    if is_placeholder(env.get("OPENAI_API_KEY", "")):
        unresolved.append("OPENAI_API_KEY")

    print(f"Wrote {env_path}")
    if changes:
        print(f"Updated keys: {', '.join(changes)}")
    else:
        print("No key updates were required.")

    if unresolved:
        print(f"Manual values still required: {', '.join(unresolved)}")
        return 1

    print("Environment bootstrap complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

