"""
Core Premium Reports API Routes

Unified report generation endpoints for all client types:
- Generate tiered advisory reports (Basic, Standard, Premium)
- Download reports in multiple formats
- Get pricing and tier information

Access control:
- direct_client: Full access to all tiers (pays platform pricing)
- firm_client: Full access to all tiers (CPA sets pricing)
- partner/staff: Can generate reports for their firm_clients

Pricing:
- Basic: Free
- Standard: $79 (platform pricing for direct_client)
- Premium: $199 (platform pricing for direct_client)
- CPA sets their own pricing for firm_clients
"""

import logging
import json
from datetime import datetime
from typing import Optional, List, Any
from enum import Enum
from uuid import uuid4
from pathlib import Path
import re
import sqlite3

from fastapi import APIRouter, HTTPException, Depends, Query, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from .auth_routes import get_current_user
from ..models.user import UserContext, UserType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["Core Premium Reports"])

_PRIMARY_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "tax_returns.db"
_LEGACY_DB_PATH = Path(__file__).resolve().parents[2] / "database" / "jorss_gbo.db"
_TAX_RETURNS_DB_PATH = _PRIMARY_DB_PATH

_PLATFORM_PRICING = {
    "basic": 0.0,
    "standard": 79.0,
    "premium": 199.0,
}

_CPA_DEFAULT_PRICING = {
    "basic": {"price": 0.0, "enabled": True},
    "standard": {"price": 99.0, "enabled": True},
    "premium": {"price": 299.0, "enabled": True},
}


def _candidate_db_paths() -> List[Path]:
    """Return prioritized DB candidates (configured path first, then fallbacks)."""
    seen = set()
    ordered = []
    for path in (_TAX_RETURNS_DB_PATH, _PRIMARY_DB_PATH, _LEGACY_DB_PATH):
        normalized = str(path)
        if normalized not in seen:
            ordered.append(path)
            seen.add(normalized)
    return ordered


# =============================================================================
# MODELS
# =============================================================================

class ReportTierRequest(str, Enum):
    BASIC = "basic"
    STANDARD = "standard"
    PREMIUM = "premium"


class ReportFormatRequest(str, Enum):
    HTML = "html"
    PDF = "pdf"
    JSON = "json"


class GenerateReportRequest(BaseModel):
    """Request to generate a premium report."""
    session_id: str = Field(..., description="Tax calculation session ID")
    tier: ReportTierRequest = Field(default=ReportTierRequest.BASIC, description="Report tier")
    format: ReportFormatRequest = Field(default=ReportFormatRequest.HTML, description="Output format")


class ReportResponse(BaseModel):
    """Response containing generated report."""
    report_id: str
    session_id: str
    tier: str
    format: str
    generated_at: str
    taxpayer_name: str
    tax_year: int
    section_count: int
    action_item_count: int
    html_content: Optional[str] = None
    json_data: Optional[dict] = None


class TierInfo(BaseModel):
    """Information about a report tier."""
    tier: str
    price: float
    label: str
    description: str
    section_count: int
    sections: List[str]


class ReportHistoryItem(BaseModel):
    """Persisted premium report metadata for a session."""
    report_id: str
    session_id: str
    tier: str
    format: str
    generated_at: str
    taxpayer_name: str
    tax_year: int
    section_count: int
    action_item_count: int


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_premium_generator():
    """Get the premium report generator singleton."""
    from export.premium_report_generator import PremiumReportGenerator
    return PremiumReportGenerator()


def _validate_sql_identifier(name: str) -> str:
    """Validate a SQL identifier (table/column name) to prevent injection."""
    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return name


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    """Get column names for a SQLite table."""
    _validate_sql_identifier(table_name)
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {str(row[1]) for row in cursor.fetchall()}


def _parse_json_object(value: Optional[str]) -> Optional[dict]:
    """Safely parse JSON objects from text columns."""
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return None
    payload = value.strip()
    if not payload:
        return None
    try:
        parsed = json.loads(payload)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _normalize_pricing_map(value: dict) -> Optional[dict]:
    """
    Normalize arbitrary pricing payload into tier-> {price, enabled}.

    Supports values like:
    - {"standard": 89}
    - {"standard": {"price": 89, "enabled": true}}
    """
    normalized = {}
    for tier in _PLATFORM_PRICING:
        tier_value = value.get(tier)
        if tier_value is None:
            continue

        enabled = True
        raw_price = tier_value
        if isinstance(tier_value, dict):
            raw_price = tier_value.get("price")
            enabled = bool(tier_value.get("enabled", True))

        try:
            price = float(raw_price)
        except (TypeError, ValueError):
            continue

        normalized[tier] = {"price": max(price, 0.0), "enabled": enabled}

    return normalized or None


def _extract_pricing_from_settings(settings: Optional[dict]) -> Optional[dict]:
    """Search known settings shapes for report pricing."""
    if not isinstance(settings, dict):
        return None

    queue = [settings]
    visited = set()
    candidate_keys = ("report_pricing", "pricing", "reports", "premium_reports", "premium_report_pricing")

    while queue:
        current = queue.pop(0)
        marker = id(current)
        if marker in visited:
            continue
        visited.add(marker)

        normalized = _normalize_pricing_map(current)
        if normalized:
            return normalized

        for key in candidate_keys:
            nested = current.get(key)
            if isinstance(nested, dict):
                queue.append(nested)

    return None


def _get_session_ownership(session_id: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Resolve ownership metadata for a session.

    Returns: (owner_user_id, owner_firm_id, owner_preparer_id)
    """
    # Primary source: session persistence metadata
    try:
        from database.session_persistence import get_session_persistence

        session_record = get_session_persistence().load_session(session_id)
        if session_record:
            session_data = session_record.data or {}
            session_metadata = session_record.metadata or {}
            owner_user_id = (
                session_data.get("user_id")
                or session_data.get("client_id")
                or session_metadata.get("user_id")
                or session_metadata.get("client_id")
            )
            owner_firm_id = (
                session_data.get("firm_id")
                or session_metadata.get("firm_id")
                or (session_record.tenant_id if session_record.tenant_id != "default" else None)
            )
            owner_preparer_id = (
                session_data.get("preparer_id")
                or session_metadata.get("preparer_id")
            )
            return owner_user_id, owner_firm_id, owner_preparer_id
    except Exception as exc:
        logger.debug(f"Session ownership lookup failed for {session_id}: {exc}")

    # Fallback: tax_returns table (schema varies by deployment)
    try:
        for db_path in _candidate_db_paths():
            if not db_path.exists():
                continue

            with sqlite3.connect(db_path) as conn:
                columns = _table_columns(conn, "tax_returns")
                if "session_id" not in columns:
                    continue

                select_parts = []
                owner_user_col = None
                owner_firm_col = None
                owner_preparer_col = None

                for candidate in ("client_id", "user_id", "taxpayer_id"):
                    if candidate in columns:
                        owner_user_col = candidate
                        break
                if owner_user_col:
                    select_parts.append(owner_user_col)

                if "firm_id" in columns:
                    owner_firm_col = "firm_id"
                    select_parts.append(owner_firm_col)
                elif "tenant_id" in columns:
                    owner_firm_col = "tenant_id"
                    select_parts.append(owner_firm_col)

                if "preparer_id" in columns:
                    owner_preparer_col = "preparer_id"
                    select_parts.append(owner_preparer_col)

                if not select_parts:
                    continue

                query = f"SELECT {', '.join(select_parts)} FROM tax_returns WHERE session_id = ?"
                cursor = conn.cursor()
                cursor.execute(query, (session_id,))
                row = cursor.fetchone()
                if not row:
                    continue

                values = {column: row[idx] for idx, column in enumerate(select_parts)}
                owner_user_id = str(values.get(owner_user_col)) if owner_user_col and values.get(owner_user_col) else None
                owner_firm_raw = values.get(owner_firm_col) if owner_firm_col else None
                owner_firm_id = str(owner_firm_raw) if owner_firm_raw and owner_firm_raw != "default" else None
                owner_preparer_id = (
                    str(values.get(owner_preparer_col))
                    if owner_preparer_col and values.get(owner_preparer_col)
                    else None
                )

                return owner_user_id, owner_firm_id, owner_preparer_id
    except Exception as exc:
        logger.warning(f"Fallback session ownership lookup failed for {session_id}: {exc}")

    return None, None, None


def _resolve_client_firm_id(user: UserContext) -> Optional[str]:
    """Resolve firm ID for CPA clients when not present in JWT context."""
    if user.firm_id:
        return user.firm_id

    try:
        for db_path in _candidate_db_paths():
            if not db_path.exists():
                continue

            with sqlite3.connect(db_path) as conn:
                users_columns = _table_columns(conn, "users")
                clients_columns = _table_columns(conn, "clients")
                cursor = conn.cursor()

                # If client user is also in users table with a firm, use it directly.
                if {"user_id", "firm_id"}.issubset(users_columns):
                    cursor.execute(
                        "SELECT firm_id FROM users WHERE user_id = ? LIMIT 1",
                        (user.user_id,),
                    )
                    row = cursor.fetchone()
                    if row and row[0]:
                        return str(row[0])

                # If clients table stores firm_id, use it.
                if {"client_id", "firm_id"}.issubset(clients_columns):
                    cursor.execute(
                        "SELECT firm_id FROM clients WHERE client_id = ? LIMIT 1",
                        (user.user_id,),
                    )
                    row = cursor.fetchone()
                    if row and row[0]:
                        return str(row[0])

                # If clients table stores preparer_id, map preparer -> firm via users.
                if (
                    {"client_id", "preparer_id"}.issubset(clients_columns)
                    and {"user_id", "firm_id"}.issubset(users_columns)
                ):
                    cursor.execute(
                        """
                        SELECT u.firm_id
                        FROM clients c
                        JOIN users u ON u.user_id = c.preparer_id
                        WHERE c.client_id = ?
                        LIMIT 1
                        """,
                        (user.user_id,),
                    )
                    row = cursor.fetchone()
                    if row and row[0]:
                        return str(row[0])

                # Last fallback: assigned CPA -> users.firm_id
                if user.assigned_cpa_id and {"user_id", "firm_id"}.issubset(users_columns):
                    cursor.execute(
                        "SELECT firm_id FROM users WHERE user_id = ? LIMIT 1",
                        (user.assigned_cpa_id,),
                    )
                    row = cursor.fetchone()
                    if row and row[0]:
                        return str(row[0])
    except Exception as exc:
        logger.warning(f"Client firm lookup failed for user {user.user_id}: {exc}")

    return None


def _client_belongs_to_firm(client_id: str, firm_id: str) -> Optional[bool]:
    """
    Verify whether a client belongs to the CPA's firm.

    Returns:
    - True/False when verifiable from DB
    - None when schema/data is insufficient to verify
    """
    try:
        for db_path in _candidate_db_paths():
            if not db_path.exists():
                continue

            with sqlite3.connect(db_path) as conn:
                users_columns = _table_columns(conn, "users")
                clients_columns = _table_columns(conn, "clients")
                cursor = conn.cursor()

                # Unified users table path
                if {"user_id", "firm_id"}.issubset(users_columns):
                    cursor.execute(
                        "SELECT firm_id FROM users WHERE user_id = ? LIMIT 1",
                        (client_id,),
                    )
                    row = cursor.fetchone()
                    if row is not None:
                        return bool(row[0] and str(row[0]) == firm_id)

                # Legacy clients table path
                if {"client_id", "firm_id"}.issubset(clients_columns):
                    cursor.execute(
                        "SELECT firm_id FROM clients WHERE client_id = ? LIMIT 1",
                        (client_id,),
                    )
                    row = cursor.fetchone()
                    if row is not None:
                        return bool(row[0] and str(row[0]) == firm_id)

                # Legacy clients->preparer relation path
                if (
                    {"client_id", "preparer_id"}.issubset(clients_columns)
                    and {"user_id", "firm_id"}.issubset(users_columns)
                ):
                    cursor.execute(
                        """
                        SELECT u.firm_id
                        FROM clients c
                        JOIN users u ON u.user_id = c.preparer_id
                        WHERE c.client_id = ?
                        LIMIT 1
                        """,
                        (client_id,),
                    )
                    row = cursor.fetchone()
                    if row is not None:
                        return bool(row[0] and str(row[0]) == firm_id)
    except Exception as exc:
        logger.warning(f"Client-to-firm verification failed for {client_id}: {exc}")

    return None


def _get_firm_report_pricing(firm_id: Optional[str]) -> Optional[dict]:
    """Fetch custom report pricing from firm settings, if configured."""
    if not firm_id:
        return None

    try:
        for db_path in _candidate_db_paths():
            if not db_path.exists():
                continue

            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()

                # Source 1: firms.settings JSON
                firms_columns = _table_columns(conn, "firms")
                if {"firm_id", "settings"}.issubset(firms_columns):
                    cursor.execute(
                        "SELECT settings FROM firms WHERE firm_id = ? LIMIT 1",
                        (firm_id,),
                    )
                    row = cursor.fetchone()
                    if row and row[0]:
                        settings = _parse_json_object(row[0])
                        pricing = _extract_pricing_from_settings(settings)
                        if pricing:
                            return pricing

                # Source 2: firm_settings JSON blobs
                firm_settings_columns = _table_columns(conn, "firm_settings")
                selectable_columns = [
                    column for column in ("integrations", "notification_preferences")
                    if column in firm_settings_columns
                ]
                if "firm_id" in firm_settings_columns and selectable_columns:
                    query = (
                        f"SELECT {', '.join(selectable_columns)} "
                        "FROM firm_settings WHERE firm_id = ? LIMIT 1"
                    )
                    cursor.execute(query, (firm_id,))
                    row = cursor.fetchone()
                    if row:
                        for cell in row:
                            settings = _parse_json_object(cell)
                            pricing = _extract_pricing_from_settings(settings)
                            if pricing:
                                return pricing
    except Exception as exc:
        logger.warning(f"Firm pricing lookup failed for {firm_id}: {exc}")

    return None


def _is_user_or_team_allowed(
    user: UserContext,
    owner_user_id: Optional[str],
    owner_firm_id: Optional[str] = None,
    owner_preparer_id: Optional[str] = None,
) -> bool:
    """Evaluate report access rules for a user against ownership metadata."""
    if user.user_type == UserType.PLATFORM_ADMIN:
        return True

    if user.user_type in {UserType.CONSUMER, UserType.CPA_CLIENT}:
        return bool(owner_user_id and owner_user_id == user.user_id)

    if user.user_type == UserType.CPA_TEAM:
        if owner_firm_id and user.firm_id and owner_firm_id == user.firm_id:
            return True
        if owner_preparer_id and owner_preparer_id == user.user_id:
            return True
        if owner_user_id and owner_user_id == user.user_id:
            return True
        return False

    return False


def check_report_access(user: UserContext, session_id: str) -> bool:
    """
    Check if user has access to generate reports for this session.

    Access rules:
    - direct_client: Can only access their own sessions
    - firm_client: Can only access their own sessions
    - partner/staff: Can access sessions for clients in their firm
    - platform_admin: Can access all sessions
    """
    # Platform admins have full access
    if user.user_type == UserType.PLATFORM_ADMIN:
        return True

    owner_user_id, owner_firm_id, owner_preparer_id = _get_session_ownership(session_id)
    if _is_user_or_team_allowed(user, owner_user_id, owner_firm_id, owner_preparer_id):
        return True

    logger.warning(
        "Report access denied: unable to verify ownership "
        f"(user={user.user_id}, user_type={user.user_type}, session={session_id})"
    )
    return False


def get_pricing_for_user(user: UserContext, tier: str) -> dict:
    """
    Get pricing information for a user.

    - direct_client: Platform pricing
    - firm_client: CPA-set pricing (retrieved from firm settings)
    - partner/staff: Free (generating for clients)
    """
    if user.user_type in [UserType.CPA_TEAM]:
        # CPAs generate for free (they charge clients directly)
        return {"price": 0, "currency": "USD", "source": "cpa_included"}

    if user.user_type == UserType.CPA_CLIENT:
        firm_id = _resolve_client_firm_id(user)
        firm_pricing = _get_firm_report_pricing(firm_id)
        if firm_pricing and tier in firm_pricing:
            tier_pricing = firm_pricing[tier]
            if tier_pricing.get("enabled", True):
                return {
                    "price": tier_pricing["price"],
                    "currency": "USD",
                    "source": "firm_pricing",
                    "firm_id": firm_id,
                }

        # Fallback to platform pricing if firm has no custom tier config.
        return {
            "price": _PLATFORM_PRICING.get(tier, 0.0),
            "currency": "USD",
            "source": "firm_pricing_fallback" if firm_id else "platform",
            "firm_id": firm_id,
        }

    # direct_client or consumer
    return {"price": _PLATFORM_PRICING.get(tier, 0.0), "currency": "USD", "source": "platform"}


def _resolve_tenant_scope(user: UserContext) -> str:
    """Resolve tenant scope for persistence writes."""
    return str(user.firm_id or "default")


def _persist_generated_report(report: Any, user: UserContext) -> None:
    """Persist generated report metadata to durable session storage."""
    try:
        from database.session_persistence import get_session_persistence
    except Exception as exc:
        logger.warning(f"Session persistence unavailable for report storage: {exc}")
        return

    payload = {
        "report_id": report.report_id,
        "session_id": report.session_id,
        "tier": report.tier.value,
        "format": report.format.value,
        "generated_at": report.generated_at,
        "taxpayer_name": report.taxpayer_name,
        "tax_year": report.tax_year,
        "section_count": len(getattr(report, "sections", []) or []),
        "action_item_count": len(getattr(report, "action_items", []) or []),
        "metadata": report.metadata or {},
        "action_items": [
            item.to_dict() if hasattr(item, "to_dict") else item
            for item in (getattr(report, "action_items", []) or [])
        ],
    }

    if report.format.value == "html" and getattr(report, "html_content", ""):
        payload["html_content"] = report.html_content
    elif report.format.value == "json" and getattr(report, "json_data", None):
        payload["json_data"] = report.json_data
    elif report.format.value == "pdf" and getattr(report, "pdf_bytes", b""):
        payload["pdf_size_bytes"] = len(report.pdf_bytes)

    tenant_id = _resolve_tenant_scope(user)
    persistence = get_session_persistence()
    persistence.save_document_result(
        document_id=report.report_id,
        session_id=report.session_id,
        tenant_id=tenant_id,
        document_type=f"premium_report:{report.tier.value}:{report.format.value}",
        status="completed",
        result=payload,
    )


def _list_persisted_reports(session_id: str, user: UserContext) -> List[ReportHistoryItem]:
    """List persisted report metadata for a session."""
    try:
        from database.session_persistence import get_session_persistence
    except Exception as exc:
        logger.warning(f"Session persistence unavailable for report history: {exc}")
        return []

    persistence = get_session_persistence()
    tenant_id = _resolve_tenant_scope(user)
    records = persistence.list_session_documents(session_id=session_id, tenant_id=tenant_id)

    history: List[ReportHistoryItem] = []
    for record in records:
        doc_type = str(record.document_type or "")
        if not doc_type.startswith("premium_report:"):
            continue

        result = record.result or {}
        try:
            history.append(
                ReportHistoryItem(
                    report_id=str(result.get("report_id") or record.document_id),
                    session_id=str(result.get("session_id") or record.session_id),
                    tier=str(result.get("tier") or "unknown"),
                    format=str(result.get("format") or "unknown"),
                    generated_at=str(result.get("generated_at") or record.created_at),
                    taxpayer_name=str(result.get("taxpayer_name") or "Taxpayer"),
                    tax_year=int(result.get("tax_year") or 2025),
                    section_count=int(result.get("section_count") or 0),
                    action_item_count=int(result.get("action_item_count") or 0),
                )
            )
        except Exception:
            continue

    history.sort(key=lambda item: item.generated_at, reverse=True)
    return history


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/generate", response_model=ReportResponse)
async def generate_report(
    request: GenerateReportRequest,
    user: UserContext = Depends(get_current_user),
):
    """
    Generate a tiered tax advisory report.

    Tiers:
    - **basic** (free): Tax summary + computation statement
    - **standard** ($79): + Advisory sections + scenarios
    - **premium** ($199): + Full appendices + action items + PDF

    The same intelligence is provided to both direct_client and firm_client.
    CPA partners can generate reports for their clients with their own pricing.

    Returns:
        Generated report with HTML content (or JSON for format=json)
    """
    # Check access
    if not check_report_access(user, request.session_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this session",
        )

    # Get pricing (for logging/billing)
    pricing = get_pricing_for_user(user, request.tier.value)
    logger.info(
        f"Report generation: user={user.user_id}, session={request.session_id}, "
        f"tier={request.tier.value}, price=${pricing['price']}"
    )

    try:
        from export.premium_report_generator import (
            PremiumReportGenerator,
            ReportTier,
            ReportFormat,
        )

        generator = PremiumReportGenerator()
        report = generator.generate(
            session_id=request.session_id,
            tier=ReportTier(request.tier.value),
            format=ReportFormat(request.format.value),
        )

        # Check for errors
        if report.metadata.get("error"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=report.metadata["error"],
            )

        _persist_generated_report(report, user)

        response = ReportResponse(
            report_id=report.report_id,
            session_id=report.session_id,
            tier=report.tier.value,
            format=report.format.value,
            generated_at=report.generated_at,
            taxpayer_name=report.taxpayer_name,
            tax_year=report.tax_year,
            section_count=len(report.sections),
            action_item_count=len(report.action_items),
        )

        if request.format == ReportFormatRequest.HTML:
            response.html_content = report.html_content
        elif request.format == ReportFormatRequest.JSON:
            response.json_data = report.json_data

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report generation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Report generation failed. Please try again later.",
        )


@router.get("/download/{session_id}")
async def download_report(
    session_id: str,
    tier: ReportTierRequest = Query(default=ReportTierRequest.PREMIUM),
    format: ReportFormatRequest = Query(default=ReportFormatRequest.PDF),
    user: UserContext = Depends(get_current_user),
):
    """
    Download a generated report as a file.

    Returns:
        - PDF: application/pdf
        - HTML: text/html
        - JSON: application/json
    """
    if not check_report_access(user, session_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this session",
        )

    try:
        from export.premium_report_generator import (
            PremiumReportGenerator,
            ReportTier,
            ReportFormat,
        )

        generator = PremiumReportGenerator()
        report = generator.generate(
            session_id=session_id,
            tier=ReportTier(tier.value),
            format=ReportFormat(format.value),
        )

        if report.metadata.get("error"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=report.metadata["error"],
            )

        _persist_generated_report(report, user)

        timestamp = datetime.now().strftime("%Y%m%d")
        safe_name = report.taxpayer_name.replace(" ", "_")

        if format == ReportFormatRequest.PDF:
            return Response(
                content=report.pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="{safe_name}_TaxReport_{timestamp}.pdf"'
                },
            )
        elif format == ReportFormatRequest.HTML:
            return Response(
                content=report.html_content,
                media_type="text/html",
                headers={
                    "Content-Disposition": f'attachment; filename="{safe_name}_TaxReport_{timestamp}.html"'
                },
            )
        else:  # JSON
            import json
            return Response(
                content=json.dumps(report.json_data, indent=2),
                media_type="application/json",
                headers={
                    "Content-Disposition": f'attachment; filename="{safe_name}_TaxReport_{timestamp}.json"'
                },
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report download error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Report download failed. Please try again later.",
        )


@router.get("/tiers", response_model=List[TierInfo])
async def get_report_tiers(
    user: UserContext = Depends(get_current_user),
):
    """
    Get available report tiers and pricing.

    Returns pricing based on user type:
    - direct_client: Platform pricing ($0/$79/$199)
    - firm_client: CPA's custom pricing
    - partner/staff: Free (CPA charges clients directly)
    """
    from export.premium_report_generator import (
        get_tier_pricing,
        get_tier_sections,
        ReportTier,
    )

    pricing_info = get_tier_pricing()
    tiers = []

    for tier_key, info in pricing_info.items():
        # Adjust pricing based on user type
        user_pricing = get_pricing_for_user(user, tier_key)

        tiers.append(TierInfo(
            tier=tier_key,
            price=user_pricing["price"],
            label=info["label"],
            description=info["description"],
            section_count=info["section_count"],
            sections=get_tier_sections(tier_key),
        ))

    return tiers


@router.get("/sections/{tier}")
async def get_tier_sections_endpoint(
    tier: ReportTierRequest,
    user: UserContext = Depends(get_current_user),
):
    """
    Get list of sections included in a specific tier.

    Returns section IDs and metadata for the requested tier.
    """
    from export.premium_report_generator import (
        get_tier_sections,
        SECTION_METADATA,
        ReportSection,
    )

    section_ids = get_tier_sections(tier.value)
    sections = []

    for section_id in section_ids:
        try:
            section_enum = ReportSection(section_id)
            meta = SECTION_METADATA.get(section_enum, {})
            sections.append({
                "section_id": section_id,
                "title": meta.get("title", section_id),
                "description": meta.get("description", ""),
                "order": meta.get("order", 50),
            })
        except ValueError:
            sections.append({
                "section_id": section_id,
                "title": section_id,
                "description": "",
                "order": 50,
            })

    # Sort by order
    sections.sort(key=lambda s: s["order"])

    return {
        "tier": tier.value,
        "section_count": len(sections),
        "sections": sections,
    }


@router.get("/preview/{session_id}")
async def preview_report(
    session_id: str,
    user: UserContext = Depends(get_current_user),
):
    """
    Get a preview of what would be included in each tier.

    Returns a summary without generating the full report.
    Useful for showing users what they get with each tier before purchase.
    """
    if not check_report_access(user, session_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this session",
        )

    from export.premium_report_generator import (
        get_tier_pricing,
        get_tier_sections,
    )

    pricing = get_tier_pricing()
    previews = {}

    for tier_key, info in pricing.items():
        user_pricing = get_pricing_for_user(user, tier_key)
        sections = get_tier_sections(tier_key)

        previews[tier_key] = {
            "price": user_pricing["price"],
            "label": info["label"],
            "description": info["description"],
            "section_count": len(sections),
            "includes": sections,
            "highlights": _get_tier_highlights(tier_key),
        }

    return {
        "session_id": session_id,
        "tiers": previews,
        "recommended": "premium",  # Could be dynamic based on user's situation
    }


@router.get("/history/{session_id}", response_model=List[ReportHistoryItem])
async def get_report_history(
    session_id: str,
    user: UserContext = Depends(get_current_user),
):
    """List persisted premium reports for a session."""
    if not check_report_access(user, session_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this session",
        )

    return _list_persisted_reports(session_id, user)


def _get_tier_highlights(tier: str) -> List[str]:
    """Get marketing highlights for a tier."""
    highlights = {
        "basic": [
            "Tax calculation summary",
            "Computation transparency",
            "Advisory baseline metrics",
        ],
        "standard": [
            "Everything in Basic",
            "Credit eligibility analysis",
            "Deduction optimization",
            "Filing status comparison",
            "What-if scenario analysis",
            "Retirement contribution strategy",
        ],
        "premium": [
            "Everything in Standard",
            "Prioritized action items",
            "Multi-year tax projection",
            "Entity structure analysis",
            "Investment tax planning",
            "Full IRC citations",
            "Downloadable PDF report",
            "Detailed calculation appendix",
        ],
    }
    return highlights.get(tier, [])


# =============================================================================
# CPA-SPECIFIC ENDPOINTS
# =============================================================================

@router.post("/cpa/generate-for-client")
async def generate_report_for_client(
    client_id: str = Query(..., description="Client user ID"),
    session_id: str = Query(..., description="Tax session ID"),
    tier: ReportTierRequest = Query(default=ReportTierRequest.PREMIUM),
    format: ReportFormatRequest = Query(default=ReportFormatRequest.HTML),
    user: UserContext = Depends(get_current_user),
):
    """
    CPA endpoint to generate a report for one of their clients.

    Only accessible by partner/staff users.
    The CPA can then deliver this to their client with their own pricing.
    """
    # Verify user is CPA team member
    if user.user_type != UserType.CPA_TEAM:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only for CPA team members",
        )

    if not user.firm_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CPA team member must be associated with a firm",
        )

    if not check_report_access(user, session_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this session",
        )

    owner_user_id, owner_firm_id, _ = _get_session_ownership(session_id)

    # Guard against accidental cross-client delivery.
    if owner_user_id and owner_user_id != client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Provided client_id does not match the owner of this tax session. "
                "Use the client's actual session_id."
            ),
        )

    # Enforce same-firm ownership when firm metadata is available.
    if owner_firm_id and owner_firm_id != user.firm_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This session belongs to a different firm",
        )

    # Additional defense using client roster metadata when available.
    client_firm_match = _client_belongs_to_firm(client_id, user.firm_id)
    if client_firm_match is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The specified client does not belong to your firm",
        )
    if client_firm_match is None and not owner_user_id:
        logger.warning(
            "Client ownership metadata unavailable; allowing CPA report generation "
            f"based on session access only (firm={user.firm_id}, client={client_id}, session={session_id})"
        )

    try:
        from export.premium_report_generator import (
            PremiumReportGenerator,
            ReportTier,
            ReportFormat,
        )

        generator = PremiumReportGenerator()
        report = generator.generate(
            session_id=session_id,
            tier=ReportTier(tier.value),
            format=ReportFormat(format.value),
        )

        if report.metadata.get("error"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=report.metadata["error"],
            )

        return {
            "report_id": report.report_id,
            "client_id": client_id,
            "session_id": session_id,
            "tier": report.tier.value,
            "generated_at": report.generated_at,
            "taxpayer_name": report.taxpayer_name,
            "section_count": len(report.sections),
            "action_items": [item.to_dict() for item in report.action_items],
            "html_content": report.html_content if format == ReportFormatRequest.HTML else None,
            "message": "Report generated. You can now deliver this to your client with your pricing.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CPA report generation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Report generation failed. Please try again later.",
        )


@router.get("/cpa/pricing")
async def get_cpa_pricing_settings(
    user: UserContext = Depends(get_current_user),
):
    """
    Get CPA firm's custom pricing settings for reports.

    Only accessible by partner/staff users.
    """
    if user.user_type != UserType.CPA_TEAM:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only for CPA team members",
        )

    if not user.firm_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CPA team member must be associated with a firm",
        )

    firm_pricing = _get_firm_report_pricing(user.firm_id)
    pricing = firm_pricing or _CPA_DEFAULT_PRICING
    source = "firm_settings" if firm_pricing else "default_profile"

    return {
        "firm_id": user.firm_id,
        "pricing": pricing,
        "source": source,
        "notes": "Set custom report pricing in firm settings to override defaults",
    }
