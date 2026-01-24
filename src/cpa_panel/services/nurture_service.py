"""
Lead Nurture Sequence Service

Automated email sequences to nurture leads through the conversion funnel:
1. Initial welcome series (0-7 days)
2. Value demonstration emails (7-14 days)
3. Social proof and testimonials (14-21 days)
4. Conversion push with offer (21-30 days)

Each sequence is customizable per CPA/tenant and adapts based on lead behavior.
"""

from __future__ import annotations

import uuid
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================

class NurtureSequenceType(str, Enum):
    """Types of nurture sequences."""
    INITIAL_WELCOME = "initial_welcome"
    VALUE_DEMO = "value_demo"
    SOCIAL_PROOF = "social_proof"
    CONVERSION_PUSH = "conversion_push"
    RE_ENGAGEMENT = "re_engagement"


class NurtureEmailStatus(str, Enum):
    """Status of a nurture email."""
    SCHEDULED = "scheduled"
    SENT = "sent"
    OPENED = "opened"
    CLICKED = "clicked"
    BOUNCED = "bounced"
    UNSUBSCRIBED = "unsubscribed"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class NurtureEmail:
    """A nurture sequence email."""
    email_id: str
    sequence_type: NurtureSequenceType
    sequence_order: int  # 1, 2, 3... within sequence
    subject: str
    body_template: str
    html_template: Optional[str] = None
    delay_days: int = 0  # Days after previous email
    delay_hours: int = 0  # Hours after previous email


@dataclass
class LeadNurtureEnrollment:
    """A lead's enrollment in a nurture sequence."""
    enrollment_id: str
    lead_id: str
    cpa_email: str
    sequence_type: NurtureSequenceType
    current_step: int = 1
    status: str = "active"  # active, paused, completed, converted, unsubscribed
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_email_at: Optional[datetime] = None
    next_email_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# =============================================================================
# NURTURE SEQUENCE TEMPLATES
# =============================================================================

NURTURE_SEQUENCES: Dict[NurtureSequenceType, List[NurtureEmail]] = {
    NurtureSequenceType.INITIAL_WELCOME: [
        NurtureEmail(
            email_id="welcome_1",
            sequence_type=NurtureSequenceType.INITIAL_WELCOME,
            sequence_order=1,
            subject="Your Tax Advisory Report is Ready!",
            delay_days=0,
            delay_hours=0,
            body_template="""
Hello {lead_name},

Thank you for using our Tax Advisory Assessment! Your personalized report is now ready.

Based on your tax profile, we've identified potential savings of {savings_range}.

Here are the next steps:
1. Review your report in our portal
2. Note the top opportunities we've identified
3. Schedule a free consultation to discuss your options

Your report link: {report_link}

Questions? Reply to this email anytime.

Best regards,
{cpa_name}
{cpa_firm}
            """.strip(),
            html_template=None,  # Will use plain text or auto-generate
        ),
        NurtureEmail(
            email_id="welcome_2",
            sequence_type=NurtureSequenceType.INITIAL_WELCOME,
            sequence_order=2,
            subject="Did you see your tax savings opportunity?",
            delay_days=2,
            delay_hours=0,
            body_template="""
Hi {lead_name},

I wanted to follow up on the tax advisory report we sent a couple days ago.

We identified {insight_count} potential opportunities for your tax situation, with estimated savings of {savings_range}.

The top opportunity we found was:
{top_insight}

Many of our clients miss these opportunities because they don't know what to look for. That's exactly what we help with.

Would you like to schedule a quick 15-minute call to discuss your options? It's completely free and there's no obligation.

Book a time here: {booking_link}

Best,
{cpa_name}
            """.strip(),
        ),
        NurtureEmail(
            email_id="welcome_3",
            sequence_type=NurtureSequenceType.INITIAL_WELCOME,
            sequence_order=3,
            subject="Quick question about your tax situation",
            delay_days=5,
            delay_hours=0,
            body_template="""
Hi {lead_name},

I'm reaching out one more time regarding your tax assessment.

Based on what you shared, you have a {complexity} tax situation with potential for significant optimization.

I understand you might be busy, so I wanted to offer a couple of options:

1. Schedule a 15-minute call: {booking_link}
2. Reply with questions: I'll answer them directly
3. Forward to your accountant: They might find our analysis useful

No pressure at all - I just want to make sure you have the opportunity to explore these savings.

Cheers,
{cpa_name}
            """.strip(),
        ),
    ],

    NurtureSequenceType.VALUE_DEMO: [
        NurtureEmail(
            email_id="value_1",
            sequence_type=NurtureSequenceType.VALUE_DEMO,
            sequence_order=1,
            subject="3 tax strategies most people miss",
            delay_days=7,
            delay_hours=0,
            body_template="""
Hi {lead_name},

I wanted to share three common tax strategies that many people overlook:

1. **Retirement Contribution Timing**
   - Maximizing contributions can reduce your taxable income significantly
   - Even small increases can have a big impact

2. **Charitable Giving Strategies**
   - Bunching donations in certain years can increase deductions
   - Donor-advised funds offer flexibility

3. **Business Expense Optimization**
   - Many deductible expenses go unclaimed
   - Home office deductions are often underutilized

Based on your tax profile, at least one of these strategies could benefit you.

Want to discuss which ones apply to your situation? Let's schedule a quick call.

{booking_link}

Best,
{cpa_name}
            """.strip(),
        ),
        NurtureEmail(
            email_id="value_2",
            sequence_type=NurtureSequenceType.VALUE_DEMO,
            sequence_order=2,
            subject="A real example of tax savings",
            delay_days=10,
            delay_hours=0,
            body_template="""
Hi {lead_name},

I wanted to share a quick story about a client with a similar tax situation to yours.

They came to us with a {complexity} tax situation and thought they were doing everything right. After our analysis, we found:

- $2,400 in overlooked deductions
- A retirement strategy adjustment worth $800/year
- A filing optimization that saved $600

Total first-year savings: $3,800

Their situation was similar to yours - which is why I think we could find similar opportunities for you.

Ready to explore your options? Schedule a free consultation:
{booking_link}

Best,
{cpa_name}
            """.strip(),
        ),
    ],

    NurtureSequenceType.SOCIAL_PROOF: [
        NurtureEmail(
            email_id="proof_1",
            sequence_type=NurtureSequenceType.SOCIAL_PROOF,
            sequence_order=1,
            subject="What our clients are saying",
            delay_days=14,
            delay_hours=0,
            body_template="""
Hi {lead_name},

I thought you might like to hear from some of our recent clients:

"I had no idea I was leaving money on the table. The analysis showed me exactly where to focus." - Sarah M.

"Professional, thorough, and they actually explained everything in plain English." - Michael R.

"Best tax decision I've made. Already saved more than the cost of their services." - Jennifer T.

We've helped hundreds of clients optimize their tax situations. Many started exactly where you are now - with a free assessment.

Your assessment showed potential savings of {savings_range}. Ready to take the next step?

{booking_link}

Best,
{cpa_name}
            """.strip(),
        ),
    ],

    NurtureSequenceType.CONVERSION_PUSH: [
        NurtureEmail(
            email_id="convert_1",
            sequence_type=NurtureSequenceType.CONVERSION_PUSH,
            sequence_order=1,
            subject="Special offer for you",
            delay_days=21,
            delay_hours=0,
            body_template="""
Hi {lead_name},

I wanted to reach out with a special offer.

Since you completed our tax assessment showing {savings_range} in potential savings, I'd like to offer you:

**20% off your first tax advisory consultation**

This includes:
- Full review of your tax assessment
- Detailed action plan with prioritized recommendations
- Clear next steps you can implement immediately

This offer expires in 7 days.

Ready to get started? Book your consultation:
{booking_link}

Best,
{cpa_name}
            """.strip(),
        ),
        NurtureEmail(
            email_id="convert_2",
            sequence_type=NurtureSequenceType.CONVERSION_PUSH,
            sequence_order=2,
            subject="Last chance: Your tax savings offer expires soon",
            delay_days=27,
            delay_hours=0,
            body_template="""
Hi {lead_name},

Just a quick reminder that your 20% discount offer expires in 3 days.

Your tax assessment showed {savings_range} in potential savings. Don't let this opportunity slip away.

Book your consultation before the offer expires:
{booking_link}

If now isn't the right time, no worries at all. Just reply and let me know - I'm happy to help whenever you're ready.

Best,
{cpa_name}
            """.strip(),
        ),
    ],

    NurtureSequenceType.RE_ENGAGEMENT: [
        NurtureEmail(
            email_id="reengage_1",
            sequence_type=NurtureSequenceType.RE_ENGAGEMENT,
            sequence_order=1,
            subject="Still thinking about your taxes?",
            delay_days=45,
            delay_hours=0,
            body_template="""
Hi {lead_name},

It's been a while since you completed your tax assessment, and I wanted to check in.

Your assessment showed potential savings of {savings_range}. If you haven't acted on those opportunities yet, they may still be available.

Tax laws change, but many strategies remain effective year after year. Would you like to:

1. Get an updated assessment
2. Schedule a quick call to discuss your options
3. Receive our latest tax tips newsletter

Just reply with 1, 2, or 3 and I'll take care of it.

Best,
{cpa_name}
            """.strip(),
        ),
    ],
}


# =============================================================================
# NURTURE SERVICE
# =============================================================================

class NurtureService:
    """Service for managing lead nurture sequences."""

    _instance: Optional['NurtureService'] = None

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self._db_path = db_path
        else:
            self._db_path = str(Path(__file__).parent.parent.parent / "database" / "jorss_gbo.db")

        self._ensure_tables()

    @classmethod
    def get_instance(cls) -> 'NurtureService':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_db_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self):
        """Ensure nurture tables exist."""
        conn = self._get_db_connection()
        cursor = conn.cursor()

        # Nurture enrollments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nurture_enrollments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                enrollment_id TEXT UNIQUE NOT NULL,
                lead_id TEXT NOT NULL,
                cpa_email TEXT NOT NULL,
                sequence_type TEXT NOT NULL,
                current_step INTEGER DEFAULT 1,
                status TEXT DEFAULT 'active',
                started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_email_at TEXT,
                next_email_at TEXT,
                completed_at TEXT
            )
        """)

        # Nurture emails sent table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nurture_emails_sent (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                send_id TEXT UNIQUE NOT NULL,
                enrollment_id TEXT NOT NULL,
                email_id TEXT NOT NULL,
                sequence_step INTEGER NOT NULL,
                status TEXT DEFAULT 'scheduled',
                scheduled_for TEXT,
                sent_at TEXT,
                opened_at TEXT,
                clicked_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Index for finding due emails
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_nurture_next_email
            ON nurture_enrollments(status, next_email_at)
        """)

        conn.commit()
        conn.close()

    # =========================================================================
    # ENROLLMENT METHODS
    # =========================================================================

    def enroll_lead(
        self,
        lead_id: str,
        cpa_email: str,
        sequence_type: NurtureSequenceType = NurtureSequenceType.INITIAL_WELCOME,
        lead_data: Optional[Dict[str, Any]] = None,
    ) -> LeadNurtureEnrollment:
        """
        Enroll a lead in a nurture sequence.

        Args:
            lead_id: Lead identifier
            cpa_email: CPA email (for branding)
            sequence_type: Type of nurture sequence
            lead_data: Optional lead data for personalization

        Returns:
            Created enrollment
        """
        enrollment_id = f"nurture-{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()

        # Get first email in sequence
        sequence = NURTURE_SEQUENCES.get(sequence_type, [])
        if not sequence:
            logger.warning(f"No sequence found for type {sequence_type}")
            sequence = NURTURE_SEQUENCES[NurtureSequenceType.INITIAL_WELCOME]

        first_email = sequence[0]
        next_email_at = now + timedelta(days=first_email.delay_days, hours=first_email.delay_hours)

        enrollment = LeadNurtureEnrollment(
            enrollment_id=enrollment_id,
            lead_id=lead_id,
            cpa_email=cpa_email,
            sequence_type=sequence_type,
            current_step=1,
            started_at=now,
            next_email_at=next_email_at,
        )

        # Persist
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO nurture_enrollments (
                    enrollment_id, lead_id, cpa_email, sequence_type,
                    current_step, status, started_at, next_email_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                enrollment_id,
                lead_id,
                cpa_email,
                sequence_type.value,
                1,
                "active",
                now.isoformat(),
                next_email_at.isoformat(),
            ))
            conn.commit()
            conn.close()

            logger.info(f"Enrolled lead {lead_id} in {sequence_type.value} sequence")

        except Exception as e:
            logger.error(f"Failed to enroll lead in nurture: {e}")

        return enrollment

    def pause_enrollment(self, enrollment_id: str) -> bool:
        """Pause a nurture enrollment."""
        return self._update_enrollment_status(enrollment_id, "paused")

    def resume_enrollment(self, enrollment_id: str) -> bool:
        """Resume a paused enrollment."""
        return self._update_enrollment_status(enrollment_id, "active")

    def complete_enrollment(self, enrollment_id: str, reason: str = "converted") -> bool:
        """Complete an enrollment (lead converted or finished sequence)."""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE nurture_enrollments
                SET status = ?, completed_at = ?
                WHERE enrollment_id = ?
            """, (reason, datetime.utcnow().isoformat(), enrollment_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to complete enrollment: {e}")
            return False

    def _update_enrollment_status(self, enrollment_id: str, status: str) -> bool:
        """Update enrollment status."""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE nurture_enrollments SET status = ? WHERE enrollment_id = ?
            """, (status, enrollment_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to update enrollment status: {e}")
            return False

    # =========================================================================
    # EMAIL PROCESSING
    # =========================================================================

    def get_due_emails(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get emails that are due to be sent.

        Returns list of emails with lead and enrollment data.
        """
        now = datetime.utcnow().isoformat()

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT e.*, l.first_name, l.email, l.lead_score, l.session_id
                FROM nurture_enrollments e
                LEFT JOIN lead_magnet_leads l ON e.lead_id = l.lead_id
                WHERE e.status = 'active' AND e.next_email_at <= ?
                ORDER BY e.next_email_at ASC
                LIMIT ?
            """, (now, limit))

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get due emails: {e}")
            return []

    def process_email(
        self,
        enrollment_id: str,
        lead_data: Dict[str, Any],
        cpa_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Process the next email in a sequence.

        Args:
            enrollment_id: Enrollment identifier
            lead_data: Lead data for personalization
            cpa_data: CPA data for branding

        Returns:
            Email content to send, or None if sequence is complete
        """
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            # Get enrollment
            cursor.execute("""
                SELECT * FROM nurture_enrollments WHERE enrollment_id = ?
            """, (enrollment_id,))
            row = cursor.fetchone()

            if not row:
                conn.close()
                return None

            sequence_type = NurtureSequenceType(row["sequence_type"])
            current_step = row["current_step"]

            # Get sequence
            sequence = NURTURE_SEQUENCES.get(sequence_type, [])

            if current_step > len(sequence):
                # Sequence complete
                self.complete_enrollment(enrollment_id, "completed")
                conn.close()
                return None

            # Get current email template
            email = sequence[current_step - 1]

            # Personalize email
            personalized = self._personalize_email(email, lead_data, cpa_data)

            # Record email send
            send_id = f"send-{uuid.uuid4().hex[:12]}"
            now = datetime.utcnow()

            cursor.execute("""
                INSERT INTO nurture_emails_sent (
                    send_id, enrollment_id, email_id, sequence_step, status, sent_at
                ) VALUES (?, ?, ?, ?, 'sent', ?)
            """, (send_id, enrollment_id, email.email_id, current_step, now.isoformat()))

            # Update enrollment for next email
            next_step = current_step + 1
            if next_step <= len(sequence):
                next_email = sequence[next_step - 1]
                next_email_at = now + timedelta(days=next_email.delay_days, hours=next_email.delay_hours)

                cursor.execute("""
                    UPDATE nurture_enrollments
                    SET current_step = ?, last_email_at = ?, next_email_at = ?
                    WHERE enrollment_id = ?
                """, (next_step, now.isoformat(), next_email_at.isoformat(), enrollment_id))
            else:
                # Last email in sequence
                cursor.execute("""
                    UPDATE nurture_enrollments
                    SET current_step = ?, last_email_at = ?, next_email_at = NULL, status = 'completed', completed_at = ?
                    WHERE enrollment_id = ?
                """, (next_step, now.isoformat(), now.isoformat(), enrollment_id))

            conn.commit()
            conn.close()

            logger.info(f"Processed nurture email {email.email_id} for enrollment {enrollment_id}")

            return personalized

        except Exception as e:
            logger.error(f"Failed to process email: {e}")
            return None

    def _personalize_email(
        self,
        email: NurtureEmail,
        lead_data: Dict[str, Any],
        cpa_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Personalize email template with lead and CPA data."""
        cpa_data = cpa_data or {}

        # Default values
        defaults = {
            "lead_name": lead_data.get("first_name", "there"),
            "savings_range": lead_data.get("savings_range", "$500 - $2,000"),
            "insight_count": lead_data.get("insight_count", 5),
            "complexity": lead_data.get("complexity", "moderate"),
            "top_insight": lead_data.get("top_insight", "Retirement contribution optimization"),
            "report_link": lead_data.get("report_link", "#"),
            "booking_link": cpa_data.get("booking_link", "#"),
            "cpa_name": cpa_data.get("cpa_name", "Your Tax Advisor"),
            "cpa_firm": cpa_data.get("cpa_firm", ""),
        }

        # Personalize subject and body
        subject = email.subject
        body = email.body_template

        for key, value in defaults.items():
            subject = subject.replace(f"{{{key}}}", str(value))
            body = body.replace(f"{{{key}}}", str(value))

        return {
            "email_id": email.email_id,
            "sequence_type": email.sequence_type.value,
            "sequence_order": email.sequence_order,
            "subject": subject,
            "body": body,
            "recipient_email": lead_data.get("email"),
            "recipient_name": lead_data.get("first_name"),
        }

    # =========================================================================
    # ANALYTICS
    # =========================================================================

    def get_enrollment_stats(self, cpa_email: Optional[str] = None) -> Dict[str, Any]:
        """Get nurture sequence statistics."""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            # By status
            if cpa_email:
                cursor.execute("""
                    SELECT status, COUNT(*) as count
                    FROM nurture_enrollments
                    WHERE cpa_email = ?
                    GROUP BY status
                """, (cpa_email,))
            else:
                cursor.execute("""
                    SELECT status, COUNT(*) as count
                    FROM nurture_enrollments
                    GROUP BY status
                """)
            by_status = {row["status"]: row["count"] for row in cursor.fetchall()}

            # By sequence type
            cursor.execute("""
                SELECT sequence_type, COUNT(*) as count
                FROM nurture_enrollments
                GROUP BY sequence_type
            """)
            by_type = {row["sequence_type"]: row["count"] for row in cursor.fetchall()}

            # Total emails sent
            cursor.execute("""
                SELECT COUNT(*) as count FROM nurture_emails_sent WHERE status = 'sent'
            """)
            total_sent = cursor.fetchone()["count"]

            conn.close()

            return {
                "by_status": by_status,
                "by_type": by_type,
                "total_sent": total_sent,
                "active": by_status.get("active", 0),
                "completed": by_status.get("completed", 0),
                "converted": by_status.get("converted", 0),
            }

        except Exception as e:
            logger.error(f"Failed to get enrollment stats: {e}")
            return {}


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

def get_nurture_service() -> NurtureService:
    """Get the nurture service singleton."""
    return NurtureService.get_instance()
