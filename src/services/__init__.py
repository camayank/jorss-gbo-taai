"""
Services Module - Business logic services for the Tax Decision Intelligence Platform.

Application Services (orchestration):
- TaxReturnService: Tax return lifecycle management
- ScenarioService: What-if scenario operations
- AdvisoryService: Recommendation generation and management

Domain Services (business logic):
- CalculationPipeline: Orchestrates tax calculations
- ValidationService: Input/output validation

Infrastructure Services:
- OCR document processing and data extraction
- Document validation and verification
- Logging and observability
"""

from .ocr import DocumentProcessor, OCREngine, FieldExtractor

# Import new services (will be created)
# These imports are deferred to avoid circular imports
def get_tax_return_service():
    """Get TaxReturnService instance."""
    from .tax_return_service import TaxReturnService
    return TaxReturnService()

def get_scenario_service():
    """Get ScenarioService instance."""
    from .scenario_service import ScenarioService
    return ScenarioService()

def get_advisory_service():
    """Get AdvisoryService instance."""
    from .advisory_service import AdvisoryService
    return AdvisoryService()

def get_validation_service():
    """Get ValidationService instance for input/output validation.

    ValidationService provides 11 validation rules:
    - RequiredFieldRule: Ensures required fields are present
    - SSNFormatRule: Validates SSN format (XXX-XX-XXXX)
    - IncomeRangeRule: Validates income within reasonable bounds
    - DeductionLimitRule: Validates deductions don't exceed limits
    - FilingStatusRule: Validates filing status is valid
    - DependentRule: Validates dependent information
    - DateFormatRule: Validates date formats
    - StateCodeRule: Validates state codes
    - TaxYearRule: Validates tax year is supported
    - CrossFieldRule: Validates cross-field dependencies
    - BusinessExpenseRule: Validates business expense limits

    Usage:
        validator = get_validation_service()
        result = validator.validate(tax_return, raw_data)
        if not result.is_valid:
            for issue in result.issues:
                print(f"{issue.severity}: {issue.message}")
    """
    from .validation_service import ValidationService
    return ValidationService()

async def get_cached_calculation_pipeline():
    """Get CachedCalculationPipeline instance (async).

    Returns a pipeline that caches calculation results in Redis.
    """
    from .cached_calculation_pipeline import get_cached_pipeline
    return await get_cached_pipeline()

def create_cached_calculation_pipeline(**kwargs):
    """Create a new CachedCalculationPipeline with options.

    Args:
        include_state: Include state tax calculation.
        include_validation: Include validation steps.
        ttl: Cache TTL in seconds.
        enable_caching: Override to enable/disable caching.
    """
    from .cached_calculation_pipeline import create_cached_pipeline
    return create_cached_pipeline(**kwargs)

def get_tax_knowledge_base():
    """Get PerplexityTaxKnowledgeBase instance for real-time tax research."""
    from .ai_knowledge_base import get_tax_knowledge_base as _get_kb
    return _get_kb()

def get_tax_law_interpreter():
    """Get ClaudeTaxLawInterpreter instance for tax law analysis."""
    from .tax_law_interpreter import get_tax_law_interpreter as _get_interp
    return _get_interp()

def get_case_matcher():
    """Get OpenAICaseMatcher instance for finding similar cases."""
    from .case_matcher import get_case_matcher as _get_matcher
    return _get_matcher()

def get_client_communicator(firm_name: str = "Your Tax Advisory Firm"):
    """Get ClaudeClientCommunicator instance for personalized client emails."""
    from .client_communicator import get_client_communicator as _get_comm
    return _get_comm(firm_name=firm_name)

def get_multimodal_support():
    """Get GeminiMultimodalSupport instance for voice/video processing."""
    from .multimodal_support import get_multimodal_support as _get_mm
    return _get_mm()

__all__ = [
    # OCR Services
    "DocumentProcessor",
    "OCREngine",
    "FieldExtractor",
    # Service Factories
    "get_tax_return_service",
    "get_scenario_service",
    "get_advisory_service",
    "get_validation_service",
    "get_cached_calculation_pipeline",
    "create_cached_calculation_pipeline",
    # AI Tax Research Services (Phase 5)
    "get_tax_knowledge_base",
    "get_tax_law_interpreter",
    "get_case_matcher",
    # AI Client Communication Services (Phase 6)
    "get_client_communicator",
    "get_multimodal_support",
]
