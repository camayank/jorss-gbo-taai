"""
Database models for Advisory Reports.

Tables:
- advisory_reports: Main report metadata and status
- report_sections: Individual report sections (for caching)
"""

from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, Text, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import Optional, List, Dict, Any

Base = declarative_base()


class AdvisoryReport(Base):
    """Advisory report storage with metadata and status."""
    __tablename__ = "advisory_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Identifiers
    report_id = Column(String(100), unique=True, nullable=False, index=True)
    session_id = Column(String(100), nullable=False, index=True)

    # Report metadata
    report_type = Column(String(50), nullable=False)  # "full_analysis", "standard_report", etc.
    tax_year = Column(Integer, nullable=False)

    # Taxpayer info
    taxpayer_name = Column(String(200), nullable=False)
    filing_status = Column(String(50), nullable=False)

    # Financial summary
    current_tax_liability = Column(Float, nullable=False, default=0.0)
    potential_savings = Column(Float, nullable=False, default=0.0)
    confidence_score = Column(Float, nullable=False, default=0.0)
    recommendations_count = Column(Integer, nullable=False, default=0)

    # Report data (full JSON structure)
    report_data = Column(JSON, nullable=False)

    # PDF info
    pdf_path = Column(String(500), nullable=True)
    pdf_generated = Column(Boolean, default=False)
    pdf_watermark = Column(String(50), nullable=True)

    # Status tracking
    status = Column(String(20), default="generating")  # "generating", "complete", "error"
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    generated_at = Column(DateTime, nullable=True)

    # Version for updates
    version = Column(Integer, default=1, nullable=False)

    # Relationships
    sections = relationship("ReportSection", back_populates="report", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "report_id": self.report_id,
            "session_id": self.session_id,
            "report_type": self.report_type,
            "tax_year": self.tax_year,
            "taxpayer_name": self.taxpayer_name,
            "filing_status": self.filing_status,
            "current_tax_liability": self.current_tax_liability,
            "potential_savings": self.potential_savings,
            "confidence_score": self.confidence_score,
            "recommendations_count": self.recommendations_count,
            "pdf_path": self.pdf_path,
            "pdf_generated": self.pdf_generated,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
        }


class ReportSection(Base):
    """Individual report sections for granular caching."""
    __tablename__ = "report_sections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, ForeignKey("advisory_reports.id", ondelete="CASCADE"), nullable=False)

    # Section info
    section_id = Column(String(100), nullable=False)  # "executive_summary", "recommendations", etc.
    section_title = Column(String(200), nullable=False)
    page_number = Column(Integer, nullable=True)

    # Section content (JSON)
    content_data = Column(JSON, nullable=False)

    # Timestamps
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship
    report = relationship("AdvisoryReport", back_populates="sections")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "section_id": self.section_id,
            "section_title": self.section_title,
            "page_number": self.page_number,
            "content_data": self.content_data,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
        }


# Helper functions for working with advisory reports

def create_advisory_report_from_result(
    result: "AdvisoryReportResult",
    session_id: str,
    session,
) -> AdvisoryReport:
    """
    Create database model from AdvisoryReportResult.

    Args:
        result: AdvisoryReportResult from report generator
        session_id: Session ID to associate with report
        session: SQLAlchemy session

    Returns:
        AdvisoryReport database model
    """
    # Create main report record
    db_report = AdvisoryReport(
        report_id=result.report_id,
        session_id=session_id,
        report_type=result.report_type.value,
        tax_year=result.tax_year,
        taxpayer_name=result.taxpayer_name,
        filing_status=result.filing_status,
        current_tax_liability=float(result.current_tax_liability),
        potential_savings=float(result.potential_savings),
        confidence_score=float(result.confidence_score),
        recommendations_count=result.top_recommendations_count,
        report_data=result.to_dict(),
        status=result.status,
        error_message=result.error_message,
        generated_at=datetime.fromisoformat(result.generated_at),
    )

    session.add(db_report)
    session.flush()  # Get the ID

    # Create section records
    for section in result.sections:
        db_section = ReportSection(
            report_id=db_report.id,
            section_id=section.section_id,
            section_title=section.title,
            page_number=section.page_number,
            content_data=section.content,
        )
        session.add(db_section)

    session.commit()

    return db_report


def get_advisory_report_by_id(report_id: str, session) -> Optional[AdvisoryReport]:
    """
    Get advisory report by report_id.

    Args:
        report_id: Report ID to look up
        session: SQLAlchemy session

    Returns:
        AdvisoryReport or None
    """
    return session.query(AdvisoryReport).filter_by(report_id=report_id).first()


def get_advisory_reports_by_session(session_id: str, session) -> List[AdvisoryReport]:
    """
    Get all advisory reports for a session.

    Args:
        session_id: Session ID
        session: SQLAlchemy session

    Returns:
        List of AdvisoryReport
    """
    return session.query(AdvisoryReport).filter_by(session_id=session_id).order_by(
        AdvisoryReport.created_at.desc()
    ).all()


def update_report_pdf_path(report_id: str, pdf_path: str, session):
    """
    Update report with PDF path.

    Args:
        report_id: Report ID
        pdf_path: Path to generated PDF
        session: SQLAlchemy session
    """
    report = get_advisory_report_by_id(report_id, session)
    if report:
        report.pdf_path = pdf_path
        report.pdf_generated = True
        report.updated_at = datetime.utcnow()
        session.commit()


def delete_advisory_report(report_id: str, session) -> bool:
    """
    Delete advisory report and all sections.

    Args:
        report_id: Report ID
        session: SQLAlchemy session

    Returns:
        True if deleted, False if not found
    """
    report = get_advisory_report_by_id(report_id, session)
    if report:
        session.delete(report)
        session.commit()
        return True
    return False
