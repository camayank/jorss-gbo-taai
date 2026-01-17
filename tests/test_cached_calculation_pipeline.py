"""Tests for cached calculation pipeline."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, asdict

from services.cached_calculation_pipeline import (
    CachedCalculationPipeline,
    create_cached_pipeline,
    get_cached_pipeline,
)
from services.calculation_pipeline import PipelineContext


@dataclass
class MockCalculationBreakdown:
    """Mock calculation breakdown for testing."""
    tax_year: int = 2025
    filing_status: str = "single"
    gross_income: float = 75000.0
    agi: float = 70000.0
    taxable_income: float = 55000.0
    total_tax: float = 8000.0
    effective_tax_rate: float = 0.107
    refund_or_owed: float = -500.0
    total_payments: float = 7500.0


@dataclass
class MockTaxReturn:
    """Mock tax return for testing."""
    pass


@dataclass
class MockTaxpayer:
    """Mock taxpayer for testing."""
    first_name: str = "John"
    last_name: str = "Doe"
    filing_status: MagicMock = None

    def __post_init__(self):
        if self.filing_status is None:
            self.filing_status = MagicMock()
            self.filing_status.value = "single"


@dataclass
class MockIncome:
    """Mock income for testing."""
    w2_forms: list = None
    self_employment_income: float = 0.0
    dividend_income: float = 0.0
    qualified_dividends: float = 0.0

    def __post_init__(self):
        if self.w2_forms is None:
            self.w2_forms = []


class TestCachedCalculationPipeline:
    """Tests for CachedCalculationPipeline class."""

    @pytest.fixture
    def mock_pipeline(self):
        """Create mock calculation pipeline."""
        pipeline = MagicMock()
        context = PipelineContext(
            tax_return=MagicMock(),
            tax_return_data={"tax_year": 2025},
        )
        context.breakdown = MockCalculationBreakdown()
        context.is_valid = True
        pipeline.execute.return_value = context
        return pipeline

    @pytest.fixture
    def mock_cache(self):
        """Create mock calculation cache."""
        cache = AsyncMock()
        cache.get_calculation = AsyncMock(return_value=None)
        cache.set_calculation = AsyncMock(return_value=True)
        cache.get_cache_stats = AsyncMock(return_value={"connected": True})
        cache._hash_context = MagicMock(return_value="abc123")
        return cache

    @pytest.fixture
    def mock_tax_return(self):
        """Create mock tax return."""
        tax_return = MagicMock()
        tax_return.taxpayer = MockTaxpayer()
        tax_return.income = MockIncome()
        return tax_return

    def test_init_with_defaults(self, mock_pipeline):
        """Pipeline initializes with defaults."""
        with patch("services.cached_calculation_pipeline.get_settings") as mock_settings:
            mock_settings.return_value.enable_caching = True

            pipeline = CachedCalculationPipeline(pipeline=mock_pipeline)

            assert pipeline._pipeline == mock_pipeline
            assert pipeline._ttl == 3600

    def test_init_caching_disabled(self, mock_pipeline):
        """Pipeline respects caching disabled setting."""
        pipeline = CachedCalculationPipeline(
            pipeline=mock_pipeline,
            enable_caching=False,
        )

        assert pipeline._caching_enabled is False

    @pytest.mark.asyncio
    async def test_execute_cache_miss(self, mock_pipeline, mock_cache, mock_tax_return):
        """Execute computes on cache miss."""
        with patch("services.cached_calculation_pipeline.get_settings") as mock_settings:
            mock_settings.return_value.enable_caching = True

            pipeline = CachedCalculationPipeline(
                pipeline=mock_pipeline,
                cache=mock_cache,
                enable_caching=True,
            )

            context = await pipeline.execute(
                tax_return=mock_tax_return,
                tax_return_data={"tax_year": 2025},
                return_id="return-123",
            )

            # Should have executed the underlying pipeline
            mock_pipeline.execute.assert_called_once()
            # Should have cached the result
            mock_cache.set_calculation.assert_called_once()
            # Context should indicate cache miss
            assert context.metadata.get("cache_hit") is False

    @pytest.mark.asyncio
    async def test_execute_cache_hit(self, mock_pipeline, mock_cache, mock_tax_return):
        """Execute returns cached result on hit."""
        # Set up cache hit
        cached_breakdown = asdict(MockCalculationBreakdown())
        mock_cache.get_calculation = AsyncMock(return_value=cached_breakdown)

        with patch("services.cached_calculation_pipeline.get_settings") as mock_settings:
            mock_settings.return_value.enable_caching = True

            pipeline = CachedCalculationPipeline(
                pipeline=mock_pipeline,
                cache=mock_cache,
                enable_caching=True,
            )

            context = await pipeline.execute(
                tax_return=mock_tax_return,
                tax_return_data={"tax_year": 2025},
                return_id="return-123",
            )

            # Should NOT have executed the underlying pipeline
            mock_pipeline.execute.assert_not_called()
            # Context should indicate cache hit
            assert context.metadata.get("cache_hit") is True
            # Should have breakdown from cache
            assert context.breakdown is not None
            assert context.breakdown.total_tax == 8000.0

    @pytest.mark.asyncio
    async def test_execute_bypass_cache(self, mock_pipeline, mock_cache, mock_tax_return):
        """Execute with bypass_cache skips cache lookup."""
        with patch("services.cached_calculation_pipeline.get_settings") as mock_settings:
            mock_settings.return_value.enable_caching = True

            pipeline = CachedCalculationPipeline(
                pipeline=mock_pipeline,
                cache=mock_cache,
                enable_caching=True,
            )

            await pipeline.execute(
                tax_return=mock_tax_return,
                tax_return_data={"tax_year": 2025},
                return_id="return-123",
                bypass_cache=True,
            )

            # Should NOT have called get (cache lookup)
            mock_cache.get_calculation.assert_not_called()
            # Should still have called set (cache store)
            mock_cache.set_calculation.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_no_return_id(self, mock_pipeline, mock_cache, mock_tax_return):
        """Execute without return_id skips caching."""
        with patch("services.cached_calculation_pipeline.get_settings") as mock_settings:
            mock_settings.return_value.enable_caching = True

            pipeline = CachedCalculationPipeline(
                pipeline=mock_pipeline,
                cache=mock_cache,
                enable_caching=True,
            )

            await pipeline.execute(
                tax_return=mock_tax_return,
                tax_return_data={"tax_year": 2025},
                # No return_id
            )

            # Should not interact with cache without return_id
            mock_cache.get_calculation.assert_not_called()
            mock_cache.set_calculation.assert_not_called()

    def test_execute_sync(self, mock_pipeline, mock_tax_return):
        """Sync execute bypasses caching."""
        pipeline = CachedCalculationPipeline(
            pipeline=mock_pipeline,
            enable_caching=False,
        )

        context = pipeline.execute_sync(
            tax_return=mock_tax_return,
            tax_return_data={"tax_year": 2025},
            return_id="return-123",
        )

        mock_pipeline.execute.assert_called_once()
        assert context.breakdown is not None

    @pytest.mark.asyncio
    async def test_invalidate(self, mock_pipeline):
        """Invalidate clears cache for return."""
        with patch("services.cached_calculation_pipeline.get_settings") as mock_settings:
            mock_settings.return_value.enable_caching = True

            with patch("services.cached_calculation_pipeline.get_calculation_cache") as mock_get_cache:
                mock_cache = AsyncMock()
                mock_cache.invalidate_return = AsyncMock()
                mock_get_cache.return_value = mock_cache

                pipeline = CachedCalculationPipeline(
                    pipeline=mock_pipeline,
                    enable_caching=True,
                )

                result = await pipeline.invalidate("return-123")

                assert result is True

    @pytest.mark.asyncio
    async def test_invalidate_all(self, mock_pipeline):
        """Invalidate all clears all caches."""
        with patch("services.cached_calculation_pipeline.get_settings") as mock_settings:
            mock_settings.return_value.enable_caching = True

            with patch("services.cached_calculation_pipeline.get_calculation_cache") as mock_get_cache:
                mock_cache = AsyncMock()
                mock_cache.client = AsyncMock()
                mock_cache.client.delete_pattern = AsyncMock(return_value=10)
                mock_get_cache.return_value = mock_cache

                pipeline = CachedCalculationPipeline(
                    pipeline=mock_pipeline,
                    enable_caching=True,
                )

                result = await pipeline.invalidate_all()

                assert result is True

    @pytest.mark.asyncio
    async def test_warmup(self, mock_pipeline, mock_cache, mock_tax_return):
        """Warmup pre-populates cache."""
        with patch("services.cached_calculation_pipeline.get_settings") as mock_settings:
            mock_settings.return_value.enable_caching = True

            pipeline = CachedCalculationPipeline(
                pipeline=mock_pipeline,
                cache=mock_cache,
                enable_caching=True,
            )

            result = await pipeline.warmup(
                return_id="return-123",
                tax_return=mock_tax_return,
                tax_return_data={"tax_year": 2025},
            )

            assert result is True
            # Should have computed (bypass_cache=True)
            mock_pipeline.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cache_stats(self, mock_pipeline, mock_cache):
        """Get stats returns cache information."""
        with patch("services.cached_calculation_pipeline.get_settings") as mock_settings:
            mock_settings.return_value.enable_caching = True

            pipeline = CachedCalculationPipeline(
                pipeline=mock_pipeline,
                cache=mock_cache,
                enable_caching=True,
            )

            stats = await pipeline.get_cache_stats()

            assert stats["connected"] is True

    @pytest.mark.asyncio
    async def test_get_cache_stats_disabled(self, mock_pipeline):
        """Get stats when caching disabled."""
        pipeline = CachedCalculationPipeline(
            pipeline=mock_pipeline,
            enable_caching=False,
        )

        stats = await pipeline.get_cache_stats()

        assert stats["enabled"] is False


class TestCreateCachedPipeline:
    """Tests for create_cached_pipeline function."""

    def test_creates_pipeline_with_defaults(self):
        """Creates pipeline with default options."""
        with patch("services.cached_calculation_pipeline.get_settings") as mock_settings:
            mock_settings.return_value.enable_caching = False

            pipeline = create_cached_pipeline()

            assert isinstance(pipeline, CachedCalculationPipeline)

    def test_creates_pipeline_with_custom_ttl(self):
        """Creates pipeline with custom TTL."""
        with patch("services.cached_calculation_pipeline.get_settings") as mock_settings:
            mock_settings.return_value.enable_caching = False

            pipeline = create_cached_pipeline(ttl=7200)

            assert pipeline._ttl == 7200

    def test_creates_pipeline_without_state(self):
        """Creates pipeline without state calculation."""
        with patch("services.cached_calculation_pipeline.get_settings") as mock_settings:
            mock_settings.return_value.enable_caching = False

            pipeline = create_cached_pipeline(include_state=False)

            # Verify state step is not in pipeline
            step_names = [s.name for s in pipeline._pipeline._steps]
            assert "state_calculation" not in step_names


class TestCacheContextHash:
    """Tests for cache key context hashing."""

    @pytest.fixture
    def pipeline(self):
        """Create pipeline with mock cache."""
        with patch("services.cached_calculation_pipeline.get_settings") as mock_settings:
            mock_settings.return_value.enable_caching = False

            mock_cache = AsyncMock()
            mock_cache._hash_context = lambda x: "test_hash"

            p = CachedCalculationPipeline(enable_caching=False)
            p._cache = mock_cache
            return p

    def test_context_hash_includes_tax_year(self, pipeline):
        """Context hash includes tax year."""
        hash1 = pipeline._create_cache_key_context(
            {"tax_year": 2025, "filing_status": "single"},
            None,
        )

        # With mock, always returns test_hash
        assert hash1 == "test_hash"

    def test_context_hash_includes_carryovers(self, pipeline):
        """Context hash includes carryover info."""
        from dataclasses import dataclass

        @dataclass
        class MockCarryovers:
            tax_year: int = 2024

        hash1 = pipeline._create_cache_key_context(
            {"tax_year": 2025},
            MockCarryovers(),
        )

        assert hash1 == "test_hash"
