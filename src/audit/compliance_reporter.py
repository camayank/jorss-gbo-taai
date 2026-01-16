"""Compliance Reporting Module.

Generate comprehensive compliance reports and audit
packages for IRS examination and professional review.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import uuid

from audit.audit_trail import AuditTrail, AuditEventType
from audit.filing_records import FilingRecordManager, FilingRecord, FilingStatus
from audit.document_retention import DocumentRetentionManager, DocumentCategory
from audit.calculation_snapshot import SnapshotManager, CalculationSnapshot


@dataclass
class ComplianceIssue:
    """Represents a compliance concern or issue."""
    issue_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    severity: str = "medium"  # low, medium, high, critical
    category: str = ""  # documentation, calculation, filing, retention
    title: str = ""
    description: str = ""
    recommendation: str = ""
    affected_items: List[str] = field(default_factory=list)
    resolved: bool = False
    resolution_notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'issue_id': self.issue_id,
            'severity': self.severity,
            'category': self.category,
            'title': self.title,
            'description': self.description,
            'recommendation': self.recommendation,
            'affected_items': self.affected_items,
            'resolved': self.resolved,
            'resolution_notes': self.resolution_notes
        }


@dataclass
class ComplianceReport:
    """Comprehensive compliance report for a tax return."""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    return_id: str = ""
    tax_year: int = 2025
    generated_at: datetime = field(default_factory=datetime.now)
    generated_by: Optional[str] = None

    # Overall status
    overall_status: str = "compliant"  # compliant, issues_found, non_compliant
    compliance_score: float = 100.0  # 0-100

    # Summary counts
    total_issues: int = 0
    critical_issues: int = 0
    high_issues: int = 0
    medium_issues: int = 0
    low_issues: int = 0

    # Detailed issues
    issues: List[ComplianceIssue] = field(default_factory=list)

    # Section summaries
    documentation_summary: Dict[str, Any] = field(default_factory=dict)
    calculation_summary: Dict[str, Any] = field(default_factory=dict)
    filing_summary: Dict[str, Any] = field(default_factory=dict)
    retention_summary: Dict[str, Any] = field(default_factory=dict)
    audit_trail_summary: Dict[str, Any] = field(default_factory=dict)

    # Recommendations
    recommendations: List[str] = field(default_factory=list)

    def add_issue(self, issue: ComplianceIssue):
        """Add an issue and update counts."""
        self.issues.append(issue)
        self.total_issues += 1

        if issue.severity == 'critical':
            self.critical_issues += 1
        elif issue.severity == 'high':
            self.high_issues += 1
        elif issue.severity == 'medium':
            self.medium_issues += 1
        else:
            self.low_issues += 1

        # Update overall status
        if self.critical_issues > 0:
            self.overall_status = 'non_compliant'
        elif self.high_issues > 0 or self.medium_issues > 2:
            self.overall_status = 'issues_found'

        # Update compliance score
        self._calculate_score()

    def _calculate_score(self):
        """Calculate compliance score based on issues."""
        # Start at 100, deduct based on issues
        self.compliance_score = 100.0
        self.compliance_score -= self.critical_issues * 25
        self.compliance_score -= self.high_issues * 10
        self.compliance_score -= self.medium_issues * 5
        self.compliance_score -= self.low_issues * 1
        self.compliance_score = max(0, self.compliance_score)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'report_id': self.report_id,
            'return_id': self.return_id,
            'tax_year': self.tax_year,
            'generated_at': self.generated_at.isoformat(),
            'generated_by': self.generated_by,
            'overall_status': self.overall_status,
            'compliance_score': self.compliance_score,
            'issue_counts': {
                'total': self.total_issues,
                'critical': self.critical_issues,
                'high': self.high_issues,
                'medium': self.medium_issues,
                'low': self.low_issues
            },
            'issues': [i.to_dict() for i in self.issues],
            'documentation_summary': self.documentation_summary,
            'calculation_summary': self.calculation_summary,
            'filing_summary': self.filing_summary,
            'retention_summary': self.retention_summary,
            'audit_trail_summary': self.audit_trail_summary,
            'recommendations': self.recommendations
        }


@dataclass
class AuditPackage:
    """Complete audit package for IRS examination."""
    package_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    return_id: str = ""
    tax_year: int = 2025
    created_at: datetime = field(default_factory=datetime.now)
    created_by: Optional[str] = None

    # Taxpayer information
    taxpayer_name: str = ""
    taxpayer_ssn_last4: str = ""
    filing_status: str = ""

    # Package contents
    compliance_report: Optional[ComplianceReport] = None
    filing_records: List[Dict[str, Any]] = field(default_factory=list)
    calculation_snapshots: List[Dict[str, Any]] = field(default_factory=list)
    document_inventory: List[Dict[str, Any]] = field(default_factory=list)
    audit_trail_entries: List[Dict[str, Any]] = field(default_factory=list)

    # Summary
    package_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'package_id': self.package_id,
            'return_id': self.return_id,
            'tax_year': self.tax_year,
            'created_at': self.created_at.isoformat(),
            'created_by': self.created_by,
            'taxpayer_info': {
                'name': self.taxpayer_name,
                'ssn_last4': self.taxpayer_ssn_last4,
                'filing_status': self.filing_status
            },
            'compliance_report': self.compliance_report.to_dict() if self.compliance_report else None,
            'filing_records': self.filing_records,
            'calculation_snapshots': self.calculation_snapshots,
            'document_inventory': self.document_inventory,
            'audit_trail_entries': self.audit_trail_entries,
            'package_summary': self.package_summary
        }


class ComplianceReporter:
    """
    Generates compliance reports and audit packages.

    Analyzes tax returns for compliance issues and
    generates comprehensive documentation for audits.
    """

    def __init__(
        self,
        audit_trail: Optional[AuditTrail] = None,
        filing_manager: Optional[FilingRecordManager] = None,
        document_manager: Optional[DocumentRetentionManager] = None,
        snapshot_manager: Optional[SnapshotManager] = None
    ):
        self.audit_trail = audit_trail
        self.filing_manager = filing_manager
        self.document_manager = document_manager
        self.snapshot_manager = snapshot_manager

    def generate_compliance_report(
        self,
        return_id: str,
        tax_year: int,
        generated_by: Optional[str] = None
    ) -> ComplianceReport:
        """Generate a comprehensive compliance report."""
        report = ComplianceReport(
            return_id=return_id,
            tax_year=tax_year,
            generated_by=generated_by
        )

        # Check documentation compliance
        self._check_documentation_compliance(report)

        # Check calculation integrity
        self._check_calculation_compliance(report)

        # Check filing compliance
        self._check_filing_compliance(report)

        # Check retention compliance
        self._check_retention_compliance(report)

        # Check audit trail integrity
        self._check_audit_trail_compliance(report)

        # Generate recommendations
        self._generate_recommendations(report)

        return report

    def _check_documentation_compliance(self, report: ComplianceReport):
        """Check documentation for compliance issues."""
        report.documentation_summary = {
            'total_documents': 0,
            'verified_documents': 0,
            'missing_documents': [],
            'unverified_documents': []
        }

        if not self.document_manager:
            return

        docs = self.document_manager.get_documents_for_return(report.return_id)
        report.documentation_summary['total_documents'] = len(docs)
        report.documentation_summary['verified_documents'] = sum(
            1 for d in docs if d.verified
        )

        # Check for unverified documents
        unverified = [d for d in docs if not d.verified]
        if unverified:
            report.documentation_summary['unverified_documents'] = [
                d.document_name for d in unverified
            ]

            # Add issue if critical documents unverified
            critical_categories = [
                DocumentCategory.W2,
                DocumentCategory.TAX_RETURN,
                DocumentCategory.FORM_1099_NEC
            ]
            critical_unverified = [
                d for d in unverified if d.category in critical_categories
            ]

            if critical_unverified:
                report.add_issue(ComplianceIssue(
                    severity='high',
                    category='documentation',
                    title='Critical Documents Not Verified',
                    description=f'{len(critical_unverified)} critical documents have not been verified',
                    recommendation='Review and verify all critical tax documents',
                    affected_items=[d.document_name for d in critical_unverified]
                ))

        # Check for W-2 without corresponding document
        w2_docs = self.document_manager.get_documents_by_category(DocumentCategory.W2)
        w2_for_return = [d for d in w2_docs if d.return_id == report.return_id]

        if not w2_for_return and report.tax_year == 2025:  # Assuming there should be W-2
            report.add_issue(ComplianceIssue(
                severity='medium',
                category='documentation',
                title='No W-2 Documents Found',
                description='No W-2 wage statements are attached to this return',
                recommendation='Upload W-2 documents or confirm no W-2 income'
            ))

    def _check_calculation_compliance(self, report: ComplianceReport):
        """Check calculation integrity."""
        report.calculation_summary = {
            'snapshots_available': 0,
            'integrity_verified': True,
            'pre_filing_snapshot': False,
            'calculation_changes': []
        }

        if not self.snapshot_manager:
            return

        snapshots = self.snapshot_manager.get_snapshots_for_return(report.return_id)
        report.calculation_summary['snapshots_available'] = len(snapshots)

        if not snapshots:
            report.add_issue(ComplianceIssue(
                severity='medium',
                category='calculation',
                title='No Calculation Snapshots',
                description='No calculation snapshots found for verification',
                recommendation='Run calculations and capture snapshots before filing'
            ))
            return

        # Check for pre-filing snapshot
        pre_filing = self.snapshot_manager.get_pre_filing_snapshot(report.return_id)
        report.calculation_summary['pre_filing_snapshot'] = pre_filing is not None

        if not pre_filing:
            report.add_issue(ComplianceIssue(
                severity='low',
                category='calculation',
                title='No Pre-Filing Snapshot',
                description='No pre-filing calculation snapshot was captured',
                recommendation='Capture a pre-filing snapshot before submitting'
            ))

        # Verify integrity of all snapshots
        for snapshot in snapshots:
            if not snapshot.verify_integrity():
                report.calculation_summary['integrity_verified'] = False
                report.add_issue(ComplianceIssue(
                    severity='critical',
                    category='calculation',
                    title='Calculation Integrity Failed',
                    description=f'Snapshot {snapshot.snapshot_id} failed integrity check',
                    recommendation='Investigate potential data tampering',
                    affected_items=[snapshot.snapshot_id]
                ))

        # Check for significant changes between snapshots
        if len(snapshots) >= 2:
            latest = snapshots[-1]
            first = snapshots[0]
            comparison = self.snapshot_manager.compare_snapshots(
                first.snapshot_id,
                latest.snapshot_id
            )

            if comparison and comparison.has_critical_differences:
                report.add_issue(ComplianceIssue(
                    severity='medium',
                    category='calculation',
                    title='Significant Calculation Changes',
                    description='Significant changes detected between first and final calculations',
                    recommendation='Review calculation history for accuracy',
                    affected_items=[
                        d.field_path for d in comparison.differences
                        if d.significance in ['critical', 'high']
                    ]
                ))

    def _check_filing_compliance(self, report: ComplianceReport):
        """Check filing records for compliance."""
        report.filing_summary = {
            'filings_found': 0,
            'accepted_filings': 0,
            'rejected_filings': 0,
            'pending_filings': 0
        }

        if not self.filing_manager:
            return

        filings = self.filing_manager.get_records_for_return(report.return_id)
        report.filing_summary['filings_found'] = len(filings)
        report.filing_summary['accepted_filings'] = sum(
            1 for f in filings if f.status == FilingStatus.ACCEPTED
        )
        report.filing_summary['rejected_filings'] = sum(
            1 for f in filings if f.status == FilingStatus.REJECTED
        )
        report.filing_summary['pending_filings'] = sum(
            1 for f in filings if f.status == FilingStatus.PENDING
        )

        # Check for unresolved rejections
        rejected = [f for f in filings if f.status == FilingStatus.REJECTED]
        if rejected:
            report.add_issue(ComplianceIssue(
                severity='high',
                category='filing',
                title='Rejected Filings Present',
                description=f'{len(rejected)} filing(s) were rejected by IRS/state',
                recommendation='Review rejection codes and resubmit corrected returns',
                affected_items=[f.filing_id for f in rejected]
            ))

        # Check for missing confirmation
        submitted = [
            f for f in filings
            if f.status == FilingStatus.SUBMITTED and not f.confirmation_number
        ]
        if submitted:
            report.add_issue(ComplianceIssue(
                severity='medium',
                category='filing',
                title='Missing Filing Confirmation',
                description='Filed returns without confirmation numbers',
                recommendation='Verify filing status with IRS and obtain confirmation',
                affected_items=[f.filing_id for f in submitted]
            ))

    def _check_retention_compliance(self, report: ComplianceReport):
        """Check document retention compliance."""
        report.retention_summary = {
            'retention_compliant': True,
            'expired_documents': 0,
            'expiring_soon': 0
        }

        if not self.document_manager:
            return

        expired = self.document_manager.get_expired_documents()
        expiring = self.document_manager.get_documents_expiring_soon(90)

        # Filter for this return
        return_docs = self.document_manager.get_documents_for_return(report.return_id)
        return_doc_ids = {d.document_id for d in return_docs}

        expired_for_return = [d for d in expired if d.document_id in return_doc_ids]
        expiring_for_return = [d for d in expiring if d.document_id in return_doc_ids]

        report.retention_summary['expired_documents'] = len(expired_for_return)
        report.retention_summary['expiring_soon'] = len(expiring_for_return)

        if expired_for_return:
            report.retention_summary['retention_compliant'] = False
            report.add_issue(ComplianceIssue(
                severity='low',
                category='retention',
                title='Documents Past Retention Period',
                description=f'{len(expired_for_return)} documents have exceeded retention requirements',
                recommendation='Review and archive or dispose of expired documents per policy',
                affected_items=[d.document_name for d in expired_for_return]
            ))

    def _check_audit_trail_compliance(self, report: ComplianceReport):
        """Check audit trail integrity."""
        report.audit_trail_summary = {
            'entries_count': 0,
            'integrity_verified': True,
            'has_required_events': True,
            'missing_events': []
        }

        if not self.audit_trail:
            report.add_issue(ComplianceIssue(
                severity='high',
                category='audit_trail',
                title='No Audit Trail Available',
                description='Audit trail not found for this return',
                recommendation='Ensure audit trail is maintained for all returns'
            ))
            return

        report.audit_trail_summary['entries_count'] = len(self.audit_trail.entries)

        # Verify integrity
        is_valid, issues = self.audit_trail.verify_trail_integrity()
        report.audit_trail_summary['integrity_verified'] = is_valid

        if not is_valid:
            report.add_issue(ComplianceIssue(
                severity='critical',
                category='audit_trail',
                title='Audit Trail Integrity Failed',
                description='Audit trail failed integrity verification',
                recommendation='Investigate potential tampering or system issues',
                affected_items=issues
            ))

        # Check for required events
        required_events = [
            AuditEventType.RETURN_CREATED,
            AuditEventType.CALCULATION_RUN,
        ]

        existing_types = {e.event_type for e in self.audit_trail.entries}
        missing = [e.value for e in required_events if e not in existing_types]

        if missing:
            report.audit_trail_summary['has_required_events'] = False
            report.audit_trail_summary['missing_events'] = missing
            report.add_issue(ComplianceIssue(
                severity='medium',
                category='audit_trail',
                title='Missing Required Audit Events',
                description=f'Required audit events not found: {", ".join(missing)}',
                recommendation='Ensure all required events are logged',
                affected_items=missing
            ))

    def _generate_recommendations(self, report: ComplianceReport):
        """Generate recommendations based on issues found."""
        report.recommendations = []

        if report.critical_issues > 0:
            report.recommendations.append(
                "URGENT: Address critical compliance issues before filing or audit"
            )

        if not report.documentation_summary.get('pre_filing_snapshot'):
            report.recommendations.append(
                "Capture a pre-filing calculation snapshot for verification"
            )

        verification_rate = 0
        if report.documentation_summary.get('total_documents', 0) > 0:
            verification_rate = (
                report.documentation_summary.get('verified_documents', 0) /
                report.documentation_summary['total_documents']
            )

        if verification_rate < 1.0:
            report.recommendations.append(
                f"Verify remaining documents ({int((1-verification_rate)*100)}% unverified)"
            )

        if report.filing_summary.get('rejected_filings', 0) > 0:
            report.recommendations.append(
                "Review and resolve filing rejections promptly"
            )

        if report.compliance_score < 80:
            report.recommendations.append(
                "Consider professional review before IRS examination"
            )

        # General best practices
        if len(report.recommendations) == 0:
            report.recommendations.append(
                "Return is compliant. Maintain documentation for retention period."
            )

    def generate_audit_package(
        self,
        return_id: str,
        tax_year: int,
        taxpayer_name: str,
        ssn: str,
        filing_status: str,
        created_by: Optional[str] = None
    ) -> AuditPackage:
        """Generate a complete audit package."""
        package = AuditPackage(
            return_id=return_id,
            tax_year=tax_year,
            taxpayer_name=taxpayer_name,
            taxpayer_ssn_last4=ssn[-4:] if len(ssn) >= 4 else ssn,
            filing_status=filing_status,
            created_by=created_by
        )

        # Generate compliance report
        package.compliance_report = self.generate_compliance_report(
            return_id, tax_year, created_by
        )

        # Include filing records
        if self.filing_manager:
            filings = self.filing_manager.get_records_for_return(return_id)
            package.filing_records = [f.to_dict() for f in filings]

        # Include calculation snapshots
        if self.snapshot_manager:
            snapshots = self.snapshot_manager.get_snapshots_for_return(return_id)
            package.calculation_snapshots = [s.to_dict() for s in snapshots]

        # Include document inventory
        if self.document_manager:
            docs = self.document_manager.get_documents_for_return(return_id)
            package.document_inventory = [d.to_dict() for d in docs]

        # Include audit trail
        if self.audit_trail:
            package.audit_trail_entries = [
                e.to_dict() for e in self.audit_trail.entries
            ]

        # Generate summary
        package.package_summary = self._generate_package_summary(package)

        return package

    def _generate_package_summary(self, package: AuditPackage) -> Dict[str, Any]:
        """Generate summary for audit package."""
        return {
            'return_id': package.return_id,
            'tax_year': package.tax_year,
            'taxpayer': f"{package.taxpayer_name} (***-**-{package.taxpayer_ssn_last4})",
            'filing_status': package.filing_status,
            'generated': package.created_at.isoformat(),
            'contents': {
                'compliance_report': package.compliance_report is not None,
                'filing_records': len(package.filing_records),
                'calculation_snapshots': len(package.calculation_snapshots),
                'documents': len(package.document_inventory),
                'audit_entries': len(package.audit_trail_entries)
            },
            'compliance': {
                'status': package.compliance_report.overall_status if package.compliance_report else 'unknown',
                'score': package.compliance_report.compliance_score if package.compliance_report else 0,
                'issues': package.compliance_report.total_issues if package.compliance_report else 0
            }
        }

    def export_audit_package(self, package: AuditPackage) -> str:
        """Export audit package to JSON."""
        return json.dumps(package.to_dict(), indent=2)

    def generate_audit_report_text(self, package: AuditPackage) -> str:
        """Generate human-readable audit report."""
        lines = [
            "=" * 70,
            "COMPREHENSIVE AUDIT PACKAGE",
            "=" * 70,
            "",
            "TAXPAYER INFORMATION",
            "-" * 40,
            f"Name: {package.taxpayer_name}",
            f"SSN: ***-**-{package.taxpayer_ssn_last4}",
            f"Filing Status: {package.filing_status}",
            f"Tax Year: {package.tax_year}",
            "",
            "PACKAGE CONTENTS",
            "-" * 40,
            f"Filing Records: {len(package.filing_records)}",
            f"Calculation Snapshots: {len(package.calculation_snapshots)}",
            f"Supporting Documents: {len(package.document_inventory)}",
            f"Audit Trail Entries: {len(package.audit_trail_entries)}",
            ""
        ]

        if package.compliance_report:
            report = package.compliance_report
            lines.extend([
                "COMPLIANCE STATUS",
                "-" * 40,
                f"Overall Status: {report.overall_status.upper()}",
                f"Compliance Score: {report.compliance_score:.1f}/100",
                "",
                f"Issues Found: {report.total_issues}",
                f"  Critical: {report.critical_issues}",
                f"  High: {report.high_issues}",
                f"  Medium: {report.medium_issues}",
                f"  Low: {report.low_issues}",
                ""
            ])

            if report.issues:
                lines.extend([
                    "COMPLIANCE ISSUES",
                    "-" * 40
                ])
                for issue in report.issues:
                    lines.extend([
                        f"\n[{issue.severity.upper()}] {issue.title}",
                        f"  Category: {issue.category}",
                        f"  Description: {issue.description}",
                        f"  Recommendation: {issue.recommendation}"
                    ])

            if report.recommendations:
                lines.extend([
                    "",
                    "RECOMMENDATIONS",
                    "-" * 40
                ])
                for i, rec in enumerate(report.recommendations, 1):
                    lines.append(f"{i}. {rec}")

        # Filing history
        if package.filing_records:
            lines.extend([
                "",
                "FILING HISTORY",
                "-" * 40
            ])
            for filing in package.filing_records:
                lines.append(
                    f"  {filing.get('filing_type', 'N/A')}: "
                    f"{filing.get('status', 'N/A')} "
                    f"({filing.get('confirmation_number', 'No confirmation')})"
                )

        # Document inventory
        if package.document_inventory:
            lines.extend([
                "",
                "DOCUMENT INVENTORY",
                "-" * 40
            ])
            for doc in package.document_inventory:
                verified = "Verified" if doc.get('verified') else "Unverified"
                lines.append(
                    f"  [{doc.get('category', 'N/A')}] "
                    f"{doc.get('document_name', 'N/A')} - {verified}"
                )

        lines.extend([
            "",
            "=" * 70,
            f"Generated: {package.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Package ID: {package.package_id}",
            "=" * 70
        ])

        return "\n".join(lines)
