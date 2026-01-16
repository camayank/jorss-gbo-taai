# US Tax Return Preparation Agent - Project Summary

## Overview

A comprehensive AI-powered agent system for preparing US tax returns (Form 1040) for tax year 2025. The system guides users through data collection, calculates tax liability, and generates completed tax forms.

## Architecture

### Core Components

1. **Data Models** (`src/models/`)
   - `TaxpayerInfo`: Personal information, filing status, dependents
   - `Income`: W-2s, 1099s, and other income sources
   - `Deductions`: Standard and itemized deductions
   - `TaxCredits`: EITC, child tax credit, and other credits
   - `TaxReturn`: Complete tax return data structure

2. **Tax Calculator** (`src/calculator/`)
   - Progressive tax bracket calculations (2024 rates)
   - Supports all filing statuses
   - Calculates AGI, taxable income, and tax liability

3. **AI Agent** (`src/agent/`)
   - LangChain-based conversational interface
   - Multi-stage data collection (personal info → income → deductions → credits)
   - Intelligent prompting and validation

4. **Document Parser** (`src/parser/`)
   - PDF and image parsing for W-2 and 1099 forms
   - OCR support via Tesseract
   - Structured data extraction

5. **Form Generator** (`src/forms/`)
   - Generates Form 1040 data structure
   - Human-readable summaries
   - JSON export functionality

## Features

✅ **Conversational Data Collection**
- Natural language interaction
- Step-by-step guidance
- Information validation

✅ **Tax Calculations**
- 2024 federal tax brackets
- Standard and itemized deductions
- Tax credits (EITC, Child Tax Credit)
- Refund/amount owed calculations

✅ **Document Processing**
- W-2 form parsing
- 1099 form parsing
- OCR for scanned documents

✅ **Form Generation**
- Form 1040 data structure
- Detailed tax summaries
- JSON export

## File Structure

```
Jorss-Gbo/
├── src/
│   ├── models/          # Data models
│   ├── calculator/      # Tax calculation engine
│   ├── agent/           # AI agent
│   ├── parser/          # Document parsing
│   ├── forms/           # Form generation
│   └── main.py          # Application entry point
├── run.py               # Main execution script
├── example.py           # Example usage
├── requirements.txt     # Dependencies
├── README.md            # Documentation
├── USAGE.md             # Usage guide
└── .gitignore          # Git ignore rules
```

## Key Technologies

- **LangChain**: AI agent framework
- **OpenAI GPT-4**: Language model for conversation
- **Pydantic**: Data validation and models
- **pdfplumber**: PDF parsing
- **pytesseract**: OCR for images
- **Python 3.8+**: Core language

## Tax Year Configuration

Currently configured for **Tax Year 2025** (filing in 2026):
- 2025 tax brackets (inflation-adjusted)
- 2025 standard deduction amounts ($15,000 single, $30,000 married joint)
- 2025 credit amounts (EITC, Child Tax Credit $2,200 per child)
- 2025 phaseout thresholds

## Usage Modes

1. **Interactive Mode**: `python run.py`
   - Conversational agent guides user through data collection

2. **Demo Mode**: `python run.py --demo`
   - Shows example calculations without API key

3. **Programmatic**: `python example.py`
   - Demonstrates programmatic usage

## Important Considerations

⚠️ **Legal & Compliance**
- This is a development/educational tool
- Not a substitute for professional tax advice
- Users should review all calculations
- Consult tax professionals for complex situations
- Ensure compliance with IRS regulations

⚠️ **Accuracy**
- Tax laws change annually
- Some calculations are simplified
- Complex scenarios may require additional schedules
- State taxes not included (federal only)

⚠️ **Security**
- SSN and sensitive data should be handled securely
- No data persistence implemented (add for production)
- Encryption recommended for production use

## Future Enhancements

Potential improvements:
- [ ] State tax calculations
- [ ] Additional schedules (Schedule A, C, D, etc.)
- [ ] IRS e-file integration
- [ ] Data persistence and user accounts
- [ ] Enhanced document parsing accuracy
- [ ] Multi-year support
- [ ] Tax planning features
- [ ] Audit trail and compliance features

## Testing

Run examples to verify functionality:
```bash
python example.py
```

## Dependencies

See `requirements.txt` for complete list. Key dependencies:
- langchain, langchain-openai
- openai
- pydantic
- pdfplumber, pytesseract
- python-dotenv

## License

MIT License - Use at your own risk for tax preparation purposes.
