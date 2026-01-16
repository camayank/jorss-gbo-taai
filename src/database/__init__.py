"""
Database Layer for US Tax Return Preparation System.

This module provides:
- SQLAlchemy ORM models with IRS-compliant structure
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
]
