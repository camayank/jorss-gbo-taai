# Amended Return Workflow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a complete amended return (1040-X) workflow allowing CPAs to file amendments with diff engine, IRS submission, and state forms.

**Architecture:**
- **Return Cloning**: Copy original return into amendment record with amendment_number tracking
- **Diff Engine**: Three-column display (original/net change/corrected) per IRS Form 1040-X layout
- **Validation & Calculations**: Lock original return, auto-calc lines 18/20, validate against original
- **PDF & e-File**: Generate 1040-X PDF with metadata, submit to IRS via MeF schema
- **State Forms**: Auto-generate affected state amendment forms
- **Workflow**: FSM state management (DRAFT → IN_PROGRESS → READY_TO_FILE → AMENDED)

**Tech Stack:**
- FastAPI (REST endpoints), SQLAlchemy (database), Pydantic (validation)
- ReportLab (PDF generation), IRS MeF SDK (e-file submission)
- PostgreSQL (transaction safety for return cloning)

---

## Task 1: Create Amendment Service (Return Cloning)

**Files:**
- Create: `src/services/amendment_service.py`
- Modify: `src/database/models.py` (add amendment-related validators)
- Test: `tests/test_amendment_service.py`

**Step 1: Write the failing test for return cloning**

Run: `pytest tests/test_amendment_service.py::test_clone_return_creates_amendment -xvs`

```python
# tests/test_amendment_service.py
import pytest
from decimal import Decimal
from uuid import uuid4
from src.database.models import TaxReturn, ReturnStatus
from src.services.amendment_service import AmendmentService
from src.database.persistence import TaxReturnRepository

def test_clone_return_creates_amendment():
    """Test that cloning a return creates an amendment with correct tracking."""
    # Create original return
    original = TaxReturn(
        return_id=uuid4(),
        tax_year=2025,
        taxpayer_ssn_hash="test_hash",
        filing_status="single",
        status=ReturnStatus.ACCEPTED,
        firm_id=uuid4(),
        line_1_wages=Decimal("50000.00"),
        line_9_total_income=Decimal("50000.00"),
    )

    # Clone it
    amendment = AmendmentService.clone_return(original, reason="Correction to wages")

    # Verify amendment properties
    assert amendment.original_return_id == original.return_id
    assert amendment.is_amended == True
    assert amendment.amendment_number == 1
    assert amendment.status == ReturnStatus.DRAFT
    assert amendment.line_1_wages == original.line_1_wages
    assert amendment.return_id != original.return_id
    assert amendment.created_at is not None
```

**Step 2: Run test to verify it fails**

Expected: `FAILED - AmendmentService not found`

**Step 3: Write minimal AmendmentService implementation**

```python
# src/services/amendment_service.py
from typing import Optional
from uuid import UUID, uuid4
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.database.models import TaxReturn, ReturnStatus
from src.database.persistence import TaxReturnRepository

class AmendmentService:
    """Service for managing amended tax returns (Form 1040-X)."""

    @staticmethod
    def clone_return(original_return: TaxReturn, reason: str) -> TaxReturn:
        """
        Clone a filed return into an amendment record.

        Args:
            original_return: The original (ACCEPTED or FILED) return to amend
            reason: Reason for amendment (required by IRS)

        Returns:
            New TaxReturn record with is_amended=True and amendment_number set

        Raises:
            ValueError: If original return is not in a valid state for amendment
        """
        if original_return.status not in (ReturnStatus.ACCEPTED, ReturnStatus.FILED):
            raise ValueError(f"Cannot amend return in status {original_return.status}")

        # Calculate next amendment number
        next_amendment_number = (original_return.amendment_number or 0) + 1

        # Clone all fields
        amendment = TaxReturn(
            return_id=uuid4(),
            tax_year=original_return.tax_year,
            taxpayer_ssn_hash=original_return.taxpayer_ssn_hash,
            filing_status=original_return.filing_status,
            status=ReturnStatus.DRAFT,
            firm_id=original_return.firm_id,
            client_id=original_return.client_id,
            is_amended=True,
            original_return_id=original_return.return_id,
            amendment_number=next_amendment_number,
            # Copy all line items
            line_1_wages=original_return.line_1_wages,
            line_2a_tax_exempt_interest=original_return.line_2a_tax_exempt_interest,
            line_2b_taxable_interest=original_return.line_2b_taxable_interest,
            # ... all other line items ...
            state_code=original_return.state_code,
            preparer_ptin=original_return.preparer_ptin,
            firm_ein=original_return.firm_ein,
            software_version=original_return.software_version,
        )

        return amendment
```

**Step 4: Run test to verify it passes**

Expected: `PASSED`

**Step 5: Add validation for amendment reason storage**

Modify TaxReturn model to add amendment_reason field:

```python
# In TaxReturn class (src/database/models.py)
amendment_reason = Column(String(500), nullable=True, comment="IRS-required reason for amendment")
```

**Step 6: Commit**

```bash
git add src/services/amendment_service.py src/database/models.py tests/test_amendment_service.py
git commit -m "feat: implement return cloning for amendments

- Add AmendmentService.clone_return() to copy filed returns
- Increment amendment_number on cloned returns
- Clone all income/deduction/credit line items
- Preserve firm and client relationships
- Set status to DRAFT for amendment editing
- Add amendment_reason field to TaxReturn model

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 2: Diff Engine (Three-Column Comparison)

**Files:**
- Create: `src/calculator/diff_engine.py`
- Test: `tests/test_diff_engine.py`

**Step 1: Write failing test for diff calculation**

```python
# tests/test_diff_engine.py
import pytest
from decimal import Decimal
from uuid import uuid4
from src.calculator.diff_engine import DiffEngine, AmendmentDiff
from src.database.models import TaxReturn, ReturnStatus

def test_diff_engine_calculates_net_change():
    """Test that diff engine correctly calculates net changes between returns."""
    original = TaxReturn(
        return_id=uuid4(),
        line_1_wages=Decimal("50000.00"),
        line_9_total_income=Decimal("52000.00"),
        line_24_total_tax_liability=Decimal("8000.00"),
    )

    amendment = TaxReturn(
        return_id=uuid4(),
        line_1_wages=Decimal("55000.00"),  # +5000
        line_9_total_income=Decimal("57000.00"),  # +5000
        line_24_total_tax_liability=Decimal("8750.00"),  # +750
        original_return_id=original.return_id,
    )

    diff = DiffEngine.calculate_diff(original, amendment)

    # Verify diff structure
    assert diff.original_return_id == original.return_id
    assert diff.amendment_return_id == amendment.return_id
    assert diff.line_1_wages_original == Decimal("50000.00")
    assert diff.line_1_wages_amended == Decimal("55000.00")
    assert diff.line_1_wages_change == Decimal("5000.00")
    assert diff.line_24_tax_liability_change == Decimal("750.00")
```

**Step 2: Run test to verify it fails**

Expected: `FAILED - DiffEngine not found`

**Step 3: Write DiffEngine implementation**

```python
# src/calculator/diff_engine.py
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Dict, List
from uuid import UUID
from src.database.models import TaxReturn

@dataclass
class LineDiff:
    """Represents change in a single tax form line."""
    line_number: str
    line_description: str
    original_value: Decimal
    amended_value: Decimal
    net_change: Decimal
    percent_change: Optional[float] = None

    def __post_init__(self):
        if self.original_value != 0:
            self.percent_change = float((self.net_change / self.original_value) * 100)

@dataclass
class AmendmentDiff:
    """Complete diff between original and amended returns."""
    original_return_id: UUID
    amendment_return_id: UUID
    amendments: Dict[str, LineDiff] = field(default_factory=dict)
    total_tax_change: Decimal = Decimal("0.00")
    refund_change: Decimal = Decimal("0.00")

    # Shortcut properties for common lines
    @property
    def line_1_wages_original(self) -> Decimal:
        return self.amendments.get("line_1_wages", LineDiff("1", "Wages", Decimal("0"), Decimal("0"), Decimal("0"))).original_value

    @property
    def line_1_wages_amended(self) -> Decimal:
        return self.amendments.get("line_1_wages", LineDiff("1", "Wages", Decimal("0"), Decimal("0"), Decimal("0"))).amended_value

    @property
    def line_1_wages_change(self) -> Decimal:
        return self.amendments.get("line_1_wages", LineDiff("1", "Wages", Decimal("0"), Decimal("0"), Decimal("0"))).net_change

    @property
    def line_24_tax_liability_change(self) -> Decimal:
        return self.amendments.get("line_24_total_tax_liability", LineDiff("24", "Tax", Decimal("0"), Decimal("0"), Decimal("0"))).net_change

class DiffEngine:
    """Calculates differences between original and amended tax returns (Form 1040-X format)."""

    # IRS Form 1040-X line mappings
    IRS_1040X_LINES = {
        "line_1_wages": ("1", "Wages, salaries, tips"),
        "line_2b_taxable_interest": ("2b", "Taxable interest"),
        "line_3b_ordinary_dividends": ("3b", "Ordinary dividends"),
        "line_4b_taxable_ira": ("4b", "Taxable IRAs"),
        "line_5b_taxable_pensions": ("5b", "Taxable pensions"),
        "line_6b_taxable_social_security": ("6b", "Taxable social security"),
        "line_7_capital_gain_loss": ("7", "Capital gain/loss"),
        "line_8_other_income": ("8", "Other income"),
        "line_9_total_income": ("9", "Total income"),
        "line_10_adjustments": ("10", "Adjustments"),
        "line_11_agi": ("11", "Adjusted Gross Income"),
        "line_12c_total_deduction": ("12", "Deductions"),
        "line_13_qbi_deduction": ("13", "QBI deduction"),
        "line_14_total_deductions": ("14", "Total deductions"),
        "line_15_taxable_income": ("15", "Taxable income"),
        "line_16_tax": ("16", "Tax"),
        "line_17_schedule_2_line_3": ("17", "Additional taxes"),
        "line_18_total_tax": ("18", "Total tax"),
        "line_19_child_tax_credit": ("19", "Child tax credit"),
        "line_20_schedule_3_line_8": ("20", "Other credits"),
        "line_21_total_credits": ("21", "Total credits"),
        "line_22_tax_minus_credits": ("22", "Tax minus credits"),
        "line_23_other_taxes": ("23", "Other taxes"),
        "line_24_total_tax_liability": ("24", "Total tax liability"),
        "line_25d_total_withholding": ("25d", "Total withholding"),
        "line_26_estimated_payments": ("26", "Estimated payments"),
        "line_27_eic": ("27", "Earned income credit"),
        "line_28_additional_child_credit": ("28", "Additional child credit"),
        "line_29_american_opportunity": ("29", "American opportunity"),
        "line_30_recovery_rebate": ("30", "Recovery rebate"),
        "line_31_schedule_3_line_15": ("31", "Other payments"),
        "line_32_other_payments": ("32", "Other payments"),
        "line_33_total_payments": ("33", "Total payments"),
        "line_34_overpayment": ("34", "Overpayment"),
        "line_35a_refund": ("35a", "Refund"),
        "line_36_applied_to_next_year": ("36", "Applied to next year"),
        "line_37_amount_owed": ("37", "Amount owed"),
    }

    @staticmethod
    def calculate_diff(original: TaxReturn, amended: TaxReturn) -> AmendmentDiff:
        """
        Calculate differences between original and amended returns.

        Args:
            original: The original (filed) return
            amended: The amended return

        Returns:
            AmendmentDiff object with all line-by-line changes
        """
        diff = AmendmentDiff(
            original_return_id=original.return_id,
            amendment_return_id=amended.return_id
        )

        # Calculate diffs for each line
        for field_name, (line_num, description) in DiffEngine.IRS_1040X_LINES.items():
            original_val = getattr(original, field_name, Decimal("0")) or Decimal("0")
            amended_val = getattr(amended, field_name, Decimal("0")) or Decimal("0")
            net_change = amended_val - original_val

            diff.amendments[field_name] = LineDiff(
                line_number=line_num,
                line_description=description,
                original_value=original_val,
                amended_value=amended_val,
                net_change=net_change
            )

        # Calculate tax and refund changes
        diff.total_tax_change = (amended.line_24_total_tax_liability or Decimal("0")) - (original.line_24_total_tax_liability or Decimal("0"))
        diff.refund_change = (amended.line_35a_refund or Decimal("0")) - (original.line_35a_refund or Decimal("0"))

        return diff
```

**Step 4: Run test to verify it passes**

Expected: `PASSED`

**Step 5: Add test for filtering non-zero amendments**

```python
# Add to tests/test_diff_engine.py
def test_diff_engine_filters_zero_changes():
    """Test that diff engine returns only lines with changes."""
    original = TaxReturn(
        return_id=uuid4(),
        line_1_wages=Decimal("50000.00"),
        line_2b_taxable_interest=Decimal("1000.00"),
    )

    amendment = TaxReturn(
        return_id=uuid4(),
        line_1_wages=Decimal("55000.00"),  # Changed
        line_2b_taxable_interest=Decimal("1000.00"),  # Unchanged
        original_return_id=original.return_id,
    )

    diff = DiffEngine.calculate_diff(original, amendment)
    changed_lines = {k: v for k, v in diff.amendments.items() if v.net_change != 0}

    assert len(changed_lines) == 1
    assert "line_1_wages" in changed_lines
    assert "line_2b_taxable_interest" not in changed_lines
```

**Step 6: Commit**

```bash
git add src/calculator/diff_engine.py tests/test_diff_engine.py
git commit -m "feat: implement diff engine for amended returns

- Create LineDiff dataclass to represent line-by-line changes
- Implement AmendmentDiff to store complete return diffs
- Add IRS Form 1040-X line mappings
- Calculate net change and percent change for each line
- Support filtering to show only changed amounts
- Match IRS layout for 1040-X three-column display

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 3: Lock Original Return & Validate Amendment Fields

**Files:**
- Modify: `src/database/models.py` (add is_locked field)
- Create: `src/services/amendment_validation_service.py`
- Test: `tests/test_amendment_validation_service.py`

**Step 1: Write failing test for return locking**

```python
# tests/test_amendment_validation_service.py
import pytest
from decimal import Decimal
from uuid import uuid4
from src.database.models import TaxReturn, ReturnStatus
from src.services.amendment_validation_service import AmendmentValidationService

def test_lock_original_return_prevents_edits():
    """Test that locking original return prevents modifications."""
    original = TaxReturn(
        return_id=uuid4(),
        status=ReturnStatus.ACCEPTED,
        is_locked=False,
    )

    AmendmentValidationService.lock_original_return(original)

    assert original.is_locked == True
    assert original.locked_at is not None

def test_cannot_edit_locked_return_fields():
    """Test that locked returns reject field edits for non-amendable fields."""
    original = TaxReturn(
        return_id=uuid4(),
        status=ReturnStatus.ACCEPTED,
        is_locked=True,
        line_1_wages=Decimal("50000.00"),
    )

    with pytest.raises(ValueError, match="Cannot modify locked return"):
        AmendmentValidationService.validate_amendable_field(original, "line_1_wages", Decimal("55000.00"))
```

**Step 2: Run test to verify it fails**

Expected: `FAILED - is_locked not found, AmendmentValidationService not found`

**Step 3: Add is_locked field to TaxReturn model**

```python
# In TaxReturn class (src/database/models.py)
is_locked = Column(Boolean, default=False, index=True, comment="Locked when amendment filed")
locked_at = Column(DateTime, nullable=True, comment="Timestamp when locked for amendment")
```

**Step 4: Implement AmendmentValidationService**

```python
# src/services/amendment_validation_service.py
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Set
from src.database.models import TaxReturn

class AmendmentValidationService:
    """Validates amendments and enforces amendment business rules."""

    # Fields that can be edited in an amendment (IRS allows certain corrections)
    AMENDABLE_FIELDS = {
        "line_1_wages",
        "line_2a_tax_exempt_interest",
        "line_2b_taxable_interest",
        "line_3a_qualified_dividends",
        "line_3b_ordinary_dividends",
        "line_4a_ira_distributions",
        "line_4b_taxable_ira",
        "line_5a_pensions",
        "line_5b_taxable_pensions",
        "line_6a_social_security",
        "line_6b_taxable_social_security",
        "line_7_capital_gain_loss",
        "line_8_other_income",
        "line_10_adjustments",
        "line_12a_standard_deduction",
        "line_13_qbi_deduction",
        # ... add more as IRS allows ...
    }

    @staticmethod
    def lock_original_return(return_obj: TaxReturn) -> None:
        """Lock original return when amendment is filed to prevent further modifications."""
        return_obj.is_locked = True
        return_obj.locked_at = datetime.now(timezone.utc)

    @staticmethod
    def validate_amendable_field(return_obj: TaxReturn, field_name: str, new_value: Any) -> None:
        """
        Validate that a field can be edited in an amendment.

        Raises:
            ValueError: If field is not amendable or return is locked
        """
        if return_obj.is_locked and not return_obj.is_amended:
            raise ValueError("Cannot modify locked return that is not an amendment")

        if field_name not in AmendmentValidationService.AMENDABLE_FIELDS:
            raise ValueError(f"Field {field_name} cannot be amended per IRS rules")

    @staticmethod
    def get_non_zero_amendments(original: TaxReturn, amended: TaxReturn) -> Set[str]:
        """Get list of fields that changed between original and amended return."""
        changed = set()
        for field_name in AmendmentValidationService.AMENDABLE_FIELDS:
            original_val = getattr(original, field_name, Decimal("0")) or Decimal("0")
            amended_val = getattr(amended, field_name, Decimal("0")) or Decimal("0")
            if original_val != amended_val:
                changed.add(field_name)
        return changed
```

**Step 5: Run tests to verify they pass**

Expected: `PASSED`

**Step 6: Commit**

```bash
git add src/database/models.py src/services/amendment_validation_service.py tests/test_amendment_validation_service.py
git commit -m "feat: implement return locking and amendment field validation

- Add is_locked and locked_at fields to TaxReturn
- Prevent modifications to locked original returns
- Define AMENDABLE_FIELDS set per IRS rules
- Validate that only amendable fields are modified
- Track which fields changed between original and amendment

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 4: Auto-Calculate Lines 18 & 20 (Tax & Overpayment)

**Files:**
- Create: `src/calculator/amendment_calculator.py`
- Test: `tests/test_amendment_calculator.py`

**Step 1: Write failing test for auto-calculation**

```python
# tests/test_amendment_calculator.py
import pytest
from decimal import Decimal
from uuid import uuid4
from src.database.models import TaxReturn, ReturnStatus
from src.calculator.amendment_calculator import AmendmentCalculator

def test_auto_calculate_line_18_amended_tax():
    """Test that line 18 (total tax) is auto-calculated from components."""
    amended = TaxReturn(
        return_id=uuid4(),
        line_16_tax=Decimal("7500.00"),
        line_17_schedule_2_line_3=Decimal("500.00"),  # Additional taxes
        line_18_total_tax=Decimal("0.00"),  # Will be calculated
    )

    AmendmentCalculator.calculate_total_tax(amended)

    assert amended.line_18_total_tax == Decimal("8000.00")

def test_auto_calculate_line_20_overpayment():
    """Test that lines 34-37 (refund/amount owed) are auto-calculated."""
    amended = TaxReturn(
        return_id=uuid4(),
        line_24_total_tax_liability=Decimal("8000.00"),
        line_33_total_payments=Decimal("8500.00"),
        line_34_overpayment=Decimal("0.00"),  # Will be calculated
        line_35a_refund=Decimal("0.00"),
        line_37_amount_owed=Decimal("0.00"),
    )

    AmendmentCalculator.calculate_refund_or_owed(amended)

    assert amended.line_34_overpayment == Decimal("500.00")
    assert amended.line_35a_refund == Decimal("500.00")
    assert amended.line_37_amount_owed == Decimal("0.00")
```

**Step 2: Run tests to verify they fail**

Expected: `FAILED - AmendmentCalculator not found`

**Step 3: Implement AmendmentCalculator**

```python
# src/calculator/amendment_calculator.py
from decimal import Decimal
from typing import Optional
from src.database.models import TaxReturn

class AmendmentCalculator:
    """
    Calculates amendments to tax returns.
    Follows IRS Form 1040-X reconciliation logic.
    """

    @staticmethod
    def calculate_total_tax(return_obj: TaxReturn) -> None:
        """
        Auto-calculate Line 18: Total Tax
        Formula: Line 16 + Line 17 + other taxes (Schedule 2)
        """
        line_16 = return_obj.line_16_tax or Decimal("0")
        line_17 = return_obj.line_17_schedule_2_line_3 or Decimal("0")
        line_23 = return_obj.line_23_other_taxes or Decimal("0")

        return_obj.line_18_total_tax = line_16 + line_17 + line_23

    @staticmethod
    def calculate_total_tax_liability(return_obj: TaxReturn) -> None:
        """
        Auto-calculate Line 24: Total Tax Liability
        Formula: Line 18 (total tax) + Line 23 (other taxes) - Line 21 (credits)
        """
        line_18 = return_obj.line_18_total_tax or Decimal("0")
        line_23 = return_obj.line_23_other_taxes or Decimal("0")
        line_21 = return_obj.line_21_total_credits or Decimal("0")

        return_obj.line_24_total_tax_liability = line_18 + line_23 - line_21

    @staticmethod
    def calculate_refund_or_owed(return_obj: TaxReturn) -> None:
        """
        Auto-calculate Lines 34-37 (Refund/Amount Owed).

        Formula:
        Line 34: Total Payments (Line 33) - Total Tax Liability (Line 24)
        Line 35a: If Line 34 > 0, set to Line 34 (refund)
        Line 37: If Line 34 < 0, set to abs(Line 34) (amount owed)
        """
        line_24 = return_obj.line_24_total_tax_liability or Decimal("0")
        line_33 = return_obj.line_33_total_payments or Decimal("0")

        overpayment = line_33 - line_24

        return_obj.line_34_overpayment = max(Decimal("0"), overpayment)
        return_obj.line_35a_refund = max(Decimal("0"), overpayment)
        return_obj.line_37_amount_owed = max(Decimal("0"), -overpayment)

    @staticmethod
    def calculate_amendment(return_obj: TaxReturn) -> None:
        """Run all amendment calculations in proper sequence."""
        AmendmentCalculator.calculate_total_tax(return_obj)
        AmendmentCalculator.calculate_total_tax_liability(return_obj)
        AmendmentCalculator.calculate_refund_or_owed(return_obj)
```

**Step 4: Run tests to verify they pass**

Expected: `PASSED`

**Step 5: Commit**

```bash
git add src/calculator/amendment_calculator.py tests/test_amendment_calculator.py
git commit -m "feat: implement amendment auto-calculations for lines 18 & 20+

- Calculate Line 18 (Total Tax) from components
- Calculate Line 24 (Total Tax Liability)
- Calculate Lines 34-37 (Refund/Amount Owed)
- Support overpayment vs amount owed logic
- Auto-run calculations in proper sequence

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 5: Amendment Reason & Validation

**Files:**
- Modify: `src/database/models.py` (add amendment_reason field if not present)
- Create: `src/services/amendment_reason_service.py`
- Test: `tests/test_amendment_reason_service.py`

**Step 1: Write failing test**

```python
# tests/test_amendment_reason_service.py
import pytest
from uuid import uuid4
from src.database.models import TaxReturn, ReturnStatus
from src.services.amendment_reason_service import AmendmentReasonService

def test_validate_amendment_reason_required():
    """Test that amendment reason is required by IRS."""
    amended = TaxReturn(
        return_id=uuid4(),
        amendment_reason=None,
    )

    with pytest.raises(ValueError, match="Amendment reason required"):
        AmendmentReasonService.validate_reason(amended)

def test_amendment_reason_minimum_length():
    """Test that reason meets minimum length requirement."""
    amended = TaxReturn(
        return_id=uuid4(),
        amendment_reason="Fix",  # Too short
    )

    with pytest.raises(ValueError, match="Reason must be at least"):
        AmendmentReasonService.validate_reason(amended)

def test_valid_amendment_reason_accepted():
    """Test that valid reason is accepted."""
    amended = TaxReturn(
        return_id=uuid4(),
        amendment_reason="Correction to wages reported on Line 1",
    )

    AmendmentReasonService.validate_reason(amended)  # Should not raise
```

**Step 2-6: Implement and commit**

```python
# src/services/amendment_reason_service.py
from src.database.models import TaxReturn

class AmendmentReasonService:
    """Manages amendment reasons (required by IRS on Form 1040-X)."""

    IRS_REASON_CATEGORIES = {
        "income_error": "Correction to income reported",
        "deduction_error": "Correction to deduction amounts",
        "credit_error": "Correction to credits claimed",
        "filing_status_change": "Change in filing status",
        "dependent_change": "Added or removed dependent",
        "withholding_error": "Correction to withholding",
        "payment_error": "Correction to estimated payments",
        "other": "Other reason (specify below)",
    }

    @staticmethod
    def validate_reason(return_obj: TaxReturn) -> None:
        """Validate amendment reason meets IRS requirements."""
        if not return_obj.amendment_reason:
            raise ValueError("Amendment reason required by IRS")

        if len(return_obj.amendment_reason) < 10:
            raise ValueError("Reason must be at least 10 characters")

        if len(return_obj.amendment_reason) > 500:
            raise ValueError("Reason cannot exceed 500 characters")
```

---

## Task 6: Form 1040-X PDF Generation

**Files:**
- Create: `src/pdf/form_1040x_generator.py`
- Test: `tests/test_form_1040x_generator.py`

**Implementation Note:** This task generates Form 1040-X PDF with:
- Three columns (original/change/corrected)
- IRS-compliant layout
- Metadata (dates, SSN, amendment number)
- Signature lines
- State box (lines 51-53)

Use ReportLab for PDF generation to match existing PDF services.

---

## Task 7: IRS e-File Submission Service (MeF Schema)

**Files:**
- Create: `src/services/irs_efile_service.py`
- Create: `src/irs/mef_builder.py`
- Test: `tests/test_irs_efile_service.py`

**Implementation Note:** This task:
- Builds MeF (e-file) schema for 1040-X submissions
- Handles authentication with IRS e-services
- Queues submissions for batch processing
- Tracks submission status
- Handles rejections and corrections

---

## Task 8: State Amendment Forms Generation

**Files:**
- Create: `src/services/state_amendment_service.py`
- Test: `tests/test_state_amendment_service.py`

**Implementation Note:** This task:
- Identifies affected states from original return
- Generates state-specific amendment forms
- Maps federal changes to state filings
- Tracks state acceptance

---

## Task 9: Amendment REST API Endpoints

**Files:**
- Modify: `src/web/routers/returns.py`
- Test: `tests/integration/test_amendment_api.py`

**Step 1: Create endpoint to initiate amendment**

```python
# Add to src/web/routers/returns.py
@router.post("/returns/{return_id}/amend")
async def initiate_amendment(
    return_id: UUID,
    request: AmendmentInitiateRequest,
    current_user: User = Depends(get_current_user),
):
    """
    POST /returns/{return_id}/amend

    Initiate amendment workflow for a filed return.
    Creates cloned return and locks original.

    Request:
    {
        "reason": "Correction to wages reported on Line 1"
    }

    Response:
    {
        "amendment_id": "uuid",
        "amendment_number": 1,
        "status": "draft",
        "original_return_id": "uuid"
    }
    """
```

**Step 2: Create endpoint to get diff**

```python
# Add to src/web/routers/returns.py
@router.get("/returns/{amendment_id}/diff")
async def get_amendment_diff(
    amendment_id: UUID,
    current_user: User = Depends(get_current_user),
):
    """
    GET /returns/{amendment_id}/diff

    Get three-column diff (original/change/corrected) for amendment.

    Response:
    {
        "amendments": {
            "line_1_wages": {
                "original": 50000.00,
                "amended": 55000.00,
                "change": 5000.00
            }
        },
        "tax_change": 750.00
    }
    """
```

**Step 3: Create endpoint to file amendment**

```python
# Add to src/web/routers/returns.py
@router.post("/returns/{amendment_id}/file")
async def file_amendment(
    amendment_id: UUID,
    current_user: User = Depends(get_current_user),
):
    """
    POST /returns/{amendment_id}/file

    Submit amendment to IRS and applicable states.

    Validates:
    - Amendment completeness
    - Required fields present
    - Calculations correct
    - State forms generated

    Response:
    {
        "amendment_id": "uuid",
        "status": "amended",
        "irs_submission_id": "uuid",
        "state_submissions": [...]
    }
    """
```

---

## Task 10: Frontend UI for Amendment Workflow

**Files:**
- Create: `src/web/templates/amendment_editor.html`
- Create: `src/web/static/js/amendment_diff.js`
- Test: `tests/e2e/test_amendment_ui.py`

**Implementation Note:** This task:
- Shows original vs amended side-by-side with diff highlighting
- Allows editing of amendable fields only
- Shows calculated changes in real-time
- Displays reasons and validation messages
- Provides filing confirmation workflow

---

## Task 11: Database Migrations & Indexes

**Files:**
- Create: `migrations/add_amendment_fields.sql`
- Test: `tests/test_migrations.py`

---

## Task 12: Integration Test - Full Amendment Flow

**Files:**
- Create: `tests/integration/test_amendment_end_to_end.py`

This test runs the complete flow:
1. Create original return
2. Accept/file original
3. Initiate amendment
4. Edit amendable fields
5. Review diff
6. File amendment
7. Verify original is locked
8. Verify amendment status is AMENDED

---

## Execution

After these 12 core tasks, the system will have:

✅ Return cloning with amendment tracking
✅ Three-column diff engine per 1040-X layout
✅ Original return locking and field validation
✅ Auto-calculation of tax and refund lines
✅ Amendment reason collection (IRS required)
✅ Form 1040-X PDF generation
✅ IRS e-file submission via MeF schema
✅ State amendment form generation
✅ REST API endpoints for amendment workflow
✅ Frontend UI with diff visualization
✅ Database schema and migrations
✅ End-to-end integration tests

**Total estimated complexity:** 2500-3000 lines of code
**Test coverage target:** 85%+
**Database transactions:** All amendment cloning/filing operations use transactions for consistency
