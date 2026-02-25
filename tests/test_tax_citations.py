"""Tests for tax law citations."""

import pytest


class TestTaxCitations:
    """Tests for tax citation lookup."""

    def test_get_citation_returns_formatted_string(self):
        """get_citation should return formatted citation."""
        from src.tax_references.citations import get_citation

        citation = get_citation("standard_deduction")
        assert citation is not None
        assert "IRC" in citation
        assert "Section" in citation

    def test_get_citation_unknown_topic_returns_none(self):
        """Unknown topics should return None."""
        from src.tax_references.citations import get_citation

        citation = get_citation("unknown_topic_xyz")
        assert citation is None

    def test_all_top_20_citations_exist(self):
        """All top 20 tax topics should have citations."""
        from src.tax_references.citations import get_citation, TOP_20_TOPICS

        for topic in TOP_20_TOPICS:
            citation = get_citation(topic)
            assert citation is not None, f"Missing citation for {topic}"


class TestCitationIntegration:
    """Tests for citation integration with API responses."""

    def test_add_citations_to_response_adds_references(self):
        """Response mentioning tax topics should get citations."""
        from src.tax_references.citations import add_citations_to_response

        response = "You can claim the standard deduction of $15,000."
        result = add_citations_to_response(response)
        assert "Tax Law References" in result
        assert "IRC Section 63(c)" in result

    def test_add_citations_no_topics_unchanged(self):
        """Response without tax topics should be unchanged."""
        from src.tax_references.citations import add_citations_to_response

        response = "Hello! How can I help you today?"
        result = add_citations_to_response(response)
        assert result == response
        assert "Tax Law References" not in result

    def test_detect_topics_finds_multiple(self):
        """Should detect multiple tax topics in text."""
        from src.tax_references.citations import detect_topics

        text = "Your mortgage interest and child tax credit will reduce your taxes."
        topics = detect_topics(text)
        assert "mortgage_interest" in topics
        assert "child_tax_credit" in topics
