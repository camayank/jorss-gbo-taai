"""
Tests for CPA Workspace Service - Multi-client management.
"""

import pytest
import os
import sys
from uuid import uuid4
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestPreparerModel:
    """Tests for Preparer domain model."""

    def test_create_preparer(self):
        """Test creating a preparer."""
        from domain.aggregates import Preparer

        preparer = Preparer(
            first_name="John",
            last_name="Smith",
            email="john.smith@example.com",
            firm_name="Smith Tax Advisory",
            credentials=["CPA", "EA"],
            license_state="CA",
        )

        assert preparer.first_name == "John"
        assert preparer.last_name == "Smith"
        assert preparer.full_name == "John Smith"
        assert preparer.display_name == "John Smith, CPA, EA"
        assert preparer.firm_name == "Smith Tax Advisory"
        assert preparer.is_active is True

    def test_preparer_client_management(self):
        """Test adding/removing clients from preparer."""
        from domain.aggregates import Preparer

        preparer = Preparer(
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
        )

        client_id = uuid4()
        preparer.add_client(client_id)

        assert client_id in preparer.client_ids
        assert preparer.client_count == 1

        # Remove client
        removed = preparer.remove_client(client_id)
        assert removed is True
        assert client_id not in preparer.client_ids
        assert preparer.client_count == 0

    def test_preparer_profile_dict(self):
        """Test converting preparer to dictionary."""
        from domain.aggregates import Preparer

        preparer = Preparer(
            first_name="Test",
            last_name="Preparer",
            email="test@example.com",
            firm_name="Test Firm",
        )

        profile = preparer.to_profile_dict()

        assert profile["name"] == "Test Preparer"
        assert profile["email"] == "test@example.com"
        assert profile["firm_name"] == "Test Firm"
        assert "branding" in profile


class TestClientSessionModel:
    """Tests for ClientSession domain model."""

    def test_create_client_session(self):
        """Test creating a client session."""
        from domain.aggregates import ClientSession, ClientStatus

        session = ClientSession(
            client_id=uuid4(),
            preparer_id=uuid4(),
            tax_year=2025,
        )

        assert session.tax_year == 2025
        assert session.status == ClientStatus.NEW
        assert session.documents_processed == 0
        assert session.scenarios_analyzed == 0

    def test_session_add_document(self):
        """Test adding a document to session."""
        from domain.aggregates import ClientSession

        session = ClientSession(
            client_id=uuid4(),
            preparer_id=uuid4(),
            tax_year=2025,
        )

        doc_id = uuid4()
        session.add_document(doc_id)

        assert doc_id in session.document_ids
        assert session.documents_processed == 1

        # Adding same document again shouldn't duplicate
        session.add_document(doc_id)
        assert session.documents_processed == 1

    def test_session_add_scenario(self):
        """Test adding a scenario to session."""
        from domain.aggregates import ClientSession

        session = ClientSession(
            client_id=uuid4(),
            preparer_id=uuid4(),
            tax_year=2025,
        )

        scenario_id = uuid4()
        session.add_scenario(scenario_id)

        assert scenario_id in session.scenario_ids
        assert session.scenarios_analyzed == 1

    def test_session_update_metrics(self):
        """Test updating session metrics."""
        from domain.aggregates import ClientSession

        session = ClientSession(
            client_id=uuid4(),
            preparer_id=uuid4(),
            tax_year=2025,
        )

        session.update_metrics(
            refund=5000.0,
            income=75000.0,
            savings=1200.0,
        )

        assert session.estimated_refund == 5000.0
        assert session.total_income == 75000.0
        assert session.potential_savings == 1200.0

    def test_session_to_list_item(self):
        """Test converting session to list item for dashboard."""
        from domain.aggregates import ClientSession

        session = ClientSession(
            client_id=uuid4(),
            preparer_id=uuid4(),
            tax_year=2025,
        )
        session.update_metrics(refund=3000.0, savings=500.0)

        list_item = session.to_list_item()

        assert list_item["tax_year"] == 2025
        assert list_item["status"] == "new"
        assert list_item["estimated_refund"] == 3000.0
        assert list_item["potential_savings"] == 500.0


class TestClientStatusEnum:
    """Tests for ClientStatus enum."""

    def test_client_status_values(self):
        """Test all client status values exist."""
        from domain.aggregates import ClientStatus

        expected_statuses = [
            "new", "in_progress", "ready_for_review",
            "reviewed", "delivered", "archived"
        ]

        for status in expected_statuses:
            assert hasattr(ClientStatus, status.upper())


class TestDatabaseModels:
    """Tests for database models."""

    def test_preparer_record_exists(self):
        """Test PreparerRecord model exists and has expected fields."""
        from database.models import PreparerRecord

        assert hasattr(PreparerRecord, 'preparer_id')
        assert hasattr(PreparerRecord, 'email')
        assert hasattr(PreparerRecord, 'first_name')
        assert hasattr(PreparerRecord, 'last_name')
        assert hasattr(PreparerRecord, 'firm_name')
        assert hasattr(PreparerRecord, 'credentials')

    def test_client_record_exists(self):
        """Test ClientRecord model exists and has expected fields."""
        from database.models import ClientRecord

        assert hasattr(ClientRecord, 'client_id')
        assert hasattr(ClientRecord, 'preparer_id')
        assert hasattr(ClientRecord, 'first_name')
        assert hasattr(ClientRecord, 'last_name')
        assert hasattr(ClientRecord, 'external_id')

    def test_client_session_record_exists(self):
        """Test ClientSessionRecord model exists and has expected fields."""
        from database.models import ClientSessionRecord

        assert hasattr(ClientSessionRecord, 'session_id')
        assert hasattr(ClientSessionRecord, 'client_id')
        assert hasattr(ClientSessionRecord, 'preparer_id')
        assert hasattr(ClientSessionRecord, 'tax_year')
        assert hasattr(ClientSessionRecord, 'status')
        assert hasattr(ClientSessionRecord, 'estimated_refund')
        assert hasattr(ClientSessionRecord, 'potential_savings')


class TestWorkspaceServiceImport:
    """Tests for workspace service module."""

    def test_workspace_service_import(self):
        """Test workspace service can be imported."""
        from services.workspace_service import WorkspaceService, get_workspace_service

        assert WorkspaceService is not None
        assert get_workspace_service is not None

    def test_sort_fields_exist(self):
        """Test sort fields enum exists."""
        from services.workspace_service import SortField, SortOrder

        assert SortField.NAME
        assert SortField.STATUS
        assert SortField.LAST_ACCESSED
        assert SortOrder.ASC
        assert SortOrder.DESC


class TestWorkspaceAPIImport:
    """Tests for workspace API module."""

    def test_workspace_api_router_import(self):
        """Test workspace API router can be imported."""
        from web.workspace_api import router

        assert router is not None

    def test_request_models_import(self):
        """Test request models can be imported."""
        from web.workspace_api import (
            PreparerRegisterRequest,
            ClientCreateRequest,
            SessionCreateRequest,
        )

        assert PreparerRegisterRequest is not None
        assert ClientCreateRequest is not None
        assert SessionCreateRequest is not None


class TestDomainExports:
    """Tests for domain module exports."""

    def test_preparer_exported(self):
        """Test Preparer is exported from domain."""
        from domain import Preparer, ClientSession, ClientStatus

        assert Preparer is not None
        assert ClientSession is not None
        assert ClientStatus is not None
