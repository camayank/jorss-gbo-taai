"""
Database Security Helpers.

Provides security-focused database utilities:
- Row-Level Security (RLS) helpers for PostgreSQL
- Secure query builders
- SQL injection prevention utilities
- Parameterized query helpers
- Audit-enabled database operations

CRITICAL: Always use parameterized queries. This module provides defense-in-depth.
"""

from __future__ import annotations

import logging
import re
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, TypeVar, Union
from uuid import UUID

from sqlalchemy import Column, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Query, Session

logger = logging.getLogger(__name__)


# =============================================================================
# SQL INJECTION PREVENTION
# =============================================================================


# Patterns that indicate potential SQL injection
SQL_INJECTION_PATTERNS = [
    re.compile(r";\s*DROP\s", re.IGNORECASE),
    re.compile(r";\s*DELETE\s", re.IGNORECASE),
    re.compile(r";\s*UPDATE\s", re.IGNORECASE),
    re.compile(r";\s*INSERT\s", re.IGNORECASE),
    re.compile(r";\s*ALTER\s", re.IGNORECASE),
    re.compile(r";\s*CREATE\s", re.IGNORECASE),
    re.compile(r";\s*TRUNCATE\s", re.IGNORECASE),
    re.compile(r"UNION\s+SELECT", re.IGNORECASE),
    re.compile(r"UNION\s+ALL\s+SELECT", re.IGNORECASE),
    re.compile(r"--\s*$"),
    re.compile(r"/\*.*\*/"),
    re.compile(r"'\s*OR\s+'", re.IGNORECASE),
    re.compile(r"'\s*OR\s+1\s*=\s*1", re.IGNORECASE),
    re.compile(r"'\s*AND\s+1\s*=\s*1", re.IGNORECASE),
    re.compile(r"SLEEP\s*\(", re.IGNORECASE),
    re.compile(r"BENCHMARK\s*\(", re.IGNORECASE),
    re.compile(r"WAITFOR\s+DELAY", re.IGNORECASE),
]

# Characters that should be escaped in string values
ESCAPE_CHARS = {
    "'": "''",
    "\\": "\\\\",
    "\x00": "",
    "\n": "\\n",
    "\r": "\\r",
    "\x1a": "\\Z",
}


def check_sql_injection(value: str) -> bool:
    """
    Check if a string contains potential SQL injection patterns.

    Returns True if injection attempt detected.

    NOTE: This is defense-in-depth. Always use parameterized queries!
    """
    for pattern in SQL_INJECTION_PATTERNS:
        if pattern.search(value):
            return True
    return False


def escape_string(value: str) -> str:
    """
    Escape a string value for safe SQL inclusion.

    NOTE: Prefer parameterized queries over string escaping!
    """
    for char, replacement in ESCAPE_CHARS.items():
        value = value.replace(char, replacement)
    return value


def validate_identifier(identifier: str) -> str:
    """
    Validate and return a safe SQL identifier (table/column name).

    Raises ValueError if identifier is invalid.
    """
    # Only allow alphanumeric and underscore
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', identifier):
        raise ValueError(f"Invalid SQL identifier: {identifier}")

    # Check against reserved words (basic list)
    reserved = {
        "SELECT", "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER",
        "TABLE", "DATABASE", "INDEX", "VIEW", "TRIGGER", "PROCEDURE",
        "FUNCTION", "GRANT", "REVOKE", "UNION", "WHERE", "FROM", "JOIN",
    }
    if identifier.upper() in reserved:
        raise ValueError(f"Reserved SQL keyword cannot be used as identifier: {identifier}")

    return identifier


def validate_sort_column(column: str, allowed_columns: Set[str]) -> str:
    """
    Validate a sort column against a whitelist.

    Returns the column name if valid, raises ValueError otherwise.
    """
    if column not in allowed_columns:
        raise ValueError(
            f"Invalid sort column: {column}. "
            f"Allowed: {', '.join(sorted(allowed_columns))}"
        )
    return column


def validate_sort_direction(direction: str) -> str:
    """Validate sort direction (ASC/DESC)."""
    direction = direction.upper()
    if direction not in ("ASC", "DESC"):
        raise ValueError(f"Invalid sort direction: {direction}")
    return direction


# =============================================================================
# ROW-LEVEL SECURITY HELPERS
# =============================================================================


class RLSContext:
    """
    Context for Row-Level Security enforcement.

    Stores the current user/tenant context for query filtering.
    """

    def __init__(
        self,
        user_id: Optional[UUID] = None,
        tenant_id: Optional[UUID] = None,
        is_superuser: bool = False,
        allowed_tenant_ids: Optional[Set[UUID]] = None,
    ):
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.is_superuser = is_superuser
        self.allowed_tenant_ids = allowed_tenant_ids or set()


class SecureQueryBuilder:
    """
    Builder for creating secure, tenant-isolated queries.

    Automatically applies tenant filters and prevents common injection patterns.

    Usage:
        builder = SecureQueryBuilder(session, Client, rls_context)
        clients = builder.filter(status="active").order_by("created_at").limit(10).all()
    """

    def __init__(
        self,
        session: Session,
        model: Any,
        rls_context: RLSContext,
        tenant_column: str = "firm_id",
    ):
        self.session = session
        self.model = model
        self.rls_context = rls_context
        self.tenant_column = tenant_column
        self._query = session.query(model)
        self._apply_rls()

    def _apply_rls(self) -> None:
        """Apply row-level security filter."""
        if self.rls_context.is_superuser:
            return  # Superuser sees all

        tenant_col = getattr(self.model, self.tenant_column, None)
        if not tenant_col:
            logger.warning(
                f"Model {self.model.__name__} has no {self.tenant_column} column for RLS"
            )
            return

        if self.rls_context.tenant_id:
            if self.rls_context.allowed_tenant_ids:
                # User can access own tenant and allowed tenants
                all_allowed = {self.rls_context.tenant_id} | self.rls_context.allowed_tenant_ids
                self._query = self._query.filter(tenant_col.in_(all_allowed))
            else:
                # User can only access own tenant
                self._query = self._query.filter(tenant_col == self.rls_context.tenant_id)
        else:
            # No tenant context - filter to nothing (safety)
            self._query = self._query.filter(tenant_col == None)  # noqa: E711

    def filter(self, **kwargs) -> "SecureQueryBuilder":
        """Add filter conditions."""
        for key, value in kwargs.items():
            # Validate column name
            if not hasattr(self.model, key):
                raise ValueError(f"Invalid filter column: {key}")

            col = getattr(self.model, key)

            # Check for injection in string values
            if isinstance(value, str) and check_sql_injection(value):
                logger.warning(f"Potential SQL injection in filter value for {key}")
                raise ValueError("Invalid filter value")

            self._query = self._query.filter(col == value)

        return self

    def filter_in(self, column: str, values: List[Any]) -> "SecureQueryBuilder":
        """Filter where column is in a list of values."""
        if not hasattr(self.model, column):
            raise ValueError(f"Invalid filter column: {column}")

        col = getattr(self.model, column)
        self._query = self._query.filter(col.in_(values))
        return self

    def filter_like(self, column: str, pattern: str) -> "SecureQueryBuilder":
        """Filter with LIKE pattern (properly escaped)."""
        if not hasattr(self.model, column):
            raise ValueError(f"Invalid filter column: {column}")

        # Escape special LIKE characters
        pattern = pattern.replace("\\", "\\\\")
        pattern = pattern.replace("%", "\\%")
        pattern = pattern.replace("_", "\\_")

        col = getattr(self.model, column)
        self._query = self._query.filter(col.like(f"%{pattern}%", escape="\\"))
        return self

    def order_by(
        self,
        column: str,
        direction: str = "ASC",
        allowed_columns: Optional[Set[str]] = None,
    ) -> "SecureQueryBuilder":
        """Add order by clause with validation."""
        # Validate against whitelist if provided
        if allowed_columns:
            validate_sort_column(column, allowed_columns)

        if not hasattr(self.model, column):
            raise ValueError(f"Invalid sort column: {column}")

        direction = validate_sort_direction(direction)
        col = getattr(self.model, column)

        if direction == "DESC":
            self._query = self._query.order_by(col.desc())
        else:
            self._query = self._query.order_by(col.asc())

        return self

    def limit(self, limit: int) -> "SecureQueryBuilder":
        """Add limit clause."""
        if limit < 0:
            raise ValueError("Limit must be non-negative")
        if limit > 10000:
            limit = 10000  # Cap at reasonable maximum
        self._query = self._query.limit(limit)
        return self

    def offset(self, offset: int) -> "SecureQueryBuilder":
        """Add offset clause."""
        if offset < 0:
            raise ValueError("Offset must be non-negative")
        self._query = self._query.offset(offset)
        return self

    def all(self) -> List[Any]:
        """Execute query and return all results."""
        return self._query.all()

    def first(self) -> Optional[Any]:
        """Execute query and return first result."""
        return self._query.first()

    def count(self) -> int:
        """Return count of matching records."""
        return self._query.count()

    def exists(self) -> bool:
        """Check if any matching records exist."""
        return self.session.query(self._query.exists()).scalar()


# =============================================================================
# AUDIT-ENABLED OPERATIONS
# =============================================================================


class AuditedSession:
    """
    Session wrapper that automatically logs all data modifications.

    Usage:
        with AuditedSession(session, user_id, tenant_id) as audited:
            audited.add(new_client)
            audited.delete(old_client)
            audited.commit()  # All changes logged
    """

    def __init__(
        self,
        session: Session,
        user_id: Optional[UUID] = None,
        tenant_id: Optional[UUID] = None,
        audit_logger: Optional[Any] = None,
    ):
        self.session = session
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.audit_logger = audit_logger
        self._pending_adds: List[Tuple[Any, str]] = []
        self._pending_deletes: List[Tuple[Any, str]] = []
        self._pending_updates: List[Tuple[Any, str, Dict]] = []

    def add(self, obj: Any, reason: str = "") -> None:
        """Add an object to the session with audit tracking."""
        self.session.add(obj)
        self._pending_adds.append((obj, reason))

    def delete(self, obj: Any, reason: str = "") -> None:
        """Mark an object for deletion with audit tracking."""
        self.session.delete(obj)
        self._pending_deletes.append((obj, reason))

    def update(self, obj: Any, changes: Dict[str, Any], reason: str = "") -> None:
        """Update an object with audit tracking."""
        old_values = {}
        for key, new_value in changes.items():
            if hasattr(obj, key):
                old_values[key] = getattr(obj, key)
                setattr(obj, key, new_value)

        self._pending_updates.append((obj, reason, {"old": old_values, "new": changes}))

    def commit(self) -> None:
        """Commit all changes and log to audit trail."""
        try:
            self.session.commit()
            self._log_audit_entries()
        except Exception:
            self.session.rollback()
            raise

    def rollback(self) -> None:
        """Rollback changes and clear pending audit entries."""
        self.session.rollback()
        self._pending_adds.clear()
        self._pending_deletes.clear()
        self._pending_updates.clear()

    def _log_audit_entries(self) -> None:
        """Log all pending operations to audit trail."""
        if not self.audit_logger:
            return

        for obj, reason in self._pending_adds:
            self._log_entry("CREATE", obj, reason)

        for obj, reason in self._pending_deletes:
            self._log_entry("DELETE", obj, reason)

        for obj, reason, changes in self._pending_updates:
            self._log_entry("UPDATE", obj, reason, changes)

        # Clear pending
        self._pending_adds.clear()
        self._pending_deletes.clear()
        self._pending_updates.clear()

    def _log_entry(
        self,
        action: str,
        obj: Any,
        reason: str,
        changes: Optional[Dict] = None
    ) -> None:
        """Log a single audit entry."""
        try:
            obj_type = type(obj).__name__
            obj_id = getattr(obj, "id", None) or getattr(obj, "uuid", None)

            log_data = {
                "action": action,
                "object_type": obj_type,
                "object_id": str(obj_id) if obj_id else None,
                "user_id": str(self.user_id) if self.user_id else None,
                "tenant_id": str(self.tenant_id) if self.tenant_id else None,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            }

            if changes:
                log_data["changes"] = changes

            logger.info(f"[AUDIT] {action} {obj_type} {obj_id}: {reason}")

            # Call audit logger if provided
            if hasattr(self.audit_logger, "log"):
                self.audit_logger.log(**log_data)

        except Exception as e:
            logger.error(f"Failed to log audit entry: {e}")

    def __enter__(self) -> "AuditedSession":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            self.rollback()
        else:
            self.commit()


# =============================================================================
# POSTGRESQL RLS SETUP HELPERS
# =============================================================================


def generate_rls_policy_sql(
    table_name: str,
    tenant_column: str = "firm_id",
    policy_name: Optional[str] = None,
) -> str:
    """
    Generate SQL to create Row-Level Security policy for a table.

    Returns SQL that should be run during database setup/migration.

    NOTE: Run this as a database administrator with appropriate privileges.
    """
    policy_name = policy_name or f"{table_name}_tenant_isolation"

    return f"""
-- Enable RLS on table
ALTER TABLE {validate_identifier(table_name)} ENABLE ROW LEVEL SECURITY;

-- Force RLS for table owner too
ALTER TABLE {validate_identifier(table_name)} FORCE ROW LEVEL SECURITY;

-- Create policy for tenant isolation
CREATE POLICY {validate_identifier(policy_name)} ON {validate_identifier(table_name)}
    USING (
        {validate_identifier(tenant_column)} = current_setting('app.current_tenant_id')::uuid
        OR current_setting('app.is_superuser', true)::boolean = true
    );

-- Grant usage to application role
GRANT SELECT, INSERT, UPDATE, DELETE ON {validate_identifier(table_name)} TO app_user;
"""


def generate_set_tenant_sql(tenant_id: UUID) -> str:
    """Generate SQL to set the current tenant for RLS."""
    return f"SET app.current_tenant_id = '{tenant_id}';"


def generate_set_superuser_sql(is_superuser: bool = True) -> str:
    """Generate SQL to set superuser mode for RLS bypass."""
    return f"SET app.is_superuser = '{str(is_superuser).lower()}';"


@contextmanager
def tenant_context_for_session(
    session: Session,
    tenant_id: Optional[UUID] = None,
    is_superuser: bool = False,
):
    """
    Context manager to set tenant context for a database session.

    Usage:
        with tenant_context_for_session(session, tenant_id=firm_id):
            # All queries in this block are tenant-isolated
            clients = session.query(Client).all()
    """
    try:
        if tenant_id:
            session.execute(text(generate_set_tenant_sql(tenant_id)))
        if is_superuser:
            session.execute(text(generate_set_superuser_sql(True)))

        yield session

    finally:
        # Reset context
        session.execute(text("RESET app.current_tenant_id;"))
        session.execute(text("RESET app.is_superuser;"))


# =============================================================================
# QUERY LOGGING FOR DEBUGGING
# =============================================================================


def enable_query_logging(engine: Engine, log_level: int = logging.DEBUG) -> None:
    """
    Enable SQL query logging for debugging.

    WARNING: Only use in development! Logs may contain sensitive data.
    """
    import os

    if os.environ.get("APP_ENVIRONMENT", "development") == "production":
        logger.warning("Query logging should not be enabled in production")
        return

    @event.listens_for(engine, "before_cursor_execute")
    def log_query(conn, cursor, statement, parameters, context, executemany):
        logger.log(log_level, f"SQL: {statement}")
        if parameters:
            logger.log(log_level, f"Parameters: {parameters}")
