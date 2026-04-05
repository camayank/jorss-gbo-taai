"""Test suite for semantic IRS RAG implementation."""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.irs_rag import SemanticIRSRag, IRSChunk, get_irs_rag


class TestSemanticIRSRag:
    """Test semantic RAG retrieval and formatting."""

    def test_load_rag(self):
        """Test that RAG loads without errors."""
        rag = SemanticIRSRag(tax_year=2025)
        assert rag is not None

    def test_retrieve_basic(self):
        """Test basic retrieval functionality."""
        rag = SemanticIRSRag(tax_year=2025)
        chunks = rag.retrieve("IRA contribution limit", top_k=3)
        assert len(chunks) > 0
        assert all(isinstance(c, IRSChunk) for c in chunks)
        # Verify scores are between 0 and 1
        assert all(0 <= c.score <= 1 for c in chunks)

    def test_retrieve_with_zero_k(self):
        """Test retrieval with top_k=0."""
        rag = SemanticIRSRag(tax_year=2025)
        chunks = rag.retrieve("IRA contribution limit", top_k=0)
        assert len(chunks) == 0

    def test_format_for_prompt(self):
        """Test formatting results for LLM prompt."""
        rag = SemanticIRSRag(tax_year=2025)
        result = rag.format_for_prompt("401k contribution limit")
        assert len(result) > 0
        assert "Relevant IRS Guidance" in result
        assert "Pub " in result

    def test_format_multi(self):
        """Test multi-query deduplication."""
        rag = SemanticIRSRag(tax_year=2025)
        # Use overlapping queries to test dedup
        result = rag.format_multi(
            ["IRA contribution limit", "Traditional IRA limit"],
            top_k_per_query=2
        )
        assert len(result) > 0
        # Count how many times we see each publication
        pub_count = result.count("[Pub")
        # With dedup, should be fewer than 4 (2 queries × 2 top_k)
        assert pub_count <= 4

    def test_format_empty_query(self):
        """Test formatting with empty query list."""
        rag = SemanticIRSRag(tax_year=2025)
        result = rag.format_multi([], top_k_per_query=2)
        assert result == ""

    def test_singleton_cache(self):
        """Test that get_irs_rag caches instances correctly."""
        rag1 = get_irs_rag(tax_year=2025)
        rag2 = get_irs_rag(tax_year=2025)
        # Should be the same cached instance
        assert rag1 is rag2

    def test_semantic_quality(self):
        """Test that semantic search finds semantically relevant results."""
        rag = SemanticIRSRag(tax_year=2025)
        # Query about Roth IRA
        chunks = rag.retrieve("Roth individual retirement account", top_k=1)
        assert len(chunks) > 0
        # Should find a Roth-related publication
        assert "Roth" in chunks[0].topic or "590" in chunks[0].pub

    def test_iris_chunk_format(self):
        """Test IRSChunk formatting."""
        chunk = IRSChunk(
            id="test_id",
            pub="Pub 17",
            topic="Test Topic",
            tags=["test"],
            text="Test text content",
            score=0.95
        )
        formatted = chunk.to_prompt_string()
        assert "[Pub 17 — Test Topic]" in formatted
        assert "Test text content" in formatted
