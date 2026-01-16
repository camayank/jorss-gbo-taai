# US Tax Return Preparation System

A comprehensive tax preparation system for US federal and state income taxes. Supports Tax Year 2025 with full calculation engines, 25+ IRS forms, and all 50 states + DC.

[![Tests](https://img.shields.io/badge/tests-1557%20passing-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.8+-blue)]()
[![Tax Year](https://img.shields.io/badge/tax%20year-2025-orange)]()

## Features

### Federal Tax Calculation
- **Progressive tax brackets** for all filing statuses (Single, MFJ, MFS, HOH, QSS)
- **Standard and itemized deductions** with automatic optimization
- **Alternative Minimum Tax (AMT)** calculation (Form 6251)
- **Qualified Business Income (QBI)** deduction (Form 8995)
- **Estimated tax penalty** calculation (Form 2210)

### Supported IRS Forms

| Category | Forms |
|----------|-------|
| **Core** | Form 1040, Form 1040-X (Amended) |
| **Schedules** | Schedule A (Itemized), B (Interest/Dividends), C (Business), D (Capital Gains), E (Rental/K-1), F (Farm), H (Household Employment) |
| **Income** | Form 8949 (Capital Asset Sales), Form 6781 (Section 1256 Contracts), Form 8814 (Parent's Election) |
| **Retirement** | Form 8606 (Nondeductible IRAs), Form 5329 (Retirement Penalties), Form 8889 (HSA) |
| **Credits** | Form 8801 (Prior Year AMT Credit), Form 1116 (Foreign Tax Credit) |
| **International** | Form 2555 (Foreign Earned Income), Form 5471 (Foreign Corporation) |
| **Real Estate** | Form 4797 (Business Property Sales), Form 6252 (Installment Sales), Form 8582 (Passive Activity Loss) |
| **Investment** | Form 4952 (Investment Interest Expense), Form 8615 (Kiddie Tax) |
| **Other** | Form 2210 (Estimated Tax Penalty), Form 8995 (QBI Deduction) |

### Tax Credits
- Child Tax Credit / Additional Child Tax Credit
- Earned Income Tax Credit (EITC)
- Child and Dependent Care Credit
- Education Credits (American Opportunity, Lifetime Learning)
- Retirement Savings Contributions Credit (Saver's Credit)
- Foreign Tax Credit
- Residential Energy Credits
- Clean Vehicle Credit (EV)
- Adoption Credit
- Premium Tax Credit (ACA)
- Work Opportunity Tax Credit (WOTC)
- Small Employer Health Insurance Credit
- Disabled Access Credit

### State Tax Calculators

All 50 states + DC supported with state-specific rules:

| Type | States |
|------|--------|
| **No Income Tax** | AK, FL, NV, NH, SD, TN, TX, WA, WY |
| **Flat Tax** | CO, IL, IN, KY, MA, MI, NC, PA, UT |
| **Progressive** | CA, NY, NJ, and 28 others |
| **With Surtax** | MA (millionaire tax), NJ (millionaire tax) |
| **Local Tax** | OH, NY (NYC/Yonkers), MD, PA localities |

### Additional Features
- **Document parsing** for W-2s, 1099s (PDF/image with OCR)
- **AI-powered conversational agent** for guided data collection
- **Web interface** for browser-based preparation
- **Export** to JSON, PDF summary
- **Validation** with IRS compliance checks
- **Audit support** with computation statements

## Installation

### Requirements
- Python 3.8+
- pip package manager

### Setup

```bash
# Clone the repository
git clone https://github.com/camayank/jorss-gbo-taai.git
cd jorss-gbo-taai

# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your API key (for AI agent features)
OPENAI_API_KEY=your_openai_api_key_here
```

## Usage

### Command Line

```bash
# Run interactive agent
python run.py

# Run in demo mode (no API key required)
python run.py --demo

# Run example calculations
python example.py
```

### Web Interface

```bash
python run_web.py
# Open http://127.0.0.1:8000 in your browser
```

### Programmatic Usage

```python
from models.tax_return import TaxReturn
from models.taxpayer import TaxpayerInfo, FilingStatus
from models.income import Income, W2Info
from models.deductions import Deductions
from models.credits import TaxCredits
from calculator.engine import TaxCalculationEngine

# Create a tax return
tax_return = TaxReturn(
    tax_year=2025,
    taxpayer=TaxpayerInfo(
        first_name="John",
        last_name="Doe",
        filing_status=FilingStatus.SINGLE,
        state="CA",
    ),
    income=Income(
        w2_forms=[
            W2Info(
                employer_name="Acme Corp",
                wages=85000.0,
                federal_tax_withheld=12000.0,
                state_tax_withheld=4500.0,
                state_code="CA",
            )
        ],
    ),
    deductions=Deductions(use_standard_deduction=True),
    credits=TaxCredits(),
    state_of_residence="CA",
)

# Calculate taxes
engine = TaxCalculationEngine(tax_year=2025)
breakdown = engine.calculate(tax_return)

# View results
print(f"Taxable Income: ${breakdown.taxable_income:,.2f}")
print(f"Federal Tax: ${breakdown.total_tax:,.2f}")
print(f"Refund/Owed: ${breakdown.refund_or_owed:,.2f}")
```

### State Tax Calculation

```python
from calculator.state.state_engine import StateTaxEngine

# Calculate state taxes
state_engine = StateTaxEngine(tax_year=2025)
state_breakdown = state_engine.calculate(tax_return)

if state_breakdown:
    print(f"State: {state_breakdown.state_code}")
    print(f"State Tax: ${state_breakdown.state_tax_after_credits:,.2f}")
```

## Project Structure

```
jorss-gbo-taai/
├── src/
│   ├── models/              # Data models
│   │   ├── taxpayer.py      # TaxpayerInfo, FilingStatus, Dependent
│   │   ├── income.py        # Income, W2Info, 1099 forms, Schedules
│   │   ├── deductions.py    # Standard/Itemized deductions
│   │   ├── credits.py       # All tax credit models
│   │   ├── tax_return.py    # TaxReturn container
│   │   ├── schedule_*.py    # Schedule A, B, C, D, E, F models
│   │   └── form_*.py        # IRS form models (1116, 2555, etc.)
│   │
│   ├── calculator/          # Tax calculation engines
│   │   ├── engine.py        # Main federal tax engine
│   │   ├── tax_year_config.py  # 2025 brackets, rates, limits
│   │   ├── qbi_calculator.py   # QBI deduction calculator
│   │   └── state/           # State tax calculators
│   │       ├── state_engine.py
│   │       ├── state_registry.py
│   │       └── configs/state_2025/  # 42 state configs
│   │
│   ├── agent/               # AI conversational agent
│   ├── parser/              # Document parsing (W-2, 1099)
│   ├── forms/               # Form generation
│   ├── export/              # PDF/JSON export
│   ├── validation/          # Input validation
│   ├── audit/               # Audit trail & compliance
│   └── web/                 # Web interface
│
├── tests/                   # Test suite (1557 tests)
│   ├── test_*.py            # Federal tax tests
│   └── state/               # State calculator tests
│
├── docs/                    # Additional documentation
├── data/                    # Reference data files
├── example.py               # Usage examples
├── run.py                   # CLI entry point
├── run_web.py               # Web server entry point
└── requirements.txt         # Python dependencies
```

## Testing

```bash
# Run all tests
PYTHONPATH=".:src" pytest tests/ -v

# Run specific test file
PYTHONPATH=".:src" pytest tests/test_brackets.py -v

# Run state tax tests
PYTHONPATH=".:src" pytest tests/state/ -v

# Run with coverage
PYTHONPATH=".:src" pytest tests/ --cov=src --cov-report=html
```

**Current test coverage:** 1557 tests passing

## Tax Year 2025 Configuration

| Item | Single | Married Filing Jointly |
|------|--------|------------------------|
| Standard Deduction | $15,000 | $30,000 |
| Top Bracket (37%) | $626,350+ | $751,600+ |
| Child Tax Credit | $2,200/child | $2,200/child |
| EITC (max, 3+ children) | ~$8,046 | ~$8,046 |
| AMT Exemption | $88,100 | $137,000 |

## Form 2210: Estimated Tax Penalty

The system calculates estimated tax underpayment penalties per IRS rules:

- **Safe Harbor**: No penalty if payments >= min(90% current year, 100%/110% prior year)
- **Threshold**: $1,000 minimum underpayment for penalty to apply
- **Rate**: 8% annual rate (2025)
- **Farmer/Fisherman**: 66⅔% safe harbor exception

## Important Disclaimers

> **This is a development/educational tool.**

- Review all calculations carefully before filing
- Consult a qualified tax professional for complex situations
- Tax laws change annually - verify current IRS rules
- This tool does not replace professional tax advice
- Not affiliated with or endorsed by the IRS

## Security Considerations

- SSN and sensitive data should be encrypted in production
- No data persistence by default (add database for production)
- API keys should be stored securely in environment variables
- Consider audit logging for compliance requirements

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-form`)
3. Add tests for new functionality
4. Ensure all tests pass (`pytest tests/`)
5. Submit a pull request

## License

MIT License - See [LICENSE](LICENSE) for details.

Use at your own risk for tax preparation purposes.

## Acknowledgments

- IRS Publication 17 and form instructions
- State revenue department documentation
- Tax policy research organizations
