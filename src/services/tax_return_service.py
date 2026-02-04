"""
Tax Return Service - Application service for tax return operations.

Provides synchronous tax return operations:
- Creating and updating tax returns
- Performing calculations (federal + state)
- Managing prior year data and carryovers
- Persisting and retrieving returns

Used by:
- ScenarioService for what-if scenario calculations

For async operations, see: async_tax_return_service.py
"""
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from dataclasses import dataclass

from .logging_config import get_logger, CalculationLogger

# Import domain models
from domain import (
    PriorYearCarryovers,
    PriorYearSummary,
    TaxReturnCreated,
    TaxReturnCalculated,
    TaxReturnUpdated,
    publish_event,
)

# Import existing models and calculator
from models.tax_return import TaxReturn
from calculator.engine import FederalTaxEngine, CalculationBreakdown
from calculator.state import StateTaxEngine
from database.persistence import (
    TaxReturnPersistence,
    get_persistence,
    save_tax_return,
    load_tax_return,
)

# Import validation service for comprehensive validation
try:
    from services.validation_service import ValidationService, ValidationSeverity
    VALIDATION_SERVICE_AVAILABLE = True
except ImportError:
    VALIDATION_SERVICE_AVAILABLE = False
    ValidationService = None


logger = get_logger(__name__)


@dataclass
class CalculationResult:
    """Result of a tax calculation."""
    success: bool
    breakdown: Optional[CalculationBreakdown] = None
    state_result: Optional[Dict[str, Any]] = None
    errors: List[str] = None
    warnings: List[str] = None
    computation_time_ms: int = 0

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


class TaxReturnService:
    """
    Application service for tax return operations.

    Orchestrates:
    - Tax return CRUD operations
    - Tax calculations (federal + state)
    - Prior year data management
    - Event publishing for audit trails
    """

    def __init__(
        self,
        persistence: Optional[TaxReturnPersistence] = None,
        federal_engine: Optional[FederalTaxEngine] = None,
        state_engine: Optional[StateTaxEngine] = None
    ):
        """
        Initialize TaxReturnService.

        Args:
            persistence: Persistence layer for tax returns
            federal_engine: Federal tax calculation engine
            state_engine: State tax calculation engine
        """
        self._persistence = persistence or get_persistence()
        self._federal_engine = federal_engine or FederalTaxEngine()
        self._state_engine = state_engine or StateTaxEngine()
        self._logger = get_logger(__name__)

    def create_return(
        self,
        session_id: str,
        tax_year: int = 2025,
        initial_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new tax return.

        Args:
            session_id: Session identifier
            tax_year: Tax year for the return
            initial_data: Optional initial data

        Returns:
            The return_id of the created return
        """
        return_id = str(uuid4())

        # Initialize with defaults if no data provided
        if initial_data is None:
            initial_data = {
                "tax_year": tax_year,
                "taxpayer": {
                    "filing_status": "single",
                    "first_name": "",
                    "last_name": "",
                },
                "income": {},
                "deductions": {},
                "credits": {},
            }
        else:
            initial_data["tax_year"] = tax_year

        # Save to persistence
        self._persistence.save_return(session_id, initial_data, return_id)

        # Publish event
        publish_event(TaxReturnCreated(
            return_id=UUID(return_id),
            tax_year=tax_year,
            filing_status=initial_data.get("taxpayer", {}).get("filing_status", "single"),
            aggregate_id=UUID(return_id),
            aggregate_type="tax_return",
        ))

        self._logger.info(
            f"Created tax return",
            extra={'extra_data': {
                'return_id': return_id,
                'tax_year': tax_year,
            }}
        )

        return return_id

    def get_return(self, return_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a tax return by ID.

        Args:
            return_id: Return identifier

        Returns:
            Tax return data or None if not found
        """
        return self._persistence.load_return(return_id)

    def get_return_by_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent return for a session.

        Args:
            session_id: Session identifier

        Returns:
            Tax return data or None if not found
        """
        return self._persistence.load_by_session(session_id)

    def update_return(
        self,
        return_id: str,
        session_id: str,
        updates: Dict[str, Any],
        recalculate: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Update a tax return.

        Args:
            return_id: Return identifier
            session_id: Session identifier
            updates: Fields to update
            recalculate: Whether to recalculate after update

        Returns:
            Updated tax return data
        """
        # Load existing return
        existing = self._persistence.load_return(return_id)
        if not existing:
            self._logger.warning(f"Return not found for update: {return_id}")
            return None

        # Track changes for event
        previous_values = {}
        changed_fields = {}

        # Apply updates
        for key, value in updates.items():
            if key in existing:
                previous_values[key] = existing[key]
                changed_fields[key] = value
            existing[key] = value

        # Invalidate calculation cache when data changes
        if changed_fields:
            try:
                from web.calculation_helper import invalidate_cache
                import asyncio
                # Run async invalidation
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(invalidate_cache(return_id))
                    self._logger.info(f"Invalidated cache for return {return_id}")
                finally:
                    loop.close()
            except Exception as e:
                self._logger.debug(f"Cache invalidation skipped: {e}")

        # Recalculate if requested
        if recalculate:
            calc_result = self.calculate(return_id, session_id, existing)
            if calc_result.success and calc_result.breakdown:
                # Update with calculation results
                existing["adjusted_gross_income"] = calc_result.breakdown.agi
                existing["taxable_income"] = calc_result.breakdown.taxable_income
                existing["tax_liability"] = calc_result.breakdown.total_tax
                existing["refund_or_owed"] = calc_result.breakdown.refund_or_owed

        # Save updates
        self._persistence.save_return(session_id, existing, return_id)

        # Publish event
        if changed_fields:
            publish_event(TaxReturnUpdated(
                return_id=UUID(return_id),
                changed_fields=changed_fields,
                previous_values=previous_values,
                aggregate_id=UUID(return_id),
                aggregate_type="tax_return",
            ))

        return existing

    def delete_return(self, return_id: str) -> bool:
        """
        Delete a tax return.

        Args:
            return_id: Return identifier

        Returns:
            True if deleted, False if not found
        """
        return self._persistence.delete_return(return_id)

    def calculate(
        self,
        return_id: str,
        session_id: str,
        tax_return_data: Optional[Dict[str, Any]] = None
    ) -> CalculationResult:
        """
        Perform full tax calculation (federal + state).

        Args:
            return_id: Return identifier
            session_id: Session identifier
            tax_return_data: Optional pre-loaded return data

        Returns:
            CalculationResult with breakdown and any errors/warnings
        """
        calc_logger = CalculationLogger(UUID(return_id) if return_id else None)
        start_time = time.time()
        errors = []
        warnings = []

        # Load return if not provided
        if tax_return_data is None:
            tax_return_data = self._persistence.load_return(return_id)
            if not tax_return_data:
                return CalculationResult(
                    success=False,
                    errors=["Tax return not found"]
                )

        try:
            # Convert to TaxReturn model
            tax_return = self._dict_to_tax_return(tax_return_data)
            filing_status = tax_return.taxpayer.filing_status.value
            tax_year = tax_return_data.get("tax_year", 2025)

            calc_logger.start_calculation(tax_year, filing_status)

            # Comprehensive validation using ValidationService
            if VALIDATION_SERVICE_AVAILABLE:
                validator = ValidationService()
                validation_result = validator.validate(tax_return, tax_return_data)

                # Process validation issues
                for issue in validation_result.issues:
                    calc_logger.log_validation_error(issue.field_path, issue.message)
                    if issue.severity == ValidationSeverity.ERROR:
                        errors.append(f"{issue.field_path}: {issue.message}")
                    else:
                        warnings.append(f"{issue.field_path}: {issue.message}")

                # Log validation summary
                logger.info(
                    f"Validation: {validation_result.error_count} errors, "
                    f"{validation_result.warning_count} warnings"
                )

                # Stop on errors for formal returns (not advisor estimates)
                if not validation_result.is_valid and tax_return_data.get("strict_validation", False):
                    return CalculationResult(
                        success=False,
                        errors=errors,
                        warnings=warnings
                    )
            else:
                # Fallback to basic validation
                validation_errors = self._validate_inputs(tax_return)
                if validation_errors:
                    for error in validation_errors:
                        calc_logger.log_validation_error(error["field"], error["message"])
                    warnings.extend([f"{e['field']}: {e['message']}" for e in validation_errors])

            # Calculate federal taxes
            step_start = calc_logger.log_step("federal_calculation")
            breakdown = self._federal_engine.calculate(tax_return)
            calc_logger.complete_step(
                "federal_calculation",
                step_start,
                total_tax=breakdown.total_tax
            )

            # Log calculation details
            calc_logger.log_income(
                breakdown.gross_income,
                breakdown.adjustments_to_income,
                breakdown.agi
            )
            calc_logger.log_deductions(
                breakdown.deduction_type,
                breakdown.deduction_amount,
                breakdown.taxable_income
            )
            calc_logger.log_tax(
                breakdown.ordinary_income_tax,
                breakdown.preferential_income_tax,
                breakdown.self_employment_tax,
                breakdown.total_tax_before_credits
            )
            calc_logger.log_credits(
                breakdown.nonrefundable_credits,
                breakdown.refundable_credits,
                breakdown.total_credits
            )

            # Calculate state taxes if applicable
            state_result = None
            state_code = tax_return_data.get("state_of_residence")
            if state_code:
                step_start = calc_logger.log_step("state_calculation", state=state_code)
                state_result = self._calculate_state_tax(tax_return, state_code, breakdown)
                calc_logger.complete_step(
                    "state_calculation",
                    step_start,
                    state_tax=state_result.get("tax_liability", 0) if state_result else 0
                )

            # Update tax return data with results
            tax_return_data["adjusted_gross_income"] = breakdown.agi
            tax_return_data["taxable_income"] = breakdown.taxable_income
            tax_return_data["tax_liability"] = breakdown.total_tax
            tax_return_data["total_credits"] = breakdown.total_credits
            tax_return_data["total_payments"] = breakdown.total_payments
            tax_return_data["refund_or_owed"] = breakdown.refund_or_owed

            if state_result:
                tax_return_data["state_tax_result"] = state_result
                tax_return_data["state_tax_liability"] = state_result.get("tax_liability", 0)
                tax_return_data["state_refund_or_owed"] = state_result.get("refund_or_owed", 0)
                tax_return_data["combined_tax_liability"] = (
                    breakdown.total_tax + state_result.get("tax_liability", 0)
                )
                tax_return_data["combined_refund_or_owed"] = (
                    breakdown.refund_or_owed + state_result.get("refund_or_owed", 0)
                )

            # Save updated return
            self._persistence.save_return(session_id, tax_return_data, return_id)

            # Calculate computation time
            computation_time_ms = int((time.time() - start_time) * 1000)

            # Log final result
            calc_logger.log_result(
                breakdown.total_tax,
                breakdown.total_payments,
                breakdown.refund_or_owed,
                breakdown.effective_tax_rate
            )

            # Publish calculation event
            publish_event(TaxReturnCalculated(
                return_id=UUID(return_id),
                tax_year=tax_year,
                gross_income=breakdown.gross_income,
                adjusted_gross_income=breakdown.agi,
                taxable_income=breakdown.taxable_income,
                total_tax=breakdown.total_tax,
                effective_rate=breakdown.effective_tax_rate,
                refund_or_owed=breakdown.refund_or_owed,
                computation_time_ms=computation_time_ms,
                forms_calculated=self._get_calculated_forms(breakdown),
                warnings=warnings,
                aggregate_id=UUID(return_id),
                aggregate_type="tax_return",
            ))

            return CalculationResult(
                success=True,
                breakdown=breakdown,
                state_result=state_result,
                errors=errors,
                warnings=warnings,
                computation_time_ms=computation_time_ms
            )

        except Exception as e:
            calc_logger.log_error(f"Calculation failed: {str(e)}")
            self._logger.exception(f"Calculation error for return {return_id}")
            return CalculationResult(
                success=False,
                errors=[str(e)],
                warnings=warnings,
                computation_time_ms=int((time.time() - start_time) * 1000)
            )

    def _calculate_state_tax(
        self,
        tax_return: TaxReturn,
        state_code: str,
        federal_breakdown: CalculationBreakdown
    ) -> Optional[Dict[str, Any]]:
        """Calculate state taxes."""
        try:
            return self._state_engine.calculate(
                tax_return,
                state_code,
                federal_agi=federal_breakdown.agi,
                federal_taxable_income=federal_breakdown.taxable_income,
                federal_tax=federal_breakdown.total_tax
            )
        except Exception as e:
            self._logger.warning(f"State tax calculation failed for {state_code}: {e}")
            return None

    def _dict_to_tax_return(self, data: Dict[str, Any]) -> TaxReturn:
        """Convert dictionary to TaxReturn model."""
        return TaxReturn(**data)

    def _validate_inputs(self, tax_return: TaxReturn) -> List[Dict[str, str]]:
        """
        Validate tax return inputs.

        Returns list of validation errors.
        """
        errors = []

        # Check required taxpayer info
        if not tax_return.taxpayer.first_name:
            errors.append({"field": "taxpayer.first_name", "message": "First name is required"})
        if not tax_return.taxpayer.last_name:
            errors.append({"field": "taxpayer.last_name", "message": "Last name is required"})

        # Validate income values are non-negative
        income = tax_return.income
        if income.self_employment_income < 0:
            errors.append({
                "field": "income.self_employment_income",
                "message": "Self-employment income cannot be negative"
            })

        return errors

    def _get_calculated_forms(self, breakdown: CalculationBreakdown) -> List[str]:
        """Get list of forms that were calculated."""
        forms = ["Form 1040"]

        # Check for various form indicators
        if breakdown.self_employment_tax > 0:
            forms.append("Schedule SE")
        if breakdown.schedule_a_total_deductions > 0:
            forms.append("Schedule A")
        if breakdown.schedule_d_net_gain_loss != 0:
            forms.append("Schedule D")
        if breakdown.qbi_deduction > 0:
            forms.append("Form 8995")
        if breakdown.alternative_minimum_tax > 0:
            forms.append("Form 6251")
        if breakdown.form_1116_ftc_allowed > 0:
            forms.append("Form 1116")

        return forms

    def get_prior_year_data(
        self,
        return_id: str,
        prior_return_id: Optional[str] = None
    ) -> Optional[PriorYearSummary]:
        """
        Get prior year data for a return.

        Args:
            return_id: Current return identifier
            prior_return_id: Optional prior year return ID

        Returns:
            PriorYearSummary if available
        """
        # Load prior year return if we have an ID
        if prior_return_id:
            prior_data = self._persistence.load_return(prior_return_id)
            if prior_data:
                return PriorYearSummary(
                    tax_year=prior_data.get("tax_year", 2024),
                    total_income=prior_data.get("adjusted_gross_income", 0),
                    adjusted_gross_income=prior_data.get("adjusted_gross_income", 0),
                    taxable_income=prior_data.get("taxable_income", 0),
                    total_tax=prior_data.get("tax_liability", 0),
                    effective_rate=self._calculate_effective_rate(
                        prior_data.get("tax_liability", 0),
                        prior_data.get("adjusted_gross_income", 0)
                    ),
                    filing_status=prior_data.get("taxpayer", {}).get("filing_status", "single"),
                    total_withholding=prior_data.get("total_payments", 0),
                    refund_or_owed=prior_data.get("refund_or_owed", 0),
                )

        return None

    def _calculate_effective_rate(self, tax: float, income: float) -> float:
        """Calculate effective tax rate."""
        if income > 0:
            return tax / income
        return 0.0

    def calculate_carryovers(
        self,
        return_id: str,
        breakdown: CalculationBreakdown
    ) -> PriorYearCarryovers:
        """
        Calculate carryovers from a completed return.

        Args:
            return_id: Return identifier
            breakdown: Calculation breakdown

        Returns:
            PriorYearCarryovers for next year
        """
        return PriorYearCarryovers(
            short_term_capital_loss_carryover=breakdown.new_st_loss_carryforward,
            long_term_capital_loss_carryover=breakdown.new_lt_loss_carryforward,
            amt_credit_carryover=getattr(breakdown, 'new_amt_credit_carryforward', 0.0),
            prior_year_total_tax=breakdown.total_tax,
            prior_year_agi=breakdown.agi,
        )

    def get_prior_year_carryovers(
        self,
        prior_return_id: str
    ) -> Optional[PriorYearCarryovers]:
        """
        Get capital loss and other carryovers from a prior year return.

        Per IRC Section 1212, capital losses that exceed the $3,000 annual
        deduction limit carry forward indefinitely to future years.

        Args:
            prior_return_id: The return ID of the prior year return

        Returns:
            PriorYearCarryovers with carryforward amounts, or None if not found
        """
        prior_data = self._persistence.load_return(prior_return_id)
        if not prior_data:
            self._logger.warning(f"Prior year return not found: {prior_return_id}")
            return None

        # Extract carryforward values from prior year calculation results
        # These are stored in the return data after calculation
        income_data = prior_data.get("income", {})

        # Get the NEW carryforward amounts calculated from the prior year return
        # These represent losses that couldn't be used in that year
        st_loss_carryforward = prior_data.get(
            "new_st_loss_carryforward",
            income_data.get("new_st_loss_carryforward", 0.0)
        )
        lt_loss_carryforward = prior_data.get(
            "new_lt_loss_carryforward",
            income_data.get("new_lt_loss_carryforward", 0.0)
        )

        # If no explicit carryforward stored, check if there's a calculation breakdown
        if st_loss_carryforward == 0 and lt_loss_carryforward == 0:
            calc_breakdown = prior_data.get("calculation_breakdown", {})
            st_loss_carryforward = calc_breakdown.get("new_st_loss_carryforward", 0.0)
            lt_loss_carryforward = calc_breakdown.get("new_lt_loss_carryforward", 0.0)

        # Get other carryover amounts
        amt_credit_carryover = prior_data.get(
            "amt_credit_carryforward",
            prior_data.get("calculation_breakdown", {}).get("new_amt_credit_carryforward", 0.0)
        )

        carryovers = PriorYearCarryovers(
            short_term_capital_loss_carryover=st_loss_carryforward,
            long_term_capital_loss_carryover=lt_loss_carryforward,
            amt_credit_carryover=amt_credit_carryover,
            prior_year_total_tax=prior_data.get("tax_liability", 0.0),
            prior_year_agi=prior_data.get("adjusted_gross_income", 0.0),
        )

        self._logger.info(
            f"Loaded prior year carryovers",
            extra={'extra_data': {
                'prior_return_id': prior_return_id,
                'st_loss_carryforward': st_loss_carryforward,
                'lt_loss_carryforward': lt_loss_carryforward,
            }}
        )

        return carryovers

    def apply_carryovers_to_return(
        self,
        return_id: str,
        session_id: str,
        carryovers: PriorYearCarryovers
    ) -> bool:
        """
        Apply prior year carryovers to a tax return.

        Updates the income section of the return with carryforward amounts
        so they are included in the next calculation.

        Args:
            return_id: Current year return ID
            session_id: Session identifier
            carryovers: Prior year carryover amounts

        Returns:
            True if successfully applied, False otherwise
        """
        # Load the current return
        return_data = self._persistence.load_return(return_id)
        if not return_data:
            self._logger.warning(f"Return not found for carryover application: {return_id}")
            return False

        # Get or create income section
        income_data = return_data.get("income", {})

        # Apply capital loss carryforwards to income
        # These fields are used by the calculator in net_capital_gain_loss calculation
        income_data["short_term_loss_carryforward"] = carryovers.short_term_capital_loss_carryover
        income_data["long_term_loss_carryforward"] = carryovers.long_term_capital_loss_carryover

        # Store the applied carryovers for audit trail
        return_data["income"] = income_data
        return_data["applied_carryovers"] = {
            "short_term_capital_loss": carryovers.short_term_capital_loss_carryover,
            "long_term_capital_loss": carryovers.long_term_capital_loss_carryover,
            "amt_credit": carryovers.amt_credit_carryover,
            "prior_year_agi": carryovers.prior_year_agi,
            "prior_year_tax": carryovers.prior_year_total_tax,
            "applied_at": datetime.now().isoformat(),
        }

        # Save updated return
        self._persistence.save_return(session_id, return_data, return_id)

        self._logger.info(
            f"Applied carryovers to return",
            extra={'extra_data': {
                'return_id': return_id,
                'st_loss_carryforward': carryovers.short_term_capital_loss_carryover,
                'lt_loss_carryforward': carryovers.long_term_capital_loss_carryover,
            }}
        )

        return True

    def initialize_return_with_prior_year(
        self,
        session_id: str,
        tax_year: int,
        prior_return_id: str,
        initial_data: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Create a new tax return and automatically apply carryovers from prior year.

        This is the recommended way to create a return when a prior year return exists,
        as it ensures capital loss carryforwards (IRC Section 1212) and other
        carryover amounts are properly initialized.

        Args:
            session_id: Session identifier
            tax_year: Tax year for the new return
            prior_return_id: Return ID of the prior year return
            initial_data: Optional additional initial data

        Returns:
            The return_id of the created return, or None if prior year not found
        """
        # Get carryovers from prior year
        carryovers = self.get_prior_year_carryovers(prior_return_id)
        if not carryovers:
            self._logger.warning(
                f"Could not load prior year carryovers from {prior_return_id}"
            )
            # Still create the return, just without carryovers
            return self.create_return(session_id, tax_year, initial_data)

        # Initialize income data with carryovers
        if initial_data is None:
            initial_data = {}

        income_data = initial_data.get("income", {})
        income_data["short_term_loss_carryforward"] = carryovers.short_term_capital_loss_carryover
        income_data["long_term_loss_carryforward"] = carryovers.long_term_capital_loss_carryover
        initial_data["income"] = income_data

        # Store reference to prior year for audit trail
        initial_data["prior_year_return_id"] = prior_return_id
        initial_data["carryovers_applied"] = True

        # Create the return with carryovers pre-populated
        return_id = self.create_return(session_id, tax_year, initial_data)

        self._logger.info(
            f"Created return with prior year carryovers",
            extra={'extra_data': {
                'return_id': return_id,
                'prior_return_id': prior_return_id,
                'st_loss_carryforward': carryovers.short_term_capital_loss_carryover,
                'lt_loss_carryforward': carryovers.long_term_capital_loss_carryover,
            }}
        )

        return return_id

    def list_returns(
        self,
        tax_year: Optional[int] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List tax returns.

        Args:
            tax_year: Optional filter by year
            limit: Maximum returns to list

        Returns:
            List of return summaries
        """
        returns = self._persistence.list_returns(tax_year, limit)
        return [
            {
                "return_id": r.return_id,
                "taxpayer_name": r.taxpayer_name,
                "tax_year": r.tax_year,
                "filing_status": r.filing_status,
                "gross_income": r.gross_income,
                "tax_liability": r.tax_liability,
                "refund_or_owed": r.refund_or_owed,
                "status": r.status,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
            for r in returns
        ]

    def get_summary(self, return_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a summary of a tax return.

        Args:
            return_id: Return identifier

        Returns:
            Summary dictionary
        """
        data = self.get_return(return_id)
        if not data:
            return None

        return {
            "return_id": return_id,
            "tax_year": data.get("tax_year"),
            "filing_status": data.get("taxpayer", {}).get("filing_status"),
            "taxpayer_name": f"{data.get('taxpayer', {}).get('first_name', '')} {data.get('taxpayer', {}).get('last_name', '')}".strip(),
            "gross_income": data.get("adjusted_gross_income", 0),
            "taxable_income": data.get("taxable_income", 0),
            "federal_tax": data.get("tax_liability", 0),
            "state_tax": data.get("state_tax_liability", 0),
            "total_tax": data.get("combined_tax_liability", data.get("tax_liability", 0)),
            "total_payments": data.get("total_payments", 0),
            "refund_or_owed": data.get("combined_refund_or_owed", data.get("refund_or_owed", 0)),
            "state": data.get("state_of_residence"),
        }
