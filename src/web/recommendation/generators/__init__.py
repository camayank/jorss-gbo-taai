"""
Recommendation Generators Package

SPEC-006: Modular recommendation generators organized by domain.

Generator modules:
- core: Credits, deductions, investment optimizers
- retirement: 401k, IRA, Roth, Medicare, Social Security
- credits: Education savings, specialized credit generators
- deductions: QBI, smart deduction detection
- investments: Opportunity detection, tax-loss harvesting
- real_estate: Home sale, 1031, installment, passive activity, rental depreciation
- lifecycle: Filing status, timing, charitable strategies
- penalties: AMT risk, estimated tax penalty
- entity: S-Corp optimization, CPA referral
- international: Foreign tax credit, FBAR, FATCA
- strategy: Withholding, tax impact, refund, planning insights
- analytics: Tax drivers, complexity router, rules-based, real-time, CPA knowledge
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
from .credits import (
    get_education_savings_recs,
)
from .deductions import (
    get_qbi_optimizer_recs,
    get_smart_deduction_detector_recs,
)
from .investments import (
    get_opportunity_detector_recs,
)
from .real_estate import (
    get_home_sale_exclusion_recs,
    get_1031_exchange_recs,
    get_installment_sale_recs,
    get_passive_activity_loss_recs,
    get_rental_depreciation_recs,
)
from .lifecycle import (
    get_filing_status_optimizer_recs,
    get_timing_strategy_recs,
    get_charitable_strategy_recs,
)
from .penalties import (
    get_amt_risk_recs,
    get_estimated_tax_penalty_recs,
)
from .entity import (
    get_entity_optimizer_recs,
    get_cpa_opportunities,
)
from .international import (
    get_foreign_tax_credit_recs,
)
from .strategy import (
    get_withholding_optimizer_recs,
    get_tax_impact_recs,
    get_refund_estimator_recs,
    get_tax_strategy_advisor_recs,
    get_planning_insights_recs,
)
from .analytics import (
    get_tax_drivers_recs,
    get_complexity_router_recs,
    get_rules_based_recs,
    get_realtime_estimator_recs,
    get_cpa_knowledge_recs,
    get_adaptive_question_recs,
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
    # Credits
    "get_education_savings_recs",
    # Deductions
    "get_qbi_optimizer_recs",
    "get_smart_deduction_detector_recs",
    # Investments
    "get_opportunity_detector_recs",
    # Real Estate
    "get_home_sale_exclusion_recs",
    "get_1031_exchange_recs",
    "get_installment_sale_recs",
    "get_passive_activity_loss_recs",
    "get_rental_depreciation_recs",
    # Lifecycle
    "get_filing_status_optimizer_recs",
    "get_timing_strategy_recs",
    "get_charitable_strategy_recs",
    # Penalties
    "get_amt_risk_recs",
    "get_estimated_tax_penalty_recs",
    # Entity
    "get_entity_optimizer_recs",
    "get_cpa_opportunities",
    # International
    "get_foreign_tax_credit_recs",
    # Strategy
    "get_withholding_optimizer_recs",
    "get_tax_impact_recs",
    "get_refund_estimator_recs",
    "get_tax_strategy_advisor_recs",
    "get_planning_insights_recs",
    # Analytics
    "get_tax_drivers_recs",
    "get_complexity_router_recs",
    "get_rules_based_recs",
    "get_realtime_estimator_recs",
    "get_cpa_knowledge_recs",
    "get_adaptive_question_recs",
]
