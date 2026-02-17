"""
Scenario Service - Application service for what-if scenario operations.

This service provides tax scenario analysis capabilities:
- Creating and calculating what-if scenarios
- Comparing multiple scenarios
- Filing status optimization
- Applying recommended scenarios to returns

This is an APPLICATION SERVICE - it orchestrates domain operations
but contains no business logic itself.
"""

import copy
import time
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID, uuid4

from .logging_config import get_logger
from .tax_return_service import TaxReturnService

# Import domain models
from domain import (
    Scenario,
    ScenarioType,
    ScenarioStatus,
    ScenarioModification,
    ScenarioResult,
    ScenarioCreated,
    ScenarioCalculated,
    ScenarioCompared,
    publish_event,
)

# Import existing models and calculator
from models.tax_return import TaxReturn
from models.taxpayer import FilingStatus
from calculator.engine import FederalTaxEngine, CalculationBreakdown
from database.persistence import get_persistence
from database.scenario_persistence import get_scenario_persistence
from database.snapshot_persistence import get_snapshot_persistence, compute_input_hash


logger = get_logger(__name__)


class ScenarioService:
    """
    Application service for tax scenario operations.

    Provides what-if analysis capabilities:
    - Filing status comparison
    - Retirement contribution scenarios
    - Deduction bunching
    - Entity structure analysis
    - Multi-scenario comparison
    """

    def __init__(
        self,
        tax_return_service: Optional[TaxReturnService] = None,
        federal_engine: Optional[FederalTaxEngine] = None
    ):
        """
        Initialize ScenarioService.

        Args:
            tax_return_service: Service for tax return operations
            federal_engine: Federal tax calculation engine
        """
        self._tax_return_service = tax_return_service or TaxReturnService()
        self._federal_engine = federal_engine or FederalTaxEngine()
        self._persistence = get_persistence()
        self._scenario_persistence = get_scenario_persistence()
        self._snapshot_persistence = get_snapshot_persistence()
        self._logger = get_logger(__name__)

    def create_scenario(
        self,
        return_id: str,
        name: str,
        scenario_type: ScenarioType,
        modifications: List[Dict[str, Any]],
        description: Optional[str] = None
    ) -> Scenario:
        """
        Create a new scenario.

        Args:
            return_id: Base return identifier
            name: Scenario name
            scenario_type: Type of scenario
            modifications: List of modifications to apply
            description: Optional description

        Returns:
            Created Scenario
        """
        # Load base return
        base_return = self._persistence.load_return(return_id)
        if not base_return:
            raise ValueError(f"Return not found: {return_id}")

        # Remove identity fields that are irrelevant for tax math and can break
        # scenario recalculation due to masking/validation mismatches.
        base_snapshot = self._strip_identity_fields(base_return)

        # Create scenario
        scenario = Scenario(
            return_id=UUID(return_id),
            name=name,
            scenario_type=scenario_type,
            description=description,
            base_snapshot=base_snapshot,
            modifications=[
                ScenarioModification(
                    field_path=m["field_path"],
                    original_value=(
                        m["original_value"]
                        if "original_value" in m
                        else self._get_nested_value(base_snapshot, m["field_path"])
                    ),
                    new_value=m["new_value"],
                    description=m.get("description")
                )
                for m in modifications
            ]
        )

        # Store scenario in database
        self._save_scenario_to_db(scenario)

        # Publish event
        publish_event(ScenarioCreated(
            scenario_id=scenario.scenario_id,
            return_id=UUID(return_id),
            name=name,
            scenario_type=scenario_type.value,
            modifications=[m.to_dict() for m in scenario.modifications],
            aggregate_id=scenario.scenario_id,
            aggregate_type="scenario",
        ))

        self._logger.info(
            f"Created scenario: {name}",
            extra={'extra_data': {
                'scenario_id': str(scenario.scenario_id),
                'return_id': return_id,
                'type': scenario_type.value,
            }}
        )

        return scenario

    def calculate_scenario(self, scenario_id: str) -> Scenario:
        """
        Calculate tax results for a scenario using snapshot-based model.

        Snapshots are reused when inputs haven't changed:
        1. Apply modifications to get modified input data
        2. Compute input hash to detect changes
        3. Check if snapshot with same hash exists - reuse if so
        4. Otherwise calculate and create new snapshot
        5. Link scenario to the snapshot

        Args:
            scenario_id: Scenario identifier

        Returns:
            Updated Scenario with results
        """
        scenario = self._load_scenario_from_db(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario not found: {scenario_id}")

        start_time = time.time()

        # Apply modifications to base snapshot used for tax calculations.
        base_snapshot = self._strip_identity_fields(scenario.base_snapshot)
        scenario.base_snapshot = base_snapshot
        modified_data = self._apply_modifications(
            base_snapshot,
            scenario.modifications
        )

        # Compute input hash to detect if recalculation is needed
        input_hash = compute_input_hash(modified_data)

        # Check if we already have a snapshot for this input
        existing_snapshot = self._snapshot_persistence.get_snapshot_by_hash(input_hash)

        try:
            if existing_snapshot:
                # Reuse existing snapshot - no recalculation needed
                snapshot = existing_snapshot
                self._logger.info(
                    f"Reusing existing snapshot for scenario: {scenario.name}",
                    extra={'extra_data': {
                        'scenario_id': scenario_id,
                        'snapshot_id': snapshot['snapshot_id'],
                        'input_hash': input_hash,
                    }}
                )
            else:
                # Calculate new result
                tax_return = TaxReturn(**modified_data)
                breakdown = self._federal_engine.calculate(tax_return)

                # Create snapshot with calculation result
                result_data = {
                    "total_tax": breakdown.total_tax,
                    "effective_rate": breakdown.effective_tax_rate,
                    "marginal_rate": breakdown.marginal_tax_rate,
                    "taxable_income": breakdown.taxable_income,
                    "total_deductions": breakdown.deduction_amount,
                    "total_credits": breakdown.total_credits,
                    "agi": breakdown.agi,
                    "ordinary_tax": breakdown.ordinary_income_tax,
                    "preferential_tax": breakdown.preferential_income_tax,
                    "se_tax": breakdown.self_employment_tax,
                    "amt": breakdown.alternative_minimum_tax,
                }

                snapshot = self._snapshot_persistence.save_snapshot(
                    return_id=str(scenario.return_id),
                    input_data=modified_data,
                    result_data=result_data,
                    tax_year=breakdown.tax_year,
                    filing_status=breakdown.filing_status,
                    total_tax=breakdown.total_tax,
                    effective_rate=breakdown.effective_tax_rate,
                    taxable_income=breakdown.taxable_income,
                    total_credits=breakdown.total_credits,
                )

                self._logger.info(
                    f"Created new snapshot for scenario: {scenario.name}",
                    extra={'extra_data': {
                        'scenario_id': scenario_id,
                        'snapshot_id': snapshot['snapshot_id'],
                        'input_hash': input_hash,
                    }}
                )

            # Get base snapshot for comparison (also use snapshot model)
            base_hash = compute_input_hash(base_snapshot)
            base_snapshot = self._snapshot_persistence.get_snapshot_by_hash(base_hash)

            if not base_snapshot:
                # Calculate base snapshot if not exists
                base_return = TaxReturn(**scenario.base_snapshot)
                base_breakdown = self._federal_engine.calculate(base_return)

                base_result_data = {
                    "total_tax": base_breakdown.total_tax,
                    "effective_rate": base_breakdown.effective_tax_rate,
                    "marginal_rate": base_breakdown.marginal_tax_rate,
                    "taxable_income": base_breakdown.taxable_income,
                    "total_deductions": base_breakdown.deduction_amount,
                    "total_credits": base_breakdown.total_credits,
                }

                base_snapshot = self._snapshot_persistence.save_snapshot(
                    return_id=str(scenario.return_id),
                    input_data=scenario.base_snapshot,
                    result_data=base_result_data,
                    tax_year=base_breakdown.tax_year,
                    filing_status=base_breakdown.filing_status,
                    total_tax=base_breakdown.total_tax,
                    effective_rate=base_breakdown.effective_tax_rate,
                    taxable_income=base_breakdown.taxable_income,
                    total_credits=base_breakdown.total_credits,
                )

            # Calculate savings from snapshots
            base_tax = base_snapshot['total_tax']
            modified_tax = snapshot['total_tax']
            savings = base_tax - modified_tax
            savings_percent = (savings / base_tax * 100) if base_tax > 0 else 0

            # Create result from snapshot data
            result_data = snapshot['result_data']
            result = ScenarioResult(
                total_tax=snapshot['total_tax'],
                federal_tax=snapshot['total_tax'],
                effective_rate=snapshot['effective_rate'],
                marginal_rate=result_data.get('marginal_rate', 0),
                base_tax=base_tax,
                savings=savings,
                savings_percent=savings_percent,
                taxable_income=snapshot['taxable_income'],
                total_deductions=result_data.get('total_deductions', 0),
                total_credits=snapshot['total_credits'],
                breakdown={
                    "agi": result_data.get('agi', 0),
                    "ordinary_tax": result_data.get('ordinary_tax', 0),
                    "preferential_tax": result_data.get('preferential_tax', 0),
                    "se_tax": result_data.get('se_tax', 0),
                    "amt": result_data.get('amt', 0),
                }
            )

            scenario.set_result(result)

            # Save updated scenario with snapshot references
            self._save_scenario_to_db(
                scenario,
                snapshot_id=snapshot['snapshot_id'],
                base_snapshot_id=base_snapshot['snapshot_id'],
                input_hash=input_hash
            )

            computation_time_ms = int((time.time() - start_time) * 1000)

            # Publish event
            publish_event(ScenarioCalculated(
                scenario_id=scenario.scenario_id,
                return_id=scenario.return_id,
                total_tax=snapshot['total_tax'],
                effective_rate=snapshot['effective_rate'],
                savings_vs_base=savings,
                computation_time_ms=computation_time_ms,
                aggregate_id=scenario.scenario_id,
                aggregate_type="scenario",
            ))

            self._logger.info(
                f"Calculated scenario: {scenario.name}",
                extra={'extra_data': {
                    'scenario_id': scenario_id,
                    'total_tax': snapshot['total_tax'],
                    'savings': savings,
                    'reused_snapshot': existing_snapshot is not None,
                }}
            )

            return scenario

        except Exception as e:
            self._logger.error(f"Scenario calculation failed: {e}")
            raise

    def get_scenario(self, scenario_id: str) -> Optional[Scenario]:
        """Get a scenario by ID."""
        return self._load_scenario_from_db(scenario_id)

    def get_scenarios_for_return(self, return_id: str) -> List[Scenario]:
        """Get all scenarios for a return."""
        scenario_dicts = self._scenario_persistence.load_scenarios_for_return(return_id)
        return [self._dict_to_scenario(d) for d in scenario_dicts]

    def delete_scenario(self, scenario_id: str) -> bool:
        """Delete a scenario."""
        return self._scenario_persistence.delete_scenario(scenario_id)

    def compare_scenarios(
        self,
        scenario_ids: List[str],
        return_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compare multiple scenarios.

        Args:
            scenario_ids: List of scenario IDs to compare
            return_id: Optional return ID for context

        Returns:
            Comparison results
        """
        unique_ids = list(dict.fromkeys(scenario_ids))
        if len(unique_ids) < 2:
            raise ValueError("At least 2 distinct scenario IDs are required")

        expected_return_id = str(return_id) if return_id else None
        invalid_ids: List[str] = []
        scenarios: List[Scenario] = []

        # Validate all scenario IDs before comparison work.
        for sid in unique_ids:
            scenario = self._load_scenario_from_db(sid)
            if not scenario:
                invalid_ids.append(sid)
                continue

            scenario_return_id = str(scenario.return_id)
            if expected_return_id and scenario_return_id != expected_return_id:
                if return_id:
                    invalid_ids.append(sid)
                    continue
                raise ValueError("All scenarios must belong to the same return")

            if not expected_return_id:
                expected_return_id = scenario_return_id

            scenarios.append(scenario)

        if invalid_ids:
            raise ValueError(f"Invalid or out-of-scope scenario IDs: {', '.join(invalid_ids)}")

        if len(scenarios) < 2:
            raise ValueError("At least 2 valid scenarios are required")

        # Calculate scenarios that don't have results yet.
        for idx, scenario in enumerate(scenarios):
            if scenario.result is None:
                self.calculate_scenario(str(scenario.scenario_id))
                reloaded = self._load_scenario_from_db(str(scenario.scenario_id))
                if not reloaded or reloaded.result is None:
                    raise RuntimeError(f"Failed to calculate scenario: {scenario.scenario_id}")
                scenarios[idx] = reloaded

        # Find the winner (lowest tax)
        winner = min(scenarios, key=lambda s: s.result.total_tax if s.result else float('inf'))
        max_savings = max(s.result.savings if s.result else 0 for s in scenarios)

        # Mark winner as recommended and save
        winner.mark_as_recommended(f"Lowest tax liability: ${winner.result.total_tax:,.2f}")
        self._save_scenario_to_db(winner)

        comparison_id = uuid4()

        # Build comparison data
        comparison = {
            "comparison_id": str(comparison_id),
            "return_id": expected_return_id,
            "scenarios": [s.to_comparison_dict() for s in scenarios],
            "winner": {
                "scenario_id": str(winner.scenario_id),
                "name": winner.name,
                "total_tax": winner.result.total_tax if winner.result else 0,
                "savings": winner.result.savings if winner.result else 0,
            },
            "max_savings": max_savings,
            "compared_at": datetime.utcnow().isoformat(),
        }

        # Publish event
        publish_event(ScenarioCompared(
            comparison_id=comparison_id,
            return_id=UUID(expected_return_id) if expected_return_id else winner.return_id,
            scenario_ids=[s.scenario_id for s in scenarios],
            winner_scenario_id=winner.scenario_id,
            max_savings=max_savings,
            comparison_summary=f"Best option: {winner.name} saves ${max_savings:,.2f}",
            aggregate_id=comparison_id,
            aggregate_type="scenario",
        ))

        self._logger.info(
            f"Compared {len(scenarios)} scenarios",
            extra={'extra_data': {
                'comparison_id': str(comparison_id),
                'winner': winner.name,
                'max_savings': max_savings,
            }}
        )

        return comparison

    def get_filing_status_scenarios(
        self,
        return_id: str,
        eligible_statuses: Optional[List[str]] = None
    ) -> List[Scenario]:
        """
        Generate filing status comparison scenarios.

        Args:
            return_id: Base return identifier
            eligible_statuses: Optional list of statuses to compare

        Returns:
            List of filing status scenarios
        """
        base_return = self._persistence.load_return(return_id)
        if not base_return:
            raise ValueError(f"Return not found: {return_id}")

        current_status = base_return.get("taxpayer", {}).get("filing_status", "single")

        # Determine eligible statuses
        if eligible_statuses is None:
            eligible_statuses = self._get_eligible_filing_statuses(base_return)

        scenarios = []
        for status in eligible_statuses:
            # Create scenario for each status
            scenario = self.create_scenario(
                return_id=return_id,
                name=f"Filing Status: {self._format_status_name(status)}",
                scenario_type=ScenarioType.FILING_STATUS,
                modifications=[{
                    "field_path": "taxpayer.filing_status",
                    "original_value": current_status,
                    "new_value": status,
                    "description": f"Change filing status to {status}"
                }],
                description=f"Calculate taxes using {self._format_status_name(status)} filing status"
            )

            # Calculate immediately
            self.calculate_scenario(str(scenario.scenario_id))
            scenarios.append(scenario)

        self._logger.info(
            f"Generated {len(scenarios)} filing status scenarios",
            extra={'extra_data': {'return_id': return_id}}
        )

        return scenarios

    def get_retirement_scenarios(
        self,
        return_id: str,
        contribution_amounts: Optional[List[float]] = None
    ) -> List[Scenario]:
        """
        Generate retirement contribution scenarios.

        Args:
            return_id: Base return identifier
            contribution_amounts: Optional list of amounts to test

        Returns:
            List of retirement scenarios
        """
        base_return = self._persistence.load_return(return_id)
        if not base_return:
            raise ValueError(f"Return not found: {return_id}")

        current_401k = base_return.get("deductions", {}).get("retirement_contributions", 0)

        # Default contribution levels to test
        if contribution_amounts is None:
            age_50_plus = base_return.get("taxpayer", {}).get("is_age_50_plus", False)
            max_contrib = 23500 + (7500 if age_50_plus else 0)  # 2025 limits
            contribution_amounts = [
                current_401k,
                min(current_401k + 5000, max_contrib),
                min(current_401k + 10000, max_contrib),
                max_contrib,  # Max out
            ]
            contribution_amounts = sorted(set(contribution_amounts))

        scenarios = []
        for amount in contribution_amounts:
            if amount == current_401k:
                name = f"Current 401k: ${amount:,.0f}"
            elif amount >= 23500:
                name = f"Max 401k: ${amount:,.0f}"
            else:
                name = f"401k: ${amount:,.0f}"

            scenario = self.create_scenario(
                return_id=return_id,
                name=name,
                scenario_type=ScenarioType.RETIREMENT,
                modifications=[{
                    "field_path": "deductions.retirement_contributions",
                    "original_value": current_401k,
                    "new_value": amount,
                    "description": f"401k contribution of ${amount:,.0f}"
                }],
                description=f"Calculate taxes with ${amount:,.0f} in 401k contributions"
            )

            self.calculate_scenario(str(scenario.scenario_id))
            scenarios.append(scenario)

        return scenarios

    def apply_scenario(
        self,
        scenario_id: str,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Apply a scenario's modifications to the base return.

        Args:
            scenario_id: Scenario to apply
            session_id: Session identifier

        Returns:
            Updated return data
        """
        scenario = self._load_scenario_from_db(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario not found: {scenario_id}")

        return_id = str(scenario.return_id)

        # Apply modifications
        base_snapshot = self._strip_identity_fields(scenario.base_snapshot)
        scenario.base_snapshot = base_snapshot
        modified_data = self._apply_modifications(
            base_snapshot,
            scenario.modifications
        )

        # Update the return
        result = self._tax_return_service.update_return(
            return_id=return_id,
            session_id=session_id,
            updates=modified_data,
            recalculate=True,
            fail_on_recalc_error=True,
        )

        # Mark scenario as applied and save
        scenario.status = ScenarioStatus.APPLIED
        self._save_scenario_to_db(scenario)

        self._logger.info(
            f"Applied scenario to return",
            extra={'extra_data': {
                'scenario_id': scenario_id,
                'return_id': return_id,
            }}
        )

        return result

    def _apply_modifications(
        self,
        base_data: Dict[str, Any],
        modifications: List[ScenarioModification]
    ) -> Dict[str, Any]:
        """Apply modifications to base data."""
        data = copy.deepcopy(base_data)

        for mod in modifications:
            self._set_nested_value(data, mod.field_path, mod.new_value)

        return data

    def _strip_identity_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove identity fields that are not needed for tax math.

        Scenario calculations should be stable regardless of whether SSNs are
        masked in persistence.
        """
        sanitized = copy.deepcopy(data)
        taxpayer = sanitized.get("taxpayer")
        if isinstance(taxpayer, dict):
            taxpayer.pop("ssn", None)
            taxpayer.pop("spouse_ssn", None)
        return sanitized

    def _set_nested_value(
        self,
        data: Dict[str, Any],
        path: str,
        value: Any
    ) -> None:
        """Set a value in nested dictionary using dot notation."""
        keys = path.split(".")
        current = data

        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value

    def _get_nested_value(
        self,
        data: Dict[str, Any],
        path: str,
        default: Any = None
    ) -> Any:
        """Get a value from nested dictionary using dot notation."""
        keys = path.split(".")
        current = data

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default

        return current

    def _get_eligible_filing_statuses(self, return_data: Dict[str, Any]) -> List[str]:
        """Determine eligible filing statuses based on return data."""
        taxpayer = return_data.get("taxpayer", {})
        is_married = taxpayer.get("is_married", False)
        has_dependents = len(taxpayer.get("dependents", [])) > 0
        spouse_died_this_year = taxpayer.get("spouse_died_this_year", False)
        spouse_died_last_year = taxpayer.get("spouse_died_last_year", False)

        statuses = []

        if is_married and not spouse_died_this_year:
            statuses.append("married_joint")
            statuses.append("married_separate")
        else:
            statuses.append("single")

        # Head of household requires unmarried + qualifying person
        if not is_married and has_dependents:
            statuses.append("head_of_household")

        # Qualifying widow(er) - spouse died in prior 2 years + dependent child
        if (spouse_died_this_year or spouse_died_last_year) and has_dependents:
            statuses.append("qualifying_widow")

        return statuses

    def _format_status_name(self, status: str) -> str:
        """Format filing status for display."""
        names = {
            "single": "Single",
            "married_joint": "Married Filing Jointly",
            "married_separate": "Married Filing Separately",
            "head_of_household": "Head of Household",
            "qualifying_widow": "Qualifying Surviving Spouse",
        }
        return names.get(status, status.replace("_", " ").title())

    def create_what_if_scenario(
        self,
        return_id: str,
        name: str,
        modifications: Dict[str, Any]
    ) -> Scenario:
        """
        Create a generic what-if scenario.

        Args:
            return_id: Base return identifier
            name: Scenario name
            modifications: Dict of field_path -> new_value

        Returns:
            Created scenario
        """
        base_return = self._persistence.load_return(return_id)
        if not base_return:
            raise ValueError(f"Return not found: {return_id}")

        mod_list = []
        for field_path, new_value in modifications.items():
            original = self._get_nested_value(base_return, field_path)
            mod_list.append({
                "field_path": field_path,
                "original_value": original,
                "new_value": new_value,
            })

        return self.create_scenario(
            return_id=return_id,
            name=name,
            scenario_type=ScenarioType.WHAT_IF,
            modifications=mod_list
        )

    # =========================================================================
    # DATABASE PERSISTENCE HELPERS
    # =========================================================================

    def _save_scenario_to_db(
        self,
        scenario: Scenario,
        snapshot_id: Optional[str] = None,
        base_snapshot_id: Optional[str] = None,
        input_hash: Optional[str] = None
    ) -> str:
        """Save a Scenario domain object to the database."""
        scenario_dict = {
            "scenario_id": str(scenario.scenario_id),
            "return_id": str(scenario.return_id),
            "name": scenario.name,
            "description": scenario.description,
            "scenario_type": scenario.scenario_type.value,
            "status": scenario.status.value,
            "base_snapshot": scenario.base_snapshot,
            "modifications": [m.to_dict() for m in scenario.modifications],
            "result": scenario.result.to_dict() if scenario.result else None,
            "is_recommended": scenario.is_recommended,
            "recommendation_reason": scenario.recommendation_reason,
            "created_at": scenario.created_at.isoformat() if scenario.created_at else None,
            "created_by": scenario.created_by,
            "calculated_at": scenario.calculated_at.isoformat() if scenario.calculated_at else None,
            "version": scenario.version,
            "snapshot_id": snapshot_id,
            "base_snapshot_id": base_snapshot_id,
            "input_hash": input_hash,
        }
        return self._scenario_persistence.save_scenario(scenario_dict)

    def _load_scenario_from_db(self, scenario_id: str) -> Optional[Scenario]:
        """Load a Scenario domain object from the database."""
        data = self._scenario_persistence.load_scenario(scenario_id)
        if not data:
            return None
        return self._dict_to_scenario(data)

    def _dict_to_scenario(self, data: Dict[str, Any]) -> Scenario:
        """Convert a database dictionary to a Scenario domain object."""
        from datetime import datetime as dt

        # Parse modifications
        modifications = []
        for m in data.get("modifications", []):
            modifications.append(ScenarioModification(
                field_path=m.get("field_path", ""),
                original_value=m.get("original_value"),
                new_value=m.get("new_value"),
                description=m.get("description"),
            ))

        # Parse result
        result = None
        result_data = data.get("result")
        if result_data:
            result = ScenarioResult(
                total_tax=result_data.get("total_tax", 0),
                federal_tax=result_data.get("federal_tax", 0),
                state_tax=result_data.get("state_tax", 0),
                effective_rate=result_data.get("effective_rate", 0),
                marginal_rate=result_data.get("marginal_rate", 0),
                base_tax=result_data.get("base_tax", 0),
                savings=result_data.get("savings", 0),
                savings_percent=result_data.get("savings_percent", 0),
                taxable_income=result_data.get("taxable_income", 0),
                total_deductions=result_data.get("total_deductions", 0),
                total_credits=result_data.get("total_credits", 0),
                breakdown=result_data.get("breakdown", {}),
            )

        # Parse timestamps
        created_at = data.get("created_at")
        if created_at and isinstance(created_at, str):
            try:
                created_at = dt.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError:
                created_at = dt.utcnow()

        calculated_at = data.get("calculated_at")
        if calculated_at and isinstance(calculated_at, str):
            try:
                calculated_at = dt.fromisoformat(calculated_at.replace("Z", "+00:00"))
            except ValueError:
                calculated_at = None

        return Scenario(
            scenario_id=UUID(data["scenario_id"]),
            return_id=UUID(data["return_id"]),
            name=data.get("name", ""),
            description=data.get("description"),
            scenario_type=ScenarioType(data.get("scenario_type", "what_if")),
            status=ScenarioStatus(data.get("status", "draft")),
            base_snapshot=data.get("base_snapshot", {}),
            modifications=modifications,
            result=result,
            is_recommended=data.get("is_recommended", False),
            recommendation_reason=data.get("recommendation_reason"),
            created_at=created_at or dt.utcnow(),
            created_by=data.get("created_by"),
            calculated_at=calculated_at,
            version=data.get("version", 1),
        )
