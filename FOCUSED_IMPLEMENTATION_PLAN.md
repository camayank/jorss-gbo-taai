# Focused Implementation Plan
## Individual Tax Filing - Core Capabilities Only

**Date**: 2026-01-22
**Scope**: Individual (1040) tax filing for USA only
**NOT in scope**: 800 forms, enterprise features, batch processing

---

## Current State Summary

### What You Already Have (95% Complete)

**Form Models**: 47 complete Pydantic models covering all individual tax forms
**Calculations**: 4,000+ lines of calculation engine code
**Coverage**: 95% of individual tax situations

### Core Forms Needed (You Have All Models)

| Form | Model Status | Calculation Status | PDF Output |
|------|--------------|-------------------|------------|
| Form 1040 | ✅ Complete | ✅ Complete | ⚠️ Basic |
| Schedule 1,2,3 | ✅ Complete | ✅ Complete | ❌ Missing |
| Schedule A (Itemized) | ✅ Complete | ✅ Complete | ⚠️ Basic |
| Schedule B (Interest/Div) | ✅ Complete | ✅ Complete | ❌ Missing |
| Schedule C (Self-Emp) | ✅ Complete | ✅ Complete | ⚠️ Basic |
| Schedule D (Cap Gains) | ✅ Complete | ✅ Complete | ❌ Missing |
| Schedule E (Rental/K-1) | ✅ Complete | ⚠️ Missing depreciation | ❌ Missing |
| Form 8949 (Transactions) | ✅ Complete | ⚠️ Aggregate only | ❌ Missing |
| Form 4562 (Depreciation) | ✅ Complete | ⚠️ Not integrated | ❌ Missing |
| Form 8995 (QBI) | ✅ Complete | ✅ Complete | ❌ Missing |
| Schedule SE | ✅ Complete | ✅ Complete | ❌ Missing |

---

## What's Actually Missing (4 Items)

### 1. Audit Trail ❌ CRITICAL
Every change must be logged for professional use.

### 2. Form 8949 Transaction Detail ❌ BROKEN
Currently asks for "short-term gains" aggregate instead of transaction-by-transaction.

### 3. K-1 Basis Tracking ❌ MISSING
S-Corp/Partnership distributions need basis tracking.

### 4. Rental Depreciation ❌ MISSING
Schedule E needs 27.5-year depreciation calculation.

### 5. Draft Form PDF Output ❌ MISSING
Generate IRS-like draft forms on demand.

---

## Implementation Plan

### Phase 1: Audit Trail (3 days)

**Goal**: Log every data change with user, timestamp, old value, new value.

**Files to Create/Modify**:
```
src/audit/
├── __init__.py
├── audit_logger.py      # Core audit logging
├── audit_models.py      # AuditEntry data model
└── audit_middleware.py  # Auto-capture changes
```

**Implementation**:

```python
# src/audit/audit_models.py
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from enum import Enum

class AuditAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    CALCULATE = "calculate"
    EXTRACT = "extract"  # OCR/AI extraction
    REVIEW = "review"    # CPA reviewed
    APPROVE = "approve"  # CPA approved

@dataclass
class AuditEntry:
    """Single audit log entry"""
    id: str                      # UUID
    session_id: str              # Tax session
    timestamp: datetime
    action: AuditAction
    entity_type: str             # e.g., "w2_wages", "filing_status"
    entity_id: Optional[str]     # Specific entity if applicable
    old_value: Any
    new_value: Any
    user_id: Optional[str]       # Who made change (None = AI)
    source: str                  # "user_input", "ocr_extraction", "ai_chat", "cpa_review"
    confidence: Optional[float]  # For AI extractions
    reason: Optional[str]        # Why change was made
    ip_address: Optional[str]
    user_agent: Optional[str]
```

```python
# src/audit/audit_logger.py
from typing import Any, Optional
from datetime import datetime
import uuid
from .audit_models import AuditEntry, AuditAction

class AuditLogger:
    """
    Log all changes to tax data for compliance and debugging.
    """

    def __init__(self, session_id: str, storage_backend=None):
        self.session_id = session_id
        self.storage = storage_backend or InMemoryAuditStorage()

    def log_change(
        self,
        action: AuditAction,
        entity_type: str,
        old_value: Any,
        new_value: Any,
        user_id: Optional[str] = None,
        source: str = "user_input",
        confidence: Optional[float] = None,
        reason: Optional[str] = None
    ) -> AuditEntry:
        """Log a single change"""
        entry = AuditEntry(
            id=str(uuid.uuid4()),
            session_id=self.session_id,
            timestamp=datetime.now(),
            action=action,
            entity_type=entity_type,
            entity_id=None,
            old_value=old_value,
            new_value=new_value,
            user_id=user_id,
            source=source,
            confidence=confidence,
            reason=reason,
            ip_address=None,
            user_agent=None
        )
        self.storage.save(entry)
        return entry

    def get_history(self, entity_type: Optional[str] = None) -> List[AuditEntry]:
        """Get audit history, optionally filtered by entity type"""
        return self.storage.get_by_session(self.session_id, entity_type)

    def get_timeline(self) -> List[AuditEntry]:
        """Get complete session timeline"""
        return self.storage.get_by_session(self.session_id)


class SQLiteAuditStorage:
    """Persist audit entries to SQLite"""

    def __init__(self, db_path: str = "audit.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT,
                old_value TEXT,
                new_value TEXT,
                user_id TEXT,
                source TEXT,
                confidence REAL,
                reason TEXT,
                ip_address TEXT,
                user_agent TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON audit_log(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_log(timestamp)")
        conn.commit()
        conn.close()

    def save(self, entry: AuditEntry):
        import sqlite3
        import json
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO audit_log VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.id,
            entry.session_id,
            entry.timestamp.isoformat(),
            entry.action.value,
            entry.entity_type,
            entry.entity_id,
            json.dumps(entry.old_value) if entry.old_value else None,
            json.dumps(entry.new_value) if entry.new_value else None,
            entry.user_id,
            entry.source,
            entry.confidence,
            entry.reason,
            entry.ip_address,
            entry.user_agent
        ))
        conn.commit()
        conn.close()
```

**Integration with Chatbot**:
```python
# In intelligent_tax_agent.py, modify _apply_extracted_entity()

def _apply_extracted_entity(self, entity: ExtractedEntity):
    # Get old value before change
    old_value = self._get_current_value(entity.entity_type)

    # Apply the change (existing code)
    # ...

    # Log the change
    self.audit_logger.log_change(
        action=AuditAction.UPDATE if old_value else AuditAction.CREATE,
        entity_type=entity.entity_type,
        old_value=old_value,
        new_value=entity.value,
        source="ai_chat" if entity.source == "conversation" else "ocr_extraction",
        confidence=entity.confidence.value
    )
```

---

### Phase 2: Form 8949 Transaction Detail (4 days)

**Goal**: Collect transaction-by-transaction capital gains data instead of aggregate.

**Current Problem**:
```
Bot: "What were your short-term capital gains?"  ❌ WRONG
User: "$5,000"
# Can't generate Form 8949 - needs individual transactions
```

**Fixed Flow**:
```
Bot: "Did you sell any stocks, bonds, or other investments in 2025?"
User: "Yes"
Bot: "Let's record each sale. First transaction:
      - Description (e.g., '100 shares AAPL')
      - Date acquired
      - Date sold
      - Proceeds (sale price)
      - Cost basis (what you paid)"
User: "100 shares Apple, bought Jan 2023, sold March 2025, sold for $18,000, cost $15,000"
Bot: "Got it! That's a long-term gain of $3,000. Any more sales?"
```

**Implementation**:

```python
# src/models/form_8949.py - Already exists, needs enhancement

@dataclass
class CapitalGainTransaction:
    """Single capital gain/loss transaction for Form 8949"""
    description: str              # "100 sh AAPL"
    date_acquired: date
    date_sold: date
    proceeds: Decimal             # Sales price
    cost_basis: Decimal           # Purchase price + fees
    adjustment_code: Optional[str] = None  # W=wash sale, B=basis reported, etc.
    adjustment_amount: Decimal = Decimal("0")

    @property
    def gain_or_loss(self) -> Decimal:
        return self.proceeds - self.cost_basis - self.adjustment_amount

    @property
    def holding_period_days(self) -> int:
        return (self.date_sold - self.date_acquired).days

    @property
    def is_long_term(self) -> bool:
        return self.holding_period_days > 365

    @property
    def is_wash_sale(self) -> bool:
        return self.adjustment_code == "W"


@dataclass
class Form8949:
    """Complete Form 8949 with all transactions"""
    transactions: List[CapitalGainTransaction] = field(default_factory=list)

    @property
    def short_term_transactions(self) -> List[CapitalGainTransaction]:
        return [t for t in self.transactions if not t.is_long_term]

    @property
    def long_term_transactions(self) -> List[CapitalGainTransaction]:
        return [t for t in self.transactions if t.is_long_term]

    @property
    def total_short_term_proceeds(self) -> Decimal:
        return sum(t.proceeds for t in self.short_term_transactions)

    @property
    def total_short_term_basis(self) -> Decimal:
        return sum(t.cost_basis for t in self.short_term_transactions)

    @property
    def total_short_term_gain_loss(self) -> Decimal:
        return sum(t.gain_or_loss for t in self.short_term_transactions)

    @property
    def total_long_term_proceeds(self) -> Decimal:
        return sum(t.proceeds for t in self.long_term_transactions)

    @property
    def total_long_term_basis(self) -> Decimal:
        return sum(t.cost_basis for t in self.long_term_transactions)

    @property
    def total_long_term_gain_loss(self) -> Decimal:
        return sum(t.gain_or_loss for t in self.long_term_transactions)
```

**Chatbot Integration**:
```python
# Add to intelligent_tax_agent.py entity types
"capital_gain_transaction",  # Single transaction

# Add extraction for transactions
def _extract_capital_gain_transaction(self, user_input: str) -> Optional[CapitalGainTransaction]:
    """Extract capital gain transaction from natural language"""
    # Use GPT to extract structured data
    extraction_prompt = """
    Extract capital gain transaction details from this text:
    "{user_input}"

    Return JSON:
    {
        "description": "100 sh AAPL",
        "date_acquired": "2023-01-15",
        "date_sold": "2025-03-20",
        "proceeds": 18000,
        "cost_basis": 15000
    }
    """
    # ... GPT extraction logic
```

**Wash Sale Detection**:
```python
def detect_wash_sales(transactions: List[CapitalGainTransaction]) -> List[CapitalGainTransaction]:
    """
    Detect wash sales: loss + repurchase within 30 days before/after
    """
    flagged = []
    for i, sale in enumerate(transactions):
        if sale.gain_or_loss >= 0:
            continue  # Only losses can be wash sales

        # Check if same security repurchased within 30 days
        for other in transactions:
            if other == sale:
                continue
            if other.description == sale.description:  # Same security
                days_apart = abs((other.date_acquired - sale.date_sold).days)
                if days_apart <= 30:
                    sale.adjustment_code = "W"
                    sale.adjustment_amount = abs(sale.gain_or_loss)
                    flagged.append(sale)
                    break

    return flagged
```

---

### Phase 3: K-1 Basis Tracking (4 days)

**Goal**: Track shareholder/partner basis to determine taxable distributions.

**Why This Matters**:
- Distributions up to basis = tax-free return of capital
- Distributions exceeding basis = taxable capital gain
- Without tracking, users may owe unexpected capital gains tax

**Implementation**:

```python
# src/calculator/k1_basis_tracker.py
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional
from datetime import date

@dataclass
class K1BasisRecord:
    """Track basis for a single K-1 entity (partnership or S-Corp)"""
    entity_name: str
    entity_type: str  # "partnership" or "s_corp"
    entity_ein: str

    # Beginning basis (from prior year)
    beginning_basis: Decimal = Decimal("0")

    # Current year changes
    capital_contributions: Decimal = Decimal("0")
    ordinary_income: Decimal = Decimal("0")       # K-1 Box 1 (partnership) or Box 1 (S-Corp)
    separately_stated_income: Decimal = Decimal("0")  # Interest, dividends, etc.
    tax_exempt_income: Decimal = Decimal("0")
    nondeductible_expenses: Decimal = Decimal("0")
    distributions: Decimal = Decimal("0")
    losses_and_deductions: Decimal = Decimal("0")

    @property
    def ending_basis(self) -> Decimal:
        """Calculate ending basis per IRS ordering rules"""
        basis = self.beginning_basis

        # Increases (in order)
        basis += self.capital_contributions
        basis += self.ordinary_income
        basis += self.separately_stated_income
        basis += self.tax_exempt_income

        # Decreases (in order, but can't go below zero)
        basis -= self.nondeductible_expenses
        basis -= self.distributions
        # Losses limited to remaining basis
        allowable_losses = min(self.losses_and_deductions, max(basis, Decimal("0")))
        basis -= allowable_losses

        return max(basis, Decimal("0"))

    @property
    def taxable_distribution(self) -> Decimal:
        """Amount of distribution that exceeds basis (taxable as capital gain)"""
        # Basis before distributions
        basis_before_dist = (
            self.beginning_basis +
            self.capital_contributions +
            self.ordinary_income +
            self.separately_stated_income +
            self.tax_exempt_income -
            self.nondeductible_expenses
        )

        excess = self.distributions - max(basis_before_dist, Decimal("0"))
        return max(excess, Decimal("0"))

    @property
    def suspended_losses(self) -> Decimal:
        """Losses that exceed basis (suspended until basis restored)"""
        # Calculate basis available for losses
        basis_for_losses = (
            self.beginning_basis +
            self.capital_contributions +
            self.ordinary_income +
            self.separately_stated_income +
            self.tax_exempt_income -
            self.nondeductible_expenses -
            self.distributions
        )
        basis_for_losses = max(basis_for_losses, Decimal("0"))

        suspended = self.losses_and_deductions - basis_for_losses
        return max(suspended, Decimal("0"))


class K1BasisTracker:
    """Track K-1 basis across multiple entities and years"""

    def __init__(self):
        self.records: List[K1BasisRecord] = []

    def add_k1(self, k1_data: dict) -> K1BasisRecord:
        """Add K-1 and calculate basis impact"""
        record = K1BasisRecord(
            entity_name=k1_data["entity_name"],
            entity_type=k1_data["entity_type"],
            entity_ein=k1_data["ein"],
            beginning_basis=Decimal(str(k1_data.get("beginning_basis", 0))),
            capital_contributions=Decimal(str(k1_data.get("contributions", 0))),
            ordinary_income=Decimal(str(k1_data.get("ordinary_income", 0))),
            separately_stated_income=Decimal(str(k1_data.get("other_income", 0))),
            distributions=Decimal(str(k1_data.get("distributions", 0))),
            losses_and_deductions=Decimal(str(k1_data.get("losses", 0)))
        )
        self.records.append(record)
        return record

    def get_total_taxable_distributions(self) -> Decimal:
        """Total capital gain from excess distributions"""
        return sum(r.taxable_distribution for r in self.records)

    def get_total_suspended_losses(self) -> Decimal:
        """Total losses suspended due to basis limitation"""
        return sum(r.suspended_losses for r in self.records)

    def generate_basis_worksheet(self) -> str:
        """Generate CPA-friendly basis worksheet"""
        output = []
        for record in self.records:
            output.append(f"""
K-1 Basis Worksheet: {record.entity_name} ({record.entity_ein})
Entity Type: {record.entity_type.upper()}
═══════════════════════════════════════════════════════════

Beginning Basis (from prior year)          ${record.beginning_basis:>12,.2f}

INCREASES:
  Capital contributions                    ${record.capital_contributions:>12,.2f}
  Ordinary business income (Box 1)         ${record.ordinary_income:>12,.2f}
  Separately stated income                 ${record.separately_stated_income:>12,.2f}
  Tax-exempt income                        ${record.tax_exempt_income:>12,.2f}
                                           ─────────────────
  Subtotal (basis before decreases)        ${(
      record.beginning_basis +
      record.capital_contributions +
      record.ordinary_income +
      record.separately_stated_income +
      record.tax_exempt_income
  ):>12,.2f}

DECREASES:
  Nondeductible expenses                   ${record.nondeductible_expenses:>12,.2f}
  Distributions                            ${record.distributions:>12,.2f}
  Losses and deductions (limited)          ${min(record.losses_and_deductions, record.ending_basis + record.losses_and_deductions):>12,.2f}
                                           ─────────────────
ENDING BASIS                               ${record.ending_basis:>12,.2f}

TAXABLE DISTRIBUTION (excess over basis)   ${record.taxable_distribution:>12,.2f}
SUSPENDED LOSSES (carry forward)           ${record.suspended_losses:>12,.2f}
""")
        return "\n".join(output)
```

---

### Phase 4: Rental Depreciation (3 days)

**Goal**: Calculate 27.5-year straight-line depreciation for residential rental property.

**Implementation**:

```python
# src/calculator/rental_depreciation.py
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from typing import Optional

@dataclass
class RentalProperty:
    """Single rental property with depreciation tracking"""
    address: str
    property_type: str  # "residential", "commercial"

    # Acquisition info
    date_acquired: date
    purchase_price: Decimal
    land_value: Decimal  # Land is NOT depreciable

    # Improvements (added to basis)
    improvements: Decimal = Decimal("0")

    # Prior depreciation (if property owned before)
    prior_depreciation: Decimal = Decimal("0")

    @property
    def depreciable_basis(self) -> Decimal:
        """Building value only (excludes land)"""
        return self.purchase_price - self.land_value + self.improvements

    @property
    def recovery_period(self) -> int:
        """IRS recovery period in years"""
        if self.property_type == "residential":
            return 27.5  # Residential rental (27.5 years)
        else:
            return 39    # Commercial (39 years)

    def calculate_annual_depreciation(self, tax_year: int) -> Decimal:
        """
        Calculate depreciation for a given tax year.
        Uses mid-month convention for real property.
        """
        # Full year depreciation
        annual_depreciation = self.depreciable_basis / Decimal(str(self.recovery_period))

        # First year: mid-month convention
        if tax_year == self.date_acquired.year:
            month_acquired = self.date_acquired.month
            # Mid-month: count from middle of acquisition month
            months_in_service = 12 - month_acquired + 0.5
            first_year_depreciation = annual_depreciation * Decimal(str(months_in_service / 12))
            return first_year_depreciation.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Check if fully depreciated
        years_owned = tax_year - self.date_acquired.year
        if years_owned > self.recovery_period:
            return Decimal("0")

        return annual_depreciation.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def calculate_accumulated_depreciation(self, through_year: int) -> Decimal:
        """Total depreciation taken through given year"""
        total = self.prior_depreciation
        for year in range(self.date_acquired.year, through_year + 1):
            total += self.calculate_annual_depreciation(year)
        return total

    @property
    def adjusted_basis(self) -> Decimal:
        """Current basis after depreciation (for sale calculations)"""
        # Would need to know current year - simplified here
        return self.depreciable_basis + self.land_value - self.prior_depreciation


class RentalDepreciationCalculator:
    """Calculate depreciation for Schedule E"""

    def __init__(self):
        self.properties: list[RentalProperty] = []

    def add_property(self, property_data: dict) -> RentalProperty:
        """Add rental property"""
        prop = RentalProperty(
            address=property_data["address"],
            property_type=property_data.get("type", "residential"),
            date_acquired=property_data["date_acquired"],
            purchase_price=Decimal(str(property_data["purchase_price"])),
            land_value=Decimal(str(property_data.get("land_value", 0))),
            improvements=Decimal(str(property_data.get("improvements", 0))),
            prior_depreciation=Decimal(str(property_data.get("prior_depreciation", 0)))
        )
        self.properties.append(prop)
        return prop

    def calculate_total_depreciation(self, tax_year: int) -> Decimal:
        """Total depreciation for all properties"""
        return sum(p.calculate_annual_depreciation(tax_year) for p in self.properties)

    def generate_depreciation_schedule(self, tax_year: int) -> str:
        """Generate depreciation report for each property"""
        output = [f"DEPRECIATION SCHEDULE - Tax Year {tax_year}\n" + "=" * 60]

        total = Decimal("0")
        for prop in self.properties:
            annual = prop.calculate_annual_depreciation(tax_year)
            total += annual

            output.append(f"""
Property: {prop.address}
Type: {prop.property_type.title()} ({prop.recovery_period}-year recovery)
Date Acquired: {prop.date_acquired}

Cost Basis Calculation:
  Purchase Price:              ${prop.purchase_price:>12,.2f}
  Less: Land Value:            ${prop.land_value:>12,.2f}
  Plus: Improvements:          ${prop.improvements:>12,.2f}
  Depreciable Basis:           ${prop.depreciable_basis:>12,.2f}

{tax_year} Depreciation:       ${annual:>12,.2f}
Accumulated Depreciation:      ${prop.calculate_accumulated_depreciation(tax_year):>12,.2f}
""")

        output.append(f"\nTOTAL DEPRECIATION (Schedule E, Line 18): ${total:>12,.2f}")
        return "\n".join(output)
```

**Chatbot Integration**:
```python
# Questions to ask when rental income detected:

RENTAL_DEPRECIATION_QUESTIONS = [
    "When did you purchase this rental property? (Date)",
    "What was the purchase price?",
    "What is the estimated land value? (Land isn't depreciable - typically 15-30% of purchase price)",
    "Have you made any improvements to the property since purchase?"
]
```

---

### Phase 5: Draft Form PDF Output (5 days)

**Goal**: Generate IRS-like draft PDFs on demand for review.

**Approach**: Use existing form models + ReportLab to generate clean draft output.

```python
# src/export/draft_form_generator.py
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from decimal import Decimal
from typing import Optional

class DraftFormGenerator:
    """Generate IRS-like draft form PDFs"""

    def __init__(self, tax_return):
        self.tax_return = tax_return
        self.styles = getSampleStyleSheet()

    def generate_form_1040_draft(self, filename: str):
        """Generate Form 1040 draft"""
        doc = SimpleDocTemplate(filename, pagesize=letter)
        elements = []

        # Header
        elements.append(Paragraph(
            "<b>DRAFT - Form 1040 - U.S. Individual Income Tax Return</b>",
            self.styles['Title']
        ))
        elements.append(Paragraph(
            "Tax Year 2025 - FOR REVIEW ONLY - NOT FOR FILING",
            self.styles['Normal']
        ))
        elements.append(Spacer(1, 20))

        # Taxpayer Info
        tp = self.tax_return.taxpayer
        info_data = [
            ["Name:", f"{tp.first_name} {tp.last_name}"],
            ["SSN:", self._mask_ssn(tp.ssn)],
            ["Filing Status:", tp.filing_status.value.replace("_", " ").title()],
            ["Address:", f"{tp.address}, {tp.city}, {tp.state} {tp.zip_code}"]
        ]
        elements.append(self._create_table(info_data, "Taxpayer Information"))
        elements.append(Spacer(1, 15))

        # Income Section
        income = self.tax_return.income
        calc = self.tax_return.calculation_breakdown

        income_data = [
            ["Line", "Description", "Amount"],
            ["1a", "Total W-2 wages", self._fmt(income.total_wages)],
            ["2b", "Taxable interest", self._fmt(income.taxable_interest)],
            ["3b", "Qualified dividends", self._fmt(income.qualified_dividends)],
            ["4b", "IRA distributions (taxable)", self._fmt(income.taxable_ira_distributions)],
            ["5b", "Pensions/annuities (taxable)", self._fmt(income.taxable_pension)],
            ["6b", "Social Security (taxable)", self._fmt(income.taxable_social_security)],
            ["7", "Capital gain or loss", self._fmt(income.capital_gain_or_loss)],
            ["8", "Other income (Schedule 1)", self._fmt(income.other_income)],
            ["9", "Total income", self._fmt(calc.total_income)],
            ["10", "Adjustments (Schedule 1)", self._fmt(calc.total_adjustments)],
            ["11", "Adjusted Gross Income (AGI)", self._fmt(calc.agi)],
        ]
        elements.append(self._create_table(income_data, "Income"))
        elements.append(Spacer(1, 15))

        # Deductions Section
        deductions_data = [
            ["Line", "Description", "Amount"],
            ["12", "Standard OR Itemized deduction", self._fmt(calc.deduction_amount)],
            ["13", "QBI deduction (Section 199A)", self._fmt(calc.qbi_deduction)],
            ["14", "Total deductions", self._fmt(calc.total_deductions)],
            ["15", "Taxable income", self._fmt(calc.taxable_income)],
        ]
        elements.append(self._create_table(deductions_data, "Deductions"))
        elements.append(Spacer(1, 15))

        # Tax and Credits
        tax_data = [
            ["Line", "Description", "Amount"],
            ["16", "Tax (from tax table/worksheet)", self._fmt(calc.income_tax)],
            ["17", "Additional taxes (Schedule 2)", self._fmt(calc.additional_taxes)],
            ["18", "Total tax before credits", self._fmt(calc.total_tax_before_credits)],
            ["19", "Child Tax Credit", self._fmt(calc.child_tax_credit)],
            ["20", "Other credits (Schedule 3)", self._fmt(calc.other_credits)],
            ["21", "Total credits", self._fmt(calc.total_credits)],
            ["22", "Net tax", self._fmt(calc.total_tax)],
        ]
        elements.append(self._create_table(tax_data, "Tax and Credits"))
        elements.append(Spacer(1, 15))

        # Payments and Refund/Owed
        payments_data = [
            ["Line", "Description", "Amount"],
            ["25a", "Federal tax withheld (W-2s)", self._fmt(calc.federal_withholding)],
            ["26", "Estimated tax payments", self._fmt(calc.estimated_payments)],
            ["27", "Total payments", self._fmt(calc.total_payments)],
            ["", "", ""],
            ["33", "REFUND" if calc.refund_or_owed < 0 else "AMOUNT YOU OWE",
             self._fmt(abs(calc.refund_or_owed))],
        ]
        elements.append(self._create_table(payments_data, "Payments"))

        # Footer
        elements.append(Spacer(1, 30))
        elements.append(Paragraph(
            "<i>This is a DRAFT for review purposes only. Do not file this document with the IRS.</i>",
            self.styles['Normal']
        ))
        elements.append(Paragraph(
            f"<i>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</i>",
            self.styles['Normal']
        ))

        doc.build(elements)
        return filename

    def generate_schedule_c_draft(self, filename: str):
        """Generate Schedule C draft"""
        # Similar pattern for Schedule C
        pass

    def generate_schedule_e_draft(self, filename: str):
        """Generate Schedule E draft with depreciation"""
        pass

    def generate_form_8949_draft(self, filename: str):
        """Generate Form 8949 with transaction detail"""
        pass

    def _create_table(self, data, title):
        """Create styled table"""
        table = Table(data, colWidths=[50, 300, 100])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        return table

    def _fmt(self, value) -> str:
        """Format currency"""
        if value is None:
            return "$0.00"
        return f"${value:,.2f}"

    def _mask_ssn(self, ssn: str) -> str:
        """Mask SSN for draft"""
        if ssn and len(ssn) >= 4:
            return f"XXX-XX-{ssn[-4:]}"
        return "XXX-XX-XXXX"
```

---

## Implementation Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Phase 1: Audit Trail | 3 days | Complete change logging |
| Phase 2: Form 8949 | 4 days | Transaction-level capital gains |
| Phase 3: K-1 Basis | 4 days | Basis tracking with worksheets |
| Phase 4: Rental Depreciation | 3 days | 27.5-year depreciation calculation |
| Phase 5: Draft PDFs | 5 days | On-demand draft form output |
| **TOTAL** | **19 days** | **Core capabilities complete** |

---

## Files to Create/Modify

### New Files
```
src/audit/
├── __init__.py
├── audit_logger.py
├── audit_models.py
└── audit_storage.py

src/calculator/
├── k1_basis_tracker.py      # NEW
├── rental_depreciation.py    # NEW
└── capital_gains_detail.py   # NEW

src/export/
└── draft_form_generator.py   # NEW
```

### Files to Modify
```
src/agent/intelligent_tax_agent.py
  - Add audit logging to _apply_extracted_entity()
  - Add Form 8949 transaction extraction
  - Add rental depreciation questions
  - Add K-1 basis questions

src/calculator/engine.py
  - Integrate rental depreciation
  - Integrate K-1 basis calculations
  - Integrate detailed capital gains

src/models/form_8949.py
  - Enhance with transaction-level detail

src/web/app.py
  - Add draft form generation endpoints
```

---

## API Endpoints

```python
# Draft Form Generation
GET /api/v1/draft-forms/{session_id}/1040      # Draft Form 1040
GET /api/v1/draft-forms/{session_id}/schedule-c  # Draft Schedule C
GET /api/v1/draft-forms/{session_id}/schedule-e  # Draft Schedule E
GET /api/v1/draft-forms/{session_id}/form-8949   # Draft Form 8949
GET /api/v1/draft-forms/{session_id}/all         # All applicable forms

# Audit Trail
GET /api/v1/audit/{session_id}/timeline    # Complete audit history
GET /api/v1/audit/{session_id}/changes     # Data changes only
GET /api/v1/audit/{session_id}/export      # Export audit log
```

---

## Success Criteria

After implementation:

1. **Audit Trail**: Every change to tax data is logged with timestamp, source, old/new values
2. **Form 8949**: Transaction-by-transaction capital gains with wash sale detection
3. **K-1 Basis**: Basis worksheet showing taxable distributions and suspended losses
4. **Depreciation**: Automatic 27.5-year calculation for rental properties
5. **Draft Forms**: Clean PDF output of all applicable forms on demand

**NOT in scope** (per your direction):
- 800 form enterprise library
- E-file capability
- SOC 2 certification
- Batch processing
- State form generation

This is focused, achievable in ~4 weeks, and directly supports your advisory intelligence vision.
