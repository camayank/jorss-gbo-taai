"""
FastAPI Dependency Injection for Async Services.

Provides dependency injection for:
- AsyncTaxReturnService
- AsyncCalculationPipeline
- IUnitOfWork
- Cache layer

Usage in endpoints:
    @app.post("/api/calculate")
    async def calculate(
        service: AsyncTaxReturnService = Depends(get_async_tax_return_service)
    ):
        ...
"""

from typing import AsyncGenerator
from functools import lru_cache

from fastapi import Depends

from database.unit_of_work import UnitOfWork, get_unit_of_work
from domain.repositories import IUnitOfWork
from services.async_tax_return_service import AsyncTaxReturnService
from services.async_calculation_pipeline import AsyncCalculationPipeline, create_async_pipeline
from calculator.engine import FederalTaxEngine
from calculator.state.state_tax_engine import StateTaxEngine


# Singleton engines (thread-safe, stateless)
@lru_cache(maxsize=1)
def get_federal_engine() -> FederalTaxEngine:
    """Get singleton federal tax engine."""
    return FederalTaxEngine()


@lru_cache(maxsize=1)
def get_state_engine() -> StateTaxEngine:
    """Get singleton state tax engine."""
    return StateTaxEngine()


# Unit of Work dependency
async def get_uow() -> IUnitOfWork:
    """
    Get a unit of work instance.

    Returns an uninitialized UoW - must be used with async context manager.
    """
    return await get_unit_of_work()


# Managed Unit of Work (for endpoints that need transaction scope)
async def get_managed_uow() -> AsyncGenerator[IUnitOfWork, None]:
    """
    Get a managed unit of work with automatic commit/rollback.

    Usage:
        @app.post("/api/returns")
        async def create_return(
            uow: IUnitOfWork = Depends(get_managed_uow)
        ):
            # Transaction starts automatically
            await uow.tax_returns.save(...)
            # Auto-commits on success, rolls back on exception
    """
    uow = UnitOfWork()
    async with uow:
        yield uow


# AsyncTaxReturnService dependency
async def get_async_tax_return_service(
    uow: IUnitOfWork = Depends(get_managed_uow),
    federal_engine: FederalTaxEngine = Depends(get_federal_engine),
    state_engine: StateTaxEngine = Depends(get_state_engine),
) -> AsyncTaxReturnService:
    """
    Get AsyncTaxReturnService with injected dependencies.

    The service receives a managed UoW that auto-commits/rollbacks.
    """
    return AsyncTaxReturnService(
        unit_of_work=uow,
        federal_engine=federal_engine,
        state_engine=state_engine,
    )


# Service without auto-commit (for manual transaction control)
async def get_tax_return_service_manual_commit(
    uow: IUnitOfWork = Depends(get_uow),
    federal_engine: FederalTaxEngine = Depends(get_federal_engine),
    state_engine: StateTaxEngine = Depends(get_state_engine),
) -> AsyncTaxReturnService:
    """
    Get AsyncTaxReturnService with manual transaction control.

    Use this when you need to control commit/rollback yourself.
    Must call await uow.commit() explicitly.
    """
    return AsyncTaxReturnService(
        unit_of_work=uow,
        federal_engine=federal_engine,
        state_engine=state_engine,
    )


# AsyncCalculationPipeline dependency
def get_async_pipeline(
    include_state: bool = True,
    include_validation: bool = True
) -> AsyncCalculationPipeline:
    """
    Get configured AsyncCalculationPipeline.

    Args:
        include_state: Include state tax calculation
        include_validation: Include validation steps

    Returns:
        Configured pipeline instance
    """
    return create_async_pipeline(
        include_state=include_state,
        include_validation=include_validation
    )


# Default pipeline
def get_default_pipeline() -> AsyncCalculationPipeline:
    """Get default async calculation pipeline."""
    return create_async_pipeline()


# Optional: Cache-backed service
try:
    from cache.calculation_cache import CalculationCache
    from cache.redis_client import RedisClient

    async def get_calculation_cache() -> CalculationCache:
        """Get calculation cache instance."""
        client = RedisClient()
        return CalculationCache(client)

except ImportError:
    # Cache not available
    async def get_calculation_cache():
        """Cache not available - return None."""
        return None


# Combined dependencies for common endpoint patterns
class ServiceBundle:
    """Bundle of commonly used services."""

    def __init__(
        self,
        tax_return_service: AsyncTaxReturnService,
        pipeline: AsyncCalculationPipeline,
    ):
        self.tax_return_service = tax_return_service
        self.pipeline = pipeline


async def get_service_bundle(
    service: AsyncTaxReturnService = Depends(get_async_tax_return_service),
    pipeline: AsyncCalculationPipeline = Depends(get_default_pipeline),
) -> ServiceBundle:
    """Get bundle of commonly used services."""
    return ServiceBundle(
        tax_return_service=service,
        pipeline=pipeline,
    )
