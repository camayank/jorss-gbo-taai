"""
Centralized Tax Calculation Helper

Central entry point for ALL tax calculations in the platform.
Ensures every calculation:
1. Gets validated (11 validation rules)
2. Uses the calculation pipeline
3. Leverages caching when available
4. Handles errors gracefully
5. Records metrics for observability

Usage:
    from web.calculation_helper import calculate_taxes, calculate_taxes_sync

    # Async (preferred)
    result = await calculate_taxes(tax_data, session_id="abc123")

    # Sync (for non-async contexts)
    result = calculate_taxes_sync(tax_data, session_id="abc123")
"""

import logging
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


def _record_calculation_metrics(
    cache_hit: bool,
    validation_errors: int,
    validation_warnings: int,
    latency_ms: float,
    filing_status: str
):
    """Record calculation metrics to the health/metrics system."""
    try:
        from web.routers.health import record_calculation
        record_calculation(
            cache_hit=cache_hit,
            validation_errors=validation_errors,
            validation_warnings=validation_warnings,
            latency_ms=latency_ms,
            filing_status=filing_status
        )
    except ImportError:
        pass  # Metrics not available
    except Exception as e:
        logger.debug(f"Failed to record metrics: {e}")

# Singleton instances
_cached_pipeline = None
_validator = None


@dataclass
class CalculationResult:
    """Result of a tax calculation."""
    success: bool
    breakdown: Optional[Dict[str, Any]] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    cache_hit: bool = False
    validation_issues: List[Dict[str, Any]] = field(default_factory=list)

    # Convenience accessors for common fields
    @property
    def federal_tax(self) -> float:
        if self.breakdown:
            return self.breakdown.get("federal_tax", 0) or self.breakdown.get("total_federal_tax", 0)
        return 0

    @property
    def state_tax(self) -> float:
        if self.breakdown:
            return self.breakdown.get("state_tax", 0) or self.breakdown.get("total_state_tax", 0)
        return 0

    @property
    def total_tax(self) -> float:
        if self.breakdown:
            return self.breakdown.get("total_tax", 0) or (self.federal_tax + self.state_tax)
        return 0

    @property
    def effective_rate(self) -> float:
        if self.breakdown:
            return self.breakdown.get("effective_rate", 0) or self.breakdown.get("effective_tax_rate", 0)
        return 0

    @property
    def agi(self) -> float:
        if self.breakdown:
            return self.breakdown.get("agi", 0) or self.breakdown.get("adjusted_gross_income", 0)
        return 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "breakdown": self.breakdown,
            "errors": self.errors,
            "warnings": self.warnings,
            "cache_hit": self.cache_hit,
            "validation_issues": self.validation_issues,
            "federal_tax": self.federal_tax,
            "state_tax": self.state_tax,
            "total_tax": self.total_tax,
            "effective_rate": self.effective_rate,
            "agi": self.agi
        }


def _get_validator():
    """Get or create ValidationService singleton."""
    global _validator
    if _validator is None:
        try:
            from services.validation_service import ValidationService
            _validator = ValidationService()
            logger.info("ValidationService initialized")
        except ImportError as e:
            logger.warning(f"ValidationService not available: {e}")
            _validator = None
    return _validator


def _get_pipeline():
    """Get or create CachedCalculationPipeline singleton."""
    global _cached_pipeline
    if _cached_pipeline is None:
        try:
            from services.cached_calculation_pipeline import CachedCalculationPipeline
            _cached_pipeline = CachedCalculationPipeline()
            logger.info("CachedCalculationPipeline initialized")
        except ImportError as e:
            logger.warning(f"CachedCalculationPipeline not available: {e}")
            _cached_pipeline = None
    return _cached_pipeline


def _calculate_rental_net_income(profile: Dict[str, Any]) -> float:
    """
    Calculate net rental income from profile.

    If enhanced rental fields (gross, expenses, depreciation) are provided,
    calculates: gross - expenses - depreciation
    Otherwise falls back to simple rental_income field.
    """
    rental_gross = profile.get("rental_gross_income", 0) or 0

    if rental_gross > 0:
        # Enhanced rental calculation
        rental_expenses = profile.get("rental_expenses", 0) or 0
        rental_depreciation = profile.get("rental_depreciation", 0) or 0
        rental_mortgage = profile.get("rental_mortgage_interest", 0) or 0
        rental_taxes = profile.get("rental_property_taxes", 0) or 0

        # Total deductible expenses
        total_expenses = rental_expenses + rental_depreciation + rental_mortgage + rental_taxes

        return rental_gross - total_expenses
    else:
        # Simple rental income (already net)
        return profile.get("rental_income", 0) or 0


def _build_tax_return_from_profile(profile: Dict[str, Any]):
    """
    Build a TaxReturn object from advisor profile data.

    Maps the flat profile structure to nested TaxReturn model.
    Uses a simplified approach that works with the actual model structure.
    """
    from models.tax_return import TaxReturn
    from models.taxpayer import TaxpayerInfo, FilingStatus
    from models.income import Income, W2Info, ScheduleK1, K1SourceType
    from models.deductions import Deductions
    from models.credits import TaxCredits

    # Map filing status string to enum
    status_map = {
        "single": FilingStatus.SINGLE,
        "married_joint": FilingStatus.MARRIED_JOINT,
        "married_separate": FilingStatus.MARRIED_SEPARATE,
        "head_of_household": FilingStatus.HEAD_OF_HOUSEHOLD,
        "qualifying_widow": FilingStatus.QUALIFYING_WIDOW,
        # Handle variations
        "married_filing_jointly": FilingStatus.MARRIED_JOINT,
        "married_filing_separately": FilingStatus.MARRIED_SEPARATE,
        "mfj": FilingStatus.MARRIED_JOINT,
        "mfs": FilingStatus.MARRIED_SEPARATE,
        "hoh": FilingStatus.HEAD_OF_HOUSEHOLD,
    }

    filing_status_str = profile.get("filing_status", "single").lower().replace(" ", "_")
    filing_status = status_map.get(filing_status_str, FilingStatus.SINGLE)

    # Build W2 forms if w2_income provided
    w2_forms = []
    w2_income = profile.get("w2_income", 0) or 0
    if w2_income > 0:
        w2_forms.append(W2Info(
            employer_name=profile.get("employer_name", "Primary Employer"),
            employer_ein="00-0000000",
            wages=w2_income,
            federal_tax_withheld=profile.get("federal_withheld", 0) or 0,
            state_wages=w2_income,
            state_tax_withheld=profile.get("state_withheld", 0) or 0,
            social_security_wages=min(w2_income, 168600),  # 2025 SS wage base
            social_security_tax_withheld=min(w2_income, 168600) * 0.062,
            medicare_wages=w2_income,
            medicare_tax_withheld=w2_income * 0.0145,
        ))

    # Build Schedule K-1 if K-1 income provided
    k1_forms = []
    k1_ordinary = profile.get("k1_ordinary_income", 0) or 0
    k1_rental = profile.get("k1_rental_income", 0) or 0
    k1_interest = profile.get("k1_interest_income", 0) or 0
    k1_dividends = profile.get("k1_dividends", 0) or 0
    k1_cap_gains = profile.get("k1_capital_gains", 0) or 0
    k1_guaranteed = profile.get("k1_guaranteed_payments", 0) or 0

    if any([k1_ordinary, k1_rental, k1_interest, k1_dividends, k1_cap_gains, k1_guaranteed]):
        k1_forms.append(ScheduleK1(
            k1_type=K1SourceType.PARTNERSHIP,  # Default to partnership
            entity_name=profile.get("k1_entity_name", "Pass-through Entity"),
            ordinary_business_income=k1_ordinary,
            net_rental_real_estate=k1_rental,
            guaranteed_payments=k1_guaranteed,
            interest_income=k1_interest,
            ordinary_dividends=k1_dividends,
            net_long_term_capital_gain=k1_cap_gains,
            # QBI-related fields
            qbi_ordinary_income=k1_ordinary if not profile.get("k1_is_sstb", False) else 0,
            w2_wages_for_qbi=profile.get("k1_w2_wages", 0) or 0,
            ubia_for_qbi=profile.get("k1_ubia", 0) or 0,
            is_sstb=profile.get("k1_is_sstb", False),
            is_passive_activity=profile.get("k1_is_passive", True),
            # Section 179 flows through as ordinary deduction
            self_employment_earnings=k1_ordinary if not profile.get("k1_is_passive", True) else 0,
        ))

    # Build TaxReturn
    tax_return = TaxReturn(
        tax_year=profile.get("tax_year", 2025),
        taxpayer=TaxpayerInfo(
            first_name=profile.get("first_name", "Taxpayer"),
            last_name=profile.get("last_name", "User"),
            ssn=profile.get("ssn", "000-00-0000"),
            date_of_birth=profile.get("date_of_birth"),
            filing_status=filing_status,
            occupation=profile.get("occupation"),
            spouse_first_name=profile.get("spouse_first_name"),
            spouse_last_name=profile.get("spouse_last_name"),
            spouse_ssn=profile.get("spouse_ssn"),
            number_of_dependents=profile.get("dependents", 0) or 0,
            state_of_residence=profile.get("state", "CA"),
        ),
        income=Income(
            w2_forms=w2_forms,
            schedule_k1_forms=k1_forms,
            dividend_income=profile.get("dividend_income", 0) or 0,
            qualified_dividends=profile.get("qualified_dividends", 0) or 0,
            interest_income=profile.get("interest_income", 0) or profile.get("investment_income", 0) or 0,
            self_employment_income=profile.get("business_income", 0) or profile.get("self_employment_income", 0) or 0,
            # Enhanced rental: use gross - expenses if provided, otherwise simple rental_income
            rental_income=_calculate_rental_net_income(profile),
            rental_expenses=profile.get("rental_expenses", 0) or 0,
            short_term_capital_gains=profile.get("capital_gains_short", 0) or 0,
            long_term_capital_gains=profile.get("capital_gains_long", 0) or profile.get("capital_gains", 0) or 0,
            social_security_benefits=profile.get("social_security_income", 0) or 0,
            retirement_income=profile.get("retirement_income", 0) or 0,
            other_income=profile.get("other_income", 0) or 0,
        ),
        deductions=Deductions(
            use_standard_deduction=True,  # Default to standard
            student_loan_interest=profile.get("student_loan_interest", 0) or 0,
            educator_expenses=profile.get("educator_expenses", 0) or 0,
            hsa_contributions=profile.get("hsa_contributions", 0) or 0,
            ira_contributions=profile.get("ira_contributions", 0) or 0,
            self_employed_se_health=profile.get("self_employed_health_insurance", 0) or 0,
        ),
        credits=TaxCredits(
            child_tax_credit=0,  # Will be calculated
            earned_income_credit=0,  # Will be calculated
            education_credits=profile.get("education_credits", 0) or 0,
            child_care_credit=profile.get("child_care_credit", 0) or 0,
            other_credits=profile.get("other_credits", 0) or 0,
        ),
    )

    # Handle itemized deductions if provided
    mortgage_interest = profile.get("mortgage_interest", 0) or 0
    property_taxes = profile.get("property_taxes", 0) or 0
    charitable = profile.get("charitable_donations", 0) or 0
    medical = profile.get("medical_expenses", 0) or 0
    state_taxes = profile.get("state_taxes_paid", 0) or 0

    if any([mortgage_interest, property_taxes, charitable, medical, state_taxes]):
        from models.deductions import ItemizedDeductions
        tax_return.deductions.use_standard_deduction = False
        tax_return.deductions.itemized = ItemizedDeductions(
            mortgage_interest=mortgage_interest,
            real_estate_tax=property_taxes,
            state_local_income_tax=state_taxes,
            charitable_cash=charitable,
            medical_expenses=medical,
        )

    return tax_return


def _convert_breakdown_to_dict(breakdown) -> Dict[str, Any]:
    """Convert CalculationBreakdown to dictionary."""
    if breakdown is None:
        return {}

    try:
        # Try dataclass asdict
        from dataclasses import asdict
        return asdict(breakdown)
    except Exception:
        pass

    try:
        # Try Pydantic model_dump
        return breakdown.model_dump()
    except Exception:
        pass

    try:
        # Try dict() or to_dict()
        if hasattr(breakdown, 'to_dict'):
            return breakdown.to_dict()
        return dict(breakdown)
    except Exception:
        pass

    # Manual extraction
    return {
        "total_federal_tax": getattr(breakdown, 'total_federal_tax', 0),
        "total_state_tax": getattr(breakdown, 'total_state_tax', 0),
        "total_tax": getattr(breakdown, 'total_tax', 0),
        "effective_tax_rate": getattr(breakdown, 'effective_tax_rate', 0),
        "marginal_bracket": getattr(breakdown, 'marginal_bracket', 0),
        "adjusted_gross_income": getattr(breakdown, 'adjusted_gross_income', 0),
        "taxable_income": getattr(breakdown, 'taxable_income', 0),
    }


async def calculate_taxes(
    tax_data: Dict[str, Any],
    return_id: Optional[str] = None,
    session_id: Optional[str] = None,
    use_cache: bool = True,
    validate: bool = True,
    prior_year_data: Optional[Dict[str, Any]] = None,
    is_profile_format: bool = True
) -> CalculationResult:
    """
    Central async tax calculation with validation + caching.

    Args:
        tax_data: Tax return data or advisor profile
        return_id: Tax return identifier (for caching)
        session_id: Session identifier
        use_cache: Whether to use calculation cache
        validate: Whether to run validation rules
        prior_year_data: Prior year carryover data
        is_profile_format: True if tax_data is advisor profile format

    Returns:
        CalculationResult with breakdown, errors, warnings
    """
    start_time = time.time()
    errors = []
    warnings = []
    validation_issues = []
    validation_error_count = 0
    validation_warning_count = 0
    filing_status = str(tax_data.get("filing_status", "unknown") or "unknown")

    # Build TaxReturn from data
    try:
        if is_profile_format:
            tax_return = _build_tax_return_from_profile(tax_data)
        else:
            from models.tax_return import TaxReturn
            tax_return = TaxReturn.from_dict(tax_data)
    except Exception as e:
        logger.error(f"Failed to build TaxReturn: {e}")
        return CalculationResult(
            success=False,
            errors=[f"Invalid tax data: {str(e)}"]
        )

    # Validation
    if validate:
        validator = _get_validator()
        if validator:
            try:
                validation_result = validator.validate(tax_return, tax_data)

                # Collect validation issues
                for issue in validation_result.issues:
                    validation_issues.append(issue.to_dict())
                    if issue.severity.value == "error":
                        errors.append(issue.message)
                        validation_error_count += 1
                    elif issue.severity.value == "warning":
                        warnings.append(issue.message)
                        validation_warning_count += 1

                # For advisor flow, don't block on validation errors
                # (users may not have all required fields yet)
                if not validation_result.is_valid and not is_profile_format:
                    return CalculationResult(
                        success=False,
                        errors=errors,
                        warnings=warnings,
                        validation_issues=validation_issues
                    )

            except Exception as e:
                logger.warning(f"Validation failed: {e}")
                warnings.append(f"Validation skipped: {str(e)}")

    # Calculate with pipeline
    pipeline = _get_pipeline()
    cache_hit = False

    if pipeline:
        try:
            # Use cached pipeline
            context = await pipeline.execute(
                tax_return=tax_return,
                tax_return_data=tax_data,
                return_id=return_id or session_id,
                session_id=session_id,
                prior_year_carryovers=prior_year_data,
                bypass_cache=not use_cache
            )

            cache_hit = context.metadata.get('cache_hit', False)

            if context.is_valid and context.breakdown:
                breakdown_dict = _convert_breakdown_to_dict(context.breakdown)
                # Record metrics for observability
                latency_ms = (time.time() - start_time) * 1000
                _record_calculation_metrics(
                    cache_hit=cache_hit,
                    validation_errors=validation_error_count,
                    validation_warnings=validation_warning_count,
                    latency_ms=latency_ms,
                    filing_status=filing_status
                )
                return CalculationResult(
                    success=True,
                    breakdown=breakdown_dict,
                    errors=errors + context.errors,
                    warnings=warnings + context.warnings,
                    cache_hit=cache_hit,
                    validation_issues=validation_issues
                )
            else:
                errors.extend(context.errors)
                warnings.extend(context.warnings)

        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}")
            warnings.append(f"Pipeline failed, using direct calculation: {str(e)}")

    # Fallback to direct calculation
    try:
        from calculator.engine import FederalTaxEngine

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)
        breakdown_dict = _convert_breakdown_to_dict(breakdown)

        # Record metrics for observability (fallback = cache miss)
        latency_ms = (time.time() - start_time) * 1000
        _record_calculation_metrics(
            cache_hit=False,
            validation_errors=validation_error_count,
            validation_warnings=validation_warning_count,
            latency_ms=latency_ms,
            filing_status=filing_status
        )

        return CalculationResult(
            success=True,
            breakdown=breakdown_dict,
            errors=errors,
            warnings=warnings,
            cache_hit=False,
            validation_issues=validation_issues
        )

    except Exception as e:
        logger.error(f"Direct calculation failed: {e}")
        errors.append(f"Calculation failed: {str(e)}")
        return CalculationResult(
            success=False,
            errors=errors,
            warnings=warnings,
            validation_issues=validation_issues
        )


def calculate_taxes_sync(
    tax_data: Dict[str, Any],
    return_id: Optional[str] = None,
    session_id: Optional[str] = None,
    use_cache: bool = False,  # Sync version doesn't use async cache
    validate: bool = True,
    is_profile_format: bool = True
) -> CalculationResult:
    """
    Synchronous tax calculation with validation.

    Use this for non-async contexts. Does not use caching.

    Args:
        tax_data: Tax return data or advisor profile
        return_id: Tax return identifier
        session_id: Session identifier
        use_cache: Ignored (sync doesn't support caching)
        validate: Whether to run validation rules
        is_profile_format: True if tax_data is advisor profile format

    Returns:
        CalculationResult with breakdown, errors, warnings
    """
    start_time = time.time()
    errors = []
    warnings = []
    validation_issues = []
    validation_error_count = 0
    validation_warning_count = 0
    filing_status = str(tax_data.get("filing_status", "unknown") or "unknown")

    # Build TaxReturn from data
    try:
        if is_profile_format:
            tax_return = _build_tax_return_from_profile(tax_data)
        else:
            from models.tax_return import TaxReturn
            tax_return = TaxReturn.from_dict(tax_data)
    except Exception as e:
        logger.error(f"Failed to build TaxReturn: {e}")
        return CalculationResult(
            success=False,
            errors=[f"Invalid tax data: {str(e)}"]
        )

    # Validation
    if validate:
        validator = _get_validator()
        if validator:
            try:
                validation_result = validator.validate(tax_return, tax_data)

                for issue in validation_result.issues:
                    validation_issues.append(issue.to_dict())
                    if issue.severity.value == "error":
                        errors.append(issue.message)
                        validation_error_count += 1
                    elif issue.severity.value == "warning":
                        warnings.append(issue.message)
                        validation_warning_count += 1

            except Exception as e:
                logger.warning(f"Validation failed: {e}")
                warnings.append(f"Validation skipped: {str(e)}")

    # Use sync pipeline if available
    pipeline = _get_pipeline()
    if pipeline:
        try:
            context = pipeline.execute_sync(
                tax_return=tax_return,
                tax_return_data=tax_data,
                return_id=return_id or session_id,
                session_id=session_id,
            )

            if context.is_valid and context.breakdown:
                breakdown_dict = _convert_breakdown_to_dict(context.breakdown)
                # Record metrics
                latency_ms = (time.time() - start_time) * 1000
                _record_calculation_metrics(
                    cache_hit=False,  # Sync doesn't use cache
                    validation_errors=validation_error_count,
                    validation_warnings=validation_warning_count,
                    latency_ms=latency_ms,
                    filing_status=filing_status
                )
                return CalculationResult(
                    success=True,
                    breakdown=breakdown_dict,
                    errors=errors + context.errors,
                    warnings=warnings + context.warnings,
                    cache_hit=False,
                    validation_issues=validation_issues
                )
            else:
                errors.extend(context.errors)
                warnings.extend(context.warnings)

        except Exception as e:
            logger.warning(f"Pipeline failed: {e}")

    # Fallback to direct calculation
    try:
        from calculator.engine import FederalTaxEngine

        engine = FederalTaxEngine()
        breakdown = engine.calculate(tax_return)
        breakdown_dict = _convert_breakdown_to_dict(breakdown)

        # Record metrics
        latency_ms = (time.time() - start_time) * 1000
        _record_calculation_metrics(
            cache_hit=False,
            validation_errors=validation_error_count,
            validation_warnings=validation_warning_count,
            latency_ms=latency_ms,
            filing_status=filing_status
        )

        return CalculationResult(
            success=True,
            breakdown=breakdown_dict,
            errors=errors,
            warnings=warnings,
            cache_hit=False,
            validation_issues=validation_issues
        )

    except Exception as e:
        logger.error(f"Direct calculation failed: {e}")
        errors.append(f"Calculation failed: {str(e)}")
        return CalculationResult(
            success=False,
            errors=errors,
            warnings=warnings,
            validation_issues=validation_issues
        )


async def invalidate_cache(return_id: str) -> bool:
    """
    Invalidate cached calculation for a return.

    Call this when return data changes.

    Args:
        return_id: Tax return ID

    Returns:
        True if invalidation succeeded
    """
    pipeline = _get_pipeline()
    if pipeline:
        try:
            return await pipeline.invalidate(return_id)
        except Exception as e:
            logger.error(f"Cache invalidation failed: {e}")
    return False


async def warm_cache(
    return_id: str,
    tax_data: Dict[str, Any],
    is_profile_format: bool = True
) -> bool:
    """
    Pre-compute and cache calculation for faster access.

    Args:
        return_id: Tax return ID
        tax_data: Tax return data or profile
        is_profile_format: True if tax_data is advisor profile format

    Returns:
        True if warming succeeded
    """
    result = await calculate_taxes(
        tax_data=tax_data,
        return_id=return_id,
        use_cache=True,
        validate=False,  # Skip validation for warming
        is_profile_format=is_profile_format
    )
    return result.success
