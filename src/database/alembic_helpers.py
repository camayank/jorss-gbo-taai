"""Alembic migration helpers for PostgreSQL.

Provides async-compatible utilities for running and managing Alembic migrations
programmatically. Complements the existing SQLite migrations module.

Usage:
    from database.alembic_helpers import AlembicManager

    manager = AlembicManager()

    # Check current revision
    current = await manager.get_current_revision()

    # Check if migrations are needed
    if await manager.has_pending_migrations():
        manager.upgrade()

    # Or use convenience functions
    from database.alembic_helpers import check_migrations_on_startup
    await check_migrations_on_startup()
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# Handle optional alembic import
try:
    from alembic import command
    from alembic.config import Config
    from alembic.util.exc import CommandError
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
    ALEMBIC_AVAILABLE = True
except ImportError:
    ALEMBIC_AVAILABLE = False
    command = None
    Config = None
    CommandError = Exception
    MigrationContext = None
    ScriptDirectory = None

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from config.database import DatabaseSettings, get_database_settings

logger = logging.getLogger(__name__)


# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"
ALEMBIC_DIR = Path(__file__).parent / "alembic"


@dataclass
class MigrationInfo:
    """Information about a migration revision."""

    revision: str
    down_revision: Optional[str]
    description: str
    is_head: bool = False
    is_current: bool = False


@dataclass
class AlembicStatus:
    """Current Alembic migration status."""

    current_revision: Optional[str]
    head_revision: str
    pending_count: int
    pending_revisions: List[str]
    is_up_to_date: bool
    database_type: str


class AlembicManager:
    """Manages database migrations using Alembic.

    Provides both sync and async methods for common migration operations.
    Designed for PostgreSQL async migrations but also works with SQLite.

    Example:
        manager = AlembicManager()

        # Get status
        status = await manager.get_status()
        print(f"Current: {status.current_revision}")
        print(f"Pending: {status.pending_count}")

        # Upgrade to latest
        if not status.is_up_to_date:
            manager.upgrade()
    """

    def __init__(
        self,
        settings: Optional[DatabaseSettings] = None,
        alembic_ini: Optional[Path] = None,
    ):
        """Initialize Alembic manager.

        Args:
            settings: Database settings. Uses default if not provided.
            alembic_ini: Path to alembic.ini. Uses default if not provided.

        Raises:
            ImportError: If Alembic is not installed.
        """
        if not ALEMBIC_AVAILABLE:
            raise ImportError(
                "Alembic is not installed. Install with: pip install alembic"
            )

        self._settings = settings or get_database_settings()
        self._alembic_ini = alembic_ini or ALEMBIC_INI
        self._config: Optional[Config] = None

    @property
    def settings(self) -> DatabaseSettings:
        """Get database settings."""
        return self._settings

    def _get_config(self) -> Config:
        """Get Alembic configuration."""
        if self._config is None:
            if not self._alembic_ini.exists():
                raise FileNotFoundError(
                    f"Alembic config not found: {self._alembic_ini}"
                )
            self._config = Config(str(self._alembic_ini))
            # Override URL from settings
            self._config.set_main_option(
                "sqlalchemy.url", self._settings.sync_url
            )
        return self._config

    def _get_script_directory(self) -> ScriptDirectory:
        """Get Alembic script directory."""
        return ScriptDirectory.from_config(self._get_config())

    async def _get_current_revision_async(self) -> Optional[str]:
        """Get current database revision asynchronously."""
        engine = create_async_engine(
            self._settings.async_url,
            echo=False,
        )

        try:
            async with engine.connect() as conn:
                # Check if alembic_version table exists
                if self._settings.is_postgres:
                    check_sql = text("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables
                            WHERE table_name = 'alembic_version'
                        )
                    """)
                else:
                    check_sql = text("""
                        SELECT COUNT(*) FROM sqlite_master
                        WHERE type='table' AND name='alembic_version'
                    """)

                result = await conn.execute(check_sql)
                exists = result.scalar()

                if not exists:
                    return None

                result = await conn.execute(
                    text("SELECT version_num FROM alembic_version")
                )
                row = result.fetchone()
                return row[0] if row else None
        except Exception as e:
            logger.debug(f"Could not get current revision: {e}")
            return None
        finally:
            await engine.dispose()

    async def get_current_revision(self) -> Optional[str]:
        """Get current database revision.

        Returns:
            Current revision ID or None if no migrations applied.
        """
        return await self._get_current_revision_async()

    def get_head_revision(self) -> str:
        """Get latest available migration revision.

        Returns:
            Head revision ID.
        """
        script = self._get_script_directory()
        return script.get_current_head()

    def get_all_revisions(self) -> List[MigrationInfo]:
        """Get all available migrations.

        Returns:
            List of migration info in order (oldest first).
        """
        script = self._get_script_directory()
        head = script.get_current_head()
        revisions = []

        for rev in script.walk_revisions():
            info = MigrationInfo(
                revision=rev.revision,
                down_revision=rev.down_revision[0] if rev.down_revision else None,
                description=rev.doc or "",
                is_head=rev.revision == head,
            )
            revisions.append(info)

        return list(reversed(revisions))

    async def get_status(self) -> AlembicStatus:
        """Get current migration status.

        Returns:
            AlembicStatus with current state.
        """
        current = await self.get_current_revision()
        head = self.get_head_revision()
        script = self._get_script_directory()

        # Find pending revisions. script.walk_revisions expects (base, head).
        pending = []
        if current != head:
            try:
                if current:
                    revisions = script.walk_revisions(base=current, head=head)
                else:
                    revisions = script.walk_revisions(base="base", head=head)

                for rev in revisions:
                    if rev.revision != current:
                        pending.append(rev.revision)
            except CommandError:
                # Current revision is unknown or divergent from graph; surface as fully pending.
                for rev in script.walk_revisions(base="base", head=head):
                    pending.append(rev.revision)

        db_type = "postgresql" if self._settings.is_postgres else "sqlite"

        return AlembicStatus(
            current_revision=current,
            head_revision=head,
            pending_count=len(pending),
            pending_revisions=list(reversed(pending)),
            is_up_to_date=current == head,
            database_type=db_type,
        )

    async def has_pending_migrations(self) -> bool:
        """Check if there are pending migrations.

        Returns:
            True if migrations need to be run.
        """
        status = await self.get_status()
        return not status.is_up_to_date

    def upgrade(self, revision: str = "head") -> None:
        """Run migrations up to specified revision.

        Args:
            revision: Target revision. Default "head" for latest.
        """
        config = self._get_config()
        command.upgrade(config, revision)
        logger.info(f"Upgraded database to revision: {revision}")

    def downgrade(self, revision: str) -> None:
        """Downgrade to specified revision.

        Args:
            revision: Target revision. Use "-1" for one step back.
        """
        config = self._get_config()
        command.downgrade(config, revision)
        logger.info(f"Downgraded database to revision: {revision}")

    def create_revision(
        self,
        message: str,
        autogenerate: bool = False,
    ) -> Optional[str]:
        """Create a new migration revision.

        Args:
            message: Migration description.
            autogenerate: Auto-detect changes from models.

        Returns:
            New revision ID or None if failed.
        """
        config = self._get_config()
        try:
            script = command.revision(
                config,
                message=message,
                autogenerate=autogenerate,
            )
            revision_id = script.revision if script else None
            if revision_id:
                logger.info(f"Created new revision: {revision_id}")
            return revision_id
        except Exception as e:
            logger.error(f"Failed to create revision: {e}")
            return None

    def stamp(self, revision: str) -> None:
        """Stamp database with revision without running migrations.

        Useful for marking database as up-to-date after manual changes.

        Args:
            revision: Revision to stamp.
        """
        config = self._get_config()
        command.stamp(config, revision)
        logger.info(f"Stamped database with revision: {revision}")

    def show_history(self, verbose: bool = False) -> List[str]:
        """Get migration history.

        Args:
            verbose: Include detailed info.

        Returns:
            List of revision descriptions.
        """
        script = self._get_script_directory()
        history = []

        for rev in script.walk_revisions():
            if verbose:
                history.append(f"{rev.revision}: {rev.doc}")
            else:
                history.append(rev.revision)

        return list(reversed(history))

    async def ensure_up_to_date(self) -> bool:
        """Ensure database is up to date with migrations.

        Runs upgrade if pending migrations exist.

        Returns:
            True if migrations were run, False if already up to date.
        """
        if await self.has_pending_migrations():
            self.upgrade()
            return True
        return False

    async def get_health_info(self) -> Dict[str, Any]:
        """Get migration health information for monitoring.

        Returns:
            Dict with health info suitable for health check endpoints.
        """
        try:
            status = await self.get_status()
            return {
                "healthy": status.is_up_to_date,
                "database_type": status.database_type,
                "current_revision": status.current_revision,
                "head_revision": status.head_revision,
                "pending_migrations": status.pending_count,
                "up_to_date": status.is_up_to_date,
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
            }


class AlembicCLI:
    """Command-line interface for Alembic migrations.

    Provides CLI commands for common migration operations.
    """

    def __init__(self, manager: Optional[AlembicManager] = None):
        """Initialize CLI.

        Args:
            manager: Alembic manager. Creates default if not provided.
        """
        self.manager = manager or AlembicManager()

    def run(self, args: List[str]) -> int:
        """Run a migration command.

        Args:
            args: Command and arguments.

        Returns:
            Exit code (0 for success).
        """
        if not args:
            return self._cmd_help([])

        cmd = args[0]
        cmd_args = args[1:]

        commands = {
            "status": self._cmd_status,
            "upgrade": self._cmd_upgrade,
            "downgrade": self._cmd_downgrade,
            "revision": self._cmd_revision,
            "history": self._cmd_history,
            "current": self._cmd_current,
            "head": self._cmd_head,
            "stamp": self._cmd_stamp,
            "check": self._cmd_check,
            "help": self._cmd_help,
        }

        handler = commands.get(cmd)
        if handler:
            return handler(cmd_args)
        else:
            print(f"Unknown command: {cmd}")
            return self._cmd_help([])

    def _cmd_status(self, args: List[str]) -> int:
        """Show migration status."""
        status = asyncio.run(self.manager.get_status())

        print(f"\nAlembic Migration Status")
        print(f"{'='*40}")
        print(f"Database:         {status.database_type}")
        print(f"Current revision: {status.current_revision or '(none)'}")
        print(f"Head revision:    {status.head_revision}")
        print(f"Up to date:       {'Yes' if status.is_up_to_date else 'No'}")

        if status.pending_revisions:
            print(f"\nPending migrations ({status.pending_count}):")
            for rev in status.pending_revisions:
                print(f"  → {rev}")

        return 0

    def _cmd_upgrade(self, args: List[str]) -> int:
        """Run upgrade migration."""
        revision = args[0] if args else "head"
        try:
            self.manager.upgrade(revision)
            print(f"✓ Upgraded to: {revision}")
            return 0
        except Exception as e:
            print(f"✗ Upgrade failed: {e}")
            return 1

    def _cmd_downgrade(self, args: List[str]) -> int:
        """Run downgrade migration."""
        if not args:
            print("Error: downgrade requires a revision argument")
            print("Use '-1' for one step back or specify revision ID")
            return 1

        revision = args[0]
        try:
            self.manager.downgrade(revision)
            print(f"✓ Downgraded to: {revision}")
            return 0
        except Exception as e:
            print(f"✗ Downgrade failed: {e}")
            return 1

    def _cmd_revision(self, args: List[str]) -> int:
        """Create new migration."""
        if not args:
            print("Error: revision requires a message")
            return 1

        autogenerate = "--autogenerate" in args or "-a" in args
        # Remove flags from args
        message_parts = [a for a in args if a not in ("--autogenerate", "-a")]
        message = " ".join(message_parts)

        if not message:
            print("Error: revision requires a message")
            return 1

        try:
            rev_id = self.manager.create_revision(message, autogenerate=autogenerate)
            if rev_id:
                print(f"✓ Created revision: {rev_id}")
                return 0
            else:
                print("✗ Failed to create revision")
                return 1
        except Exception as e:
            print(f"✗ Failed: {e}")
            return 1

    def _cmd_history(self, args: List[str]) -> int:
        """Show migration history."""
        verbose = "-v" in args or "--verbose" in args
        history = self.manager.show_history(verbose=verbose)

        print("\nMigration History:")
        print("-" * 40)
        for rev in history:
            print(f"  {rev}")

        return 0

    def _cmd_current(self, args: List[str]) -> int:
        """Show current revision."""
        current = asyncio.run(self.manager.get_current_revision())
        print(f"Current revision: {current or '(none)'}")
        return 0

    def _cmd_head(self, args: List[str]) -> int:
        """Show head revision."""
        head = self.manager.get_head_revision()
        print(f"Head revision: {head}")
        return 0

    def _cmd_stamp(self, args: List[str]) -> int:
        """Stamp database with revision."""
        if not args:
            print("Error: stamp requires a revision argument")
            return 1

        revision = args[0]
        try:
            self.manager.stamp(revision)
            print(f"✓ Stamped with: {revision}")
            return 0
        except Exception as e:
            print(f"✗ Stamp failed: {e}")
            return 1

    def _cmd_check(self, args: List[str]) -> int:
        """Check if migrations are up to date (for CI/CD)."""
        status = asyncio.run(self.manager.get_status())

        if status.is_up_to_date:
            print("✓ Database is up to date")
            return 0
        else:
            print(f"✗ {status.pending_count} pending migration(s)")
            return 1

    def _cmd_help(self, args: List[str]) -> int:
        """Print help message."""
        print("""
Alembic Migration CLI for PostgreSQL

Usage: python -m database.alembic_helpers <command> [args]

Commands:
  status              Show current migration status
  upgrade [revision]  Upgrade to revision (default: head)
  downgrade <rev>     Downgrade to revision (use -1 for one back)
  revision <msg> [-a] Create new revision (-a for autogenerate)
  history [-v]        Show migration history
  current             Show current database revision
  head                Show latest available revision
  stamp <revision>    Stamp database without running migrations
  check               Check if migrations up to date (for CI/CD)
  help                Show this help message

Examples:
  python -m database.alembic_helpers status
  python -m database.alembic_helpers upgrade
  python -m database.alembic_helpers downgrade -1
  python -m database.alembic_helpers revision "Add user table" -a
  python -m database.alembic_helpers check  # Exit 1 if pending
""")
        return 0


# =============================================================================
# Convenience Functions
# =============================================================================

async def get_alembic_status() -> AlembicStatus:
    """Get current Alembic migration status.

    Returns:
        AlembicStatus with current state.
    """
    manager = AlembicManager()
    return await manager.get_status()


async def run_alembic_migrations() -> bool:
    """Run pending Alembic migrations.

    Returns:
        True if migrations were run.
    """
    manager = AlembicManager()
    return await manager.ensure_up_to_date()


async def check_migrations_on_startup() -> None:
    """Check and optionally run migrations on application startup.

    Logs warning if migrations are pending. Set AUTO_MIGRATE=true
    to enable auto-migration on startup.
    """
    manager = AlembicManager()

    try:
        status = await manager.get_status()
    except Exception as e:
        logger.warning(f"Could not check migration status: {e}")
        return

    if status.is_up_to_date:
        logger.info(
            f"Database migrations up to date "
            f"({status.database_type}, revision: {status.current_revision})"
        )
        return

    logger.warning(
        f"Database has {status.pending_count} pending migration(s). "
        f"Current: {status.current_revision}, Head: {status.head_revision}"
    )

    # Auto-migrate if enabled
    auto_migrate = os.getenv("AUTO_MIGRATE", "").lower() in ("true", "1", "yes")
    if auto_migrate:
        logger.info("AUTO_MIGRATE enabled, running migrations...")
        try:
            manager.upgrade()
            logger.info("Migrations complete")
        except Exception as e:
            logger.error(f"Auto-migration failed: {e}")
            raise
    else:
        logger.warning(
            "Set AUTO_MIGRATE=true to auto-run migrations, "
            "or run: python -m database.alembic_helpers upgrade"
        )


async def get_migration_health() -> Dict[str, Any]:
    """Get migration health for health check endpoints.

    Returns:
        Dict with migration health info.
    """
    manager = AlembicManager()
    return await manager.get_health_info()


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    cli = AlembicCLI()
    sys.exit(cli.run(sys.argv[1:]))
