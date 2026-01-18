"""
Admin Panel API Routes

Organized into domain-specific routers:
- dashboard_routes: Firm dashboard and metrics
- team_routes: Team member management
- billing_routes: Subscription and billing
- settings_routes: Firm settings and branding
- auth_routes: Authentication and session management
- compliance_routes: Audit trail and compliance reporting
- client_routes: Client management from admin perspective
- workflow_routes: Return workflow and task management
- alert_routes: AI-driven alerts and notifications
- superadmin_routes: Platform admin operations
"""

from .router import admin_router

__all__ = ["admin_router"]
