"""
Admin Panel API Router

Aggregates all admin-related routes into a single router.
Organized by domain for maintainability.

Route Structure:
- /api/v1/admin/           - Firm admin routes
- /api/v1/superadmin/      - Platform admin routes
"""

from fastapi import APIRouter
import logging

logger = logging.getLogger(__name__)

# Create main admin router
admin_router = APIRouter(tags=["Admin Panel"])

# Import and include domain-specific routers
try:
    from .dashboard_routes import router as dashboard_router
    admin_router.include_router(dashboard_router, prefix="/admin")
    logger.info("Admin dashboard routes enabled")
except ImportError as e:
    logger.warning(f"Dashboard routes not available: {e}")

try:
    from .team_routes import router as team_router
    admin_router.include_router(team_router, prefix="/admin")
    logger.info("Team management routes enabled")
except ImportError as e:
    logger.warning(f"Team routes not available: {e}")

try:
    from .billing_routes import router as billing_router
    admin_router.include_router(billing_router, prefix="/admin")
    logger.info("Billing routes enabled")
except ImportError as e:
    logger.warning(f"Billing routes not available: {e}")

try:
    from .settings_routes import router as settings_router
    admin_router.include_router(settings_router, prefix="/admin")
    logger.info("Settings routes enabled")
except ImportError as e:
    logger.warning(f"Settings routes not available: {e}")

try:
    from .auth_routes import router as auth_router
    admin_router.include_router(auth_router, prefix="/admin")
    logger.info("Auth routes enabled")
except ImportError as e:
    logger.warning(f"Auth routes not available: {e}")

try:
    from .compliance_routes import router as compliance_router
    admin_router.include_router(compliance_router, prefix="/admin")
    logger.info("Compliance & audit routes enabled")
except ImportError as e:
    logger.warning(f"Compliance routes not available: {e}")

try:
    from .client_routes import router as client_router
    admin_router.include_router(client_router, prefix="/admin")
    logger.info("Client management routes enabled")
except ImportError as e:
    logger.warning(f"Client routes not available: {e}")

try:
    from .workflow_routes import router as workflow_router
    admin_router.include_router(workflow_router, prefix="/admin")
    logger.info("Workflow management routes enabled")
except ImportError as e:
    logger.warning(f"Workflow routes not available: {e}")

try:
    from .alert_routes import router as alert_router
    admin_router.include_router(alert_router, prefix="/admin")
    logger.info("Alert routes enabled")
except ImportError as e:
    logger.warning(f"Alert routes not available: {e}")

try:
    from .superadmin_routes import router as superadmin_router
    admin_router.include_router(superadmin_router, prefix="/superadmin")
    logger.info("Superadmin routes enabled")
except ImportError as e:
    logger.warning(f"Superadmin routes not available: {e}")

try:
    from .rbac_routes import router as rbac_router
    admin_router.include_router(rbac_router, prefix="/admin")
    logger.info("RBAC management routes enabled")
except ImportError as e:
    logger.warning(f"RBAC routes not available: {e}")

try:
    from .platform_billing_routes import router as platform_billing_router
    admin_router.include_router(platform_billing_router, prefix="/superadmin")
    logger.info("Platform billing routes enabled")
except ImportError as e:
    logger.warning(f"Platform billing routes not available: {e}")


# =============================================================================
# HEALTH CHECK
# =============================================================================

@admin_router.get("/admin/health")
async def admin_health_check():
    """Admin panel health check endpoint."""
    return {
        "status": "healthy",
        "module": "admin_panel",
        "routes": {
            "dashboard": "active",
            "team": "active",
            "billing": "active",
            "settings": "active",
            "auth": "active",
            "compliance": "active",
            "clients": "active",
            "workflow": "active",
            "alerts": "active",
            "superadmin": "active",
            "rbac": "active",
            "platform_billing": "active",
        },
    }


# =============================================================================
# API DOCUMENTATION
# =============================================================================

@admin_router.get("/admin/docs/routes")
async def get_admin_route_documentation():
    """Get documentation of all admin panel routes."""
    return {
        "prefix": "/api/v1/admin",
        "domains": {
            "dashboard": {
                "description": "Firm dashboard and metrics",
                "endpoints": [
                    "GET /dashboard - Dashboard overview with metrics",
                    "GET /dashboard/alerts - AI-powered alerts",
                    "GET /dashboard/activity - Recent activity feed",
                ],
            },
            "team": {
                "description": "Team member management",
                "endpoints": [
                    "GET /team - List team members",
                    "POST /team - Add team member",
                    "GET /team/{user_id} - Get team member details",
                    "PUT /team/{user_id} - Update team member",
                    "DELETE /team/{user_id} - Deactivate team member",
                    "POST /team/invite - Send invitation",
                    "GET /team/invitations - List pending invitations",
                    "DELETE /team/invitations/{id} - Revoke invitation",
                ],
            },
            "billing": {
                "description": "Subscription and billing",
                "endpoints": [
                    "GET /billing/subscription - Current subscription",
                    "GET /billing/usage - Usage metrics",
                    "POST /billing/upgrade - Upgrade plan",
                    "POST /billing/downgrade - Downgrade plan",
                    "GET /billing/invoices - Invoice history",
                    "GET /billing/invoices/{id} - Invoice details",
                ],
            },
            "settings": {
                "description": "Firm settings and branding",
                "endpoints": [
                    "GET /settings - All settings",
                    "PUT /settings/profile - Update firm profile",
                    "PUT /settings/branding - Update branding",
                    "PUT /settings/security - Update security settings",
                    "GET /settings/api-keys - List API keys",
                    "POST /settings/api-keys - Create API key",
                    "DELETE /settings/api-keys/{id} - Revoke API key",
                ],
            },
            "auth": {
                "description": "Authentication",
                "endpoints": [
                    "POST /auth/login - Login",
                    "POST /auth/logout - Logout",
                    "POST /auth/refresh - Refresh token",
                    "POST /auth/password/change - Change password",
                    "POST /auth/password/reset - Request password reset",
                ],
            },
            "compliance": {
                "description": "Compliance & audit trail",
                "endpoints": [
                    "GET /audit/logs - Query audit logs",
                    "GET /audit/logs/{id} - Audit log details",
                    "GET /audit/activity/summary - Firm activity summary",
                    "GET /audit/activity/user/{id} - User activity",
                    "GET /compliance/report - Compliance report",
                    "GET /compliance/status - Compliance status",
                    "POST /audit/export - Export audit logs",
                ],
            },
            "clients": {
                "description": "Client management",
                "endpoints": [
                    "GET /clients - List clients",
                    "GET /clients/{id} - Client details",
                    "GET /clients/unassigned - Unassigned clients",
                    "POST /clients/assign - Assign clients",
                    "GET /clients/metrics - Client metrics",
                    "POST /clients/export - Export clients",
                ],
            },
            "workflow": {
                "description": "Workflow & task management",
                "endpoints": [
                    "GET /workflow/overview - Pipeline overview",
                    "GET /workflow/queue - Workflow queue",
                    "POST /workflow/{id}/advance - Advance stage",
                    "GET /tasks - List tasks",
                    "POST /tasks - Create task",
                    "GET /deadlines - Upcoming deadlines",
                    "GET /review-queue - Review queue",
                ],
            },
            "alerts": {
                "description": "AI-driven alerts & notifications",
                "endpoints": [
                    "GET /alerts - List alerts",
                    "GET /alerts/summary - Alert summary",
                    "POST /alerts/{id}/acknowledge - Acknowledge",
                    "POST /alerts/{id}/resolve - Resolve",
                    "POST /alerts/generate/all - Generate alerts",
                    "GET /notifications/preferences - Notification prefs",
                ],
            },
            "rbac": {
                "description": "Role-Based Access Control management",
                "endpoints": [
                    "GET /rbac/permissions - List all permissions",
                    "GET /rbac/roles - List roles (system + custom)",
                    "POST /rbac/roles - Create custom role",
                    "GET /rbac/roles/{role_id} - Get role details",
                    "PUT /rbac/roles/{role_id}/permissions - Update role permissions",
                    "DELETE /rbac/roles/{role_id} - Delete custom role",
                    "GET /rbac/users/{user_id}/roles - Get user roles",
                    "POST /rbac/users/{user_id}/roles - Assign role to user",
                    "DELETE /rbac/users/{user_id}/roles/{role_id} - Remove role",
                    "POST /rbac/users/{user_id}/permissions - Create permission override",
                    "POST /rbac/seed - Seed system permissions and roles",
                ],
            },
        },
        "superadmin_prefix": "/api/v1/superadmin",
        "superadmin_domains": {
            "firms": {
                "description": "Multi-firm management",
                "endpoints": [
                    "GET /firms - List all firms",
                    "GET /firms/{id} - Firm details",
                    "PUT /firms/{id} - Update firm",
                    "POST /firms/{id}/impersonate - Enter support mode",
                ],
            },
            "subscriptions": {
                "description": "Subscription management",
                "endpoints": [
                    "GET /subscriptions/metrics - Subscription metrics",
                    "GET /subscriptions/mrr - MRR breakdown",
                    "POST /subscriptions/{firm_id}/adjust - Manual adjustment",
                ],
            },
            "features": {
                "description": "Feature flag management",
                "endpoints": [
                    "GET /features - All feature flags",
                    "POST /features - Create flag",
                    "PUT /features/{id} - Update flag",
                    "POST /features/{id}/rollout - Adjust rollout",
                ],
            },
            "system": {
                "description": "System health",
                "endpoints": [
                    "GET /system/health - Service health",
                    "GET /system/errors - Error tracking",
                    "POST /system/announcements - System announcements",
                ],
            },
        },
    }
