"""
Interview & validation API routes — extracted from app.py.

Routes:
- POST /api/legacy/validate/fields
- POST /api/legacy/validate/field/{field_name}
- POST /api/legacy/suggestions
- POST /api/interview/state
- GET  /api/partials/{partial_name}
"""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from decimal import ROUND_HALF_UP
from calculator.decimal_math import money

logger = logging.getLogger(__name__)

router = APIRouter(tags=["interview-api"])


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def safe_float(value: Any, default: float = 0.0, min_val: float = 0.0, max_val: float = 999_999_999.0) -> float:
    """Safely convert value to float with bounds checking."""
    if value is None:
        return default
    try:
        result = float(value)
        if result < min_val:
            return min_val
        if result > max_val:
            return max_val
        return float(money(result))
    except (ValueError, TypeError):
        logger.warning(f"Invalid float value: {value}, using default {default}")
        return default


# ---------------------------------------------------------------------------
# Validation endpoints
# ---------------------------------------------------------------------------

@router.post("/api/legacy/validate/fields", include_in_schema=False, deprecated=True)
async def validate_and_get_field_states(request: Request):
    """
    Get smart field visibility and validation based on current data.

    Implements 100+ conditional rules to show/hide fields, auto-calculate
    values, validate data, and provide smart suggestions.
    """
    from validation import TaxContext, get_rules_engine, ValidationSeverity

    body = await request.json()

    ctx = TaxContext(
        # Personal
        first_name=body.get('firstName', ''),
        last_name=body.get('lastName', ''),
        ssn=body.get('ssn', ''),
        date_of_birth=body.get('dob', ''),
        is_blind=body.get('isBlind', False),
        # Spouse
        spouse_first_name=body.get('spouseFirstName', ''),
        spouse_last_name=body.get('spouseLastName', ''),
        spouse_ssn=body.get('spouseSsn', ''),
        spouse_dob=body.get('spouseDob', ''),
        spouse_is_blind=body.get('spouseIsBlind', False),
        # Filing
        filing_status=body.get('filingStatus', ''),
        # Address
        street=body.get('street', ''),
        city=body.get('city', ''),
        state=body.get('state', ''),
        zip_code=body.get('zipCode', ''),
        # Dependents
        dependents=body.get('dependents', []),
        # Income
        wages=safe_float(body.get('wages')),
        wages_secondary=safe_float(body.get('wagesSecondary')),
        interest_income=safe_float(body.get('interestIncome')),
        dividend_income=safe_float(body.get('dividendIncome')),
        qualified_dividends=safe_float(body.get('qualifiedDividends')),
        capital_gains_short=safe_float(body.get('capitalGainsShort')),
        capital_gains_long=safe_float(body.get('capitalGainsLong')),
        business_income=safe_float(body.get('businessIncome')),
        business_expenses=safe_float(body.get('businessExpenses')),
        rental_income=safe_float(body.get('rentalIncome')),
        rental_expenses=safe_float(body.get('rentalExpenses')),
        retirement_income=safe_float(body.get('retirementIncome')),
        social_security=safe_float(body.get('socialSecurity')),
        unemployment=safe_float(body.get('unemployment')),
        other_income=safe_float(body.get('otherIncome')),
        # Withholding
        federal_withheld=safe_float(body.get('federalWithheld')),
        state_withheld=safe_float(body.get('stateWithheld')),
        # Deductions
        use_standard_deduction=body.get('useStandardDeduction', True),
        medical_expenses=safe_float(body.get('medicalExpenses')),
        state_local_taxes=safe_float(body.get('stateLocalTaxes')),
        real_estate_taxes=safe_float(body.get('realEstateTaxes')),
        mortgage_interest=safe_float(body.get('mortgageInterest')),
        charitable_cash=safe_float(body.get('charitableCash')),
        charitable_noncash=safe_float(body.get('charitableNoncash')),
        student_loan_interest=safe_float(body.get('studentLoanInterest')),
        educator_expenses=safe_float(body.get('educatorExpenses')),
        hsa_contribution=safe_float(body.get('hsaContribution')),
        ira_contribution=safe_float(body.get('iraContribution')),
        # Credits
        child_care_expenses=safe_float(body.get('childCareExpenses')),
        child_care_provider_name=body.get('childCareProviderName', ''),
        child_care_provider_ein=body.get('childCareProviderEin', ''),
        education_expenses=safe_float(body.get('educationExpenses')),
        student_name=body.get('studentName', ''),
        school_name=body.get('schoolName', ''),
        # State
        state_of_residence=body.get('stateOfResidence', body.get('state', '')),
    )

    ctx.calculate_derived_fields()
    engine = get_rules_engine()

    field_states = engine.get_all_field_states(ctx)
    validation_results = engine.validate_all(ctx)
    smart_defaults = engine.get_smart_defaults(ctx)

    fields = {}
    for field_id, state in field_states.items():
        fields[field_id] = {
            'visible': state.visible,
            'enabled': state.enabled,
            'requirement': state.requirement.value,
            'hint': state.hint,
            'defaultValue': state.default_value,
        }

    errors = []
    warnings = []
    info = []

    for result in validation_results:
        item = {
            'field': result.field,
            'message': result.message,
            'suggestion': result.suggestion,
        }
        if result.severity == ValidationSeverity.ERROR:
            errors.append(item)
        elif result.severity == ValidationSeverity.WARNING:
            warnings.append(item)
        else:
            info.append(item)

    return JSONResponse({
        'fields': fields,
        'validation': {
            'isValid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'info': info,
        },
        'computed': {
            'age': ctx.age,
            'spouseAge': ctx.spouse_age,
            'totalIncome': ctx.total_income,
            'earnedIncome': ctx.earned_income,
            'numDependents': ctx.num_dependents,
            'numQualifyingChildren': ctx.num_qualifying_children,
            'is65OrOlder': ctx.age >= 65,
            'spouseIs65OrOlder': ctx.spouse_age >= 65,
        },
        'defaults': smart_defaults,
    })


@router.post("/api/legacy/validate/field/{field_name}", operation_id="validate_tax_field", include_in_schema=False, deprecated=True)
async def validate_tax_field(field_name: str, request: Request):
    """Validate a single field and return its state."""
    from validation import TaxContext, get_rules_engine, ValidationSeverity

    body = await request.json()

    ctx = TaxContext(
        first_name=body.get('firstName', ''),
        last_name=body.get('lastName', ''),
        ssn=body.get('ssn', ''),
        date_of_birth=body.get('dob', ''),
        filing_status=body.get('filingStatus', ''),
        spouse_ssn=body.get('spouseSsn', ''),
        spouse_dob=body.get('spouseDob', ''),
        dependents=body.get('dependents', []),
        wages=safe_float(body.get('wages')),
        business_income=safe_float(body.get('businessIncome')),
    )

    ctx.calculate_derived_fields()
    engine = get_rules_engine()

    results = engine.validate_field(field_name, ctx)
    requirement = engine.get_field_requirement(field_name, ctx)
    visible = engine.is_field_visible(field_name, ctx)

    errors = [r for r in results if r.severity == ValidationSeverity.ERROR and not r.valid]
    warnings = [r for r in results if r.severity == ValidationSeverity.WARNING]

    return JSONResponse({
        'field': field_name,
        'visible': visible,
        'requirement': requirement.value,
        'isValid': len(errors) == 0,
        'errors': [{'message': e.message, 'suggestion': e.suggestion} for e in errors],
        'warnings': [{'message': w.message, 'suggestion': w.suggestion} for w in warnings],
    })


# ---------------------------------------------------------------------------
# Suggestions & Interview State
# ---------------------------------------------------------------------------

@router.post("/api/legacy/suggestions", include_in_schema=False, deprecated=True)
async def get_tax_suggestions(request: Request):
    """Get contextual tax optimization suggestions."""
    from validation import TaxContext, get_rules_engine
    from recommendation import get_recommendation_engine

    body = await request.json()

    ctx = TaxContext(
        filing_status=body.get('filingStatus', ''),
        date_of_birth=body.get('dob', ''),
        spouse_dob=body.get('spouseDob', ''),
        dependents=body.get('dependents', []),
        wages=safe_float(body.get('wages')),
        business_income=safe_float(body.get('businessIncome')),
        interest_income=safe_float(body.get('interestIncome')),
        dividend_income=safe_float(body.get('dividendIncome')),
        retirement_income=safe_float(body.get('retirementIncome')),
        social_security=safe_float(body.get('socialSecurity')),
        capital_gains_long=safe_float(body.get('capitalGainsLong')),
        use_standard_deduction=body.get('useStandardDeduction', True),
        mortgage_interest=safe_float(body.get('mortgageInterest')),
        charitable_cash=safe_float(body.get('charitableCash')),
        state_local_taxes=safe_float(body.get('stateLocalTaxes')),
        medical_expenses=safe_float(body.get('medicalExpenses')),
        ira_contribution=safe_float(body.get('iraContribution')),
        hsa_contribution=safe_float(body.get('hsaContribution')),
        child_care_expenses=safe_float(body.get('childCareExpenses')),
        education_expenses=safe_float(body.get('educationExpenses')),
        state_of_residence=body.get('stateOfResidence', body.get('state', '')),
    )

    ctx.calculate_derived_fields()

    try:
        rec_engine = get_recommendation_engine()
        recommendations = rec_engine.get_recommendations(ctx)

        tips = []
        total_potential_savings = 0

        for rec in recommendations:
            tip = {
                'id': rec.id,
                'category': rec.category,
                'title': rec.title,
                'description': rec.description,
                'potential_savings': rec.potential_savings,
                'action': rec.action,
                'priority': rec.priority,
            }
            tips.append(tip)
            total_potential_savings += rec.potential_savings or 0

        tips.sort(key=lambda x: (-x.get('priority', 0), -(x.get('potential_savings') or 0)))

        did_you_know = []

        if ctx.age and ctx.age >= 50:
            did_you_know.append({
                'message': f"At age {ctx.age}, you may be eligible for catch-up contributions to retirement accounts.",
                'category': 'retirement'
            })

        salt = ctx.state_local_taxes + (ctx.real_estate_taxes or 0)
        if salt > 10000:
            did_you_know.append({
                'message': f"Your state and local taxes (${salt:,.0f}) exceed the $10,000 SALT cap. Only $10,000 is deductible.",
                'category': 'deductions'
            })

        if not ctx.use_standard_deduction:
            std_ded = 15000 if ctx.filing_status == 'single' else 30000
            itemized = (ctx.mortgage_interest or 0) + (ctx.charitable_cash or 0) + min(salt, 10000)
            if itemized < std_ded:
                did_you_know.append({
                    'message': f"The standard deduction (${std_ded:,.0f}) may give you a larger deduction than itemizing (${itemized:,.0f}).",
                    'category': 'deductions'
                })

        return JSONResponse({
            'tips': tips[:10],
            'potential_savings': total_potential_savings,
            'did_you_know': did_you_know,
            'context': {
                'age': ctx.age,
                'filing_status': ctx.filing_status,
                'num_dependents': ctx.num_dependents,
                'total_income': ctx.total_income,
            }
        })

    except Exception as e:
        logger.error(f"Error generating suggestions: {e}")
        return JSONResponse({
            'tips': [],
            'potential_savings': 0,
            'did_you_know': [],
            'error': 'An internal error occurred'
        })


@router.post("/api/interview/state")
async def get_interview_state(request: Request):
    """Get the current interview/wizard flow state."""
    from validation import TaxContext, get_rules_engine
    from onboarding import get_interview_flow

    body = await request.json()

    ctx = TaxContext(
        filing_status=body.get('filingStatus', ''),
        date_of_birth=body.get('dob', ''),
        spouse_dob=body.get('spouseDob', ''),
        dependents=body.get('dependents', []),
        wages=safe_float(body.get('wages')),
        business_income=safe_float(body.get('businessIncome')),
        retirement_income=safe_float(body.get('retirementIncome')),
        state_of_residence=body.get('stateOfResidence', body.get('state', '')),
    )

    ctx.calculate_derived_fields()

    try:
        flow = get_interview_flow()
        current_step = body.get('currentStep', 1)

        sections = flow.get_visible_sections(ctx)
        skippable = flow.get_skippable_sections(ctx)
        progress = flow.calculate_progress(ctx, current_step)
        next_action = flow.get_next_action(ctx, current_step)

        return JSONResponse({
            'currentStep': current_step,
            'totalSteps': len(sections),
            'sections': [
                {
                    'id': s.id,
                    'name': s.name,
                    'visible': s.visible,
                    'completed': s.completed,
                    'skippable': s.id in skippable,
                }
                for s in sections
            ],
            'progress': {
                'percentage': progress.percentage,
                'completed_sections': progress.completed,
                'total_sections': progress.total,
            },
            'next_action': {
                'type': next_action.type,
                'section': next_action.section,
                'message': next_action.message,
            } if next_action else None,
        })

    except Exception as e:
        logger.error(f"Error getting interview state: {e}")
        return JSONResponse({
            'currentStep': body.get('currentStep', 1),
            'totalSteps': 7,
            'sections': [
                {'id': 'welcome', 'name': 'Welcome', 'visible': True, 'completed': False, 'skippable': False},
                {'id': 'filing_status', 'name': 'Filing Status', 'visible': True, 'completed': False, 'skippable': False},
                {'id': 'personal_info', 'name': 'Personal Info', 'visible': True, 'completed': False, 'skippable': False},
                {'id': 'income', 'name': 'Income', 'visible': True, 'completed': False, 'skippable': False},
                {'id': 'deductions', 'name': 'Deductions', 'visible': True, 'completed': False, 'skippable': True},
                {'id': 'credits', 'name': 'Credits', 'visible': True, 'completed': False, 'skippable': True},
                {'id': 'review', 'name': 'Review', 'visible': True, 'completed': False, 'skippable': False},
            ],
            'progress': {'percentage': 0, 'completed_sections': 0, 'total_sections': 7},
            'next_action': None,
        })


# ---------------------------------------------------------------------------
# HTMX Partials
# ---------------------------------------------------------------------------

@router.get("/api/partials/{partial_name}")
async def get_htmx_partial(partial_name: str, request: Request):
    """Render an htmx partial template."""
    allowed_partials = {
        'field-feedback',
        'optimization-tips',
        'validation-summary',
        'progress-bar',
        'section-header',
    }

    if partial_name not in allowed_partials:
        raise HTTPException(status_code=404, detail=f"Partial '{partial_name}' not found")

    params = dict(request.query_params)
    html = ""

    if partial_name == 'field-feedback':
        field_id = params.get('field', '')
        severity = params.get('severity', 'info')
        message = params.get('message', '')

        import html as html_module
        allowed_severities = {'info', 'warning', 'error', 'success'}
        severity = severity if severity in allowed_severities else 'info'
        severity_class = f"validation-{severity}"
        safe_message = html_module.escape(message)
        html = f'<div class="{severity_class}">{safe_message}</div>'

    elif partial_name == 'optimization-tips':
        html = '<div class="optimization-tip"><strong>Tip:</strong> Consider maximizing your retirement contributions.</div>'

    elif partial_name == 'validation-summary':
        errors = int(params.get('errors', 0))
        warnings = int(params.get('warnings', 0))

        if errors > 0:
            html = f'<div class="validation-error">{errors} error(s) need to be fixed</div>'
        elif warnings > 0:
            html = f'<div class="validation-warning">{warnings} warning(s) to review</div>'
        else:
            html = '<div class="validation-success">All fields validated successfully</div>'

    elif partial_name == 'progress-bar':
        percentage = int(params.get('percentage', 0))
        html = f'''
        <div class="progress-container">
            <div class="progress-bar" style="width: {percentage}%"></div>
            <span class="progress-text">{percentage}% complete</span>
        </div>
        '''

    return HTMLResponse(content=html)
