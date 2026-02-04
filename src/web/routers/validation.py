"""
Validation Routes - Field and Form Validation

SPEC-005: Extracted from app.py for modularity.

Routes:
- POST /api/validate/fields - Validate multiple fields
- POST /api/validate/field/{field_name} - Validate single field
- POST /api/suggestions - Get field suggestions/autocomplete
"""

import json
import re
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import logging

from web.validation_helpers import (
    validate_ssn as _canonical_validate_ssn,
    validate_ein as _canonical_validate_ein,
    validate_state_code,
    VALID_STATE_CODES,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Validation"])


# =============================================================================
# VALIDATION HELPERS — delegating to canonical web.validation_helpers
# =============================================================================

def validate_ssn(ssn: str) -> tuple[bool, str]:
    """Validate SSN format. Delegates to validation_helpers."""
    if not ssn:
        return False, "SSN is required"
    is_valid, error = _canonical_validate_ssn(ssn)
    return (True, "Valid SSN") if is_valid else (False, error or "Invalid SSN format")


def validate_ein(ein: str) -> tuple[bool, str]:
    """Validate EIN format. Delegates to validation_helpers."""
    if not ein:
        return False, "EIN is required"
    is_valid, error = _canonical_validate_ein(ein)
    return (True, "Valid EIN") if is_valid else (False, error or "Invalid EIN format")


def validate_zip_code(zip_code: str) -> tuple[bool, str]:
    """Validate ZIP code format."""
    if not zip_code:
        return False, "ZIP code is required"

    # 5-digit or 5+4 format
    pattern = r'^\d{5}(-\d{4})?$'
    if re.match(pattern, zip_code):
        return True, "Valid ZIP code"
    return False, "Invalid ZIP code format"


def validate_phone(phone: str) -> tuple[bool, str]:
    """Validate phone number format."""
    if not phone:
        return True, "Phone is optional"  # Optional field

    # Remove common formatting
    clean = re.sub(r'[\s\-\(\)\.]', '', phone)

    if not clean.isdigit():
        return False, "Phone must contain only digits"

    if len(clean) == 10:
        return True, "Valid phone number"
    elif len(clean) == 11 and clean.startswith("1"):
        return True, "Valid phone number"
    else:
        return False, "Phone must be 10 digits"


def validate_email(email: str) -> tuple[bool, str]:
    """Validate email format."""
    if not email:
        return True, "Email is optional"  # Optional field

    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if re.match(pattern, email):
        return True, "Valid email"
    return False, "Invalid email format"


def validate_date(date_str: str) -> tuple[bool, str]:
    """Validate date format."""
    if not date_str:
        return False, "Date is required"

    # Try common formats
    from datetime import datetime
    formats = ["%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"]

    for fmt in formats:
        try:
            datetime.strptime(date_str, fmt)
            return True, "Valid date"
        except ValueError:
            continue

    return False, "Invalid date format (use YYYY-MM-DD or MM/DD/YYYY)"


def validate_amount(amount: Any, field_name: str = "Amount") -> tuple[bool, str]:
    """Validate monetary amount."""
    if amount is None:
        return True, f"{field_name} is optional"

    try:
        value = float(amount)
        if value < 0:
            return False, f"{field_name} cannot be negative"
        if value > 999_999_999:
            return False, f"{field_name} exceeds maximum value"
        return True, f"Valid {field_name.lower()}"
    except (ValueError, TypeError):
        return False, f"{field_name} must be a number"


# Field validators registry
FIELD_VALIDATORS = {
    "ssn": validate_ssn,
    "social_security_number": validate_ssn,
    "ein": validate_ein,
    "employer_ein": validate_ein,
    "state": lambda v: (validate_state_code(v), "Valid state" if validate_state_code(v) else "Invalid state code"),
    "state_code": lambda v: (validate_state_code(v), "Valid state" if validate_state_code(v) else "Invalid state code"),
    "zip": validate_zip_code,
    "zip_code": validate_zip_code,
    "phone": validate_phone,
    "phone_number": validate_phone,
    "email": validate_email,
    "date_of_birth": validate_date,
    "dob": validate_date,
}


# =============================================================================
# VALIDATION ROUTES
# =============================================================================

@router.post("/validate/fields")
async def validate_fields(request: Request):
    """
    Validate multiple fields at once.

    Request body:
    {
        "fields": {
            "ssn": "123-45-6789",
            "email": "test@example.com",
            "wages": 50000
        }
    }
    """
    try:
        body = await request.json()
        fields = body.get("fields", body)  # Support both nested and flat

        results = {}
        all_valid = True

        for field_name, value in fields.items():
            # Check for specific validator
            if field_name in FIELD_VALIDATORS:
                valid, message = FIELD_VALIDATORS[field_name](value)
            elif field_name.endswith("_amount") or field_name in ("wages", "income", "tax"):
                valid, message = validate_amount(value, field_name.replace("_", " ").title())
            elif field_name.endswith("_date"):
                valid, message = validate_date(str(value) if value else "")
            else:
                # Default: just check if present for required fields
                valid = value is not None and str(value).strip() != ""
                message = "Valid" if valid else "Field is required"

            results[field_name] = {
                "valid": valid,
                "message": message,
                "value": value,
            }

            if not valid:
                all_valid = False

        return JSONResponse({
            "status": "success",
            "all_valid": all_valid,
            "fields": results,
            "error_count": sum(1 for r in results.values() if not r["valid"]),
        })

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "error": f"Invalid request: {e}"}
        )
    except TypeError as e:
        logger.exception(f"Field validation type error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": "Internal validation error"}
        )


@router.post("/validate/field/{field_name}")
async def validate_single_field(field_name: str, request: Request):
    """Validate a single field."""
    try:
        body = await request.json()
        value = body.get("value", body.get(field_name))

        # Check for specific validator
        if field_name in FIELD_VALIDATORS:
            valid, message = FIELD_VALIDATORS[field_name](value)
        elif field_name.endswith("_amount") or field_name in ("wages", "income", "tax"):
            valid, message = validate_amount(value, field_name.replace("_", " ").title())
        elif field_name.endswith("_date"):
            valid, message = validate_date(str(value) if value else "")
        else:
            valid = value is not None and str(value).strip() != ""
            message = "Valid" if valid else "Field is required"

        return JSONResponse({
            "status": "success",
            "field": field_name,
            "valid": valid,
            "message": message,
            "value": value,
        })

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "error": f"Invalid request: {e}"}
        )
    except TypeError as e:
        logger.exception(f"Single field validation type error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": "Internal validation error"}
        )


@router.post("/suggestions")
async def get_suggestions(request: Request):
    """
    Get suggestions/autocomplete for a field.

    Request body:
    {
        "field": "state",
        "query": "cal"
    }
    """
    try:
        body = await request.json()
        field = body.get("field", "")
        query = body.get("query", "").lower()

        suggestions = []

        if field in ("state", "state_code"):
            states = {
                "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
                "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
                "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
                "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
                "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
                "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
                "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
                "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
                "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
                "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
                "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
                "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
                "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
            }

            for code, name in states.items():
                if query in code.lower() or query in name.lower():
                    suggestions.append({"value": code, "label": f"{name} ({code})"})

        elif field == "filing_status":
            statuses = [
                {"value": "single", "label": "Single"},
                {"value": "married_filing_jointly", "label": "Married Filing Jointly"},
                {"value": "married_filing_separately", "label": "Married Filing Separately"},
                {"value": "head_of_household", "label": "Head of Household"},
                {"value": "qualifying_widow", "label": "Qualifying Surviving Spouse"},
            ]
            suggestions = [s for s in statuses if query in s["value"] or query in s["label"].lower()]

        elif field == "document_type":
            doc_types = [
                {"value": "W-2", "label": "W-2 (Wage Statement)"},
                {"value": "1099-INT", "label": "1099-INT (Interest Income)"},
                {"value": "1099-DIV", "label": "1099-DIV (Dividends)"},
                {"value": "1099-MISC", "label": "1099-MISC (Miscellaneous)"},
                {"value": "1099-NEC", "label": "1099-NEC (Nonemployee Compensation)"},
                {"value": "1099-R", "label": "1099-R (Retirement)"},
                {"value": "1098", "label": "1098 (Mortgage Interest)"},
                {"value": "1098-T", "label": "1098-T (Tuition)"},
            ]
            suggestions = [d for d in doc_types if query in d["value"].lower() or query in d["label"].lower()]

        return JSONResponse({
            "status": "success",
            "field": field,
            "query": query,
            "suggestions": suggestions[:10],  # Limit to 10
        })

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "error": f"Invalid request: {e}"}
        )
    except TypeError as e:
        logger.exception(f"Suggestions type error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": "Internal suggestion error"}
        )
