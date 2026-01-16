from .taxpayer import TaxpayerInfo, FilingStatus
from .income import Income, IncomeSource, W2Info, Form1099Info
from .deductions import Deductions, ItemizedDeductions
from .credits import TaxCredits
from .tax_return import TaxReturn

__all__ = [
    'TaxpayerInfo',
    'FilingStatus',
    'Income',
    'IncomeSource',
    'W2Info',
    'Form1099Info',
    'Deductions',
    'ItemizedDeductions',
    'TaxCredits',
    'TaxReturn',
]
