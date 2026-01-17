"""
Async Calculation Pipeline - Domain service for orchestrated tax calculations.

Async version of the calculation pipeline that supports:
- Async pipeline steps
- Integration with IUnitOfWork
- Non-blocking tax calculations
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List

from .logging_config import get_logger, CalculationLogger

# Import models and engines
from models.tax_return import TaxReturn
from calculator.engine import FederalTaxEngine, CalculationBreakdown
from calculator.state.state_tax_engine import StateTaxEngine
from domain import PriorYearCarryovers


logger = get_logger(__name__)


@dataclass
class PipelineContext:
    """
    Context passed through the calculation pipeline.

    Contains all data needed for calculation steps.
    """
    # Input
    tax_return: TaxReturn
    tax_return_data: Dict[str, Any]
    return_id: Optional[str] = None
    session_id: Optional[str] = None

    # Prior year data
    prior_year_return: Optional[TaxReturn] = None
    prior_year_carryovers: Optional[PriorYearCarryovers] = None

    # Results
    breakdown: Optional[CalculationBreakdown] = None
    state_result: Optional[Dict[str, Any]] = None

    # Status
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    is_valid: bool = True

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    step_timings: Dict[str, int] = field(default_factory=dict)

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)

    def add_error(self, message: str) -> None:
        """Add an error message and mark as invalid."""
        self.errors.append(message)
        self.is_valid = False

    def record_step_timing(self, step_name: str, duration_ms: int) -> None:
        """Record timing for a pipeline step."""
        self.step_timings[step_name] = duration_ms


class AsyncPipelineStep(ABC):
    """
    Abstract base class for async pipeline steps.

    Each step processes the context asynchronously and passes it to the next step.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Step name for logging."""
        pass

    @abstractmethod
    async def execute(self, context: PipelineContext) -> PipelineContext:
        """
        Execute this pipeline step asynchronously.

        Args:
            context: Pipeline context with current state

        Returns:
            Updated context
        """
        pass

    def should_execute(self, context: PipelineContext) -> bool:
        """
        Check if this step should execute.

        Override to add conditional execution.
        """
        return context.is_valid


class AsyncValidationStep(AsyncPipelineStep):
    """Validate inputs before calculation."""

    @property
    def name(self) -> str:
        return "input_validation"

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Validate tax return inputs."""
        tax_return = context.tax_return
        start = time.time()

        # Required taxpayer info
        if not tax_return.taxpayer.first_name:
            context.add_warning("Taxpayer first name is missing")
        if not tax_return.taxpayer.last_name:
            context.add_warning("Taxpayer last name is missing")

        # Validate filing status is set
        if not tax_return.taxpayer.filing_status:
            context.add_error("Filing status is required")

        # Validate income values
        income = tax_return.income
        if getattr(income, 'self_employment_income', 0) < 0:
            context.add_error("Self-employment income cannot be negative")

        # Validate W-2 forms
        for w2 in income.w2_forms:
            if w2.wages < 0:
                context.add_error(f"W-2 wages cannot be negative: {w2.employer_name}")
            if w2.federal_tax_withheld < 0:
                context.add_warning(f"Federal withholding should not be negative: {w2.employer_name}")

        # Cross-field validation
        if getattr(income, 'qualified_dividends', 0) > getattr(income, 'dividend_income', 0):
            context.add_warning("Qualified dividends exceed total dividends")

        context.record_step_timing(self.name, int((time.time() - start) * 1000))
        return context


class AsyncPrepareStep(AsyncPipelineStep):
    """Prepare data for calculation."""

    @property
    def name(self) -> str:
        return "prepare"

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Prepare data for calculation."""
        start = time.time()

        # Apply carryovers if available
        if context.prior_year_carryovers:
            self._apply_carryovers(context)

        # Set up metadata
        context.metadata["preparation_completed_at"] = datetime.utcnow().isoformat()

        context.record_step_timing(self.name, int((time.time() - start) * 1000))
        return context

    def _apply_carryovers(self, context: PipelineContext) -> None:
        """Apply prior year carryovers to current return."""
        carryovers = context.prior_year_carryovers
        income = context.tax_return.income

        # Capital loss carryovers
        if carryovers.short_term_capital_loss_carryover > 0:
            income.short_term_loss_carryforward = carryovers.short_term_capital_loss_carryover
        if carryovers.long_term_capital_loss_carryover > 0:
            income.long_term_loss_carryforward = carryovers.long_term_capital_loss_carryover

        # AMT credit carryover
        if carryovers.amt_credit_carryover > 0:
            income.prior_year_amt_credit = carryovers.amt_credit_carryover

        # Prior year data for safe harbor
        if carryovers.prior_year_total_tax > 0:
            income.prior_year_tax = carryovers.prior_year_total_tax
        if carryovers.prior_year_agi > 0:
            income.prior_year_agi = carryovers.prior_year_agi


class AsyncFederalCalculationStep(AsyncPipelineStep):
    """Calculate federal taxes asynchronously."""

    def __init__(self, engine: Optional[FederalTaxEngine] = None):
        """Initialize with optional engine."""
        self._engine = engine or FederalTaxEngine()

    @property
    def name(self) -> str:
        return "federal_calculation"

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Execute federal tax calculation."""
        start = time.time()

        try:
            # The actual calculation is CPU-bound but we wrap it
            # for pipeline consistency
            context.breakdown = self._engine.calculate(context.tax_return)

            logger.info(
                "Federal calculation complete",
                extra={'extra_data': {
                    'total_tax': context.breakdown.total_tax,
                    'agi': context.breakdown.agi,
                    'effective_rate': context.breakdown.effective_tax_rate,
                }}
            )

        except Exception as e:
            context.add_error(f"Federal calculation failed: {str(e)}")
            logger.exception("Federal calculation error")

        context.record_step_timing(self.name, int((time.time() - start) * 1000))
        return context


class AsyncStateCalculationStep(AsyncPipelineStep):
    """Calculate state taxes asynchronously."""

    def __init__(self, engine: Optional[StateTaxEngine] = None):
        """Initialize with optional engine."""
        self._engine = engine or StateTaxEngine()

    @property
    def name(self) -> str:
        return "state_calculation"

    def should_execute(self, context: PipelineContext) -> bool:
        """Only execute if state is specified and federal succeeded."""
        state_code = context.tax_return_data.get("state_of_residence")
        return context.is_valid and context.breakdown is not None and state_code is not None

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Execute state tax calculation."""
        start = time.time()
        state_code = context.tax_return_data.get("state_of_residence")

        if not state_code:
            return context

        try:
            context.state_result = self._engine.calculate(
                context.tax_return,
                state_code,
                federal_agi=context.breakdown.agi,
                federal_taxable_income=context.breakdown.taxable_income,
                federal_tax=context.breakdown.total_tax
            )

            logger.info(
                f"State calculation complete: {state_code}",
                extra={'extra_data': {
                    'state': state_code,
                    'state_tax': context.state_result.get('tax_liability', 0),
                }}
            )

        except Exception as e:
            context.add_warning(f"State calculation failed for {state_code}: {str(e)}")
            logger.warning(f"State calculation error for {state_code}: {e}")

        context.record_step_timing(self.name, int((time.time() - start) * 1000))
        return context


class AsyncOutputValidationStep(AsyncPipelineStep):
    """Validate calculation outputs."""

    @property
    def name(self) -> str:
        return "output_validation"

    def should_execute(self, context: PipelineContext) -> bool:
        """Only execute if calculation succeeded."""
        return context.breakdown is not None

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Validate calculation outputs."""
        start = time.time()
        breakdown = context.breakdown

        # Sanity checks
        if breakdown.total_tax < 0:
            context.add_warning("Total tax is negative (possible refundable credits)")

        if breakdown.effective_tax_rate > 0.50:
            context.add_warning("Effective tax rate exceeds 50% - verify calculations")

        if breakdown.agi < 0:
            context.add_warning("AGI is negative - verify income and adjustments")

        # Verify payments
        if breakdown.total_payments < 0:
            context.add_error("Total payments cannot be negative")

        # Check refund/owed calculation
        expected_refund = breakdown.total_payments - breakdown.total_tax
        if abs(expected_refund - breakdown.refund_or_owed) > 1:
            context.add_warning(
                f"Refund calculation mismatch: expected {expected_refund}, got {breakdown.refund_or_owed}"
            )

        context.record_step_timing(self.name, int((time.time() - start) * 1000))
        return context


class AsyncCalculationPipeline:
    """
    Orchestrates the async tax calculation pipeline.

    Executes steps in sequence, passing context through each.
    Supports customization by adding/removing steps.
    """

    def __init__(self, steps: Optional[List[AsyncPipelineStep]] = None):
        """
        Initialize the pipeline.

        Args:
            steps: Optional list of steps. Uses default if not provided.
        """
        self._steps = steps if steps is not None else self._default_steps()
        self._logger = get_logger(__name__)

    def _default_steps(self) -> List[AsyncPipelineStep]:
        """Create default pipeline steps."""
        return [
            AsyncValidationStep(),
            AsyncPrepareStep(),
            AsyncFederalCalculationStep(),
            AsyncStateCalculationStep(),
            AsyncOutputValidationStep(),
        ]

    def add_step(self, step: AsyncPipelineStep, position: Optional[int] = None) -> None:
        """
        Add a step to the pipeline.

        Args:
            step: Step to add
            position: Optional position (appends if not specified)
        """
        if position is None:
            self._steps.append(step)
        else:
            self._steps.insert(position, step)

    def remove_step(self, step_name: str) -> bool:
        """
        Remove a step by name.

        Args:
            step_name: Name of step to remove

        Returns:
            True if removed
        """
        for i, step in enumerate(self._steps):
            if step.name == step_name:
                self._steps.pop(i)
                return True
        return False

    async def execute(
        self,
        tax_return: TaxReturn,
        tax_return_data: Dict[str, Any],
        return_id: Optional[str] = None,
        session_id: Optional[str] = None,
        prior_year_carryovers: Optional[PriorYearCarryovers] = None
    ) -> PipelineContext:
        """
        Execute the calculation pipeline asynchronously.

        Args:
            tax_return: TaxReturn model instance
            tax_return_data: Raw return data dictionary
            return_id: Optional return identifier
            session_id: Optional session identifier
            prior_year_carryovers: Optional carryovers from prior year

        Returns:
            PipelineContext with results
        """
        calc_logger = CalculationLogger(return_id)
        start_time = time.time()

        # Initialize context
        context = PipelineContext(
            tax_return=tax_return,
            tax_return_data=tax_return_data,
            return_id=return_id,
            session_id=session_id,
            prior_year_carryovers=prior_year_carryovers,
        )

        filing_status = getattr(tax_return.taxpayer.filing_status, 'value', None)
        if filing_status is None:
            filing_status = str(tax_return.taxpayer.filing_status) if tax_return.taxpayer.filing_status else "unknown"
        calc_logger.start_calculation(
            tax_return_data.get("tax_year", 2025),
            filing_status
        )

        # Execute each step
        for step in self._steps:
            if not step.should_execute(context):
                self._logger.debug(f"Skipping step: {step.name}")
                continue

            self._logger.debug(f"Executing step: {step.name}")

            try:
                context = await step.execute(context)
            except Exception as e:
                context.add_error(f"Step {step.name} failed: {str(e)}")
                self._logger.exception(f"Pipeline step {step.name} failed")
                break

            # Check for fatal errors
            if not context.is_valid and step.name in ["input_validation", "federal_calculation"]:
                self._logger.warning(f"Pipeline stopped at step: {step.name}")
                break

        # Record total time
        total_time_ms = int((time.time() - start_time) * 1000)
        context.metadata["total_time_ms"] = total_time_ms

        # Log completion
        if context.breakdown:
            calc_logger.log_result(
                context.breakdown.total_tax,
                context.breakdown.total_payments,
                context.breakdown.refund_or_owed,
                context.breakdown.effective_tax_rate
            )

        # Log warnings/errors
        for warning in context.warnings:
            calc_logger.log_warning(warning)
        for error in context.errors:
            calc_logger.log_error(error)

        self._logger.info(
            "Pipeline completed",
            extra={'extra_data': {
                'return_id': return_id,
                'total_time_ms': total_time_ms,
                'step_timings': context.step_timings,
                'warning_count': len(context.warnings),
                'error_count': len(context.errors),
            }}
        )

        return context


# Pipeline builder for convenience
def create_async_pipeline(
    include_state: bool = True,
    include_validation: bool = True
) -> AsyncCalculationPipeline:
    """
    Create an async calculation pipeline with optional steps.

    Args:
        include_state: Include state tax calculation
        include_validation: Include validation steps

    Returns:
        Configured AsyncCalculationPipeline
    """
    steps = []

    if include_validation:
        steps.append(AsyncValidationStep())

    steps.append(AsyncPrepareStep())
    steps.append(AsyncFederalCalculationStep())

    if include_state:
        steps.append(AsyncStateCalculationStep())

    if include_validation:
        steps.append(AsyncOutputValidationStep())

    return AsyncCalculationPipeline(steps)
