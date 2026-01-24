"""
Database Column Specifications - Explicit column lists for all tables.

Provides:
- Explicit column definitions for each table
- Column sets for different query types (list, detail, sensitive)
- Query builders with proper column selection

Resolves Audit Finding: "SELECT * queries without column specification"
"""

from __future__ import annotations

from typing import Dict, List, Set

# =============================================================================
# TENANT TABLE COLUMNS
# =============================================================================

TENANT_COLUMNS = [
    "tenant_id",
    "tenant_name",
    "status",
    "subscription_tier",
    "branding",
    "features",
    "custom_domain",
    "custom_domain_verified",
    "admin_user_id",
    "admin_email",
    "stripe_customer_id",
    "subscription_expires_at",
    "created_at",
    "updated_at",
    "metadata",
    "total_returns",
    "total_cpas",
    "total_clients",
    "storage_used_gb",
]

# Columns safe to expose in list views (excludes sensitive/internal)
TENANT_LIST_COLUMNS = [
    "tenant_id",
    "tenant_name",
    "status",
    "subscription_tier",
    "custom_domain",
    "created_at",
]

# Columns for branding display
TENANT_BRANDING_COLUMNS = [
    "tenant_id",
    "tenant_name",
    "branding",
    "features",
    "custom_domain",
]

# =============================================================================
# SESSION TABLE COLUMNS
# =============================================================================

SESSION_COLUMNS = [
    "session_id",
    "tenant_id",
    "session_type",
    "created_at",
    "last_activity",
    "expires_at",
    "data_json",
    "metadata_json",
    "agent_state_blob",
]

SESSION_LIST_COLUMNS = [
    "session_id",
    "tenant_id",
    "session_type",
    "created_at",
    "last_activity",
    "expires_at",
]

# =============================================================================
# TAX RETURN TABLE COLUMNS
# =============================================================================

TAX_RETURN_COLUMNS = [
    "session_id",
    "tenant_id",
    "created_at",
    "updated_at",
    "tax_year",
    "return_data_json",
    "calculated_results_json",
]

# Exclude sensitive data for list views
TAX_RETURN_LIST_COLUMNS = [
    "session_id",
    "tenant_id",
    "created_at",
    "updated_at",
    "tax_year",
]

# =============================================================================
# DOCUMENT PROCESSING TABLE COLUMNS
# =============================================================================

DOCUMENT_COLUMNS = [
    "document_id",
    "session_id",
    "tenant_id",
    "created_at",
    "document_type",
    "status",
    "result_json",
    "error_message",
]

DOCUMENT_LIST_COLUMNS = [
    "document_id",
    "session_id",
    "tenant_id",
    "created_at",
    "document_type",
    "status",
]

# =============================================================================
# ADVISORY REPORT TABLE COLUMNS
# =============================================================================

ADVISORY_REPORT_COLUMNS = [
    "report_id",
    "session_id",
    "tenant_id",
    "report_type",
    "taxpayer_name",
    "generated_at",
    "current_tax_liability",
    "potential_savings",
    "recommendations_count",
    "confidence_score",
    "pdf_path",
    "report_data_json",
]

ADVISORY_REPORT_LIST_COLUMNS = [
    "report_id",
    "session_id",
    "tenant_id",
    "report_type",
    "generated_at",
    "current_tax_liability",
    "potential_savings",
]

# =============================================================================
# SCENARIO TABLE COLUMNS
# =============================================================================

SCENARIO_COLUMNS = [
    "scenario_id",
    "return_id",
    "tenant_id",
    "name",
    "description",
    "scenario_type",
    "status",
    "is_recommended",
    "recommendation_reason",
    "created_at",
    "calculated_at",
    "modifications_json",
    "result_json",
]

SCENARIO_LIST_COLUMNS = [
    "scenario_id",
    "return_id",
    "tenant_id",
    "name",
    "scenario_type",
    "status",
    "is_recommended",
    "created_at",
]

# =============================================================================
# CPA BRANDING TABLE COLUMNS
# =============================================================================

CPA_BRANDING_COLUMNS = [
    "cpa_id",
    "tenant_id",
    "display_name",
    "tagline",
    "accent_color",
    "profile_photo_url",
    "signature_image_url",
    "direct_email",
    "direct_phone",
    "office_address",
    "bio",
    "credentials",
    "years_experience",
    "specializations",
    "welcome_message",
    "created_at",
    "updated_at",
]

CPA_BRANDING_PUBLIC_COLUMNS = [
    "cpa_id",
    "display_name",
    "tagline",
    "accent_color",
    "profile_photo_url",
    "bio",
    "credentials",
    "years_experience",
    "specializations",
]

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def build_select_query(
    table: str,
    columns: List[str],
    where_clause: str = None,
    order_by: str = None,
    limit: int = None,
    offset: int = None,
) -> str:
    """
    Build a SELECT query with explicit columns.

    Args:
        table: Table name
        columns: List of column names to select
        where_clause: Optional WHERE clause (without WHERE keyword)
        order_by: Optional ORDER BY clause (without ORDER BY keyword)
        limit: Optional LIMIT value
        offset: Optional OFFSET value

    Returns:
        SQL query string

    Example:
        >>> query = build_select_query(
        ...     "tenants",
        ...     TENANT_LIST_COLUMNS,
        ...     where_clause="status = ?",
        ...     order_by="created_at DESC",
        ...     limit=10
        ... )
        >>> print(query)
        SELECT tenant_id, tenant_name, status, ... FROM tenants WHERE status = ? ORDER BY created_at DESC LIMIT 10
    """
    column_list = ", ".join(columns)
    query = f"SELECT {column_list} FROM {table}"

    if where_clause:
        query += f" WHERE {where_clause}"

    if order_by:
        query += f" ORDER BY {order_by}"

    if limit is not None:
        query += f" LIMIT {limit}"

    if offset is not None:
        query += f" OFFSET {offset}"

    return query


def build_count_query(table: str, where_clause: str = None) -> str:
    """
    Build a COUNT query for pagination.

    Args:
        table: Table name
        where_clause: Optional WHERE clause

    Returns:
        SQL count query string
    """
    query = f"SELECT COUNT(*) FROM {table}"

    if where_clause:
        query += f" WHERE {where_clause}"

    return query


def get_columns_for_table(table_name: str, include_sensitive: bool = False) -> List[str]:
    """
    Get appropriate columns for a table.

    Args:
        table_name: Name of the database table
        include_sensitive: Whether to include sensitive columns

    Returns:
        List of column names
    """
    column_map = {
        "tenants": (TENANT_COLUMNS, TENANT_LIST_COLUMNS),
        "session_states": (SESSION_COLUMNS, SESSION_LIST_COLUMNS),
        "session_tax_returns": (TAX_RETURN_COLUMNS, TAX_RETURN_LIST_COLUMNS),
        "document_processing": (DOCUMENT_COLUMNS, DOCUMENT_LIST_COLUMNS),
        "advisory_reports": (ADVISORY_REPORT_COLUMNS, ADVISORY_REPORT_LIST_COLUMNS),
        "scenarios": (SCENARIO_COLUMNS, SCENARIO_LIST_COLUMNS),
        "cpa_branding": (CPA_BRANDING_COLUMNS, CPA_BRANDING_PUBLIC_COLUMNS),
    }

    if table_name in column_map:
        full_cols, list_cols = column_map[table_name]
        return full_cols if include_sensitive else list_cols

    # Unknown table - return empty (force explicit column specification)
    return []


def validate_columns(columns: List[str], allowed: List[str]) -> List[str]:
    """
    Validate requested columns against allowed list.

    Args:
        columns: Requested columns
        allowed: Allowed column names

    Returns:
        Filtered list of valid columns
    """
    allowed_set = set(allowed)
    return [c for c in columns if c in allowed_set]


# =============================================================================
# COLUMN SETS BY USE CASE
# =============================================================================

# Columns that should NEVER be exposed in API responses
SENSITIVE_COLUMNS: Set[str] = {
    "ssn",
    "password_hash",
    "api_key",
    "secret_key",
    "stripe_customer_id",
    "agent_state_blob",
}

# Columns that are safe for public/unauthenticated access
PUBLIC_SAFE_COLUMNS: Set[str] = {
    "tenant_id",
    "tenant_name",
    "display_name",
    "tagline",
    "accent_color",
    "profile_photo_url",
}


def filter_sensitive_columns(columns: List[str]) -> List[str]:
    """Remove sensitive columns from a column list."""
    return [c for c in columns if c not in SENSITIVE_COLUMNS]
