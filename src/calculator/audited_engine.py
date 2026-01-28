"""
Audit-Integrated Tax Calculation Engine

SPEC-012 Critical Gap Fix: Wraps FederalTaxEngine with comprehensive audit logging.

This module provides audit trail functionality for all tax computations,
ensuring compliance requirements are met for:
- Computation tracking
- Input/output logging
- Change detection
- IRS audit support
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from models.tax_return import TaxReturn
from calculator.engine import FederalTaxEngine, CalculationBreakdown
from calculator.tax_year_config import TaxYearConfig
from audit.audit_logger import (
    get_audit_logger,
    audit_tax_calculation,
    AuditEventType,
    AuditSeverity,
)


class AuditedTaxEngine:
    """
    Tax calculation engine with comprehensive audit logging.

    Wraps FederalTaxEngine to automatically log:
    - All calculation inputs (with PII redaction)
    - Calculation results and breakdown
    - Computation timestamps and duration
    - Hash-based computation verification

    Usage:
        engine = AuditedTaxEngine(session_id="...", user_id="...")
        result = engine.calculate(tax_return)
        # Audit trail is automatically created
    """

    def __init__(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        config: Optional[TaxYearConfig] = None,
    ):
        """
        Initialize audited tax engine.

        Args:
            session_id: Tax filing session ID (required for audit trail)
            user_id: User performing the calculation
            tenant_id: Tenant context for multi-tenant systems
            config: Tax year configuration (defaults to 2025)
        """
        self.session_id = session_id
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.config = config or TaxYearConfig.for_2025()
        self._engine = FederalTaxEngine(config=self.config)
        self._logger = get_audit_logger()
        self._calculation_count = 0

    def calculate(self, tax_return: TaxReturn) -> CalculationBreakdown:
        """
        Execute tax calculation with full audit logging.

        Args:
            tax_return: Complete tax return data

        Returns:
            CalculationBreakdown with all computed values
        """
        start_time = datetime.utcnow()
        self._calculation_count += 1

        # Capture inputs (redacted for audit)
        inputs = self._capture_inputs(tax_return)
        input_hash = self._compute_hash(inputs)

        try:
            # Execute calculation
            result = self._engine.calculate(tax_return)

            # Capture outputs
            outputs = self._capture_outputs(result)
            output_hash = self._compute_hash(outputs)

            # Calculate duration
            end_time = datetime.utcnow()
            duration_ms = (end_time - start_time).total_seconds() * 1000

            # Log successful calculation
            self._log_calculation(
                calculation_type="federal_tax",
                inputs=inputs,
                outputs=outputs,
                input_hash=input_hash,
                output_hash=output_hash,
                duration_ms=duration_ms,
                success=True,
            )

            return result

        except Exception as e:
            # Log failed calculation
            end_time = datetime.utcnow()
            duration_ms = (end_time - start_time).total_seconds() * 1000

            self._log_calculation(
                calculation_type="federal_tax",
                inputs=inputs,
                outputs=None,
                input_hash=input_hash,
                output_hash=None,
                duration_ms=duration_ms,
                success=False,
                error_message=str(e),
            )
            raise

    def calculate_with_scenarios(
        self,
        tax_return: TaxReturn,
        scenario_name: str = "base",
    ) -> CalculationBreakdown:
        """
        Calculate with scenario tracking for what-if analysis.

        Args:
            tax_return: Tax return data
            scenario_name: Name of the scenario (e.g., "base", "itemized", "mfj")

        Returns:
            Calculation breakdown
        """
        start_time = datetime.utcnow()

        # Capture inputs
        inputs = self._capture_inputs(tax_return)
        inputs["scenario_name"] = scenario_name
        input_hash = self._compute_hash(inputs)

        try:
            result = self._engine.calculate(tax_return)
            outputs = self._capture_outputs(result)
            output_hash = self._compute_hash(outputs)

            end_time = datetime.utcnow()
            duration_ms = (end_time - start_time).total_seconds() * 1000

            # Log with scenario context
            self._log_calculation(
                calculation_type="scenario_analysis",
                inputs=inputs,
                outputs=outputs,
                input_hash=input_hash,
                output_hash=output_hash,
                duration_ms=duration_ms,
                success=True,
                metadata={"scenario_name": scenario_name},
            )

            return result

        except Exception as e:
            self._log_calculation(
                calculation_type="scenario_analysis",
                inputs=inputs,
                outputs=None,
                input_hash=input_hash,
                output_hash=None,
                duration_ms=0,
                success=False,
                error_message=str(e),
                metadata={"scenario_name": scenario_name},
            )
            raise

    def _capture_inputs(self, tax_return: TaxReturn) -> Dict[str, Any]:
        """Capture calculation inputs with PII redaction."""
        return {
            "tax_year": tax_return.tax_year,
            "filing_status": tax_return.taxpayer.filing_status.value if tax_return.taxpayer.filing_status else None,
            # Redact SSN but include hash for verification
            "ssn_hash": self._hash_ssn(tax_return.taxpayer.ssn) if tax_return.taxpayer.ssn else None,
            # Income summary (not individual amounts for privacy)
            "income_summary": {
                "total_wages": float(tax_return.income.get_total_wages()),
                "total_income": float(tax_return.income.get_total_income()),
                "has_business_income": tax_return.income.get_schedule_c_net_profit() > 0,
                "has_investment_income": (
                    tax_return.income.interest_income > 0 or
                    tax_return.income.dividend_income > 0 or
                    tax_return.income.qualified_dividends > 0
                ),
                "has_rental_income": tax_return.income.rental_income != 0,
            },
            # Deduction summary
            "deduction_summary": {
                "ira_contributions": float(tax_return.deductions.ira_contributions),
                "hsa_contributions": float(tax_return.deductions.hsa_contributions),
                "student_loan_interest": float(tax_return.deductions.student_loan_interest),
            },
            # Dependent count (not individual details)
            "dependent_count": len(tax_return.dependents) if tax_return.dependents else 0,
            # Calculation version
            "engine_version": "2025.1",
            "config_tax_year": self.config.tax_year,
        }

    def _capture_outputs(self, result: CalculationBreakdown) -> Dict[str, Any]:
        """Capture calculation outputs for audit."""
        return {
            "gross_income": float(result.gross_income),
            "adjustments_to_income": float(result.adjustments_to_income),
            "agi": float(result.agi),
            "deduction_type": result.deduction_type,
            "deduction_amount": float(result.deduction_amount),
            "qbi_deduction": float(result.qbi_deduction),
            "taxable_income": float(result.taxable_income),
            "ordinary_income_tax": float(result.ordinary_income_tax),
            "preferential_income_tax": float(result.preferential_income_tax),
            "self_employment_tax": float(result.self_employment_tax),
            "additional_medicare_tax": float(result.additional_medicare_tax),
            "net_investment_income_tax": float(result.net_investment_income_tax),
            "alternative_minimum_tax": float(result.alternative_minimum_tax),
            "total_tax_before_credits": float(result.total_tax_before_credits),
            "nonrefundable_credits": float(result.nonrefundable_credits),
            "refundable_credits": float(result.refundable_credits),
            "total_tax": float(result.total_tax),
            "total_payments": float(result.total_payments),
            "refund_or_owed": float(result.refund_or_owed),
            "effective_tax_rate": float(result.effective_tax_rate),
            "marginal_tax_rate": float(result.marginal_tax_rate),
        }

    def _compute_hash(self, data: Dict[str, Any]) -> str:
        """Compute SHA-256 hash of data for integrity verification."""
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]

    def _hash_ssn(self, ssn: str) -> str:
        """Hash SSN for audit trail (never store plaintext)."""
        if not ssn:
            return None
        # Remove formatting
        clean_ssn = ssn.replace("-", "").replace(" ", "")
        return hashlib.sha256(clean_ssn.encode()).hexdigest()[:16]

    def _log_calculation(
        self,
        calculation_type: str,
        inputs: Dict[str, Any],
        outputs: Optional[Dict[str, Any]],
        input_hash: str,
        output_hash: Optional[str],
        duration_ms: float,
        success: bool,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Log calculation to audit trail."""
        self._logger.log(
            event_type=AuditEventType.TAX_DATA_CALCULATION,
            action=f"calculate_{calculation_type}",
            resource_type="tax_calculation",
            resource_id=self.session_id,
            user_id=self.user_id,
            tenant_id=self.tenant_id,
            old_value=inputs,
            new_value=outputs,
            details={
                "calculation_type": calculation_type,
                "calculation_number": self._calculation_count,
                "input_hash": input_hash,
                "output_hash": output_hash,
                "duration_ms": round(duration_ms, 2),
                "tax_year": inputs.get("tax_year"),
                "filing_status": inputs.get("filing_status"),
                **(metadata or {}),
            },
            success=success,
            error_message=error_message,
            severity=AuditSeverity.INFO if success else AuditSeverity.ERROR,
        )

    def get_calculation_history(self) -> list:
        """
        Get calculation history for this session.

        Returns:
            List of audit entries for calculations in this session
        """
        return self._logger.query(
            resource_id=self.session_id,
            event_type=AuditEventType.TAX_DATA_CALCULATION,
            limit=100,
        )

    def export_audit_trail(self) -> Dict[str, Any]:
        """
        Export complete audit trail for this session.

        Returns:
            Comprehensive audit report for IRS compliance
        """
        from audit.audit_logger import export_session_audit_report
        return export_session_audit_report(self.session_id)


def create_audited_engine(
    session_id: str,
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    tax_year: int = 2025,
) -> AuditedTaxEngine:
    """
    Factory function to create an audited tax engine.

    Args:
        session_id: Tax filing session ID
        user_id: User performing calculations
        tenant_id: Tenant context
        tax_year: Tax year for configuration

    Returns:
        Configured AuditedTaxEngine instance
    """
    config = TaxYearConfig.for_year(tax_year) if hasattr(TaxYearConfig, 'for_year') else TaxYearConfig.for_2025()
    return AuditedTaxEngine(
        session_id=session_id,
        user_id=user_id,
        tenant_id=tenant_id,
        config=config,
    )
