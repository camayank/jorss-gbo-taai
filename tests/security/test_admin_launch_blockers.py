"""Security regressions for admin launch blockers."""

import importlib
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from admin_panel.api.ticket_routes import ticket_router
from admin_panel.auth.rbac import get_current_user
from admin_panel.support.ticket_service import ticket_service
from rbac.context import AuthContext
from rbac.roles import Role


def _firm_user_context(*, role: Role, firm_id: UUID) -> AuthContext:
    """Create a firm-scoped authenticated context."""
    return AuthContext.for_firm_user(
        user_id=uuid4(),
        email=f"{role.value}@example.com",
        name=f"{role.value.title()} User",
        role=role,
        firm_id=firm_id,
        firm_name="Test Firm",
    )


def _platform_user_context(*, role: Role = Role.SUPPORT) -> AuthContext:
    """Create a platform-scoped authenticated context."""
    return AuthContext.for_platform_admin(
        user_id=uuid4(),
        email=f"{role.value}@platform.test",
        name=f"{role.value.title()} Platform User",
        role=role,
    )


@pytest.fixture(autouse=True)
def _reset_ticket_store():
    """Reset in-memory ticket storage between tests."""
    ticket_service._tickets.clear()
    ticket_service._ticket_counter = 0
    yield
    ticket_service._tickets.clear()
    ticket_service._ticket_counter = 0


@pytest.fixture
def ticket_app() -> FastAPI:
    """App with admin ticket routes mounted."""
    app = FastAPI()
    app.include_router(ticket_router, prefix="/api/v1/admin")
    return app


@pytest.fixture
def ticket_client(ticket_app: FastAPI) -> TestClient:
    """HTTP test client for ticket routes."""
    return TestClient(ticket_app)


def _set_current_user(app: FastAPI, user: AuthContext) -> None:
    """Override auth dependency for route tests."""
    app.dependency_overrides[get_current_user] = lambda: user


def _create_ticket_payload(**overrides) -> dict:
    payload = {
        "subject": "Need help",
        "description": "Unable to upload documents",
        "customer_email": "client@example.com",
        "customer_name": "Client One",
        "category": "technical",
        "priority": "normal",
    }
    payload.update(overrides)
    return payload


def test_admin_ticket_routes_require_auth(ticket_client: TestClient):
    """Anonymous callers must be rejected."""
    response = ticket_client.get("/api/v1/admin/tickets")
    assert response.status_code == 401


def test_admin_ticket_routes_reject_role_mismatch(
    ticket_app: FastAPI,
    ticket_client: TestClient,
):
    """Client roles cannot access internal admin ticket APIs."""
    client_ctx = AuthContext.for_client(
        user_id=uuid4(),
        email="client@test.com",
        name="Client User",
        firm_id=uuid4(),
        firm_name="Client Firm",
    )
    _set_current_user(ticket_app, client_ctx)

    response = ticket_client.post(
        "/api/v1/admin/tickets",
        json=_create_ticket_payload(),
    )
    assert response.status_code == 403
    assert "not allowed" in response.json()["detail"].lower()


def test_admin_ticket_routes_block_cross_firm_access(
    ticket_app: FastAPI,
    ticket_client: TestClient,
):
    """Firm users must not read tickets from other firms."""
    firm_a = uuid4()
    firm_b = uuid4()

    _set_current_user(ticket_app, _firm_user_context(role=Role.PARTNER, firm_id=firm_a))
    create_response = ticket_client.post(
        "/api/v1/admin/tickets",
        json=_create_ticket_payload(),
    )
    assert create_response.status_code == 200
    ticket_id = create_response.json()["ticket"]["id"]

    _set_current_user(ticket_app, _firm_user_context(role=Role.PARTNER, firm_id=firm_b))
    get_response = ticket_client.get(f"/api/v1/admin/tickets/{ticket_id}")
    assert get_response.status_code == 403
    assert "access denied" in get_response.json()["detail"].lower()


def test_admin_ticket_routes_block_cross_firm_create_spoofing(
    ticket_app: FastAPI,
    ticket_client: TestClient,
):
    """Firm users cannot create tickets scoped to another firm."""
    firm_a = uuid4()
    firm_b = uuid4()
    _set_current_user(ticket_app, _firm_user_context(role=Role.STAFF, firm_id=firm_a))

    response = ticket_client.post(
        "/api/v1/admin/tickets",
        json=_create_ticket_payload(firm_id=str(firm_b)),
    )
    assert response.status_code == 403
    assert "access denied to this firm" in response.json()["detail"].lower()


def test_admin_ticket_routes_allow_platform_cross_firm_create(
    ticket_app: FastAPI,
    ticket_client: TestClient,
):
    """Platform roles can create tickets for arbitrary firms."""
    _set_current_user(ticket_app, _platform_user_context(role=Role.SUPPORT))

    target_firm = uuid4()
    response = ticket_client.post(
        "/api/v1/admin/tickets",
        json=_create_ticket_payload(firm_id=str(target_firm)),
    )
    assert response.status_code == 200
    assert response.json()["ticket"]["firm_id"] == str(target_firm)


def test_admin_rbac_routes_use_canonical_prefix_in_openapi():
    """
    Canonical path should be /api/v1/admin/rbac/*.

    Legacy /api/v1/admin/admin/rbac/* remains runtime alias but hidden in schema.
    """
    import admin_panel.api.router as admin_router_module

    admin_router_module = importlib.reload(admin_router_module)

    app = FastAPI()
    app.include_router(admin_router_module.admin_router, prefix="/api/v1")

    paths = app.openapi()["paths"].keys()
    assert "/api/v1/admin/rbac/permissions" in paths
    assert "/api/v1/admin/admin/rbac/permissions" not in paths

    runtime_paths = {route.path for route in app.routes}
    assert "/api/v1/admin/admin/rbac/permissions" in runtime_paths
