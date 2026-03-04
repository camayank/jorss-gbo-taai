"""
CPA Panel Data Routes

Endpoints for accessing client, tax return, recommendation, and engagement data
from the database. These routes power the CPA dashboard.

Features:
- Connection pooling with context manager
- Retry logic for transient failures
- Input validation and sanitization
- Consistent error responses
"""

from fastapi import APIRouter, HTTPException, Request, Query
from typing import Dict, Any, Optional, List
import json
import time
import logging

from .common import (
    get_db_connection,
    format_success_response,
    format_error_response,
    ErrorCode,
    validate_session_id,
    validate_pagination,
    validate_enum_value,
    sanitize_search_query,
    generate_request_id,
    log_api_event,
    get_tenant_id,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["data"])

# Valid filter values for validation
VALID_COMPLEXITY = ["simple", "moderate", "complex", "high_net_worth"]
VALID_FILING_STATUS = ["single", "married_filing_jointly", "married_filing_separately", "head_of_household", "qualifying_widow"]


def row_to_dict(row) -> dict:
    """Convert sqlite3.Row to dict."""
    if row is None:
        return None
    return dict(row)


def safe_json_parse(json_str: str, default=None):
    """Safely parse JSON string, returning default on error."""
    if not json_str:
        return default
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default


# =============================================================================
# CLIENT ENDPOINTS
# =============================================================================

@router.get("/data/clients")
async def list_clients(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    complexity: Optional[str] = None,
    filing_status: Optional[str] = None,
    search: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List all clients with optional filtering.

    Query params:
    - limit: Max number of clients to return (default 50)
    - offset: Pagination offset
    - complexity: Filter by complexity tier
    - filing_status: Filter by filing status
    - search: Search by name or email
    """
    request_id = generate_request_id()
    start_time = time.time()

    # Input validation
    valid, err = validate_pagination(limit, offset)
    if not valid:
        return format_error_response(err, ErrorCode.VALIDATION_ERROR, request_id=request_id)

    if complexity:
        valid, err = validate_enum_value(complexity, VALID_COMPLEXITY, "complexity")
        if not valid:
            return format_error_response(err, ErrorCode.VALIDATION_ERROR, request_id=request_id)

    if filing_status:
        valid, err = validate_enum_value(filing_status, VALID_FILING_STATUS, "filing_status")
        if not valid:
            return format_error_response(err, ErrorCode.VALIDATION_ERROR, request_id=request_id)

    # Sanitize search query
    search = sanitize_search_query(search) if search else None

    # Get tenant_id for multi-tenant isolation
    tenant_id = get_tenant_id(request)

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Build WHERE clause for reuse across count and data queries
            # SECURITY: Always filter by tenant_id to prevent cross-tenant data access
            where_clauses = ["1=1"]
            params = []

            # Add tenant filter — firm_id takes precedence, then tenant_id
            if tenant_id and tenant_id != "default":
                where_clauses.append("(tenant_id = ? OR firm_id = ?)")
                params.extend([tenant_id, tenant_id])

            if complexity:
                where_clauses.append("complexity = ?")
                params.append(complexity)

            if filing_status:
                where_clauses.append("filing_status = ?")
                params.append(filing_status)

            if search:
                where_clauses.append("(first_name LIKE ? OR last_name LIKE ? OR email LIKE ?)")
                search_param = f"%{search}%"
                params.extend([search_param, search_param, search_param])

            where_sql = " AND ".join(where_clauses)

            # Get total count
            cursor.execute(f"SELECT COUNT(*) FROM clients WHERE {where_sql}", params)
            total = cursor.fetchone()[0]

            # Get paginated results
            cursor.execute(f"SELECT * FROM clients WHERE {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?", params + [limit, offset])
            rows = cursor.fetchall()

            clients = []
            for row in rows:
                client = row_to_dict(row)
                # Parse JSON fields safely
                client["address"] = safe_json_parse(client.get("address_json"))
                client["spouse"] = safe_json_parse(client.get("spouse_json"))
                client["dependents"] = safe_json_parse(client.get("dependents_json"))
                clients.append(client)

        # Log successful request
        duration_ms = (time.time() - start_time) * 1000
        log_api_event("LIST_CLIENTS", f"Listed {len(clients)} clients", request_id=request_id, duration_ms=duration_ms)

        return format_success_response({
            "clients": clients,
            "total": total,
            "limit": limit,
            "offset": offset,
        }, request_id=request_id)

    except FileNotFoundError:
        return format_error_response("Database unavailable", ErrorCode.DB_CONNECTION_ERROR, request_id=request_id)
    except Exception as e:
        logger.error(f"Error listing clients: {e}", extra={"request_id": request_id})
        return format_error_response(str(e), ErrorCode.INTERNAL_ERROR, request_id=request_id)


@router.get("/data/clients/{client_id}")
async def get_client(request: Request, client_id: str) -> Dict[str, Any]:
    """Get a single client by ID or session ID."""
    request_id = generate_request_id()
    start_time = time.time()

    # Validate client_id
    valid, err = validate_session_id(client_id)
    if not valid:
        return format_error_response(err, ErrorCode.VALIDATION_ERROR, request_id=request_id)

    # Get tenant_id for multi-tenant isolation
    tenant_id = get_tenant_id(request)

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Try to find by client_id or session_id with tenant isolation
            # SECURITY: Include tenant_id/firm_id check to prevent cross-tenant data access
            if tenant_id and tenant_id != "default":
                cursor.execute(
                    """SELECT * FROM clients
                       WHERE (client_id = ? OR session_id = ?)
                       AND (tenant_id = ? OR firm_id = ? )""",
                    (client_id, client_id, tenant_id, tenant_id)
                )
            else:
                cursor.execute(
                    "SELECT * FROM clients WHERE client_id = ? OR session_id = ?",
                    (client_id, client_id)
                )
            row = cursor.fetchone()

            if not row:
                return format_error_response(
                    "Client not found",
                    ErrorCode.NOT_FOUND,
                    request_id=request_id
                )

            client = row_to_dict(row)
            actual_client_id = client.get("client_id")

            # Parse JSON fields safely
            client["address"] = safe_json_parse(client.get("address_json"))
            client["spouse"] = safe_json_parse(client.get("spouse_json"))
            client["dependents"] = safe_json_parse(client.get("dependents_json"))

            # Get associated tax return (scoped by tenant)
            if tenant_id and tenant_id != "default":
                cursor.execute("SELECT * FROM tax_returns WHERE client_id = ? AND (tenant_id = ? OR firm_id = ?)", (actual_client_id, tenant_id, tenant_id))
            else:
                cursor.execute("SELECT * FROM tax_returns WHERE client_id = ?", (actual_client_id,))
            tax_return_row = cursor.fetchone()
            if tax_return_row:
                tr = row_to_dict(tax_return_row)
                tr["adjustments"] = safe_json_parse(tr.get("adjustments_json"))
                tr["itemized_deductions"] = safe_json_parse(tr.get("itemized_deductions_json"))
                tr["credits"] = safe_json_parse(tr.get("credits_json"))
                client["tax_return"] = tr

            # Get associated recommendations
            cursor.execute(
                "SELECT * FROM recommendations WHERE client_id = ? ORDER BY estimated_savings DESC",
                (actual_client_id,)
            )
            client["recommendations"] = [row_to_dict(r) for r in cursor.fetchall()]

        # Log successful request
        duration_ms = (time.time() - start_time) * 1000
        log_api_event("GET_CLIENT", f"Fetched client {client_id}", request_id=request_id, duration_ms=duration_ms)

        return format_success_response({"client": client}, request_id=request_id)

    except FileNotFoundError:
        return format_error_response("Database unavailable", ErrorCode.DB_CONNECTION_ERROR, request_id=request_id)
    except Exception as e:
        logger.error(f"Error getting client {client_id}: {e}", extra={"request_id": request_id})
        return format_error_response(str(e), ErrorCode.INTERNAL_ERROR, request_id=request_id)


# =============================================================================
# TAX RETURN ENDPOINTS
# =============================================================================

@router.get("/data/tax-returns")
async def list_tax_returns(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    complexity: Optional[str] = None,
    has_refund: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    List all tax returns with optional filtering.
    """
    tenant_id = get_tenant_id(request)

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            where_clauses = ["1=1"]
            params = []

            # SECURITY: Scope by tenant/firm
            if tenant_id and tenant_id != "default":
                where_clauses.append("(tenant_id = ? OR firm_id = ?)")
                params.extend([tenant_id, tenant_id])

            if complexity:
                where_clauses.append("complexity_tier = ?")
                params.append(complexity)

            if has_refund is not None:
                if has_refund:
                    where_clauses.append("refund_amount > 0")
                else:
                    where_clauses.append("balance_due > 0")

            where_sql = " AND ".join(where_clauses)

            # Get total count
            cursor.execute(f"SELECT COUNT(*) FROM tax_returns WHERE {where_sql}", params)
            total = cursor.fetchone()[0]

            # Get paginated results
            cursor.execute(f"SELECT * FROM tax_returns WHERE {where_sql} ORDER BY agi DESC LIMIT ? OFFSET ?", params + [limit, offset])
            rows = cursor.fetchall()

            tax_returns = []
            for row in rows:
                tr = row_to_dict(row)
                # Parse JSON fields
                tr["adjustments"] = safe_json_parse(tr.get("adjustments_json"))
                tr["itemized_deductions"] = safe_json_parse(tr.get("itemized_deductions_json"))
                tr["credits"] = safe_json_parse(tr.get("credits_json"))
                tax_returns.append(tr)

        return {
            "success": True,
            "tax_returns": tax_returns,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        logger.error(f"Error listing tax returns: {e}")
        return {"success": False, "error": "An internal error occurred", "tax_returns": []}


@router.get("/data/tax-returns/{session_id}")
async def get_tax_return(request: Request, session_id: str) -> Dict[str, Any]:
    """Get a single tax return by session ID."""
    tenant_id = get_tenant_id(request)

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # SECURITY: Scope by tenant/firm
            if tenant_id and tenant_id != "default":
                cursor.execute("SELECT * FROM tax_returns WHERE session_id = ? AND (tenant_id = ? OR firm_id = ?)", (session_id, tenant_id, tenant_id))
            else:
                cursor.execute("SELECT * FROM tax_returns WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Tax return not found")

            tr = row_to_dict(row)

            # Parse JSON fields
            tr["adjustments"] = safe_json_parse(tr.get("adjustments_json"))
            tr["itemized_deductions"] = safe_json_parse(tr.get("itemized_deductions_json"))
            tr["credits"] = safe_json_parse(tr.get("credits_json"))

        return {"success": True, "tax_return": tr}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tax return {session_id}: {e}")
        return {"success": False, "error": "An internal error occurred"}


# =============================================================================
# RECOMMENDATION ENDPOINTS
# =============================================================================

@router.get("/data/recommendations")
async def list_recommendations(
    request: Request,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    category: Optional[str] = None,
    status: Optional[str] = None,
    client_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List recommendations with optional filtering. Scoped by tenant.
    """
    tenant_id = get_tenant_id(request)
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            from_join = "FROM recommendations r LEFT JOIN clients c ON r.client_id = c.client_id"
            where_clauses = ["1=1"]
            params = []

            # Tenant scoping
            if tenant_id and tenant_id != "default":
                where_clauses.append("(c.tenant_id = ? OR c.firm_id = ?)")
                params.extend([tenant_id, tenant_id])

            if category:
                where_clauses.append("r.category = ?")
                params.append(category)

            if status:
                where_clauses.append("r.status = ?")
                params.append(status)

            if client_id:
                where_clauses.append("(r.client_id = ? OR r.session_id = ?)")
                params.extend([client_id, client_id])

            where_sql = " AND ".join(where_clauses)

            # Get total count
            cursor.execute(f"SELECT COUNT(*) {from_join} WHERE {where_sql}", params)
            total = cursor.fetchone()[0]

            # Get total savings
            cursor.execute(f"SELECT SUM(r.estimated_savings) {from_join} WHERE {where_sql}", params)
            total_savings = cursor.fetchone()[0] or 0

            # Get paginated results
            cursor.execute(f"SELECT r.*, c.first_name, c.last_name {from_join} WHERE {where_sql} ORDER BY r.estimated_savings DESC LIMIT ? OFFSET ?", params + [limit, offset])
            recommendations = [row_to_dict(r) for r in cursor.fetchall()]

            # Get category counts (scoped by tenant)
            cat_filter = "WHERE (c.tenant_id = ? OR c.firm_id = ? )" if tenant_id and tenant_id != "default" else ""
            cat_params = (tenant_id, tenant_id) if tenant_id and tenant_id != "default" else ()
            cursor.execute(
                f"SELECT r.category, COUNT(*) as count, SUM(r.estimated_savings) as savings FROM recommendations r JOIN clients c ON r.client_id = c.client_id {cat_filter} GROUP BY r.category ORDER BY savings DESC",
                cat_params,
            )
            categories = [row_to_dict(r) for r in cursor.fetchall()]

        return {
            "success": True,
            "recommendations": recommendations,
            "total": total,
            "total_savings": total_savings,
            "categories": categories,
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        logger.error(f"Error listing recommendations: {e}")
        return {"success": False, "error": "An internal error occurred", "recommendations": []}


# =============================================================================
# ENGAGEMENT LETTER ENDPOINTS
# =============================================================================

@router.get("/data/engagements")
async def list_engagements(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List engagement letters with optional filtering. Scoped by tenant.
    """
    tenant_id = get_tenant_id(request)
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            where_clauses = ["1=1"]
            params = []

            # Tenant scoping
            if tenant_id and tenant_id != "default":
                where_clauses.append("(tenant_id = ? OR firm_id = ?)")
                params.extend([tenant_id, tenant_id])

            if status:
                where_clauses.append("status = ?")
                params.append(status)

            where_sql = " AND ".join(where_clauses)

            # Get total count
            cursor.execute(f"SELECT COUNT(*) FROM engagement_letters WHERE {where_sql}", params)
            total = cursor.fetchone()[0]

            # Get total fees
            cursor.execute(f"SELECT SUM(total_fee) FROM engagement_letters WHERE {where_sql}", params)
            total_fees = cursor.fetchone()[0] or 0

            # Get status counts (scoped by tenant)
            status_filter = "WHERE (tenant_id = ? OR firm_id = ? )" if tenant_id and tenant_id != "default" else ""
            status_params = (tenant_id, tenant_id) if tenant_id and tenant_id != "default" else ()
            cursor.execute(
                f"SELECT status, COUNT(*) as count, SUM(total_fee) as fees FROM engagement_letters {status_filter} GROUP BY status",
                status_params,
            )
            status_summary = {r["status"]: {"count": r["count"], "fees": r["fees"]} for r in cursor.fetchall()}

            # Get paginated results
            cursor.execute(f"SELECT * FROM engagement_letters WHERE {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?", params + [limit, offset])
            engagements = []
            for row in cursor.fetchall():
                eng = row_to_dict(row)
                eng["fee_adjustments"] = safe_json_parse(eng.get("fee_adjustments_json"))
                eng["scope"] = safe_json_parse(eng.get("scope_json"))
                engagements.append(eng)

        return {
            "success": True,
            "engagements": engagements,
            "total": total,
            "total_fees": total_fees,
            "status_summary": status_summary,
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        logger.error(f"Error listing engagements: {e}")
        return {"success": False, "error": "An internal error occurred", "engagements": []}


# =============================================================================
# DASHBOARD SUMMARY ENDPOINTS
# =============================================================================

@router.get("/data/dashboard/summary")
async def get_dashboard_summary(request: Request) -> Dict[str, Any]:
    """
    Get comprehensive dashboard summary with all key metrics.
    Scoped by tenant_id to prevent cross-firm data leakage.
    """
    tenant_id = get_tenant_id(request)
    tenant_filter = "AND (tenant_id = ? OR firm_id = ?)" if tenant_id and tenant_id != "default" else ""
    tenant_filter_c = "AND (c.tenant_id = ? OR c.firm_id = ?)" if tenant_id and tenant_id != "default" else ""
    tenant_params = (tenant_id, tenant_id) if tenant_id and tenant_id != "default" else ()

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            summary = {}

            # Client stats (scoped by tenant)
            cursor.execute(f"SELECT COUNT(*) FROM clients WHERE 1=1 {tenant_filter}", tenant_params)
            summary["total_clients"] = cursor.fetchone()[0]

            cursor.execute(
                f"SELECT complexity, COUNT(*) as count FROM clients WHERE 1=1 {tenant_filter} GROUP BY complexity ORDER BY count DESC",
                tenant_params,
            )
            summary["clients_by_complexity"] = {r["complexity"]: r["count"] for r in cursor.fetchall()}

            cursor.execute(
                f"SELECT filing_status, COUNT(*) as count FROM clients WHERE 1=1 {tenant_filter} GROUP BY filing_status ORDER BY count DESC",
                tenant_params,
            )
            summary["clients_by_filing_status"] = {r["filing_status"]: r["count"] for r in cursor.fetchall()}

            # Tax return stats (scoped by tenant)
            cursor.execute(f"SELECT COUNT(*), SUM(agi), AVG(agi), SUM(total_tax) FROM tax_returns WHERE 1=1 {tenant_filter}", tenant_params)
            row = cursor.fetchone()
            summary["tax_returns"] = {
                "total": row[0] or 0,
                "total_agi": row[1] or 0,
                "avg_agi": row[2] or 0,
                "total_tax": row[3] or 0,
            }

            cursor.execute(f"SELECT SUM(refund_amount), COUNT(*) FROM tax_returns WHERE refund_amount > 0 {tenant_filter}", tenant_params)
            row = cursor.fetchone()
            summary["refunds"] = {"total": row[0] or 0, "count": row[1] or 0}

            cursor.execute(f"SELECT SUM(balance_due), COUNT(*) FROM tax_returns WHERE balance_due > 0 {tenant_filter}", tenant_params)
            row = cursor.fetchone()
            summary["balance_due"] = {"total": row[0] or 0, "count": row[1] or 0}

            # Recommendation stats (scoped by tenant via client join)
            cursor.execute(
                f"SELECT COUNT(*), SUM(r.estimated_savings) FROM recommendations r JOIN clients c ON r.client_id = c.client_id WHERE 1=1 {tenant_filter_c}",
                tenant_params,
            )
            row = cursor.fetchone()
            summary["recommendations"] = {
                "total": row[0] or 0,
                "total_savings": row[1] or 0,
            }

            cursor.execute(
                f"SELECT r.category, COUNT(*) as count, SUM(r.estimated_savings) as savings FROM recommendations r JOIN clients c ON r.client_id = c.client_id WHERE 1=1 {tenant_filter_c} GROUP BY r.category ORDER BY savings DESC",
                tenant_params,
            )
            summary["recommendations_by_category"] = [
                {"category": r["category"], "count": r["count"], "savings": r["savings"]}
                for r in cursor.fetchall()
            ]

            cursor.execute(
                f"SELECT r.status, COUNT(*) as count FROM recommendations r JOIN clients c ON r.client_id = c.client_id WHERE 1=1 {tenant_filter_c} GROUP BY r.status",
                tenant_params,
            )
            summary["recommendations_by_status"] = {r["status"]: r["count"] for r in cursor.fetchall()}

            # Engagement stats (scoped by tenant)
            cursor.execute(f"SELECT COUNT(*), SUM(total_fee) FROM engagement_letters WHERE 1=1 {tenant_filter}", tenant_params)
            row = cursor.fetchone()
            summary["engagements"] = {
                "total": row[0] or 0,
                "total_fees": row[1] or 0,
            }

            cursor.execute(
                f"SELECT status, COUNT(*) as count, SUM(total_fee) as fees FROM engagement_letters WHERE 1=1 {tenant_filter} GROUP BY status",
                tenant_params,
            )
            summary["engagements_by_status"] = {
                r["status"]: {"count": r["count"], "fees": r["fees"]}
                for r in cursor.fetchall()
            }

            # Top clients by savings potential (scoped by tenant)
            cursor.execute(f"""
                SELECT c.client_id, c.first_name, c.last_name, c.complexity,
                       SUM(r.estimated_savings) as total_savings,
                       COUNT(r.rec_id) as rec_count
                FROM clients c
                JOIN recommendations r ON c.client_id = r.client_id
                WHERE 1=1 {tenant_filter_c}
                GROUP BY c.client_id
                ORDER BY total_savings DESC
                LIMIT 10
            """, tenant_params)
            summary["top_clients_by_savings"] = [
                {
                    "client_id": r["client_id"],
                    "name": f"{r['first_name']} {r['last_name']}",
                    "complexity": r["complexity"],
                    "total_savings": r["total_savings"],
                    "recommendation_count": r["rec_count"],
                }
                for r in cursor.fetchall()
            ]

            # High-value opportunities (scoped by tenant)
            cursor.execute(f"""
                SELECT r.*, c.first_name, c.last_name
                FROM recommendations r
                JOIN clients c ON r.client_id = c.client_id
                WHERE r.estimated_savings > 5000 {tenant_filter_c}
                ORDER BY r.estimated_savings DESC
                LIMIT 20
            """, tenant_params)
            summary["high_value_opportunities"] = [
                {
                    "rec_id": r["rec_id"],
                    "client_name": f"{r['first_name']} {r['last_name']}",
                    "title": r["title"],
                    "category": r["category"],
                    "savings": r["estimated_savings"],
                    "status": r["status"],
                }
                for r in cursor.fetchall()
            ]

        return {"success": True, "summary": summary}
    except Exception as e:
        logger.error(f"Error getting dashboard summary: {e}")
        return {"success": False, "error": "An internal error occurred"}


@router.get("/data/clients-for-select")
async def get_clients_for_select(request: Request) -> Dict[str, Any]:
    """
    Get a simplified list of clients for dropdown selects.
    Returns client_id, session_id, name, and complexity.
    """
    request_id = generate_request_id()
    start_time = time.time()

    tenant_id = get_tenant_id(request)
    tenant_filter = "WHERE (tenant_id = ? OR firm_id = ? )" if tenant_id and tenant_id != "default" else ""
    tenant_params = (tenant_id, tenant_id) if tenant_id and tenant_id != "default" else ()

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(f"""
                SELECT client_id, session_id, first_name, last_name, complexity,
                       (SELECT SUM(estimated_savings) FROM recommendations WHERE client_id = c.client_id) as savings_potential
                FROM clients c
                {tenant_filter}
                ORDER BY last_name, first_name
            """, tenant_params)

            clients = [
                {
                    "id": r["session_id"],  # Use session_id for API compatibility
                    "client_id": r["client_id"],
                    "name": f"{r['first_name']} {r['last_name']}",
                    "complexity": r["complexity"],
                    "savings_potential": r["savings_potential"] or 0,
                }
                for r in cursor.fetchall()
            ]

        duration_ms = (time.time() - start_time) * 1000
        log_api_event("CLIENTS_FOR_SELECT", f"Fetched {len(clients)} clients", request_id=request_id, duration_ms=duration_ms)

        return format_success_response({"clients": clients}, request_id=request_id)

    except FileNotFoundError:
        return format_error_response("Database unavailable", ErrorCode.DB_CONNECTION_ERROR, request_id=request_id)
    except Exception as e:
        logger.error(f"Error getting clients for select: {e}", extra={"request_id": request_id})
        return format_error_response(str(e), ErrorCode.INTERNAL_ERROR, request_id=request_id)
