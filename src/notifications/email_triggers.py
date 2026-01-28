"""
Email Notification Triggers

Comprehensive email notification triggers for all platform events.
Integrates with the email provider for delivery and tracks all notifications.

Trigger Categories:
- Appointment notifications (booking, reminder, cancellation)
- Task notifications (assignment, due, completion)
- Deadline notifications (approaching, overdue)
- Client notifications (document requests, messages, updates)
- Lead notifications (new lead, conversion, follow-up)
- Support notifications (ticket updates, resolution)
- Account notifications (welcome, password, billing)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID
from enum import Enum

from .email_provider import (
    get_email_provider,
    EmailMessage,
    DeliveryResult,
    send_email,
)

logger = logging.getLogger(__name__)


class EmailTriggerType(str, Enum):
    """Types of email triggers."""
    # Appointments
    APPOINTMENT_BOOKED = "appointment_booked"
    APPOINTMENT_CONFIRMED = "appointment_confirmed"
    APPOINTMENT_REMINDER_24H = "appointment_reminder_24h"
    APPOINTMENT_REMINDER_1H = "appointment_reminder_1h"
    APPOINTMENT_CANCELLED = "appointment_cancelled"
    APPOINTMENT_RESCHEDULED = "appointment_rescheduled"

    # Tasks
    TASK_ASSIGNED = "task_assigned"
    TASK_DUE_SOON = "task_due_soon"
    TASK_OVERDUE = "task_overdue"
    TASK_COMPLETED = "task_completed"
    TASK_COMMENT_ADDED = "task_comment_added"

    # Deadlines
    DEADLINE_APPROACHING_7D = "deadline_approaching_7d"
    DEADLINE_APPROACHING_3D = "deadline_approaching_3d"
    DEADLINE_APPROACHING_1D = "deadline_approaching_1d"
    DEADLINE_OVERDUE = "deadline_overdue"

    # Client
    CLIENT_DOCUMENT_REQUEST = "client_document_request"
    CLIENT_DOCUMENT_RECEIVED = "client_document_received"
    CLIENT_MESSAGE_RECEIVED = "client_message_received"
    CLIENT_RETURN_READY = "client_return_ready"
    CLIENT_SIGNATURE_NEEDED = "client_signature_needed"

    # Lead
    LEAD_CAPTURED = "lead_captured"
    LEAD_HOT_ALERT = "lead_hot_alert"
    LEAD_FOLLOW_UP_REMINDER = "lead_follow_up_reminder"
    LEAD_CONVERTED = "lead_converted"

    # Support
    TICKET_CREATED = "ticket_created"
    TICKET_ASSIGNED = "ticket_assigned"
    TICKET_UPDATED = "ticket_updated"
    TICKET_RESOLVED = "ticket_resolved"

    # Account
    ACCOUNT_WELCOME = "account_welcome"
    ACCOUNT_PASSWORD_RESET = "account_password_reset"
    ACCOUNT_INVITATION = "account_invitation"
    ACCOUNT_BILLING_REMINDER = "account_billing_reminder"
    ACCOUNT_SUBSCRIPTION_EXPIRING = "account_subscription_expiring"


@dataclass
class EmailNotification:
    """Email notification record."""
    id: UUID
    trigger_type: EmailTriggerType
    recipient_email: str
    recipient_name: str
    subject: str
    body_html: str
    body_text: str

    # Context
    firm_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    entity_id: Optional[str] = None  # Related entity (task_id, appointment_id, etc.)
    entity_type: Optional[str] = None  # Entity type (task, appointment, etc.)

    # Status
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    message_id: Optional[str] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class EmailTriggerService:
    """
    Service for triggering and sending email notifications.

    Provides templates and sending logic for all notification types.
    """

    def __init__(self):
        self._notifications: List[EmailNotification] = []
        self._from_name = "TaxFlow Advisory"
        self._from_email = None  # Use provider default

    # =========================================================================
    # APPOINTMENT TRIGGERS
    # =========================================================================

    async def send_appointment_booked(
        self,
        recipient_email: str,
        recipient_name: str,
        appointment_time: datetime,
        appointment_type: str,
        cpa_name: str,
        confirmation_code: str,
        meeting_link: Optional[str] = None,
        location: Optional[str] = None,
        firm_id: Optional[UUID] = None,
    ) -> DeliveryResult:
        """Send appointment booking confirmation."""
        time_str = appointment_time.strftime("%B %d, %Y at %I:%M %p")

        subject = f"Appointment Confirmed - {time_str}"
        body_text = f"""
Hello {recipient_name},

Your appointment has been scheduled!

Details:
- Date & Time: {time_str}
- Type: {appointment_type.replace('_', ' ').title()}
- With: {cpa_name}
- Confirmation Code: {confirmation_code}

{f'Meeting Link: {meeting_link}' if meeting_link else ''}
{f'Location: {location}' if location else ''}

Please save this confirmation code in case you need to reschedule or cancel.

Thank you,
{self._from_name}
        """.strip()

        body_html = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #10b981;">Appointment Confirmed</h2>
    <p>Hello {recipient_name},</p>
    <p>Your appointment has been scheduled!</p>

    <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <table style="width: 100%;">
            <tr><td style="padding: 8px 0; font-weight: bold;">Date & Time:</td><td>{time_str}</td></tr>
            <tr><td style="padding: 8px 0; font-weight: bold;">Type:</td><td>{appointment_type.replace('_', ' ').title()}</td></tr>
            <tr><td style="padding: 8px 0; font-weight: bold;">With:</td><td>{cpa_name}</td></tr>
            <tr><td style="padding: 8px 0; font-weight: bold;">Confirmation Code:</td><td style="font-family: monospace; font-size: 18px; color: #10b981;">{confirmation_code}</td></tr>
            {f'<tr><td style="padding: 8px 0; font-weight: bold;">Meeting Link:</td><td><a href="{meeting_link}">{meeting_link}</a></td></tr>' if meeting_link else ''}
            {f'<tr><td style="padding: 8px 0; font-weight: bold;">Location:</td><td>{location}</td></tr>' if location else ''}
        </table>
    </div>

    <p style="color: #6b7280; font-size: 14px;">Please save this confirmation code in case you need to reschedule or cancel.</p>

    <p>Thank you,<br>{self._from_name}</p>
</div>
        """

        return await self._send_email(
            EmailTriggerType.APPOINTMENT_BOOKED,
            recipient_email,
            recipient_name,
            subject,
            body_html,
            body_text,
            firm_id=firm_id,
            entity_id=confirmation_code,
            entity_type="appointment",
        )

    async def send_appointment_reminder(
        self,
        recipient_email: str,
        recipient_name: str,
        appointment_time: datetime,
        appointment_type: str,
        cpa_name: str,
        reminder_type: str,  # "24h" or "1h"
        meeting_link: Optional[str] = None,
        location: Optional[str] = None,
        firm_id: Optional[UUID] = None,
    ) -> DeliveryResult:
        """Send appointment reminder."""
        time_str = appointment_time.strftime("%B %d, %Y at %I:%M %p")
        time_until = "tomorrow" if reminder_type == "24h" else "in 1 hour"

        trigger = EmailTriggerType.APPOINTMENT_REMINDER_24H if reminder_type == "24h" else EmailTriggerType.APPOINTMENT_REMINDER_1H

        subject = f"Reminder: Appointment {time_until} - {appointment_type.replace('_', ' ').title()}"
        body_text = f"""
Hello {recipient_name},

This is a friendly reminder about your upcoming appointment.

Details:
- Date & Time: {time_str}
- Type: {appointment_type.replace('_', ' ').title()}
- With: {cpa_name}

{f'Meeting Link: {meeting_link}' if meeting_link else ''}
{f'Location: {location}' if location else ''}

We look forward to seeing you!

Thank you,
{self._from_name}
        """.strip()

        body_html = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #f59e0b;">Appointment Reminder</h2>
    <p>Hello {recipient_name},</p>
    <p>This is a friendly reminder about your upcoming appointment <strong>{time_until}</strong>.</p>

    <div style="background: #fef3c7; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #f59e0b;">
        <p style="margin: 0; font-size: 18px; font-weight: bold;">{time_str}</p>
        <p style="margin: 8px 0 0 0; color: #92400e;">{appointment_type.replace('_', ' ').title()} with {cpa_name}</p>
    </div>

    {f'<p><strong>Meeting Link:</strong> <a href="{meeting_link}">{meeting_link}</a></p>' if meeting_link else ''}
    {f'<p><strong>Location:</strong> {location}</p>' if location else ''}

    <p>We look forward to seeing you!</p>

    <p>Thank you,<br>{self._from_name}</p>
</div>
        """

        return await self._send_email(
            trigger,
            recipient_email,
            recipient_name,
            subject,
            body_html,
            body_text,
            firm_id=firm_id,
            entity_type="appointment",
        )

    async def send_appointment_cancelled(
        self,
        recipient_email: str,
        recipient_name: str,
        appointment_time: datetime,
        appointment_type: str,
        cancelled_by: str,
        reason: Optional[str] = None,
        firm_id: Optional[UUID] = None,
    ) -> DeliveryResult:
        """Send appointment cancellation notification."""
        time_str = appointment_time.strftime("%B %d, %Y at %I:%M %p")

        subject = f"Appointment Cancelled - {time_str}"
        body_text = f"""
Hello {recipient_name},

Your appointment scheduled for {time_str} has been cancelled.

Appointment Type: {appointment_type.replace('_', ' ').title()}
Cancelled By: {cancelled_by}
{f'Reason: {reason}' if reason else ''}

If you would like to reschedule, please visit our booking page or contact us.

Thank you,
{self._from_name}
        """.strip()

        body_html = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #ef4444;">Appointment Cancelled</h2>
    <p>Hello {recipient_name},</p>
    <p>Your appointment has been cancelled.</p>

    <div style="background: #fef2f2; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ef4444;">
        <p style="margin: 0;"><strong>Date & Time:</strong> {time_str}</p>
        <p style="margin: 8px 0;"><strong>Type:</strong> {appointment_type.replace('_', ' ').title()}</p>
        <p style="margin: 8px 0;"><strong>Cancelled By:</strong> {cancelled_by}</p>
        {f'<p style="margin: 8px 0;"><strong>Reason:</strong> {reason}</p>' if reason else ''}
    </div>

    <p>If you would like to reschedule, please visit our booking page or contact us.</p>

    <p>Thank you,<br>{self._from_name}</p>
</div>
        """

        return await self._send_email(
            EmailTriggerType.APPOINTMENT_CANCELLED,
            recipient_email,
            recipient_name,
            subject,
            body_html,
            body_text,
            firm_id=firm_id,
            entity_type="appointment",
        )

    # =========================================================================
    # TASK TRIGGERS
    # =========================================================================

    async def send_task_assigned(
        self,
        recipient_email: str,
        recipient_name: str,
        task_title: str,
        assigned_by: str,
        due_date: Optional[datetime] = None,
        priority: str = "normal",
        description: Optional[str] = None,
        firm_id: Optional[UUID] = None,
        task_id: Optional[UUID] = None,
    ) -> DeliveryResult:
        """Send task assignment notification."""
        due_str = due_date.strftime("%B %d, %Y") if due_date else "No due date"

        subject = f"New Task Assigned: {task_title}"
        body_text = f"""
Hello {recipient_name},

A new task has been assigned to you by {assigned_by}.

Task: {task_title}
Priority: {priority.title()}
Due Date: {due_str}
{f'Description: {description}' if description else ''}

Please log in to your dashboard to view and complete this task.

Thank you,
{self._from_name}
        """.strip()

        priority_colors = {
            "low": "#22c55e",
            "normal": "#3b82f6",
            "high": "#f97316",
            "urgent": "#ef4444",
        }
        color = priority_colors.get(priority.lower(), "#3b82f6")

        body_html = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #3b82f6;">New Task Assigned</h2>
    <p>Hello {recipient_name},</p>
    <p>A new task has been assigned to you by <strong>{assigned_by}</strong>.</p>

    <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid {color};">
        <h3 style="margin: 0 0 12px 0; color: #1f2937;">{task_title}</h3>
        <p style="margin: 8px 0;"><span style="background: {color}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; text-transform: uppercase;">{priority}</span></p>
        <p style="margin: 8px 0;"><strong>Due:</strong> {due_str}</p>
        {f'<p style="margin: 8px 0; color: #6b7280;">{description}</p>' if description else ''}
    </div>

    <p>Please log in to your dashboard to view and complete this task.</p>

    <p>Thank you,<br>{self._from_name}</p>
</div>
        """

        return await self._send_email(
            EmailTriggerType.TASK_ASSIGNED,
            recipient_email,
            recipient_name,
            subject,
            body_html,
            body_text,
            firm_id=firm_id,
            entity_id=str(task_id) if task_id else None,
            entity_type="task",
        )

    async def send_task_due_reminder(
        self,
        recipient_email: str,
        recipient_name: str,
        task_title: str,
        due_date: datetime,
        is_overdue: bool = False,
        firm_id: Optional[UUID] = None,
        task_id: Optional[UUID] = None,
    ) -> DeliveryResult:
        """Send task due/overdue reminder."""
        due_str = due_date.strftime("%B %d, %Y")
        trigger = EmailTriggerType.TASK_OVERDUE if is_overdue else EmailTriggerType.TASK_DUE_SOON

        if is_overdue:
            subject = f"OVERDUE: Task - {task_title}"
            status_text = "is overdue"
            color = "#ef4444"
        else:
            subject = f"Reminder: Task Due Soon - {task_title}"
            status_text = "is due soon"
            color = "#f59e0b"

        body_text = f"""
Hello {recipient_name},

This is a reminder that your task "{task_title}" {status_text}.

Due Date: {due_str}

Please log in to your dashboard to complete this task.

Thank you,
{self._from_name}
        """.strip()

        body_html = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: {color};">{'Task Overdue' if is_overdue else 'Task Due Soon'}</h2>
    <p>Hello {recipient_name},</p>
    <p>Your task <strong>{task_title}</strong> {status_text}.</p>

    <div style="background: {'#fef2f2' if is_overdue else '#fef3c7'}; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid {color};">
        <p style="margin: 0; font-size: 18px; font-weight: bold;">{task_title}</p>
        <p style="margin: 8px 0 0 0; color: {'#b91c1c' if is_overdue else '#92400e'};">Due: {due_str}</p>
    </div>

    <p>Please log in to your dashboard to complete this task.</p>

    <p>Thank you,<br>{self._from_name}</p>
</div>
        """

        return await self._send_email(
            trigger,
            recipient_email,
            recipient_name,
            subject,
            body_html,
            body_text,
            firm_id=firm_id,
            entity_id=str(task_id) if task_id else None,
            entity_type="task",
        )

    # =========================================================================
    # DEADLINE TRIGGERS
    # =========================================================================

    async def send_deadline_reminder(
        self,
        recipient_email: str,
        recipient_name: str,
        deadline_type: str,
        due_date: datetime,
        days_remaining: int,
        client_name: Optional[str] = None,
        firm_id: Optional[UUID] = None,
        deadline_id: Optional[UUID] = None,
    ) -> DeliveryResult:
        """Send deadline approaching reminder."""
        due_str = due_date.strftime("%B %d, %Y")

        if days_remaining <= 0:
            trigger = EmailTriggerType.DEADLINE_OVERDUE
            subject = f"OVERDUE: {deadline_type} Deadline"
            urgency = "overdue"
            color = "#ef4444"
        elif days_remaining == 1:
            trigger = EmailTriggerType.DEADLINE_APPROACHING_1D
            subject = f"Deadline Tomorrow: {deadline_type}"
            urgency = "due tomorrow"
            color = "#ef4444"
        elif days_remaining <= 3:
            trigger = EmailTriggerType.DEADLINE_APPROACHING_3D
            subject = f"Deadline in {days_remaining} Days: {deadline_type}"
            urgency = f"due in {days_remaining} days"
            color = "#f97316"
        else:
            trigger = EmailTriggerType.DEADLINE_APPROACHING_7D
            subject = f"Upcoming Deadline: {deadline_type}"
            urgency = f"due in {days_remaining} days"
            color = "#f59e0b"

        body_text = f"""
Hello {recipient_name},

This is a reminder about an important deadline.

Deadline: {deadline_type}
Due Date: {due_str} ({urgency})
{f'Client: {client_name}' if client_name else ''}

Please ensure all required actions are completed before the deadline.

Thank you,
{self._from_name}
        """.strip()

        body_html = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: {color};">Deadline {'Overdue' if days_remaining <= 0 else 'Reminder'}</h2>
    <p>Hello {recipient_name},</p>
    <p>This is a reminder about an important deadline.</p>

    <div style="background: {'#fef2f2' if days_remaining <= 1 else '#fef3c7'}; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid {color};">
        <p style="margin: 0; font-size: 18px; font-weight: bold;">{deadline_type}</p>
        <p style="margin: 8px 0; font-size: 24px; color: {color};">{due_str}</p>
        <p style="margin: 8px 0 0 0; text-transform: uppercase; font-size: 12px; color: {'#b91c1c' if days_remaining <= 1 else '#92400e'};">{urgency}</p>
        {f'<p style="margin: 12px 0 0 0;"><strong>Client:</strong> {client_name}</p>' if client_name else ''}
    </div>

    <p>Please ensure all required actions are completed before the deadline.</p>

    <p>Thank you,<br>{self._from_name}</p>
</div>
        """

        return await self._send_email(
            trigger,
            recipient_email,
            recipient_name,
            subject,
            body_html,
            body_text,
            firm_id=firm_id,
            entity_id=str(deadline_id) if deadline_id else None,
            entity_type="deadline",
        )

    # =========================================================================
    # CLIENT TRIGGERS
    # =========================================================================

    async def send_document_request(
        self,
        recipient_email: str,
        recipient_name: str,
        cpa_name: str,
        documents_needed: List[str],
        message: Optional[str] = None,
        due_date: Optional[datetime] = None,
        upload_link: Optional[str] = None,
        firm_id: Optional[UUID] = None,
    ) -> DeliveryResult:
        """Send document request to client."""
        due_str = due_date.strftime("%B %d, %Y") if due_date else None

        docs_list = "\n".join(f"- {doc}" for doc in documents_needed)
        docs_html = "".join(f"<li>{doc}</li>" for doc in documents_needed)

        subject = f"Documents Needed: {cpa_name} is requesting documents"
        body_text = f"""
Hello {recipient_name},

{cpa_name} is requesting the following documents for your tax preparation:

{docs_list}

{f'Please provide these documents by {due_str}.' if due_str else 'Please provide these documents at your earliest convenience.'}

{f'Note from your CPA: {message}' if message else ''}

{f'Upload your documents here: {upload_link}' if upload_link else 'Please log in to your client portal to upload the documents.'}

Thank you,
{self._from_name}
        """.strip()

        body_html = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #3b82f6;">Documents Needed</h2>
    <p>Hello {recipient_name},</p>
    <p><strong>{cpa_name}</strong> is requesting the following documents for your tax preparation:</p>

    <div style="background: #eff6ff; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <ul style="margin: 0; padding-left: 20px;">
            {docs_html}
        </ul>
    </div>

    <p>{f'Please provide these documents by <strong>{due_str}</strong>.' if due_str else 'Please provide these documents at your earliest convenience.'}</p>

    {f'<div style="background: #f3f4f6; padding: 16px; border-radius: 8px; margin: 20px 0;"><p style="margin: 0; font-style: italic;">"{message}"</p><p style="margin: 8px 0 0 0; color: #6b7280;">- {cpa_name}</p></div>' if message else ''}

    {f'<a href="{upload_link}" style="display: inline-block; background: #3b82f6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin-top: 16px;">Upload Documents</a>' if upload_link else '<p>Please log in to your client portal to upload the documents.</p>'}

    <p>Thank you,<br>{self._from_name}</p>
</div>
        """

        return await self._send_email(
            EmailTriggerType.CLIENT_DOCUMENT_REQUEST,
            recipient_email,
            recipient_name,
            subject,
            body_html,
            body_text,
            firm_id=firm_id,
            entity_type="document_request",
        )

    async def send_return_ready_notification(
        self,
        recipient_email: str,
        recipient_name: str,
        cpa_name: str,
        tax_year: int,
        review_link: Optional[str] = None,
        firm_id: Optional[UUID] = None,
        session_id: Optional[str] = None,
    ) -> DeliveryResult:
        """Send notification that tax return is ready for review."""
        subject = f"Your {tax_year} Tax Return is Ready for Review"
        body_text = f"""
Hello {recipient_name},

Great news! Your {tax_year} tax return has been completed by {cpa_name} and is ready for your review.

Please log in to review your return and provide your signature to authorize filing.

{f'Review your return: {review_link}' if review_link else 'Please log in to your client portal to review.'}

If you have any questions, please contact your tax professional.

Thank you,
{self._from_name}
        """.strip()

        body_html = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #10b981;">Your Tax Return is Ready!</h2>
    <p>Hello {recipient_name},</p>
    <p>Great news! Your <strong>{tax_year}</strong> tax return has been completed by <strong>{cpa_name}</strong> and is ready for your review.</p>

    <div style="background: #ecfdf5; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center; border: 2px solid #10b981;">
        <p style="margin: 0; font-size: 24px;">Tax Year {tax_year}</p>
        <p style="margin: 8px 0 0 0; color: #059669;">Ready for Review & Signature</p>
    </div>

    {f'<a href="{review_link}" style="display: inline-block; background: #10b981; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin-top: 16px;">Review Your Return</a>' if review_link else '<p>Please log in to your client portal to review.</p>'}

    <p style="margin-top: 24px;">If you have any questions, please contact your tax professional.</p>

    <p>Thank you,<br>{self._from_name}</p>
</div>
        """

        return await self._send_email(
            EmailTriggerType.CLIENT_RETURN_READY,
            recipient_email,
            recipient_name,
            subject,
            body_html,
            body_text,
            firm_id=firm_id,
            entity_id=session_id,
            entity_type="tax_return",
        )

    # =========================================================================
    # SUPPORT TRIGGERS
    # =========================================================================

    async def send_ticket_update(
        self,
        recipient_email: str,
        recipient_name: str,
        ticket_number: str,
        ticket_subject: str,
        update_message: str,
        update_type: str = "update",  # "created", "update", "resolved"
        agent_name: Optional[str] = None,
        firm_id: Optional[UUID] = None,
    ) -> DeliveryResult:
        """Send support ticket update notification."""
        if update_type == "created":
            trigger = EmailTriggerType.TICKET_CREATED
            subject = f"Ticket #{ticket_number} Created: {ticket_subject}"
            heading = "Support Ticket Created"
            color = "#3b82f6"
        elif update_type == "resolved":
            trigger = EmailTriggerType.TICKET_RESOLVED
            subject = f"Ticket #{ticket_number} Resolved: {ticket_subject}"
            heading = "Support Ticket Resolved"
            color = "#10b981"
        else:
            trigger = EmailTriggerType.TICKET_UPDATED
            subject = f"Ticket #{ticket_number} Updated: {ticket_subject}"
            heading = "Support Ticket Updated"
            color = "#f59e0b"

        body_text = f"""
Hello {recipient_name},

{heading}

Ticket: #{ticket_number}
Subject: {ticket_subject}
{f'Agent: {agent_name}' if agent_name else ''}

Message:
{update_message}

You can reply to this email or log in to view the full ticket history.

Thank you,
{self._from_name} Support
        """.strip()

        body_html = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: {color};">{heading}</h2>
    <p>Hello {recipient_name},</p>

    <div style="background: #f3f4f6; padding: 16px; border-radius: 8px; margin: 20px 0;">
        <p style="margin: 0;"><strong>Ticket:</strong> #{ticket_number}</p>
        <p style="margin: 8px 0;"><strong>Subject:</strong> {ticket_subject}</p>
        {f'<p style="margin: 8px 0;"><strong>Agent:</strong> {agent_name}</p>' if agent_name else ''}
    </div>

    <div style="background: white; border: 1px solid #e5e7eb; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <p style="margin: 0; white-space: pre-wrap;">{update_message}</p>
    </div>

    <p style="color: #6b7280; font-size: 14px;">You can reply to this email or log in to view the full ticket history.</p>

    <p>Thank you,<br>{self._from_name} Support</p>
</div>
        """

        return await self._send_email(
            trigger,
            recipient_email,
            recipient_name,
            subject,
            body_html,
            body_text,
            firm_id=firm_id,
            entity_id=ticket_number,
            entity_type="ticket",
        )

    # =========================================================================
    # ACCOUNT TRIGGERS
    # =========================================================================

    async def send_welcome_email(
        self,
        recipient_email: str,
        recipient_name: str,
        firm_name: str,
        login_link: Optional[str] = None,
        setup_guide_link: Optional[str] = None,
        firm_id: Optional[UUID] = None,
    ) -> DeliveryResult:
        """Send welcome email to new user."""
        subject = f"Welcome to {firm_name}!"
        body_text = f"""
Hello {recipient_name},

Welcome to {firm_name}! Your account has been created and you're ready to get started.

{f'Log in here: {login_link}' if login_link else 'Please log in to access your account.'}

{f'Getting started guide: {setup_guide_link}' if setup_guide_link else ''}

If you have any questions, don't hesitate to reach out to our support team.

Thank you,
{self._from_name}
        """.strip()

        body_html = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h1 style="color: #3b82f6; text-align: center;">Welcome!</h1>
    <p>Hello {recipient_name},</p>
    <p>Welcome to <strong>{firm_name}</strong>! Your account has been created and you're ready to get started.</p>

    <div style="text-align: center; margin: 30px 0;">
        {f'<a href="{login_link}" style="display: inline-block; background: #3b82f6; color: white; padding: 14px 32px; text-decoration: none; border-radius: 6px; font-size: 16px;">Log In to Your Account</a>' if login_link else ''}
    </div>

    {f'<p style="text-align: center;"><a href="{setup_guide_link}">View Getting Started Guide</a></p>' if setup_guide_link else ''}

    <p>If you have any questions, don't hesitate to reach out to our support team.</p>

    <p>Thank you,<br>{self._from_name}</p>
</div>
        """

        return await self._send_email(
            EmailTriggerType.ACCOUNT_WELCOME,
            recipient_email,
            recipient_name,
            subject,
            body_html,
            body_text,
            firm_id=firm_id,
            entity_type="account",
        )

    async def send_invitation_email(
        self,
        recipient_email: str,
        recipient_name: str,
        inviter_name: str,
        firm_name: str,
        role: str,
        invitation_link: str,
        expires_in_days: int = 7,
        firm_id: Optional[UUID] = None,
    ) -> DeliveryResult:
        """Send team invitation email."""
        subject = f"You're invited to join {firm_name}"
        body_text = f"""
Hello{f' {recipient_name}' if recipient_name else ''},

{inviter_name} has invited you to join {firm_name} as a {role}.

Click the link below to accept the invitation and create your account:
{invitation_link}

This invitation will expire in {expires_in_days} days.

If you have any questions, please contact {inviter_name} or our support team.

Thank you,
{self._from_name}
        """.strip()

        body_html = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #3b82f6;">You're Invited!</h2>
    <p>Hello{f' {recipient_name}' if recipient_name else ''},</p>
    <p><strong>{inviter_name}</strong> has invited you to join <strong>{firm_name}</strong> as a <strong>{role}</strong>.</p>

    <div style="text-align: center; margin: 30px 0;">
        <a href="{invitation_link}" style="display: inline-block; background: #10b981; color: white; padding: 14px 32px; text-decoration: none; border-radius: 6px; font-size: 16px;">Accept Invitation</a>
    </div>

    <p style="color: #6b7280; font-size: 14px; text-align: center;">This invitation will expire in {expires_in_days} days.</p>

    <p>If you have any questions, please contact {inviter_name} or our support team.</p>

    <p>Thank you,<br>{self._from_name}</p>
</div>
        """

        return await self._send_email(
            EmailTriggerType.ACCOUNT_INVITATION,
            recipient_email,
            recipient_name or "there",
            subject,
            body_html,
            body_text,
            firm_id=firm_id,
            entity_type="invitation",
        )

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    async def _send_email(
        self,
        trigger_type: EmailTriggerType,
        recipient_email: str,
        recipient_name: str,
        subject: str,
        body_html: str,
        body_text: str,
        firm_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        entity_id: Optional[str] = None,
        entity_type: Optional[str] = None,
    ) -> DeliveryResult:
        """Send email and track the notification."""
        from uuid import uuid4

        notification = EmailNotification(
            id=uuid4(),
            trigger_type=trigger_type,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            firm_id=firm_id,
            user_id=user_id,
            entity_id=entity_id,
            entity_type=entity_type,
        )

        try:
            result = send_email(
                to=recipient_email,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                from_name=self._from_name,
                tags=[f"trigger:{trigger_type.value}", f"entity:{entity_type}"] if entity_type else [],
            )

            if result.success:
                notification.sent_at = datetime.utcnow()
                notification.message_id = result.message_id
            else:
                notification.failed_at = datetime.utcnow()
                notification.error_message = result.error_message

            self._notifications.append(notification)

            # Keep last 1000 notifications
            if len(self._notifications) > 1000:
                self._notifications = self._notifications[-1000:]

            logger.info(
                f"[EMAIL] {trigger_type.value} to {recipient_email}: "
                f"{'sent' if result.success else 'failed'}"
            )

            return result

        except Exception as e:
            logger.exception(f"[EMAIL] Error sending {trigger_type.value}: {e}")
            notification.failed_at = datetime.utcnow()
            notification.error_message = str(e)
            self._notifications.append(notification)

            return DeliveryResult(
                success=False,
                status=DeliveryStatus.FAILED,
                error_message=str(e),
            )

    def get_notification_stats(self) -> Dict[str, Any]:
        """Get email notification statistics."""
        total = len(self._notifications)
        sent = sum(1 for n in self._notifications if n.sent_at)
        failed = sum(1 for n in self._notifications if n.failed_at)

        by_trigger = {}
        for n in self._notifications:
            trigger = n.trigger_type.value
            by_trigger[trigger] = by_trigger.get(trigger, 0) + 1

        return {
            "total": total,
            "sent": sent,
            "failed": failed,
            "success_rate": round(sent / total * 100, 2) if total > 0 else 0,
            "by_trigger": by_trigger,
        }


# Singleton instance
email_triggers = EmailTriggerService()


# Convenience functions
async def send_appointment_booked(*args, **kwargs) -> DeliveryResult:
    return await email_triggers.send_appointment_booked(*args, **kwargs)


async def send_appointment_reminder(*args, **kwargs) -> DeliveryResult:
    return await email_triggers.send_appointment_reminder(*args, **kwargs)


async def send_task_assigned(*args, **kwargs) -> DeliveryResult:
    return await email_triggers.send_task_assigned(*args, **kwargs)


async def send_deadline_reminder(*args, **kwargs) -> DeliveryResult:
    return await email_triggers.send_deadline_reminder(*args, **kwargs)


async def send_document_request(*args, **kwargs) -> DeliveryResult:
    return await email_triggers.send_document_request(*args, **kwargs)


async def send_ticket_update(*args, **kwargs) -> DeliveryResult:
    return await email_triggers.send_ticket_update(*args, **kwargs)


async def send_welcome_email(*args, **kwargs) -> DeliveryResult:
    return await email_triggers.send_welcome_email(*args, **kwargs)


async def send_invitation_email(*args, **kwargs) -> DeliveryResult:
    return await email_triggers.send_invitation_email(*args, **kwargs)
