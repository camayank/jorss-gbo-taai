"""
Funnel Orchestrator Service - Wires together all funnel components.

This service orchestrates the complete lead-to-client funnel:
1. ATTRACT: Quick estimate → Teaser generation
2. QUALIFY: Questionnaire → Complexity scoring → Lead scoring
3. CONVERT: Advisory report generation → PDF export → Email delivery
4. MATCH: Auto-assignment → CPA notification → Lead handoff
5. FACILITATE: Nurture sequences → E-sign → Service delivery

All existing components are wired together here for seamless flow.
"""

from __future__ import annotations

import os
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from io import BytesIO
import tempfile
from calculator.decimal_math import money, to_decimal

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class FunnelConfig:
    """Funnel configuration settings."""
    # Platform fee for lead revenue (separate from Stripe processing fee)
    lead_revenue_share_percent: float = 15.0  # 15% of engagement value
    high_value_revenue_share_percent: float = 12.0  # 12% for engagements > $5000

    # Auto-assignment settings
    auto_assignment_enabled: bool = True
    assignment_algorithm: str = "round_robin"  # "round_robin", "complexity_match", "capacity"
    max_leads_per_cpa_per_day: int = 10

    # Email settings
    send_report_to_lead: bool = True
    send_report_to_cpa: bool = True
    send_hot_lead_alerts: bool = True

    # Nurture settings
    auto_enroll_nurture: bool = True
    default_nurture_sequence: str = "initial_welcome"


# Load config from environment
def get_funnel_config() -> FunnelConfig:
    """Get funnel configuration from environment."""
    return FunnelConfig(
        lead_revenue_share_percent=float(os.environ.get("LEAD_REVENUE_SHARE_PERCENT", "15.0")),
        high_value_revenue_share_percent=float(os.environ.get("HIGH_VALUE_REVENUE_SHARE_PERCENT", "12.0")),
        auto_assignment_enabled=os.environ.get("AUTO_ASSIGNMENT_ENABLED", "true").lower() == "true",
        assignment_algorithm=os.environ.get("ASSIGNMENT_ALGORITHM", "round_robin"),
        max_leads_per_cpa_per_day=int(os.environ.get("MAX_LEADS_PER_CPA_PER_DAY", "10")),
        send_report_to_lead=os.environ.get("SEND_REPORT_TO_LEAD", "true").lower() == "true",
        send_report_to_cpa=os.environ.get("SEND_REPORT_TO_CPA", "true").lower() == "true",
        auto_enroll_nurture=os.environ.get("AUTO_ENROLL_NURTURE", "true").lower() == "true",
    )


# =============================================================================
# LEAD AUTO-ASSIGNMENT
# =============================================================================

@dataclass
class CPACapacity:
    """CPA capacity for lead assignment."""
    cpa_id: str
    cpa_email: str
    cpa_name: str
    firm_id: str

    # Capacity metrics
    leads_today: int = 0
    leads_this_week: int = 0
    active_leads: int = 0
    max_daily_leads: int = 10

    # Specialization (for complexity matching)
    handles_complex: bool = True
    handles_business: bool = True
    handles_international: bool = False

    # Availability
    is_available: bool = True
    last_assigned_at: Optional[datetime] = None


class LeadAutoAssigner:
    """
    Automatically assigns leads to CPAs using configurable algorithms.

    Algorithms:
    - round_robin: Distribute evenly across available CPAs
    - complexity_match: Match lead complexity to CPA expertise
    - capacity: Assign to CPA with most available capacity
    """

    def __init__(self):
        self._cpa_capacities: Dict[str, CPACapacity] = {}
        self._assignment_index: int = 0  # For round-robin

    def register_cpa(self, cpa: CPACapacity):
        """Register a CPA for lead assignment."""
        self._cpa_capacities[cpa.cpa_id] = cpa
        logger.info(f"Registered CPA {cpa.cpa_name} ({cpa.cpa_id}) for auto-assignment")

    def assign_lead(
        self,
        lead_id: str,
        lead_data: Dict[str, Any],
        algorithm: str = "round_robin",
        firm_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Automatically assign a lead to a CPA.

        Args:
            lead_id: Lead identifier
            lead_data: Lead data including complexity, source, etc.
            algorithm: Assignment algorithm to use
            firm_id: Optional firm ID to restrict assignment to

        Returns:
            CPA ID if assigned, None if no CPA available
        """
        # Get available CPAs
        available = self._get_available_cpas(firm_id)
        if not available:
            logger.warning(f"No available CPAs for lead {lead_id}")
            return None

        # Select CPA based on algorithm
        if algorithm == "round_robin":
            cpa = self._assign_round_robin(available)
        elif algorithm == "complexity_match":
            cpa = self._assign_complexity_match(available, lead_data)
        elif algorithm == "capacity":
            cpa = self._assign_by_capacity(available)
        else:
            cpa = self._assign_round_robin(available)

        if cpa:
            # Update capacity
            cpa.leads_today += 1
            cpa.leads_this_week += 1
            cpa.active_leads += 1
            cpa.last_assigned_at = datetime.utcnow()

            logger.info(f"Auto-assigned lead {lead_id} to CPA {cpa.cpa_name} ({cpa.cpa_id})")
            return cpa.cpa_id

        return None

    def _get_available_cpas(self, firm_id: Optional[str] = None) -> List[CPACapacity]:
        """Get list of available CPAs."""
        available = []
        config = get_funnel_config()

        for cpa in self._cpa_capacities.values():
            # Check availability
            if not cpa.is_available:
                continue

            # Check firm restriction
            if firm_id and cpa.firm_id != firm_id:
                continue

            # Check daily capacity
            if cpa.leads_today >= config.max_leads_per_cpa_per_day:
                continue

            available.append(cpa)

        return available

    def _assign_round_robin(self, cpas: List[CPACapacity]) -> Optional[CPACapacity]:
        """Assign using round-robin algorithm."""
        if not cpas:
            return None

        # Sort by last assigned time to ensure fairness
        cpas_sorted = sorted(
            cpas,
            key=lambda c: c.last_assigned_at or datetime.min
        )

        return cpas_sorted[0]

    def _assign_complexity_match(
        self,
        cpas: List[CPACapacity],
        lead_data: Dict[str, Any],
    ) -> Optional[CPACapacity]:
        """Assign by matching lead complexity to CPA expertise."""
        if not cpas:
            return None

        complexity = lead_data.get("complexity", "simple")
        has_business = lead_data.get("has_business", False)
        has_international = lead_data.get("has_international", False)

        # Filter by capability
        matching = cpas

        if complexity in ("complex", "professional"):
            matching = [c for c in matching if c.handles_complex]

        if has_business:
            matching = [c for c in matching if c.handles_business]

        if has_international:
            matching = [c for c in matching if c.handles_international]

        # Fall back to any available if no match
        if not matching:
            matching = cpas

        # Among matches, use round-robin
        return self._assign_round_robin(matching)

    def _assign_by_capacity(self, cpas: List[CPACapacity]) -> Optional[CPACapacity]:
        """Assign to CPA with most available capacity."""
        if not cpas:
            return None

        # Sort by remaining capacity (most capacity first)
        cpas_sorted = sorted(
            cpas,
            key=lambda c: c.max_daily_leads - c.leads_today,
            reverse=True
        )

        return cpas_sorted[0]

    def reset_daily_counts(self):
        """Reset daily lead counts (call at midnight)."""
        for cpa in self._cpa_capacities.values():
            cpa.leads_today = 0
        logger.info("Reset daily lead counts for all CPAs")

    def reset_weekly_counts(self):
        """Reset weekly lead counts (call on Monday)."""
        for cpa in self._cpa_capacities.values():
            cpa.leads_this_week = 0
        logger.info("Reset weekly lead counts for all CPAs")


# Singleton
_auto_assigner: Optional[LeadAutoAssigner] = None

def get_auto_assigner() -> LeadAutoAssigner:
    """Get singleton auto-assigner."""
    global _auto_assigner
    if _auto_assigner is None:
        _auto_assigner = LeadAutoAssigner()
    return _auto_assigner


# =============================================================================
# PLATFORM FEE CALCULATOR
# =============================================================================

@dataclass
class PlatformFeeCalculation:
    """Platform fee calculation result."""
    engagement_value: float
    lead_revenue_share: float
    lead_revenue_share_percent: float
    stripe_processing_fee: float
    stripe_processing_percent: float
    total_platform_fee: float
    net_to_cpa: float
    breakdown: Dict[str, float]


def calculate_lead_platform_fee(
    engagement_value: float,
    is_high_value: bool = False,
) -> PlatformFeeCalculation:
    """
    Calculate platform fees for a lead engagement.

    This combines:
    1. Lead revenue share (15% standard, 12% for high-value)
    2. Stripe processing fee (2.9% + $0.30)

    Args:
        engagement_value: Total engagement value in dollars
        is_high_value: Whether this is a high-value engagement (>$5000)

    Returns:
        Detailed fee calculation
    """
    config = get_funnel_config()

    # Determine revenue share percentage
    if is_high_value or engagement_value > 5000:
        revenue_share_percent = config.high_value_revenue_share_percent
    else:
        revenue_share_percent = config.lead_revenue_share_percent

    # Calculate lead revenue share
    lead_revenue_share = engagement_value * (revenue_share_percent / 100)

    # Stripe processing fee (2.9% + $0.30)
    stripe_percent = 2.9
    stripe_fixed = 0.30
    stripe_fee = engagement_value * (stripe_percent / 100) + stripe_fixed

    # Total platform fee
    total_fee = lead_revenue_share + stripe_fee

    # Net to CPA
    net_to_cpa = engagement_value - total_fee

    return PlatformFeeCalculation(
        engagement_value=engagement_value,
        lead_revenue_share=float(money(lead_revenue_share)),
        lead_revenue_share_percent=revenue_share_percent,
        stripe_processing_fee=float(money(stripe_fee)),
        stripe_processing_percent=stripe_percent,
        total_platform_fee=float(money(total_fee)),
        net_to_cpa=float(money(net_to_cpa)),
        breakdown={
            "engagement_value": engagement_value,
            "lead_revenue_share": float(money(lead_revenue_share)),
            "stripe_fee": float(money(stripe_fee)),
            "total_fee": float(money(total_fee)),
            "net_to_cpa": float(money(net_to_cpa)),
        }
    )


# =============================================================================
# FUNNEL ORCHESTRATOR
# =============================================================================

class FunnelOrchestrator:
    """
    Main orchestrator that wires together all funnel components.

    This class coordinates:
    - Lead creation and scoring
    - Advisory report generation
    - PDF export
    - Email delivery
    - CPA assignment
    - Nurture enrollment
    - E-signature flow
    """

    def __init__(self):
        self.config = get_funnel_config()
        self._pdf_exporter = None
        self._email_service = None
        self._nurture_service = None
        self._report_service = None
        self._lead_service = None

    # Lazy loading of services
    @property
    def pdf_exporter(self):
        if self._pdf_exporter is None:
            from export.advisory_pdf_exporter import AdvisoryPDFExporter
            self._pdf_exporter = AdvisoryPDFExporter()
        return self._pdf_exporter

    @property
    def email_service(self):
        if self._email_service is None:
            from notifications.email_triggers import EmailTriggerService
            self._email_service = EmailTriggerService()
        return self._email_service

    @property
    def nurture_service(self):
        if self._nurture_service is None:
            from cpa_panel.services.nurture_service import get_nurture_service
            self._nurture_service = get_nurture_service()
        return self._nurture_service

    @property
    def report_service(self):
        if self._report_service is None:
            from cpa_panel.services.advisory_report_service import get_report_service
            self._report_service = get_report_service()
        return self._report_service

    @property
    def lead_service(self):
        if self._lead_service is None:
            from cpa_panel.services.lead_generation_service import get_lead_generation_service
            self._lead_service = get_lead_generation_service()
        return self._lead_service

    # =========================================================================
    # STEP 3: CONVERT - Generate report, export PDF, send emails
    # =========================================================================

    async def generate_and_deliver_report(
        self,
        lead_id: str,
        session_id: str,
        lead_email: str,
        lead_name: str,
        cpa_id: Optional[str] = None,
        cpa_email: Optional[str] = None,
        cpa_name: Optional[str] = None,
        brand_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate advisory report, export to PDF, and deliver via email.

        This is the main CONVERT step that:
        1. Generates the advisory report
        2. Exports to professional PDF
        3. Sends PDF to lead
        4. Sends notification + PDF to CPA
        5. Enrolls in nurture sequence

        Args:
            lead_id: Lead identifier
            session_id: Tax session ID
            lead_email: Lead's email address
            lead_name: Lead's name
            cpa_id: Optional CPA ID (will auto-assign if not provided)
            cpa_email: CPA email for notification
            cpa_name: CPA name for branding
            brand_config: Optional branding configuration

        Returns:
            Result with PDF path, delivery status, and assignment info
        """
        result = {
            "success": False,
            "lead_id": lead_id,
            "session_id": session_id,
            "report_generated": False,
            "pdf_generated": False,
            "pdf_path": None,
            "lead_email_sent": False,
            "cpa_email_sent": False,
            "cpa_assigned": None,
            "nurture_enrolled": False,
            "errors": [],
        }

        try:
            # Step 1: Generate advisory report
            logger.info(f"Generating advisory report for lead {lead_id}, session {session_id}")
            report_result = self.report_service.generate_report(session_id)

            if not report_result.get("success"):
                result["errors"].append(f"Report generation failed: {report_result.get('error')}")
                return result

            result["report_generated"] = True
            report_data = report_result.get("report", {})
            total_savings = report_data.get("total_potential_savings", 0)

            # Step 2: Export to PDF
            logger.info(f"Exporting report to PDF for lead {lead_id}")
            pdf_result = await self._export_report_to_pdf(
                report_data=report_data,
                lead_name=lead_name,
                brand_config=brand_config,
            )

            if pdf_result.get("success"):
                result["pdf_generated"] = True
                result["pdf_path"] = pdf_result.get("pdf_path")
            else:
                result["errors"].append(f"PDF export failed: {pdf_result.get('error')}")

            # Step 3: Auto-assign CPA if not provided
            if not cpa_id and self.config.auto_assignment_enabled:
                logger.info(f"Auto-assigning CPA for lead {lead_id}")
                assigner = get_auto_assigner()
                cpa_id = assigner.assign_lead(
                    lead_id=lead_id,
                    lead_data={
                        "complexity": report_data.get("complexity", "moderate"),
                        "total_savings": total_savings,
                    },
                )
                if cpa_id:
                    result["cpa_assigned"] = cpa_id
                    # Update lead with assignment
                    self.lead_service.assign_lead_to_cpa(lead_id, cpa_id)

            # Step 4: Send email to lead with report
            if self.config.send_report_to_lead and result["pdf_generated"]:
                logger.info(f"Sending report to lead {lead_email}")
                email_result = await self._send_report_to_lead(
                    lead_email=lead_email,
                    lead_name=lead_name,
                    pdf_path=result["pdf_path"],
                    total_savings=total_savings,
                    cpa_name=cpa_name,
                )
                result["lead_email_sent"] = email_result.get("success", False)
                if not result["lead_email_sent"]:
                    result["errors"].append(f"Lead email failed: {email_result.get('error')}")

            # Step 5: Send notification to CPA
            if self.config.send_report_to_cpa and cpa_email:
                logger.info(f"Sending lead notification to CPA {cpa_email}")
                cpa_email_result = await self._send_lead_notification_to_cpa(
                    cpa_email=cpa_email,
                    cpa_name=cpa_name or "CPA",
                    lead_name=lead_name,
                    lead_email=lead_email,
                    total_savings=total_savings,
                    pdf_path=result.get("pdf_path"),
                    lead_id=lead_id,
                )
                result["cpa_email_sent"] = cpa_email_result.get("success", False)
                if not result["cpa_email_sent"]:
                    result["errors"].append(f"CPA email failed: {cpa_email_result.get('error')}")

            # Step 6: Enroll in nurture sequence
            if self.config.auto_enroll_nurture:
                logger.info(f"Enrolling lead {lead_id} in nurture sequence")
                try:
                    from cpa_panel.services.nurture_service import NurtureSequenceType
                    enrollment = self.nurture_service.enroll_lead(
                        lead_id=lead_id,
                        cpa_email=cpa_email or "platform@jorss-gbo.com",
                        sequence_type=NurtureSequenceType.INITIAL_WELCOME,
                        lead_data={
                            "first_name": lead_name,
                            "email": lead_email,
                            "savings_range": f"${total_savings:,.0f}",
                        }
                    )
                    result["nurture_enrolled"] = True
                except Exception as e:
                    result["errors"].append(f"Nurture enrollment failed: {e}")

            result["success"] = result["report_generated"] and (
                result["pdf_generated"] or result["lead_email_sent"]
            )

            logger.info(f"Funnel orchestration complete for lead {lead_id}: {result}")
            return result

        except Exception as e:
            logger.exception(f"Funnel orchestration failed for lead {lead_id}: {e}")
            result["errors"].append(str(e))
            return result

    async def _export_report_to_pdf(
        self,
        report_data: Dict[str, Any],
        lead_name: str,
        brand_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Export advisory report to PDF."""
        try:
            from export.advisory_pdf_exporter import AdvisoryPDFExporter, CPABrandConfig

            exporter = AdvisoryPDFExporter()

            # Create brand config
            brand = None
            if brand_config:
                brand = CPABrandConfig(
                    firm_name=brand_config.get("firm_name", "Tax Advisory Services"),
                    advisor_name=brand_config.get("advisor_name"),
                    contact_email=brand_config.get("contact_email"),
                    contact_phone=brand_config.get("contact_phone"),
                    logo_path=brand_config.get("logo_path"),
                    primary_color=brand_config.get("primary_color", "#2c5aa0"),
                )

            # Generate PDF to temp file
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            safe_name = "".join(c for c in lead_name if c.isalnum() or c in " _-").strip()
            filename = f"advisory_report_{safe_name}_{timestamp}.pdf"

            # Use temp directory for PDF storage
            pdf_dir = Path(tempfile.gettempdir()) / "advisory_reports"
            pdf_dir.mkdir(parents=True, exist_ok=True)
            pdf_path = pdf_dir / filename

            # Export
            exporter.export_report(
                report_data=report_data,
                output_path=str(pdf_path),
                brand_config=brand,
            )

            return {
                "success": True,
                "pdf_path": str(pdf_path),
                "filename": filename,
            }

        except Exception as e:
            logger.error(f"PDF export failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def _send_report_to_lead(
        self,
        lead_email: str,
        lead_name: str,
        pdf_path: str,
        total_savings: float,
        cpa_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send advisory report to lead via email."""
        try:
            from notifications.email_provider import send_email_with_attachment

            subject = "Your Personalized Tax Advisory Report is Ready!"

            body_html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #10b981;">Your Tax Advisory Report</h2>
                <p>Hello {lead_name},</p>

                <p>Great news! Your personalized tax advisory report is now ready.</p>

                <div style="background: #ecfdf5; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center;">
                    <p style="margin: 0; font-size: 14px; color: #065f46;">Potential Tax Savings Identified</p>
                    <p style="margin: 8px 0 0 0; font-size: 32px; font-weight: bold; color: #10b981;">${total_savings:,.0f}</p>
                </div>

                <p>Your comprehensive report is attached to this email. It includes:</p>
                <ul>
                    <li>Executive summary of your tax situation</li>
                    <li>Detailed analysis of optimization opportunities</li>
                    <li>Prioritized action items</li>
                    <li>Personalized recommendations</li>
                </ul>

                <p><strong>Next Steps:</strong></p>
                <p>Review your report and schedule a free consultation with {cpa_name or 'our tax professional'} to discuss your options and create an action plan.</p>

                <a href="#book-consultation" style="display: inline-block; background: #10b981; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; margin-top: 16px;">Book Your Free Consultation</a>

                <p style="margin-top: 24px; color: #6b7280; font-size: 14px;">Questions? Simply reply to this email.</p>

                <p>Best regards,<br>{cpa_name or 'Your Tax Advisory Team'}</p>
            </div>
            """

            body_text = f"""
Hello {lead_name},

Your personalized tax advisory report is ready!

POTENTIAL TAX SAVINGS IDENTIFIED: ${total_savings:,.0f}

Your comprehensive report is attached. It includes:
- Executive summary of your tax situation
- Detailed analysis of optimization opportunities
- Prioritized action items
- Personalized recommendations

NEXT STEPS:
Review your report and schedule a free consultation to discuss your options.

Best regards,
{cpa_name or 'Your Tax Advisory Team'}
            """

            result = await send_email_with_attachment(
                to=lead_email,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                attachment_path=pdf_path,
                attachment_name="Tax_Advisory_Report.pdf",
            )

            return {"success": result.success, "error": result.error_message if not result.success else None}

        except ImportError:
            # Fallback if attachment function not available
            logger.warning("Email attachment function not available, sending without attachment")
            return {"success": False, "error": "Email attachment not supported"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _send_lead_notification_to_cpa(
        self,
        cpa_email: str,
        cpa_name: str,
        lead_name: str,
        lead_email: str,
        total_savings: float,
        pdf_path: Optional[str],
        lead_id: str,
    ) -> Dict[str, Any]:
        """Send new lead notification to CPA."""
        try:
            # Determine lead temperature
            if total_savings > 5000:
                temperature = "🔥 HOT"
                temp_color = "#ef4444"
            elif total_savings > 2000:
                temperature = "🌡️ WARM"
                temp_color = "#f59e0b"
            else:
                temperature = "INTERESTED"
                temp_color = "#1e3a5f"

            subject = f"[{temperature}] New Lead: {lead_name} - ${total_savings:,.0f} potential savings"

            body_html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: {temp_color}; color: white; padding: 12px 20px; border-radius: 8px 8px 0 0;">
                    <h2 style="margin: 0;">New Lead Assigned</h2>
                </div>

                <div style="border: 1px solid #e5e7eb; border-top: none; padding: 20px; border-radius: 0 0 8px 8px;">
                    <p>Hello {cpa_name},</p>

                    <p>A new lead has been assigned to you!</p>

                    <div style="background: #f3f4f6; padding: 16px; border-radius: 8px; margin: 20px 0;">
                        <table style="width: 100%;">
                            <tr>
                                <td style="padding: 8px 0;"><strong>Name:</strong></td>
                                <td>{lead_name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0;"><strong>Email:</strong></td>
                                <td><a href="mailto:{lead_email}">{lead_email}</a></td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0;"><strong>Potential Savings:</strong></td>
                                <td style="font-size: 18px; color: #10b981; font-weight: bold;">${total_savings:,.0f}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0;"><strong>Temperature:</strong></td>
                                <td><span style="background: {temp_color}; color: white; padding: 4px 8px; border-radius: 4px;">{temperature}</span></td>
                            </tr>
                        </table>
                    </div>

                    <p><strong>Their advisory report is attached.</strong> Review it before reaching out.</p>

                    <p><strong>Recommended Actions:</strong></p>
                    <ol>
                        <li>Review the attached advisory report</li>
                        <li>Contact the lead within 24 hours</li>
                        <li>Schedule an initial consultation</li>
                    </ol>

                    <a href="#view-lead" style="display: inline-block; background: #1e3a5f; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">View Lead in Dashboard</a>

                    <p style="margin-top: 24px; color: #6b7280; font-size: 12px;">Lead ID: {lead_id}</p>
                </div>
            </div>
            """

            # Try to send with attachment
            try:
                from notifications.email_provider import send_email_with_attachment

                if pdf_path:
                    result = await send_email_with_attachment(
                        to=cpa_email,
                        subject=subject,
                        body_html=body_html,
                        body_text=f"New lead: {lead_name} ({lead_email}) - ${total_savings:,.0f} potential savings",
                        attachment_path=pdf_path,
                        attachment_name=f"Advisory_Report_{lead_name.replace(' ', '_')}.pdf",
                    )
                    return {"success": result.success, "error": result.error_message if not result.success else None}
            except ImportError:
                pass

            # Fallback: send without attachment
            from notifications.email_provider import send_email

            result = send_email(
                to=cpa_email,
                subject=subject,
                body_html=body_html,
                body_text=f"New lead: {lead_name} ({lead_email}) - ${total_savings:,.0f} potential savings",
            )

            return {"success": result.success, "error": result.error_message if not result.success else None}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # =========================================================================
    # STEP 4: MATCH - CPA assignment and handoff
    # =========================================================================

    def get_lead_platform_fee(
        self,
        engagement_value: float,
    ) -> PlatformFeeCalculation:
        """
        Calculate platform fee for a lead conversion.

        This is the fee collected when a lead converts to a paying client.
        """
        return calculate_lead_platform_fee(
            engagement_value=engagement_value,
            is_high_value=engagement_value > 5000,
        )

    # =========================================================================
    # FULL FUNNEL FLOW
    # =========================================================================

    async def process_qualified_lead(
        self,
        lead_id: str,
        lead_email: str,
        lead_name: str,
        session_id: str,
        cpa_pool: Optional[List[Dict[str, Any]]] = None,
        brand_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a fully qualified lead through the funnel.

        This is the main entry point after a lead has:
        1. Completed the quick estimate (ATTRACT)
        2. Provided contact info and answered questions (QUALIFY)

        It then:
        3. Generates and delivers the advisory report (CONVERT)
        4. Assigns to a CPA (MATCH)
        5. Enrolls in nurture and e-sign flows (FACILITATE)

        Args:
            lead_id: Lead identifier
            lead_email: Lead's email
            lead_name: Lead's name
            session_id: Tax session with answers
            cpa_pool: Optional list of CPAs to consider for assignment
            brand_config: Optional branding configuration

        Returns:
            Complete funnel result
        """
        # Register CPAs if provided
        if cpa_pool:
            assigner = get_auto_assigner()
            for cpa in cpa_pool:
                assigner.register_cpa(CPACapacity(
                    cpa_id=cpa["cpa_id"],
                    cpa_email=cpa["email"],
                    cpa_name=cpa["name"],
                    firm_id=cpa.get("firm_id", "default"),
                    handles_complex=cpa.get("handles_complex", True),
                    handles_business=cpa.get("handles_business", True),
                ))

        # Get assigned CPA info (or first from pool)
        cpa_email = None
        cpa_name = None
        if cpa_pool:
            cpa_email = cpa_pool[0].get("email")
            cpa_name = cpa_pool[0].get("name")

        # Run the CONVERT step
        result = await self.generate_and_deliver_report(
            lead_id=lead_id,
            session_id=session_id,
            lead_email=lead_email,
            lead_name=lead_name,
            cpa_email=cpa_email,
            cpa_name=cpa_name,
            brand_config=brand_config,
        )

        return result


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_orchestrator: Optional[FunnelOrchestrator] = None


def get_funnel_orchestrator() -> FunnelOrchestrator:
    """Get singleton funnel orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = FunnelOrchestrator()
    return _orchestrator
