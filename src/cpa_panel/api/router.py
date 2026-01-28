"""
CPA Panel API Router

Aggregates all domain-specific routers into a single CPA panel API.

Domain Routers:
- workflow_routes: Status, approval, queue management
- analysis_routes: Delta analysis, tax drivers, scenarios
- notes_routes: CPA review notes
- insights_routes: CPA insights and checklists
- lead_routes: Lead state management and signals
- exposure_routes: Prospect-safe discovery exposure
- staff_routes: Staff assignment and management
- engagement_routes: Engagement letters
- client_visibility_routes: Client visibility surface
- practice_intelligence_routes: Practice analytics (3 metrics only)

All endpoints are prefixed with /api/cpa when included in the main app.
"""

from fastapi import APIRouter
import logging

logger = logging.getLogger(__name__)

# Create main CPA router
cpa_router = APIRouter(prefix="/cpa", tags=["CPA Panel"])

# Import domain-specific routers
from .workflow_routes import workflow_router
from .analysis_routes import analysis_router
from .notes_routes import notes_router
from .insights_routes import insights_router
from .lead_routes import lead_router
from .exposure_routes import exposure_router

# Import additional routers with error handling (may not exist yet)
try:
    from .staff_routes import router as staff_router
    cpa_router.include_router(staff_router)
    logger.info("Staff routes enabled")
except ImportError as e:
    logger.warning(f"Staff routes not available: {e}")

try:
    from .engagement_routes import router as engagement_router
    cpa_router.include_router(engagement_router)
    logger.info("Engagement routes enabled")
except ImportError as e:
    logger.warning(f"Engagement routes not available: {e}")

try:
    from .client_visibility_routes import router as client_visibility_router
    cpa_router.include_router(client_visibility_router)
    logger.info("Client visibility routes enabled")
except ImportError as e:
    logger.warning(f"Client visibility routes not available: {e}")

try:
    from .practice_intelligence_routes import router as intelligence_router
    cpa_router.include_router(intelligence_router)
    logger.info("Practice intelligence routes enabled")
except ImportError as e:
    logger.warning(f"Practice intelligence routes not available: {e}")

try:
    from .aggregated_insights_routes import router as aggregated_insights_router
    cpa_router.include_router(aggregated_insights_router)
    logger.info("Aggregated insights routes enabled")
except ImportError as e:
    logger.warning(f"Aggregated insights routes not available: {e}")

# NEW: Optimizer routes - Credit, deduction, filing status, entity, strategy
try:
    from .optimizer_routes import optimizer_router
    cpa_router.include_router(optimizer_router)
    logger.info("Optimizer routes enabled")
except ImportError as e:
    logger.warning(f"Optimizer routes not available: {e}")

# NEW: Scenario analysis routes - What-if analysis
try:
    from .scenario_routes import scenario_router
    cpa_router.include_router(scenario_router)
    logger.info("Scenario routes enabled")
except ImportError as e:
    logger.warning(f"Scenario routes not available: {e}")

# NEW: Pipeline routes - Lead pipeline and metrics
try:
    from .pipeline_routes import pipeline_router
    cpa_router.include_router(pipeline_router)
    logger.info("Pipeline routes enabled")
except ImportError as e:
    logger.warning(f"Pipeline routes not available: {e}")

# NEW: Document routes - Upload and OCR
try:
    from .document_routes import document_router
    cpa_router.include_router(document_router)
    logger.info("Document routes enabled")
except ImportError as e:
    logger.warning(f"Document routes not available: {e}")

# NEW: Pricing routes - Complexity pricing
try:
    from .pricing_routes import pricing_router
    cpa_router.include_router(pricing_router)
    logger.info("Pricing routes enabled")
except ImportError as e:
    logger.warning(f"Pricing routes not available: {e}")

# NEW: Intake routes - Client onboarding
try:
    from .intake_routes import intake_router
    cpa_router.include_router(intake_router)
    logger.info("Intake routes enabled")
except ImportError as e:
    logger.warning(f"Intake routes not available: {e}")

# NEW: Report routes - Advisory reports
try:
    from .report_routes import report_router
    cpa_router.include_router(report_router)
    logger.info("Report routes enabled")
except ImportError as e:
    logger.warning(f"Report routes not available: {e}")

# NEW: Data routes - Database access for clients, tax returns, recommendations
try:
    from .data_routes import router as data_router
    cpa_router.include_router(data_router)
    logger.info("Data routes enabled")
except ImportError as e:
    logger.warning(f"Data routes not available: {e}")

# NEW: Smart Onboarding routes - 60-second client onboarding
try:
    from .smart_onboarding_routes import smart_onboarding_router
    cpa_router.include_router(smart_onboarding_router)
    logger.info("Smart onboarding routes enabled")
except ImportError as e:
    logger.warning(f"Smart onboarding routes not available: {e}")

# NEW: Lead Generation routes - Prospect lead capture and conversion
try:
    from .lead_generation_routes import lead_generation_router
    cpa_router.include_router(lead_generation_router)
    logger.info("Lead generation routes enabled")
except ImportError as e:
    logger.warning(f"Lead generation routes not available: {e}")

# NEW: Lead Magnet routes - Smart tax advisory lead magnet flow
try:
    from .lead_magnet_routes import lead_magnet_router
    cpa_router.include_router(lead_magnet_router)
    logger.info("Lead magnet routes enabled")
except ImportError as e:
    logger.warning(f"Lead magnet routes not available: {e}")

# NEW: Client Portal routes - B2C client dashboard
try:
    from .client_portal_routes import router as client_portal_router
    cpa_router.include_router(client_portal_router)
    logger.info("Client portal routes enabled")
except ImportError as e:
    logger.warning(f"Client portal routes not available: {e}")

# NEW: Notification routes - In-app notifications and reminders
try:
    from .notification_routes import notification_router
    cpa_router.include_router(notification_router)
    logger.info("Notification routes enabled")
except ImportError as e:
    logger.warning(f"Notification routes not available: {e}")

# NEW: Payment Settings routes - Stripe Connect integration for CPAs
try:
    from .payment_settings_routes import router as payment_settings_router
    cpa_router.include_router(payment_settings_router)
    logger.info("Payment settings routes enabled")
except ImportError as e:
    logger.warning(f"Payment settings routes not available: {e}")

# NEW: Deadline Management routes - Tax deadline tracking
try:
    from .deadline_routes import deadline_router
    cpa_router.include_router(deadline_router)
    logger.info("Deadline routes enabled")
except ImportError as e:
    logger.warning(f"Deadline routes not available: {e}")

# NEW: Task Management routes - Task tracking and workflow
try:
    from .task_routes import task_router
    cpa_router.include_router(task_router)
    logger.info("Task routes enabled")
except ImportError as e:
    logger.warning(f"Task routes not available: {e}")

# NEW: Appointment Scheduling routes - Client appointment booking
try:
    from .appointment_routes import appointment_router
    cpa_router.include_router(appointment_router)
    logger.info("Appointment routes enabled")
except ImportError as e:
    logger.warning(f"Appointment routes not available: {e}")

# NEW: Invoice and Payment routes - Client billing and payment collection
try:
    from .invoice_routes import invoice_router, payment_link_router, payments_router
    cpa_router.include_router(invoice_router)
    cpa_router.include_router(payment_link_router)
    cpa_router.include_router(payments_router)
    logger.info("Invoice and payment routes enabled")
except ImportError as e:
    logger.warning(f"Invoice routes not available: {e}")

# Include core domain routers
cpa_router.include_router(workflow_router)
cpa_router.include_router(analysis_router)
cpa_router.include_router(notes_router)
cpa_router.include_router(insights_router)
cpa_router.include_router(lead_router)
cpa_router.include_router(exposure_router)


# =============================================================================
# HEALTH CHECK
# =============================================================================

@cpa_router.get("/health")
async def cpa_health_check():
    """CPA Panel health check endpoint."""
    return {
        "status": "healthy",
        "module": "cpa_panel",
        "routes": {
            "workflow": "active",
            "analysis": "active",
            "notes": "active",
            "insights": "active",
            "leads": "active",
            "exposure": "active",
            "staff": "active",
            "engagements": "active",
            "client_visibility": "active",
            "practice_intelligence": "active (3 metrics only)",
            "aggregated_insights": "active (real recommendation engine)",
            "optimizers": "active (credit, deduction, filing, entity, strategy)",
            "scenarios": "active (what-if analysis)",
            "pipeline": "active (lead pipeline metrics)",
            "documents": "active (OCR upload)",
            "pricing": "active (complexity pricing)",
            "intake": "active (client onboarding)",
            "reports": "active (advisory reports)",
            "smart_onboarding": "active (60-second client onboarding)",
            "lead_generation": "active (prospect lead capture)",
            "lead_magnet": "active (smart tax advisory lead magnet flow)",
            "client_portal": "active (B2C client dashboard)",
            "notifications": "active (in-app notifications and reminders)",
            "payment_settings": "active (Stripe Connect for client payments)",
            "deadlines": "active (tax deadline management)",
            "tasks": "active (task management and workflow)",
            "appointments": "active (client appointment scheduling)",
            "invoices": "active (client invoicing)",
            "payment_links": "active (payment link generation)",
            "payments": "active (payment tracking and analytics)",
        },
    }


# =============================================================================
# API DOCUMENTATION
# =============================================================================

@cpa_router.get("/docs/routes")
async def get_route_documentation():
    """Get documentation of all CPA panel routes."""
    return {
        "prefix": "/api/cpa",
        "domains": {
            "workflow": {
                "description": "Return status management, approval workflow, review queue",
                "endpoints": [
                    "GET /returns/{session_id}/status",
                    "POST /returns/{session_id}/submit-for-review",
                    "POST /returns/{session_id}/approve",
                    "POST /returns/{session_id}/revert",
                    "GET /returns/{session_id}/approval-certificate",
                    "GET /returns/{session_id}/summary",
                    "GET /queue/counts",
                    "GET /queue/{status}",
                ],
            },
            "analysis": {
                "description": "Delta analysis, tax drivers, scenario comparison",
                "endpoints": [
                    "POST /returns/{session_id}/delta",
                    "GET /returns/{session_id}/tax-drivers",
                    "POST /returns/{session_id}/compare-scenarios",
                    "GET /returns/{session_id}/suggested-scenarios",
                ],
            },
            "notes": {
                "description": "CPA review notes management",
                "endpoints": [
                    "POST /returns/{session_id}/notes",
                    "GET /returns/{session_id}/notes",
                    "DELETE /returns/{session_id}/notes/{note_id}",
                ],
            },
            "insights": {
                "description": "CPA-specific insights and review checklists",
                "endpoints": [
                    "GET /returns/{session_id}/insights",
                    "GET /returns/{session_id}/review-checklist",
                ],
            },
            "leads": {
                "description": "Lead state management and signal processing",
                "endpoints": [
                    "GET /leads/{lead_id}",
                    "POST /leads",
                    "POST /leads/{lead_id}/signals",
                    "POST /leads/{lead_id}/signals/batch",
                    "GET /leads/queue/summary",
                    "GET /leads/queue/visible",
                    "GET /leads/queue/monetizable",
                    "GET /leads/queue/priority",
                    "GET /leads/queue/state/{state}",
                    "GET /signals/catalog",
                    "GET /states/info",
                ],
            },
            "exposure": {
                "description": "Prospect-safe discovery exposure (Red Line compliant)",
                "endpoints": [
                    "GET /prospect/{session_id}/discovery",
                    "GET /prospect/{session_id}/outcome",
                    "GET /prospect/{session_id}/complexity",
                    "GET /prospect/{session_id}/drivers",
                    "GET /exposure/contracts",
                ],
            },
            "aggregated_insights": {
                "description": "Real recommendation engine insights aggregated across all clients",
                "endpoints": [
                    "GET /insights/aggregate - All insights across clients",
                    "GET /insights/summary - Dashboard hero metrics",
                    "GET /insights/categories - Insights by category",
                    "GET /insights/client/{session_id} - Single client insights",
                ],
            },
            "optimizers": {
                "description": "Tax optimization analysis (credit, deduction, filing status, entity, strategy)",
                "endpoints": [
                    "POST /session/{session_id}/credits/analyze",
                    "POST /session/{session_id}/deductions/analyze",
                    "POST /session/{session_id}/filing-status/compare",
                    "POST /session/{session_id}/entity/compare",
                    "POST /session/{session_id}/strategy/analyze",
                    "GET /session/{session_id}/optimization/summary",
                ],
            },
            "scenarios": {
                "description": "What-if scenario analysis and comparison",
                "endpoints": [
                    "POST /session/{session_id}/scenarios/compare",
                    "POST /session/{session_id}/scenarios/compare-templates",
                    "GET /session/{session_id}/scenarios/templates",
                    "GET /scenarios/categories",
                    "POST /session/{session_id}/scenarios/quick-compare",
                    "GET /session/{session_id}/scenarios/suggested",
                ],
            },
            "pipeline": {
                "description": "Lead pipeline views and metrics",
                "endpoints": [
                    "GET /leads/pipeline",
                    "GET /leads/pipeline/metrics",
                    "GET /leads/pipeline/conversion",
                    "GET /leads/pipeline/velocity",
                    "GET /leads/priority-queue",
                    "POST /leads/{lead_id}/advance",
                ],
            },
            "documents": {
                "description": "Document upload and OCR processing",
                "endpoints": [
                    "POST /session/{session_id}/documents/upload",
                    "GET /session/{session_id}/documents",
                    "GET /session/{session_id}/documents/{document_id}",
                    "GET /session/{session_id}/documents/{document_id}/extracted",
                    "POST /session/{session_id}/documents/{document_id}/apply",
                    "GET /documents/supported-types",
                ],
            },
            "pricing": {
                "description": "Complexity-based pricing calculation",
                "endpoints": [
                    "POST /session/{session_id}/pricing/calculate",
                    "GET /pricing/tiers",
                    "POST /session/{session_id}/pricing/quote",
                ],
            },
            "intake": {
                "description": "Client intake and onboarding",
                "endpoints": [
                    "POST /clients/intake/start",
                    "GET /clients/{session_id}/intake/status",
                    "GET /clients/{session_id}/intake/progress",
                    "GET /clients/{session_id}/intake/estimate",
                    "POST /clients/{session_id}/intake/answers",
                ],
            },
            "reports": {
                "description": "Advisory report generation",
                "endpoints": [
                    "POST /session/{session_id}/report/generate",
                    "GET /session/{session_id}/report/download",
                    "GET /session/{session_id}/report/sections",
                ],
            },
            "ai_insights": {
                "description": "AI-enhanced recommendations and explanations",
                "endpoints": [
                    "GET /session/{session_id}/insights/ai-enhanced",
                    "POST /session/{session_id}/insights/explain/{rec_id}",
                    "GET /session/{session_id}/insights/client-summary",
                ],
            },
            "smart_onboarding": {
                "description": "60-second smart client onboarding with OCR and AI",
                "endpoints": [
                    "POST /onboarding/start - Start onboarding session",
                    "POST /onboarding/{session_id}/upload - Upload 1040 for OCR",
                    "GET /onboarding/{session_id}/questions - Get smart questions",
                    "POST /onboarding/{session_id}/answers - Submit answers, get analysis",
                    "POST /onboarding/{session_id}/create-client - Create client",
                    "GET /onboarding/{session_id} - Get session status",
                    "POST /onboarding/batch/quick-add - Quick add without document",
                ],
            },
            "lead_generation": {
                "description": "Prospect lead capture and conversion",
                "endpoints": [
                    "POST /leads/estimate - Quick tax savings estimate",
                    "POST /leads/upload - Upload 1040 for teaser",
                    "POST /leads/{lead_id}/contact - Capture contact, unlock analysis",
                    "GET /leads/pipeline - Pipeline summary",
                    "GET /leads/unassigned - Unassigned leads",
                    "GET /leads/high-priority - High priority leads",
                    "GET /leads/cpa/{cpa_id} - Leads for CPA",
                    "POST /leads/{lead_id}/assign - Assign to CPA",
                    "POST /leads/{lead_id}/convert - Convert to client",
                ],
            },
            "client_portal": {
                "description": "B2C client dashboard (authenticated clients)",
                "endpoints": [
                    "GET /client/dashboard - Full dashboard data",
                    "GET /client/returns - List tax returns",
                    "GET /client/returns/{id} - Return details",
                    "GET /client/returns/{id}/download - Download filed return",
                    "GET /client/documents/requests - Document requests",
                    "GET /client/documents/uploaded - Uploaded documents",
                    "POST /client/documents/upload - Upload document",
                    "GET /client/messages - Message thread",
                    "POST /client/messages - Send message",
                    "POST /client/messages/read - Mark messages read",
                    "GET /client/billing - Billing summary",
                    "GET /client/billing/invoices/{id} - Invoice details",
                    "POST /client/billing/invoices/{id}/pay - Pay invoice",
                    "GET /client/billing/invoices/{id}/receipt - Download receipt",
                    "GET /client/profile - Client profile",
                    "PUT /client/profile - Update profile",
                    "GET /client/notifications - Notifications",
                ],
            },
            "notifications": {
                "description": "In-app notifications and follow-up reminders",
                "endpoints": [
                    "GET /notifications - List notifications",
                    "POST /notifications/mark-read - Mark notifications as read",
                    "POST /notifications/mark-all-read - Mark all as read",
                    "GET /notifications/preferences - Get notification preferences",
                    "PUT /notifications/preferences - Update preferences",
                    "GET /notifications/stats - Notification statistics",
                    "GET /reminders - Get follow-up reminders",
                    "POST /reminders/{id}/complete - Complete reminder",
                    "POST /reminders/{id}/snooze - Snooze reminder",
                ],
            },
            "payment_settings": {
                "description": "Stripe Connect integration for CPAs to collect client payments",
                "endpoints": [
                    "GET /payment-settings - Get payment settings and Stripe status",
                    "PUT /payment-settings - Update payment preferences",
                    "GET /payment-settings/stripe/connect-url - Get OAuth URL to connect Stripe",
                    "GET /payment-settings/stripe/callback - OAuth callback handler",
                    "POST /payment-settings/stripe/disconnect - Disconnect Stripe account",
                    "GET /payment-settings/stripe/account-status - Get Stripe account status",
                    "POST /payment-settings/create-payment-intent - Create payment for client",
                    "GET /payment-settings/payment-history - Get payment history",
                ],
            },
            "deadlines": {
                "description": "Tax deadline tracking and management",
                "endpoints": [
                    "POST /deadlines - Create deadline",
                    "GET /deadlines - List deadlines with filters",
                    "GET /deadlines/{id} - Get deadline details",
                    "PUT /deadlines/{id} - Update deadline",
                    "DELETE /deadlines/{id} - Delete deadline",
                    "POST /deadlines/{id}/complete - Mark as completed",
                    "POST /deadlines/{id}/extension - Request extension",
                    "GET /deadlines/upcoming - Get upcoming deadlines",
                    "GET /deadlines/overdue - Get overdue deadlines",
                    "GET /deadlines/calendar/{year}/{month} - Calendar view",
                    "POST /deadlines/generate-standard - Generate standard tax deadlines",
                    "GET /deadlines/reminders/pending - Get pending reminders",
                    "POST /deadlines/{id}/reminders/{type}/sent - Mark reminder sent",
                    "GET /deadlines/alerts - Get deadline alerts",
                    "POST /deadlines/alerts/{id}/acknowledge - Acknowledge alert",
                    "GET /deadlines/summary - Dashboard metrics",
                ],
            },
            "tasks": {
                "description": "Task management and workflow tracking",
                "endpoints": [
                    "POST /tasks - Create task",
                    "GET /tasks - List tasks with filters",
                    "GET /tasks/{id} - Get task details",
                    "PUT /tasks/{id} - Update task",
                    "DELETE /tasks/{id} - Delete task",
                    "POST /tasks/from-template - Create from template",
                    "GET /tasks/templates - List task templates",
                    "POST /tasks/{id}/assign - Assign to user",
                    "POST /tasks/{id}/reassign - Reassign task",
                    "POST /tasks/{id}/unassign - Unassign task",
                    "POST /tasks/{id}/start - Start working on task",
                    "POST /tasks/{id}/complete - Complete task",
                    "POST /tasks/{id}/block - Block task",
                    "POST /tasks/{id}/unblock - Unblock task",
                    "POST /tasks/{id}/comments - Add comment",
                    "GET /tasks/{id}/comments - Get comments",
                    "POST /tasks/{id}/checklist - Update checklist",
                    "GET /tasks/my-tasks - Get my tasks",
                    "GET /tasks/unassigned - Get unassigned tasks",
                    "GET /tasks/overdue - Get overdue tasks",
                    "GET /tasks/kanban - Kanban board view",
                    "GET /tasks/workload - Team workload analytics",
                    "GET /tasks/categories - List task categories",
                ],
            },
            "appointments": {
                "description": "Client appointment scheduling and availability",
                "endpoints": [
                    "POST /appointments/availability - Set CPA availability",
                    "GET /appointments/availability/{cpa_id} - Get availability",
                    "POST /appointments/availability/{cpa_id}/block-date - Block date",
                    "DELETE /appointments/availability/{cpa_id}/block-date - Unblock date",
                    "GET /appointments/slots - Get available time slots",
                    "POST /appointments - Book appointment",
                    "GET /appointments - List appointments",
                    "GET /appointments/{id} - Get appointment details",
                    "PUT /appointments/{id} - Update appointment",
                    "POST /appointments/{id}/confirm - Confirm appointment",
                    "POST /appointments/{id}/cancel - Cancel appointment",
                    "POST /appointments/{id}/reschedule - Reschedule appointment",
                    "POST /appointments/{id}/complete - Mark as completed",
                    "POST /appointments/{id}/no-show - Mark as no-show",
                    "GET /appointments/upcoming - Get upcoming appointments",
                    "GET /appointments/today - Get today's appointments",
                    "GET /appointments/client/{client_id} - Client appointments",
                    "GET /appointments/reminders/pending - Get pending reminders",
                    "POST /appointments/{id}/reminders/{type}/sent - Mark reminder sent",
                    "GET /appointments/summary - Appointment analytics",
                    "GET /appointments/types - List appointment types",
                    "GET /appointments/statuses - List statuses",
                ],
            },
        },
    }
