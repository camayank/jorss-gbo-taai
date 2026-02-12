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

            # Build query with tenant isolation
            # SECURITY: Always filter by tenant_id to prevent cross-tenant data access
            query = "SELECT * FROM clients WHERE 1=1"
            params = []

            # Add tenant filter if not default (platform admin can see all with default)
            if tenant_id and tenant_id != "default":
                query += " AND (tenant_id = ? OR tenant_id IS NULL)"
                params.append(tenant_id)

            if complexity:
                query += " AND complexity = ?"
                params.append(complexity)

            if filing_status:
                query += " AND filing_status = ?"
                params.append(filing_status)

            if search:
                query += " AND (first_name LIKE ? OR last_name LIKE ? OR email LIKE ?)"
                search_param = f"%{search}%"
                params.extend([search_param, search_param, search_param])

            # Get total count
            count_query = query.replace("SELECT *", "SELECT COUNT(*)")
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]

            # Get paginated results
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
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
            # SECURITY: Include tenant_id check to prevent cross-tenant data access
            if tenant_id and tenant_id != "default":
                cursor.execute(
                    """SELECT * FROM clients
                       WHERE (client_id = ? OR session_id = ?)
                       AND (tenant_id = ? OR tenant_id IS NULL)""",
                    (client_id, client_id, tenant_id)
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

            # Get associated tax return
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
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM tax_returns WHERE 1=1"
            params = []

            if complexity:
                query += " AND complexity_tier = ?"
                params.append(complexity)

            if has_refund is not None:
                if has_refund:
                    query += " AND refund_amount > 0"
                else:
                    query += " AND balance_due > 0"

            # Get total count
            count_query = query.replace("SELECT *", "SELECT COUNT(*)")
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]

            # Get paginated results
            query += " ORDER BY agi DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
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
        return {"success": False, "error": str(e), "tax_returns": []}


@router.get("/data/tax-returns/{session_id}")
async def get_tax_return(request: Request, session_id: str) -> Dict[str, Any]:
    """Get a single tax return by session ID."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

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
        return {"success": False, "error": str(e)}


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
    List recommendations with optional filtering.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT r.*, c.first_name, c.last_name FROM recommendations r LEFT JOIN clients c ON r.client_id = c.client_id WHERE 1=1"
            params = []

            if category:
                query += " AND r.category = ?"
                params.append(category)

            if status:
                query += " AND r.status = ?"
                params.append(status)

            if client_id:
                query += " AND (r.client_id = ? OR r.session_id = ?)"
                params.extend([client_id, client_id])

            # Get total count
            count_query = query.replace("SELECT r.*, c.first_name, c.last_name", "SELECT COUNT(*)")
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]

            # Get total savings
            savings_query = query.replace("SELECT r.*, c.first_name, c.last_name", "SELECT SUM(r.estimated_savings)")
            cursor.execute(savings_query, params)
            total_savings = cursor.fetchone()[0] or 0

            # Get paginated results
            query += " ORDER BY r.estimated_savings DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            recommendations = [row_to_dict(r) for r in cursor.fetchall()]

            # Get category counts
            cursor.execute(
                "SELECT category, COUNT(*) as count, SUM(estimated_savings) as savings FROM recommendations GROUP BY category ORDER BY savings DESC"
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
        return {"success": False, "error": str(e), "recommendations": []}


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
    List engagement letters with optional filtering.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM engagement_letters WHERE 1=1"
            params = []

            if status:
                query += " AND status = ?"
                params.append(status)

            # Get total count
            count_query = query.replace("SELECT *", "SELECT COUNT(*)")
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]

            # Get total fees
            fees_query = query.replace("SELECT *", "SELECT SUM(total_fee)")
            cursor.execute(fees_query, params)
            total_fees = cursor.fetchone()[0] or 0

            # Get status counts
            cursor.execute(
                "SELECT status, COUNT(*) as count, SUM(total_fee) as fees FROM engagement_letters GROUP BY status"
            )
            status_summary = {r["status"]: {"count": r["count"], "fees": r["fees"]} for r in cursor.fetchall()}

            # Get paginated results
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
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
        return {"success": False, "error": str(e), "engagements": []}


# =============================================================================
# DASHBOARD SUMMARY ENDPOINTS
# =============================================================================

@router.get("/data/dashboard/summary")
async def get_dashboard_summary(request: Request) -> Dict[str, Any]:
    """
    Get comprehensive dashboard summary with all key metrics.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            summary = {}

            # Client stats
            cursor.execute("SELECT COUNT(*) FROM clients")
            summary["total_clients"] = cursor.fetchone()[0]

            cursor.execute(
                "SELECT complexity, COUNT(*) as count FROM clients GROUP BY complexity ORDER BY count DESC"
            )
            summary["clients_by_complexity"] = {r["complexity"]: r["count"] for r in cursor.fetchall()}

            cursor.execute(
                "SELECT filing_status, COUNT(*) as count FROM clients GROUP BY filing_status ORDER BY count DESC"
            )
            summary["clients_by_filing_status"] = {r["filing_status"]: r["count"] for r in cursor.fetchall()}

            # Tax return stats
            cursor.execute("SELECT COUNT(*), SUM(agi), AVG(agi), SUM(total_tax) FROM tax_returns")
            row = cursor.fetchone()
            summary["tax_returns"] = {
                "total": row[0] or 0,
                "total_agi": row[1] or 0,
                "avg_agi": row[2] or 0,
                "total_tax": row[3] or 0,
            }

            cursor.execute("SELECT SUM(refund_amount), COUNT(*) FROM tax_returns WHERE refund_amount > 0")
            row = cursor.fetchone()
            summary["refunds"] = {"total": row[0] or 0, "count": row[1] or 0}

            cursor.execute("SELECT SUM(balance_due), COUNT(*) FROM tax_returns WHERE balance_due > 0")
            row = cursor.fetchone()
            summary["balance_due"] = {"total": row[0] or 0, "count": row[1] or 0}

            # Recommendation stats
            cursor.execute(
                "SELECT COUNT(*), SUM(estimated_savings) FROM recommendations"
            )
            row = cursor.fetchone()
            summary["recommendations"] = {
                "total": row[0] or 0,
                "total_savings": row[1] or 0,
            }

            cursor.execute(
                "SELECT category, COUNT(*) as count, SUM(estimated_savings) as savings FROM recommendations GROUP BY category ORDER BY savings DESC"
            )
            summary["recommendations_by_category"] = [
                {"category": r["category"], "count": r["count"], "savings": r["savings"]}
                for r in cursor.fetchall()
            ]

            cursor.execute(
                "SELECT status, COUNT(*) as count FROM recommendations GROUP BY status"
            )
            summary["recommendations_by_status"] = {r["status"]: r["count"] for r in cursor.fetchall()}

            # Engagement stats
            cursor.execute("SELECT COUNT(*), SUM(total_fee) FROM engagement_letters")
            row = cursor.fetchone()
            summary["engagements"] = {
                "total": row[0] or 0,
                "total_fees": row[1] or 0,
            }

            cursor.execute(
                "SELECT status, COUNT(*) as count, SUM(total_fee) as fees FROM engagement_letters GROUP BY status"
            )
            summary["engagements_by_status"] = {
                r["status"]: {"count": r["count"], "fees": r["fees"]}
                for r in cursor.fetchall()
            }

            # Top clients by savings potential
            cursor.execute("""
                SELECT c.client_id, c.first_name, c.last_name, c.complexity,
                       SUM(r.estimated_savings) as total_savings,
                       COUNT(r.rec_id) as rec_count
                FROM clients c
                JOIN recommendations r ON c.client_id = r.client_id
                GROUP BY c.client_id
                ORDER BY total_savings DESC
                LIMIT 10
            """)
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

            # High-value opportunities (individual recs > $5000)
            cursor.execute("""
                SELECT r.*, c.first_name, c.last_name
                FROM recommendations r
                JOIN clients c ON r.client_id = c.client_id
                WHERE r.estimated_savings > 5000
                ORDER BY r.estimated_savings DESC
                LIMIT 20
            """)
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
        return {"success": False, "error": str(e)}


@router.get("/data/clients-for-select")
async def get_clients_for_select(request: Request) -> Dict[str, Any]:
    """
    Get a simplified list of clients for dropdown selects.
    Returns client_id, session_id, name, and complexity.
    """
    request_id = generate_request_id()
    start_time = time.time()

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT client_id, session_id, first_name, last_name, complexity,
                       (SELECT SUM(estimated_savings) FROM recommendations WHERE client_id = c.client_id) as savings_potential
                FROM clients c
                ORDER BY last_name, first_name
            """)

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
