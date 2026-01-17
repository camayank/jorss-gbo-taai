"""
Integration tests for document classification system.
"""

import pytest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ml.document_classifier import DocumentClassifier, create_classifier
from ml.classifiers.base import DOCUMENT_TYPES


class TestDocumentClassifierIntegration:
    """Integration tests for the main DocumentClassifier."""

    @pytest.fixture
    def classifier(self):
        """Create a DocumentClassifier instance."""
        return DocumentClassifier()

    def test_classify_w2_document(self, classifier):
        """Test end-to-end W-2 classification."""
        w2_text = """
        Form W-2 Wage and Tax Statement 2025

        Employer's name, address, and ZIP code:
        ACME Corporation
        123 Main Street
        New York, NY 10001

        Employer identification number (EIN): 12-3456789
        Employee's social security number: XXX-XX-1234
        Employee's name: John Smith

        Box 1 Wages, tips, other compensation: $85,000.00
        Box 2 Federal income tax withheld: $15,300.00
        Box 3 Social security wages: $85,000.00
        Box 4 Social security tax withheld: $5,270.00
        Box 5 Medicare wages and tips: $85,000.00
        Box 6 Medicare tax withheld: $1,232.50
        """

        result = classifier.classify(w2_text)

        assert result.document_type == "w2"
        assert result.confidence >= 0.5
        assert result.processing_time_ms >= 0

    def test_classify_1099_int_document(self, classifier):
        """Test end-to-end 1099-INT classification."""
        text = """
        Form 1099-INT Interest Income 2025

        PAYER'S name: First National Bank
        PAYER'S TIN: 98-7654321
        RECIPIENT'S TIN: XXX-XX-5678

        Box 1 Interest income: $2,450.00
        Box 2 Early withdrawal penalty: $0.00
        Box 3 Interest on U.S. Savings Bonds: $0.00
        Box 4 Federal income tax withheld: $0.00
        Box 8 Tax-exempt interest: $150.00
        """

        result = classifier.classify(text)

        assert result.document_type == "1099-int"
        assert result.confidence >= 0.5

    def test_classify_1099_div_document(self, classifier):
        """Test end-to-end 1099-DIV classification."""
        text = """
        Form 1099-DIV Dividends and Distributions 2025

        PAYER'S name: Vanguard Investments

        Box 1a Total ordinary dividends: $3,200.00
        Box 1b Qualified dividends: $2,800.00
        Box 2a Total capital gain distributions: $450.00
        Box 3 Nondividend distributions: $0.00
        Box 4 Federal income tax withheld: $0.00
        """

        result = classifier.classify(text)

        assert result.document_type == "1099-div"
        assert result.confidence >= 0.5

    def test_classify_k1_document(self, classifier):
        """Test end-to-end Schedule K-1 classification."""
        text = """
        Schedule K-1 (Form 1065)
        Partner's Share of Income, Deductions, Credits, etc.

        Partnership's name: ABC Investment Partners LP
        Partnership's EIN: 45-6789012

        Part III Partner's Share of Current Year Income
        Box 1 Ordinary business income (loss): $12,500.00
        Box 5 Interest income: $250.00
        Box 6a Ordinary dividends: $180.00
        """

        result = classifier.classify(text)

        assert result.document_type == "k1"
        assert result.confidence >= 0.5

    def test_classify_batch(self, classifier):
        """Test batch classification."""
        texts = [
            "Form W-2 Wage and Tax Statement Box 1 Wages $50,000",
            "Form 1099-INT Interest Income Box 1 Interest $1,000",
            "Form 1099-DIV Dividends and Distributions Ordinary dividends $500",
        ]

        results = classifier.classify_batch(texts)

        assert len(results) == 3
        assert results[0].document_type == "w2"
        assert results[1].document_type == "1099-int"
        assert results[2].document_type == "1099-div"

    def test_classify_unknown_document(self, classifier):
        """Test classifying an unrecognized document."""
        text = """
        xyz abc qwerty asdf jkl zxcvbnm poiuytrewq
        random gibberish text that has no tax-related content
        mnbvcxz lkjhgfdsa qwertyuiop
        """

        result = classifier.classify(text)

        # Should return unknown or have low confidence
        # ML classifiers may return a guess even for unknown docs,
        # but with low confidence
        if result.document_type != "unknown":
            assert result.confidence < 0.6, \
                f"Expected low confidence for non-tax document, got {result.confidence}"

    def test_classify_empty_text(self, classifier):
        """Test classifying empty text."""
        result = classifier.classify("")

        assert result.document_type == "unknown"
        assert result.confidence == 0.0

    def test_get_supported_document_types(self, classifier):
        """Test getting supported document types."""
        supported = classifier.get_supported_document_types()

        assert "w2" in supported
        assert "1099-int" in supported
        assert "1099-div" in supported
        assert "unknown" not in supported  # unknown should be excluded

    def test_get_document_type_description(self, classifier):
        """Test getting document type descriptions."""
        desc = classifier.get_document_type_description("w2")
        assert "W-2" in desc
        assert "Wage" in desc

        desc = classifier.get_document_type_description("1099-int")
        assert "Interest" in desc

    def test_get_classifier_info(self, classifier):
        """Test getting classifier configuration info."""
        info = classifier.get_classifier_info()

        assert "primary_classifier" in info
        assert "fallback_enabled" in info
        assert "available_classifiers" in info
        assert isinstance(info["available_classifiers"], list)


class TestCreateClassifier:
    """Tests for create_classifier factory function."""

    def test_create_default_ensemble(self):
        """Test creating default ensemble classifier."""
        classifier = create_classifier()

        info = classifier.get_classifier_info()
        assert "ensemble" in info["primary_classifier"]

    def test_create_regex_only(self):
        """Test creating regex-only classifier."""
        classifier = create_classifier("regex")

        # Should still work for classification
        result = classifier.classify("Form W-2 Wage and Tax Statement")
        assert result.document_type == "w2"


class TestClassifierWithRealDocumentPatterns:
    """Test classification with realistic document patterns."""

    @pytest.fixture
    def classifier(self):
        return DocumentClassifier()

    def test_w2_with_ocr_noise(self, classifier):
        """Test W-2 classification with OCR-like noise."""
        text = """
        Forn W-2 Wage and Tax Statment 2025

        Emp1oyer's narne: ACME Corp
        EIN: l2-3456789

        Box l Wages: $75,OOO.OO
        Box 2 Federal tax withheld: $l3,500.OO
        Socia1 security wages: $75,OOO.OO
        Medicare wages: $75,OOO.OO
        """

        result = classifier.classify(text)
        # Should still recognize as W-2 despite OCR errors
        assert result.document_type == "w2"

    def test_1098_mortgage_interest(self, classifier):
        """Test 1098 mortgage interest statement."""
        text = """
        Form 1098 Mortgage Interest Statement

        Recipient's name: ABC Mortgage Company

        Box 1 Mortgage interest received from payer(s)/borrower(s): $12,500.00
        Box 2 Outstanding mortgage principal: $285,000.00
        Box 5 Mortgage insurance premiums: $1,200.00
        Box 6 Points paid on purchase of principal residence: $0.00

        Property address: 456 Oak Avenue, Springfield, IL 62701
        """

        result = classifier.classify(text)
        assert result.document_type == "1098"

    def test_1098_e_student_loan(self, classifier):
        """Test 1098-E student loan interest."""
        text = """
        Form 1098-E Student Loan Interest Statement

        Lender's name: Federal Student Aid

        Box 1 Student loan interest received by lender: $2,500.00

        Recipient's name: Jane Doe
        """

        result = classifier.classify(text)
        assert result.document_type == "1098-e"

    def test_1098_t_tuition(self, classifier):
        """Test 1098-T tuition statement."""
        text = """
        Form 1098-T Tuition Statement

        Filer's name: State University
        Student's name: John Student

        Box 1 Payments received for qualified tuition: $15,000.00
        Box 5 Scholarships or grants: $5,000.00

        Half-time student: Yes
        Graduate student: No
        """

        result = classifier.classify(text)
        assert result.document_type == "1098-t"

    def test_1099_r_retirement(self, classifier):
        """Test 1099-R retirement distribution."""
        text = """
        Form 1099-R Distributions From Pensions, Annuities, Retirement
        or Profit-Sharing Plans, IRAs, Insurance Contracts, etc.

        Payer's name: Retirement Fund Inc.

        Box 1 Gross distribution: $25,000.00
        Box 2a Taxable amount: $25,000.00
        Box 4 Federal income tax withheld: $5,000.00
        Box 7 Distribution code: 7
        IRA/SEP/SIMPLE: X
        """

        result = classifier.classify(text)
        assert result.document_type == "1099-r"

    def test_1099_g_government(self, classifier):
        """Test 1099-G government payments."""
        text = """
        Form 1099-G Certain Government Payments

        Payer's name: State Department of Labor

        Box 1 Unemployment compensation: $8,500.00
        Box 2 State or local income tax refunds, credits, or offsets: $0.00
        Box 4 Federal income tax withheld: $850.00
        """

        result = classifier.classify(text)
        assert result.document_type == "1099-g"

    def test_1099_b_broker(self, classifier):
        """Test 1099-B broker transactions."""
        text = """
        Form 1099-B Proceeds From Broker and Barter Exchange Transactions

        Broker's name: E*TRADE Securities

        Summary of proceeds from broker transactions:
        Box 1d Proceeds: $50,000.00
        Box 1e Cost or other basis: $45,000.00
        Type of gain or loss: Long-term

        Multiple transactions reported - see attached statements
        """

        result = classifier.classify(text)
        assert result.document_type == "1099-b"

    def test_1095_a_marketplace(self, classifier):
        """Test 1095-A health insurance marketplace."""
        text = """
        Form 1095-A Health Insurance Marketplace Statement

        Marketplace identifier: FF-12345678
        Policy number: POL-9876543
        Policy issuer name: Blue Cross Blue Shield

        Coverage start date: 01/01/2025

        Monthly enrollment premium: $850.00
        Monthly SLCSP premium: $900.00
        Monthly advance payment of PTC: $500.00
        """

        result = classifier.classify(text)
        assert result.document_type == "1095-a"

    def test_1095_b_health_coverage(self, classifier):
        """Test 1095-B health coverage."""
        text = """
        Form 1095-B Health Coverage

        Issuer name: United Healthcare

        Part III Covered Individuals
        Name: John Doe
        SSN: XXX-XX-1234
        Months of coverage: All 12 months

        Minimum essential coverage provided
        """

        result = classifier.classify(text)
        assert result.document_type == "1095-b"

    def test_1095_c_employer(self, classifier):
        """Test 1095-C employer health insurance."""
        text = """
        Form 1095-C Employer-Provided Health Insurance Offer and Coverage

        Employer's name: Big Corporation Inc.
        Employee's name: Jane Employee

        Line 14 Offer of coverage: 1A
        Line 15 Employee share of lowest cost monthly premium: $150.00
        Line 16 Section 4980H Safe Harbor: 2C

        Part III Covered Individuals included
        """

        result = classifier.classify(text)
        assert result.document_type == "1095-c"
