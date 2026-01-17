"""Tests for Alembic migration helpers."""

import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

# Mock alembic before importing our modules
mock_alembic = MagicMock()
mock_alembic.command = MagicMock()
mock_alembic.config = MagicMock()
mock_alembic.config.Config = MagicMock
mock_alembic.runtime = MagicMock()
mock_alembic.runtime.migration = MagicMock()
mock_alembic.runtime.migration.MigrationContext = MagicMock
mock_alembic.script = MagicMock()
mock_alembic.script.ScriptDirectory = MagicMock

sys.modules["alembic"] = mock_alembic
sys.modules["alembic.command"] = mock_alembic.command
sys.modules["alembic.config"] = mock_alembic.config
sys.modules["alembic.runtime"] = mock_alembic.runtime
sys.modules["alembic.runtime.migration"] = mock_alembic.runtime.migration
sys.modules["alembic.script"] = mock_alembic.script

# Now import with mocked alembic
from database.alembic_helpers import (
    AlembicManager,
    AlembicStatus,
    AlembicCLI,
    MigrationInfo,
    get_alembic_status,
    run_alembic_migrations,
    check_migrations_on_startup,
    get_migration_health,
    ALEMBIC_AVAILABLE,
)

from config.database import DatabaseSettings


class TestAlembicManager:
    """Tests for AlembicManager class."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock database settings."""
        settings = DatabaseSettings(
            driver="sqlite+aiosqlite",
            sqlite_path="test_migrations.db"
        )
        return settings

    @pytest.fixture
    def manager(self, mock_settings):
        """Create manager with mock settings."""
        return AlembicManager(settings=mock_settings)

    def test_init_with_defaults(self):
        """Manager initializes with default settings."""
        with patch("database.alembic_helpers.get_database_settings") as mock_get:
            mock_get.return_value = DatabaseSettings()
            manager = AlembicManager()
            assert manager.settings is not None

    def test_init_with_custom_settings(self, mock_settings):
        """Manager accepts custom settings."""
        manager = AlembicManager(settings=mock_settings)
        assert manager.settings == mock_settings

    def test_get_head_revision(self, manager):
        """Manager returns head revision from script directory."""
        with patch.object(manager, "_get_script_directory") as mock_script:
            mock_script.return_value.get_current_head.return_value = "abc123"
            head = manager.get_head_revision()
            assert head == "abc123"

    def test_get_all_revisions(self, manager):
        """Manager returns all available revisions."""
        with patch.object(manager, "_get_script_directory") as mock_script:
            mock_rev = MagicMock()
            mock_rev.revision = "abc123"
            mock_rev.down_revision = None
            mock_rev.doc = "Initial migration"

            mock_script.return_value.walk_revisions.return_value = [mock_rev]
            mock_script.return_value.get_current_head.return_value = "abc123"

            revisions = manager.get_all_revisions()

            assert len(revisions) == 1
            assert revisions[0].revision == "abc123"
            assert revisions[0].is_head is True

    @pytest.mark.asyncio
    async def test_get_current_revision_no_table(self, manager):
        """Manager returns None when alembic_version table doesn't exist."""
        with patch("database.alembic_helpers.create_async_engine") as mock_engine:
            mock_conn = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar.return_value = False  # Table doesn't exist
            mock_conn.execute.return_value = mock_result

            mock_engine_instance = AsyncMock()
            mock_engine_instance.connect.return_value.__aenter__.return_value = mock_conn
            mock_engine_instance.dispose = AsyncMock()
            mock_engine.return_value = mock_engine_instance

            result = await manager.get_current_revision()
            assert result is None

    @pytest.mark.asyncio
    async def test_get_status(self, manager):
        """Manager returns migration status."""
        with patch.object(manager, "get_current_revision", new_callable=AsyncMock) as mock_current:
            mock_current.return_value = "abc123"

            with patch.object(manager, "get_head_revision") as mock_head:
                mock_head.return_value = "abc123"

                with patch.object(manager, "_get_script_directory") as mock_script:
                    mock_script.return_value.walk_revisions.return_value = []

                    status = await manager.get_status()

                    assert status.current_revision == "abc123"
                    assert status.head_revision == "abc123"
                    assert status.is_up_to_date is True
                    assert status.pending_count == 0

    @pytest.mark.asyncio
    async def test_get_status_with_pending(self, manager):
        """Manager detects pending migrations."""
        with patch.object(manager, "get_current_revision", new_callable=AsyncMock) as mock_current:
            mock_current.return_value = "abc123"

            with patch.object(manager, "get_head_revision") as mock_head:
                mock_head.return_value = "def456"

                with patch.object(manager, "_get_script_directory") as mock_script:
                    mock_rev = MagicMock()
                    mock_rev.revision = "def456"
                    mock_script.return_value.walk_revisions.return_value = [mock_rev]

                    status = await manager.get_status()

                    assert status.current_revision == "abc123"
                    assert status.head_revision == "def456"
                    assert status.is_up_to_date is False
                    assert status.pending_count == 1

    @pytest.mark.asyncio
    async def test_has_pending_migrations_true(self, manager):
        """Manager correctly identifies pending migrations."""
        with patch.object(manager, "get_status", new_callable=AsyncMock) as mock_status:
            mock_status.return_value = AlembicStatus(
                current_revision="abc123",
                head_revision="def456",
                pending_count=1,
                pending_revisions=["def456"],
                is_up_to_date=False,
                database_type="sqlite",
            )

            result = await manager.has_pending_migrations()
            assert result is True

    @pytest.mark.asyncio
    async def test_has_pending_migrations_false(self, manager):
        """Manager correctly identifies no pending migrations."""
        with patch.object(manager, "get_status", new_callable=AsyncMock) as mock_status:
            mock_status.return_value = AlembicStatus(
                current_revision="abc123",
                head_revision="abc123",
                pending_count=0,
                pending_revisions=[],
                is_up_to_date=True,
                database_type="sqlite",
            )

            result = await manager.has_pending_migrations()
            assert result is False

    def test_upgrade(self, manager):
        """Manager runs upgrade command."""
        with patch.object(manager, "_get_config") as mock_config:
            with patch("database.alembic_helpers.command.upgrade") as mock_upgrade:
                manager.upgrade("head")
                mock_upgrade.assert_called_once_with(mock_config.return_value, "head")

    def test_downgrade(self, manager):
        """Manager runs downgrade command."""
        with patch.object(manager, "_get_config") as mock_config:
            with patch("database.alembic_helpers.command.downgrade") as mock_downgrade:
                manager.downgrade("-1")
                mock_downgrade.assert_called_once_with(mock_config.return_value, "-1")

    def test_create_revision(self, manager):
        """Manager creates new revision."""
        with patch.object(manager, "_get_config") as mock_config:
            with patch("database.alembic_helpers.command.revision") as mock_revision:
                mock_script = MagicMock()
                mock_script.revision = "new123"
                mock_revision.return_value = mock_script

                result = manager.create_revision("Test migration")

                assert result == "new123"
                mock_revision.assert_called_once_with(
                    mock_config.return_value,
                    message="Test migration",
                    autogenerate=False,
                )

    def test_create_revision_autogenerate(self, manager):
        """Manager creates autogenerated revision."""
        with patch.object(manager, "_get_config") as mock_config:
            with patch("database.alembic_helpers.command.revision") as mock_revision:
                mock_script = MagicMock()
                mock_script.revision = "auto123"
                mock_revision.return_value = mock_script

                result = manager.create_revision("Auto migration", autogenerate=True)

                assert result == "auto123"
                mock_revision.assert_called_once_with(
                    mock_config.return_value,
                    message="Auto migration",
                    autogenerate=True,
                )

    def test_stamp(self, manager):
        """Manager stamps database."""
        with patch.object(manager, "_get_config") as mock_config:
            with patch("database.alembic_helpers.command.stamp") as mock_stamp:
                manager.stamp("abc123")
                mock_stamp.assert_called_once_with(mock_config.return_value, "abc123")

    def test_show_history(self, manager):
        """Manager returns migration history."""
        with patch.object(manager, "_get_script_directory") as mock_script:
            mock_rev1 = MagicMock()
            mock_rev1.revision = "def456"
            mock_rev1.doc = "Second"

            mock_rev2 = MagicMock()
            mock_rev2.revision = "abc123"
            mock_rev2.doc = "First"

            mock_script.return_value.walk_revisions.return_value = [mock_rev1, mock_rev2]

            history = manager.show_history()

            assert history == ["abc123", "def456"]

    def test_show_history_verbose(self, manager):
        """Manager returns verbose migration history."""
        with patch.object(manager, "_get_script_directory") as mock_script:
            mock_rev = MagicMock()
            mock_rev.revision = "abc123"
            mock_rev.doc = "Initial migration"

            mock_script.return_value.walk_revisions.return_value = [mock_rev]

            history = manager.show_history(verbose=True)

            assert history == ["abc123: Initial migration"]

    @pytest.mark.asyncio
    async def test_ensure_up_to_date_runs_upgrade(self, manager):
        """Manager runs upgrade when pending migrations exist."""
        with patch.object(manager, "has_pending_migrations", new_callable=AsyncMock) as mock_pending:
            mock_pending.return_value = True

            with patch.object(manager, "upgrade") as mock_upgrade:
                result = await manager.ensure_up_to_date()

                assert result is True
                mock_upgrade.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_up_to_date_skips_when_current(self, manager):
        """Manager skips upgrade when already current."""
        with patch.object(manager, "has_pending_migrations", new_callable=AsyncMock) as mock_pending:
            mock_pending.return_value = False

            with patch.object(manager, "upgrade") as mock_upgrade:
                result = await manager.ensure_up_to_date()

                assert result is False
                mock_upgrade.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_health_info(self, manager):
        """Manager returns health info."""
        with patch.object(manager, "get_status", new_callable=AsyncMock) as mock_status:
            mock_status.return_value = AlembicStatus(
                current_revision="abc123",
                head_revision="abc123",
                pending_count=0,
                pending_revisions=[],
                is_up_to_date=True,
                database_type="sqlite",
            )

            health = await manager.get_health_info()

            assert health["healthy"] is True
            assert health["database_type"] == "sqlite"
            assert health["current_revision"] == "abc123"
            assert health["up_to_date"] is True


class TestAlembicCLI:
    """Tests for AlembicCLI class."""

    @pytest.fixture
    def mock_manager(self):
        """Create mock manager."""
        manager = MagicMock(spec=AlembicManager)
        return manager

    @pytest.fixture
    def cli(self, mock_manager):
        """Create CLI with mock manager."""
        return AlembicCLI(manager=mock_manager)

    def test_cmd_status(self, cli, mock_manager):
        """CLI status command works."""
        mock_manager.get_status = AsyncMock(return_value=AlembicStatus(
            current_revision="abc123",
            head_revision="abc123",
            pending_count=0,
            pending_revisions=[],
            is_up_to_date=True,
            database_type="sqlite",
        ))

        result = cli.run(["status"])

        assert result == 0

    def test_cmd_upgrade(self, cli, mock_manager):
        """CLI upgrade command works."""
        result = cli.run(["upgrade"])

        assert result == 0
        mock_manager.upgrade.assert_called_once_with("head")

    def test_cmd_upgrade_specific_revision(self, cli, mock_manager):
        """CLI upgrade to specific revision works."""
        result = cli.run(["upgrade", "abc123"])

        assert result == 0
        mock_manager.upgrade.assert_called_once_with("abc123")

    def test_cmd_downgrade(self, cli, mock_manager):
        """CLI downgrade command works."""
        result = cli.run(["downgrade", "-1"])

        assert result == 0
        mock_manager.downgrade.assert_called_once_with("-1")

    def test_cmd_downgrade_requires_revision(self, cli, mock_manager):
        """CLI downgrade requires revision argument."""
        result = cli.run(["downgrade"])

        assert result == 1
        mock_manager.downgrade.assert_not_called()

    def test_cmd_revision(self, cli, mock_manager):
        """CLI revision command creates migration."""
        mock_manager.create_revision.return_value = "new123"

        result = cli.run(["revision", "Add user table"])

        assert result == 0
        mock_manager.create_revision.assert_called_once_with(
            "Add user table",
            autogenerate=False
        )

    def test_cmd_revision_autogenerate(self, cli, mock_manager):
        """CLI revision with autogenerate flag."""
        mock_manager.create_revision.return_value = "auto123"

        result = cli.run(["revision", "Auto migration", "-a"])

        assert result == 0
        mock_manager.create_revision.assert_called_once_with(
            "Auto migration",
            autogenerate=True
        )

    def test_cmd_history(self, cli, mock_manager):
        """CLI history command works."""
        mock_manager.show_history.return_value = ["abc123", "def456"]

        result = cli.run(["history"])

        assert result == 0

    def test_cmd_current(self, cli, mock_manager):
        """CLI current command works."""
        mock_manager.get_current_revision = AsyncMock(return_value="abc123")

        result = cli.run(["current"])

        assert result == 0

    def test_cmd_head(self, cli, mock_manager):
        """CLI head command works."""
        mock_manager.get_head_revision.return_value = "abc123"

        result = cli.run(["head"])

        assert result == 0

    def test_cmd_stamp(self, cli, mock_manager):
        """CLI stamp command works."""
        result = cli.run(["stamp", "abc123"])

        assert result == 0
        mock_manager.stamp.assert_called_once_with("abc123")

    def test_cmd_stamp_requires_revision(self, cli, mock_manager):
        """CLI stamp requires revision argument."""
        result = cli.run(["stamp"])

        assert result == 1
        mock_manager.stamp.assert_not_called()

    def test_cmd_check_up_to_date(self, cli, mock_manager):
        """CLI check command returns 0 when up to date."""
        mock_manager.get_status = AsyncMock(return_value=AlembicStatus(
            current_revision="abc123",
            head_revision="abc123",
            pending_count=0,
            pending_revisions=[],
            is_up_to_date=True,
            database_type="sqlite",
        ))

        result = cli.run(["check"])

        assert result == 0

    def test_cmd_check_pending(self, cli, mock_manager):
        """CLI check command returns 1 when pending migrations."""
        mock_manager.get_status = AsyncMock(return_value=AlembicStatus(
            current_revision="abc123",
            head_revision="def456",
            pending_count=1,
            pending_revisions=["def456"],
            is_up_to_date=False,
            database_type="sqlite",
        ))

        result = cli.run(["check"])

        assert result == 1

    def test_cmd_help(self, cli, mock_manager):
        """CLI help command works."""
        result = cli.run(["help"])
        assert result == 0

    def test_cmd_unknown(self, cli, mock_manager):
        """CLI prints message for unknown command and shows help."""
        result = cli.run(["unknown_command"])
        # Shows help after unknown command, which returns 0
        assert result == 0


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    @pytest.mark.asyncio
    async def test_get_alembic_status(self):
        """get_alembic_status returns status."""
        with patch("database.alembic_helpers.AlembicManager") as MockManager:
            mock_instance = MockManager.return_value
            mock_instance.get_status = AsyncMock(return_value=AlembicStatus(
                current_revision="abc123",
                head_revision="abc123",
                pending_count=0,
                pending_revisions=[],
                is_up_to_date=True,
                database_type="sqlite",
            ))

            status = await get_alembic_status()

            assert status.current_revision == "abc123"
            assert status.is_up_to_date is True

    @pytest.mark.asyncio
    async def test_run_alembic_migrations(self):
        """run_alembic_migrations runs pending migrations."""
        with patch("database.alembic_helpers.AlembicManager") as MockManager:
            mock_instance = MockManager.return_value
            mock_instance.ensure_up_to_date = AsyncMock(return_value=True)

            result = await run_alembic_migrations()

            assert result is True
            mock_instance.ensure_up_to_date.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_migrations_on_startup_up_to_date(self):
        """check_migrations_on_startup logs info when up to date."""
        with patch("database.alembic_helpers.AlembicManager") as MockManager:
            mock_instance = MockManager.return_value
            mock_instance.get_status = AsyncMock(return_value=AlembicStatus(
                current_revision="abc123",
                head_revision="abc123",
                pending_count=0,
                pending_revisions=[],
                is_up_to_date=True,
                database_type="sqlite",
            ))

            # Should not raise
            await check_migrations_on_startup()

    @pytest.mark.asyncio
    async def test_check_migrations_on_startup_pending(self):
        """check_migrations_on_startup warns when pending."""
        with patch("database.alembic_helpers.AlembicManager") as MockManager:
            mock_instance = MockManager.return_value
            mock_instance.get_status = AsyncMock(return_value=AlembicStatus(
                current_revision="abc123",
                head_revision="def456",
                pending_count=1,
                pending_revisions=["def456"],
                is_up_to_date=False,
                database_type="sqlite",
            ))

            # Should not raise, just warn
            await check_migrations_on_startup()

    @pytest.mark.asyncio
    async def test_check_migrations_on_startup_auto_migrate(self):
        """check_migrations_on_startup auto-migrates when enabled."""
        with patch("database.alembic_helpers.AlembicManager") as MockManager:
            mock_instance = MockManager.return_value
            mock_instance.get_status = AsyncMock(return_value=AlembicStatus(
                current_revision="abc123",
                head_revision="def456",
                pending_count=1,
                pending_revisions=["def456"],
                is_up_to_date=False,
                database_type="sqlite",
            ))

            with patch.dict("os.environ", {"AUTO_MIGRATE": "true"}):
                await check_migrations_on_startup()
                mock_instance.upgrade.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_migration_health(self):
        """get_migration_health returns health info."""
        with patch("database.alembic_helpers.AlembicManager") as MockManager:
            mock_instance = MockManager.return_value
            mock_instance.get_health_info = AsyncMock(return_value={
                "healthy": True,
                "database_type": "sqlite",
                "current_revision": "abc123",
                "head_revision": "abc123",
                "pending_migrations": 0,
                "up_to_date": True,
            })

            health = await get_migration_health()

            assert health["healthy"] is True
            assert health["up_to_date"] is True


class TestMigrationInfo:
    """Tests for MigrationInfo dataclass."""

    def test_create_migration_info(self):
        """MigrationInfo can be created."""
        info = MigrationInfo(
            revision="abc123",
            down_revision="xyz789",
            description="Test migration",
            is_head=True,
            is_current=True,
        )

        assert info.revision == "abc123"
        assert info.down_revision == "xyz789"
        assert info.description == "Test migration"
        assert info.is_head is True
        assert info.is_current is True

    def test_migration_info_defaults(self):
        """MigrationInfo has correct defaults."""
        info = MigrationInfo(
            revision="abc123",
            down_revision=None,
            description="Test",
        )

        assert info.is_head is False
        assert info.is_current is False


class TestAlembicStatus:
    """Tests for AlembicStatus dataclass."""

    def test_create_alembic_status(self):
        """AlembicStatus can be created."""
        status = AlembicStatus(
            current_revision="abc123",
            head_revision="def456",
            pending_count=1,
            pending_revisions=["def456"],
            is_up_to_date=False,
            database_type="postgresql",
        )

        assert status.current_revision == "abc123"
        assert status.head_revision == "def456"
        assert status.pending_count == 1
        assert status.pending_revisions == ["def456"]
        assert status.is_up_to_date is False
        assert status.database_type == "postgresql"
