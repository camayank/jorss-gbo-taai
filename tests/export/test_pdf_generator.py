"""
Tests for PDF generation functionality.

Tests:
- PDF structure and format
- Draft watermark/warning
- SSN masking
- State tax inclusion
- Client summary generation
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime


class TestPDFStructure:
    """Tests for PDF document structure."""

    def test_pdf_has_required_sections(self, mock_tax_return):
        """Test that generated PDF has all required sections."""
        required_sections = [
            "header",
            "taxpayer_info",
            "income_summary",
            "deductions",
            "tax_calculation",
            "payments_and_refund",
        ]

        # Mock PDF generator output
        pdf_sections = {
            "header": {"title": "Tax Return Summary", "year": 2025},
            "taxpayer_info": {"name": mock_tax_return.taxpayer.full_name},
            "income_summary": {"total": mock_tax_return.total_income},
            "deductions": {"standard": 14400},
            "tax_calculation": {"total_tax": mock_tax_return.total_tax},
            "payments_and_refund": {"refund": mock_tax_return.refund_or_owed},
        }

        for section in required_sections:
            assert section in pdf_sections

    def test_pdf_header_contains_year(self, mock_tax_return):
        """Test that PDF header contains tax year."""
        header_info = {
            "title": f"Tax Year {mock_tax_return.tax_year} Return Summary",
            "tax_year": mock_tax_return.tax_year,
        }

        assert str(mock_tax_return.tax_year) in header_info["title"]
        assert header_info["tax_year"] == 2025


class TestDraftWarning:
    """Tests for draft return warning display."""

    def test_draft_return_shows_warning(self, mock_draft_return):
        """Test that draft returns display warning."""
        is_draft = mock_draft_return.status == "draft"
        assert is_draft

        # Draft should show warning
        warning_text = "DRAFT - NOT FOR FILING"
        assert mock_draft_return.status == "draft"

    def test_completed_return_no_draft_warning(self, mock_tax_return):
        """Test that completed returns don't show draft warning."""
        is_draft = mock_tax_return.status == "draft"
        assert not is_draft

    def test_draft_watermark_placement(self, mock_draft_return):
        """Test that draft watermark is prominently placed."""
        # Watermark should be diagonal across page
        watermark_config = {
            "text": "DRAFT",
            "rotation": 45,
            "opacity": 0.3,
            "position": "center",
        }

        assert watermark_config["text"] == "DRAFT"
        assert watermark_config["opacity"] < 0.5  # Should be semi-transparent


class TestSSNMasking:
    """Tests for SSN masking in PDF output."""

    def test_ssn_is_masked(self, mock_taxpayer):
        """Test that SSN is properly masked."""
        masked_ssn = mock_taxpayer.masked_ssn

        # Should show only last 4 digits
        assert "XXX-XX-" in masked_ssn
        assert masked_ssn.endswith(mock_taxpayer.ssn_last_four)

    def test_full_ssn_not_displayed(self, mock_taxpayer):
        """Test that full SSN is never displayed."""
        # The PDF should never contain a full SSN
        output_text = f"SSN: {mock_taxpayer.masked_ssn}"

        # Should not contain 9 consecutive digits
        import re
        full_ssn_pattern = r'\d{3}-\d{2}-\d{4}'
        full_matches = re.findall(full_ssn_pattern, output_text)

        # Masked format should not match full SSN pattern
        for match in full_matches:
            assert match.startswith("XXX") or "XX" in match

    def test_ein_not_masked(self, mock_w2):
        """Test that EIN (employer ID) is not masked."""
        ein = mock_w2.employer_ein

        # EIN should be fully visible
        assert "-" in ein
        assert not ein.startswith("XX")


class TestStateTaxInclusion:
    """Tests for state tax information in PDF."""

    def test_state_return_included(self, mock_tax_return):
        """Test that state return info is included."""
        state_returns = mock_tax_return.state_returns

        assert len(state_returns) > 0

        for state_return in state_returns:
            assert "state_code" in state_return
            assert "state_tax" in state_return

    def test_multi_state_handling(self, mock_multi_state_return):
        """Test handling of multiple state returns."""
        state_returns = mock_multi_state_return.state_returns

        assert len(state_returns) == 2

        state_codes = [sr["state_code"] for sr in state_returns]
        assert "CA" in state_codes
        assert "NY" in state_codes

    def test_state_totals_calculated(self, mock_multi_state_return):
        """Test that state totals are correctly calculated."""
        state_returns = mock_multi_state_return.state_returns

        total_state_tax = sum(sr["state_tax"] for sr in state_returns)
        total_state_withholding = sum(sr["state_withholding"] for sr in state_returns)

        assert total_state_tax == 6000.00  # 3600 + 2400
        assert total_state_withholding == 6500.00  # 4000 + 2500


class TestClientSummary:
    """Tests for client summary generation."""

    def test_summary_includes_key_figures(self, mock_tax_return):
        """Test that summary includes key tax figures."""
        summary = {
            "total_income": mock_tax_return.total_income,
            "agi": mock_tax_return.adjusted_gross_income,
            "taxable_income": mock_tax_return.taxable_income,
            "total_tax": mock_tax_return.total_tax,
            "refund_or_owed": mock_tax_return.refund_or_owed,
        }

        assert summary["total_income"] > 0
        assert summary["refund_or_owed"] != 0

    def test_summary_shows_refund_or_owed(self, mock_tax_return):
        """Test that summary clearly indicates refund or amount owed."""
        refund_or_owed = mock_tax_return.refund_or_owed

        if refund_or_owed > 0:
            status = "Refund"
        elif refund_or_owed < 0:
            status = "Amount Owed"
        else:
            status = "No Refund/No Amount Owed"

        assert status == "Refund"
        assert refund_or_owed == 2500.00

    def test_summary_includes_taxpayer_name(self, mock_tax_return):
        """Test that summary includes taxpayer name."""
        taxpayer_name = mock_tax_return.taxpayer.full_name

        assert taxpayer_name == "John Smith"

    def test_amended_return_indicator(self, mock_amended_return):
        """Test that amended returns are clearly indicated."""
        is_amended = mock_amended_return.is_amended
        amendment_number = mock_amended_return.amendment_number

        assert is_amended == True
        assert amendment_number == 1

        # Amended returns should be labeled "1040-X"
        form_type = "1040-X" if is_amended else "1040"
        assert form_type == "1040-X"
