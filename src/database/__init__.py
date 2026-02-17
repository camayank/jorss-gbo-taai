"""
Database Layer for US Tax Return Preparation System.

This module provides:
- SQLAlchemy ORM models with IRS-compliant structure
- Async database engine with connection pooling
- Transaction management and Unit of Work pattern
- Data validation and business rules enforcement
- ETL (Extract, Load, Transform) pipeline
- Computation worksheets per US tax formats
- Audit trail persistence
"""

from .models import (
    Base,
    TaxReturnRecord,
    TaxpayerRecord,
    IncomeRecord,
    W2Record,
    Form1099Record,
    DeductionRecord,
    CreditRecord,
    DependentRecord,
    StateReturnRecord,
    AuditLogRecord,
    ComputationWorksheet,
    FilingStatusFlag,
)

from .schema import (
    TaxReturnSchema,
    ValidationResult,
    BusinessRuleResult,
)

from .etl import (
    ETLPipeline,
    DataExtractor,
    DataTransformer,
    DataLoader,
)

from .validation import (
    StructuralValidator,
    BusinessRulesValidator,
    IRSComplianceValidator,
)

# Async database components (optional - requires config module)
try:
    from .async_engine import (
        get_async_engine,
        get_async_session,
        get_async_session_factory,
        check_database_connection,
        init_database,
        close_database,
        DatabaseHealth,
    )
except ImportError:
    # Config module not available, async engine not usable
    get_async_engine = None
    get_async_session = None
    get_async_session_factory = None
    check_database_connection = None
    init_database = None
    close_database = None
    DatabaseHealth = None

from .transaction import (
    TransactionManager,
    NestedTransaction,
    transaction,
    read_only_session,
    transactional,
    TransactionContext,
)

from .unit_of_work import (
    UnitOfWork,
    unit_of_work,
    UnitOfWorkFactory,
    get_unit_of_work,
)

from .repositories import TaxReturnRepository

__all__ = [
    # Models
    "Base",
    "TaxReturnRecord",
    "TaxpayerRecord",
    "IncomeRecord",
    "W2Record",
    "Form1099Record",
    "DeductionRecord",
    "CreditRecord",
    "DependentRecord",
    "StateReturnRecord",
    "AuditLogRecord",
    "ComputationWorksheet",
    "FilingStatusFlag",
    # Schema
    "TaxReturnSchema",
    "ValidationResult",
    "BusinessRuleResult",
    # ETL
    "ETLPipeline",
    "DataExtractor",
    "DataTransformer",
    "DataLoader",
    # Validation
    "StructuralValidator",
    "BusinessRulesValidator",
    "IRSComplianceValidator",
    # Async Engine
    "get_async_engine",
    "get_async_session",
    "get_async_session_factory",
    "check_database_connection",
    "init_database",
    "close_database",
    "DatabaseHealth",
    # Transaction Management
    "TransactionManager",
    "NestedTransaction",
    "transaction",
    "read_only_session",
    "transactional",
    "TransactionContext",
    # Unit of Work
    "UnitOfWork",
    "unit_of_work",
    "UnitOfWorkFactory",
    "get_unit_of_work",
    # Repositories
    "TaxReturnRepository",
    # Migration Helpers
    "AlembicManager",
    "AlembicStatus",
    "AlembicCLI",
    "get_alembic_status",
    "run_alembic_migrations",
    "check_migrations_on_startup",
    "get_migration_health",
    "ALEMBIC_AVAILABLE",
]


_MIGRATION_EXPORTS = {
    "AlembicManager",
    "AlembicStatus",
    "AlembicCLI",
    "get_alembic_status",
    "run_alembic_migrations",
    "check_migrations_on_startup",
    "get_migration_health",
    "ALEMBIC_AVAILABLE",
}


def __getattr__(name):
    """
    Lazily resolve migration helpers to avoid circular import side effects.

    In particular, this prevents `python -m database.alembic_helpers ...` from
    importing `database.alembic_helpers` via package init before runpy executes
    the target module, which previously produced runtime warnings.
    """
    if name in _MIGRATION_EXPORTS:
        try:
            from . import alembic_helpers as _alembic_helpers
        except ImportError as exc:
            if name == "ALEMBIC_AVAILABLE":
                return False
            raise AttributeError(
                f"module {__name__!r} has no attribute {name!r}"
            ) from exc
        return getattr(_alembic_helpers, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
