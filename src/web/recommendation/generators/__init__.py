"""
Recommendation Generators Package

SPEC-006: Modular recommendation generators organized by domain.

Generator modules:
- core: Credits, deductions, investment optimizers
- retirement: 401k, IRA, Roth, Medicare, Social Security
- business: Entity, QBI, rental, passive activity
- advanced: Filing status, timing, charitable, AMT
- compliance: Penalties, withholding, tax impact
- intelligence: Detectors, CPA, strategy advisors
"""

from .core import (
    get_credit_optimizer_recs,
    get_deduction_analyzer_recs,
    get_investment_optimizer_recs,
)
from .retirement import (
    get_retirement_optimizer_recs,
    get_backdoor_roth_recs,
    get_medicare_irmaa_recs,
    get_social_security_recs,
)

__all__ = [
    # Core
    "get_credit_optimizer_recs",
    "get_deduction_analyzer_recs",
    "get_investment_optimizer_recs",
    # Retirement
    "get_retirement_optimizer_recs",
    "get_backdoor_roth_recs",
    "get_medicare_irmaa_recs",
    "get_social_security_recs",
]
