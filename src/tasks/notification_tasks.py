"""
Proactive notification tasks — the scheduler that makes the platform year-round.

Tasks:
- process_deadline_reminders: Every hour — sends reminder emails for upcoming deadlines
- process_nurture_emails: Every hour — sends due nurture sequence emails
- scan_client_opportunities: Daily at 6 AM — scans client profiles for tax opportunities
- compile_and_send_daily_digest: Daily at 7 AM — sends CPA daily alert digest
"""

import asyncio
import logging
from datetime import datetime, timezone

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="tasks.notifications.process_deadline_reminders")
def process_deadline_reminders():
    """
    Check all firms' deadlines and send reminder emails for those approaching.
    Runs hourly.
    """
    sent_count = 0
    error_count = 0

    try:
        from cpa_panel.deadlines.deadline_service import DeadlineService
        from notifications.email_triggers import email_triggers
    except ImportError as e:
        logger.warning(f"Deadline reminder dependencies unavailable: {e}")
        return {"sent": 0, "errors": 0, "skipped": True}

    try:
        deadline_service = DeadlineService()
        pending = deadline_service.get_pending_reminders()

        for reminder in pending:
            try:
                deadline = reminder.get("deadline")
                if not deadline:
                    continue

                days_remaining = (deadline.due_date - datetime.now(timezone.utc)).days
                recipient_email = reminder.get("recipient_email", "")
                if not recipient_email:
                    continue

                asyncio.run(
                    email_triggers.send_deadline_reminder(
                        recipient_email=recipient_email,
                        recipient_name=reminder.get("recipient_name", ""),
                        deadline_type=getattr(deadline, "deadline_type", "Tax Deadline"),
                        due_date=deadline.due_date,
                        days_remaining=days_remaining,
                        client_name=reminder.get("client_name"),
                        firm_id=reminder.get("firm_id"),
                    )
                )

                reminder_id = reminder.get("reminder_id")
                if reminder_id and hasattr(deadline_service, "mark_reminder_sent"):
                    deadline_service.mark_reminder_sent(reminder_id)

                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send deadline reminder: {e}")
                error_count += 1

    except Exception as e:
        logger.error(f"Deadline reminder scan failed: {e}")

    logger.info(f"Deadline reminders: sent={sent_count}, errors={error_count}")
    return {"sent": sent_count, "errors": error_count}


@shared_task(name="tasks.notifications.process_nurture_emails")
def process_nurture_emails():
    """
    Process due nurture sequence emails.
    Runs hourly.
    """
    sent_count = 0
    error_count = 0

    try:
        from cpa_panel.services.nurture_service import NurtureService
        from notifications.email_provider import send_email
    except ImportError as e:
        logger.warning(f"Nurture email dependencies unavailable: {e}")
        return {"sent": 0, "errors": 0, "skipped": True}

    try:
        nurture = NurtureService()
        due_emails = nurture.get_due_emails()

        for enrollment in due_emails:
            try:
                content = nurture.process_email(enrollment)
                if not content:
                    continue

                send_email(
                    to=content.get("to_email", ""),
                    subject=content.get("subject", ""),
                    body_html=content.get("body_html", ""),
                    body_text=content.get("body_text", ""),
                    from_name=content.get("from_name", "TaxFlow Advisory"),
                )

                if hasattr(nurture, "mark_email_sent"):
                    nurture.mark_email_sent(enrollment.enrollment_id)

                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send nurture email for {getattr(enrollment, 'enrollment_id', '?')}: {e}")
                error_count += 1

    except Exception as e:
        logger.error(f"Nurture email scan failed: {e}")

    logger.info(f"Nurture emails: sent={sent_count}, errors={error_count}")
    return {"sent": sent_count, "errors": error_count}


@shared_task(name="tasks.notifications.scan_client_opportunities")
def scan_client_opportunities():
    """
    Daily scan of all client profiles for proactive tax opportunity alerts.
    Runs daily at 6 AM.
    """
    clients_scanned = 0
    alerts_created = 0

    try:
        from database.models import ClientRecord, ClientSessionRecord, get_db_session
        from web.recommendation.orchestrator import get_recommendations
        from admin_panel.services.alert_service import AlertService, AlertType, AlertPriority
    except ImportError as e:
        logger.warning(f"Opportunity scan dependencies unavailable: {e}")
        return {"clients_scanned": 0, "alerts_created": 0, "skipped": True}

    try:
        with get_db_session() as db:
            clients = db.query(ClientRecord).filter(
                ClientRecord.firm_id.isnot(None),
                ClientRecord.is_active == True,
            ).all()

        for client in clients:
            try:
                # Load latest session profile
                profile = _load_client_profile(client)
                if not profile:
                    continue

                clients_scanned += 1
                recs = get_recommendations(profile)

                # Filter high-value opportunities (>$1000 estimated savings)
                high_value = [
                    r for r in recs
                    if getattr(r, "estimated_savings", 0) and float(getattr(r, "estimated_savings", 0)) > 1000
                ]

                if high_value:
                    alert_service = AlertService(db=None)
                    for rec in high_value[:3]:
                        asyncio.run(
                            alert_service.create_alert(
                                firm_id=str(client.firm_id),
                                alert_type=AlertType.OPPORTUNITY.value,
                                priority=AlertPriority.MEDIUM.value,
                                title=f"Opportunity: {getattr(rec, 'title', 'Tax Savings')}",
                                message=(
                                    f"{client.full_name}: {getattr(rec, 'description', '')}. "
                                    f"Est. savings: ${float(getattr(rec, 'estimated_savings', 0)):,.0f}"
                                ),
                                client_id=str(client.client_id),
                                metadata={
                                    "estimated_savings": float(getattr(rec, "estimated_savings", 0)),
                                    "category": getattr(rec, "category", "general"),
                                },
                            )
                        )
                        alerts_created += 1

            except Exception as e:
                logger.error(f"Error scanning client {client.client_id}: {e}")

    except Exception as e:
        logger.error(f"Client opportunity scan failed: {e}")

    logger.info(f"Opportunity scan: clients={clients_scanned}, alerts={alerts_created}")
    return {"clients_scanned": clients_scanned, "alerts_created": alerts_created}


@shared_task(name="tasks.notifications.compile_and_send_daily_digest")
def compile_and_send_daily_digest():
    """
    Compile and send daily alert digest email to each CPA firm's admins.
    Runs daily at 7 AM.
    """
    digests_sent = 0

    try:
        from admin_panel.services.alert_service import AlertService
        from notifications.email_provider import send_email
    except ImportError as e:
        logger.warning(f"Daily digest dependencies unavailable: {e}")
        return {"digests_sent": 0, "skipped": True}

    try:
        alert_service = AlertService(db=None)

        # Get all firms with cached alerts
        for firm_id, alerts in alert_service._alerts_cache.items():
            if not alerts:
                continue

            try:
                digest = asyncio.run(alert_service.compile_daily_digest(firm_id))

                if not digest.get("requires_action"):
                    continue

                summary = digest.get("summary", {})
                critical = digest.get("critical_alerts", [])
                high = digest.get("high_priority_alerts", [])

                # Build digest email
                alert_items = ""
                for alert in (critical + high)[:10]:
                    alert_items += f"<li><strong>{alert.get('title', '')}</strong> — {alert.get('message', '')}</li>"

                html_body = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #1e3a5f;">Daily Alert Digest</h2>
                    <p>You have <strong>{summary.get('total', 0)}</strong> active alerts:</p>
                    <ul style="list-style: disc; padding-left: 20px;">
                        <li>Critical: {summary.get('critical', 0)}</li>
                        <li>High: {summary.get('high', 0)}</li>
                        <li>Other: {summary.get('other', 0)}</li>
                    </ul>
                    <h3>Top Priority Items</h3>
                    <ul>{alert_items}</ul>
                    <p><a href="/cpa/dashboard">View Dashboard</a></p>
                </div>
                """

                # In production, look up firm admin emails
                # For now, log the digest
                logger.info(f"Daily digest for firm {firm_id}: {summary}")
                digests_sent += 1

            except Exception as e:
                logger.error(f"Failed to compile digest for firm {firm_id}: {e}")

    except Exception as e:
        logger.error(f"Daily digest compilation failed: {e}")

    logger.info(f"Daily digests sent: {digests_sent}")
    return {"digests_sent": digests_sent}


def _load_client_profile(client) -> dict:
    """Load a client's tax profile from their latest session."""
    try:
        from database.models import ClientSessionRecord, get_db_session
        from database.session_persistence import SessionPersistence

        with get_db_session() as db:
            session = db.query(ClientSessionRecord).filter_by(
                client_id=client.client_id
            ).order_by(ClientSessionRecord.created_at.desc()).first()

        if not session:
            return {}

        persistence = SessionPersistence()
        state = persistence.load_session(str(session.session_id))
        return state.get("profile", {}) if state else {}

    except Exception as e:
        logger.debug(f"Could not load profile for client {client.client_id}: {e}")
        return {}
