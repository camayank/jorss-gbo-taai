"""Document Retention Management.

Manage document storage, retention policies, and
IRS compliance for record keeping requirements.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime, timedelta
import json
import hashlib
import uuid


class DocumentCategory(Enum):
    """Categories of tax documents."""
    # Income documents
    W2 = "w2"
    W2_G = "w2_g"
    FORM_1099_NEC = "1099_nec"
    FORM_1099_MISC = "1099_misc"
    FORM_1099_INT = "1099_int"
    FORM_1099_DIV = "1099_div"
    FORM_1099_B = "1099_b"
    FORM_1099_R = "1099_r"
    FORM_1099_G = "1099_g"
    FORM_1099_K = "1099_k"
    SCHEDULE_K1 = "schedule_k1"
    SSA_1099 = "ssa_1099"

    # Deduction documents
    FORM_1098 = "1098"  # Mortgage interest
    FORM_1098_T = "1098_t"  # Tuition
    FORM_1098_E = "1098_e"  # Student loan interest
    CHARITABLE_RECEIPT = "charitable_receipt"
    MEDICAL_RECEIPT = "medical_receipt"
    PROPERTY_TAX_BILL = "property_tax_bill"

    # Business documents
    BUSINESS_EXPENSE = "business_expense"
    MILEAGE_LOG = "mileage_log"
    HOME_OFFICE = "home_office"
    DEPRECIATION_SCHEDULE = "depreciation_schedule"

    # Investment documents
    BROKERAGE_STATEMENT = "brokerage_statement"
    COST_BASIS = "cost_basis"
    CRYPTO_STATEMENT = "crypto_statement"

    # Tax returns and correspondence
    TAX_RETURN = "tax_return"
    AMENDED_RETURN = "amended_return"
    IRS_NOTICE = "irs_notice"
    STATE_NOTICE = "state_notice"
    FILING_CONFIRMATION = "filing_confirmation"

    # Identification
    ID_DOCUMENT = "id_document"
    BANK_STATEMENT = "bank_statement"

    # Other
    OTHER = "other"


class RetentionPeriod(Enum):
    """IRS-compliant retention periods."""
    THREE_YEARS = 3  # Standard for most returns
    SIX_YEARS = 6  # Underreported income >25%
    SEVEN_YEARS = 7  # Worthless securities, bad debts
    INDEFINITE = 99  # Fraud, unfiled returns, property records


@dataclass
class RetentionPolicy:
    """Retention policy for a document category."""
    category: DocumentCategory
    retention_years: int
    description: str
    legal_reference: str
    requires_original: bool = False
    special_conditions: Optional[str] = None

    def get_retention_date(self, filing_date: datetime) -> datetime:
        """Calculate the date until which document must be retained."""
        return filing_date + timedelta(days=365 * self.retention_years)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'category': self.category.value,
            'retention_years': self.retention_years,
            'description': self.description,
            'legal_reference': self.legal_reference,
            'requires_original': self.requires_original,
            'special_conditions': self.special_conditions
        }


# IRS-compliant retention policies
DEFAULT_RETENTION_POLICIES = {
    DocumentCategory.W2: RetentionPolicy(
        category=DocumentCategory.W2,
        retention_years=7,
        description="W-2 Wage statements",
        legal_reference="IRS Publication 552",
        requires_original=False,
        special_conditions="Keep until Social Security benefits confirmed"
    ),
    DocumentCategory.FORM_1099_NEC: RetentionPolicy(
        category=DocumentCategory.FORM_1099_NEC,
        retention_years=3,
        description="Non-employee compensation",
        legal_reference="IRC Section 6501"
    ),
    DocumentCategory.FORM_1099_INT: RetentionPolicy(
        category=DocumentCategory.FORM_1099_INT,
        retention_years=3,
        description="Interest income",
        legal_reference="IRC Section 6501"
    ),
    DocumentCategory.FORM_1099_B: RetentionPolicy(
        category=DocumentCategory.FORM_1099_B,
        retention_years=7,
        description="Brokerage transactions",
        legal_reference="IRC Section 6501",
        special_conditions="Keep until all positions closed + 3 years"
    ),
    DocumentCategory.TAX_RETURN: RetentionPolicy(
        category=DocumentCategory.TAX_RETURN,
        retention_years=7,
        description="Federal and state tax returns",
        legal_reference="IRS Publication 552",
        special_conditions="Keep indefinitely for property cost basis"
    ),
    DocumentCategory.CHARITABLE_RECEIPT: RetentionPolicy(
        category=DocumentCategory.CHARITABLE_RECEIPT,
        retention_years=3,
        description="Charitable donation receipts",
        legal_reference="IRC Section 170",
        special_conditions="Written acknowledgment required for $250+"
    ),
    DocumentCategory.DEPRECIATION_SCHEDULE: RetentionPolicy(
        category=DocumentCategory.DEPRECIATION_SCHEDULE,
        retention_years=99,  # Indefinite
        description="Depreciation records",
        legal_reference="IRS Publication 946",
        special_conditions="Keep until asset disposed + 3 years"
    ),
    DocumentCategory.COST_BASIS: RetentionPolicy(
        category=DocumentCategory.COST_BASIS,
        retention_years=99,  # Indefinite
        description="Investment cost basis records",
        legal_reference="IRC Section 1012",
        special_conditions="Keep until position sold + 7 years"
    ),
    DocumentCategory.HOME_OFFICE: RetentionPolicy(
        category=DocumentCategory.HOME_OFFICE,
        retention_years=7,
        description="Home office expense documentation",
        legal_reference="IRC Section 280A"
    ),
    DocumentCategory.MILEAGE_LOG: RetentionPolicy(
        category=DocumentCategory.MILEAGE_LOG,
        retention_years=3,
        description="Business mileage records",
        legal_reference="IRC Section 274",
        special_conditions="Contemporaneous records required"
    ),
}


@dataclass
class DocumentRecord:
    """Record of a stored document."""
    document_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    return_id: str = ""
    tax_year: int = 2025
    category: DocumentCategory = DocumentCategory.OTHER
    document_name: str = ""
    original_filename: str = ""
    file_type: str = ""  # pdf, jpg, png, etc.
    file_size: int = 0  # bytes
    file_hash: str = ""  # SHA-256 for integrity

    # Content
    storage_path: Optional[str] = None
    encrypted: bool = True
    ocr_text: Optional[str] = None
    extracted_data: Dict[str, Any] = field(default_factory=dict)

    # Dates
    upload_date: datetime = field(default_factory=datetime.now)
    document_date: Optional[datetime] = None  # Date on the document
    retention_until: Optional[datetime] = None

    # Source and verification
    source: str = ""  # uploaded, imported, irs_transcript
    verified: bool = False
    verification_date: Optional[datetime] = None
    verified_by: Optional[str] = None

    # Metadata
    notes: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def calculate_hash(self, content: bytes) -> str:
        """Calculate SHA-256 hash of document content."""
        self.file_hash = hashlib.sha256(content).hexdigest()
        return self.file_hash

    def verify_hash(self, content: bytes) -> bool:
        """Verify document hasn't been modified."""
        current_hash = hashlib.sha256(content).hexdigest()
        return current_hash == self.file_hash

    def set_retention_policy(self, policy: RetentionPolicy, filing_date: datetime):
        """Apply retention policy to document."""
        self.retention_until = policy.get_retention_date(filing_date)

    def is_retention_expired(self) -> bool:
        """Check if retention period has expired."""
        if not self.retention_until:
            return False
        return datetime.now() > self.retention_until

    def to_dict(self) -> Dict[str, Any]:
        return {
            'document_id': self.document_id,
            'return_id': self.return_id,
            'tax_year': self.tax_year,
            'category': self.category.value,
            'document_name': self.document_name,
            'original_filename': self.original_filename,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'file_hash': self.file_hash,
            'storage_path': self.storage_path,
            'encrypted': self.encrypted,
            'upload_date': self.upload_date.isoformat(),
            'document_date': self.document_date.isoformat() if self.document_date else None,
            'retention_until': self.retention_until.isoformat() if self.retention_until else None,
            'source': self.source,
            'verified': self.verified,
            'verification_date': self.verification_date.isoformat() if self.verification_date else None,
            'verified_by': self.verified_by,
            'notes': self.notes,
            'tags': self.tags,
            'extracted_data': self.extracted_data,
            'metadata': self.metadata
        }


class DocumentRetentionManager:
    """
    Manages document retention and compliance.

    Ensures all tax documents are properly stored,
    tracked, and retained per IRS requirements.
    """

    def __init__(self):
        self.documents: Dict[str, DocumentRecord] = {}
        self.policies = DEFAULT_RETENTION_POLICIES.copy()
        self._documents_by_return: Dict[str, List[str]] = {}
        self._documents_by_year: Dict[int, List[str]] = {}
        self._documents_by_category: Dict[DocumentCategory, List[str]] = {}

    def add_policy(self, policy: RetentionPolicy):
        """Add or update a retention policy."""
        self.policies[policy.category] = policy

    def get_policy(self, category: DocumentCategory) -> RetentionPolicy:
        """Get retention policy for a category."""
        return self.policies.get(category, RetentionPolicy(
            category=category,
            retention_years=7,  # Default to 7 years
            description="Default retention policy",
            legal_reference="IRS Publication 552"
        ))

    def add_document(
        self,
        return_id: str,
        tax_year: int,
        category: DocumentCategory,
        document_name: str,
        original_filename: str,
        file_type: str,
        content: Optional[bytes] = None,
        **kwargs
    ) -> DocumentRecord:
        """Add a document to retention storage."""
        record = DocumentRecord(
            return_id=return_id,
            tax_year=tax_year,
            category=category,
            document_name=document_name,
            original_filename=original_filename,
            file_type=file_type,
            **kwargs
        )

        if content:
            record.file_size = len(content)
            record.calculate_hash(content)

        # Apply retention policy
        policy = self.get_policy(category)
        # Use April 15 of following year as filing date estimate
        filing_date = datetime(tax_year + 1, 4, 15)
        record.set_retention_policy(policy, filing_date)

        # Store and index
        self.documents[record.document_id] = record
        self._index_document(record)

        return record

    def _index_document(self, record: DocumentRecord):
        """Index document for efficient lookups."""
        # By return
        if record.return_id not in self._documents_by_return:
            self._documents_by_return[record.return_id] = []
        self._documents_by_return[record.return_id].append(record.document_id)

        # By year
        if record.tax_year not in self._documents_by_year:
            self._documents_by_year[record.tax_year] = []
        self._documents_by_year[record.tax_year].append(record.document_id)

        # By category
        if record.category not in self._documents_by_category:
            self._documents_by_category[record.category] = []
        self._documents_by_category[record.category].append(record.document_id)

    def get_document(self, document_id: str) -> Optional[DocumentRecord]:
        """Get a document by ID."""
        return self.documents.get(document_id)

    def get_documents_for_return(self, return_id: str) -> List[DocumentRecord]:
        """Get all documents for a return."""
        doc_ids = self._documents_by_return.get(return_id, [])
        return [self.documents[did] for did in doc_ids if did in self.documents]

    def get_documents_for_year(self, tax_year: int) -> List[DocumentRecord]:
        """Get all documents for a tax year."""
        doc_ids = self._documents_by_year.get(tax_year, [])
        return [self.documents[did] for did in doc_ids if did in self.documents]

    def get_documents_by_category(
        self,
        category: DocumentCategory
    ) -> List[DocumentRecord]:
        """Get all documents of a specific category."""
        doc_ids = self._documents_by_category.get(category, [])
        return [self.documents[did] for did in doc_ids if did in self.documents]

    def verify_document(
        self,
        document_id: str,
        verified_by: str,
        content: Optional[bytes] = None
    ) -> bool:
        """Mark a document as verified."""
        record = self.documents.get(document_id)
        if not record:
            return False

        # Verify hash if content provided
        if content and not record.verify_hash(content):
            return False

        record.verified = True
        record.verification_date = datetime.now()
        record.verified_by = verified_by
        return True

    def get_expired_documents(self) -> List[DocumentRecord]:
        """Get documents past their retention period."""
        return [
            doc for doc in self.documents.values()
            if doc.is_retention_expired()
        ]

    def get_documents_expiring_soon(
        self,
        days: int = 90
    ) -> List[DocumentRecord]:
        """Get documents expiring within specified days."""
        cutoff = datetime.now() + timedelta(days=days)
        return [
            doc for doc in self.documents.values()
            if doc.retention_until and doc.retention_until <= cutoff
            and not doc.is_retention_expired()
        ]

    def get_missing_documents(
        self,
        return_id: str,
        required_categories: List[DocumentCategory]
    ) -> List[DocumentCategory]:
        """Check for missing required documents."""
        existing = set(
            doc.category for doc in self.get_documents_for_return(return_id)
        )
        return [cat for cat in required_categories if cat not in existing]

    def get_required_documents_for_return(
        self,
        has_w2_income: bool = False,
        has_1099_income: bool = False,
        has_investments: bool = False,
        has_business: bool = False,
        itemizes_deductions: bool = False,
        has_education: bool = False
    ) -> List[DocumentCategory]:
        """Get list of required documents based on return type."""
        required = []

        if has_w2_income:
            required.append(DocumentCategory.W2)

        if has_1099_income:
            required.extend([
                DocumentCategory.FORM_1099_NEC,
                DocumentCategory.FORM_1099_INT,
                DocumentCategory.FORM_1099_DIV
            ])

        if has_investments:
            required.extend([
                DocumentCategory.FORM_1099_B,
                DocumentCategory.BROKERAGE_STATEMENT,
                DocumentCategory.COST_BASIS
            ])

        if has_business:
            required.extend([
                DocumentCategory.BUSINESS_EXPENSE,
                DocumentCategory.MILEAGE_LOG
            ])

        if itemizes_deductions:
            required.extend([
                DocumentCategory.FORM_1098,
                DocumentCategory.PROPERTY_TAX_BILL,
                DocumentCategory.CHARITABLE_RECEIPT
            ])

        if has_education:
            required.extend([
                DocumentCategory.FORM_1098_T,
                DocumentCategory.FORM_1098_E
            ])

        return required

    def generate_document_checklist(
        self,
        return_id: str,
        tax_year: int
    ) -> Dict[str, Any]:
        """Generate a checklist of documents for a return."""
        existing_docs = self.get_documents_for_return(return_id)
        existing_categories = {doc.category for doc in existing_docs}

        checklist = {
            'tax_year': tax_year,
            'return_id': return_id,
            'generated_at': datetime.now().isoformat(),
            'categories': {}
        }

        for category in DocumentCategory:
            policy = self.get_policy(category)
            docs = [d for d in existing_docs if d.category == category]

            checklist['categories'][category.value] = {
                'name': category.name,
                'has_document': len(docs) > 0,
                'document_count': len(docs),
                'verified': all(d.verified for d in docs) if docs else False,
                'retention_years': policy.retention_years,
                'documents': [
                    {
                        'id': d.document_id,
                        'name': d.document_name,
                        'verified': d.verified,
                        'upload_date': d.upload_date.isoformat()
                    }
                    for d in docs
                ]
            }

        return checklist

    def generate_retention_report(self) -> Dict[str, Any]:
        """Generate a retention compliance report."""
        total_docs = len(self.documents)
        verified_docs = sum(1 for d in self.documents.values() if d.verified)
        expired_docs = self.get_expired_documents()
        expiring_soon = self.get_documents_expiring_soon(90)

        by_category = {}
        for category in DocumentCategory:
            docs = self.get_documents_by_category(category)
            if docs:
                policy = self.get_policy(category)
                by_category[category.value] = {
                    'count': len(docs),
                    'verified': sum(1 for d in docs if d.verified),
                    'retention_years': policy.retention_years,
                    'oldest': min(d.upload_date for d in docs).isoformat(),
                    'newest': max(d.upload_date for d in docs).isoformat()
                }

        by_year = {}
        for year in sorted(self._documents_by_year.keys()):
            docs = self.get_documents_for_year(year)
            by_year[year] = {
                'count': len(docs),
                'verified': sum(1 for d in docs if d.verified),
                'categories': len(set(d.category for d in docs))
            }

        return {
            'report_date': datetime.now().isoformat(),
            'summary': {
                'total_documents': total_docs,
                'verified_documents': verified_docs,
                'verification_rate': verified_docs / total_docs if total_docs else 0,
                'expired_count': len(expired_docs),
                'expiring_soon_count': len(expiring_soon)
            },
            'by_category': by_category,
            'by_year': by_year,
            'expired_documents': [
                {
                    'id': d.document_id,
                    'name': d.document_name,
                    'category': d.category.value,
                    'tax_year': d.tax_year,
                    'retention_until': d.retention_until.isoformat() if d.retention_until else None
                }
                for d in expired_docs
            ],
            'expiring_soon': [
                {
                    'id': d.document_id,
                    'name': d.document_name,
                    'category': d.category.value,
                    'tax_year': d.tax_year,
                    'retention_until': d.retention_until.isoformat() if d.retention_until else None,
                    'days_remaining': (d.retention_until - datetime.now()).days if d.retention_until else None
                }
                for d in expiring_soon
            ]
        }

    def export_documents_metadata(self) -> str:
        """Export all document metadata to JSON."""
        return json.dumps({
            'documents': [d.to_dict() for d in self.documents.values()],
            'policies': {
                cat.value: pol.to_dict()
                for cat, pol in self.policies.items()
            },
            'export_timestamp': datetime.now().isoformat()
        }, indent=2)
