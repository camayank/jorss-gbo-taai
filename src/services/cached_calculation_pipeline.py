"""Cached Calculation Pipeline - Tax calculations with Redis caching.

Wraps the CalculationPipeline with cache-aside pattern:
1. Check cache for existing result
2. If miss, execute calculation pipeline
3. Cache the result for future requests
4. Automatic invalidation on data changes

This significantly reduces computation time for repeated calculations
on the same tax return.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Dict, Optional

from config.settings import get_settings
from domain import PriorYearCarryovers
from models.tax_return import TaxReturn

from .calculation_pipeline import (
    CalculationPipeline,
    PipelineContext,
    create_pipeline,
)

logger = logging.getLogger(__name__)

# Import cache components - handle gracefully if Redis unavailable
try:
    from cache import (
        CalculationCache,
        CacheInvalidator,
        get_calculation_cache,
        DEFAULT_CALCULATION_TTL,
    )
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    CalculationCache = None
    CacheInvalidator = None
    get_calculation_cache = None
    DEFAULT_CALCULATION_TTL = 3600


class CachedCalculationPipeline:
    """Calculation pipeline with Redis caching.

    Provides cache-aside pattern for tax calculations:
    - Check cache before computing
    - Store results after computation
    - Automatic cache invalidation

    Usage:
        pipeline = CachedCalculationPipeline()

        # Execute with caching (async)
        context = await pipeline.execute(
            tax_return=tax_return,
            tax_return_data=data,
            return_id="123",
        )

        # Invalidate cache when data changes
        await pipeline.invalidate(return_id="123")

        # Warm up cache after data load
        await pipeline.warmup(return_id="123", tax_return=tr, data=data)
    """

    def __init__(
        self,
        pipeline: Optional[CalculationPipeline] = None,
        cache: Optional[CalculationCache] = None,
        ttl: int = DEFAULT_CALCULATION_TTL,
        enable_caching: Optional[bool] = None,
    ):
        """Initialize cached calculation pipeline.

        Args:
            pipeline: Underlying calculation pipeline.
            cache: Calculation cache instance.
            ttl: Cache TTL in seconds (default 1 hour).
            enable_caching: Override settings to enable/disable caching.
        """
        self._pipeline = pipeline or create_pipeline()
        self._cache = cache
        self._ttl = ttl
        self._invalidator: Optional[CacheInvalidator] = None

        # Determine if caching is enabled
        if enable_caching is not None:
            self._caching_enabled = enable_caching and CACHE_AVAILABLE
        else:
            settings = get_settings()
            self._caching_enabled = settings.enable_caching and CACHE_AVAILABLE

    async def _get_cache(self) -> Optional[CalculationCache]:
        """Get or initialize cache instance."""
        if not self._caching_enabled:
            return None

        if self._cache is None:
            try:
                self._cache = await get_calculation_cache()
            except Exception as e:
                logger.warning(f"Failed to connect to cache: {e}")
                self._caching_enabled = False
                return None

        return self._cache

    async def _get_invalidator(self) -> Optional[CacheInvalidator]:
        """Get or initialize cache invalidator."""
        if not self._caching_enabled:
            return None

        if self._invalidator is None:
            cache = await self._get_cache()
            if cache:
                self._invalidator = CacheInvalidator(cache)

        return self._invalidator

    def _breakdown_to_dict(self, context: PipelineContext) -> Optional[Dict[str, Any]]:
        """Convert calculation breakdown to cacheable dict."""
        if context.breakdown is None:
            return None

        try:
            return asdict(context.breakdown)
        except Exception as e:
            logger.warning(f"Failed to serialize breakdown: {e}")
            return None

    def _create_cache_key_context(
        self,
        tax_return_data: Dict[str, Any],
        prior_year_carryovers: Optional[PriorYearCarryovers],
    ) -> Optional[str]:
        """Create context hash for cache key versioning.

        This ensures cache is invalidated when input data changes.
        """
        cache = self._cache
        if cache is None:
            return None

        # Create context dict for hashing
        context_data = {
            "tax_year": tax_return_data.get("tax_year"),
            "filing_status": tax_return_data.get("filing_status"),
            "state": tax_return_data.get("state_of_residence"),
        }

        # Include carryover info if present
        if prior_year_carryovers:
            context_data["has_carryovers"] = True
            context_data["carryover_year"] = getattr(
                prior_year_carryovers, "tax_year", None
            )

        return cache._hash_context(context_data)

    async def execute(
        self,
        tax_return: TaxReturn,
        tax_return_data: Dict[str, Any],
        return_id: Optional[str] = None,
        session_id: Optional[str] = None,
        prior_year_carryovers: Optional[PriorYearCarryovers] = None,
        bypass_cache: bool = False,
    ) -> PipelineContext:
        """Execute calculation with caching.

        Args:
            tax_return: TaxReturn model instance.
            tax_return_data: Raw return data dictionary.
            return_id: Optional return identifier (required for caching).
            session_id: Optional session identifier.
            prior_year_carryovers: Optional carryovers from prior year.
            bypass_cache: Skip cache lookup (still stores result).

        Returns:
            PipelineContext with calculation results.
        """
        cache = await self._get_cache()

        # Try to get cached result
        if cache and return_id and not bypass_cache:
            context_hash = self._create_cache_key_context(
                tax_return_data, prior_year_carryovers
            )

            try:
                cached_breakdown = await cache.get_calculation(
                    return_id, context_hash
                )

                if cached_breakdown is not None:
                    logger.info(f"Cache HIT for return {return_id}")

                    # Reconstruct context with cached breakdown
                    from calculator.engine import CalculationBreakdown

                    context = PipelineContext(
                        tax_return=tax_return,
                        tax_return_data=tax_return_data,
                        return_id=return_id,
                        session_id=session_id,
                        prior_year_carryovers=prior_year_carryovers,
                    )

                    # Convert dict back to CalculationBreakdown
                    context.breakdown = CalculationBreakdown(**cached_breakdown)
                    context.metadata["cache_hit"] = True
                    context.metadata["from_cache"] = True

                    return context

            except Exception as e:
                logger.warning(f"Cache lookup failed for {return_id}: {e}")

        # Cache miss - execute pipeline
        logger.debug(f"Cache MISS for return {return_id or 'unknown'}")

        context = self._pipeline.execute(
            tax_return=tax_return,
            tax_return_data=tax_return_data,
            return_id=return_id,
            session_id=session_id,
            prior_year_carryovers=prior_year_carryovers,
        )

        context.metadata["cache_hit"] = False
        context.metadata["from_cache"] = False

        # Cache the result if successful
        if cache and return_id and context.breakdown is not None:
            context_hash = self._create_cache_key_context(
                tax_return_data, prior_year_carryovers
            )
            breakdown_dict = self._breakdown_to_dict(context)

            if breakdown_dict:
                try:
                    await cache.set_calculation(
                        return_id,
                        breakdown_dict,
                        context_hash=context_hash,
                        ttl=self._ttl,
                    )
                    logger.debug(f"Cached calculation for {return_id}")
                except Exception as e:
                    logger.warning(f"Failed to cache calculation: {e}")

        return context

    def execute_sync(
        self,
        tax_return: TaxReturn,
        tax_return_data: Dict[str, Any],
        return_id: Optional[str] = None,
        session_id: Optional[str] = None,
        prior_year_carryovers: Optional[PriorYearCarryovers] = None,
    ) -> PipelineContext:
        """Execute calculation without caching (sync version).

        Use this when caching is not needed or in sync contexts.

        Args:
            tax_return: TaxReturn model instance.
            tax_return_data: Raw return data dictionary.
            return_id: Optional return identifier.
            session_id: Optional session identifier.
            prior_year_carryovers: Optional carryovers from prior year.

        Returns:
            PipelineContext with calculation results.
        """
        return self._pipeline.execute(
            tax_return=tax_return,
            tax_return_data=tax_return_data,
            return_id=return_id,
            session_id=session_id,
            prior_year_carryovers=prior_year_carryovers,
        )

    async def invalidate(self, return_id: str) -> bool:
        """Invalidate cached calculation for a return.

        Call this when return data changes.

        Args:
            return_id: Tax return ID.

        Returns:
            True if cache was invalidated.
        """
        invalidator = await self._get_invalidator()
        if invalidator:
            try:
                await invalidator.on_return_updated(return_id)
                logger.info(f"Invalidated cache for return {return_id}")
                return True
            except Exception as e:
                logger.warning(f"Cache invalidation failed: {e}")
        return False

    async def invalidate_all(self) -> bool:
        """Invalidate all cached calculations.

        Call this when tax configuration changes.

        Returns:
            True if caches were invalidated.
        """
        invalidator = await self._get_invalidator()
        if invalidator:
            try:
                await invalidator.on_config_changed()
                logger.info("Invalidated all calculation caches")
                return True
            except Exception as e:
                logger.warning(f"Cache invalidation failed: {e}")
        return False

    async def warmup(
        self,
        return_id: str,
        tax_return: TaxReturn,
        tax_return_data: Dict[str, Any],
        prior_year_carryovers: Optional[PriorYearCarryovers] = None,
    ) -> bool:
        """Warm up cache by pre-computing calculation.

        Useful after loading return data to pre-populate cache.

        Args:
            return_id: Tax return ID.
            tax_return: TaxReturn model instance.
            tax_return_data: Raw return data.
            prior_year_carryovers: Optional carryovers.

        Returns:
            True if warmup succeeded.
        """
        try:
            context = await self.execute(
                tax_return=tax_return,
                tax_return_data=tax_return_data,
                return_id=return_id,
                prior_year_carryovers=prior_year_carryovers,
                bypass_cache=True,  # Force fresh calculation
            )
            return context.breakdown is not None
        except Exception as e:
            logger.warning(f"Cache warmup failed for {return_id}: {e}")
            return False

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with cache stats.
        """
        cache = await self._get_cache()
        if cache:
            return await cache.get_cache_stats()
        return {
            "enabled": False,
            "reason": "caching disabled" if not self._caching_enabled else "unavailable",
        }


# Global cached pipeline instance
_cached_pipeline: Optional[CachedCalculationPipeline] = None


async def get_cached_pipeline() -> CachedCalculationPipeline:
    """Get or create global cached calculation pipeline.

    Returns:
        Cached calculation pipeline instance.
    """
    global _cached_pipeline

    if _cached_pipeline is None:
        _cached_pipeline = CachedCalculationPipeline()

    return _cached_pipeline


def create_cached_pipeline(
    include_state: bool = True,
    include_validation: bool = True,
    ttl: int = DEFAULT_CALCULATION_TTL,
    enable_caching: Optional[bool] = None,
) -> CachedCalculationPipeline:
    """Create a cached calculation pipeline with options.

    Args:
        include_state: Include state tax calculation.
        include_validation: Include validation steps.
        ttl: Cache TTL in seconds.
        enable_caching: Override to enable/disable caching.

    Returns:
        Configured CachedCalculationPipeline.
    """
    pipeline = create_pipeline(
        include_state=include_state,
        include_validation=include_validation,
    )

    return CachedCalculationPipeline(
        pipeline=pipeline,
        ttl=ttl,
        enable_caching=enable_caching,
    )
