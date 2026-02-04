"""
Income Models Package.

This package provides all income-related data models for the tax platform.
Currently re-exports from the legacy income_legacy.py module.

Future work: Decompose income_legacy.py into sub-modules:
- enums.py: IncomeSource, Form1099RDistributionCode, etc.
- employment.py: W2Info, Form1099Info
- passthrough.py: ScheduleK1
- retirement.py: Form1099R, FormRRB1099, ClergyHousingAllowance, MilitaryCombatPay
- investment.py: Form1099Q, StateTaxRefund, Form1099OID, Form1099PATR, Form1099LTC
- exotic.py: VirtualCurrencyTransaction, GamblingWinnings, StockCompensationEvent, etc.
- depreciation.py: MACRSPropertyClass, MACRSConvention, DepreciableAsset
- core.py: Main Income class
"""

# Explicit re-exports from the legacy module
from models.income_legacy import (  # noqa: F401
    IncomeSource,
    Form1099RDistributionCode,
    StockCompensationType,
    DebtCancellationType,
    GamblingType,
    K1SourceType,
    ScheduleK1,
    VirtualCurrencyTransactionType,
    CostBasisMethod,
    VirtualCurrencyTransaction,
    GamblingWinnings,
    Form1099R,
    StockCompensationEvent,
    Form1099C,
    AlimonyInfo,
    W2Info,
    Form1099Info,
    Form1099QAccountType,
    Form1099Q,
    StateTaxRefund,
    Form1099OID,
    Form1099PATR,
    Form1099LTC,
    FormRRB1099,
    Form4137,
    ClergyHousingAllowance,
    MilitaryCombatPay,
    MACRSPropertyClass,
    MACRSConvention,
    DepreciableAsset,
    Income,
)
