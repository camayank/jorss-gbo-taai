"""
Lead magnet delivery and notification logic.

Extracted from LeadMagnetService:
- _send_lead_notifications()
- Lead engagement and conversion helpers
- CPA profile management helpers
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def send_lead_notifications(
    session,
    lead,
    insights: list,
) -> None:
    """
    Send notifications when a new lead is captured.

    Sends:
    1. CPA notification email (new lead alert)
    2. Lead confirmation email (tier 1 report teaser)
    3. Celery proactive alerts (if available)
    """
    # 1. CPA notification
    try:
        _send_cpa_lead_alert(session, lead, insights)
    except Exception as e:
        logger.warning(f"Failed to send CPA lead alert: {e}")

    # 2. Lead confirmation email
    try:
        _send_lead_confirmation(lead, insights)
    except Exception as e:
        logger.warning(f"Failed to send lead confirmation: {e}")

    # 3. Celery proactive scheduler
    try:
        from tasks.notification_tasks import (
            send_lead_notification_task,
            schedule_follow_up_task,
        )
        send_lead_notification_task.delay(
            lead_id=lead.lead_id,
            cpa_id=lead.cpa_id,
            lead_email=lead.email,
            lead_name=lead.first_name,
            lead_score=lead.lead_score,
        )
        # Schedule a follow-up in 24 hours
        schedule_follow_up_task.apply_async(
            args=[lead.lead_id],
            countdown=86400,  # 24 hours
        )
    except ImportError:
        logger.debug("Celery notification tasks not available")
    except Exception as e:
        logger.warning(f"Failed to schedule notification tasks: {e}")


def _send_cpa_lead_alert(session, lead, insights: list) -> None:
    """Send alert email to CPA about new lead."""
    try:
        from services.email_provider import get_email_provider
        provider = get_email_provider()

        cpa_email = None
        if session.cpa_profile:
            cpa_email = session.cpa_profile.email

        if not cpa_email:
            logger.debug("No CPA email configured for lead alert")
            return

        total_savings = sum(i.savings_high for i in insights)
        subject = f"New Tax Lead: {lead.first_name} ({lead.lead_temperature.value.upper()})"
        body = f"""
New lead captured from your tax assessment funnel:

Name: {lead.first_name}
Email: {lead.email}
Phone: {lead.phone or 'Not provided'}
Lead Score: {lead.lead_score}/100 ({lead.lead_temperature.value})
Complexity: {lead.complexity.value}
Income Range: {lead.income_range}
Estimated Savings: ${total_savings:,.0f}

View details in your CPA dashboard.
"""
        provider.send_email(
            to_email=cpa_email,
            subject=subject,
            body=body,
        )
        logger.info(f"CPA alert sent to {cpa_email} for lead {lead.lead_id}")
    except ImportError:
        logger.debug("Email provider not available for CPA alerts")
    except Exception as e:
        logger.warning(f"CPA lead alert email failed: {e}")


def _send_lead_confirmation(lead, insights: list) -> None:
    """Send confirmation email to the lead."""
    try:
        from services.email_provider import get_email_provider
        provider = get_email_provider()

        total_savings = sum(i.savings_high for i in insights)
        subject = "Your Tax Assessment Results Are Ready"
        body = f"""
Hi {lead.first_name},

Thank you for completing your tax assessment. Here's a preview:

Potential Tax Savings: Up to ${total_savings:,.0f}
{len(insights)} optimization strategies identified
Complexity: {lead.complexity.value}

A tax professional will review your profile and reach out within 24 hours
to discuss your personalized tax strategy.

Best regards,
Tax Advisory Team
"""
        provider.send_email(
            to_email=lead.email,
            subject=subject,
            body=body,
        )
        logger.info(f"Lead confirmation email sent to {lead.email}")
    except ImportError:
        logger.debug("Email provider not available for lead confirmations")
    except Exception as e:
        logger.warning(f"Lead confirmation email failed: {e}")


def prepare_lead_engagement_data(
    lead_id: str,
    engagement_type: str = "consultation_booked",
) -> Dict[str, Any]:
    """
    Prepare data for lead engagement tracking.

    Used when marking a lead as engaged (e.g., consultation booked,
    engagement letter signed).
    """
    return {
        "lead_id": lead_id,
        "engagement_type": engagement_type,
        "engaged_at": datetime.now(timezone.utc).isoformat(),
    }
