"""
Form 1040 Parser - Extracts structured data from Form 1040 tax returns.

Uses OCR and pattern matching to extract all relevant fields from
uploaded 1040 PDF/images for smart onboarding.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal
from enum import Enum
import logging

# Import from existing OCR infrastructure
try:
    from services.ocr.field_extractor import (
        FieldTemplate, FieldType, ExtractedField, FieldExtractor
    )
    from services.ocr.ocr_engine import OCRResult
except ImportError:
    # Fallback for when running from different working directories
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    from services.ocr.field_extractor import (
        FieldTemplate, FieldType, ExtractedField, FieldExtractor
    )
    from services.ocr.ocr_engine import OCRResult

logger = logging.getLogger(__name__)


class FilingStatus(str, Enum):
    """IRS Filing Status options."""
    SINGLE = "single"
    MARRIED_FILING_JOINTLY = "married_filing_jointly"
    MARRIED_FILING_SEPARATELY = "married_filing_separately"
    HEAD_OF_HOUSEHOLD = "head_of_household"
    QUALIFYING_SURVIVING_SPOUSE = "qualifying_surviving_spouse"


@dataclass
class DependentInfo:
    """Information about a dependent from 1040."""
    name: str
    ssn: Optional[str] = None
    relationship: Optional[str] = None
    child_tax_credit: bool = False
    other_dependent_credit: bool = False


@dataclass
class Parsed1040Data:
    """
    Structured data extracted from Form 1040.

    Contains all the key information needed for tax advisory analysis.
    """
    # Tax Year
    tax_year: int = 2024

    # Personal Information
    taxpayer_name: Optional[str] = None
    taxpayer_ssn: Optional[str] = None
    spouse_name: Optional[str] = None
    spouse_ssn: Optional[str] = None
    address: Optional[str] = None
    city_state_zip: Optional[str] = None

    # Filing Status
    filing_status: Optional[FilingStatus] = None

    # Dependents
    dependents: List[DependentInfo] = field(default_factory=list)
    total_dependents: int = 0

    # Income (Lines 1-11)
    wages_salaries_tips: Optional[Decimal] = None  # Line 1
    tax_exempt_interest: Optional[Decimal] = None  # Line 2a
    taxable_interest: Optional[Decimal] = None  # Line 2b
    qualified_dividends: Optional[Decimal] = None  # Line 3a
    ordinary_dividends: Optional[Decimal] = None  # Line 3b
    ira_distributions: Optional[Decimal] = None  # Line 4a
    ira_taxable_amount: Optional[Decimal] = None  # Line 4b
    pensions_annuities: Optional[Decimal] = None  # Line 5a
    pensions_taxable: Optional[Decimal] = None  # Line 5b
    social_security: Optional[Decimal] = None  # Line 6a
    social_security_taxable: Optional[Decimal] = None  # Line 6b
    capital_gain_or_loss: Optional[Decimal] = None  # Line 7
    other_income: Optional[Decimal] = None  # Line 8
    total_income: Optional[Decimal] = None  # Line 9

    # Adjustments (Lines 10-11)
    adjustments_to_income: Optional[Decimal] = None  # Line 10
    adjusted_gross_income: Optional[Decimal] = None  # Line 11 (AGI)

    # Deductions (Lines 12-15)
    standard_deduction: Optional[Decimal] = None  # Line 12a
    charitable_if_standard: Optional[Decimal] = None  # Line 12b (COVID provision)
    itemized_deductions: Optional[Decimal] = None  # Line 12 (if itemized)
    qualified_business_deduction: Optional[Decimal] = None  # Line 13
    total_deductions: Optional[Decimal] = None  # Line 14
    taxable_income: Optional[Decimal] = None  # Line 15

    # Tax and Credits (Lines 16-24)
    tax: Optional[Decimal] = None  # Line 16
    schedule_2_line_3: Optional[Decimal] = None  # Line 17 (additional taxes)
    total_tax_before_credits: Optional[Decimal] = None  # Line 18
    child_tax_credit: Optional[Decimal] = None  # Line 19 (from Schedule 8812)
    schedule_3_line_8: Optional[Decimal] = None  # Line 20 (other credits)
    total_credits: Optional[Decimal] = None  # Line 21
    tax_after_credits: Optional[Decimal] = None  # Line 22
    other_taxes: Optional[Decimal] = None  # Line 23 (Schedule 2)
    total_tax: Optional[Decimal] = None  # Line 24

    # Payments (Lines 25-33)
    federal_withholding: Optional[Decimal] = None  # Line 25a
    estimated_tax_payments: Optional[Decimal] = None  # Line 26
    earned_income_credit: Optional[Decimal] = None  # Line 27
    additional_child_tax_credit: Optional[Decimal] = None  # Line 28
    american_opportunity_credit: Optional[Decimal] = None  # Line 29
    other_payments: Optional[Decimal] = None  # Line 31
    total_payments: Optional[Decimal] = None  # Line 33

    # Refund or Amount Owed (Lines 34-37)
    overpaid: Optional[Decimal] = None  # Line 34
    refund_amount: Optional[Decimal] = None  # Line 35a
    amount_owed: Optional[Decimal] = None  # Line 37

    # Metadata
    extraction_confidence: float = 0.0
    fields_extracted: int = 0
    fields_missing: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        def decimal_to_float(val):
            if isinstance(val, Decimal):
                return float(val)
            return val

        return {
            "tax_year": self.tax_year,
            "personal_info": {
                "taxpayer_name": self.taxpayer_name,
                "taxpayer_ssn": self.taxpayer_ssn,
                "spouse_name": self.spouse_name,
                "spouse_ssn": self.spouse_ssn,
                "address": self.address,
                "city_state_zip": self.city_state_zip,
            },
            "filing_status": self.filing_status.value if self.filing_status else None,
            "dependents": {
                "count": self.total_dependents,
                "details": [
                    {
                        "name": d.name,
                        "relationship": d.relationship,
                        "child_tax_credit": d.child_tax_credit,
                        "other_dependent_credit": d.other_dependent_credit,
                    }
                    for d in self.dependents
                ]
            },
            "income": {
                "wages_salaries_tips": decimal_to_float(self.wages_salaries_tips),
                "tax_exempt_interest": decimal_to_float(self.tax_exempt_interest),
                "taxable_interest": decimal_to_float(self.taxable_interest),
                "qualified_dividends": decimal_to_float(self.qualified_dividends),
                "ordinary_dividends": decimal_to_float(self.ordinary_dividends),
                "ira_distributions": decimal_to_float(self.ira_distributions),
                "ira_taxable": decimal_to_float(self.ira_taxable_amount),
                "pensions_annuities": decimal_to_float(self.pensions_annuities),
                "pensions_taxable": decimal_to_float(self.pensions_taxable),
                "social_security": decimal_to_float(self.social_security),
                "social_security_taxable": decimal_to_float(self.social_security_taxable),
                "capital_gain_or_loss": decimal_to_float(self.capital_gain_or_loss),
                "other_income": decimal_to_float(self.other_income),
                "total_income": decimal_to_float(self.total_income),
            },
            "adjustments": {
                "adjustments_to_income": decimal_to_float(self.adjustments_to_income),
                "adjusted_gross_income": decimal_to_float(self.adjusted_gross_income),
            },
            "deductions": {
                "standard_deduction": decimal_to_float(self.standard_deduction),
                "itemized_deductions": decimal_to_float(self.itemized_deductions),
                "qualified_business_deduction": decimal_to_float(self.qualified_business_deduction),
                "total_deductions": decimal_to_float(self.total_deductions),
                "taxable_income": decimal_to_float(self.taxable_income),
            },
            "tax_and_credits": {
                "tax": decimal_to_float(self.tax),
                "child_tax_credit": decimal_to_float(self.child_tax_credit),
                "total_credits": decimal_to_float(self.total_credits),
                "total_tax": decimal_to_float(self.total_tax),
            },
            "payments": {
                "federal_withholding": decimal_to_float(self.federal_withholding),
                "estimated_tax_payments": decimal_to_float(self.estimated_tax_payments),
                "earned_income_credit": decimal_to_float(self.earned_income_credit),
                "additional_child_tax_credit": decimal_to_float(self.additional_child_tax_credit),
                "american_opportunity_credit": decimal_to_float(self.american_opportunity_credit),
                "total_payments": decimal_to_float(self.total_payments),
            },
            "refund_or_owed": {
                "overpaid": decimal_to_float(self.overpaid),
                "refund_amount": decimal_to_float(self.refund_amount),
                "amount_owed": decimal_to_float(self.amount_owed),
            },
            "extraction_metadata": {
                "confidence": self.extraction_confidence,
                "fields_extracted": self.fields_extracted,
                "fields_missing": self.fields_missing,
                "warnings": self.warnings,
            }
        }


def create_1040_templates() -> List[FieldTemplate]:
    """
    Create field templates for Form 1040 extraction.

    Covers all major lines of Form 1040 (2024).
    """
    return [
        # Tax Year
        FieldTemplate(
            field_name="tax_year",
            field_label="Tax Year",
            field_type=FieldType.INTEGER,
            patterns=[
                r'Form\s+1040\s+.*?(\d{4})',
                r'(?:Tax\s+Year|TY|For\s+year)\s*[:.]?\s*(\d{4})',
                r'(?:20\d{2})\s+Form\s+1040',
                r'\b(20\d{2})\b.*?(?:1040|tax\s+return)',
            ],
            irs_reference="Form 1040 Header",
        ),

        # Personal Information
        FieldTemplate(
            field_name="taxpayer_name",
            field_label="Your first name and middle initial / Last name",
            field_type=FieldType.STRING,
            patterns=[
                r'(?:Your\s+)?(?:first\s+)?name.*?last\s+name[:\s]+([A-Za-z\s]+)',
                r'(?:Name|Taxpayer)[:\s]+([A-Z][a-z]+\s+[A-Z][a-z]+)',
                r'^([A-Z][A-Za-z]+\s+[A-Z][A-Za-z]+)\s+\d{3}-\d{2}-\d{4}',
            ],
            required=True,
            irs_reference="Form 1040 Name Line",
        ),
        FieldTemplate(
            field_name="taxpayer_ssn",
            field_label="Your social security number",
            field_type=FieldType.SSN,
            patterns=[
                r'(?:Your\s+)?(?:social\s+security\s+number|SSN)[:\s]*(\d{3}[-\s]?\d{2}[-\s]?\d{4})',
                r'(?:SSN|Social\s+Security)[:\s]*(\d{3}-\d{2}-\d{4})',
            ],
            required=True,
            irs_reference="Form 1040 SSN",
        ),
        FieldTemplate(
            field_name="spouse_name",
            field_label="Spouse's name",
            field_type=FieldType.STRING,
            patterns=[
                r'(?:Spouse[\'s]*\s+)?(?:first\s+)?name.*?last\s+name[:\s]+([A-Za-z\s]+)',
                r'Spouse[:\s]+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            ],
            irs_reference="Form 1040 Spouse Name",
        ),
        FieldTemplate(
            field_name="spouse_ssn",
            field_label="Spouse's SSN",
            field_type=FieldType.SSN,
            patterns=[
                r'(?:Spouse[\'s]*\s+)?(?:social\s+security\s+number|SSN)[:\s]*(\d{3}[-\s]?\d{2}[-\s]?\d{4})',
            ],
            irs_reference="Form 1040 Spouse SSN",
        ),

        # Filing Status (checkboxes - detect which one)
        FieldTemplate(
            field_name="filing_status",
            field_label="Filing Status",
            field_type=FieldType.STRING,
            patterns=[
                r'(?:Filing\s+Status)[:\s]*(Single|Married\s+filing\s+jointly|Married\s+filing\s+separately|Head\s+of\s+household|Qualifying)',
                r'\[X?\]\s*(Single|Married\s+filing\s+jointly|MFJ|Married\s+filing\s+separately|MFS|Head\s+of\s+household|HOH)',
                r'(?:Status)[:\s]*(1|2|3|4|5)\b',
            ],
            required=True,
            irs_reference="Form 1040 Filing Status",
        ),

        # Dependents count
        FieldTemplate(
            field_name="total_dependents",
            field_label="Number of dependents",
            field_type=FieldType.INTEGER,
            patterns=[
                r'(?:Number\s+of\s+)?(?:dependents|children)[:\s]*(\d+)',
                r'(?:Total\s+)?dependents[:\s]*(\d+)',
                r'(?:Dependents\s+who\s+qualify)[:\s]*(\d+)',
            ],
            irs_reference="Form 1040 Dependents",
        ),

        # Line 1: Wages, salaries, tips
        FieldTemplate(
            field_name="wages_salaries_tips",
            field_label="Wages, salaries, tips, etc.",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?1[a-z]?\s+.*?[Ww]ages.*?\$?([\d,]+\.?\d*)',
                r'1[:\.\s]+\$?([\d,]+\.?\d*)\s+(?:wages|salaries)',
                r'[Ww]ages,?\s+salaries,?\s+tips[:\s]*\$?([\d,]+\.?\d*)',
                r'(?:Box\s+1|Line\s+1)[:\s]*\$?([\d,]+\.?\d*)',
            ],
            required=True,
            box_number="1",
            irs_reference="Form 1040 Line 1",
        ),

        # Line 2a: Tax-exempt interest
        FieldTemplate(
            field_name="tax_exempt_interest",
            field_label="Tax-exempt interest",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?2a\s+.*?[Tt]ax-exempt\s+interest[:\s]*\$?([\d,]+\.?\d*)',
                r'2a[:\.\s]+\$?([\d,]+\.?\d*)',
                r'[Tt]ax-exempt\s+interest[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="2a",
            irs_reference="Form 1040 Line 2a",
        ),

        # Line 2b: Taxable interest
        FieldTemplate(
            field_name="taxable_interest",
            field_label="Taxable interest",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?2b\s+.*?[Tt]axable\s+interest[:\s]*\$?([\d,]+\.?\d*)',
                r'2b[:\.\s]+\$?([\d,]+\.?\d*)',
                r'[Tt]axable\s+interest[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="2b",
            irs_reference="Form 1040 Line 2b",
        ),

        # Line 3a: Qualified dividends
        FieldTemplate(
            field_name="qualified_dividends",
            field_label="Qualified dividends",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?3a\s+.*?[Qq]ualified\s+dividends[:\s]*\$?([\d,]+\.?\d*)',
                r'3a[:\.\s]+\$?([\d,]+\.?\d*)',
                r'[Qq]ualified\s+dividends[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="3a",
            irs_reference="Form 1040 Line 3a",
        ),

        # Line 3b: Ordinary dividends
        FieldTemplate(
            field_name="ordinary_dividends",
            field_label="Ordinary dividends",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?3b\s+.*?[Oo]rdinary\s+dividends[:\s]*\$?([\d,]+\.?\d*)',
                r'3b[:\.\s]+\$?([\d,]+\.?\d*)',
                r'[Oo]rdinary\s+dividends[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="3b",
            irs_reference="Form 1040 Line 3b",
        ),

        # Line 4a: IRA distributions
        FieldTemplate(
            field_name="ira_distributions",
            field_label="IRA distributions",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?4a\s+.*?IRA\s+distributions[:\s]*\$?([\d,]+\.?\d*)',
                r'4a[:\.\s]+\$?([\d,]+\.?\d*)',
                r'IRA\s+distributions[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="4a",
            irs_reference="Form 1040 Line 4a",
        ),

        # Line 4b: IRA taxable amount
        FieldTemplate(
            field_name="ira_taxable_amount",
            field_label="IRA taxable amount",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?4b\s+.*?[Tt]axable\s+amount[:\s]*\$?([\d,]+\.?\d*)',
                r'4b[:\.\s]+\$?([\d,]+\.?\d*)',
            ],
            box_number="4b",
            irs_reference="Form 1040 Line 4b",
        ),

        # Line 5a: Pensions and annuities
        FieldTemplate(
            field_name="pensions_annuities",
            field_label="Pensions and annuities",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?5a\s+.*?[Pp]ensions\s+and\s+annuities[:\s]*\$?([\d,]+\.?\d*)',
                r'5a[:\.\s]+\$?([\d,]+\.?\d*)',
                r'[Pp]ensions\s+and\s+annuities[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="5a",
            irs_reference="Form 1040 Line 5a",
        ),

        # Line 5b: Pensions taxable
        FieldTemplate(
            field_name="pensions_taxable",
            field_label="Pensions taxable amount",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?5b\s+.*?[Tt]axable\s+amount[:\s]*\$?([\d,]+\.?\d*)',
                r'5b[:\.\s]+\$?([\d,]+\.?\d*)',
            ],
            box_number="5b",
            irs_reference="Form 1040 Line 5b",
        ),

        # Line 6a: Social Security benefits
        FieldTemplate(
            field_name="social_security",
            field_label="Social Security benefits",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?6a\s+.*?[Ss]ocial\s+[Ss]ecurity[:\s]*\$?([\d,]+\.?\d*)',
                r'6a[:\.\s]+\$?([\d,]+\.?\d*)',
                r'[Ss]ocial\s+[Ss]ecurity\s+benefits[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="6a",
            irs_reference="Form 1040 Line 6a",
        ),

        # Line 6b: Social Security taxable
        FieldTemplate(
            field_name="social_security_taxable",
            field_label="Social Security taxable amount",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?6b\s+.*?[Tt]axable\s+amount[:\s]*\$?([\d,]+\.?\d*)',
                r'6b[:\.\s]+\$?([\d,]+\.?\d*)',
            ],
            box_number="6b",
            irs_reference="Form 1040 Line 6b",
        ),

        # Line 7: Capital gain or loss
        FieldTemplate(
            field_name="capital_gain_or_loss",
            field_label="Capital gain or (loss)",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?7\s+.*?[Cc]apital\s+gain[:\s]*\$?([\d,]+\.?\d*)',
                r'7[:\.\s]+\$?([\d,]+\.?\d*)\s+(?:capital|gain)',
                r'[Cc]apital\s+gain\s+or\s+\(?loss\)?[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="7",
            irs_reference="Form 1040 Line 7",
        ),

        # Line 8: Other income
        FieldTemplate(
            field_name="other_income",
            field_label="Other income",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?8\s+.*?[Oo]ther\s+income[:\s]*\$?([\d,]+\.?\d*)',
                r'8[:\.\s]+\$?([\d,]+\.?\d*)\s+(?:other|Schedule)',
                r'[Oo]ther\s+income\s+from\s+Schedule\s+1[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="8",
            irs_reference="Form 1040 Line 8",
        ),

        # Line 9: Total income
        FieldTemplate(
            field_name="total_income",
            field_label="Total income",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?9\s+.*?[Tt]otal\s+income[:\s]*\$?([\d,]+\.?\d*)',
                r'9[:\.\s]+\$?([\d,]+\.?\d*)\s+(?:total|Add)',
                r'[Tt]otal\s+income[:\s]*\$?([\d,]+\.?\d*)',
            ],
            required=True,
            box_number="9",
            irs_reference="Form 1040 Line 9",
        ),

        # Line 10: Adjustments to income
        FieldTemplate(
            field_name="adjustments_to_income",
            field_label="Adjustments to income",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?10\s+.*?[Aa]djustments[:\s]*\$?([\d,]+\.?\d*)',
                r'10[:\.\s]+\$?([\d,]+\.?\d*)\s+(?:adjustments|Schedule)',
                r'[Aa]djustments\s+to\s+income[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="10",
            irs_reference="Form 1040 Line 10",
        ),

        # Line 11: Adjusted Gross Income (AGI)
        FieldTemplate(
            field_name="adjusted_gross_income",
            field_label="Adjusted gross income",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?11\s+.*?[Aa]djusted\s+[Gg]ross\s+[Ii]ncome[:\s]*\$?([\d,]+\.?\d*)',
                r'11[:\.\s]+\$?([\d,]+\.?\d*)\s+(?:AGI|adjusted)',
                r'[Aa]djusted\s+[Gg]ross\s+[Ii]ncome[:\s]*\$?([\d,]+\.?\d*)',
                r'AGI[:\s]*\$?([\d,]+\.?\d*)',
            ],
            required=True,
            box_number="11",
            irs_reference="Form 1040 Line 11",
        ),

        # Line 12: Standard deduction or itemized
        FieldTemplate(
            field_name="standard_deduction",
            field_label="Standard deduction",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?12[a]?\s+.*?[Ss]tandard\s+[Dd]eduction[:\s]*\$?([\d,]+\.?\d*)',
                r'12[a]?[:\.\s]+\$?([\d,]+\.?\d*)\s+(?:standard|deduction)',
                r'[Ss]tandard\s+[Dd]eduction[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="12",
            irs_reference="Form 1040 Line 12",
        ),
        FieldTemplate(
            field_name="itemized_deductions",
            field_label="Itemized deductions",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?12\s+.*?[Ii]temized\s+[Dd]eductions[:\s]*\$?([\d,]+\.?\d*)',
                r'[Ii]temized\s+[Dd]eductions[:\s]*\$?([\d,]+\.?\d*)',
                r'Schedule\s+A[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="12",
            irs_reference="Form 1040 Line 12 (if itemizing)",
        ),

        # Line 13: Qualified business income deduction
        FieldTemplate(
            field_name="qualified_business_deduction",
            field_label="Qualified business income deduction",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?13\s+.*?[Qq]ualified\s+[Bb]usiness[:\s]*\$?([\d,]+\.?\d*)',
                r'13[:\.\s]+\$?([\d,]+\.?\d*)\s+(?:QBI|qualified)',
                r'QBI\s+[Dd]eduction[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="13",
            irs_reference="Form 1040 Line 13",
        ),

        # Line 14: Total deductions
        FieldTemplate(
            field_name="total_deductions",
            field_label="Total deductions",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?14\s+.*?[Tt]otal\s+[Dd]eductions[:\s]*\$?([\d,]+\.?\d*)',
                r'14[:\.\s]+\$?([\d,]+\.?\d*)',
            ],
            box_number="14",
            irs_reference="Form 1040 Line 14",
        ),

        # Line 15: Taxable income
        FieldTemplate(
            field_name="taxable_income",
            field_label="Taxable income",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?15\s+.*?[Tt]axable\s+[Ii]ncome[:\s]*\$?([\d,]+\.?\d*)',
                r'15[:\.\s]+\$?([\d,]+\.?\d*)\s+(?:taxable|income)',
                r'[Tt]axable\s+[Ii]ncome[:\s]*\$?([\d,]+\.?\d*)',
            ],
            required=True,
            box_number="15",
            irs_reference="Form 1040 Line 15",
        ),

        # Line 16: Tax
        FieldTemplate(
            field_name="tax",
            field_label="Tax",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?16\s+.*?[Tt]ax[:\s]*\$?([\d,]+\.?\d*)',
                r'16[:\.\s]+\$?([\d,]+\.?\d*)',
            ],
            required=True,
            box_number="16",
            irs_reference="Form 1040 Line 16",
        ),

        # Line 19: Child tax credit
        FieldTemplate(
            field_name="child_tax_credit",
            field_label="Child tax credit",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?19\s+.*?[Cc]hild\s+[Tt]ax\s+[Cc]redit[:\s]*\$?([\d,]+\.?\d*)',
                r'19[:\.\s]+\$?([\d,]+\.?\d*)',
                r'[Cc]hild\s+[Tt]ax\s+[Cc]redit[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="19",
            irs_reference="Form 1040 Line 19",
        ),

        # Line 24: Total tax
        FieldTemplate(
            field_name="total_tax",
            field_label="Total tax",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?24\s+.*?[Tt]otal\s+[Tt]ax[:\s]*\$?([\d,]+\.?\d*)',
                r'24[:\.\s]+\$?([\d,]+\.?\d*)\s+(?:total|tax)',
                r'[Tt]otal\s+[Tt]ax[:\s]*\$?([\d,]+\.?\d*)',
            ],
            required=True,
            box_number="24",
            irs_reference="Form 1040 Line 24",
        ),

        # Line 25a: Federal tax withheld (W-2)
        FieldTemplate(
            field_name="federal_withholding",
            field_label="Federal income tax withheld",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?25[a]?\s+.*?[Ff]ederal.*?[Ww]ithheld[:\s]*\$?([\d,]+\.?\d*)',
                r'25[a]?[:\.\s]+\$?([\d,]+\.?\d*)',
                r'[Ff]ederal\s+[Ii]ncome\s+[Tt]ax\s+[Ww]ithheld[:\s]*\$?([\d,]+\.?\d*)',
            ],
            required=True,
            box_number="25a",
            irs_reference="Form 1040 Line 25a",
        ),

        # Line 26: Estimated tax payments
        FieldTemplate(
            field_name="estimated_tax_payments",
            field_label="Estimated tax payments",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?26\s+.*?[Ee]stimated\s+[Tt]ax[:\s]*\$?([\d,]+\.?\d*)',
                r'26[:\.\s]+\$?([\d,]+\.?\d*)',
                r'[Ee]stimated\s+[Tt]ax\s+[Pp]ayments[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="26",
            irs_reference="Form 1040 Line 26",
        ),

        # Line 27: Earned Income Credit (EIC)
        FieldTemplate(
            field_name="earned_income_credit",
            field_label="Earned income credit (EIC)",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?27[a]?\s+.*?[Ee]arned\s+[Ii]ncome\s+[Cc]redit[:\s]*\$?([\d,]+\.?\d*)',
                r'27[a]?[:\.\s]+\$?([\d,]+\.?\d*)',
                r'EIC[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="27",
            irs_reference="Form 1040 Line 27",
        ),

        # Line 28: Additional child tax credit
        FieldTemplate(
            field_name="additional_child_tax_credit",
            field_label="Additional child tax credit",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?28\s+.*?[Aa]dditional\s+[Cc]hild\s+[Tt]ax[:\s]*\$?([\d,]+\.?\d*)',
                r'28[:\.\s]+\$?([\d,]+\.?\d*)',
                r'[Aa]dditional\s+[Cc]hild\s+[Tt]ax\s+[Cc]redit[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="28",
            irs_reference="Form 1040 Line 28",
        ),

        # Line 29: American Opportunity Credit
        FieldTemplate(
            field_name="american_opportunity_credit",
            field_label="American opportunity credit",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?29\s+.*?[Aa]merican\s+[Oo]pportunity[:\s]*\$?([\d,]+\.?\d*)',
                r'29[:\.\s]+\$?([\d,]+\.?\d*)',
                r'AOTC[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="29",
            irs_reference="Form 1040 Line 29",
        ),

        # Line 33: Total payments
        FieldTemplate(
            field_name="total_payments",
            field_label="Total other payments and refundable credits",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?33\s+.*?[Tt]otal.*?[Pp]ayments[:\s]*\$?([\d,]+\.?\d*)',
                r'33[:\.\s]+\$?([\d,]+\.?\d*)',
            ],
            box_number="33",
            irs_reference="Form 1040 Line 33",
        ),

        # Line 34: Overpaid
        FieldTemplate(
            field_name="overpaid",
            field_label="Amount overpaid",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?34\s+.*?[Oo]verpaid[:\s]*\$?([\d,]+\.?\d*)',
                r'34[:\.\s]+\$?([\d,]+\.?\d*)',
                r'[Oo]verpaid[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="34",
            irs_reference="Form 1040 Line 34",
        ),

        # Line 35a: Refund
        FieldTemplate(
            field_name="refund_amount",
            field_label="Refund amount",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?35[a]?\s+.*?[Rr]efund[:\s]*\$?([\d,]+\.?\d*)',
                r'35[a]?[:\.\s]+\$?([\d,]+\.?\d*)',
                r'[Rr]efund[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="35a",
            irs_reference="Form 1040 Line 35a",
        ),

        # Line 37: Amount owed
        FieldTemplate(
            field_name="amount_owed",
            field_label="Amount you owe",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:Line\s+)?37\s+.*?[Aa]mount.*?[Oo]we[:\s]*\$?([\d,]+\.?\d*)',
                r'37[:\.\s]+\$?([\d,]+\.?\d*)',
                r'[Aa]mount\s+[Yy]ou\s+[Oo]we[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="37",
            irs_reference="Form 1040 Line 37",
        ),
    ]


class Form1040Parser:
    """
    Parser for Form 1040 tax returns.

    Uses OCR results and field templates to extract structured
    tax return data for advisory analysis.
    """

    def __init__(self):
        self.extractor = FieldExtractor()
        self.templates = create_1040_templates()

    def parse(self, ocr_result: OCRResult) -> Parsed1040Data:
        """
        Parse OCR result into structured 1040 data.

        Args:
            ocr_result: OCR processing result

        Returns:
            Parsed1040Data with extracted fields
        """
        # Extract fields using templates
        extracted_fields = self.extractor.extract(ocr_result, self.templates)

        # Build parsed data object
        parsed = Parsed1040Data()
        parsed.extraction_confidence = ocr_result.confidence

        # Map extracted fields to parsed data
        field_map = {f.field_name: f for f in extracted_fields}

        # Personal info
        self._map_field(parsed, field_map, "taxpayer_name", "taxpayer_name")
        self._map_field(parsed, field_map, "taxpayer_ssn", "taxpayer_ssn")
        self._map_field(parsed, field_map, "spouse_name", "spouse_name")
        self._map_field(parsed, field_map, "spouse_ssn", "spouse_ssn")

        # Tax year
        if "tax_year" in field_map and field_map["tax_year"].normalized_value:
            parsed.tax_year = int(field_map["tax_year"].normalized_value)

        # Filing status
        self._parse_filing_status(parsed, field_map)

        # Dependents
        if "total_dependents" in field_map and field_map["total_dependents"].normalized_value:
            parsed.total_dependents = int(field_map["total_dependents"].normalized_value)

        # Income fields
        self._map_field(parsed, field_map, "wages_salaries_tips", "wages_salaries_tips")
        self._map_field(parsed, field_map, "tax_exempt_interest", "tax_exempt_interest")
        self._map_field(parsed, field_map, "taxable_interest", "taxable_interest")
        self._map_field(parsed, field_map, "qualified_dividends", "qualified_dividends")
        self._map_field(parsed, field_map, "ordinary_dividends", "ordinary_dividends")
        self._map_field(parsed, field_map, "ira_distributions", "ira_distributions")
        self._map_field(parsed, field_map, "ira_taxable_amount", "ira_taxable_amount")
        self._map_field(parsed, field_map, "pensions_annuities", "pensions_annuities")
        self._map_field(parsed, field_map, "pensions_taxable", "pensions_taxable")
        self._map_field(parsed, field_map, "social_security", "social_security")
        self._map_field(parsed, field_map, "social_security_taxable", "social_security_taxable")
        self._map_field(parsed, field_map, "capital_gain_or_loss", "capital_gain_or_loss")
        self._map_field(parsed, field_map, "other_income", "other_income")
        self._map_field(parsed, field_map, "total_income", "total_income")

        # Adjustments
        self._map_field(parsed, field_map, "adjustments_to_income", "adjustments_to_income")
        self._map_field(parsed, field_map, "adjusted_gross_income", "adjusted_gross_income")

        # Deductions
        self._map_field(parsed, field_map, "standard_deduction", "standard_deduction")
        self._map_field(parsed, field_map, "itemized_deductions", "itemized_deductions")
        self._map_field(parsed, field_map, "qualified_business_deduction", "qualified_business_deduction")
        self._map_field(parsed, field_map, "total_deductions", "total_deductions")
        self._map_field(parsed, field_map, "taxable_income", "taxable_income")

        # Tax and credits
        self._map_field(parsed, field_map, "tax", "tax")
        self._map_field(parsed, field_map, "child_tax_credit", "child_tax_credit")
        self._map_field(parsed, field_map, "total_tax", "total_tax")

        # Payments
        self._map_field(parsed, field_map, "federal_withholding", "federal_withholding")
        self._map_field(parsed, field_map, "estimated_tax_payments", "estimated_tax_payments")
        self._map_field(parsed, field_map, "earned_income_credit", "earned_income_credit")
        self._map_field(parsed, field_map, "additional_child_tax_credit", "additional_child_tax_credit")
        self._map_field(parsed, field_map, "american_opportunity_credit", "american_opportunity_credit")
        self._map_field(parsed, field_map, "total_payments", "total_payments")

        # Refund/owed
        self._map_field(parsed, field_map, "overpaid", "overpaid")
        self._map_field(parsed, field_map, "refund_amount", "refund_amount")
        self._map_field(parsed, field_map, "amount_owed", "amount_owed")

        # Count extracted vs missing
        parsed.fields_extracted = len([f for f in extracted_fields if f.normalized_value is not None])

        # Track missing required fields
        required_fields = ["taxpayer_name", "wages_salaries_tips", "total_income",
                         "adjusted_gross_income", "taxable_income", "tax",
                         "total_tax", "federal_withholding"]
        for req in required_fields:
            if req not in field_map or field_map[req].normalized_value is None:
                parsed.fields_missing.append(req)

        # Add warnings for validation issues
        for f in extracted_fields:
            if not f.is_valid and f.validation_errors:
                parsed.warnings.extend([f"{f.field_name}: {e}" for e in f.validation_errors])

        return parsed

    def _map_field(
        self,
        parsed: Parsed1040Data,
        field_map: Dict[str, ExtractedField],
        source_field: str,
        target_attr: str
    ) -> None:
        """Map an extracted field to the parsed data object."""
        if source_field in field_map and field_map[source_field].normalized_value is not None:
            setattr(parsed, target_attr, field_map[source_field].normalized_value)

    def _parse_filing_status(
        self,
        parsed: Parsed1040Data,
        field_map: Dict[str, ExtractedField]
    ) -> None:
        """Parse and normalize filing status."""
        if "filing_status" not in field_map:
            return

        raw_status = str(field_map["filing_status"].normalized_value or "").lower()

        if "jointly" in raw_status or raw_status in ["2", "mfj"]:
            parsed.filing_status = FilingStatus.MARRIED_FILING_JOINTLY
        elif "separately" in raw_status or raw_status in ["3", "mfs"]:
            parsed.filing_status = FilingStatus.MARRIED_FILING_SEPARATELY
        elif "head" in raw_status or raw_status in ["4", "hoh"]:
            parsed.filing_status = FilingStatus.HEAD_OF_HOUSEHOLD
        elif "qualifying" in raw_status or "surviving" in raw_status or raw_status == "5":
            parsed.filing_status = FilingStatus.QUALIFYING_SURVIVING_SPOUSE
        elif "single" in raw_status or raw_status == "1":
            parsed.filing_status = FilingStatus.SINGLE

    def parse_from_text(self, raw_text: str, confidence: float = 75.0) -> Parsed1040Data:
        """
        Parse directly from raw text (convenience method for testing).

        Args:
            raw_text: Raw OCR text
            confidence: Confidence score to assign

        Returns:
            Parsed1040Data
        """
        # Create a mock OCR result
        mock_result = OCRResult(
            raw_text=raw_text,
            blocks=[],
            confidence=confidence,
            page_count=1,
            metadata={}
        )
        return self.parse(mock_result)


# Add to template registry
def register_1040_templates():
    """Register 1040 templates with the document processor."""
    from services.ocr.field_extractor import DOCUMENT_TEMPLATES
    DOCUMENT_TEMPLATES["1040"] = create_1040_templates
    DOCUMENT_TEMPLATES["form-1040"] = create_1040_templates
