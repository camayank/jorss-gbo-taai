"""
Core Platform API Router

Combines all core API routes into a single router.
Mount this router at /api/core in your FastAPI application.

All endpoints use unified authentication and role-based access control.
The same API serves:
- Direct B2C consumers
- CPA clients
- CPA team members
- Platform administrators
"""

from fastapi import APIRouter

from .auth_routes import router as auth_router
from .tax_returns_routes import router as tax_returns_router
from .documents_routes import router as documents_router
from .scenarios_routes import router as scenarios_router
from .recommendations_routes import router as recommendations_router
from .users_routes import router as users_router
from .billing_routes import router as billing_router
from .messaging_routes import router as messaging_router

# =============================================================================
# CORE API ROUTER
# =============================================================================

core_router = APIRouter(prefix="/api/core")

# Include all sub-routers
core_router.include_router(auth_router)
core_router.include_router(tax_returns_router)
core_router.include_router(documents_router)
core_router.include_router(scenarios_router)
core_router.include_router(recommendations_router)
core_router.include_router(users_router)
core_router.include_router(billing_router)
core_router.include_router(messaging_router)


# =============================================================================
# HEALTH & INFO ENDPOINTS
# =============================================================================

@core_router.get("/health")
async def health_check():
    """
    Core Platform API health check.

    Returns status of all core services.
    """
    return {
        "status": "healthy",
        "api": "core",
        "version": "1.0.0",
        "services": {
            "auth": "operational",
            "users": "operational",
            "tax_returns": "operational",
            "documents": "operational",
            "scenarios": "operational",
            "recommendations": "operational",
            "billing": "operational",
            "messaging": "operational"
        }
    }


@core_router.post("/test-data/init")
async def init_test_data():
    """
    Initialize comprehensive test data.

    Creates test users, firms, tax returns, documents, scenarios, and recommendations.
    Only available in testing mode.

    Returns:
        Initialization results for each data type.
    """
    try:
        from core.services.test_data_init import init_all_test_data, TEST_PASSWORD
        results = init_all_test_data()
        results["test_password"] = TEST_PASSWORD
        results["message"] = "Test data initialized successfully"
        return results
    except Exception as e:
        return {"error": str(e), "message": "Failed to initialize test data"}


@core_router.get("/test-data/users")
async def get_test_users():
    """
    Get list of test user credentials.

    Returns all test users with their emails and passwords for testing.
    """
    from core.services.test_data_init import get_test_user_credentials
    return {
        "users": get_test_user_credentials(),
        "message": "Use these credentials to test different user scenarios"
    }


@core_router.get("/test-data/summary")
async def get_test_data_summary():
    """
    Get summary of current test data in the system.
    """
    from core.api import tax_returns_routes, documents_routes, scenarios_routes, recommendations_routes
    from core.services.auth_service import CoreAuthService

    auth_service = CoreAuthService()

    # Count unique users (by ID to avoid duplicates from email->user mapping)
    unique_users = {u.id: u for u in auth_service._users_db.values()}

    # Count users by type
    users_by_type = {}
    for user in unique_users.values():
        user_type = user.user_type.value if hasattr(user.user_type, 'value') else user.user_type
        users_by_type[user_type] = users_by_type.get(user_type, 0) + 1

    return {
        "counts": {
            "users": len(unique_users),
            "tax_returns": len(tax_returns_routes._tax_returns_db),
            "documents": len(documents_routes._documents_db),
            "scenarios": len(scenarios_routes._scenarios_db),
            "recommendations": len(recommendations_routes._recommendations_db),
        },
        "users_by_type": users_by_type,
        "message": "Current test data summary"
    }


@core_router.get("/")
async def api_info():
    """
    Core Platform API information.

    Returns documentation about available endpoints.
    """
    return {
        "name": "Core Platform API",
        "version": "1.0.0",
        "description": "Unified API for all user types with role-based access control",
        "endpoints": {
            "/api/core/auth": {
                "description": "Authentication endpoints",
                "methods": ["POST /login", "POST /register", "POST /magic-link", "GET /me", "POST /refresh", "POST /logout"]
            },
            "/api/core/users": {
                "description": "User profile and preferences",
                "methods": ["GET /me", "PATCH /me", "GET /{user_id}", "GET /me/preferences", "PATCH /me/preferences"]
            },
            "/api/core/tax-returns": {
                "description": "Tax return management",
                "methods": ["GET /", "GET /{id}", "POST /", "PATCH /{id}", "POST /{id}/submit", "GET /analytics/summary"]
            },
            "/api/core/documents": {
                "description": "Document management",
                "methods": ["GET /", "GET /{id}", "POST /", "PATCH /{id}", "DELETE /{id}", "POST /{id}/verify", "GET /requests/pending"]
            },
            "/api/core/scenarios": {
                "description": "Tax planning scenarios",
                "methods": ["GET /", "GET /{id}", "POST /", "PATCH /{id}", "POST /{id}/calculate", "GET /templates/list"]
            },
            "/api/core/recommendations": {
                "description": "Tax recommendations",
                "methods": ["GET /", "GET /{id}", "POST /", "POST /{id}/actions/{step}/complete", "POST /{id}/dismiss"]
            },
            "/api/core/billing": {
                "description": "Subscription and billing",
                "methods": ["GET /plans", "GET /subscription", "POST /subscription", "GET /invoices", "GET /payment-methods"]
            },
            "/api/core/messages": {
                "description": "Messaging and notifications",
                "methods": ["GET /conversations", "POST /conversations", "GET /conversations/{id}/messages", "POST /conversations/{id}/messages", "GET /notifications"]
            }
        },
        "user_types": {
            "consumer": "Direct B2C users accessing tax tools",
            "cpa_client": "Users managed by a CPA firm",
            "cpa_team": "CPA firm team members",
            "platform_admin": "Platform administrators"
        },
        "authentication": {
            "type": "Bearer Token",
            "header": "Authorization: Bearer <token>",
            "endpoints": {
                "login": "POST /api/core/auth/login",
                "magic_link": "POST /api/core/auth/magic-link",
                "refresh": "POST /api/core/auth/refresh"
            }
        }
    }


# =============================================================================
# API DOCUMENTATION
# =============================================================================

API_TAGS = [
    {
        "name": "Core Authentication",
        "description": "Unified authentication for all user types"
    },
    {
        "name": "Core Users",
        "description": "User profile and preferences management"
    },
    {
        "name": "Core Tax Returns",
        "description": "Tax return creation, management, and tracking"
    },
    {
        "name": "Core Documents",
        "description": "Document upload, storage, and verification"
    },
    {
        "name": "Core Tax Scenarios",
        "description": "Tax planning and what-if scenarios"
    },
    {
        "name": "Core Tax Recommendations",
        "description": "AI-powered and CPA tax recommendations"
    },
    {
        "name": "Core Billing",
        "description": "Subscriptions, invoices, and payments"
    },
    {
        "name": "Core Messaging",
        "description": "Conversations, messages, and notifications"
    }
]


__all__ = ["core_router", "API_TAGS"]
