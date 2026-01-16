"""Tax validation and conditional rules module."""

from .tax_rules_engine import (
    TaxRulesEngine,
    TaxContext,
    FieldRequirement,
    FieldState,
    ValidationResult,
    ValidationSeverity,
    get_rules_engine,
)

from .dependent_validator import (
    DependentValidator,
    DependentQualificationType,
    DependentQualificationResult,
    QualificationTestResult,
    QualificationFailureReason,
    validate_all_dependents,
    get_eitc_qualifying_children,
    get_ctc_qualifying_children,
    get_other_dependents_count,
)

__all__ = [
    # Tax Rules Engine
    'TaxRulesEngine',
    'TaxContext',
    'FieldRequirement',
    'FieldState',
    'ValidationResult',
    'ValidationSeverity',
    'get_rules_engine',
    # Dependent Validator
    'DependentValidator',
    'DependentQualificationType',
    'DependentQualificationResult',
    'QualificationTestResult',
    'QualificationFailureReason',
    'validate_all_dependents',
    'get_eitc_qualifying_children',
    'get_ctc_qualifying_children',
    'get_other_dependents_count',
]
