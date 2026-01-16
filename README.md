# US Tax Return Preparation Agent

An AI-powered agent that helps users prepare their US tax returns by collecting information, calculating taxes, and generating completed tax forms.

## Features

- **Intelligent Data Collection**: Conversational interface to gather taxpayer information
- **Document Processing**: Parse W-2s, 1099s, and other tax documents
- **Tax Calculation**: Automated calculation of federal tax liability, deductions, and credits
- **Form Generation**: Generate completed Form 1040 and supporting schedules
- **Validation**: Error checking and completeness verification

## Project Structure

```
├── src/
│   ├── models/          # Tax data models
│   ├── calculator/      # Tax calculation engine
│   ├── parser/          # Document parsing utilities
│   ├── agent/           # AI agent and conversation flow
│   ├── forms/           # Tax form generation
│   └── main.py          # Application entry point
├── tests/               # Unit tests
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
cp .env.example .env
# Add your OpenAI API key to .env:
# OPENAI_API_KEY=your_openai_api_key_here
```

3. Run the agent:
```bash
python run.py
```

Or try the demo mode (no API key required):
```bash
python run.py --demo
```

Or run examples:
```bash
python example.py
```

## Web UI

Run the browser UI:

```bash
python run_web.py
```

Then open `http://127.0.0.1:8000` in your browser.

## Usage

The agent will guide you through a conversation to collect:
- Personal information (name, SSN, filing status, dependents)
- Income sources (W-2 wages, 1099 income, interest, dividends)
- Deductions (itemized or standard)
- Credits (EITC, child tax credit, etc.)
- Other relevant tax information

## Important Notes

⚠️ **This is a development tool. For actual tax filing:**
- Review all calculations carefully
- Consult with a tax professional for complex situations
- Ensure compliance with IRS regulations
- This tool does not replace professional tax advice

## Tax Year

Currently configured for **Tax Year 2025** (filing in 2026). Update tax brackets and rules annually.

## License

MIT License - Use at your own risk for tax preparation purposes.
