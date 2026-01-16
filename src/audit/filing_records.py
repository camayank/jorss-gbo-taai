"""Filing Records Management.

Track filing submissions, acceptances, rejections,
and amendments for complete filing history.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime
import json
import uuid


class FilingStatus(Enum):
    """Status of a tax filing."""
    DRAFT = "draft"
    READY_TO_FILE = "ready_to_file"
    PENDING_SIGNATURE = "pending_signature"
    SIGNED = "signed"
    SUBMITTED = "submitted"
    PENDING = "pending"  # Waiting for IRS/state response
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    AMENDED = "amended"
    VOIDED = "voided"


class FilingType(Enum):
    """Type of filing."""
    FEDERAL_EFILE = "federal_efile"
    FEDERAL_PAPER = "federal_paper"
    STATE_EFILE = "state_efile"
    STATE_PAPER = "state_paper"
    EXTENSION = "extension"
    ESTIMATED_PAYMENT = "estimated_payment"
    AMENDED = "amended"


@dataclass
class FilingTimestamp:
    """Important timestamps in filing lifecycle."""
    created: datetime = field(default_factory=datetime.now)
    prepared: Optional[datetime] = None
    signed_taxpayer: Optional[datetime] = None
    signed_spouse: Optional[datetime] = None
    signed_preparer: Optional[datetime] = None
    submitted: Optional[datetime] = None
    acknowledged: Optional[datetime] = None
    accepted: Optional[datetime] = None
    rejected: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Optional[str]]:
        return {
            'created': self.created.isoformat(),
            'prepared': self.prepared.isoformat() if self.prepared else None,
            'signed_taxpayer': self.signed_taxpayer.isoformat() if self.signed_taxpayer else None,
            'signed_spouse': self.signed_spouse.isoformat() if self.signed_spouse else None,
            'signed_preparer': self.signed_preparer.isoformat() if self.signed_preparer else None,
            'submitted': self.submitted.isoformat() if self.submitted else None,
            'acknowledged': self.acknowledged.isoformat() if self.acknowledged else None,
            'accepted': self.accepted.isoformat() if self.accepted else None,
            'rejected': self.rejected.isoformat() if self.rejected else None
        }


@dataclass
class RejectionInfo:
    """Information about a filing rejection."""
    rejection_code: str
    rejection_message: str
    rejection_category: str  # schema, business_rule, system
    rejection_timestamp: datetime = field(default_factory=datetime.now)
    can_resubmit: bool = True
    suggested_fix: Optional[str] = None
    affected_fields: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'rejection_code': self.rejection_code,
            'rejection_message': self.rejection_message,
            'rejection_category': self.rejection_category,
            'rejection_timestamp': self.rejection_timestamp.isoformat(),
            'can_resubmit': self.can_resubmit,
            'suggested_fix': self.suggested_fix,
            'affected_fields': self.affected_fields
        }


@dataclass
class PaymentInfo:
    """Information about tax payment or refund."""
    payment_type: str  # 'payment_due', 'refund', 'no_payment'
    amount: float
    payment_method: Optional[str] = None  # 'direct_debit', 'check', 'direct_deposit'
    bank_routing: Optional[str] = None  # Last 4 digits only for security
    bank_account: Optional[str] = None  # Last 4 digits only
    payment_date: Optional[datetime] = None
    confirmation_number: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'payment_type': self.payment_type,
            'amount': self.amount,
            'payment_method': self.payment_method,
            'bank_routing_last4': self.bank_routing,
            'bank_account_last4': self.bank_account,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'confirmation_number': self.confirmation_number
        }


@dataclass
class FilingRecord:
    """Complete record of a tax filing."""
    filing_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    return_id: str = ""
    tax_year: int = 2025
    filing_type: FilingType = FilingType.FEDERAL_EFILE
    status: FilingStatus = FilingStatus.DRAFT

    # Taxpayer information (redacted for security)
    taxpayer_name: str = ""
    taxpayer_ssn_last4: str = ""  # Only last 4 digits
    filing_status: str = ""
    state_code: Optional[str] = None

    # Financial summary
    gross_income: float = 0.0
    adjusted_gross_income: float = 0.0
    taxable_income: float = 0.0
    total_tax: float = 0.0
    total_payments: float = 0.0
    refund_or_owed: float = 0.0

    # Filing details
    timestamps: FilingTimestamp = field(default_factory=FilingTimestamp)
    submission_id: Optional[str] = None  # IRS/state submission ID
    confirmation_number: Optional[str] = None
    rejection_info: Optional[RejectionInfo] = None
    payment_info: Optional[PaymentInfo] = None

    # Preparer information
    preparer_name: Optional[str] = None
    preparer_ptin: Optional[str] = None
    firm_name: Optional[str] = None
    firm_ein: Optional[str] = None

    # Amendment tracking
    is_amended: bool = False
    original_filing_id: Optional[str] = None
    amendment_reason: Optional[str] = None

    # Document hashes for verification
    return_xml_hash: Optional[str] = None
    return_pdf_hash: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def mark_submitted(self, submission_id: str):
        """Mark the filing as submitted."""
        self.status = FilingStatus.SUBMITTED
        self.submission_id = submission_id
        self.timestamps.submitted = datetime.now()

    def mark_accepted(self, confirmation_number: str):
        """Mark the filing as accepted."""
        self.status = FilingStatus.ACCEPTED
        self.confirmation_number = confirmation_number
        self.timestamps.accepted = datetime.now()

    def mark_rejected(
        self,
        rejection_code: str,
        rejection_message: str,
        rejection_category: str = "business_rule",
        suggested_fix: Optional[str] = None
    ):
        """Mark the filing as rejected."""
        self.status = FilingStatus.REJECTED
        self.timestamps.rejected = datetime.now()
        self.rejection_info = RejectionInfo(
            rejection_code=rejection_code,
            rejection_message=rejection_message,
            rejection_category=rejection_category,
            suggested_fix=suggested_fix
        )

    def get_status_history(self) -> List[Dict[str, Any]]:
        """Get the status history based on timestamps."""
        history = []

        if self.timestamps.created:
            history.append({
                'status': 'created',
                'timestamp': self.timestamps.created
            })
        if self.timestamps.prepared:
            history.append({
                'status': 'prepared',
                'timestamp': self.timestamps.prepared
            })
        if self.timestamps.signed_taxpayer:
            history.append({
                'status': 'signed_by_taxpayer',
                'timestamp': self.timestamps.signed_taxpayer
            })
        if self.timestamps.submitted:
            history.append({
                'status': 'submitted',
                'timestamp': self.timestamps.submitted
            })
        if self.timestamps.accepted:
            history.append({
                'status': 'accepted',
                'timestamp': self.timestamps.accepted
            })
        if self.timestamps.rejected:
            history.append({
                'status': 'rejected',
                'timestamp': self.timestamps.rejected
            })

        return sorted(history, key=lambda x: x['timestamp'])

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'filing_id': self.filing_id,
            'return_id': self.return_id,
            'tax_year': self.tax_year,
            'filing_type': self.filing_type.value,
            'status': self.status.value,
            'taxpayer_name': self.taxpayer_name,
            'taxpayer_ssn_last4': self.taxpayer_ssn_last4,
            'filing_status': self.filing_status,
            'state_code': self.state_code,
            'gross_income': self.gross_income,
            'adjusted_gross_income': self.adjusted_gross_income,
            'taxable_income': self.taxable_income,
            'total_tax': self.total_tax,
            'total_payments': self.total_payments,
            'refund_or_owed': self.refund_or_owed,
            'timestamps': self.timestamps.to_dict(),
            'submission_id': self.submission_id,
            'confirmation_number': self.confirmation_number,
            'rejection_info': self.rejection_info.to_dict() if self.rejection_info else None,
            'payment_info': self.payment_info.to_dict() if self.payment_info else None,
            'preparer_name': self.preparer_name,
            'preparer_ptin': self.preparer_ptin,
            'firm_name': self.firm_name,
            'firm_ein': self.firm_ein,
            'is_amended': self.is_amended,
            'original_filing_id': self.original_filing_id,
            'amendment_reason': self.amendment_reason,
            'return_xml_hash': self.return_xml_hash,
            'return_pdf_hash': self.return_pdf_hash,
            'metadata': self.metadata
        }

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class AmendmentRecord:
    """Record of an amended return."""
    amendment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    original_filing_id: str = ""
    amended_filing_id: str = ""
    tax_year: int = 2025
    amendment_date: datetime = field(default_factory=datetime.now)
    amendment_reason: str = ""

    # What changed
    original_values: Dict[str, Any] = field(default_factory=dict)
    amended_values: Dict[str, Any] = field(default_factory=dict)

    # Financial impact
    original_tax: float = 0.0
    amended_tax: float = 0.0
    tax_difference: float = 0.0  # Positive = owe more, negative = additional refund

    # Status
    status: FilingStatus = FilingStatus.DRAFT
    submission_id: Optional[str] = None
    confirmation_number: Optional[str] = None

    def calculate_difference(self):
        """Calculate tax difference."""
        self.tax_difference = self.amended_tax - self.original_tax

    def to_dict(self) -> Dict[str, Any]:
        return {
            'amendment_id': self.amendment_id,
            'original_filing_id': self.original_filing_id,
            'amended_filing_id': self.amended_filing_id,
            'tax_year': self.tax_year,
            'amendment_date': self.amendment_date.isoformat(),
            'amendment_reason': self.amendment_reason,
            'original_values': self.original_values,
            'amended_values': self.amended_values,
            'original_tax': self.original_tax,
            'amended_tax': self.amended_tax,
            'tax_difference': self.tax_difference,
            'status': self.status.value,
            'submission_id': self.submission_id,
            'confirmation_number': self.confirmation_number
        }


class FilingRecordManager:
    """Manages filing records for a taxpayer or firm."""

    def __init__(self):
        self.records: Dict[str, FilingRecord] = {}
        self.amendments: Dict[str, AmendmentRecord] = {}
        self._records_by_return: Dict[str, List[str]] = {}
        self._records_by_year: Dict[int, List[str]] = {}

    def create_filing_record(
        self,
        return_id: str,
        tax_year: int,
        filing_type: FilingType,
        taxpayer_name: str,
        ssn: str,
        filing_status: str,
        **kwargs
    ) -> FilingRecord:
        """Create a new filing record."""
        record = FilingRecord(
            return_id=return_id,
            tax_year=tax_year,
            filing_type=filing_type,
            taxpayer_name=taxpayer_name,
            taxpayer_ssn_last4=ssn[-4:] if len(ssn) >= 4 else ssn,
            filing_status=filing_status,
            **kwargs
        )

        self.records[record.filing_id] = record

        # Index by return
        if return_id not in self._records_by_return:
            self._records_by_return[return_id] = []
        self._records_by_return[return_id].append(record.filing_id)

        # Index by year
        if tax_year not in self._records_by_year:
            self._records_by_year[tax_year] = []
        self._records_by_year[tax_year].append(record.filing_id)

        return record

    def get_record(self, filing_id: str) -> Optional[FilingRecord]:
        """Get a filing record by ID."""
        return self.records.get(filing_id)

    def get_records_for_return(self, return_id: str) -> List[FilingRecord]:
        """Get all filing records for a specific return."""
        filing_ids = self._records_by_return.get(return_id, [])
        return [self.records[fid] for fid in filing_ids if fid in self.records]

    def get_records_for_year(self, tax_year: int) -> List[FilingRecord]:
        """Get all filing records for a tax year."""
        filing_ids = self._records_by_year.get(tax_year, [])
        return [self.records[fid] for fid in filing_ids if fid in self.records]

    def get_records_by_status(self, status: FilingStatus) -> List[FilingRecord]:
        """Get all records with a specific status."""
        return [r for r in self.records.values() if r.status == status]

    def update_status(
        self,
        filing_id: str,
        new_status: FilingStatus,
        **kwargs
    ) -> Optional[FilingRecord]:
        """Update the status of a filing record."""
        record = self.records.get(filing_id)
        if not record:
            return None

        record.status = new_status

        if new_status == FilingStatus.SUBMITTED and 'submission_id' in kwargs:
            record.mark_submitted(kwargs['submission_id'])
        elif new_status == FilingStatus.ACCEPTED and 'confirmation_number' in kwargs:
            record.mark_accepted(kwargs['confirmation_number'])
        elif new_status == FilingStatus.REJECTED:
            record.mark_rejected(
                kwargs.get('rejection_code', 'UNKNOWN'),
                kwargs.get('rejection_message', 'Unknown rejection'),
                kwargs.get('rejection_category', 'business_rule'),
                kwargs.get('suggested_fix')
            )

        return record

    def create_amendment(
        self,
        original_filing_id: str,
        amendment_reason: str,
        original_values: Dict[str, Any],
        amended_values: Dict[str, Any]
    ) -> Optional[AmendmentRecord]:
        """Create an amendment record."""
        original = self.records.get(original_filing_id)
        if not original:
            return None

        # Create new filing record for the amendment
        amended_record = self.create_filing_record(
            return_id=original.return_id,
            tax_year=original.tax_year,
            filing_type=FilingType.AMENDED,
            taxpayer_name=original.taxpayer_name,
            ssn=original.taxpayer_ssn_last4,
            filing_status=original.filing_status,
            is_amended=True,
            original_filing_id=original_filing_id,
            amendment_reason=amendment_reason
        )

        # Create amendment record
        amendment = AmendmentRecord(
            original_filing_id=original_filing_id,
            amended_filing_id=amended_record.filing_id,
            tax_year=original.tax_year,
            amendment_reason=amendment_reason,
            original_values=original_values,
            amended_values=amended_values,
            original_tax=original.total_tax
        )

        self.amendments[amendment.amendment_id] = amendment

        # Update original record status
        original.status = FilingStatus.AMENDED

        return amendment

    def get_filing_summary(self) -> Dict[str, Any]:
        """Get a summary of all filing records."""
        status_counts = {}
        for record in self.records.values():
            status = record.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        year_counts = {}
        for year, filing_ids in self._records_by_year.items():
            year_counts[year] = len(filing_ids)

        accepted_records = self.get_records_by_status(FilingStatus.ACCEPTED)
        total_refunds = sum(
            r.refund_or_owed for r in accepted_records if r.refund_or_owed < 0
        )
        total_owed = sum(
            r.refund_or_owed for r in accepted_records if r.refund_or_owed > 0
        )

        return {
            'total_records': len(self.records),
            'total_amendments': len(self.amendments),
            'status_breakdown': status_counts,
            'year_breakdown': year_counts,
            'accepted_filings': len(accepted_records),
            'total_refunds': abs(total_refunds),
            'total_owed': total_owed,
            'pending_filings': len(self.get_records_by_status(FilingStatus.PENDING)),
            'rejected_filings': len(self.get_records_by_status(FilingStatus.REJECTED))
        }

    def generate_filing_report(self, filing_id: str) -> Optional[str]:
        """Generate a detailed filing report."""
        record = self.records.get(filing_id)
        if not record:
            return None

        lines = [
            "=" * 60,
            "FILING RECORD REPORT",
            "=" * 60,
            f"Filing ID: {record.filing_id}",
            f"Return ID: {record.return_id}",
            f"Tax Year: {record.tax_year}",
            f"Filing Type: {record.filing_type.value}",
            f"Status: {record.status.value}",
            "",
            "TAXPAYER INFORMATION",
            "-" * 40,
            f"Name: {record.taxpayer_name}",
            f"SSN: ***-**-{record.taxpayer_ssn_last4}",
            f"Filing Status: {record.filing_status}",
            "",
            "FINANCIAL SUMMARY",
            "-" * 40,
            f"Gross Income: ${record.gross_income:,.2f}",
            f"Adjusted Gross Income: ${record.adjusted_gross_income:,.2f}",
            f"Taxable Income: ${record.taxable_income:,.2f}",
            f"Total Tax: ${record.total_tax:,.2f}",
            f"Total Payments: ${record.total_payments:,.2f}",
        ]

        if record.refund_or_owed < 0:
            lines.append(f"REFUND: ${abs(record.refund_or_owed):,.2f}")
        elif record.refund_or_owed > 0:
            lines.append(f"AMOUNT OWED: ${record.refund_or_owed:,.2f}")
        else:
            lines.append("No refund or amount owed")

        lines.extend([
            "",
            "FILING TIMELINE",
            "-" * 40,
        ])

        for event in record.get_status_history():
            lines.append(f"  {event['status']}: {event['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")

        if record.submission_id:
            lines.append(f"\nSubmission ID: {record.submission_id}")
        if record.confirmation_number:
            lines.append(f"Confirmation Number: {record.confirmation_number}")

        if record.rejection_info:
            lines.extend([
                "",
                "REJECTION INFORMATION",
                "-" * 40,
                f"Code: {record.rejection_info.rejection_code}",
                f"Message: {record.rejection_info.rejection_message}",
                f"Category: {record.rejection_info.rejection_category}",
            ])
            if record.rejection_info.suggested_fix:
                lines.append(f"Suggested Fix: {record.rejection_info.suggested_fix}")

        if record.preparer_name:
            lines.extend([
                "",
                "PREPARER INFORMATION",
                "-" * 40,
                f"Name: {record.preparer_name}",
                f"PTIN: {record.preparer_ptin or 'N/A'}",
                f"Firm: {record.firm_name or 'N/A'}",
            ])

        lines.append("=" * 60)

        return "\n".join(lines)

    def export_records(self) -> str:
        """Export all records to JSON."""
        return json.dumps({
            'records': {fid: r.to_dict() for fid, r in self.records.items()},
            'amendments': {aid: a.to_dict() for aid, a in self.amendments.items()},
            'export_timestamp': datetime.now().isoformat()
        }, indent=2)

    def import_records(self, json_data: str):
        """Import records from JSON."""
        data = json.loads(json_data)

        for filing_id, record_data in data.get('records', {}).items():
            record = FilingRecord(
                filing_id=record_data['filing_id'],
                return_id=record_data['return_id'],
                tax_year=record_data['tax_year'],
                filing_type=FilingType(record_data['filing_type']),
                status=FilingStatus(record_data['status']),
                taxpayer_name=record_data['taxpayer_name'],
                taxpayer_ssn_last4=record_data['taxpayer_ssn_last4'],
                filing_status=record_data['filing_status']
            )
            self.records[filing_id] = record

            # Rebuild indices
            if record.return_id not in self._records_by_return:
                self._records_by_return[record.return_id] = []
            self._records_by_return[record.return_id].append(filing_id)

            if record.tax_year not in self._records_by_year:
                self._records_by_year[record.tax_year] = []
            self._records_by_year[record.tax_year].append(filing_id)
