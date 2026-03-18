"""PII scrubber for AI prompts.

Removes or generalizes personally identifiable information before
sending data to external AI providers (Anthropic, OpenAI).
"""


# Fields that are completely removed (contain direct identifiers)
_REMOVE_FIELDS = frozenset({
    # SSN / Tax ID
    'ssn', 'ein', 'social_security_number', 'taxpayer_id', 'tax_id',
    'itin', 'ssn_last4',
    # Email
    'email', 'email_address', 'contact_email',
    # Phone
    'phone', 'phone_number', 'mobile', 'cell', 'fax',
    # Address
    'address', 'street_address', 'address_line1', 'address_line2',
    'city', 'zip', 'zip_code', 'postal_code',
})

# Fields whose values are replaced with "the taxpayer"
_NAME_FIELDS = frozenset({
    'name', 'first_name', 'last_name', 'client_name', 'taxpayer_name',
    'spouse_name', 'spouse_first_name', 'spouse_last_name',
    'dependent_name', 'business_name', 'employer_name',
})

# Substrings that identify a numeric field as financial
_FINANCIAL_KEYWORDS = (
    'income', 'tax', 'savings', 'deduction', 'credit',
    'liability', 'payment', 'contribution', 'expense',
    'wage', 'salary', 'gain', 'loss', 'agi', 'refund',
)


def scrub_for_ai(data: dict) -> dict:
    """Replace PII with generic references before sending to AI providers.

    - Names → "the taxpayer"
    - SSN, email, phone, address fields → removed entirely
    - Dollar amounts with financial keywords → rounded to nearest $1,000
    - Nested dicts → recursively scrubbed
    """
    scrubbed = {}

    for key, val in data.items():
        lower_key = key.lower()

        # 1. Remove direct identifiers entirely
        if lower_key in _REMOVE_FIELDS:
            continue

        # 2. Replace name fields
        if lower_key in _NAME_FIELDS:
            scrubbed[key] = "the taxpayer"
            continue

        # 3. Recurse into nested dicts
        if isinstance(val, dict):
            scrubbed[key] = scrub_for_ai(val)
            continue

        # 4. Round financial amounts
        if isinstance(val, (int, float)) and any(k in lower_key for k in _FINANCIAL_KEYWORDS):
            scrubbed[key] = round(val / 1000) * 1000
            continue

        # 5. Pass everything else through unchanged
        scrubbed[key] = val

    return scrubbed
