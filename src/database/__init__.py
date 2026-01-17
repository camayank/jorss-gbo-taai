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

# Async database components
from .async_engine import (
    get_async_engine,
    get_async_session,
    get_async_session_factory,
    check_database_connection,
    init_database,
    close_database,
    DatabaseHealth,
)

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

# Migration helpers (optional - requires alembic)
try:
    from .alembic_helpers import (
        AlembicManager,
        AlembicStatus,
        AlembicCLI,
        get_alembic_status,
        run_alembic_migrations,
        check_migrations_on_startup,
        get_migration_health,
        ALEMBIC_AVAILABLE,
    )
except ImportError:
    # Alembic not installed - provide stubs
    AlembicManager = None
    AlembicStatus = None
    AlembicCLI = None
    get_alembic_status = None
    run_alembic_migrations = None
    check_migrations_on_startup = None
    get_migration_health = None
    ALEMBIC_AVAILABLE = False

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
