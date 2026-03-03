# Year-Round Tax Advisory Platform — Complete Fix Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all broken linkages, dead ends, and missing features across the Admin → CPA → Client chain to make the platform production-ready for year-round tax advisory intelligence.

**Architecture:** The codebase has a dual-database problem (PostgreSQL for admin/firms/users, SQLite for sessions/leads/branding) with no foreign keys between them. We fix this by: (1) adding `firm_id` columns where missing, (2) wiring the proactive alert scheduler, (3) building the CPA review gate for AI chat, (4) fixing all dead-end UI buttons, and (5) connecting the nurture email pipeline.

**Tech Stack:** Python/FastAPI, SQLAlchemy (PostgreSQL), SQLite (legacy), Celery/Redis, SendGrid/SES email, Jinja2 templates, Alpine.js frontend.

---

## Phase 0: Critical Data Linkage Fixes (Do First — Everything Depends On This)

### Task 1: Add `firm_id` to `clients` table and fix the preparer→user bridge

The `clients` table links to the deprecated `preparers` table via `preparer_id`, but the new system uses `users` table. The `clients` table has NO `firm_id` column. This breaks all firm-scoped client queries.

**Files:**
- Create: `src/database/alembic/versions/20260304_0001_add_firm_id_to_clients.py`
- Modify: `src/database/models.py` (ClientRecord class, ~line 1317)

**Step 1: Write the migration**

```python
"""Add firm_id to clients table and create bridge index.

Revision ID: 20260304_0001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "20260304_0001"
down_revision = None  # Update to latest existing revision
branch_labels = None
depends_on = None


def upgrade():
    # Add firm_id column to clients
    op.add_column("clients", sa.Column("firm_id", UUID(as_uuid=True), nullable=True))

    # Backfill firm_id from preparers → users chain
    op.execute("""
        UPDATE clients c
        SET firm_id = u.firm_id
        FROM users u
        WHERE c.preparer_id = u.user_id
        AND c.firm_id IS NULL
    """)

    # Also try via preparers table for legacy records
    op.execute("""
        UPDATE clients c
        SET firm_id = u.firm_id
        FROM preparers p
        JOIN users u ON LOWER(p.email) = LOWER(u.email)
        WHERE c.preparer_id = p.preparer_id
        AND c.firm_id IS NULL
    """)

    # Create index for firm-scoped queries
    op.create_index("ix_clients_firm_id", "clients", ["firm_id"])

    # Add FK constraint (nullable for now — legacy records may not have a firm)
    op.create_foreign_key(
        "fk_clients_firm_id", "clients", "firms",
        ["firm_id"], ["firm_id"], ondelete="SET NULL"
    )


def downgrade():
    op.drop_constraint("fk_clients_firm_id", "clients", type_="foreignkey")
    op.drop_index("ix_clients_firm_id", table_name="clients")
    op.drop_column("clients", "firm_id")
```

**Step 2: Update the ORM model**

In `src/database/models.py`, add to `ClientRecord`:

```python
firm_id = Column(UUID(as_uuid=True), ForeignKey("firms.firm_id", ondelete="SET NULL"), nullable=True, index=True)
```

**Step 3: Fix the client query in admin panel**

Modify `src/admin_panel/api/client_routes.py` to use the direct `firm_id`:

```python
# Replace the fragile JOIN chain:
# OLD: JOIN users u ON c.preparer_id = u.user_id WHERE u.firm_id = :firm_id
# NEW: WHERE c.firm_id = :firm_id
```

**Step 4: Run migration and verify**

```bash
cd src && alembic upgrade head
pytest tests/test_data_models.py -v
```

**Step 5: Commit**

```bash
git add src/database/alembic/versions/20260304_0001_add_firm_id_to_clients.py src/database/models.py src/admin_panel/api/client_routes.py
git commit -m "fix: add firm_id to clients table, fix preparer→user bridge"
```

---

### Task 2: Add `firm_id` and `client_id` to `tax_returns` table

The `tax_returns` table has NO foreign keys to clients, preparers, or firms. Returns are only reachable via `client_sessions.return_id`. This breaks firm isolation.

**Files:**
- Create: `src/database/alembic/versions/20260304_0002_add_firm_id_to_tax_returns.py`
- Modify: `src/database/models.py` (TaxReturnRecord class)

**Step 1: Write the migration**

```python
"""Add firm_id and client_id to tax_returns table.

Revision ID: 20260304_0002
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "20260304_0002"
down_revision = "20260304_0001"


def upgrade():
    op.add_column("tax_returns", sa.Column("firm_id", UUID(as_uuid=True), nullable=True))
    op.add_column("tax_returns", sa.Column("client_id", UUID(as_uuid=True), nullable=True))

    # Backfill from client_sessions chain
    op.execute("""
        UPDATE tax_returns tr
        SET client_id = cs.client_id,
            firm_id = c.firm_id
        FROM client_sessions cs
        JOIN clients c ON cs.client_id = c.client_id
        WHERE cs.return_id = tr.return_id
        AND tr.client_id IS NULL
    """)

    op.create_index("ix_tax_returns_firm_id", "tax_returns", ["firm_id"])
    op.create_index("ix_tax_returns_client_id", "tax_returns", ["client_id"])

    op.create_foreign_key(
        "fk_tax_returns_firm_id", "tax_returns", "firms",
        ["firm_id"], ["firm_id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_tax_returns_client_id", "tax_returns", "clients",
        ["client_id"], ["client_id"], ondelete="SET NULL"
    )


def downgrade():
    op.drop_constraint("fk_tax_returns_client_id", "tax_returns", type_="foreignkey")
    op.drop_constraint("fk_tax_returns_firm_id", "tax_returns", type_="foreignkey")
    op.drop_index("ix_tax_returns_client_id", table_name="tax_returns")
    op.drop_index("ix_tax_returns_firm_id", table_name="tax_returns")
    op.drop_column("tax_returns", "client_id")
    op.drop_column("tax_returns", "firm_id")
```

**Step 2: Update ORM model, run migration, commit**

Same pattern as Task 1.

---

### Task 3: Create `tenant_id` ↔ `firm_id` mapping table

SQLite tables use string `tenant_id` (e.g., "acme-cpa"). PostgreSQL uses UUID `firm_id`. There is no mapping between them.

**Files:**
- Create: `src/database/alembic/versions/20260304_0003_tenant_firm_mapping.py`
- Create: `src/database/tenant_mapping.py`

**Step 1: Write the migration**

```python
"""Create tenant_firm_mapping table.

Revision ID: 20260304_0003
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "20260304_0003"
down_revision = "20260304_0002"


def upgrade():
    op.create_table(
        "tenant_firm_mapping",
        sa.Column("tenant_id", sa.String(255), primary_key=True),
        sa.Column("firm_id", UUID(as_uuid=True), sa.ForeignKey("firms.firm_id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # Backfill from cpa_profiles where cpa_slug exists
    op.execute("""
        INSERT INTO tenant_firm_mapping (tenant_id, firm_id)
        SELECT DISTINCT cp.cpa_slug, u.firm_id
        FROM cpa_profiles cp
        JOIN users u ON cp.user_id = u.user_id
        WHERE cp.cpa_slug IS NOT NULL
        AND u.firm_id IS NOT NULL
        ON CONFLICT DO NOTHING
    """)


def downgrade():
    op.drop_table("tenant_firm_mapping")
```

**Step 2: Create mapping helper**

```python
# src/database/tenant_mapping.py
"""Resolves tenant_id (string slug) ↔ firm_id (UUID) bidirectionally."""

from typing import Optional
from uuid import UUID
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_firm_id_for_tenant(db: AsyncSession, tenant_id: str) -> Optional[UUID]:
    """Convert a tenant slug to a firm UUID."""
    result = await db.execute(
        text("SELECT firm_id FROM tenant_firm_mapping WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )
    row = result.fetchone()
    return row[0] if row else None


async def get_tenant_id_for_firm(db: AsyncSession, firm_id: UUID) -> Optional[str]:
    """Convert a firm UUID to a tenant slug."""
    result = await db.execute(
        text("SELECT tenant_id FROM tenant_firm_mapping WHERE firm_id = :fid"),
        {"fid": str(firm_id)},
    )
    row = result.fetchone()
    return row[0] if row else None


async def register_mapping(db: AsyncSession, tenant_id: str, firm_id: UUID) -> None:
    """Register a tenant_id ↔ firm_id mapping."""
    await db.execute(
        text("""
            INSERT INTO tenant_firm_mapping (tenant_id, firm_id)
            VALUES (:tid, :fid)
            ON CONFLICT (tenant_id) DO UPDATE SET firm_id = :fid
        """),
        {"tid": tenant_id, "fid": str(firm_id)},
    )
    await db.commit()
```

**Step 3: Run migration, test, commit**

---

### Task 4: Implement lead-to-client conversion (currently a stub)

`convert_lead_to_client()` in `lead_generation_service.py` generates a UUID but never writes to the database.

**Files:**
- Modify: `src/cpa_panel/services/lead_generation_service.py` (~line 353-379)
- Test: `tests/cpa/test_lead_conversion.py`

**Step 1: Write the failing test**

```python
# tests/cpa/test_lead_conversion.py
import pytest
from uuid import uuid4


def test_convert_lead_creates_client_record(db_session):
    """Converting a lead must create a real ClientRecord in the database."""
    from cpa_panel.services.lead_generation_service import LeadGenerationService

    service = LeadGenerationService()
    # Create a test lead
    lead_id = service.create_lead(
        cpa_id=str(uuid4()),
        firm_id=str(uuid4()),
        email="test@example.com",
        name="Test Client",
        phone="555-0100",
    )

    lead, client_id = service.convert_lead_to_client(
        lead_id=lead_id,
        cpa_id=str(uuid4()),
        firm_id=str(uuid4()),
    )

    assert client_id is not None
    # Verify a real record exists in the clients table
    from database.models import ClientRecord
    client = db_session.query(ClientRecord).filter_by(client_id=client_id).first()
    assert client is not None
    assert client.firm_id is not None
```

**Step 2: Implement the conversion**

Replace the stub in `convert_lead_to_client()` with actual DB insert:

```python
def convert_lead_to_client(self, lead_id: str, cpa_id: str, firm_id: str) -> Tuple[Any, str]:
    """Convert a lead to a client, creating a real ClientRecord."""
    lead = self._leads.get(lead_id)
    if not lead:
        raise ValueError(f"Lead {lead_id} not found")

    client_id = str(uuid.uuid4())

    # Create actual database record
    from database.models import ClientRecord, get_db_session
    with get_db_session() as db:
        client = ClientRecord(
            client_id=client_id,
            preparer_id=cpa_id,
            firm_id=firm_id,
            first_name=lead.name.split()[0] if lead.name else "",
            last_name=" ".join(lead.name.split()[1:]) if lead.name and len(lead.name.split()) > 1 else "",
            email=lead.email,
            phone=lead.phone,
            created_at=datetime.utcnow(),
        )
        db.add(client)
        db.commit()

    lead.status = LeadStatus.CONVERTED
    lead.converted_client_id = client_id

    return lead, client_id
```

**Step 3: Test, commit**

---

## Phase 1: Proactive Alerts Engine (The #1 Differentiator)

### Task 5: Create Celery tasks for proactive alert scanning

Wire the existing recommendation generators to a Celery beat schedule that runs daily.

**Files:**
- Create: `src/tasks/notification_tasks.py`
- Modify: `src/tasks/celery_app.py` (add to `include` list and `beat_schedule`)

**Step 1: Create the notification tasks module**

```python
# src/tasks/notification_tasks.py
"""
Proactive notification tasks — the scheduler that makes the platform year-round.

Runs on Celery beat schedule:
- process_deadline_reminders: Every hour — checks for upcoming deadlines and sends reminders
- process_nurture_emails: Every hour — sends due nurture sequence emails
- scan_client_opportunities: Daily at 6 AM — scans all client profiles for tax opportunities
- compile_daily_digest: Daily at 7 AM — compiles and sends CPA daily digest
"""

import logging
from datetime import datetime, timedelta
from tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.notifications.process_deadline_reminders")
def process_deadline_reminders():
    """
    Check all firms' deadlines and send reminder emails for those approaching.

    Runs hourly. Checks DeadlineService.get_pending_reminders() and dispatches
    via EmailTriggerService.send_deadline_reminder().
    """
    import asyncio
    from notifications.email_triggers import email_triggers
    from cpa_panel.deadlines.deadline_service import DeadlineService

    deadline_service = DeadlineService()
    pending = deadline_service.get_pending_reminders()

    sent_count = 0
    for reminder in pending:
        deadline = reminder.get("deadline")
        if not deadline:
            continue

        days_remaining = (deadline.due_date - datetime.utcnow()).days

        # Send via the real email infrastructure
        try:
            asyncio.get_event_loop().run_until_complete(
                email_triggers.send_deadline_reminder(
                    recipient_email=reminder.get("recipient_email", ""),
                    recipient_name=reminder.get("recipient_name", ""),
                    deadline_type=deadline.deadline_type,
                    due_date=deadline.due_date,
                    days_remaining=days_remaining,
                    client_name=reminder.get("client_name"),
                    firm_id=reminder.get("firm_id"),
                )
            )
            deadline_service.mark_reminder_sent(reminder["reminder_id"])
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send deadline reminder: {e}")

    logger.info(f"Processed {sent_count} deadline reminders")
    return {"sent": sent_count}


@celery_app.task(name="tasks.notifications.process_nurture_emails")
def process_nurture_emails():
    """
    Process due nurture sequence emails.

    Runs hourly. Calls NurtureService.get_due_emails() and dispatches
    via EmailTriggerService.
    """
    import asyncio
    from cpa_panel.services.nurture_service import NurtureService
    from notifications.email_triggers import send_email
    from notifications.email_provider import send_email as provider_send

    nurture = NurtureService()
    due_emails = nurture.get_due_emails()

    sent_count = 0
    for enrollment in due_emails:
        try:
            content = nurture.process_email(enrollment)
            if content:
                provider_send(
                    to=content["to_email"],
                    subject=content["subject"],
                    body_html=content.get("body_html", ""),
                    body_text=content.get("body_text", ""),
                    from_name=content.get("from_name", "TaxFlow Advisory"),
                )
                nurture.mark_email_sent(enrollment.enrollment_id)
                sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send nurture email: {e}")

    logger.info(f"Processed {sent_count} nurture emails")
    return {"sent": sent_count}


@celery_app.task(name="tasks.notifications.scan_client_opportunities")
def scan_client_opportunities():
    """
    Daily scan of all client profiles for proactive tax opportunity alerts.

    Runs daily. For each firm's clients:
    1. Loads client profile data
    2. Runs recommendation generators (retirement, investments, real_estate)
    3. Creates alerts for high-value opportunities
    4. Sends CPA notification for critical findings
    """
    import asyncio
    from database.models import get_db_session, ClientRecord
    from web.recommendation.orchestrator import get_recommendations
    from admin_panel.services.alert_service import AlertService, AlertType, AlertPriority

    logger.info("Starting daily client opportunity scan")

    with get_db_session() as db:
        # Get all clients with firm_id set
        clients = db.query(ClientRecord).filter(
            ClientRecord.firm_id.isnot(None)
        ).all()

    alerts_created = 0
    for client in clients:
        try:
            # Build profile from client's latest session data
            profile = _build_profile_from_client(client)
            if not profile:
                continue

            # Run recommendation generators
            recs = get_recommendations(profile)

            # Filter for high-value opportunities (>$1000 savings)
            high_value = [r for r in recs if getattr(r, "estimated_savings", 0) > 1000]

            if high_value:
                # Create alert for the CPA firm
                alert_service = AlertService(db=None)  # In-memory for now
                for rec in high_value[:3]:  # Top 3 per client
                    asyncio.get_event_loop().run_until_complete(
                        alert_service.create_alert(
                            firm_id=str(client.firm_id),
                            alert_type=AlertType.OPPORTUNITY.value,
                            priority=AlertPriority.MEDIUM.value,
                            title=f"Opportunity: {rec.title}",
                            message=f"{client.first_name} {client.last_name}: {rec.description}. Est. savings: ${rec.estimated_savings:,.0f}",
                            client_id=str(client.client_id),
                            metadata={
                                "estimated_savings": float(rec.estimated_savings),
                                "category": rec.category,
                            },
                        )
                    )
                    alerts_created += 1
        except Exception as e:
            logger.error(f"Error scanning client {client.client_id}: {e}")

    logger.info(f"Daily scan complete. Created {alerts_created} opportunity alerts.")
    return {"clients_scanned": len(clients), "alerts_created": alerts_created}


@celery_app.task(name="tasks.notifications.compile_and_send_daily_digest")
def compile_and_send_daily_digest():
    """
    Compile and send daily alert digest email to each CPA firm's admins.

    Runs daily at 7 AM. For each firm:
    1. Compiles active alerts by priority
    2. Renders digest email
    3. Sends to firm admins
    """
    import asyncio
    from admin_panel.services.alert_service import AlertService
    from notifications.email_provider import send_email

    logger.info("Compiling daily digests")
    # Implementation: iterate firms, compile digest, send email
    return {"digests_sent": 0}


def _build_profile_from_client(client) -> dict:
    """Build a tax profile dict from a ClientRecord for recommendation scanning."""
    # Load from the client's latest session or stored profile data
    from database.models import get_db_session, ClientSessionRecord

    with get_db_session() as db:
        session = db.query(ClientSessionRecord).filter_by(
            client_id=client.client_id
        ).order_by(ClientSessionRecord.created_at.desc()).first()

    if not session:
        return {}

    # The session's tax data is stored in the session_states SQLite table
    from database.session_persistence import SessionPersistence
    persistence = SessionPersistence()
    state = persistence.load_session(str(session.session_id))

    return state.get("profile", {}) if state else {}
```

**Step 2: Register in Celery beat schedule**

Add to `src/tasks/celery_app.py`:

```python
# In the include list:
include=[
    "tasks.ocr_tasks",
    "tasks.data_retention",
    "tasks.notification_tasks",  # NEW
],

# In beat_schedule:
"process-deadline-reminders": {
    "task": "tasks.notifications.process_deadline_reminders",
    "schedule": 3600.0,  # Every hour
},
"process-nurture-emails": {
    "task": "tasks.notifications.process_nurture_emails",
    "schedule": 3600.0,  # Every hour
},
"scan-client-opportunities": {
    "task": "tasks.notifications.scan_client_opportunities",
    "schedule": crontab(hour=6, minute=0),  # Daily at 6 AM
},
"compile-daily-digest": {
    "task": "tasks.notifications.compile_and_send_daily_digest",
    "schedule": crontab(hour=7, minute=0),  # Daily at 7 AM
},
```

Also add `from celery.schedules import crontab` to the imports.

**Step 3: Test, commit**

```bash
pytest tests/test_notification_tasks.py -v
git commit -m "feat: add proactive alert scheduler with deadline, nurture, and opportunity scanning"
```

---

### Task 6: Connect lead magnet notification service to real email provider

The `_send_notification()` in `src/cpa_panel/services/notification_service.py` (lead magnet side) marks emails as SENT without actually sending. Connect it to the real `EmailTriggerService`.

**Files:**
- Modify: `src/cpa_panel/services/notification_service.py` (~line where `_send_notification` is defined)

**Step 1: Replace the stub**

```python
# Replace the _send_notification stub with:
async def _send_notification(self, notification):
    """Send notification via the real email infrastructure."""
    from notifications.email_provider import send_email

    if notification.channel == "email" and notification.recipient_email:
        result = send_email(
            to=notification.recipient_email,
            subject=notification.subject,
            body_html=notification.body_html or notification.body,
            body_text=notification.body,
            from_name="TaxFlow Advisory",
            tags=[f"notification:{notification.notification_type}"],
        )
        notification.status = "SENT" if result.success else "FAILED"
        notification.sent_at = datetime.utcnow()
        if not result.success:
            notification.error_message = result.error_message
    else:
        notification.status = "SENT"
        notification.sent_at = datetime.utcnow()
```

**Step 2: Test, commit**

---

## Phase 2: CPA Review Gate for AI Chat

### Task 7: Add CPA approval queue for AI-drafted responses

Currently, AI chat responses go directly to clients without CPA review. Build the review gate.

**Files:**
- Create: `src/cpa_panel/services/ai_review_service.py`
- Create: `src/cpa_panel/api/ai_review_routes.py`
- Modify: `src/web/intelligent_advisor_api.py` (add review gate check)
- Create: `src/web/templates/cpa/ai_review_queue.html`

**Step 1: Create the AI review service**

```python
# src/cpa_panel/services/ai_review_service.py
"""
CPA Review Gate for AI-Generated Responses.

When a client asks a question via the intelligent advisor and the CPA firm
has review_mode enabled, the AI-drafted response is queued for CPA approval
instead of being sent directly.

Flow:
1. Client asks question → AI generates draft response
2. Draft is stored in review queue with status PENDING
3. CPA sees queue on their dashboard
4. CPA approves (one-click) or edits → response is released to client
5. Client sees the response (attributed as "from [CPA Firm Name]")
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List, Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"


@dataclass
class AIResponseDraft:
    draft_id: str
    session_id: str
    firm_id: str
    client_question: str
    ai_response: str
    status: ReviewStatus = ReviewStatus.PENDING
    reviewer_id: Optional[str] = None
    reviewer_name: Optional[str] = None
    edited_response: Optional[str] = None
    review_note: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    reviewed_at: Optional[datetime] = None
    client_name: Optional[str] = None
    client_email: Optional[str] = None
    complexity: Optional[str] = None
    estimated_savings: Optional[float] = None


class AIReviewService:
    """Service for managing AI response review queue."""

    def __init__(self):
        # In-memory for now — migrate to DB in production
        self._drafts: Dict[str, AIResponseDraft] = {}

    def queue_for_review(
        self,
        session_id: str,
        firm_id: str,
        client_question: str,
        ai_response: str,
        client_name: Optional[str] = None,
        client_email: Optional[str] = None,
        complexity: Optional[str] = None,
        estimated_savings: Optional[float] = None,
    ) -> AIResponseDraft:
        """Queue an AI-generated response for CPA review."""
        draft = AIResponseDraft(
            draft_id=str(uuid4()),
            session_id=session_id,
            firm_id=firm_id,
            client_question=client_question,
            ai_response=ai_response,
            client_name=client_name,
            client_email=client_email,
            complexity=complexity,
            estimated_savings=estimated_savings,
        )
        self._drafts[draft.draft_id] = draft
        logger.info(f"Queued AI response {draft.draft_id} for review (firm={firm_id})")
        return draft

    def get_pending_reviews(self, firm_id: str) -> List[AIResponseDraft]:
        """Get all pending reviews for a firm."""
        return [
            d for d in self._drafts.values()
            if d.firm_id == firm_id and d.status == ReviewStatus.PENDING
        ]

    def approve_draft(
        self,
        draft_id: str,
        reviewer_id: str,
        reviewer_name: str,
    ) -> Optional[AIResponseDraft]:
        """Approve an AI response as-is."""
        draft = self._drafts.get(draft_id)
        if not draft:
            return None
        draft.status = ReviewStatus.APPROVED
        draft.reviewer_id = reviewer_id
        draft.reviewer_name = reviewer_name
        draft.reviewed_at = datetime.utcnow()
        return draft

    def edit_and_approve(
        self,
        draft_id: str,
        reviewer_id: str,
        reviewer_name: str,
        edited_response: str,
        review_note: Optional[str] = None,
    ) -> Optional[AIResponseDraft]:
        """Edit and approve an AI response."""
        draft = self._drafts.get(draft_id)
        if not draft:
            return None
        draft.status = ReviewStatus.EDITED
        draft.reviewer_id = reviewer_id
        draft.reviewer_name = reviewer_name
        draft.edited_response = edited_response
        draft.review_note = review_note
        draft.reviewed_at = datetime.utcnow()
        return draft

    def reject_draft(
        self,
        draft_id: str,
        reviewer_id: str,
        reviewer_name: str,
        review_note: str,
    ) -> Optional[AIResponseDraft]:
        """Reject an AI response."""
        draft = self._drafts.get(draft_id)
        if not draft:
            return None
        draft.status = ReviewStatus.REJECTED
        draft.reviewer_id = reviewer_id
        draft.reviewer_name = reviewer_name
        draft.review_note = review_note
        draft.reviewed_at = datetime.utcnow()
        return draft

    def get_final_response(self, draft_id: str) -> Optional[str]:
        """Get the final response to send to the client."""
        draft = self._drafts.get(draft_id)
        if not draft:
            return None
        if draft.status == ReviewStatus.EDITED:
            return draft.edited_response
        if draft.status == ReviewStatus.APPROVED:
            return draft.ai_response
        return None  # Not yet approved


# Singleton
ai_review_service = AIReviewService()
```

**Step 2: Create API routes**

```python
# src/cpa_panel/api/ai_review_routes.py
"""CPA AI Review Queue API routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from cpa_panel.services.ai_review_service import ai_review_service, ReviewStatus

router = APIRouter(prefix="/ai-review", tags=["AI Review"])


class ApproveRequest(BaseModel):
    reviewer_id: str
    reviewer_name: str


class EditApproveRequest(BaseModel):
    reviewer_id: str
    reviewer_name: str
    edited_response: str
    review_note: Optional[str] = None


class RejectRequest(BaseModel):
    reviewer_id: str
    reviewer_name: str
    review_note: str


@router.get("/pending/{firm_id}")
async def get_pending_reviews(firm_id: str):
    """Get all pending AI response drafts for a firm."""
    drafts = ai_review_service.get_pending_reviews(firm_id)
    return {
        "count": len(drafts),
        "drafts": [
            {
                "draft_id": d.draft_id,
                "client_question": d.client_question,
                "ai_response": d.ai_response,
                "client_name": d.client_name,
                "complexity": d.complexity,
                "estimated_savings": d.estimated_savings,
                "created_at": d.created_at.isoformat(),
            }
            for d in drafts
        ],
    }


@router.post("/{draft_id}/approve")
async def approve_draft(draft_id: str, req: ApproveRequest):
    """One-click approve an AI response."""
    draft = ai_review_service.approve_draft(
        draft_id, req.reviewer_id, req.reviewer_name
    )
    if not draft:
        raise HTTPException(404, "Draft not found")
    return {"status": "approved", "draft_id": draft_id}


@router.post("/{draft_id}/edit-approve")
async def edit_and_approve(draft_id: str, req: EditApproveRequest):
    """Edit and approve an AI response."""
    draft = ai_review_service.edit_and_approve(
        draft_id, req.reviewer_id, req.reviewer_name,
        req.edited_response, req.review_note
    )
    if not draft:
        raise HTTPException(404, "Draft not found")
    return {"status": "edited", "draft_id": draft_id}


@router.post("/{draft_id}/reject")
async def reject_draft(draft_id: str, req: RejectRequest):
    """Reject an AI response."""
    draft = ai_review_service.reject_draft(
        draft_id, req.reviewer_id, req.reviewer_name, req.review_note
    )
    if not draft:
        raise HTTPException(404, "Draft not found")
    return {"status": "rejected", "draft_id": draft_id}
```

**Step 3: Wire into the intelligent advisor chat flow**

In `src/web/intelligent_advisor_api.py`, add a review gate check after AI generates its response:

```python
# After the AI generates a response, before returning to client:
# Check if this session's firm has review mode enabled
firm_settings = get_firm_settings(session.get("firm_id"))
if firm_settings and firm_settings.get("require_ai_review", False):
    from cpa_panel.services.ai_review_service import ai_review_service

    draft = ai_review_service.queue_for_review(
        session_id=session_id,
        firm_id=session.get("firm_id", ""),
        client_question=user_message,
        ai_response=response_text,
        client_name=session.get("contact", {}).get("name"),
        client_email=session.get("contact", {}).get("email"),
        complexity=complexity,
    )

    # Return a "pending review" message instead of the AI response
    return ChatResponse(
        response="Your question has been received! Our tax advisor is reviewing the response and will get back to you shortly.",
        response_type="pending_review",
        quick_actions=[],
        metadata={"draft_id": draft.draft_id, "review_status": "pending"},
    )
```

**Step 4: Register routes, test, commit**

---

## Phase 3: Fix All CPA Panel Dead Ends

### Task 8: Fix team management — wire invite button

**Files:**
- Modify: `src/web/templates/cpa/team.html` (add JS for invite)
- Verify: `src/admin_panel/api/team_routes.py` exists

**Step 1: Add JavaScript to team.html invite form**

```javascript
// In the invite form submit handler:
async function sendInvite() {
    const email = document.getElementById('invite-email').value;
    const role = document.getElementById('invite-role').value;

    const response = await fetch('/api/v1/admin/team/invite', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getAuthToken()}`,
        },
        body: JSON.stringify({ email, role }),
    });

    if (response.ok) {
        showToast('Invitation sent successfully!', 'success');
        closeModal('invite-modal');
        loadTeamMembers();
    } else {
        const data = await response.json();
        showToast(data.detail || 'Failed to send invitation', 'error');
    }
}
```

**Step 2: Test manually, commit**

---

### Task 9: Fix billing page — wire Change Plan button and payment method

**Files:**
- Modify: `src/web/templates/cpa/billing.html`

**Step 1: Add JavaScript for Change Plan**

```javascript
async function changePlan() {
    // Create Stripe checkout session for plan change
    const response = await fetch('/api/v1/admin/billing/checkout', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getAuthToken()}`,
        },
        body: JSON.stringify({
            plan_id: selectedPlanId,
            billing_cycle: 'monthly',
        }),
    });

    if (response.ok) {
        const data = await response.json();
        if (data.checkout_url) {
            window.location.href = data.checkout_url;
        }
    }
}
```

**Step 2: Load real payment method data**

Replace the hardcoded "Mercury wallet" with a fetch to `/api/v1/admin/billing/payment-method`.

**Step 3: Test, commit**

---

### Task 10: Fix client management — add search, contact button, dedicated detail page

**Files:**
- Modify: `src/web/templates/cpa/clients.html` (wire search, contact)
- Create: `src/web/templates/cpa/client_detail.html` (dedicated page instead of redirecting to lead detail)

**Step 1: Wire search bar**

```javascript
function searchClients() {
    const query = document.getElementById('client-search').value.toLowerCase();
    document.querySelectorAll('.client-card').forEach(card => {
        const name = card.dataset.clientName.toLowerCase();
        card.style.display = name.includes(query) ? '' : 'none';
    });
}
```

**Step 2: Wire contact button to messaging or mailto**

```javascript
function contactClient(clientEmail, clientName) {
    // Use the messaging API if available, otherwise mailto
    window.location.href = `mailto:${clientEmail}?subject=Tax Advisory Update`;
}
```

**Step 3: Commit**

---

### Task 11: Fix CPA messaging — create inbox template

**Files:**
- Create: `src/web/templates/cpa/messages.html`
- Modify: `src/web/cpa_dashboard_pages.py` (add route)
- Modify: `src/web/templates/cpa/base.html` (add sidebar link)

**Step 1: Add page route**

```python
# In src/web/cpa_dashboard_pages.py
@router.get("/cpa/messages", response_class=HTMLResponse)
async def cpa_messages_page(request: Request):
    return templates.TemplateResponse("cpa/messages.html", {"request": request})
```

**Step 2: Create basic messages template**

A simple two-panel layout: conversation list on left, message thread on right. Uses existing `/messages/conversations` and `/messages/conversations/{id}/messages` APIs.

**Step 3: Add sidebar link in base.html**

```html
<a href="/cpa/messages" class="nav-link">
    <span class="nav-icon">💬</span>
    <span>Messages</span>
    <span class="badge" x-show="unreadCount > 0" x-text="unreadCount"></span>
</a>
```

**Step 4: Commit**

---

### Task 12: Move engagement letters from in-memory to database

**Files:**
- Create: `src/database/alembic/versions/20260304_0004_engagement_letters_table.py`
- Modify: `src/cpa_panel/api/engagement_routes.py` (replace `_letters` dict with DB queries)

**Step 1: Migration**

```python
def upgrade():
    op.create_table(
        "engagement_letters",
        sa.Column("letter_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("firm_id", UUID(as_uuid=True), sa.ForeignKey("firms.firm_id"), nullable=False),
        sa.Column("session_id", sa.String(100), nullable=True),
        sa.Column("client_name", sa.String(255), nullable=False),
        sa.Column("client_email", sa.String(255)),
        sa.Column("tax_year", sa.Integer),
        sa.Column("services", sa.JSON),
        sa.Column("fee_amount", sa.Numeric(10, 2)),
        sa.Column("letter_html", sa.Text),
        sa.Column("status", sa.String(50), default="draft"),  # draft, sent, signed, expired
        sa.Column("signed_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
```

**Step 2: Replace in-memory storage in engagement_routes.py, commit**

---

### Task 13: Move password reset tokens from in-memory to database

**Files:**
- Modify: `src/admin_panel/api/auth_routes.py` (replace `_reset_tokens` dict)

Store reset tokens in the `users` table (add `reset_token` and `reset_token_expires` columns) or a dedicated `password_reset_tokens` table.

---

## Phase 4: Stripe Webhook Handler (Critical for Billing)

### Task 14: Create inbound Stripe webhook endpoint

**Files:**
- Create: `src/admin_panel/api/stripe_webhook_routes.py`
- Modify: `src/admin_panel/api/router.py` (register webhook route)

**Step 1: Create webhook handler**

```python
# src/admin_panel/api/stripe_webhook_routes.py
"""
Inbound Stripe webhook handler.

Handles subscription lifecycle events:
- checkout.session.completed → activate subscription
- customer.subscription.updated → sync status
- customer.subscription.deleted → mark cancelled
- invoice.payment_failed → mark past_due
- invoice.paid → confirm payment
"""

import os
import hmac
import hashlib
import logging
from fastapi import APIRouter, Request, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")


@router.post("/stripe")
async def handle_stripe_webhook(request: Request):
    """Handle inbound Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not STRIPE_WEBHOOK_SECRET:
        logger.warning("STRIPE_WEBHOOK_SECRET not configured, skipping verification")
    else:
        # Verify webhook signature
        if not _verify_stripe_signature(payload, sig_header, STRIPE_WEBHOOK_SECRET):
            raise HTTPException(400, "Invalid signature")

    import json
    event = json.loads(payload)
    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    logger.info(f"Stripe webhook received: {event_type}")

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(data)
    elif event_type == "customer.subscription.updated":
        await _handle_subscription_updated(data)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(data)
    elif event_type == "invoice.payment_failed":
        await _handle_payment_failed(data)
    elif event_type == "invoice.paid":
        await _handle_invoice_paid(data)

    return {"received": True}


def _verify_stripe_signature(payload: bytes, sig_header: str, secret: str) -> bool:
    """Verify Stripe webhook signature using HMAC-SHA256."""
    try:
        elements = dict(item.split("=", 1) for item in sig_header.split(","))
        timestamp = elements.get("t", "")
        signature = elements.get("v1", "")

        signed_payload = f"{timestamp}.{payload.decode()}"
        expected = hmac.new(
            secret.encode(), signed_payload.encode(), hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


async def _handle_checkout_completed(data: dict):
    """Activate subscription after successful checkout."""
    from admin_panel.services.billing_service import BillingService

    subscription_id = data.get("subscription")
    customer_id = data.get("customer")
    firm_id = data.get("metadata", {}).get("firm_id")

    if firm_id:
        logger.info(f"Activating subscription for firm {firm_id}")
        # Update subscription status to ACTIVE in database


async def _handle_subscription_updated(data: dict):
    """Sync subscription status changes from Stripe."""
    stripe_status = data.get("status")  # active, past_due, canceled, etc.
    logger.info(f"Subscription updated: {data.get('id')} → {stripe_status}")


async def _handle_subscription_deleted(data: dict):
    """Mark subscription as cancelled."""
    logger.info(f"Subscription deleted: {data.get('id')}")


async def _handle_payment_failed(data: dict):
    """Handle failed payment — mark subscription as past_due."""
    logger.info(f"Payment failed for invoice: {data.get('id')}")


async def _handle_invoice_paid(data: dict):
    """Confirm payment received."""
    logger.info(f"Invoice paid: {data.get('id')}")
```

**Step 2: Register route (IMPORTANT: no auth on webhook endpoint), commit**

---

## Phase 5: Client-Facing Advisory Dashboard

### Task 15: Create client tax health dashboard

**Files:**
- Create: `src/web/templates/client_dashboard.html`
- Modify: `src/web/routers/pages.py` (add `/dashboard` route or update existing)
- Modify: `src/cpa_panel/api/client_portal_routes.py` (add dashboard data endpoint)

Build a simple dashboard showing:
- Tax health score (0-100 based on profile completeness + strategy adoption)
- Active alerts/reminders (estimated payments, deadlines)
- Recommended actions (top 3 strategies from recommendation engine)
- Year-over-year comparison (if prior year data exists)
- Quick links: Chat with CPA, Upload Document, View Report

This template reuses existing API endpoints: `/api/cpa/client/dashboard`, `/api/scenarios`, `/messages/notifications`.

---

### Task 16: Enable client scenario viewing

**Files:**
- Modify: `src/admin_panel/models/firm.py` (change `client_can_view_scenarios` default to `True`)

```python
# Change from:
client_can_view_scenarios: bool = False
# To:
client_can_view_scenarios: bool = True
```

This is a one-line change that unlocks the existing scenario comparison UI for clients.

---

## Phase 6: Consolidate Pricing (Fix 3 Conflicting Price Lists)

### Task 17: Unify pricing to single source of truth

**Files:**
- Modify: `src/admin_panel/services/platform_billing_config.py` (remove hardcoded prices)
- Modify: `src/core/api/billing_routes.py` (remove mock prices)
- Keep: `src/admin_panel/models/subscription.py` as THE authoritative source

The `SubscriptionPlan` DB table is the source of truth. All other code must read from it.

```python
# In platform_billing_config.py, replace hardcoded tiers with:
async def get_subscription_tiers(db: AsyncSession):
    from admin_panel.services.billing_service import BillingService
    service = BillingService(db)
    return await service.list_plans()
```

---

## Execution Summary

| Phase | Tasks | Impact | Effort |
|---|---|---|---|
| **Phase 0: Data Linkage** | Tasks 1-4 | CRITICAL — everything depends on this | 2-3 days |
| **Phase 1: Proactive Alerts** | Tasks 5-6 | The #1 differentiator vs competitors | 2 days |
| **Phase 2: CPA Review Gate** | Task 7 | Trust-builder for CPA firms | 1-2 days |
| **Phase 3: Dead End Fixes** | Tasks 8-13 | Polish — makes the product feel finished | 2-3 days |
| **Phase 4: Stripe Webhooks** | Task 14 | Billing reliability | 1 day |
| **Phase 5: Client Dashboard** | Tasks 15-16 | Year-round engagement | 1-2 days |
| **Phase 6: Pricing Cleanup** | Task 17 | Consistency | Half day |

**Total: ~17 tasks, ~10-14 days of focused work.**

**Dependency order:** Phase 0 → (Phase 1 + Phase 2 + Phase 3 in parallel) → Phase 4 → Phase 5 → Phase 6
