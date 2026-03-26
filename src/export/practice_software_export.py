"""
Practice Software Export — Drake, Lacerte, ProConnect compatible data export.

Exports tax return data in formats importable by major professional tax software.
This is the #1 feature CPAs need to integrate this platform into their workflow.

Supported formats:
- Drake Software CSV (DrakeCRD compatible)
- Lacerte/ProConnect CSV
- Universal JSON with IRS form/line mappings
"""

import csv
import io
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class PracticeSoftwareExporter:
    """Export tax return data for professional tax software import."""

    # IRS Form 1040 line mapping (2025)
    FORM_1040_LINES = {
        "1a": "wages",
        "2a": "tax_exempt_interest",
        "2b": "taxable_interest",
        "3a": "qualified_dividends",
        "3b": "ordinary_dividends",
        "4a": "ira_distributions_gross",
        "4b": "ira_distributions_taxable",
        "5a": "pensions_gross",
        "5b": "pensions_taxable",
        "6a": "social_security_gross",
        "6b": "social_security_taxable",
        "7": "capital_gain_or_loss",
        "8": "other_income",
        "9": "total_income",
        "10": "adjustments_to_income",
        "11": "adjusted_gross_income",
        "12": "deductions",
        "13": "qualified_business_income_deduction",
        "14": "total_deductions",
        "15": "taxable_income",
        "16": "tax",
        "17": "amount_from_schedule_2",
        "18": "total_tax_before_credits",
        "19": "child_tax_credit",
        "20": "amount_from_schedule_3",
        "21": "total_credits",
        "22": "tax_minus_credits",
        "23": "other_taxes",
        "24": "total_tax",
        "25a": "w2_withholding",
        "25b": "1099_withholding",
        "25c": "other_withholding",
        "25d": "total_withholding",
        "26": "estimated_tax_payments",
        "27": "earned_income_credit",
        "28": "additional_child_tax_credit",
        "29": "american_opportunity_credit",
        "30": "reserved",
        "31": "amount_from_schedule_3_line_15",
        "32": "total_other_payments_credits",
        "33": "total_payments",
        "34": "overpayment",
        "35a": "refund",
        "37": "amount_owed",
    }

    def export_drake_csv(self, return_data: Dict[str, Any]) -> str:
        """
        Export in Drake Software import format.

        Drake uses a specific CSV format for client data import.
        This generates a DrakeCRD-compatible structure.
        """
        output = io.StringIO()
        writer = csv.writer(output)

        tp = return_data.get("taxpayer", {})
        inc = return_data.get("income", return_data)

        # Drake header row
        writer.writerow(["Field", "Value", "Form", "Line"])

        # Taxpayer info
        writer.writerow(["FirstName", tp.get("first_name", ""), "1040", ""])
        writer.writerow(["LastName", tp.get("last_name", ""), "1040", ""])
        writer.writerow(["SSN", tp.get("ssn", "***-**-****"), "1040", ""])
        writer.writerow(["FilingStatus", return_data.get("filing_status", "single"), "1040", ""])
        writer.writerow(["State", return_data.get("state_of_residence", ""), "1040", ""])
        writer.writerow(["TaxYear", return_data.get("tax_year", 2025), "1040", ""])

        # Income fields
        wages = return_data.get("w2_wages", 0) or inc.get("wages", 0) or return_data.get("total_income", 0)
        writer.writerow(["Wages", wages, "1040", "1a"])
        writer.writerow(["InterestIncome", return_data.get("interest_income", 0) or inc.get("interest_income", 0), "1040", "2b"])
        writer.writerow(["DividendIncome", return_data.get("dividend_income", 0) or inc.get("dividend_income", 0), "1040", "3b"])
        writer.writerow(["QualifiedDividends", return_data.get("qualified_dividends", 0) or inc.get("qualified_dividends", 0), "1040", "3a"])
        writer.writerow(["BusinessIncome", return_data.get("self_employment_income", 0) or inc.get("self_employment_income", 0), "SchC", "31"])
        writer.writerow(["CapitalGains", return_data.get("capital_gains", 0) or inc.get("long_term_capital_gains", 0), "SchD", ""])
        writer.writerow(["RentalIncome", return_data.get("rental_income", 0) or inc.get("rental_income", 0), "SchE", ""])
        writer.writerow(["SocialSecurity", return_data.get("ss_benefits", 0) or inc.get("social_security_benefits", 0), "1040", "6a"])

        # Calculated fields
        writer.writerow(["AGI", return_data.get("adjusted_gross_income", 0), "1040", "11"])
        writer.writerow(["TaxableIncome", return_data.get("taxable_income", 0), "1040", "15"])
        writer.writerow(["TotalTax", return_data.get("tax_liability", 0), "1040", "24"])
        writer.writerow(["TotalPayments", return_data.get("total_payments", 0), "1040", "33"])
        writer.writerow(["RefundOrOwed", return_data.get("refund_or_owed", 0), "1040", "34/37"])

        # Deductions
        writer.writerow(["DeductionType", return_data.get("deduction_type", "standard"), "1040", "12"])
        writer.writerow(["DeductionAmount", return_data.get("deduction_amount", 0), "1040", "12"])
        writer.writerow(["MortgageInterest", return_data.get("mortgage_interest", 0), "SchA", "8a"])
        writer.writerow(["StateTaxes", return_data.get("state_taxes_paid", 0), "SchA", "5a"])
        writer.writerow(["CharitableDonations", return_data.get("charitable_donations", 0), "SchA", "12"])

        # Withholding
        writer.writerow(["FederalWithholding", return_data.get("federal_withholding", 0) or return_data.get("total_payments", 0), "1040", "25d"])
        writer.writerow(["EstimatedPayments", return_data.get("estimated_payments", 0), "1040", "26"])

        # Credits
        writer.writerow(["ChildTaxCredit", return_data.get("child_tax_credit", 0), "1040", "19"])
        writer.writerow(["EITC", return_data.get("eitc", 0), "1040", "27"])
        writer.writerow(["EducationCredit", return_data.get("education_credit", 0), "8863", ""])

        # Effective rate
        writer.writerow(["EffectiveRate", return_data.get("effective_rate", 0), "Computed", ""])

        return output.getvalue()

    def export_lacerte_csv(self, return_data: Dict[str, Any]) -> str:
        """
        Export in Lacerte/ProConnect import format.

        Lacerte uses a tab-delimited format with screen/field references.
        This generates a simplified version compatible with Lacerte Client Import.
        """
        output = io.StringIO()
        writer = csv.writer(output, delimiter='\t')

        tp = return_data.get("taxpayer", {})

        # Lacerte header
        writer.writerow(["Screen", "Field", "Value"])

        # Client info (Screen 1)
        writer.writerow(["1", "First Name", tp.get("first_name", "")])
        writer.writerow(["1", "Last Name", tp.get("last_name", "")])
        writer.writerow(["1", "SSN", tp.get("ssn", "***-**-****")])
        writer.writerow(["1", "Filing Status", return_data.get("filing_status", "single")])
        writer.writerow(["1", "State", return_data.get("state_of_residence", "")])

        # W-2 Income (Screen 10)
        writer.writerow(["10", "Employer Wages", return_data.get("w2_wages", 0)])
        writer.writerow(["10", "Federal Withheld", return_data.get("federal_withholding", 0)])

        # Interest/Dividends (Screen 11)
        writer.writerow(["11", "Taxable Interest", return_data.get("interest_income", 0)])
        writer.writerow(["11", "Ordinary Dividends", return_data.get("dividend_income", 0)])
        writer.writerow(["11", "Qualified Dividends", return_data.get("qualified_dividends", 0)])

        # Schedule C (Screen 16)
        writer.writerow(["16", "Business Income", return_data.get("self_employment_income", 0)])
        writer.writerow(["16", "Business Expenses", return_data.get("business_expenses", 0)])

        # Capital Gains (Screen 17)
        writer.writerow(["17", "Long-term Gains", return_data.get("long_term_capital_gains", 0)])
        writer.writerow(["17", "Short-term Gains", return_data.get("short_term_capital_gains", 0)])

        # Rental (Screen 18)
        writer.writerow(["18", "Rental Income", return_data.get("rental_income", 0)])
        writer.writerow(["18", "Rental Expenses", return_data.get("rental_expenses", 0)])

        # Deductions (Screen 25)
        writer.writerow(["25", "Mortgage Interest", return_data.get("mortgage_interest", 0)])
        writer.writerow(["25", "State/Local Taxes", return_data.get("state_taxes_paid", 0)])
        writer.writerow(["25", "Charitable", return_data.get("charitable_donations", 0)])
        writer.writerow(["25", "Medical Expenses", return_data.get("medical_expenses", 0)])

        # Retirement (Screen 13)
        writer.writerow(["13", "401k Contribution", return_data.get("retirement_401k", 0)])
        writer.writerow(["13", "IRA Contribution", return_data.get("retirement_ira", 0)])
        writer.writerow(["13", "HSA Contribution", return_data.get("hsa_contributions", 0)])

        return output.getvalue()

    def export_universal_json(self, return_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Export as universal JSON with IRS form/line mappings.

        This format can be adapted by any practice software that accepts
        structured data. Each field includes form, line, and description.
        """
        tp = return_data.get("taxpayer", {})

        export = {
            "export_format": "jorss-gbo-universal-v1",
            "export_date": datetime.utcnow().isoformat(),
            "tax_year": return_data.get("tax_year", 2025),
            "platform": "Jorss-GBO Tax Advisory Platform",

            "taxpayer": {
                "first_name": tp.get("first_name", ""),
                "last_name": tp.get("last_name", ""),
                "ssn_masked": tp.get("ssn", "***-**-****"),
                "filing_status": return_data.get("filing_status", ""),
                "state": return_data.get("state_of_residence", ""),
            },

            "form_1040": {
                "line_1a_wages": return_data.get("w2_wages", 0) or return_data.get("total_income", 0),
                "line_2b_interest": return_data.get("interest_income", 0),
                "line_3a_qualified_dividends": return_data.get("qualified_dividends", 0),
                "line_3b_ordinary_dividends": return_data.get("dividend_income", 0),
                "line_7_capital_gains": return_data.get("capital_gains", 0),
                "line_8_other_income": return_data.get("other_income", 0),
                "line_9_total_income": return_data.get("total_income", 0),
                "line_11_agi": return_data.get("adjusted_gross_income", 0),
                "line_12_deductions": return_data.get("deduction_amount", 0),
                "line_13_qbi_deduction": return_data.get("qbi_deduction", 0),
                "line_15_taxable_income": return_data.get("taxable_income", 0),
                "line_16_tax": return_data.get("tax_liability", 0),
                "line_24_total_tax": return_data.get("tax_liability", 0),
                "line_25d_withholding": return_data.get("total_payments", 0),
                "line_26_estimated_payments": return_data.get("estimated_payments", 0),
                "line_33_total_payments": return_data.get("total_payments", 0),
                "line_34_overpayment": max(0, (return_data.get("refund_or_owed", 0))),
                "line_37_amount_owed": max(0, -(return_data.get("refund_or_owed", 0))),
            },

            "schedule_c": {
                "gross_income": return_data.get("self_employment_income", 0),
                "total_expenses": return_data.get("business_expenses", 0),
                "net_profit": (return_data.get("self_employment_income", 0) or 0) - (return_data.get("business_expenses", 0) or 0),
            },

            "schedule_a": {
                "mortgage_interest": return_data.get("mortgage_interest", 0),
                "state_local_taxes": return_data.get("state_taxes_paid", 0),
                "charitable_contributions": return_data.get("charitable_donations", 0),
                "medical_expenses": return_data.get("medical_expenses", 0),
                "total_itemized": return_data.get("total_itemized", 0),
            },

            "computed": {
                "deduction_type": return_data.get("deduction_type", "standard"),
                "standard_deduction": return_data.get("standard_deduction", 0),
                "effective_rate": return_data.get("effective_rate", 0),
                "refund_or_owed": return_data.get("refund_or_owed", 0),
                "se_tax": return_data.get("se_tax", 0),
                "amt": return_data.get("amt", 0),
                "niit": return_data.get("niit", 0),
            },

            "credits": {
                "child_tax_credit": return_data.get("child_tax_credit", 0),
                "additional_child_tax_credit": return_data.get("additional_child_tax_credit", 0),
                "eitc": return_data.get("eitc", 0),
                "education_credit": return_data.get("education_credit", 0),
                "foreign_tax_credit": return_data.get("foreign_tax_credit", 0),
            },
        }

        return export


# Module-level singleton
_exporter = PracticeSoftwareExporter()


def get_drake_csv(return_data: Dict[str, Any]) -> str:
    """Get Drake Software compatible CSV export."""
    return _exporter.export_drake_csv(return_data)


def get_lacerte_csv(return_data: Dict[str, Any]) -> str:
    """Get Lacerte/ProConnect compatible CSV export."""
    return _exporter.export_lacerte_csv(return_data)


def get_universal_json(return_data: Dict[str, Any]) -> Dict[str, Any]:
    """Get universal JSON export with IRS form/line mappings."""
    return _exporter.export_universal_json(return_data)
