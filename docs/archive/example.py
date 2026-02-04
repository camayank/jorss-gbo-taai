#!/usr/bin/env python3
"""
Example script showing how to use the Tax Agent programmatically
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from models.tax_return import TaxReturn
from models.taxpayer import TaxpayerInfo, FilingStatus
from models.income import Income, W2Info
from models.deductions import Deductions
from models.credits import TaxCredits
from calculator.tax_calculator import TaxCalculator
from forms.form_generator import FormGenerator


def example_single_taxpayer():
    """Example: Single taxpayer with W-2 income"""
    print("Example 1: Single Taxpayer with W-2 Income")
    print("=" * 60)
    
    # Create tax return
    tax_return = TaxReturn(
        taxpayer=TaxpayerInfo(
            first_name="John",
            last_name="Doe",
            filing_status=FilingStatus.SINGLE,
            is_over_65=False,
            is_blind=False
        ),
        income=Income(
            w2_forms=[
                W2Info(
                    employer_name="ABC Company",
                    wages=75000.0,
                    federal_tax_withheld=12000.0
                )
            ]
        ),
        deductions=Deductions(use_standard_deduction=True),
        credits=TaxCredits()
    )
    
    # Calculate
    calculator = TaxCalculator()
    calculator.calculate_complete_return(tax_return)
    
    # Display results
    form_generator = FormGenerator()
    summary = form_generator.generate_summary(tax_return)
    print(summary)
    print()


def example_married_joint():
    """Example: Married filing jointly with children"""
    print("Example 2: Married Filing Jointly with Children")
    print("=" * 60)
    
    from models.taxpayer import Dependent
    
    tax_return = TaxReturn(
        taxpayer=TaxpayerInfo(
            first_name="Jane",
            last_name="Smith",
            filing_status=FilingStatus.MARRIED_JOINT,
            spouse_first_name="John",
            spouse_last_name="Smith",
            dependents=[
                Dependent(name="Alice Smith", age=8, relationship="daughter", lives_with_you=True),
                Dependent(name="Bob Smith", age=5, relationship="son", lives_with_you=True)
            ]
        ),
        income=Income(
            w2_forms=[
                W2Info(
                    employer_name="Tech Corp",
                    wages=95000.0,
                    federal_tax_withheld=15000.0
                ),
                W2Info(
                    employer_name="Design Inc",
                    wages=65000.0,
                    federal_tax_withheld=9000.0
                )
            ]
        ),
        deductions=Deductions(use_standard_deduction=True),
        credits=TaxCredits(
            eitc_eligible=True,
            child_tax_credit_children=2
        )
    )
    
    # Calculate
    calculator = TaxCalculator()
    calculator.calculate_complete_return(tax_return)
    
    # Display results
    form_generator = FormGenerator()
    summary = form_generator.generate_summary(tax_return)
    print(summary)
    print()


def example_itemized_deductions():
    """Example: Taxpayer with itemized deductions"""
    print("Example 3: Itemized Deductions")
    print("=" * 60)
    
    from models.deductions import ItemizedDeductions
    
    tax_return = TaxReturn(
        taxpayer=TaxpayerInfo(
            first_name="Robert",
            last_name="Johnson",
            filing_status=FilingStatus.SINGLE
        ),
        income=Income(
            w2_forms=[
                W2Info(
                    employer_name="Finance LLC",
                    wages=120000.0,
                    federal_tax_withheld=22000.0
                )
            ],
            interest_income=5000.0,
            dividend_income=3000.0
        ),
        deductions=Deductions(
            use_standard_deduction=False,
            itemized=ItemizedDeductions(
                state_local_income_tax=8000.0,
                real_estate_tax=5000.0,
                mortgage_interest=12000.0,
                charitable_cash=5000.0
            )
        ),
        credits=TaxCredits()
    )
    
    # Calculate
    calculator = TaxCalculator()
    calculator.calculate_complete_return(tax_return)
    
    # Display results
    form_generator = FormGenerator()
    summary = form_generator.generate_summary(tax_return)
    print(summary)
    print()


if __name__ == "__main__":
    example_single_taxpayer()
    example_married_joint()
    example_itemized_deductions()
    
    print("=" * 60)
    print("All examples completed!")
    print("=" * 60)
