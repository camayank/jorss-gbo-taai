"""
Database Query Helpers

Provides reusable eager loading patterns to prevent N+1 queries.

Usage:
    from database.query_helpers import (
        tax_return_with_income,
        client_with_sessions,
        TaxReturnListOptions,
    )

    # Get returns with all income data eagerly loaded
    returns = session.query(TaxReturnRecord).options(
        *tax_return_with_income()
    ).filter(...)

    # Get clients with their sessions
    clients = session.query(ClientRecord).options(
        *client_with_sessions()
    ).filter(...)
"""

from typing import List, Any
from sqlalchemy.orm import (
    selectinload,
    joinedload,
    Load,
    contains_eager,
    subqueryload,
)


def tax_return_with_income() -> List[Any]:
    """
    Eager loading options for tax returns with income data.

    Use when displaying return summaries that need income totals.

    Returns:
        List of SQLAlchemy loading options
    """
    from database.models import TaxReturnRecord

    return [
        selectinload(TaxReturnRecord.taxpayer),
        selectinload(TaxReturnRecord.income_records),
        selectinload(TaxReturnRecord.w2_records),
        selectinload(TaxReturnRecord.form1099_records),
    ]


def tax_return_with_all_forms() -> List[Any]:
    """
    Eager loading options for tax returns with all form data.

    Use when generating PDF exports or full return views.

    Returns:
        List of SQLAlchemy loading options
    """
    from database.models import TaxReturnRecord

    return [
        selectinload(TaxReturnRecord.taxpayer),
        selectinload(TaxReturnRecord.income_records),
        selectinload(TaxReturnRecord.w2_records),
        selectinload(TaxReturnRecord.form1099_records),
        selectinload(TaxReturnRecord.deduction_records),
        selectinload(TaxReturnRecord.credit_records),
        selectinload(TaxReturnRecord.dependent_records),
        selectinload(TaxReturnRecord.state_returns),
    ]


def tax_return_for_calculation() -> List[Any]:
    """
    Eager loading options for tax calculation.

    Loads all data needed for tax computation in a single query batch.

    Returns:
        List of SQLAlchemy loading options
    """
    from database.models import TaxReturnRecord

    return [
        selectinload(TaxReturnRecord.taxpayer),
        selectinload(TaxReturnRecord.income_records),
        selectinload(TaxReturnRecord.w2_records),
        selectinload(TaxReturnRecord.form1099_records),
        selectinload(TaxReturnRecord.deduction_records),
        selectinload(TaxReturnRecord.credit_records),
        selectinload(TaxReturnRecord.dependent_records),
        selectinload(TaxReturnRecord.computation_worksheets),
    ]


def tax_return_list_minimal() -> List[Any]:
    """
    Minimal eager loading for list views.

    Only loads taxpayer for display name - other relationships
    are loaded on demand.

    Returns:
        List of SQLAlchemy loading options
    """
    from database.models import TaxReturnRecord

    return [
        selectinload(TaxReturnRecord.taxpayer),
    ]


def client_with_sessions() -> List[Any]:
    """
    Eager loading options for clients with their sessions.

    Use when displaying client lists with session counts/status.

    Returns:
        List of SQLAlchemy loading options
    """
    from database.models import ClientRecord

    return [
        selectinload(ClientRecord.sessions),
    ]


def client_session_with_return() -> List[Any]:
    """
    Eager loading options for sessions with tax return data.

    Use when displaying session details with return summary.

    Returns:
        List of SQLAlchemy loading options
    """
    from database.models import ClientSessionRecord, TaxReturnRecord

    return [
        selectinload(ClientSessionRecord.client),
        selectinload(ClientSessionRecord.tax_return).selectinload(
            TaxReturnRecord.taxpayer
        ),
    ]


def preparer_with_workload() -> List[Any]:
    """
    Eager loading options for preparer workload views.

    Loads clients and sessions for workload dashboards.

    Returns:
        List of SQLAlchemy loading options
    """
    from database.models import PreparerRecord

    return [
        selectinload(PreparerRecord.clients),
        selectinload(PreparerRecord.client_sessions),
    ]


# =============================================================================
# QUERY BUILDERS - Higher level helpers for common patterns
# =============================================================================

class TaxReturnListOptions:
    """
    Configurable options for tax return list queries.

    Example:
        options = TaxReturnListOptions(
            include_taxpayer=True,
            include_income=True,
        )
        returns = session.query(TaxReturnRecord).options(
            *options.get_loading_options()
        ).all()
    """

    def __init__(
        self,
        include_taxpayer: bool = True,
        include_income: bool = False,
        include_deductions: bool = False,
        include_credits: bool = False,
        include_dependents: bool = False,
        include_state_returns: bool = False,
    ):
        self.include_taxpayer = include_taxpayer
        self.include_income = include_income
        self.include_deductions = include_deductions
        self.include_credits = include_credits
        self.include_dependents = include_dependents
        self.include_state_returns = include_state_returns

    def get_loading_options(self) -> List[Any]:
        """Get SQLAlchemy loading options based on configuration."""
        from database.models import TaxReturnRecord

        options = []

        if self.include_taxpayer:
            options.append(selectinload(TaxReturnRecord.taxpayer))

        if self.include_income:
            options.extend([
                selectinload(TaxReturnRecord.income_records),
                selectinload(TaxReturnRecord.w2_records),
                selectinload(TaxReturnRecord.form1099_records),
            ])

        if self.include_deductions:
            options.append(selectinload(TaxReturnRecord.deduction_records))

        if self.include_credits:
            options.append(selectinload(TaxReturnRecord.credit_records))

        if self.include_dependents:
            options.append(selectinload(TaxReturnRecord.dependent_records))

        if self.include_state_returns:
            options.append(selectinload(TaxReturnRecord.state_returns))

        return options


# =============================================================================
# BATCH LOADING UTILITIES
# =============================================================================

def batch_load_returns_by_ids(session, return_ids: List[str], include_income: bool = True):
    """
    Efficiently load multiple tax returns by ID.

    Args:
        session: SQLAlchemy session
        return_ids: List of return UUIDs
        include_income: Whether to include income records

    Returns:
        List of TaxReturnRecord with eager-loaded relationships
    """
    from database.models import TaxReturnRecord

    if not return_ids:
        return []

    options = tax_return_with_income() if include_income else tax_return_list_minimal()

    return session.query(TaxReturnRecord).options(
        *options
    ).filter(
        TaxReturnRecord.return_id.in_(return_ids)
    ).all()


def batch_load_clients_by_preparer(session, preparer_id: str, active_only: bool = True):
    """
    Efficiently load all clients for a preparer.

    Args:
        session: SQLAlchemy session
        preparer_id: Preparer UUID
        active_only: Only include active clients

    Returns:
        List of ClientRecord with eager-loaded sessions
    """
    from database.models import ClientRecord

    query = session.query(ClientRecord).options(
        *client_with_sessions()
    ).filter(
        ClientRecord.preparer_id == preparer_id
    )

    if active_only:
        query = query.filter(ClientRecord.is_active == True)

    return query.all()
