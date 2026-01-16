"""
ETL (Extract, Load, Transform) Pipeline for US Tax Return Processing.

This module provides:
- DataExtractor: Extract tax data from various sources (JSON, CSV, API, PDF)
- DataTransformer: Transform and normalize data to IRS-compliant formats
- DataLoader: Load validated data into database with audit trail
- ETLPipeline: Orchestrate the complete ETL workflow
"""

from __future__ import annotations

import json
import csv
import uuid
import hashlib
import logging
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Any, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from .models import (
    TaxReturnRecord,
    TaxpayerRecord,
    IncomeRecord,
    W2Record,
    Form1099Record,
    DeductionRecord,
    CreditRecord,
    DependentRecord,
    StateReturnRecord,
    AuditLogRecord,
    ComputationWorksheet,
    FilingStatusFlag,
    ReturnStatus,
    IncomeSourceType,
    Form1099Type,
    DeductionType,
    CreditType,
    DependentRelationship,
)
from .validation import (
    StructuralValidator,
    BusinessRulesValidator,
    IRSComplianceValidator,
)
from .schema import ValidationResult, BusinessRuleResult


logger = logging.getLogger(__name__)


class DataSourceType(Enum):
    """Supported data source types for extraction."""
    JSON = "json"
    CSV = "csv"
    XML = "xml"
    PDF = "pdf"
    API = "api"
    MANUAL = "manual"


class TransformationStatus(Enum):
    """Status of data transformation."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class LoadStatus(Enum):
    """Status of data loading."""
    INSERTED = "inserted"
    UPDATED = "updated"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class ExtractionResult:
    """Result of data extraction operation."""
    source_type: DataSourceType
    source_path: str
    success: bool
    records_extracted: int
    raw_data: Dict[str, Any]
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    extraction_timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TransformationResult:
    """Result of data transformation operation."""
    status: TransformationStatus
    transformed_data: Dict[str, Any]
    validation_results: List[ValidationResult] = field(default_factory=list)
    business_rule_results: List[BusinessRuleResult] = field(default_factory=list)
    field_mappings: Dict[str, str] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class LoadResult:
    """Result of data loading operation."""
    status: LoadStatus
    record_id: Optional[str] = None
    records_inserted: int = 0
    records_updated: int = 0
    records_failed: int = 0
    errors: List[str] = field(default_factory=list)
    audit_log_id: Optional[str] = None


@dataclass
class ETLResult:
    """Complete ETL pipeline result."""
    pipeline_id: str
    extraction: ExtractionResult
    transformation: TransformationResult
    load: LoadResult
    success: bool
    total_duration_ms: float
    started_at: datetime
    completed_at: datetime


class DataExtractor:
    """
    Extract tax data from various sources.

    Supports:
    - JSON files (tax return data exports)
    - CSV files (W-2, 1099 bulk imports)
    - API responses (employer/broker data feeds)
    - Manual entry (user input validation)
    """

    # Field mapping from common external formats to internal schema
    FIELD_MAPPINGS = {
        # Common JSON field variations
        "social_security_number": "ssn",
        "socialSecurityNumber": "ssn",
        "ssn": "ssn",
        "tax_id": "ssn",
        "taxpayer_id": "ssn",

        "first_name": "first_name",
        "firstName": "first_name",
        "fname": "first_name",

        "last_name": "last_name",
        "lastName": "last_name",
        "lname": "last_name",

        "filing_status": "filing_status",
        "filingStatus": "filing_status",
        "status": "filing_status",

        "wages": "wages_salaries_tips",
        "wage_income": "wages_salaries_tips",
        "w2_wages": "wages_salaries_tips",
        "box1": "wages_salaries_tips",

        "federal_withholding": "federal_income_tax_withheld",
        "federalWithholding": "federal_income_tax_withheld",
        "fed_withhold": "federal_income_tax_withheld",
        "box2": "federal_income_tax_withheld",

        "social_security_wages": "social_security_wages",
        "ss_wages": "social_security_wages",
        "box3": "social_security_wages",

        "social_security_tax": "social_security_tax_withheld",
        "ss_tax": "social_security_tax_withheld",
        "box4": "social_security_tax_withheld",

        "medicare_wages": "medicare_wages_tips",
        "med_wages": "medicare_wages_tips",
        "box5": "medicare_wages_tips",

        "medicare_tax": "medicare_tax_withheld",
        "med_tax": "medicare_tax_withheld",
        "box6": "medicare_tax_withheld",

        "interest_income": "taxable_interest",
        "dividend_income": "ordinary_dividends",
        "qualified_dividends": "qualified_dividends",
        "capital_gains": "capital_gain_loss",
        "ira_distributions": "ira_distributions_taxable",
        "pension_income": "pensions_annuities_taxable",
        "social_security_benefits": "social_security_benefits",
        "unemployment": "unemployment_compensation",
        "other_income": "other_income",
    }

    # Filing status normalization
    FILING_STATUS_MAP = {
        "single": FilingStatusFlag.SINGLE,
        "s": FilingStatusFlag.SINGLE,
        "1": FilingStatusFlag.SINGLE,

        "married_filing_jointly": FilingStatusFlag.MARRIED_FILING_JOINTLY,
        "mfj": FilingStatusFlag.MARRIED_FILING_JOINTLY,
        "married_joint": FilingStatusFlag.MARRIED_FILING_JOINTLY,
        "2": FilingStatusFlag.MARRIED_FILING_JOINTLY,

        "married_filing_separately": FilingStatusFlag.MARRIED_FILING_SEPARATELY,
        "mfs": FilingStatusFlag.MARRIED_FILING_SEPARATELY,
        "married_separate": FilingStatusFlag.MARRIED_FILING_SEPARATELY,
        "3": FilingStatusFlag.MARRIED_FILING_SEPARATELY,

        "head_of_household": FilingStatusFlag.HEAD_OF_HOUSEHOLD,
        "hoh": FilingStatusFlag.HEAD_OF_HOUSEHOLD,
        "head": FilingStatusFlag.HEAD_OF_HOUSEHOLD,
        "4": FilingStatusFlag.HEAD_OF_HOUSEHOLD,

        "qualifying_surviving_spouse": FilingStatusFlag.QUALIFYING_SURVIVING_SPOUSE,
        "qss": FilingStatusFlag.QUALIFYING_SURVIVING_SPOUSE,
        "widow": FilingStatusFlag.QUALIFYING_SURVIVING_SPOUSE,
        "widower": FilingStatusFlag.QUALIFYING_SURVIVING_SPOUSE,
        "5": FilingStatusFlag.QUALIFYING_SURVIVING_SPOUSE,
    }

    def __init__(self):
        self.extraction_log: List[Dict[str, Any]] = []

    def extract_from_json(self, file_path: str) -> ExtractionResult:
        """Extract tax data from JSON file."""
        errors = []
        warnings = []
        raw_data = {}

        try:
            path = Path(file_path)
            if not path.exists():
                return ExtractionResult(
                    source_type=DataSourceType.JSON,
                    source_path=file_path,
                    success=False,
                    records_extracted=0,
                    raw_data={},
                    errors=[f"File not found: {file_path}"]
                )

            with open(path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)

            # Validate basic structure
            if not isinstance(raw_data, dict):
                if isinstance(raw_data, list):
                    raw_data = {"records": raw_data}
                    warnings.append("JSON was array, wrapped in 'records' key")
                else:
                    return ExtractionResult(
                        source_type=DataSourceType.JSON,
                        source_path=file_path,
                        success=False,
                        records_extracted=0,
                        raw_data={},
                        errors=["Invalid JSON structure: expected object or array"]
                    )

            # Count records
            records = 1 if "records" not in raw_data else len(raw_data.get("records", []))

            return ExtractionResult(
                source_type=DataSourceType.JSON,
                source_path=file_path,
                success=True,
                records_extracted=records,
                raw_data=raw_data,
                warnings=warnings
            )

        except json.JSONDecodeError as e:
            return ExtractionResult(
                source_type=DataSourceType.JSON,
                source_path=file_path,
                success=False,
                records_extracted=0,
                raw_data={},
                errors=[f"JSON parse error: {str(e)}"]
            )
        except Exception as e:
            return ExtractionResult(
                source_type=DataSourceType.JSON,
                source_path=file_path,
                success=False,
                records_extracted=0,
                raw_data={},
                errors=[f"Extraction error: {str(e)}"]
            )

    def extract_from_csv(
        self,
        file_path: str,
        record_type: str = "w2"
    ) -> ExtractionResult:
        """
        Extract tax data from CSV file.

        Args:
            file_path: Path to CSV file
            record_type: Type of records (w2, 1099_int, 1099_div, 1099_misc, etc.)
        """
        errors = []
        warnings = []
        records = []

        try:
            path = Path(file_path)
            if not path.exists():
                return ExtractionResult(
                    source_type=DataSourceType.CSV,
                    source_path=file_path,
                    success=False,
                    records_extracted=0,
                    raw_data={},
                    errors=[f"File not found: {file_path}"]
                )

            with open(path, 'r', encoding='utf-8') as f:
                # Detect delimiter
                sample = f.read(1024)
                f.seek(0)

                delimiter = ','
                if sample.count('\t') > sample.count(','):
                    delimiter = '\t'
                    warnings.append("Detected tab-delimited format")

                reader = csv.DictReader(f, delimiter=delimiter)

                for row_num, row in enumerate(reader, start=1):
                    try:
                        # Normalize field names
                        normalized_row = {}
                        for key, value in row.items():
                            if key:
                                norm_key = key.lower().strip().replace(' ', '_')
                                normalized_row[norm_key] = value.strip() if value else None

                        normalized_row['_source_row'] = row_num
                        normalized_row['_record_type'] = record_type
                        records.append(normalized_row)

                    except Exception as e:
                        warnings.append(f"Row {row_num}: {str(e)}")

            return ExtractionResult(
                source_type=DataSourceType.CSV,
                source_path=file_path,
                success=True,
                records_extracted=len(records),
                raw_data={"records": records, "record_type": record_type},
                warnings=warnings
            )

        except Exception as e:
            return ExtractionResult(
                source_type=DataSourceType.CSV,
                source_path=file_path,
                success=False,
                records_extracted=0,
                raw_data={},
                errors=[f"CSV extraction error: {str(e)}"]
            )

    def extract_from_dict(self, data: Dict[str, Any]) -> ExtractionResult:
        """Extract and validate data from dictionary (API or manual entry)."""
        try:
            if not isinstance(data, dict):
                return ExtractionResult(
                    source_type=DataSourceType.MANUAL,
                    source_path="dict_input",
                    success=False,
                    records_extracted=0,
                    raw_data={},
                    errors=["Input must be a dictionary"]
                )

            return ExtractionResult(
                source_type=DataSourceType.MANUAL,
                source_path="dict_input",
                success=True,
                records_extracted=1,
                raw_data=data
            )

        except Exception as e:
            return ExtractionResult(
                source_type=DataSourceType.MANUAL,
                source_path="dict_input",
                success=False,
                records_extracted=0,
                raw_data={},
                errors=[f"Extraction error: {str(e)}"]
            )

    def normalize_field_name(self, field_name: str) -> str:
        """Normalize field name to internal schema format."""
        normalized = field_name.lower().strip().replace(' ', '_').replace('-', '_')
        return self.FIELD_MAPPINGS.get(normalized, normalized)

    def normalize_filing_status(self, status: str) -> Optional[FilingStatusFlag]:
        """Normalize filing status string to enum."""
        if status is None:
            return None
        normalized = status.lower().strip().replace(' ', '_').replace('-', '_')
        return self.FILING_STATUS_MAP.get(normalized)


class DataTransformer:
    """
    Transform extracted data to IRS-compliant format.

    Handles:
    - Field mapping and normalization
    - Data type conversion
    - Computed field calculations
    - Validation integration
    """

    # Tax Year 2025 parameters
    TAX_YEAR = 2025

    # Standard deduction amounts for 2025 (IRS Rev. Proc. 2024-40)
    STANDARD_DEDUCTIONS = {
        FilingStatusFlag.SINGLE: Decimal("15750"),
        FilingStatusFlag.MARRIED_FILING_JOINTLY: Decimal("31500"),
        FilingStatusFlag.MARRIED_FILING_SEPARATELY: Decimal("15750"),
        FilingStatusFlag.HEAD_OF_HOUSEHOLD: Decimal("23625"),
        FilingStatusFlag.QUALIFYING_SURVIVING_SPOUSE: Decimal("31500"),
    }

    def __init__(self):
        self.structural_validator = StructuralValidator()
        self.business_validator = BusinessRulesValidator()
        self.compliance_validator = IRSComplianceValidator()
        self.extractor = DataExtractor()

    def transform(self, extraction_result: ExtractionResult) -> TransformationResult:
        """
        Transform extracted data to IRS-compliant format.

        Performs:
        1. Field mapping and normalization
        2. Data type conversion
        3. Computed field calculations
        4. Structural validation
        5. Business rules validation
        """
        if not extraction_result.success:
            return TransformationResult(
                status=TransformationStatus.FAILED,
                transformed_data={},
                errors=extraction_result.errors
            )

        errors = []
        warnings = []
        field_mappings = {}

        try:
            raw_data = extraction_result.raw_data
            transformed = {}

            # Step 1: Normalize and map fields
            transformed, field_mappings = self._normalize_fields(raw_data)

            # Step 2: Convert data types
            transformed = self._convert_data_types(transformed)

            # Step 3: Calculate computed fields
            transformed = self._calculate_computed_fields(transformed)

            # Step 4: Generate required identifiers
            transformed = self._generate_identifiers(transformed)

            # Step 5: Validate structure
            validation_results = self.structural_validator.validate_all(transformed)
            structural_errors = [v.message for v in validation_results if not v.is_valid]

            # Step 6: Validate business rules
            business_results = self.business_validator.validate(transformed)
            business_errors = [b.message for b in business_results if not b.passed]

            # Determine status
            if structural_errors or business_errors:
                status = TransformationStatus.PARTIAL
                errors.extend(structural_errors)
                errors.extend(business_errors)
            else:
                status = TransformationStatus.SUCCESS

            return TransformationResult(
                status=status,
                transformed_data=transformed,
                validation_results=validation_results,
                business_rule_results=business_results,
                field_mappings=field_mappings,
                errors=errors,
                warnings=warnings
            )

        except Exception as e:
            logger.exception("Transformation error")
            return TransformationResult(
                status=TransformationStatus.FAILED,
                transformed_data={},
                errors=[f"Transformation error: {str(e)}"]
            )

    def _normalize_fields(
        self,
        raw_data: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """Normalize field names and structure."""
        normalized = {}
        mappings = {}

        def process_dict(data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
            result = {}
            for key, value in data.items():
                # Skip internal keys
                if key.startswith('_'):
                    continue

                original_key = f"{prefix}{key}" if prefix else key
                norm_key = self.extractor.normalize_field_name(key)

                if norm_key != original_key:
                    mappings[original_key] = norm_key

                if isinstance(value, dict):
                    result[norm_key] = process_dict(value, f"{norm_key}.")
                elif isinstance(value, list):
                    result[norm_key] = [
                        process_dict(item) if isinstance(item, dict) else item
                        for item in value
                    ]
                else:
                    result[norm_key] = value

            return result

        normalized = process_dict(raw_data)
        return normalized, mappings

    def _convert_data_types(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert fields to appropriate data types."""
        converted = data.copy()

        # Monetary fields - convert to Decimal
        monetary_fields = [
            'wages_salaries_tips', 'taxable_interest', 'tax_exempt_interest',
            'ordinary_dividends', 'qualified_dividends', 'capital_gain_loss',
            'ira_distributions_total', 'ira_distributions_taxable',
            'pensions_annuities_total', 'pensions_annuities_taxable',
            'social_security_benefits', 'social_security_taxable',
            'other_income', 'total_income', 'adjustments_to_income',
            'adjusted_gross_income', 'standard_deduction', 'itemized_deductions',
            'qualified_business_income_deduction', 'taxable_income',
            'total_tax', 'federal_income_tax_withheld', 'estimated_tax_payments',
            'earned_income_credit', 'child_tax_credit', 'other_credits',
            'total_payments', 'amount_owed', 'overpaid', 'refund_amount',
            'social_security_wages', 'social_security_tax_withheld',
            'medicare_wages_tips', 'medicare_tax_withheld',
        ]

        for field in monetary_fields:
            if field in converted and converted[field] is not None:
                converted[field] = self._to_decimal(converted[field])

        # Integer fields
        integer_fields = ['tax_year', 'num_dependents']
        for field in integer_fields:
            if field in converted and converted[field] is not None:
                try:
                    converted[field] = int(converted[field])
                except (ValueError, TypeError):
                    pass

        # Filing status normalization
        if 'filing_status' in converted:
            status = self.extractor.normalize_filing_status(
                str(converted['filing_status'])
            )
            if status:
                converted['filing_status'] = status.value

        # Date fields
        date_fields = ['date_of_birth', 'spouse_date_of_birth']
        for field in date_fields:
            if field in converted and converted[field]:
                converted[field] = self._parse_date(converted[field])

        # Boolean fields
        boolean_fields = [
            'is_blind', 'spouse_is_blind', 'can_be_claimed_as_dependent',
            'spouse_can_be_claimed', 'has_health_coverage', 'is_self_employed',
        ]
        for field in boolean_fields:
            if field in converted:
                converted[field] = self._to_boolean(converted[field])

        return converted

    def _to_decimal(self, value: Any) -> Optional[Decimal]:
        """Convert value to Decimal."""
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        try:
            # Remove common formatting
            if isinstance(value, str):
                value = value.replace(',', '').replace('$', '').strip()
                if value == '' or value.lower() in ('null', 'none', 'n/a'):
                    return None
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    def _parse_date(self, value: Any) -> Optional[date]:
        """Parse date from various formats."""
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()

        date_formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%m-%d-%Y',
            '%Y/%m/%d',
            '%d-%m-%Y',
            '%d/%m/%Y',
        ]

        value_str = str(value).strip()
        for fmt in date_formats:
            try:
                return datetime.strptime(value_str, fmt).date()
            except ValueError:
                continue

        return None

    def _to_boolean(self, value: Any) -> bool:
        """Convert value to boolean."""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', 'yes', '1', 'y', 't')
        return bool(value)

    def _calculate_computed_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate derived/computed fields."""
        computed = data.copy()

        # Calculate total income if components provided
        income_fields = [
            'wages_salaries_tips', 'taxable_interest', 'ordinary_dividends',
            'capital_gain_loss', 'ira_distributions_taxable',
            'pensions_annuities_taxable', 'social_security_taxable',
            'unemployment_compensation', 'other_income',
        ]

        if 'total_income' not in computed or computed['total_income'] is None:
            total = Decimal('0')
            for field in income_fields:
                if field in computed and computed[field] is not None:
                    total += computed[field]
            if total > 0:
                computed['total_income'] = total

        # Calculate AGI if adjustments provided
        if ('adjusted_gross_income' not in computed or
            computed['adjusted_gross_income'] is None):
            if 'total_income' in computed and computed['total_income'] is not None:
                adjustments = computed.get('adjustments_to_income') or Decimal('0')
                computed['adjusted_gross_income'] = (
                    computed['total_income'] - adjustments
                )

        # Set standard deduction if not provided
        if ('standard_deduction' not in computed or
            computed['standard_deduction'] is None):
            if 'filing_status' in computed:
                status_str = computed['filing_status']
                try:
                    status = FilingStatusFlag(status_str)
                    computed['standard_deduction'] = self.STANDARD_DEDUCTIONS.get(status)
                except ValueError:
                    pass

        # Calculate taxable income
        if 'taxable_income' not in computed or computed['taxable_income'] is None:
            agi = computed.get('adjusted_gross_income')
            if agi is not None:
                deduction = computed.get('itemized_deductions')
                if deduction is None or deduction <= 0:
                    deduction = computed.get('standard_deduction') or Decimal('0')
                qbi = computed.get('qualified_business_income_deduction') or Decimal('0')
                taxable = agi - deduction - qbi
                computed['taxable_income'] = max(taxable, Decimal('0'))

        # Calculate total payments
        if 'total_payments' not in computed or computed['total_payments'] is None:
            payments = Decimal('0')
            payment_fields = [
                'federal_income_tax_withheld', 'estimated_tax_payments',
                'earned_income_credit', 'additional_child_tax_credit',
                'american_opportunity_credit_refundable', 'other_refundable_credits',
            ]
            for field in payment_fields:
                if field in computed and computed[field] is not None:
                    payments += computed[field]
            if payments > 0:
                computed['total_payments'] = payments

        # Set tax year if not provided
        if 'tax_year' not in computed or computed['tax_year'] is None:
            computed['tax_year'] = self.TAX_YEAR

        return computed

    def _generate_identifiers(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate required identifiers and hashes."""
        result = data.copy()

        # Generate return_id if not present
        if 'return_id' not in result or result['return_id'] is None:
            result['return_id'] = str(uuid.uuid4())

        # Generate SSN hash for lookup (if SSN provided)
        if 'ssn' in result and result['ssn']:
            ssn = str(result['ssn']).replace('-', '').replace(' ', '')
            result['ssn_hash'] = hashlib.sha256(ssn.encode()).hexdigest()

        # Add metadata timestamps
        now = datetime.utcnow()
        if 'created_at' not in result:
            result['created_at'] = now
        result['updated_at'] = now

        return result


class DataLoader:
    """
    Load validated data into the database.

    Handles:
    - Record creation/update with proper transactions
    - Audit trail generation
    - Rollback on errors
    - Duplicate detection
    """

    def __init__(self, session: Optional[Session] = None):
        """
        Initialize DataLoader.

        Args:
            session: SQLAlchemy session (optional, can be set later)
        """
        self.session = session

    def set_session(self, session: Session) -> None:
        """Set the database session."""
        self.session = session

    def load_tax_return(
        self,
        transformation_result: TransformationResult,
        user_id: Optional[str] = None
    ) -> LoadResult:
        """
        Load transformed tax return data into database.

        Creates or updates:
        - TaxReturnRecord (master)
        - TaxpayerRecord (taxpayer info)
        - Associated income, deduction, credit records
        - Audit log entry
        """
        if transformation_result.status == TransformationStatus.FAILED:
            return LoadResult(
                status=LoadStatus.FAILED,
                errors=transformation_result.errors
            )

        if self.session is None:
            return LoadResult(
                status=LoadStatus.FAILED,
                errors=["Database session not configured"]
            )

        data = transformation_result.transformed_data
        errors = []

        try:
            # Check for existing record
            existing = self._find_existing_return(data)

            if existing:
                # Update existing record
                result = self._update_return(existing, data, user_id)
            else:
                # Create new record
                result = self._create_return(data, user_id)

            # Commit transaction
            self.session.commit()
            return result

        except Exception as e:
            self.session.rollback()
            logger.exception("Load error")
            return LoadResult(
                status=LoadStatus.FAILED,
                errors=[f"Database error: {str(e)}"]
            )

    def _find_existing_return(self, data: Dict[str, Any]) -> Optional[TaxReturnRecord]:
        """Find existing tax return by composite key."""
        tax_year = data.get('tax_year')
        ssn_hash = data.get('ssn_hash')

        if not tax_year or not ssn_hash:
            return None

        return self.session.query(TaxReturnRecord).filter(
            TaxReturnRecord.tax_year == tax_year,
            TaxReturnRecord.taxpayer_ssn_hash == ssn_hash
        ).first()

    def _create_return(
        self,
        data: Dict[str, Any],
        user_id: Optional[str]
    ) -> LoadResult:
        """Create new tax return record."""
        try:
            # Create taxpayer record
            taxpayer = self._create_taxpayer(data)
            self.session.add(taxpayer)
            self.session.flush()

            # Create tax return record
            tax_return = TaxReturnRecord(
                return_id=uuid.UUID(data['return_id']) if isinstance(data.get('return_id'), str) else uuid.uuid4(),
                taxpayer_id=taxpayer.taxpayer_id,
                taxpayer_ssn_hash=data.get('ssn_hash', ''),
                tax_year=data.get('tax_year', 2025),
                filing_status=FilingStatusFlag(data['filing_status']) if data.get('filing_status') else FilingStatusFlag.SINGLE,

                # Form 1040 Line Items
                wages_salaries_tips=data.get('wages_salaries_tips'),
                taxable_interest=data.get('taxable_interest'),
                tax_exempt_interest=data.get('tax_exempt_interest'),
                ordinary_dividends=data.get('ordinary_dividends'),
                qualified_dividends=data.get('qualified_dividends'),
                capital_gain_loss=data.get('capital_gain_loss'),
                ira_distributions_total=data.get('ira_distributions_total'),
                ira_distributions_taxable=data.get('ira_distributions_taxable'),
                pensions_annuities_total=data.get('pensions_annuities_total'),
                pensions_annuities_taxable=data.get('pensions_annuities_taxable'),
                social_security_benefits=data.get('social_security_benefits'),
                social_security_taxable=data.get('social_security_taxable'),
                schedule_1_additional_income=data.get('schedule_1_additional_income'),
                total_income=data.get('total_income'),
                adjustments_to_income=data.get('adjustments_to_income'),
                adjusted_gross_income=data.get('adjusted_gross_income'),
                standard_deduction=data.get('standard_deduction'),
                itemized_deductions=data.get('itemized_deductions'),
                qualified_business_income_deduction=data.get('qualified_business_income_deduction'),
                taxable_income=data.get('taxable_income'),
                tax_from_tables=data.get('tax_from_tables'),
                schedule_2_additional_tax=data.get('schedule_2_additional_tax'),
                total_tax=data.get('total_tax'),
                federal_income_tax_withheld=data.get('federal_income_tax_withheld'),
                estimated_tax_payments=data.get('estimated_tax_payments'),
                earned_income_credit=data.get('earned_income_credit'),
                child_tax_credit=data.get('child_tax_credit'),
                other_refundable_credits=data.get('other_refundable_credits'),
                total_payments=data.get('total_payments'),
                amount_owed=data.get('amount_owed'),
                overpaid=data.get('overpaid'),
                refund_amount=data.get('refund_amount'),
                amount_applied_to_next_year=data.get('amount_applied_to_next_year'),

                status=ReturnStatus.DRAFT,
                created_by=user_id,
                updated_by=user_id,
            )

            self.session.add(tax_return)
            self.session.flush()

            # Create W-2 records if present
            w2_records = data.get('w2_records', [])
            for w2_data in w2_records:
                w2 = self._create_w2(tax_return.return_id, w2_data)
                self.session.add(w2)

            # Create 1099 records if present
            form_1099_records = data.get('form_1099_records', [])
            for f1099_data in form_1099_records:
                f1099 = self._create_1099(tax_return.return_id, f1099_data)
                self.session.add(f1099)

            # Create audit log
            audit = self._create_audit_log(
                tax_return.return_id,
                'CREATE',
                user_id,
                None,
                data
            )
            self.session.add(audit)

            return LoadResult(
                status=LoadStatus.INSERTED,
                record_id=str(tax_return.return_id),
                records_inserted=1,
                audit_log_id=str(audit.log_id)
            )

        except Exception as e:
            raise

    def _update_return(
        self,
        existing: TaxReturnRecord,
        data: Dict[str, Any],
        user_id: Optional[str]
    ) -> LoadResult:
        """Update existing tax return record."""
        old_data = self._record_to_dict(existing)

        # Update fields
        updatable_fields = [
            'wages_salaries_tips', 'taxable_interest', 'tax_exempt_interest',
            'ordinary_dividends', 'qualified_dividends', 'capital_gain_loss',
            'ira_distributions_total', 'ira_distributions_taxable',
            'pensions_annuities_total', 'pensions_annuities_taxable',
            'social_security_benefits', 'social_security_taxable',
            'total_income', 'adjustments_to_income', 'adjusted_gross_income',
            'standard_deduction', 'itemized_deductions',
            'qualified_business_income_deduction', 'taxable_income',
            'tax_from_tables', 'total_tax', 'federal_income_tax_withheld',
            'estimated_tax_payments', 'earned_income_credit', 'child_tax_credit',
            'total_payments', 'amount_owed', 'overpaid', 'refund_amount',
        ]

        for field in updatable_fields:
            if field in data:
                setattr(existing, field, data[field])

        existing.updated_at = datetime.utcnow()
        existing.updated_by = user_id

        # Create audit log
        audit = self._create_audit_log(
            existing.return_id,
            'UPDATE',
            user_id,
            old_data,
            data
        )
        self.session.add(audit)

        return LoadResult(
            status=LoadStatus.UPDATED,
            record_id=str(existing.return_id),
            records_updated=1,
            audit_log_id=str(audit.log_id)
        )

    def _create_taxpayer(self, data: Dict[str, Any]) -> TaxpayerRecord:
        """Create taxpayer record."""
        return TaxpayerRecord(
            taxpayer_id=uuid.uuid4(),
            ssn_hash=data.get('ssn_hash', ''),
            ssn_encrypted=data.get('ssn_encrypted'),
            first_name=data.get('first_name', ''),
            middle_name=data.get('middle_name'),
            last_name=data.get('last_name', ''),
            suffix=data.get('suffix'),
            date_of_birth=data.get('date_of_birth'),
            is_blind=data.get('is_blind', False),
            occupation=data.get('occupation'),
            phone_number=data.get('phone_number'),
            email=data.get('email'),
            address_street=data.get('address_street'),
            address_apt=data.get('address_apt'),
            address_city=data.get('address_city'),
            address_state=data.get('address_state'),
            address_zip=data.get('address_zip'),
            address_country=data.get('address_country', 'US'),
        )

    def _create_w2(
        self,
        return_id: uuid.UUID,
        data: Dict[str, Any]
    ) -> W2Record:
        """Create W-2 record."""
        return W2Record(
            w2_id=uuid.uuid4(),
            return_id=return_id,
            employer_ein=data.get('employer_ein', ''),
            employer_name=data.get('employer_name', ''),
            employer_address=data.get('employer_address'),
            control_number=data.get('control_number'),
            wages_tips_compensation=data.get('wages_tips_compensation'),
            federal_income_tax_withheld=data.get('federal_income_tax_withheld'),
            social_security_wages=data.get('social_security_wages'),
            social_security_tax_withheld=data.get('social_security_tax_withheld'),
            medicare_wages_tips=data.get('medicare_wages_tips'),
            medicare_tax_withheld=data.get('medicare_tax_withheld'),
            social_security_tips=data.get('social_security_tips'),
            allocated_tips=data.get('allocated_tips'),
            dependent_care_benefits=data.get('dependent_care_benefits'),
            nonqualified_plans=data.get('nonqualified_plans'),
            box_12_codes=data.get('box_12_codes'),
            is_statutory_employee=data.get('is_statutory_employee', False),
            is_retirement_plan=data.get('is_retirement_plan', False),
            is_third_party_sick_pay=data.get('is_third_party_sick_pay', False),
            state_employer_id=data.get('state_employer_id'),
            state_wages=data.get('state_wages'),
            state_income_tax=data.get('state_income_tax'),
            local_wages=data.get('local_wages'),
            local_income_tax=data.get('local_income_tax'),
            locality_name=data.get('locality_name'),
        )

    def _create_1099(
        self,
        return_id: uuid.UUID,
        data: Dict[str, Any]
    ) -> Form1099Record:
        """Create Form 1099 record."""
        form_type = data.get('form_type', 'INT')
        try:
            form_type_enum = Form1099Type(form_type)
        except ValueError:
            form_type_enum = Form1099Type.MISC

        return Form1099Record(
            form_1099_id=uuid.uuid4(),
            return_id=return_id,
            form_type=form_type_enum,
            payer_tin=data.get('payer_tin', ''),
            payer_name=data.get('payer_name', ''),
            payer_address=data.get('payer_address'),
            account_number=data.get('account_number'),
            box_1_amount=data.get('box_1_amount'),
            box_2_amount=data.get('box_2_amount'),
            box_3_amount=data.get('box_3_amount'),
            federal_income_tax_withheld=data.get('federal_income_tax_withheld'),
            state_tax_withheld=data.get('state_tax_withheld'),
            state_payer_id=data.get('state_payer_id'),
        )

    def _create_audit_log(
        self,
        return_id: uuid.UUID,
        action: str,
        user_id: Optional[str],
        old_values: Optional[Dict],
        new_values: Dict
    ) -> AuditLogRecord:
        """Create audit log entry."""
        return AuditLogRecord(
            log_id=uuid.uuid4(),
            return_id=return_id,
            action=action,
            table_name='tax_return',
            old_values=json.dumps(old_values) if old_values else None,
            new_values=json.dumps(new_values, default=str),
            performed_by=user_id,
            ip_address=None,
            user_agent=None,
        )

    def _record_to_dict(self, record: TaxReturnRecord) -> Dict[str, Any]:
        """Convert record to dictionary for audit."""
        return {
            'return_id': str(record.return_id),
            'tax_year': record.tax_year,
            'filing_status': record.filing_status.value if record.filing_status else None,
            'wages_salaries_tips': str(record.wages_salaries_tips) if record.wages_salaries_tips else None,
            'total_income': str(record.total_income) if record.total_income else None,
            'adjusted_gross_income': str(record.adjusted_gross_income) if record.adjusted_gross_income else None,
            'taxable_income': str(record.taxable_income) if record.taxable_income else None,
            'total_tax': str(record.total_tax) if record.total_tax else None,
            'refund_amount': str(record.refund_amount) if record.refund_amount else None,
            'status': record.status.value if record.status else None,
        }


class ETLPipeline:
    """
    Complete ETL pipeline orchestrator.

    Coordinates extraction, transformation, and loading with:
    - Full audit trail
    - Error handling and rollback
    - Progress tracking
    - Validation at each stage
    """

    def __init__(self, session: Optional[Session] = None):
        """
        Initialize ETL pipeline.

        Args:
            session: SQLAlchemy database session
        """
        self.extractor = DataExtractor()
        self.transformer = DataTransformer()
        self.loader = DataLoader(session)
        self.pipeline_runs: List[ETLResult] = []

    def set_session(self, session: Session) -> None:
        """Set database session for loader."""
        self.loader.set_session(session)

    def process_json_file(
        self,
        file_path: str,
        user_id: Optional[str] = None
    ) -> ETLResult:
        """Process tax return from JSON file."""
        return self._run_pipeline(
            lambda: self.extractor.extract_from_json(file_path),
            user_id
        )

    def process_csv_file(
        self,
        file_path: str,
        record_type: str = "w2",
        user_id: Optional[str] = None
    ) -> ETLResult:
        """Process records from CSV file."""
        return self._run_pipeline(
            lambda: self.extractor.extract_from_csv(file_path, record_type),
            user_id
        )

    def process_dict(
        self,
        data: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> ETLResult:
        """Process tax return from dictionary."""
        return self._run_pipeline(
            lambda: self.extractor.extract_from_dict(data),
            user_id
        )

    def _run_pipeline(
        self,
        extract_fn,
        user_id: Optional[str]
    ) -> ETLResult:
        """Run complete ETL pipeline."""
        pipeline_id = str(uuid.uuid4())
        started_at = datetime.utcnow()

        try:
            # Step 1: Extract
            extraction_result = extract_fn()

            if not extraction_result.success:
                return self._create_result(
                    pipeline_id,
                    extraction_result,
                    TransformationResult(
                        status=TransformationStatus.SKIPPED,
                        transformed_data={}
                    ),
                    LoadResult(status=LoadStatus.SKIPPED),
                    started_at
                )

            # Step 2: Transform
            transformation_result = self.transformer.transform(extraction_result)

            if transformation_result.status == TransformationStatus.FAILED:
                return self._create_result(
                    pipeline_id,
                    extraction_result,
                    transformation_result,
                    LoadResult(status=LoadStatus.SKIPPED),
                    started_at
                )

            # Step 3: Load
            load_result = self.loader.load_tax_return(
                transformation_result,
                user_id
            )

            return self._create_result(
                pipeline_id,
                extraction_result,
                transformation_result,
                load_result,
                started_at
            )

        except Exception as e:
            logger.exception("Pipeline error")
            return self._create_result(
                pipeline_id,
                ExtractionResult(
                    source_type=DataSourceType.MANUAL,
                    source_path="",
                    success=False,
                    records_extracted=0,
                    raw_data={},
                    errors=[str(e)]
                ),
                TransformationResult(
                    status=TransformationStatus.FAILED,
                    transformed_data={},
                    errors=[str(e)]
                ),
                LoadResult(status=LoadStatus.FAILED, errors=[str(e)]),
                started_at
            )

    def _create_result(
        self,
        pipeline_id: str,
        extraction: ExtractionResult,
        transformation: TransformationResult,
        load: LoadResult,
        started_at: datetime
    ) -> ETLResult:
        """Create pipeline result."""
        completed_at = datetime.utcnow()
        duration_ms = (completed_at - started_at).total_seconds() * 1000

        success = (
            extraction.success and
            transformation.status in (
                TransformationStatus.SUCCESS,
                TransformationStatus.PARTIAL
            ) and
            load.status in (LoadStatus.INSERTED, LoadStatus.UPDATED)
        )

        result = ETLResult(
            pipeline_id=pipeline_id,
            extraction=extraction,
            transformation=transformation,
            load=load,
            success=success,
            total_duration_ms=duration_ms,
            started_at=started_at,
            completed_at=completed_at
        )

        self.pipeline_runs.append(result)
        return result

    def get_pipeline_history(self) -> List[ETLResult]:
        """Get history of pipeline runs."""
        return self.pipeline_runs.copy()

    def validate_without_load(
        self,
        data: Dict[str, Any]
    ) -> Tuple[TransformationResult, List[str]]:
        """
        Validate data without loading to database.

        Useful for preview/dry-run operations.
        """
        extraction = self.extractor.extract_from_dict(data)

        if not extraction.success:
            return TransformationResult(
                status=TransformationStatus.FAILED,
                transformed_data={},
                errors=extraction.errors
            ), []

        transformation = self.transformer.transform(extraction)

        # Run IRS compliance validation
        compliance_errors = []
        if transformation.status != TransformationStatus.FAILED:
            compliance_validator = IRSComplianceValidator()
            compliance_results = compliance_validator.validate_efile_requirements(
                transformation.transformed_data
            )
            for result in compliance_results:
                if not result.is_valid:
                    compliance_errors.append(
                        f"{result.code}: {result.message}"
                    )

        return transformation, compliance_errors


# Convenience functions for common operations
def extract_from_json(file_path: str) -> ExtractionResult:
    """Extract tax data from JSON file."""
    extractor = DataExtractor()
    return extractor.extract_from_json(file_path)


def extract_from_csv(file_path: str, record_type: str = "w2") -> ExtractionResult:
    """Extract tax data from CSV file."""
    extractor = DataExtractor()
    return extractor.extract_from_csv(file_path, record_type)


def transform_data(extraction_result: ExtractionResult) -> TransformationResult:
    """Transform extracted data to IRS-compliant format."""
    transformer = DataTransformer()
    return transformer.transform(extraction_result)


def validate_tax_return(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate tax return data without loading.

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    pipeline = ETLPipeline()
    result, compliance_errors = pipeline.validate_without_load(data)

    all_errors = result.errors + compliance_errors
    is_valid = (
        result.status == TransformationStatus.SUCCESS and
        len(compliance_errors) == 0
    )

    return is_valid, all_errors
