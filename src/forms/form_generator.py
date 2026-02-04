"""
Generate tax forms (Form 1040 and schedules) from completed tax return
"""
from __future__ import annotations

from typing import Dict, Any, TYPE_CHECKING
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal

if TYPE_CHECKING:
    from models.tax_return import TaxReturn


class FormGenerator:
    """Generate tax forms from tax return data"""
    
    def generate_form_1040(self, tax_return: TaxReturn) -> Dict[str, Any]:
        """
        Generate Form 1040 data structure
        Returns a dictionary representing the form fields
        """
        taxpayer = tax_return.taxpayer
        income = tax_return.income
        deductions = tax_return.deductions
        
        form_data = {
            "form_name": "Form 1040",
            "tax_year": tax_return.tax_year,
            
            # Personal Information
            "name": f"{taxpayer.first_name} {taxpayer.last_name}",
            "ssn": taxpayer.ssn or "[Not provided]",
            "filing_status": taxpayer.filing_status.value,
            "address": taxpayer.address or "",
            "city_state_zip": f"{taxpayer.city or ''}, {taxpayer.state or ''} {taxpayer.zip_code or ''}",
            
            # Spouse Information (if applicable)
            "spouse_name": f"{taxpayer.spouse_first_name or ''} {taxpayer.spouse_last_name or ''}".strip() or None,
            "spouse_ssn": taxpayer.spouse_ssn or None,
            
            # Income (Line 1-11)
            "line_1_wages": income.get_total_wages(),
            "line_2a_tax_exempt_interest": 0.0,  # Would need additional input
            "line_2b_taxable_interest": income.interest_income,
            "line_3a_qualified_dividends": income.qualified_dividends,
            "line_3b_ordinary_dividends": income.dividend_income,
            "line_4a_ira_distributions": 0.0,  # Would need additional input
            "line_4b_taxable_amount": income.retirement_income,
            "line_5a_pensions_annuities": income.retirement_income,
            "line_5b_taxable_amount": income.retirement_income,
            "line_6_social_security": income.social_security_benefits,
            "line_7_capital_gain": 0.0,  # Would need Schedule D
            "line_8_other_income": income.other_income,
            "line_9_total_income": income.get_total_income(),
            
            # Adjustments (Line 10-14)
            "line_10_educator_expenses": deductions.educator_expenses,
            "line_11_certain_business_expenses": 0.0,  # Would need Schedule C
            "line_12_hsa_deduction": deductions.hsa_contributions,
            "line_13_moving_expenses": 0.0,  # Military only for 2025
            "line_14_deduction_contributions": deductions.ira_contributions,
            "line_15_student_loan_interest": deductions.student_loan_interest,
            "line_16_tuition_fees": 0.0,  # Would need Form 8917
            "line_17_other_adjustments": deductions.other_adjustments,
            "line_18_total_adjustments": deductions.get_total_adjustments(),
            
            # Adjusted Gross Income
            "line_19_agi": tax_return.adjusted_gross_income or 0.0,
            
            # Standard Deduction or Itemized
            "line_20_standard_deduction": 0.0,
            "line_21_itemized_deductions": 0.0,
            "line_22_qualified_business_income": 0.0,  # Would need Schedule 1
            "line_23_total_deductions": deductions.get_deduction_amount(
                taxpayer.filing_status.value,
                tax_return.adjusted_gross_income or 0.0,
                taxpayer.is_over_65,
                taxpayer.is_blind
            ),
            
            # Taxable Income
            "line_24_taxable_income": tax_return.taxable_income or 0.0,
            
            # Tax (Line 25-32)
            "line_25_tax": tax_return.tax_liability or 0.0,
            "line_26_alternative_minimum_tax": 0.0,  # Would need Form 6251
            "line_27_excess_advance_premium": 0.0,  # Would need Form 8962
            "line_28_total_tax": tax_return.tax_liability or 0.0,
            
            # Payments (Line 33-38)
            "line_33_federal_withholding": income.get_total_federal_withholding(),
            "line_34_estimated_tax_payments": 0.0,
            "line_35_earned_income_credit": 0.0,  # Calculated separately
            "line_36_other_payments": 0.0,
            "line_37_total_payments": tax_return.total_payments or 0.0,
            
            # Refund or Amount Owed
            "line_38_refund": 0.0,
            "line_39_amount_owed": 0.0,
        }
        
        # Calculate refund or amount owed
        total_tax = form_data["line_28_total_tax"]
        total_credits = tax_return.total_credits or 0.0
        net_tax = total_tax - total_credits
        total_payments = form_data["line_37_total_payments"]
        
        if total_payments > net_tax:
            form_data["line_38_refund"] = total_payments - net_tax
            form_data["line_39_amount_owed"] = 0.0
        else:
            form_data["line_38_refund"] = 0.0
            form_data["line_39_amount_owed"] = net_tax - total_payments
        
        # Set standard vs itemized
        if deductions.use_standard_deduction:
            form_data["line_20_standard_deduction"] = form_data["line_23_total_deductions"]
        else:
            form_data["line_21_itemized_deductions"] = form_data["line_23_total_deductions"]
        
        return form_data

    def generate_schedule_d(self, tax_return: TaxReturn) -> Dict[str, Any]:
        """
        Generate Schedule D - Capital Gains and Losses
        Returns a dictionary representing the form fields
        """
        income = tax_return.income
        filing_status = tax_return.taxpayer.filing_status.value

        # Calculate net capital gain/loss using the proper method (IRC 1211/1212)
        cap_result = income.calculate_net_capital_gain_loss(filing_status=filing_status)
        (net_gain_for_tax, loss_deduction, new_st_cf, new_lt_cf, net_short_term, net_long_term) = cap_result

        # Overall net for the form
        total_net_gain_loss = net_short_term + net_long_term

        # Prior year carryforward amounts (entered as negative on Schedule D)
        st_carryover = -income.short_term_loss_carryforward if income.short_term_loss_carryforward > 0 else 0.0
        lt_carryover = -income.long_term_loss_carryforward if income.long_term_loss_carryforward > 0 else 0.0

        # Get K-1 capital gains
        k1_st, k1_lt = income.get_k1_capital_gains()

        # Qualified Dividends and Capital Gain Tax Worksheet data
        qualified_dividends = income.qualified_dividends

        return {
            "form_name": "Schedule D",
            "form_title": "Capital Gains and Losses",
            "tax_year": tax_return.tax_year,

            # Part I - Short-Term
            "part1_description": "Short-Term Capital Gains and Losses (Held 1 Year or Less)",
            "line_1a_totals_from_8949_box_a": 0.0,  # From Form 8949
            "line_1b_totals_from_8949_box_b": 0.0,  # From Form 8949
            "line_1c_totals_from_8949_box_c": 0.0,  # From Form 8949
            "line_2_short_term_from_k1": k1_st,  # From K-1s
            "line_3_short_term_carryover": st_carryover,  # Prior year carryover (negative)
            "line_4_short_term_gain_loss_2439": 0.0,  # From Form 2439
            "line_5_net_short_term_from_other": income.short_term_capital_gains,
            "line_6_short_term_prior_year": 0.0,
            "line_7_net_short_term_gain_loss": net_short_term,

            # Part II - Long-Term
            "part2_description": "Long-Term Capital Gains and Losses (Held More Than 1 Year)",
            "line_8a_totals_from_8949_box_d": 0.0,  # From Form 8949
            "line_8b_totals_from_8949_box_e": 0.0,  # From Form 8949
            "line_8c_totals_from_8949_box_f": 0.0,  # From Form 8949
            "line_9_long_term_from_k1": k1_lt,  # From K-1s
            "line_10_long_term_carryover": lt_carryover,  # Prior year carryover (negative)
            "line_11_long_term_gain_2439": 0.0,  # From Form 2439
            "line_12_net_long_term_from_other": income.long_term_capital_gains,
            "line_13_long_term_collectibles_gain": 0.0,  # 28% rate gain
            "line_14_long_term_1250_gain": 0.0,  # Unrecaptured Section 1250 gain
            "line_15_net_long_term_gain_loss": net_long_term,

            # Part III - Summary
            "part3_description": "Summary",
            "line_16_combine_lines_7_15": total_net_gain_loss,
            "line_17_gain_both_positive": "yes" if (net_short_term >= 0 and net_long_term >= 0) else "no",
            "line_18_28_rate_gain": 0.0,  # Collectibles
            "line_19_unrecaptured_1250": 0.0,  # Unrecaptured Section 1250
            "line_20_worksheet_required": "yes" if (net_long_term > 0 or qualified_dividends > 0) else "no",
            "line_21_loss_limited_to_3000": loss_deduction,

            # Summary amounts for Form 1040
            "total_short_term_gain_loss": net_short_term,
            "total_long_term_gain_loss": net_long_term,
            "net_capital_gain_loss": total_net_gain_loss,
            "qualified_dividends": qualified_dividends,

            # Transfer to Form 1040 (gain or limited loss)
            "to_form_1040_line_7": net_gain_for_tax if net_gain_for_tax > 0 else -loss_deduction,

            # Carryforward to next year (for taxpayer reference)
            "carryforward_short_term": new_st_cf,
            "carryforward_long_term": new_lt_cf,
        }

    def generate_schedule_e(self, tax_return: TaxReturn) -> Dict[str, Any]:
        """
        Generate Schedule E - Supplemental Income and Loss
        (Rental Real Estate, Royalties, Partnerships, S Corporations, Estates, Trusts)
        Returns a dictionary representing the form fields
        """
        income = tax_return.income
        taxpayer = tax_return.taxpayer

        # Rental Real Estate (Part I)
        gross_rents = income.rental_income
        rental_expenses = income.rental_expenses
        net_rental = gross_rents - rental_expenses

        # Royalty Income (also Part I)
        royalty_income = income.royalty_income

        # Total Part I income
        total_part1 = net_rental + royalty_income

        return {
            "form_name": "Schedule E",
            "form_title": "Supplemental Income and Loss",
            "tax_year": tax_return.tax_year,
            "taxpayer_name": f"{taxpayer.first_name} {taxpayer.last_name}",
            "taxpayer_ssn": taxpayer.ssn or "[Not provided]",

            # Part I - Income or Loss From Rental Real Estate and Royalties
            "part1_description": "Income or Loss From Rental Real Estate and Royalties",

            # Property A (simplified - assuming single property)
            "property_a_address": "See attached statement",
            "property_a_type": "Residential Rental",
            "property_a_fair_rental_days": 365,
            "property_a_personal_use_days": 0,
            "property_a_qbi_property": "yes",

            # Income
            "line_3_rents_received_a": gross_rents,
            "line_4_royalties_received_a": royalty_income,

            # Expenses (simplified breakdown)
            "line_5_advertising": 0.0,
            "line_6_auto_travel": 0.0,
            "line_7_cleaning_maintenance": float(money(rental_expenses * 0.15)) if rental_expenses > 0 else 0.0,
            "line_8_commissions": 0.0,
            "line_9_insurance": float(money(rental_expenses * 0.10)) if rental_expenses > 0 else 0.0,
            "line_10_legal_professional": 0.0,
            "line_11_management_fees": float(money(rental_expenses * 0.10)) if rental_expenses > 0 else 0.0,
            "line_12_mortgage_interest": float(money(rental_expenses * 0.30)) if rental_expenses > 0 else 0.0,
            "line_13_other_interest": 0.0,
            "line_14_repairs": float(money(rental_expenses * 0.15)) if rental_expenses > 0 else 0.0,
            "line_15_supplies": 0.0,
            "line_16_taxes": float(money(rental_expenses * 0.15)) if rental_expenses > 0 else 0.0,
            "line_17_utilities": float(money(rental_expenses * 0.05)) if rental_expenses > 0 else 0.0,
            "line_18_depreciation": 0.0,  # Would need cost basis and placed-in-service date
            "line_19_other": 0.0,
            "line_20_total_expenses": rental_expenses,

            # Net Income/Loss
            "line_21_net_income_loss_a": net_rental,
            "line_22_deductible_rental_loss": 0.0,  # Passive activity rules may limit
            "line_23a_total_rental_real_estate": net_rental,
            "line_23b_total_royalties": royalty_income,
            "line_24_income_from_form_4835": 0.0,  # Farm rental
            "line_25_passive_activity_loss": 0.0,
            "line_26_total_part1": total_part1,

            # Part II - Income or Loss From Partnerships and S Corporations
            "part2_description": "Income or Loss From Partnerships and S Corporations",
            "line_28_passive_income": 0.0,
            "line_29_nonpassive_income": 0.0,
            "line_30_passive_loss": 0.0,
            "line_31_nonpassive_loss": 0.0,
            "line_32_total_partnership_s_corp": 0.0,

            # Part III - Income or Loss From Estates and Trusts
            "part3_description": "Income or Loss From Estates and Trusts",
            "line_33_passive_income": 0.0,
            "line_34_nonpassive_income": 0.0,
            "line_35_passive_loss": 0.0,
            "line_36_nonpassive_loss": 0.0,
            "line_37_total_estates_trusts": 0.0,

            # Part IV - Income or Loss From REMICs
            "part4_description": "Income or Loss From REMICs",
            "line_38_total_remic": 0.0,

            # Part V - Summary
            "part5_description": "Summary",
            "line_39_total_real_estate": net_rental,
            "line_40_total_royalties": royalty_income,
            "line_41_total_partnerships": 0.0,
            "line_42_total_trusts": 0.0,
            "line_43_net_farm": 0.0,
            "line_44_reconciliation": 0.0,

            # Total to Schedule 1
            "total_schedule_e_income": total_part1,
            "to_schedule_1_line_5": total_part1,
        }

    def generate_schedule_c(self, tax_return: TaxReturn) -> Dict[str, Any]:
        """
        Generate Schedule C - Profit or Loss From Business
        Returns a dictionary representing the form fields
        """
        income = tax_return.income
        taxpayer = tax_return.taxpayer

        gross_receipts = income.self_employment_income
        total_expenses = income.self_employment_expenses
        net_profit = gross_receipts - total_expenses

        return {
            "form_name": "Schedule C",
            "form_title": "Profit or Loss From Business (Sole Proprietorship)",
            "tax_year": tax_return.tax_year,
            "taxpayer_name": f"{taxpayer.first_name} {taxpayer.last_name}",
            "taxpayer_ssn": taxpayer.ssn or "[Not provided]",

            # Business Information
            "line_a_principal_business": "Professional Services",  # Default
            "line_b_business_code": "541990",  # Other professional services
            "line_c_business_name": f"{taxpayer.first_name} {taxpayer.last_name}",
            "line_d_employer_id": "",  # EIN if applicable
            "line_e_business_address": taxpayer.address or "",
            "line_f_accounting_method": "Cash",
            "line_g_material_participation": "yes",
            "line_h_started_or_acquired": "no",
            "line_i_payments_requiring_1099": "no",
            "line_j_filed_required_1099s": "N/A",

            # Part I - Income
            "line_1_gross_receipts": gross_receipts,
            "line_2_returns_allowances": 0.0,
            "line_3_subtract": gross_receipts,
            "line_4_cost_of_goods_sold": 0.0,
            "line_5_gross_profit": gross_receipts,
            "line_6_other_income": 0.0,
            "line_7_gross_income": gross_receipts,

            # Part II - Expenses (simplified)
            "line_8_advertising": float(money(total_expenses * 0.05)) if total_expenses > 0 else 0.0,
            "line_9_car_truck": float(money(total_expenses * 0.10)) if total_expenses > 0 else 0.0,
            "line_10_commissions": 0.0,
            "line_11_contract_labor": float(money(total_expenses * 0.15)) if total_expenses > 0 else 0.0,
            "line_12_depletion": 0.0,
            "line_13_depreciation": float(money(total_expenses * 0.10)) if total_expenses > 0 else 0.0,
            "line_14_employee_benefits": 0.0,
            "line_15_insurance": float(money(total_expenses * 0.05)) if total_expenses > 0 else 0.0,
            "line_16a_mortgage_interest": 0.0,
            "line_16b_other_interest": 0.0,
            "line_17_legal_professional": float(money(total_expenses * 0.05)) if total_expenses > 0 else 0.0,
            "line_18_office_expense": float(money(total_expenses * 0.10)) if total_expenses > 0 else 0.0,
            "line_19_pension_plans": 0.0,
            "line_20a_rent_vehicles": 0.0,
            "line_20b_rent_other": float(money(total_expenses * 0.10)) if total_expenses > 0 else 0.0,
            "line_21_repairs": float(money(total_expenses * 0.05)) if total_expenses > 0 else 0.0,
            "line_22_supplies": float(money(total_expenses * 0.10)) if total_expenses > 0 else 0.0,
            "line_23_taxes_licenses": float(money(total_expenses * 0.05)) if total_expenses > 0 else 0.0,
            "line_24a_travel": float(money(total_expenses * 0.05)) if total_expenses > 0 else 0.0,
            "line_24b_meals": float(money(total_expenses * 0.05)) if total_expenses > 0 else 0.0,
            "line_25_utilities": 0.0,
            "line_26_wages": 0.0,
            "line_27a_other_expenses": 0.0,
            "line_27b_reserved": 0.0,
            "line_28_total_expenses": total_expenses,

            # Net Profit or Loss
            "line_29_tentative_profit": net_profit,
            "line_30_home_office_deduction": 0.0,
            "line_31_net_profit_loss": net_profit,
            "line_32a_at_risk_investment": gross_receipts,
            "line_32b_some_investment_not_at_risk": "no",

            # Summary
            "net_self_employment_income": net_profit,
            "to_schedule_1_line_3": net_profit,
            "to_schedule_se": net_profit,
        }

    def generate_all_schedules(self, tax_return: TaxReturn) -> Dict[str, Any]:
        """
        Generate all applicable schedules based on tax return data.
        Returns a dictionary with all forms and schedules.
        """
        income = tax_return.income
        result = {
            "form_1040": self.generate_form_1040(tax_return),
        }

        # Generate Schedule C if self-employment income exists
        if income.self_employment_income > 0:
            result["schedule_c"] = self.generate_schedule_c(tax_return)

        # Generate Schedule D if capital gains/losses exist
        if income.short_term_capital_gains > 0 or income.long_term_capital_gains > 0:
            result["schedule_d"] = self.generate_schedule_d(tax_return)

        # Generate Schedule E if rental/royalty income exists
        if income.rental_income > 0 or income.royalty_income > 0:
            result["schedule_e"] = self.generate_schedule_e(tax_return)

        return result

    def generate_summary(self, tax_return: TaxReturn) -> str:
        """Generate a human-readable summary of the tax return"""
        if not tax_return:
            return "No tax return data available."
        
        summary_lines = [
            "=" * 60,
            "TAX RETURN SUMMARY - 2025",
            "=" * 60,
            "",
            f"Taxpayer: {tax_return.taxpayer.first_name} {tax_return.taxpayer.last_name}",
            f"Filing Status: {tax_return.taxpayer.filing_status.value.replace('_', ' ').title()}",
            "",
            "INCOME:",
            f"  W-2 Wages: ${tax_return.income.get_total_wages():,.2f}",
            f"  Other Income: ${tax_return.income.get_total_income() - tax_return.income.get_total_wages():,.2f}",
            f"  Total Income: ${tax_return.income.get_total_income():,.2f}",
            "",
            "ADJUSTMENTS:",
            f"  Total Adjustments: ${tax_return.deductions.get_total_adjustments():,.2f}",
            "",
            "ADJUSTED GROSS INCOME:",
            f"  AGI: ${tax_return.adjusted_gross_income or 0:,.2f}",
            "",
            "DEDUCTIONS:",
        ]
        
        if tax_return.deductions.use_standard_deduction:
            deduction_amount = tax_return.deductions.get_deduction_amount(
                tax_return.taxpayer.filing_status.value,
                tax_return.adjusted_gross_income or 0.0,
                tax_return.taxpayer.is_over_65,
                tax_return.taxpayer.is_blind
            )
            summary_lines.append(f"  Standard Deduction: ${deduction_amount:,.2f}")
        else:
            itemized = tax_return.deductions.itemized.get_total_itemized(
                tax_return.adjusted_gross_income or 0.0
            )
            summary_lines.append(f"  Itemized Deductions: ${itemized:,.2f}")
        
        summary_lines.extend([
            "",
            "TAXABLE INCOME:",
            f"  Taxable Income: ${tax_return.taxable_income or 0:,.2f}",
            "",
            "TAX LIABILITY:",
            f"  Federal Tax: ${tax_return.tax_liability or 0:,.2f}",
            f"  Total Credits: ${tax_return.total_credits or 0:,.2f}",
            f"  Net Tax: ${(tax_return.tax_liability or 0) - (tax_return.total_credits or 0):,.2f}",
            "",
            "PAYMENTS & REFUND:",
            f"  Federal Withholding: ${tax_return.total_payments or 0:,.2f}",
        ])
        
        refund_owed = tax_return.refund_or_owed or 0.0
        if refund_owed > 0:
            summary_lines.append(f"  REFUND: ${refund_owed:,.2f}")
        elif refund_owed < 0:
            summary_lines.append(f"  AMOUNT OWED: ${abs(refund_owed):,.2f}")
        else:
            summary_lines.append("  BALANCE: $0.00")
        
        summary_lines.extend([
            "",
            "=" * 60,
        ])

        return "\n".join(summary_lines)

    def generate_state_summary(self, tax_return: TaxReturn) -> str:
        """Generate a human-readable summary of state tax calculation."""
        if not tax_return.state_tax_result:
            return "No state tax calculation available."

        result = tax_return.state_tax_result
        state_code = result.get("state_code", "")
        state_name = result.get("state_name", state_code)

        summary_lines = [
            "=" * 60,
            f"STATE TAX SUMMARY - {state_name} ({state_code})",
            "=" * 60,
            "",
            "INCOME CALCULATION:",
            f"  Federal AGI: ${result.get('federal_agi', 0):,.2f}",
            f"  State Additions: ${result.get('state_additions', 0):,.2f}",
            f"  State Subtractions: ${result.get('state_subtractions', 0):,.2f}",
            f"  State Adjusted Income: ${result.get('state_adjusted_income', 0):,.2f}",
            "",
            "DEDUCTIONS:",
            f"  Deduction Type: {result.get('deduction_used', 'standard').title()}",
            f"  Deduction Amount: ${result.get('deduction_amount', 0):,.2f}",
            "",
            "EXEMPTIONS:",
            f"  Personal Exemptions: {result.get('personal_exemptions', 0)}",
            f"  Dependent Exemptions: {result.get('dependent_exemptions', 0)}",
            f"  Exemption Amount/Credit: ${result.get('exemption_amount', 0):,.2f}",
            "",
            "TAXABLE INCOME:",
            f"  State Taxable Income: ${result.get('state_taxable_income', 0):,.2f}",
            "",
            "STATE TAX:",
            f"  Tax Before Credits: ${result.get('state_tax_before_credits', 0):,.2f}",
        ]

        # Add local tax if applicable
        local_tax = result.get('local_tax', 0)
        if local_tax > 0:
            summary_lines.append(f"  Local Tax: ${local_tax:,.2f}")

        # Add credits breakdown
        credits = result.get('state_credits', {})
        if credits:
            summary_lines.append("")
            summary_lines.append("STATE CREDITS:")
            for credit_name, credit_amount in credits.items():
                if credit_amount > 0:
                    formatted_name = credit_name.replace('_', ' ').title()
                    summary_lines.append(f"  {formatted_name}: ${credit_amount:,.2f}")
            summary_lines.append(f"  Total Credits: ${result.get('total_state_credits', 0):,.2f}")

        summary_lines.extend([
            "",
            "STATE TAX LIABILITY:",
            f"  State Tax: ${result.get('state_tax_liability', 0):,.2f}",
            "",
            "PAYMENTS & REFUND:",
            f"  State Withholding: ${result.get('state_withholding', 0):,.2f}",
        ])

        state_refund = result.get('state_refund_or_owed', 0)
        if state_refund > 0:
            summary_lines.append(f"  STATE REFUND: ${state_refund:,.2f}")
        elif state_refund < 0:
            summary_lines.append(f"  STATE AMOUNT OWED: ${abs(state_refund):,.2f}")
        else:
            summary_lines.append("  STATE BALANCE: $0.00")

        summary_lines.extend([
            "",
            "=" * 60,
        ])

        return "\n".join(summary_lines)

    def generate_combined_summary(self, tax_return: TaxReturn) -> str:
        """Generate combined federal and state tax summary."""
        # Federal summary
        federal_summary = self.generate_summary(tax_return)

        # State summary (if available)
        if tax_return.state_tax_result:
            state_summary = self.generate_state_summary(tax_return)

            # Combined totals section
            combined_lines = [
                "",
                "=" * 60,
                "COMBINED TAX SUMMARY",
                "=" * 60,
                "",
                f"Federal Tax Liability: ${tax_return.tax_liability or 0:,.2f}",
                f"State Tax Liability: ${tax_return.state_tax_liability or 0:,.2f}",
                f"Combined Tax Liability: ${tax_return.combined_tax_liability or 0:,.2f}",
                "",
                f"Federal Refund/Owed: ${tax_return.refund_or_owed or 0:,.2f}",
                f"State Refund/Owed: ${tax_return.state_refund_or_owed or 0:,.2f}",
            ]

            combined_refund = tax_return.combined_refund_or_owed or 0
            if combined_refund > 0:
                combined_lines.append(f"TOTAL REFUND: ${combined_refund:,.2f}")
            elif combined_refund < 0:
                combined_lines.append(f"TOTAL AMOUNT OWED: ${abs(combined_refund):,.2f}")
            else:
                combined_lines.append("TOTAL BALANCE: $0.00")

            combined_lines.extend([
                "",
                "=" * 60,
            ])

            return federal_summary + "\n" + state_summary + "\n".join(combined_lines)

        return federal_summary

    def export_to_json(self, tax_return: TaxReturn) -> Dict[str, Any]:
        """Export tax return to JSON format"""
        form_1040 = self.generate_form_1040(tax_return)
        
        return {
            "tax_year": tax_return.tax_year,
            "form_1040": form_1040,
            "taxpayer": {
                "first_name": tax_return.taxpayer.first_name,
                "last_name": tax_return.taxpayer.last_name,
                "filing_status": tax_return.taxpayer.filing_status.value,
                "dependents_count": len(tax_return.taxpayer.dependents),
            },
            "calculations": {
                "total_income": tax_return.income.get_total_income(),
                "adjusted_gross_income": tax_return.adjusted_gross_income,
                "taxable_income": tax_return.taxable_income,
                "federal_tax_liability": tax_return.tax_liability,
                "total_credits": tax_return.total_credits,
                "total_payments": tax_return.total_payments,
                "federal_refund_or_owed": tax_return.refund_or_owed,
                "state_tax_liability": tax_return.state_tax_liability,
                "state_refund_or_owed": tax_return.state_refund_or_owed,
                "combined_tax_liability": tax_return.combined_tax_liability,
                "combined_refund_or_owed": tax_return.combined_refund_or_owed,
            },
            "state_tax": tax_return.state_tax_result,
        }
