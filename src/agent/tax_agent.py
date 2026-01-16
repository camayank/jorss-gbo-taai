"""
AI Agent for tax return preparation
Uses OpenAI to guide users through tax information collection
"""
import os
from typing import Dict, Any, Optional, List
from openai import OpenAI

from models.tax_return import TaxReturn
from models.taxpayer import TaxpayerInfo, FilingStatus, Dependent
from models.income import Income, W2Info, Form1099Info
from models.deductions import Deductions, ItemizedDeductions
from models.credits import TaxCredits


class TaxAgent:
    """AI agent that guides users through tax return preparation"""

    def __init__(self, api_key: Optional[str] = None):
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY environment variable.")

        self.client = OpenAI(api_key=api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o")

        self.messages: List[Dict[str, str]] = []
        self.tax_return: Optional[TaxReturn] = None
        self.collection_stage = "personal_info"  # personal_info, income, deductions, credits, review

        self._setup_system_prompt()

    def _setup_system_prompt(self):
        """Setup the system prompt for the assistant"""
        self.system_prompt = """You are a helpful US tax preparation assistant for Tax Year 2025. Your goal is to collect
all necessary information to prepare a US tax return (Form 1040).

You should:
1. Ask questions clearly and one at a time
2. Be friendly and professional
3. Explain tax terms in simple language when needed
4. Validate information when possible
5. Guide users through the process step by step

Collection stages:
- personal_info: Name, SSN, filing status, address
- income: W-2 wages, 1099 income, interest, dividends, capital gains
- deductions: Standard vs itemized, mortgage interest, charitable contributions, SALT
- credits: Child tax credit, education credits, energy credits
- review: Summary and final review

Keep responses concise. Ask one question at a time. Be helpful and encouraging."""

        self.messages = [{"role": "system", "content": self.system_prompt}]

    def start_conversation(self) -> str:
        """Initialize the tax preparation conversation"""
        greeting = """Hello! I'm here to help you prepare your 2025 US tax return.

I'll guide you through the process step by step, collecting information about:
- Your personal information
- Income (W-2s, 1099s, investments)
- Deductions and credits

Let's get started! What is your first name?"""

        self.messages.append({"role": "assistant", "content": greeting})
        return greeting

    def process_message(self, user_input: str) -> str:
        """Process user input and return agent response"""
        # Add user message to history
        self.messages.append({"role": "user", "content": user_input})

        # Add context about collection stage
        context = f"\n\n[Current stage: {self.collection_stage}]"
        if self.tax_return:
            context += f"\n[Collected: {self._get_collected_info_summary()}]"

        # Create messages with context
        messages_with_context = self.messages.copy()
        messages_with_context[-1]["content"] = user_input + context

        # Get response from OpenAI
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages_with_context,
                temperature=0.3,
                max_tokens=500
            )
            assistant_message = response.choices[0].message.content
        except Exception as e:
            assistant_message = f"I apologize, but I encountered an issue. Let's continue - {str(e)[:100]}"

        # Add assistant response to history
        self.messages.append({"role": "assistant", "content": assistant_message})

        # Try to extract structured data from conversation
        self._extract_and_store_info(user_input)

        # Update collection stage if needed
        self._update_collection_stage()

        return assistant_message

    def _get_collected_info_summary(self) -> str:
        """Get summary of information collected so far"""
        if not self.tax_return:
            return "No information collected yet."

        summary = []

        if self.tax_return.taxpayer.first_name:
            summary.append(f"Name: {self.tax_return.taxpayer.first_name} {self.tax_return.taxpayer.last_name}")
            summary.append(f"Filing Status: {self.tax_return.taxpayer.filing_status.value}")

        if self.tax_return.income.w2_forms:
            summary.append(f"W-2 forms: {len(self.tax_return.income.w2_forms)}")

        if self.tax_return.income.get_total_income() > 0:
            summary.append(f"Total Income: ${self.tax_return.income.get_total_income():,.2f}")

        return "; ".join(summary) if summary else "No information collected yet."

    def _extract_and_store_info(self, user_input: str):
        """Extract structured information from user input and store in tax return"""
        if not self.tax_return:
            # Initialize tax return with default values
            self.tax_return = TaxReturn(
                taxpayer=TaxpayerInfo(
                    first_name="",
                    last_name="",
                    filing_status=FilingStatus.SINGLE
                ),
                income=Income(),
                deductions=Deductions(),
                credits=TaxCredits()
            )

        # Simple extraction logic
        user_lower = user_input.lower().strip()

        # Extract name (first response is likely a name)
        if not self.tax_return.taxpayer.first_name and self.collection_stage == "personal_info":
            words = user_input.strip().split()
            if words and len(words[0]) > 1 and words[0].isalpha():
                self.tax_return.taxpayer.first_name = words[0].capitalize()
                if len(words) > 1 and words[-1].isalpha():
                    self.tax_return.taxpayer.last_name = words[-1].capitalize()

        # Extract filing status
        if "single" in user_lower and "married" not in user_lower:
            self.tax_return.taxpayer.filing_status = FilingStatus.SINGLE
        elif "married" in user_lower and "separate" in user_lower:
            self.tax_return.taxpayer.filing_status = FilingStatus.MARRIED_SEPARATE
        elif "married" in user_lower and ("joint" in user_lower or "together" in user_lower):
            self.tax_return.taxpayer.filing_status = FilingStatus.MARRIED_JOINT
        elif "head" in user_lower and "household" in user_lower:
            self.tax_return.taxpayer.filing_status = FilingStatus.HEAD_OF_HOUSEHOLD
        elif "widow" in user_lower or "surviving spouse" in user_lower:
            self.tax_return.taxpayer.filing_status = FilingStatus.QUALIFYING_WIDOW

        # Extract dollar amounts for income
        import re
        dollar_match = re.search(r'\$?([\d,]+(?:\.\d{2})?)', user_input)
        if dollar_match and self.collection_stage == "income":
            amount = float(dollar_match.group(1).replace(',', ''))
            if amount > 1000:  # Likely wages
                if not self.tax_return.income.w2_forms:
                    self.tax_return.income.w2_forms.append(
                        W2Info(employer_name="Employer", wages=amount, federal_tax_withheld=0)
                    )

    def _update_collection_stage(self):
        """Update the current collection stage based on progress"""
        if not self.tax_return:
            self.collection_stage = "personal_info"
            return

        taxpayer = self.tax_return.taxpayer

        if not taxpayer.first_name:
            self.collection_stage = "personal_info"
        elif not self.tax_return.income.w2_forms and self.tax_return.income.get_total_income() == 0:
            self.collection_stage = "income"
        elif self.collection_stage == "income" and self.tax_return.income.get_total_income() > 0:
            self.collection_stage = "deductions"
        elif self.collection_stage == "deductions":
            self.collection_stage = "credits"
        elif self.collection_stage == "credits":
            self.collection_stage = "review"

    def add_w2_manually(self, employer_name: str, wages: float, federal_withheld: float, **kwargs) -> bool:
        """Manually add W-2 information"""
        if not self.tax_return:
            return False

        w2 = W2Info(
            employer_name=employer_name,
            wages=wages,
            federal_tax_withheld=federal_withheld,
            **kwargs
        )
        self.tax_return.income.w2_forms.append(w2)
        return True

    def add_1099_manually(self, payer_name: str, amount: float, form_type: str = "1099-MISC", **kwargs) -> bool:
        """Manually add 1099 information"""
        if not self.tax_return:
            return False

        form_1099 = Form1099Info(
            payer_name=payer_name,
            amount=amount,
            form_type=form_type,
            **kwargs
        )
        self.tax_return.income.form_1099.append(form_1099)
        return True

    def get_tax_return(self) -> Optional[TaxReturn]:
        """Get the current tax return object"""
        return self.tax_return

    def is_complete(self) -> bool:
        """Check if enough information has been collected"""
        if not self.tax_return:
            return False

        taxpayer = self.tax_return.taxpayer
        income = self.tax_return.income

        # Minimum required: name, filing status, and some income
        has_basic_info = taxpayer.first_name and taxpayer.filing_status
        has_income = income.get_total_income() > 0

        return has_basic_info and has_income
