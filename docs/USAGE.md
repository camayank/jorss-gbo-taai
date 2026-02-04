# Usage Guide

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Up Environment**
   ```bash
   cp .env.example .env
   # Edit .env and add your OpenAI API key:
   # OPENAI_API_KEY=your_key_here
   ```

3. **Run the Agent**
   ```bash
   python run.py
   ```

4. **Try Demo Mode** (no API key needed for demo)
   ```bash
   python run.py --demo
   ```

5. **Run the Web UI**
   ```bash
   python run_web.py
   ```
   Then open `http://127.0.0.1:8000` in your browser.

## Interactive Mode

The agent will guide you through collecting:
- Personal information (name, SSN, filing status)
- Income sources (W-2s, 1099s, other income)
- Deductions (standard or itemized)
- Credits (EITC, child tax credit, etc.)

**Note:** This agent is configured for **Tax Year 2025** (filing in 2026).

### Commands

- `calculate` - Calculate and display tax summary
- `summary` - Show current tax return summary
- `quit` or `exit` - Exit the application

## Example Conversation

```
Agent: Hello! I'm here to help you prepare your 2025 US tax return.
       What is your first name?

You: John

Agent: What is your last name?

You: Doe

Agent: What is your filing status? (single, married joint, married separate, head of household)

You: single

Agent: Do you have any W-2 forms?

You: yes

Agent: What is the name of your employer?

You: ABC Company

Agent: What were your total wages (Box 1)?

You: 75000

Agent: How much federal tax was withheld (Box 2)?

You: 12000

You: calculate

Agent: [Displays tax summary]
```

## Document Upload

To parse W-2 or 1099 forms from PDF/images, use the document parser.
Make sure `src/` is on your `PYTHONPATH`, for example:

```bash
PYTHONPATH=".:src" python your_script.py
```

```python
from parser.document_parser import DocumentParser

parser = DocumentParser()
w2_info = parser.parse_w2("path/to/w2.pdf")
```

## Programmatic Usage

Ensure `src/` is on your `PYTHONPATH` when running these examples.

```python
from agent.tax_agent import TaxAgent
from calculator.tax_calculator import TaxCalculator
from forms.form_generator import FormGenerator

# Initialize
agent = TaxAgent(api_key="your_key")
calculator = TaxCalculator()
form_generator = FormGenerator()

# Collect information
agent.start_conversation()
response = agent.process_message("My name is John Doe")

# Calculate
tax_return = agent.get_tax_return()
calculator.calculate_complete_return(tax_return)

# Generate forms
summary = form_generator.generate_summary(tax_return)
form_data = form_generator.generate_form_1040(tax_return)
json_export = form_generator.export_to_json(tax_return)
```

## Important Notes

⚠️ **This is a development tool for educational purposes.**

- Review all calculations carefully
- Consult with a tax professional for complex situations
- Ensure compliance with IRS regulations
- This tool does not replace professional tax advice
- Tax laws change annually - verify calculations for your specific tax year

## Tax Year

Currently configured for **Tax Year 2025** (filing in 2026). Tax brackets, standard deductions, and credit amounts have been updated for 2025.
