#!/usr/bin/env python3
"""
Launch preflight checks for production readiness.

Validates:
- Required environment variables and secret strength
- Alembic availability
- Alembic revision graph integrity
- Migration status (optional)

Usage:
  python scripts/preflight_launch.py --mode production
  python scripts/preflight_launch.py --mode production --skip-migration-status
"""

from __future__ import annotations

import argparse
import ast
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency path
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERSIONS_DIR = PROJECT_ROOT / "src" / "database" / "alembic" / "versions"
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"

PROD_ENV_VALUES = {"production", "prod", "staging"}
PLACEHOLDER_PREFIXES = ("REPLACE_", "CHANGE_ME", "CHANGEME", "<", "YOUR_")

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
END = "\033[0m"


@dataclass
class Check:
    name: str
    level: str  # PASS/WARN/FAIL
    message: str


def icon(level: str) -> str:
    if level == "PASS":
        return f"{GREEN}OK{END}"
    if level == "WARN":
        return f"{YELLOW}WARN{END}"
    return f"{RED}FAIL{END}"


def is_placeholder(value: Optional[str]) -> bool:
    if value is None:
        return True
    normalized = value.strip()
    if not normalized:
        return True
    upper = normalized.upper()
    return any(upper.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES)


def get_env(name: str) -> str:
    return os.environ.get(name, "").strip()


def get_env_bool(name: str) -> bool:
    return get_env(name).lower() in {"1", "true", "yes", "on"}


def check_required_secret(name: str, min_len: int) -> Optional[str]:
    value = get_env(name)
    if is_placeholder(value):
        return f"{name} is missing"
    if len(value) < min_len:
        return f"{name} is too short ({len(value)} chars, need {min_len}+)"
    return None


def detect_database_configured(require_postgres: bool) -> Tuple[bool, str]:
    database_url = get_env("DATABASE_URL")
    if not is_placeholder(database_url):
        normalized = database_url.lower()
        if require_postgres and not normalized.startswith(
            ("postgresql://", "postgres://", "postgresql+")
        ):
            return False, "DATABASE_URL must use PostgreSQL in production"
        return True, "DATABASE_URL"

    driver = get_env("DB_DRIVER").lower()
    host = get_env("DB_HOST")
    name = get_env("DB_NAME")
    user = get_env("DB_USER")
    if "postgres" in driver and host and name and user:
        return True, "DB_* variables"

    if require_postgres:
        return False, "DATABASE_URL or DB_* (PostgreSQL) not configured"
    return False, "DATABASE_URL or DB_* not configured"


def _read_py_assignment(path: Path, names: Sequence[str]) -> Dict[str, object]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    values: Dict[str, object] = {}

    for node in tree.body:
        target_name: Optional[str] = None
        value_node: Optional[ast.AST] = None

        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    target_name = target.id
                    value_node = node.value
                    break
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target_name = node.target.id
            value_node = node.value

        if target_name in names and value_node is not None:
            try:
                values[target_name] = ast.literal_eval(value_node)
            except Exception:
                values[target_name] = None

    return values


def check_migration_graph() -> Check:
    if not VERSIONS_DIR.exists():
        return Check("Alembic graph", "FAIL", f"Missing directory: {VERSIONS_DIR}")

    revisions: Dict[str, Path] = {}
    down_refs: Dict[str, List[str]] = {}
    failures: List[str] = []

    files = sorted(VERSIONS_DIR.glob("*.py"))
    if not files:
        return Check("Alembic graph", "FAIL", "No migration files found")

    for file in files:
        values = _read_py_assignment(file, ("revision", "down_revision"))
        revision = values.get("revision")
        down_revision = values.get("down_revision")

        if not revision or not isinstance(revision, str):
            failures.append(f"{file.name}: missing/invalid revision")
            continue

        if revision in revisions:
            failures.append(
                f"duplicate revision '{revision}' in {file.name} and {revisions[revision].name}"
            )
            continue

        revisions[revision] = file

        refs: List[str] = []
        if isinstance(down_revision, str):
            refs = [down_revision]
        elif isinstance(down_revision, (tuple, list)):
            refs = [str(r) for r in down_revision if r]
        elif down_revision is None:
            refs = []
        else:
            failures.append(f"{file.name}: invalid down_revision value")

        down_refs[revision] = refs

    if failures:
        return Check("Alembic graph", "FAIL", "; ".join(failures))

    missing_links: List[str] = []
    referenced: set[str] = set()
    for revision, refs in down_refs.items():
        for ref in refs:
            referenced.add(ref)
            if ref not in revisions:
                missing_links.append(f"{revision} -> missing {ref}")

    if missing_links:
        return Check("Alembic graph", "FAIL", "; ".join(missing_links))

    heads = sorted(set(revisions.keys()) - referenced)
    if len(heads) != 1:
        return Check(
            "Alembic graph",
            "FAIL",
            f"expected 1 head revision, found {len(heads)} ({', '.join(heads)})",
        )

    return Check(
        "Alembic graph",
        "PASS",
        f"{len(revisions)} revisions, head={heads[0]}",
    )


def find_python_with_alembic() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    candidates = [sys.executable]
    python3 = shutil.which("python3")
    if python3 and python3 not in candidates:
        candidates.append(python3)

    for executable in candidates:
        cmd = [executable, "-c", "import alembic; print(alembic.__version__)"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            version = proc.stdout.strip() or "unknown"
            return executable, version, None

    return None, None, "Alembic not found in current interpreter or system python3"


def run_cmd(
    cmd: List[str],
    env: Optional[Dict[str, str]] = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def run_alembic_status_check(python_exec: str) -> Check:
    env = dict(os.environ)
    src_path = str(PROJECT_ROOT / "src")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{src_path}{os.pathsep}{existing}" if existing else src_path
    env["PYTHONPYCACHEPREFIX"] = env.get("PYTHONPYCACHEPREFIX", "/tmp/codex-pycache")

    proc = run_cmd(
        [
            python_exec,
            "-m",
            "database.alembic_helpers",
            "check",
        ],
        env=env,
    )

    if proc.returncode == 0:
        return Check("Migration status", "PASS", "database is up to date")

    output = (proc.stdout + "\n" + proc.stderr).strip()
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    tail = " | ".join(lines[-4:]) if lines else "unknown migration error"
    return Check("Migration status", "FAIL", tail)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run launch preflight checks")
    parser.add_argument("--env-file", default=".env", help="Path to env file to load")
    parser.add_argument(
        "--mode",
        default="production",
        choices=["production", "development"],
        help="Validation strictness mode",
    )
    parser.add_argument(
        "--skip-migration-status",
        action="store_true",
        help="Skip DB migration status check (schema graph is still validated)",
    )
    args = parser.parse_args()

    env_file = Path(args.env_file)
    if load_dotenv and env_file.exists():
        load_dotenv(env_file, override=False)

    checks: List[Check] = []
    failures = 0
    warnings = 0

    is_production_mode = args.mode == "production"
    env_name = get_env("APP_ENVIRONMENT").lower() or "unset"
    if is_production_mode and env_name not in PROD_ENV_VALUES:
        checks.append(
            Check(
                "APP_ENVIRONMENT",
                "FAIL",
                f"expected production-like value, found '{env_name}'",
            )
        )
        failures += 1
    else:
        checks.append(Check("APP_ENVIRONMENT", "PASS", f"value='{env_name}'"))

    required_secrets = {
        "APP_SECRET_KEY": 32,
        "JWT_SECRET": 32,
        "AUTH_SECRET_KEY": 32,
        "CSRF_SECRET_KEY": 32,
        "ENCRYPTION_MASTER_KEY": 32,
        "SSN_HASH_SECRET": 32,
        "PASSWORD_SALT": 16,
    }
    optional_secrets = {
        "SERIALIZER_SECRET_KEY": 16,
        "AUDIT_HMAC_KEY": 16,
    }

    secret_values: Dict[str, str] = {}

    for name, min_len in required_secrets.items():
        err = check_required_secret(name, min_len)
        if err:
            checks.append(Check(name, "FAIL", err))
            failures += 1
        else:
            checks.append(Check(name, "PASS", f"configured (len>={min_len})"))
            secret_values[name] = get_env(name)

    for name, min_len in optional_secrets.items():
        value = get_env(name)
        if is_placeholder(value):
            checks.append(Check(name, "WARN", "missing (will be auto-generated)"))
            warnings += 1
        elif len(value) < min_len:
            checks.append(Check(name, "WARN", f"too short ({len(value)} chars, need {min_len}+)"))
            warnings += 1
        else:
            checks.append(Check(name, "PASS", f"configured (len>={min_len})"))
            secret_values[name] = value

    # Uniqueness check: no two secrets should share the same value
    seen: Dict[str, str] = {}
    duplicates: List[str] = []
    for name, value in secret_values.items():
        if value in seen:
            duplicates.append(f"{name} == {seen[value]}")
        else:
            seen[value] = name
    if duplicates:
        checks.append(Check("Secret uniqueness", "FAIL", f"duplicates: {', '.join(duplicates)}"))
        failures += 1
    elif secret_values:
        checks.append(Check("Secret uniqueness", "PASS", f"{len(secret_values)} unique secrets"))

    # Redis check (required for production sessions/cache)
    redis_url = get_env("REDIS_URL")
    redis_host = get_env("REDIS_HOST")
    if not is_placeholder(redis_url):
        checks.append(Check("Redis config", "PASS", "REDIS_URL configured"))
    elif redis_host:
        checks.append(Check("Redis config", "PASS", "REDIS_HOST configured"))
    elif is_production_mode:
        checks.append(Check("Redis config", "FAIL", "REDIS_URL or REDIS_HOST not set"))
        failures += 1
    else:
        checks.append(Check("Redis config", "WARN", "not configured (using in-memory fallback)"))
        warnings += 1

    # CORS origins check (must be set in production)
    cors_origins = get_env("CORS_ORIGINS")
    if is_production_mode:
        if is_placeholder(cors_origins):
            checks.append(Check("CORS_ORIGINS", "FAIL", "not set (required in production)"))
            failures += 1
        elif "*" in cors_origins:
            checks.append(Check("CORS_ORIGINS", "FAIL", "wildcard '*' not allowed in production"))
            failures += 1
        else:
            checks.append(Check("CORS_ORIGINS", "PASS", cors_origins))
    else:
        if is_placeholder(cors_origins):
            checks.append(Check("CORS_ORIGINS", "WARN", "not set (defaults apply in dev)"))
            warnings += 1
        else:
            checks.append(Check("CORS_ORIGINS", "PASS", cors_origins))

    database_ok, database_hint = detect_database_configured(require_postgres=is_production_mode)
    if database_ok:
        checks.append(Check("Database config", "PASS", f"configured via {database_hint}"))
    else:
        checks.append(Check("Database config", "FAIL", database_hint))
        failures += 1

    openai_key = get_env("OPENAI_API_KEY")
    allow_missing_openai = get_env_bool("ALLOW_MISSING_OPENAI")
    if is_placeholder(openai_key):
        if is_production_mode and not allow_missing_openai:
            checks.append(Check("OPENAI_API_KEY", "FAIL", "missing"))
            failures += 1
        else:
            checks.append(Check("OPENAI_API_KEY", "WARN", "missing (AI features disabled)"))
            warnings += 1
    else:
        checks.append(Check("OPENAI_API_KEY", "PASS", "configured"))

    graph_check = check_migration_graph()
    checks.append(graph_check)
    if graph_check.level == "FAIL":
        failures += 1

    py_exec, alembic_version, alembic_err = find_python_with_alembic()
    if py_exec:
        if py_exec == sys.executable:
            checks.append(
                Check("Alembic runtime", "PASS", f"{alembic_version} in {py_exec}")
            )
        else:
            checks.append(
                Check(
                    "Alembic runtime",
                    "WARN",
                    f"{alembic_version} found in fallback interpreter {py_exec}; install in current venv",
                )
            )
            warnings += 1
    else:
        checks.append(Check("Alembic runtime", "FAIL", alembic_err or "not available"))
        failures += 1

    if args.skip_migration_status:
        checks.append(
            Check("Migration status", "WARN", "skipped (--skip-migration-status)")
        )
        warnings += 1
    elif not database_ok:
        checks.append(
            Check(
                "Migration status",
                "WARN",
                "skipped because database config is incomplete",
            )
        )
        warnings += 1
    elif py_exec:
        status_check = run_alembic_status_check(py_exec)
        checks.append(status_check)
        if status_check.level == "FAIL":
            failures += 1

    print(f"\n{BOLD}Launch Preflight ({args.mode}){END}")
    print(f"Project: {PROJECT_ROOT}")
    if env_file.exists():
        print(f"Env file: {env_file}")
    else:
        print(f"Env file: {env_file} (not found)")
    print("-" * 72)
    for check in checks:
        print(f"[{icon(check.level)}] {check.name}: {check.message}")

    print("-" * 72)
    print(f"Failures: {failures} | Warnings: {warnings}")

    if failures:
        print(f"{RED}Preflight failed. Resolve blocking items before launch.{END}")
        return 2

    if warnings:
        print(f"{YELLOW}Preflight passed with warnings.{END}")
        return 0

    print(f"{GREEN}Preflight passed.{END}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
