"""
Document-to-Form Mapping Service

Maps extracted document data (from OCR) to tax form models.
This service bridges the gap between document extraction and tax calculations.

Usage:
    from services.document_form_mapper import DocumentFormMapper

    mapper = DocumentFormMapper()
    mapper.apply_to_session(session_id, document_type, extracted_data)
"""

import logging
from typing import Dict, Any, Optional, List
from decimal import Decimal

logger = logging.getLogger(__name__)


class DocumentFormMapper:
    """
    Maps extracted document data to TaxReturn model fields.

    Supported document types:
    - W-2: Wage and Tax Statement
    - 1099-INT: Interest Income
    - 1099-DIV: Dividends
    - 1099-NEC: Non-Employee Compensation
    - 1099-MISC: Miscellaneous Income
    - 1099-G: Government Payments
    - 1099-R: Retirement Distributions
    """

    # Field mappings: extracted_field -> model_field
    W2_FIELD_MAPPINGS = {
        # Direct mappings
        'employer_name': 'employer_name',
        'employer_ein': 'employer_ein',

        # Box 1: Wages
        'w2_wages': 'wages',
        'wages': 'wages',
        'box_1_wages': 'wages',
        'total_wages': 'wages',

        # Box 2: Federal withholding
        'federal_withheld': 'federal_tax_withheld',
        'federal_tax_withheld': 'federal_tax_withheld',
        'box_2_federal_withheld': 'federal_tax_withheld',

        # Box 3: Social Security wages
        'box_3_social_security_wages': 'social_security_wages',
        'social_security_wages': 'social_security_wages',

        # Box 4: Social Security tax
        'box_4_social_security_withheld': 'social_security_tax_withheld',
        'social_security_tax_withheld': 'social_security_tax_withheld',

        # Box 5: Medicare wages
        'box_5_medicare_wages': 'medicare_wages',
        'medicare_wages': 'medicare_wages',

        # Box 6: Medicare tax
        'box_6_medicare_withheld': 'medicare_tax_withheld',
        'medicare_tax_withheld': 'medicare_tax_withheld',

        # State wages/tax
        'state_wages': 'state_wages',
        'state_withheld': 'state_tax_withheld',
        'state_tax_withheld': 'state_tax_withheld',
    }

    FORM_1099_INT_MAPPINGS = {
        'payer_name': 'payer_name',
        'interest_income': 'amount',
        '1099_interest': 'amount',
        'interest': 'amount',
    }

    FORM_1099_DIV_MAPPINGS = {
        'payer_name': 'payer_name',
        'dividend_income': 'amount',
        '1099_dividends': 'amount',
        'dividends': 'amount',
        'qualified_dividends': 'qualified_dividends',
    }

    FORM_1099_NEC_MAPPINGS = {
        'payer_name': 'payer_name',
        '1099_nec': 'amount',
        'nonemployee_compensation': 'amount',
        'self_employment_income': 'amount',
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def apply_to_session(
        self,
        session_id: str,
        document_type: str,
        extracted_data: Dict[str, Any],
        persistence=None
    ) -> Dict[str, Any]:
        """
        Apply extracted document data to a session's tax return.

        Args:
            session_id: The session ID
            document_type: Type of document (w2, 1099-int, etc.)
            extracted_data: Dictionary of extracted fields
            persistence: Optional SessionPersistence instance

        Returns:
            Dictionary with applied fields and any warnings
        """
        if not persistence:
            from database.session_persistence import SessionPersistence
            persistence = SessionPersistence()

        # Load session
        session = persistence.load_unified_session(session_id)
        if not session:
            return {
                'success': False,
                'error': 'Session not found',
                'applied_fields': []
            }

        # Get or create tax return
        tax_return = self._get_or_create_tax_return(session)

        # Map fields based on document type
        doc_type_lower = document_type.lower().replace('-', '_').replace(' ', '_')
        applied_fields = []
        warnings = []

        if doc_type_lower in ('w2', 'w_2', 'wage_and_tax_statement'):
            result = self._apply_w2_data(tax_return, extracted_data)
            applied_fields = result.get('applied', [])
            warnings = result.get('warnings', [])

        elif doc_type_lower in ('1099_int', '1099int', 'interest'):
            result = self._apply_1099_int_data(tax_return, extracted_data)
            applied_fields = result.get('applied', [])
            warnings = result.get('warnings', [])

        elif doc_type_lower in ('1099_div', '1099div', 'dividends'):
            result = self._apply_1099_div_data(tax_return, extracted_data)
            applied_fields = result.get('applied', [])
            warnings = result.get('warnings', [])

        elif doc_type_lower in ('1099_nec', '1099nec', 'nonemployee'):
            result = self._apply_1099_nec_data(tax_return, extracted_data)
            applied_fields = result.get('applied', [])
            warnings = result.get('warnings', [])

        else:
            # Generic handling for unknown document types
            self.logger.warning(f"Unknown document type: {document_type}")
            warnings.append(f"Document type '{document_type}' not fully supported - data stored but not mapped to forms")

        # Update session with modified tax return
        if hasattr(session, 'tax_return'):
            session.tax_return = tax_return
        elif isinstance(session, dict):
            session['tax_return'] = tax_return.model_dump() if hasattr(tax_return, 'model_dump') else tax_return

        # Save session
        try:
            persistence.save_unified_session(session)
            self.logger.info(f"Applied {len(applied_fields)} fields from {document_type} to session {session_id}")
        except Exception as e:
            self.logger.error(f"Failed to save session after applying document data: {e}")
            return {
                'success': False,
                'error': str(e),
                'applied_fields': applied_fields
            }

        return {
            'success': True,
            'applied_fields': applied_fields,
            'warnings': warnings,
            'document_type': document_type
        }

    def _get_or_create_tax_return(self, session):
        """Get existing tax return or create a new one."""
        from models.tax_return import TaxReturn
        from models.taxpayer import TaxpayerInfo, FilingStatus
        from models.income import Income
        from models.deductions import Deductions
        from models.credits import TaxCredits

        # Try to get existing tax return
        tax_return = None

        if hasattr(session, 'tax_return') and session.tax_return:
            tax_return = session.tax_return
        elif isinstance(session, dict) and session.get('tax_return'):
            tr_data = session['tax_return']
            if isinstance(tr_data, dict):
                try:
                    tax_return = TaxReturn(**tr_data)
                except Exception as e:
                    self.logger.warning(f"Could not parse existing tax return: {e}")

        # Create new if needed
        if not tax_return:
            tax_return = TaxReturn(
                taxpayer=TaxpayerInfo(
                    first_name="",
                    last_name="",
                    filing_status=FilingStatus.SINGLE
                ),
                income=Income(),
                deductions=Deductions(),
                credits=TaxCredits()
            )

        return tax_return

    def _apply_w2_data(self, tax_return, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply W-2 data to tax return income."""
        from models.income_legacy import W2Info

        applied = []
        warnings = []

        # Build W2Info from extracted data
        w2_data = {
            'employer_name': 'Unknown Employer',  # Default
            'wages': 0.0,
            'federal_tax_withheld': 0.0,
        }

        # Map extracted fields to W2 fields
        for extracted_field, value in extracted_data.items():
            if extracted_field in self.W2_FIELD_MAPPINGS:
                model_field = self.W2_FIELD_MAPPINGS[extracted_field]
                parsed_value = self._parse_value(value, model_field)

                if parsed_value is not None:
                    w2_data[model_field] = parsed_value
                    applied.append({
                        'source_field': extracted_field,
                        'target_field': f'W2.{model_field}',
                        'value': parsed_value
                    })

        # Validate minimum required fields
        if w2_data.get('wages', 0) <= 0:
            warnings.append("W-2 wages not found or zero - please verify")

        # Create W2Info and add to income
        try:
            w2_info = W2Info(**w2_data)

            # Add to income's w2_forms list
            if hasattr(tax_return.income, 'w2_forms'):
                # Check for duplicate (same employer, same wages)
                is_duplicate = any(
                    w2.employer_name == w2_info.employer_name and
                    abs(w2.wages - w2_info.wages) < 0.01
                    for w2 in tax_return.income.w2_forms
                )

                if not is_duplicate:
                    tax_return.income.w2_forms.append(w2_info)
                    self.logger.info(f"Added W-2 from {w2_info.employer_name} with wages ${w2_info.wages:,.2f}")
                else:
                    warnings.append(f"Duplicate W-2 detected for {w2_info.employer_name} - skipped")

        except Exception as e:
            self.logger.error(f"Failed to create W2Info: {e}")
            warnings.append(f"Could not process W-2 data: {str(e)}")

        return {'applied': applied, 'warnings': warnings}

    def _apply_1099_int_data(self, tax_return, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply 1099-INT data to tax return."""
        applied = []
        warnings = []

        # Get interest amount
        interest = 0.0
        for field in ['interest_income', '1099_interest', 'interest', 'amount']:
            if field in extracted_data:
                interest = self._parse_value(extracted_data[field], 'amount') or 0.0
                if interest > 0:
                    break

        if interest > 0:
            # Add to interest income
            if hasattr(tax_return.income, 'interest_income'):
                tax_return.income.interest_income += interest
                applied.append({
                    'source_field': 'interest_income',
                    'target_field': 'Income.interest_income',
                    'value': interest
                })
            else:
                warnings.append("Could not add interest income to return")
        else:
            warnings.append("No interest amount found in 1099-INT")

        return {'applied': applied, 'warnings': warnings}

    def _apply_1099_div_data(self, tax_return, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply 1099-DIV data to tax return."""
        applied = []
        warnings = []

        # Get dividend amount
        dividends = 0.0
        for field in ['dividend_income', '1099_dividends', 'dividends', 'amount']:
            if field in extracted_data:
                dividends = self._parse_value(extracted_data[field], 'amount') or 0.0
                if dividends > 0:
                    break

        if dividends > 0:
            if hasattr(tax_return.income, 'dividend_income'):
                tax_return.income.dividend_income += dividends
                applied.append({
                    'source_field': 'dividend_income',
                    'target_field': 'Income.dividend_income',
                    'value': dividends
                })
        else:
            warnings.append("No dividend amount found in 1099-DIV")

        return {'applied': applied, 'warnings': warnings}

    def _apply_1099_nec_data(self, tax_return, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply 1099-NEC data to tax return (self-employment income)."""
        applied = []
        warnings = []

        # Get non-employee compensation
        nec_income = 0.0
        for field in ['1099_nec', 'nonemployee_compensation', 'self_employment_income', 'amount']:
            if field in extracted_data:
                nec_income = self._parse_value(extracted_data[field], 'amount') or 0.0
                if nec_income > 0:
                    break

        if nec_income > 0:
            if hasattr(tax_return.income, 'self_employment_income'):
                tax_return.income.self_employment_income += nec_income
                applied.append({
                    'source_field': '1099_nec',
                    'target_field': 'Income.self_employment_income',
                    'value': nec_income
                })
        else:
            warnings.append("No compensation amount found in 1099-NEC")

        return {'applied': applied, 'warnings': warnings}

    def _parse_value(self, value: Any, field_type: str) -> Any:
        """Parse and validate extracted value."""
        if value is None:
            return None

        # Handle string values
        if isinstance(value, str):
            value = value.strip()

            # Empty string
            if not value:
                return None

            # Numeric fields - remove currency formatting
            if field_type in ('wages', 'federal_tax_withheld', 'amount', 'state_wages',
                             'state_tax_withheld', 'social_security_wages', 'medicare_wages',
                             'social_security_tax_withheld', 'medicare_tax_withheld'):
                # Remove $, commas, and other formatting
                cleaned = value.replace('$', '').replace(',', '').replace(' ', '')
                try:
                    return float(cleaned)
                except ValueError:
                    self.logger.warning(f"Could not parse numeric value: {value}")
                    return None

            # String fields
            return value

        # Already numeric
        if isinstance(value, (int, float, Decimal)):
            return float(value)

        return value


# Convenience function for use in other modules
def apply_document_to_tax_return(
    session_id: str,
    document_type: str,
    extracted_data: Dict[str, Any],
    persistence=None
) -> Dict[str, Any]:
    """
    Apply extracted document data to a session's tax return.

    This is the main entry point for document-to-form mapping.

    Args:
        session_id: The session ID
        document_type: Type of document (w2, 1099-int, etc.)
        extracted_data: Dictionary of extracted fields
        persistence: Optional SessionPersistence instance

    Returns:
        Dictionary with success status, applied fields, and warnings
    """
    mapper = DocumentFormMapper()
    return mapper.apply_to_session(session_id, document_type, extracted_data, persistence)
