"""Tests for PII scrubber used before sending data to AI providers."""

import pytest

from advisory.pii_scrubber import scrub_for_ai


class TestNameScrubbing:
    """Name fields are replaced with 'the taxpayer'."""

    def test_first_name_replaced(self):
        result = scrub_for_ai({"first_name": "Alice"})
        assert result["first_name"] == "the taxpayer"

    def test_last_name_replaced(self):
        result = scrub_for_ai({"last_name": "Smith"})
        assert result["last_name"] == "the taxpayer"

    def test_client_name_replaced(self):
        result = scrub_for_ai({"client_name": "Alice Smith"})
        assert result["client_name"] == "the taxpayer"

    def test_taxpayer_name_replaced(self):
        result = scrub_for_ai({"taxpayer_name": "Bob Jones"})
        assert result["taxpayer_name"] == "the taxpayer"

    def test_generic_name_field_replaced(self):
        result = scrub_for_ai({"name": "Charlie Brown"})
        assert result["name"] == "the taxpayer"

    def test_multiple_name_fields_all_replaced(self):
        data = {
            "first_name": "Alice",
            "last_name": "Smith",
            "client_name": "Alice Smith",
        }
        result = scrub_for_ai(data)
        assert result["first_name"] == "the taxpayer"
        assert result["last_name"] == "the taxpayer"
        assert result["client_name"] == "the taxpayer"

    def test_name_fields_do_not_mutate_original(self):
        data = {"first_name": "Alice"}
        scrub_for_ai(data)
        assert data["first_name"] == "Alice"


class TestFinancialAmountRounding:
    """Financial amounts are rounded to the nearest $1,000."""

    @pytest.mark.parametrize("key", [
        "gross_income",
        "total_tax",
        "tax_savings",
        "itemized_deduction",
        "child_tax_credit",
        "tax_liability",
        "estimated_payment",
        "retirement_contribution",
        "business_expense",
        "w2_wage",
        "annual_salary",
        "capital_gain",
        "net_loss",
        "adjusted_agi",
        "expected_refund",
    ])
    def test_financial_keyword_fields_rounded(self, key):
        result = scrub_for_ai({key: 54321})
        assert result[key] == 54000

    def test_income_rounded_up(self):
        result = scrub_for_ai({"gross_income": 54501})
        assert result["gross_income"] == 55000

    def test_income_rounded_down(self):
        result = scrub_for_ai({"gross_income": 54499})
        assert result["gross_income"] == 54000

    def test_exact_thousand_unchanged(self):
        result = scrub_for_ai({"gross_income": 50000})
        assert result["gross_income"] == 50000

    def test_float_income_rounded(self):
        result = scrub_for_ai({"gross_income": 54321.78})
        assert result["gross_income"] == 54000

    def test_zero_amount_stays_zero(self):
        result = scrub_for_ai({"total_tax": 0})
        assert result["total_tax"] == 0

    def test_small_amount_rounds_to_zero(self):
        result = scrub_for_ai({"total_tax": 499})
        assert result["total_tax"] == 0

    def test_small_amount_rounds_to_thousand(self):
        result = scrub_for_ai({"total_tax": 501})
        assert result["total_tax"] == 1000

    def test_financial_rounding_does_not_mutate_original(self):
        data = {"gross_income": 54321}
        scrub_for_ai(data)
        assert data["gross_income"] == 54321


class TestNonFinancialFieldsPreserved:
    """Non-financial numeric fields are left unchanged."""

    def test_age_unchanged(self):
        result = scrub_for_ai({"age": 42})
        assert result["age"] == 42

    def test_dependents_count_unchanged(self):
        result = scrub_for_ai({"dependents": 3})
        assert result["dependents"] == 3

    def test_filing_year_unchanged(self):
        result = scrub_for_ai({"filing_year": 2025})
        assert result["filing_year"] == 2025

    def test_zip_code_removed_as_pii(self):
        result = scrub_for_ai({"zip_code": 90210})
        assert "zip_code" not in result

    def test_string_fields_unchanged(self):
        result = scrub_for_ai({"filing_status": "married_filing_jointly"})
        assert result["filing_status"] == "married_filing_jointly"

    def test_boolean_fields_unchanged(self):
        result = scrub_for_ai({"is_blind": True})
        assert result["is_blind"] is True


class TestEmptyAndMinimalInput:
    """Edge cases with empty or minimal data."""

    def test_empty_dict_returns_empty_dict(self):
        result = scrub_for_ai({})
        assert result == {}

    def test_single_non_pii_field(self):
        result = scrub_for_ai({"filing_status": "single"})
        assert result == {"filing_status": "single"}

    def test_only_name_field(self):
        result = scrub_for_ai({"name": "Jane Doe"})
        assert result == {"name": "the taxpayer"}


class TestSSNRemoval:
    """SSN and EIN patterns should be removed.

    NOTE: The current implementation does not yet scrub SSN/EIN fields.
    These tests document the expected future behavior.
    """

    def test_ssn_field_removed(self):
        result = scrub_for_ai({"ssn": "123-45-6789", "filing_status": "single"})
        assert "ssn" not in result

    def test_ein_field_removed(self):
        result = scrub_for_ai({"ein": "12-3456789", "business_name": "Acme"})
        assert "ein" not in result

    def test_social_security_number_field_removed(self):
        result = scrub_for_ai({"social_security_number": "123-45-6789"})
        assert "social_security_number" not in result

    def test_taxpayer_id_field_removed(self):
        result = scrub_for_ai({"taxpayer_id": "123-45-6789"})
        assert "taxpayer_id" not in result


class TestEmailRemoval:
    """Email addresses should be removed.

    NOTE: The current implementation does not yet scrub email fields.
    These tests document the expected future behavior.
    """

    def test_email_field_removed(self):
        result = scrub_for_ai({"email": "alice@example.com", "filing_year": 2025})
        assert "email" not in result

    def test_email_address_field_removed(self):
        result = scrub_for_ai({"email_address": "bob@company.org"})
        assert "email_address" not in result


class TestPhoneRemoval:
    """Phone numbers should be removed.

    NOTE: The current implementation does not yet scrub phone fields.
    These tests document the expected future behavior.
    """

    def test_phone_field_removed(self):
        result = scrub_for_ai({"phone": "555-123-4567", "filing_status": "single"})
        assert "phone" not in result

    def test_phone_number_field_removed(self):
        result = scrub_for_ai({"phone_number": "(555) 123-4567"})
        assert "phone_number" not in result


class TestAddressRemoval:
    """Address fields should be removed.

    NOTE: The current implementation does not yet scrub address fields.
    These tests document the expected future behavior.
    """

    def test_address_field_removed(self):
        result = scrub_for_ai({"address": "123 Main St", "filing_year": 2025})
        assert "address" not in result

    def test_street_address_field_removed(self):
        result = scrub_for_ai({"street_address": "456 Oak Ave"})
        assert "street_address" not in result

    def test_city_state_zip_removed(self):
        data = {"city": "Springfield", "state": "IL", "zip": "62704"}
        result = scrub_for_ai(data)
        assert "city" not in result
        # "state" is tax-relevant (filing state), so it is preserved
        assert result["state"] == "IL"
        assert "zip" not in result


class TestNestedDictHandling:
    """Nested dicts should be scrubbed recursively.

    NOTE: The current implementation uses a shallow copy and does not
    recurse into nested dicts. These tests document expected future behavior.
    """

    def test_nested_name_scrubbed(self):
        data = {"taxpayer": {"first_name": "Alice", "last_name": "Smith"}}
        result = scrub_for_ai(data)
        assert result["taxpayer"]["first_name"] == "the taxpayer"
        assert result["taxpayer"]["last_name"] == "the taxpayer"

    def test_nested_financial_rounded(self):
        data = {"summary": {"gross_income": 54321, "total_tax": 12345}}
        result = scrub_for_ai(data)
        assert result["summary"]["gross_income"] == 54000
        assert result["summary"]["total_tax"] == 12000


class TestMixedData:
    """Realistic payloads with multiple PII types."""

    def test_names_and_financials_scrubbed_together(self):
        data = {
            "first_name": "Alice",
            "last_name": "Smith",
            "filing_status": "single",
            "gross_income": 85432,
            "total_tax": 12876,
            "dependents": 2,
            "filing_year": 2025,
        }
        result = scrub_for_ai(data)

        # Names replaced
        assert result["first_name"] == "the taxpayer"
        assert result["last_name"] == "the taxpayer"

        # Financial amounts rounded
        assert result["gross_income"] == 85000
        assert result["total_tax"] == 13000

        # Non-PII preserved exactly
        assert result["filing_status"] == "single"
        assert result["dependents"] == 2
        assert result["filing_year"] == 2025

    def test_all_name_variants_with_financials(self):
        data = {
            "name": "Alice Smith",
            "first_name": "Alice",
            "last_name": "Smith",
            "client_name": "Alice Smith",
            "taxpayer_name": "Alice Smith",
            "adjusted_agi": 150750,
            "child_tax_credit": 2000,
            "itemized_deduction": 28499,
        }
        result = scrub_for_ai(data)

        for key in ("name", "first_name", "last_name", "client_name", "taxpayer_name"):
            assert result[key] == "the taxpayer"

        assert result["adjusted_agi"] == 151000
        assert result["child_tax_credit"] == 2000
        assert result["itemized_deduction"] == 28000

    def test_full_pii_payload(self):
        """A comprehensive payload with all PII types."""
        data = {
            "first_name": "Alice",
            "last_name": "Smith",
            "ssn": "123-45-6789",
            "email": "alice@example.com",
            "phone": "555-123-4567",
            "address": "123 Main St",
            "city": "Springfield",
            "state": "IL",
            "zip": "62704",
            "gross_income": 85432,
            "total_tax": 12876,
            "filing_status": "single",
            "dependents": 2,
        }
        result = scrub_for_ai(data)

        # Names replaced
        assert result["first_name"] == "the taxpayer"
        assert result["last_name"] == "the taxpayer"

        # Sensitive fields removed entirely
        assert "ssn" not in result
        assert "email" not in result
        assert "phone" not in result
        assert "address" not in result
        assert "city" not in result
        assert result["state"] == "IL"  # state is tax-relevant, preserved
        assert "zip" not in result

        # Financials rounded
        assert result["gross_income"] == 85000
        assert result["total_tax"] == 13000

        # Non-PII preserved
        assert result["filing_status"] == "single"
        assert result["dependents"] == 2
