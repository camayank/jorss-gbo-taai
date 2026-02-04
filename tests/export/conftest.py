"""
Pytest fixtures for export functionality tests.

Provides mock data for testing:
- Tax return data
- Taxpayer information
- Income records
- PDF generation
"""

import pytest
from datetime import datetime, date
from uuid import uuid4
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class MockTaxpayer:
    """Mock taxpayer data for testing."""
    taxpayer_id: str
    first_name: str
    last_name: str
    ssn_last_four: str = "1234"
    filing_status: str = "single"
    address: str = "123 Main St, City, ST 12345"
    email: str = "taxpayer@example.com"
    phone: str = "555-123-4567"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def masked_ssn(self) -> str:
        return f"XXX-XX-{self.ssn_last_four}"


@dataclass
class MockW2:
    """Mock W-2 data for testing."""
    employer_name: str
    employer_ein: str
    wages: float
    federal_withholding: float
    social_security_wages: float
    social_security_withholding: float
    medicare_wages: float
    medicare_withholding: float
    state_code: str = "CA"
    state_wages: float = 0
    state_withholding: float = 0


@dataclass
class MockIncome:
    """Mock income record for testing."""
    income_type: str
    amount: float
    source: str
    description: str = ""


@dataclass
class MockTaxReturn:
    """Mock tax return data for testing."""
    return_id: str
    tax_year: int
    filing_status: str
    status: str = "draft"
    total_income: float = 0
    adjusted_gross_income: float = 0
    taxable_income: float = 0
    total_tax: float = 0
    total_payments: float = 0
    refund_or_owed: float = 0
    is_amended: bool = False
    amendment_number: int = 0
    taxpayer: MockTaxpayer = None
    w2_records: List[MockW2] = field(default_factory=list)
    income_records: List[MockIncome] = field(default_factory=list)
    state_returns: List[Dict] = field(default_factory=list)


@pytest.fixture
def mock_taxpayer():
    """Create a mock taxpayer."""
    return MockTaxpayer(
        taxpayer_id=str(uuid4()),
        first_name="John",
        last_name="Smith",
        ssn_last_four="5678",
        filing_status="single",
        address="456 Oak Ave, Springfield, IL 62701",
        email="john.smith@example.com",
        phone="555-987-6543",
    )


@pytest.fixture
def mock_w2():
    """Create a mock W-2."""
    return MockW2(
        employer_name="Acme Corporation",
        employer_ein="12-3456789",
        wages=75000.00,
        federal_withholding=12000.00,
        social_security_wages=75000.00,
        social_security_withholding=4650.00,
        medicare_wages=75000.00,
        medicare_withholding=1087.50,
        state_code="IL",
        state_wages=75000.00,
        state_withholding=3750.00,
    )


@pytest.fixture
def mock_income_record():
    """Create a mock income record."""
    return MockIncome(
        income_type="1099-INT",
        amount=500.00,
        source="First National Bank",
        description="Interest income",
    )


@pytest.fixture
def mock_tax_return(mock_taxpayer, mock_w2, mock_income_record):
    """Create a complete mock tax return."""
    return MockTaxReturn(
        return_id=str(uuid4()),
        tax_year=2025,
        filing_status="single",
        status="completed",
        total_income=75500.00,
        adjusted_gross_income=75500.00,
        taxable_income=61100.00,  # After standard deduction
        total_tax=9500.00,
        total_payments=12000.00,
        refund_or_owed=2500.00,  # Refund
        is_amended=False,
        amendment_number=0,
        taxpayer=mock_taxpayer,
        w2_records=[mock_w2],
        income_records=[mock_income_record],
        state_returns=[{
            "state_code": "IL",
            "state_agi": 75500.00,
            "state_tax": 3750.00,
            "state_withholding": 3750.00,
            "state_refund_or_owed": 0,
        }],
    )


@pytest.fixture
def mock_draft_return(mock_taxpayer):
    """Create a mock draft (incomplete) tax return."""
    return MockTaxReturn(
        return_id=str(uuid4()),
        tax_year=2025,
        filing_status="single",
        status="draft",
        total_income=0,
        adjusted_gross_income=0,
        taxable_income=0,
        total_tax=0,
        total_payments=0,
        refund_or_owed=0,
        is_amended=False,
        amendment_number=0,
        taxpayer=mock_taxpayer,
        w2_records=[],
        income_records=[],
        state_returns=[],
    )


@pytest.fixture
def mock_amended_return(mock_tax_return):
    """Create a mock amended tax return."""
    amended = MockTaxReturn(
        return_id=str(uuid4()),
        tax_year=mock_tax_return.tax_year,
        filing_status=mock_tax_return.filing_status,
        status="completed",
        total_income=80000.00,  # Corrected amount
        adjusted_gross_income=80000.00,
        taxable_income=65600.00,
        total_tax=10200.00,
        total_payments=12000.00,
        refund_or_owed=1800.00,  # Reduced refund
        is_amended=True,
        amendment_number=1,
        taxpayer=mock_tax_return.taxpayer,
        w2_records=mock_tax_return.w2_records,
        income_records=mock_tax_return.income_records,
        state_returns=mock_tax_return.state_returns,
    )
    return amended


@pytest.fixture
def mock_multi_state_return(mock_taxpayer):
    """Create a mock return with multiple state filings."""
    return MockTaxReturn(
        return_id=str(uuid4()),
        tax_year=2025,
        filing_status="single",
        status="completed",
        total_income=100000.00,
        adjusted_gross_income=100000.00,
        taxable_income=85600.00,
        total_tax=15000.00,
        total_payments=18000.00,
        refund_or_owed=3000.00,
        is_amended=False,
        taxpayer=mock_taxpayer,
        state_returns=[
            {
                "state_code": "CA",
                "state_agi": 60000.00,
                "state_tax": 3600.00,
                "state_withholding": 4000.00,
                "state_refund_or_owed": 400.00,
            },
            {
                "state_code": "NY",
                "state_agi": 40000.00,
                "state_tax": 2400.00,
                "state_withholding": 2500.00,
                "state_refund_or_owed": 100.00,
            },
        ],
    )
