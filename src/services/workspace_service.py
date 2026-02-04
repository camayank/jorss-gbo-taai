"""
CPA Workspace Service - Multi-client management for tax preparers.

This service provides:
- Preparer registration and profile management
- Client list management (add, search, sort)
- Session management (create, resume, duplicate prior year)
- Dashboard metrics and status tracking

Phase 1-2 Implementation: Single preparer, many clients, no teams.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from enum import Enum

from sqlalchemy import create_engine, desc, asc, or_, and_
from sqlalchemy.orm import sessionmaker, Session as DBSession

from database.models import (
    PreparerRecord,
    ClientRecord,
    ClientSessionRecord,
    ClientStatusDB,
    TaxReturnRecord,
    hash_ssn,
)

from services.logging_config import get_logger

logger = get_logger(__name__)


class SortField(str, Enum):
    """Fields available for sorting client list."""
    NAME = "name"
    STATUS = "status"
    LAST_ACCESSED = "last_accessed"
    TAX_YEAR = "tax_year"
    REFUND = "refund"
    CREATED = "created"


class SortOrder(str, Enum):
    """Sort order."""
    ASC = "asc"
    DESC = "desc"


class WorkspaceService:
    """
    CPA Workspace Service for multi-client management.

    Provides CRUD operations for preparers, clients, and sessions.
    Enables dashboard display, search, and session resumption.
    """

    def __init__(self, db_url: str = "sqlite:///tax_returns.db"):
        """
        Initialize the workspace service.

        Args:
            db_url: Database connection URL
        """
        self._engine = create_engine(db_url, echo=False)
        self._Session = sessionmaker(bind=self._engine)
        self._logger = get_logger(__name__)

    def _get_session(self) -> DBSession:
        """Get a database session."""
        return self._Session()

    # =========================================================================
    # PREPARER MANAGEMENT
    # =========================================================================

    def register_preparer(
        self,
        email: str,
        first_name: str,
        last_name: str,
        firm_name: Optional[str] = None,
        credentials: Optional[List[str]] = None,
        license_state: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Register a new preparer (CPA).

        Args:
            email: Preparer's email (unique identifier)
            first_name: Preparer's first name
            last_name: Preparer's last name
            firm_name: Optional firm name for branding
            credentials: Optional list of credentials (CPA, EA, etc.)
            license_state: Optional primary state of licensure
            phone: Optional phone number

        Returns:
            Preparer profile dictionary
        """
        with self._get_session() as session:
            # Check if email already exists
            existing = session.query(PreparerRecord).filter(
                PreparerRecord.email == email
            ).first()
            if existing:
                raise ValueError(f"Preparer with email {email} already exists")

            preparer = PreparerRecord(
                preparer_id=uuid4(),
                email=email,
                first_name=first_name,
                last_name=last_name,
                firm_name=firm_name,
                credentials=credentials or [],
                license_state=license_state,
                phone=phone,
            )

            session.add(preparer)
            session.commit()

            self._logger.info(
                f"Registered preparer: {preparer.full_name}",
                extra={'extra_data': {'preparer_id': str(preparer.preparer_id)}}
            )

            return self._preparer_to_dict(preparer)

    def get_preparer(self, preparer_id: UUID) -> Optional[Dict[str, Any]]:
        """Get preparer by ID."""
        with self._get_session() as session:
            preparer = session.query(PreparerRecord).filter(
                PreparerRecord.preparer_id == preparer_id
            ).first()
            if preparer:
                return self._preparer_to_dict(preparer)
            return None

    def get_preparer_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get preparer by email."""
        with self._get_session() as session:
            preparer = session.query(PreparerRecord).filter(
                PreparerRecord.email == email
            ).first()
            if preparer:
                return self._preparer_to_dict(preparer)
            return None

    def update_preparer_branding(
        self,
        preparer_id: UUID,
        firm_name: Optional[str] = None,
        logo_url: Optional[str] = None,
        primary_color: Optional[str] = None,
        secondary_color: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update preparer branding for white-label (Phase 4)."""
        with self._get_session() as session:
            preparer = session.query(PreparerRecord).filter(
                PreparerRecord.preparer_id == preparer_id
            ).first()
            if not preparer:
                raise ValueError(f"Preparer not found: {preparer_id}")

            if firm_name is not None:
                preparer.firm_name = firm_name
            if logo_url is not None:
                preparer.logo_url = logo_url
            if primary_color is not None:
                preparer.primary_color = primary_color
            if secondary_color is not None:
                preparer.secondary_color = secondary_color

            session.commit()
            return self._preparer_to_dict(preparer)

    def record_preparer_login(self, preparer_id: UUID) -> None:
        """Record preparer login timestamp."""
        with self._get_session() as session:
            preparer = session.query(PreparerRecord).filter(
                PreparerRecord.preparer_id == preparer_id
            ).first()
            if preparer:
                preparer.last_login_at = datetime.utcnow()
                session.commit()

    # =========================================================================
    # CLIENT MANAGEMENT
    # =========================================================================

    def add_client(
        self,
        preparer_id: UUID,
        first_name: str,
        last_name: str,
        email: Optional[str] = None,
        external_id: Optional[str] = None,
        ssn: Optional[str] = None,
        phone: Optional[str] = None,
        street_address: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        zip_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add a new client to the preparer's workspace.

        Args:
            preparer_id: Preparer's ID
            first_name: Client's first name
            last_name: Client's last name
            email: Optional email
            external_id: Optional CPA's own client number
            ssn: Optional SSN (will be hashed)
            phone: Optional phone
            street_address: Optional address
            city: Optional city
            state: Optional state
            zip_code: Optional zip

        Returns:
            Client dictionary
        """
        with self._get_session() as session:
            # Verify preparer exists
            preparer = session.query(PreparerRecord).filter(
                PreparerRecord.preparer_id == preparer_id
            ).first()
            if not preparer:
                raise ValueError(f"Preparer not found: {preparer_id}")

            # Check external_id uniqueness for this preparer
            if external_id:
                existing = session.query(ClientRecord).filter(
                    ClientRecord.preparer_id == preparer_id,
                    ClientRecord.external_id == external_id
                ).first()
                if existing:
                    raise ValueError(f"Client with external_id {external_id} already exists")

            client = ClientRecord(
                client_id=uuid4(),
                preparer_id=preparer_id,
                first_name=first_name,
                last_name=last_name,
                email=email,
                external_id=external_id,
                ssn_hash=hash_ssn(ssn) if ssn else None,
                phone=phone,
                street_address=street_address,
                city=city,
                state=state,
                zip_code=zip_code,
            )

            session.add(client)
            session.commit()

            self._logger.info(
                f"Added client: {client.full_name}",
                extra={'extra_data': {
                    'client_id': str(client.client_id),
                    'preparer_id': str(preparer_id),
                }}
            )

            return self._client_to_dict(client)

    def get_client(self, client_id: UUID) -> Optional[Dict[str, Any]]:
        """Get client by ID."""
        with self._get_session() as session:
            client = session.query(ClientRecord).filter(
                ClientRecord.client_id == client_id
            ).first()
            if client:
                return self._client_to_dict(client)
            return None

    def list_clients(
        self,
        preparer_id: UUID,
        search: Optional[str] = None,
        status_filter: Optional[str] = None,
        tax_year: int = 2025,
        sort_by: SortField = SortField.LAST_ACCESSED,
        sort_order: SortOrder = SortOrder.DESC,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        List clients for a preparer with search, filter, and sort.

        Args:
            preparer_id: Preparer's ID
            search: Optional search string (name, email, external_id)
            status_filter: Optional status filter
            tax_year: Tax year for session info
            sort_by: Field to sort by
            sort_order: Sort order (asc/desc)
            limit: Maximum results
            offset: Pagination offset

        Returns:
            Dictionary with clients list and pagination info
        """
        with self._get_session() as session:
            # Base query - clients for this preparer
            query = session.query(ClientRecord).filter(
                ClientRecord.preparer_id == preparer_id,
                ClientRecord.is_active == True
            )

            # Apply search filter
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        ClientRecord.first_name.ilike(search_term),
                        ClientRecord.last_name.ilike(search_term),
                        ClientRecord.email.ilike(search_term),
                        ClientRecord.external_id.ilike(search_term),
                    )
                )

            # Get total count before pagination
            total_count = query.count()

            # Apply sorting
            if sort_by == SortField.NAME:
                order_col = ClientRecord.last_name
            elif sort_by == SortField.CREATED:
                order_col = ClientRecord.created_at
            else:
                order_col = ClientRecord.updated_at

            if sort_order == SortOrder.DESC:
                query = query.order_by(desc(order_col))
            else:
                query = query.order_by(asc(order_col))

            # Apply pagination with eager loading to prevent N+1 queries
            from database.query_helpers import client_with_sessions
            clients = query.options(
                *client_with_sessions()
            ).offset(offset).limit(limit).all()

            # Build session lookup from eagerly loaded data (no additional queries)
            client_list = []
            for client in clients:
                client_dict = self._client_to_dict(client)

                # Find session for tax year from already-loaded sessions (N+1 fix)
                sess = next(
                    (s for s in client.sessions if s.tax_year == tax_year),
                    None
                )

                if sess:
                    client_dict["session"] = self._session_to_dict(sess)
                else:
                    client_dict["session"] = None

                client_list.append(client_dict)

            return {
                "clients": client_list,
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + limit) < total_count,
            }

    def update_client(
        self,
        client_id: UUID,
        **updates
    ) -> Dict[str, Any]:
        """Update client information."""
        with self._get_session() as session:
            client = session.query(ClientRecord).filter(
                ClientRecord.client_id == client_id
            ).first()
            if not client:
                raise ValueError(f"Client not found: {client_id}")

            allowed_fields = [
                'first_name', 'last_name', 'email', 'phone',
                'external_id', 'street_address', 'city', 'state', 'zip_code'
            ]
            for field, value in updates.items():
                if field in allowed_fields:
                    setattr(client, field, value)

            if 'ssn' in updates and updates['ssn']:
                client.ssn_hash = hash_ssn(updates['ssn'])

            session.commit()
            return self._client_to_dict(client)

    def archive_client(self, client_id: UUID) -> bool:
        """Archive (soft delete) a client."""
        with self._get_session() as session:
            client = session.query(ClientRecord).filter(
                ClientRecord.client_id == client_id
            ).first()
            if client:
                client.is_active = False
                session.commit()
                return True
            return False

    # =========================================================================
    # SESSION MANAGEMENT (Resume, Duplicate Prior Year)
    # =========================================================================

    def create_session(
        self,
        client_id: UUID,
        preparer_id: UUID,
        tax_year: int = 2025,
    ) -> Dict[str, Any]:
        """
        Create a new client session for a tax year.

        Args:
            client_id: Client's ID
            preparer_id: Preparer's ID
            tax_year: Tax year for this session

        Returns:
            Session dictionary
        """
        with self._get_session() as session:
            # Check if session already exists
            existing = session.query(ClientSessionRecord).filter(
                ClientSessionRecord.client_id == client_id,
                ClientSessionRecord.tax_year == tax_year
            ).first()
            if existing:
                # Return existing session
                existing.last_accessed_at = datetime.utcnow()
                session.commit()
                return self._session_to_dict(existing)

            # Create new session
            client_session = ClientSessionRecord(
                session_id=uuid4(),
                client_id=client_id,
                preparer_id=preparer_id,
                tax_year=tax_year,
                status=ClientStatusDB.NEW,
            )

            session.add(client_session)
            session.commit()

            self._logger.info(
                f"Created session for client",
                extra={'extra_data': {
                    'session_id': str(client_session.session_id),
                    'client_id': str(client_id),
                    'tax_year': tax_year,
                }}
            )

            return self._session_to_dict(client_session)

    def get_session(self, session_id: UUID) -> Optional[Dict[str, Any]]:
        """Get session by ID."""
        with self._get_session() as session:
            sess = session.query(ClientSessionRecord).filter(
                ClientSessionRecord.session_id == session_id
            ).first()
            if sess:
                # Update last accessed
                sess.last_accessed_at = datetime.utcnow()
                session.commit()
                return self._session_to_dict(sess)
            return None

    def get_session_for_client(
        self,
        client_id: UUID,
        tax_year: int = 2025
    ) -> Optional[Dict[str, Any]]:
        """Get session for a client and tax year."""
        with self._get_session() as session:
            sess = session.query(ClientSessionRecord).filter(
                ClientSessionRecord.client_id == client_id,
                ClientSessionRecord.tax_year == tax_year
            ).first()
            if sess:
                sess.last_accessed_at = datetime.utcnow()
                session.commit()
                return self._session_to_dict(sess)
            return None

    def update_session_status(
        self,
        session_id: UUID,
        status: str,
    ) -> Dict[str, Any]:
        """Update session status."""
        with self._get_session() as session:
            sess = session.query(ClientSessionRecord).filter(
                ClientSessionRecord.session_id == session_id
            ).first()
            if not sess:
                raise ValueError(f"Session not found: {session_id}")

            sess.status = ClientStatusDB(status)
            sess.updated_at = datetime.utcnow()
            session.commit()
            return self._session_to_dict(sess)

    def update_session_metrics(
        self,
        session_id: UUID,
        estimated_refund: Optional[float] = None,
        estimated_tax_owed: Optional[float] = None,
        total_income: Optional[float] = None,
        potential_savings: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Update session metrics for dashboard display."""
        with self._get_session() as session:
            sess = session.query(ClientSessionRecord).filter(
                ClientSessionRecord.session_id == session_id
            ).first()
            if not sess:
                raise ValueError(f"Session not found: {session_id}")

            if estimated_refund is not None:
                sess.estimated_refund = estimated_refund
            if estimated_tax_owed is not None:
                sess.estimated_tax_owed = estimated_tax_owed
            if total_income is not None:
                sess.total_income = total_income
            if potential_savings is not None:
                sess.potential_savings = potential_savings

            sess.updated_at = datetime.utcnow()
            session.commit()
            return self._session_to_dict(sess)

    def link_return_to_session(
        self,
        session_id: UUID,
        return_id: UUID,
    ) -> Dict[str, Any]:
        """Link a tax return to a session."""
        with self._get_session() as session:
            sess = session.query(ClientSessionRecord).filter(
                ClientSessionRecord.session_id == session_id
            ).first()
            if not sess:
                raise ValueError(f"Session not found: {session_id}")

            sess.return_id = return_id
            sess.calculations_run += 1
            sess.updated_at = datetime.utcnow()
            session.commit()
            return self._session_to_dict(sess)

    def add_scenario_to_session(
        self,
        session_id: UUID,
        scenario_id: UUID,
    ) -> Dict[str, Any]:
        """Add a scenario to a session."""
        with self._get_session() as session:
            sess = session.query(ClientSessionRecord).filter(
                ClientSessionRecord.session_id == session_id
            ).first()
            if not sess:
                raise ValueError(f"Session not found: {session_id}")

            scenario_ids = sess.scenario_ids or []
            if str(scenario_id) not in scenario_ids:
                scenario_ids.append(str(scenario_id))
                sess.scenario_ids = scenario_ids
                sess.scenarios_analyzed += 1

            sess.updated_at = datetime.utcnow()
            session.commit()
            return self._session_to_dict(sess)

    def add_document_to_session(
        self,
        session_id: UUID,
        document_id: UUID,
    ) -> Dict[str, Any]:
        """Add a document to a session."""
        with self._get_session() as session:
            sess = session.query(ClientSessionRecord).filter(
                ClientSessionRecord.session_id == session_id
            ).first()
            if not sess:
                raise ValueError(f"Session not found: {session_id}")

            document_ids = sess.document_ids or []
            if str(document_id) not in document_ids:
                document_ids.append(str(document_id))
                sess.document_ids = document_ids
                sess.documents_processed += 1

            sess.updated_at = datetime.utcnow()
            session.commit()
            return self._session_to_dict(sess)

    def duplicate_prior_year(
        self,
        client_id: UUID,
        preparer_id: UUID,
        from_year: int,
        to_year: int,
    ) -> Dict[str, Any]:
        """
        Duplicate a prior year session to a new year.

        Copies notes and references, but starts with clean metrics.

        Args:
            client_id: Client's ID
            preparer_id: Preparer's ID
            from_year: Source tax year
            to_year: Target tax year

        Returns:
            New session dictionary
        """
        with self._get_session() as session:
            # Get prior year session
            prior_session = session.query(ClientSessionRecord).filter(
                ClientSessionRecord.client_id == client_id,
                ClientSessionRecord.tax_year == from_year
            ).first()

            if not prior_session:
                raise ValueError(f"No session found for year {from_year}")

            # Check if target year session exists
            existing = session.query(ClientSessionRecord).filter(
                ClientSessionRecord.client_id == client_id,
                ClientSessionRecord.tax_year == to_year
            ).first()
            if existing:
                raise ValueError(f"Session for year {to_year} already exists")

            # Create new session with prior year reference
            new_session = ClientSessionRecord(
                session_id=uuid4(),
                client_id=client_id,
                preparer_id=preparer_id,
                tax_year=to_year,
                status=ClientStatusDB.NEW,
                preparer_notes=f"Duplicated from {from_year}. Prior year notes: {prior_session.preparer_notes or 'None'}",
            )

            session.add(new_session)
            session.commit()

            self._logger.info(
                f"Duplicated prior year session",
                extra={'extra_data': {
                    'client_id': str(client_id),
                    'from_year': from_year,
                    'to_year': to_year,
                }}
            )

            return self._session_to_dict(new_session)

    def get_client_history(
        self,
        client_id: UUID,
    ) -> List[Dict[str, Any]]:
        """Get all sessions for a client (past years)."""
        with self._get_session() as session:
            sessions = session.query(ClientSessionRecord).filter(
                ClientSessionRecord.client_id == client_id
            ).order_by(desc(ClientSessionRecord.tax_year)).all()

            return [self._session_to_dict(s) for s in sessions]

    # =========================================================================
    # DASHBOARD METRICS
    # =========================================================================

    def get_dashboard_stats(
        self,
        preparer_id: UUID,
        tax_year: int = 2025,
    ) -> Dict[str, Any]:
        """
        Get dashboard statistics for a preparer.

        Returns counts by status, total clients, etc.
        """
        with self._get_session() as session:
            # Total clients
            total_clients = session.query(ClientRecord).filter(
                ClientRecord.preparer_id == preparer_id,
                ClientRecord.is_active == True
            ).count()

            # Sessions for this year
            sessions = session.query(ClientSessionRecord).filter(
                ClientSessionRecord.preparer_id == preparer_id,
                ClientSessionRecord.tax_year == tax_year
            ).all()

            # Count by status
            status_counts = {}
            for status in ClientStatusDB:
                status_counts[status.value] = sum(
                    1 for s in sessions if s.status == status
                )

            # Total potential savings
            total_savings = sum(
                float(s.potential_savings or 0) for s in sessions
            )

            # Recent activity (last 7 days)
            from datetime import timedelta
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent_activity = sum(
                1 for s in sessions if s.last_accessed_at and s.last_accessed_at > week_ago
            )

            return {
                "tax_year": tax_year,
                "total_clients": total_clients,
                "active_sessions": len(sessions),
                "status_breakdown": status_counts,
                "total_potential_savings": total_savings,
                "recent_activity_count": recent_activity,
            }

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    def _preparer_to_dict(self, preparer: PreparerRecord) -> Dict[str, Any]:
        """Convert preparer record to dictionary."""
        return {
            "preparer_id": str(preparer.preparer_id),
            "email": preparer.email,
            "first_name": preparer.first_name,
            "last_name": preparer.last_name,
            "full_name": preparer.full_name,
            "firm_name": preparer.firm_name,
            "credentials": preparer.credentials or [],
            "license_state": preparer.license_state,
            "phone": preparer.phone,
            "branding": {
                "logo_url": preparer.logo_url,
                "primary_color": preparer.primary_color,
                "secondary_color": preparer.secondary_color,
            },
            "default_tax_year": preparer.default_tax_year,
            "timezone": preparer.timezone,
            "is_active": preparer.is_active,
            "last_login_at": preparer.last_login_at.isoformat() if preparer.last_login_at else None,
            "created_at": preparer.created_at.isoformat() if preparer.created_at else None,
        }

    def _client_to_dict(self, client: ClientRecord) -> Dict[str, Any]:
        """Convert client record to dictionary."""
        return {
            "client_id": str(client.client_id),
            "preparer_id": str(client.preparer_id),
            "external_id": client.external_id,
            "first_name": client.first_name,
            "last_name": client.last_name,
            "full_name": client.full_name,
            "email": client.email,
            "phone": client.phone,
            "address": {
                "street": client.street_address,
                "city": client.city,
                "state": client.state,
                "zip_code": client.zip_code,
            },
            "is_active": client.is_active,
            "created_at": client.created_at.isoformat() if client.created_at else None,
            "updated_at": client.updated_at.isoformat() if client.updated_at else None,
        }

    def _session_to_dict(self, sess: ClientSessionRecord) -> Dict[str, Any]:
        """Convert session record to dictionary."""
        return {
            "session_id": str(sess.session_id),
            "client_id": str(sess.client_id),
            "preparer_id": str(sess.preparer_id),
            "tax_year": sess.tax_year,
            "status": sess.status.value if sess.status else "new",
            "return_id": str(sess.return_id) if sess.return_id else None,
            "scenario_ids": sess.scenario_ids or [],
            "recommendation_plan_id": str(sess.recommendation_plan_id) if sess.recommendation_plan_id else None,
            "document_ids": sess.document_ids or [],
            "progress": {
                "documents_processed": sess.documents_processed,
                "calculations_run": sess.calculations_run,
                "scenarios_analyzed": sess.scenarios_analyzed,
            },
            "metrics": {
                "estimated_refund": float(sess.estimated_refund) if sess.estimated_refund else None,
                "estimated_tax_owed": float(sess.estimated_tax_owed) if sess.estimated_tax_owed else None,
                "total_income": float(sess.total_income) if sess.total_income else None,
                "potential_savings": float(sess.potential_savings) if sess.potential_savings else None,
            },
            "preparer_notes": sess.preparer_notes,
            "created_at": sess.created_at.isoformat() if sess.created_at else None,
            "updated_at": sess.updated_at.isoformat() if sess.updated_at else None,
            "last_accessed_at": sess.last_accessed_at.isoformat() if sess.last_accessed_at else None,
        }


# Singleton instance
_workspace_service: Optional[WorkspaceService] = None


def get_workspace_service(db_url: str = "sqlite:///tax_returns.db") -> WorkspaceService:
    """Get or create the workspace service instance."""
    global _workspace_service
    if _workspace_service is None:
        _workspace_service = WorkspaceService(db_url=db_url)
    return _workspace_service
