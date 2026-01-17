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
    """Get ValidationService instance."""
    from .validation_service import ValidationService
    return ValidationService()

def get_calculation_pipeline():
    """Get CalculationPipeline instance."""
    from .calculation_pipeline import CalculationPipeline
    return CalculationPipeline()

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
    "get_calculation_pipeline",
    "get_cached_calculation_pipeline",
    "create_cached_calculation_pipeline",
]
