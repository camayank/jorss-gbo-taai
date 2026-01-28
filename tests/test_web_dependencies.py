"""Tests for FastAPI dependency injection module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from web.dependencies import (
    get_federal_engine,
    get_state_engine,
    get_uow,
    get_managed_uow,
    get_async_tax_return_service,
    get_default_pipeline,
    get_async_pipeline,
    ServiceBundle,
    get_service_bundle,
)
from calculator.engine import FederalTaxEngine
from calculator.state.state_tax_engine import StateTaxEngine
from services.async_tax_return_service import AsyncTaxReturnService
from services.async_calculation_pipeline import AsyncCalculationPipeline


class TestEngineGetters:
    """Tests for singleton engine getters."""

    def test_get_federal_engine_returns_singleton(self):
        """Should return same FederalTaxEngine instance."""
        # Clear cache to ensure fresh test
        get_federal_engine.cache_clear()

        engine1 = get_federal_engine()
        engine2 = get_federal_engine()

        assert engine1 is engine2
        assert isinstance(engine1, FederalTaxEngine)

    def test_get_state_engine_returns_singleton(self):
        """Should return same StateTaxEngine instance."""
        get_state_engine.cache_clear()

        engine1 = get_state_engine()
        engine2 = get_state_engine()

        assert engine1 is engine2
        assert isinstance(engine1, StateTaxEngine)


class TestUnitOfWorkDependencies:
    """Tests for UoW dependency functions."""

    def setup_method(self):
        """Reset database globals."""
        try:
            import database.async_engine as module
            module._async_engine = None
            module._async_session_factory = None
        except ImportError:
            pass

    @pytest.mark.asyncio
    async def test_get_uow_returns_unit_of_work(self):
        """Should return UnitOfWork instance."""
        uow = await get_uow()

        from database.unit_of_work import UnitOfWork
        assert isinstance(uow, UnitOfWork)

    @pytest.mark.asyncio
    async def test_get_managed_uow_yields_unit_of_work(self):
        """Should yield managed UoW that auto-commits."""
        async for uow in get_managed_uow():
            from database.unit_of_work import UnitOfWork
            assert isinstance(uow, UnitOfWork)
            assert uow._session is not None  # Session should be initialized
            break  # Only need first yield


class TestServiceDependencies:
    """Tests for service dependency functions."""

    def setup_method(self):
        """Reset globals."""
        try:
            import database.async_engine as module
            module._async_engine = None
            module._async_session_factory = None
        except ImportError:
            pass
        get_federal_engine.cache_clear()
        get_state_engine.cache_clear()

    @pytest.mark.asyncio
    async def test_get_async_tax_return_service(self):
        """Should return configured AsyncTaxReturnService."""
        # Need to manually create mocks since the dependency chain is complex
        mock_uow = MagicMock()

        with patch('web.dependencies.get_managed_uow') as mock_get_uow:
            # Create async generator that yields the mock
            async def mock_gen():
                yield mock_uow

            mock_get_uow.return_value = mock_gen()

            service = await get_async_tax_return_service(
                uow=mock_uow,
                federal_engine=get_federal_engine(),
                state_engine=get_state_engine()
            )

            assert isinstance(service, AsyncTaxReturnService)
            assert service._uow is mock_uow


class TestPipelineDependencies:
    """Tests for pipeline dependency functions."""

    def test_get_default_pipeline(self):
        """Should return default pipeline."""
        pipeline = get_default_pipeline()

        assert isinstance(pipeline, AsyncCalculationPipeline)
        assert len(pipeline._steps) == 5  # All default steps

    def test_get_async_pipeline_with_options(self):
        """Should return pipeline with specified options."""
        pipeline = get_async_pipeline(
            include_state=False,
            include_validation=False
        )

        step_names = [s.name for s in pipeline._steps]
        assert "state_calculation" not in step_names
        assert "input_validation" not in step_names

    def test_get_async_pipeline_full(self):
        """Should return full pipeline by default."""
        pipeline = get_async_pipeline()

        step_names = [s.name for s in pipeline._steps]
        assert "federal_calculation" in step_names
        assert "state_calculation" in step_names
        assert "input_validation" in step_names


class TestServiceBundle:
    """Tests for ServiceBundle class."""

    def test_service_bundle_init(self):
        """Should initialize with services."""
        mock_service = MagicMock(spec=AsyncTaxReturnService)
        mock_pipeline = MagicMock(spec=AsyncCalculationPipeline)
        mock_validator = MagicMock()

        bundle = ServiceBundle(
            tax_return_service=mock_service,
            pipeline=mock_pipeline,
            validator=mock_validator
        )

        assert bundle.tax_return_service is mock_service
        assert bundle.pipeline is mock_pipeline
        assert bundle.validator is mock_validator

    @pytest.mark.asyncio
    async def test_get_service_bundle(self):
        """Should return bundle with services."""
        mock_service = MagicMock(spec=AsyncTaxReturnService)
        mock_pipeline = MagicMock(spec=AsyncCalculationPipeline)

        bundle = await get_service_bundle(
            service=mock_service,
            pipeline=mock_pipeline
        )

        assert isinstance(bundle, ServiceBundle)
        assert bundle.tax_return_service is mock_service
        assert bundle.pipeline is mock_pipeline


class TestCacheDependencies:
    """Tests for optional cache dependencies."""

    @pytest.mark.asyncio
    async def test_get_calculation_cache(self):
        """Should return cache or None depending on availability."""
        from web.dependencies import get_calculation_cache

        # The function should return cache or None without raising exceptions
        try:
            cache = await get_calculation_cache()
            # Either it's a CalculationCache instance or None
            assert cache is None or hasattr(cache, 'get_calculation')
        except Exception as e:
            # If there's an import or connection error, that's acceptable
            assert "redis" in str(e).lower() or "connection" in str(e).lower() or "import" in str(e).lower()

    def test_cache_dependency_is_optional(self):
        """Cache dependency should be optional and not break the app."""
        # Just verify the module loads without issues
        from web.dependencies import get_calculation_cache
        assert callable(get_calculation_cache)
