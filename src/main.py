"""
Main application entry point for US Tax Return Preparation Agent
"""
import os
import sys
from dotenv import load_dotenv

from agent.tax_agent import TaxAgent
from calculator.tax_calculator import TaxCalculator
from forms.form_generator import FormGenerator
from parser.document_parser import DocumentParser

# Load environment variables
load_dotenv()


def main():
    """Main interactive application"""
    print("=" * 60)
    print("US TAX RETURN PREPARATION AGENT")
    print("Tax Year 2025")
    print("=" * 60)
    print()
    
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not found in environment variables.")
        print("Please set your OpenAI API key in a .env file or environment variable.")
        sys.exit(1)
    
    # Initialize components
    try:
        agent = TaxAgent()
        calculator = TaxCalculator()
        form_generator = FormGenerator()
        parser = DocumentParser()
    except Exception as e:
        print(f"Error initializing agent: {e}")
        sys.exit(1)
    
    # Start conversation
    print(agent.start_conversation())
    print()
    
    # Interactive loop
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            # Check for special commands
            if user_input.lower() in ['quit', 'exit', 'done']:
                print("\nThank you for using the Tax Preparation Agent!")
                break
            
            if user_input.lower() == 'calculate':
                # Calculate tax return
                tax_return = agent.get_tax_return()
                if tax_return and agent.is_complete():
                    calculator.calculate_complete_return(tax_return)
                    summary = form_generator.generate_summary(tax_return)
                    print("\n" + summary)
                    print("\nWould you like to continue? (Type 'quit' to exit)")
                else:
                    print("\nNot enough information collected yet. Please continue answering questions.")
                continue
            
            if user_input.lower() == 'summary':
                # Show current summary
                tax_return = agent.get_tax_return()
                if tax_return:
                    if agent.is_complete():
                        calculator.calculate_complete_return(tax_return)
                    summary = form_generator.generate_summary(tax_return)
                    print("\n" + summary)
                else:
                    print("\nNo information collected yet.")
                continue
            
            # Process user message
            response = agent.process_message(user_input)
            print(f"\nAgent: {response}\n")
            
            # Check if we have enough info and suggest calculation
            if agent.is_complete():
                tax_return = agent.get_tax_return()
                if tax_return:
                    calculator.calculate_complete_return(tax_return)
                    print("\n" + "=" * 60)
                    print("You've provided enough information for a preliminary calculation.")
                    print("Type 'calculate' to see your tax summary, or continue with more details.")
                    print("=" * 60 + "\n")
        
        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        except Exception as e:
            print(f"\nError: {e}")
            print("Please try again or type 'quit' to exit.\n")


def demo_mode():
    """Demo mode with sample data"""
    print("=" * 60)
    print("DEMO MODE - Sample Tax Return")
    print("=" * 60)
    print()
    
    from models.tax_return import TaxReturn
    from models.taxpayer import TaxpayerInfo, FilingStatus
    from models.income import Income, W2Info
    from models.deductions import Deductions
    from models.credits import TaxCredits
    
    # Create sample tax return
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
    
    # Generate summary
    form_generator = FormGenerator()
    summary = form_generator.generate_summary(tax_return)
    print(summary)
    
    # Export to JSON
    json_data = form_generator.export_to_json(tax_return)
    print("\nJSON Export (sample):")
    import json
    print(json.dumps(json_data, indent=2))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo_mode()
    else:
        main()
