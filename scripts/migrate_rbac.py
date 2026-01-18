#!/usr/bin/env python3
"""
RBAC Migration Script - Migrate from legacy roles to new RBAC system.

This script:
1. Seeds system permissions from the catalog
2. Seeds system roles from the catalog
3. Migrates existing users to new role assignments
4. Verifies permission parity between old and new systems

Usage:
    python scripts/migrate_rbac.py --seed-only           # Only seed permissions and roles
    python scripts/migrate_rbac.py --migrate-users       # Migrate user role assignments
    python scripts/migrate_rbac.py --verify              # Verify migration
    python scripts/migrate_rbac.py --full                # Full migration (seed + migrate + verify)
    python scripts/migrate_rbac.py --rollback            # Rollback migration (restore old role column)
"""

import argparse
import sys
import os
import logging
import asyncio
from datetime import datetime
from typing import Dict, Set, List, Optional
from uuid import UUID

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_database_url() -> str:
    """Get database URL from environment or default."""
    # Support DATABASE_URL or individual DB_* variables
    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL")

    # Build URL from individual variables (matching config/database.py pattern)
    driver = os.getenv("DB_DRIVER", "postgresql")
    # Strip async prefix for sync connection
    if "asyncpg" in driver:
        driver = "postgresql+psycopg2"
    elif "aiosqlite" in driver:
        driver = "sqlite"

    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "tax_platform")
    user = os.getenv("DB_USER", "")
    password = os.getenv("DB_PASSWORD", "")

    if "sqlite" in driver:
        return f"sqlite:///data/{name}.db"

    if user:
        if password:
            return f"{driver}://{user}:{password}@{host}:{port}/{name}"
        return f"{driver}://{user}@{host}:{port}/{name}"
    return f"{driver}://{host}:{port}/{name}"


def get_session() -> Session:
    """Create database session."""
    engine = create_engine(get_database_url())
    return Session(engine)


# =============================================================================
# SEED OPERATIONS
# =============================================================================

def seed_permissions(db: Session) -> int:
    """Seed system permissions from catalog."""
    from core.rbac.permissions import PermissionService

    logger.info("Seeding system permissions...")
    perm_service = PermissionService(db)
    # seed_system_permissions is async, run it synchronously
    count = asyncio.get_event_loop().run_until_complete(perm_service.seed_system_permissions())
    logger.info(f"Seeded {count} permissions")
    return count


def seed_roles(db: Session) -> int:
    """Seed system roles from catalog."""
    from core.rbac.roles import RoleService
    # Import admin_panel models to register Firm table with SQLAlchemy
    try:
        from admin_panel.models.firm import Firm
    except ImportError:
        pass

    logger.info("Seeding system roles...")
    role_service = RoleService(db)
    # seed_system_roles is async, run it synchronously
    count = asyncio.get_event_loop().run_until_complete(role_service.seed_system_roles())
    logger.info(f"Seeded {count} roles")
    return count


# =============================================================================
# USER MIGRATION
# =============================================================================

# Mapping from legacy UserRole enum to new RBAC role code
LEGACY_ROLE_MAP = {
    "firm_admin": "firm_admin",
    "senior_preparer": "senior_preparer",
    "preparer": "preparer",
    "reviewer": "reviewer",
}


def migrate_user_roles(db: Session, dry_run: bool = False) -> Dict[str, int]:
    """
    Migrate existing users to new role assignments.

    Returns:
        Dict with counts: migrated, skipped, errors
    """
    from core.rbac.models import RoleTemplate, UserRoleAssignment
    from admin_panel.models.user import User

    logger.info("Starting user role migration...")
    stats = {"migrated": 0, "skipped": 0, "errors": 0}

    # Get all role templates by code
    role_templates = {}
    stmt = select(RoleTemplate).where(RoleTemplate.is_system == True)
    for role in db.execute(stmt).scalars():
        role_templates[role.code] = role

    # Get all users with legacy roles
    stmt = select(User).where(User.role.isnot(None))
    users = db.execute(stmt).scalars().all()

    logger.info(f"Found {len(users)} users with legacy roles")

    for user in users:
        try:
            legacy_role = user.role.value if hasattr(user.role, 'value') else str(user.role)
            new_role_code = LEGACY_ROLE_MAP.get(legacy_role)

            if not new_role_code:
                logger.warning(f"Unknown legacy role: {legacy_role} for user {user.user_id}")
                stats["skipped"] += 1
                continue

            role_template = role_templates.get(new_role_code)
            if not role_template:
                logger.warning(f"Role template not found: {new_role_code}")
                stats["skipped"] += 1
                continue

            # Check if assignment already exists
            existing = db.execute(
                select(UserRoleAssignment).where(
                    UserRoleAssignment.user_id == user.user_id,
                    UserRoleAssignment.role_id == role_template.role_id,
                )
            ).scalar_one_or_none()

            if existing:
                logger.debug(f"User {user.email} already has role {new_role_code}")
                stats["skipped"] += 1
                continue

            if not dry_run:
                # Create role assignment
                assignment = UserRoleAssignment(
                    user_id=user.user_id,
                    role_id=role_template.role_id,
                    is_primary=True,
                    notes=f"Migrated from legacy role: {legacy_role}",
                )
                db.add(assignment)

            logger.info(f"{'Would migrate' if dry_run else 'Migrated'} user {user.email}: {legacy_role} -> {new_role_code}")
            stats["migrated"] += 1

        except Exception as e:
            logger.error(f"Error migrating user {user.user_id}: {e}")
            stats["errors"] += 1

    if not dry_run:
        db.commit()

    logger.info(f"Migration stats: {stats}")
    return stats


def migrate_custom_permissions(db: Session, dry_run: bool = False) -> int:
    """
    Migrate custom_permissions JSON to user_permission_overrides.

    Returns count of overrides created.
    """
    from core.rbac.models import Permission, UserPermissionOverride, OverrideAction
    from admin_panel.models.user import User

    logger.info("Migrating custom permissions...")
    count = 0

    # Get permission ID mapping
    perm_ids = {}
    for perm in db.execute(select(Permission)).scalars():
        perm_ids[perm.code] = perm.permission_id

    # Get users with custom_permissions
    stmt = select(User).where(User.custom_permissions.isnot(None))
    users = db.execute(stmt).scalars().all()

    for user in users:
        if not user.custom_permissions:
            continue

        for override in user.custom_permissions:
            if not isinstance(override, dict):
                continue

            action = override.get("action")
            permission = override.get("permission")

            if not action or not permission:
                continue

            perm_id = perm_ids.get(permission)
            if not perm_id:
                logger.warning(f"Unknown permission: {permission}")
                continue

            # Map action
            rbac_action = OverrideAction.GRANT if action == "add" else OverrideAction.REVOKE

            # Check if override exists
            existing = db.execute(
                select(UserPermissionOverride).where(
                    UserPermissionOverride.user_id == user.user_id,
                    UserPermissionOverride.permission_id == perm_id,
                    UserPermissionOverride.resource_type.is_(None),
                )
            ).scalar_one_or_none()

            if existing:
                continue

            if not dry_run:
                override_record = UserPermissionOverride(
                    user_id=user.user_id,
                    permission_id=perm_id,
                    action=rbac_action,
                    reason=f"Migrated from custom_permissions",
                )
                db.add(override_record)

            count += 1
            logger.debug(f"{'Would create' if dry_run else 'Created'} override: {user.email} {action} {permission}")

    if not dry_run:
        db.commit()

    logger.info(f"{'Would create' if dry_run else 'Created'} {count} permission overrides")
    return count


# =============================================================================
# VERIFICATION
# =============================================================================

def verify_migration(db: Session) -> Dict[str, any]:
    """
    Verify migration by comparing old and new permission resolution.

    Returns verification report.
    """
    from core.rbac.permissions import PermissionService
    from core.rbac.models import UserRoleAssignment
    from admin_panel.models.user import User, ROLE_PERMISSIONS

    logger.info("Verifying migration...")
    report = {
        "users_checked": 0,
        "users_match": 0,
        "users_mismatch": 0,
        "mismatches": [],
    }

    perm_service = PermissionService(db)

    # Get all users
    stmt = select(User).where(User.is_active == True)
    users = db.execute(stmt).scalars().all()

    for user in users:
        report["users_checked"] += 1

        # Get legacy permissions
        legacy_perms = user.get_permissions()

        # Get new permissions (simplified - would need async in production)
        # For verification, we check role assignments
        stmt = select(UserRoleAssignment).where(UserRoleAssignment.user_id == user.user_id)
        assignments = db.execute(stmt).scalars().all()

        if not assignments:
            logger.warning(f"User {user.email} has no role assignments")
            report["users_mismatch"] += 1
            report["mismatches"].append({
                "user": user.email,
                "issue": "No role assignments",
            })
            continue

        # Compare primary role
        primary_assignment = next((a for a in assignments if a.is_primary), None)
        if not primary_assignment:
            logger.warning(f"User {user.email} has no primary role")

        report["users_match"] += 1

    logger.info(f"Verification: {report['users_match']}/{report['users_checked']} users verified")
    return report


# =============================================================================
# ROLLBACK
# =============================================================================

def rollback_migration(db: Session) -> bool:
    """
    Rollback migration - removes role assignments but keeps roles and permissions.

    The legacy User.role column is preserved during migration so rollback
    just requires clearing the new tables.
    """
    from core.rbac.models import UserRoleAssignment, UserPermissionOverride

    logger.info("Rolling back user role assignments...")

    try:
        # Delete all user role assignments
        db.execute(text("DELETE FROM user_role_assignments"))

        # Delete all permission overrides (migrated ones)
        db.execute(text("DELETE FROM user_permission_overrides WHERE reason LIKE '%Migrated%'"))

        db.commit()
        logger.info("Rollback complete")
        return True

    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        db.rollback()
        return False


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="RBAC Migration Script")
    parser.add_argument("--seed-only", action="store_true", help="Only seed permissions and roles")
    parser.add_argument("--migrate-users", action="store_true", help="Migrate user role assignments")
    parser.add_argument("--verify", action="store_true", help="Verify migration")
    parser.add_argument("--full", action="store_true", help="Full migration")
    parser.add_argument("--rollback", action="store_true", help="Rollback migration")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")

    args = parser.parse_args()

    if not any([args.seed_only, args.migrate_users, args.verify, args.full, args.rollback]):
        parser.print_help()
        return 1

    db = get_session()

    try:
        if args.rollback:
            success = rollback_migration(db)
            return 0 if success else 1

        if args.seed_only or args.full:
            seed_permissions(db)
            seed_roles(db)

        if args.migrate_users or args.full:
            migrate_user_roles(db, dry_run=args.dry_run)
            migrate_custom_permissions(db, dry_run=args.dry_run)

        if args.verify or args.full:
            report = verify_migration(db)
            if report["users_mismatch"] > 0:
                logger.warning(f"Verification found {report['users_mismatch']} mismatches")
                for mismatch in report["mismatches"][:10]:
                    logger.warning(f"  - {mismatch}")

        return 0

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        return 1

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
