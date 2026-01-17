"""Tests for AsyncCalculationPipeline."""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

from services.async_calculation_pipeline import (
    AsyncCalculationPipeline,
    AsyncPipelineStep,
    AsyncValidationStep,
    AsyncPrepareStep,
    AsyncFederalCalculationStep,
    AsyncStateCalculationStep,
    AsyncOutputValidationStep,
    PipelineContext,
    create_async_pipeline,
)
from models.tax_return import TaxReturn
from calculator.engine import CalculationBreakdown


class TestPipelineContext:
    """Tests for PipelineContext dataclass."""

    def test_init_with_defaults(self):
        """Should initialize with default values."""
        mock_return = MagicMock()
        context = PipelineContext(
            tax_return=mock_return,
            tax_return_data={"tax_year": 2025}
        )

        assert context.tax_return is mock_return
        assert context.is_valid is True
        assert context.warnings == []
        assert context.errors == []
        assert context.step_timings == {}

    def test_add_warning(self):
        """Should add warning to list."""
        context = PipelineContext(
            tax_return=MagicMock(),
            tax_return_data={}
        )

        context.add_warning("Test warning")

        assert "Test warning" in context.warnings
        assert context.is_valid is True  # Warnings don't invalidate

    def test_add_error(self):
        """Should add error and mark as invalid."""
        context = PipelineContext(
            tax_return=MagicMock(),
            tax_return_data={}
        )

        context.add_error("Test error")

        assert "Test error" in context.errors
        assert context.is_valid is False

    def test_record_step_timing(self):
        """Should record step timing."""
        context = PipelineContext(
            tax_return=MagicMock(),
            tax_return_data={}
        )

        context.record_step_timing("test_step", 100)

        assert context.step_timings["test_step"] == 100


class TestAsyncValidationStep:
    """Tests for AsyncValidationStep."""

    @pytest.mark.asyncio
    async def test_validates_taxpayer_info(self):
        """Should add warnings for missing taxpayer info."""
        mock_return = MagicMock()
        mock_return.taxpayer.first_name = ""
        mock_return.taxpayer.last_name = ""
        mock_return.taxpayer.filing_status = "single"
        mock_return.income.w2_forms = []
        mock_return.income.self_employment_income = 0
        mock_return.income.qualified_dividends = 0
        mock_return.income.dividend_income = 0

        context = PipelineContext(
            tax_return=mock_return,
            tax_return_data={"tax_year": 2025}
        )

        step = AsyncValidationStep()
        result = await step.execute(context)

        assert "Taxpayer first name is missing" in result.warnings
        assert "Taxpayer last name is missing" in result.warnings

    @pytest.mark.asyncio
    async def test_validates_filing_status(self):
        """Should add error for missing filing status."""
        mock_return = MagicMock()
        mock_return.taxpayer.first_name = "John"
        mock_return.taxpayer.last_name = "Doe"
        mock_return.taxpayer.filing_status = None
        mock_return.income.w2_forms = []
        mock_return.income.self_employment_income = 0
        mock_return.income.qualified_dividends = 0
        mock_return.income.dividend_income = 0

        context = PipelineContext(
            tax_return=mock_return,
            tax_return_data={}
        )

        step = AsyncValidationStep()
        result = await step.execute(context)

        assert "Filing status is required" in result.errors
        assert result.is_valid is False

    @pytest.mark.asyncio
    async def test_validates_negative_self_employment(self):
        """Should add error for negative self-employment income."""
        mock_return = MagicMock()
        mock_return.taxpayer.first_name = "John"
        mock_return.taxpayer.last_name = "Doe"
        mock_return.taxpayer.filing_status = "single"
        mock_return.income.w2_forms = []
        mock_return.income.self_employment_income = -1000
        mock_return.income.qualified_dividends = 0
        mock_return.income.dividend_income = 0

        context = PipelineContext(
            tax_return=mock_return,
            tax_return_data={}
        )

        step = AsyncValidationStep()
        result = await step.execute(context)

        assert "Self-employment income cannot be negative" in result.errors

    @pytest.mark.asyncio
    async def test_records_timing(self):
        """Should record step timing."""
        mock_return = MagicMock()
        mock_return.taxpayer.first_name = "John"
        mock_return.taxpayer.last_name = "Doe"
        mock_return.taxpayer.filing_status = "single"
        mock_return.income.w2_forms = []
        mock_return.income.self_employment_income = 0
        mock_return.income.qualified_dividends = 0
        mock_return.income.dividend_income = 0

        context = PipelineContext(
            tax_return=mock_return,
            tax_return_data={}
        )

        step = AsyncValidationStep()
        result = await step.execute(context)

        assert "input_validation" in result.step_timings


class TestAsyncPrepareStep:
    """Tests for AsyncPrepareStep."""

    @pytest.mark.asyncio
    async def test_execute_without_carryovers(self):
        """Should execute without errors when no carryovers."""
        context = PipelineContext(
            tax_return=MagicMock(),
            tax_return_data={}
        )

        step = AsyncPrepareStep()
        result = await step.execute(context)

        assert "preparation_completed_at" in result.metadata
        assert "prepare" in result.step_timings

    @pytest.mark.asyncio
    async def test_applies_carryovers(self):
        """Should apply prior year carryovers."""
        mock_income = MagicMock()
        mock_return = MagicMock()
        mock_return.income = mock_income

        mock_carryovers = MagicMock()
        mock_carryovers.short_term_capital_loss_carryover = 1000
        mock_carryovers.long_term_capital_loss_carryover = 2000
        mock_carryovers.amt_credit_carryover = 500
        mock_carryovers.prior_year_total_tax = 10000
        mock_carryovers.prior_year_agi = 75000

        context = PipelineContext(
            tax_return=mock_return,
            tax_return_data={},
            prior_year_carryovers=mock_carryovers
        )

        step = AsyncPrepareStep()
        await step.execute(context)

        assert mock_income.short_term_loss_carryforward == 1000
        assert mock_income.long_term_loss_carryforward == 2000
        assert mock_income.prior_year_amt_credit == 500


class TestAsyncFederalCalculationStep:
    """Tests for AsyncFederalCalculationStep."""

    @pytest.mark.asyncio
    async def test_calculate_success(self):
        """Should calculate federal taxes successfully."""
        mock_engine = MagicMock()
        mock_breakdown = MagicMock(spec=CalculationBreakdown)
        mock_breakdown.total_tax = 10000
        mock_breakdown.agi = 75000
        mock_breakdown.effective_tax_rate = 0.133
        mock_engine.calculate.return_value = mock_breakdown

        context = PipelineContext(
            tax_return=MagicMock(),
            tax_return_data={}
        )

        step = AsyncFederalCalculationStep(engine=mock_engine)
        result = await step.execute(context)

        assert result.breakdown is mock_breakdown
        assert result.is_valid is True
        mock_engine.calculate.assert_called_once()

    @pytest.mark.asyncio
    async def test_calculate_handles_error(self):
        """Should handle calculation errors gracefully."""
        mock_engine = MagicMock()
        mock_engine.calculate.side_effect = Exception("Calculation failed")

        context = PipelineContext(
            tax_return=MagicMock(),
            tax_return_data={}
        )

        step = AsyncFederalCalculationStep(engine=mock_engine)
        result = await step.execute(context)

        assert result.is_valid is False
        assert any("Federal calculation failed" in e for e in result.errors)


class TestAsyncStateCalculationStep:
    """Tests for AsyncStateCalculationStep."""

    @pytest.mark.asyncio
    async def test_should_execute_checks_state(self):
        """Should only execute if state is specified."""
        step = AsyncStateCalculationStep()

        # No state specified
        context_no_state = PipelineContext(
            tax_return=MagicMock(),
            tax_return_data={},
            breakdown=MagicMock()
        )
        assert step.should_execute(context_no_state) is False

        # State specified
        context_with_state = PipelineContext(
            tax_return=MagicMock(),
            tax_return_data={"state_of_residence": "CA"},
            breakdown=MagicMock()
        )
        assert step.should_execute(context_with_state) is True

    @pytest.mark.asyncio
    async def test_should_not_execute_without_breakdown(self):
        """Should not execute if federal calculation failed."""
        step = AsyncStateCalculationStep()

        context = PipelineContext(
            tax_return=MagicMock(),
            tax_return_data={"state_of_residence": "CA"},
            breakdown=None
        )

        assert step.should_execute(context) is False

    @pytest.mark.asyncio
    async def test_calculate_state_success(self):
        """Should calculate state taxes successfully."""
        mock_engine = MagicMock()
        mock_engine.calculate.return_value = {"tax_liability": 5000}

        mock_breakdown = MagicMock()
        mock_breakdown.agi = 75000
        mock_breakdown.taxable_income = 60000
        mock_breakdown.total_tax = 10000

        context = PipelineContext(
            tax_return=MagicMock(),
            tax_return_data={"state_of_residence": "CA"},
            breakdown=mock_breakdown
        )

        step = AsyncStateCalculationStep(engine=mock_engine)
        result = await step.execute(context)

        assert result.state_result is not None
        assert result.state_result["tax_liability"] == 5000

    @pytest.mark.asyncio
    async def test_calculate_state_handles_error(self):
        """Should handle state calculation errors gracefully."""
        mock_engine = MagicMock()
        mock_engine.calculate.side_effect = Exception("State calc failed")

        context = PipelineContext(
            tax_return=MagicMock(),
            tax_return_data={"state_of_residence": "CA"},
            breakdown=MagicMock()
        )

        step = AsyncStateCalculationStep(engine=mock_engine)
        result = await step.execute(context)

        # State errors should be warnings, not errors
        assert result.is_valid is True
        assert any("State calculation failed" in w for w in result.warnings)


class TestAsyncOutputValidationStep:
    """Tests for AsyncOutputValidationStep."""

    @pytest.mark.asyncio
    async def test_should_execute_checks_breakdown(self):
        """Should only execute if breakdown exists."""
        step = AsyncOutputValidationStep()

        context_no_breakdown = PipelineContext(
            tax_return=MagicMock(),
            tax_return_data={},
            breakdown=None
        )
        assert step.should_execute(context_no_breakdown) is False

        context_with_breakdown = PipelineContext(
            tax_return=MagicMock(),
            tax_return_data={},
            breakdown=MagicMock()
        )
        assert step.should_execute(context_with_breakdown) is True

    @pytest.mark.asyncio
    async def test_validates_negative_tax(self):
        """Should warn on negative total tax."""
        mock_breakdown = MagicMock()
        mock_breakdown.total_tax = -1000
        mock_breakdown.effective_tax_rate = 0.1
        mock_breakdown.agi = 50000
        mock_breakdown.total_payments = 5000
        mock_breakdown.refund_or_owed = 6000

        context = PipelineContext(
            tax_return=MagicMock(),
            tax_return_data={},
            breakdown=mock_breakdown
        )

        step = AsyncOutputValidationStep()
        result = await step.execute(context)

        assert any("negative" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_validates_high_effective_rate(self):
        """Should warn on very high effective tax rate."""
        mock_breakdown = MagicMock()
        mock_breakdown.total_tax = 60000
        mock_breakdown.effective_tax_rate = 0.60
        mock_breakdown.agi = 100000
        mock_breakdown.total_payments = 60000
        mock_breakdown.refund_or_owed = 0

        context = PipelineContext(
            tax_return=MagicMock(),
            tax_return_data={},
            breakdown=mock_breakdown
        )

        step = AsyncOutputValidationStep()
        result = await step.execute(context)

        assert any("50%" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_validates_negative_payments(self):
        """Should error on negative payments."""
        mock_breakdown = MagicMock()
        mock_breakdown.total_tax = 10000
        mock_breakdown.effective_tax_rate = 0.1
        mock_breakdown.agi = 100000
        mock_breakdown.total_payments = -1000
        mock_breakdown.refund_or_owed = 11000

        context = PipelineContext(
            tax_return=MagicMock(),
            tax_return_data={},
            breakdown=mock_breakdown
        )

        step = AsyncOutputValidationStep()
        result = await step.execute(context)

        assert any("negative" in e.lower() for e in result.errors)


class TestAsyncCalculationPipeline:
    """Tests for AsyncCalculationPipeline."""

    @pytest.mark.asyncio
    async def test_default_pipeline_has_all_steps(self):
        """Should have all default steps."""
        pipeline = AsyncCalculationPipeline()

        step_names = [s.name for s in pipeline._steps]
        assert "input_validation" in step_names
        assert "prepare" in step_names
        assert "federal_calculation" in step_names
        assert "state_calculation" in step_names
        assert "output_validation" in step_names

    def test_add_step(self):
        """Should add step to pipeline."""
        pipeline = AsyncCalculationPipeline(steps=[])

        # Use the provided step classes instead of creating new ones
        step = AsyncValidationStep()
        pipeline.add_step(step)
        assert len(pipeline._steps) == 1
        assert pipeline._steps[0].name == "input_validation"

    def test_add_step_at_position(self):
        """Should add step at specific position."""
        pipeline = AsyncCalculationPipeline()
        original_count = len(pipeline._steps)

        class CustomStep(AsyncPipelineStep):
            @property
            def name(self):
                return "custom"

            async def execute(self, context):
                return context

        pipeline.add_step(CustomStep(), position=0)
        assert pipeline._steps[0].name == "custom"
        assert len(pipeline._steps) == original_count + 1

    def test_remove_step(self):
        """Should remove step by name."""
        pipeline = AsyncCalculationPipeline()
        original_count = len(pipeline._steps)

        removed = pipeline.remove_step("output_validation")

        assert removed is True
        assert len(pipeline._steps) == original_count - 1
        assert "output_validation" not in [s.name for s in pipeline._steps]

    def test_remove_nonexistent_step(self):
        """Should return False for nonexistent step."""
        pipeline = AsyncCalculationPipeline()

        removed = pipeline.remove_step("nonexistent")

        assert removed is False

    @pytest.mark.asyncio
    async def test_execute_full_pipeline(self):
        """Should execute all steps in order."""
        mock_return = MagicMock()
        mock_return.taxpayer.first_name = "John"
        mock_return.taxpayer.last_name = "Doe"
        mock_return.taxpayer.filing_status.value = "single"
        mock_return.income.w2_forms = []
        mock_return.income.self_employment_income = 0
        mock_return.income.qualified_dividends = 0
        mock_return.income.dividend_income = 0

        mock_engine = MagicMock()
        mock_breakdown = MagicMock()
        mock_breakdown.total_tax = 10000
        mock_breakdown.agi = 75000
        mock_breakdown.taxable_income = 60000
        mock_breakdown.effective_tax_rate = 0.133
        mock_breakdown.total_payments = 12000
        mock_breakdown.refund_or_owed = 2000
        mock_engine.calculate.return_value = mock_breakdown

        pipeline = AsyncCalculationPipeline(steps=[
            AsyncValidationStep(),
            AsyncPrepareStep(),
            AsyncFederalCalculationStep(engine=mock_engine),
            AsyncOutputValidationStep(),
        ])

        context = await pipeline.execute(
            tax_return=mock_return,
            tax_return_data={"tax_year": 2025}
        )

        assert context.breakdown is not None
        assert "total_time_ms" in context.metadata

    @pytest.mark.asyncio
    async def test_execute_stops_on_fatal_error(self):
        """Should stop on fatal validation error."""
        mock_return = MagicMock()
        mock_return.taxpayer.first_name = "John"
        mock_return.taxpayer.last_name = "Doe"
        mock_return.taxpayer.filing_status = None  # This will cause error
        mock_return.income.w2_forms = []
        mock_return.income.self_employment_income = 0
        mock_return.income.qualified_dividends = 0
        mock_return.income.dividend_income = 0

        # Create a tracking engine to verify federal step wasn't executed
        mock_engine = MagicMock()
        mock_engine.calculate.return_value = MagicMock()

        pipeline = AsyncCalculationPipeline(steps=[
            AsyncValidationStep(),
            AsyncFederalCalculationStep(engine=mock_engine),
        ])

        context = await pipeline.execute(
            tax_return=mock_return,
            tax_return_data={"tax_year": 2025}
        )

        assert context.is_valid is False
        # Federal engine should not have been called due to validation failure
        mock_engine.calculate.assert_not_called()


class TestCreateAsyncPipeline:
    """Tests for create_async_pipeline factory function."""

    def test_creates_default_pipeline(self):
        """Should create pipeline with all steps."""
        pipeline = create_async_pipeline()

        step_names = [s.name for s in pipeline._steps]
        assert len(step_names) == 5

    def test_creates_pipeline_without_state(self):
        """Should create pipeline without state step."""
        pipeline = create_async_pipeline(include_state=False)

        step_names = [s.name for s in pipeline._steps]
        assert "state_calculation" not in step_names

    def test_creates_pipeline_without_validation(self):
        """Should create pipeline without validation steps."""
        pipeline = create_async_pipeline(include_validation=False)

        step_names = [s.name for s in pipeline._steps]
        assert "input_validation" not in step_names
        assert "output_validation" not in step_names

    def test_creates_minimal_pipeline(self):
        """Should create minimal pipeline."""
        pipeline = create_async_pipeline(
            include_state=False,
            include_validation=False
        )

        step_names = [s.name for s in pipeline._steps]
        assert step_names == ["prepare", "federal_calculation"]
