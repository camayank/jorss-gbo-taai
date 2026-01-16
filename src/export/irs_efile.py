"""IRS E-File XML Generation.

Generates IRS Modernized e-File (MeF) compliant XML for electronic
filing of federal tax returns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from datetime import datetime
import xml.etree.ElementTree as ET
import hashlib
import uuid

if TYPE_CHECKING:
    from models.tax_return import TaxReturn


@dataclass
class EFileValidationResult:
    """Result of e-file validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    rejection_codes: List[str] = field(default_factory=list)


@dataclass
class EFileSubmission:
    """E-file submission package."""
    submission_id: str
    timestamp: str
    xml_content: str
    schema_version: str
    tax_year: int
    return_type: str  # 1040, 1040-SR, etc.
    filing_status: str
    taxpayer_ssn_masked: str
    validation_result: EFileValidationResult
    signature_info: Dict[str, Any] = field(default_factory=dict)


class IRSEFileGenerator:
    """
    Generates IRS MeF-compliant XML for e-filing.

    Creates XML documents that conform to IRS Modernized e-File (MeF)
    specifications for individual tax returns (Form 1040).
    """

    # IRS MeF namespaces
    NAMESPACES = {
        "efile": "http://www.irs.gov/efile",
        "common": "http://www.irs.gov/efile/common",
        "irs1040": "http://www.irs.gov/efile/irs1040",
    }

    # Schema versions
    SCHEMA_VERSION = "2025v1.0"

    # Filing status codes per IRS
    FILING_STATUS_CODES = {
        "single": "1",
        "married_joint": "2",
        "married_separate": "3",
        "head_of_household": "4",
        "qualifying_widow": "5",
    }

    def __init__(self):
        """Initialize the e-file generator."""
        self._submission_counter = 0

    def generate_submission(
        self, tax_return: "TaxReturn", include_signature: bool = True
    ) -> EFileSubmission:
        """
        Generate complete e-file submission package.

        Args:
            tax_return: The tax return to submit
            include_signature: Whether to include electronic signature

        Returns:
            EFileSubmission ready for transmission
        """
        # Generate submission ID
        submission_id = self._generate_submission_id()

        # Validate before generating
        validation = self.validate(tax_return)

        # Generate the XML
        xml_content = self._generate_return_xml(tax_return)

        # Get taxpayer info
        taxpayer = tax_return.taxpayer
        filing_status = taxpayer.filing_status.value if hasattr(taxpayer.filing_status, 'value') else str(taxpayer.filing_status)

        # Signature info
        signature_info = {}
        if include_signature:
            signature_info = self._generate_signature_info(tax_return)

        return EFileSubmission(
            submission_id=submission_id,
            timestamp=datetime.now().isoformat(),
            xml_content=xml_content,
            schema_version=self.SCHEMA_VERSION,
            tax_year=2025,
            return_type="1040",
            filing_status=filing_status,
            taxpayer_ssn_masked=self._mask_ssn(getattr(taxpayer, 'ssn', '')),
            validation_result=validation,
            signature_info=signature_info,
        )

    def validate(self, tax_return: "TaxReturn") -> EFileValidationResult:
        """
        Validate tax return for e-file compliance.

        Args:
            tax_return: The tax return to validate

        Returns:
            EFileValidationResult with any issues found
        """
        errors = []
        warnings = []
        rejection_codes = []

        taxpayer = tax_return.taxpayer
        income = tax_return.income

        # Required fields validation
        if not getattr(taxpayer, 'ssn', None):
            errors.append("Taxpayer SSN is required")
            rejection_codes.append("R0000-001-01")

        if not getattr(taxpayer, 'first_name', None):
            errors.append("Taxpayer first name is required")
            rejection_codes.append("R0000-002-01")

        if not getattr(taxpayer, 'last_name', None):
            errors.append("Taxpayer last name is required")
            rejection_codes.append("R0000-003-01")

        # SSN format validation
        ssn = getattr(taxpayer, 'ssn', '') or ''
        if ssn and not self._validate_ssn_format(ssn):
            errors.append("Invalid SSN format")
            rejection_codes.append("R0000-004-01")

        # AGI validation
        agi = tax_return.adjusted_gross_income
        if agi is None:
            errors.append("Adjusted Gross Income must be calculated")
            rejection_codes.append("R0000-010-01")

        # Withholding validation
        withholding = getattr(income, 'federal_withholding', 0) or 0
        if withholding < 0:
            errors.append("Federal withholding cannot be negative")
            rejection_codes.append("R0000-020-01")

        # Tax liability validation
        tax = tax_return.tax_liability
        if tax is not None and tax < 0:
            errors.append("Tax liability cannot be negative")
            rejection_codes.append("R0000-030-01")

        # Filing status validation
        filing_status = taxpayer.filing_status.value if hasattr(taxpayer.filing_status, 'value') else str(taxpayer.filing_status)
        if filing_status not in self.FILING_STATUS_CODES:
            errors.append(f"Invalid filing status: {filing_status}")
            rejection_codes.append("R0000-040-01")

        # Warnings (not blocking)
        if agi and agi > 500000:
            warnings.append("High income return - may receive additional scrutiny")

        refund = tax_return.refund_or_owed
        if refund and refund > 10000:
            warnings.append("Large refund - ensure all income is reported")

        return EFileValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            rejection_codes=rejection_codes,
        )

    def _generate_return_xml(self, tax_return: "TaxReturn") -> str:
        """Generate the complete return XML."""
        # Create root element
        root = ET.Element("Return")
        root.set("xmlns", self.NAMESPACES["efile"])
        root.set("returnVersion", self.SCHEMA_VERSION)

        # Return header
        header = ET.SubElement(root, "ReturnHeader")
        self._add_return_header(header, tax_return)

        # Return data
        return_data = ET.SubElement(root, "ReturnData")
        return_data.set("documentCnt", "1")

        # IRS1040
        irs1040 = ET.SubElement(return_data, "IRS1040")
        self._add_irs1040(irs1040, tax_return)

        # Schedule 1 (if needed)
        if self._needs_schedule_1(tax_return):
            sched1 = ET.SubElement(return_data, "IRS1040Schedule1")
            self._add_schedule_1(sched1, tax_return)

        # Schedule 2 (if needed)
        if self._needs_schedule_2(tax_return):
            sched2 = ET.SubElement(return_data, "IRS1040Schedule2")
            self._add_schedule_2(sched2, tax_return)

        # Schedule 3 (if needed)
        if self._needs_schedule_3(tax_return):
            sched3 = ET.SubElement(return_data, "IRS1040Schedule3")
            self._add_schedule_3(sched3, tax_return)

        # Schedule A (if itemizing)
        if self._is_itemizing(tax_return):
            scheda = ET.SubElement(return_data, "IRS1040ScheduleA")
            self._add_schedule_a(scheda, tax_return)

        # Schedule C (if self-employment)
        if self._has_self_employment(tax_return):
            schedc = ET.SubElement(return_data, "IRS1040ScheduleC")
            self._add_schedule_c(schedc, tax_return)

        # Schedule SE (if self-employment)
        if self._has_self_employment(tax_return):
            schedse = ET.SubElement(return_data, "IRS1040ScheduleSE")
            self._add_schedule_se(schedse, tax_return)

        # Convert to string
        return ET.tostring(root, encoding="unicode", method="xml")

    def _add_return_header(self, header: ET.Element, tax_return: "TaxReturn") -> None:
        """Add return header elements."""
        # Return timestamp
        timestamp = ET.SubElement(header, "ReturnTs")
        timestamp.text = datetime.now().isoformat()

        # Tax year
        tax_year = ET.SubElement(header, "TaxYr")
        tax_year.text = "2025"

        # Tax period begin/end
        period_begin = ET.SubElement(header, "TaxPeriodBeginDt")
        period_begin.text = "2025-01-01"
        period_end = ET.SubElement(header, "TaxPeriodEndDt")
        period_end.text = "2025-12-31"

        # Return type
        return_type = ET.SubElement(header, "ReturnTypeCd")
        return_type.text = "1040"

        # Filer
        filer = ET.SubElement(header, "Filer")
        self._add_filer_info(filer, tax_return)

        # Preparer (software)
        preparer = ET.SubElement(header, "PaidPreparerInformationGrp")
        self._add_preparer_info(preparer)

        # IP address (placeholder)
        ip = ET.SubElement(header, "IPAddress")
        ip.set("IPTypeCd", "IPv4")
        ip.text = "0.0.0.0"  # Would be actual IP in production

    def _add_filer_info(self, filer: ET.Element, tax_return: "TaxReturn") -> None:
        """Add filer information."""
        taxpayer = tax_return.taxpayer

        # Primary
        primary = ET.SubElement(filer, "PrimarySSN")
        primary.text = (getattr(taxpayer, 'ssn', '') or '').replace("-", "")

        name_grp = ET.SubElement(filer, "NameLine1Txt")
        name_grp.text = f"{getattr(taxpayer, 'first_name', '')} {getattr(taxpayer, 'last_name', '')}"

        # Address
        addr = ET.SubElement(filer, "USAddress")
        addr_line = ET.SubElement(addr, "AddressLine1Txt")
        addr_line.text = getattr(taxpayer, 'address', '') or "123 Main St"
        city = ET.SubElement(addr, "CityNm")
        city.text = getattr(taxpayer, 'city', '') or "Anytown"
        state = ET.SubElement(addr, "StateAbbreviationCd")
        state.text = getattr(taxpayer, 'state', '') or "CA"
        zip_code = ET.SubElement(addr, "ZIPCd")
        zip_code.text = getattr(taxpayer, 'zip_code', '') or "00000"

    def _add_preparer_info(self, preparer: ET.Element) -> None:
        """Add software preparer info."""
        soft_id = ET.SubElement(preparer, "SoftwareId")
        soft_id.text = "GORSS-GBO-2025"

        soft_ver = ET.SubElement(preparer, "SoftwareVersionNum")
        soft_ver.text = "1.0.0"

    def _add_irs1040(self, irs1040: ET.Element, tax_return: "TaxReturn") -> None:
        """Add main 1040 form data."""
        taxpayer = tax_return.taxpayer
        income = tax_return.income
        deductions = tax_return.deductions

        # Filing status
        filing_status = taxpayer.filing_status.value if hasattr(taxpayer.filing_status, 'value') else str(taxpayer.filing_status)
        status_elem = ET.SubElement(irs1040, "IndividualReturnFilingStatusCd")
        status_elem.text = self.FILING_STATUS_CODES.get(filing_status, "1")

        # Exemptions/Dependents
        dependents = taxpayer.dependents if hasattr(taxpayer, 'dependents') else []
        if dependents:
            dep_grp = ET.SubElement(irs1040, "DependentDetailGrp")
            for dep in dependents:
                dep_elem = ET.SubElement(dep_grp, "DependentDetail")
                name = ET.SubElement(dep_elem, "DependentNameControlTxt")
                name.text = (getattr(dep, 'last_name', '') or 'DEPENDENT')[:4].upper()

        # Line 1: W-2 wages
        w2_wages = income.get_total_wages() if hasattr(income, 'get_total_wages') else 0
        if w2_wages > 0:
            wages = ET.SubElement(irs1040, "WagesSalariesAndTipsAmt")
            wages.text = str(int(w2_wages))

        # Line 2: Interest
        interest = getattr(income, 'interest_income', 0) or 0
        if interest > 0:
            int_elem = ET.SubElement(irs1040, "TaxableInterestAmt")
            int_elem.text = str(int(interest))

        # Line 3: Dividends
        dividends = getattr(income, 'dividend_income', 0) or 0
        if dividends > 0:
            div_elem = ET.SubElement(irs1040, "OrdinaryDividendsAmt")
            div_elem.text = str(int(dividends))

        # Line 7: Capital gain/loss
        cap_gain = getattr(income, 'capital_gain_income', 0) or 0
        if cap_gain != 0:
            cap_elem = ET.SubElement(irs1040, "CapitalGainLossAmt")
            cap_elem.text = str(int(cap_gain))

        # Line 9: Total income
        total_income = ET.SubElement(irs1040, "TotalIncomeAmt")
        total_income.text = str(int(tax_return.adjusted_gross_income or 0))

        # Line 11: AGI
        agi_elem = ET.SubElement(irs1040, "AdjustedGrossIncomeAmt")
        agi_elem.text = str(int(tax_return.adjusted_gross_income or 0))

        # Line 12: Standard/Itemized deduction
        deduction_elem = ET.SubElement(irs1040, "TotalItemizedOrStandardDedAmt")
        deduction_amt = tax_return.total_deduction if hasattr(tax_return, 'total_deduction') else 15750
        deduction_elem.text = str(int(deduction_amt))

        # Line 15: Taxable income
        taxable_elem = ET.SubElement(irs1040, "TaxableIncomeAmt")
        taxable_elem.text = str(int(tax_return.taxable_income or 0))

        # Line 16: Tax
        tax_elem = ET.SubElement(irs1040, "TaxAmt")
        tax_elem.text = str(int(tax_return.tax_liability or 0))

        # Line 25: Withholding
        withholding = getattr(income, 'federal_withholding', 0) or 0
        if withholding > 0:
            wh_elem = ET.SubElement(irs1040, "WithholdingTaxAmt")
            wh_elem.text = str(int(withholding))

        # Line 34/37: Refund or amount owed
        result = tax_return.refund_or_owed or 0
        if result > 0:
            refund_elem = ET.SubElement(irs1040, "OverpaidAmt")
            refund_elem.text = str(int(result))
            refund_amount = ET.SubElement(irs1040, "RefundAmt")
            refund_amount.text = str(int(result))
        elif result < 0:
            owed_elem = ET.SubElement(irs1040, "OwedAmt")
            owed_elem.text = str(int(abs(result)))

    def _add_schedule_1(self, sched1: ET.Element, tax_return: "TaxReturn") -> None:
        """Add Schedule 1 (Additional Income and Adjustments)."""
        income = tax_return.income

        # Part I: Additional Income
        # Line 3: Business income
        se_income = getattr(income, 'self_employment_income', 0) or 0
        se_expenses = getattr(income, 'self_employment_expenses', 0) or 0
        net_se = max(0, se_income - se_expenses)
        if net_se > 0:
            bus_elem = ET.SubElement(sched1, "BusinessIncomeLossAmt")
            bus_elem.text = str(int(net_se))

        # Part II: Adjustments
        # Line 15: Self-employment tax deduction (half of SE tax)
        if net_se > 0:
            se_tax = net_se * 0.9235 * 0.153
            se_ded = ET.SubElement(sched1, "OneHalfSelfEmploymentTaxAmt")
            se_ded.text = str(int(se_tax / 2))

        # Line 21: Student loan interest
        sl_interest = getattr(income, 'student_loan_interest', 0) or 0
        if sl_interest > 0:
            sl_elem = ET.SubElement(sched1, "StudentLoanInterestDedAmt")
            sl_elem.text = str(int(min(sl_interest, 2500)))

    def _add_schedule_2(self, sched2: ET.Element, tax_return: "TaxReturn") -> None:
        """Add Schedule 2 (Additional Taxes)."""
        income = tax_return.income

        # Self-employment tax
        se_income = getattr(income, 'self_employment_income', 0) or 0
        se_expenses = getattr(income, 'self_employment_expenses', 0) or 0
        net_se = max(0, se_income - se_expenses)

        if net_se > 0:
            se_tax = net_se * 0.9235 * 0.153
            se_elem = ET.SubElement(sched2, "SelfEmploymentTaxAmt")
            se_elem.text = str(int(se_tax))

    def _add_schedule_3(self, sched3: ET.Element, tax_return: "TaxReturn") -> None:
        """Add Schedule 3 (Additional Credits and Payments)."""
        credits = tax_return.credits

        # Foreign tax credit
        foreign_tax = getattr(credits, 'foreign_tax_credit', 0) or 0
        if foreign_tax > 0:
            foreign_elem = ET.SubElement(sched3, "ForeignTaxCreditAmt")
            foreign_elem.text = str(int(foreign_tax))

        # Education credits
        ed_credit = getattr(credits, 'education_credit', 0) or 0
        if ed_credit > 0:
            ed_elem = ET.SubElement(sched3, "EducationCreditAmt")
            ed_elem.text = str(int(ed_credit))

    def _add_schedule_a(self, scheda: ET.Element, tax_return: "TaxReturn") -> None:
        """Add Schedule A (Itemized Deductions)."""
        deductions = tax_return.deductions

        # Medical (Line 4 - amount over 7.5% AGI)
        medical = getattr(deductions, 'medical_expenses', 0) or 0
        agi = tax_return.adjusted_gross_income or 0
        medical_deductible = max(0, medical - agi * 0.075)
        if medical_deductible > 0:
            med_elem = ET.SubElement(scheda, "MedicalAndDentalExpensesAmt")
            med_elem.text = str(int(medical_deductible))

        # SALT (Line 5, capped at $10,000)
        property_tax = getattr(deductions, 'property_taxes', 0) or 0
        state_tax = getattr(deductions, 'state_local_taxes', 0) or 0
        salt = min(property_tax + state_tax, 10000)
        if salt > 0:
            salt_elem = ET.SubElement(scheda, "StateAndLocalTaxAmt")
            salt_elem.text = str(int(salt))

        # Mortgage interest (Line 8)
        mortgage = getattr(deductions, 'mortgage_interest', 0) or 0
        if mortgage > 0:
            mort_elem = ET.SubElement(scheda, "HomeAcquisitionDebtInterestAmt")
            mort_elem.text = str(int(mortgage))

        # Charitable (Line 14)
        charity_cash = getattr(deductions, 'charitable_cash', 0) or 0
        charity_noncash = getattr(deductions, 'charitable_noncash', 0) or 0
        total_charity = charity_cash + charity_noncash
        if total_charity > 0:
            char_elem = ET.SubElement(scheda, "GiftsToCharityAmt")
            char_elem.text = str(int(total_charity))

        # Total itemized (Line 17)
        total = medical_deductible + salt + mortgage + total_charity
        total_elem = ET.SubElement(scheda, "TotalItemizedDeductionsAmt")
        total_elem.text = str(int(total))

    def _add_schedule_c(self, schedc: ET.Element, tax_return: "TaxReturn") -> None:
        """Add Schedule C (Business Income)."""
        income = tax_return.income

        # Gross receipts
        gross = getattr(income, 'self_employment_income', 0) or 0
        gross_elem = ET.SubElement(schedc, "TotalGrossReceiptsAmt")
        gross_elem.text = str(int(gross))

        # Gross income
        gross_inc = ET.SubElement(schedc, "GrossProfitAmt")
        gross_inc.text = str(int(gross))

        # Expenses
        expenses = getattr(income, 'self_employment_expenses', 0) or 0
        exp_elem = ET.SubElement(schedc, "TotalExpensesAmt")
        exp_elem.text = str(int(expenses))

        # Net profit/loss
        net = gross - expenses
        net_elem = ET.SubElement(schedc, "NetProfitOrLossAmt")
        net_elem.text = str(int(net))

    def _add_schedule_se(self, schedse: ET.Element, tax_return: "TaxReturn") -> None:
        """Add Schedule SE (Self-Employment Tax)."""
        income = tax_return.income

        se_income = getattr(income, 'self_employment_income', 0) or 0
        se_expenses = getattr(income, 'self_employment_expenses', 0) or 0
        net_se = max(0, se_income - se_expenses)

        # Net self-employment income
        net_elem = ET.SubElement(schedse, "NetEarningsFromSelfEmplmnAmt")
        net_elem.text = str(int(net_se * 0.9235))

        # Self-employment tax
        se_tax = net_se * 0.9235 * 0.153
        tax_elem = ET.SubElement(schedse, "SelfEmploymentTaxAmt")
        tax_elem.text = str(int(se_tax))

    def _needs_schedule_1(self, tax_return: "TaxReturn") -> bool:
        """Check if Schedule 1 is needed."""
        income = tax_return.income
        se_income = getattr(income, 'self_employment_income', 0) or 0
        sl_interest = getattr(income, 'student_loan_interest', 0) or 0
        return se_income > 0 or sl_interest > 0

    def _needs_schedule_2(self, tax_return: "TaxReturn") -> bool:
        """Check if Schedule 2 is needed."""
        income = tax_return.income
        se_income = getattr(income, 'self_employment_income', 0) or 0
        return se_income > 0

    def _needs_schedule_3(self, tax_return: "TaxReturn") -> bool:
        """Check if Schedule 3 is needed."""
        credits = tax_return.credits
        foreign_tax = getattr(credits, 'foreign_tax_credit', 0) or 0
        ed_credit = getattr(credits, 'education_credit', 0) or 0
        return foreign_tax > 0 or ed_credit > 0

    def _is_itemizing(self, tax_return: "TaxReturn") -> bool:
        """Check if taxpayer is itemizing."""
        deduction_type = getattr(tax_return, 'deduction_type', 'standard')
        return deduction_type == 'itemized'

    def _has_self_employment(self, tax_return: "TaxReturn") -> bool:
        """Check for self-employment income."""
        income = tax_return.income
        se_income = getattr(income, 'self_employment_income', 0) or 0
        return se_income > 0

    def _generate_submission_id(self) -> str:
        """Generate unique submission ID."""
        self._submission_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_part = uuid.uuid4().hex[:8]
        return f"SUB-{timestamp}-{self._submission_counter:04d}-{random_part}"

    def _generate_signature_info(self, tax_return: "TaxReturn") -> Dict[str, Any]:
        """Generate electronic signature information."""
        taxpayer = tax_return.taxpayer

        # Generate hash of key data for signature
        data_to_hash = f"{getattr(taxpayer, 'ssn', '')}|{tax_return.adjusted_gross_income or 0}"
        signature_hash = hashlib.sha256(data_to_hash.encode()).hexdigest()

        return {
            "signature_type": "self_select_pin",
            "signature_timestamp": datetime.now().isoformat(),
            "data_hash": signature_hash,
            "prior_year_agi": getattr(tax_return, 'prior_year_agi', None),
            "identity_verification": "pending",
        }

    def _mask_ssn(self, ssn: str) -> str:
        """Mask SSN showing only last 4."""
        if not ssn:
            return "XXX-XX-XXXX"
        cleaned = ssn.replace("-", "")
        if len(cleaned) >= 4:
            return f"XXX-XX-{cleaned[-4:]}"
        return "XXX-XX-XXXX"

    def _validate_ssn_format(self, ssn: str) -> bool:
        """Validate SSN format."""
        cleaned = ssn.replace("-", "")
        return len(cleaned) == 9 and cleaned.isdigit()


class MeF_XML_Generator(IRSEFileGenerator):
    """
    Extended MeF XML generator with additional features.

    Provides additional validation and formatting options for
    IRS Modernized e-File submissions.
    """

    def generate_manifest(
        self, submissions: List[EFileSubmission]
    ) -> str:
        """Generate transmission manifest for batch submissions."""
        manifest = ET.Element("IRS990ScheduleM")  # Manifest element
        manifest.set("xmlns", self.NAMESPACES["efile"])

        # Transmission info
        trans_info = ET.SubElement(manifest, "TransmissionInfo")
        trans_id = ET.SubElement(trans_info, "TransmissionId")
        trans_id.text = uuid.uuid4().hex

        # Count
        count_elem = ET.SubElement(trans_info, "ReturnCount")
        count_elem.text = str(len(submissions))

        # Individual submissions
        for sub in submissions:
            sub_elem = ET.SubElement(manifest, "SubmissionInfo")
            sub_id = ET.SubElement(sub_elem, "SubmissionId")
            sub_id.text = sub.submission_id
            sub_status = ET.SubElement(sub_elem, "ValidationStatus")
            sub_status.text = "Valid" if sub.validation_result.is_valid else "Invalid"

        return ET.tostring(manifest, encoding="unicode")


class StateEFileGenerator:
    """
    Generates state e-file XML for state tax returns.

    Different states have different e-file requirements and formats.
    This generator supports major state-specific formats.
    """

    def __init__(self, state_code: str):
        """Initialize for specific state."""
        self.state_code = state_code

    def generate_state_return(self, tax_return: "TaxReturn") -> str:
        """Generate state-specific e-file XML."""
        # State-specific logic would go here
        # For now, return generic format

        root = ET.Element("StateReturn")
        root.set("state", self.state_code)
        root.set("taxYear", "2025")

        # Add state-specific data
        taxpayer = tax_return.taxpayer
        state_info = ET.SubElement(root, "TaxpayerInfo")

        name = ET.SubElement(state_info, "Name")
        name.text = f"{getattr(taxpayer, 'first_name', '')} {getattr(taxpayer, 'last_name', '')}"

        # State tax results
        if hasattr(tax_return, 'state_tax_result'):
            result = tax_return.state_tax_result
            if result:
                results_elem = ET.SubElement(root, "StateResults")

                state_tax = ET.SubElement(results_elem, "StateTax")
                state_tax.text = str(int(result.state_tax_liability))

                state_refund = ET.SubElement(results_elem, "StateRefundOwed")
                state_refund.text = str(int(result.state_refund_or_owed))

        return ET.tostring(root, encoding="unicode")
