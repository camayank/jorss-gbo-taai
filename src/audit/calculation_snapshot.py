"""Calculation Snapshot System.

Capture and compare tax calculation snapshots for
verification, debugging, and audit purposes.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import json
import hashlib
import uuid
from copy import deepcopy


@dataclass
class CalculationSnapshot:
    """A point-in-time snapshot of tax calculations."""
    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    return_id: str = ""
    tax_year: int = 2025
    created_at: datetime = field(default_factory=datetime.now)
    created_by: Optional[str] = None
    snapshot_type: str = "manual"  # manual, auto, pre_filing, verified

    # Input data
    taxpayer_info: Dict[str, Any] = field(default_factory=dict)
    income_data: Dict[str, Any] = field(default_factory=dict)
    deduction_data: Dict[str, Any] = field(default_factory=dict)
    credit_data: Dict[str, Any] = field(default_factory=dict)

    # Calculated values - Federal
    federal_calculations: Dict[str, Any] = field(default_factory=lambda: {
        'gross_income': 0.0,
        'adjustments': 0.0,
        'agi': 0.0,
        'standard_or_itemized': 'standard',
        'deduction_amount': 0.0,
        'qbi_deduction': 0.0,
        'taxable_income': 0.0,
        'tax_before_credits': 0.0,
        'nonrefundable_credits': 0.0,
        'tax_after_credits': 0.0,
        'other_taxes': 0.0,
        'total_tax': 0.0,
        'total_payments': 0.0,
        'refund_or_owed': 0.0
    })

    # Calculated values - State
    state_calculations: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Intermediate calculations
    calculation_details: Dict[str, Any] = field(default_factory=lambda: {
        'bracket_breakdown': [],
        'credit_details': {},
        'deduction_details': {},
        'adjustment_details': {}
    })

    # Metadata
    version: str = "1.0"
    calculation_engine_version: str = ""
    notes: Optional[str] = None
    integrity_hash: str = ""

    def __post_init__(self):
        """Generate integrity hash after initialization."""
        if not self.integrity_hash:
            self.integrity_hash = self._generate_hash()

    def _generate_hash(self) -> str:
        """Generate hash for integrity verification."""
        data = {
            'snapshot_id': self.snapshot_id,
            'return_id': self.return_id,
            'tax_year': self.tax_year,
            'income_data': self.income_data,
            'deduction_data': self.deduction_data,
            'federal_calculations': self.federal_calculations,
            'state_calculations': self.state_calculations
        }
        content = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify the snapshot hasn't been tampered with."""
        return self._generate_hash() == self.integrity_hash

    def get_bottom_line(self) -> Dict[str, float]:
        """Get the key bottom-line numbers."""
        federal = self.federal_calculations
        return {
            'agi': federal.get('agi', 0),
            'taxable_income': federal.get('taxable_income', 0),
            'total_tax': federal.get('total_tax', 0),
            'total_payments': federal.get('total_payments', 0),
            'refund_or_owed': federal.get('refund_or_owed', 0)
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            'snapshot_id': self.snapshot_id,
            'return_id': self.return_id,
            'tax_year': self.tax_year,
            'created_at': self.created_at.isoformat(),
            'created_by': self.created_by,
            'snapshot_type': self.snapshot_type,
            'taxpayer_info': self.taxpayer_info,
            'income_data': self.income_data,
            'deduction_data': self.deduction_data,
            'credit_data': self.credit_data,
            'federal_calculations': self.federal_calculations,
            'state_calculations': self.state_calculations,
            'calculation_details': self.calculation_details,
            'version': self.version,
            'calculation_engine_version': self.calculation_engine_version,
            'notes': self.notes,
            'integrity_hash': self.integrity_hash
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CalculationSnapshot':
        """Create snapshot from dictionary."""
        snapshot = cls(
            snapshot_id=data['snapshot_id'],
            return_id=data['return_id'],
            tax_year=data['tax_year'],
            created_at=datetime.fromisoformat(data['created_at']),
            created_by=data.get('created_by'),
            snapshot_type=data.get('snapshot_type', 'manual'),
            taxpayer_info=data.get('taxpayer_info', {}),
            income_data=data.get('income_data', {}),
            deduction_data=data.get('deduction_data', {}),
            credit_data=data.get('credit_data', {}),
            federal_calculations=data.get('federal_calculations', {}),
            state_calculations=data.get('state_calculations', {}),
            calculation_details=data.get('calculation_details', {}),
            version=data.get('version', '1.0'),
            calculation_engine_version=data.get('calculation_engine_version', ''),
            notes=data.get('notes'),
            integrity_hash=data.get('integrity_hash', '')
        )
        return snapshot


@dataclass
class SnapshotDifference:
    """Represents a difference between two snapshots."""
    field_path: str
    old_value: Any
    new_value: Any
    difference: float = 0.0  # For numeric values
    percent_change: Optional[float] = None
    category: str = ""  # income, deduction, calculation, etc.
    significance: str = "low"  # low, medium, high, critical

    def to_dict(self) -> Dict[str, Any]:
        return {
            'field_path': self.field_path,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'difference': self.difference,
            'percent_change': self.percent_change,
            'category': self.category,
            'significance': self.significance
        }


@dataclass
class SnapshotComparison:
    """Comparison between two calculation snapshots."""
    comparison_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    snapshot_1_id: str = ""
    snapshot_2_id: str = ""
    compared_at: datetime = field(default_factory=datetime.now)
    differences: List[SnapshotDifference] = field(default_factory=list)

    @property
    def has_differences(self) -> bool:
        return len(self.differences) > 0

    @property
    def has_critical_differences(self) -> bool:
        return any(d.significance == 'critical' for d in self.differences)

    @property
    def bottom_line_changed(self) -> bool:
        critical_fields = ['total_tax', 'refund_or_owed', 'agi', 'taxable_income']
        return any(
            d.field_path.endswith(f) for d in self.differences for f in critical_fields
        )

    def get_differences_by_category(self, category: str) -> List[SnapshotDifference]:
        return [d for d in self.differences if d.category == category]

    def get_differences_by_significance(
        self,
        significance: str
    ) -> List[SnapshotDifference]:
        return [d for d in self.differences if d.significance == significance]

    def get_summary(self) -> Dict[str, Any]:
        return {
            'comparison_id': self.comparison_id,
            'snapshot_1_id': self.snapshot_1_id,
            'snapshot_2_id': self.snapshot_2_id,
            'compared_at': self.compared_at.isoformat(),
            'total_differences': len(self.differences),
            'by_significance': {
                'critical': len(self.get_differences_by_significance('critical')),
                'high': len(self.get_differences_by_significance('high')),
                'medium': len(self.get_differences_by_significance('medium')),
                'low': len(self.get_differences_by_significance('low'))
            },
            'bottom_line_changed': self.bottom_line_changed
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            'comparison_id': self.comparison_id,
            'snapshot_1_id': self.snapshot_1_id,
            'snapshot_2_id': self.snapshot_2_id,
            'compared_at': self.compared_at.isoformat(),
            'differences': [d.to_dict() for d in self.differences],
            'summary': self.get_summary()
        }


class SnapshotManager:
    """
    Manages calculation snapshots for tax returns.

    Provides functionality to capture, compare, and
    analyze calculation snapshots over time.
    """

    def __init__(self):
        self.snapshots: Dict[str, CalculationSnapshot] = {}
        self.comparisons: Dict[str, SnapshotComparison] = {}
        self._snapshots_by_return: Dict[str, List[str]] = {}

    def capture_snapshot(
        self,
        return_id: str,
        tax_year: int,
        taxpayer_info: Dict[str, Any],
        income_data: Dict[str, Any],
        deduction_data: Dict[str, Any],
        credit_data: Dict[str, Any],
        federal_calculations: Dict[str, Any],
        state_calculations: Optional[Dict[str, Dict[str, Any]]] = None,
        calculation_details: Optional[Dict[str, Any]] = None,
        snapshot_type: str = "manual",
        created_by: Optional[str] = None,
        notes: Optional[str] = None
    ) -> CalculationSnapshot:
        """Capture a new calculation snapshot."""
        snapshot = CalculationSnapshot(
            return_id=return_id,
            tax_year=tax_year,
            snapshot_type=snapshot_type,
            created_by=created_by,
            taxpayer_info=deepcopy(taxpayer_info),
            income_data=deepcopy(income_data),
            deduction_data=deepcopy(deduction_data),
            credit_data=deepcopy(credit_data),
            federal_calculations=deepcopy(federal_calculations),
            state_calculations=deepcopy(state_calculations or {}),
            calculation_details=deepcopy(calculation_details or {}),
            notes=notes
        )

        self.snapshots[snapshot.snapshot_id] = snapshot

        # Index by return
        if return_id not in self._snapshots_by_return:
            self._snapshots_by_return[return_id] = []
        self._snapshots_by_return[return_id].append(snapshot.snapshot_id)

        return snapshot

    def capture_from_tax_return(
        self,
        tax_return: Any,  # TaxReturn object
        snapshot_type: str = "auto",
        created_by: Optional[str] = None
    ) -> CalculationSnapshot:
        """Capture snapshot from a TaxReturn object."""
        # Extract data from tax return
        taxpayer_info = {
            'first_name': getattr(tax_return, 'first_name', ''),
            'last_name': getattr(tax_return, 'last_name', ''),
            'filing_status': str(getattr(tax_return, 'filing_status', '')),
        }

        income_data = {}
        if hasattr(tax_return, 'income'):
            income = tax_return.income
            income_data = {
                'w2_wages': getattr(income, 'w2_wages', 0),
                'interest_income': getattr(income, 'interest_income', 0),
                'dividend_income': getattr(income, 'dividend_income', 0),
                'capital_gains': getattr(income, 'capital_gains', 0),
                'business_income': getattr(income, 'business_income', 0),
            }

        deduction_data = {}
        if hasattr(tax_return, 'deductions'):
            deductions = tax_return.deductions
            deduction_data = {
                'mortgage_interest': getattr(deductions, 'mortgage_interest', 0),
                'property_taxes': getattr(deductions, 'property_taxes', 0),
                'charitable_cash': getattr(deductions, 'charitable_cash', 0),
                'medical_expenses': getattr(deductions, 'medical_expenses', 0),
            }

        federal_calculations = {}
        if hasattr(tax_return, 'calculated_results'):
            results = tax_return.calculated_results
            federal_calculations = {
                'gross_income': getattr(results, 'gross_income', 0),
                'agi': getattr(results, 'agi', 0),
                'taxable_income': getattr(results, 'taxable_income', 0),
                'total_tax': getattr(results, 'total_tax', 0),
                'total_payments': getattr(results, 'total_payments', 0),
                'refund_or_owed': getattr(results, 'refund_or_owed', 0),
            }

        return self.capture_snapshot(
            return_id=getattr(tax_return, 'return_id', str(uuid.uuid4())),
            tax_year=getattr(tax_return, 'tax_year', 2025),
            taxpayer_info=taxpayer_info,
            income_data=income_data,
            deduction_data=deduction_data,
            credit_data={},
            federal_calculations=federal_calculations,
            snapshot_type=snapshot_type,
            created_by=created_by
        )

    def get_snapshot(self, snapshot_id: str) -> Optional[CalculationSnapshot]:
        """Get a snapshot by ID."""
        return self.snapshots.get(snapshot_id)

    def get_snapshots_for_return(
        self,
        return_id: str
    ) -> List[CalculationSnapshot]:
        """Get all snapshots for a return, sorted by date."""
        snapshot_ids = self._snapshots_by_return.get(return_id, [])
        snapshots = [
            self.snapshots[sid] for sid in snapshot_ids
            if sid in self.snapshots
        ]
        return sorted(snapshots, key=lambda s: s.created_at)

    def get_latest_snapshot(
        self,
        return_id: str
    ) -> Optional[CalculationSnapshot]:
        """Get the most recent snapshot for a return."""
        snapshots = self.get_snapshots_for_return(return_id)
        return snapshots[-1] if snapshots else None

    def get_pre_filing_snapshot(
        self,
        return_id: str
    ) -> Optional[CalculationSnapshot]:
        """Get the pre-filing snapshot for a return."""
        snapshots = self.get_snapshots_for_return(return_id)
        for snapshot in reversed(snapshots):
            if snapshot.snapshot_type == 'pre_filing':
                return snapshot
        return None

    def compare_snapshots(
        self,
        snapshot_1_id: str,
        snapshot_2_id: str
    ) -> Optional[SnapshotComparison]:
        """Compare two snapshots and identify differences."""
        snapshot_1 = self.snapshots.get(snapshot_1_id)
        snapshot_2 = self.snapshots.get(snapshot_2_id)

        if not snapshot_1 or not snapshot_2:
            return None

        comparison = SnapshotComparison(
            snapshot_1_id=snapshot_1_id,
            snapshot_2_id=snapshot_2_id
        )

        # Compare income data
        self._compare_dicts(
            snapshot_1.income_data,
            snapshot_2.income_data,
            'income_data',
            'income',
            comparison.differences
        )

        # Compare deduction data
        self._compare_dicts(
            snapshot_1.deduction_data,
            snapshot_2.deduction_data,
            'deduction_data',
            'deduction',
            comparison.differences
        )

        # Compare federal calculations
        self._compare_dicts(
            snapshot_1.federal_calculations,
            snapshot_2.federal_calculations,
            'federal_calculations',
            'calculation',
            comparison.differences
        )

        # Compare state calculations
        for state in set(snapshot_1.state_calculations.keys()) | set(snapshot_2.state_calculations.keys()):
            state_1 = snapshot_1.state_calculations.get(state, {})
            state_2 = snapshot_2.state_calculations.get(state, {})
            self._compare_dicts(
                state_1,
                state_2,
                f'state_calculations.{state}',
                'state_calculation',
                comparison.differences
            )

        # Store comparison
        self.comparisons[comparison.comparison_id] = comparison

        return comparison

    def _compare_dicts(
        self,
        dict_1: Dict[str, Any],
        dict_2: Dict[str, Any],
        path: str,
        category: str,
        differences: List[SnapshotDifference]
    ):
        """Compare two dictionaries and record differences."""
        all_keys = set(dict_1.keys()) | set(dict_2.keys())

        for key in all_keys:
            val_1 = dict_1.get(key)
            val_2 = dict_2.get(key)

            if val_1 != val_2:
                # Calculate numeric difference if applicable
                diff = 0.0
                pct_change = None
                if isinstance(val_1, (int, float)) and isinstance(val_2, (int, float)):
                    diff = val_2 - val_1
                    if val_1 != 0:
                        pct_change = (diff / val_1) * 100

                # Determine significance
                significance = self._determine_significance(
                    key, val_1, val_2, diff, category
                )

                differences.append(SnapshotDifference(
                    field_path=f"{path}.{key}",
                    old_value=val_1,
                    new_value=val_2,
                    difference=diff,
                    percent_change=pct_change,
                    category=category,
                    significance=significance
                ))

    def _determine_significance(
        self,
        field: str,
        old_val: Any,
        new_val: Any,
        diff: float,
        category: str
    ) -> str:
        """Determine the significance of a difference."""
        # Critical fields
        critical_fields = ['total_tax', 'refund_or_owed', 'agi', 'taxable_income']
        if field in critical_fields:
            if abs(diff) > 100:
                return 'critical'
            elif abs(diff) > 10:
                return 'high'

        # Large dollar differences
        if isinstance(diff, (int, float)):
            if abs(diff) > 5000:
                return 'critical'
            elif abs(diff) > 1000:
                return 'high'
            elif abs(diff) > 100:
                return 'medium'

        # Calculation changes are more significant
        if category == 'calculation':
            return 'medium'

        return 'low'

    def compare_with_latest(
        self,
        snapshot_id: str
    ) -> Optional[SnapshotComparison]:
        """Compare a snapshot with the latest for the same return."""
        snapshot = self.snapshots.get(snapshot_id)
        if not snapshot:
            return None

        latest = self.get_latest_snapshot(snapshot.return_id)
        if not latest or latest.snapshot_id == snapshot_id:
            return None

        return self.compare_snapshots(snapshot_id, latest.snapshot_id)

    def verify_calculation(
        self,
        return_id: str,
        expected_values: Dict[str, float],
        tolerance: float = 0.01
    ) -> Tuple[bool, List[str]]:
        """Verify calculation matches expected values."""
        latest = self.get_latest_snapshot(return_id)
        if not latest:
            return False, ["No snapshot found for return"]

        discrepancies = []
        calculations = latest.federal_calculations

        for field, expected in expected_values.items():
            actual = calculations.get(field, 0)
            if abs(actual - expected) > tolerance:
                discrepancies.append(
                    f"{field}: expected {expected:.2f}, got {actual:.2f}"
                )

        return len(discrepancies) == 0, discrepancies

    def generate_calculation_report(
        self,
        return_id: str
    ) -> Optional[Dict[str, Any]]:
        """Generate a detailed calculation report for a return."""
        snapshots = self.get_snapshots_for_return(return_id)
        if not snapshots:
            return None

        latest = snapshots[-1]

        report = {
            'return_id': return_id,
            'tax_year': latest.tax_year,
            'generated_at': datetime.now().isoformat(),
            'snapshot_count': len(snapshots),
            'latest_snapshot': {
                'id': latest.snapshot_id,
                'type': latest.snapshot_type,
                'created_at': latest.created_at.isoformat(),
                'integrity_verified': latest.verify_integrity()
            },
            'calculations': {
                'income': latest.income_data,
                'deductions': latest.deduction_data,
                'credits': latest.credit_data,
                'federal': latest.federal_calculations,
                'state': latest.state_calculations
            },
            'bottom_line': latest.get_bottom_line()
        }

        # Add history if multiple snapshots
        if len(snapshots) > 1:
            history = []
            for i, snap in enumerate(snapshots):
                entry = {
                    'snapshot_id': snap.snapshot_id,
                    'created_at': snap.created_at.isoformat(),
                    'type': snap.snapshot_type,
                    'bottom_line': snap.get_bottom_line()
                }

                # Compare with previous
                if i > 0:
                    comparison = self.compare_snapshots(
                        snapshots[i-1].snapshot_id,
                        snap.snapshot_id
                    )
                    if comparison:
                        entry['changes_from_previous'] = comparison.get_summary()

                history.append(entry)

            report['history'] = history

        return report

    def export_snapshots(self, return_id: Optional[str] = None) -> str:
        """Export snapshots to JSON."""
        if return_id:
            snapshots = self.get_snapshots_for_return(return_id)
        else:
            snapshots = list(self.snapshots.values())

        return json.dumps({
            'snapshots': [s.to_dict() for s in snapshots],
            'export_timestamp': datetime.now().isoformat()
        }, indent=2)

    def import_snapshots(self, json_data: str):
        """Import snapshots from JSON."""
        data = json.loads(json_data)

        for snap_data in data.get('snapshots', []):
            snapshot = CalculationSnapshot.from_dict(snap_data)
            self.snapshots[snapshot.snapshot_id] = snapshot

            # Rebuild index
            if snapshot.return_id not in self._snapshots_by_return:
                self._snapshots_by_return[snapshot.return_id] = []
            if snapshot.snapshot_id not in self._snapshots_by_return[snapshot.return_id]:
                self._snapshots_by_return[snapshot.return_id].append(snapshot.snapshot_id)
