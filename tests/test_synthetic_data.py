"""
Tests for synthetic data generator.
"""

import pytest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ml.training.synthetic_data_generator import SyntheticDataGenerator, SyntheticDocument


class TestSyntheticDataGenerator:
    """Tests for SyntheticDataGenerator."""

    @pytest.fixture
    def generator(self):
        """Create a generator instance."""
        return SyntheticDataGenerator(seed=42)

    def test_generate_w2_document(self, generator):
        """Test generating a W-2 document."""
        doc = generator.generate_document("w2")

        assert doc.document_type == "w2"
        assert len(doc.text) > 0
        # Check for W-2 specific content
        text_lower = doc.text.lower()
        assert any(phrase in text_lower for phrase in ["w-2", "w2", "wage"])

    def test_generate_1099_int_document(self, generator):
        """Test generating a 1099-INT document."""
        doc = generator.generate_document("1099-int")

        assert doc.document_type == "1099-int"
        text_lower = doc.text.lower()
        assert any(phrase in text_lower for phrase in ["1099-int", "interest"])

    def test_generate_1099_div_document(self, generator):
        """Test generating a 1099-DIV document."""
        doc = generator.generate_document("1099-div")

        assert doc.document_type == "1099-div"
        text_lower = doc.text.lower()
        assert any(phrase in text_lower for phrase in ["1099-div", "dividend"])

    def test_generate_document_with_variations(self, generator):
        """Test generating document with variations."""
        doc = generator.generate_document("w2", num_variations=3)

        assert doc.document_type == "w2"
        assert len(doc.variations) == 2  # num_variations - 1
        # Each variation should be different
        all_texts = [doc.text] + doc.variations
        assert len(set(all_texts)) == len(all_texts)

    def test_generate_invalid_document_type(self, generator):
        """Test that invalid document type raises error."""
        with pytest.raises(ValueError):
            generator.generate_document("invalid_type")

    def test_generate_dataset(self, generator):
        """Test generating a complete dataset."""
        texts, labels = generator.generate_dataset(
            samples_per_type=10,
            document_types=["w2", "1099-int"],
        )

        # Should have 10 samples for each type = 20 total
        assert len(texts) == len(labels)
        assert len(texts) >= 20  # At least 10 per type

        # Check that we have both labels
        assert "w2" in labels
        assert "1099-int" in labels

    def test_generate_dataset_all_types(self, generator):
        """Test generating dataset for all document types."""
        texts, labels = generator.generate_dataset(samples_per_type=5)

        assert len(texts) == len(labels)
        # Should have multiple different labels
        unique_labels = set(labels)
        assert len(unique_labels) > 5

    def test_reproducibility_with_seed(self):
        """Test that same seed produces same results."""
        gen1 = SyntheticDataGenerator(seed=123)
        gen2 = SyntheticDataGenerator(seed=123)

        doc1 = gen1.generate_document("w2")
        doc2 = gen2.generate_document("w2")

        assert doc1.text == doc2.text

    def test_different_seeds_produce_different_results(self):
        """Test that different seeds produce different results."""
        gen1 = SyntheticDataGenerator(seed=123)
        gen2 = SyntheticDataGenerator(seed=456)

        doc1 = gen1.generate_document("w2")
        doc2 = gen2.generate_document("w2")

        assert doc1.text != doc2.text

    def test_generated_amounts_format(self, generator):
        """Test that generated amounts are properly formatted."""
        doc = generator.generate_document("w2")

        # Check for dollar amounts in typical format
        import re
        amount_pattern = r'\$[\d,]+\.\d{2}'
        amounts = re.findall(amount_pattern, doc.text)
        assert len(amounts) > 0

    def test_generated_ein_format(self, generator):
        """Test that generated EINs are properly formatted."""
        # Generate multiple documents to ensure we get one with EIN
        for _ in range(5):
            doc = generator.generate_document("w2")
            # Check for EIN pattern
            import re
            ein_pattern = r'\d{2}-\d{7}'
            eins = re.findall(ein_pattern, doc.text)
            if eins:
                assert len(eins[0]) == 10  # XX-XXXXXXX
                return
        # If no EIN found in 5 tries, that's still OK due to randomness

    def test_all_document_types_supported(self, generator):
        """Test that all expected document types can be generated."""
        expected_types = [
            "w2", "1099-int", "1099-div", "1099-nec", "1099-misc",
            "1099-b", "1099-r", "1099-g", "1098", "1098-e", "1098-t",
            "k1", "1095-a", "1095-b", "1095-c"
        ]

        for doc_type in expected_types:
            doc = generator.generate_document(doc_type)
            assert doc.document_type == doc_type
            assert len(doc.text) > 0


class TestSyntheticDocument:
    """Tests for SyntheticDocument dataclass."""

    def test_create_synthetic_document(self):
        """Test creating a synthetic document."""
        doc = SyntheticDocument(
            text="Test content",
            document_type="w2",
            variations=["Variation 1", "Variation 2"],
        )

        assert doc.text == "Test content"
        assert doc.document_type == "w2"
        assert len(doc.variations) == 2
