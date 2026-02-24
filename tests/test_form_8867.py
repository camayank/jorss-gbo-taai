"""
Tests for Form 8867: Paid Preparer's Due Diligence Checklist.

Required for paid preparers claiming EITC, CTC, AOTC, or HOH filing status.
Penalty: $600 per failure (2025) per IRC §6695(g).
"""

import pytest
from models.form_8867 import (
    Form8867,
    CreditType,
    DueDiligenceQuestion,
)


class TestForm8867Model:
    """Test Form 8867 model structure."""

    def test_credit_type_enum(self):
        """CreditType enum should include required credits."""
        assert CreditType.EITC.value == "eitc"
        assert CreditType.CTC.value == "ctc"
        assert CreditType.ACTC.value == "actc"
        assert CreditType.ODC.value == "odc"
        assert CreditType.AOTC.value == "aotc"
        assert CreditType.HOH.value == "hoh"

    def test_form_has_required_fields(self):
        """Form should have required preparer and credit fields."""
        form = Form8867()
        assert hasattr(form, 'preparer_name')
        assert hasattr(form, 'preparer_ptin')
        assert hasattr(form, 'credits_claimed')
        assert hasattr(form, 'tax_year')

    def test_credits_claimed_tracking(self):
        """Form should track which credits are claimed."""
        form = Form8867(
            credits_claimed=[CreditType.EITC, CreditType.CTC]
        )
        assert CreditType.EITC in form.credits_claimed
        assert CreditType.CTC in form.credits_claimed
        assert CreditType.AOTC not in form.credits_claimed


class TestForm8867Validation:
    """Test Form 8867 validation logic."""

    def test_empty_form_is_incomplete(self):
        """Empty form should not validate as complete."""
        form = Form8867()
        is_complete, missing = form.validate_completeness()
        assert is_complete is False
        assert len(missing) > 0

    def test_complete_form_validates(self):
        """Form with all required fields should validate."""
        form = Form8867(
            preparer_name="Test Preparer",
            preparer_ptin="P12345678",
            credits_claimed=[CreditType.EITC],
            knowledge_obtained=True,
            documents_reviewed=True,
            record_retention_acknowledged=True,
        )
        is_complete, missing = form.validate_completeness()
        assert is_complete is True
        assert len(missing) == 0


class TestForm8867Penalty:
    """Test Form 8867 penalty calculation."""

    def test_penalty_single_credit(self):
        """Penalty for single credit failure: $600."""
        form = Form8867(credits_claimed=[CreditType.EITC])
        penalty = form.calculate_potential_penalty()
        assert penalty == 600.0

    def test_penalty_multiple_credits(self):
        """Penalty for multiple credit failures: $600 each."""
        form = Form8867(
            credits_claimed=[CreditType.EITC, CreditType.CTC, CreditType.AOTC]
        )
        penalty = form.calculate_potential_penalty()
        assert penalty == 1800.0  # 3 × $600

    def test_no_credits_no_penalty(self):
        """No credits claimed means no penalty."""
        form = Form8867()
        penalty = form.calculate_potential_penalty()
        assert penalty == 0.0
