"""
Configuration Management API.

Provides REST endpoints for accessing and managing tax configuration:
- GET /api/config/tax-year/{year} : Get configuration for a tax year
- GET /api/config/parameters : List available parameters
- GET /api/config/parameter/{name} : Get specific parameter value
- GET /api/config/metadata/{year} : Get configuration metadata
- GET /api/config/changes : Get configuration change history
- GET /api/rules : List all active rules
- GET /api/rules/{rule_id} : Get specific rule details
- POST /api/rules/evaluate : Evaluate rules against context
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["Configuration"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class ConfigParameterResponse(BaseModel):
    """Response for a configuration parameter."""
    name: str
    value: Any
    tax_year: int
    filing_status: Optional[str] = None
    description: Optional[str] = None
    irs_reference: Optional[str] = None


class ConfigMetadataResponse(BaseModel):
    """Response for configuration metadata."""
    tax_year: int
    effective_date: str
    source: str
    irs_references: List[str]
    last_updated: str


class RuleResponse(BaseModel):
    """Response for a rule."""
    rule_id: str
    name: str
    description: str
    category: str
    rule_type: str
    severity: str
    limit: Optional[float] = None
    threshold: Optional[float] = None
    rate: Optional[float] = None
    irs_reference: Optional[str] = None
    irs_form: Optional[str] = None
    irs_publication: Optional[str] = None
    tax_year: int


class RuleEvaluationRequest(BaseModel):
    """Request for rule evaluation."""
    tax_year: int = Field(default=2025, description="Tax year for evaluation")
    filing_status: str = Field(description="Filing status (single, married_joint, etc.)")
    adjusted_gross_income: float = Field(default=0, description="Adjusted gross income")
    earned_income: Optional[float] = None
    wages: Optional[float] = None
    self_employment_income: Optional[float] = None
    retirement_contributions: Optional[float] = None
    itemized_deductions: Optional[float] = None
    custom_data: Optional[Dict[str, Any]] = None


class RuleEvaluationResult(BaseModel):
    """Result of evaluating a rule."""
    rule_id: str
    rule_name: str
    passed: bool
    severity: str
    message: str
    value: Optional[float] = None
    irs_reference: Optional[str] = None


class ChangeHistoryItem(BaseModel):
    """A configuration change history item."""
    parameter: str
    old_value: Any
    new_value: Any
    reason: str
    changed_by: str
    changed_at: str
    irs_reference: Optional[str] = None


# =============================================================================
# CONFIGURATION ENDPOINTS
# =============================================================================

@router.get("/tax-year/{year}", response_model=Dict[str, Any])
async def get_tax_year_config(year: int):
    """
    Get the complete tax configuration for a specific year.

    Args:
        year: Tax year (e.g., 2025)

    Returns:
        Complete configuration dictionary for the tax year
    """
    try:
        from config.tax_config_loader import TaxConfigLoader
        from pathlib import Path

        config_dir = Path(__file__).parent.parent / "config" / "tax_parameters"
        loader = TaxConfigLoader(config_dir=config_dir)

        config = loader.load_config(year)

        return {
            "success": True,
            "tax_year": year,
            "config": config,
            "retrieved_at": datetime.utcnow().isoformat(),
        }
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Configuration for tax year {year} not found"
        )
    except Exception as e:
        logger.error(f"Error loading config for year {year}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error loading configuration. Please try again later."
        )


@router.get("/parameters", response_model=Dict[str, Any])
async def list_parameters(year: int = Query(default=2025, description="Tax year")):
    """
    List all available configuration parameters for a tax year.

    Returns names and brief descriptions of all parameters.
    """
    try:
        from config.tax_config_loader import TaxConfigLoader
        from pathlib import Path

        config_dir = Path(__file__).parent.parent / "config" / "tax_parameters"
        loader = TaxConfigLoader(config_dir=config_dir)

        config = loader.load_config(year)

        # Build parameter list
        parameters = []
        for key, value in config.items():
            if key.startswith('_'):  # Skip metadata
                continue
            param_type = type(value).__name__
            if isinstance(value, dict):
                param_type = "by_filing_status"
            parameters.append({
                "name": key,
                "type": param_type,
                "has_filing_status_variants": isinstance(value, dict),
            })

        return {
            "success": True,
            "tax_year": year,
            "parameter_count": len(parameters),
            "parameters": parameters,
        }
    except Exception as e:
        logger.error(f"Error listing parameters: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error listing parameters. Please try again later."
        )


@router.get("/parameter/{name}", response_model=ConfigParameterResponse)
async def get_parameter(
    name: str,
    year: int = Query(default=2025, description="Tax year"),
    filing_status: Optional[str] = Query(default=None, description="Filing status")
):
    """
    Get a specific configuration parameter value.

    Args:
        name: Parameter name (e.g., 'standard_deduction', 'ss_wage_base')
        year: Tax year
        filing_status: Optional filing status for status-specific values

    Returns:
        Parameter value with metadata
    """
    try:
        from config.tax_config_loader import TaxConfigLoader
        from pathlib import Path

        config_dir = Path(__file__).parent.parent / "config" / "tax_parameters"
        loader = TaxConfigLoader(config_dir=config_dir)

        value = loader.get_parameter(name, year, filing_status)

        if value is None:
            raise HTTPException(
                status_code=404,
                detail=f"Parameter '{name}' not found for tax year {year}"
            )

        return ConfigParameterResponse(
            name=name,
            value=value,
            tax_year=year,
            filing_status=filing_status,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting parameter {name}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error getting parameter. Please try again later."
        )


@router.get("/metadata/{year}", response_model=ConfigMetadataResponse)
async def get_config_metadata(year: int):
    """
    Get metadata for a tax year's configuration.

    Includes source, IRS references, and last update time.
    """
    try:
        from config.tax_config_loader import TaxConfigLoader
        from pathlib import Path

        config_dir = Path(__file__).parent.parent / "config" / "tax_parameters"
        loader = TaxConfigLoader(config_dir=config_dir)

        loader.load_config(year)
        metadata = loader.get_metadata(year)

        if not metadata:
            raise HTTPException(
                status_code=404,
                detail=f"Metadata for tax year {year} not found"
            )

        return ConfigMetadataResponse(
            tax_year=metadata.tax_year,
            effective_date=metadata.effective_date,
            source=metadata.source,
            irs_references=metadata.irs_references,
            last_updated=metadata.last_updated,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting metadata for year {year}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error getting metadata. Please try again later."
        )


@router.get("/changes", response_model=Dict[str, Any])
async def get_change_history():
    """
    Get configuration change history.

    Returns list of all configuration changes for audit purposes.
    """
    try:
        from config.tax_config_loader import TaxConfigLoader
        from pathlib import Path

        config_dir = Path(__file__).parent.parent / "config" / "tax_parameters"
        loader = TaxConfigLoader(config_dir=config_dir)

        history = loader.get_change_history()

        changes = [
            ChangeHistoryItem(
                parameter=change.parameter,
                old_value=change.old_value,
                new_value=change.new_value,
                reason=change.reason,
                changed_by=change.changed_by,
                changed_at=change.changed_at,
                irs_reference=change.irs_reference,
            ).dict()
            for change in history
        ]

        return {
            "success": True,
            "change_count": len(changes),
            "changes": changes,
        }
    except Exception as e:
        logger.error(f"Error getting change history: {e}")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred"
        )


# =============================================================================
# RULES ENDPOINTS
# =============================================================================

rules_router = APIRouter(prefix="/api/rules", tags=["Rules"])


@rules_router.get("", response_model=Dict[str, Any])
async def list_rules(
    year: int = Query(default=2025, description="Tax year"),
    category: Optional[str] = Query(default=None, description="Filter by category")
):
    """
    List all active rules.

    Args:
        year: Tax year for rules
        category: Optional category filter

    Returns:
        List of all rules with their details
    """
    try:
        from rules import RuleEngine, RuleCategory

        engine = RuleEngine(tax_year=year)
        all_rules = engine.get_all_rules()

        # Filter by category if provided
        if category:
            try:
                cat_enum = RuleCategory(category.lower())
                all_rules = [r for r in all_rules if r.category == cat_enum]
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid category: {category}"
                )

        rules = [
            RuleResponse(
                rule_id=rule.rule_id,
                name=rule.name,
                description=rule.description,
                category=rule.category.value if hasattr(rule.category, 'value') else str(rule.category),
                rule_type=rule.rule_type.value if hasattr(rule.rule_type, 'value') else str(rule.rule_type),
                severity=rule.severity.value if hasattr(rule.severity, 'value') else str(rule.severity),
                limit=rule.limit,
                threshold=rule.threshold,
                rate=rule.rate,
                irs_reference=rule.irs_reference,
                irs_form=rule.irs_form,
                irs_publication=rule.irs_publication,
                tax_year=rule.tax_year,
            ).dict()
            for rule in all_rules
        ]

        return {
            "success": True,
            "tax_year": year,
            "rule_count": len(rules),
            "rules": rules,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing rules: {e}")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred"
        )


@rules_router.get("/categories", response_model=Dict[str, Any])
async def list_rule_categories():
    """
    List all available rule categories.

    Returns all valid rule category values for filtering.
    """
    try:
        from rules import RuleCategory

        categories = [
            {"value": cat.value, "name": cat.name}
            for cat in RuleCategory
        ]

        return {
            "success": True,
            "categories": categories,
        }
    except Exception as e:
        logger.error(f"Error listing categories: {e}")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred"
        )


@rules_router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(rule_id: str, year: int = Query(default=2025)):
    """
    Get details for a specific rule.

    Args:
        rule_id: Rule identifier (e.g., 'DED001', 'CRD001')
        year: Tax year

    Returns:
        Rule details
    """
    try:
        from rules import RuleEngine

        engine = RuleEngine(tax_year=year)
        rule = engine.get_rule(rule_id)

        if not rule:
            raise HTTPException(
                status_code=404,
                detail=f"Rule '{rule_id}' not found"
            )

        return RuleResponse(
            rule_id=rule.rule_id,
            name=rule.name,
            description=rule.description,
            category=rule.category.value if hasattr(rule.category, 'value') else str(rule.category),
            rule_type=rule.rule_type.value if hasattr(rule.rule_type, 'value') else str(rule.rule_type),
            severity=rule.severity.value if hasattr(rule.severity, 'value') else str(rule.severity),
            limit=rule.limit,
            threshold=rule.threshold,
            rate=rule.rate,
            irs_reference=rule.irs_reference,
            irs_form=rule.irs_form,
            irs_publication=rule.irs_publication,
            tax_year=rule.tax_year,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting rule {rule_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred"
        )


@rules_router.post("/evaluate", response_model=Dict[str, Any])
async def evaluate_rules(request: RuleEvaluationRequest):
    """
    Evaluate rules against a tax context.

    Runs all applicable rules and returns results.
    """
    try:
        from rules import RuleEngine, RuleContext

        engine = RuleEngine(tax_year=request.tax_year)

        # Build context
        context = RuleContext(
            tax_year=request.tax_year,
            filing_status=request.filing_status,
            adjusted_gross_income=request.adjusted_gross_income,
            earned_income=request.earned_income,
            wages=request.wages,
            self_employment_income=request.self_employment_income,
            retirement_contributions=request.retirement_contributions,
            itemized_deductions=request.itemized_deductions,
            custom_data=request.custom_data,
        )

        # Evaluate all rules
        results = engine.evaluate_all(context)

        # Convert to response format
        evaluation_results = [
            RuleEvaluationResult(
                rule_id=r.rule_id,
                rule_name=r.rule_name,
                passed=r.passed,
                severity=r.severity.value if hasattr(r.severity, 'value') else str(r.severity),
                message=r.message,
                value=r.value,
                irs_reference=r.irs_reference,
            ).dict()
            for r in results
        ]

        # Separate passed and failed
        passed = [r for r in evaluation_results if r['passed']]
        failed = [r for r in evaluation_results if not r['passed']]

        return {
            "success": True,
            "tax_year": request.tax_year,
            "filing_status": request.filing_status,
            "total_rules_evaluated": len(results),
            "rules_passed": len(passed),
            "rules_failed": len(failed),
            "results": evaluation_results,
            "summary": {
                "passed": passed,
                "failed": failed,
            }
        }
    except Exception as e:
        logger.error(f"Error evaluating rules: {e}")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred"
        )
